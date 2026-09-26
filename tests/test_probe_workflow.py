import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "operations-probe.yml"


class ProbeWorkflowContractTests(unittest.TestCase):
    def test_probe_keeps_read_only_schedule_and_app_token(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("schedule:", text)
        self.assertIn('cron: "57 10 * * *"', text)
        self.assertIn("OPS_APP_CLIENT_ID", text)
        self.assertIn("OPS_APP_PRIVATE_KEY", text)
        self.assertIn("actions/create-github-app-token@v3", text)
        self.assertNotIn("git push", text)
        self.assertNotIn("contents: write", text)

    def test_raw_evidence_is_transient_and_artifact_is_strictly_public_safe(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("$RUNNER_TEMP/academic-door-operations/github.json", text)
        self.assertIn("$RUNNER_TEMP/academic-door-operations/owner.json", text)
        self.assertNotIn("data/github-latest.json", text)
        self.assertNotIn("data/owner-latest.json", text)
        self.assertNotIn("data/latest.json", text)
        self.assertIn("operations-public-safe-report", text)
        self.assertIn("retention-days: 7", text)

        artifact_block = text.split("name: operations-public-safe-report", 1)[1]
        self.assertIn("public/latest.json", artifact_block)
        self.assertIn("public/latest.md", artifact_block)
        self.assertIn("public/manifest.json", artifact_block)
        self.assertNotIn("$RUNNER_TEMP", artifact_block)


if __name__ == "__main__":
    unittest.main()
