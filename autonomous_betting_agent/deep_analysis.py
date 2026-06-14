from __future__ import annotations

from typing import Any

import pandas as pd

from .ara_filters import apply_ara_decision_layer, parse_float, parse_percent

DEEP_COLUMNS = [
    "ara_deep_score",
    "ara_deep_grade",
    "ara_deep_recommendation",
    "ara_deep_primary_risk",
    "ara_deep_factors",
]

NEGATIVE_FLAGS = {
    "classification_avoid": 40,
    "soccer_draw_risk_extreme_30_plus": 35,
    "soccer_draw_risk_block_ml_25_plus": 28,
    "weather_location_mismatch": 30,
    "weather_api_error": 30,
    "weather_missing_for_relevant_event": 25,
    "data_quality_under_80": 25,
    "low_book_coverage_under_5": 20,
    "heavy_favorite_price_under_1_30": 18,
    "longshot_price_over_3_00": 18,
    "baseball_watch_low_edge_50_56": 16,
    "market_overround_high": 15,
    "price_range_disagreement": 12,
    "soccer_draw_risk_elevated_18_plus": 10,
    "limited_book_coverage_under_8": 8,
    "weather_forecast_not_exact": 8,
    "watch_track_only": 6,
    "independent_ara_probability_missing": 15,
}

WEATHER_PENALTIES = {
    "weather_wind_block": 18,
    "weather_precip_block": 18,
    "weather_condition_severe": 20,
    "weather_wind_watch": 8,
    "weather_precip_watch": 8,
}

BLANK_TEXT = {"", "nan", "none", "null", "nat"}


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


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("-", " ").replace(".", " ").split())


def _event_key(value: Any) -> str:
    text = _normalize_text(value)
    return text.replace(" vs ", " at ").replace(" v ", " at ").replace(" @ ", " at ")


def _grade(score: float) -> str:
    if score >= 82:
        return "A"
    if score >= 70:
        return "B"
    if score >= 58:
        return "C"
    if score >= 45:
        return "D"
    return "F"


def _recommendation(row: pd.Series, score: float) -> str:
    live_decision = str(row.get("ara_live_decision", "")).upper()
    requires_probability = str(row.get("ara_requires_independent_probability", "")).upper() == "YES"
    if live_decision == "AVOID" or score < 45:
        return "DEEP_AVOID"
    if requires_probability:
        return "DEEP_TRACK_ONLY_NEEDS_MODEL_PROBABILITY"
    if score >= 82 and live_decision in {"BET", "BET_SMALL", "BET_STRONG"}:
        return "DEEP_READY_STRONG"
    if score >= 70 and live_decision in {"BET", "BET_SMALL", "BET_STRONG"}:
        return "DEEP_READY"
    return "DEEP_WATCH"


def _movement_adjustment(row: pd.Series) -> tuple[float, list[str]]:
    factors: list[str] = []
    score = 0.0
    signal = str(row.get("movement_signal", "")).upper()
    strength = str(row.get("movement_strength", "")).lower()
    probability_move = parse_float(row.get("probability_move"))
    confidence = parse_float(row.get("market_confidence_score"))

    if confidence is not None:
        if confidence >= 80:
            score += 8
            factors.append("high_market_confidence")
        elif confidence < 45:
            score -= 12
            factors.append("low_market_confidence")

    if signal == "STEAM":
        if strength == "strong":
            score += 12
        elif strength == "moderate":
            score += 8
        elif strength == "small":
            score += 4
        factors.append(f"steam_{strength or 'unknown'}")
    elif signal == "DRIFT":
        if strength == "strong":
            score -= 14
        elif strength == "moderate":
            score -= 10
        elif strength == "small":
            score -= 5
        factors.append(f"drift_{strength or 'unknown'}")
    elif probability_move is not None and abs(probability_move) < 0.01:
        factors.append("market_stable")

    return score, factors


