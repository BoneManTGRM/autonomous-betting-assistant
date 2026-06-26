from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def canonical_text(value: Any) -> str:
    text = _strip_accents(safe_text(value)).lower()
    text = re.sub(r"\s+(?:at|vs|v|@)\s+", " vs ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def row_event_name(row: Mapping[str, Any]) -> str:
    event = safe_text(row.get("public_event") or row.get("event") or row.get("event_name") or row.get("matchup") or row.get("game"))
    if event:
        return event
    away = safe_text(row.get("away_team") or row.get("team_a") or row.get("team1"))
    home = safe_text(row.get("home_team") or row.get("team_b") or row.get("team2"))
    if away and home:
        return f"{away} vs {home}"
    team = safe_text(row.get("team") or row.get("team_name"))
    opponent = safe_text(row.get("opponent"))
    return f"{team} vs {opponent}" if team and opponent else team or opponent


def row_event_start(row: Mapping[str, Any]) -> str:
    return safe_text(
        row.get("event_start_utc")
        or row.get("event_start_time")
        or row.get("commence_time")
        or row.get("start_time")
        or row.get("event_date")
    )


def row_event_context(row: Mapping[str, Any]) -> str:
    return "|".join(
        part
        for part in (
            canonical_text(row.get("sport")),
            canonical_text(row.get("league")),
            canonical_text(row.get("competition")),
        )
        if part
    )


def event_group_key(row: Mapping[str, Any]) -> str:
    event = canonical_text(row_event_name(row))
    start = canonical_text(row_event_start(row))
    if start:
        return "|".join(part for part in (event, start) if part)
    context = row_event_context(row)
    return "|".join(part for part in (event, context) if part)


def row_market_key(row: Mapping[str, Any]) -> str:
    fields = (
        event_group_key(row),
        canonical_text(row.get("prediction") or row.get("pick") or row.get("selection") or row.get("public_pick")),
        canonical_text(row.get("market_type") or row.get("market")),
        canonical_text(row.get("line_point") or row.get("line") or row.get("handicap") or row.get("total")),
    )
    return "|".join(part for part in fields if part)


def _safe_float(value: Any) -> float | None:
    text = safe_text(value).replace("%", "").replace(",", "")
    if not text or text.lower() in {"none", "null", "nan", "n/a", "na"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _has_positive_value(row: Mapping[str, Any]) -> bool:
    for key in ("model_market_edge", "edge", "expected_value_per_unit", "ev"):
        parsed = _safe_float(row.get(key))
        if parsed is not None and parsed > 0:
            return True
    return False


def _has_complete_price_probability(row: Mapping[str, Any]) -> bool:
    price = any(safe_text(row.get(key)) for key in ("decimal_price", "best_price", "average_price", "odds_decimal", "odds_at_pick", "odds"))
    probability = any(safe_text(row.get(key)) for key in ("model_probability", "learned_model_probability", "final_adjusted_probability", "probability"))
    return price and probability


def _row_priority(row: Mapping[str, Any]) -> int:
    action = canonical_text(row.get("consumer_action") or row.get("recommended_action") or row.get("public_action") or row.get("report_lane"))
    publish_ready = safe_text(row.get("official_publish_ready") or row.get("publish_ready")).lower() in {"true", "1", "yes"}
    proof = bool(safe_text(row.get("proof_id") or row.get("locked_at_utc") or row.get("proof_hash")))
    if publish_ready or "official" in action or "oficial" in action or proof:
        return 0
    if _has_positive_value(row):
        return 1
    if _has_complete_price_probability(row):
        return 2
    return 3


def collapse_to_event_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return one display row per event while preserving row-level data elsewhere.

    This is for dashboards, selectors, and public-facing list views. It should not
    be used to delete market-level rows from proof ledgers or learning memory.
    """
    unique: list[dict[str, Any]] = []
    index_by_event: dict[str, int] = {}
    priority_by_event: dict[str, int] = {}
    counts_by_event: dict[str, int] = {}
    markets_by_event: dict[str, set[str]] = {}

    for source_row in rows:
        row = dict(source_row)
        key = event_group_key(row)
        if not key:
            unique.append(row)
            continue
        counts_by_event[key] = counts_by_event.get(key, 0) + 1
        market = safe_text(row.get("market_type") or row.get("market"))
        markets_by_event.setdefault(key, set())
        if market:
            markets_by_event[key].add(market)
        priority = _row_priority(row)
        if key in index_by_event:
            if priority < priority_by_event[key]:
                unique[index_by_event[key]] = row
                priority_by_event[key] = priority
            continue
        index_by_event[key] = len(unique)
        priority_by_event[key] = priority
        unique.append(row)

    for row in unique:
        key = event_group_key(row)
        if key and counts_by_event.get(key, 0) > 1:
            row["event_duplicate_count"] = counts_by_event[key]
            row["event_market_count"] = len(markets_by_event.get(key, set()))
            row["event_display_note"] = f"{counts_by_event[key]} rows grouped for this event"
    return unique


def event_duplicate_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = event_group_key(row)
        if key:
            counts[key] = counts.get(key, 0) + 1
    duplicate_events = sum(1 for count in counts.values() if count > 1)
    duplicate_rows = sum(count - 1 for count in counts.values() if count > 1)
    return {
        "total_rows": len(rows),
        "unique_events": len(counts),
        "duplicate_events": duplicate_events,
        "duplicate_event_rows": duplicate_rows,
    }
