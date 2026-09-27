#!/usr/bin/env python3
"""Collect bounded, read-only GitHub operations evidence.

Raw output is transient workflow input. Public persistence is handled only by
scripts.build_snapshot after strict aggregation/sanitization.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.github_api import GitHubApi, GitHubApiError


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _minutes(start: str | None, end: str | None) -> float:
    started = _dt(start)
    finished = _dt(end)
    if not started or not finished or finished < started:
        return 0.0
    return round((finished - started).total_seconds() / 60.0, 2)


def _gap(area: str, error: GitHubApiError, repository: str | None = None) -> dict:
    return {
        "area": area,
        "status": error.status,
        "message": str(error),
        "repository": repository,
    }


def _billing(api: GitHubApi, org: str, observed: datetime, gaps: list[dict]) -> dict:
    path = f"/organizations/{org}/settings/billing/usage/summary"
    try:
        payload = api.get_json(
            path,
            params={"year": observed.year, "month": observed.month, "product": "Actions"},
        ) or {}
    except GitHubApiError as error:
        gaps.append(_gap("github-billing", error))
        return {
            "evidence_class": "UNKNOWN",
            "net_amount": None,
            "gross_amount": None,
            "discount_amount": None,
            "reason": str(error),
        }

    items = [
        item
        for item in payload.get("usageItems", [])
        if str(item.get("product", "")).lower() == "actions"
    ]
    return {
        "evidence_class": "ACTUAL",
        "net_amount": round(sum(float(item.get("netAmount") or 0) for item in items), 6),
        "gross_amount": round(sum(float(item.get("grossAmount") or 0) for item in items), 6),
        "discount_amount": round(sum(float(item.get("discountAmount") or 0) for item in items), 6),
        "reason": None,
    }


def collect_github(api: GitHubApi, org: str, observed_at: str, run_window_days: int = 14) -> dict:
    observed = _dt(observed_at)
    if observed is None:
        raise ValueError("observed_at must be ISO-8601")
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)

    gaps: list[dict] = []
    repos = api.get_paginated(
        "/installation/repositories",
        item_key="repositories",
        params={"per_page": 100},
        max_pages=20,
    )
    repositories = []
    actions = []
    since = observed - timedelta(days=run_window_days)
    created_filter = f">={since.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"

    for repo in sorted(repos, key=lambda item: item.get("full_name", "")):
        full_name = repo.get("full_name")
        if not full_name or not full_name.startswith(f"{org}/"):
            continue

        repositories.append(
            {
                "full_name": full_name,
                "private": bool(repo.get("private")),
                "archived": bool(repo.get("archived")),
            }
        )
        owner, name = full_name.split("/", 1)

        try:
            workflows = api.get_paginated(
                f"/repos/{owner}/{name}/actions/workflows",
                item_key="workflows",
                params={"per_page": 100},
                max_pages=10,
            )
            runs = api.get_paginated(
                f"/repos/{owner}/{name}/actions/runs",
                item_key="workflow_runs",
                params={"per_page": 100, "created": created_filter},
                max_pages=5,
            )
            grouped = defaultdict(list)
            for run in runs:
                grouped[run.get("workflow_id")].append(run)

            for workflow in workflows:
                workflow_runs = grouped.get(workflow.get("id"), [])
                if not workflow_runs:
                    continue
                conclusions = defaultdict(int)
                estimated_wall_minutes = 0.0
                for run in workflow_runs:
                    conclusions[run.get("conclusion") or "unknown"] += 1
                    estimated_wall_minutes += _minutes(
                        run.get("run_started_at"), run.get("updated_at")
                    )
                actions.append(
                    {
                        "repository": full_name,
                        "workflow_id": workflow.get("id"),
                        "run_count": len(workflow_runs),
                        "failure_count": conclusions.get("failure", 0),
                        "estimated_wall_minutes": round(estimated_wall_minutes, 2),
                    }
                )
        except GitHubApiError as error:
            gaps.append(_gap("github-actions", error, full_name))

    return {
        "schema_version": 2,
        "observed_at": observed_at,
        "organization": org,
        "run_window_days": run_window_days,
        "repositories": repositories,
        "actions": actions,
        "billing": _billing(api, org, observed, gaps),
        "gaps": gaps,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", default=os.environ.get("OPS_GITHUB_ORG", "academic-door"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--run-window-days", type=int, default=14)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_READ_TOKEN")
    if not token:
        raise SystemExit("GITHUB_READ_TOKEN is required")

    observed_at = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    payload = collect_github(
        GitHubApi(token), args.org, observed_at, args.run_window_days
    )
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
