"""Behavioral installer tests. Run: python -m unittest discover -s tests -p test_installer.py -v"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("installer", ROOT / "scripts/install_skills.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skills test ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        for name in ("alpha", "beta", "improve-skills"):
            path = self.source / name
            path.mkdir(parents=True)
            (path / "SKILL.md").write_text(f"---\nname: {name}\n---\nversion one\n")
        self.dest = self.root / "home/.agents/skills"
        self.store = self.root / "store"
        self.args = ["--source", str(self.source), "--dest", str(self.dest), "--store", str(self.store)]

    def run_cli(self, *args, input=None):
        return subprocess.run([sys.executable, str(ROOT / "scripts/install_skills.py"), *self.args, *args],
                              input=input, capture_output=True, text=True)

    def state(self):
        path = next(self.store.glob("state-*.json"))
        return path, json.loads(path.read_text())

    def test_fingerprint_detects_posix_execute_bits(self):
        # Exercise mode hashing on every host, including Windows, without
        # pretending Windows chmod provides POSIX execute-bit semantics.
        root, item = Mock(), Mock()
        root.rglob.return_value = [item]
        item.relative_to.return_value.as_posix.return_value = "launcher.sh"
        item.read_bytes.return_value = b"#!/bin/sh\nexit 0\n"
        with patch.object(m, "is_link", return_value=False), patch.object(m.os, "name", "posix"):
            item.stat.return_value.st_mode = 0o100755
            executable = m.fingerprint(root)
            for mode in (0o100655, 0o100745, 0o100754, 0o100644):
                item.stat.return_value.st_mode = mode
                self.assertNotEqual(m.fingerprint(root), executable)
            item.stat.return_value.st_mode = 0o100555
            self.assertEqual(m.fingerprint(root), executable)

    def test_windows_fingerprint_ignores_execute_bits(self):
        root, item = Mock(), Mock()
        root.rglob.return_value = [item]
        item.relative_to.return_value.as_posix.return_value = "launcher.sh"
        item.read_bytes.return_value = b"#!/bin/sh\nexit 0\n"
        with patch.object(m, "is_link", return_value=False), patch.object(m.os, "name", "nt"):
            item.stat.return_value.st_mode = 0o100755
            executable = m.fingerprint(root)
            item.stat.return_value.st_mode = 0o100644
            self.assertEqual(m.fingerprint(root), executable)

    def make_launcher(self, skill="alpha", mode=0o755):
        launcher = self.source / skill / "launcher.sh"
        launcher.write_text("#!/bin/sh\nprintf 'launcher works\\n'\n")
        launcher.chmod(mode)
        return launcher

    def use_legacy_state(self):
        # Recreate the shipped v1 algorithm independently of production helpers.
        def old_fingerprint(path):
            digest = hashlib.sha256()
            for item in sorted(path.rglob("*")):
                if item.is_file():
                    digest.update(item.relative_to(path).as_posix().encode() + b"\0")
                    digest.update(hashlib.sha256(item.read_bytes()).digest())
            return digest.hexdigest()
        path, state = self.state()
        for name, entry in state.items():
            root = Path(entry["target"]).parent
            parts = [old_fingerprint(root / name)]
            if name != "improve-skills":
                parts.append(old_fingerprint(root / "improve-skills"))
            entry["hash"] = hashlib.sha256("".join(parts).encode()).hexdigest()
            entry.pop("fingerprint_version", None)
        path.write_text(json.dumps(state))
        return path, state

    @unittest.skipIf(os.name == "nt", "requires actual POSIX execute permissions")
    def test_managed_mode_damage_and_shared_helper_are_conflicts(self):
        self.make_launcher()
        self.make_launcher("improve-skills")
        self.assertEqual(self.run_cli("--skills", "alpha").returncode, 0)
        target = (self.dest / "alpha").resolve()
        for launcher in (target / "launcher.sh", target.parent / "improve-skills/launcher.sh"):
            with self.subTest(launcher=launcher):
                launcher.chmod(0o644)
                with self.assertRaises(PermissionError):
                    subprocess.run([str(launcher)], check=True, capture_output=True)
                self.assertIn("conflict: modified managed files", self.run_cli("--list").stdout)
                result = self.run_cli("--skills", "alpha", "--adopt")
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual((self.dest / "alpha").resolve(), target)
                self.assertEqual(launcher.stat().st_mode & 0o111, 0)
                launcher.chmod(0o755)
        self.assertNotIn("conflict", self.run_cli("--list").stdout)

    @unittest.skipIf(os.name == "nt", "requires actual POSIX execute permissions")
    def test_upstream_mode_only_update_installs_executable_launcher(self):
        launcher = self.make_launcher(mode=0o644)
        self.assertEqual(self.run_cli("--skills", "alpha").returncode, 0)
        launcher.chmod(0o755)
        self.assertIn("update available", self.run_cli("--list").stdout)
        result = self.run_cli("--skills", "alpha")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([str(self.dest / "alpha/launcher.sh")], check=True, capture_output=True, text=True)
        self.assertEqual(result.stdout, "launcher works\n")
        self.assertNotIn("update available", self.run_cli("--list").stdout)

    def test_legacy_state_migrates_without_false_content_conflict(self):
        self.make_launcher("improve-skills")
        self.assertEqual(self.run_cli("--skills", "alpha").returncode, 0)
        target = (self.dest / "alpha").resolve()
        if os.name != "nt":
            # Legacy hashes cannot see this damage; migration must use upstream
            # permissions, not record the damaged file as the new baseline.
            (target.parent / "improve-skills/launcher.sh").chmod(0o644)
        path, state = self.use_legacy_state()
        result = self.run_cli("--list")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("conflict", result.stdout)
        self.assertEqual(json.loads(path.read_text()), state)  # --list is read-only.
        if os.name == "nt":
            self.assertNotIn("update available", result.stdout)
        else:
            self.assertIn("update available", result.stdout)
        result = self.run_cli("--skills", "alpha")
        self.assertEqual(result.returncode, 0, result.stderr)
        if os.name != "nt":
            _, migrated = self.state()
            self.assertEqual(migrated["alpha"]["fingerprint_version"], 2)
            new_target = (self.dest / "alpha").resolve()
            self.assertNotEqual(new_target, target)
            launcher = new_target.parent / "improve-skills/launcher.sh"
            self.assertEqual(launcher.stat().st_mode & 0o111, 0o111)
            self.assertEqual((target.parent / "improve-skills/launcher.sh").stat().st_mode & 0o111, 0)
            self.assertEqual(subprocess.run([str(launcher)], check=True, capture_output=True, text=True).stdout,
                             "launcher works\n")
            self.assertIn("Previous installation preserved", result.stdout)
        self.assertNotIn("update available", self.run_cli("--list").stdout)

    def test_legacy_state_still_protects_content_edits(self):
        self.assertEqual(self.run_cli("--skills", "alpha").returncode, 0)
        self.use_legacy_state()
        (self.dest / "alpha/SKILL.md").write_text("local edit")
        result = self.run_cli("--skills", "alpha", "--adopt")
        self.assertEqual(result.returncode, 1)
        self.assertIn("modified managed files", result.stderr)
        self.assertEqual((self.dest / "alpha/SKILL.md").read_text(), "local edit")

    def test_install_update_current_and_preserve_unselected(self):
        first = self.run_cli("--skills", "alpha", "beta")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue(m.is_link(self.dest / "alpha"))
        self.assertTrue((self.dest / "improve-skills/SKILL.md").is_file())
        beta_target = (self.dest / "beta").resolve()
        for name in ("alpha", "beta"):
            (self.source / name / "SKILL.md").write_text("version two")
        self.assertIn("update available", self.run_cli("--list").stdout)
        updated = self.run_cli("--skills", "alpha")
        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertEqual((self.dest / "alpha/SKILL.md").read_text(), "version two")
        self.assertEqual((self.dest / "beta").resolve(), beta_target)
        self.assertIn("version one", (self.dest / "beta/SKILL.md").read_text())
        self.assertIn("current", self.run_cli("--list").stdout)

    def test_existing_directory_requires_adoption_and_is_backed_up(self):
        self.dest.mkdir(parents=True)
        (self.dest / "alpha").mkdir()
        (self.dest / "alpha/local.txt").write_text("keep me")
        refused = self.run_cli("--skills", "alpha")
        self.assertEqual(refused.returncode, 1)
        self.assertTrue((self.dest / "alpha/local.txt").is_file())
        self.assertFalse((self.store / "install.lock").exists())
        adopted = self.run_cli("--skills", "alpha", "--adopt")
        self.assertEqual(adopted.returncode, 0, adopted.stderr)
        backups = list((self.dest.parent / ".codex-skills-backups").glob("*/alpha/local.txt"))
        self.assertEqual(backups[0].read_text(), "keep me")

    def test_modified_managed_content_is_never_overwritten(self):
        self.assertEqual(self.run_cli("--skills", "alpha").returncode, 0)
        (self.dest / "alpha/SKILL.md").write_text("local edit")
        result = self.run_cli("--skills", "alpha", "--adopt")
        self.assertEqual(result.returncode, 1)
        self.assertIn("modified managed files", result.stderr)
        self.assertEqual((self.dest / "alpha/SKILL.md").read_text(), "local edit")

    def test_adoption_does_not_move_git_controlled_directory(self):
        (self.dest / "alpha").mkdir(parents=True)
        (self.dest / ".git").mkdir()
        (self.dest / "alpha/SKILL.md").write_text("checkout")
        result = self.run_cli("--skills", "alpha", "--adopt")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Git checkout", result.stderr)
        self.assertEqual((self.dest / "alpha/SKILL.md").read_text(), "checkout")

    def test_failed_state_write_restores_previous_link(self):
        self.assertEqual(self.run_cli("--skills", "alpha").returncode, 0)
        old_target = (self.dest / "alpha").resolve()
        (self.source / "alpha/SKILL.md").write_text("update")
        path, state = self.state()
        with patch.object(m, "save_state", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                m.install("alpha", self.source, self.dest / "alpha", self.store, state, path)
        self.assertEqual((self.dest / "alpha").resolve(), old_target)
        self.assertFalse(list(self.dest.glob(".install-*")))

    def test_menu_invalid_retry_quit_and_selection(self):
        result = self.run_cli(input="99\nalpha\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Unknown selection", result.stdout)
        self.assertTrue((self.dest / "alpha").is_dir())
        self.assertFalse((self.dest / "beta").exists())
        result = self.run_cli(input="q\n")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_list_does_not_write_and_unknown_selection_fails(self):
        self.assertEqual(self.run_cli("--list").returncode, 0)
        self.assertFalse(self.store.exists())
        self.assertFalse(self.dest.exists())
        self.assertEqual(self.run_cli("--skills", "missing").returncode, 1)
        self.assertFalse(self.store.exists())

    def test_custom_codex_home_does_not_change_standard_skill_location(self):
        with patch.object(Path, "home", return_value=self.root), patch.dict(os.environ, {"CODEX_HOME": str(self.root / "custom")}):
            dest, _, codex_home, _ = m.locations()
        self.assertEqual(dest, self.root / ".agents/skills")
        self.assertEqual(codex_home, self.root / "custom")

    def test_source_failure_preserves_installation(self):
        self.assertEqual(self.run_cli("--skills", "alpha").returncode, 0)
        old_target = (self.dest / "alpha").resolve()
        with patch.object(m, "fetch_main", side_effect=OSError("offline")), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(OSError):
                m.main(["--dest", str(self.dest), "--store", str(self.store), "--skills", "alpha"])
        self.assertEqual((self.dest / "alpha").resolve(), old_target)

    def test_archive_validation_and_commit_pinning(self):
        sha = "a" * 40
        def archive(path):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as z:
                z.writestr(path, "skill")
            return buffer.getvalue()
        for name in (f"codex-skills-{sha}/../escape", f"codex-skills-{sha}/CON", "/absolute"):
            with self.subTest(name=name), patch.object(m, "download", side_effect=[json.dumps({"sha": sha}).encode(), archive(name)]):
                with self.assertRaises(ValueError):
                    m.fetch_main(self.root)
        with patch.object(m, "download", side_effect=[json.dumps({"sha": sha}).encode(), archive(f"codex-skills-{sha}/alpha/SKILL.md")]) as get:
            source, commit = m.fetch_main(self.root)
            self.assertEqual(commit, sha)
            self.assertEqual(m.catalog(source), ["alpha"])
            self.assertIn(sha, get.call_args.args[0])

    def test_existing_lock_and_store_inside_discovery_are_rejected(self):
        self.store.mkdir()
        (self.store / "install.lock").touch()
        self.assertEqual(self.run_cli("--skills", "alpha").returncode, 1)
        self.assertTrue((self.store / "install.lock").exists())
        result = self.run_cli("--store", str(self.dest / "store"), "--list")
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
