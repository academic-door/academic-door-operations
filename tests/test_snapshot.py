import json
import unittest
from pathlib import Path

from scripts.render_report import render
from scripts.validate_snapshot import validate


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "seed-snapshot.json"


class PublicSnapshotContractTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    def test_seed_snapshot_validates(self):
        self.assertEqual(validate(self.snapshot), [])

    def test_scope_is_explicitly_public_safe(self):
        self.assertEqual(self.snapshot["scope"], "ACADEMIC_DOOR_PUBLIC_SAFE")

    def test_jina_keeps_lifecycle_without_private_account_context(self):
        jina = next(item for item in self.snapshot["services"] if item["id"] == "jina-reader")
        self.assertEqual(jina["lifecycle_state"], "RETIRING")
        self.assertEqual(
            jina["usefulness_status"],
            "RETIRE_BY_DEFAULT_PENDING_DAILY_PROVENANCE_GATE",
        )
        serialized = json.dumps(self.snapshot).lower()
        self.assertNotIn("human principal", serialized)
        self.assertNotIn("no payment", serialized)
        self.assertNotIn("jina_api_key", serialized)

    def test_report_is_deterministic_and_public_safe(self):
        first = render(self.snapshot)
        second = render(self.snapshot)
        self.assertEqual(first, second)
        for heading in (
            "## Public-safe billing",
            "## Public estimated costs",
            "## Public provider health",
            "## Public service lifecycle",
            "## GitHub Actions aggregate",
            "## Human actions",
        ):
            self.assertIn(heading, first)
        self.assertNotIn("Credential metadata", first)
        self.assertNotIn("private report", first.lower())


if __name__ == "__main__":
    unittest.main()
