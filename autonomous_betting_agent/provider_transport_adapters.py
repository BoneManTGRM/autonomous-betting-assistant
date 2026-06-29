from __future__ import annotations

from typing import Any, Callable, Mapping

HttpGet = Callable[[str, Mapping[str, Any], Mapping[str, str]], Mapping[str, Any]]

SPORTSDATAIO_BASE = "https://api.sportsdata.io/v3"
THE_ODDS_API_BASE = "https://api.the-odds-api.com/v4"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _safe_headers(api_key: str | None = None, header_name: str = "Ocp-Apim-Subscription-Key") -> dict[str, str]:
    key = _text(api_key)
    return {header_name: key} if key else {}


def redact_request_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    safe = dict(plan)
    headers = dict(safe.get("headers") or {})
    safe["headers"] = {key: "***" for key in headers}
    params = dict(safe.get("params") or {})
    for key in list(params):
        if "key" in key.lower() or "token" in key.lower() or "secret" in key.lower():
            params[key] = "***"
    safe["params"] = params
    return safe


def build_sportsdataio_confirmation_request(request: Mapping[str, Any], api_key: str | None = None) -> dict[str, Any]:
    sport = _text(request.get("sport") or "general").lower()
    return {
        "provider": "sportsdataio",
        "url": f"{SPORTSDATAIO_BASE}/{sport}/scores/json/GamesByDate/{_text(request.get('event_start_utc'))[:10]}",
        "params": {
            "event": _text(request.get("event")),
            "market_type": _text(request.get("market_type")),
            "selection": _text(request.get("selection")),
        },
        "headers": _safe_headers(api_key),
    }


def build_the_odds_value_request(request: Mapping[str, Any], api_key: str | None = None) -> dict[str, Any]:
    sport = _text(request.get("sport") or "upcoming").lower()
    return {
        "provider": "the_odds_api",
        "url": f"{THE_ODDS_API_BASE}/sports/{sport}/odds",
        "params": {
            "apiKey": _text(api_key),
            "regions": "us",
            "markets": _text(request.get("market_type") or "h2h"),
            "event": _text(request.get("event")),
            "selection": _text(request.get("selection")),
        },
        "headers": {},
    }


def normalize_confirmation_response(request: Mapping[str, Any], response: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "sport": _text(request.get("sport")),
        "event": _text(request.get("event")),
        "event_start_utc": _text(request.get("event_start_utc")),
        "market_type": _text(request.get("market_type")),
        "selection": _text(request.get("selection")),
        "provider": _text(response.get("provider") or "sportsdataio"),
        "primary_value": response.get("primary_value", response.get("home_score")),
        "secondary_value": response.get("secondary_value", response.get("away_score")),
        "confidence": max(0.0, min(1.0, _float(response.get("confidence"), 1.0))),
        "confirmed_at_utc": _text(response.get("confirmed_at_utc") or response.get("checked_at_utc")),
    }


def normalize_value_response(request: Mapping[str, Any], response: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "sport": _text(request.get("sport")),
        "event": _text(request.get("event")),
        "event_start_utc": _text(request.get("event_start_utc")),
        "market_type": _text(request.get("market_type")),
        "selection": _text(request.get("selection")),
        "provider": _text(response.get("provider") or "the_odds_api"),
        "original_value": response.get("original_value", response.get("locked_value")),
        "latest_value": response.get("latest_value", response.get("closing_value")),
    }


def make_sportsdataio_confirmation_transport(api_key: str | None, http_get: HttpGet):
    def transport(request: Mapping[str, Any]) -> dict[str, Any]:
        plan = build_sportsdataio_confirmation_request(request, api_key)
        response = http_get(plan["url"], plan["params"], plan["headers"])
        return normalize_confirmation_response(request, response)
    return transport


def make_the_odds_value_transport(api_key: str | None, http_get: HttpGet):
    def transport(request: Mapping[str, Any]) -> dict[str, Any]:
        plan = build_the_odds_value_request(request, api_key)
        response = http_get(plan["url"], plan["params"], plan["headers"])
        return normalize_value_response(request, response)
    return transport
