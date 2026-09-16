import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "operations-probe.yml"


class ProbeWorkflowContractTests(unittest.TestCase):
    def test_probe_supports_manual_and_bounded_daily_read_only_runs(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("schedule:", text)
        self.assertIn("cron: \"17 9 * * *\"", text)
        self.assertIn("OPS_APP_CLIENT_ID", text)
        self.assertIn("OPS_APP_PRIVATE_KEY", text)
        self.assertIn("actions/create-github-app-token@v3", text)
        self.assertIn("owner: academic-door", text)
        self.assertIn("GITHUB_READ_TOKEN", text)
        self.assertNotIn("git push", text)
        self.assertNotIn("contents: write", text)

    def test_probe_builds_validates_renders_and_uploads_bounded_history(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for required in (
            "python -m scripts.collect_github",
            "scripts/build_snapshot.py",
            "scripts/validate_snapshot.py data/latest.json",
            "scripts/render_report.py data/latest.json reports/latest.md",
            "actions/upload-artifact@v4",
            "retention-days: 30",
        ):
            self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
