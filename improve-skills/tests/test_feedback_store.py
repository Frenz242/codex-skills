from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import threading
import unittest
from unittest import mock


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SKILL_ROOT.parent
MODULE_PATH = SKILL_ROOT / "scripts" / "feedback_store.py"
SPEC = importlib.util.spec_from_file_location("improve_skills_feedback_store", MODULE_PATH)
assert SPEC and SPEC.loader
store = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(store)


def make_skill(parent: Path, name: str, body: str = "Do the focused work.") -> Path:
    path = parent / name
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Test fixture for {name}.\n---\n\n# {name}\n\n{body}\n",
        encoding="utf-8",
    )
    return path


def observation(
    summary: str = "A repeatable validation step was missing.",
    *,
    category: str = "missing-instruction",
    evidence_type: str = "self-observation",
    target_kind: str = "skill",
    target_skill_path: Path | None = None,
    severity: str = "medium",
    reusability: str = "high",
    confidence_tier: str = "isolated-self-observation",
    suggestion_kind: str = "existing-skill",
    candidate_name: str | None = None,
    target_component: str | None = None,
    positive: bool = False,
) -> dict[str, object]:
    value: dict[str, object] = {
        "category": category,
        "evidence_type": evidence_type,
        "summary": summary,
        "severity": severity,
        "reusability": reusability,
        "confidence_tier": confidence_tier,
        "suggestion_kind": suggestion_kind,
        "target_kind": target_kind,
        "positive": positive,
    }
    if target_skill_path is not None:
        value["target_skill_path"] = str(target_skill_path)
    if candidate_name is not None:
        value["candidate_name"] = candidate_name
    if target_component is not None:
        value["target_component"] = target_component
    return value


class StoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.db = self.root / "feedback.db"
        self.skill = make_skill(self.root, "sample-skill")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def open(self, *, target_schema_version: int = store.SCHEMA_VERSION, busy_timeout_ms: int = 1_500):
        return store.open_store(
            self.db,
            allow_unsafe_for_tests=True,
            target_schema_version=target_schema_version,
            busy_timeout_ms=busy_timeout_ms,
        )[0]

    def record_run(self, connection: sqlite3.Connection, observations=(), **overrides):
        arguments = {
            "skill_path": self.skill,
            "invocation_mode": "explicit",
            "outcome": "success",
            "context_path": self.root / "context-one",
            "observations": observations,
        }
        arguments.update(overrides)
        return store.record_run(connection, **arguments)


