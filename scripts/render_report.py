#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def value(v):
    return "UNKNOWN" if v is None else str(v)


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    out.extend("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |" for row in rows)
    return "\n".join(out)


def _cost_value(item, field):
    raw = item.get(field)
    if raw is None:
        return "UNKNOWN"
    currency = item.get("currency")
    return f"{raw} {currency}" if currency else str(raw)


def _usage_value(item):
    summary = item.get("usage_summary")
    if summary:
        return summary
    quantity = item.get("usage_quantity")
    unit = item.get("usage_unit")
    if quantity is None:
        return "UNKNOWN"
    return f"{quantity} {unit or ''}".strip()


def _money_totals(costs, evidence_class):
    totals = {}
    for item in costs:
        if item.get("evidence_class") != evidence_class:
            continue
        amount = item.get("amount")
        if not isinstance(amount, (int, float)):
            continue
        currency = item.get("currency") or "currency-not-exposed"
        totals[currency] = totals.get(currency, 0.0) + amount
    return totals


def _format_totals(totals):
    if not totals:
        return "NONE"
    return "; ".join(f"{amount} {currency}" for currency, amount in sorted(totals.items()))


def _surface_list(costs, *, evidence_class=None, coverage_status=None):
    values = []
    for item in costs:
        if evidence_class is not None and item.get("evidence_class") != evidence_class:
            continue
        if coverage_status is not None and item.get("coverage_status") != coverage_status:
            continue
        values.append(item.get("service") or item.get("id"))
    return ", ".join(values) if values else "NONE"


def render(snapshot):
    lines = [
        "# Academic Door Operations — latest snapshot",
        "",
        f"Observed at: `{snapshot['observed_at']}`",
        f"Scope: `{snapshot['scope']}`",
        "",
        "## Cost coverage summary",
        "",
        f"- Known ACTUAL billed subtotal: {_format_totals(_money_totals(snapshot['costs'], 'ACTUAL'))}",
        f"- Separately labeled ESTIMATED subtotal: {_format_totals(_money_totals(snapshot['costs'], 'ESTIMATED'))}",
        f"- Provider-reported free/quota surfaces: {_surface_list(snapshot['costs'], evidence_class='PROVIDER_REPORTED')}",
        f"- Account-billing UNKNOWN residuals: {_surface_list(snapshot['costs'], coverage_status='ACCOUNT_BILLING_UNKNOWN')}",
        "- Period-end projection: UNKNOWN unless an accepted provider/account or owner projection method is present; no projection is manufactured.",
        "",
        "## Cost / usage",
        "",
        table(
            ["Service", "Owner", "Evidence", "Coverage", "Net billable", "Gross", "Discount", "Usage / quota", "Evidence observed", "Status"],
            [
                [
                    x["service"],
                    x["owner"],
                    x["evidence_class"],
                    x.get("coverage_status", "UNKNOWN"),
                    _cost_value(x, "amount"),
                    _cost_value(x, "gross_amount"),
                    _cost_value(x, "discount_amount"),
                    x.get("included_quota") or _usage_value(x),
                    x.get("evidence_observed_at") or "UNKNOWN",
                    x["status"],
                ]
                for x in snapshot["costs"]
            ],
        ),
        "",
        "## Account evidence routes",
        "",
        table(
            ["Service", "Current evidence", "Next evidence route", "Human action"],
            [
                [
                    x["service"],
                    x["evidence_class"],
                    x.get("next_evidence_route") or "UNKNOWN",
                    (
                        "REQUIRED — " + (x.get("human_action_reason") or "provider/account activation required")
                        if x.get("human_action_required")
                        else "NONE"
                    ),
                ]
                for x in snapshot["costs"]
                if x.get("coverage_status") == "ACCOUNT_BILLING_UNKNOWN"
            ],
        ),
        "",
        "## Quota / provider pressure",
        "",
        table(
            ["Provider", "Owner", "Evidence", "Remaining / Limit", "Status"],
            [[x["provider"], x["owner"], x["evidence_class"], f"{value(x.get('remaining'))} / {value(x.get('limit'))}", x["status"]] for x in snapshot["quotas"]],
        ),
        "",
        "## Credential metadata",
        "",
        table(
            ["Logical credential", "Provider", "Owner", "Consumers", "Status"],
            [[x["logical_name"], x["provider"], x["owner"], ", ".join(x["consumers"]), x["status"]] for x in snapshot["credentials"]],
        ),
        "",
        "## Infrastructure / recurring services",
        "",
        table(
            ["Service", "Category", "Owner", "Evidence", "Status"],
            [[x["id"], x["category"], x["owner"], x["evidence_class"], x["status"]] for x in snapshot["services"]],
        ),
        "",
        "## GitHub Actions / recurring workloads",
        "",
        table(
            ["Repository", "Class", "Evidence", "Status"],
            [[x["repository"], x["workflow_class"], x["evidence_class"], x["status"]] for x in snapshot["actions"]],
        ),
        "",
        "## Material alerts",
        "",
    ]

    alerts = snapshot.get("alerts", [])
    if alerts:
        lines.append(
            table(
                ["Condition", "Severity", "Evidence", "Summary", "Source"],
                [
                    [
                        item["condition"],
                        item["severity"],
                        item["evidence_class"],
                        item["summary"],
                        item["source"],
                    ]
                    for item in alerts
                ],
            )
        )
    else:
        lines.append("- NONE")

    lines.extend(["", "## Human Principal actions", ""])
    if snapshot["human_actions"]:
        lines.extend(f"- {item}" for item in snapshot["human_actions"])
    else:
        lines.append("- NONE")
    lines.extend(["", "> Secret values are never collected or displayed by this repository.", ""])
    return "\n".join(lines)


def main(src, dst=None):
    snapshot = json.loads(Path(src).read_text(encoding="utf-8"))
    output = render(snapshot)
    if dst:
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        Path(dst).write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else "data/seed-snapshot.json"
    destination = sys.argv[2] if len(sys.argv) > 2 else None
    main(source, destination)
