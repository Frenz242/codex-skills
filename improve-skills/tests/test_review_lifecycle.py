"""Exercise an explicit review and its evaluation gates using generalized fixtures."""

from contextlib import closing
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_feedback_store import MODULE_PATH, make_skill, observation, store


class ReviewLifecycleTests(unittest.TestCase):
    def setUp(self):
        # Public CLI durability checks require a user-local, non-temporary root.
        self.fixture = tempfile.TemporaryDirectory(dir=Path.home(), prefix=".skill-review-test-")
        self.addCleanup(self.fixture.cleanup)
        self.root = Path(self.fixture.name)
        self.db = self.root / "fixture.db"

    def review(self, expected_status=0):
        result = subprocess.run(
            [sys.executable, "-B", str(MODULE_PATH), "--db", str(self.db),
             "review", "--skill", "sample-skill", "--skill", "absent-skill"],
            capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(expected_status, result.returncode, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_distinguishes_missing_empty_and_unreadable_store(self):
        self.assertEqual("missing", self.review()["coverage"]["storeStatus"])
        self.assertFalse(self.db.exists())
        connection, _ = store.open_store(self.db)
        connection.close()
        self.assertEqual("empty", self.review()["coverage"]["storeStatus"])
        self.db.write_bytes(b"unreadable database fixture")
        report = self.review(expected_status=2)
        self.assertEqual("unavailable", report["coverage"]["storeStatus"])
        self.assertTrue(report["coverageGaps"])

    def test_detect_evaluate_and_link_a_disposition(self):
        skill = make_skill(self.root, "sample-skill")
        script = skill / "probe.py"
        script.write_text("print('missing')\n", encoding="utf-8")
        criteria = self.root / "criteria.txt"
        criteria.write_text("The probe returns ready.", encoding="utf-8")
        holdout = self.root / "holdout.txt"
        holdout.write_text("Importing the probe is silent.", encoding="utf-8")

        def probe(*arguments):
            result = subprocess.run([sys.executable, "-B", *arguments], cwd=skill, check=True,
                                    capture_output=True, text=True, timeout=10)
            return result.stdout.strip()

        with closing(store.open_store(self.db)[0]) as conn:
            record = store.record_run(
                conn, skill_path=skill, invocation_mode="explicit", outcome="partial",
                observations=[observation("A status probe gave the wrong output.", evidence_type="objective-check")],
            )
            report = self.review()
            self.assertEqual(1, report["coverage"]["untriagedObservations"])
            self.assertTrue(report["findings"])
            group = store.cluster_observations(conn, problem_key="incorrect-status-probe", kind="existing-skill",
                canonical_problem="A status probe returned unexpected output.", observation_ids=record["observationIds"])
            eval_id = store.begin_evaluation(conn, cluster_id=group["clusterId"], skill_path=skill,
                backend="degraded", criteria_file=criteria, holdout_file=holdout)["evaluationId"]

            def grade(phase, actual, expected):
                artifact = self.root / (phase + ".json")
                artifact.write_text(json.dumps({"expected": expected, "actual": actual}), encoding="utf-8")
                status = "pass" if actual == expected else "fail"
                store.record_evaluation_result(conn, evaluation_id=eval_id, phase=phase,
                    result_file=artifact, result_status=status)
                return status

            self.assertEqual("fail", grade("baseline", probe("probe.py"), "ready"))
            script.write_text("if __name__ == '__main__':\n    print('ready')\n", encoding="utf-8")
            self.assertEqual("pass", grade("experiment", probe("probe.py"), "ready"))
            self.assertEqual("pass", grade("holdout", probe("-c", "import probe"), ""))
            decision = store.decide_evaluation(conn, evaluation_id=eval_id, decision="recommend", after_skill_path=skill)
            self.assertFalse(decision["draftPrEligible"])
            link = store.link_entity(conn, entity_type="evaluation", entity_id=eval_id,
                                     link_type="outcome", external_ref="probe-correction-recommended")
            self.assertTrue(link["ok"])
            final = self.review()
            self.assertEqual(1, final["coverage"]["evaluations"])
            finding = next(item for item in final["findings"] if item["problemKey"] == "incorrect-status-probe")
            evaluated, = finding["evaluations"]
            self.assertEqual("recommended", evaluated["status"])
            self.assertNotEqual(evaluated["beforeVersion"], evaluated["afterVersion"])
            self.assertEqual([("baseline", "fail"), ("experiment", "pass"), ("holdout", "pass")],
                             [(phase["phase"], phase["resultStatus"]) for phase in evaluated["phases"]])
            self.assertIn({"type": "outcome", "ref": "probe-correction-recommended"}, evaluated["links"])

    def test_frozen_or_failing_holdout_blocks_promotion(self):
        skill = make_skill(self.root, "sample-skill")
        criterion = self.root / "check.txt"
        criterion.write_text("Frozen fixture", encoding="utf-8")
        with closing(store.open_store(self.db)[0]) as conn:
            run = store.record_run(conn, skill_path=skill, invocation_mode="explicit", outcome="partial",
                                   observations=[observation()])
            group = store.cluster_observations(conn, problem_key="holdout-fixture", kind="existing-skill",
                canonical_problem="Exercise holdout protection.", observation_ids=run["observationIds"])
            # Synthetic backend results exercise the promotion gate itself.
            eval_id = store.begin_evaluation(conn, cluster_id=group["clusterId"], skill_path=skill,
                backend="plugin-eval", criteria_file=criterion, holdout_file=criterion)["evaluationId"]
            for phase, status in (("baseline", "fail"), ("experiment", "pass"), ("regression", "pass")):
                store.record_evaluation_result(conn, evaluation_id=eval_id, phase=phase,
                                              result_file=criterion, result_status=status)
            (skill / "helper.py").write_text("print('changed')\n", encoding="utf-8")
            with self.assertRaisesRegex(store.FeedbackStoreError, "frozen holdout"):
                store.decide_evaluation(conn, evaluation_id=eval_id, decision="keep", after_skill_path=skill)
            store.record_evaluation_result(conn, evaluation_id=eval_id, phase="holdout",
                                          result_file=criterion, result_status="fail")
            with self.assertRaisesRegex(store.FeedbackStoreError, "passing regression or holdout"):
                store.decide_evaluation(conn, evaluation_id=eval_id, decision="keep", after_skill_path=skill)
            # A new iteration must repeat both the previously passing regression and the failed holdout.
            store.record_evaluation_result(conn, evaluation_id=eval_id, phase="experiment",
                                          result_file=criterion, result_status="pass")
            with self.assertRaisesRegex(store.FeedbackStoreError, "frozen holdout"):
                store.decide_evaluation(conn, evaluation_id=eval_id, decision="keep", after_skill_path=skill)
            store.record_evaluation_result(conn, evaluation_id=eval_id, phase="holdout",
                                          result_file=criterion, result_status="pass")
            with self.assertRaisesRegex(store.FeedbackStoreError, "latest experiment"):
                store.decide_evaluation(conn, evaluation_id=eval_id, decision="keep", after_skill_path=skill)
            store.record_evaluation_result(conn, evaluation_id=eval_id, phase="regression",
                                          result_file=criterion, result_status="pass")
            self.assertTrue(store.decide_evaluation(conn, evaluation_id=eval_id, decision="keep",
                                                    after_skill_path=skill)["draftPrEligible"])
