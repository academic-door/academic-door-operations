import unittest

from scripts.collect_github import collect_github
from scripts.github_api import GitHubApiError


class FakeApi:
    def __init__(self, billing_error=None):
        self.billing_error = billing_error

    def get_paginated(self, path, item_key=None, params=None, max_pages=10):
        mapping = {
            "/installation/repositories": [
                {"name": "repo-a", "full_name": "academic-door/repo-a", "private": True, "archived": False, "default_branch": "main"},
                {"name": "repo-b", "full_name": "academic-door/repo-b", "private": False, "archived": False, "default_branch": "main"},
            ],
            "/repos/academic-door/repo-a/actions/workflows": [
                {"id": 1, "name": "Fast", "path": ".github/workflows/fast.yml", "state": "active"}
            ],
            "/repos/academic-door/repo-b/actions/workflows": [
                {"id": 2, "name": "Public CI", "path": ".github/workflows/public.yml", "state": "active"}
            ],
            "/repos/academic-door/repo-a/actions/runs": [
                {
                    "workflow_id": 1,
                    "name": "Fast",
                    "conclusion": "success",
                    "run_started_at": "2026-09-16T10:00:00Z",
                    "updated_at": "2026-09-16T10:03:00Z",
                },
                {
                    "workflow_id": 1,
                    "name": "Fast",
                    "conclusion": "failure",
                    "run_started_at": "2026-09-16T11:00:00Z",
                    "updated_at": "2026-09-16T11:02:00Z",
                },
            ],
            "/repos/academic-door/repo-b/actions/runs": [
                {
                    "workflow_id": 2,
                    "name": "Public CI",
                    "conclusion": "success",
                    "run_started_at": "2026-09-16T12:00:00Z",
                    "updated_at": "2026-09-16T12:01:00Z",
                }
            ],
            "/orgs/academic-door/actions/secrets": [
                {"name": "ORG_KEY", "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-02-01T00:00:00Z", "visibility": "selected"}
            ],
            "/repos/academic-door/repo-a/actions/secrets": [
                {"name": "REPO_KEY", "created_at": "2026-03-01T00:00:00Z", "updated_at": "2026-04-01T00:00:00Z"}
            ],
            "/repos/academic-door/repo-b/actions/secrets": [],
        }
        return mapping[path]

    def get_json(self, path, params=None):
        if path == "/organizations/academic-door/settings/billing/usage/summary":
            if self.billing_error:
                raise self.billing_error
            return {
                "timePeriod": {"year": 2026, "month": 9},
                "organization": "academic-door",
                "usageItems": [
                    {"product": "Actions", "sku": "actions_linux", "unitType": "minutes", "grossQuantity": 100, "grossAmount": 0.8, "netQuantity": 75, "netAmount": 0.6}
                ],
            }
        raise AssertionError(path)


class CollectGitHubTests(unittest.TestCase):
    def test_dynamic_repository_actions_billing_and_secret_metadata(self):
        result = collect_github(FakeApi(), "academic-door", "2026-09-16T15:00:00Z", run_window_days=14)

        self.assertEqual([r["full_name"] for r in result["repositories"]], ["academic-door/repo-a", "academic-door/repo-b"])
        self.assertEqual(len(result["actions"]), 2)
        action = next(item for item in result["actions"] if item["repository"] == "academic-door/repo-a")
        public_action = next(item for item in result["actions"] if item["repository"] == "academic-door/repo-b")
        self.assertEqual(action["repository"], "academic-door/repo-a")
        self.assertEqual(action["workflow_name"], "Fast")
        self.assertEqual(action["run_count"], 2)
        self.assertEqual(action["success_count"], 1)
        self.assertEqual(action["failure_count"], 1)
        self.assertEqual(action["estimated_wall_minutes"], 5.0)
        self.assertEqual(action["evidence_class"], "ESTIMATED")
        self.assertEqual(action["repository_visibility"], "PRIVATE")
        self.assertEqual(action["billing_scarcity_class"], "PRIVATE_INCLUDED_MINUTES")
        self.assertEqual(public_action["repository_visibility"], "PUBLIC")
        self.assertEqual(public_action["billing_scarcity_class"], "PUBLIC_STANDARD_RUNNER_FREE_ELIGIBLE")

        self.assertEqual(result["billing"]["evidence_class"], "ACTUAL")
        self.assertEqual(result["billing"]["net_amount"], 0.6)
        self.assertEqual(result["billing"]["net_quantity"], 75)

        org_secret = result["credential_metadata"]["organization"][0]
        repo_secret = result["credential_metadata"]["repositories"]["academic-door/repo-a"][0]
        self.assertEqual(org_secret["name"], "ORG_KEY")
        self.assertEqual(org_secret["visibility"], "selected")
        self.assertEqual(repo_secret["name"], "REPO_KEY")
        for secret in (org_secret, repo_secret):
            self.assertNotIn("value", secret)
            self.assertNotIn("secret_value", secret)

    def test_billing_permission_gap_is_unknown_not_zero(self):
        api = FakeApi(billing_error=GitHubApiError(403, "Resource not accessible by integration", "/billing"))
        result = collect_github(api, "academic-door", "2026-09-16T15:00:00Z")

        self.assertEqual(result["billing"]["evidence_class"], "UNKNOWN")
        self.assertIsNone(result["billing"]["net_amount"])
        self.assertTrue(any(gap["area"] == "github-billing" and gap["status"] == 403 for gap in result["gaps"]))


if __name__ == "__main__":
    unittest.main()
