from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Iterable, Mapping, Sequence

try:  # pandas is optional at import time for lightweight tests and tooling.
    import pandas as pd
except Exception:  # pragma: no cover - pandas is a project dependency, but keep import safe.
    pd = None  # type: ignore[assignment]

PLAYABLE = "Playable"
WATCHLIST = "Watchlist"
LIVE_TRIGGER_ONLY = "Live trigger only"
HIGH_RISK = "High risk"
REJECTED = "Rejected"
DATA_UNAVAILABLE = "Data unavailable"
NO_BET = "No bet"
PREDICTION_ONLY = "Prediction only"
CONSENSUS_ONLY = "consensus-only, no sportsbook-level line shopping available"
FLASH_UNAVAILABLE = "Flash bet unavailable: missing live event feed."
LEARNING_INACTIVE = "Dynamic learning inactive: insufficient completed graded history."
SAFETY_LANGUAGE = "Betting involves risk. Parlays are higher variance than straight bets. No guarantees."

EVENT_KEY_FIELDS = (
    "source_event_id",
    "sportsbook_event_id",
    "event_id",
    "fixture_id",
    "game_id",
    "public_event",
    "event",
    "event_name",
    "matchup",
    "game",
    "fixture",
)
SPORT_FIELDS = ("sport", "league", "competition")
HOME_FIELDS = ("home_team", "home", "team_home")
AWAY_FIELDS = ("away_team", "away", "team_away")
MARKET_FIELDS = ("market_type", "market", "market_name")
SELECTION_FIELDS = ("selection", "pick", "prediction", "side", "outcome")
LINE_FIELDS = ("line", "handicap", "total", "points")
SPORTSBOOK_FIELDS = ("sportsbook", "bookmaker", "book", "odds_source")
ODDS_TIMESTAMP_FIELDS = ("odds_timestamp", "price_timestamp", "signal_timestamp", "last_update", "commence_time")
LIVE_CLOCK_FIELDS = ("live_clock", "game_clock", "minute", "event_minute", "match_minute")
LIVE_SCORE_FIELDS = ("live_score", "score", "current_score")

PROBABILITY_FIELDS = (
    "model_probability",
    "advisory_probability",
    "probability",
    "confidence_probability",
    "confidence",
)
DYNAMIC_PROBABILITY_FIELDS = ("dynamic_probability", "lr_probability")
DECIMAL_ODDS_FIELDS = (
    "best_available_odds",
    "best_price",
    "decimal_odds",
    "decimal_price",
    "odds_decimal",
    "odds",
    "price",
)
AMERICAN_ODDS_FIELDS = ("american_odds", "odds_american", "moneyline", "line_price")
RAW_EV_FIELDS = ("advisory_EV", "advisory_ev", "raw_EV", "raw_ev", "expected_value", "expected_value_per_unit", "EV", "ev")
EDGE_FIELDS = ("advisory_edge", "raw_edge", "edge", "model_market_edge", "no_vig_edge")
MARKET_COMPLETE_FIELDS = ("market_completeness_status", "market_complete", "has_all_market_sides", "market_coverage_status")
STARTED_FIELDS = ("event_started", "started", "is_live", "in_progress")
STALE_FIELDS = ("odds_stale", "stale_odds", "is_stale", "price_stale")
STATUS_FIELDS = ("advisory_status", "value_status", "report_lane", "recommended_action", "consumer_action", "public_action")
BLOCKER_FIELDS = ("blocked_reason", "data_issue_reason", "advisory_blocker", "blocker", "blockers")
WARNING_FIELDS = ("warning", "warnings", "advisory_warning", "risk_warning", "correlation_warning")

_PROVIDER_MARKET_RULES: dict[str, tuple[str, ...]] = {
    "player_props_available": ("player", "player_points", "player_rebounds", "player_assists", "shots", "shots_on_target", "home run", "strikeouts", "touchdown", "receiving", "rushing", "passing"),
    "team_props_available": ("team total", "team_total", "team goals", "team points"),
    "same_game_parlay_pricing_available": ("sgp", "same game parlay", "same-game parlay", "same_game_parlay"),
    "soccer_specials_available": ("corner", "card", "throw", "free kick", "penalty", "next goal", "goal time"),
    "next_event_markets_available": ("next goal", "next basket", "next score", "next run", "next game"),
    "qualification_markets_available": ("qualify", "qualification", "advance", "advancement", "to win group", "outright", "future"),
}


