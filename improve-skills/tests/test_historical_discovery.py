from contextlib import closing
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from test_feedback_store import StoreCase, make_skill, observation, store


sys.path.insert(0, str(Path(store.__file__).parent))
import history_sources


class HistoricalDiscoveryTests(StoreCase):
    repo = "example/skills"
    commit = "a" * 40

    def setUp(self):
        super().setUp()
        affected = make_skill(self.root, "new-project")
        self.records = [
            {"issue": 30, "observation": observation(
                "Delivered artifact was unreadable to its recipient.", target_kind="infrastructure",
                target_component="artifact-handoff", suggestion_kind="shared-infrastructure")},
            {"issue": 39, "event_at": "2026-10-14T16:39:20Z", "affected_version": "b" * 40,
             "observation": observation("Two remote selection instructions conflicted.",
                                        target_skill_path=affected)},
        ]

    def github(self, *args):
        if args[:2] == ("repo", "view"):
            return {"defaultBranchRef": {"name": "main"}, "visibility": "PUBLIC"}
        if args[:2] == ("issue", "view"):
            number = {30: 31, 39: 42}[int(args[2])]
            return {"state": "CLOSED", "stateReason": "COMPLETED", "closedByPullRequestsReferences": [
                {"number": number, "repository": {"owner": {"login": "example"}, "name": "skills"}}]}
        if args[:2] == ("pr", "view") and int(args[2]) in (31, 42):
            return {"mergedAt": "2026-10-15T00:00:00Z", "mergeCommit": {"oid": self.commit}}
        if args[:2] == ("api", f"repos/{self.repo}/compare/{self.commit}...main"):
            return "ahead"
        self.fail(f"Unexpected source request {args[:2]}")

    def discover(self, conn, records):
        return store.discover_history(conn, repo=self.repo, records=records, observer_skill_path=self.skill)

    def test_independent_owners_and_fix_links_across_overlapping_artifacts(self):
        with closing(self.open()) as conn, patch.object(history_sources, "github", self.github):
            first = self.discover(conn, self.records)
            self.assertEqual(["fixed", "fixed"], [item["disposition"] for item in first["incidents"]])
            # A later pass through review feedback and its corrective PR canonicalizes to the source issue.
            again = self.discover(conn, [self.records[1], *self.records])
            self.assertEqual(2, len(again["incidents"]))
            self.assertTrue(all(r["alreadyProcessed"] for r in again["incidents"]))
            self.assertEqual(2, conn.execute("SELECT count(*) FROM observations").fetchone()[0])
            self.assertEqual(0, conn.execute("SELECT count(*) FROM skill_runs WHERE run_kind='live'").fetchone()[0])
            owners = conn.execute("""
                SELECT coalesce(v.skill_name,o.target_component), h.affected_version, h.event_at
                FROM observations o JOIN historical_incidents h USING(run_id)
                LEFT JOIN skill_versions v ON v.version_id=o.primary_skill_version_id
                ORDER BY 1
            """).fetchall()
            self.assertEqual(("artifact-handoff", None, None), tuple(owners[0]))
            self.assertEqual("new-project", owners[1][0])
            self.assertEqual("b" * 40, owners[1][1])
            self.assertTrue(owners[1][2].startswith("2026-10-14"))
            queried = store.query_observations(conn, skill_name="new-project")[0]
            self.assertEqual(("backfill", "fixed", "b" * 40),
                             (queried["run_kind"], queried["historical_disposition"],
                              queried["historical_affected_version"]))
            refs = [r[0] for r in conn.execute("SELECT external_ref FROM entity_links WHERE link_type='pr'")]
            self.assertCountEqual([f"https://github.com/{self.repo}/pull/{i}" for i in (31, 42)], refs)

    def test_changed_evidence_keeps_initial_facts_and_rejects_conflicting_owners(self):
        with closing(self.open()) as conn, patch.object(history_sources, "github", self.github):
            self.discover(conn, self.records)
            original = self.records[1]
            edited = dict(original, observation=dict(original["observation"], summary="Same problem rephrased."),
                          event_at="2026-10-14T11:39:20-05:00")
            self.assertTrue(self.discover(conn, [edited])["incidents"][0]["retainedEarlierSummary"])
            different_owner = dict(original, observation=self.records[0]["observation"])
            with self.assertRaisesRegex(store.FeedbackStoreError, "Conflicting historical owner"):
                self.discover(conn, [different_owner])
            with self.assertRaisesRegex(store.FeedbackStoreError, "Conflicting historical attribution"):
                self.discover(conn, [dict(original, affected_version="c" * 40)])
            self.assertEqual(2, conn.execute("SELECT count(*) FROM observations").fetchone()[0])

    def test_source_shape_and_partial_write_recovery(self):
        with closing(self.open()) as conn:
            with patch.object(history_sources, "github", return_value={"defaultBranchRef": None}):
                self.assertFalse(self.discover(conn, self.records)["ok"])
            with patch.object(history_sources, "github", self.github):
                with patch.object(store, "link_entity", side_effect=store.FeedbackStoreError("fixture")):
                    with self.assertRaises(store.FeedbackStoreError):
                        self.discover(conn, self.records)
                self.assertEqual(0, conn.execute("SELECT count(*) FROM skill_runs").fetchone()[0])
                self.assertTrue(self.discover(conn, self.records)["ok"])

    def test_inaccessible_branch_and_unmerged_history_do_not_claim_a_fix(self):
        def inspect(*args):
            if args[0] == "api":
                return "diverged"
            if args[:3] == ("issue", "view", "39"):
                raise history_sources.HistoryGap("GitHub source unavailable or unreadable.")
            return self.github(*args)
        with closing(self.open()) as conn, patch.object(history_sources, "github", inspect):
            result = self.discover(conn, self.records)
            self.assertFalse(result["ok"])
            self.assertEqual(2, result["coverageGaps"][0]["entry"])
            self.assertEqual("unknown", result["incidents"][0]["disposition"])
            self.assertEqual(1, conn.execute("SELECT count(*) FROM observations").fetchone()[0])

    def test_invalid_event_and_private_repo_leave_no_raw_identifiers(self):
        def inspect(*args):
            result = self.github(*args)
            if args[:2] == ("repo", "view"):
                result["visibility"] = "PRIVATE"
            return result
        with closing(self.open()) as conn, patch.object(history_sources, "github", inspect):
            self.discover(conn, self.records[:1])
            self.assertFalse(any(self.repo in row[0] for row in conn.execute("SELECT external_ref FROM entity_links")))
            with self.assertRaises(store.FeedbackStoreError):
                self.discover(conn, [dict(self.records[0], affected_version="unverified")])
            self.assertEqual(1, conn.execute("SELECT count(*) FROM historical_incidents").fetchone()[0])

    def test_inventory_reports_truncation_without_import(self):
        with patch.object(history_sources, "github", return_value=[{"number": n} for n in range(101)]):
            result = history_sources.inventory(self.repo)
            self.assertEqual(100, len(result["issues"]))
            self.assertTrue(result["moreAvailable"])
            self.assertTrue(result["coverageGaps"])
