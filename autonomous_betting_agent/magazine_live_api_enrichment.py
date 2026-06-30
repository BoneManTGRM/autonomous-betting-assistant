from __future__ import annotations

import builtins
import hashlib
import importlib
import json
import os
import re
import time
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.request import Request, urlopen

ENRICHMENT_VERSION = "live_api_enrichment_v12_final_report_truth"
_TIMEOUT_SECONDS = 7.0
_CACHE: dict[tuple[str, str], Any] = {}
_RUN_COUNTER = 0
_SPANISH_TR_MARKER = "_aba_spanish_report_tr_v12"
_RELOAD_MARKER = "_aba_magazine_reload_patch_v12"

API_SECRET_DEFS = {
    "Odds API": ("ODDS_API_KEY", "THE_ODDS_API_KEY"),
    "SportsDataIO": ("SPORTSDATAIO_API_KEY", "SPORTS_DATA_IO_API_KEY", "SPORTSDATA_API_KEY"),
    "WeatherAPI": ("WEATHERAPI_KEY", "WEATHER_API_KEY"),
    "API-Football": ("API_FOOTBALL_KEY", "APIFOOTBALL_KEY"),
    "NewsAPI": ("NEWSAPI_KEY", "NEWS_API_KEY"),
    "Perplexity": ("PERPLEXITY_API_KEY", "PPLX_API_KEY"),
}

FALLBACK_TOKENS = (
    "context unavailable",
    "no sdio event id",
    "sdio checked; no provider event id",
    "api-fb lookup checked",
    "no fixture match",
    "no match returned",
    "show hn: simple news aggregator",
    "simple news aggregator",
    "uploaded/cached row",
    "uploaded row",
    "no live",
    "data not returned for this event",
    "player data not returned for this event",
    "not returned by active sources",
    "not returned for this soccer event",
    "sin id de evento sdio",
    "sin coincidencia",
    "fila cargada/en caché",
    "api key missing",
    "payment required",
)


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict"):
        data = value.to_dict()
        return dict(data) if isinstance(data, Mapping) else {}
    return dict(getattr(value, "__dict__", {}) or {})


def _bad(value: Any) -> bool:
    return value is None or str(value).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


def _useful(value: Any) -> bool:
    if _bad(value):
        return False
    text = str(value).strip().lower()
    if text in {"false", "0", "no", "not available", "unavailable", "data unavailable", "none available"}:
        return False
    return not any(token in text for token in FALLBACK_TOKENS)


