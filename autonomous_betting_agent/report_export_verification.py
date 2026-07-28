from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import json
import re
from typing import Any, Iterable, Mapping

LIVE_MAX_AGE_MINUTES = 10
PREGAME_MAX_AGE_MINUTES = 60
PRICE_TOLERANCE_DECIMAL = 0.03
LINE_TOLERANCE = 0.25

STATUS_VERIFIED_LIVE = "VERIFIED LIVE"
STATUS_VERIFIED_RECENT = "VERIFIED RECENT"
STATUS_STALE_BLOCKED = "STALE - EXPORT BLOCKED"
STATUS_PRICE_MOVED = "PRICE MOVED - EXPORT BLOCKED"
STATUS_LINE_MOVED = "LINE MOVED - EXPORT BLOCKED"
STATUS_API_UNAVAILABLE = "API UNAVAILABLE - NOT VERIFIED"
STATUS_HISTORICAL = "HISTORICAL RESULT - NOT LIVE"
STATUS_PROVIDER_UNAVAILABLE = "PROVIDER DATA UNAVAILABLE"
STATUS_EXPORT_BLOCKED = "EXPORT BLOCKED"

BLOCKING_CODES = {
    "STALE_TIMESTAMP",
    "PRICE_MOVED",
    "LINE_MOVED",
    "EVENT_MISMATCH",
    "MARKET_NOT_FOUND",
    "API_FETCH_FAILED",
    "SNAPSHOT_MISSING",
    "EXPORT_BLOCKED",
}

PLACEHOLDER_TOKENS = (
    "context unavailable",
    "not returned for this event",
    "data not returned",
    "player data not returned",
    "uploaded/cached row",
    "api key missing",
    "payment required",
    "endpoint unknown",
    "status code unknown",
    "rows returned",
)

SOURCE_PLACEHOLDER_TOKENS = ("saved", "uploaded", "cached", "handoff", "fallback", "manual", "ledger", "history", "uploaded_row")

TIMESTAMP_KEYS = ("odds_last_refresh", "odds_timestamp", "price_timestamp", "odds_updated_at", "last_api_refresh_time", "line_timestamp", "locked_at_utc", "timestamp", "commence_time", "event_start_utc")
PRICE_KEYS = ("current_verified_price", "verified_price", "decimal_price", "decimal_odds", "best_price", "odds_at_pick", "odds_decimal")
LINE_KEYS = ("current_line", "spread_line", "total_line", "game_total_line", "run_line", "line", "point", "points", "handicap", "market_line", "line_point")
EVENT_ID_KEYS = ("event_id", "provider_event_id", "game_id", "fixture_id", "odds_api_event_id", "sportsdataio_event_id", "sdio_event_id", "api_football_fixture_id")
SNAPSHOT_KEYS = ("market_snapshot", "snapshot_id", "odds_snapshot", "team_snapshot", "sports_context_summary", "matchup_notes", "weather_summary", "newsapi_summary", "sportsdataio_context")
INJURY_KEYS = ("injury_report", "injuries", "lineup_status", "key_players", "sportsdataio_injury_summary", "api_football_lineup_summary", "news_injury_summary")
SECTION_KEYS = ("sports_context_summary", "matchup_notes", "weather_summary", "newsapi_summary", "sportsdataio_context", "injury_report", "injuries", "lineup_status", "team_snapshot", "player_notes", "parlay_notes", "chain_notes")


@dataclass(frozen=True)
class ExportGateSummary:
    total_rows: int
    verified_rows: int
    blocked_rows: int
    stale_rows: int
    quarantined_rows: int
    status_counts: dict[str, int]


def _clean(value: Any) -> str:
    text = str(value if value is not None else "").replace("−", "-").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


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


