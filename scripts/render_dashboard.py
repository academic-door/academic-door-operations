#!/usr/bin/env python3
"""Render a self-contained HTML dashboard from the *validated* public snapshot.

No private inputs, network calls, JavaScript, provider credentials, or new hosting.
This is an additional, strictly allowlisted report artifact, not a private ledger.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from scripts.validate_snapshot import validate


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else "UNKNOWN"), quote=True)


def label(value: object) -> str:
    return esc(value).replace("_", " ")


def panel(title: str, body: str, note: str = "") -> str:
    return (
        '<section class="panel"><h2>' + esc(title) + '</h2>'
        + (('<p class="note">' + esc(note) + '</p>') if note else "")
        + body + '</section>'
    )


def table(headers: list[str], rows: list[list[object]]) -> str:
    head = "".join("<th scope=\"col\">" + esc(item) + "</th>" for item in headers)
    items = "".join(
        "<tr>" + "".join("<td>" + esc(value) + "</td>" for value in row) + "</tr>"
        for row in rows
    )
    if not items:
        items = '<tr><td colspan="' + str(len(headers)) + '">No observed data</td></tr>'
    return '<div class="scroll"><table><thead><tr>' + head + '</tr></thead><tbody>' + items + '</tbody></table></div>'


def metric(title: str, value: str, description: str) -> str:
    return (
        '<div class="metric"><div class="metric-label">' + esc(title) + '</div>'
        + '<div class="metric-value">' + esc(value) + '</div>'
        + '<div class="metric-note">' + esc(description) + '</div></div>'
    )


def render(snapshot: dict) -> str:
    errors = validate(snapshot)
    if errors:
        raise ValueError("Public-safe snapshot rejected: " + "; ".join(errors))

    bills = snapshot["billing"]["github_actions"]
    costs = snapshot["costs"]
    actions = snapshot["actions"]
    observed_at = snapshot["observed_at"] or "UNKNOWN"
    billable = bills["billable_state"]
    billed_label = {
        "ZERO": "ZERO",
        "POSITIVE": "POSITIVE",
        "UNKNOWN": "UNKNOWN",
    }[billable]

    estimated = [
        item for item in costs
        if item["service"] == "DeepSeek"
        and item["currency"] == "USD"
        and item["period"] == "CURRENT_MONTH"
    ]
    ai_amount = ("$" + format(estimated[0]["amount"], ".4f")) if estimated else "UNKNOWN"
    classes = {item["class"]: item for item in actions["classes"]}
    public = classes.get("PUBLIC_STANDARD_RUNNER_FREE_ELIGIBLE", {})
    private = classes.get("PRIVATE_INCLUDED_MINUTES", {})

    def minute(item: dict) -> str:
        return (format(item["estimated_wall_minutes"], ",.2f") + " min") if item else "UNKNOWN"

    def state_tag(state: object) -> str:
        raw = str(state)
        cls = ("good" if raw in ("HEALTHY", "ACTIVE") else
               "warn" if raw in ("WATCH", "PRESSURED", "ACTIVE_DEGRADED") else "neutral")
        return '<span class="pill ' + cls + '">' + esc(raw) + '</span>'

    provider_rows = "".join(
        "<tr><td>" + esc(item["provider"]) + "</td><td>" + state_tag(item["status"])
        + "</td><td>" + esc(item["attempts"]) + "</td><td>" + esc(item["available"])
        + "</td><td>" + esc(item["failed"]) + "</td><td>" + esc(item["rate_limited"])
        + "</td><td>" + esc(item["observed_at"]) + "</td></tr>"
        for item in snapshot["provider_health"]
    )
    if not provider_rows:
        provider_rows = '<tr><td colspan="7">No observed provider health</td></tr>'

    actions_table = table(
        ["Scarcity class", "Repos", "Workflows", "Runs", "Failures", "Est. wall minutes"],
        [[item["class"], item["repositories_observed"], item["workflows_with_runs"],
          item["run_count"], item["failure_count"], item["estimated_wall_minutes"]]
         for item in actions["classes"]],
    )
    cost_table = table(
        ["Service", "Observed period", "Amount", "Evidence", "Observed at"],
        [[item["service"], item["period"], format(item["amount"], ".6f") + " " + item["currency"],
          item["evidence_class"], item["observed_at"]]
         for item in costs],
    )
    service_rows = table(
        ["Service", "Owner", "Lifecycle", "Last success"],
        [[item["id"], item["owner"], item["lifecycle_state"], item["last_success_at"]]
         for item in snapshot["services"]],
    )
    alert_table = table(
        ["Condition", "Severity", "Summary"],
        [[item["condition"], item["severity"], item["summary"]]
         for item in snapshot["alerts"]],
    )

    panels = (
        panel("Observed cost evidence", cost_table,
              "Estimated, owner-metered amounts are not provider invoices. Only listed services are covered.")
        + panel("Billing coverage", '<div class="coverage">'
                '<div><strong>GitHub Actions</strong><span>' + esc(billed_label) + ' · ' + esc(bills["evidence_class"]) + '</span></div>'
                '<div><strong>Other account bills</strong><span>UNKNOWN in this public snapshot</span></div>'
                '<div><strong>Project-wide total</strong><span>NOT AVAILABLE — incomplete billing coverage</span></div>'
                '<div><strong>Provider quotas and resets</strong><span>UNKNOWN unless explicitly observed</span></div>'
                '</div>',
                "Never substitute a budget, free-plan label, or an estimate for authoritative billed spend.")
        + panel("GitHub Actions scarcity", actions_table,
                "Last " + str(actions["window_days"]) +
                " days. Wall-clock estimates are not billed runner minutes or remaining included quota.")
        + panel("Public provider health",
                '<div class="scroll"><table><thead><tr><th>Provider</th><th>Status</th>'
                '<th>Attempts</th><th>Available</th><th>Failed</th>'
                '<th>Rate limited</th><th>Observed</th></tr></thead><tbody>'
                + provider_rows + '</tbody></table></div>')
        + panel("Service lifecycle", service_rows)
        + panel("Material alerts", alert_table,
                "No alerts in this snapshot does not establish healthy unobserved accounts.")
    )
    if snapshot["human_actions"]:
        panels += panel("Actions requiring attention",
                        "<ul>" + "".join("<li>" + esc(x) + "</li>" for x in snapshot["human_actions"]) + "</ul>")

    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'">
<title>Academic Door · Operations</title>
<style>
:root {color-scheme:light;--bg:#f4f6fa;--ink:#19273a;--muted:#64748b;--line:#e2e8f0;--blue:#245cbd}
* {box-sizing:border-box} body {margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}
main {max-width:1160px;margin:auto;padding:36px 22px 72px}
header {margin-bottom:25px} .eyebrow {color:var(--blue);font-weight:800;letter-spacing:.13em;text-transform:uppercase;font-size:12px}
h1 {font-size:clamp(28px,4vw,43px);letter-spacing:-.03em;margin:6px 0}
h2 {font-size:19px;letter-spacing:-.02em;margin:0 0 13px}
p {margin:6px 0} .note,.stamp,.metric-note {color:var(--muted);font-size:12px}
.grid {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px;margin:23px 0}
.metric,.panel {background:#fff;border:1px solid var(--line);border-radius:14px}
.metric {padding:20px} .metric-label {font-weight:700;color:#475569}
.metric-value {font-size:clamp(23px,3vw,32px);font-weight:800;letter-spacing:-.04em;margin:7px 0;overflow-wrap:anywhere}
.panel {padding:22px;margin-top:15px;box-shadow:0 1px 3px #152b4010}
.scroll {overflow-x:auto} table {width:100%;border-collapse:collapse;text-align:left;font-size:13px}
th {color:var(--muted);font-weight:700;font-size:11px;text-transform:uppercase;letter-spacing:.04em}
th,td {padding:10px 11px;border-bottom:1px solid var(--line);white-space:nowrap}
tr:last-child td {border:0}
.pill {display:inline-block;border-radius:20px;padding:2px 9px;font-size:11px;font-weight:800;background:#eff3f8}
.pill.good {background:#e7f7ed;color:#156b3a}.pill.warn {background:#fff3de;color:#945d0b}
.coverage>div {display:flex;justify-content:space-between;gap:16px;border-bottom:1px solid var(--line);padding:10px 0}
.coverage>div:last-child {border:0}.coverage span {text-align:right;color:#475569}
footer {font-size:12px;color:var(--muted);padding-top:23px}
@media(max-width:820px){.grid {grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:480px){.grid {grid-template-columns:1fr}.coverage>div {display:block}.coverage span {display:block;text-align:left}}
</style></head><body><main>
<header><div class="eyebrow">Academic Door / Operations</div>
<h1>Cost &amp; quota overview</h1>
<p>A public-safe, read-only operational snapshot. No private account ledger or complete project spend total.</p>
<p class="stamp">Snapshot observed: """ + esc(observed_at) + """ UTC when timestamp is Z · Evidence: live scheduled collector output</p></header>
<div class="grid">""" + (
        metric("Actions billable net", billed_label, str(bills["evidence_class"]) + " · state, not an amount")
        + metric("DeepSeek this month", ai_amount, "ESTIMATED · owner meter")
        + metric("Public Actions", minute(public), "14-day estimated wall time")
        + metric("Private Actions", minute(private), "14-day estimated wall time")
    ) + """</div>
""" + panels + """
<footer>Only allowlisted public aggregate fields are rendered. The page makes no requests,
runs no JavaScript, and requires no new services. Private bill/allowance coverage and
notification delivery require independent acceptance.</footer></main></body></html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    snapshot = json.loads(Path(args.source).read_text(encoding="utf-8"))
    rendered = render(snapshot)
    destination = Path(args.destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
