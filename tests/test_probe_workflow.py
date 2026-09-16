import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "operations-probe.yml"


class ProbeWorkflowContractTests(unittest.TestCase):
    def test_probe_is_manual_only_and_uses_read_only_app_credentials(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("schedule:", text)
        self.assertIn("OPS_APP_CLIENT_ID", text)
        self.assertIn("OPS_APP_PRIVATE_KEY", text)
        self.assertIn("actions/create-github-app-token@v3", text)
        self.assertIn("owner: academic-door", text)
        self.assertIn("GITHUB_READ_TOKEN", text)
        self.assertNotIn("git push", text)
        self.assertNotIn("contents: write", text)

    def test_probe_builds_validates_renders_and_uploads_artifacts(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for required in (
            "scripts/collect_github.py",
            "scripts/build_snapshot.py",
            "scripts/validate_snapshot.py data/latest.json",
            "scripts/render_report.py data/latest.json reports/latest.md",
            "actions/upload-artifact@v4",
        ):
            self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
