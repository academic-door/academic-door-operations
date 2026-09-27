#!/usr/bin/env python3
"""Validate the strict public-safe Operations snapshot contract."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


TOP_KEYS = {
    "schema_version",
    "observed_at",
    "scope",
    "billing",
    "costs",
    "provider_health",
    "services",
    "actions",
    "alerts",
    "human_actions",
}

BILLING_KEYS = {"github_actions"}
GITHUB_BILLING_KEYS = {"evidence_class", "billable_state"}
COST_KEYS = {"service", "evidence_class", "amount", "currency", "period", "observed_at"}
PROVIDER_KEYS = {
    "provider",
    "status",
    "observed_at",
    "attempts",
    "available",
    "failed",
    "rate_limited",
    "skipped",
}
SERVICE_KEYS = {
    "id",
    "owner",
    "lifecycle_state",
    "usefulness_status",
    "status",
    "last_success_at",
    "last_failure_at",
}
ACTIONS_KEYS = {"window_days", "classes"}
ACTION_CLASS_KEYS = {
    "class",
    "repositories_observed",
    "workflows_with_runs",
    "run_count",
    "failure_count",
    "estimated_wall_minutes",
}
ALERT_KEYS = {"condition", "severity", "summary"}

FORBIDDEN_FIELD_FRAGMENTS = (
    "credential",
    "logical_name",
    "secret",
    "token",
    "password",
    "private_key",
    "payment_method",
    "invoice",
    "account_id",
)
FORBIDDEN_VALUE_PATTERNS = (
    re.compile(r"academic-door/", re.IGNORECASE),
    re.compile(r"#[0-9]+"),
    re.compile(r"human principal", re.IGNORECASE),
    re.compile(r"no payment|payment method|invoice", re.IGNORECASE),
    re.compile(r"\b[A-Z0-9_]*(?:API_KEY|TOKEN|PASSWORD|PRIVATE_KEY)[A-Z0-9_]*\b"),
    re.compile(r"\bSMTP_[A-Z0-9_]+\b"),
)

LIFECYCLE = {
    "ACTIVE",
    "ACTIVE_DEGRADED",
    "RETIRING",
    "RETIRED",
    "CONDITIONAL",
    "ACTIVE_UNVERIFIED",
}
USEFULNESS = {
    "PROVEN",
    "ACTIVE_UNVERIFIED",
    "RETIRE_BY_DEFAULT_PENDING_DAILY_PROVENANCE_GATE",
    "RETIRED",
    "CONDITIONAL",
}
PROVIDER_STATUS = {"HEALTHY", "WATCH", "PRESSURED", "UNKNOWN"}
BILLABLE_STATE = {"ZERO", "POSITIVE", "UNKNOWN"}
ACTION_CLASSES = {
    "PUBLIC_STANDARD_RUNNER_FREE_ELIGIBLE",
    "PRIVATE_INCLUDED_MINUTES",
}


def _exact_keys(obj: dict, allowed: set[str], where: str, errors: list[str]) -> None:
    extra = set(obj) - allowed
    missing = allowed - set(obj)
    if extra:
        errors.append(f"{where} contains non-public fields: {sorted(extra)}")
    if missing:
        errors.append(f"{where} missing fields: {sorted(missing)}")


def _scan(value, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in FORBIDDEN_FIELD_FRAGMENTS):
                errors.append(f"{path}.{key}: forbidden public field")
            _scan(child, f"{path}.{key}", errors)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            _scan(child, f"{path}[{i}]", errors)
    elif isinstance(value, str):
        for pattern in FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(value):
                errors.append(f"{path}: forbidden private/account/credential value")


def validate(snapshot: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(snapshot, dict):
        return ["snapshot root must be an object"]

    _exact_keys(snapshot, TOP_KEYS, "snapshot", errors)
    if snapshot.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if snapshot.get("scope") != "ACADEMIC_DOOR_PUBLIC_SAFE":
        errors.append("scope must equal ACADEMIC_DOOR_PUBLIC_SAFE")

    billing = snapshot.get("billing")
    if isinstance(billing, dict):
        _exact_keys(billing, BILLING_KEYS, "billing", errors)
        github = billing.get("github_actions")
        if isinstance(github, dict):
            _exact_keys(github, GITHUB_BILLING_KEYS, "billing.github_actions", errors)
            if github.get("evidence_class") not in {"ACTUAL", "UNKNOWN"}:
                errors.append("billing.github_actions evidence_class invalid")
            if github.get("billable_state") not in BILLABLE_STATE:
                errors.append("billing.github_actions billable_state invalid")
        else:
            errors.append("billing.github_actions must be an object")
    else:
        errors.append("billing must be an object")

    for i, item in enumerate(snapshot.get("costs", [])):
        if not isinstance(item, dict):
            errors.append(f"costs[{i}] must be an object")
            continue
        _exact_keys(item, COST_KEYS, f"costs[{i}]", errors)
        if item.get("evidence_class") != "ESTIMATED":
            errors.append(f"costs[{i}] public costs must be ESTIMATED")

    for i, item in enumerate(snapshot.get("provider_health", [])):
        if not isinstance(item, dict):
            errors.append(f"provider_health[{i}] must be an object")
            continue
        _exact_keys(item, PROVIDER_KEYS, f"provider_health[{i}]", errors)
        if item.get("status") not in PROVIDER_STATUS:
            errors.append(f"provider_health[{i}] status invalid")

    for i, item in enumerate(snapshot.get("services", [])):
        if not isinstance(item, dict):
            errors.append(f"services[{i}] must be an object")
            continue
        _exact_keys(item, SERVICE_KEYS, f"services[{i}]", errors)
        if item.get("lifecycle_state") not in LIFECYCLE:
            errors.append(f"services[{i}] lifecycle_state invalid")
        if item.get("usefulness_status") not in USEFULNESS:
            errors.append(f"services[{i}] usefulness_status invalid")

    actions = snapshot.get("actions")
    if isinstance(actions, dict):
        _exact_keys(actions, ACTIONS_KEYS, "actions", errors)
        seen = set()
        for i, item in enumerate(actions.get("classes", [])):
            if not isinstance(item, dict):
                errors.append(f"actions.classes[{i}] must be an object")
                continue
            _exact_keys(item, ACTION_CLASS_KEYS, f"actions.classes[{i}]", errors)
            klass = item.get("class")
            if klass not in ACTION_CLASSES:
                errors.append(f"actions.classes[{i}] class invalid")
            if klass in seen:
                errors.append(f"actions.classes[{i}] duplicate class")
            seen.add(klass)
    else:
        errors.append("actions must be an object")

    for i, item in enumerate(snapshot.get("alerts", [])):
        if not isinstance(item, dict):
            errors.append(f"alerts[{i}] must be an object")
            continue
        _exact_keys(item, ALERT_KEYS, f"alerts[{i}]", errors)

    if not isinstance(snapshot.get("human_actions"), list):
        errors.append("human_actions must be a list")

    _scan(snapshot, "snapshot", errors)
    return errors


def main(path: str) -> None:
    snapshot = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = validate(snapshot)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate_snapshot.py <snapshot.json>")
    main(sys.argv[1])