def _first(data: Mapping[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        text = _clean(data.get(key))
        if text and text.lower() not in {"nan", "none", "null", "n/a", "na", "--", "data unavailable", "not provided"}:
            return text
    return ""


def _number(value: Any) -> float | None:
    text = _clean(value).replace("%", "").replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _decimal_price(value: Any) -> float | None:
    num = _number(value)
    if num is None:
        return None
    if num >= 100:
        return 1.0 + num / 100.0
    if num <= -100:
        return 1.0 + 100.0 / abs(num)
    return num if num > 1.0 else None


def _parse_time(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _timestamp(data: Mapping[str, Any]) -> tuple[str, datetime | None]:
    text = _first(data, TIMESTAMP_KEYS)
    return text, _parse_time(text)


def _event_status(data: Mapping[str, Any]) -> str:
    return _first(data, ("event_status", "status", "game_status", "live_status", "market_status")).lower()


def _is_live_market(data: Mapping[str, Any]) -> bool:
    text = " ".join(_clean(data.get(k)).lower() for k in ("event_status", "status", "game_status", "live_status", "market_status"))
    return any(token in text for token in ("live", "in progress", "started"))


def _is_completed(data: Mapping[str, Any]) -> bool:
    return any(token in _event_status(data) for token in ("final", "complete", "completed", "graded", "result"))


def _is_saved_source(data: Mapping[str, Any]) -> bool:
    text = " ".join(_clean(data.get(k)).lower() for k in ("source_mode", "selected_source_key", "odds_source", "data_source", "source", "source_file", "source_label", "odds_status", "report_source", "report_source_mode"))
    return any(token in text for token in SOURCE_PLACEHOLDER_TOKENS)


def _is_live_odds(data: Mapping[str, Any]) -> bool:
    text = " ".join(_clean(data.get(k)).lower() for k in ("odds_status", "odds_source", "odds_api_status", "price_source", "provider_match_status", "api_match_status"))
    return any(token in text for token in ("live", "live_api", "odds api", "provider matched", "current provider row")) and not _is_saved_source(data)


def _is_june_stale(stamp: datetime | None, now: datetime) -> bool:
    return bool(stamp and stamp.year == now.year and stamp.month == 6 and now.month >= 7)


def _age_minutes(stamp: datetime | None, now: datetime) -> float | None:
    if stamp is None:
        return None
    return max(0.0, (now - stamp).total_seconds() / 60.0)


def _freshness_status(data: Mapping[str, Any], now: datetime) -> tuple[bool, str, str]:
    raw, stamp = _timestamp(data)
    if _is_completed(data):
        return False, "HISTORICAL_RESULT", raw
    if stamp is None:
        return False, "STALE_TIMESTAMP", raw
    if _is_june_stale(stamp, now):
        return False, "STALE_TIMESTAMP", raw
    age = _age_minutes(stamp, now)
    max_age = LIVE_MAX_AGE_MINUTES if _is_live_market(data) else PREGAME_MAX_AGE_MINUTES
    if age is None or age > max_age:
        return False, "STALE_TIMESTAMP", raw
    return True, "FRESH", raw


def _line_value(data: Mapping[str, Any]) -> float | None:
    for key in LINE_KEYS:
        value = _number(data.get(key))
        if value is not None:
            return value
    return None


def _price_value(data: Mapping[str, Any]) -> float | None:
    for key in PRICE_KEYS:
        value = _decimal_price(data.get(key))
        if value is not None:
            return value
    return None


def _has_snapshot(data: Mapping[str, Any]) -> bool:
    return any(_clean(data.get(key)) for key in SNAPSHOT_KEYS)


def _has_required_identity(data: Mapping[str, Any]) -> bool:
    event = _first(data, ("event", "game", "matchup", "event_name", "public_event"))
    selection = _first(data, ("selection", "pick", "prediction", "public_pick", "exact_bet", "recommended_action"))
    market = _first(data, ("market_type", "market", "market_name", "wager_type"))
    teams = _first(data, ("home_team", "away_team", "team", "opponent"))
    return bool(event and selection and (market or teams))


def _provider_unavailable(data: Mapping[str, Any]) -> bool:
    statuses = " ".join(_clean(data.get(k)).upper() for k in ("sportsdataio_match_status", "api_football_match_status", "news_status", "weather_status", "perplexity_status", "injury_status", "lineup_status"))
    return any(token in statuses for token in ("UNSUPPORTED", "API_KEY_MISSING", "NO_PROVIDER_EVENT_ID", "NO_MATCH", "NO_QUERY"))


def safe_provider_error(provider: str, endpoint: str, exc: BaseException | str, *, status: int | None = None, blocking: bool = True, section: str = "") -> dict[str, Any]:
    message = _clean(exc)
    message = re.sub(r"([?&](?:api_?key|key|token|authorization)=)[^&\s]+", r"\1***", message, flags=re.I)
    message = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer ***", message, flags=re.I)
    message = message[:180]
    return {
        "provider": _clean(provider),
        "endpoint": _clean(endpoint),
        "http_status": status,
        "message": message or exc.__class__.__name__ if isinstance(exc, BaseException) else message,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "blocking": bool(blocking),
        "section": _clean(section),
    }


def _clean_section_text(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    low = text.lower()
    if any(token in low for token in PLACEHOLDER_TOKENS):
        return ""
    return text


def drop_empty_public_sections(row: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(row)
    for key in SECTION_KEYS:
        if key in data:
            cleaned = _clean_section_text(data.get(key))
            if cleaned:
                data[key] = cleaned
            else:
                data.pop(key, None)
    if not any(_clean(data.get(key)) for key in INJURY_KEYS):
        data["injury_section_visible"] = "false"
    if not _has_snapshot(data):
        data["snapshot_section_visible"] = "false"
    return data


def verify_export_row(row_like: Any, *, now: datetime | None = None) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    row = drop_empty_public_sections(_row(row_like))
    row["export_gate_checked_at"] = now.isoformat(timespec="seconds")

    fresh, freshness_code, timestamp_text = _freshness_status(row, now)
    price = _price_value(row)
    line = _line_value(row)
    saved = _is_saved_source(row)
    live_odds = _is_live_odds(row)
    reasons: list[str] = []

    if _is_completed(row):
        status = STATUS_HISTORICAL
        reasons.append("HISTORICAL_RESULT")
    elif not fresh:
        status = STATUS_STALE_BLOCKED
        reasons.append(freshness_code)
    elif saved:
        status = STATUS_API_UNAVAILABLE
        reasons.append("API_FETCH_FAILED")
    elif not live_odds:
        status = STATUS_API_UNAVAILABLE
        reasons.append("API_FETCH_FAILED")
    elif price is None:
        status = STATUS_API_UNAVAILABLE
        reasons.append("API_FETCH_FAILED")
    elif not _has_required_identity(row):
        status = STATUS_EXPORT_BLOCKED
        reasons.append("EVENT_MISMATCH")
    elif not _has_snapshot(row):
        status = STATUS_STALE_BLOCKED
        reasons.append("SNAPSHOT_MISSING")
    elif line is None and any(token in _clean(row.get("market_type") or row.get("market")).lower() for token in ("spread", "total", "run", "line", "handicap")):
        status = STATUS_LINE_MOVED
        reasons.append("LINE_MOVED")
    else:
        status = STATUS_VERIFIED_LIVE if _is_live_market(row) else STATUS_VERIFIED_RECENT
        reasons.append("VERIFICATION_PASSED")

    if _provider_unavailable(row) and status in {STATUS_VERIFIED_LIVE, STATUS_VERIFIED_RECENT}:
        row["injury_lineup_status"] = STATUS_PROVIDER_UNAVAILABLE
    elif not any(_clean(row.get(key)) for key in INJURY_KEYS):
        row["injury_lineup_status"] = STATUS_PROVIDER_UNAVAILABLE

    blocked = any(code in BLOCKING_CODES for code in reasons) or "BLOCKED" in status or "NOT VERIFIED" in status or status == STATUS_PROVIDER_UNAVAILABLE
    row["verification_status"] = status
    row["export_verification_status"] = status
    row["export_blocked"] = str(bool(blocked)).lower()
    row["export_block_reason"] = "; ".join(reasons)
    row["export_timestamp_checked"] = timestamp_text
    row["odds_verified"] = str(status in {STATUS_VERIFIED_LIVE, STATUS_VERIFIED_RECENT}).lower()
    row["price_verification_status"] = status
    row["risk"] = status if blocked else "VERIFIED"
    row["risk_level"] = row["risk_label"] = row["risk"]
    row["final_decision"] = status if blocked else "VERIFIED CANDIDATE"
    row["recommended_action"] = row["consumer_action"] = row["final_decision"]
    return row


def prepare_export_rows(rows: Iterable[Any], *, require_verified: bool = True, now: datetime | None = None) -> tuple[list[dict[str, Any]], ExportGateSummary, list[dict[str, Any]]]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    prepared = [verify_export_row(row, now=now) for row in list(rows or [])]
    blocked = [row for row in prepared if str(row.get("export_blocked")).lower() == "true"]
    verified = [row for row in prepared if str(row.get("export_blocked")).lower() != "true"]
    output = verified if require_verified else prepared
    counts: dict[str, int] = {}
    for row in prepared:
        status = _clean(row.get("export_verification_status")) or "UNKNOWN"
        counts[status] = counts.get(status, 0) + 1
    summary = ExportGateSummary(
        total_rows=len(prepared),
        verified_rows=len(verified),
        blocked_rows=len(blocked),
        stale_rows=sum("STALE_TIMESTAMP" in _clean(row.get("export_block_reason")) for row in blocked),
        quarantined_rows=len(blocked),
        status_counts=counts,
    )
    return output, summary, blocked


def validate_parlay_legs(legs: Iterable[Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    rejected: list[dict[str, str]] = []
    for leg_like in legs or []:
        leg = verify_export_row(leg_like)
        event_id = _first(leg, EVENT_ID_KEYS) or _first(leg, ("event", "game", "matchup"))
        market = _first(leg, ("market_type", "market", "market_name"))
        selection = _first(leg, ("selection", "pick", "prediction", "public_pick"))
        key = (event_id.lower(), market.lower(), selection.lower())
        if str(leg.get("export_blocked")).lower() == "true":
            rejected.append({"reason": _clean(leg.get("export_block_reason")), "selection": selection})
            continue
        if key in seen:
            rejected.append({"reason": "DUPLICATE_PARLAY_LEG", "selection": selection})
            continue
        seen.add(key)
        verified.append(leg)
    playable = len(verified) >= 2
    combined_odds = None
    combined_implied = None
    combined_model = None
    ev = None
    if playable:
        combined_odds = 1.0
        combined_model = 1.0
        for leg in verified:
            combined_odds *= _price_value(leg) or 1.0
            prob = _number(leg.get("model_probability"))
            if prob is not None and prob > 1:
                prob /= 100.0
            combined_model *= prob if prob is not None and 0 <= prob <= 1 else 0.0
        combined_implied = 1.0 / combined_odds if combined_odds else None
        ev = combined_model * combined_odds - 1 if combined_odds and combined_model is not None else None
    return verified, {
        "playable": playable,
        "rejected": rejected,
        "combined_decimal_odds": combined_odds,
        "combined_implied_probability": combined_implied,
        "adjusted_model_probability": combined_model,
        "expected_value": ev,
        "correlation_warning": "independent legs only; same-event legs require supported correlation handling",
        "status": "VERIFIED PARLAY" if playable else "NO_VERIFIED_PARLAY_AVAILABLE",
    }


def blocked_pdf(summary: ExportGateSummary, blocked_rows: list[Mapping[str, Any]] | None = None, *, title: str = "ABA Signal Pro export blocked") -> bytes:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1080, 1620), (244, 235, 211))
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 1040, 1580), outline=(190, 30, 28), width=8)
    draw.text((80, 110), title, fill=(13, 14, 16))
    draw.text((80, 180), "Normal PDF export was blocked by the live verification gate.", fill=(13, 14, 16))
    draw.text((80, 240), f"Rows checked: {summary.total_rows}", fill=(13, 14, 16))
    draw.text((80, 290), f"Verified rows: {summary.verified_rows}", fill=(13, 14, 16))
    draw.text((80, 340), f"Blocked rows: {summary.blocked_rows}", fill=(13, 14, 16))
    y = 420
    for row in list(blocked_rows or [])[:8]:
        reason = _clean(row.get("export_block_reason")) or _clean(row.get("export_verification_status"))
        event = _first(row, ("event", "game", "matchup", "event_name")) or "event unavailable"
        draw.text((80, y), f"- {event}: {reason[:90]}", fill=(13, 14, 16))
        y += 52
    out = BytesIO()
    image.save(out, format="PDF")
    return out.getvalue()


def patch_magazine_renderer(module: Any) -> Any:
    if getattr(module, "_ABA_EXPORT_VERIFICATION_GATE", False):
        return module
    original_pdf = getattr(module, "render_full_magazine_book_pdf", None)
    original_pages = getattr(module, "render_full_magazine_book_pages", None)
    original_png = getattr(module, "render_full_magazine_book_png", None)
    original_zip = getattr(module, "render_full_magazine_zip", None)

    def _verified(rows: Iterable[Any]) -> tuple[list[dict[str, Any]], ExportGateSummary, list[dict[str, Any]]]:
        try:
            from autonomous_betting_agent.magazine_live_api_enrichment import enrich_rows_with_live_api_data
            rows = enrich_rows_with_live_api_data(list(rows or []))
        except Exception:
            rows = list(rows or [])
        return prepare_export_rows(rows, require_verified=True)

    if callable(original_pdf):
        def guarded_pdf(rows, *args: Any, **kwargs: Any):
            verified, summary, blocked = _verified(rows)
            if not verified:
                return blocked_pdf(summary, blocked)
            return original_pdf(verified, *args, **kwargs)
        module.render_full_magazine_book_pdf = guarded_pdf
    if callable(original_pages):
        def guarded_pages(rows, *args: Any, **kwargs: Any):
            verified, summary, blocked = _verified(rows)
            if not verified:
                return []
            return original_pages(verified, *args, **kwargs)
        module.render_full_magazine_book_pages = guarded_pages
    if callable(original_png):
        def guarded_png(rows, *args: Any, **kwargs: Any):
            verified, summary, blocked = _verified(rows)
            if not verified:
                return b""
            return original_png(verified, *args, **kwargs)
        module.render_full_magazine_book_png = guarded_png
    if callable(original_zip):
        def guarded_zip(rows, *args: Any, **kwargs: Any):
            verified, summary, blocked = _verified(rows)
            if not verified:
                return b""
            return original_zip(verified, *args, **kwargs)
        module.render_full_magazine_zip = guarded_zip
    module._ABA_EXPORT_VERIFICATION_GATE = True
    return module


def manifest(summary: ExportGateSummary, blocked_rows: list[Mapping[str, Any]]) -> str:
    return json.dumps({"summary": summary.__dict__, "blocked_reasons": [_clean(row.get("export_block_reason")) for row in blocked_rows]}, sort_keys=True)
