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


def render(snapshot):
    lines = [
        "# Academic Door Operations — latest snapshot",
        "",
        f"Observed at: `{snapshot['observed_at']}`",
        f"Scope: `{snapshot['scope']}`",
        "",
        "## Cost / usage",
        "",
        table(
            ["Service", "Owner", "Evidence", "Net billable", "Gross", "Discount", "Usage", "Status"],
            [
                [
                    x["service"],
                    x["owner"],
                    x["evidence_class"],
                    _cost_value(x, "amount"),
                    _cost_value(x, "gross_amount"),
                    _cost_value(x, "discount_amount"),
                    _usage_value(x),
                    x["status"],
                ]
                for x in snapshot["costs"]
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
