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


# Human-facing labels only; the validated public-safe JSON contract stays in English.
LABELS = {
    "ZERO": "计费净额为零（ZERO）",
    "POSITIVE": "存在计费（POSITIVE）",
    "UNKNOWN": "未知（UNKNOWN）",
    "ACTUAL": "供应商实测（ACTUAL）",
    "ESTIMATED": "估算（ESTIMATED）",
    "PROVIDER_REPORTED": "供应商报告（PROVIDER_REPORTED）",
    "CURRENT_MONTH": "本月累计",
    "HEALTHY": "正常",
    "WATCH": "需关注",
    "PRESSURED": "额度或服务承压",
    "ACTIVE": "运行中",
    "ACTIVE_DEGRADED": "运行中·性能下降",
    "ACTIVE_UNVERIFIED": "运行中·待核验",
    "RETIRING": "退出中",
    "RETIRED": "已退出",
    "RETIRED_PENDING_ACCOUNT_CLEANUP": "已停用·待账户清理",
    "CONDITIONAL": "有条件使用",
    "PROVEN": "已验证",
    "RETIRE_BY_DEFAULT_PENDING_DAILY_PROVENANCE_GATE": "待来源核验后默认停用",
    "PUBLIC_STANDARD_RUNNER_FREE_ELIGIBLE": "公开仓库·可能适用免费标准运行器",
    "PRIVATE_INCLUDED_MINUTES": "私有仓库·有限赠送分钟",
    "daily-door": "每日之门",
    "journal-system": "期刊体系",
    "jina-reader": "Jina 阅读器",
    "deepseek-inference": "DeepSeek 推理服务",
    "semantic-scholar": "Semantic Scholar",
    "elsevier-metadata": "Elsevier 元数据",
    "crossref": "Crossref",
    "openalex": "OpenAlex",
    "journals-production-monitor": "期刊体系生产监测",
    "GITHUB_ACTIONS_POSITIVE_BILLABLE_NET": "GitHub Actions 本期计费为正",
    "PARENT_REVIEW": "需总控复核",
    "GitHub Actions current-period billable net is positive.": "GitHub Actions 本期净计费金额为正，需复核。",
}


def display(value: object) -> str:
    """HTML-escape public fields after translating known enum labels."""
    return esc(LABELS.get("UNKNOWN" if value is None else str(value), "UNKNOWN" if value is None else value))


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else "UNKNOWN"), quote=True)


def label(value: object) -> str:
    return display(value).replace("_", " ")


def panel(title: str, body: str, note: str = "") -> str:
    return (
        '<section class="panel"><h2>' + esc(title) + '</h2>'
        + (('<p class="note">' + esc(note) + '</p>') if note else "")
        + body + '</section>'
    )


def table(headers: list[str], rows: list[list[object]]) -> str:
    head = "".join("<th scope=\"col\">" + esc(item) + "</th>" for item in headers)
    items = "".join(
        "<tr>" + "".join("<td>" + display(value) + "</td>" for value in row) + "</tr>"
        for row in rows
    )
    if not items:
        items = '<tr><td colspan="' + str(len(headers)) + '">暂无观测数据</td></tr>'
    return '<div class="scroll"><table><thead><tr>' + head + '</tr></thead><tbody>' + items + '</tbody></table></div>'


