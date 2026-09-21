import copy
import json
import unittest
from pathlib import Path

from scripts.build_snapshot import build_snapshot
from scripts.render_report import render
from scripts.validate_snapshot import validate


ROOT = Path(__file__).resolve().parents[1]
SEED = json.loads((ROOT / "data" / "seed-snapshot.json").read_text(encoding="utf-8"))


class CostCoverageTests(unittest.TestCase):
    def setUp(self):
        self.seed = copy.deepcopy(SEED)
        self.github = {
            "schema_version": 1,
            "observed_at": "2026-09-21T10:30:00Z",
            "organization": "academic-door",
            "run_window_days": 14,
            "repositories": [],
            "actions": [],
            "billing": {
                "evidence_class": "ACTUAL",
                "net_amount": 0.0,
                "gross_amount": 150.0,
                "discount_amount": 150.0,
                "net_quantity": None,
                "unit_type": None,
                "items": [],
                "reason": None,
            },
            "credential_metadata": {
                "organization": [
                    {"name": "DEEPSEEK_API_KEY", "scope": "organization", "visibility": "all"},
                    {"name": "QWEN_API_KEY", "scope": "organization", "visibility": "all"},
                ],
                "repositories": {
                    "academic-door/academic-door-composer": [
                        {"name": "CLOUDFLARE_ACCOUNT_ID", "scope": "repository"},
                        {"name": "CLOUDFLARE_API_TOKEN", "scope": "repository"},
                    ],
                    "academic-door/journals": [
                        {"name": "SMTP_PASSWORD", "scope": "repository"},
                        {"name": "AUTO_REVIEWER_PRIVATE_KEY", "scope": "repository"},
                    ],
                },
            },
            "gaps": [],
        }
        self.owner = {
            "schema_version": 1,
            "observed_at": "2026-09-21T10:31:00Z",
            "daily_ai_cost": {
                "observed_at": "2026-09-21T10:29:00Z",
                "currency": "USD",
                "current_month_estimated_cost": 0.2,
                "rolling_30d_estimated_cost": 0.2,
                "rolling_30d_requests": 2500,
                "pricing_version": "test-pricing",
            },
            "gaps": [],
        }

    def test_ledger_distinguishes_actual_estimated_provider_reported_and_unknown(self):
        snapshot = build_snapshot(self.seed, self.github, self.owner)
        by_id = {item["id"]: item for item in snapshot["costs"]}

        self.assertEqual(by_id["github-actions"]["evidence_class"], "ACTUAL")
        self.assertEqual(by_id["github-actions"]["coverage_status"], "ACTUAL_BILLED")
        self.assertEqual(by_id["github-actions"]["amount"], 0.0)
        self.assertEqual(by_id["github-actions"]["evidence_observed_at"], "2026-09-21T10:30:00Z")

        self.assertEqual(by_id["deepseek-daily-door"]["evidence_class"], "ESTIMATED")
        self.assertEqual(by_id["deepseek-daily-door"]["coverage_status"], "ESTIMATED_USAGE")
        self.assertEqual(by_id["deepseek-daily-door"]["amount"], 0.2)
        self.assertEqual(by_id["deepseek-daily-door"]["evidence_observed_at"], "2026-09-21T10:29:00Z")

        self.assertEqual(by_id["supabase-academic-door"]["evidence_class"], "PROVIDER_REPORTED")
        self.assertEqual(by_id["supabase-academic-door"]["coverage_status"], "PROVIDER_REPORTED_FREE")
        self.assertEqual(by_id["supabase-academic-door"]["amount"], 0.0)

        self.assertEqual(by_id["firecrawl"]["coverage_status"], "PROVIDER_REPORTED_QUOTA")
        self.assertEqual(by_id["firecrawl"]["authorized_paid_budget"], 0.0)
        self.assertIsNone(by_id["firecrawl"]["amount"])

        for item in snapshot["costs"]:
            if item["evidence_class"] == "UNKNOWN":
                self.assertEqual(item["coverage_status"], "ACCOUNT_BILLING_UNKNOWN")
                self.assertTrue(item["next_evidence_route"])
                self.assertIsNone(item["amount"])

        self.assertEqual(validate(snapshot), [])

    def test_report_answers_cost_question_with_named_residuals_and_routes(self):
        snapshot = build_snapshot(self.seed, self.github, self.owner)
        text = render(snapshot)
        self.assertIn("## Cost coverage summary", text)
        self.assertIn("Known ACTUAL billed subtotal: 0.0 currency-not-exposed", text)
        self.assertIn("Separately labeled ESTIMATED subtotal: 0.2 USD", text)
        self.assertIn("Supabase", text)
        self.assertIn("Firecrawl", text)
        self.assertIn("Cloudflare Workers / D1 / runtime", text)
        self.assertIn("## Account evidence routes", text)
        self.assertIn("authoritative Cloudflare invoice/receipt/export", text)
        self.assertIn("Period-end projection: UNKNOWN", text)

    def test_budget_zero_is_not_billed_zero(self):
        firecrawl = next(item for item in self.seed["costs"] if item["id"] == "firecrawl")
        self.assertEqual(firecrawl["authorized_paid_budget"], 0.0)
        self.assertIsNone(firecrawl["amount"])
        self.assertEqual(firecrawl["evidence_class"], "PROVIDER_REPORTED")

    def test_known_credential_names_are_classified_without_secret_fields(self):
        snapshot = build_snapshot(self.seed, self.github, self.owner)
        by_name = {item["logical_name"]: item for item in snapshot["credentials"]}

        self.assertEqual(by_name["CLOUDFLARE_API_TOKEN"]["provider"], "Cloudflare")
        self.assertEqual(by_name["DEEPSEEK_API_KEY"]["provider"], "DeepSeek")
        self.assertEqual(by_name["QWEN_API_KEY"]["provider"], "Qwen / DashScope / Alibaba Cloud")
        self.assertEqual(by_name["SMTP_PASSWORD"]["provider"], "NetEase 163 SMTP")
        self.assertEqual(by_name["AUTO_REVIEWER_PRIVATE_KEY"]["provider"], "GitHub App")

        for item in snapshot["credentials"]:
            self.assertNotIn("secret_value", item)
            self.assertNotIn("token", item)
            self.assertNotIn("private_key", item)

    def test_unknown_cost_without_evidence_route_is_invalid(self):
        snapshot = copy.deepcopy(self.seed)
        cloudflare = next(item for item in snapshot["costs"] if item["id"] == "cloudflare")
        cloudflare["next_evidence_route"] = ""
        errors = validate(snapshot)
        self.assertTrue(any("next_evidence_route" in error for error in errors), errors)

    def test_secret_bearing_field_is_rejected_anywhere_in_snapshot(self):
        snapshot = copy.deepcopy(self.seed)
        snapshot["costs"][0]["token"] = "must-not-survive"
        errors = validate(snapshot)
        self.assertTrue(any("forbidden secret-bearing field" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
