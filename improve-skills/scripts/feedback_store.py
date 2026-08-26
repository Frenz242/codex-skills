#!/usr/bin/env python3
"""Local, privacy-conscious evidence store for Codex skill improvement.

The module intentionally uses only the Python standard library.  It is both a
small CLI and an importable library for deterministic tests.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Iterable, Sequence
import uuid
from datetime import datetime, timezone


SCHEMA_VERSION = 4
DATABASE_ENV = "CODEX_SKILL_FEEDBACK_DB"
PLUGIN_EVAL_ROOT_ENV = "PLUGIN_EVAL_ROOT"
DEFAULT_BUSY_TIMEOUT_MS = 1_500
MAX_WRITE_ATTEMPTS = 3
READ_ONLY_COMMANDS = {"health", "query", "history", "clusters", "plugin-eval-status"}

OBSERVATION_CATEGORIES = {
    "explicit-user-correction": "The user explicitly corrected the skill or its result.",
    "objective-failure": "A deterministic failure or violated acceptance criterion.",
    "validation-failure": "A validation command or artifact check failed.",
    "activation-false-negative": "A skill should have activated but apparently did not.",
    "activation-false-positive": "A skill activated for an unrelated request.",
    "missing-instruction": "A reusable instruction or invariant was absent.",
    "ambiguous-instruction": "An instruction supported materially different readings.",
    "scope-overlap": "Two skills or responsibilities collided.",
    "unexpected-environment": "A repeatable environment difference exposed a weakness.",
    "reusable-workaround": "A workaround appears reusable.",
    "unnecessary-complexity": "Existing guidance or machinery was not earning its cost.",
    "guardrail-success": "A guardrail materially prevented a problem.",
    "cross-cutting-principle": "Evidence may support a repository-wide principle.",
    "possible-new-skill": "A recurring workflow may deserve a distinct skill.",
    "regression-after-improvement": "A problem appeared after an intervention.",
}

EVIDENCE_TYPES = {
    "explicit-user-feedback": "Direct user correction or negative feedback.",
    "objective-check": "A test, assertion, acceptance criterion, or invalid artifact.",
    "independent-recurrence": "Repeated occurrence across independent runs.",
    "cross-context-recurrence": "Repeated occurrence across distinct contexts.",
    "activation-benchmark": "External activation or routing benchmark evidence.",
    "self-observation": "Agent observation without external confirmation.",
    "historical-backfill": "Evidence reconstructed from durable historical artifacts.",
    "positive-guardrail": "Evidence that existing behavior prevented harm or rework.",
    "speculative": "An unconfirmed idea retained only for later review.",
}

LIFECYCLE_STATES = {
    "observed",
    "candidate",
    "validating",
    "validated",
    "promotable",
    "implemented",
    "monitoring",
    "confirmed",
    "deferred",
    "invalid",
    "duplicate",
    "superseded",
    "regressed",
    "reverted",
    "declined",
}

ALLOWED_TRANSITIONS = {
    "observed": {"candidate", "deferred", "invalid", "duplicate", "declined"},
    "candidate": {"validating", "deferred", "invalid", "duplicate", "superseded", "declined"},
    "validating": {"validated", "deferred", "invalid", "regressed"},
    "validated": {"promotable", "deferred", "regressed", "declined"},
    "promotable": {"implemented", "deferred", "declined", "regressed"},
    "implemented": {"monitoring", "regressed", "reverted"},
    "monitoring": {"confirmed", "regressed", "reverted"},
    "confirmed": {"regressed", "reverted"},
    "deferred": {"candidate", "invalid", "declined", "superseded"},
    "regressed": {"validating", "reverted", "superseded"},
    "reverted": {"candidate", "superseded", "declined"},
    "duplicate": {"superseded"},
    "invalid": set(),
    "superseded": set(),
    "declined": {"candidate"},
}

SEVERITIES = {"info", "low", "medium", "high", "critical"}
REUSABILITY_VALUES = {"high", "medium", "low", "task-specific"}
CONFIDENCE_TIERS = {
    "explicit-user-correction",
    "objective-failure",
    "repeated-independent",
    "cross-context",
    "repeatable-activation",
    "repeated-self-observation",
    "isolated-self-observation",
    "speculative",
}
SUGGESTION_KINDS = {
    "existing-skill",
    "repository-rule",
    "shared-infrastructure",
    "new-skill",
    "no-action",
}
TARGET_KINDS = {"skill", "repository", "infrastructure", "new-skill"}
SOURCE_KINDS = {"skill", "agent"}
INVOCATION_MODES = {"explicit", "implicit", "unknown"}
OUTCOMES = {"success", "partial", "failure", "cancelled", "unknown"}
CLUSTER_KINDS = {
    "existing-skill",
    "repository-rule",
    "shared-infrastructure",
    "new-skill",
    "insufficient-evidence",
    "no-action",
}

OBSERVATION_KEYS = {
    "category",
    "evidence_type",
    "summary",
    "workaround_summary",
    "severity",
    "reusability",
    "confidence_tier",
    "suggestion_kind",
    "target_kind",
    "target_skill_path",
    "related_skill_paths",
    "candidate_name",
    "target_component",
    "positive",
}

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", re.I),
    re.compile(r"\b(?:github_pat_|gh[pousr]_|sk-|xox[baprs]-)[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(
        r"\b(?:api[_ -]?key|access[_ -]?token|auth[_ -]?token|password|passwd|client[_ -]?secret)"
        r"\s*[:=]\s*[^\s,;]{6,}",
        re.I,
    ),
]
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
URL_PATTERN = re.compile(r"\b(?:https?|ssh)://\S+", re.I)
WINDOWS_ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s]+")
UNC_PATH = re.compile(r"\\\\[^\\\s]+\\[^\s]+")
POSIX_PERSONAL_PATH = re.compile(r"(?<!\w)/(?:Users|home|var/tmp|tmp)/[^\s]+")
SAFE_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


class FeedbackStoreError(RuntimeError):
    """Base error with a user-safe message."""


class PrivacyError(FeedbackStoreError):
    """Raised when text is unsafe to persist."""


class BusyStoreError(FeedbackStoreError):
    """Raised after bounded retries cannot acquire the write lock."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str | None, field: str) -> str:
    if value is None:
        return utc_now()
    candidate = value.strip()
    try:
        datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FeedbackStoreError(f"{field} must be an ISO-8601 timestamp") from exc
    return candidate


