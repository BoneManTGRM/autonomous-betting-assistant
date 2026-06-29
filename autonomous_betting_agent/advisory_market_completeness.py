from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

import pandas as pd

COMPLETE_MARKET = "COMPLETE_MARKET"
INCOMPLETE_MARKET = "INCOMPLETE_MARKET"
UNKNOWN_MARKET_STRUCTURE = "UNKNOWN_MARKET_STRUCTURE"
FUTURES_OUTRIGHT_INCOMPLETE = "FUTURES_OUTRIGHT_INCOMPLETE"
MISSING_MARKET_SIDE = "MISSING_MARKET_SIDE"
MISMATCHED_TOTAL_LINE = "MISMATCHED_TOTAL_LINE"
MISMATCHED_SPREAD_LINE = "MISMATCHED_SPREAD_LINE"
MIXED_SPORTSBOOK_MARKET = "MIXED_SPORTSBOOK_MARKET"
MISSING_SELECTION = "MISSING_SELECTION"
MISSING_LINE_VALUE = "MISSING_LINE_VALUE"

LINE_PAIRING_MATCHED = "LINE_PAIRING_MATCHED"
LINE_PAIRING_NOT_REQUIRED = "LINE_PAIRING_NOT_REQUIRED"
LINE_PAIRING_MISSING = "LINE_PAIRING_MISSING"
LINE_PAIRING_MISMATCHED = "LINE_PAIRING_MISMATCHED"

REAL_SPORTSBOOK = "REAL_SPORTSBOOK"
CONSENSUS_ONLY = "CONSENSUS_ONLY"
UNKNOWN_SOURCE = "UNKNOWN_SOURCE"

MARKET_COMPLETENESS_COLUMNS = [
    "advisory_market_completeness_status",
    "advisory_market_completeness_reason",
    "advisory_detected_market_sides",
    "advisory_missing_market_sides",
    "advisory_required_market_sides",
    "advisory_market_pairing_key",
    "advisory_market_side_count",
    "advisory_required_side_count",
    "advisory_line_value",
    "advisory_line_pairing_status",
    "advisory_no_vig_available",
    "advisory_no_vig_blocker_reason",
]

EVENT_FIELDS = ("event_id", "game_id", "matchup", "event", "event_name", "game")
MARKET_FIELDS = ("market_type", "market", "bet_type")
SELECTION_FIELDS = ("selection", "prediction", "pick", "public_pick", "outcome", "name", "team")
LINE_FIELDS = ("line", "point", "points", "spread", "handicap", "total", "total_points")
RAW_SPORTSBOOK_FIELDS = ("sportsbook", "bookmaker", "book", "book_name", "odds_source", "provider", "source", "sportsbook_name", "casino", "bookie")
SPORTSBOOK_FIELDS = ("advisory_normalized_sportsbook", *RAW_SPORTSBOOK_FIELDS)
ODDS_FIELDS = ("advisory_current_decimal_odds", "decimal_odds", "decimal_price", "price_decimal", "odds_decimal", "odds", "price")

H2H_ALIASES = {"h2h", "moneyline", "money_line", "ml", "winner", "match_winner", "head_to_head"}
THREE_WAY_ALIASES = {"1x2", "three_way", "3way", "3_way", "soccer_1x2", "match_result"}
TOTAL_ALIASES = {"total", "totals", "over_under", "ou", "game_total"}
SPREAD_ALIASES = {"spread", "spreads", "handicap", "asian_handicap", "puck_line", "run_line"}
FUTURE_ALIASES = {"future", "futures", "outright", "outrights", "championship", "winner_market"}
CONSENSUS_SOURCE_TOKENS = {"consensus", "consensus_average", "average", "market_average", "aggregated", "aggregate", "median", "market_consensus", "consensus_price"}
UNKNOWN_SOURCE_TOKENS = {"", "unknown", "none", "null", "nan", "n/a", "na"}

OVER_ALIASES = {"over", "o"}
UNDER_ALIASES = {"under", "u"}
DRAW_ALIASES = {"draw", "tie", "x"}
HOME_ALIASES = {"home", "home_team", "local"}
AWAY_ALIASES = {"away", "away_team", "visitor", "road"}

