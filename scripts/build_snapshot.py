#!/usr/bin/env python3
"""Merge bounded provider evidence into the normalized Operations snapshot."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path


LEGACY_DEFERRED_ACTION_PREFIX = "Account-level read access will eventually be required"


def _billing_usage_summary(items: list[dict]) -> str | None:
    parts = []
    for item in items:
        sku = item.get("sku") or "unknown-sku"
        unit = item.get("unitType") or "units"
        gross = item.get("grossQuantity")
        discount = item.get("discountQuantity")
        net = item.get("netQuantity")
        parts.append(f"{sku}: gross={gross} {unit}, discount={discount} {unit}, net={net} {unit}")
    return "; ".join(parts) if parts else None


def _merge_costs(seed_costs: list[dict], billing: dict) -> list[dict]:
    costs = copy.deepcopy(seed_costs)
    github = next((item for item in costs if item.get("id") == "github-actions"), None)
    if github is None:
        github = {
            "id": "github-actions",
            "service": "GitHub Actions",
            "owner": "parent-shared-cost-guardrail",
            "consumer": "Academic Door-wide",
        }
        costs.append(github)

    github["evidence_class"] = billing.get("evidence_class", "UNKNOWN")
    github["amount"] = billing.get("net_amount")
    github["currency"] = None
    github["gross_amount"] = billing.get("gross_amount")
    github["discount_amount"] = billing.get("discount_amount")
    github["usage_quantity"] = billing.get("net_quantity")
    github["usage_unit"] = billing.get("unit_type")
    github["usage_summary"] = _billing_usage_summary(billing.get("items", []))

    if github["evidence_class"] == "ACTUAL":
        if (github.get("amount") or 0) == 0 and (github.get("gross_amount") or 0) > 0:
            github["status"] = "current-month billable net is zero; observed usage is covered by included usage/discounts"
        else:
            github["status"] = "authoritative current-month organization billing usage observed"
    else:
        github["status"] = billing.get("reason") or "organization billing usage unavailable"

    github["source"] = "GitHub organization billing usage summary API"
    if github["evidence_class"] == "ACTUAL":
        github["note"] = (
            f"gross_amount={github.get('gross_amount')}; discount_amount={github.get('discount_amount')}; "
            f"net_amount={github.get('amount')}; usage={github.get('usage_summary') or 'mixed/unspecified units'}"
        )
    else:
        github["note"] = "UNKNOWN is preserved; no zero-cost inference is allowed."
    return costs


def _actions(entries: list[dict]) -> list[dict]:
    result = []
    for entry in entries:
        failures = entry.get("failure_count", 0)
        runs = entry.get("run_count", 0)
        result.append(
            {
                "repository": entry.get("repository"),
                "workflow_class": entry.get("workflow_name") or entry.get("workflow_path") or "unknown-workflow",
                "evidence_class": entry.get("evidence_class", "ESTIMATED"),
                "status": f"{runs} runs in {entry.get('window_days')}d; failures={failures}",
                "source": "GitHub Actions workflow/run REST evidence",
                "note": "Estimated minutes are workflow wall-clock duration, not authoritative billed runner minutes.",
                "run_count": runs,
                "estimated_minutes": entry.get("estimated_wall_minutes"),
                "window_days": entry.get("window_days"),
                "success_count": entry.get("success_count", 0),
                "failure_count": failures,
                "cancelled_count": entry.get("cancelled_count", 0),
            }
        )
    return result


def _metadata_records(github_evidence: dict):
    metadata = github_evidence.get("credential_metadata", {})
    for item in metadata.get("organization", []):
        yield item.get("name"), item, "Academic Door organization"
    for repository, items in metadata.get("repositories", {}).items():
        for item in items:
            yield item.get("name"), item, repository


def _credentials(seed_credentials: list[dict], github_evidence: dict) -> list[dict]:
    credentials = copy.deepcopy(seed_credentials)
    by_name = {item.get("logical_name"): item for item in credentials}

    for name, metadata, consumer in _metadata_records(github_evidence):
        if not name:
            continue
        item = by_name.get(name)
        if item is None:
            item = {
                "logical_name": name,
                "provider": "UNKNOWN_PROVIDER",
                "owner": "inventory-unclassified",
                "consumers": [],
                "secret_value_policy": "NEVER_COLLECT",
                "status": "metadata-observed",
                "last_legitimate_use_source": None,
                "note": "Discovered from GitHub Actions secret metadata; provider/owner classification remains separate from secret storage metadata.",
            }
            credentials.append(item)
            by_name[name] = item

        consumers = item.setdefault("consumers", [])
        if consumer not in consumers:
            consumers.append(consumer)
        item["status"] = "metadata-observed"
        item["created_at"] = metadata.get("created_at") or item.get("created_at")
        item["updated_at"] = metadata.get("updated_at") or item.get("updated_at")
        scope = metadata.get("scope")
        previous_scope = item.get("storage_scope")
        if scope:
            item["storage_scope"] = scope if not previous_scope or previous_scope == scope else "mixed"
        if metadata.get("visibility") is not None:
            item["visibility"] = metadata.get("visibility")

        # Whitelist only metadata fields above. Values/tokens/authorization data are never copied.
        item.pop("secret_value", None)
        item.pop("value", None)
        item.pop("token", None)
        item.pop("authorization", None)
        item.pop("private_key", None)

    for item in credentials:
        item["consumers"] = sorted(set(item.get("consumers", [])))
    return sorted(credentials, key=lambda item: item.get("logical_name", ""))


def _human_actions(seed_actions: list[str], gaps: list[dict]) -> list[str]:
    actions = [
        item
        for item in seed_actions
        if item
        and item != "NONE"
        and not item.startswith(LEGACY_DEFERRED_ACTION_PREFIX)
    ]
    for gap in gaps:
        area = gap.get("area")
        if area == "github-billing":
            actions.append(
                "GitHub organization billing remains unreadable after the Operations App probe; verify Administration:read and enhanced-billing availability before treating GitHub cost as ACTUAL."
            )
    return list(dict.fromkeys(actions))


def build_snapshot(seed: dict, github_evidence: dict) -> dict:
    snapshot = copy.deepcopy(seed)
    snapshot["observed_at"] = github_evidence["observed_at"]
    snapshot["costs"] = _merge_costs(seed.get("costs", []), github_evidence.get("billing", {}))
    snapshot["actions"] = _actions(github_evidence.get("actions", []))
    snapshot["credentials"] = _credentials(seed.get("credentials", []), github_evidence)
    snapshot["human_actions"] = _human_actions(seed.get("human_actions", []), github_evidence.get("gaps", []))
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", default="data/seed-snapshot.json")
    parser.add_argument("--github", default="data/github-latest.json")
    parser.add_argument("--output", default="data/latest.json")
    args = parser.parse_args()

    seed = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    github = json.loads(Path(args.github).read_text(encoding="utf-8"))
    snapshot = build_snapshot(seed, github)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