def _get(row: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if not _bad(value):
            return str(value).strip()
    return default


def _secret(*names: str) -> str:
    getter = getattr(builtins, "get_secret", None)
    if callable(getter):
        try:
            value = str(getter(*names) or "").strip()
            if value:
                return value
        except Exception:
            pass
    try:
        import streamlit as st  # type: ignore
        for name in names:
            try:
                value = str(st.secrets.get(name, "") or "").strip()
            except Exception:
                value = ""
            if value:
                return value
    except Exception:
        pass
    for name in names:
        value = str(os.getenv(name, "") or "").strip()
        if value:
            return value
    return ""


def _mask(value: str) -> str:
    text = str(value or "")
    if not text:
        return ""
    return "***" if len(text) <= 8 else f"{text[:4]}...{text[-4:]}"


def check_api_health(mask_secrets: bool = True) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for name, keys in API_SECRET_DEFS.items():
        key = _secret(*keys)
        out[name] = {"status": "CONFIGURED" if key else "API_KEY_MISSING", "key": _mask(key) if mask_secrets and key else ("present" if key else "")}
    return out


def _hash_payload(value: Any) -> str:
    try:
        text = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
    except Exception:
        text = str(value)
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _new_run_meta(rows: list[Any] | tuple[Any, ...]) -> tuple[str, str]:
    global _RUN_COUNTER
    _RUN_COUNTER += 1
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return f"aba_mag_{int(time.time())}_{_RUN_COUNTER}_{_hash_payload(rows)}", ts


def _normalize(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\s+(?:at|vs|v|@)\s+", " vs ", text)
    text = re.sub(r"[^a-z0-9áéíóúüñ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _split_teams(row: Mapping[str, Any]) -> tuple[str, str]:
    away = _get(row, "away_team", "team_a", "team1")
    home = _get(row, "home_team", "team_b", "team2")
    if away and home:
        return away, home
    event = _get(row, "public_event", "event", "event_name", "matchup", "game")
    for sep in (" at ", " vs ", " VS ", " v ", " @ "):
        if sep in event:
            left, right = event.split(sep, 1)
            return left.strip(), right.strip()
    return _get(row, "team", default=""), _get(row, "opponent", default="")


def _event_key(row: Mapping[str, Any]) -> str:
    away, home = _split_teams(row)
    event = _get(row, "public_event", "event", "event_name", "matchup") or f"{away} vs {home}".strip()
    return "|".join(part for part in (_normalize(event), _normalize(_get(row, "sport", "league")), _get(row, "event_date", "start_time", "commence_time")[:10]) if part) or "unknown_event"


def _safe_float(value: Any) -> float | None:
    if _bad(value):
        return None
    try:
        return float(str(value).replace("%", "").replace(",", ""))
    except Exception:
        return None


def _probability(row: Mapping[str, Any]) -> tuple[float | None, str]:
    for key in ("learned_model_probability", "model_probability_clean", "model_probability", "final_probability", "probability", "confidence"):
        value = _safe_float(row.get(key))
        if value is not None:
            value = value / 100 if abs(value) > 1 else value
            if 0 <= value <= 1:
                return value, key
    return None, "MISSING"


def _decimal_odds(row: Mapping[str, Any]) -> tuple[float | None, str]:
    for key in ("decimal_odds", "decimal_price", "best_price", "average_price", "avg_price", "odds_decimal", "odds_at_pick"):
        value = _safe_float(row.get(key))
        if value is not None and value > 1:
            return value, key
    american = _safe_float(row.get("american_odds") or row.get("odds_american") or row.get("odds"))
    if american is not None and abs(american) >= 100:
        dec = (american / 100 + 1) if american > 0 else (100 / abs(american) + 1)
        return dec, "american_odds"
    return None, "MISSING"


def _american_from_decimal(decimal: float | None) -> str:
    if decimal is None:
        return ""
    if decimal >= 2:
        return f"+{round((decimal - 1) * 100):.0f}"
    return f"-{round(100 / max(decimal - 1, 0.001)):.0f}"


def _request_post_json(url: str, payload: Mapping[str, Any], *, headers: Mapping[str, str] | None = None, cache_key: tuple[str, str] | None = None) -> Any:
    key = cache_key or ("post", url + _hash_payload(payload))
    if key in _CACHE:
        return _CACHE[key]
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, method="POST", headers={"User-Agent": "ABA-Signal-Pro/1.0", "Content-Type": "application/json", **dict(headers or {})})
    try:
        with urlopen(req, timeout=_TIMEOUT_SECONDS) as response:  # noqa: S310 - controlled API URL only
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        data = {"_error": exc.__class__.__name__}
    _CACHE[key] = data
    return data


def _enrich_perplexity(row: dict[str, Any]) -> None:
    existing = _get(row, "perplexity_context", "perplexity_summary", "perplexity_news_context")
    if _useful(existing):
        row["perplexity_status"] = "LIVE"
        row["context_source"] = "Perplexity"
        row["perplexity_context"] = existing
        return
    key = _secret(*API_SECRET_DEFS["Perplexity"])
    if not key:
        row["perplexity_status"] = "API_KEY_MISSING"
        row["perplexity_failure_reason"] = "Perplexity key missing"
        return
    event = _get(row, "public_event", "event", "event_name", "matchup")
    pick = _get(row, "public_pick", "prediction", "pick", "selection", "recommended_action")
    if not event and not pick:
        row["perplexity_status"] = "NO_QUERY"
        row["perplexity_failure_reason"] = "No event/pick query available"
        return
    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "Write concise sports betting research context. Do not invent data; say unavailable if unverified."},
            {"role": "user", "content": f"Event: {event}. Pick: {pick}. Sport/league: {_get(row, 'sport', 'league')}. Give one short context sentence."},
        ],
        "max_tokens": 90,
        "temperature": 0.1,
    }
    data = _request_post_json("https://api.perplexity.ai/chat/completions", payload, headers={"Authorization": f"Bearer {key}"}, cache_key=("perplexity", _event_key(row)))
    if isinstance(data, Mapping) and data.get("_error"):
        row["perplexity_status"] = "API_ERROR"
        row["perplexity_failure_reason"] = str(data.get("_error"))
        return
    content = ""
    choices = data.get("choices") if isinstance(data, Mapping) else None
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") if isinstance(choices[0], Mapping) else None
        if isinstance(msg, Mapping):
            content = str(msg.get("content") or "").strip()
    if _useful(content):
        row["perplexity_status"] = "LIVE"
        row["perplexity_context"] = re.sub(r"\s+", " ", content).strip()[:240]
        row["context_source"] = "Perplexity"
    else:
        row["perplexity_status"] = "NO_LIVE_CONTEXT_RETURNED"
        row["perplexity_failure_reason"] = "Perplexity returned no usable context for this row"


