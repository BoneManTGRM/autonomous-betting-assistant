from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.provider_transport_adapters import (
    build_sportsdataio_confirmation_request,
    build_the_odds_value_request,
    redact_request_plan,
)

SCHEMA_VERSION = "api_smoke_test_v1"
SUPPORTED_PROVIDERS = ("the_odds_api", "sportsdataio", "weatherapi")
KEY_ALIASES = {
    "the_odds_api": ("ODDS_API_KEY", "THE_ODDS_API_KEY"),
    "sportsdataio": ("SPORTSDATAIO_API_KEY", "SPORTS_DATA_IO_API_KEY"),
    "weatherapi": ("WEATHERAPI_KEY", "WEATHER_API_KEY"),
}
READY = "API READY"
REVIEW = "REVIEW REQUIRED"
MISSING = "MISSING KEYS"
EMPTY = "NO SAMPLE RESPONSE"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def parse_json_payload(text: str | None) -> Any:
    raw = _text(text)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return {"parse_error": "invalid_json"}


def secret_key_status(secrets: Mapping[str, Any] | None, provider: str) -> dict[str, Any]:
    source = dict(secrets or {})
    aliases = KEY_ALIASES.get(provider, ())
    matched_name = ""
    present = False
    for name in aliases:
        value = _text(source.get(name))
        if value:
            matched_name = name
            present = True
            break
    return {
        "provider": provider,
        "present": present,
        "matched_name": matched_name,
        "display_value": "loaded" if present else "missing",
    }


def build_key_readiness_report(secrets: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    return [secret_key_status(secrets, provider) for provider in SUPPORTED_PROVIDERS]


def build_sample_request() -> dict[str, Any]:
    return {
        "sport": "tennis",
        "event": "sample_event",
        "event_start_utc": _now()[:10],
        "market_type": "moneyline",
        "selection": "sample_selection",
    }


def build_redacted_request_plans(secrets: Mapping[str, Any] | None, sample_request: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    source = dict(secrets or {})
    request = dict(sample_request or build_sample_request())
    odds_key = _text(source.get("ODDS_API_KEY") or source.get("THE_ODDS_API_KEY"))
    sportsdata_key = _text(source.get("SPORTSDATAIO_API_KEY") or source.get("SPORTS_DATA_IO_API_KEY"))
    plans = [
        redact_request_plan(build_the_odds_value_request(request, odds_key)),
        redact_request_plan(build_sportsdataio_confirmation_request(request, sportsdata_key)),
        {
            "provider": "weatherapi",
            "url": "https://api.weatherapi.com/v1/current.json",
            "params": {"key": "***" if _text(source.get("WEATHERAPI_KEY") or source.get("WEATHER_API_KEY")) else "", "q": "sample_location"},
            "headers": {},
        },
    ]
    return plans


def _iter_records(payload: Any) -> list[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, Mapping):
        for key in ("data", "events", "games", "markets", "bookmakers", "response", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return [payload]
    return []


def _contains_key(payload: Any, names: Sequence[str]) -> bool:
    lower_names = {name.lower() for name in names}
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if str(key).lower() in lower_names:
                return True
            if _contains_key(value, names):
                return True
    elif isinstance(payload, list):
        return any(_contains_key(item, names) for item in payload)
    return False


def analyze_provider_payload(provider: str, payload: Any) -> dict[str, Any]:
    records = _iter_records(payload)
    parse_error = isinstance(payload, Mapping) and payload.get("parse_error") == "invalid_json"
    has_error = parse_error or _contains_key(payload, ("error", "errors", "message"))
    has_event = _contains_key(payload, ("event", "event_name", "home_team", "away_team", "name", "teams"))
    has_score = _contains_key(payload, ("home_score", "away_score", "score", "final_score"))
    has_odds = _contains_key(payload, ("odds", "price", "decimal_odds", "bookmakers", "markets"))
    has_time = _contains_key(payload, ("commence_time", "event_start_utc", "last_update", "timestamp", "updated"))
    if payload is None:
        status = EMPTY
    elif has_error:
        status = REVIEW
    elif provider == "the_odds_api" and has_event and has_odds:
        status = READY
    elif provider == "sportsdataio" and has_event and (has_score or records):
        status = READY
    elif provider == "weatherapi" and records:
        status = READY
    else:
        status = REVIEW
    return {
        "provider": provider,
        "status": status,
        "record_count": len(records),
        "has_event_fields": has_event,
        "has_score_fields": has_score,
        "has_odds_fields": has_odds,
        "has_timestamp_fields": has_time,
        "has_error_fields": bool(has_error),
        "parse_error": bool(parse_error),
    }


def build_api_smoke_report(
    workspace_id: str | None = None,
    secrets: Mapping[str, Any] | None = None,
    sample_payloads: Mapping[str, Any] | None = None,
    sample_request: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payloads = dict(sample_payloads or {})
    key_rows = build_key_readiness_report(secrets or {})
    analyses = [analyze_provider_payload(provider, payloads.get(provider)) for provider in SUPPORTED_PROVIDERS]
    missing_keys = [row for row in key_rows if not row["present"]]
    ready_payloads = [row for row in analyses if row["status"] == READY]
    review_payloads = [row for row in analyses if row["status"] == REVIEW]
    no_sample = [row for row in analyses if row["status"] == EMPTY]
    if missing_keys:
        status = MISSING
    elif review_payloads:
        status = REVIEW
    elif no_sample:
        status = EMPTY
    else:
        status = READY
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "status": status,
        "ready_provider_count": len(ready_payloads),
        "review_provider_count": len(review_payloads),
        "missing_key_count": len(missing_keys),
        "no_sample_count": len(no_sample),
        "key_readiness": key_rows,
        "request_plans": build_redacted_request_plans(secrets or {}, sample_request),
        "payload_analysis": analyses,
        "preview_only": True,
        "proof_rows_changed": 0,
        "errors": [f"missing key: {row['provider']}" for row in missing_keys],
        "warnings": [f"review payload: {row['provider']}" for row in review_payloads] + [f"no sample: {row['provider']}" for row in no_sample],
    }


def export_api_smoke_report_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)
