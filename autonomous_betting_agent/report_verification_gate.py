from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping
import re

from .report_public_quality import (
    build_full_market_label,
    has_exact_market_line,
    is_saved_source,
    market_type,
    provider_state,
    public_text,
    to_float,
)

VERSION = "verification_gate_v1"
VERIFIED_BUYER_PICK = "VERIFIED_BUYER_PICK"
WATCHLIST_VERIFY_PRICE = "WATCHLIST_VERIFY_PRICE"
NO_PRICE_REJECTED = "NO_B" + "ET_PRICE_REJECTED"
RESEARCH_ONLY = "RESEARCH_ONLY"
AUDIT_ONLY = "AUDIT_ONLY"
VERIFIED_REPORT = "Verified 100 Report"
WATCHLIST_REPORT = "Verification Watchlist"
AUDIT_REPORT = "Full Audit Book"
NO_VERIFIED_MESSAGE = "No verified buyer picks available from current provider data yet."
STATUS = {
    VERIFIED_BUYER_PICK: "VERIFIED CANDIDATE / PLAYABLE VALUE",
    WATCHLIST_VERIFY_PRICE: "WATCHLIST / VERIFY PRICE",
    NO_PRICE_REJECTED: "NO B" + "ET / PRICE REJECTED",
    RESEARCH_ONLY: "RESEARCH ONLY",
    AUDIT_ONLY: "AUDIT ONLY",
}
RISK = {
    VERIFIED_BUYER_PICK: "VERIFIED PRICE",
    WATCHLIST_VERIFY_PRICE: "VERIFY PRICE",
    NO_PRICE_REJECTED: "PRICE REJECTED",
    RESEARCH_ONLY: "RESEARCH ONLY",
    AUDIT_ONLY: "AUDIT ONLY",
}
TIME_KEYS = ("provider_timestamp", "price_timestamp", "verified_timestamp", "timestamp", "last_update", "last_updated", "updated_at", "odds_timestamp")
PRICE_KEYS = ("decimal_price", "decimal_odds", "best_price", "odds_decimal", "odds_at_pick", "verified_price", "current_price", "price", "odds")
PROB_KEYS = ("learned_model_probability", "final_adjusted_probability", "adjusted_model_probability", "model_probability_clean", "model_probability", "probability")
EV_KEYS = ("expected_value_per_unit", "profit_expected_value", "expected_value", "ev", "EV", "raw_EV", "two_page_raw_EV")
EDGE_KEYS = ("model_market_edge", "edge", "raw_edge", "two_page_raw_edge")
EVENT_ID_KEYS = ("provider_event_id", "odds_api_event_id", "sportsdataio_event_id", "sdio_event_id", "api_football_fixture_id", "fixture_id", "game_id", "event_id")
SELECTION_KEYS = ("selection", "pick", "prediction", "side", "outcome", "team", "participant", "exact_" + "b" + "et")
PROVIDER_KEYS = ("provider", "odds_provider", "api_provider", "odds_source", "data_source", "source")
BOOK_KEYS = ("sportsbook", "bookmaker", "book", "best_bookmaker")
BAD_SOURCE = ("saved", "uploaded", "cached", "fallback", "handoff", "history", "ledger", "manual", "old")
BAD_STATUS = ("cancel", "blocked", "do not publish", "post-start", "post start", "unsafe", "void", "final", "finished", "completed", "settled", "graded", "expired", "stale")


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        try:
            data = value.to_dict()
            return dict(data) if isinstance(data, Mapping) else {}
        except Exception:
            return {}
    return dict(getattr(value, "__dict__", {}) or {})


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("−", "-").replace("–", "-").replace("—", "-").strip())


