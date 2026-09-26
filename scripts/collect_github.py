#!/usr/bin/env python3
"""Collect bounded, read-only GitHub operations evidence."""

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


def _safe_secret(item: dict, scope: str, repository: str | None = None) -> dict:
    safe = {
        "name": item.get("name"),
        "scope": scope,
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }
    if scope == "organization":
        safe["visibility"] = item.get("visibility")
    if repository:
        safe["repository"] = repository
    return safe


def _gap(area: str, error: GitHubApiError, repository: str | None = None) -> dict:
    item = {"area": area, "status": error.status, "message": str(error), "repository": repository}
    return item


def _billing(api: GitHubApi, org: str, observed: datetime, gaps: list[dict]) -> dict:
    path = f"/organizations/{org}/settings/billing/usage/summary"
    try:
        payload = api.get_json(path, params={"year": observed.year, "month": observed.month, "product": "Actions"}) or {}
    except GitHubApiError as error:
        gaps.append(_gap("github-billing", error))
        return {
            "evidence_class": "UNKNOWN",
            "net_amount": None,
            "gross_amount": None,
            "discount_amount": None,
            "net_quantity": None,
            "unit_type": None,
            "items": [],
            "reason": str(error),
        }

    items = [item for item in payload.get("usageItems", []) if str(item.get("product", "")).lower() == "actions"]
    net_amount = round(sum(float(item.get("netAmount") or 0) for item in items), 6)
    gross_amount = round(sum(float(item.get("grossAmount") or 0) for item in items), 6)
    discount_amount = round(sum(float(item.get("discountAmount") or 0) for item in items), 6)
    net_quantity = sum(float(item.get("netQuantity") or item.get("quantity") or 0) for item in items)
    unit_types = {item.get("unitType") for item in items if item.get("unitType")}
    return {
        "evidence_class": "ACTUAL",
        "net_amount": net_amount,
        "gross_amount": gross_amount,
        "discount_amount": discount_amount,
        "net_quantity": net_quantity if len(unit_types) == 1 else None,
        "unit_type": next(iter(unit_types)) if len(unit_types) == 1 else None,
        "items": items,
        "reason": None,
    }


def collect_github(api: GitHubApi, org: str, observed_at: str, run_window_days: int = 14) -> dict:
    observed = _dt(observed_at)
    if observed is None:
        raise ValueError("observed_at must be ISO-8601")
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)

    gaps: list[dict] = []
    repos = api.get_paginated("/installation/repositories", item_key="repositories", params={"per_page": 100}, max_pages=20)
    repositories = []
    actions = []
    repo_secret_metadata: dict[str, list[dict]] = {}
    since = observed - timedelta(days=run_window_days)
    created_filter = f">={since.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"

    for repo in sorted(repos, key=lambda item: item.get("full_name", "")):
        full_name = repo.get("full_name")
        if not full_name or not full_name.startswith(f"{org}/"):
            continue
        repositories.append(
            {
                "name": repo.get("name"),
                "full_name": full_name,
                "private": bool(repo.get("private")),
                "archived": bool(repo.get("archived")),
                "default_branch": repo.get("default_branch"),
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
                    estimated_wall_minutes += _minutes(run.get("run_started_at"), run.get("updated_at"))
                actions.append(
                    {
                        "repository": full_name,
                        "repository_visibility": "PRIVATE" if bool(repo.get("private")) else "PUBLIC",
                        "billing_scarcity_class": (
                            "PRIVATE_INCLUDED_MINUTES"
                            if bool(repo.get("private"))
                            else "PUBLIC_STANDARD_RUNNER_FREE_ELIGIBLE"
                        ),
                        "workflow_id": workflow.get("id"),
                        "workflow_name": workflow.get("name"),
                        "workflow_path": workflow.get("path"),
                        "workflow_state": workflow.get("state"),
                        "run_count": len(workflow_runs),
                        "success_count": conclusions.get("success", 0),
                        "failure_count": conclusions.get("failure", 0),
                        "cancelled_count": conclusions.get("cancelled", 0),
                        "other_count": len(workflow_runs)
                        - conclusions.get("success", 0)
                        - conclusions.get("failure", 0)
                        - conclusions.get("cancelled", 0),
                        "estimated_wall_minutes": round(estimated_wall_minutes, 2),
                        "window_days": run_window_days,
                        "evidence_class": "ESTIMATED",
                    }
                )
        except GitHubApiError as error:
            gaps.append(_gap("github-actions", error, full_name))

        try:
            secrets = api.get_paginated(
                f"/repos/{owner}/{name}/actions/secrets",
                item_key="secrets",
                params={"per_page": 100},
                max_pages=10,
            )
            repo_secret_metadata[full_name] = [_safe_secret(item, "repository", full_name) for item in secrets]
        except GitHubApiError as error:
            gaps.append(_gap("github-repository-secret-metadata", error, full_name))
            repo_secret_metadata[full_name] = []

    try:
        org_secrets = api.get_paginated(
            f"/orgs/{org}/actions/secrets",
            item_key="secrets",
            params={"per_page": 100},
            max_pages=10,
        )
        org_secret_metadata = [_safe_secret(item, "organization") for item in org_secrets]
    except GitHubApiError as error:
        gaps.append(_gap("github-organization-secret-metadata", error))
        org_secret_metadata = []

    billing = _billing(api, org, observed, gaps)

    return {
        "schema_version": 1,
        "observed_at": observed_at,
        "organization": org,
        "run_window_days": run_window_days,
        "repositories": repositories,
        "actions": sorted(actions, key=lambda item: (item["repository"], item.get("workflow_name") or "")),
        "billing": billing,
        "credential_metadata": {
            "organization": org_secret_metadata,
            "repositories": repo_secret_metadata,
        },
        "gaps": gaps,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", default=os.environ.get("OPS_GITHUB_ORG", "academic-door"))
    parser.add_argument("--output", default="data/github-latest.json")
    parser.add_argument("--run-window-days", type=int, default=14)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_READ_TOKEN")
    if not token:
        raise SystemExit("GITHUB_READ_TOKEN is required")
    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = collect_github(GitHubApi(token), args.org, observed_at, args.run_window_days)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
