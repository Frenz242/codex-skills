"""Read-only coverage and candidate findings for an explicit skills review."""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
import math
import re
import sqlite3


# Similar text is a triage hint. Only analyst-confirmed cluster membership is durable.
_STOP_WORDS = frozenset(
    "a an and are as at be been but by did do for from had has have in into is it its of on or "
    "that the their then there this through to was were when with without".split()
)


def _terms(text):
    words = re.findall(r"[^\W_]+", text.casefold())
    terms = set()
    for word in words:
        if word in _STOP_WORDS or len(word) < 2:
            continue
        # Light inflection normalization keeps directory names and short CLI flags legible.
        if len(word) > 5:
            word = re.sub(r"(ing|ed|s)$", "", word)
        terms.add(word)
    return terms


def _similarity(left, right, weights):
    shared = left & right
    if left == right and left:
        return 1.0
    if len(shared) < 3:
        return 0.0
    # Dice similarity weighted by distinctiveness in the evidence corpus.
    return 2 * sum(weights[t] for t in shared) / (
        sum(weights[t] for t in left) + sum(weights[t] for t in right)
    )


def _instant(text):
    if text is None:
        return None
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _utc_text(value):
    instant = _instant(value)
    return instant.isoformat(timespec="microseconds") if instant else None


def _coverage(db, participants, since):
    rows = list(db.execute("""
        SELECT r.run_kind, r.source_kind, v.skill_name, v.content_hash, v.bundle_hash,
               count(*) AS runs, sum(r.observation_count=0) AS no_detail,
               min(skill_review_utc(r.completed_at)) AS first_at, max(skill_review_utc(r.completed_at)) AS last_at
        FROM skill_runs r LEFT JOIN skill_versions v ON v.version_id=r.skill_version_id
        WHERE (? IS NULL OR skill_review_utc(r.completed_at) >= ?)
        GROUP BY r.run_kind, r.source_kind, v.skill_name, v.content_hash, v.bundle_hash
        ORDER BY v.skill_name, first_at, v.content_hash, v.bundle_hash
    """, (since, since)))
    live_skills = [r for r in rows if r["run_kind"] == "live" and r["source_kind"] == "skill"]
    status = "available"
    if not rows:
        status = "no-records-in-window" if db.execute("SELECT 1 FROM skill_runs LIMIT 1").fetchone() else "empty"
    return {
        "storeStatus": status,
        "since": since,
        "firstRecordedAt": min((r["first_at"] for r in rows), default=None),
        "lastRecordedAt": max((r["last_at"] for r in rows), default=None),
        "windowBasis": "Run completion for live evidence and import completion for historical evidence.",
        "totalInvocations": None,
        "liveSkillRuns": sum(r["runs"] for r in live_skills),
        "liveSkillRunsWithoutObservation": sum(r["no_detail"] for r in live_skills),
        "liveAgentRuns": sum(r["runs"] for r in rows if r["run_kind"] == "live" and r["source_kind"] == "agent"),
        "historicalImports": sum(r["runs"] for r in rows if r["run_kind"] == "backfill"),
        "skillsWithoutRecordedRuns": sorted(set(participants) - {r["skill_name"] for r in live_skills}),
        "liveRunsByVersion": [
            {"skill": r["skill_name"], "contentHash": r["content_hash"], "bundleHash": r["bundle_hash"],
             "runs": r["runs"], "runsWithoutObservation": r["no_detail"]}
            for r in live_skills
        ],
        "evaluations": db.execute(
            "SELECT count(*) FROM evaluations WHERE (? IS NULL OR skill_review_utc(created_at) >= ?)", (since, since)
        ).fetchone()[0],
    }


def _records(db):
    # Legacy backfill has import-time identities. Never advertise those as historical versions.
    current_history = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='historical_incidents'"
    ).fetchone()
    history_fields = "h.event_at, h.affected_version, h.disposition" if current_history else (
        "NULL AS event_at, NULL AS affected_version, NULL AS disposition"
    )
    history_join = "LEFT JOIN historical_incidents h ON h.run_id=r.run_id" if current_history else ""
    return list(db.execute(f"""
        SELECT o.observation_id, o.summary, o.workaround_summary, o.primary_target_kind,
               o.category, o.evidence_type, o.confidence_tier, o.positive_evidence, o.target_component, o.state,
               tv.skill_name AS owner, tv.bundle_hash AS target_version,
               r.source_kind, r.run_kind, r.run_id, r.completed_at, skill_review_utc(r.completed_at) AS completed_utc, r.context_hash,
               sv.skill_name AS observer, sv.bundle_hash AS observer_version, {history_fields}
        FROM observations o JOIN skill_runs r ON r.run_id=o.run_id
        LEFT JOIN skill_versions tv ON tv.version_id=o.primary_skill_version_id
        LEFT JOIN skill_versions sv ON sv.version_id=r.skill_version_id
        {history_join}
        ORDER BY completed_utc, o.observation_id
    """))


