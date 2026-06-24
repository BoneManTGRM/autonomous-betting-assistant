"""Deterministic small-chain bet builder for ABA Signal Pro.

The builder creates candidate 2- to 4-leg chains from already-scored pick rows.
It does not fetch odds, place bets, or create random parlays. Rows must already
include analysis, odds, probability, and EV fields suitable for catalog review.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any, Iterable, Mapping

from .bet_catalog import (
    build_catalog_pick,
    normalize_decimal_odds,
)


def _text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _same_event(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    a_game = _text(a, "game", "event", "event_name", "matchup").lower()
    b_game = _text(b, "game", "event", "event_name", "matchup").lower()
    return bool(a_game and b_game and a_game == b_game)


def _market(row: Mapping[str, Any]) -> str:
    return _text(row, "bet_type", "market", "market_type", "exact_bet", "pick").lower()


def _is_high_volatility(row: Mapping[str, Any]) -> bool:
    market = _market(row)
    return any(token in market for token in ("home run", "hr", "homer", "prop", "player"))


def _leg_probability(row: Mapping[str, Any]) -> float | None:
    pick = build_catalog_pick(row)
    return pick.model_probability


def _leg_ev(row: Mapping[str, Any]) -> float | None:
    pick = build_catalog_pick(row)
    return pick.expected_value


def _playable_leg(row: Mapping[str, Any], minimum_probability: float = 0.55) -> bool:
    pick = build_catalog_pick(row)
    if pick.final_decision not in {"BET", "SMALL BET", "CHAIN ONLY"}:
        return False
    if pick.model_probability is None or pick.model_probability < minimum_probability:
        return False
    if pick.expected_value is None or pick.expected_value <= 0:
        return False
    return True


def _combined_decimal_odds(legs: tuple[Mapping[str, Any], ...]) -> float | None:
    total = 1.0
    for leg in legs:
        decimal = normalize_decimal_odds(leg)
        if decimal is None or decimal <= 1:
            return None
        total *= decimal
    return total


def _raw_probability(legs: tuple[Mapping[str, Any], ...]) -> float | None:
    total = 1.0
    for leg in legs:
        probability = _leg_probability(leg)
        if probability is None:
            return None
        total *= probability
    return total


def _correlation_penalty(legs: tuple[Mapping[str, Any], ...]) -> float:
    penalty = 0.03 * max(len(legs) - 1, 0)
    for left, right in combinations(legs, 2):
        if _same_event(left, right):
            penalty += 0.12
    penalty += sum(0.04 for leg in legs if _is_high_volatility(leg))
    return min(0.45, penalty)


def _chain_risk(legs: tuple[Mapping[str, Any], ...], adjusted_probability: float, combined_ev: float) -> float:
    base = 10 - adjusted_probability * 10
    base += 0.55 * len(legs)
    base += sum(0.85 for leg in legs if _is_high_volatility(leg))
    if combined_ev > 0:
        base -= min(combined_ev * 2, 1.25)
    return round(max(1.0, min(10.0, base)), 1)


def _chain_tier(risk_score: float) -> str:
    if risk_score <= 4:
        return "conservative"
    if risk_score <= 7:
        return "balanced"
    return "aggressive"


def _american(decimal_odds: float) -> int:
    return int(round((decimal_odds - 1) * 100)) if decimal_odds >= 2 else int(round(-100 / (decimal_odds - 1)))


def build_small_chain_candidates(
    rows: Iterable[Mapping[str, Any]],
    *,
    min_legs: int = 2,
    max_legs: int = 4,
    limit: int = 12,
    minimum_leg_probability: float = 0.55,
) -> list[dict[str, Any]]:
    """Create ranked, non-random small chain candidates.

    The function only uses rows whose individual picks are already playable, have
    positive EV, and meet the supplied minimum leg probability.
    """

    source_rows = [dict(row) for row in rows if _playable_leg(row, minimum_leg_probability)]
    candidates: list[dict[str, Any]] = []
    max_legs = max(min(max_legs, 4), min_legs)

    for size in range(max(2, min_legs), max_legs + 1):
        for legs in combinations(source_rows, size):
            decimal_odds = _combined_decimal_odds(legs)
            raw_probability = _raw_probability(legs)
            if decimal_odds is None or raw_probability is None:
                continue
            penalty = _correlation_penalty(legs)
            adjusted_probability = max(0.0, raw_probability * (1 - penalty))
            combined_ev = adjusted_probability * decimal_odds - 1
            if combined_ev <= 0:
                continue
            risk = _chain_risk(legs, adjusted_probability, combined_ev)
            tier = _chain_tier(risk)
            candidates.append(
                {
                    "pick_title": f"{tier.title()} Small Chain — {size} legs",
                    "game": " + ".join(_text(leg, "game", "event", "event_name", "matchup") or "Game" for leg in legs),
                    "sport": "MLB Baseball",
                    "bet_type": "Chain Bet",
                    "exact_bet": " + ".join(_text(leg, "exact_bet", "pick", "prediction", "selection") or "Bet" for leg in legs),
                    "sportsbook": "Best available by leg",
                    "decimal_odds": round(decimal_odds, 4),
                    "american_odds": _american(decimal_odds),
                    "combined_adjusted_probability": round(adjusted_probability, 6),
                    "raw_combined_probability": round(raw_probability, 6),
                    "correlation_penalty": round(penalty, 4),
                    "expected_value": round(combined_ev, 6),
                    "risk_score": risk,
                    "final_decision": "SMALL BET" if risk <= 7 else "AGGRESSIVE ONLY",
                    "why_pick": "Each leg passed the individual analysis and odds-value gates; the chain keeps leg count limited and remains positive EV after correlation adjustment.",
                    "why_lose": "A chain loses if any leg fails. Correlation, lineup changes, pitcher variance, or market movement can reduce the true probability.",
                    "legs": [dict(leg) for leg in legs],
                    "leg_probabilities": [round(_leg_probability(leg) or 0.0, 6) for leg in legs],
                    "leg_expected_values": [round(_leg_ev(leg) or 0.0, 6) for leg in legs],
                    "chain_tier": tier,
                }
            )

    candidates.sort(
        key=lambda row: (
            row["risk_score"],
            -row["combined_adjusted_probability"],
            -row["expected_value"],
        )
    )
    return candidates[:limit]


def best_near_double_chains(rows: Iterable[Mapping[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    """Return positive-EV chain candidates closest to 2.00 decimal odds."""

    chains = build_small_chain_candidates(rows, max_legs=3, limit=50)
    chains.sort(
        key=lambda row: (
            abs(float(row.get("decimal_odds", 99)) - 2.0),
            row.get("risk_score", 10),
            -float(row.get("expected_value", -99)),
        )
    )
    return chains[:limit]