def resolve_magazine_context(row: Mapping[str, Any]) -> tuple[str, str]:
    for source, key in (
        ("Perplexity", "perplexity_context"),
        ("Perplexity", "perplexity_summary"),
        ("NewsAPI", "newsapi_summary"),
        ("NewsAPI", "news_summary"),
        ("API-Football", "api_football_summary"),
        ("SportsDataIO", "sportsdataio_context"),
        ("WeatherAPI", "weather_summary"),
        ("Input", "sports_context_summary"),
        ("Input", "preview_summary"),
        ("Input", "game_summary"),
        ("Input", "short_reason"),
    ):
        value = row.get(key)
        if _useful(value):
            return source, str(value).strip()
    reasons = [str(row.get(k)) for k in ("perplexity_failure_reason", "news_failure_reason", "api_football_failure_reason", "sportsdataio_failure_reason", "weather_failure_reason", "odds_failure_reason") if row.get(k)]
    reason = "; ".join(reasons[:3]) or "no live context returned by configured sources"
    return "EMPTY_WITH_REASON", f"Context unavailable because: {reason}."


def _set_if_empty(row: dict[str, Any], key: str, value: str) -> None:
    if value and not _useful(row.get(key)):
        row[key] = value


def _apply_final_fields(row: dict[str, Any], report_run_id: str, refresh_time: str) -> dict[str, Any]:
    row["event_key"] = row.get("event_key") or _event_key(row)
    row["duplicate_group_id"] = row.get("duplicate_group_id") or row["event_key"]
    row["row_id"] = row.get("row_id") or _hash_payload(row)
    row["raw_input_hash"] = row.get("raw_input_hash") or _hash_payload({k: v for k, v in row.items() if not str(k).startswith("_")})
    row["enrichment_input_hash"] = row.get("enrichment_input_hash") or _hash_payload({"event_key": row["event_key"], "api_health": check_api_health(True)})
    row["report_source"] = "final_enriched_picks_df"
    row["report_run_id"] = report_run_id
    row["last_api_refresh_time"] = refresh_time
    row["cache_status"] = row.get("cache_status") or "LIVE_REFRESH"
    row["data_freshness_status"] = row.get("data_freshness_status") or "CURRENT_REPORT_RUN"
    row["enrichment_status"] = row.get("enrichment_status") or "FINAL_ENRICHED"

    prob, prob_source = _probability(row)
    dec, dec_source = _decimal_odds(row)
    row["model_probability_source"] = row.get("model_probability_source") or prob_source
    row["confidence_source"] = row.get("confidence_source") or prob_source
    row["confidence_status"] = "LIVE_OR_INPUT" if prob is not None else "MISSING"
    if prob is not None:
        row["model_probability"] = prob
    live_marker = str(row.get("odds_status") or row.get("odds_source") or row.get("odds_api_status") or "").strip().lower()
    live_odds = live_marker in {"live", "live_api", "odds api", "the odds api"}
    if dec is None:
        row["odds_status"] = "MISSING"
        row["odds_source"] = "MISSING"
        row["odds_failure_reason"] = f"No usable decimal odds field found; checked {dec_source}."
        row["ev_status"] = "UNVERIFIED_ODDS_MISSING"
    else:
        row["decimal_odds"] = dec
        row["decimal_price"] = dec
        row["american_odds"] = row.get("american_odds") or row.get("odds_american") or _american_from_decimal(dec)
        row["raw_implied_probability"] = 1 / dec
        row["market_probability"] = 1 / dec
        row["odds_status"] = "LIVE" if live_odds else "UPLOADED_ROW"
        row["odds_source"] = "LIVE_API" if live_odds else "UPLOADED_ROW"
        if live_odds:
            row["odds_last_refresh"] = row.get("odds_last_refresh") or refresh_time
        if prob is not None:
            edge = prob - (1 / dec)
            ev = prob * dec - 1
            row["edge"] = edge
            row["model_market_edge"] = edge
            row["EV"] = ev
            row["expected_value_per_unit"] = ev
            row["fair_odds"] = 1 / prob if prob > 0 else ""
            row["ev_status"] = "RECALCULATED"
            row["ev_source"] = "LIVE" if live_odds else "FALLBACK_CALCULATED"
        else:
            row["ev_status"] = "UNVERIFIED_MODEL_PROBABILITY_MISSING"
    row["no_vig_status"] = row.get("no_vig_status") or "UNAVAILABLE_MARKET_INCOMPLETE"
    row["odds_market_sides_available"] = row.get("odds_market_sides_available") or "false"

    source, context = resolve_magazine_context(row)
    row["context_source"] = source
    row["context_status"] = "LIVE_OR_SOURCE_BACKED" if source != "EMPTY_WITH_REASON" else "EMPTY_WITH_REASON"
    if source == "EMPTY_WITH_REASON":
        row["context_failure_reason"] = context
    for key in ("sports_context_summary", "preview_summary", "game_summary", "short_reason", "matchup_notes"):
        _set_if_empty(row, key, context)

    fallback = row.get("odds_status") != "LIVE" or source == "EMPTY_WITH_REASON"
    row["fallback_used"] = str(bool(fallback))
    if fallback:
        parts = []
        if row.get("odds_status") != "LIVE":
            parts.append(f"odds_status={row.get('odds_status')}")
        if source == "EMPTY_WITH_REASON":
            parts.append("context_empty")
        row["fallback_reason"] = row.get("fallback_reason") or "; ".join(parts)
    if not _useful(row.get("risk_label")) and fallback:
        row["risk_label"] = "FALLBACK MODE"
    if not _useful(row.get("final_decision")):
        ev = _safe_float(row.get("EV") or row.get("expected_value_per_unit"))
        row["final_decision"] = "BET CANDIDATE" if ev is not None and ev > 0 else "WATCHLIST"
    row["field_provenance_json"] = json.dumps({"report_source": "final_enriched_picks_df", "odds": row.get("odds_source"), "ev": row.get("ev_source") or row.get("ev_status"), "context": source}, sort_keys=True)
    row["source_trace_json"] = json.dumps({"report_run_id": report_run_id, "event_key": row.get("event_key"), "fallback_used": row.get("fallback_used"), "fallback_reason": row.get("fallback_reason")}, sort_keys=True)
    row["api_health_json"] = json.dumps(check_api_health(True), sort_keys=True)
    row["api_sources_active"] = " · ".join([name for name, data in check_api_health(True).items() if data.get("status") == "CONFIGURED"])
    return row