class InitializationTests(StoreCase):
    def test_first_and_repeated_initialization_are_idempotent(self) -> None:
        connection = self.open()
        self.assertEqual(
            store.SCHEMA_VERSION,
            connection.execute("SELECT version FROM schema_metadata").fetchone()[0],
        )
        self.assertEqual("wal", connection.execute("PRAGMA journal_mode").fetchone()[0])
        connection.close()

        connection = self.open()
        versions = [row[0] for row in connection.execute("SELECT version FROM migration_history")]
        self.assertEqual(list(range(1, store.SCHEMA_VERSION + 1)), versions)
        self.assertEqual("ok", connection.execute("PRAGMA integrity_check").fetchone()[0])
        connection.close()

    def test_schema_migration_preserves_existing_rows(self) -> None:
        connection = self.open(target_schema_version=3)
        first = self.record_run(connection)
        version_id = connection.execute(
            "SELECT skill_version_id FROM skill_runs WHERE run_id = ?", (first["runId"],)
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO observations(
                observation_id, run_id, primary_target_kind, primary_skill_version_id,
                category, evidence_type, summary, severity, reusability,
                confidence_tier, suggestion_kind, state, positive_evidence,
                summary_fingerprint, created_at
            ) VALUES ('preserved-observation', ?, 'skill', ?, 'missing-instruction',
                      'self-observation', 'A generalized historical observation.', 'medium',
                      'high', 'isolated-self-observation', 'existing-skill', 'observed', 0,
                      'preserved-fingerprint', '2026-01-01T00:00:00Z')
            """,
            (first["runId"], version_id),
        )
        connection.execute(
            """
            INSERT INTO observation_state_history(
                history_id, observation_id, from_state, to_state, reason, changed_at
            ) VALUES ('preserved-history', 'preserved-observation', NULL, 'observed',
                      'Initial state assigned transactionally', '2026-01-01T00:00:00Z')
            """
        )
        connection.execute(
            "UPDATE skill_runs SET observation_count = 1 WHERE run_id = ?", (first["runId"],)
        )
        connection.close()

        connection = self.open()
        self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM skill_runs").fetchone()[0])
        self.assertEqual(first["runId"], connection.execute("SELECT run_id FROM skill_runs").fetchone()[0])
        migrated = connection.execute(
            "SELECT source_kind, skill_version_id, observation_count FROM skill_runs"
        ).fetchone()
        self.assertEqual(("skill", version_id, 1), tuple(migrated))
        self.assertEqual(
            "preserved-observation",
            connection.execute("SELECT observation_id FROM observations").fetchone()[0],
        )
        self.assertEqual(
            "preserved-history",
            connection.execute("SELECT history_id FROM observation_state_history").fetchone()[0],
        )
        self.assertIsNotNone(
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='candidate_clusters'"
            ).fetchone()
        )
        connection.close()

    def test_default_path_and_override_are_stable_user_level_locations(self) -> None:
        default = store.default_database_path(environ={}, home=Path("C:/Users/Example"))
        self.assertTrue(str(default).lower().endswith(".agents\\skill-feedback\\skill-feedback.db"))
        override = self.root / "stable" / "custom.db"
        self.assertEqual(
            override.resolve(),
            store.default_database_path(environ={store.DATABASE_ENV: str(override)}),
        )

    def test_git_temp_and_cache_paths_are_not_durable(self) -> None:
        git_root = self.root / "repo"
        (git_root / ".git").mkdir(parents=True)
        with mock.patch.object(store.tempfile, "gettempdir", return_value="Z:/unrelated-temp"):
            self.assertEqual(
                "git-controlled",
                store.classify_database_path(git_root / "feedback.db")["classification"],
            )
        self.assertFalse(store.classify_database_path(self.root / "feedback.db")["durable"])
        cache = Path("C:/Users/Example/.codex/plugins/cache/package/feedback.db")
        self.assertEqual("volatile-cache", store.classify_database_path(cache)["classification"])

    def test_health_runs_integrity_check(self) -> None:
        connection = self.open()
        report = store.health_report(connection, self.db.resolve())
        self.assertTrue(report["ok"])
        self.assertEqual(["ok"], report["integrity"])
        self.assertEqual(store.SCHEMA_VERSION, report["schemaVersion"])
        connection.close()

    def test_read_only_open_never_initializes_or_accepts_mutation(self) -> None:
        missing = self.root / "missing.db"
        with self.assertRaisesRegex(store.FeedbackStoreError, "does not exist"):
            store.open_store_read_only(missing, allow_unsafe_for_tests=True)
        self.assertFalse(missing.exists())

        connection = self.open()
        self.run_id = self.record_run(connection)["runId"]
        connection.close()
        read_only, _ = store.open_store_read_only(self.db, allow_unsafe_for_tests=True)
        self.assertEqual(self.run_id, read_only.execute("SELECT run_id FROM skill_runs").fetchone()[0])
        with self.assertRaises(sqlite3.OperationalError):
            read_only.execute("DELETE FROM skill_runs")
        read_only.close()


class RecordingTests(StoreCase):
    def test_run_without_observation_creates_denominator_only(self) -> None:
        connection = self.open()
        result = self.record_run(connection)
        self.assertEqual(0, result["observationCount"])
        self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM skill_runs").fetchone()[0])
        self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0])
        connection.close()

    def test_one_run_can_record_explicit_objective_positive_and_new_skill_evidence(self) -> None:
        connection = self.open()
        evidence = [
            observation(
                "The user corrected the repository-state interpretation.",
                category="explicit-user-correction",
                evidence_type="explicit-user-feedback",
                confidence_tier="explicit-user-correction",
                target_skill_path=self.skill,
            ),
            observation(
                "A deterministic fixture failed before artifact publication.",
                category="objective-failure",
                evidence_type="objective-check",
                confidence_tier="objective-failure",
                target_skill_path=self.skill,
            ),
            observation(
                "The dirty-worktree guardrail prevented unrelated edits from being overwritten.",
                category="guardrail-success",
                evidence_type="positive-guardrail",
                confidence_tier="objective-failure",
                suggestion_kind="no-action",
                target_skill_path=self.skill,
                positive=True,
            ),
            observation(
                "A recurring release-evidence workflow has no current owner.",
                category="possible-new-skill",
                target_kind="new-skill",
                suggestion_kind="new-skill",
                candidate_name="review-release-evidence",
            ),
        ]
        result = self.record_run(connection, evidence)
        self.assertEqual(4, result["observationCount"])
        self.assertEqual(
            {"explicit-user-correction", "objective-failure", "guardrail-success", "possible-new-skill"},
            {row[0] for row in connection.execute("SELECT category FROM observations")},
        )
        self.assertEqual(1, connection.execute("SELECT SUM(positive_evidence) FROM observations").fetchone()[0])
        connection.close()

    def test_several_observations_in_one_run_are_one_independent_occurrence(self) -> None:
        connection = self.open()
        result = self.record_run(
            connection,
            [
                observation("The first symptom exposed one root problem.", target_skill_path=self.skill),
                observation(
                    "A second symptom exposed the same root problem.",
                    category="reusable-workaround",
                    target_skill_path=self.skill,
                ),
            ],
        )
        cluster = store.cluster_observations(
            connection,
            problem_key="same-root-problem",
            kind="existing-skill",
            canonical_problem="The same root problem appears through multiple symptoms.",
            observation_ids=result["observationIds"],
        )
        self.assertEqual(2, cluster["observationCount"])
        self.assertEqual(1, cluster["independentRunCount"])
        connection.close()

    def test_exact_duplicate_within_run_is_stored_once(self) -> None:
        connection = self.open()
        item = observation(target_skill_path=self.skill)
        result = self.record_run(connection, [item, dict(item)])
        self.assertEqual(1, result["observationCount"])
        self.assertEqual(1, result["skippedDuplicates"])
        connection.close()

    def test_low_reuse_task_specific_self_observation_is_omitted(self) -> None:
        connection = self.open()
        item = observation(
            "A one-time fixture name was unusual.",
            severity="low",
            reusability="task-specific",
            target_skill_path=self.skill,
        )
        result = self.record_run(connection, [item])
        self.assertEqual(0, result["observationCount"])
        self.assertEqual(1, result["skippedTaskSpecific"])
        self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM skill_runs").fetchone()[0])
        connection.close()

    def test_missing_skill_target_is_rejected(self) -> None:
        connection = self.open()
        item = observation(target_skill_path=self.root / "missing")
        with self.assertRaisesRegex(store.FeedbackStoreError, "does not exist"):
            self.record_run(connection, [item])
        self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM skill_runs").fetchone()[0])
        connection.close()

    def test_content_hash_and_dirty_flag_distinguish_versions(self) -> None:
        salt = b"x" * 32
        root_result = subprocess.CompletedProcess([], 0, stdout=str(self.root), stderr="")
        head_result = subprocess.CompletedProcess([], 0, stdout="a" * 40, stderr="")
        dirty_result = subprocess.CompletedProcess([], 0, stdout=" M sample-skill/SKILL.md", stderr="")

        def fake_git(arguments, _cwd):
            if arguments[:2] == ["rev-parse", "--show-toplevel"]:
                return root_result
            if arguments[:2] == ["rev-parse", "HEAD"]:
                return head_result
            return dirty_result

        with mock.patch.object(store, "_run_git", side_effect=fake_git):
            before = store.discover_skill_metadata(self.skill, salt)
            (self.skill / "SKILL.md").write_text(
                (self.skill / "SKILL.md").read_text(encoding="utf-8") + "\nFocused edit.\n",
                encoding="utf-8",
            )
            after = store.discover_skill_metadata(self.skill, salt)
        self.assertTrue(before["dirty"])
        self.assertEqual("a" * 40, before["repo_commit"])
        self.assertNotEqual(before["content_hash"], after["content_hash"])
        self.assertNotEqual(before["version_key"], after["version_key"])

    def test_concurrent_writers_generate_unique_uuid_rows(self) -> None:
        connection = self.open()
        connection.close()
        barrier = threading.Barrier(8)

        def write(index: int) -> str:
            connection = self.open()
            barrier.wait()
            try:
                return self.record_run(
                    connection,
                    [
                        observation(
                            f"Concurrent generalized evidence item {index}.",
                            target_skill_path=self.skill,
                        )
                    ],
                )["runId"]
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=8) as pool:
            run_ids = list(pool.map(write, range(8)))
        self.assertEqual(8, len(set(run_ids)))
        connection = self.open()
        observation_ids = [row[0] for row in connection.execute("SELECT observation_id FROM observations")]
        self.assertEqual(8, len(set(observation_ids)))
        connection.close()

    def test_busy_database_fails_after_bounded_retries(self) -> None:
        connection = self.open(busy_timeout_ms=10)
        blocker = sqlite3.connect(self.db, timeout=0.01, isolation_level=None)
        blocker.execute("BEGIN IMMEDIATE")
        try:
            with self.assertRaises(store.BusyStoreError):
                self.record_run(connection)
        finally:
            blocker.execute("ROLLBACK")
            blocker.close()
            connection.close()


class AgentSourceTests(StoreCase):
    def test_agent_run_records_without_creating_skill_identity(self) -> None:
        connection = self.open()
        spec = observation(
            "The command broker repeatedly rejected a safe helper invocation.",
            category="unexpected-environment",
            target_kind="infrastructure",
            suggestion_kind="shared-infrastructure",
            target_component="codex-windows-sandbox",
        )
        result = store.record_run(
            connection,
            source_kind="agent",
            outcome="partial",
            context_path=self.root / "context-one",
            observations=[spec],
        )

        self.assertEqual("agent", result["sourceKind"])
        self.assertIsNone(result["skill"])
        row = connection.execute(
            "SELECT source_kind, skill_version_id FROM skill_runs WHERE run_id = ?",
            (result["runId"],),
        ).fetchone()
        self.assertEqual(("agent", None), tuple(row))
        self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM skill_versions").fetchone()[0])
        self.assertEqual([], store.query_observations(connection))
        agent_rows = store.query_observations(
            connection,
            source_kind="agent",
            target_kind="infrastructure",
            target_component="codex-windows-sandbox",
        )
        self.assertEqual(1, len(agent_rows))
        self.assertEqual("agent", agent_rows[0]["source_kind"])
        self.assertEqual("codex-windows-sandbox", agent_rows[0]["target_component"])
        connection.close()

    def test_source_and_skill_combinations_are_rejected(self) -> None:
        connection = self.open()
        with self.assertRaisesRegex(store.FeedbackStoreError, "require skill_path"):
            store.record_run(connection, source_kind="skill")
        with self.assertRaisesRegex(store.FeedbackStoreError, "must not include skill_path"):
            store.record_run(connection, source_kind="agent", skill_path=self.skill)
        with self.assertRaisesRegex(store.FeedbackStoreError, "requires --source-kind"):
            store.record_run(connection)

        skill_run = self.record_run(connection)
        version_id = connection.execute(
            "SELECT skill_version_id FROM skill_runs WHERE run_id = ?", (skill_run["runId"],)
        ).fetchone()[0]
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO skill_runs(
                    run_id, skill_version_id, source_kind, started_at, completed_at,
                    invocation_mode, outcome, run_kind, observation_count, created_at
                ) VALUES ('invalid-agent', ?, 'agent', '2026-01-01T00:00:00Z',
                          '2026-01-01T00:00:01Z', 'unknown', 'success', 'live', 0,
                          '2026-01-01T00:00:01Z')
                """,
                (version_id,),
            )
        connection.close()

    def test_agent_skill_target_requires_external_activation_evidence(self) -> None:
        connection = self.open()
        unsupported = observation(
            "The skill may have missed an activation opportunity.",
            category="activation-false-negative",
            target_skill_path=self.skill,
        )
        with self.assertRaisesRegex(store.FeedbackStoreError, "requires explicit user feedback"):
            store.record_run(
                connection,
                source_kind="agent",
                observations=[unsupported],
            )

        supported = observation(
            "Explicit user feedback identified a missed activation.",
            category="activation-false-negative",
            evidence_type="explicit-user-feedback",
            confidence_tier="explicit-user-correction",
            target_skill_path=self.skill,
        )
        result = store.record_run(
            connection,
            source_kind="agent",
            observations=[supported],
        )
        self.assertEqual(1, result["observationCount"])
        row = connection.execute(
            "SELECT source_kind, skill_version_id FROM skill_runs WHERE run_id = ?",
            (result["runId"],),
        ).fetchone()
        self.assertEqual("agent", row["source_kind"])
        self.assertIsNone(row["skill_version_id"])
        connection.close()

    def test_target_component_is_private_safe_and_infrastructure_only(self) -> None:
        connection = self.open()
        invalid_slug = observation(
            target_kind="infrastructure",
            suggestion_kind="shared-infrastructure",
            target_component="Customer Runtime",
        )
        with self.assertRaisesRegex(store.FeedbackStoreError, "target_component"):
            store.record_run(connection, source_kind="agent", observations=[invalid_slug])

        wrong_target = observation(target_component="github-cli")
        with self.assertRaisesRegex(store.FeedbackStoreError, "only valid for infrastructure"):
            self.record_run(connection, [wrong_target])

        repository_target = observation(
            target_kind="repository",
            suggestion_kind="repository-rule",
        )
        with self.assertRaisesRegex(store.FeedbackStoreError, "require context_path"):
            store.record_run(
                connection,
                source_kind="agent",
                observations=[repository_target],
            )
        connection.close()

    def test_agent_clusters_filter_by_source_and_target(self) -> None:
        connection = self.open()
        result = store.record_run(
            connection,
            source_kind="agent",
            observations=[
                observation(
                    "A repeatable broker failure affected helper execution.",
                    target_kind="infrastructure",
                    suggestion_kind="shared-infrastructure",
                    target_component="mcp-runtime",
                )
            ],
        )
        cluster = store.cluster_observations(
            connection,
            problem_key="mcp-runtime-helper-failure",
            kind="shared-infrastructure",
            canonical_problem="The runtime broker repeatedly rejects a helper operation.",
            observation_ids=result["observationIds"],
        )
        self.assertEqual(1, cluster["independentRunCount"])
        self.assertEqual([], store.list_clusters(connection))
        filtered = store.list_clusters(
            connection,
            source_kind="agent",
            target_kind="infrastructure",
            target_component="mcp-runtime",
        )
        self.assertEqual(1, len(filtered))
        self.assertEqual(1, filtered[0]["independentRunCount"])
        connection.close()