STATUS_REASONS = {
    COMPLETE_MARKET: "Complete same-sportsbook market detected. No-vig probability can be calculated.",
    MISSING_MARKET_SIDE: "This market is missing one or more required sides, so no-vig probability is unavailable.",
    MISMATCHED_TOTAL_LINE: "Over/under sides were found, but the total lines do not match.",
    MISMATCHED_SPREAD_LINE: "Spread sides were found, but the spread lines do not pair correctly.",
    MIXED_SPORTSBOOK_MARKET: "Market sides came from different sportsbooks. No-vig must be calculated from one sportsbook market only.",
    FUTURES_OUTRIGHT_INCOMPLETE: "Futures/outright markets are treated as incomplete unless the full outcome set is available.",
    UNKNOWN_MARKET_STRUCTURE: "Market structure is unknown. No-vig probability is unavailable until the market type is recognized.",
    MISSING_SELECTION: "Selection/side is missing or ambiguous, so no-vig probability is unavailable.",
    MISSING_LINE_VALUE: "A total/spread line value is required but missing, so no-vig probability is unavailable.",
    INCOMPLETE_MARKET: "Market is incomplete, so no-vig probability is unavailable.",
}


def _records(rows: Sequence[Mapping[str, Any]] | pd.DataFrame | None) -> list[dict[str, Any]]:
    if rows is None:
        return []
    if isinstance(rows, pd.DataFrame):
        return rows.to_dict("records")
    return [deepcopy(dict(row)) for row in rows if isinstance(row, Mapping)]


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "nat"}:
        return ""
    return " ".join(text.replace("–", "-").replace("—", "-").split())


def _norm(value: Any) -> str:
    return _clean_text(value).lower().replace("/", "_").replace("-", "_").replace(" ", "_")