def _first(data: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        text = public_text(data.get(key))
        if text:
            return text
    return ""


def _num(data: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        parsed = to_float(data.get(key))
        if parsed is not None:
            return parsed
    return None


def _prob(data: Mapping[str, Any]) -> float | None:
    value = _num(data, *PROB_KEYS)
    if value is None:
        return None
    if 1.0 < abs(value) <= 100.0:
        value /= 100.0
    return value if 0.0 <= value <= 1.0 else None


def _price(data: Mapping[str, Any]) -> float | None:
    value = _num(data, *PRICE_KEYS)
    if value is None:
        value = _num(data, "american_odds", "odds_american")
    if value is None:
        return None
    if value <= -100:
        value = 1.0 + 100.0 / abs(value)
    elif value >= 100:
        value = 1.0 + value / 100.0
    return value if value > 1.0 else None


def _edge(data: Mapping[str, Any]) -> float | None:
    value = _num(data, *EDGE_KEYS)
    if value is not None and 1.0 < abs(value) <= 100.0:
        value /= 100.0
    return value


def _ev(data: Mapping[str, Any]) -> float | None:
    value = _num(data, *EV_KEYS)
    if value is not None:
        return value
    prob = _prob(data)
    price = _price(data)
    return prob * price - 1.0 if prob is not None and price is not None else None


def _truthy(value: Any) -> bool | None:
    text = public_text(value).lower()
    if text in {"1", "true", "yes", "y", "ok", "fresh", "verified", "current", "matched"}:
        return True
    if text in {"0", "false", "no", "n", "stale", "expired", "missing", "unverified", "unmatched"}:
        return False
    return None


def _blob(data: Mapping[str, Any], keys: Iterable[str]) -> str:
    return " ".join(public_text(data.get(key)).lower() for key in keys if public_text(data.get(key)))


def _parse_time(value: Any) -> datetime | None:
    text = public_text(value)
    if not text:
        return None
    if text.lower() in {"now", "current"}:
        return datetime.now(timezone.utc)
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        try:
            return datetime.fromtimestamp(float(text), tz=timezone.utc)
        except Exception:
            return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    return (parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed).astimezone(timezone.utc)


def _is_live(data: Mapping[str, Any]) -> bool:
    return any(token in _blob(data, ("is_live", "live", "in_play", "market_status", "status", "event_status", "odds_status")) for token in ("live", "in-play", "inplay", "in progress"))


def _fresh(data: Mapping[str, Any], now: datetime | None = None) -> tuple[bool, str, float | None]:
    text = _first(data, *TIME_KEYS)
    parsed = _parse_time(text)
    if not text or parsed is None:
        return False, "missing", None
    now = now or datetime.now(timezone.utc)
    age = (now.astimezone(timezone.utc) - parsed).total_seconds()
    limit = 60 if _is_live(data) else 900
    if age < -300:
        return False, "future", age
    if age > limit:
        return False, "stale", age
    return True, "fresh", age


def _source_current(data: Mapping[str, Any]) -> tuple[bool, str]:
    if is_saved_source(data):
        return False, "Saved-source row requires current provider verification."
    blob = _blob(data, ("source_mode", "selected_source_key", "odds_source", "data_source", "source", "source_label", "odds_status", "report_source", "report_source_mode"))
    if any(token in blob for token in BAD_SOURCE):
        return False, "Saved-source row requires current provider verification."
    if "consensus" in blob and not _first(data, *BOOK_KEYS):
        return False, "Book-level source required."
    matched = provider_state(data) == "Provider matched"
    explicit = any(_truthy(data.get(key)) is True for key in ("current_provider_verified", "provider_verified", "odds_verified", "price_verified", "odds_api_live", "the_odds_api_live"))
    return (matched or explicit), ("Current provider match confirmed." if (matched or explicit) else "Current provider verification unavailable.")


def _blocked(data: Mapping[str, Any]) -> tuple[bool, str]:
    blob = _blob(data, ("event_status", "game_status", "market_status", "status", "price_status", "odds_freshness_status", "cancel_condition", "cancel_reason", "blocked_reason"))
    live = _is_live(data)
    if any(token in blob for token in BAD_STATUS) and not live:
        return True, "Market is stale, blocked, final, or unsafe."
    if live and not (bool(_first(data, "live_clock", "game_clock", "minute")) and bool(_first(data, "live_score", "score", "current_score"))):
        return True, "Live market missing live-feed confirmation."
    return False, ""


def _line(data: Mapping[str, Any], kind: str) -> str:
    if kind == "total":
        keys = ("total_line", "game_total_line", "total", "point", "points", "line", "handicap")
    elif kind == "run_line":
        keys = ("run_line", "runline", "spread_line", "handicap", "point", "points", "line")
    elif kind == "spread":
        keys = ("spread_line", "handicap", "point", "points", "line")
    else:
        keys = ("line", "point", "points", "handicap")
    return _first(data, *keys)


def _has_provider_line(data: Mapping[str, Any], kind: str) -> bool:
    return bool(_line(data, kind)) if kind in {"total", "team_total", "run_line", "spread", "player_prop"} else has_exact_market_line(data)


def verify_current_provider_match(row: Any, now: datetime | None = None) -> dict[str, Any]:
    data = _row(row)
    source_ok, source_reason = _source_current(data)
    fresh, ts_status, age = _fresh(data, now)
    blocked, block_reason = _blocked(data)
    kind = market_type(data)
    price = _price(data)
    prob = _prob(data)
    edge = _edge(data)
    ev = _ev(data)
    line_ok = _has_provider_line(data, kind)
    checks = {
        "event_id": bool(_first(data, *EVENT_ID_KEYS)),
        "selection": bool(_first(data, *SELECTION_KEYS)),
        "market_type": bool(kind and kind != "unknown"),
        "exact_line": line_ok,
        "price": price is not None,
        "timestamp": fresh,
        "model_probability": prob is not None,
        "edge_positive": edge is not None and edge > 0,
        "ev_positive": ev is not None and ev > 0,
        "source_current": source_ok,
        "not_blocked": not blocked,
    }
    reasons: list[str] = []
    if not checks["event_id"]:
        reasons.append("Current provider event ID required.")
    if not checks["selection"]:
        reasons.append("Selection match required.")
    if not checks["market_type"]:
        reasons.append("Market type required.")
    if not checks["exact_line"]:
        reasons.append("Exact provider market line required.")
    if price is None:
        reasons.append("Current provider price required.")
    if not fresh:
        reasons.append("Fresh provider timestamp required." if ts_status == "missing" else "Provider timestamp is stale.")
    if prob is None:
        reasons.append("Model probability required.")
    if edge is None:
        reasons.append("Edge required.")
    elif edge <= 0:
        reasons.append("Edge must be positive.")
    if ev is None:
        reasons.append("EV required.")
    elif ev <= 0:
        reasons.append("EV must be positive.")
    if not source_ok:
        reasons.append(source_reason)
    if blocked:
        reasons.append(block_reason)
    return {
        "verified": all(checks.values()),
        "checks": checks,
        "reasons": reasons,
        "market_label": build_full_market_label(data),
        "provider_event_id": _first(data, *EVENT_ID_KEYS),
        "verified_price": price,
        "verified_line": _line(data, kind),
        "verified_timestamp": _first(data, *TIME_KEYS),
        "timestamp_status": ts_status,
        "timestamp_age_seconds": age,
        "provider_name": _first(data, *PROVIDER_KEYS),
        "book": _first(data, *BOOK_KEYS),
        "model_probability": prob,
        "edge": edge,
        "ev": ev,
    }


def normalize_verified_market_label(row: Any) -> str:
    return build_full_market_label(_row(row))


def classify_report_row(row: Any, now: datetime | None = None) -> dict[str, Any]:
    data = _row(row)
    info = verify_current_provider_match(data, now)
    edge = info["edge"]
    ev = info["ev"]
    blocked, block_reason = _blocked(data)
    if edge is not None and ev is not None and (edge <= 0 or ev <= 0):
        cls = NO_PRICE_REJECTED
    elif blocked:
        cls = AUDIT_ONLY
    elif info["verified"]:
        cls = VERIFIED_BUYER_PICK
    elif edge is not None and ev is not None and edge > 0 and ev > 0:
        cls = WATCHLIST_VERIFY_PRICE
    else:
        cls = RESEARCH_ONLY
    reasons = list(info["reasons"])
    if blocked and block_reason and block_reason not in reasons:
        reasons.append(block_reason)
    if not reasons:
        reasons = ["Current provider verification confirmed."] if cls == VERIFIED_BUYER_PICK else ["Current provider verification unavailable."]
    out = dict(data)
    out.update({
        "report_verification_class": cls,
        "report_classification": cls,
        "verification_gate_version": VERSION,
        "verification_status": STATUS[cls],
        "final_decision": STATUS[cls],
        "agent_decision": STATUS[cls],
        "recommendation": STATUS[cls],
        "consumer_action": STATUS[cls],
        "recommended_action": STATUS[cls],
        "risk": RISK[cls],
        "risk_level": RISK[cls],
        "risk_label": RISK[cls],
        "profit_guard_status": RISK[cls],
        "report_verification_reason": reasons[0],
        "verification_reason": reasons[0],
        "verification_reasons": reasons,
        "final_explanation": reasons[0],
        "action_reason": reasons[0],
        "recommendation_reason": reasons[0],
        "public_market_label": info["market_label"],
        "verified_market_label": info["market_label"],
        "full_market_label": info["market_label"],
        "provider_event_id": info["provider_event_id"] or data.get("provider_event_id", ""),
        "verified_price": info["verified_price"],
        "verified_line": info["verified_line"],
        "verified_timestamp": info["verified_timestamp"],
        "timestamp_status": info["timestamp_status"],
        "timestamp_age_seconds": info["timestamp_age_seconds"],
        "provider_name": info["provider_name"],
        "book": info["book"],
        "model_probability": info["model_probability"] if info["model_probability"] is not None else data.get("model_probability"),
        "model_market_edge": info["edge"] if info["edge"] is not None else data.get("model_market_edge"),
        "expected_value_per_unit": info["ev"] if info["ev"] is not None else data.get("expected_value_per_unit"),
        "report_renderer_marker": f"Renderer: {VERSION}",
    })
    return out


def _dedupe_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    data = _row(row)
    return (
        _first(data, "provider_event_id", *EVENT_ID_KEYS).lower(),
        str(market_type(data)).lower(),
        _first(data, *SELECTION_KEYS).lower(),
        str(data.get("verified_line") or _line(data, market_type(data))).lower(),
        f"{_first(data, *BOOK_KEYS, *PROVIDER_KEYS).lower()}:{data.get('verified_price') or _price(data) or ''}",
    )


def detect_duplicate_rows(rows: Iterable[Any]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        data = dict(_row(row)) if _row(row).get("report_verification_class") else classify_report_row(row)
        key = _dedupe_key(data)
        if data.get("report_verification_class") == VERIFIED_BUYER_PICK and key in seen:
            data.update({"report_verification_class": AUDIT_ONLY, "verification_status": STATUS[AUDIT_ONLY], "final_decision": STATUS[AUDIT_ONLY], "risk": RISK[AUDIT_ONLY], "report_verification_reason": "Duplicate removed from buyer report.", "duplicate_removed": True})
        else:
            seen.add(key)
        out.append(data)
    return out


def _rank_key(row: Mapping[str, Any]) -> tuple[float, float, float, float, float]:
    ev = _ev(row) or 0.0
    edge = _edge(row) or 0.0
    no_vig = _num(row, "no_vig_edge", "novig_edge") or edge
    age = to_float(row.get("timestamp_age_seconds"))
    freshness = -age if age is not None else -999999.0
    line_quality = 1.0 if has_exact_market_line(row) else 0.0
    prob = _prob(row) or 0.0
    return (ev, no_vig, freshness, line_quality, prob)


def apply_correlation_control(rows: Iterable[Any], max_primary_per_event: int = 1) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    out: list[dict[str, Any]] = []
    for data in sorted([dict(_row(r)) for r in rows], key=_rank_key, reverse=True):
        if data.get("report_verification_class") == VERIFIED_BUYER_PICK:
            event_key = (_first(data, "provider_event_id", *EVENT_ID_KEYS) or _first(data, "event", "event_name", "game", "matchup")).lower()
            counts[event_key] = counts.get(event_key, 0) + 1
            if counts[event_key] > max_primary_per_event:
                data.update({"report_verification_class": AUDIT_ONLY, "verification_status": STATUS[AUDIT_ONLY], "final_decision": STATUS[AUDIT_ONLY], "risk": RISK[AUDIT_ONLY], "report_verification_reason": "Excluded by correlation control.", "correlation_excluded": True})
        out.append(data)
    return out


def rank_verified_buyer_picks(rows: Iterable[Any], limit: int = 100) -> list[dict[str, Any]]:
    return sorted([dict(_row(r)) for r in rows if _row(r).get("report_verification_class") == VERIFIED_BUYER_PICK], key=_rank_key, reverse=True)[:limit]


def _prepared(rows: Iterable[Any], now: datetime | None = None) -> list[dict[str, Any]]:
    return apply_correlation_control(detect_duplicate_rows([classify_report_row(r, now) for r in rows]))


def build_report_count_summary(rows: Iterable[Any]) -> dict[str, int]:
    counts = {"verified_buyer_picks": 0, "watchlist_verify_price_rows": 0, "price_rejected_rows": 0, "research_only_rows": 0, "audit_only_rows": 0, "duplicate_rows_removed": 0, "rows_excluded_by_correlation_control": 0, "rows_excluded_by_provider_failure": 0, "rows_excluded_by_stale_timestamp": 0, "rows_excluded_by_line_mismatch": 0}
    for r in rows:
        d = _row(r)
        cls = d.get("report_verification_class") or classify_report_row(d).get("report_verification_class")
        key = {VERIFIED_BUYER_PICK: "verified_buyer_picks", WATCHLIST_VERIFY_PRICE: "watchlist_verify_price_rows", NO_PRICE_REJECTED: "price_rejected_rows", RESEARCH_ONLY: "research_only_rows"}.get(cls, "audit_only_rows")
        counts[key] += 1
        reason = _clean(d.get("report_verification_reason")).lower()
        counts["duplicate_rows_removed"] += int(bool(d.get("duplicate_removed")))
        counts["rows_excluded_by_correlation_control"] += int(bool(d.get("correlation_excluded")))
        counts["rows_excluded_by_provider_failure"] += int("provider" in reason and ("unavailable" in reason or "required" in reason))
        counts["rows_excluded_by_stale_timestamp"] += int("stale" in reason or d.get("timestamp_status") == "stale")
        counts["rows_excluded_by_line_mismatch"] += int("line" in reason and "required" in reason)
    return counts


def _stamp(rows: list[dict[str, Any]], mode: str, summary: Mapping[str, int]) -> list[dict[str, Any]]:
    for row in rows:
        row["report_mode"] = mode
        row["report_count_summary"] = dict(summary)
        row["report_renderer_marker"] = f"Renderer: {VERSION} | Mode: {mode} | Verified count: {summary.get('verified_buyer_picks', 0)} / 100"
    return rows


def _no_verified_row(summary: Mapping[str, int]) -> dict[str, Any]:
    reason = f"Verified buyer picks: 0 / 100. Watchlist rows: {summary.get('watchlist_verify_price_rows', 0)}. Price-rejected rows: {summary.get('price_rejected_rows', 0)}. Research-only rows: {summary.get('research_only_rows', 0)}. Audit-only rows: {summary.get('audit_only_rows', 0)}."
    return _stamp([{"event": NO_VERIFIED_MESSAGE, "game": NO_VERIFIED_MESSAGE, "prediction": "No verified buyer picks", "pick": "No verified buyer picks", "market_type": "research only", "report_verification_class": RESEARCH_ONLY, "verification_status": RESEARCH_ONLY, "final_decision": "NO VERIFIED BUYER PICKS", "agent_decision": "NO VERIFIED BUYER PICKS", "recommendation": "NO VERIFIED BUYER PICKS", "consumer_action": "NO VERIFIED BUYER PICKS", "risk": "RESEARCH ONLY", "risk_level": "RESEARCH ONLY", "risk_label": "RESEARCH ONLY", "report_verification_reason": NO_VERIFIED_MESSAGE, "verification_reason": NO_VERIFIED_MESSAGE, "final_explanation": reason, "action_reason": reason, "recommendation_reason": reason}], VERIFIED_REPORT, summary)


def build_verified_100_report_rows(rows: Iterable[Any], limit: int = 100, now: datetime | None = None) -> list[dict[str, Any]]:
    prepared = _prepared(rows, now)
    summary = build_report_count_summary(prepared)
    ranked = rank_verified_buyer_picks(prepared, limit)
    if not ranked:
        return _no_verified_row(summary)
    for row in ranked:
        if summary["verified_buyer_picks"] < 100:
            row["report_shortfall_summary"] = f"{summary['verified_buyer_picks']} verified buyer picks available from current provider data. {max(0, 100 - summary['verified_buyer_picks'])} additional rows were excluded because they could not be verified."
    return _stamp(ranked, VERIFIED_REPORT, summary)


def build_watchlist_rows(rows: Iterable[Any], now: datetime | None = None) -> list[dict[str, Any]]:
    prepared = _prepared(rows, now)
    return _stamp([r for r in prepared if r.get("report_verification_class") == WATCHLIST_VERIFY_PRICE], WATCHLIST_REPORT, build_report_count_summary(prepared))


def build_audit_rows(rows: Iterable[Any], now: datetime | None = None) -> list[dict[str, Any]]:
    prepared = _prepared(rows, now)
    return _stamp(prepared, AUDIT_REPORT, build_report_count_summary(prepared))


def build_report_rows(rows: Iterable[Any], mode: str | None = None, limit: int = 100, now: datetime | None = None) -> list[dict[str, Any]]:
    text = (mode or VERIFIED_REPORT).lower().replace("_", " ")
    if "watch" in text:
        return build_watchlist_rows(rows, now)
    if "audit" in text or "full" in text:
        return build_audit_rows(rows, now)
    return build_verified_100_report_rows(rows, limit, now)


def should_render_verified_buyer_pick(row: Any) -> bool:
    data = _row(row)
    return (data.get("report_verification_class") or classify_report_row(data).get("report_verification_class")) == VERIFIED_BUYER_PICK


def should_render_page_two(row: Any) -> bool:
    data = _row(row)
    if not should_render_verified_buyer_pick(data):
        return False
    if any(_truthy(data.get(k)) is True for k in ("verified_advanced_market", "advanced_market_verified", "verified_prop_market", "verified_live_trigger")):
        return True
    text = _clean(data.get("advanced_markets") or data.get("advanced_market_rows") or data.get("prop_markets") or data.get("live_markets")).lower()
    return bool(text and "verified" in text and "positive" in text)
