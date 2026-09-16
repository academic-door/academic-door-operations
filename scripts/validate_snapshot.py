#!/usr/bin/env python3
import json
import sys
from pathlib import Path

EVIDENCE = {"ACTUAL", "PROVIDER_REPORTED", "ESTIMATED", "UNKNOWN"}
QUOTA_STATUS = {"HEALTHY", "WATCH", "PRESSURED", "EXHAUSTED", "UNKNOWN"}
REQUIRED = {"schema_version", "observed_at", "scope", "costs", "quotas", "credentials", "services", "actions", "human_actions"}
FORBIDDEN_KEYS = {"secret_value", "token", "authorization", "password", "private_key", "cookie"}


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
