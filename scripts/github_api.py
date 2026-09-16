#!/usr/bin/env python3
"""Small read-only GitHub REST client used by Academic Door Operations."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


API_VERSION = "2026-03-10"


class GitHubApiError(RuntimeError):
    def __init__(self, status: int | None, message: str, path: str):
        self.status = status
        self.path = path
        super().__init__(f"GitHub API error status={status} path={path}: {message}")


class GitHubApi:
    def __init__(self, token: str, base_url: str = "https://api.github.com", opener=None, timeout: int = 30):
        if not token:
            raise ValueError("GitHub token is required")
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.opener = opener or urlopen
        self.timeout = timeout

    def _url(self, path: str, params=None) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            url = path
        else:
            url = f"{self.base_url}/{path.lstrip('/')}"
        if params:
            query = urlencode(params, doseq=True)
            url = f"{url}{'&' if '?' in url else '?'}{query}"
        return url

    def _request(self, url: str, logical_path: str):
        request = Request(
            url,
            method="GET",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": "academic-door-operations",
            },
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                raw = response.read()
                payload = json.loads(raw.decode("utf-8")) if raw else None
                return payload, dict(response.headers)
        except HTTPError as exc:
            try:
                raw = exc.read().decode("utf-8")
                parsed = json.loads(raw) if raw else {}
                message = parsed.get("message") or exc.reason or "HTTP error"
            except Exception:
                message = exc.reason or "HTTP error"
            raise GitHubApiError(exc.code, str(message), logical_path) from None
        except URLError as exc:
            raise GitHubApiError(None, str(exc.reason), logical_path) from None

    def get_json(self, path: str, params=None):
        payload, _ = self._request(self._url(path, params), path)
        return payload

    @staticmethod
    def _next_link(link_header: str | None) -> str | None:
        if not link_header:
            return None
        for part in link_header.split(","):
            section = part.strip()
            if 'rel="next"' not in section:
                continue
            if section.startswith("<") and ">" in section:
                return section[1 : section.index(">")]
        return None

    def get_paginated(self, path: str, item_key: str | None = None, params=None, max_pages: int = 10):
        url = self._url(path, params)
        logical_path = path
        items = []
        for _ in range(max_pages):
            payload, headers = self._request(url, logical_path)
            page_items = payload.get(item_key, []) if item_key else payload
            if not isinstance(page_items, list):
                raise GitHubApiError(None, "paginated response was not a list", logical_path)
            items.extend(page_items)
            next_url = self._next_link(headers.get("Link") or headers.get("link"))
            if not next_url:
                break
            parsed = urlparse(next_url)
            if parsed.netloc and parsed.netloc != urlparse(self.base_url).netloc:
                raise GitHubApiError(None, "refusing pagination to a different host", logical_path)
            url = next_url
        return items