def _finding(cluster, members, since, links):
    visible = [(row, relation) for row, relation in members if _in_window(row, since)]
    if not visible:
        return None
    evidence = []
    owners = set()
    checks = set()
    contexts = set()
    live_runs = set()
    repeats = Counter()
    affected = defaultdict(set)
    references = set(links.get(cluster["cluster_id"], ())) if cluster else set()
    recurrence = False
    for row, relation in visible:
        historical = row["run_kind"] == "backfill"
        timestamp = row["event_at"] if historical else row["completed_at"]
        version = row["affected_version"] if historical else row["target_version"]
        owner = row["owner"] or row["primary_target_kind"]
        if row["target_component"]:
            owner += ":" + row["target_component"]
        owners.add(owner)
        references.update(links.get(row["observation_id"], ()))
        if row["workaround_summary"]:
            checks.add(row["workaround_summary"])
        positive = bool(row["positive_evidence"]) or relation == "counter-evidence"
        supporting = not positive and relation != "duplicate" and row["state"] not in {"invalid", "duplicate"}
        if supporting:
            if not historical:
                live_runs.add(row["run_id"])
                affected[(owner, version)].add(row["run_id"])
            if row["context_hash"]:
                contexts.add(row["context_hash"])
                repeats[(row["context_hash"], " ".join(row["summary"].casefold().split()))] += 1
            old_version = (cluster and version and version == cluster["before_version"]
                           and version != cluster["after_version"])
            event_time = _instant(timestamp)
            fixed_time = _instant(cluster["last_fix"]) if cluster else None
            if (fixed_time and event_time and event_time > fixed_time
                    and not old_version and row["disposition"] != "fixed"
                    and cluster["state"] in {"implemented", "monitoring", "confirmed"}):
                recurrence = True
        evidence.append({
            "observationId": row["observation_id"], "sourceKind": row["source_kind"], "runKind": row["run_kind"],
            "observerSkill": row["observer"], "observerVersion": row["observer_version"],
            "targetKind": row["primary_target_kind"], "reportedOwner": owner, "affectedVersion": version,
            "eventAt": timestamp, "historicalDisposition": (row["disposition"] or "unknown") if historical else None,
            "relationship": relation, "counterEvidence": positive, "category": row["category"],
            "evidenceType": row["evidence_type"], "confidence": row["confidence_tier"], "summary": row["summary"],
        })
    return {
        "problemKey": cluster["problem_key"] if cluster else None,
        "classification": cluster["kind"] if cluster else None,
        "state": cluster["state"] if cluster else "needs-triage",
        "summary": cluster["canonical_problem"] if cluster else visible[0][0]["summary"],
        "distinctLiveRuns": len(live_runs), "knownContextCount": len(contexts),
        "possibleDuplicateReports": sum(count - 1 for count in repeats.values()),
        "duplicateBasis": "Repeated wording in a known context may describe the same incident.",
        "reportedOwners": sorted(owners), "recordedChecksOrWorkarounds": sorted(checks),
        "liveRunsByAffectedVersion": [
            {"reportedOwner": owner, "affectedVersion": version, "runs": len(runs)}
            for (owner, version), runs in sorted(affected.items(), key=lambda item: (item[0][0], item[0][1] or ""))
        ],
        "links": [{"type": kind, "ref": ref} for kind, ref in sorted(references)],
        "possibleRecurrence": recurrence, "evidence": evidence,
    }


def _in_window(row, since):
    return since is None or (row["completed_utc"] is not None and row["completed_utc"] >= since)


def _evaluations(db, links):
    phases = defaultdict(list)
    for row in db.execute("""
        SELECT evaluation_id, phase, iteration, result_status, result_hash FROM evaluation_runs
        ORDER BY iteration, CASE phase WHEN 'baseline' THEN 1 WHEN 'experiment' THEN 2
                                       WHEN 'regression' THEN 3 ELSE 4 END
    """):
        phases[row["evaluation_id"]].append({"phase": row["phase"], "iteration": row["iteration"],
            "resultStatus": row["result_status"], "resultHash": row["result_hash"]})
    grouped = defaultdict(list)
    for row in db.execute("""
        SELECT e.*, before.bundle_hash AS before_version, after.bundle_hash AS after_version
        FROM evaluations e JOIN skill_versions before ON before.version_id=e.target_skill_version_id
        LEFT JOIN skill_versions after ON after.version_id=e.after_skill_version_id
        ORDER BY skill_review_utc(e.created_at), e.evaluation_id
    """):
        key = row["evaluation_id"]
        grouped[row["cluster_id"]].append({
            "evaluationId": key, "backend": row["backend"], "status": row["status"], "decision": row["decision"],
            "beforeVersion": row["before_version"], "afterVersion": row["after_version"],
            "phases": phases[key], "links": [{"type": kind, "ref": ref} for kind, ref in sorted(links[key])],
        })
    return grouped