def _as_rows(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if pd is not None and isinstance(frame, pd.DataFrame):
        return [dict(row) for _, row in frame.iterrows()]
    return [dict(row) for row in frame]


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "null", "nat", "n/a", "na", "--"} else text


def _lower(value: Any) -> str:
    return _text(value).lower()


def _first(row: Mapping[str, Any], fields: Sequence[str], default: str = "") -> str:
    for field in fields:
        value = _text(row.get(field))
        if value:
            return value
    return default


def _to_float(value: Any) -> float | None:
    text = _text(value)
    if not text:
        return None
    text = text.replace("%", "").replace(",", "")
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _truthy(value: Any) -> bool:
    return _lower(value) in {"1", "true", "yes", "y", "live", "started", "active", "enabled", "complete", "completed", "passed", "ready"}


def _falsey(value: Any) -> bool:
    return _lower(value) in {"0", "false", "no", "n", "inactive", "disabled", "missing", "unavailable", "failed", "blocked"}


def _probability(value: Any) -> float | None:
    num = _to_float(value)
    if num is None:
        return None
    if num > 1.0 and num <= 100.0:
        num /= 100.0
    if num < 0 or num > 1:
        return None
    return num


def american_to_decimal(odds: float | int | str | None) -> float | None:
    value = _to_float(odds)
    if value is None or value == 0:
        return None
    if value > 0:
        return 1.0 + value / 100.0
    return 1.0 + 100.0 / abs(value)


def decimal_to_american(decimal_odds: float | int | str | None) -> int | None:
    value = _to_float(decimal_odds)
    if value is None or value <= 1.0:
        return None
    if value >= 2.0:
        return int(round((value - 1.0) * 100))
    return int(round(-100.0 / (value - 1.0)))


def decimal_odds_from_row(row: Mapping[str, Any]) -> float | None:
    for field in DECIMAL_ODDS_FIELDS:
        value = _to_float(row.get(field))
        if value is not None and value > 1.0:
            return value
    for field in AMERICAN_ODDS_FIELDS:
        dec = american_to_decimal(row.get(field))
        if dec is not None and dec > 1.0:
            return dec
    return None


def implied_probability(decimal_odds: float | int | str | None) -> float | None:
    value = _to_float(decimal_odds)
    if value is None or value <= 1.0:
        return None
    return 1.0 / value


def expected_value(probability: float | None, decimal_odds: float | None) -> float | None:
    if probability is None or decimal_odds is None:
        return None
    return probability * decimal_odds - 1.0


def fair_odds(probability: float | None) -> float | None:
    if probability is None or probability <= 0:
        return None
    return 1.0 / probability


def _model_probability(row: Mapping[str, Any]) -> float | None:
    for field in PROBABILITY_FIELDS:
        prob = _probability(row.get(field))
        if prob is not None:
            return prob
    return None


def _dynamic_probability(row: Mapping[str, Any]) -> float | None:
    for field in DYNAMIC_PROBABILITY_FIELDS:
        prob = _probability(row.get(field))
        if prob is not None:
            return prob
    return None


def unique_event_key(row: Mapping[str, Any]) -> str:
    explicit = _first(row, EVENT_KEY_FIELDS)
    if explicit:
        return re.sub(r"\s+", " ", explicit).strip().lower()
    parts = [
        _first(row, SPORT_FIELDS),
        _first(row, AWAY_FIELDS),
        _first(row, HOME_FIELDS),
        _first(row, ("start_time", "commence_time", "event_start", "game_time")),
    ]
    return "|".join(_lower(part) for part in parts if _text(part))


def unique_pick_key(row: Mapping[str, Any]) -> str:
    parts = [unique_event_key(row), _first(row, MARKET_FIELDS), _first(row, SELECTION_FIELDS), _first(row, LINE_FIELDS)]
    return "|".join(_lower(part) for part in parts if _text(part))


