import copy
import json
import unittest
from pathlib import Path

from scripts.build_snapshot import build_snapshot
from scripts.validate_snapshot import validate


ROOT = Path(__file__).resolve().parents[1]
SEED = json.loads((ROOT / "data" / "seed-snapshot.json").read_text(encoding="utf-8"))


class PublicSnapshotBuildTests(unittest.TestCase):
    def setUp(self):
        self.seed = copy.deepcopy(SEED)
        self.github = {
            "schema_version": 2,
            "observed_at": "2026-09-26T12:00:00Z",
            "organization": "academic-door",
            "run_window_days": 14,
            "repositories": [
                {"full_name": "academic-door/public-a", "private": False, "archived": False},
                {"full_name": "academic-door/private-a", "private": True, "archived": False},
            ],
            "actions": [
                {
                    "repository": "academic-door/public-a",
                    "workflow_id": 1,
                    "run_count": 4,
                    "failure_count": 1,
                    "estimated_wall_minutes": 8.0,
                },
                {
                    "repository": "academic-door/private-a",
                    "workflow_id": 2,
                    "run_count": 3,
                    "failure_count": 0,
                    "estimated_wall_minutes": 6.0,
                },
            ],
            "billing": {
                "evidence_class": "ACTUAL",
                "net_amount": 0.0,
                "gross_amount": 20.0,
                "discount_amount": 20.0,
                "reason": None,
            },
            "gaps": [],
        }
        self.owner = {
            "schema_version": 1,
            "observed_at": "2026-09-26T12:01:00Z",
            "daily_provider_health": {
                "observed_at": "2026-09-26T12:00:30Z",
                "providers": {
                    "crossref": {
                        "attempts": 100,
                        "available": 80,
                        "failed": 0,
                        "rate_limited": 0,
                        "skipped": 0,
                    },
                    "semantic-scholar": {
                        "attempts": 100,
                        "available": 20,
                        "failed": 10,
                        "rate_limited": 5,
                        "skipped": 65,
                        "control": {"circuit_open": True},
                    },
                },
            },
            "daily_ai_cost": {
                "observed_at": "2026-09-26T11:59:00Z",
                "currency": "USD",
                "current_month_estimated_cost": 0.25,
                "rolling_30d_requests": 2500,
            },
            "gaps": [],
        }

    def test_builds_only_aggregated_public_safe_output(self):
        snapshot = build_snapshot(self.seed, self.github, self.owner)
        self.assertEqual(validate(snapshot), [])
        self.assertEqual(snapshot["billing"]["github_actions"]["billable_state"], "ZERO")

        classes = {item["class"]: item for item in snapshot["actions"]["classes"]}
        self.assertEqual(classes["PUBLIC_STANDARD_RUNNER_FREE_ELIGIBLE"]["run_count"], 4)
        self.assertEqual(classes["PRIVATE_INCLUDED_MINUTES"]["run_count"], 3)
        self.assertEqual(classes["PRIVATE_INCLUDED_MINUTES"]["repositories_observed"], 1)

        serialized = json.dumps(snapshot)
        self.assertNotIn("academic-door/public-a", serialized)
        self.assertNotIn("academic-door/private-a", serialized)

    def test_positive_billable_net_is_coarse_not_amount_bearing(self):
        self.github["billing"]["net_amount"] = 1.25
        snapshot = build_snapshot(self.seed, self.github, self.owner)
        self.assertEqual(snapshot["billing"]["github_actions"]["billable_state"], "POSITIVE")
        self.assertEqual(snapshot["alerts"][0]["condition"], "GITHUB_ACTIONS_POSITIVE_BILLABLE_NET")
        self.assertNotIn("1.25", json.dumps(snapshot))


if __name__ == "__main__":
    unittest.main()