class PrivacyTests(StoreCase):
    def test_secret_email_url_and_absolute_path_are_rejected_before_write(self) -> None:
        connection = self.open()
        unsafe = [
            "A token was " + "ghp_" + "abcdefghijklmnopqrstuvwxyz012345.",
            "Contact operator@example.invalid for the fixture.",
            "The private page was https://private.invalid/item.",
            "The fixture used C:\\Client\\Sensitive\\data.txt.",
        ]
        for summary in unsafe:
            with self.subTest(summary=summary):
                with self.assertRaises(store.PrivacyError):
                    self.record_run(connection, [observation(summary, target_skill_path=self.skill)])
        self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM skill_runs").fetchone()[0])
        connection.close()

    def test_raw_prompt_field_cannot_enter_schema(self) -> None:
        connection = self.open()
        item = observation(target_skill_path=self.skill)
        item["raw_prompt"] = "Never persist this"
        with self.assertRaisesRegex(store.FeedbackStoreError, "Unknown observation fields"):
            self.record_run(connection, [item])
        columns = {row[1] for row in connection.execute("PRAGMA table_info(observations)")}
        self.assertNotIn("raw_prompt", columns)
        connection.close()

    def test_sanitized_summary_persists_without_raw_context_path(self) -> None:
        connection = self.open()
        summary = "Repository ownership prevented normal Git inspection."
        self.record_run(connection, [observation(summary, target_skill_path=self.skill)])
        self.assertEqual(summary, connection.execute("SELECT summary FROM observations").fetchone()[0])
        context = connection.execute("SELECT context_hash FROM skill_runs").fetchone()[0]
        self.assertEqual(64, len(context))
        self.assertNotEqual(str(self.root / "context-one"), context)
        self.assertNotIn("path", {row[1] for row in connection.execute("PRAGMA table_info(skill_runs)")})
        connection.close()


