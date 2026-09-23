#!/usr/bin/env python3
"""Merge bounded GitHub and owner evidence into the normalized Operations snapshot."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path


LEGACY_DEFERRED_ACTION_PREFIX = "Account-level read access will eventually be required"

CREDENTIAL_CLASSIFICATION = {
    "AUTO_REVIEWER_APP_ID": ("GitHub App", "journal-system"),
    "AUTO_REVIEWER_PRIVATE_KEY": ("GitHub App", "journal-system"),
    "CF_WEB_ANALYTICS_TOKEN": ("Cloudflare", "frontier-door"),
    "CLOUDFLARE_ACCOUNT_ID": ("Cloudflare", "mixed-product-runtime"),
    "CLOUDFLARE_API_TOKEN": ("Cloudflare", "mixed-product-runtime"),
    "COMPOSER_DEPLOY_KEY": ("GitHub Deploy Key", "composer"),
    "DEEPSEEK_API_KEY": ("DeepSeek", "product-local-with-parent-cost-escalation"),
    "NOTIFICATION_EMAIL_TO": ("NetEase 163 project mailbox", "parent-shared-notification-routing"),
    "OPS_APP_PRIVATE_KEY": ("GitHub App", "parent-shared-operations"),
    "PUBLIC_PAGES_DEPLOY_KEY": ("GitHub Deploy Key", "frontier-door"),
    "QWEN_API_KEY": ("Qwen / DashScope / Alibaba Cloud", "daily-door-benchmark-capability"),
    "SMTP_FROM": ("NetEase 163 SMTP", "journal-system"),
    "SMTP_HOST": ("NetEase 163 SMTP", "journal-system"),
    "SMTP_PASSWORD": ("NetEase 163 SMTP", "journal-system"),
    "SMTP_PORT": ("NetEase 163 SMTP", "journal-system"),
    "SMTP_SECURITY": ("NetEase 163 SMTP", "journal-system"),
    "SMTP_USERNAME": ("NetEase 163 SMTP", "journal-system"),
}


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


def _merge_costs(seed_costs: list[dict], billing: dict, observed_at: str | None = None) -> list[dict]:
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
    github["evidence_observed_at"] = observed_at or github.get("evidence_observed_at")
    github["coverage_status"] = (
        "ACTUAL_BILLED" if github["evidence_class"] == "ACTUAL" else "ACCOUNT_BILLING_UNKNOWN"
    )
    github["next_evidence_route"] = (
        "Continue the accepted GitHub organization billing usage API. "
        "Keep remaining included allowance UNKNOWN unless GitHub exposes it directly."
    )
    github["human_action_required"] = False
    github["human_action_reason"] = None
    if github["evidence_class"] == "ACTUAL":
        github["note"] = (
            f"gross_amount={github.get('gross_amount')}; discount_amount={github.get('discount_amount')}; "
            f"net_amount={github.get('amount')}; usage={github.get('usage_summary') or 'mixed/unspecified units'}"
        )
    else:
        github["note"] = "UNKNOWN is preserved; no zero-cost inference is allowed."
    return costs


def _merge_owner_costs(costs: list[dict], owner: dict | None) -> list[dict]:
    result = copy.deepcopy(costs)
    ai = (owner or {}).get("daily_ai_cost") or {}
    if not ai:
        return result
    item = next((x for x in result if x.get("id") == "deepseek-daily-door"), None)
    if item is None:
        item = {
            "id": "deepseek-daily-door",
            "service": "DeepSeek AI / translation / enrichment — Daily Door",
            "owner": "daily-door",
            "consumer": "academic-door/econ-paper-monitor",
        }
        result.append(item)
    item.update(
        {
            "evidence_class": "ESTIMATED",
            "amount": ai.get("current_month_estimated_cost"),
            "currency": ai.get("currency") or "USD",
            "gross_amount": None,
            "discount_amount": None,
            "usage_quantity": ai.get("rolling_30d_requests"),
            "usage_unit": "requests/rolling-30d",
            "usage_summary": (
                f"rolling30d_estimated_cost={ai.get('rolling_30d_estimated_cost')} {ai.get('currency') or 'USD'}; "
                f"rolling30d_requests={ai.get('rolling_30d_requests')}"
            ),
            "status": "current-month cost estimate from owner token/request metering and pinned pricing table",
            "source": "academic-door/econ-paper-monitor:data/ai_cost_usage.json",
            "note": (
                f"observed_at={ai.get('observed_at')}; pricing_version={ai.get('pricing_version')}; "
                "ESTIMATED is not provider-billed spend."
            ),
            "coverage_status": "ESTIMATED_USAGE",
            "evidence_observed_at": ai.get("observed_at") or item.get("evidence_observed_at"),
            "next_evidence_route": (
                "Continue owner request/token metering for ESTIMATED cost; use an authoritative "
                "DeepSeek billing/usage console, export, or read-only account API to promote billed spend to ACTUAL."
            ),
            "human_action_required": False,
            "human_action_reason": None,
        }
    )
    return result


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

        classification = CREDENTIAL_CLASSIFICATION.get(name)
        if classification:
            provider, owner = classification
            item["provider"] = provider
            item["owner"] = owner
            existing_note = item.get("note") or ""
            classification_note = (
                "Provider/owner classification is metadata-only from the logical credential name and "
                "current owner contract; no secret value was read."
            )
            if classification_note not in existing_note:
                item["note"] = " ".join(part for part in (existing_note, classification_note) if part).strip()

        # Whitelist only metadata fields above. Values/tokens/authorization data are never copied.
        item.pop("secret_value", None)
        item.pop("value", None)
        item.pop("token", None)
        item.pop("authorization", None)
        item.pop("private_key", None)

    for item in credentials:
        item["consumers"] = sorted(set(item.get("consumers", [])))
    return sorted(credentials, key=lambda item: item.get("logical_name", ""))


def _merge_owner_credentials(credentials: list[dict], owner: dict | None) -> list[dict]:
    result = copy.deepcopy(credentials)
    by_name = {item.get("logical_name"): item for item in result}
    usage = (owner or {}).get("daily_provider_usage") or {}
    health = (owner or {}).get("daily_provider_health") or {}
    providers = usage.get("providers") or {}
    health_providers = health.get("providers") or {}

    s2_usage = providers.get("semantic-scholar") or {}
    s2 = by_name.get("SEMANTIC_SCHOLAR_API_KEY")
    if s2 and s2_usage:
        last_used = s2_usage.get("last_used_at")
        pressure = health_providers.get("semantic-scholar") or {}
        pressured = bool((pressure.get("control") or {}).get("circuit_open") or pressure.get("rate_limited"))
        s2["status"] = (
            f"configured; legitimate use observed at {last_used}; "
            + ("provider pressure present" if pressured else "no current pressure observed")
        )
        note_parts = [s2.get("note") or ""]
        if usage.get("synthetic_keepalive_observed"):
            note_parts.append(
                "Synthetic keep-alive still observed in owner telemetry; owner reconciliation remains "
                f"econ-paper-monitor#208 (reason={usage.get('synthetic_keepalive_reason')})."
            )
        s2["note"] = " ".join(part for part in note_parts if part).strip()
        s2["last_legitimate_use_source"] = "academic-door/econ-paper-monitor:data/semantic_scholar_usage.json"

    elsevier_usage = providers.get("elsevier") or {}
    for logical_name in ("ELSEVIER_API_KEY", "ELSEVIER_INST_TOKEN"):
        item = by_name.get(logical_name)
        if item and elsevier_usage:
            item["status"] = (
                f"configured; legitimate use observed at {elsevier_usage.get('last_used_at')}; "
                f"rate_limited={((elsevier_usage.get('total') or {}).get('rate_limited', 0))}"
            )
            item["last_legitimate_use_source"] = "academic-door/econ-paper-monitor:data/semantic_scholar_usage.json"

    return sorted(result, key=lambda item: item.get("logical_name", ""))


def _quota_status(provider_name: str, payload: dict) -> str:
    rate_limited = payload.get("rate_limited", 0) or 0
    failed = payload.get("failed", 0) or 0
    circuit_open = bool((payload.get("control") or {}).get("circuit_open"))
    if provider_name == "semantic-scholar" and (rate_limited or circuit_open):
        return "PRESSURED"
    if rate_limited:
        return "PRESSURED"
    if failed:
        return "WATCH"
    return "HEALTHY"


def _merge_owner_quotas(seed_quotas: list[dict], owner: dict | None) -> list[dict]:
    result = copy.deepcopy(seed_quotas)
    by_id = {item.get("id"): item for item in result}
    health = (owner or {}).get("daily_provider_health") or {}
    providers = health.get("providers") or {}
    mappings = {
        "semantic-scholar": ("semantic-scholar-academic-graph", "Semantic Scholar"),
        "elsevier": ("elsevier-metadata", "Elsevier"),
        "crossref": ("crossref", "Crossref"),
        "openalex": ("openalex", "OpenAlex"),
    }
    for provider_name, (item_id, display_name) in mappings.items():
        payload = providers.get(provider_name)
        if not payload:
            continue
        item = by_id.get(item_id)
        if item is None:
            item = {
                "id": item_id,
                "provider": display_name,
                "owner": "daily-door" if provider_name == "semantic-scholar" else "product-local-provider-use",
            }
            result.append(item)
            by_id[item_id] = item
        control = payload.get("control") or {}
        item.update(
            {
                "evidence_class": "PROVIDER_REPORTED",
                "limit": None,
                "remaining": None,
                "status": _quota_status(provider_name, payload),
                "source": "academic-door/econ-paper-monitor:data/metadata_provider_health.json",
                "note": (
                    f"observed_at={health.get('observed_at')}; attempts={payload.get('attempts', 0)}; "
                    f"available={payload.get('available', 0)}; empty={payload.get('empty', 0)}; "
                    f"failed={payload.get('failed', 0)}; rate_limited={payload.get('rate_limited', 0)}; "
                    f"skipped={payload.get('skipped', 0)}"
                    + (
                        f"; circuit_open={control.get('circuit_open')}; client_target_rps={control.get('client_target_rps')}"
                        if control
                        else ""
                    )
                    + "; provider account quota is not invented when not exposed"
                ),
            }
        )
    return result


def _merge_services(seed_services: list[dict], billing: dict, owner: dict | None) -> list[dict]:
    result = copy.deepcopy(seed_services)
    by_id = {item.get("id"): item for item in result}
    github = by_id.get("github-organization")
    if github and billing.get("evidence_class") == "ACTUAL":
        github["evidence_class"] = "ACTUAL"
        github["status"] = "operational; organization Actions billing usage observable"
        github["source"] = "GitHub organization billing usage summary API"

    journals = (owner or {}).get("journals_monitoring") or {}
    if journals:
        item = by_id.get("journals-production-monitor")
        if item is None:
            item = {
                "id": "journals-production-monitor",
                "category": "product-runtime-health",
                "owner": "journal-system",
                "purpose": "Bounded production health summary for the Journal System.",
                "consumers": ["academic-door/journals"],
                "lifecycle_state": "ACTIVE",
                "current_role": "owner production health monitor",
                "operational_evidence_class": "OWNER_RUNTIME",
                "usefulness_status": "PROVEN",
                "last_success_at": None,
                "last_success_source": None,
                "last_failure_at": None,
                "last_failure_source": None,
                "cost_pointer": None,
                "retirement_condition": (
                    "Retire only if the Journal System replaces this monitoring contract with an accepted successor."
                ),
            }
            result.append(item)
            by_id[item["id"]] = item
        summary = journals.get("summary") or {}
        item.update(
            {
                "evidence_class": "ACTUAL",
                "status": (
                    f"{journals.get('status')}; configured_journals={summary.get('configured_journals', 0)}; "
                    f"warnings={summary.get('warnings', 0)}; failed={summary.get('failed', 0)}; "
                    f"awaiting_official={summary.get('awaiting_official', 0)}"
                ),
                "source": "academic-door/journals:data:public/api/v1/monitoring.json",
                "note": f"observed_at={journals.get('observed_at')}; schedule={journals.get('schedule')}",
                "last_success_at": (
                    journals.get("observed_at") if journals.get("status") == "healthy" else item.get("last_success_at")
                ),
                "last_success_source": (
                    "academic-door/journals:data:public/api/v1/monitoring.json"
                    if journals.get("status") == "healthy"
                    else item.get("last_success_source")
                ),
                "last_failure_at": (
                    journals.get("observed_at") if journals.get("status") not in (None, "healthy") else None
                ),
                "last_failure_source": (
                    "academic-door/journals:data:public/api/v1/monitoring.json"
                    if journals.get("status") not in (None, "healthy")
                    else None
                ),
            }
        )
    return result


def _material_alerts(snapshot: dict) -> list[dict]:
    alerts = []

    github = next((item for item in snapshot.get("costs", []) if item.get("id") == "github-actions"), None)
    if github and github.get("evidence_class") == "ACTUAL":
        amount = github.get("amount")
        if isinstance(amount, (int, float)) and amount > 0:
            currency = github.get("currency")
            amount_text = f"{amount} {currency}" if currency else str(amount)
            alerts.append(
                {
                    "id": "github-actions-positive-billable-net",
                    "severity": "PARENT_REVIEW",
                    "scope": "PARENT",
                    "condition": "GITHUB_ACTIONS_POSITIVE_BILLABLE_NET",
                    "evidence_class": "ACTUAL",
                    "summary": f"GitHub Actions current-period billable net is positive: {amount_text}",
                    "source": github.get("source") or "GitHub organization billing evidence",
                }
            )

    for quota in snapshot.get("quotas", []):
        if quota.get("status") != "EXHAUSTED":
            continue
        evidence = quota.get("evidence_class")
        if evidence not in {"ACTUAL", "PROVIDER_REPORTED"}:
            continue
        quota_id = quota.get("id") or "unknown"
        provider = quota.get("provider") or quota_id
        alerts.append(
            {
                "id": f"quota-exhausted-{quota_id}",
                "severity": "PARENT_REVIEW",
                "scope": "PARENT",
                "condition": "AUTHORITATIVE_QUOTA_EXHAUSTED",
                "evidence_class": evidence,
                "summary": f"{provider} quota is explicitly reported EXHAUSTED",
                "source": quota.get("source") or "normalized provider quota evidence",
            }
        )

    return alerts


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


def build_snapshot(seed: dict, github_evidence: dict, owner_evidence: dict | None = None) -> dict:
    snapshot = copy.deepcopy(seed)
    snapshot["observed_at"] = (owner_evidence or {}).get("observed_at") or github_evidence["observed_at"]
    costs = _merge_costs(seed.get("costs", []), github_evidence.get("billing", {}), github_evidence.get("observed_at"))
    snapshot["costs"] = _merge_owner_costs(costs, owner_evidence)
    snapshot["actions"] = _actions(github_evidence.get("actions", []))
    credentials = _credentials(seed.get("credentials", []), github_evidence)
    snapshot["credentials"] = _merge_owner_credentials(credentials, owner_evidence)
    snapshot["quotas"] = _merge_owner_quotas(seed.get("quotas", []), owner_evidence)
    snapshot["services"] = _merge_services(seed.get("services", []), github_evidence.get("billing", {}), owner_evidence)
    snapshot["human_actions"] = _human_actions(seed.get("human_actions", []), github_evidence.get("gaps", []))
    snapshot["alerts"] = _material_alerts(snapshot)
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", default="data/seed-snapshot.json")
    parser.add_argument("--github", default="data/github-latest.json")
    parser.add_argument("--owner", default=None)
    parser.add_argument("--output", default="data/latest.json")
    args = parser.parse_args()

    seed = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    github = json.loads(Path(args.github).read_text(encoding="utf-8"))
    owner = json.loads(Path(args.owner).read_text(encoding="utf-8")) if args.owner else None
    snapshot = build_snapshot(seed, github, owner)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
