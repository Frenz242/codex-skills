from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RepositoryPolicyTests(unittest.TestCase):
    def test_pull_request_template_has_required_sections(self) -> None:
        template = (ROOT / ".github/pull_request_template.md").read_text(encoding="utf-8")
        for heading in ("## Summary", "## Why", "## Validation", "## Risks and rollout"):
            self.assertIn(heading, template)