def enrich_row_with_live_api_data(row_like: Any, *, report_run_id: str | None = None, last_api_refresh_time: str | None = None) -> dict[str, Any]:
    row = _row(row_like)
    if row.get("_live_api_enriched") == ENRICHMENT_VERSION and row.get("report_source") == "final_enriched_picks_df":
        return row
    if not report_run_id or not last_api_refresh_time:
        report_run_id, last_api_refresh_time = _new_run_meta([row])
    row["odds_api_status"] = "CONFIGURED" if _secret(*API_SECRET_DEFS["Odds API"]) else "API_KEY_MISSING"
    if row["odds_api_status"] == "API_KEY_MISSING":
        row["odds_failure_reason"] = row.get("odds_failure_reason") or "Odds API key missing or no live odds matched."
    _enrich_perplexity(row)
    _apply_final_fields(row, report_run_id, last_api_refresh_time)
    row["_live_api_enriched"] = ENRICHMENT_VERSION
    return row


def _report_page_priority(row: Mapping[str, Any]) -> int:
    lane = _get(row, "report_lane", "report_lane_v2").lower()
    action = _get(row, "consumer_action", "recommended_action", "public_action").lower()
    ready = _get(row, "official_publish_ready", "publish_ready").lower() in {"true", "1", "yes"}
    return 0 if ready or "official" in action or lane in {"best_play", "best play"} else 1