def default_database_path(
    environ: dict[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    env = os.environ if environ is None else environ
    override = env.get(DATABASE_ENV)
    if override:
        return Path(override).expanduser().resolve()
    if home is None:
        profile = env.get("USERPROFILE")
        home = Path(profile) if profile else Path.home()
    return (home / ".agents" / "skill-feedback" / "skill-feedback.db").resolve()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def classify_database_path(path: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    lowered_parts = [part.lower() for part in resolved.parts]
    volatile_markers = [
        (".codex", "plugins", "cache"),
        (".agents", "plugins", "cache"),
        ("plugin", "cache"),
    ]
    for marker in volatile_markers:
        for index in range(0, len(lowered_parts) - len(marker) + 1):
            if tuple(lowered_parts[index : index + len(marker)]) == marker:
                return {"classification": "volatile-cache", "durable": False, "path": str(resolved)}

    temp_root = Path(tempfile.gettempdir()).resolve()
    if _is_relative_to(resolved, temp_root):
        return {"classification": "temporary", "durable": False, "path": str(resolved)}

    current = resolved.parent
    while True:
        if (current / ".git").exists():
            return {"classification": "git-controlled", "durable": False, "path": str(resolved)}
        if current.parent == current:
            break
        current = current.parent

    return {"classification": "stable-local", "durable": True, "path": str(resolved)}


def ensure_durable_database_path(path: Path, *, allow_unsafe_for_tests: bool = False) -> Path:
    resolved = path.expanduser().resolve()
    classification = classify_database_path(resolved)
    if not classification["durable"] and not allow_unsafe_for_tests:
        raise FeedbackStoreError(
            f"Feedback database path is {classification['classification']}; "
            "choose a stable path outside Git, caches, and temp directories"
        )
    return resolved


def _normalize_text(value: Any, field: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise FeedbackStoreError(f"{field} must be text")
    normalized = " ".join(value.split())
    if not normalized:
        raise FeedbackStoreError(f"{field} must not be empty")
    if len(normalized) > max_length:
        raise FeedbackStoreError(f"{field} exceeds {max_length} characters")
    for pattern in SECRET_PATTERNS:
        if pattern.search(normalized):
            raise PrivacyError(f"{field} contains secret-like material; generalize or remove it before persistence")
    if EMAIL_PATTERN.search(normalized):
        raise PrivacyError(f"{field} contains a full email address; generalize it before persistence")
    if URL_PATTERN.search(normalized):
        raise PrivacyError(f"{field} contains a URL; summaries must stay generalized")
    if (
        WINDOWS_ABSOLUTE_PATH.search(normalized)
        or UNC_PATH.search(normalized)
        or POSIX_PERSONAL_PATH.search(normalized)
    ):
        raise PrivacyError(f"{field} contains an unnecessary absolute path; describe the condition instead")
    return normalized


def _optional_text(value: Any, field: str, max_length: int) -> str | None:
    if value in (None, ""):
        return None
    return _normalize_text(value, field, max_length)


def _safe_slug(value: str, field: str) -> str:
    candidate = value.strip().lower()
    if not SAFE_SLUG.fullmatch(candidate):
        raise FeedbackStoreError(f"{field} must be a lowercase slug")
    return candidate


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_file(path: Path) -> str:
    return _hash_bytes(path.read_bytes())


def _bundle_hash(skill_dir: Path) -> str:
    digest = hashlib.sha256()
    excluded_parts = {".git", ".plugin-eval", "__pycache__", ".pytest_cache", "tests"}
    files = []
    for candidate in skill_dir.rglob("*"):
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(skill_dir)
        if any(part in excluded_parts for part in relative.parts) or candidate.suffix == ".pyc":
            continue
        files.append((relative.as_posix(), candidate))
    for relative, candidate in sorted(files):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(candidate.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _skill_name(skill_file: Path) -> str:
    text = skill_file.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise FeedbackStoreError(f"Skill file lacks YAML frontmatter: {skill_file}")
    end = text.find("\n---", 3)
    if end < 0:
        raise FeedbackStoreError(f"Skill file has unterminated YAML frontmatter: {skill_file}")
    match = re.search(r"(?m)^name:\s*[\"']?([^\"'\r\n]+)[\"']?\s*$", text[: end + 1])
    if not match:
        raise FeedbackStoreError(f"Skill file lacks a name field: {skill_file}")
    return match.group(1).strip()


def _run_git(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def discover_skill_metadata(skill_path: str | Path, privacy_salt: bytes) -> dict[str, Any]:
    supplied = Path(skill_path).expanduser().resolve()
    skill_file = supplied if supplied.name == "SKILL.md" else supplied / "SKILL.md"
    if not skill_file.is_file():
        raise FeedbackStoreError(f"Skill target does not exist: {skill_file}")
    skill_dir = skill_file.parent
    name = _skill_name(skill_file)
    repo_commit = None
    dirty = False
    root_result = _run_git(["rev-parse", "--show-toplevel"], skill_dir)
    repo_root: Path | None = None
    if root_result and root_result.returncode == 0:
        repo_root = Path(root_result.stdout.strip()).resolve()
        commit_result = _run_git(["rev-parse", "HEAD"], skill_dir)
        if commit_result and commit_result.returncode == 0:
            repo_commit = commit_result.stdout.strip()
        relative = skill_dir.relative_to(repo_root).as_posix()
        status_result = _run_git(["status", "--porcelain", "--", relative], repo_root)
        dirty = bool(status_result and status_result.returncode == 0 and status_result.stdout.strip())

    canonical = os.path.normcase(str(skill_dir)).encode("utf-8", errors="surrogatepass")
    path_hash = hmac.new(privacy_salt, canonical, hashlib.sha256).hexdigest()
    content_hash = _hash_file(skill_file)
    bundle_hash = _bundle_hash(skill_dir)
    version_material = json.dumps(
        {
            "name": name,
            "repo_commit": repo_commit,
            "content_hash": content_hash,
            "bundle_hash": bundle_hash,
            "dirty": dirty,
            "path_hash": path_hash,
        },
        sort_keys=True,
    ).encode("utf-8")
    return {
        "skill_name": name,
        "repo_commit": repo_commit,
        "content_hash": content_hash,
        "bundle_hash": bundle_hash,
        "dirty": dirty,
        "path_hash": path_hash,
        "version_key": _hash_bytes(version_material),
    }


def _connect(path: Path, busy_timeout_ms: int) -> sqlite3.Connection:
    connection = sqlite3.connect(
        path,
        timeout=max(busy_timeout_ms, 1) / 1000,
        isolation_level=None,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    return connection


def _write_with_retry(
    connection: sqlite3.Connection,
    operation: Callable[[sqlite3.Connection], Any],
    *,
    attempts: int = MAX_WRITE_ATTEMPTS,
) -> Any:
    last_error: sqlite3.OperationalError | None = None
    for attempt in range(attempts):
        try:
            connection.execute("BEGIN IMMEDIATE")
            result = operation(connection)
            connection.execute("COMMIT")
            return result
        except sqlite3.OperationalError as exc:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                raise
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.04 * (2**attempt))
        except Exception:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
    raise BusyStoreError(f"Feedback store stayed busy after {attempts} bounded attempts") from last_error


def _execute_script_in_transaction(connection: sqlite3.Connection, script: str) -> None:
    """Execute a migration script without sqlite3.executescript's implicit COMMIT."""

    statement = ""
    for line in script.splitlines():
        statement += line + "\n"
        if sqlite3.complete_statement(statement):
            sql = statement.strip()
            if sql:
                connection.execute(sql)
            statement = ""
    if statement.strip():
        raise FeedbackStoreError("Migration contains an incomplete SQL statement")


def _migration_one(connection: sqlite3.Connection) -> None:
    _execute_script_in_transaction(
        connection,
        """
        CREATE TABLE IF NOT EXISTS schema_metadata (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            version INTEGER NOT NULL
        );
        INSERT OR IGNORE INTO schema_metadata(singleton, version) VALUES (1, 0);

        CREATE TABLE IF NOT EXISTS migration_history (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS privacy_settings (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            context_salt BLOB NOT NULL
        );

        CREATE TABLE IF NOT EXISTS observation_categories (
            name TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS evidence_types (
            name TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS lifecycle_states (
            name TEXT PRIMARY KEY,
            terminal INTEGER NOT NULL DEFAULT 0 CHECK (terminal IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS skill_versions (
            version_id TEXT PRIMARY KEY,
            version_key TEXT NOT NULL UNIQUE,
            skill_name TEXT NOT NULL,
            skill_path_hash TEXT NOT NULL,
            repo_commit TEXT,
            content_hash TEXT NOT NULL,
            bundle_hash TEXT NOT NULL,
            dirty INTEGER NOT NULL CHECK (dirty IN (0, 1)),
            captured_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS skill_runs (
            run_id TEXT PRIMARY KEY,
            skill_version_id TEXT NOT NULL REFERENCES skill_versions(version_id),
            started_at TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            invocation_mode TEXT NOT NULL CHECK (invocation_mode IN ('explicit', 'implicit', 'unknown')),
            outcome TEXT NOT NULL CHECK (outcome IN ('success', 'partial', 'failure', 'cancelled', 'unknown')),
            run_kind TEXT NOT NULL DEFAULT 'live' CHECK (run_kind IN ('live', 'backfill')),
            context_hash TEXT,
            observation_count INTEGER NOT NULL DEFAULT 0 CHECK (observation_count >= 0),
            source_key TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS observations (
            observation_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES skill_runs(run_id),
            primary_target_kind TEXT NOT NULL CHECK (
                primary_target_kind IN ('skill', 'repository', 'infrastructure', 'new-skill')
            ),
            primary_skill_version_id TEXT REFERENCES skill_versions(version_id),
            category TEXT NOT NULL REFERENCES observation_categories(name),
            evidence_type TEXT NOT NULL REFERENCES evidence_types(name),
            summary TEXT NOT NULL,
            workaround_summary TEXT,
            severity TEXT NOT NULL CHECK (severity IN ('info', 'low', 'medium', 'high', 'critical')),
            reusability TEXT NOT NULL CHECK (reusability IN ('high', 'medium', 'low', 'task-specific')),
            confidence_tier TEXT NOT NULL,
            suggestion_kind TEXT NOT NULL CHECK (
                suggestion_kind IN (
                    'existing-skill', 'repository-rule', 'shared-infrastructure',
                    'new-skill', 'no-action'
                )
            ),
            state TEXT NOT NULL DEFAULT 'observed' REFERENCES lifecycle_states(name),
            candidate_name TEXT,
            positive_evidence INTEGER NOT NULL DEFAULT 0 CHECK (positive_evidence IN (0, 1)),
            summary_fingerprint TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(run_id, summary_fingerprint),
            CHECK (
                (primary_target_kind = 'skill' AND primary_skill_version_id IS NOT NULL)
                OR (primary_target_kind <> 'skill' AND primary_skill_version_id IS NULL)
            )
        );

        CREATE TABLE IF NOT EXISTS observation_related_skills (
            observation_id TEXT NOT NULL REFERENCES observations(observation_id),
            skill_version_id TEXT NOT NULL REFERENCES skill_versions(version_id),
            PRIMARY KEY (observation_id, skill_version_id)
        );

        CREATE TABLE IF NOT EXISTS observation_state_history (
            history_id TEXT PRIMARY KEY,
            observation_id TEXT NOT NULL REFERENCES observations(observation_id),
            from_state TEXT,
            to_state TEXT NOT NULL REFERENCES lifecycle_states(name),
            reason TEXT NOT NULL,
            changed_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_observations_run ON observations(run_id);
        CREATE INDEX IF NOT EXISTS idx_observations_state ON observations(state);
        CREATE INDEX IF NOT EXISTS idx_observations_target ON observations(primary_skill_version_id);
        CREATE INDEX IF NOT EXISTS idx_runs_skill_version ON skill_runs(skill_version_id);
        """
    )
    connection.execute(
        "INSERT OR IGNORE INTO privacy_settings(singleton, context_salt) VALUES (1, ?)",
        (secrets.token_bytes(32),),
    )
    connection.executemany(
        "INSERT OR IGNORE INTO observation_categories(name, description) VALUES (?, ?)",
        sorted(OBSERVATION_CATEGORIES.items()),
    )
    connection.executemany(
        "INSERT OR IGNORE INTO evidence_types(name, description) VALUES (?, ?)",
        sorted(EVIDENCE_TYPES.items()),
    )
    terminal = {"invalid", "duplicate", "superseded", "confirmed"}
    connection.executemany(
        "INSERT OR IGNORE INTO lifecycle_states(name, terminal) VALUES (?, ?)",
        [(state, int(state in terminal)) for state in sorted(LIFECYCLE_STATES)],
    )


def _migration_two(connection: sqlite3.Connection) -> None:
    _execute_script_in_transaction(
        connection,
        """
        CREATE TABLE IF NOT EXISTS candidate_clusters (
            cluster_id TEXT PRIMARY KEY,
            problem_key TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL CHECK (
                kind IN (
                    'existing-skill', 'repository-rule', 'shared-infrastructure',
                    'new-skill', 'insufficient-evidence', 'no-action'
                )
            ),
            canonical_problem TEXT NOT NULL,
            working_name TEXT,
            state TEXT NOT NULL DEFAULT 'candidate' REFERENCES lifecycle_states(name),
            derived_priority TEXT CHECK (derived_priority IN ('low', 'normal', 'high') OR derived_priority IS NULL),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS cluster_aliases (
            normalized_alias TEXT PRIMARY KEY,
            cluster_id TEXT NOT NULL REFERENCES candidate_clusters(cluster_id),
            display_alias TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS cluster_observations (
            cluster_id TEXT NOT NULL REFERENCES candidate_clusters(cluster_id),
            observation_id TEXT NOT NULL REFERENCES observations(observation_id),
            relationship TEXT NOT NULL CHECK (relationship IN ('support', 'counter-evidence', 'duplicate')),
            attached_at TEXT NOT NULL,
            PRIMARY KEY (cluster_id, observation_id)
        );

        CREATE TABLE IF NOT EXISTS cluster_state_history (
            history_id TEXT PRIMARY KEY,
            cluster_id TEXT NOT NULL REFERENCES candidate_clusters(cluster_id),
            from_state TEXT,
            to_state TEXT NOT NULL REFERENCES lifecycle_states(name),
            reason TEXT NOT NULL,
            changed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS evaluations (
            evaluation_id TEXT PRIMARY KEY,
            cluster_id TEXT NOT NULL REFERENCES candidate_clusters(cluster_id),
            target_skill_version_id TEXT NOT NULL REFERENCES skill_versions(version_id),
            backend TEXT NOT NULL CHECK (backend IN ('plugin-eval', 'degraded')),
            criteria_hash TEXT NOT NULL,
            criteria_label TEXT NOT NULL,
            holdout_hash TEXT,
            holdout_label TEXT,
            status TEXT NOT NULL CHECK (status IN ('frozen', 'running', 'discarded', 'recommended', 'promotable')),
            decision TEXT CHECK (decision IN ('discard', 'recommend', 'keep') OR decision IS NULL),
            after_skill_version_id TEXT REFERENCES skill_versions(version_id),
            created_at TEXT NOT NULL,
            frozen_at TEXT NOT NULL,
            decided_at TEXT
        );

        CREATE TABLE IF NOT EXISTS evaluation_runs (
            evaluation_run_id TEXT PRIMARY KEY,
            evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id),
            phase TEXT NOT NULL CHECK (phase IN ('baseline', 'experiment', 'regression', 'holdout')),
            iteration INTEGER NOT NULL DEFAULT 1 CHECK (iteration BETWEEN 1 AND 3),
            result_hash TEXT NOT NULL,
            result_label TEXT NOT NULL,
            result_status TEXT NOT NULL CHECK (result_status IN ('pass', 'fail', 'mixed')),
            notes TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(evaluation_id, phase, iteration)
        );

        CREATE TABLE IF NOT EXISTS entity_links (
            link_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL CHECK (entity_type IN ('observation', 'cluster', 'evaluation')),
            entity_id TEXT NOT NULL,
            link_type TEXT NOT NULL CHECK (link_type IN ('issue', 'pr', 'merge', 'outcome')),
            external_ref TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(entity_type, entity_id, link_type, external_ref)
        );

        CREATE TABLE IF NOT EXISTS backfill_sources (
            source_key TEXT PRIMARY KEY,
            source_type TEXT NOT NULL CHECK (source_type IN ('git-history', 'github', 'artifact', 'other')),
            completed_at TEXT NOT NULL,
            run_id TEXT NOT NULL REFERENCES skill_runs(run_id),
            observation_count INTEGER NOT NULL CHECK (observation_count >= 0)
        );

        CREATE INDEX IF NOT EXISTS idx_cluster_observations_observation ON cluster_observations(observation_id);
        CREATE INDEX IF NOT EXISTS idx_evaluation_runs_evaluation ON evaluation_runs(evaluation_id);
        """
    )


def _migration_three(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_runs_backfill_source
        ON skill_runs(source_key)
        WHERE run_kind = 'backfill' AND source_key IS NOT NULL
        """
    )


def _migration_four(connection: sqlite3.Connection) -> None:
    _execute_script_in_transaction(
        connection,
        """
        CREATE TABLE skill_runs_v4 (
            run_id TEXT PRIMARY KEY,
            skill_version_id TEXT REFERENCES skill_versions(version_id),
            source_kind TEXT NOT NULL CHECK (source_kind IN ('skill', 'agent')),
            started_at TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            invocation_mode TEXT NOT NULL CHECK (invocation_mode IN ('explicit', 'implicit', 'unknown')),
            outcome TEXT NOT NULL CHECK (outcome IN ('success', 'partial', 'failure', 'cancelled', 'unknown')),
            run_kind TEXT NOT NULL DEFAULT 'live' CHECK (run_kind IN ('live', 'backfill')),
            context_hash TEXT,
            observation_count INTEGER NOT NULL DEFAULT 0 CHECK (observation_count >= 0),
            source_key TEXT,
            created_at TEXT NOT NULL,
            CHECK (
                (source_kind = 'skill' AND skill_version_id IS NOT NULL)
                OR (source_kind = 'agent' AND skill_version_id IS NULL)
            )
        );

        INSERT INTO skill_runs_v4(
            run_id, skill_version_id, source_kind, started_at, completed_at,
            invocation_mode, outcome, run_kind, context_hash,
            observation_count, source_key, created_at
        )
        SELECT
            run_id, skill_version_id, 'skill', started_at, completed_at,
            invocation_mode, outcome, run_kind, context_hash,
            observation_count, source_key, created_at
        FROM skill_runs;

        DROP TABLE skill_runs;
        ALTER TABLE skill_runs_v4 RENAME TO skill_runs;

        CREATE INDEX idx_runs_skill_version ON skill_runs(skill_version_id);
        CREATE INDEX idx_runs_source_kind ON skill_runs(source_kind);
        CREATE UNIQUE INDEX idx_runs_backfill_source
        ON skill_runs(source_key)
        WHERE run_kind = 'backfill' AND source_key IS NOT NULL;

        ALTER TABLE observations ADD COLUMN target_component TEXT
            CHECK (target_component IS NULL OR primary_target_kind = 'infrastructure');
        CREATE INDEX idx_observations_target_component ON observations(target_component);
        """,
    )


MIGRATIONS = {1: _migration_one, 2: _migration_two, 3: _migration_three, 4: _migration_four}


def open_store(
    db_path: str | Path | None = None,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    allow_unsafe_for_tests: bool = False,
    target_schema_version: int = SCHEMA_VERSION,
) -> tuple[sqlite3.Connection, Path]:
    if target_schema_version < 1 or target_schema_version > SCHEMA_VERSION:
        raise FeedbackStoreError(f"Unsupported target schema version: {target_schema_version}")
    path = ensure_durable_database_path(
        default_database_path() if db_path is None else Path(db_path),
        allow_unsafe_for_tests=allow_unsafe_for_tests,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = _connect(path, busy_timeout_ms)
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")

    def migrate(conn: sqlite3.Connection) -> None:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_metadata ("
            "singleton INTEGER PRIMARY KEY CHECK (singleton = 1), "
            "version INTEGER NOT NULL)"
        )
        conn.execute("INSERT OR IGNORE INTO schema_metadata(singleton, version) VALUES (1, 0)")
        current = int(conn.execute("SELECT version FROM schema_metadata WHERE singleton = 1").fetchone()[0])
        for version in range(current + 1, target_schema_version + 1):
            MIGRATIONS[version](conn)
            conn.execute("UPDATE schema_metadata SET version = ? WHERE singleton = 1", (version,))
            conn.execute(
                "INSERT OR REPLACE INTO migration_history(version, applied_at) VALUES (?, ?)",
                (version, utc_now()),
            )

    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        _write_with_retry(connection, migrate)
    finally:
        connection.execute("PRAGMA foreign_keys = ON")
    violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise FeedbackStoreError("Schema migration produced invalid foreign-key references")
    return connection, path


def open_store_read_only(
    db_path: str | Path | None = None,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    allow_unsafe_for_tests: bool = False,
) -> tuple[sqlite3.Connection, Path]:
    path = ensure_durable_database_path(
        default_database_path() if db_path is None else Path(db_path),
        allow_unsafe_for_tests=allow_unsafe_for_tests,
    )
    if not path.is_file():
        raise FeedbackStoreError("Feedback store does not exist; read-only mode will not initialize it")
    connection = sqlite3.connect(
        f"file:{path.as_posix()}?mode=ro",
        uri=True,
        timeout=max(busy_timeout_ms, 1) / 1000,
        isolation_level=None,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    connection.execute("PRAGMA query_only = ON")
    return connection, path


def _privacy_salt(connection: sqlite3.Connection) -> bytes:
    row = connection.execute("SELECT context_salt FROM privacy_settings WHERE singleton = 1").fetchone()
    if not row:
        raise FeedbackStoreError("Feedback store privacy settings are missing")
    return bytes(row[0])


def _context_hash(connection: sqlite3.Connection, context_path: str | Path | None) -> str | None:
    if context_path is None:
        return None
    canonical = os.path.normcase(str(Path(context_path).expanduser().resolve())).encode(
        "utf-8", errors="surrogatepass"
    )
    return hmac.new(_privacy_salt(connection), canonical, hashlib.sha256).hexdigest()


def _upsert_skill_version(connection: sqlite3.Connection, metadata: dict[str, Any]) -> str:
    existing = connection.execute(
        "SELECT version_id FROM skill_versions WHERE version_key = ?", (metadata["version_key"],)
    ).fetchone()
    if existing:
        return str(existing[0])
    version_id = str(uuid.uuid4())
    connection.execute(
        """
        INSERT INTO skill_versions(
            version_id, version_key, skill_name, skill_path_hash, repo_commit,
            content_hash, bundle_hash, dirty, captured_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version_id,
            metadata["version_key"],
            metadata["skill_name"],
            metadata["path_hash"],
            metadata["repo_commit"],
            metadata["content_hash"],
            metadata["bundle_hash"],
            int(metadata["dirty"]),
            utc_now(),
        ),
    )
    return version_id


def _observation_fingerprint(spec: dict[str, Any], target_version_id: str | None) -> str:
    material = {
        "target_kind": spec["target_kind"],
        "target_component": spec.get("target_component"),
        "target_version": target_version_id,
        "category": spec["category"],
        "evidence_type": spec["evidence_type"],
        "summary": spec["summary"].casefold(),
        "suggestion_kind": spec["suggestion_kind"],
    }
    return _hash_bytes(json.dumps(material, sort_keys=True).encode("utf-8"))


def validate_observation_spec(spec: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise FeedbackStoreError("Each observation must be a JSON object")
    unknown = set(spec) - OBSERVATION_KEYS
    if unknown:
        raise FeedbackStoreError(f"Unknown observation fields are not persisted: {', '.join(sorted(unknown))}")
    required = {
        "category",
        "evidence_type",
        "summary",
        "severity",
        "reusability",
        "confidence_tier",
        "suggestion_kind",
        "target_kind",
    }
    missing = required - set(spec)
    if missing:
        raise FeedbackStoreError(f"Observation is missing required fields: {', '.join(sorted(missing))}")

    normalized = dict(spec)
    normalized["category"] = _safe_slug(str(spec["category"]), "category")
    normalized["evidence_type"] = _safe_slug(str(spec["evidence_type"]), "evidence_type")
    normalized["summary"] = _normalize_text(spec["summary"], "summary", 500)
    normalized["workaround_summary"] = _optional_text(
        spec.get("workaround_summary"), "workaround_summary", 300
    )
    normalized["severity"] = str(spec["severity"])
    normalized["reusability"] = str(spec["reusability"])
    normalized["confidence_tier"] = str(spec["confidence_tier"])
    normalized["suggestion_kind"] = str(spec["suggestion_kind"])
    normalized["target_kind"] = str(spec["target_kind"])
    normalized["positive"] = bool(spec.get("positive", False))
    normalized["candidate_name"] = (
        _safe_slug(str(spec["candidate_name"]), "candidate_name") if spec.get("candidate_name") else None
    )
    normalized["target_component"] = (
        _safe_slug(str(spec["target_component"]), "target_component")
        if spec.get("target_component")
        else None
    )
    related = spec.get("related_skill_paths", [])
    if not isinstance(related, list) or not all(isinstance(item, str) for item in related):
        raise FeedbackStoreError("related_skill_paths must be a JSON array of paths")
    normalized["related_skill_paths"] = related

    if normalized["severity"] not in SEVERITIES:
        raise FeedbackStoreError(f"Invalid severity: {normalized['severity']}")
    if normalized["reusability"] not in REUSABILITY_VALUES:
        raise FeedbackStoreError(f"Invalid reusability: {normalized['reusability']}")
    if normalized["confidence_tier"] not in CONFIDENCE_TIERS:
        raise FeedbackStoreError(f"Invalid confidence_tier: {normalized['confidence_tier']}")
    if normalized["suggestion_kind"] not in SUGGESTION_KINDS:
        raise FeedbackStoreError(f"Invalid suggestion_kind: {normalized['suggestion_kind']}")
    if normalized["target_kind"] not in TARGET_KINDS:
        raise FeedbackStoreError(f"Invalid target_kind: {normalized['target_kind']}")
    if normalized["target_kind"] == "skill":
        if spec.get("candidate_name"):
            raise FeedbackStoreError("candidate_name is only valid for new-skill targets")
        if normalized["target_component"]:
            raise FeedbackStoreError("target_component is only valid for infrastructure targets")
    elif spec.get("target_skill_path"):
        raise FeedbackStoreError("target_skill_path is only valid for skill targets")
    elif normalized["target_kind"] != "infrastructure" and normalized["target_component"]:
        raise FeedbackStoreError("target_component is only valid for infrastructure targets")
    if normalized["target_kind"] == "new-skill" and not normalized["candidate_name"]:
        raise FeedbackStoreError("new-skill observations require candidate_name")
    return normalized


def _should_skip_task_specific(spec: dict[str, Any]) -> bool:
    return (
        spec["reusability"] == "task-specific"
        and spec["severity"] in {"info", "low"}
        and spec["evidence_type"] not in {"explicit-user-feedback", "objective-check"}
    )


def _validate_observation_for_source(spec: dict[str, Any], source_kind: str) -> None:
    if (
        source_kind == "agent"
        and spec["target_kind"] == "skill"
        and spec["category"] == "activation-false-negative"
        and spec["evidence_type"]
        not in {"explicit-user-feedback", "activation-benchmark", "objective-check"}
    ):
        raise FeedbackStoreError(
            "Agent-sourced activation-false-negative evidence requires explicit user feedback, "
            "an external activation benchmark, or an objective check"
        )


def _prepare_observations(
    connection: sqlite3.Connection,
    run_skill_path: str | Path | None,
    source_kind: str,
    observations: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    salt = _privacy_salt(connection)
    prepared: list[dict[str, Any]] = []
    skipped_task_specific = 0
    skipped_duplicates = 0
    seen: set[str] = set()
    for raw in observations:
        spec = validate_observation_spec(raw)
        _validate_observation_for_source(spec, source_kind)
        if _should_skip_task_specific(spec):
            skipped_task_specific += 1
            continue
        target_metadata = None
        if spec["target_kind"] == "skill":
            target_path = spec.get("target_skill_path") or run_skill_path
            if target_path is None:
                raise FeedbackStoreError(
                    "Agent-sourced skill targets require target_skill_path"
                )
            target_metadata = discover_skill_metadata(target_path, salt)
        related_metadata = [discover_skill_metadata(item, salt) for item in spec["related_skill_paths"]]
        provisional_target = target_metadata["version_key"] if target_metadata else None
        fingerprint = _observation_fingerprint(spec, provisional_target)
        if fingerprint in seen:
            skipped_duplicates += 1
            continue
        seen.add(fingerprint)
        prepared.append(
            {
                "spec": spec,
                "target_metadata": target_metadata,
                "related_metadata": related_metadata,
                "fingerprint": fingerprint,
            }
        )
    return prepared, skipped_task_specific, skipped_duplicates


def record_run(
    connection: sqlite3.Connection,
    *,
    skill_path: str | Path | None = None,
    source_kind: str | None = None,
    invocation_mode: str = "unknown",
    outcome: str = "unknown",
    started_at: str | None = None,
    completed_at: str | None = None,
    context_path: str | Path | None = None,
    observations: Sequence[dict[str, Any]] = (),
    run_kind: str = "live",
    source_key: str | None = None,
) -> dict[str, Any]:
    if source_kind is None:
        if skill_path is None:
            raise FeedbackStoreError(
                "record-run requires --source-kind when --skill-path is omitted"
            )
        source_kind = "skill"
    if source_kind not in SOURCE_KINDS:
        raise FeedbackStoreError(f"Invalid source_kind: {source_kind}")
    if source_kind == "skill" and skill_path is None:
        raise FeedbackStoreError("Skill-sourced runs require skill_path")
    if source_kind == "agent" and skill_path is not None:
        raise FeedbackStoreError("Agent-sourced runs must not include skill_path")
    if invocation_mode not in INVOCATION_MODES:
        raise FeedbackStoreError(f"Invalid invocation_mode: {invocation_mode}")
    if outcome not in OUTCOMES:
        raise FeedbackStoreError(f"Invalid outcome: {outcome}")
    if run_kind not in {"live", "backfill"}:
        raise FeedbackStoreError(f"Invalid run_kind: {run_kind}")
    if run_kind == "backfill" and not source_key:
        raise FeedbackStoreError("Backfill runs require a permanent source_key")
    if run_kind == "live" and source_key is not None:
        raise FeedbackStoreError("source_key is reserved for backfill runs")
    start = _parse_timestamp(started_at, "started_at")
    completed = _parse_timestamp(completed_at, "completed_at")
    if datetime.fromisoformat(start.replace("Z", "+00:00")) > datetime.fromisoformat(
        completed.replace("Z", "+00:00")
    ):
        raise FeedbackStoreError("started_at must not be after completed_at")

    salt = _privacy_salt(connection)
    run_metadata = discover_skill_metadata(skill_path, salt) if skill_path is not None else None
    prepared, skipped_task_specific, skipped_duplicates = _prepare_observations(
        connection, skill_path, source_kind, observations
    )
    if context_path is None and any(
        item["spec"]["target_kind"] == "repository" for item in prepared
    ):
        raise FeedbackStoreError("Repository-targeted observations require context_path")
    context_digest = _context_hash(connection, context_path)
    run_id = str(uuid.uuid4())
    created_at = utc_now()

    def write(conn: sqlite3.Connection) -> dict[str, Any]:
        run_version_id = _upsert_skill_version(conn, run_metadata) if run_metadata else None
        run_columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(skill_runs)")}
        if "source_kind" in run_columns:
            conn.execute(
                """
                INSERT INTO skill_runs(
                    run_id, skill_version_id, source_kind, started_at, completed_at,
                    invocation_mode, outcome, run_kind, context_hash,
                    observation_count, source_key, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    run_version_id,
                    source_kind,
                    start,
                    completed,
                    invocation_mode,
                    outcome,
                    run_kind,
                    context_digest,
                    len(prepared),
                    source_key,
                    created_at,
                ),
            )
        else:
            if source_kind != "skill":
                raise FeedbackStoreError("Agent-sourced runs require schema version 4 or newer")
            conn.execute(
                """
                INSERT INTO skill_runs(
                    run_id, skill_version_id, started_at, completed_at,
                    invocation_mode, outcome, run_kind, context_hash,
                    observation_count, source_key, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    run_version_id,
                    start,
                    completed,
                    invocation_mode,
                    outcome,
                    run_kind,
                    context_digest,
                    len(prepared),
                    source_key,
                    created_at,
                ),
            )
        observation_ids: list[str] = []
        for item in prepared:
            spec = item["spec"]
            target_version_id = (
                _upsert_skill_version(conn, item["target_metadata"])
                if item["target_metadata"]
                else None
            )
            observation_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO observations(
                    observation_id, run_id, primary_target_kind,
                    primary_skill_version_id, category, evidence_type,
                    summary, workaround_summary, severity, reusability,
                    confidence_tier, suggestion_kind, state, candidate_name,
                    target_component, positive_evidence, summary_fingerprint, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'observed', ?, ?, ?, ?, ?)
                """,
                (
                    observation_id,
                    run_id,
                    spec["target_kind"],
                    target_version_id,
                    spec["category"],
                    spec["evidence_type"],
                    spec["summary"],
                    spec["workaround_summary"],
                    spec["severity"],
                    spec["reusability"],
                    spec["confidence_tier"],
                    spec["suggestion_kind"],
                    spec["candidate_name"],
                    spec["target_component"],
                    int(spec["positive"]),
                    item["fingerprint"],
                    created_at,
                ),
            )
            conn.execute(
                """
                INSERT INTO observation_state_history(
                    history_id, observation_id, from_state, to_state, reason, changed_at
                ) VALUES (?, ?, NULL, 'observed', 'Initial state assigned transactionally', ?)
                """,
                (str(uuid.uuid4()), observation_id, created_at),
            )
            for related in item["related_metadata"]:
                related_version = _upsert_skill_version(conn, related)
                conn.execute(
                    "INSERT OR IGNORE INTO observation_related_skills(observation_id, skill_version_id) VALUES (?, ?)",
                    (observation_id, related_version),
                )
            observation_ids.append(observation_id)
        return {
            "ok": True,
            "runId": run_id,
            "sourceKind": source_kind,
            "skill": run_metadata["skill_name"] if run_metadata else None,
            "repoCommit": run_metadata["repo_commit"] if run_metadata else None,
            "contentHash": run_metadata["content_hash"] if run_metadata else None,
            "bundleHash": run_metadata["bundle_hash"] if run_metadata else None,
            "dirty": bool(run_metadata["dirty"]) if run_metadata else None,
            "observationIds": observation_ids,
            "observationCount": len(observation_ids),
            "skippedTaskSpecific": skipped_task_specific,
            "skippedDuplicates": skipped_duplicates,
        }

    return _write_with_retry(connection, write)


def record_observation(
    connection: sqlite3.Connection,
    *,
    run_id: str,
    observation: dict[str, Any],
) -> dict[str, Any]:
    run = connection.execute(
        """
        SELECT r.run_id, r.source_kind, r.context_hash, v.skill_path_hash, v.skill_name
        FROM skill_runs r LEFT JOIN skill_versions v ON v.version_id = r.skill_version_id
        WHERE r.run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if not run:
        raise FeedbackStoreError(f"Run does not exist: {run_id}")
    spec = validate_observation_spec(observation)
    _validate_observation_for_source(spec, str(run["source_kind"]))
    if spec["target_kind"] == "repository" and run["context_hash"] is None:
        raise FeedbackStoreError("Repository-targeted observations require run context_path")
    if _should_skip_task_specific(spec):
        return {"ok": True, "runId": run_id, "skippedTaskSpecific": True, "observationId": None}
    if spec["target_kind"] == "skill" and not spec.get("target_skill_path"):
        raise FeedbackStoreError(
            "record requires target_skill_path for skill targets; record-run may default to the executing skill"
        )
    salt = _privacy_salt(connection)
    target_metadata = (
        discover_skill_metadata(spec["target_skill_path"], salt)
        if spec["target_kind"] == "skill"
        else None
    )
    related_metadata = [discover_skill_metadata(item, salt) for item in spec["related_skill_paths"]]
    fingerprint = _observation_fingerprint(
        spec, target_metadata["version_key"] if target_metadata else None
    )
    observation_id = str(uuid.uuid4())
    created_at = utc_now()

    def write(conn: sqlite3.Connection) -> dict[str, Any]:
        target_version_id = _upsert_skill_version(conn, target_metadata) if target_metadata else None
        try:
            conn.execute(
                """
                INSERT INTO observations(
                    observation_id, run_id, primary_target_kind,
                    primary_skill_version_id, category, evidence_type,
                    summary, workaround_summary, severity, reusability,
                    confidence_tier, suggestion_kind, state, candidate_name,
                    target_component, positive_evidence, summary_fingerprint, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'observed', ?, ?, ?, ?, ?)
                """,
                (
                    observation_id,
                    run_id,
                    spec["target_kind"],
                    target_version_id,
                    spec["category"],
                    spec["evidence_type"],
                    spec["summary"],
                    spec["workaround_summary"],
                    spec["severity"],
                    spec["reusability"],
                    spec["confidence_tier"],
                    spec["suggestion_kind"],
                    spec["candidate_name"],
                    spec["target_component"],
                    int(spec["positive"]),
                    fingerprint,
                    created_at,
                ),
            )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed: observations.run_id, observations.summary_fingerprint" in str(exc):
                return {"ok": True, "runId": run_id, "skippedDuplicate": True, "observationId": None}
            raise
        conn.execute(
            """
            INSERT INTO observation_state_history(
                history_id, observation_id, from_state, to_state, reason, changed_at
            ) VALUES (?, ?, NULL, 'observed', 'Initial state assigned transactionally', ?)
            """,
            (str(uuid.uuid4()), observation_id, created_at),
        )
        for related in related_metadata:
            related_id = _upsert_skill_version(conn, related)
            conn.execute(
                "INSERT OR IGNORE INTO observation_related_skills(observation_id, skill_version_id) VALUES (?, ?)",
                (observation_id, related_id),
            )
        conn.execute(
            "UPDATE skill_runs SET observation_count = observation_count + 1 WHERE run_id = ?",
            (run_id,),
        )
        return {"ok": True, "runId": run_id, "observationId": observation_id}

    return _write_with_retry(connection, write)


def register_lookup(
    connection: sqlite3.Connection,
    *,
    table: str,
    name: str,
    description: str,
) -> dict[str, Any]:
    allowed = {"observation_categories", "evidence_types"}
    if table not in allowed:
        raise FeedbackStoreError("Unsupported lookup table")
    safe_name = _safe_slug(name, "name")
    safe_description = _normalize_text(description, "description", 300)

    def write(conn: sqlite3.Connection) -> dict[str, Any]:
        conn.execute(
            f"INSERT OR IGNORE INTO {table}(name, description, active) VALUES (?, ?, 1)",
            (safe_name, safe_description),
        )
        return {"ok": True, "table": table, "name": safe_name}

    return _write_with_retry(connection, write)


def mark_state(
    connection: sqlite3.Connection,
    *,
    entity_type: str,
    entity_id: str,
    new_state: str,
    reason: str,
) -> dict[str, Any]:
    if new_state not in LIFECYCLE_STATES:
        raise FeedbackStoreError(f"Invalid lifecycle state: {new_state}")
    safe_reason = _normalize_text(reason, "reason", 300)
    if entity_type == "observation":
        table, id_column, history_table = "observations", "observation_id", "observation_state_history"
    elif entity_type == "cluster":
        table, id_column, history_table = "candidate_clusters", "cluster_id", "cluster_state_history"
    else:
        raise FeedbackStoreError("entity_type must be observation or cluster")

    def write(conn: sqlite3.Connection) -> dict[str, Any]:
        row = conn.execute(
            f"SELECT state FROM {table} WHERE {id_column} = ?", (entity_id,)
        ).fetchone()
        if not row:
            raise FeedbackStoreError(f"{entity_type} does not exist: {entity_id}")
        current = str(row[0])
        if current == new_state:
            return {"ok": True, "entityType": entity_type, "entityId": entity_id, "state": current}
        if new_state not in ALLOWED_TRANSITIONS.get(current, set()):
            raise FeedbackStoreError(f"Invalid lifecycle transition: {current} -> {new_state}")
        conn.execute(f"UPDATE {table} SET state = ? WHERE {id_column} = ?", (new_state, entity_id))
        history_id = str(uuid.uuid4())
        entity_history_column = "observation_id" if entity_type == "observation" else "cluster_id"
        conn.execute(
            f"""
            INSERT INTO {history_table}(
                history_id, {entity_history_column}, from_state, to_state, reason, changed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (history_id, entity_id, current, new_state, safe_reason, utc_now()),
        )
        return {
            "ok": True,
            "entityType": entity_type,
            "entityId": entity_id,
            "fromState": current,
            "state": new_state,
            "historyId": history_id,
        }

    return _write_with_retry(connection, write)


def _normalize_alias(value: str) -> str:
    words = re.findall(r"[a-z0-9]+", value.casefold())
    normalized = "-".join(sorted(dict.fromkeys(words)))
    return normalized[:200]


def cluster_observations(
    connection: sqlite3.Connection,
    *,
    problem_key: str,
    kind: str,
    canonical_problem: str,
    observation_ids: Sequence[str],
    working_names: Sequence[str] = (),
    relationship: str = "support",
) -> dict[str, Any]:
    safe_key = _safe_slug(problem_key, "problem_key")
    if kind not in CLUSTER_KINDS:
        raise FeedbackStoreError(f"Invalid cluster kind: {kind}")
    if relationship not in {"support", "counter-evidence", "duplicate"}:
        raise FeedbackStoreError(f"Invalid cluster relationship: {relationship}")
    safe_problem = _normalize_text(canonical_problem, "canonical_problem", 500)
    safe_names = [_normalize_text(name, "working_name", 120) for name in working_names]
    if not observation_ids:
        raise FeedbackStoreError("At least one observation_id is required")
    created_at = utc_now()

    def write(conn: sqlite3.Connection) -> dict[str, Any]:
        row = conn.execute(
            "SELECT cluster_id, kind FROM candidate_clusters WHERE problem_key = ?", (safe_key,)
        ).fetchone()
        if row:
            cluster_id = str(row[0])
            if str(row[1]) != kind:
                raise FeedbackStoreError(
                    f"Existing cluster {safe_key} has kind {row[1]}, not {kind}"
                )
        else:
            cluster_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO candidate_clusters(
                    cluster_id, problem_key, kind, canonical_problem, working_name,
                    state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'candidate', ?, ?)
                """,
                (
                    cluster_id,
                    safe_key,
                    kind,
                    safe_problem,
                    safe_names[0] if safe_names else None,
                    created_at,
                    created_at,
                ),
            )
            conn.execute(
                """
                INSERT INTO cluster_state_history(
                    history_id, cluster_id, from_state, to_state, reason, changed_at
                ) VALUES (?, ?, NULL, 'candidate', 'Initial candidate state assigned transactionally', ?)
                """,
                (str(uuid.uuid4()), cluster_id, created_at),
            )
        for observation_id in observation_ids:
            exists = conn.execute(
                "SELECT 1 FROM observations WHERE observation_id = ?", (observation_id,)
            ).fetchone()
            if not exists:
                raise FeedbackStoreError(f"Observation does not exist: {observation_id}")
            conn.execute(
                """
                INSERT OR IGNORE INTO cluster_observations(
                    cluster_id, observation_id, relationship, attached_at
                ) VALUES (?, ?, ?, ?)
                """,
                (cluster_id, observation_id, relationship, created_at),
            )
        for display_name in safe_names:
            normalized = _normalize_alias(display_name)
            alias_row = conn.execute(
                "SELECT cluster_id FROM cluster_aliases WHERE normalized_alias = ?", (normalized,)
            ).fetchone()
            if alias_row and str(alias_row[0]) != cluster_id:
                raise FeedbackStoreError(
                    f"Working-name alias already belongs to another cluster: {display_name}"
                )
            conn.execute(
                """
                INSERT OR IGNORE INTO cluster_aliases(normalized_alias, cluster_id, display_alias)
                VALUES (?, ?, ?)
                """,
                (normalized, cluster_id, display_name),
            )
        conn.execute(
            "UPDATE candidate_clusters SET updated_at = ? WHERE cluster_id = ?",
            (created_at, cluster_id),
        )
        return candidate_cluster_summary(conn, cluster_id, source_kind=None)

    return _write_with_retry(connection, write)


def candidate_cluster_summary(
    connection: sqlite3.Connection,
    cluster_id: str,
    *,
    source_kind: str | None = "skill",
    target_kind: str | None = None,
    target_component: str | None = None,
) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT cluster_id, problem_key, kind, canonical_problem, working_name, state,
               derived_priority, created_at, updated_at
        FROM candidate_clusters WHERE cluster_id = ?
        """,
        (cluster_id,),
    ).fetchone()
    if not row:
        raise FeedbackStoreError(f"Cluster does not exist: {cluster_id}")
    clauses = ["co.cluster_id = ?"]
    params: list[Any] = [cluster_id]
    if source_kind is not None:
        if source_kind not in SOURCE_KINDS:
            raise FeedbackStoreError(f"Invalid source_kind filter: {source_kind}")
        clauses.append("r.source_kind = ?")
        params.append(source_kind)
    if target_kind is not None:
        if target_kind not in TARGET_KINDS:
            raise FeedbackStoreError(f"Invalid target_kind filter: {target_kind}")
        clauses.append("o.primary_target_kind = ?")
        params.append(target_kind)
    if target_component is not None:
        clauses.append("o.target_component = ?")
        params.append(_safe_slug(target_component, "target_component"))
    counts = connection.execute(
        f"""
        SELECT
            COUNT(DISTINCT o.observation_id) AS observation_count,
            COUNT(DISTINCT o.run_id) AS independent_run_count,
            COUNT(DISTINCT CASE WHEN r.context_hash IS NOT NULL THEN r.context_hash END) AS context_count,
            SUM(CASE WHEN co.relationship = 'counter-evidence' THEN 1 ELSE 0 END) AS counter_count,
            MAX(CASE o.severity
                    WHEN 'critical' THEN 5 WHEN 'high' THEN 4 WHEN 'medium' THEN 3
                    WHEN 'low' THEN 2 ELSE 1 END) AS max_severity_rank
        FROM cluster_observations co
        JOIN observations o ON o.observation_id = co.observation_id
        JOIN skill_runs r ON r.run_id = o.run_id
        WHERE {' AND '.join(clauses)}
        """,
        params,
    ).fetchone()
    aliases = [
        str(item[0])
        for item in connection.execute(
            "SELECT display_alias FROM cluster_aliases WHERE cluster_id = ? ORDER BY display_alias",
            (cluster_id,),
        ).fetchall()
    ]
    run_count = int(counts["independent_run_count"] or 0)
    max_severity = int(counts["max_severity_rank"] or 0)
    new_skill_eligible = row["kind"] == "new-skill" and (
        run_count >= 3 or (run_count >= 2 and max_severity >= 4)
    )
    return {
        "ok": True,
        "clusterId": row["cluster_id"],
        "problemKey": row["problem_key"],
        "kind": row["kind"],
        "canonicalProblem": row["canonical_problem"],
        "workingName": row["working_name"],
        "aliases": aliases,
        "state": row["state"],
        "derivedPriority": row["derived_priority"],
        "observationCount": int(counts["observation_count"] or 0),
        "independentRunCount": run_count,
        "distinctContextCount": int(counts["context_count"] or 0),
        "counterEvidenceCount": int(counts["counter_count"] or 0),
        "newSkillFeatureRequestEligible": new_skill_eligible,
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def list_clusters(
    connection: sqlite3.Connection,
    *,
    limit: int = 100,
    source_kind: str | None = "skill",
    target_kind: str | None = None,
    target_component: str | None = None,
) -> list[dict[str, Any]]:
    filters: list[str] = []
    params: list[Any] = []
    if source_kind is not None:
        if source_kind not in SOURCE_KINDS:
            raise FeedbackStoreError(f"Invalid source_kind filter: {source_kind}")
        filters.append("r.source_kind = ?")
        params.append(source_kind)
    if target_kind is not None:
        if target_kind not in TARGET_KINDS:
            raise FeedbackStoreError(f"Invalid target_kind filter: {target_kind}")
        filters.append("o.primary_target_kind = ?")
        params.append(target_kind)
    if target_component is not None:
        filters.append("o.target_component = ?")
        params.append(_safe_slug(target_component, "target_component"))
    where = ""
    if filters:
        where = f"""
        WHERE EXISTS (
            SELECT 1
            FROM cluster_observations co
            JOIN observations o ON o.observation_id = co.observation_id
            JOIN skill_runs r ON r.run_id = o.run_id
            WHERE co.cluster_id = c.cluster_id AND {' AND '.join(filters)}
        )
        """
    params.append(max(1, min(limit, 1_000)))
    ids = [
        str(row[0])
        for row in connection.execute(
            f"""
            SELECT c.cluster_id
            FROM candidate_clusters c
            {where}
            ORDER BY c.updated_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    ]
    summaries = [
        candidate_cluster_summary(
            connection,
            cluster_id,
            source_kind=source_kind,
            target_kind=target_kind,
            target_component=target_component,
        )
        for cluster_id in ids
    ]
    return [summary for summary in summaries if summary["observationCount"] > 0]


def query_observations(
    connection: sqlite3.Connection,
    *,
    skill_name: str | None = None,
    source_kind: str | None = "skill",
    target_kind: str | None = None,
    target_component: str | None = None,
    state: str | None = None,
    category: str | None = None,
    suggestion_kind: str | None = None,
    since: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if source_kind is not None:
        if source_kind not in SOURCE_KINDS:
            raise FeedbackStoreError(f"Invalid source_kind filter: {source_kind}")
        clauses.append("r.source_kind = ?")
        params.append(source_kind)
    if target_kind:
        if target_kind not in TARGET_KINDS:
            raise FeedbackStoreError(f"Invalid target_kind filter: {target_kind}")
        clauses.append("o.primary_target_kind = ?")
        params.append(target_kind)
    if target_component:
        clauses.append("o.target_component = ?")
        params.append(_safe_slug(target_component, "target_component"))
    if skill_name:
        clauses.append("tv.skill_name = ?")
        params.append(skill_name)
    if state:
        if state not in LIFECYCLE_STATES:
            raise FeedbackStoreError(f"Invalid state filter: {state}")
        clauses.append("o.state = ?")
        params.append(state)
    if category:
        clauses.append("o.category = ?")
        params.append(category)
    if suggestion_kind:
        clauses.append("o.suggestion_kind = ?")
        params.append(suggestion_kind)
    if since:
        clauses.append("o.created_at >= ?")
        params.append(_parse_timestamp(since, "since"))
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    params.append(max(1, min(limit, 1_000)))
    rows = connection.execute(
        f"""
            SELECT o.observation_id, o.run_id, r.source_kind, o.primary_target_kind,
                   o.target_component, tv.skill_name AS target_skill,
               o.category, o.evidence_type, o.summary, o.workaround_summary,
               o.severity, o.reusability, o.confidence_tier, o.suggestion_kind,
               o.state, o.candidate_name, o.positive_evidence, o.created_at,
               rv.skill_name AS observer_skill, rv.repo_commit, rv.content_hash,
                   rv.bundle_hash, rv.dirty, r.context_hash
            FROM observations o
            JOIN skill_runs r ON r.run_id = o.run_id
            LEFT JOIN skill_versions rv ON rv.version_id = r.skill_version_id
        LEFT JOIN skill_versions tv ON tv.version_id = o.primary_skill_version_id
        {where}
        ORDER BY o.created_at DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def lifecycle_history(
    connection: sqlite3.Connection, *, entity_type: str, entity_id: str
) -> list[dict[str, Any]]:
    if entity_type == "observation":
        rows = connection.execute(
            """
            SELECT history_id, from_state, to_state, reason, changed_at
            FROM observation_state_history WHERE observation_id = ? ORDER BY changed_at, rowid
            """,
            (entity_id,),
        ).fetchall()
    elif entity_type == "cluster":
        rows = connection.execute(
            """
            SELECT history_id, from_state, to_state, reason, changed_at
            FROM cluster_state_history WHERE cluster_id = ? ORDER BY changed_at, rowid
            """,
            (entity_id,),
        ).fetchall()
    else:
        raise FeedbackStoreError("entity_type must be observation or cluster")
    return [dict(row) for row in rows]


def begin_evaluation(
    connection: sqlite3.Connection,
    *,
    cluster_id: str,
    skill_path: str | Path,
    backend: str,
    criteria_file: str | Path,
    holdout_file: str | Path | None = None,
) -> dict[str, Any]:
    if backend not in {"plugin-eval", "degraded"}:
        raise FeedbackStoreError("backend must be plugin-eval or degraded")
    cluster = connection.execute(
        "SELECT kind FROM candidate_clusters WHERE cluster_id = ?", (cluster_id,)
    ).fetchone()
    if not cluster:
        raise FeedbackStoreError(f"Cluster does not exist: {cluster_id}")
    if cluster[0] not in {"existing-skill", "repository-rule", "shared-infrastructure"}:
        raise FeedbackStoreError("New-skill and no-action clusters cannot enter the modification evaluator")
    criteria_path = Path(criteria_file).expanduser().resolve()
    if not criteria_path.is_file() or criteria_path.stat().st_size == 0:
        raise FeedbackStoreError("criteria_file must be a non-empty file frozen before editing")
    holdout_path = Path(holdout_file).expanduser().resolve() if holdout_file else None
    if holdout_path and (not holdout_path.is_file() or holdout_path.stat().st_size == 0):
        raise FeedbackStoreError("holdout_file must be a non-empty file")
    criteria_label = _normalize_text(criteria_path.name, "criteria_label", 120)
    holdout_label = _normalize_text(holdout_path.name, "holdout_label", 120) if holdout_path else None
    metadata = discover_skill_metadata(skill_path, _privacy_salt(connection))
    evaluation_id = str(uuid.uuid4())
    now = utc_now()

    def write(conn: sqlite3.Connection) -> dict[str, Any]:
        version_id = _upsert_skill_version(conn, metadata)
        conn.execute(
            """
            INSERT INTO evaluations(
                evaluation_id, cluster_id, target_skill_version_id, backend,
                criteria_hash, criteria_label, holdout_hash, holdout_label,
                status, created_at, frozen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'frozen', ?, ?)
            """,
            (
                evaluation_id,
                cluster_id,
                version_id,
                backend,
                _hash_file(criteria_path),
                criteria_label,
                _hash_file(holdout_path) if holdout_path else None,
                holdout_label,
                now,
                now,
            ),
        )
        return {
            "ok": True,
            "evaluationId": evaluation_id,
            "clusterId": cluster_id,
            "backend": backend,
            "criteriaHash": _hash_file(criteria_path),
            "criteriaLabel": criteria_label,
            "holdoutHash": _hash_file(holdout_path) if holdout_path else None,
            "targetSkill": metadata["skill_name"],
            "beforeContentHash": metadata["content_hash"],
            "status": "frozen",
        }

    return _write_with_retry(connection, write)


def record_evaluation_result(
    connection: sqlite3.Connection,
    *,
    evaluation_id: str,
    phase: str,
    result_file: str | Path,
    result_status: str,
    notes: str | None = None,
) -> dict[str, Any]:
    if phase not in {"baseline", "experiment", "regression", "holdout"}:
        raise FeedbackStoreError(f"Invalid evaluation phase: {phase}")
    if result_status not in {"pass", "fail", "mixed"}:
        raise FeedbackStoreError(f"Invalid evaluation result status: {result_status}")
    result_path = Path(result_file).expanduser().resolve()
    if not result_path.is_file():
        raise FeedbackStoreError(f"Evaluation result does not exist: {result_path}")
    label = _normalize_text(result_path.name, "result_label", 120)
    safe_notes = _optional_text(notes, "notes", 300)

    def write(conn: sqlite3.Connection) -> dict[str, Any]:
        evaluation = conn.execute(
            "SELECT status FROM evaluations WHERE evaluation_id = ?", (evaluation_id,)
        ).fetchone()
        if not evaluation:
            raise FeedbackStoreError(f"Evaluation does not exist: {evaluation_id}")
        if evaluation[0] in {"discarded", "recommended", "promotable"}:
            raise FeedbackStoreError("Evaluation is already decided")
        baseline_count = conn.execute(
            "SELECT COUNT(*) FROM evaluation_runs WHERE evaluation_id = ? AND phase = 'baseline'",
            (evaluation_id,),
        ).fetchone()[0]
        experiment_count = conn.execute(
            "SELECT COUNT(*) FROM evaluation_runs WHERE evaluation_id = ? AND phase = 'experiment'",
            (evaluation_id,),
        ).fetchone()[0]
        if phase == "baseline":
            if baseline_count:
                raise FeedbackStoreError("Baseline is already recorded; the frozen baseline cannot be replaced")
            iteration = 1
        elif phase == "experiment":
            if not baseline_count:
                raise FeedbackStoreError("Record the frozen baseline before an experiment")
            if experiment_count >= 3:
                raise FeedbackStoreError("Evaluation permits at most three experimental iterations")
            iteration = int(experiment_count) + 1
        else:
            if not baseline_count or not experiment_count:
                raise FeedbackStoreError("Regression and holdout results require a baseline and experiment")
            iteration = int(experiment_count)
        run_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO evaluation_runs(
                evaluation_run_id, evaluation_id, phase, iteration,
                result_hash, result_label, result_status, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                evaluation_id,
                phase,
                iteration,
                _hash_file(result_path),
                label,
                result_status,
                safe_notes,
                utc_now(),
            ),
        )
        conn.execute("UPDATE evaluations SET status = 'running' WHERE evaluation_id = ?", (evaluation_id,))
        return {
            "ok": True,
            "evaluationId": evaluation_id,
            "evaluationRunId": run_id,
            "phase": phase,
            "iteration": iteration,
            "resultStatus": result_status,
            "resultHash": _hash_file(result_path),
        }

    return _write_with_retry(connection, write)


def decide_evaluation(
    connection: sqlite3.Connection,
    *,
    evaluation_id: str,
    decision: str,
    after_skill_path: str | Path | None = None,
) -> dict[str, Any]:
    if decision not in {"discard", "recommend", "keep"}:
        raise FeedbackStoreError("decision must be discard, recommend, or keep")
    after_metadata = (
        discover_skill_metadata(after_skill_path, _privacy_salt(connection)) if after_skill_path else None
    )

    def write(conn: sqlite3.Connection) -> dict[str, Any]:
        evaluation = conn.execute(
            """
            SELECT e.backend, e.status, v.skill_name AS before_skill_name,
                   v.content_hash AS before_content_hash
            FROM evaluations e
            JOIN skill_versions v ON v.version_id = e.target_skill_version_id
            WHERE e.evaluation_id = ?
            """,
            (evaluation_id,),
        ).fetchone()
        if not evaluation:
            raise FeedbackStoreError(f"Evaluation does not exist: {evaluation_id}")
        if evaluation["status"] in {"discarded", "recommended", "promotable"}:
            raise FeedbackStoreError("Evaluation is already decided")
        runs = conn.execute(
            """
            SELECT phase, iteration, result_status FROM evaluation_runs
            WHERE evaluation_id = ? ORDER BY created_at, evaluation_run_id
            """,
            (evaluation_id,),
        ).fetchall()
        phases = {str(row["phase"]) for row in runs}
        if "baseline" not in phases or "experiment" not in phases:
            raise FeedbackStoreError("A decision requires a frozen baseline and at least one experiment")
        latest_experiment = [row for row in runs if row["phase"] == "experiment"][-1]
        protection = [row for row in runs if row["phase"] in {"regression", "holdout"}]

        if decision == "keep":
            if evaluation["backend"] != "plugin-eval":
                raise FeedbackStoreError(
                    "Degraded evaluation cannot validate an automatic keep; use recommend instead"
                )
            if latest_experiment["result_status"] != "pass":
                raise FeedbackStoreError("The latest experiment must pass before keep")
            if not protection or any(row["result_status"] != "pass" for row in protection):
                raise FeedbackStoreError("Keep requires a passing regression or holdout check")
            if not after_metadata:
                raise FeedbackStoreError("keep requires after_skill_path for version attribution")
            final_status = "promotable"
        elif decision == "recommend":
            if not protection:
                raise FeedbackStoreError("Recommendation still requires a regression or holdout result")
            if not after_metadata:
                raise FeedbackStoreError("recommend requires after_skill_path for version attribution")
            final_status = "recommended"
        else:
            final_status = "discarded"

        if decision in {"keep", "recommend"}:
            if after_metadata["skill_name"] != evaluation["before_skill_name"]:
                raise FeedbackStoreError("The evaluated skill target cannot change during an experiment")
            if after_metadata["content_hash"] == evaluation["before_content_hash"]:
                raise FeedbackStoreError("No focused skill-definition change was detected")

        after_version_id = _upsert_skill_version(conn, after_metadata) if after_metadata else None
        conn.execute(
            """
            UPDATE evaluations
            SET decision = ?, status = ?, after_skill_version_id = ?, decided_at = ?
            WHERE evaluation_id = ?
            """,
            (decision, final_status, after_version_id, utc_now(), evaluation_id),
        )
        return {
            "ok": True,
            "evaluationId": evaluation_id,
            "decision": decision,
            "status": final_status,
            "afterContentHash": after_metadata["content_hash"] if after_metadata else None,
            "draftPrEligible": final_status == "promotable",
        }

    return _write_with_retry(connection, write)


def link_entity(
    connection: sqlite3.Connection,
    *,
    entity_type: str,
    entity_id: str,
    link_type: str,
    external_ref: str,
) -> dict[str, Any]:
    if entity_type not in {"observation", "cluster", "evaluation"}:
        raise FeedbackStoreError("Invalid entity_type")
    if link_type not in {"issue", "pr", "merge", "outcome"}:
        raise FeedbackStoreError("Invalid link_type")
    reference = external_ref.strip()
    safe_reference = bool(
        re.fullmatch(r"#[0-9]+", reference)
        or re.fullmatch(r"[0-9a-f]{7,40}", reference)
        or re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(?:issues|pull)/[0-9]+", reference)
        or re.fullmatch(r"[a-z0-9][a-z0-9._:-]{0,127}", reference)
    )
    if not safe_reference:
        raise PrivacyError("external_ref must be a public GitHub issue/PR, commit SHA, number, or safe outcome slug")
    table_map = {
        "observation": ("observations", "observation_id"),
        "cluster": ("candidate_clusters", "cluster_id"),
        "evaluation": ("evaluations", "evaluation_id"),
    }

    def write(conn: sqlite3.Connection) -> dict[str, Any]:
        table, column = table_map[entity_type]
        if not conn.execute(f"SELECT 1 FROM {table} WHERE {column} = ?", (entity_id,)).fetchone():
            raise FeedbackStoreError(f"{entity_type} does not exist: {entity_id}")
        existing = conn.execute(
            """
            SELECT link_id FROM entity_links
            WHERE entity_type = ? AND entity_id = ? AND link_type = ? AND external_ref = ?
            """,
            (entity_type, entity_id, link_type, reference),
        ).fetchone()
        if existing:
            return {
                "ok": True,
                "linkId": str(existing[0]),
                "entityId": entity_id,
                "externalRef": reference,
                "alreadyLinked": True,
            }
        link_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO entity_links(
                link_id, entity_type, entity_id, link_type, external_ref, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (link_id, entity_type, entity_id, link_type, reference, utc_now()),
        )
        return {
            "ok": True,
            "linkId": link_id,
            "entityId": entity_id,
            "externalRef": reference,
            "alreadyLinked": False,
        }

    return _write_with_retry(connection, write)


def import_backfill(
    connection: sqlite3.Connection,
    *,
    source_key: str,
    source_type: str,
    observer_skill_path: str | Path,
    observations: Sequence[dict[str, Any]],
    context_path: str | Path | None = None,
) -> dict[str, Any]:
    safe_source_key = _safe_slug(source_key, "source_key")
    if source_type not in {"git-history", "github", "artifact", "other"}:
        raise FeedbackStoreError(f"Invalid source_type: {source_type}")
    existing = connection.execute(
        "SELECT run_id, observation_count FROM backfill_sources WHERE source_key = ?",
        (safe_source_key,),
    ).fetchone()
    if existing:
        return {
            "ok": True,
            "alreadyProcessed": True,
            "sourceKey": safe_source_key,
            "runId": existing["run_id"],
            "observationCount": int(existing["observation_count"]),
        }
    backfill_specs = []
    for raw in observations:
        spec = dict(raw)
        spec["evidence_type"] = "historical-backfill"
        backfill_specs.append(spec)
    try:
        result = record_run(
            connection,
            skill_path=observer_skill_path,
            invocation_mode="explicit",
            outcome="success",
            context_path=context_path,
            observations=backfill_specs,
            run_kind="backfill",
            source_key=safe_source_key,
        )
    except sqlite3.IntegrityError:
        concurrent = connection.execute(
            """
            SELECT run_id, observation_count FROM skill_runs
            WHERE run_kind = 'backfill' AND source_key = ?
            """,
            (safe_source_key,),
        ).fetchone()
        if not concurrent:
            raise

        def repair_source(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT OR IGNORE INTO backfill_sources(
                    source_key, source_type, completed_at, run_id, observation_count
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    safe_source_key,
                    source_type,
                    utc_now(),
                    concurrent["run_id"],
                    concurrent["observation_count"],
                ),
            )

        _write_with_retry(connection, repair_source)
        return {
            "ok": True,
            "alreadyProcessed": True,
            "sourceKey": safe_source_key,
            "runId": concurrent["run_id"],
            "observationCount": int(concurrent["observation_count"]),
        }

    def write(conn: sqlite3.Connection) -> dict[str, Any]:
        conn.execute(
            """
            INSERT INTO backfill_sources(source_key, source_type, completed_at, run_id, observation_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                safe_source_key,
                source_type,
                utc_now(),
                result["runId"],
                result["observationCount"],
            ),
        )
        return result

    final = _write_with_retry(connection, write)
    final["sourceKey"] = safe_source_key
    final["alreadyProcessed"] = False
    return final


def health_report(connection: sqlite3.Connection, path: Path) -> dict[str, Any]:
    integrity_rows = connection.execute("PRAGMA integrity_check").fetchall()
    integrity = [str(row[0]) for row in integrity_rows]
    schema = int(connection.execute("SELECT version FROM schema_metadata WHERE singleton = 1").fetchone()[0])
    journal = str(connection.execute("PRAGMA journal_mode").fetchone()[0])
    total_runs = int(connection.execute("SELECT COUNT(*) FROM skill_runs").fetchone()[0])
    skill_runs = total_runs
    agent_runs = 0
    if schema >= 4:
        skill_runs = int(
            connection.execute("SELECT COUNT(*) FROM skill_runs WHERE source_kind = 'skill'").fetchone()[0]
        )
        agent_runs = int(
            connection.execute("SELECT COUNT(*) FROM skill_runs WHERE source_kind = 'agent'").fetchone()[0]
        )
    counts = {
        "runs": total_runs,
        "skillRuns": skill_runs,
        "agentRuns": agent_runs,
        "observations": int(connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0]),
        "clusters": int(connection.execute("SELECT COUNT(*) FROM candidate_clusters").fetchone()[0]),
        "evaluations": int(connection.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0]),
    }
    return {
        "ok": integrity == ["ok"],
        "databasePath": str(path),
        "path": classify_database_path(path),
        "schemaVersion": schema,
        "journalMode": journal,
        "integrity": integrity,
        "counts": counts,
    }


def plugin_eval_availability(environ: dict[str, str] | None = None) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    executable = _which("plugin-eval")
    if executable:
        return {"available": True, "mode": "path", "command": [executable]}
    root = env.get(PLUGIN_EVAL_ROOT_ENV)
    if root:
        resolved = Path(root).expanduser().resolve()
        candidates = [
            resolved / "scripts" / "plugin-eval.js",
            resolved / "plugin-eval" / "scripts" / "plugin-eval.js",
            resolved / "plugins" / "plugin-eval" / "scripts" / "plugin-eval.js",
        ]
        script = next((candidate for candidate in candidates if candidate.is_file()), None)
        if script is not None and _which("node"):
            return {"available": True, "mode": "checkout", "command": ["node", str(script)]}
        return {
            "available": False,
            "mode": "misconfigured-checkout",
            "reason": (
                f"{PLUGIN_EVAL_ROOT_ENV} does not identify the plugin-eval plugin or Node is unavailable"
            ),
        }
    return {
        "available": False,
        "mode": "degraded",
        "reason": "plugin-eval is not on PATH and PLUGIN_EVAL_ROOT is unset",
    }


def _which(command: str) -> str | None:
    import shutil

    return shutil.which(command)


def _load_json_argument(values: Sequence[str], files: Sequence[str]) -> list[dict[str, Any]]:
    loaded: list[Any] = []
    for value in values:
        loaded.append(json.loads(value))
    for file_name in files:
        if file_name == "-":
            loaded.append(json.load(sys.stdin))
        else:
            loaded.append(json.loads(Path(file_name).read_text(encoding="utf-8")))
    flattened: list[dict[str, Any]] = []
    for item in loaded:
        if isinstance(item, list):
            flattened.extend(item)
        else:
            flattened.append(item)
    return flattened


def _emit(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _add_observation_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--observation-json", action="append", default=[])
    parser.add_argument("--observation-file", action="append", default=[])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record and review generalized Codex skill evidence")
    parser.add_argument("--db", help=f"Database path (default: {DATABASE_ENV} or user-level .agents path)")
    parser.add_argument("--busy-timeout-ms", type=int, default=DEFAULT_BUSY_TIMEOUT_MS)
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Open an existing store without initialization or migration; valid for query commands only",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Initialize or migrate the database")
    subparsers.add_parser("health", help="Run integrity and durability checks")
    subparsers.add_parser("plugin-eval-status", help="Detect the preferred evaluation backend")

    record_run_parser = subparsers.add_parser("record-run", help="Record one completed skill or agent run")
    record_run_parser.add_argument("--skill-path")
    record_run_parser.add_argument("--source-kind", choices=sorted(SOURCE_KINDS))
    record_run_parser.add_argument("--invocation-mode", choices=sorted(INVOCATION_MODES), default="unknown")
    record_run_parser.add_argument("--outcome", choices=sorted(OUTCOMES), default="unknown")
    record_run_parser.add_argument("--started-at")
    record_run_parser.add_argument("--completed-at")
    record_run_parser.add_argument("--context-path")
    record_run_parser.add_argument("--non-blocking", action="store_true")
    _add_observation_options(record_run_parser)

    record_parser = subparsers.add_parser("record", help="Add one observation to an existing run")
    record_parser.add_argument("--run-id", required=True)
    record_parser.add_argument("--observation-json", required=True)
    record_parser.add_argument("--non-blocking", action="store_true")

    query_parser = subparsers.add_parser("query", help="Query a targeted slice of observations")
    query_parser.add_argument("--skill")
    query_parser.add_argument("--source-kind", choices=[*sorted(SOURCE_KINDS), "all"], default="skill")
    query_parser.add_argument("--target-kind", choices=sorted(TARGET_KINDS))
    query_parser.add_argument("--target-component")
    query_parser.add_argument("--state")
    query_parser.add_argument("--category")
    query_parser.add_argument("--suggestion-kind")
    query_parser.add_argument("--since")
    query_parser.add_argument("--limit", type=int, default=100)

    history_parser = subparsers.add_parser("history", help="Show lifecycle history")
    history_parser.add_argument("--entity-type", choices=["observation", "cluster"], required=True)
    history_parser.add_argument("--id", required=True)

    mark_parser = subparsers.add_parser("mark", help="Transition lifecycle state without deleting history")
    mark_parser.add_argument("--entity-type", choices=["observation", "cluster"], required=True)
    mark_parser.add_argument("--id", required=True)
    mark_parser.add_argument("--state", required=True)
    mark_parser.add_argument("--reason", required=True)

    cluster_parser = subparsers.add_parser("cluster", help="Create/reuse a problem cluster and attach evidence")
    cluster_parser.add_argument("--problem-key", required=True)
    cluster_parser.add_argument("--kind", choices=sorted(CLUSTER_KINDS), required=True)
    cluster_parser.add_argument("--summary", required=True)
    cluster_parser.add_argument("--observation-id", action="append", required=True)
    cluster_parser.add_argument("--working-name", action="append", default=[])
    cluster_parser.add_argument(
        "--relationship", choices=["support", "counter-evidence", "duplicate"], default="support"
    )

    clusters_parser = subparsers.add_parser("clusters", help="List clustered candidates")
    clusters_parser.add_argument("--source-kind", choices=[*sorted(SOURCE_KINDS), "all"], default="skill")
    clusters_parser.add_argument("--target-kind", choices=sorted(TARGET_KINDS))
    clusters_parser.add_argument("--target-component")
    clusters_parser.add_argument("--limit", type=int, default=100)

    eval_begin = subparsers.add_parser("evaluation-begin", help="Freeze criteria before changing a skill")
    eval_begin.add_argument("--cluster-id", required=True)
    eval_begin.add_argument("--skill-path", required=True)
    eval_begin.add_argument("--backend", choices=["plugin-eval", "degraded"], required=True)
    eval_begin.add_argument("--criteria-file", required=True)
    eval_begin.add_argument("--holdout-file")

    eval_record = subparsers.add_parser("evaluation-record", help="Record immutable evaluation result hashes")
    eval_record.add_argument("--evaluation-id", required=True)
    eval_record.add_argument("--phase", choices=["baseline", "experiment", "regression", "holdout"], required=True)
    eval_record.add_argument("--result-file", required=True)
    eval_record.add_argument("--result-status", choices=["pass", "fail", "mixed"], required=True)
    eval_record.add_argument("--notes")

    eval_decide = subparsers.add_parser("evaluation-decide", help="Keep, recommend, or discard an experiment")
    eval_decide.add_argument("--evaluation-id", required=True)
    eval_decide.add_argument("--decision", choices=["keep", "recommend", "discard"], required=True)
    eval_decide.add_argument("--after-skill-path")

    link_parser = subparsers.add_parser("link", help="Link evidence to a public issue, PR, merge, or outcome")
    link_parser.add_argument("--entity-type", choices=["observation", "cluster", "evaluation"], required=True)
    link_parser.add_argument("--id", required=True)
    link_parser.add_argument("--link-type", choices=["issue", "pr", "merge", "outcome"], required=True)
    link_parser.add_argument("--external-ref", required=True)

    backfill_parser = subparsers.add_parser("backfill", help="Import one sanitized historical evidence batch once")
    backfill_parser.add_argument("--source-key", required=True)
    backfill_parser.add_argument("--source-type", choices=["git-history", "github", "artifact", "other"], required=True)
    backfill_parser.add_argument("--observer-skill-path", required=True)
    backfill_parser.add_argument("--context-path")
    _add_observation_options(backfill_parser)

    register_category = subparsers.add_parser("register-category", help="Add a non-destructive category extension")
    register_category.add_argument("--name", required=True)
    register_category.add_argument("--description", required=True)

    register_evidence = subparsers.add_parser("register-evidence-type", help="Add a non-destructive evidence type")
    register_evidence.add_argument("--name", required=True)
    register_evidence.add_argument("--description", required=True)
    return parser


def _execute_command(args: argparse.Namespace, connection: sqlite3.Connection, path: Path) -> Any:
    if args.command == "init":
        return {"ok": True, "databasePath": str(path), "schemaVersion": SCHEMA_VERSION}
    if args.command == "health":
        return health_report(connection, path)
    if args.command == "plugin-eval-status":
        return plugin_eval_availability()
    if args.command == "record-run":
        observations = _load_json_argument(args.observation_json, args.observation_file)
        return record_run(
            connection,
            skill_path=args.skill_path,
            source_kind=args.source_kind,
            invocation_mode=args.invocation_mode,
            outcome=args.outcome,
            started_at=args.started_at,
            completed_at=args.completed_at,
            context_path=args.context_path,
            observations=observations,
        )
    if args.command == "record":
        return record_observation(
            connection,
            run_id=args.run_id,
            observation=json.loads(args.observation_json),
        )
    if args.command == "query":
        return query_observations(
            connection,
            skill_name=args.skill,
            source_kind=None if args.source_kind == "all" else args.source_kind,
            target_kind=args.target_kind,
            target_component=args.target_component,
            state=args.state,
            category=args.category,
            suggestion_kind=args.suggestion_kind,
            since=args.since,
            limit=args.limit,
        )
    if args.command == "history":
        return lifecycle_history(connection, entity_type=args.entity_type, entity_id=args.id)
    if args.command == "mark":
        return mark_state(
            connection,
            entity_type=args.entity_type,
            entity_id=args.id,
            new_state=args.state,
            reason=args.reason,
        )
    if args.command == "cluster":
        return cluster_observations(
            connection,
            problem_key=args.problem_key,
            kind=args.kind,
            canonical_problem=args.summary,
            observation_ids=args.observation_id,
            working_names=args.working_name,
            relationship=args.relationship,
        )
    if args.command == "clusters":
        return list_clusters(
            connection,
            limit=args.limit,
            source_kind=None if args.source_kind == "all" else args.source_kind,
            target_kind=args.target_kind,
            target_component=args.target_component,
        )
    if args.command == "evaluation-begin":
        return begin_evaluation(
            connection,
            cluster_id=args.cluster_id,
            skill_path=args.skill_path,
            backend=args.backend,
            criteria_file=args.criteria_file,
            holdout_file=args.holdout_file,
        )
    if args.command == "evaluation-record":
        return record_evaluation_result(
            connection,
            evaluation_id=args.evaluation_id,
            phase=args.phase,
            result_file=args.result_file,
            result_status=args.result_status,
            notes=args.notes,
        )
    if args.command == "evaluation-decide":
        return decide_evaluation(
            connection,
            evaluation_id=args.evaluation_id,
            decision=args.decision,
            after_skill_path=args.after_skill_path,
        )
    if args.command == "link":
        return link_entity(
            connection,
            entity_type=args.entity_type,
            entity_id=args.id,
            link_type=args.link_type,
            external_ref=args.external_ref,
        )
    if args.command == "backfill":
        return import_backfill(
            connection,
            source_key=args.source_key,
            source_type=args.source_type,
            observer_skill_path=args.observer_skill_path,
            observations=_load_json_argument(args.observation_json, args.observation_file),
            context_path=args.context_path,
        )
    if args.command == "register-category":
        return register_lookup(
            connection,
            table="observation_categories",
            name=args.name,
            description=args.description,
        )
    if args.command == "register-evidence-type":
        return register_lookup(
            connection,
            table="evidence_types",
            name=args.name,
            description=args.description,
        )
    raise FeedbackStoreError(f"Unsupported command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    non_blocking = bool(getattr(args, "non_blocking", False))
    connection: sqlite3.Connection | None = None
    try:
        if args.command == "plugin-eval-status":
            _emit(plugin_eval_availability())
            return 0
        if args.read_only and args.command not in READ_ONLY_COMMANDS:
            raise FeedbackStoreError(f"{args.command} is not permitted in read-only mode")
        if args.read_only:
            connection, path = open_store_read_only(
                args.db, busy_timeout_ms=args.busy_timeout_ms
            )
        else:
            connection, path = open_store(args.db, busy_timeout_ms=args.busy_timeout_ms)
        payload = _execute_command(args, connection, path)
        _emit(payload)
        return 0
    except (FeedbackStoreError, PrivacyError, sqlite3.Error, json.JSONDecodeError, OSError) as exc:
        payload = {
            "ok": False,
            "error": exc.__class__.__name__,
            "message": str(exc),
            "nonBlocking": non_blocking,
        }
        _emit(payload)
        return 0 if non_blocking else 2
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
