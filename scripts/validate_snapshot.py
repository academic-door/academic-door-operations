#!/usr/bin/env python3
import json
import sys
from pathlib import Path

EVIDENCE = {"ACTUAL", "PROVIDER_REPORTED", "ESTIMATED", "UNKNOWN"}
QUOTA_STATUS = {"HEALTHY", "WATCH", "PRESSURED", "EXHAUSTED", "UNKNOWN"}
ALERT_SEVERITY = {"PARENT_REVIEW"}
ALERT_SCOPE = {"PARENT"}
REQUIRED = {"schema_version", "observed_at", "scope", "costs", "quotas", "credentials", "services", "actions", "human_actions"}
ALERT_REQUIRED = {"id", "severity", "scope", "condition", "evidence_class", "summary", "source"}
FORBIDDEN_KEYS = {"secret_value", "token", "authorization", "password", "private_key", "cookie"}
COST_COVERAGE_STATUS = {
    "ACTUAL_BILLED",
    "ESTIMATED_USAGE",
    "PROVIDER_REPORTED_FREE",
    "PROVIDER_REPORTED_QUOTA",
    "ACCOUNT_BILLING_UNKNOWN",
}
COST_REQUIRED = {
    "id",
    "service",
    "owner",
    "evidence_class",
    "coverage_status",
    "status",
    "evidence_observed_at",
    "next_evidence_route",
    "human_action_required",
}


def _scan_forbidden(value, path="$"):
    errors = []
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                errors.append(f"{path}.{key} contains forbidden secret-bearing field")
            errors.extend(_scan_forbidden(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_scan_forbidden(child, f"{path}[{index}]"))
    return errors



def validate(snapshot):
    errors = []
    missing = REQUIRED - snapshot.keys()
    if missing:
        errors.append(f"missing top-level fields: {sorted(missing)}")
    if snapshot.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if snapshot.get("scope") != "ACADEMIC_DOOR_WIDE_TOPOLOGY_DYNAMIC":
        errors.append("scope must be Academic Door-wide and topology-dynamic")

    for section in ("costs", "quotas", "services", "actions"):
        for i, item in enumerate(snapshot.get(section, [])):
            evidence = item.get("evidence_class")
            if evidence not in EVIDENCE:
                errors.append(f"{section}[{i}] invalid evidence_class: {evidence!r}")
            if evidence == "UNKNOWN" and item.get("amount") == 0:
                errors.append(f"{section}[{i}] UNKNOWN must not be represented as zero")

    for i, item in enumerate(snapshot.get("costs", [])):
        missing_cost = COST_REQUIRED - item.keys()
        if missing_cost:
            errors.append(f"costs[{i}] missing fields: {sorted(missing_cost)}")
        if item.get("coverage_status") not in COST_COVERAGE_STATUS:
            errors.append(f"costs[{i}] invalid coverage_status: {item.get('coverage_status')!r}")
        if not item.get("evidence_observed_at"):
            errors.append(f"costs[{i}] evidence_observed_at must be non-empty")
        if not item.get("next_evidence_route"):
            errors.append(f"costs[{i}] next_evidence_route must be non-empty")
        if not isinstance(item.get("human_action_required"), bool):
            errors.append(f"costs[{i}] human_action_required must be boolean")
        if item.get("human_action_required") and not item.get("human_action_reason"):
            errors.append(f"costs[{i}] human_action_reason required when human_action_required=true")
        if item.get("evidence_class") == "UNKNOWN" and item.get("coverage_status") != "ACCOUNT_BILLING_UNKNOWN":
            errors.append(f"costs[{i}] UNKNOWN cost must use ACCOUNT_BILLING_UNKNOWN coverage_status")

    for i, item in enumerate(snapshot.get("quotas", [])):
        if item.get("status") not in QUOTA_STATUS:
            errors.append(f"quotas[{i}] invalid status: {item.get('status')!r}")

    for i, item in enumerate(snapshot.get("credentials", [])):
        if item.get("secret_value_policy") != "NEVER_COLLECT":
            errors.append(f"credentials[{i}] must set secret_value_policy=NEVER_COLLECT")
        lowered = {str(k).lower() for k in item}
        bad = lowered & FORBIDDEN_KEYS
        if bad:
            errors.append(f"credentials[{i}] contains forbidden secret-bearing field(s): {sorted(bad)}")

    for i, item in enumerate(snapshot.get("alerts", [])):
        missing_alert = ALERT_REQUIRED - item.keys()
        if missing_alert:
            errors.append(f"alerts[{i}] missing fields: {sorted(missing_alert)}")
        if item.get("evidence_class") not in EVIDENCE:
            errors.append(f"alerts[{i}] invalid evidence_class: {item.get('evidence_class')!r}")
        if item.get("severity") not in ALERT_SEVERITY:
            errors.append(f"alerts[{i}] invalid severity: {item.get('severity')!r}")
        if item.get("scope") not in ALERT_SCOPE:
            errors.append(f"alerts[{i}] invalid scope: {item.get('scope')!r}")
        lowered = {str(k).lower() for k in item}
        bad = lowered & FORBIDDEN_KEYS
        if bad:
            errors.append(f"alerts[{i}] contains forbidden secret-bearing field(s): {sorted(bad)}")

    errors.extend(_scan_forbidden(snapshot))
    return errors


def main(path):
    snapshot = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = validate(snapshot)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"valid: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "data/seed-snapshot.json"))
