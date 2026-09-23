import copy
import json
import unittest
from pathlib import Path

from scripts.build_snapshot import build_snapshot
from scripts.validate_snapshot import validate


ROOT = Path(__file__).resolve().parents[1]
SEED = json.loads((ROOT / "data" / "seed-snapshot.json").read_text(encoding="utf-8"))


class OwnerSnapshotMergeTests(unittest.TestCase):
    def setUp(self):
        self.seed = copy.deepcopy(SEED)
        self.github = {
            "schema_version": 1,
            "observed_at": "2026-09-16T18:00:00Z",
            "organization": "academic-door",
            "run_window_days": 14,
            "repositories": [],
            "actions": [],
            "billing": {
                "evidence_class": "ACTUAL",
                "net_amount": 0.0,
                "gross_amount": 99.58,
                "discount_amount": 99.58,
                "net_quantity": None,
                "unit_type": None,
                "items": [],
                "reason": None,
            },
            "credential_metadata": {"organization": [], "repositories": {}},
            "gaps": [],
        }
        self.owner = {
            "schema_version": 1,
            "observed_at": "2026-09-16T18:15:00Z",
            "daily_provider_health": {
                "observed_at": "2026-09-16T15:03:26+00:00",
                "providers": {
                    "semantic-scholar": {
                        "attempts": 150,
                        "available": 27,
                        "empty": 0,
                        "failed": 123,
                        "rate_limited": 4,
                        "skipped": 118,
                        "api_key_configured": True,
                        "control": {
                            "circuit_open": True,
                            "client_target_rps": 0.2,
                            "min_interval_seconds": 5.0,
                            "endpoint_class": "academic_graph_paper_details",
                            "workload_class": "metadata_recovery",
                        },
                    },
                    "elsevier": {
                        "attempts": 150,
                        "available": 37,
                        "empty": 113,
                        "failed": 0,
                        "rate_limited": 0,
                        "skipped": 0,
                        "api_key_configured": True,
                        "inst_token_configured": True,
                    },
                },
            },
            "daily_provider_usage": {
                "observed_at": "2026-09-16T15:00:17+00:00",
                "providers": {
                    "semantic-scholar": {
                        "api_key_configured": True,
                        "last_used_at": "2026-09-16T10:46:20+00:00",
                        "total": {"attempts": 3150, "available": 464, "not_found": 51, "rate_limited": 69, "skipped": 2566},
                    },
                    "elsevier": {
                        "api_key_configured": True,
                        "inst_token_configured": True,
                        "last_used_at": "2026-09-16T10:46:20+00:00",
                        "total": {"attempts": 3150, "available": 789, "empty": 2358, "rate_limited": 0},
                    },
                },
                "synthetic_keepalive_observed": True,
                "synthetic_keepalive_reason": "rate_limited",
            },
            "daily_ai_cost": {
                "observed_at": "2026-09-16T15:30:59+00:00",
                "provider": "DeepSeek",
                "currency": "USD",
                "current_month_estimated_cost": 0.09549,
                "rolling_30d_estimated_cost": 0.09549,
                "rolling_30d_requests": 1403,
                "pricing_source": "https://api-docs.deepseek.com/quick_start/pricing/",
                "pricing_version": "deepseek-pricing-2026-09-07",
            },
            "journals_monitoring": {
                "observed_at": "2026-09-16T18:13:17+00:00",
                "status": "healthy",
                "schedule": "every_two_hours",
                "summary": {"configured_journals": 49, "warnings": 0, "failed": 0, "awaiting_official": 7, "confirmed_updates": 7},
            },
            "gaps": [],
        }

    def test_owner_telemetry_updates_quota_cost_credential_and_service_summaries(self):
        snapshot = build_snapshot(self.seed, self.github, self.owner)
        self.assertEqual(validate(snapshot), [])
        self.assertEqual(snapshot["observed_at"], "2026-09-16T18:15:00Z")

        s2 = next(x for x in snapshot["quotas"] if x["id"] == "semantic-scholar-academic-graph")
        self.assertEqual(s2["status"], "PRESSURED")
        self.assertIn("rate_limited=4", s2["note"])
        self.assertIn("circuit_open=True", s2["note"])

        elsevier = next(x for x in snapshot["quotas"] if x["id"] == "elsevier-metadata")
        self.assertEqual(elsevier["status"], "HEALTHY")
        self.assertIn("rate_limited=0", elsevier["note"])

        deepseek = next(x for x in snapshot["costs"] if x["id"] == "deepseek-daily-door")
        self.assertEqual(deepseek["evidence_class"], "ESTIMATED")
        self.assertEqual(deepseek["amount"], 0.09549)
        self.assertEqual(deepseek["currency"], "USD")
        self.assertEqual(deepseek["usage_quantity"], 1403)
        self.assertEqual(deepseek["usage_unit"], "requests/rolling-30d")

        credential = next(x for x in snapshot["credentials"] if x["logical_name"] == "SEMANTIC_SCHOLAR_API_KEY")
        self.assertIn("legitimate use observed at 2026-09-16T10:46:20+00:00", credential["status"])
        self.assertIn("econ-paper-monitor#208", credential["note"])


        deepseek_service = next(x for x in snapshot["services"] if x["id"] == "deepseek-inference")
        self.assertEqual(deepseek_service["lifecycle_state"], "ACTIVE")
        self.assertEqual(deepseek_service["usefulness_status"], "PROVEN")
        self.assertEqual(deepseek_service["last_success_at"], "2026-09-16T15:30:59+00:00")

        crossref_service = next(x for x in snapshot["services"] if x["id"] == "crossref")
        self.assertEqual(crossref_service["lifecycle_state"], "ACTIVE")
        self.assertEqual(crossref_service["usefulness_status"], "PROVEN")
        self.assertEqual(crossref_service["last_success_at"], "2026-09-16T15:03:26+00:00")

        openalex_service = next(x for x in snapshot["services"] if x["id"] == "openalex")
        self.assertEqual(openalex_service["lifecycle_state"], "ACTIVE")
        self.assertEqual(openalex_service["usefulness_status"], "PROVEN")
        self.assertEqual(openalex_service["last_success_at"], "2026-09-16T15:03:26+00:00")

        s2_service = next(x for x in snapshot["services"] if x["id"] == "semantic-scholar")
        self.assertEqual(s2_service["lifecycle_state"], "ACTIVE_DEGRADED")
        self.assertEqual(s2_service["usefulness_status"], "PROVEN")
        self.assertEqual(s2_service["last_failure_at"], "2026-09-16T15:03:26+00:00")

        elsevier_service = next(x for x in snapshot["services"] if x["id"] == "elsevier-metadata")
        self.assertEqual(elsevier_service["lifecycle_state"], "ACTIVE")
        self.assertEqual(elsevier_service["usefulness_status"], "PROVEN")

        service = next(x for x in snapshot["services"] if x["id"] == "journals-production-monitor")
        self.assertEqual(service["status"], "healthy; configured_journals=49; warnings=0; failed=0; awaiting_official=7")

    def test_owner_snapshot_never_promotes_synthetic_keepalive_to_credential_health(self):
        snapshot = build_snapshot(self.seed, self.github, self.owner)
        credential = next(x for x in snapshot["credentials"] if x["logical_name"] == "SEMANTIC_SCHOLAR_API_KEY")
        self.assertNotIn("keepalive ok", credential["status"].lower())
        self.assertIn("synthetic keep-alive still observed", credential["note"].lower())


if __name__ == "__main__":
    unittest.main()
