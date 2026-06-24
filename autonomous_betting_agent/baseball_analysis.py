"""Baseball analysis scoring helpers for ABA Signal Pro."""

from __future__ import annotations

from typing import Any, Mapping


def _num(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _bounded(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return round(max(low, min(high, value)), 4)


def _positive_from(row: Mapping[str, Any], *keys: str, scale: float = 1.0) -> float:
    total = 0.0
    for key in keys:
        value = _num(row, key)
        if value is not None:
            total += value / scale
    return total


def score_pitcher_edge(row: Mapping[str, Any]) -> float:
    score = _positive_from(row, "starting_pitcher_edge", "pitcher_edge", "f5_pitcher_edge")
    for key, weight in (("era_edge", 0.15), ("whip_edge", 0.18), ("strikeout_rate_edge", 0.08), ("k_rate_edge", 0.08), ("walk_rate_edge", 0.08)):
        value = _num(row, key)
        if value is not None:
            score += value * weight
    return _bounded(score)


def score_bullpen_edge(row: Mapping[str, Any]) -> float:
    score = _positive_from(row, "bullpen_edge", "bullpen_strength_edge", "bullpen_rest_edge")
    fatigue = _num(row, "bullpen_fatigue_risk")
    if fatigue is not None:
        score -= fatigue * 0.2
    return _bounded(score)


def score_lineup_edge(row: Mapping[str, Any]) -> float:
    score = _positive_from(row, "lineup_edge", "team_batting_form", "recent_run_production_edge", "offense_edge")
    injury = _num(row, "injury_impact", "lineup_injury_risk")
    if injury is not None:
        score -= injury * 0.2
    return _bounded(score)


def score_weather_park_edge(row: Mapping[str, Any]) -> float:
    score = _positive_from(row, "park_factor_edge", "weather_edge", "wind_edge")
    wind_out = _num(row, "wind_out_boost")
    if wind_out is not None:
        score += wind_out * 0.1
    return _bounded(score)


def score_player_prop_edge(row: Mapping[str, Any]) -> float:
    score = _positive_from(row, "player_form_edge", "handedness_edge", "pitch_type_edge", "hard_hit_edge", "barrel_rate_edge", "plate_appearance_edge", "rbi_opportunity_edge")
    strikeout = _num(row, "strikeout_risk")
    if strikeout is not None:
        score -= strikeout * 0.15
    return _bounded(score)


def score_home_run_edge(row: Mapping[str, Any]) -> float:
    score = _positive_from(row, "batter_power_edge", "barrel_rate_edge", "hard_hit_edge", "pitcher_hr_allowed_edge", "park_factor_edge", "wind_edge")
    lineup = _num(row, "lineup_position_edge")
    if lineup is not None:
        score += lineup * 0.08
    return _bounded(score)


def score_baseball_game(row: Mapping[str, Any]) -> float:
    supplied = _num(row, "baseball_analysis_score", "sports_analysis_score", "analysis_confidence")
    if supplied is not None:
        return round(max(0.0, min(100.0, supplied)), 2)
    weighted = score_pitcher_edge(row) * 30 + score_bullpen_edge(row) * 20 + score_lineup_edge(row) * 25 + score_weather_park_edge(row) * 10
    weighted += _positive_from(row, "home_away_edge", "rest_edge", "travel_edge", "first_5_edge", "full_game_edge") * 15
    return round(max(0.0, min(100.0, 50 + weighted)), 2)


def build_baseball_reason(row: Mapping[str, Any]) -> str:
    supplied = _text(row, "why_pick", "why_we_are_picking", "baseball_reason", "analysis_summary")
    if supplied:
        return supplied
    parts: list[str] = []
    if score_pitcher_edge(row) > 0:
        parts.append("the starting pitcher profile creates an edge")
    if score_bullpen_edge(row) > 0:
        parts.append("the bullpen/rest profile supports the side")
    if score_lineup_edge(row) > 0:
        parts.append("recent lineup and run-production indicators support the selection")
    if score_weather_park_edge(row) > 0:
        parts.append("park/weather context improves the setup")
    if score_player_prop_edge(row) > 0:
        parts.append("player-market matchup indicators are favorable")
    if score_home_run_edge(row) > 0:
        parts.append("power, park, and pitcher HR indicators create upside")
    if not parts:
        return "Baseball-specific support is incomplete, so this row should stay in review unless other model fields are strong."
    return "We are picking this because " + ", ".join(parts) + "."


def build_baseball_loss_reason(row: Mapping[str, Any]) -> str:
    supplied = _text(row, "why_lose", "why_it_could_lose", "baseball_loss_reason", "hidden_risk")
    if supplied:
        return supplied
    risks = ["baseball variance"]
    if score_pitcher_edge(row) <= 0:
        risks.append("starting pitcher uncertainty")
    if score_bullpen_edge(row) <= 0:
        risks.append("bullpen volatility")
    if score_lineup_edge(row) <= 0:
        risks.append("lineup or run-production risk")
    if score_weather_park_edge(row) <= 0:
        risks.append("park/weather assumptions may not help")
    return "This could lose because of " + ", ".join(risks) + "."
