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
        self.assertIn("tracker issue enters `Merging`", land)
        self.assertIn("isDraft == false", land)
        self.assertIn("timeout 10m", land)
        self.assertIn("for attempt in {1..60}", land)
        self.assertIn("for attempt in 1 2 3 4 5 6", land)
        self.assertIn("codex_review_pending", land)
        self.assertIn("codex_review_failed", land)
        self.assertIn("Failed|Cancelled", land)
        self.assertIn("set -euo pipefail", land)
        self.assertIn("reports `MERGED`", land)
        self.assertIn("tracker issue to `Done`", land)
        self.assertNotIn("while true", land)
        self.assertNotIn("--auto", land)
        self.assertNotIn("--admin", land)
        self.assertNotIn("gh pr ready", land)

    def test_workflow_handoff_precedes_human_review(self) -> None:
        workflow = (ROOT / "WORKFLOW.md").read_text(encoding="utf-8")
        self.assertLess(
            workflow.index("run `gh pr ready`"),
            workflow.index("only then move the issue"),
        )
        self.assertIn("sole owner", workflow)

    def test_land_uses_fresh_paginated_head_bound_snapshot(self) -> None:
        land = (ROOT / ".codex/skills/land/SKILL.md").read_text(encoding="utf-8")
        fields = "number,title,body,state,isDraft,headRefOid,baseRefName,mergeable,comments,reviews,statusCheckRollup"
        self.assertIn(fields, land)
        self.assertIn("--paginate --slurp", land)
        self.assertIn("final_inline", land)
        self.assertIn("rules/branches", land)
        self.assertIn('--match-head-commit "$head_oid"', land)
        self.assertIn('[[ $head_oid == "$initial_head" ]]', land)
        final_snapshot = land.rindex('gh pr view --json "$snapshot_fields"')
        self.assertGreater(final_snapshot, land.index("timeout 10m"))
        self.assertGreater(final_snapshot, land.index("rules/branches"))
        self.assertLess(final_snapshot, land.index('gh pr merge "$pr_number"'))
        self.assertIn("pending_checks == 0 && failed_checks == 0", land)
        self.assertIn("pending_checks == 0 && failed_checks == 0 )) || {", land)
        self.assertIn('codex_review_failed "$final_snapshot"', land)
        self.assertGreaterEqual(land.count("exit 1"), 10)
        self.assertIn(
            "Evaluate final_snapshot and final_inline for any new actionable feedback",
            land,
        )


if __name__ == "__main__":
    unittest.main()
