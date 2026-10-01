"""Exercise installed launcher copies against isolated, durable fixture stores."""

from contextlib import closing, redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from test_feedback_store import POSIX_SHELL, SKILL_ROOT, make_skill, observation, store


class NonBlockingArgumentTests(unittest.TestCase):
    def test_parse_errors_are_structured_without_opening_a_store(self):
        for arguments in (
            ["--skill-path", "sample-skill", "--non-blocking"],
            ["record-run", "--outcome", "invalid", "--non-blocking"],
            ["record-run", "--skill-path", "--non-blocking"],
            ["record-run", "--unknown", "private-value", "--non-blocking"],
            ["record-run", "--db", "private-value", "--non-blocking"],
        ):
            with self.subTest(arguments=arguments):
                output = io.StringIO()
                with mock.patch.object(store, "open_store") as opened, redirect_stdout(output):
                    self.assertEqual(0, store.main(arguments))
                opened.assert_not_called()
                payload = json.loads(output.getvalue())
                self.assertFalse(payload["ok"])
                self.assertTrue(payload["nonBlocking"])
                self.assertEqual("FeedbackArgumentError", payload["error"])
                self.assertIn("record-run", payload["message"])
                self.assertNotIn("private-value", output.getvalue())

    def test_positional_token_does_not_opt_in(self):
        with mock.patch("sys.stderr", new=io.StringIO()), self.assertRaises(SystemExit) as error:
            store.main(["record-run", "--", "--non-blocking"])
        self.assertEqual(2, error.exception.code)