def _dedupe_report_page_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    index: dict[str, int] = {}
    priority: dict[str, int] = {}
    for row in rows:
        key = row.get("event_key") or _event_key(row)
        p = _report_page_priority(row)
        if key in index:
            if p < priority[key]:
                unique[index[key]] = row
                priority[key] = p
            continue
        index[key] = len(unique)
        priority[key] = p
        unique.append(row)
    return unique


def enrich_rows_with_live_api_data(rows: list[Any] | tuple[Any, ...]) -> list[dict[str, Any]]:
    report_run_id, refresh_time = _new_run_meta(rows)
    enriched = [enrich_row_with_live_api_data(row, report_run_id=report_run_id, last_api_refresh_time=refresh_time) for row in rows]
    out = _dedupe_report_page_rows(enriched)
    _ensure_renderer_patch()
    return out


def build_final_enriched_picks_df(raw_picks_df: Any, force_refresh: bool = False) -> Any:
    if force_refresh:
        _CACHE.clear()
    try:
        import pandas as pd  # type: ignore
        frame = raw_picks_df.copy() if hasattr(raw_picks_df, "copy") else pd.DataFrame(raw_picks_df)
        return pd.DataFrame(enrich_rows_with_live_api_data(frame.to_dict("records")))
    except Exception:
        return enrich_rows_with_live_api_data(list(raw_picks_df or []))


def _headline_context_lines(row: Any) -> list[str]:
    source, context = resolve_magazine_context(_row(row))
    return [context]


def _pairs(row: Any, lang: str) -> list[tuple[str, str]]:
    data = _row(row)
    rows = [
        ("REPORT SOURCE", _get(data, "report_source", default="final_enriched_picks_df")),
        ("ODDS ROW", _get(data, "odds_source", default="UPLOADED_ROW")),
        ("CONTEXT", _get(data, "context_source", default="EMPTY_WITH_REASON")),
        ("RUN", _get(data, "report_run_id", default="no_run_id")[:22]),
        ("REFRESH", _get(data, "last_api_refresh_time", default="no_refresh")[:22]),
    ]
    try:
        import autonomous_betting_agent.magazine_book_export as m
        return [(m._tr(label, lang), m._tr(str(value), lang)) for label, value in rows]
    except Exception:
        return [(label, str(value)) for label, value in rows]


def install(module: Any) -> Any:
    original_render = module.render_full_pick_magazine_page
    original_png = module._png

    def render(row_like: Any, *args: Any, **kwargs: Any):
        return original_render(enrich_row_with_live_api_data(row_like), *args, **kwargs)

    def render_png(row_like: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
        return original_png(module.render_full_pick_magazine_page(enrich_row_with_live_api_data(row_like), background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))

    module._useful = _useful
    module._headline_context_lines = _headline_context_lines
    module._pairs = _pairs
    module.render_full_pick_magazine_page = render
    module.render_full_pick_magazine_page_png = render_png
    module.enrich_row_with_live_api_data = enrich_row_with_live_api_data
    module.enrich_rows_with_live_api_data = enrich_rows_with_live_api_data
    module.build_final_enriched_picks_df = build_final_enriched_picks_df
    module.check_api_health = check_api_health
    if ENRICHMENT_VERSION not in str(getattr(module, "MAGAZINE_STYLE_VERSION", "")):
        module.MAGAZINE_STYLE_VERSION = f"{module.MAGAZINE_STYLE_VERSION}_{ENRICHMENT_VERSION}"
    module._LIVE_API_ENRICHMENT_VERSION = ENRICHMENT_VERSION
    return module


def _ensure_renderer_patch() -> None:
    try:
        import autonomous_betting_agent.magazine_book_export as magazine_book_export
        install(magazine_book_export)
    except Exception:
        pass


def _patch_importlib_reload() -> None:
    if getattr(importlib.reload, _RELOAD_MARKER, False):
        return
    original_reload = getattr(importlib, "_aba_original_reload", importlib.reload)
    setattr(importlib, "_aba_original_reload", original_reload)

    def reload_with_magazine_patch(module: Any) -> Any:
        reloaded = original_reload(module)
        if getattr(reloaded, "__name__", "") == "autonomous_betting_agent.magazine_book_export":
            return install(reloaded)
        return reloaded

    setattr(reload_with_magazine_patch, _RELOAD_MARKER, True)
    importlib.reload = reload_with_magazine_patch


_patch_importlib_reload()
_ensure_renderer_patch()
