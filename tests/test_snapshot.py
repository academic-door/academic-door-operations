import json
import tempfile
import unittest
from pathlib import Path

from scripts.render_report import render
from scripts.validate_snapshot import validate


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "seed-snapshot.json"


class SnapshotContractTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    def test_seed_snapshot_validates(self):
        self.assertEqual(validate(self.snapshot), [])

    def test_scope_is_project_wide(self):
        self.assertEqual(self.snapshot["scope"], "ACADEMIC_DOOR_WIDE_TOPOLOGY_DYNAMIC")

    def test_credentials_never_collect_values(self):
        for item in self.snapshot["credentials"]:
            self.assertEqual(item["secret_value_policy"], "NEVER_COLLECT")
            self.assertNotIn("secret_value", item)

    def test_unknown_cost_is_not_zero(self):
        for item in self.snapshot["costs"]:
            if item["evidence_class"] == "UNKNOWN":
                self.assertIsNone(item.get("amount"))

    def test_report_is_deterministic_and_contains_core_sections(self):
        first = render(self.snapshot)
        second = render(self.snapshot)
        self.assertEqual(first, second)
        for heading in (
            "## Cost / usage",
            "## Quota / provider pressure",
            "## Credential metadata",
            "## Infrastructure / recurring services",
            "## GitHub Actions / recurring workloads",
            "## Human Principal actions",
        ):
            self.assertIn(heading, first)
        self.assertIn("Secret values are never collected", first)


if __name__ == "__main__":
    unittest.main()
