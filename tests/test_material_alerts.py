import copy
import json
import unittest
from pathlib import Path

from scripts.build_snapshot import build_snapshot
from scripts.render_report import render
from scripts.validate_snapshot import validate


ROOT = Path(__file__).resolve().parents[1]
SEED = json.loads((ROOT / "data" / "seed-snapshot.json").read_text(encoding="utf-8"))


class PublicAlertTests(unittest.TestCase):
    def test_positive_billable_alert_is_generic(self):
        github = {
            "schema_version": 2,
            "observed_at": "2026-09-26T12:00:00Z",
            "run_window_days": 14,
            "repositories": [],
            "actions": [],
            "billing": {
                "evidence_class": "ACTUAL",
                "net_amount": 2.5,
                "gross_amount": 3.0,
                "discount_amount": 0.5,
            },
            "gaps": [],
        }
        snapshot = build_snapshot(copy.deepcopy(SEED), github, {"observed_at": "2026-09-26T12:00:01Z"})
        self.assertEqual(validate(snapshot), [])
        self.assertEqual(len(snapshot["alerts"]), 1)
        self.assertNotIn("2.5", json.dumps(snapshot))

        text = render(snapshot)
        self.assertIn("GITHUB_ACTIONS_POSITIVE_BILLABLE_NET", text)
        self.assertNotIn("2.5", text)


if __name__ == "__main__":
    unittest.main()
