"""Home run and high-volatility player market helpers."""

from __future__ import annotations

from typing import Any, Mapping

from .baseball_analysis import score_home_run_edge
from .odds_value import row_ev, row_model_probability


def _text(row: Mapping[str, Any], *keys: str) -> str:
    return " ".join(str(row.get(key, "")).strip().lower() for key in keys if row.get(key) not in (None, ""))


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


def is_home_run_market(row: Mapping[str, Any]) -> bool:
    text = _text(row, "bet_type", "market", "market_type", "exact_bet", "pick", "selection")
    return any(word in text for word in ("home run", "homer", " hr"))


def score_home_run_prop(row: Mapping[str, Any]) -> float:
    supplied = _num(row, "home_run_score", "hr_score")
    if supplied is not None:
        return round(max(0.0, min(100.0, supplied)), 2)
    base = 50 + score_home_run_edge(row) * 30
    probability = row_model_probability(row)
    if probability is not None:
        base += (probability - 0.10) * 50
    ev = row_ev(row)
    if ev is not None:
        base += max(-10, min(15, ev * 20))
    return round(max(0.0, min(100.0, base)), 2)


def classify_home_run_prop(row: Mapping[str, Any]) -> str:
    probability = row_model_probability(row)
    ev = row_ev(row)
    score = score_home_run_prop(row)
    if probability is not None and probability >= 0.65 and ev is not None and ev > 0:
        return "SMALL BET"
    if ev is not None and ev > 0 and score >= 60:
        return "AGGRESSIVE ONLY"
    if is_home_run_market(row):
        return "WATCH ONLY"
    return "NO BET"


def home_run_reason(row: Mapping[str, Any]) -> str:
    if not is_home_run_market(row):
        return "This is not classified as a home run market."
    parts = []
    for label, key in [
        ("batter power", "batter_power_edge"),
        ("barrel rate", "barrel_rate_edge"),
        ("hard-hit profile", "hard_hit_edge"),
        ("pitcher HR allowed", "pitcher_hr_allowed_edge"),
        ("park factor", "park_factor_edge"),
        ("weather/wind", "wind_edge"),
    ]:
        value = _num(row, key)
        if value is not None and value > 0:
            parts.append(label)
    if not parts:
        return "Home run upside exists only as a high-volatility watchlist item because strong power-context fields are incomplete."
    return "Home run watchlist support comes from " + ", ".join(parts) + "."


def home_run_loss_reason(row: Mapping[str, Any]) -> str:
    return "Home run props can lose even with a strong matchup because they depend on limited plate appearances, pitch sequencing, weather assumptions, and one high-variance swing outcome."