class RecorderLauncherIntegrationTests(unittest.TestCase):
    def setUp(self):
        # Use a unique home child, outside OS temp and Git, so the real durability
        # checks stay enabled. No production database or unsafe override is used.
        self.fixture = tempfile.TemporaryDirectory(prefix=".feedback-launcher-test-", dir=Path.home())
        self.addCleanup(self.fixture.cleanup)
        self.root = Path(self.fixture.name).resolve()
        self.assertTrue(store.classify_database_path(self.root / "fixture.db")["durable"])
        self.scripts = self.root / "installed skills" / "improve-skills" / "scripts"
        self.scripts.mkdir(parents=True)
        for name in ("feedback_store.py", "run_feedback_store.ps1", "run_feedback_store.sh"):
            shutil.copy2(SKILL_ROOT / "scripts" / name, self.scripts / name)
        self.skill = make_skill(self.root, "participating skill")
        self.cwd = self.root / "unrelated project"
        self.cwd.mkdir()
        self.db = self.root / "isolated feedback.db"
        self.environment = os.environ.copy()
        self.environment.pop("CODEX_SKILL_FEEDBACK_DB", None)
        self.environment["CODEX_SKILL_PYTHON"] = sys.executable
        self.environment["PYTHONDONTWRITEBYTECODE"] = "1"

    def run_cli(self, prefix, *arguments):
        return subprocess.run(
            [*prefix, *arguments], cwd=self.cwd, env=self.environment,
            capture_output=True, text=True, check=False, timeout=30,
        )

    def exercise_launcher(self, prefix):
        def invoke(*arguments):
            return self.run_cli(prefix, "--db", str(self.db), *arguments)

        # Failure before any successful record must not even create a store.
        failed = invoke("--skill-path", str(self.skill), "--non-blocking")
        self.assertEqual(0, failed.returncode, failed.stderr)
        self.assertFalse(json.loads(failed.stdout)["ok"])
        self.assertTrue(json.loads(failed.stdout)["nonBlocking"])
        self.assertIn("record-run", json.loads(failed.stdout)["message"])
        self.assertFalse(self.db.exists())

        arguments = [
            "record-run", "--skill-path", str(self.skill),
            "--invocation-mode", "explicit", "--outcome", "success",
            "--context-path", str(self.cwd), "--non-blocking",
        ]
        minimal = invoke(*arguments)
        self.assertEqual(0, minimal.returncode, minimal.stderr)
        first = json.loads(minimal.stdout)
        self.assertTrue(first["ok"])
        self.assertEqual(0, first["observationCount"])
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(
                [(first["runId"], "success", 0)],
                connection.execute("SELECT run_id, outcome, observation_count FROM skill_runs").fetchall(),
            )

        details = self.root / "sanitized observation.json"
        details.write_text(json.dumps(observation(
            evidence_type="objective-check", confidence_tier="objective-failure",
        )), encoding="utf-8")
        recorded = invoke(*arguments, "--observation-file", str(details))
        self.assertEqual(0, recorded.returncode, recorded.stderr)
        second = json.loads(recorded.stdout)
        self.assertTrue(second["ok"])
        self.assertEqual(1, second["observationCount"])
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(2, connection.execute("SELECT COUNT(*) FROM skill_runs").fetchone()[0])
            self.assertEqual(
                [(second["observationIds"][0], second["runId"], "observed")],
                connection.execute("SELECT observation_id, run_id, state FROM observations").fetchall(),
            )
            self.assertEqual(
                [(second["observationIds"][0], None, "observed")],
                connection.execute(
                    "SELECT observation_id, from_state, to_state FROM observation_state_history"
                ).fetchall(),
            )
            self.assertEqual("ok", connection.execute("PRAGMA integrity_check").fetchone()[0])

        # Both failed forms leave existing data untouched.
        for non_blocking in (True, False):
            with self.subTest(non_blocking=non_blocking):
                extra = ["--non-blocking"] if non_blocking else []
                result = invoke("--skill-path", "sync-after-merge", *extra)
                self.assertEqual(0 if non_blocking else 2, result.returncode, result.stderr)
                if non_blocking:
                    self.assertFalse(json.loads(result.stdout)["ok"])
                else:
                    self.assertIn("invalid choice", result.stderr)
                with closing(sqlite3.connect(self.db)) as connection:
                    self.assertEqual(2, connection.execute("SELECT COUNT(*) FROM skill_runs").fetchone()[0])
                    self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0])

        for arguments in (["--help"], ["record-run", "--help", "--non-blocking"]):
            result = self.run_cli(prefix, *arguments)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("usage:", result.stdout)

        health = self.run_cli(prefix, "--db", str(self.db), "--read-only", "health")
        self.assertEqual(0, health.returncode, health.stderr)
        self.assertTrue(json.loads(health.stdout)["ok"])

        # Valid syntax with a runtime validation error still forwards exit 2.
        runtime_failure = invoke("record-run", "--skill-path", str(self.root / "missing skill"))
        self.assertEqual(2, runtime_failure.returncode, runtime_failure.stderr)
        self.assertFalse(json.loads(runtime_failure.stdout)["ok"])
        non_blocking_failure = invoke(
            "record-run", "--skill-path", str(self.root / "missing skill"), "--non-blocking",
        )
        self.assertEqual(0, non_blocking_failure.returncode, non_blocking_failure.stderr)
        self.assertFalse(json.loads(non_blocking_failure.stdout)["ok"])

    @unittest.skipUnless(os.name == "nt" and shutil.which("pwsh"), "requires Windows PowerShell 7")
    def test_powershell_7(self):
        self.exercise_launcher([
            shutil.which("pwsh"), "-NoProfile", "-File", str(self.scripts / "run_feedback_store.ps1"),
        ])

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell"), "requires Windows PowerShell 5.1")
    def test_windows_powershell_51(self):
        # A pwsh parent can export its incompatible module path. Give the 5.1
        # child its own built-in modules without loading either user's profile.
        executable = Path(shutil.which("powershell"))
        self.environment["PSModulePath"] = str(executable.parent / "Modules")
        self.exercise_launcher([
            str(executable), "-NoProfile", "-File", str(self.scripts / "run_feedback_store.ps1"),
        ])

    @unittest.skipUnless(POSIX_SHELL, "requires POSIX sh")
    def test_posix_sh(self):
        self.exercise_launcher([POSIX_SHELL, (self.scripts / "run_feedback_store.sh").as_posix()])


if __name__ == "__main__":
    unittest.main()