class LifecycleAndClusterTests(StoreCase):
    def test_every_observation_has_initial_state_and_transition_history(self) -> None:
        connection = self.open()
        result = self.record_run(connection, [observation(target_skill_path=self.skill)])
        observation_id = result["observationIds"][0]
        self.assertEqual("observed", connection.execute("SELECT state FROM observations").fetchone()[0])
        store.mark_state(
            connection,
            entity_type="observation",
            entity_id=observation_id,
            new_state="invalid",
            reason="A calibrated negative fixture disproved the observation.",
        )
        history = store.lifecycle_history(
            connection, entity_type="observation", entity_id=observation_id
        )
        self.assertEqual(["observed", "invalid"], [row["to_state"] for row in history])
        self.assertEqual(1, len(store.query_observations(connection, state="invalid")))
        with self.assertRaisesRegex(store.FeedbackStoreError, "Invalid lifecycle transition"):
            store.mark_state(
                connection,
                entity_type="observation",
                entity_id=observation_id,
                new_state="candidate",
                reason="Invalid records cannot silently reappear.",
            )
        connection.close()

    def test_identifiers_are_never_reused_after_state_changes(self) -> None:
        connection = self.open()
        first = self.record_run(connection, [observation(target_skill_path=self.skill)])
        store.mark_state(
            connection,
            entity_type="observation",
            entity_id=first["observationIds"][0],
            new_state="invalid",
            reason="The first record was invalidated.",
        )
        second = self.record_run(connection, [observation(target_skill_path=self.skill)])
        self.assertNotEqual(first["runId"], second["runId"])
        self.assertNotEqual(first["observationIds"][0], second["observationIds"][0])
        self.assertEqual(2, connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0])
        connection.close()

    def test_candidate_names_are_aliases_for_one_problem_cluster(self) -> None:
        connection = self.open()
        first = self.record_run(
            connection,
            [
                observation(
                    "Release evidence review repeatedly lacks an owner.",
                    category="possible-new-skill",
                    target_kind="new-skill",
                    suggestion_kind="new-skill",
                    candidate_name="review-release-evidence",
                )
            ],
        )
        second = self.record_run(
            connection,
            [
                observation(
                    "A second release evidence review lacks an owner.",
                    category="possible-new-skill",
                    target_kind="new-skill",
                    suggestion_kind="new-skill",
                    candidate_name="release-evidence-review",
                )
            ],
            context_path=self.root / "context-two",
        )
        combined = store.cluster_observations(
            connection,
            problem_key="unowned-release-evidence-review",
            kind="new-skill",
            canonical_problem="Repeated release evidence review has no installed owner.",
            observation_ids=first["observationIds"] + second["observationIds"],
            working_names=["review release evidence", "release evidence review"],
        )
        self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM candidate_clusters").fetchone()[0])
        self.assertEqual(2, combined["independentRunCount"])
        self.assertEqual(2, combined["distinctContextCount"])
        self.assertEqual(1, len(combined["aliases"]))

        other = self.record_run(
            connection,
            [
                observation(
                    "A different dependency-audit workflow lacks an owner.",
                    category="possible-new-skill",
                    target_kind="new-skill",
                    suggestion_kind="new-skill",
                    candidate_name="audit-dependencies",
                )
            ],
        )
        store.cluster_observations(
            connection,
            problem_key="unowned-dependency-audit",
            kind="new-skill",
            canonical_problem="Dependency auditing is a genuinely different recurring goal.",
            observation_ids=other["observationIds"],
            working_names=["audit dependencies"],
        )
        self.assertEqual(2, connection.execute("SELECT COUNT(*) FROM candidate_clusters").fetchone()[0])
        connection.close()

    def test_new_skill_threshold_uses_independent_runs(self) -> None:
        connection = self.open()
        ids = []
        for index in range(3):
            result = self.record_run(
                connection,
                [
                    observation(
                        f"Independent workflow occurrence {index} lacks an owner.",
                        category="possible-new-skill",
                        target_kind="new-skill",
                        suggestion_kind="new-skill",
                        candidate_name="candidate-workflow",
                    )
                ],
                context_path=self.root / f"context-{index}",
            )
            ids.extend(result["observationIds"])
        cluster = store.cluster_observations(
            connection,
            problem_key="candidate-workflow-problem",
            kind="new-skill",
            canonical_problem="The same independent workflow recurs without an owner.",
            observation_ids=ids,
        )
        self.assertTrue(cluster["newSkillFeatureRequestEligible"])
        self.assertEqual(3, cluster["independentRunCount"])
        connection.close()


