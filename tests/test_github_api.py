import io
import json
import unittest
from urllib.error import HTTPError

from scripts.github_api import GitHubApi, GitHubApiError


class FakeResponse:
    def __init__(self, payload, status=200, headers=None):
        self._payload = payload
        self.status = status
        self.headers = headers or {}

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class SequenceOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout=30):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class GitHubApiTests(unittest.TestCase):
    def test_get_json_sets_bearer_header_and_decodes_json(self):
        opener = SequenceOpener([FakeResponse({"ok": True})])
        api = GitHubApi("token-123", opener=opener)

        self.assertEqual(api.get_json("/test"), {"ok": True})
        request = opener.requests[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer token-123")
        self.assertEqual(request.get_method(), "GET")

    def test_get_paginated_follows_link_header_and_extracts_item_key(self):
        opener = SequenceOpener(
            [
                FakeResponse(
                    {"items": [{"id": 1}]},
                    headers={"Link": '<https://api.github.com/test?page=2>; rel="next"'},
                ),
                FakeResponse({"items": [{"id": 2}]}, headers={}),
            ]
        )
        api = GitHubApi("token", opener=opener)

        items = api.get_paginated("/test", item_key="items")

        self.assertEqual(items, [{"id": 1}, {"id": 2}])
        self.assertEqual(len(opener.requests), 2)

    def test_http_error_is_normalized_without_token_leak(self):
        error = HTTPError(
            "https://api.github.com/test",
            403,
            "Forbidden",
            hdrs={},
            fp=io.BytesIO(b'{"message":"Resource not accessible by integration"}'),
        )
        opener = SequenceOpener([error])
        api = GitHubApi("super-secret-token", opener=opener)

        with self.assertRaises(GitHubApiError) as raised:
            api.get_json("/test")

        self.assertEqual(raised.exception.status, 403)
        self.assertIn("Resource not accessible", str(raised.exception))
        self.assertNotIn("super-secret-token", str(raised.exception))
        self.assertEqual(raised.exception.path, "/test")


if __name__ == "__main__":
    unittest.main()