def build_review_report(connection: sqlite3.Connection, *, participating_skills: Iterable[str] = (), since=None):
    """Return local triage suggestions without changing memberships, issue state or evaluations."""
    # SQLite date functions lose sub-millisecond precision. Normalize legacy offsets at
    # query time; the function is connection-local and read-only stores remain untouched.
    connection.create_function("skill_review_utc", 1, _utc_text, deterministic=True)
    if since is not None:
        since = _utc_text(since)
        if since is None:
            raise ValueError("since must be an ISO-8601 timestamp")
    coverage = _coverage(connection, participating_skills, since)
    clusters = {r["cluster_id"]: r for r in connection.execute("""
        SELECT c.*, COALESCE(
            (SELECT max(skill_review_utc(changed_at)) FROM cluster_state_history WHERE cluster_id=c.cluster_id AND to_state='implemented'),
            (SELECT min(skill_review_utc(changed_at)) FROM cluster_state_history WHERE cluster_id=c.cluster_id AND to_state IN ('monitoring','confirmed'))
        ) AS last_fix, before.bundle_hash AS before_version, after.bundle_hash AS after_version
        FROM candidate_clusters c LEFT JOIN evaluations e ON e.evaluation_id=(
            SELECT evaluation_id FROM evaluations WHERE cluster_id=c.cluster_id AND decision='keep'
            ORDER BY skill_review_utc(decided_at) DESC, evaluation_id DESC LIMIT 1)
        LEFT JOIN skill_versions before ON before.version_id=e.target_skill_version_id
        LEFT JOIN skill_versions after ON after.version_id=e.after_skill_version_id
        ORDER BY c.problem_key
    """)}
    links = defaultdict(list)
    for entity_id, kind, ref in connection.execute("""
        SELECT entity_id, link_type, external_ref FROM entity_links
    """):
        links[entity_id].append((kind, ref))
    evaluations = _evaluations(connection, links)
    memberships = defaultdict(list)
    for entry in connection.execute("SELECT * FROM cluster_observations ORDER BY cluster_id"):
        memberships[entry["observation_id"]].append((entry["cluster_id"], entry["relationship"]))

    groups = defaultdict(list)
    records = _records(connection)
    signatures = {}
    frequencies = Counter()
    for row in records:
        terms = _terms(row["summary"])
        details = terms | _terms(row["workaround_summary"] or "")
        signatures[row["observation_id"]] = (terms, details)
        frequencies.update(details)
    weights = {t: 1 + math.log((len(records) + 1) / (n + 1)) for t, n in frequencies.items()}
    anchors = defaultdict(list)
    candidates = defaultdict(set)

    def add(key, row, relationship):
        groups[key].append((row, relationship))
        signature = signatures[row["observation_id"]]
        # Suggested matches never become anchors in a curated cluster, avoiding drift across reviews.
        if relationship in {"duplicate", "counter-evidence"} or (key in clusters and relationship == "suggested"):
            return
        if signature not in anchors[key]:
            anchors[key].append(signature)
            for term in signature[1]:
                candidates[term].add(key)

    ungrouped = []
    observed = 0
    for row in records:
        in_window = _in_window(row, since)
        observed += in_window
        attached = memberships[row["observation_id"]]
        if attached:
            for key, relationship in attached:
                add(key, row, relationship)
        elif in_window:
            ungrouped.append(row)
    coverage.update(observations=observed, untriagedObservations=len(ungrouped))

    # Start with the most descriptive reports. A candidate must match the group's
    # original anchor; a succession of loosely similar symptoms cannot join groups.
    for row in sorted(ungrouped, key=lambda r: -len(signatures[r["observation_id"]][1])):
        signature = signatures[row["observation_id"]]
        plausible = set().union(*(candidates[t] for t in signature[1]))
        matches = []
        for key in plausible:
            scores = [max(_similarity(signature[0], other[0], weights),
                          _similarity(signature[1], other[1], weights)) for other in anchors[key]]
            if scores and max(scores) >= 0.30 and (key in clusters or scores[0] >= 0.22):
                matches.append((max(scores), key))
        matches.sort(reverse=True)
        clear = matches and (len(matches) == 1 or matches[0][0] > matches[1][0] + 0.05)
        key = matches[0][1] if clear else row["observation_id"]
        add(key, row, "suggested")

    findings = []
    for key, members in groups.items():
        finding = _finding(clusters.get(key), members, since, links)
        if finding:
            finding["evaluations"] = evaluations.get(key, [])
            findings.append(finding)
    priority = {"explicit-user-correction": 0, "explicit-user-feedback": 0, "objective-failure": 1,
                "objective-check": 1, "repeated-independent": 2, "reusable-workaround": 2}

    def order(finding):
        best = min((priority.get(e[field], 3) for e in finding["evidence"]
                    if not e["counterEvidence"] and e["relationship"] != "duplicate"
                    for field in ("category", "evidenceType", "confidence")), default=4)
        return (not finding["possibleRecurrence"], best, -finding["distinctLiveRuns"],
                -finding["knownContextCount"], finding["summary"])

    return {"ok": True, "coverage": coverage, "findings": sorted(findings, key=order)}