def _first_value(row: Mapping[str, Any], fields: Sequence[str]) -> Any:
    for field in fields:
        value = row.get(field)
        if _clean_text(value):
            return value
    return None


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    text = _clean_text(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _format_list(values: Sequence[str]) -> str:
    return ",".join([str(value) for value in values if str(value)])


def _event_identity(row: Mapping[str, Any]) -> str:
    direct = _clean_text(_first_value(row, EVENT_FIELDS))
    if direct:
        return _norm(direct)
    home = _clean_text(_first_value(row, ("home_team", "home")))
    away = _clean_text(_first_value(row, ("away_team", "away")))
    if home or away:
        return _norm(f"{away} at {home}")
    sport = _clean_text(_first_value(row, ("sport",)))
    league = _clean_text(_first_value(row, ("league",)))
    return _norm("|".join([sport, league])) or "unknown_event"


def normalize_market_type(value: Any) -> str:
    market = _norm(value)
    if not market:
        return "unknown_market"
    if market in H2H_ALIASES:
        return "h2h"
    if market in THREE_WAY_ALIASES:
        return "1x2"
    if market in TOTAL_ALIASES:
        return "totals"
    if market in SPREAD_ALIASES:
        return "spread"
    if market in FUTURE_ALIASES:
        return "futures"
    if any(token in market for token in FUTURE_ALIASES):
        return "futures"
    if any(token in market for token in TOTAL_ALIASES):
        return "totals"
    if any(token in market for token in SPREAD_ALIASES):
        return "spread"
    if any(token in market for token in THREE_WAY_ALIASES):
        return "1x2"
    if any(token in market for token in H2H_ALIASES):
        return "h2h"
    return market


def _market_type(row: Mapping[str, Any]) -> str:
    return normalize_market_type(_first_value(row, MARKET_FIELDS))


def detect_market_side(row: Mapping[str, Any]) -> str:
    raw = _norm(_first_value(row, SELECTION_FIELDS))
    if not raw or raw == "unknown_selection":
        return ""
    first = raw.split("_")[0]
    if raw in DRAW_ALIASES or first in DRAW_ALIASES:
        return "draw"
    if raw in OVER_ALIASES or first in OVER_ALIASES:
        return "over"
    if raw in UNDER_ALIASES or first in UNDER_ALIASES:
        return "under"
    if raw in HOME_ALIASES:
        return "home"
    if raw in AWAY_ALIASES:
        return "away"
    home = _norm(row.get("home_team") or row.get("home"))
    away = _norm(row.get("away_team") or row.get("away"))
    if home and raw == home:
        return "home"
    if away and raw == away:
        return "away"
    if raw in {"team_a", "side_a", "a"}:
        return "side_a"
    if raw in {"team_b", "side_b", "b"}:
        return "side_b"
    market = _market_type(row)
    if market in {"h2h", "spread"}:
        return raw
    return raw if market not in {"1x2", "totals"} else ""


def extract_line_value(row: Mapping[str, Any]) -> float | None:
    direct = _to_float(_first_value(row, LINE_FIELDS))
    if direct is not None:
        return direct
    selection = _clean_text(_first_value(row, SELECTION_FIELDS))
    for token in selection.replace("/", " ").split():
        parsed = _to_float(token)
        if parsed is not None:
            return parsed
    return None


def _line_bucket(row: Mapping[str, Any]) -> str:
    market = _market_type(row)
    line = extract_line_value(row)
    if market == "totals":
        return "" if line is None else str(round(float(line), 6))
    if market == "spread":
        return "" if line is None else str(round(abs(float(line)), 6))
    return ""


def _sportsbook_identity(row: Mapping[str, Any]) -> str:
    return _norm(_first_value(row, SPORTSBOOK_FIELDS)) or "unknown_sportsbook"


def build_market_pairing_key(row: Mapping[str, Any]) -> str:
    return "|".join([_event_identity(row), _market_type(row), _sportsbook_identity(row)])


def _cross_sportsbook_key(row: Mapping[str, Any]) -> str:
    return "|".join([_event_identity(row), _market_type(row)])


def _source_is_real(row: Mapping[str, Any]) -> bool:
    value = row.get("advisory_is_real_sportsbook")
    if isinstance(value, bool):
        return value
    if str(value).strip().lower() in {"true", "1", "yes"}:
        return True
    source_type = str(row.get("advisory_sportsbook_source_type") or "")
    if source_type:
        return source_type == REAL_SPORTSBOOK
    raw = _norm(_first_value(row, RAW_SPORTSBOOK_FIELDS))
    if raw in UNKNOWN_SOURCE_TOKENS or raw in CONSENSUS_SOURCE_TOKENS:
        return False
    return bool(raw)


def _valid_decimal_odds(row: Mapping[str, Any]) -> bool:
    odds = _to_float(_first_value(row, ODDS_FIELDS))
    return bool(odds is not None and odds > 1.0)


def _required_sides(market: str) -> list[str]:
    if market == "1x2":
        return ["home", "draw", "away"]
    if market == "totals":
        return ["over", "under"]
    if market == "h2h":
        return ["side_a", "side_b"]
    if market == "spread":
        return ["side_a", "side_b"]
    return []


def _status_for_group(group: list[dict[str, Any]], *, mixed_sportsbook: bool = False) -> dict[str, Any]:
    first = group[0]
    market = _market_type(first)
    sides = [detect_market_side(row) for row in group]
    detected = sorted({side for side in sides if side})
    line_values = [extract_line_value(row) for row in group if extract_line_value(row) is not None]
    real = all(_source_is_real(row) for row in group)
    valid_odds = all(_valid_decimal_odds(row) for row in group)
    required = _required_sides(market)

    if not real:
        status = INCOMPLETE_MARKET
        blocker = "market_source_is_not_real_sportsbook"
        line_status = LINE_PAIRING_NOT_REQUIRED
    elif market == "futures":
        status = FUTURES_OUTRIGHT_INCOMPLETE
        blocker = "futures_market_incomplete"
        line_status = LINE_PAIRING_NOT_REQUIRED
    elif market not in {"h2h", "1x2", "totals", "spread"}:
        status = UNKNOWN_MARKET_STRUCTURE
        blocker = "unknown_market_structure"
        line_status = LINE_PAIRING_NOT_REQUIRED
    elif not all(sides):
        status = MISSING_SELECTION
        blocker = "missing_selection"
        line_status = LINE_PAIRING_NOT_REQUIRED
    elif mixed_sportsbook:
        status = MIXED_SPORTSBOOK_MARKET
        blocker = "mixed_sportsbook_market"
        line_status = LINE_PAIRING_NOT_REQUIRED
    elif market == "totals":
        raw_lines = [extract_line_value(row) for row in group]
        if any(value is None for value in raw_lines):
            status = MISSING_LINE_VALUE
            blocker = "missing_line_value"
            line_status = LINE_PAIRING_MISSING
        elif len({round(float(value), 6) for value in line_values}) > 1:
            status = MISMATCHED_TOTAL_LINE
            blocker = "mismatched_total_line"
            line_status = LINE_PAIRING_MISMATCHED
        elif not {"over", "under"}.issubset(set(detected)):
            status = MISSING_MARKET_SIDE
            blocker = "missing_required_market_side"
            line_status = LINE_PAIRING_MATCHED
        else:
            status = COMPLETE_MARKET
            blocker = "none"
            line_status = LINE_PAIRING_MATCHED
    elif market == "spread":
        raw_lines = [extract_line_value(row) for row in group]
        if any(value is None for value in raw_lines):
            status = MISSING_LINE_VALUE
            blocker = "missing_line_value"
            line_status = LINE_PAIRING_MISSING
        elif len({round(abs(float(value)), 6) for value in line_values}) > 1:
            status = MISMATCHED_SPREAD_LINE
            blocker = "mismatched_spread_line"
            line_status = LINE_PAIRING_MISMATCHED
        elif len(set(detected)) < 2:
            status = MISSING_MARKET_SIDE
            blocker = "missing_required_market_side"
            line_status = LINE_PAIRING_MATCHED
        else:
            status = COMPLETE_MARKET
            blocker = "none"
            line_status = LINE_PAIRING_MATCHED
    elif market == "1x2":
        if {"home", "draw", "away"}.issubset(set(detected)):
            status = COMPLETE_MARKET
            blocker = "none"
        else:
            status = MISSING_MARKET_SIDE
            blocker = "missing_required_market_side"
        line_status = LINE_PAIRING_NOT_REQUIRED
    else:
        if len(set(detected)) >= 2:
            status = COMPLETE_MARKET
            blocker = "none"
        else:
            status = MISSING_MARKET_SIDE
            blocker = "missing_required_market_side"
        line_status = LINE_PAIRING_NOT_REQUIRED

    if status == COMPLETE_MARKET and not valid_odds:
        status = INCOMPLETE_MARKET
        blocker = "missing_or_invalid_decimal_odds_for_required_sides"

    missing = []
    if market == "1x2":
        missing = [side for side in ["home", "draw", "away"] if side not in set(detected)]
    elif market == "totals":
        missing = [side for side in ["over", "under"] if side not in set(detected)]
    elif market in {"h2h", "spread"} and len(set(detected)) < 2:
        missing = ["opposing_side"]

    no_vig_available = bool(status == COMPLETE_MARKET and real and valid_odds)
    no_vig_blocker = "none" if no_vig_available else (blocker if blocker != "none" else "market_incomplete_no_vig_unavailable")

    return {
        "status": status,
        "reason": STATUS_REASONS.get(status, STATUS_REASONS[INCOMPLETE_MARKET]),
        "detected": detected,
        "missing": missing,
        "required": required,
        "line_value": _line_bucket(first),
        "line_status": line_status,
        "no_vig_available": no_vig_available,
        "no_vig_blocker": no_vig_blocker,
    }


def market_completeness_diagnostics(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame) -> list[dict[str, Any]]:
    rows = _records(rows_or_frame)
    groups: dict[str, list[dict[str, Any]]] = {}
    cross_groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(build_market_pairing_key(row), []).append(row)
        cross_groups.setdefault(_cross_sportsbook_key(row), []).append(row)

    complete_keys: set[str] = set()
    prelim: dict[str, dict[str, Any]] = {}
    for key, group in groups.items():
        result = _status_for_group(group)
        prelim[key] = result
        if result["status"] == COMPLETE_MARKET:
            complete_keys.add(_cross_sportsbook_key(group[0]))

    cross_has_multiple_books: dict[str, bool] = {}
    for key, group in cross_groups.items():
        books = {_sportsbook_identity(row) for row in group if _sportsbook_identity(row)}
        cross_has_multiple_books[key] = len(books) > 1

    out: list[dict[str, Any]] = []
    for row in rows:
        pairing_key = build_market_pairing_key(row)
        cross_key = _cross_sportsbook_key(row)
        result = prelim[pairing_key]
        if result["status"] == MISSING_MARKET_SIDE and cross_has_multiple_books.get(cross_key) and cross_key not in complete_keys:
            result = _status_for_group(groups[pairing_key], mixed_sportsbook=True)
        item = deepcopy(row)
        item.update({
            "advisory_market_completeness_status": result["status"],
            "advisory_market_completeness_reason": result["reason"],
            "advisory_detected_market_sides": _format_list(result["detected"]),
            "advisory_missing_market_sides": _format_list(result["missing"]),
            "advisory_required_market_sides": _format_list(result["required"]),
            "advisory_market_pairing_key": pairing_key,
            "advisory_market_side_count": len(result["detected"]),
            "advisory_required_side_count": len(result["required"]),
            "advisory_line_value": result["line_value"],
            "advisory_line_pairing_status": result["line_status"],
            "advisory_no_vig_available": bool(result["no_vig_available"]),
            "advisory_no_vig_blocker_reason": result["no_vig_blocker"],
        })
        if not item["advisory_no_vig_available"]:
            item["advisory_no_vig_implied_probability"] = None
            item["advisory_no_vig_edge"] = None
            item["advisory_no_vig_value_ratio"] = None
            item["advisory_best_price_no_vig_edge"] = None
        out.append(item)
    return out


def _is_precomputed_advisory_output(rows: Sequence[Mapping[str, Any]]) -> bool:
    return any(
        "advisory_market_completeness_status" in row
        and "advisory_playable_status" in row
        and "advisory_odds_math_mode" not in row
        for row in rows
    )


def apply_market_completeness_fields(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame) -> list[dict[str, Any]]:
    source = _records(rows_or_frame)
    if _is_precomputed_advisory_output(source):
        return source
    rows = market_completeness_diagnostics(source)
    for row in rows:
        if row.get("advisory_playable_status") == "PLAYABLE_PLUS_EV" and not bool(row.get("advisory_no_vig_available")):
            row["advisory_playable_status"] = "WATCHLIST_VALUE"
            row["advisory_playable_reason"] = str(row.get("advisory_no_vig_blocker_reason") or "market_incomplete_no_vig_unavailable")
            row["advisory_odds_value_tier"] = "WATCHLIST"
    return rows


def market_completeness_summary(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    rows = market_completeness_diagnostics(rows_or_frame)
    if not rows:
        return pd.DataFrame(columns=[
            "event", "market_type", "sportsbook_source", "line_value", "completeness_status",
            "detected_sides", "missing_sides", "required_sides", "no_vig_available",
            "blocker_reason", "row_count",
        ])
    frame = pd.DataFrame(rows)
    frame["event"] = frame[[col for col in EVENT_FIELDS if col in frame.columns][0]] if any(col in frame.columns for col in EVENT_FIELDS) else ""
    frame["market_type"] = frame[[col for col in MARKET_FIELDS if col in frame.columns][0]] if any(col in frame.columns for col in MARKET_FIELDS) else frame["advisory_market_pairing_key"].astype(str).str.split("|").str[1]
    frame["sportsbook_source"] = frame.get("advisory_normalized_sportsbook", pd.Series(index=frame.index, dtype=object)).fillna(frame.get("bookmaker", pd.Series(index=frame.index, dtype=object))).fillna(frame.get("sportsbook", pd.Series(index=frame.index, dtype=object)))
    grouped = frame.groupby([
        "event", "market_type", "sportsbook_source", "advisory_line_value", "advisory_market_completeness_status",
        "advisory_detected_market_sides", "advisory_missing_market_sides", "advisory_required_market_sides",
        "advisory_no_vig_available", "advisory_no_vig_blocker_reason",
    ], dropna=False).size().reset_index(name="row_count")
    return grouped.rename(columns={
        "advisory_line_value": "line_value",
        "advisory_market_completeness_status": "completeness_status",
        "advisory_detected_market_sides": "detected_sides",
        "advisory_missing_market_sides": "missing_sides",
        "advisory_required_market_sides": "required_sides",
        "advisory_no_vig_available": "no_vig_available",
        "advisory_no_vig_blocker_reason": "blocker_reason",
    }).sort_values(["row_count", "completeness_status"], ascending=[False, True], ignore_index=True)
