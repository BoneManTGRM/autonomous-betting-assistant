from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from .ara_filters import (
    _country_mismatch,
    _field,
    _location_primary_missing,
    dedupe_ara_records,
    parse_float,
    parse_percent,
    weather_location_mismatch,
)
from .deep_analysis import apply_deep_analysis, merge_latest_movement

BEST_BET_COLUMNS = [
    "aba_best_bet_score",
    "aba_best_bet_grade",
    "aba_best_bet_status",
    "aba_best_bet_stake_units",
    "aba_best_bet_reasons",
    "aba_best_bet_required_actions",
]

HARD_REJECT_FLAGS = {
    "classification_avoid",
    "soccer_draw_risk_extreme_30_plus",
    "soccer_draw_risk_block_ml_25_plus",
    "missing_best_price",
    "missing_data_quality",
    "data_quality_under_80",
    "low_book_coverage_under_5",
    "heavy_favorite_price_under_1_30",
    "longshot_price_over_3_00",
    "baseball_watch_low_edge_50_56",
    "weather_api_error",
    "weather_missing_for_relevant_event",
    "weather_location_mismatch",
}

WATCH_FLAGS = {
    "market_overround_high",
    "price_range_disagreement",
    "limited_book_coverage_under_8",
    "weather_forecast_not_exact",
    "weather_wind_watch",
    "weather_precip_watch",
    "soccer_draw_risk_elevated_18_plus",
    "watch_track_only",
}

POSITIVE_MOVEMENT = {"STEAM"}
NEGATIVE_MOVEMENT = {"DRIFT"}
BLANK_TEXT = {"", "nan", "none", "null", "nat"}


@dataclass(frozen=True)
class BestBetPolicy:
    min_score: float = 75.0
    strong_score: float = 88.0
    min_edge: float = 0.03
    normal_edge: float = 0.05
    strong_edge: float = 0.08
    max_stake_units: float = 0.75
    require_independent_probability: bool = True


def _split_flags(value: Any) -> list[str]:
    text = str(value or "").strip()
    if text.lower() in BLANK_TEXT:
        return []
    return [item.strip() for item in text.split(";") if item.strip() and item.strip().lower() not in BLANK_TEXT]


def _num(value: Any) -> float | None:
    parsed = parse_percent(value)
    if parsed is not None:
        return parsed
    return parse_float(value)


