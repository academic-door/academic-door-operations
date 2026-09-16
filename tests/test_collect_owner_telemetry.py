import unittest

from scripts.collect_owner_telemetry import (
    normalize_daily_ai_cost,
    normalize_daily_provider_health,
    normalize_daily_provider_usage,
    normalize_journals_monitoring,
)


class OwnerTelemetryNormalizationTests(unittest.TestCase):
    def test_daily_provider_health_is_bounded_and_marks_semantic_scholar_pressure(self):
        payload = {
            "latest": {
                "checked_at": "2026-09-16T15:03:26+00:00",
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
                            "secret_value": "must-not-survive",
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
            }
        }
        result = normalize_daily_provider_health(payload)
        self.assertEqual(result["observed_at"], "2026-09-16T15:03:26+00:00")
        s2 = result["providers"]["semantic-scholar"]
        self.assertTrue(s2["control"]["circuit_open"])
        self.assertEqual(s2["rate_limited"], 4)
        self.assertEqual(s2["control"]["client_target_rps"], 0.2)
        self.assertNotIn("secret_value", str(result))

    def test_daily_provider_usage_keeps_legitimate_use_and_aggregate_counts_only(self):
        payload = {
            "updated_at": "2026-09-16T15:00:17+00:00",
            "providers": {
                "semantic-scholar": {
                    "api_key_configured": True,
                    "last_used_at": "2026-09-16T10:46:20+00:00",
                    "total": {
                        "attempts": 3150,
                        "available": 464,
                        "not_found": 51,
                        "rate_limited": 69,
                        "skipped": 2566,
                    },
                },
                "elsevier": {
                    "api_key_configured": True,
                    "inst_token_configured": True,
                    "last_used_at": "2026-09-16T10:46:20+00:00",
                    "total": {
                        "attempts": 3150,
                        "available": 789,
                        "empty": 2358,
                        "rate_limited": 0,
                    },
                },
            },
            "last_keepalive_at": "2026-09-16T15:00:16+00:00",
            "last_keepalive_reason": "rate_limited",
        }
        result = normalize_daily_provider_usage(payload)
        self.assertEqual(result["providers"]["semantic-scholar"]["last_used_at"], "2026-09-16T10:46:20+00:00")
        self.assertEqual(result["providers"]["semantic-scholar"]["total"]["rate_limited"], 69)
        self.assertTrue(result["synthetic_keepalive_observed"])
        self.assertEqual(result["synthetic_keepalive_reason"], "rate_limited")

    def test_daily_ai_cost_returns_current_month_and_rolling_30d_estimates(self):
        payload = {
            "currency": "USD",
            "updated_at": "2026-09-16T15:30:59+00:00",
            "days": {
                "2026-08-31": {"translation": {"estimated_cost_usd": 4.0}},
                "2026-09-01": {
                    "translation": {"estimated_cost_usd": 0.01},
                    "china_relevance": {"estimated_cost_usd": 0.002},
                },
                "2026-09-16": {"translation": {"estimated_cost_usd": 0.02}},
            },
            "rolling_30d": {"total": {"estimated_cost_usd": 0.09549, "requests": 1403}},
            "pricing_source": "https://api-docs.deepseek.com/quick_start/pricing/",
            "pricing_version": "deepseek-pricing-2026-09-07",
        }
        result = normalize_daily_ai_cost(payload)
        self.assertAlmostEqual(result["current_month_estimated_cost"], 0.032)
        self.assertAlmostEqual(result["rolling_30d_estimated_cost"], 0.09549)
        self.assertEqual(result["rolling_30d_requests"], 1403)
        self.assertEqual(result["currency"], "USD")

    def test_journals_monitoring_keeps_only_bounded_service_health(self):
        payload = {
            "updated_at": "2026-09-16T18:13:17+00:00",
            "status": "healthy",
            "schedule": "every_two_hours",
            "summary": {
                "configured_journals": 49,
                "unchanged": 42,
                "candidates": 0,
                "confirmed_updates": 7,
                "warnings": 0,
                "awaiting_official": 7,
                "failed": 0,
            },
            "last_successful_checks": {"AER": "too-high-cardinality"},
        }
        result = normalize_journals_monitoring(payload)
        self.assertEqual(result["status"], "healthy")
        self.assertEqual(result["summary"]["configured_journals"], 49)
        self.assertNotIn("last_successful_checks", result)


if __name__ == "__main__":
    unittest.main()
