import copy
import json
import unittest
from pathlib import Path

from scripts.build_snapshot import build_snapshot
from scripts.validate_snapshot import validate


ROOT = Path(__file__).resolve().parents[1]
SEED = json.loads((ROOT / "data" / "seed-snapshot.json").read_text(encoding="utf-8"))


class PublicOwnerMergeTests(unittest.TestCase):
    def test_public_owner_health_updates_lifecycle_without_credential_metadata(self):
        github = {
            "schema_version": 2,
            "observed_at": "2026-09-26T12:00:00Z",
            "run_window_days": 14,
            "repositories": [],
            "actions": [],
            "billing": {"evidence_class": "UNKNOWN", "net_amount": None},
            "gaps": [],
        }
        owner = {
            "schema_version": 1,
            "observed_at": "2026-09-26T12:01:00Z",
            "daily_provider_health": {
                "observed_at": "2026-09-26T12:00:30Z",
                "providers": {
                    "crossref": {
                        "attempts": 150,
                        "available": 72,
                        "failed": 0,
                        "rate_limited": 0,
                        "skipped": 0,
                    },
                    "semantic-scholar": {
                        "attempts": 150,
                        "available": 27,
                        "failed": 123,
                        "rate_limited": 4,
                        "skipped": 118,
                        "api_key_configured": True,
                        "control": {"circuit_open": True},
                    },
                },
            },
            "daily_ai_cost": {
                "observed_at": "2026-09-26T11:59:00Z",
                "currency": "USD",
                "current_month_estimated_cost": 0.1,
                "rolling_30d_requests": 1000,
            },
            "gaps": [],
        }

        snapshot = build_snapshot(copy.deepcopy(SEED), github, owner)
        self.assertEqual(validate(snapshot), [])

        services = {item["id"]: item for item in snapshot["services"]}
        self.assertEqual(services["crossref"]["lifecycle_state"], "ACTIVE")
        self.assertEqual(
            services["semantic-scholar"]["lifecycle_state"], "ACTIVE_DEGRADED"
        )
        self.assertEqual(services["deepseek-inference"]["usefulness_status"], "PROVEN")

        serialized = json.dumps(snapshot).lower()
        self.assertNotIn("api_key_configured", serialized)
        self.assertNotIn("credential", serialized)


if __name__ == "__main__":
    unittest.main()