def _row_deep_score(row: pd.Series) -> dict[str, Any]:
    score = 55.0
    factors: list[str] = []
    penalties: dict[str, float] = {}

    proxy = str(row.get("ara_proxy_filter_decision", "")).upper()
    if proxy == "PROXY_CANDIDATE":
        score += 10
        factors.append("proxy_candidate")
    elif proxy in {"PROXY_AVOID", "PROXY_WATCH_NO_ML"}:
        score -= 20
        factors.append(proxy.lower())

    live_edge = _num(row.get("ara_live_edge"))
    if live_edge is not None:
        if live_edge >= 0.08:
            score += 18
            factors.append("edge_8pct_plus")
        elif live_edge >= 0.05:
            score += 12
            factors.append("edge_5pct_plus")
        elif live_edge >= 0.03:
            score += 6
            factors.append("edge_3pct_plus")

    books = parse_float(row.get("Books"))
    if books is None:
        books = parse_float(row.get("bookmaker_count"))
    if books is not None:
        score += min(10, max(0, books - 5))
        if books >= 10:
            factors.append("broad_book_coverage")

    for flag in _split_flags(row.get("ara_risk_flags")):
        penalty = NEGATIVE_FLAGS.get(flag, 0)
        if penalty:
            score -= penalty
            penalties[flag] = penalty
            factors.append(flag)

    for flag in _split_flags(row.get("ara_weather_flags")):
        penalty = WEATHER_PENALTIES.get(flag, 0)
        if penalty:
            score -= penalty
            penalties[flag] = penalty
            factors.append(flag)

    movement_score, movement_factors = _movement_adjustment(row)
    score += movement_score
    factors.extend(movement_factors)

    score = _bounded(score)
    primary_risk = max(penalties, key=penalties.get) if penalties else "none"
    return {
        "ara_deep_score": round(score, 1),
        "ara_deep_grade": _grade(score),
        "ara_deep_recommendation": _recommendation(row, score),
        "ara_deep_primary_risk": primary_risk,
        "ara_deep_factors": "; ".join(dict.fromkeys(factors)),
    }


def apply_deep_analysis(df: pd.DataFrame) -> pd.DataFrame:
    enriched = apply_ara_decision_layer(df)
    if enriched.empty:
        for column in DEEP_COLUMNS:
            enriched[column] = pd.Series(dtype="object")
        return enriched
    deep_rows = [_row_deep_score(row) for _, row in enriched.iterrows()]
    deep = pd.DataFrame(deep_rows, index=enriched.index)
    for column in DEEP_COLUMNS:
        enriched[column] = deep[column]
    return enriched


def merge_latest_movement(predictions: pd.DataFrame, latest_movement: pd.DataFrame) -> pd.DataFrame:
    """Merge movement into prediction rows without unsafe outcome-only joins."""
    if predictions.empty or latest_movement.empty:
        return predictions.copy()
    left = predictions.copy()
    right = latest_movement.copy()
    prediction_col = "Prediction" if "Prediction" in left.columns else "prediction" if "prediction" in left.columns else None
    if prediction_col is None or "outcome" not in right.columns:
        return left

    if "event_id" in left.columns and "event_id" in right.columns:
        return left.merge(
            right,
            left_on=["event_id", prediction_col],
            right_on=["event_id", "outcome"],
            how="left",
            suffixes=("", "_movement"),
        )

    if "Event" in left.columns and {"away_team", "home_team"}.issubset(right.columns):
        left["_event_key"] = left["Event"].apply(_event_key)
        left["_prediction_key"] = left[prediction_col].apply(_normalize_text)
        right["_event_key"] = (right["away_team"].astype(str) + " at " + right["home_team"].astype(str)).apply(_event_key)
        right["_prediction_key"] = right["outcome"].apply(_normalize_text)
        merged = left.merge(right, on=["_event_key", "_prediction_key"], how="left", suffixes=("", "_movement"))
        return merged.drop(columns=["_event_key", "_prediction_key"])

    return left
