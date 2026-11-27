"""Frozen acceptance examples for the cross-source skills review."""
from contextlib import closing
import importlib.util
from pathlib import Path

from test_feedback_store import StoreCase, make_skill, observation, store


spec = importlib.util.spec_from_file_location(
    "review_report", Path(__file__).resolve().parents[1] / "scripts" / "review_report.py"
)
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class ReviewReportTests(StoreCase):
    def test_junction_evidence_from_mixed_sources_and_duplicate_reports(self):
        with closing(self.open()) as db:
            owner = make_skill(self.root, "process-issues")
            failure = "The bundle CLI returned empty output when invoked through a Windows directory junction."
            variant = "Invoking the bundle CLI via a directory junction produced empty output."
            unrelated = "A Windows compilation job truncated long directory names while staging assets."
            cmd = "Run node review-bundle-cli.mjs invalid through the installed junction."
            for text, context in [(failure, "one"), (failure, "one"), (variant, "two")]:
                detail = observation(text, evidence_type="objective-check", target_skill_path=owner)
                detail["workaround_summary"] = cmd
                self.record_run(db, [detail], context_path=self.root / context)
            detail = observation(variant, target_kind="infrastructure", target_component="node-cli")
            self.record_run(db, [detail], source_kind="agent", skill_path=None, context_path=None)
            self.record_run(db, [observation(unrelated)])
            self.record_run(db)

            result = report.build_review_report(db, participating_skills=["unused-skill"])
            self.assertEqual(2, len(result["findings"]))
            finding = result["findings"][0]
            self.assertEqual(4, finding["distinctLiveRuns"])
            self.assertEqual(2, finding["knownContextCount"])
            self.assertEqual(1, finding["possibleDuplicateReports"])
            self.assertIn("process-issues", finding["reportedOwners"])
            self.assertIn("infrastructure:node-cli", finding["reportedOwners"])
            self.assertIn(cmd, finding["recordedChecksOrWorkarounds"])
            self.assertEqual({"skill", "agent"}, {item["sourceKind"] for item in finding["evidence"]})
            coverage = result["coverage"]
            self.assertEqual(["unused-skill"], coverage["skillsWithoutRecordedRuns"])
            self.assertEqual(5, coverage["liveSkillRuns"])
            self.assertEqual(1, coverage["liveAgentRuns"])
            self.assertEqual(1, coverage["liveSkillRunsWithoutObservation"])
            self.assertEqual(5, coverage["untriagedObservations"])
            self.assertIsNone(coverage["totalInvocations"])
            self.assertEqual(0, db.execute("SELECT count(*) FROM candidate_clusters").fetchone()[0])

    def test_closed_cluster_with_later_similar_signal_is_flagged_without_mutation(self):
        with closing(self.open()) as db:
            summary = "The export command produced an empty document for a populated collection."
            old = self.record_run(db, [observation(summary)], completed_at="2026-01-01T00:00:00Z",
                                  started_at="2026-01-01T00:00:00Z")
            group = store.cluster_observations(db, problem_key="empty-export", kind="existing-skill",
                canonical_problem="An export of a populated collection was empty.",
                observation_ids=old["observationIds"])
            db.execute("UPDATE candidate_clusters SET state='monitoring' WHERE cluster_id=?", (group["clusterId"],))
            db.execute("""INSERT INTO cluster_state_history VALUES
                ('fixture-transition', ?, 'implemented', 'monitoring','Start monitoring','2026-01-02T00:00:00Z')""",
                (group["clusterId"],))
            self.record_run(db, [observation(summary)], completed_at="2026-01-03T00:00:00Z",
                            started_at="2026-01-03T00:00:00Z")
            result = report.build_review_report(db, since="2026-01-02T00:00:00Z")
            self.assertEqual(1, len(result["findings"]))
            finding = result["findings"][0]
            self.assertEqual("empty-export", finding["problemKey"])
            self.assertEqual(1, finding["distinctLiveRuns"])
            self.assertTrue(finding["possibleRecurrence"])
            self.assertEqual("monitoring", finding["state"])

    def test_empty_store_and_empty_window_have_distinct_coverage(self):
        with closing(self.open()) as db:
            self.assertEqual("empty", report.build_review_report(db)["coverage"]["storeStatus"])
            self.record_run(db)
            result = report.build_review_report(db, since="2100-01-01T00:00:00Z")
            self.assertEqual("no-records-in-window", result["coverage"]["storeStatus"])
            self.assertEqual([], result["findings"])

    def test_v4_backfill_has_unknown_event_version_and_does_not_inflate_live_counts(self):
        with closing(self.open(target_schema_version=4)) as db:
            store.import_backfill(db, source_key="legacy-fixture", source_type="github",
                observer_skill_path=self.skill, observations=[observation()])
            result = report.build_review_report(db, participating_skills=["sample-skill"])
            coverage = result["coverage"]
            self.assertEqual(1, coverage["historicalImports"])
            self.assertEqual(0, coverage["liveSkillRuns"])
            self.assertEqual(["sample-skill"], coverage["skillsWithoutRecordedRuns"])
            evidence = result["findings"][0]["evidence"][0]
            self.assertEqual("backfill", evidence["runKind"])
            self.assertIsNone(evidence["eventAt"])
            self.assertIsNone(evidence["affectedVersion"])
            self.assertEqual("unknown", evidence["historicalDisposition"])
            self.assertEqual(4, db.execute("SELECT version FROM schema_metadata").fetchone()[0])

    def test_similar_command_with_different_failure_stays_separate(self):
        with closing(self.open()) as db:
            for summary in (
                "The review bundle CLI produced no JSON through a directory junction and returned exit zero.",
                "The junction target printed JSON while the review CLI alias exited successfully without a receipt.",
                "The review bundle CLI rejected obsolete manifest fields and named the unsupported schema.",
            ):
                self.record_run(db, [observation(summary)])
            findings = report.build_review_report(db)["findings"]
            self.assertEqual([2, 1], sorted((f["distinctLiveRuns"] for f in findings), reverse=True))
            distinct = next(f for f in findings if f["distinctLiveRuns"] == 1)
            self.assertIn("obsolete manifest", distinct["summary"])

    def test_offset_and_submillisecond_window_uses_actual_completion(self):
        with closing(self.open()) as db:
            times = ("2026-01-01T00:00:00.123456+00:00", "2025-12-31T19:00:00.123457-05:00")
            for stamp in times:
                self.record_run(db, [observation()], completed_at=stamp, started_at=stamp)
            result = report.build_review_report(db, since="2026-01-01T00:00:00.123457")
            self.assertEqual(1, result["coverage"]["liveSkillRuns"])
            self.assertEqual(1, result["coverage"]["observations"])
            self.assertEqual(times[1], result["findings"][0]["evidence"][0]["eventAt"])