def market_category(row: Mapping[str, Any]) -> str:
    text = " ".join(_lower(row.get(field)) for field in (*MARKET_FIELDS, *SELECTION_FIELDS))
    if any(token in text for token in ("next goal", "next basket", "next score", "next run", "next game")):
        return "live_next_event"
    if any(token in text for token in ("qualify", "advance", "advancement", "outright", "future")):
        return "qualification/advancement"
    if any(token in text for token in ("player", "shots", "rebound", "assist", "home run", "strikeout", "touchdown", "passing", "rushing", "receiving")):
        return "player_prop"
    if any(token in text for token in ("team total", "team_total", "team goals", "team points")):
        return "team_prop"
    if any(token in text for token in ("spread", "handicap", "run line")):
        return "spread/handicap"
    if any(token in text for token in ("total", "over", "under", "o/u")):
        return "total"
    if any(token in text for token in ("moneyline", "winner", "h2h", "ml")):
        return "winner"
    return _first(row, MARKET_FIELDS, default="unknown") or "unknown"


def _has_market_complete(row: Mapping[str, Any]) -> bool | None:
    for field in MARKET_COMPLETE_FIELDS:
        value = row.get(field)
        if _truthy(value):
            return True
        lower = _lower(value)
        if lower in {"complete", "full", "all sides", "yes"}:
            return True
        if lower in {"incomplete", "missing", "partial", "false", "no"}:
            return False
    if _text(row.get("missing_market_sides")):
        return False
    return None


def _line_shopping_available(row: Mapping[str, Any]) -> bool:
    sportsbook_count = _to_float(row.get("sportsbook_count"))
    if sportsbook_count is not None and sportsbook_count >= 2:
        return True
    if _truthy(row.get("line_shopping_available")):
        return True
    best = _to_float(row.get("best_available_odds"))
    worst = _to_float(row.get("worst_available_odds"))
    book = _first(row, SPORTSBOOK_FIELDS)
    return best is not None and worst is not None and bool(book) and "consensus" not in book.lower()


def _started(row: Mapping[str, Any]) -> bool:
    if any(_truthy(row.get(field)) for field in STARTED_FIELDS):
        return True
    status = " ".join(_lower(row.get(field)) for field in ("event_status", "status", "game_status"))
    return any(token in status for token in ("started", "in progress", "live", "halftime", "final"))


def _stale(row: Mapping[str, Any]) -> bool:
    if any(_truthy(row.get(field)) for field in STALE_FIELDS):
        return True
    status = " ".join(_lower(row.get(field)) for field in ("odds_freshness", "odds_freshness_status", "price_status"))
    return any(token in status for token in ("stale", "expired", "old"))


def _explicit_blockers(row: Mapping[str, Any]) -> list[str]:
    notes: list[str] = []
    for field in BLOCKER_FIELDS:
        text = _text(row.get(field))
        if text:
            notes.append(text)
    return notes


def no_bet_reasons(row: Mapping[str, Any], *, ev: float | None, edge: float | None, implied: float | None) -> list[str]:
    reasons = _explicit_blockers(row)
    if _started(row):
        reasons.append("event already started")
    if _stale(row):
        reasons.append("stale odds")
    market_complete = _has_market_complete(row)
    if market_complete is False:
        reasons.append("incomplete market")
    if implied is None:
        reasons.append("missing odds or implied probability")
    if ev is None:
        reasons.append("EV unavailable")
    elif ev <= 0:
        reasons.append("negative EV")
    if edge is None:
        reasons.append("edge unavailable")
    elif edge <= 0:
        reasons.append("negative edge")
    if _text(row.get("dynamic_probability")) and _text(row.get("raw_market_implied_probability")):
        dyn = _probability(row.get("dynamic_probability"))
        market = _probability(row.get("raw_market_implied_probability"))
        if dyn is not None and market is not None and abs(dyn - market) < 0.000001:
            reasons.append("model probability invalid or copied from market probability")
    if _lower(row.get("dynamic_signal_status")) in {"no_lr_data", "insufficient_clean_history"}:
        reasons.append("dynamic layer inactive")
    if _lower(row.get("lr_model_loaded")) == "false" or _falsey(row.get("lr_model_loaded")):
        reasons.append("insufficient learning history")
    # Do not automatically block consensus-only rows; label them as limited instead.
    return sorted(dict.fromkeys(reason for reason in reasons if reason))