def metric(title: str, value: str, description: str) -> str:
    return (
        '<div class="metric"><div class="metric-label">' + esc(title) + '</div>'
        + '<div class="metric-value">' + display(value) + '</div>'
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
        return (format(item["estimated_wall_minutes"], ",.2f") + " 分钟") if item else "UNKNOWN"

    def state_tag(state: object) -> str:
        raw = str(state)
        cls = ("good" if raw in ("HEALTHY", "ACTIVE") else
               "warn" if raw in ("WATCH", "PRESSURED", "ACTIVE_DEGRADED") else "neutral")
        return '<span class="pill ' + cls + '">' + display(raw) + '</span>'

    provider_rows = "".join(
        "<tr><td>" + esc(item["provider"]) + "</td><td>" + state_tag(item["status"])
        + "</td><td>" + esc(item["attempts"]) + "</td><td>" + esc(item["available"])
        + "</td><td>" + esc(item["failed"]) + "</td><td>" + esc(item["rate_limited"])
        + "</td><td>" + esc(item["observed_at"]) + "</td></tr>"
        for item in snapshot["provider_health"]
    )
    if not provider_rows:
        provider_rows = '<tr><td colspan="7">暂无供应商健康观测数据</td></tr>'

    actions_table = table(
        ["资源类别", "仓库数", "工作流数", "运行次数", "失败次数", "估算运行分钟"],
        [[item["class"], item["repositories_observed"], item["workflows_with_runs"],
          item["run_count"], item["failure_count"], item["estimated_wall_minutes"]]
         for item in actions["classes"]],
    )
    cost_table = table(
        ["服务", "统计周期", "金额", "证据类型", "观测时间"],
        [[item["service"], item["period"], format(item["amount"], ".6f") + " " + item["currency"],
          item["evidence_class"], item["observed_at"]]
         for item in costs],
    )
    service_rows = table(
        ["服务", "所属产品", "生命周期", "最近成功时间"],
        [[item["id"], item["owner"], item["lifecycle_state"], item["last_success_at"]]
         for item in snapshot["services"]],
    )
    alert_table = table(
        ["异常类型", "级别", "说明"],
        [[item["condition"], item["severity"], item["summary"]]
         for item in snapshot["alerts"]],
    )

    panels = (
        panel("费用观测记录", cost_table,
              "来自业务方的费用估算不等于供应商账单；这里只覆盖已列出的服务。")
        + panel("账单覆盖情况", '<div class="coverage">'
                '<div><strong>GitHub Actions</strong><span>' + display(billed_label) + ' · ' + display(bills["evidence_class"]) + '</span></div>'
                '<div><strong>其他平台账单</strong><span>当前公开快照暂无权威数据（UNKNOWN）</span></div>'
                '<div><strong>项目费用总计</strong><span>暂无法计算：账单覆盖不完整</span></div>'
                '<div><strong>供应商额度与重置时间</strong><span>尚无已验证的额度和重置数据</span></div>'
                '</div>',
                "不能用预算上限、免费套餐标记或估算金额代替实际计费账单。")
        + panel("GitHub Actions 资源占用", actions_table,
                "近 " + str(actions["window_days"]) +
                " 天。运行耗时估算不是实际计费分钟，也不代表剩余免费额度。")
        + panel("公开供应商服务状态",
                '<div class="scroll"><table><thead><tr><th>供应商</th><th>状态</th>'
                '<th>尝试次数</th><th>有效响应</th><th>失败</th>'
                '<th>限流次数</th><th>观测时间</th></tr></thead><tbody>'
                + provider_rows + '</tbody></table></div>')
        + panel("服务生命周期", service_rows)
        + panel("重要异常提醒", alert_table,
                "当前没有公开异常记录，不代表未监测账户的状态正常。")
    )
    if snapshot["human_actions"]:
        panels += panel("需处理事项",
                        "<ul>" + "".join("<li>" + esc(x) + "</li>" for x in snapshot["human_actions"]) + "</ul>")

    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'">
<title>Academic Door · 运营观测</title>
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
<header><div class="eyebrow">Academic Door / 运营观测</div>
<h1>成本与额度总览</h1>
<p>只读、公开安全的运行快照；不包含私有账号账本，也不能代表项目完整成本。</p>
<p class="stamp">数据观测时间：""" + esc(observed_at) + """  · 来源：每日定时采集（时区见时间戳）</p></header>
<div class="grid">""" + (
        metric("Actions 实际计费状态", billed_label, LABELS.get(bills["evidence_class"], bills["evidence_class"]) + " · 仅为状态，不是具体金额")
        + metric("DeepSeek 本月费用", ai_amount, "业务方计量估算（非账单）")
        + metric("公开仓库 Actions", minute(public), "近 14 天估算运行耗时")
        + metric("私有仓库 Actions", minute(private), "近 14 天估算运行耗时")
    ) + """</div>
""" + panels + """
<footer>本页仅展示经过白名单验证的公开汇总数据；页面不发送网络请求，
不运行 JavaScript，也无需新增服务。私有账单、额度覆盖与
通知送达需要独立验收。</footer></main></body></html>
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
