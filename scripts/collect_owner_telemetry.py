#!/usr/bin/env python3
"""Collect bounded, non-secret owner telemetry from public Academic Door surfaces.

The collector intentionally fetches only public, fixed Academic Door evidence URLs and
normalizes them through explicit whitelists before persistence. Raw payloads are never
written to the Operations repository or workflow artifacts.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MAX_SOURCE_BYTES = 2 * 1024 * 1024
SOURCE_URLS = {
    "daily_provider_health": "https://raw.githubusercontent.com/academic-door/econ-paper-monitor/main/data/metadata_provider_health.json",
    "daily_provider_usage": "https://raw.githubusercontent.com/academic-door/econ-paper-monitor/main/data/semantic_scholar_usage.json",
    "daily_ai_cost": "https://raw.githubusercontent.com/academic-door/econ-paper-monitor/main/data/ai_cost_usage.json",
    "journals_monitoring": "https://raw.githubusercontent.com/academic-door/journals/data/public/api/v1/monitoring.json",
}

_COUNT_FIELDS = (
    "attempts",
    "available",
    "empty",
    "failed",
    "http_error",
    "not_found",
    "provider_error",
    "rate_limited",
    "runs",
    "skipped",
)
_CONTROL_FIELDS = (
    "circuit_open",
    "client_target_rps",
    "min_interval_seconds",
    "endpoint_class",
    "workload_class",
    "provider_rate_limit_rps",
    "keyed_max_retries",
    "recent_attempts",
    "recent_rate_limited",
    "recent_rate_limited_ratio",
)
_JOURNAL_SUMMARY_FIELDS = (
    "configured_journals",
    "unchanged",
    "candidates",
    "confirmed_updates",
    "warnings",
    "awaiting_official",
    "failed",
)


def _counts(payload: dict) -> dict:
    return {key: payload.get(key, 0) for key in _COUNT_FIELDS if key in payload}


def normalize_daily_provider_health(payload: dict) -> dict:
    latest = payload.get("latest") or {}
    providers = {}
    for name, source in (latest.get("providers") or {}).items():
        bounded = _counts(source)
        for field in ("api_key_configured", "inst_token_configured"):
            if field in source:
                bounded[field] = bool(source.get(field))
        control = source.get("control") or {}
        safe_control = {field: control.get(field) for field in _CONTROL_FIELDS if field in control}
        if safe_control:
            bounded["control"] = safe_control
        providers[name] = bounded
    return {
        "observed_at": latest.get("checked_at"),
        "providers": providers,
    }


def normalize_daily_provider_usage(payload: dict) -> dict:
    providers = {}
    for name, source in (payload.get("providers") or {}).items():
        bounded = {
            "last_used_at": source.get("last_used_at"),
            "api_key_configured": bool(source.get("api_key_configured")),
            "total": _counts(source.get("total") or {}),
        }
        if "inst_token_configured" in source:
            bounded["inst_token_configured"] = bool(source.get("inst_token_configured"))
        providers[name] = bounded
    keepalive_at = payload.get("last_keepalive_at")
    return {
        "observed_at": payload.get("updated_at"),
        "providers": providers,
        "synthetic_keepalive_observed": bool(keepalive_at),
        "synthetic_keepalive_reason": payload.get("last_keepalive_reason") if keepalive_at else None,
    }


def normalize_daily_ai_cost(payload: dict) -> dict:
    updated_at = payload.get("updated_at") or ""
    month_prefix = updated_at[:7] if len(updated_at) >= 7 else None
    current_month = 0.0
    if month_prefix:
        for day, tasks in (payload.get("days") or {}).items():
            if not day.startswith(month_prefix + "-"):
                continue
            for task in (tasks or {}).values():
                try:
                    current_month += float((task or {}).get("estimated_cost_usd") or 0)
                except (TypeError, ValueError):
                    continue
    rolling = (payload.get("rolling_30d") or {}).get("total") or {}
    return {
        "observed_at": payload.get("updated_at"),
        "provider": "DeepSeek",
        "currency": payload.get("currency") or "USD",
        "current_month_estimated_cost": round(current_month, 12),
        "rolling_30d_estimated_cost": rolling.get("estimated_cost_usd"),
        "rolling_30d_requests": rolling.get("requests"),
        "pricing_source": payload.get("pricing_source"),
        "pricing_version": payload.get("pricing_version"),
    }


def normalize_journals_monitoring(payload: dict) -> dict:
    summary = payload.get("summary") or {}
    return {
        "observed_at": payload.get("updated_at"),
        "status": payload.get("status"),
        "schedule": payload.get("schedule"),
        "summary": {field: summary.get(field, 0) for field in _JOURNAL_SUMMARY_FIELDS if field in summary},
    }


def fetch_json(url: str, *, timeout_seconds: int = 20) -> dict:
    request = Request(url, headers={"User-Agent": "academic-door-operations/1"})
    with urlopen(request, timeout=timeout_seconds) as response:
        length = response.headers.get("Content-Length")
        if length and int(length) > MAX_SOURCE_BYTES:
            raise ValueError("source exceeds bounded size limit")
        raw = response.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("source exceeds bounded size limit")
    decoded = json.loads(raw.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("source root must be a JSON object")
    return decoded


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, URLError):
        return f"URL error: {str(exc.reason)[:120]}"
    return f"{type(exc).__name__}: {str(exc)[:160]}"


def collect_owner_telemetry(fetcher=fetch_json) -> dict:
    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    result = {
        "schema_version": 1,
        "observed_at": observed_at,
        "gaps": [],
    }
    normalizers = {
        "daily_provider_health": normalize_daily_provider_health,
        "daily_provider_usage": normalize_daily_provider_usage,
        "daily_ai_cost": normalize_daily_ai_cost,
        "journals_monitoring": normalize_journals_monitoring,
    }
    for source_id, url in SOURCE_URLS.items():
        try:
            result[source_id] = normalizers[source_id](fetcher(url))
        except Exception as exc:  # observability must fail open per source
            result["gaps"].append({"source": source_id, "error": _safe_error(exc)})
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/owner-latest.json")
    args = parser.parse_args()
    payload = collect_owner_telemetry()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
