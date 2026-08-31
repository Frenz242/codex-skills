from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SymphonyPolicyTests(unittest.TestCase):
    def test_pull_request_template_has_required_sections(self) -> None:
        template = (ROOT / ".github/pull_request_template.md").read_text(encoding="utf-8")
        for heading in ("## Summary", "## Why", "## Validation", "## Risks and rollout"):
            self.assertIn(heading, template)

    def test_workflow_land_capability_exists(self) -> None:
        workflow = (ROOT / "WORKFLOW.md").read_text(encoding="utf-8")
        land_path = ROOT / ".codex/skills/land/SKILL.md"
        self.assertTrue(land_path.is_file())
        self.assertIn(".codex/skills/land/SKILL.md", workflow)

    def test_land_is_state_gated_and_bounded(self) -> None:
        land = (ROOT / ".codex/skills/land/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("only when the tracker issue is in `Merging`", land)
        self.assertIn("timeout 10m", land)
        self.assertIn("at most one minute", land)
        self.assertIn("reports `MERGED`", land)
        self.assertIn("move the issue to `Done`", land)
        self.assertNotIn("while true", land)


if __name__ == "__main__":
    unittest.main()
