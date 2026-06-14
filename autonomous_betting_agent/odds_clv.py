from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

EVENT_COLUMNS = ("event", "event_name", "game", "match", "fixture")
GAME_ID_COLUMNS = ("sdio_game_id", "sportsdataio_game_id", "game_id", "event_id")
START_COLUMNS = ("start", "start_time", "event_start", "date", "commence_time")
PICK_COLUMNS = ("prediction", "pick", "predicted_side", "selection", "team", "player_name")
PICK_TIME_COLUMNS = ("pick_time", "entry_time", "created_at", "timestamp", "as_of")
MARKET_COLUMNS = ("market", "market_key", "prop_type", "bet_type")

ODDS_EVENT_COLUMNS = ("event", "event_name", "game", "match", "fixture")
ODDS_GAME_ID_COLUMNS = ("sdio_game_id", "sportsdataio_game_id", "game_id", "event_id")
ODDS_SELECTION_COLUMNS = ("selection", "team", "outcome", "name", "participant", "player_name")
ODDS_MARKET_COLUMNS = ("market", "market_key", "prop_type", "bet_type")
ODDS_BOOK_COLUMNS = ("bookmaker", "sportsbook", "book", "site")
ODDS_PRICE_COLUMNS = ("price", "odds", "decimal_odds", "american_odds", "best_price")
ODDS_TIME_COLUMNS = ("timestamp", "last_update", "last_updated", "created_at", "snapshot_time", "as_of")
ODDS_CLOSE_COLUMNS = ("is_closing", "closing", "is_close", "snapshot_type")

ENRICHED_ODDS_COLUMNS = [
    "odds_match_status",
    "odds_match_key",
    "odds_source",
    "odds_quality_flags",
    "entry_odds",
    "closing_odds",
    "best_price",
    "bookmaker_count",
    "market",
    "selection",
    "closing_line_value",
]


@dataclass(frozen=True)
class OddsEnrichmentReport:
    raw_rows: int
    enriched_rows: int
    matched_rows: int
    unmatched_rows: int
    ambiguous_rows: int
    missing_closing_rows: int
    missing_entry_rows: int
    average_entry_odds: float | None
    average_clv: float | None
    output_csv: str | None
    notes: list[str]


def _clean_key(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _lookup(row: Mapping[str, Any]) -> dict[str, Any]:
    return {_clean_key(str(key)): value for key, value in row.items()}


def _first(row: Mapping[str, Any], keys: Iterable[str]) -> Any:
    lookup = _lookup(row)
    for key in keys:
        value = lookup.get(_clean_key(key))
        if value not in (None, ""):
            return value
    return ""


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("@", " ").replace("vs", " ").split())


