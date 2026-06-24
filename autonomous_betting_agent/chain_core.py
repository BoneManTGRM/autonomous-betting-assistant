"""Small chain construction helpers for ABA Signal Pro.

Builds 2-4 leg chains only from supplied candidate rows. It does not create
random parlays or place bets.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any, Iterable, Mapping, Sequence

from .client_profiles import client_allows_pick, normalize_client_profile, recommended_exposure
from .decision_core import evaluate_all_gates
from .odds_value import normalize_decimal_odds, row_edge, row_ev, row_model_probability

NO_CHAIN_MESSAGE = "NO CHAIN RECOMMENDED TODAY"


@dataclass(frozen=True)
class ChainCandidate:
    chain_name: str
    category: str
    games: tuple[str, ...]
    legs: tuple[Mapping[str, Any], ...]
    leg_probabilities: tuple[float, ...]
    leg_edges: tuple[float | None, ...]
    leg_evs: tuple[float | None, ...]
    raw_combined_probability: float
    correlation_adjustment: float
    combined_adjusted_probability: float
    total_decimal_odds: float
    expected_payout: float
    combined_ev: float
    combined_risk_score: float
    recommended_stake: float
    subscriber_suitability: str
    why_chain: str
    why_chain_could_lose: str
    final_recommendation: str

    def as_row(self) -> dict[str, Any]:
        return {
            "game": " + ".join(self.games),
            "bet_type": "Chain Bet",
            "exact_bet": " + ".join(str(leg.get("exact_bet") or leg.get("pick") or leg.get("selection") or "Leg") for leg in self.legs),
            "decimal_odds": self.total_decimal_odds,
            "model_probability": self.combined_adjusted_probability,
            "combined_adjusted_probability": self.combined_adjusted_probability,
            "expected_value": self.combined_ev,
            "risk_score": self.combined_risk_score,
            "recommended_stake": self.recommended_stake,
            "why_pick": self.why_chain,
            "why_lose": self.why_chain_could_lose,
            "final_decision": self.final_recommendation,
            "legs": list(self.legs),
        }


def _text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _event_key(row: Mapping[str, Any]) -> str:
    return _text(row, "event_id", "game_id", "matchup_id", "game", "event", "event_name", "matchup").lower()


def _market_text(row: Mapping[str, Any]) -> str:
    return " ".join(str(row.get(key, "")).lower() for key in ("bet_type", "market", "market_type", "exact_bet", "pick", "selection"))


def _is_player_or_hr(row: Mapping[str, Any]) -> bool:
    market = _market_text(row)
    return any(word in market for word in ("player", "prop", "home run", "homer", " hr", "hits", "total bases", "rbi", "strikeouts", "outs"))


def calculate_chain_probability(legs: Sequence[Mapping[str, Any]]) -> float:
    probability = 1.0
    for leg in legs:
        leg_probability = row_model_probability(leg)
        if leg_probability is None:
            return 0.0
        probability *= leg_probability
    return round(max(0.0, min(1.0, probability)), 6)


def calculate_correlation_adjustment(legs: Sequence[Mapping[str, Any]]) -> float:
    adjustment = 0.03 * max(0, len(legs) - 1)
    seen: set[str] = set()
    for leg in legs:
        key = _event_key(leg)
        if key and key in seen:
            adjustment += 0.12
        if key:
            seen.add(key)
    if any(_is_player_or_hr(leg) for leg in legs):
        adjustment += 0.04
    return round(min(0.35, adjustment), 4)


def calculate_chain_decimal_odds(legs: Sequence[Mapping[str, Any]]) -> float:
    odds = 1.0
    for leg in legs:
        decimal = normalize_decimal_odds(leg)
        if decimal is None:
            return 0.0
        odds *= decimal
    return round(odds, 4)


def calculate_chain_ev(legs: Sequence[Mapping[str, Any]]) -> float:
    probability = calculate_chain_probability(legs) * (1 - calculate_correlation_adjustment(legs))
    odds = calculate_chain_decimal_odds(legs)
    if odds <= 1:
        return -1.0
    return round(probability * odds - 1, 6)


def calculate_chain_risk_score(legs: Sequence[Mapping[str, Any]], subscriber: Mapping[str, Any] | None = None) -> float:
    profile = normalize_client_profile(subscriber)
    probability = calculate_chain_probability(legs) * (1 - calculate_correlation_adjustment(legs))
    ev = calculate_chain_ev(legs)
    score = 5.0 + max(0, len(legs) - 1) * 1.0
    score += max(0.0, 0.50 - probability) * 6
    if ev > 0:
        score -= min(ev * 1.5, 1.2)
    else:
        score += min(abs(ev) * 1.5, 1.5)
    if any(_is_player_or_hr(leg) for leg in legs):
        score += 0.8
    if profile.risk_profile == "conservative":
        score += 0.7
    elif profile.risk_profile == "aggressive":
        score -= 0.5
    return round(max(1.0, min(10.0, score)), 1)


def explain_chain(legs: Sequence[Mapping[str, Any]]) -> str:
    games = [_text(leg, "game", "event", "event_name", "matchup") or "game" for leg in legs]
    return "This chain uses qualifying legs from " + ", ".join(games) + " with positive individual support before combining probabilities."


def explain_chain_loss_risk(legs: Sequence[Mapping[str, Any]]) -> str:
    return "This chain can lose if any leg fails; added legs lower combined probability and same-event or player-market correlation can increase variance."


def _leg_qualifies(row: Mapping[str, Any], subscriber: Mapping[str, Any] | None = None) -> bool:
    if not client_allows_pick(row, subscriber):
        return False
    summary = evaluate_all_gates(row, subscriber)
    return summary.final_decision in {"BET", "SMALL BET"}


def _no_duplicate_events(legs: Sequence[Mapping[str, Any]]) -> bool:
    keys = [_event_key(leg) for leg in legs if _event_key(leg)]
    return len(keys) == len(set(keys))


def _make_chain(legs: Sequence[Mapping[str, Any]], category: str, subscriber: Mapping[str, Any] | None = None) -> ChainCandidate:
    raw_probability = calculate_chain_probability(legs)
    adjustment = calculate_correlation_adjustment(legs)
    adjusted = round(raw_probability * (1 - adjustment), 6)
    odds = calculate_chain_decimal_odds(legs)
    ev = calculate_chain_ev(legs)
    risk = calculate_chain_risk_score(legs, subscriber)
    profile = normalize_client_profile(subscriber)
    recommendation = "CHAIN ONLY" if adjusted >= 0.65 and ev > 0 and risk <= 7 else "SMALL BET" if ev > 0 and risk <= 8 else "AGGRESSIVE ONLY" if profile.risk_profile == "aggressive" and ev > 0 else "WATCH ONLY"
    stake = recommended_exposure({"risk_score": risk}, subscriber, risk)
    games = tuple(_text(leg, "game", "event", "event_name", "matchup") or "Game" for leg in legs)
    return ChainCandidate(
        chain_name=f"{category.title()} {len(legs)}-Leg Chain",
        category=category,
        games=games,
        legs=tuple(legs),
        leg_probabilities=tuple(row_model_probability(leg) or 0.0 for leg in legs),
        leg_edges=tuple(row_edge(leg) for leg in legs),
        leg_evs=tuple(row_ev(leg) for leg in legs),
        raw_combined_probability=raw_probability,
        correlation_adjustment=adjustment,
        combined_adjusted_probability=adjusted,
        total_decimal_odds=odds,
        expected_payout=round(stake * odds, 4),
        combined_ev=ev,
        combined_risk_score=risk,
        recommended_stake=stake,
        subscriber_suitability=profile.risk_profile,
        why_chain=explain_chain(legs),
        why_chain_could_lose=explain_chain_loss_risk(legs),
        final_recommendation=recommendation,
    )


def _build_chains(picks: Iterable[Mapping[str, Any]], sizes: Sequence[int], category: str, subscriber: Mapping[str, Any] | None = None) -> list[ChainCandidate]:
    profile = normalize_client_profile(subscriber)
    picks_list = [pick for pick in picks if _leg_qualifies(pick, subscriber)]
    results: list[ChainCandidate] = []
    for size in sizes:
        if size > profile.max_chain_legs:
            continue
        for combo in combinations(picks_list, size):
            if not _no_duplicate_events(combo):
                continue
            chain = _make_chain(combo, category, subscriber)
            if category == "conservative" and (size != 2 or chain.combined_risk_score > 5.5):
                continue
            if category == "balanced" and (size > 3 or chain.combined_risk_score > 7.5):
                continue
            if chain.combined_ev > 0:
                results.append(chain)
    return sorted(results, key=lambda chain: (-chain.combined_ev, chain.combined_risk_score, -chain.combined_adjusted_probability))[:10]


def build_conservative_chains(picks: Iterable[Mapping[str, Any]], subscriber: Mapping[str, Any] | None = None) -> list[ChainCandidate]:
    return _build_chains(picks, (2,), "conservative", subscriber)


def build_balanced_chains(picks: Iterable[Mapping[str, Any]], subscriber: Mapping[str, Any] | None = None) -> list[ChainCandidate]:
    return _build_chains(picks, (2, 3), "balanced", subscriber)


def build_aggressive_chains(picks: Iterable[Mapping[str, Any]], subscriber: Mapping[str, Any] | None = None) -> list[ChainCandidate]:
    return _build_chains(picks, (3, 4), "aggressive", subscriber)


def build_candidate_chains(picks: Iterable[Mapping[str, Any]], subscriber: Mapping[str, Any] | None = None) -> dict[str, list[ChainCandidate] | str]:
    picks_list = list(picks)
    result = {
        "conservative": build_conservative_chains(picks_list, subscriber),
        "balanced": build_balanced_chains(picks_list, subscriber),
        "aggressive": build_aggressive_chains(picks_list, subscriber),
    }
    if not any(result.values()):
        return {"message": NO_CHAIN_MESSAGE}
    return result
