"""Game-script and target-payout chain helpers for ABA Signal Pro.

This module models the Portugal-style pattern: an obvious favorite may not be
worth a straight low-price play, but a coherent same-game chain can be reviewed
when every leg matches the projected script.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any, Iterable, Mapping, Sequence

from .chain_core import ChainCandidate, _make_chain, calculate_chain_ev, calculate_chain_probability
from .client_profiles import normalize_client_profile
from .odds_value import normalize_decimal_odds, row_ev, row_implied_probability, row_model_probability

REVIEW_REQUIRED = "REVIEW REQUIRED"
NO_CHAIN_RECOMMENDED = "NO CHAIN RECOMMENDED"
NO_TARGET_CHAIN = "NO TARGET-PAYOUT CHAIN RECOMMENDED"
RANDOM_LEG_REJECTED = "RANDOM LEG REJECTED"
STRAIGHT_BET_BETTER = "STRAIGHT BET BETTER THAN CHAIN"

SCRIPT_DOMINANT_FAVORITE = "Dominant favorite controls match"
SCRIPT_FAVORITE_PRESSURE = "Favorite wins but opponent creates pressure"
SCRIPT_UNDERDOG_BUS = "Underdog parks the bus"
SCRIPT_SHOOTOUT = "High-tempo shootout"
SCRIPT_DEFENSIVE = "Low-tempo defensive match"
SCRIPT_POSSESSION = "One-sided possession match"
SCRIPT_PHYSICAL = "Physical/card-heavy match"
SCRIPT_CORNERS = "Corner-heavy pressure match"
SCRIPT_LATE_PRESSURE = "Late comeback / trailing-team pressure script"
SCRIPT_BLOWOUT = "Blowout risk script"


def _text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


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


def _prob(row: Mapping[str, Any], *keys: str) -> float | None:
    value = _num(row, *keys)
    if value is None:
        return None
    if value > 1:
        value /= 100.0
    return max(0.0, min(1.0, value))


def _market(row: Mapping[str, Any]) -> str:
    return " ".join(_text(row, key).lower() for key in ("bet_type", "market", "market_type", "exact_bet", "pick", "selection"))


def _team(row: Mapping[str, Any], favorite: bool = True) -> str:
    keys = ("favorite", "favored_side", "team", "selection") if favorite else ("underdog", "opponent", "away", "dog")
    return _text(row, *keys)


@dataclass(frozen=True)
class LegExplanation:
    leg: str
    market: str
    odds: float | None
    implied_probability: float | None
    model_probability: float | None
    game_script_reason: str
    ev: float | None
    risk_contribution: float
    why_it_could_lose: str
    rejected: bool = False
    rejection_reason: str = ""


@dataclass(frozen=True)
class ScriptChainResult:
    game: str
    script: str
    legs: tuple[Mapping[str, Any], ...]
    leg_explanations: tuple[LegExplanation, ...]
    raw_combined_probability: float
    adjusted_probability: float
    total_decimal_odds: float
    ev: float
    risk_score: float
    chain_quality_score: float
    correlation_label: str
    correlation_reason: str
    why_chain: str
    why_chain_could_lose: str
    final_recommendation: str
    stake: float = 0.0
    target_payout: float = 0.0
    required_decimal_odds: float | None = None
    estimated_payout: float = 0.0
    target_distance: float = 0.0

    def as_row(self) -> dict[str, Any]:
        return {
            "game": self.game,
            "bet_type": "Game-Script Chain",
            "exact_bet": " + ".join(exp.leg for exp in self.leg_explanations if not exp.rejected),
            "decimal_odds": self.total_decimal_odds,
            "model_probability": self.adjusted_probability,
            "combined_adjusted_probability": self.adjusted_probability,
            "expected_value": self.ev,
            "risk_score": self.risk_score,
            "chain_quality_score": self.chain_quality_score,
            "correlation_label": self.correlation_label,
            "why_pick": self.why_chain,
            "why_lose": self.why_chain_could_lose,
            "final_decision": self.final_recommendation,
            "legs": list(self.legs),
        }


def classify_game_script(row: Mapping[str, Any]) -> str:
    explicit = _text(row, "game_script", "script")
    if explicit:
        return explicit
    probability = _prob(row, "favorite_probability", "model_probability", "win_probability", "probability")
    spread = _num(row, "spread", "handicap", "line")
    possession = _num(row, "possession_edge")
    corner = _num(row, "corner_edge")
    card = _num(row, "card_edge", "foul_edge")
    tempo = _num(row, "tempo", "pace", "total_expectation")
    blowout = _num(row, "blowout_risk")
    underdog_pressure = _num(row, "underdog_pressure", "dog_pressure")

    if probability is None and spread is None and possession is None:
        return REVIEW_REQUIRED
    if blowout is not None and blowout >= 0.7:
        return SCRIPT_BLOWOUT
    if card is not None and card >= 0.65:
        return SCRIPT_PHYSICAL
    if corner is not None and corner >= 0.65:
        return SCRIPT_CORNERS
    if tempo is not None and tempo >= 0.7:
        return SCRIPT_SHOOTOUT
    if tempo is not None and tempo <= 0.35:
        return SCRIPT_DEFENSIVE
    if probability is not None and probability >= 0.72 and (possession is None or possession >= 0.45):
        return SCRIPT_DOMINANT_FAVORITE
    if probability is not None and probability >= 0.62 and underdog_pressure is not None and underdog_pressure >= 0.45:
        return SCRIPT_FAVORITE_PRESSURE
    if possession is not None and possession >= 0.65:
        return SCRIPT_POSSESSION
    if underdog_pressure is not None and underdog_pressure >= 0.55:
        return SCRIPT_LATE_PRESSURE
    return SCRIPT_UNDERDOG_BUS if probability is not None and probability >= 0.60 else REVIEW_REQUIRED


def build_game_script_reason(row: Mapping[str, Any]) -> str:
    script = classify_game_script(row)
    favorite = _team(row, favorite=True) or "the favorite"
    underdog = _team(row, favorite=False) or "the opponent"
    if script == REVIEW_REQUIRED:
        return "Game-script data is incomplete, so a same-game chain requires review."
    if script == SCRIPT_DOMINANT_FAVORITE:
        return f"{favorite} projects as the stronger side and can control possession, territory, and scoring chances."
    if script == SCRIPT_FAVORITE_PRESSURE:
        return f"{favorite} projects to win, while {underdog} can still create pressure through counters, corners, or late chasing."
    if script == SCRIPT_CORNERS:
        return "Pressure and territory indicators point toward corner-related markets being relevant."
    if script == SCRIPT_PHYSICAL:
        return "Foul/card indicators point toward a physical game script."
    if script == SCRIPT_BLOWOUT:
        return "The favorite has blowout upside, but chain legs must avoid contradictory underdog scoring assumptions."
    return f"The projected script is: {script}."


def build_game_script_loss_reason(row: Mapping[str, Any]) -> str:
    return "The script chain can fail if the favorite underperforms, scores too early and slows down, the opponent does not chase, or low-threshold side markets fail despite the main result."


def identify_low_threshold_leg(row: Mapping[str, Any]) -> bool:
    market = _market(row)
    line = _num(row, "line", "threshold", "total", "points")
    low_keywords = (
        "moneyline", "draw no bet", "over 0.5", "over 1.5", "under 4.5", "corners over 1.5", "cards over 0.5",
        "shots on target", "first 5", "team total", "hit over 0.5", "total bases over 0.5", "alternate run line",
    )
    if any(keyword in market for keyword in low_keywords):
        return True
    if line is not None and line <= 1.5 and any(word in market for word in ("goal", "corner", "card", "hit", "base")):
        return True
    return False


def leg_matches_game_script(leg: Mapping[str, Any], script: str) -> bool:
    market = _market(leg)
    if script == REVIEW_REQUIRED:
        return False
    if any(word in market for word in ("moneyline", "draw no bet")):
        return True
    if script in {SCRIPT_DOMINANT_FAVORITE, SCRIPT_POSSESSION, SCRIPT_BLOWOUT}:
        return any(word in market for word in ("team goals over", "over 1.5", "favorite corners", "corners over", "cards over", "under 4.5"))
    if script in {SCRIPT_FAVORITE_PRESSURE, SCRIPT_LATE_PRESSURE}:
        return any(word in market for word in ("corners over", "cards over", "shots on target", "team goals over", "over 1.5"))
    if script == SCRIPT_PHYSICAL:
        return "card" in market or "foul" in market or "moneyline" in market
    if script == SCRIPT_CORNERS:
        return "corner" in market or "moneyline" in market
    if script == SCRIPT_SHOOTOUT:
        return "over" in market or "team total" in market or "moneyline" in market
    if script == SCRIPT_DEFENSIVE:
        return "under" in market or "draw no bet" in market or "moneyline" in market
    return False


def leg_adds_value_without_excess_risk(leg: Mapping[str, Any]) -> bool:
    probability = row_model_probability(leg)
    ev = row_ev(leg)
    if probability is None:
        return False
    if probability < 0.50:
        return False
    if ev is not None and ev < -0.05:
        return False
    risk = _num(leg, "risk_score", "blended_risk_score")
    if risk is not None and risk > 8:
        return False
    return True


def reject_random_leg(leg: Mapping[str, Any], script: str) -> tuple[bool, str]:
    if not identify_low_threshold_leg(leg):
        return True, "Leg is not low-threshold."
    if not leg_matches_game_script(leg, script):
        return True, "Leg does not match the projected game script."
    if row_model_probability(leg) is None:
        return True, "Leg is missing model probability."
    if not leg_adds_value_without_excess_risk(leg):
        return True, "Leg does not add value without excess risk."
    return False, ""


def _leg_explanation(leg: Mapping[str, Any], script: str) -> LegExplanation:
    rejected, reason = reject_random_leg(leg, script)
    market = _text(leg, "market", "market_type", "bet_type") or _market(leg)
    label = _text(leg, "exact_bet", "pick", "selection") or market or "Leg"
    probability = row_model_probability(leg)
    ev = row_ev(leg)
    decimal = normalize_decimal_odds(leg)
    implied = row_implied_probability(leg)
    if rejected:
        script_reason = reason
    elif "corner" in _market(leg):
        script_reason = "Corner leg fits pressure, territory, or trailing-team chase assumptions."
    elif "card" in _market(leg):
        script_reason = "Card leg fits pressure, defensive workload, or tactical-foul assumptions."
    elif "goal" in _market(leg) or "over" in _market(leg):
        script_reason = "Scoring leg fits the projected control or tempo script."
    elif "moneyline" in _market(leg):
        script_reason = "Winner leg anchors the projected game script."
    else:
        script_reason = "Leg matches the projected game script."
    risk = 1.0
    if probability is not None:
        risk += max(0.0, 0.70 - probability) * 5
    if ev is not None and ev < 0:
        risk += abs(ev) * 3
    return LegExplanation(
        leg=label,
        market=market,
        odds=decimal,
        implied_probability=implied,
        model_probability=probability,
        game_script_reason=script_reason,
        ev=ev,
        risk_contribution=round(min(10.0, risk), 2),
        why_it_could_lose="This leg can fail if the game script changes, the team tempo drops, or the market threshold is not reached.",
        rejected=rejected,
        rejection_reason=reason,
    )


def find_game_script_legs(row: Mapping[str, Any], available_markets: Iterable[Mapping[str, Any]]) -> list[LegExplanation]:
    script = classify_game_script(row)
    return [_leg_explanation(leg, script) for leg in available_markets]


def detect_positive_script_correlation(legs: Sequence[Mapping[str, Any]]) -> bool:
    text = " ".join(_market(leg) for leg in legs)
    pairs = [
        ("moneyline", "team goals over"),
        ("moneyline", "corners over"),
        ("moneyline", "cards over"),
        ("team goals over", "corners over"),
    ]
    return any(a in text and b in text for a, b in pairs)


def detect_bad_correlation(legs: Sequence[Mapping[str, Any]]) -> bool:
    text = " ".join(_market(leg) for leg in legs)
    bad_pairs = [
        ("blowout", "underdog goals over"),
        ("under", "shots over"),
        ("pitcher strikeouts under", "pitcher outs over"),
        ("home run", "game under"),
    ]
    return any(a in text and b in text for a, b in bad_pairs)


def explain_correlation(legs: Sequence[Mapping[str, Any]]) -> str:
    if detect_bad_correlation(legs):
        return "Contradictory correlation: at least one leg conflicts with another part of the projected script."
    if detect_positive_script_correlation(legs):
        return "Positive script correlation: the legs can be explained by the same projected game flow."
    return "Risky correlation: the legs are not clearly contradictory, but the script link should be reviewed."


def calculate_chain_quality_score(chain: ScriptChainResult | ChainCandidate | Mapping[str, Any]) -> float:
    if isinstance(chain, ScriptChainResult):
        legs = chain.legs
        explanations = chain.leg_explanations
        adjusted = chain.adjusted_probability
        ev = chain.ev
    elif isinstance(chain, ChainCandidate):
        legs = chain.legs
        explanations = tuple()
        adjusted = chain.combined_adjusted_probability
        ev = chain.combined_ev
    else:
        legs = tuple(chain.get("legs") or [])
        explanations = tuple()
        adjusted = _prob(chain, "combined_adjusted_probability", "model_probability") or 0.0
        ev = _num(chain, "expected_value", "ev") or 0.0
    score = 70.0
    if explanations:
        rejected_count = sum(1 for exp in explanations if exp.rejected)
        score -= rejected_count * 20
        score += min(10, sum(1 for exp in explanations if identify_low_threshold_leg({"market": exp.market, "exact_bet": exp.leg})) * 2)
    if detect_positive_script_correlation(legs):
        score += 10
    if detect_bad_correlation(legs):
        score -= 25
    if adjusted >= 0.50:
        score += 8
    elif adjusted < 0.30:
        score -= 10
    if ev > 0:
        score += 7
    else:
        score -= 8
    return round(max(0.0, min(100.0, score)), 1)


def chain_quality_reason(chain: ScriptChainResult | ChainCandidate | Mapping[str, Any]) -> str:
    score = calculate_chain_quality_score(chain)
    if score >= 90:
        tier = "Excellent coherent chain"
    elif score >= 75:
        tier = "Good coherent chain"
    elif score >= 60:
        tier = "Acceptable but review"
    else:
        tier = "Weak/random/reject"
    return f"Chain quality is {score:.1f}/100: {tier}."


def _eligible_leg_rows(event: Mapping[str, Any], available_markets: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    script = classify_game_script(event)
    rows = []
    for leg in available_markets:
        rejected, _ = reject_random_leg(leg, script)
        if not rejected:
            rows.append(leg)
    return rows


def build_same_game_chain_from_script(row: Mapping[str, Any], available_markets: Iterable[Mapping[str, Any]], subscriber: Mapping[str, Any] | None = None) -> ScriptChainResult | str:
    script = classify_game_script(row)
    if script == REVIEW_REQUIRED:
        return REVIEW_REQUIRED
    profile = normalize_client_profile(subscriber)
    eligible = _eligible_leg_rows(row, available_markets)
    if len(eligible) < 2:
        return NO_CHAIN_RECOMMENDED
    best: ScriptChainResult | None = None
    for size in range(2, min(profile.max_chain_legs, len(eligible), 4) + 1):
        for combo in combinations(eligible, size):
            candidate = _build_script_result(row, script, combo, subscriber)
            if candidate.chain_quality_score < 60:
                continue
            if best is None or (candidate.chain_quality_score, candidate.ev, candidate.adjusted_probability) > (best.chain_quality_score, best.ev, best.adjusted_probability):
                best = candidate
    return best if best is not None else NO_CHAIN_RECOMMENDED


def _build_script_result(event: Mapping[str, Any], script: str, legs: Sequence[Mapping[str, Any]], subscriber: Mapping[str, Any] | None = None, stake: float = 0.0, target_payout: float = 0.0) -> ScriptChainResult:
    chain = _make_chain(legs, "game-script", subscriber)
    explanations = tuple(_leg_explanation(leg, script) for leg in legs)
    correlation = explain_correlation(legs)
    quality_base = ScriptChainResult(
        game=_text(event, "game", "event", "event_name", "matchup") or "Game",
        script=script,
        legs=tuple(legs),
        leg_explanations=explanations,
        raw_combined_probability=chain.raw_combined_probability,
        adjusted_probability=chain.combined_adjusted_probability,
        total_decimal_odds=chain.total_decimal_odds,
        ev=chain.combined_ev,
        risk_score=chain.combined_risk_score,
        chain_quality_score=0.0,
        correlation_label=correlation.split(":", 1)[0],
        correlation_reason=correlation,
        why_chain="This chain is built from low-threshold legs that match the projected game script. " + build_game_script_reason(event),
        why_chain_could_lose=build_game_script_loss_reason(event),
        final_recommendation="WATCH ONLY",
        stake=stake,
        target_payout=target_payout,
        required_decimal_odds=calculate_required_decimal_odds(stake, target_payout) if stake and target_payout else None,
        estimated_payout=round(stake * chain.total_decimal_odds, 2) if stake else 0.0,
        target_distance=abs(stake * chain.total_decimal_odds - target_payout) if stake and target_payout else 0.0,
    )
    quality = calculate_chain_quality_score(quality_base)
    if quality < 60:
        decision = RANDOM_LEG_REJECTED
    elif stake and target_payout and quality >= 75 and chain.combined_ev > 0:
        decision = "TARGET PAYOUT FIT"
    elif chain.combined_ev <= 0:
        decision = "BAD VALUE"
    elif chain.combined_adjusted_probability >= 0.65:
        decision = "CHAIN ONLY"
    else:
        decision = "SMALL BET"
    return ScriptChainResult(**{**quality_base.__dict__, "chain_quality_score": quality, "final_recommendation": decision})


def calculate_required_decimal_odds(stake: float | int, target_payout: float | int) -> float | None:
    try:
        stake_float = float(stake)
        target_float = float(target_payout)
    except (TypeError, ValueError):
        return None
    if stake_float <= 0 or target_float <= 0:
        return None
    return round(target_float / stake_float, 4)


def rank_chains_by_target_payout_fit(chains: Iterable[ScriptChainResult], target_payout: float) -> list[ScriptChainResult]:
    return sorted(chains, key=lambda chain: (chain.final_recommendation not in {"TARGET PAYOUT FIT", "CHAIN ONLY", "SMALL BET"}, abs(chain.estimated_payout - target_payout), -chain.chain_quality_score, chain.risk_score))


def explain_target_payout_fit(chain: ScriptChainResult, stake: float, target_payout: float) -> str:
    required = calculate_required_decimal_odds(stake, target_payout)
    return f"Stake {stake:.2f} needs about {required:.2f} decimal odds for target payout {target_payout:.2f}; this chain is {chain.total_decimal_odds:.2f} and estimates {chain.estimated_payout:.2f}."


def build_target_payout_chain(event: Mapping[str, Any], markets: Iterable[Mapping[str, Any]], stake: float, target_payout: float, subscriber: Mapping[str, Any] | None = None, minimum_probability: float = 0.25, maximum_risk_score: float = 8.0) -> ScriptChainResult | str:
    script = classify_game_script(event)
    if script == REVIEW_REQUIRED:
        return REVIEW_REQUIRED
    eligible = _eligible_leg_rows(event, markets)
    if len(eligible) < 2:
        return NO_TARGET_CHAIN
    profile = normalize_client_profile(subscriber)
    results: list[ScriptChainResult] = []
    for size in range(2, min(profile.max_chain_legs, len(eligible), 4) + 1):
        for combo in combinations(eligible, size):
            result = _build_script_result(event, script, combo, subscriber, stake=stake, target_payout=target_payout)
            if result.final_recommendation == RANDOM_LEG_REJECTED:
                continue
            if result.adjusted_probability < minimum_probability or result.risk_score > maximum_risk_score:
                continue
            results.append(result)
    if not results:
        return NO_TARGET_CHAIN
    ranked = rank_chains_by_target_payout_fit(results, target_payout)
    best = ranked[0]
    straight_decimal = normalize_decimal_odds(event)
    if straight_decimal and stake * straight_decimal >= target_payout * 0.92 and row_ev(event) is not None and (row_ev(event) or 0) > best.ev:
        return STRAIGHT_BET_BETTER
    return best