def calculate_row(row: Mapping[str, Any]) -> dict[str, Any]:
    decimal = decimal_odds_from_row(row)
    raw_implied = implied_probability(decimal)
    model_prob = _model_probability(row)
    dynamic_prob = _dynamic_probability(row)
    row_ev = next((_to_float(row.get(field)) for field in RAW_EV_FIELDS if _to_float(row.get(field)) is not None), None)
    raw_ev = row_ev if row_ev is not None else expected_value(model_prob, decimal)
    raw_edge = next((_to_float(row.get(field)) for field in EDGE_FIELDS if _to_float(row.get(field)) is not None), None)
    if raw_edge is not None and abs(raw_edge) > 1.0 and abs(raw_edge) <= 100.0:
        raw_edge /= 100.0
    if raw_edge is None and model_prob is not None and raw_implied is not None:
        raw_edge = model_prob - raw_implied
    odds_book = _first(row, SPORTSBOOK_FIELDS, default="consensus_average")
    line_shopping = _line_shopping_available(row)
    status = PLAYABLE
    reasons = no_bet_reasons(row, ev=raw_ev, edge=raw_edge, implied=raw_implied)
    if reasons:
        status = NO_BET
    elif not line_shopping and "consensus" in odds_book.lower():
        status = WATCHLIST
    return {
        "unique_event_key": unique_event_key(row),
        "unique_pick_key": unique_pick_key(row),
        "market_category": market_category(row),
        "decimal_odds": decimal,
        "american_odds": decimal_to_american(decimal),
        "raw_market_implied_probability": raw_implied,
        "model_probability": model_prob,
        "dynamic_probability": dynamic_prob,
        "raw_edge": raw_edge,
        "raw_EV": raw_ev,
        "fair_odds": fair_odds(model_prob),
        "target_odds": fair_odds(model_prob),
        "sportsbook": odds_book,
        "line_shopping_available": line_shopping,
        "line_shopping_status": "available" if line_shopping else CONSENSUS_ONLY,
        "bet_status": status,
        "no_bet_reasons": "; ".join(reasons) if reasons else "",
        "odds_freshness_status": "stale" if _stale(row) else "fresh_or_unverified",
        "event_started": _started(row),
        "market_complete": _has_market_complete(row),
    }


