import copy
import json
import unittest
from pathlib import Path

from scripts.build_snapshot import build_snapshot
from scripts.render_report import render
from scripts.validate_snapshot import validate


ROOT = Path(__file__).resolve().parents[1]
SEED = json.loads((ROOT / "data" / "seed-snapshot.json").read_text(encoding="utf-8"))


class MaterialAlertTests(unittest.TestCase):
    def setUp(self):
        self.seed = copy.deepcopy(SEED)
        self.github = {
            "schema_version": 1,
            "observed_at": "2026-09-16T19:00:00Z",
            "organization": "academic-door",
            "run_window_days": 14,
            "repositories": [],
            "actions": [],
            "billing": {
                "evidence_class": "ACTUAL",
                "net_amount": 0.0,
                "gross_amount": 100.0,
                "discount_amount": 100.0,
                "net_quantity": 0,
                "unit_type": "minutes",
                "items": [],
                "reason": None,
            },
            "credential_metadata": {"organization": [], "repositories": {}},
            "gaps": [],
        }
        self.owner = {
            "schema_version": 1,
            "observed_at": "2026-09-16T19:01:00Z",
            "daily_provider_health": {
                "observed_at": "2026-09-16T19:00:30Z",
                "providers": {
                    "semantic-scholar": {
                        "attempts": 150,
                        "available": 27,
                        "failed": 123,
                        "rate_limited": 4,
                        "skipped": 118,
                        "control": {"circuit_open": True, "client_target_rps": 0.2},
                    }
                },
            },
            "gaps": [],
        }

    def test_zero_bill_and_single_snapshot_provider_pressure_do_not_alert(self):
        snapshot = build_snapshot(self.seed, self.github, self.owner)
        self.assertEqual(snapshot.get("alerts"), [])
        self.assertEqual(snapshot.get("human_actions"), [])

    def test_positive_actual_github_billable_net_emits_parent_review_alert(self):
        self.github["billing"]["net_amount"] = 1.25
        snapshot = build_snapshot(self.seed, self.github, self.owner)
        alerts = snapshot.get("alerts", [])
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["id"], "github-actions-positive-billable-net")
        self.assertEqual(alert["severity"], "PARENT_REVIEW")
        self.assertEqual(alert["scope"], "PARENT")
        self.assertEqual(alert["condition"], "GITHUB_ACTIONS_POSITIVE_BILLABLE_NET")
        self.assertEqual(alert["evidence_class"], "ACTUAL")
        self.assertIn("1.25", alert["summary"])
        self.assertEqual(snapshot.get("human_actions"), [])

    def test_explicit_exhausted_quota_emits_parent_review_alert(self):
        target = next(item for item in self.seed["quotas"] if item["id"] == "semantic-scholar-academic-graph")
        target["status"] = "EXHAUSTED"
        target["evidence_class"] = "PROVIDER_REPORTED"
        snapshot = build_snapshot(self.seed, self.github)
        alerts = snapshot.get("alerts", [])
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["id"], "quota-exhausted-semantic-scholar-academic-graph")
        self.assertEqual(alert["condition"], "AUTHORITATIVE_QUOTA_EXHAUSTED")
        self.assertEqual(alert["evidence_class"], "PROVIDER_REPORTED")
        self.assertIn("Semantic Scholar", alert["summary"])

    def test_report_renders_material_alerts_separately_from_human_actions(self):
        snapshot = copy.deepcopy(self.seed)
        snapshot["alerts"] = [
            {
                "id": "github-actions-positive-billable-net",
                "severity": "PARENT_REVIEW",
                "scope": "PARENT",
                "condition": "GITHUB_ACTIONS_POSITIVE_BILLABLE_NET",
                "evidence_class": "ACTUAL",
                "summary": "GitHub Actions current-period billable net is positive: 1.25 USD",
                "source": "GitHub organization billing usage summary API",
            }
        ]
        snapshot["human_actions"] = []
        text = render(snapshot)
        self.assertIn("## Material alerts", text)
        self.assertIn("GITHUB_ACTIONS_POSITIVE_BILLABLE_NET", text)
        self.assertIn("## Human Principal actions", text)
        self.assertIn("- NONE", text)

    def test_alerts_reject_secret_bearing_fields(self):
        snapshot = copy.deepcopy(self.seed)
        snapshot["alerts"] = [
            {
                "id": "bad-alert",
                "severity": "PARENT_REVIEW",
                "scope": "PARENT",
                "condition": "TEST",
                "evidence_class": "ACTUAL",
                "summary": "test",
                "source": "test",
                "token": "must-not-survive",
            }
        ]
        errors = validate(snapshot)
        self.assertTrue(any("alerts[0]" in error and "forbidden" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
