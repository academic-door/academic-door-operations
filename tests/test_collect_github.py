import unittest

from scripts.collect_github import collect_github


class FakeApi:
    def __init__(self):
        self.paths = []

    def get_paginated(self, path, item_key=None, params=None, max_pages=10):
        self.paths.append(path)
        if "secrets" in path:
            raise AssertionError("public-safe collector must not call secret metadata endpoints")
        mapping = {
            "/installation/repositories": [
                {
                    "full_name": "academic-door/public-repo",
                    "private": False,
                    "archived": False,
                },
                {
                    "full_name": "academic-door/private-repo",
                    "private": True,
                    "archived": False,
                },
            ],
            "/repos/academic-door/public-repo/actions/workflows": [
                {"id": 1}
            ],
            "/repos/academic-door/private-repo/actions/workflows": [
                {"id": 2}
            ],
            "/repos/academic-door/public-repo/actions/runs": [
                {
                    "workflow_id": 1,
                    "conclusion": "success",
                    "run_started_at": "2026-09-26T10:00:00Z",
                    "updated_at": "2026-09-26T10:02:00Z",
                }
            ],
            "/repos/academic-door/private-repo/actions/runs": [
                {
                    "workflow_id": 2,
                    "conclusion": "failure",
                    "run_started_at": "2026-09-26T10:00:00Z",
                    "updated_at": "2026-09-26T10:03:00Z",
                }
            ],
        }
        return mapping.get(path, [])

    def get_json(self, path, params=None):
        self.paths.append(path)
        return {
            "usageItems": [
                {
                    "product": "Actions",
                    "netAmount": 0,
                    "grossAmount": 10,
                    "discountAmount": 10,
                }
            ]
        }


class GitHubCollectorTests(unittest.TestCase):
    def test_collects_transient_repo_and_actions_data_without_secret_metadata(self):
        api = FakeApi()
        result = collect_github(api, "academic-door", "2026-09-26T12:00:00Z")

        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(len(result["repositories"]), 2)
        self.assertEqual(len(result["actions"]), 2)
        self.assertEqual(result["billing"]["net_amount"], 0.0)
        self.assertNotIn("credential_metadata", result)
        self.assertFalse(any("secrets" in path for path in api.paths))


if __name__ == "__main__":
    unittest.main()