def select_page1(rows: Sequence[Mapping[str, Any]], diagnostics: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    candidates = [dict(d) for d in diagnostics if d.get("bet_status") in {PLAYABLE, WATCHLIST} and d.get("raw_EV") is not None]
    playable = [d for d in candidates if d.get("bet_status") == PLAYABLE]
    pool = playable or candidates
    if not pool:
        return {
            "page": 1,
            "label": DATA_UNAVAILABLE,
            "bet_status": NO_BET,
            "summary": "No positive-EV straight bet found with current validated data.",
            "dynamic_learning_status": LEARNING_INACTIVE,
            "safety_language": SAFETY_LANGUAGE,
        }
    best = sorted(pool, key=lambda d: (float(d.get("raw_EV") or -999), float(d.get("raw_edge") or -999)), reverse=True)[0]
    return {
        "page": 1,
        "label": "Best straight bet",
        "bet_status": best["bet_status"],
        "unique_event_key": best["unique_event_key"],
        "unique_pick_key": best["unique_pick_key"],
        "market_category": best["market_category"],
        "sportsbook": best["sportsbook"],
        "decimal_odds": best["decimal_odds"],
        "model_probability": best["model_probability"],
        "implied_probability": best["raw_market_implied_probability"],
        "edge": best["raw_edge"],
        "EV": best["raw_EV"],
        "fair_odds": best["fair_odds"],
        "target_odds": best["target_odds"],
        "line_shopping_status": best["line_shopping_status"],
        "dynamic_learning_status": LEARNING_INACTIVE,
        "why_selected": "Selected by positive EV, edge, odds availability, freshness checks, and event-level deduplication.",
        "safety_language": SAFETY_LANGUAGE,
    }


def _parlay_correlation(legs: Sequence[Mapping[str, Any]]) -> tuple[str, str]:
    event_keys = [str(leg.get("unique_event_key") or "") for leg in legs]
    pick_keys = [str(leg.get("unique_pick_key") or "") for leg in legs]
    if len(set(pick_keys)) < len(pick_keys):
        return "market-duplicate correlated", "Rejected: duplicate market leg."
    if len(set(event_keys)) < len(event_keys):
        return "same-game correlated", "Rejected: same-game joint probability unavailable."
    return "independent", ""


def build_parlay_candidate(legs: Sequence[Mapping[str, Any]], label: str) -> dict[str, Any]:
    if len(legs) < 2:
        return {"label": label, "status": DATA_UNAVAILABLE, "rejection_reason": "fewer than two eligible legs"}
    corr, reason = _parlay_correlation(legs)
    leg_odds = [float(leg["decimal_odds"]) for leg in legs if leg.get("decimal_odds")]
    leg_probs = [float(leg["model_probability"]) for leg in legs if leg.get("model_probability") is not None]
    if len(leg_odds) != len(legs) or len(leg_probs) != len(legs):
        return {"label": label, "status": DATA_UNAVAILABLE, "correlation_rating": corr, "rejection_reason": "missing leg odds or probability"}
    parlay_odds = math.prod(leg_odds)
    implied = implied_probability(parlay_odds)
    if corr != "independent":
        return {
            "label": label,
            "status": REJECTED,
            "correlation_rating": corr,
            "combined_parlay_odds": parlay_odds,
            "parlay_implied_probability": implied,
            "rejection_reason": reason,
        }
    combined_prob = math.prod(leg_probs)
    parlay_ev = expected_value(combined_prob, parlay_odds)
    return {
        "label": label,
        "status": PLAYABLE if parlay_ev is not None and parlay_ev > 0 else REJECTED,
        "risk_tier": HIGH_RISK,
        "legs": [leg.get("unique_pick_key") for leg in legs],
        "leg_count": len(legs),
        "leg_odds": leg_odds,
        "leg_model_probabilities": leg_probs,
        "combined_parlay_odds": parlay_odds,
        "parlay_implied_probability": implied,
        "combined_model_probability": combined_prob,
        "parlay_EV": parlay_ev,
        "fair_parlay_odds": fair_odds(combined_prob),
        "target_parlay_odds": fair_odds(combined_prob),
        "correlation_rating": corr,
        "sportsbook_parlay_price_available": False,
        "estimated_parlay_price": True,
        "safety_language": SAFETY_LANGUAGE,
        "rejection_reason": "" if parlay_ev is not None and parlay_ev > 0 else "combined EV is not positive",
    }


def build_page2(diagnostics: Sequence[Mapping[str, Any]], capabilities: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    eligible = [dict(d) for d in diagnostics if d.get("bet_status") == PLAYABLE and d.get("decimal_odds") and d.get("model_probability") is not None]
    eligible = sorted(eligible, key=lambda d: float(d.get("raw_EV") or -999), reverse=True)
    conservative = build_parlay_candidate(eligible[:2], "best conservative parlay")
    aggressive = build_parlay_candidate(eligible[:4], "best aggressive parlay")
    has_live = any(cap.get("live_odds_available") for cap in capabilities)
    return {
        "page": 2,
        "best_conservative_parlay": conservative,
        "best_aggressive_parlay": aggressive,
        "best_prop_opportunity": DATA_UNAVAILABLE if not any(cap.get("player_props_available") or cap.get("team_props_available") for cap in capabilities) else WATCHLIST,
        "best_live_flash_bet_trigger": LIVE_TRIGGER_ONLY if has_live else FLASH_UNAVAILABLE,
        "team_qualification_advancement": DATA_UNAVAILABLE if not any(cap.get("qualification_markets_available") for cap in capabilities) else WATCHLIST,
        "safety_language": SAFETY_LANGUAGE,
    }


def provider_capability_audit(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        sport = _first(row, ("sport",), default="unknown").lower() or "unknown"
        grouped.setdefault(sport, []).append(row)
    capabilities: list[dict[str, Any]] = []
    for sport, sport_rows in sorted(grouped.items()):
        market_text = " | ".join(" ".join(_lower(row.get(field)) for field in (*MARKET_FIELDS, *SELECTION_FIELDS)) for row in sport_rows)
        provider_text = " | ".join(_first(row, ("provider", "api_source", "source", "data_source", "odds_source")) for row in sport_rows)
        has_live = any(_truthy(row.get(field)) for row in sport_rows for field in ("live_odds_available", "has_live_odds", "is_live", "live"))
        has_book_level = any(_line_shopping_available(row) for row in sport_rows)
        cap = {
            "sport": sport,
            "provider_source": provider_text or "unknown",
            "pregame_odds_available": any(decimal_odds_from_row(row) is not None for row in sport_rows),
            "live_odds_available": has_live,
            "sportsbook_level_odds_available": has_book_level,
            "player_props_available": any(token in market_text for token in _PROVIDER_MARKET_RULES["player_props_available"]),
            "team_props_available": any(token in market_text for token in _PROVIDER_MARKET_RULES["team_props_available"]),
            "same_game_parlay_pricing_available": any(token in market_text for token in _PROVIDER_MARKET_RULES["same_game_parlay_pricing_available"]),
            "soccer_specials_available": sport == "soccer" and any(token in market_text for token in _PROVIDER_MARKET_RULES["soccer_specials_available"]),
            "next_event_markets_available": any(token in market_text for token in _PROVIDER_MARKET_RULES["next_event_markets_available"]),
            "qualification_markets_available": any(token in market_text for token in _PROVIDER_MARKET_RULES["qualification_markets_available"]),
            "injury_news_context_available": any(_text(row.get(field)) for row in sport_rows for field in ("injury_report", "injuries", "news_summary", "newsapi_summary", "sportsdataio_injury_summary")),
            "latency_freshness_limitations": "timestamps missing" if not any(_first(row, ODDS_TIMESTAMP_FIELDS) for row in sport_rows) else "timestamped rows present",
            "unsupported_markets": "show Data unavailable instead of inventing unsupported markets",
        }
        capabilities.append(cap)
    return capabilities or [{
        "sport": "unknown",
        "provider_source": "none",
        "pregame_odds_available": False,
        "live_odds_available": False,
        "sportsbook_level_odds_available": False,
        "player_props_available": False,
        "team_props_available": False,
        "same_game_parlay_pricing_available": False,
        "soccer_specials_available": False,
        "next_event_markets_available": False,
        "qualification_markets_available": False,
        "injury_news_context_available": False,
        "latency_freshness_limitations": "no rows supplied",
        "unsupported_markets": "all",
    }]


@dataclass(frozen=True)
class TwoPageDecisionBundle:
    page1: dict[str, Any]
    page2: dict[str, Any]
    diagnostics: list[dict[str, Any]]
    provider_capabilities: list[dict[str, Any]]
    diagnostics_frame: Any = None
    provider_capabilities_frame: Any = None


def build_two_page_decision_engine(frame: Any) -> TwoPageDecisionBundle:
    rows = _as_rows(frame)
    diagnostics = [calculate_row(row) for row in rows]
    capabilities = provider_capability_audit(rows)
    page1 = select_page1(rows, diagnostics)
    page2 = build_page2(diagnostics, capabilities)
    diagnostics_frame = pd.DataFrame(diagnostics) if pd is not None else diagnostics
    capabilities_frame = pd.DataFrame(capabilities) if pd is not None else capabilities
    return TwoPageDecisionBundle(page1=page1, page2=page2, diagnostics=diagnostics, provider_capabilities=capabilities, diagnostics_frame=diagnostics_frame, provider_capabilities_frame=capabilities_frame)


def append_two_page_decision_columns(frame: Any) -> Any:
    rows = _as_rows(frame)
    diagnostics = [calculate_row(row) for row in rows]
    if pd is None:
        return [{**row, **diag} for row, diag in zip(rows, diagnostics)]
    source = frame.copy(deep=True) if isinstance(frame, pd.DataFrame) else pd.DataFrame(rows)
    diag = pd.DataFrame(diagnostics)
    for column in diag.columns:
        source[f"two_page_{column}"] = diag[column].values if len(diag) == len(source) else None
    return source