class EvaluationAndFlowTests(StoreCase):
    def create_existing_cluster(self, connection: sqlite3.Connection) -> dict[str, object]:
        evidence = self.record_run(connection, [observation(target_skill_path=self.skill)])
        return store.cluster_observations(
            connection,
            problem_key="missing-repeatable-validation",
            kind="existing-skill",
            canonical_problem="The skill omits a repeatable validation step.",
            observation_ids=evidence["observationIds"],
        )

    def result_file(self, name: str, payload: str) -> Path:
        path = self.root / name
        path.write_text(payload, encoding="utf-8")
        return path

    def test_successful_plugin_eval_flow_becomes_draft_pr_eligible(self) -> None:
        connection = self.open()
        cluster = self.create_existing_cluster(connection)
        criteria = self.result_file("criteria.json", '{"assertion":"required validation occurs"}')
        holdout = self.result_file("holdout.json", '{"case":"adjacent workflow"}')
        evaluation = store.begin_evaluation(
            connection,
            cluster_id=cluster["clusterId"],
            skill_path=self.skill,
            backend="plugin-eval",
            criteria_file=criteria,
            holdout_file=holdout,
        )
        store.record_evaluation_result(
            connection,
            evaluation_id=evaluation["evaluationId"],
            phase="baseline",
            result_file=self.result_file("baseline.json", '{"status":"fail"}'),
            result_status="fail",
        )
        (self.skill / "SKILL.md").write_text(
            (self.skill / "SKILL.md").read_text(encoding="utf-8") + "\nRun the repeatable validation.\n",
            encoding="utf-8",
        )
        store.record_evaluation_result(
            connection,
            evaluation_id=evaluation["evaluationId"],
            phase="experiment",
            result_file=self.result_file("after.json", '{"status":"pass","score":1}'),
            result_status="pass",
        )
        store.record_evaluation_result(
            connection,
            evaluation_id=evaluation["evaluationId"],
            phase="regression",
            result_file=self.result_file("regression.json", '{"status":"pass"}'),
            result_status="pass",
        )
        store.record_evaluation_result(
            connection,
            evaluation_id=evaluation["evaluationId"],
            phase="holdout",
            result_file=self.result_file("holdout-result.json", '{"status":"pass"}'),
            result_status="pass",
        )
        decision = store.decide_evaluation(
            connection,
            evaluation_id=evaluation["evaluationId"],
            decision="keep",
            after_skill_path=self.skill,
        )
        self.assertEqual("promotable", decision["status"])
        self.assertTrue(decision["draftPrEligible"])
        self.assertNotEqual(evaluation["beforeContentHash"], decision["afterContentHash"])
        link = store.link_entity(
            connection,
            entity_type="evaluation",
            entity_id=evaluation["evaluationId"],
            link_type="pr",
            external_ref="#42",
        )
        self.assertFalse(link["alreadyLinked"])
        self.assertTrue(
            store.link_entity(
                connection,
                entity_type="evaluation",
                entity_id=evaluation["evaluationId"],
                link_type="pr",
                external_ref="#42",
            )["alreadyLinked"]
        )
        connection.close()

    def test_failed_experiment_is_discarded_and_degraded_mode_cannot_keep(self) -> None:
        connection = self.open()
        cluster = self.create_existing_cluster(connection)
        criteria = self.result_file("criteria.txt", "Frozen criteria")
        evaluation = store.begin_evaluation(
            connection,
            cluster_id=cluster["clusterId"],
            skill_path=self.skill,
            backend="plugin-eval",
            criteria_file=criteria,
        )
        store.record_evaluation_result(
            connection,
            evaluation_id=evaluation["evaluationId"],
            phase="baseline",
            result_file=self.result_file("baseline.txt", "fail"),
            result_status="fail",
        )
        store.record_evaluation_result(
            connection,
            evaluation_id=evaluation["evaluationId"],
            phase="experiment",
            result_file=self.result_file("experiment.txt", "still fail"),
            result_status="fail",
        )
        decision = store.decide_evaluation(
            connection, evaluation_id=evaluation["evaluationId"], decision="discard"
        )
        self.assertEqual("discarded", decision["status"])

        other_cluster_evidence = self.record_run(
            connection,
            [observation("A second evaluator case exists.", target_skill_path=self.skill)],
        )
        other_cluster = store.cluster_observations(
            connection,
            problem_key="second-evaluator-case",
            kind="existing-skill",
            canonical_problem="A second case exercises degraded evaluation.",
            observation_ids=other_cluster_evidence["observationIds"],
        )
        degraded = store.begin_evaluation(
            connection,
            cluster_id=other_cluster["clusterId"],
            skill_path=self.skill,
            backend="degraded",
            criteria_file=criteria,
        )
        store.record_evaluation_result(
            connection,
            evaluation_id=degraded["evaluationId"],
            phase="baseline",
            result_file=self.result_file("d-base.txt", "fail"),
            result_status="fail",
        )
        (self.skill / "SKILL.md").write_text(
            (self.skill / "SKILL.md").read_text(encoding="utf-8") + "\nCandidate edit.\n",
            encoding="utf-8",
        )
        store.record_evaluation_result(
            connection,
            evaluation_id=degraded["evaluationId"],
            phase="experiment",
            result_file=self.result_file("d-after.txt", "pass"),
            result_status="pass",
        )
        store.record_evaluation_result(
            connection,
            evaluation_id=degraded["evaluationId"],
            phase="regression",
            result_file=self.result_file("d-regression.txt", "pass"),
            result_status="pass",
        )
        with self.assertRaisesRegex(store.FeedbackStoreError, "Degraded evaluation cannot"):
            store.decide_evaluation(
                connection,
                evaluation_id=degraded["evaluationId"],
                decision="keep",
                after_skill_path=self.skill,
            )
        recommendation = store.decide_evaluation(
            connection,
            evaluation_id=degraded["evaluationId"],
            decision="recommend",
            after_skill_path=self.skill,
        )
        self.assertEqual("recommended", recommendation["status"])
        self.assertFalse(recommendation["draftPrEligible"])
        connection.close()

    def test_baseline_is_immutable_and_experiments_are_bounded(self) -> None:
        connection = self.open()
        cluster = self.create_existing_cluster(connection)
        criteria = self.result_file("criteria.txt", "Frozen")
        evaluation = store.begin_evaluation(
            connection,
            cluster_id=cluster["clusterId"],
            skill_path=self.skill,
            backend="plugin-eval",
            criteria_file=criteria,
        )
        baseline = self.result_file("baseline.txt", "baseline")
        store.record_evaluation_result(
            connection,
            evaluation_id=evaluation["evaluationId"],
            phase="baseline",
            result_file=baseline,
            result_status="fail",
        )
        with self.assertRaisesRegex(store.FeedbackStoreError, "Baseline is already recorded"):
            store.record_evaluation_result(
                connection,
                evaluation_id=evaluation["evaluationId"],
                phase="baseline",
                result_file=baseline,
                result_status="pass",
            )
        for index in range(3):
            store.record_evaluation_result(
                connection,
                evaluation_id=evaluation["evaluationId"],
                phase="experiment",
                result_file=self.result_file(f"experiment-{index}.txt", str(index)),
                result_status="mixed",
            )
        with self.assertRaisesRegex(store.FeedbackStoreError, "at most three"):
            store.record_evaluation_result(
                connection,
                evaluation_id=evaluation["evaluationId"],
                phase="experiment",
                result_file=self.result_file("experiment-4.txt", "four"),
                result_status="mixed",
            )
        connection.close()

    def test_backfill_is_marked_historical_and_not_reimported(self) -> None:
        connection = self.open()
        item = observation(target_skill_path=self.skill)
        first = store.import_backfill(
            connection,
            source_key="git-history-through-2026-08-21",
            source_type="git-history",
            observer_skill_path=self.skill,
            observations=[item],
        )
        second = store.import_backfill(
            connection,
            source_key="git-history-through-2026-08-21",
            source_type="git-history",
            observer_skill_path=self.skill,
            observations=[item],
        )
        self.assertFalse(first["alreadyProcessed"])
        self.assertTrue(second["alreadyProcessed"])
        self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM skill_runs").fetchone()[0])
        self.assertEqual(
            "historical-backfill", connection.execute("SELECT evidence_type FROM observations").fetchone()[0]
        )
        connection.close()

    def test_concurrent_backfill_calls_share_one_permanent_source(self) -> None:
        connection = self.open()
        connection.close()
        barrier = threading.Barrier(4)

        def import_once(_index: int) -> dict[str, object]:
            worker = self.open()
            barrier.wait()
            try:
                return store.import_backfill(
                    worker,
                    source_key="shared-github-history-snapshot",
                    source_type="github",
                    observer_skill_path=self.skill,
                    observations=[observation(target_skill_path=self.skill)],
                )
            finally:
                worker.close()

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(import_once, range(4)))
        self.assertEqual(1, sum(not bool(item["alreadyProcessed"]) for item in results))
        self.assertEqual(1, len({str(item["runId"]) for item in results}))
        connection = self.open()
        self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM skill_runs").fetchone()[0])
        self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM backfill_sources").fetchone()[0])
        connection.close()

    def test_post_merge_versions_are_queryable_by_content_hash(self) -> None:
        connection = self.open()
        before = self.record_run(
            connection, [observation("Original version failure.", target_skill_path=self.skill)]
        )
        (self.skill / "SKILL.md").write_text(
            (self.skill / "SKILL.md").read_text(encoding="utf-8") + "\nMerged-style version change.\n",
            encoding="utf-8",
        )
        after = self.record_run(
            connection,
            [
                observation(
                    "Original failure recurred after the version change.",
                    category="regression-after-improvement",
                    target_skill_path=self.skill,
                )
            ],
        )
        self.assertNotEqual(before["contentHash"], after["contentHash"])
        hashes = {row[0] for row in connection.execute("SELECT content_hash FROM skill_versions")}
        self.assertEqual({before["contentHash"], after["contentHash"]}, hashes)
        connection.close()


