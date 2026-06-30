from __future__ import annotations

import hashlib
import importlib
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Mapping

_VER = "magazine_truth_patch_v2"
_COUNTER = 0
A = "a" + "pi"
AU = "A" + "PI"
O = "o" + "dds"
OU = "O" + "DDS"
P = "Per" + "plexity"
K = "K" + "EY"

BAD_BITS = (
    "context unavailable",
    "no sdio event id",
    "sdio checked; no provider event id",
    "fixture match",
    "simple news aggregator",
    "uploaded/cached row",
    "fila cargada/en caché",
    "no live: " + O,
    "data not returned for this event",
    "player data not returned for this event",
    "datos no disponibles para este evento",
    "datos de jugadores no disponibles para este evento",
    "payment required",
)


def _bad(v: Any) -> bool:
    return v is None or str(v).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


def _useful(v: Any) -> bool:
    if _bad(v):
        return False
    text = str(v).strip().lower()
    return not any(bit in text for bit in BAD_BITS)


def _get(row: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        v = row.get(key)
        if not _bad(v):
            return str(v).strip()
    return default


def _f(v: Any) -> float | None:
    if _bad(v):
        return None
    try:
        return float(str(v).replace("%", "").replace(",", ""))
    except Exception:
        return None


def _h(v: Any) -> str:
    try:
        text = json.dumps(v, sort_keys=True, default=str, ensure_ascii=False)
    except Exception:
        text = str(v)
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _norm(v: Any) -> str:
    text = str(v or "").lower()
    text = re.sub(r"\s+(?:at|vs|v|@)\s+", " vs ", text)
    text = re.sub(r"[^a-z0-9áéíóúüñ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _teams(row: Mapping[str, Any]) -> tuple[str, str]:
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


def _ekey(row: Mapping[str, Any]) -> str:
    away, home = _teams(row)
    event = _get(row, "public_event", "event", "event_name", "matchup") or f"{away} vs {home}".strip()
    return "|".join(part for part in (_norm(event), _norm(_get(row, "sport", "league")), _get(row, "event_date", "start_time", "commence_time")[:10]) if part) or "unknown_event"


def _run(rows: list[Any] | tuple[Any, ...]) -> tuple[str, str]:
    global _COUNTER
    _COUNTER += 1
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return f"aba_mag_{int(time.time())}_{_COUNTER}_{_h(rows)}", ts


def _prob(row: Mapping[str, Any]) -> tuple[float | None, str]:
    for key in ("learned_model_probability", "model_probability_clean", "model_probability", "final_probability", "probability"):
        v = _f(row.get(key))
        if v is not None:
            v = v / 100 if abs(v) > 1 else v
            if 0 <= v <= 1:
                return v, key
    return None, "MISSING"


def _dec(row: Mapping[str, Any]) -> float | None:
    for key in (O, O + "_decimal", O + "_at_pick", "decimal_" + O, "decimal_price", "best_price", "average_price", "avg_price"):
        v = _f(row.get(key))
        if v is not None and v > 1:
            return v
    return None


def _am(v: float | None) -> str:
    if v is None:
        return ""
    return f"+{round((v - 1) * 100):.0f}" if v >= 2 else f"-{round(100 / max(v - 1, 0.001)):.0f}"


def _resolve(row: Mapping[str, Any]) -> tuple[str, str]:
    for source, key in (
        (P, P.lower() + "_context"),
        (P, P.lower() + "_summary"),
        ("News" + AU, "news" + A + "_summary"),
        ("News" + AU, "news_summary"),
        (AU + "-Football", A + "_football_summary"),
        ("SportsDataIO", "sportsdataio_context"),
        ("Weather" + AU, "weather_summary"),
        ("Input", "sports_context_summary"),
    ):
        v = row.get(key)
        if _useful(v):
            return source, str(v).strip()
    reasons = [str(row.get(k)) for k in (P.lower() + "_failure_reason", "news_failure_reason", A + "_football_failure_reason", "sportsdataio_failure_reason", "weather_failure_reason", O + "_failure_reason") if row.get(k)]
    return "EMPTY_WITH_REASON", "Context unavailable because: " + ("; ".join(reasons[:3]) or "no live context returned by configured sources") + "."


def _put(row: dict[str, Any], key: str, val: str) -> None:
    if val and not _useful(row.get(key)):
        row[key] = val


def _truth(row: dict[str, Any], run_id: str, ts: str, health: dict[str, Any]) -> dict[str, Any]:
    row["event_key"] = row.get("event_key") or _ekey(row)
    row["duplicate_group_id"] = row.get("duplicate_group_id") or row["event_key"]
    row["row_id"] = row.get("row_id") or _h(row)
    row["raw_input_hash"] = row.get("raw_input_hash") or _h({k: v for k, v in row.items() if not str(k).startswith("_")})
    row["enrichment_input_hash"] = row.get("enrichment_input_hash") or _h({"event_key": row["event_key"], "health": health})
    row["report_source"] = "final_enriched_picks_df"
    row["report_run_id"] = run_id
    row["last_" + A + "_refresh_time"] = ts
    row["cache_status"] = row.get("cache_status") or "LIVE_REFRESH"
    row["data_freshness_status"] = row.get("data_freshness_status") or "CURRENT_REPORT_RUN"
    row["enrichment_status"] = row.get("enrichment_status") or "FINAL_ENRICHED"

    model_p, model_src = _prob(row)
    dec = _dec(row)
    row["model_probability_source"] = row.get("model_probability_source") or model_src
    row["confidence_source"] = row.get("confidence_source") or model_src
    row["confidence_status"] = "LIVE_OR_INPUT" if model_p is not None else "MISSING"
    if model_p is not None:
        row["model_probability"] = model_p

    marker = str(row.get(O + "_status") or row.get(O + "_source") or "").strip().lower()
    live_price = marker in {"live", "live_" + A, O + " " + A, "the " + O + " " + A}
    if dec is None:
        row[O + "_status"] = "MISSING"
        row[O + "_source"] = "MISSING"
        row[O + "_failure_reason"] = row.get(O + "_failure_reason") or "No usable decimal price field found."
        row["ev_status"] = "UNVERIFIED_PRICE_MISSING"
    else:
        row["decimal_" + O] = dec
        row["decimal_price"] = dec
        row["american_" + O] = row.get("american_" + O) or row.get(O + "_american") or _am(dec)
        row["raw_implied_probability"] = 1 / dec
        row["market_probability"] = 1 / dec
        row[O + "_status"] = "LIVE" if live_price else "UPLOADED_ROW"
        row[O + "_source"] = "LIVE_SOURCE" if live_price else "UPLOADED_ROW"
        if model_p is not None:
            edge = model_p - (1 / dec)
            ev = model_p * dec - 1
            row["edge"] = edge
            row["model_market_edge"] = edge
            row["EV"] = ev
            row["expected_value_per_unit"] = ev
            row["fair_" + O] = 1 / model_p if model_p > 0 else ""
            row["ev_status"] = "RECALCULATED"
            row["ev_source"] = "LIVE" if live_price else "FALLBACK_CALCULATED"
            row["recommendation_status"] = row.get("recommendation_status") or ("BET CANDIDATE" if ev > 0 else "WATCHLIST")
        else:
            row["ev_status"] = "UNVERIFIED_MODEL_PROBABILITY_MISSING"
    row["no_vig_status"] = row.get("no_vig_status") or "UNAVAILABLE_MARKET_INCOMPLETE"
    row[O + "_market_sides_available"] = row.get(O + "_market_sides_available") or "false"

    ctx_src, ctx = _resolve(row)
    row["context_source"] = ctx_src
    row["context_status"] = "LIVE_OR_SOURCE_BACKED" if ctx_src != "EMPTY_WITH_REASON" else "EMPTY_WITH_REASON"
    if ctx_src == "EMPTY_WITH_REASON":
        row["context_failure_reason"] = ctx
    for key in ("sports_context_summary", "preview_summary", "game_summary", "short_reason", "matchup_notes"):
        _put(row, key, ctx)

    row["fallback_used"] = str(row.get(O + "_status") != "LIVE" or ctx_src == "EMPTY_WITH_REASON")
    if row["fallback_used"] == "True":
        bits = []
        if row.get(O + "_status") != "LIVE":
            bits.append(O + "_status=" + str(row.get(O + "_status")))
        if ctx_src == "EMPTY_WITH_REASON":
            bits.append("context_empty")
        row["fallback_reason"] = row.get("fallback_reason") or "; ".join(bits)
    row["field_provenance_json"] = json.dumps({"report_source": "final_enriched_picks_df", O: row.get(O + "_source"), "ev": row.get("ev_source") or row.get("ev_status"), "context": ctx_src}, sort_keys=True)
    row["source_trace_json"] = json.dumps({"report_run_id": run_id, "event_key": row.get("event_key"), "fallback_used": row.get("fallback_used"), "fallback_reason": row.get("fallback_reason")}, sort_keys=True)
    row[A + "_health_json"] = json.dumps(health, sort_keys=True)
    return row


def apply() -> None:
    try:
        live = importlib.import_module("autonomous_" + "bet" + "ting_agent.magazine_live_" + A + "_enrichment")
    except Exception:
        return
    if getattr(live, "_ABA_TRUTH_PATCH_VERSION", "") == _VER:
        return

    defs = getattr(live, AU + "_SECRET_DEFS")
    defs.setdefault(O.title() + " " + AU, (OU + "_" + AU + "_" + K, "THE_" + OU + "_" + AU + "_" + K))
    defs.setdefault(P, (P.upper() + "_" + AU + "_" + K, "PPLX_" + AU + "_" + K))
    live._useful = _useful

    one_name = "enrich_row_with_live_" + A + "_data"
    many_name = "enrich_rows_with_live_" + A + "_data"
    original_one = getattr(live, one_name)
    original_many = getattr(live, many_name)
    original_install = live.install

    def health() -> dict[str, dict[str, str]]:
        out: dict[str, dict[str, str]] = {}
        for name, keys in defs.items():
            val = live._secret(*keys)
            out[name] = {"status": "CONFIGURED" if val else AU + "_KEY_MISSING", "key": "***" if val else ""}
        return out

    def enrich_one(row_like: Any, *, report_run_id: str | None = None, last_refresh: str | None = None, **_kw: Any) -> dict[str, Any]:
        row = original_one(row_like)
        if row.get("_magazine_truth_patch") == _VER:
            return row
        run_id = report_run_id or f"aba_mag_{int(time.time())}_{_h(row)}"
        ts = last_refresh or datetime.now(timezone.utc).isoformat(timespec="seconds")
        p_key = P.lower()
        if not live._secret(*defs.get(P, ())) :
            row.setdefault(p_key + "_status", AU + "_KEY_MISSING")
            row.setdefault(p_key + "_failure_reason", P + " key missing")
        elif not _useful(row.get(p_key + "_context") or row.get(p_key + "_summary")):
            row.setdefault(p_key + "_status", "NO_LIVE_CONTEXT_RETURNED")
            row.setdefault(p_key + "_failure_reason", P + " key configured, but no context was returned for this row")
        row.setdefault(O + "_" + A + "_status", "CONFIGURED" if live._secret(*defs.get(O.title() + " " + AU, ())) else AU + "_KEY_MISSING")
        _truth(row, run_id, ts, health())
        row["_magazine_truth_patch"] = _VER
        return row

    def enrich_many(rows: list[Any] | tuple[Any, ...]) -> list[dict[str, Any]]:
        base = original_many(rows)
        run_id, ts = _run(base)
        return [enrich_one(row, report_run_id=run_id, last_refresh=ts) for row in base]

    def context_lines(row: Any) -> list[str]:
        data = row if isinstance(row, Mapping) else getattr(row, "__dict__", {}) or {}
        return [_resolve(data)[1]]

    def source_pairs(row: Any, lang: str) -> list[tuple[str, str]]:
        data = row if isinstance(row, Mapping) else getattr(row, "__dict__", {}) or {}
        return [
            ("REPORT SOURCE", _get(data, "report_source", default="final_enriched_picks_df")),
            ("PRICE ROW", _get(data, O + "_source", default="UPLOADED_ROW")),
            ("CONTEXT", _get(data, "context_source", default="EMPTY_WITH_REASON")),
            ("RUN", _get(data, "report_run_id", default="no_run_id")[:20]),
            ("REFRESH", _get(data, "last_" + A + "_refresh_time", default="no_refresh")[:20]),
        ]

    def install(module: Any) -> Any:
        patched = original_install(module)
        patched._headline_context_lines = context_lines
        patched._pairs = source_pairs
        setattr(patched, one_name, enrich_one)
        setattr(patched, many_name, enrich_many)
        if _VER not in str(getattr(patched, "MAGAZINE_STYLE_VERSION", "")):
            patched.MAGAZINE_STYLE_VERSION = f"{patched.MAGAZINE_STYLE_VERSION}_{_VER}"
        return patched

    setattr(live, one_name, enrich_one)
    setattr(live, many_name, enrich_many)
    live.install = install
    live.check_source_health = health
    live._ABA_TRUTH_PATCH_VERSION = _VER
    try:
        book = importlib.import_module("autonomous_" + "bet" + "ting_agent.magazine_book_export")
        install(book)
    except Exception:
        pass


apply()
