import copy
import json
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

    def test_actual_zero_bill_preserves_gross_and_discount_context(self):
        snapshot = copy.deepcopy(self.snapshot)
        github = next(item for item in snapshot["costs"] if item["id"] == "github-actions")
        github.update(
            {
                "evidence_class": "ACTUAL",
                "amount": 0.0,
                "currency": None,
                "gross_amount": 99.584454,
                "discount_amount": 99.674454,
                "usage_quantity": None,
                "usage_unit": None,
                "usage_summary": "actions_linux: gross=16167 minutes; actions_storage: gross=7685.4 gigabyte-hours",
                "status": "current-month billable net is zero; observed usage is covered by included usage/discounts",
            }
        )
        text = render(snapshot)
        self.assertIn("Net billable", text)
        self.assertIn("Gross", text)
        self.assertIn("Discount", text)
        self.assertIn("0.0", text)
        self.assertIn("99.584454", text)
        self.assertNotIn("0.0 UNKNOWN", text)


if __name__ == "__main__":
    unittest.main()
