#!/usr/bin/env python3
"""Build the public-safe Academic Door Operations snapshot.

Raw GitHub/account/owner evidence is input-only and may contain private
repository identifiers or account-level details. This module emits a strict
allowlisted aggregate designed for public persistence.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path


PUBLIC_PROVIDER_IDS = ("crossref", "openalex", "semantic-scholar", "elsevier")
PROVIDER_DISPLAY = {
    "crossref": "Crossref",
    "openalex": "OpenAlex",
    "semantic-scholar": "Semantic Scholar",
    "elsevier": "Elsevier",
}


def _provider_status(payload: dict) -> str:
    control = payload.get("control") or {}
    if (payload.get("rate_limited") or 0) > 0 or control.get("circuit_open"):
        return "PRESSURED"
    if (payload.get("failed") or 0) > 0 or (payload.get("http_error") or 0) > 0:
        return "WATCH"
    return "HEALTHY"


def _billing(raw: dict) -> dict:
    if raw.get("evidence_class") != "ACTUAL" or raw.get("net_amount") is None:
        return {"evidence_class": "UNKNOWN", "billable_state": "UNKNOWN"}
    return {
        "evidence_class": "ACTUAL",
        "billable_state": "ZERO" if float(raw.get("net_amount") or 0) == 0 else "POSITIVE",
    }


def _action_aggregates(github: dict) -> dict:
    visibility = {
        item.get("full_name"): ("PRIVATE" if item.get("private") else "PUBLIC")
        for item in github.get("repositories", [])
        if item.get("full_name")
    }

    classes = {
        "PUBLIC_STANDARD_RUNNER_FREE_ELIGIBLE": {
            "class": "PUBLIC_STANDARD_RUNNER_FREE_ELIGIBLE",
            "repositories_observed": sum(
                1
                for item in github.get("repositories", [])
                if not item.get("private") and not item.get("archived")
            ),
            "workflows_with_runs": 0,
            "run_count": 0,
            "failure_count": 0,
            "estimated_wall_minutes": 0.0,
        },
        "PRIVATE_INCLUDED_MINUTES": {
            "class": "PRIVATE_INCLUDED_MINUTES",
            "repositories_observed": sum(
                1
                for item in github.get("repositories", [])
                if item.get("private") and not item.get("archived")
            ),
            "workflows_with_runs": 0,
            "run_count": 0,
            "failure_count": 0,
            "estimated_wall_minutes": 0.0,
        },
    }

    for item in github.get("actions", []):
        repo_visibility = visibility.get(item.get("repository"))
        if repo_visibility == "PUBLIC":
            target = classes["PUBLIC_STANDARD_RUNNER_FREE_ELIGIBLE"]
        elif repo_visibility == "PRIVATE":
            target = classes["PRIVATE_INCLUDED_MINUTES"]
        else:
            continue
        target["workflows_with_runs"] += 1
        target["run_count"] += int(item.get("run_count") or 0)
        target["failure_count"] += int(item.get("failure_count") or 0)
        target["estimated_wall_minutes"] += float(
            item.get("estimated_wall_minutes") or 0
        )

    for item in classes.values():
        item["estimated_wall_minutes"] = round(item["estimated_wall_minutes"], 2)

    return {
        "window_days": int(github.get("run_window_days") or 0),
        "classes": [
            classes["PUBLIC_STANDARD_RUNNER_FREE_ELIGIBLE"],
            classes["PRIVATE_INCLUDED_MINUTES"],
        ],
    }


def _provider_health(owner: dict) -> list[dict]:
    source = (owner.get("daily_provider_health") or {})
    observed_at = source.get("observed_at")
    providers = source.get("providers") or {}
    result = []
    for provider_id in PUBLIC_PROVIDER_IDS:
        payload = providers.get(provider_id)
        if not payload:
            continue
        result.append(
            {
                "provider": PROVIDER_DISPLAY[provider_id],
                "status": _provider_status(payload),
                "observed_at": observed_at,
                "attempts": int(payload.get("attempts") or 0),
                "available": int(payload.get("available") or 0),
                "failed": int(payload.get("failed") or 0),
                "rate_limited": int(payload.get("rate_limited") or 0),
                "skipped": int(payload.get("skipped") or 0),
            }
        )
    return result


def _public_costs(owner: dict) -> list[dict]:
    ai = owner.get("daily_ai_cost") or {}
    if ai.get("current_month_estimated_cost") is None:
        return []
    return [
        {
            "service": "DeepSeek",
            "evidence_class": "ESTIMATED",
            "amount": float(ai.get("current_month_estimated_cost") or 0),
            "currency": ai.get("currency") or "USD",
            "period": "CURRENT_MONTH",
            "observed_at": ai.get("observed_at"),
        }
    ]


def _services(seed_services: list[dict], owner: dict) -> list[dict]:
    result = copy.deepcopy(seed_services)
    by_id = {item["id"]: item for item in result}

    ai = owner.get("daily_ai_cost") or {}
    deepseek = by_id.get("deepseek-inference")
    if deepseek and (ai.get("rolling_30d_requests") or 0) > 0:
        deepseek.update(
            {
                "lifecycle_state": "ACTIVE",
                "usefulness_status": "PROVEN",
                "status": "active owner-metered inference",
                "last_success_at": ai.get("observed_at"),
                "last_failure_at": None,
            }
        )

    health = owner.get("daily_provider_health") or {}
    observed_at = health.get("observed_at")
    providers = health.get("providers") or {}
    mapping = {
        "crossref": "crossref",
        "openalex": "openalex",
        "semantic-scholar": "semantic-scholar",
        "elsevier": "elsevier-metadata",
    }
    for provider_id, service_id in mapping.items():
        item = by_id.get(service_id)
        payload = providers.get(provider_id)
        if not item or not payload:
            continue
        status = _provider_status(payload)
        available = int(payload.get("available") or 0)
        item.update(
            {
                "lifecycle_state": "ACTIVE_DEGRADED"
                if status in {"PRESSURED", "WATCH"}
                else "ACTIVE",
                "usefulness_status": "PROVEN"
                if available > 0
                else "ACTIVE_UNVERIFIED",
                "status": f"public owner health={status}",
                "last_success_at": observed_at if available > 0 else item.get("last_success_at"),
                "last_failure_at": observed_at
                if status in {"PRESSURED", "WATCH"}
                else None,
            }
        )

    journals = owner.get("journals_monitoring") or {}
    item = by_id.get("journals-production-monitor")
    if item and journals:
        healthy = journals.get("status") == "healthy"
        item.update(
            {
                "lifecycle_state": "ACTIVE" if healthy else "ACTIVE_DEGRADED",
                "usefulness_status": "PROVEN" if healthy else "ACTIVE_UNVERIFIED",
                "status": "healthy public production monitor"
                if healthy
                else "public production monitor degraded",
                "last_success_at": journals.get("observed_at") if healthy else item.get("last_success_at"),
                "last_failure_at": None if healthy else journals.get("observed_at"),
            }
        )

    return result


def _alerts(billing: dict) -> list[dict]:
    if billing.get("evidence_class") == "ACTUAL" and billing.get("billable_state") == "POSITIVE":
        return [
            {
                "condition": "GITHUB_ACTIONS_POSITIVE_BILLABLE_NET",
                "severity": "PARENT_REVIEW",
                "summary": "GitHub Actions current-period billable net is positive.",
            }
        ]
    return []


def build_snapshot(seed: dict, github_evidence: dict, owner_evidence: dict | None = None) -> dict:
    owner = owner_evidence or {}
    billing = _billing(github_evidence.get("billing") or {})
    return {
        "schema_version": 1,
        "observed_at": owner.get("observed_at") or github_evidence.get("observed_at"),
        "scope": "ACADEMIC_DOOR_PUBLIC_SAFE",
        "billing": {"github_actions": billing},
        "costs": _public_costs(owner),
        "provider_health": _provider_health(owner),
        "services": _services(seed.get("services", []), owner),
        "actions": _action_aggregates(github_evidence),
        "alerts": _alerts(billing),
        "human_actions": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", default="data/seed-snapshot.json")
    parser.add_argument("--github", required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    seed = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    github = json.loads(Path(args.github).read_text(encoding="utf-8"))
    owner = json.loads(Path(args.owner).read_text(encoding="utf-8"))
    snapshot = build_snapshot(seed, github, owner)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