class FailureIsolationAndContractTests(StoreCase):
    def test_non_blocking_cli_failure_does_not_fail_primary_workflow(self) -> None:
        output = io.StringIO()
        with mock.patch.object(store, "open_store", side_effect=sqlite3.OperationalError("unavailable")):
            with redirect_stdout(output):
                status = store.main(
                    [
                        "record-run",
                        "--skill-path",
                        str(self.skill),
                        "--outcome",
                        "success",
                        "--non-blocking",
                    ]
                )
        payload = json.loads(output.getvalue())
        self.assertEqual(0, status)
        self.assertFalse(payload["ok"])
        self.assertTrue(payload["nonBlocking"])

    def test_plugin_status_does_not_create_a_feedback_database(self) -> None:
        output = io.StringIO()
        untouched = self.root / "untouched.db"
        with mock.patch.object(store, "plugin_eval_availability", return_value={"available": False}):
            with redirect_stdout(output):
                status = store.main(["--db", str(untouched), "plugin-eval-status"])
        self.assertEqual(0, status)
        self.assertEqual({"available": False}, json.loads(output.getvalue()))
        self.assertFalse(untouched.exists())

    def test_read_only_mode_rejects_mutating_commands(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            status = store.main(
                [
                    "--db",
                    str(self.db),
                    "--read-only",
                    "record-run",
                    "--skill-path",
                    str(self.skill),
                ]
            )
        self.assertEqual(2, status)
        self.assertIn("not permitted in read-only mode", json.loads(output.getvalue())["message"])
        self.assertFalse(self.db.exists())

    def test_malformed_observation_does_not_partially_write(self) -> None:
        connection = self.open()
        bad = observation(target_skill_path=self.skill)
        bad["severity"] = "catastrophic"
        with self.assertRaisesRegex(store.FeedbackStoreError, "Invalid severity"):
            self.record_run(connection, [bad])
        self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM skill_runs").fetchone()[0])
        connection.close()

    def test_plugin_eval_detection_supports_checkout_layout_without_dependency(self) -> None:
        root = self.root / "openai-plugins"
        script = root / "plugins" / "plugin-eval" / "scripts" / "plugin-eval.js"
        script.parent.mkdir(parents=True)
        script.write_text("// fixture", encoding="utf-8")
        with mock.patch.object(store, "_which", side_effect=lambda name: "node" if name == "node" else None):
            available = store.plugin_eval_availability({store.PLUGIN_EVAL_ROOT_ENV: str(root)})
        self.assertTrue(available["available"])
        self.assertEqual("checkout", available["mode"])
        with mock.patch.object(store, "_which", return_value=None):
            degraded = store.plugin_eval_availability({})
        self.assertFalse(degraded["available"])
        self.assertEqual("degraded", degraded["mode"])

    def test_skill_routing_is_explicit_and_preserves_adjacent_owners(self) -> None:
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        yaml_text = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        for positive in (
            "$improve-skills",
            "review recent skill performance",
            "improve a named reusable skill",
            "find evidence-backed new-skill opportunities",
        ):
            self.assertIn(positive, skill_text)
        for boundary in (
            "processing a backlog",
            "planning parallel work",
            "synchronizing merged pull requests",
            "ordinary coding",
            "explaining another skill",
        ):
            self.assertIn(boundary, skill_text)
        self.assertIn("allow_implicit_invocation: false", yaml_text)

    def test_self_improvement_and_publication_gates_are_structural_contracts(self) -> None:
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        evaluation_text = (SKILL_ROOT / "references" / "evaluation-and-publishing.md").read_text(
            encoding="utf-8"
        )
        for required in (
            "cannot weaken its own evidence, privacy, evaluation, draft-PR, or human-approval gates",
            "Never merge automatically",
            "Do not implement a proposed new skill",
            "no change needed",
        ):
            self.assertIn(required.casefold(), skill_text.casefold())
        self.assertIn("open a **draft** PR; never merge", evaluation_text)
        self.assertIn("Do not set `agent:ready`, create the skill", evaluation_text)
        self.assertIn("no more than three strong feature requests", evaluation_text)

    def test_upstream_failure_matrix_and_retention_rules_are_documented(self) -> None:
        provenance = (SKILL_ROOT / "references" / "design-provenance.md").read_text(encoding="utf-8")
        evaluation = (SKILL_ROOT / "references" / "evaluation-and-publishing.md").read_text(
            encoding="utf-8"
        )
        issues = (
            "#58", "#55", "#54", "#53", "#47", "#44", "#40", "#39", "#34",
            "#33", "#31", "#30", "#29", "#28", "#26", "#25", "#24", "#23",
            "#22", "#21", "#20", "#19", "#18", "#17", "#16",
        )
        for issue in issues:
            self.assertIn(issue, provenance)
        self.assertIn("Keep the active baseline/after comparison", evaluation)
        self.assertIn("Never recursively clean a broad or computed path", evaluation)


if __name__ == "__main__":
    unittest.main()
