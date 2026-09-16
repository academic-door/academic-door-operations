import copy
import json
import unittest
from pathlib import Path

from scripts.build_snapshot import build_snapshot
from scripts.validate_snapshot import validate


ROOT = Path(__file__).resolve().parents[1]
SEED = json.loads((ROOT / "data" / "seed-snapshot.json").read_text(encoding="utf-8"))


class BuildSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.seed = copy.deepcopy(SEED)
        self.github = {
            "schema_version": 1,
            "observed_at": "2026-09-16T16:00:00Z",
            "organization": "academic-door",
            "run_window_days": 14,
            "repositories": [
                {"name": "econ-paper-monitor", "full_name": "academic-door/econ-paper-monitor", "private": True, "archived": False, "default_branch": "main"}
            ],
            "actions": [
                {
                    "repository": "academic-door/econ-paper-monitor",
                    "workflow_id": 10,
                    "workflow_name": "Update Paper Monitor",
                    "workflow_path": ".github/workflows/update.yml",
                    "workflow_state": "active",
                    "run_count": 20,
                    "success_count": 19,
                    "failure_count": 1,
                    "cancelled_count": 0,
                    "other_count": 0,
                    "estimated_wall_minutes": 44.5,
                    "window_days": 14,
                    "evidence_class": "ESTIMATED",
                }
            ],
            "billing": {
                "evidence_class": "ACTUAL",
                "net_amount": 1.25,
                "gross_amount": 1.5,
                "net_quantity": 150,
                "unit_type": "minutes",
                "items": [],
                "reason": None,
            },
            "credential_metadata": {
                "organization": [
                    {"name": "JINA_API_KEY", "scope": "organization", "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-02-01T00:00:00Z", "visibility": "selected", "value": "must-not-survive"}
                ],
                "repositories": {
                    "academic-door/econ-paper-monitor": [
                        {"name": "NEW_PROVIDER_KEY", "scope": "repository", "repository": "academic-door/econ-paper-monitor", "created_at": "2026-03-01T00:00:00Z", "updated_at": "2026-04-01T00:00:00Z", "secret_value": "must-not-survive"}
                    ]
                },
            },
            "gaps": [],
        }

    def test_builds_valid_snapshot_with_actual_github_cost_and_dynamic_actions(self):
        snapshot = build_snapshot(self.seed, self.github)
        self.assertEqual(validate(snapshot), [])
        self.assertEqual(snapshot["observed_at"], "2026-09-16T16:00:00Z")

        cost = next(item for item in snapshot["costs"] if item["id"] == "github-actions")
        self.assertEqual(cost["evidence_class"], "ACTUAL")
        self.assertEqual(cost["amount"], 1.25)

        self.assertEqual(len(snapshot["actions"]), 1)
        action = snapshot["actions"][0]
        self.assertEqual(action["repository"], "academic-door/econ-paper-monitor")
        self.assertEqual(action["run_count"], 20)
        self.assertEqual(action["estimated_minutes"], 44.5)
        self.assertEqual(action["window_days"], 14)

    def test_unknown_billing_remains_unknown_not_zero(self):
        self.github["billing"] = {
            "evidence_class": "UNKNOWN",
            "net_amount": None,
            "gross_amount": None,
            "net_quantity": None,
            "unit_type": None,
            "items": [],
            "reason": "403",
        }
        snapshot = build_snapshot(self.seed, self.github)
        cost = next(item for item in snapshot["costs"] if item["id"] == "github-actions")
        self.assertEqual(cost["evidence_class"], "UNKNOWN")
        self.assertIsNone(cost["amount"])

    def test_credential_metadata_is_whitelisted_and_secret_values_never_survive(self):
        snapshot = build_snapshot(self.seed, self.github)
        jina = next(item for item in snapshot["credentials"] if item["logical_name"] == "JINA_API_KEY")
        new = next(item for item in snapshot["credentials"] if item["logical_name"] == "NEW_PROVIDER_KEY")

        self.assertEqual(jina["storage_scope"], "organization")
        self.assertEqual(jina["visibility"], "selected")
        self.assertIn("academic-door/econ-paper-monitor", new["consumers"])
        self.assertEqual(new["secret_value_policy"], "NEVER_COLLECT")
        serialized = json.dumps(snapshot)
        self.assertNotIn("must-not-survive", serialized)
        self.assertNotIn("secret_value", serialized)


if __name__ == "__main__":
    unittest.main()