def parse_float(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "").replace("%", "")
    if not text or text.lower() in {"none", "null", "nan", "unknown"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_price(value: Any) -> float | None:
    price = parse_float(value)
    if price is None:
        return None
    if price >= 100:
        return 1.0 + price / 100.0
    if price <= -100:
        return 1.0 + 100.0 / abs(price)
    if price > 1.0:
        return price
    return None


def parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_closing_row(row: Mapping[str, Any]) -> bool:
    value = str(_first(row, ODDS_CLOSE_COLUMNS)).strip().lower()
    return value in {"1", "true", "yes", "closing", "close", "final"}


def _record_key(row: Mapping[str, Any], *, odds: bool = False) -> tuple[str, str, str, str]:
    if odds:
        game_id = str(_first(row, ODDS_GAME_ID_COLUMNS)).strip().lower()
        event = _norm(_first(row, ODDS_EVENT_COLUMNS))
        market = _norm(_first(row, ODDS_MARKET_COLUMNS))
        selection = _norm(_first(row, ODDS_SELECTION_COLUMNS))
    else:
        game_id = str(_first(row, GAME_ID_COLUMNS)).strip().lower()
        event = _norm(_first(row, EVENT_COLUMNS))
        market = _norm(_first(row, MARKET_COLUMNS))
        selection = _norm(_first(row, PICK_COLUMNS))
    primary = game_id or event
    return primary, market, selection, game_id


def _candidate_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    primary, market, selection, _ = _record_key(row, odds=True)
    return primary, market, selection


def _prediction_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    primary, market, selection, _ = _record_key(row, odds=False)
    return primary, market, selection


def _bookmaker(row: Mapping[str, Any]) -> str:
    return str(_first(row, ODDS_BOOK_COLUMNS)).strip().lower()


def _timestamp(row: Mapping[str, Any]) -> datetime | None:
    return parse_time(_first(row, ODDS_TIME_COLUMNS))


def _price(row: Mapping[str, Any]) -> float | None:
    return parse_price(_first(row, ODDS_PRICE_COLUMNS))


def _choose_entry(rows: list[Mapping[str, Any]], pick_time: datetime | None) -> tuple[float | None, str]:
    usable: list[tuple[float, datetime | None]] = []
    for row in rows:
        price = _price(row)
        if price is None:
            continue
        ts = _timestamp(row)
        if pick_time is not None and ts is not None and ts > pick_time:
            continue
        if _is_closing_row(row):
            continue
        usable.append((price, ts))
    if not usable:
        return None, "missing_entry_odds"
    return max(price for price, _ in usable), "entry_best_available_at_or_before_pick"


def _choose_closing(rows: list[Mapping[str, Any]]) -> tuple[float | None, str]:
    closing = [(row, _timestamp(row)) for row in rows if _is_closing_row(row) and _price(row) is not None]
    if closing:
        closing.sort(key=lambda item: item[1] or datetime.min.replace(tzinfo=timezone.utc))
        return _price(closing[-1][0]), "explicit_closing_odds"
    timestamped = [(row, _timestamp(row)) for row in rows if _timestamp(row) is not None and _price(row) is not None]
    if timestamped:
        timestamped.sort(key=lambda item: item[1] or datetime.min.replace(tzinfo=timezone.utc))
        return _price(timestamped[-1][0]), "latest_snapshot_as_closing_odds"
    return None, "missing_closing_odds"


def _clv(entry: float | None, close: float | None) -> float | None:
    if entry is None or close is None or entry <= 0:
        return None
    return round((entry - close) / entry, 6)


def build_odds_index(odds_rows: list[Mapping[str, Any]]) -> dict[tuple[str, str, str], list[Mapping[str, Any]]]:
    index: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for row in odds_rows:
        key = _candidate_key(row)
        if not key[0] or not key[2]:
            continue
        index.setdefault(key, []).append(row)
    return index


def enrich_prediction_with_odds(row: Mapping[str, Any], odds_index: Mapping[tuple[str, str, str], list[Mapping[str, Any]]], *, source: str = "odds_csv") -> dict[str, Any]:
    out = dict(row)
    for column in ENRICHED_ODDS_COLUMNS:
        out.setdefault(column, "")
    key = _prediction_key(row)
    candidates = odds_index.get(key, [])
    if not candidates and key[1]:
        candidates = odds_index.get((key[0], "", key[2]), [])
    if not candidates:
        out["odds_match_status"] = "unmatched"
        out["odds_quality_flags"] = "missing_odds_match"
        return out

    pick_time = parse_time(_first(row, PICK_TIME_COLUMNS))
    entry, entry_reason = _choose_entry(candidates, pick_time)
    close, close_reason = _choose_closing(candidates)
    books = sorted({book for book in (_bookmaker(item) for item in candidates) if book})
    market = str(_first(candidates[0], ODDS_MARKET_COLUMNS) or _first(row, MARKET_COLUMNS) or "").strip()
    selection = str(_first(candidates[0], ODDS_SELECTION_COLUMNS) or _first(row, PICK_COLUMNS) or "").strip()
    clv = _clv(entry, close)

    flags: list[str] = []
    if entry is None:
        flags.append("missing_entry_odds")
    if close is None:
        flags.append("missing_closing_odds")
    if len(books) < 2:
        flags.append("low_bookmaker_count")
    if pick_time is None:
        flags.append("missing_pick_time")

    out["odds_match_status"] = "matched" if not flags else "matched_with_warnings"
    out["odds_match_key"] = "|".join(key)
    out["odds_source"] = source
    out["odds_quality_flags"] = "; ".join(flags)
    out["entry_odds"] = "" if entry is None else str(round(entry, 6))
    out["closing_odds"] = "" if close is None else str(round(close, 6))
    out["best_price"] = out.get("best_price") or out["entry_odds"]
    out["bookmaker_count"] = str(len(books))
    out["market"] = out.get("market") or market
    out["selection"] = out.get("selection") or selection
    out["closing_line_value"] = "" if clv is None else str(clv)
    out["odds_entry_reason"] = entry_reason
    out["odds_closing_reason"] = close_reason
    return out


def enrich_predictions_with_odds(predictions: list[Mapping[str, Any]], odds_rows: list[Mapping[str, Any]], *, source: str = "odds_csv") -> list[dict[str, Any]]:
    odds_index = build_odds_index(odds_rows)
    return [enrich_prediction_with_odds(row, odds_index, source=source) for row in predictions]


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(rows: list[Mapping[str, Any]], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def summarize_odds_enrichment(rows: list[Mapping[str, Any]], *, output_csv: str | None = None) -> OddsEnrichmentReport:
    matched = sum(1 for row in rows if str(row.get("odds_match_status", "")).startswith("matched"))
    unmatched = sum(1 for row in rows if row.get("odds_match_status") == "unmatched")
    ambiguous = sum(1 for row in rows if row.get("odds_match_status") == "ambiguous")
    missing_entry = sum(1 for row in rows if "missing_entry_odds" in str(row.get("odds_quality_flags", "")))
    missing_closing = sum(1 for row in rows if "missing_closing_odds" in str(row.get("odds_quality_flags", "")))
    entries = [parse_price(row.get("entry_odds")) for row in rows]
    entries = [item for item in entries if item is not None]
    clvs = [parse_float(row.get("closing_line_value")) for row in rows]
    clvs = [item for item in clvs if item is not None]
    return OddsEnrichmentReport(
        raw_rows=len(rows),
        enriched_rows=len(rows),
        matched_rows=matched,
        unmatched_rows=unmatched,
        ambiguous_rows=ambiguous,
        missing_closing_rows=missing_closing,
        missing_entry_rows=missing_entry,
        average_entry_odds=None if not entries else round(sum(entries) / len(entries), 4),
        average_clv=None if not clvs else round(sum(clvs) / len(clvs), 4),
        output_csv=output_csv,
        notes=[
            "CLV is calculated as (entry_odds - closing_odds) / entry_odds.",
            "Entry odds use the best available non-closing snapshot at or before pick_time when pick_time exists.",
        ],
    )


def write_report(report: OddsEnrichmentReport, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
