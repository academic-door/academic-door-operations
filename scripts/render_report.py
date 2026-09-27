#!/usr/bin/env python3
"""Render the public-safe Academic Door Operations report."""

import json
import sys
from pathlib import Path


def _table(headers, rows):
    out = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    out.extend(
        "| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |"
        for row in rows
    )
    return "\n".join(out)


def render(snapshot: dict) -> str:
    github = snapshot["billing"]["github_actions"]
    lines = [
        "# Academic Door Operations — public-safe snapshot",
        "",
        f"Observed at: `{snapshot.get('observed_at') or 'UNKNOWN'}`",
        "",
        "This report is a deliberately sanitized public observability surface. "
        "Private repository identifiers, credential metadata, private account facts, "
        "and private owner pointers are not published here.",
        "",
        "## Public-safe billing",
        "",
        f"- GitHub Actions billable state: **{github['billable_state']}** "
        f"({github['evidence_class']})",
        "",
        "## Public estimated costs",
        "",
    ]

    costs = snapshot.get("costs", [])
    if costs:
        lines.append(
            _table(
                ["Service", "Evidence", "Amount", "Period", "Observed"],
                [
                    [
                        item["service"],
                        item["evidence_class"],
                        f"{item['amount']} {item['currency']}",
                        item["period"],
                        item.get("observed_at") or "UNKNOWN",
                    ]
                    for item in costs
                ],
            )
        )
    else:
        lines.append("- NONE")

    lines.extend(["", "## Public provider health", ""])
    health = snapshot.get("provider_health", [])
    if health:
        lines.append(
            _table(
                [
                    "Provider",
                    "Status",
                    "Attempts",
                    "Available",
                    "Failed",
                    "Rate limited",
                    "Skipped",
                    "Observed",
                ],
                [
                    [
                        item["provider"],
                        item["status"],
                        item["attempts"],
                        item["available"],
                        item["failed"],
                        item["rate_limited"],
                        item["skipped"],
                        item.get("observed_at") or "UNKNOWN",
                    ]
                    for item in health
                ],
            )
        )
    else:
        lines.append("- NONE")

    lines.extend(["", "## Public service lifecycle", ""])
    lines.append(
        _table(
            [
                "Service",
                "Owner",
                "Lifecycle",
                "Usefulness",
                "Status",
                "Last success",
                "Last failure",
            ],
            [
                [
                    item["id"],
                    item["owner"],
                    item["lifecycle_state"],
                    item["usefulness_status"],
                    item["status"],
                    item.get("last_success_at") or "UNKNOWN",
                    item.get("last_failure_at") or "NONE",
                ]
                for item in snapshot.get("services", [])
            ],
        )
    )

    lines.extend(["", "## GitHub Actions aggregate", ""])
    actions = snapshot["actions"]
    lines.append(f"- Observation window: {actions['window_days']} days")
    lines.append(
        _table(
            [
                "Scarcity class",
                "Repositories",
                "Workflows with runs",
                "Runs",
                "Failures",
                "Est. wall min",
            ],
            [
                [
                    item["class"],
                    item["repositories_observed"],
                    item["workflows_with_runs"],
                    item["run_count"],
                    item["failure_count"],
                    item["estimated_wall_minutes"],
                ]
                for item in actions["classes"]
            ],
        )
    )

    lines.extend(["", "## Material alerts", ""])
    alerts = snapshot.get("alerts", [])
    if alerts:
        lines.append(
            _table(
                ["Condition", "Severity", "Summary"],
                [
                    [item["condition"], item["severity"], item["summary"]]
                    for item in alerts
                ],
            )
        )
    else:
        lines.append("- NONE")

    lines.extend(["", "## Human actions", ""])
    human_actions = snapshot.get("human_actions", [])
    if human_actions:
        lines.extend(f"- {item}" for item in human_actions)
    else:
        lines.append("- NONE")

    lines.extend(
        [
            "",
            "> Public-safe contract: raw account, credential, private-repository, "
            "and private-owner evidence is not persisted in this report.",
            "",
        ]
    )
    return "\n".join(lines)


def main(src: str, dst: str | None = None) -> None:
    snapshot = json.loads(Path(src).read_text(encoding="utf-8"))
    output = render(snapshot)
    if dst:
        path = Path(dst)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else "data/seed-snapshot.json"
    destination = sys.argv[2] if len(sys.argv) > 2 else None
    main(source, destination)