def _bounded(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _grade(score: float) -> str:
    if score >= 88:
        return "A"
    if score >= 75:
        return "B"
    if score >= 62:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def _combined_weather_location(row: Mapping[str, Any]) -> str | None:
    direct = _field(row, ("weather_location", "returned_weather_location"))
    if direct:
        return str(direct)
    parts = [
        _field(row, ("location_name", "weather_location_name")),
        _field(row, ("region", "weather_region")),
        _field(row, ("country", "weather_country")),
    ]
    text = ", ".join(str(part) for part in parts if part)
    return text or None


def _best_bet_location_mismatch(row: Mapping[str, Any]) -> bool:
    if weather_location_mismatch(row):
        return True
    query = _field(row, ("weather_location_query", "location_query", "weather_query"))
    returned = _combined_weather_location(row)
    tier = str(_field(row, ("weather_tier", "weather status", "weather_status")) or "").strip().lower()
    if not query or not returned or tier in {"skipped", "error"}:
        return False
    return _location_primary_missing(query, returned) or _country_mismatch(query, returned)


def _movement_score(row: pd.Series) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    signal = str(row.get("movement_signal", "")).upper()
    strength = str(row.get("movement_strength", "")).lower()
    confidence = parse_float(row.get("market_confidence_score"))

    if confidence is not None:
        if confidence >= 80:
            score += 5
            reasons.append("high_market_confidence")
        elif confidence < 45:
            score -= 8
            reasons.append("low_market_confidence")

    if signal in POSITIVE_MOVEMENT:
        if strength == "strong":
            score += 8
        elif strength == "moderate":
            score += 5
        elif strength == "small":
            score += 2
        reasons.append(f"steam_{strength or 'unknown'}")
    elif signal in NEGATIVE_MOVEMENT:
        if strength == "strong":
            score -= 10
        elif strength == "moderate":
            score -= 7
        elif strength == "small":
            score -= 3
        reasons.append(f"drift_{strength or 'unknown'}")
    return score, reasons


def _best_bet_row(row: pd.Series, policy: BestBetPolicy) -> dict[str, Any]:
    risk_flags = set(_split_flags(row.get("ara_risk_flags")))
    weather_flags = set(_split_flags(row.get("ara_weather_flags")))
    if _best_bet_location_mismatch(row.to_dict()):
        weather_flags.add("weather_location_mismatch")
    all_flags = risk_flags | weather_flags
    live_decision = str(row.get("ara_live_decision", "")).upper()
    proxy_decision = str(row.get("ara_proxy_filter_decision", "")).upper()
    requires_probability = str(row.get("ara_requires_independent_probability", "")).upper() == "YES"
    live_edge = _num(row.get("ara_live_edge"))
    deep_score = parse_float(row.get("ara_deep_score"))

    score = 50.0
    reasons: list[str] = []
    required_actions: list[str] = []

    if deep_score is not None:
        score = 0.55 * score + 0.45 * deep_score
        reasons.append("deep_score_blend")

    if proxy_decision == "PROXY_CANDIDATE":
        score += 8
        reasons.append("proxy_candidate")
    elif proxy_decision in {"PROXY_AVOID", "PROXY_WATCH_NO_ML"}:
        score -= 18
        reasons.append(proxy_decision.lower())

    if live_edge is None:
        required_actions.append("add_independent_model_probability")
        score -= 10
    elif live_edge >= policy.strong_edge:
        score += 22
        reasons.append("edge_8pct_plus")
    elif live_edge >= policy.normal_edge:
        score += 15
        reasons.append("edge_5pct_plus")
    elif live_edge >= policy.min_edge:
        score += 8
        reasons.append("edge_3pct_plus")
    else:
        score -= 12
        reasons.append("edge_under_3pct")

    for flag in sorted(all_flags & HARD_REJECT_FLAGS):
        score -= 24
        reasons.append(flag)
    for flag in sorted(all_flags & WATCH_FLAGS):
        score -= 8
        reasons.append(flag)

    movement_delta, movement_reasons = _movement_score(row)
    score += movement_delta
    reasons.extend(movement_reasons)

    score = _bounded(score)
    hard_blocked = bool(all_flags & HARD_REJECT_FLAGS) or live_decision == "AVOID"
    watch_blocked = bool(all_flags & WATCH_FLAGS)

    if hard_blocked:
        status = "REJECT"
        stake = 0.0
        required_actions.append("fix_hard_risk_flags_before_considering")
    elif policy.require_independent_probability and requires_probability:
        status = "TRACK_ONLY_NEEDS_MODEL_PROBABILITY"
        stake = 0.0
        required_actions.append("add_independent_model_probability")
    elif live_decision not in {"BET_SMALL", "BET", "BET_STRONG"}:
        status = "WATCH"
        stake = 0.0
    elif watch_blocked and score < policy.strong_score:
        status = "WATCH"
        stake = 0.0
        required_actions.append("resolve_watch_flags_or_require_stronger_edge")
    elif score >= policy.strong_score and live_edge is not None and live_edge >= policy.strong_edge:
        status = "QUALIFIED_STRONG"
        stake = min(policy.max_stake_units, 0.75)
    elif score >= policy.min_score and live_edge is not None and live_edge >= policy.normal_edge:
        status = "QUALIFIED"
        stake = min(policy.max_stake_units, 0.50)
    elif score >= policy.min_score and live_edge is not None and live_edge >= policy.min_edge:
        status = "QUALIFIED_SMALL"
        stake = min(policy.max_stake_units, 0.25)
    else:
        status = "WATCH"
        stake = 0.0

    return {
        "aba_best_bet_score": round(score, 1),
        "aba_best_bet_grade": _grade(score),
        "aba_best_bet_status": status,
        "aba_best_bet_stake_units": f"{stake:.2f}",
        "aba_best_bet_reasons": "; ".join(dict.fromkeys(reasons)),
        "aba_best_bet_required_actions": "; ".join(dict.fromkeys(required_actions)),
    }


def apply_best_bet_layer(df: pd.DataFrame, policy: BestBetPolicy = BestBetPolicy()) -> pd.DataFrame:
    enriched = apply_deep_analysis(df)
    if enriched.empty:
        for column in BEST_BET_COLUMNS:
            enriched[column] = pd.Series(dtype="object")
        return enriched
    rows = [_best_bet_row(row, policy) for _, row in enriched.iterrows()]
    best = pd.DataFrame(rows, index=enriched.index)
    for column in BEST_BET_COLUMNS:
        enriched[column] = best[column]
    return enriched


def rank_best_bets(
    predictions: pd.DataFrame,
    latest_movement: pd.DataFrame | None = None,
    *,
    top_n: int = 25,
    include_watch: bool = False,
    policy: BestBetPolicy = BestBetPolicy(),
) -> pd.DataFrame:
    frame = predictions.copy()
    if latest_movement is not None and not latest_movement.empty:
        frame = merge_latest_movement(frame, latest_movement)
    enriched = apply_best_bet_layer(frame, policy)
    ranked = dedupe_ara_records(enriched)
    status_order = {
        "QUALIFIED_STRONG": 0,
        "QUALIFIED": 1,
        "QUALIFIED_SMALL": 2,
        "WATCH": 3,
        "TRACK_ONLY_NEEDS_MODEL_PROBABILITY": 4,
        "REJECT": 5,
    }
    ranked["_status_order"] = ranked["aba_best_bet_status"].map(status_order).fillna(9)
    if not include_watch:
        ranked = ranked[ranked["aba_best_bet_status"].isin({"QUALIFIED_STRONG", "QUALIFIED", "QUALIFIED_SMALL"})]
    ranked = ranked.sort_values(["_status_order", "aba_best_bet_score"], ascending=[True, False]).head(top_n)
    return ranked.drop(columns=["_status_order"], errors="ignore")
