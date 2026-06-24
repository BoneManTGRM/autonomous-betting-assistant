"""Chain Bet Optimizer v2.

This module is intentionally conservative. It is designed to recommend fewer,
higher-quality chains by comparing each chain against the straight option,
scoring every leg, rejecting filler exposure, and explaining rejection reasons.

No function places bets or guarantees outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from math import prod
from typing import Any, Mapping, Sequence

NO_CHAIN_RECOMMENDED = "NO CHAIN RECOMMENDED TODAY"
STRAIGHT_BET_BETTER = "STRAIGHT BET BETTER THAN CHAIN"
WATCH_ONLY = "WATCH ONLY"
SMALL_CHAIN = "SMALL CHAIN"
BALANCED_CHAIN = "BALANCED CHAIN"
AGGRESSIVE_ONLY = "AGGRESSIVE ONLY"
GOOD_PAYOUT_BAD_CHAIN = "GOOD PAYOUT FIT, BAD CHAIN — WATCH ONLY"
SAFETY_WARNING = "This is not a guaranteed result. Chain bets can lose if any leg fails."

POSITIVE_CORRELATION = "Positive script correlation"
NEUTRAL_CORRELATION = "Neutral correlation"
RISKY_CORRELATION = "Risky correlation"
CONTRADICTORY_CORRELATION = "Contradictory correlation"


@dataclass(frozen=True)
class ChainLegScore:
    leg_name: str
    market: str
    selection: str
    decimal_odds: float | None
    model_probability: float | None
    implied_probability: float | None
    edge: float | None
    ev: float | None
    purpose_score: float
    correlation_score: float
    volatility_score: float
    dependency_risk: float
    leg_quality_score: float
    accepted: bool
    rejection_reason: str
    why_leg_belongs: str
    why_leg_could_fail: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ChainComparison:
    straight_pick: str
    straight_probability: float | None
    straight_decimal_odds: float | None
    straight_ev: float | None
    straight_risk_score: float | None
    chain_probability: float | None
    chain_decimal_odds: float | None
    chain_ev: float | None
    chain_risk_score: float | None
    probability_drop: float | None
    payout_gain: float | None
    risk_increase: float | None
    ev_delta: float | None
    straight_bet_better: bool
    chain_better_reason: str
    final_recommendation: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ChainKillerResult:
    has_killer: bool
    killer_reasons: tuple[str, ...] = field(default_factory=tuple)
    can_override: bool = False
    override_note: str = ""
    final_block_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class CorrelationResult:
    correlation_label: str
    correlation_score: float
    correlation_reason: str
    positive_correlation_factors: tuple[str, ...] = field(default_factory=tuple)
    bad_correlation_factors: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class TargetPayoutFit:
    required_decimal_odds: float | None
    actual_chain_decimal_odds: float | None
    estimated_payout: float | None
    target_distance: float | None
    target_fit_label: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ChainOptimizerResult:
    straight_pick: Mapping[str, Any] | None
    accepted_legs: tuple[ChainLegScore, ...]
    rejected_legs: tuple[ChainLegScore, ...]
    comparison: ChainComparison
    killers: ChainKillerResult
    correlation: CorrelationResult
    target_payout_fit: TargetPayoutFit | None
    chain_quality_score: float
    probability_floor: float
    final_recommendation: str
    final_explanation: str
    safety_warning: str = SAFETY_WARNING

    def as_dict(self) -> dict[str, Any]:
        return {
            "straight_pick": dict(self.straight_pick or {}),
            "accepted_legs": [leg.as_dict() for leg in self.accepted_legs],
            "rejected_legs": [leg.as_dict() for leg in self.rejected_legs],
            "comparison": self.comparison.as_dict(),
            "killers": self.killers.as_dict(),
            "correlation": self.correlation.as_dict(),
            "target_payout_fit": None if self.target_payout_fit is None else self.target_payout_fit.as_dict(),
            "chain_quality_score": self.chain_quality_score,
            "probability_floor": self.probability_floor,
            "final_recommendation": self.final_recommendation,
            "final_explanation": self.final_explanation,
            "safety_warning": self.safety_warning,
        }


def _text(row: Mapping[str, Any] | None, *keys: str, default: str = "") -> str:
    if not row:
        return default
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _num(row: Mapping[str, Any] | None, *keys: str) -> float | None:
    if not row:
        return None
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _prob(row: Mapping[str, Any] | None, *keys: str) -> float | None:
    value = _num(row, *keys)
    if value is None:
        return None
    if value > 1:
        value /= 100.0
    return max(0.0, min(1.0, value))


def _odds(row: Mapping[str, Any] | None) -> float | None:
    value = _num(row, "decimal_odds", "decimal_price", "odds_at_pick", "best_price", "current_decimal_odds")
    if value and value > 1:
        return value
    american = _num(row, "american_odds", "odds")
    if american is None or american == 0:
        return None
    return 1 + american / 100 if american > 0 else 1 + 100 / abs(american)


def _model_probability(row: Mapping[str, Any] | None) -> float | None:
    return _prob(row, "model_probability", "learned_model_probability", "probability", "projected_probability", "final_probability_clean")


def _implied_probability(row: Mapping[str, Any] | None) -> float | None:
    explicit = _prob(row, "implied_probability", "market_implied_probability")
    if explicit is not None:
        return explicit
    decimal = _odds(row)
    return None if not decimal or decimal <= 1 else 1.0 / decimal


def _ev(row: Mapping[str, Any] | None) -> float | None:
    supplied = _num(row, "expected_value", "ev", "expected_value_per_unit", "profit_expected_value")
    if supplied is not None:
        return supplied
    probability = _model_probability(row)
    decimal = _odds(row)
    if probability is None or decimal is None:
        return None
    return probability * decimal - 1.0


def _risk(row: Mapping[str, Any] | None) -> float | None:
    supplied = _num(row, "risk_score", "blended_risk_score", "combined_risk_score")
    if supplied is not None:
        return max(1.0, min(10.0, supplied))
    probability = _model_probability(row)
    if probability is None:
        return None
    return round(max(1.0, min(10.0, 10 - probability * 8)), 2)


def _market(row: Mapping[str, Any] | None) -> str:
    return _text(row, "market", "market_type", "bet_type", default="").lower()


def _selection(row: Mapping[str, Any] | None) -> str:
    return _text(row, "selection", "prediction", "pick", "exact_bet", default="")


def _leg_name(row: Mapping[str, Any] | None) -> str:
    return _text(row, "leg_name", "pick_title", "title") or f"{_selection(row)} {_market(row)}".strip() or "Unnamed leg"


def _is_hr_leg(row: Mapping[str, Any] | None) -> bool:
    text = f"{_market(row)} {_selection(row)}".lower()
    return "home run" in text or " hr" in f" {text}" or "homer" in text


def _is_player_prop(row: Mapping[str, Any] | None) -> bool:
    text = f"{_market(row)} {_selection(row)}".lower()
    markers = ("player", "prop", "hits", "total bases", "rbi", "runs", "strikeout", "home run")
    return any(marker in text for marker in markers)


def _low_threshold(row: Mapping[str, Any] | None) -> bool:
    text = f"{_market(row)} {_selection(row)}".lower()
    return any(token in text for token in ("over 0.5", "over 1.5", "under 4.5", "draw no bet", "dnb", "moneyline", "1x2", "cards over 0.5", "corners over 1.5"))


def _is_duplicate_market(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return _market(left) == _market(right) and _selection(left).lower() == _selection(right).lower()


def _script_text(script: Any) -> str:
    return str(script or "").lower()


def score_leg_purpose(leg: Mapping[str, Any], event: Mapping[str, Any] | None = None, script: Any = None) -> float:
    score = 35.0
    text = f"{_market(leg)} {_selection(leg)}".lower()
    script_text = _script_text(script) + " " + _text(event, "script", "game_script", default="").lower()
    if _low_threshold(leg):
        score += 18
    if (_ev(leg) or 0) >= 0:
        score += 14
    if (_model_probability(leg) or 0) >= 0.60:
        score += 14
    if "favorite" in script_text and any(token in text for token in ("moneyline", "1x2", "team goals over 1.5", "over 1.5")):
        score += 14
    if "pressure" in script_text and "corner" in text:
        score += 10
    if "physical" in script_text and "card" in text:
        score += 10
    if _is_player_prop(leg):
        score -= 10
    if _is_hr_leg(leg):
        score -= 18
    if "random" in text or "filler" in text:
        score -= 40
    if (_ev(leg) or 0) < -0.05:
        score -= 22
    return round(max(0.0, min(100.0, score)), 2)


def score_leg_ev_quality(leg: Mapping[str, Any]) -> float:
    ev = _ev(leg)
    edge = None
    probability = _model_probability(leg)
    implied = _implied_probability(leg)
    if probability is not None and implied is not None:
        edge = probability - implied
    if ev is None and edge is None:
        return 45.0
    base = 50.0
    if ev is not None:
        base += max(-30.0, min(30.0, ev * 220.0))
    if edge is not None:
        base += max(-15.0, min(15.0, edge * 120.0))
    return round(max(0.0, min(100.0, base)), 2)


def score_leg_probability_quality(leg: Mapping[str, Any]) -> float:
    probability = _model_probability(leg)
    if probability is None:
        return 35.0
    return round(max(0.0, min(100.0, probability * 100.0)), 2)


def score_leg_volatility(leg: Mapping[str, Any]) -> float:
    score = 20.0
    if _is_player_prop(leg):
        score += 18
    if _is_hr_leg(leg):
        score += 30
    decimal = _odds(leg)
    if decimal and decimal >= 3.0:
        score += 20
    if decimal and decimal <= 1.35:
        score -= 6
    if _low_threshold(leg):
        score -= 8
    return round(max(0.0, min(100.0, score)), 2)


def score_leg_dependency_risk(leg: Mapping[str, Any], existing_legs: Sequence[Mapping[str, Any]] | None = None) -> float:
    score = 15.0
    market = _market(leg)
    selection = _selection(leg).lower()
    for existing in existing_legs or []:
        if _is_duplicate_market(leg, existing):
            score += 55
        elif _market(existing) == market:
            score += 22
        elif selection and selection in _selection(existing).lower():
            score += 12
    if "lineup" in f"{market} {selection}" or "injury" in f"{market} {selection}":
        score += 20
    return round(max(0.0, min(100.0, score)), 2)


def score_correlation_quality(legs: Sequence[Mapping[str, Any]], script: Any = None) -> CorrelationResult:
    joined = " | ".join(f"{_market(leg)} {_selection(leg)}".lower() for leg in legs)
    script_text = _script_text(script)
    positives: list[str] = []
    bad: list[str] = []

    if ("moneyline" in joined or "1x2" in joined) and ("team goals over 1.5" in joined or "over 1.5" in joined):
        positives.append("Favorite result paired with low-threshold team scoring support")
    if "corner" in joined and ("pressure" in script_text or "favorite" in script_text):
        positives.append("Corner leg matches pressure/favorite script")
    if "card" in joined and ("physical" in script_text or "underdog" in script_text):
        positives.append("Card leg matches physical/underdog script")
    if "under 0.5" in joined and ("moneyline" in joined or "1x2" in joined):
        bad.append("Favorite/result leg conflicts with under 0.5 scoring exposure")
    if "low-tempo" in script_text and any(token in joined for token in ("corners over", "cards over", "shots over")):
        bad.append("High-event add-on fights low-tempo script")
    if "blowout" in script_text and "opponent possession" in joined:
        bad.append("Opponent possession add-on fights blowout script")

    if bad:
        label = CONTRADICTORY_CORRELATION
        score = 20.0
        reason = "; ".join(bad)
    elif positives:
        label = POSITIVE_CORRELATION
        score = 82.0
        reason = "; ".join(positives)
    elif len(legs) >= 4:
        label = RISKY_CORRELATION
        score = 45.0
        reason = "Many legs increase dependency risk even without direct contradiction"
    else:
        label = NEUTRAL_CORRELATION
        score = 60.0
        reason = "No strong positive or contradictory relationship detected"
    return CorrelationResult(label, score, reason, tuple(positives), tuple(bad))


def score_chain_leg(leg: Mapping[str, Any], event: Mapping[str, Any] | None = None, script: Any = None, external_context: Mapping[str, Any] | None = None) -> ChainLegScore:
    probability = _model_probability(leg)
    implied = _implied_probability(leg)
    edge = None if probability is None or implied is None else probability - implied
    ev = _ev(leg)
    purpose = score_leg_purpose(leg, event=event, script=script)
    ev_quality = score_leg_ev_quality(leg)
    prob_quality = score_leg_probability_quality(leg)
    volatility = score_leg_volatility(leg)
    dependency = score_leg_dependency_risk(leg)
    correlation = score_correlation_quality([leg], script=script).correlation_score
    quality = round(purpose * 0.30 + ev_quality * 0.24 + prob_quality * 0.22 + correlation * 0.12 - volatility * 0.07 - dependency * 0.05, 2)
    rejection = ""
    if "random" in f"{_market(leg)} {_selection(leg)}".lower() or "filler" in f"{_market(leg)} {_selection(leg)}".lower():
        rejection = "Random filler leg"
    elif ev is not None and ev < -0.05 and purpose < 70:
        rejection = "Negative EV with no strategic reason"
    elif probability is not None and probability < 0.20:
        rejection = "Leg probability too low"
    elif quality < 45:
        rejection = "Leg quality below threshold"
    accepted = not rejection
    why_belongs = "Low-threshold or script-supported add-on with acceptable value profile." if accepted else "Leg does not add enough value to justify inclusion."
    why_fail = "Can fail from normal variance, lineup changes, script miss, or because any chain leg can break the ticket."
    if external_context and external_context.get("no_bet_flags"):
        rejection = rejection or "External context warning"
        accepted = False
    return ChainLegScore(
        leg_name=_leg_name(leg),
        market=_market(leg),
        selection=_selection(leg),
        decimal_odds=_odds(leg),
        model_probability=probability,
        implied_probability=implied,
        edge=edge,
        ev=ev,
        purpose_score=purpose,
        correlation_score=correlation,
        volatility_score=volatility,
        dependency_risk=dependency,
        leg_quality_score=max(0.0, min(100.0, quality)),
        accepted=accepted,
        rejection_reason=rejection,
        why_leg_belongs=why_belongs,
        why_leg_could_fail=why_fail,
    )


def _combined_probability(legs: Sequence[Mapping[str, Any]]) -> float | None:
    probabilities = [_model_probability(leg) for leg in legs]
    if any(prob is None for prob in probabilities):
        return None
    raw = prod(float(prob) for prob in probabilities if prob is not None)
    correlation_penalty = min(0.22, max(0, len(legs) - 1) * 0.04)
    return round(max(0.0, raw * (1 - correlation_penalty)), 6)


def _combined_odds(legs: Sequence[Mapping[str, Any]]) -> float | None:
    odds = [_odds(leg) for leg in legs]
    if any(value is None or value <= 1 for value in odds):
        return None
    return round(prod(float(value) for value in odds if value is not None), 6)


def _chain_ev(legs: Sequence[Mapping[str, Any]]) -> float | None:
    probability = _combined_probability(legs)
    odds = _combined_odds(legs)
    if probability is None or odds is None:
        return None
    return round(probability * odds - 1.0, 6)


def _chain_risk(legs: Sequence[Mapping[str, Any]]) -> float:
    probability = _combined_probability(legs) or 0
    volatility = sum(score_leg_volatility(leg) for leg in legs) / max(1, len(legs))
    return round(max(1.0, min(10.0, 10 - probability * 10 + len(legs) * 0.55 + volatility / 45)), 2)


def compare_straight_bet_vs_chain(straight_pick: Mapping[str, Any], chain: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> ChainComparison:
    legs = list(chain.get("legs", [])) if isinstance(chain, Mapping) else list(chain)
    straight_prob = _model_probability(straight_pick)
    straight_odds = _odds(straight_pick)
    straight_ev = _ev(straight_pick)
    straight_risk = _risk(straight_pick)
    chain_prob = _prob(chain, "combined_adjusted_probability", "chain_probability") if isinstance(chain, Mapping) else None
    chain_prob = chain_prob if chain_prob is not None else _combined_probability(legs)
    chain_odds = _num(chain, "total_decimal_odds", "chain_decimal_odds") if isinstance(chain, Mapping) else None
    chain_odds = chain_odds if chain_odds is not None else _combined_odds(legs)
    chain_ev = _num(chain, "combined_ev", "chain_ev", "expected_value") if isinstance(chain, Mapping) else None
    chain_ev = chain_ev if chain_ev is not None else _chain_ev(legs)
    chain_risk = _num(chain, "combined_risk_score", "chain_risk_score", "risk_score") if isinstance(chain, Mapping) else None
    chain_risk = chain_risk if chain_risk is not None else _chain_risk(legs)
    probability_drop = None if straight_prob is None or chain_prob is None else round(straight_prob - chain_prob, 6)
    payout_gain = None if straight_odds is None or chain_odds is None else round(chain_odds - straight_odds, 6)
    risk_increase = None if straight_risk is None or chain_risk is None else round(chain_risk - straight_risk, 6)
    ev_delta = None if straight_ev is None or chain_ev is None else round(chain_ev - straight_ev, 6)
    straight_score = (straight_ev or 0) - ((straight_risk or 5) / 18)
    chain_score = (chain_ev or 0) - ((chain_risk or 8) / 18)
    straight_better = straight_score > chain_score + 0.04
    if straight_better:
        rec = STRAIGHT_BET_BETTER
        reason = "Straight option has better EV-adjusted risk profile."
    elif chain_prob is not None and chain_prob < 0.20:
        rec = NO_CHAIN_RECOMMENDED
        reason = "Chain probability collapses below the minimum recommendation floor."
    elif chain_prob is not None and chain_prob < 0.30:
        rec = AGGRESSIVE_ONLY
        reason = "Chain adds payout but remains aggressive due to low adjusted probability."
    elif chain_risk is not None and chain_risk > 8:
        rec = AGGRESSIVE_ONLY
        reason = "Chain adds payout but risk is high."
    elif chain_prob is not None and chain_prob >= 0.45:
        rec = SMALL_CHAIN
        reason = "Chain keeps adjusted probability above conservative floor while adding payout."
    else:
        rec = BALANCED_CHAIN
        reason = "Chain offers acceptable balanced probability/risk tradeoff."
    return ChainComparison(
        straight_pick=_leg_name(straight_pick), straight_probability=straight_prob, straight_decimal_odds=straight_odds,
        straight_ev=straight_ev, straight_risk_score=straight_risk, chain_probability=chain_prob,
        chain_decimal_odds=chain_odds, chain_ev=chain_ev, chain_risk_score=chain_risk,
        probability_drop=probability_drop, payout_gain=payout_gain, risk_increase=risk_increase,
        ev_delta=ev_delta, straight_bet_better=straight_better, chain_better_reason=reason,
        final_recommendation=rec,
    )


def _profile_mode(client_profile: Mapping[str, Any] | None) -> str:
    return _text(client_profile, "risk_profile", "mode", default="balanced").lower() or "balanced"


def _probability_floor(mode: str) -> float:
    if mode.startswith("conservative"):
        return 0.45
    if mode.startswith("aggressive"):
        return 0.20
    return 0.30


def _max_legs(mode: str) -> int:
    if mode.startswith("conservative"):
        return 2
    if mode.startswith("aggressive"):
        return 4
    return 3


def evaluate_chain_killers(chain: Mapping[str, Any] | Sequence[Mapping[str, Any]], straight_pick: Mapping[str, Any] | None = None, external_context: Mapping[str, Any] | None = None) -> ChainKillerResult:
    legs = list(chain.get("legs", [])) if isinstance(chain, Mapping) else list(chain)
    reasons: list[str] = []
    if external_context and external_context.get("no_bet_flags"):
        reasons.append("Major external context contradiction")
    correlation = score_correlation_quality(legs)
    if correlation.correlation_label == CONTRADICTORY_CORRELATION:
        reasons.append("Contradictory correlation")
    seen: list[Mapping[str, Any]] = []
    for leg in legs:
        if any(_is_duplicate_market(leg, prev) for prev in seen):
            reasons.append("Duplicate market exposure")
            break
        seen.append(leg)
    for leg in legs:
        ev = _ev(leg)
        if ev is not None and ev < -0.05 and score_leg_purpose(leg) < 70:
            reasons.append("Negative EV leg with no strategic reason")
            break
    chain_prob = _combined_probability(legs)
    if chain_prob is not None and chain_prob < 0.20:
        reasons.append("Adjusted probability below 20% floor")
    if _chain_risk(legs) > 8.5:
        reasons.append("Risk score above allowed limit")
    if straight_pick:
        comparison = compare_straight_bet_vs_chain(straight_pick, legs)
        if comparison.straight_bet_better:
            reasons.append("Straight bet is clearly better")
    unique = tuple(dict.fromkeys(reasons))
    return ChainKillerResult(bool(unique), unique, can_override=False, override_note="Can only be shown as WATCH ONLY.", final_block_reason="; ".join(unique))


def _target_fit(legs: Sequence[Mapping[str, Any]], target_payout: float | None, stake: float | None) -> TargetPayoutFit | None:
    if not target_payout or not stake or stake <= 0:
        return None
    required = target_payout / stake
    actual = _combined_odds(legs)
    estimated = None if actual is None else actual * stake
    distance = None if estimated is None else abs(estimated - target_payout)
    if actual is None:
        label = "Poor target fit"
    else:
        ratio = abs(actual - required) / max(required, 0.01)
        if ratio <= 0.05:
            label = "Excellent target fit"
        elif ratio <= 0.12:
            label = "Good target fit"
        elif ratio <= 0.25:
            label = "Loose target fit"
        elif actual > required and (_combined_probability(legs) or 0) < 0.30:
            label = "Forced payout chase"
        else:
            label = "Poor target fit"
    return TargetPayoutFit(round(required, 6), actual, None if estimated is None else round(estimated, 6), None if distance is None else round(distance, 6), label)


def optimize_chain_candidates(straight_pick: Mapping[str, Any], candidate_legs: Sequence[Mapping[str, Any]], target_payout: float | None = None, stake: float | None = None, external_context: Mapping[str, Any] | None = None, client_profile: Mapping[str, Any] | None = None) -> ChainOptimizerResult:
    mode = _profile_mode(client_profile)
    max_legs = min(_max_legs(mode), len(candidate_legs))
    floor = _probability_floor(mode)
    best: ChainOptimizerResult | None = None
    for size in range(2, max_legs + 1):
        for combo in combinations(candidate_legs, size):
            leg_scores = tuple(score_chain_leg(leg, event=straight_pick, script=_text(straight_pick, "script", "game_script"), external_context=external_context) for leg in combo)
            accepted = tuple(score for score in leg_scores if score.accepted)
            rejected = tuple(score for score in leg_scores if not score.accepted)
            if len(accepted) < len(combo):
                legs_for_calc = list(combo)
            else:
                legs_for_calc = list(combo)
            correlation = score_correlation_quality(legs_for_calc, script=_text(straight_pick, "script", "game_script"))
            comparison = compare_straight_bet_vs_chain(straight_pick, legs_for_calc)
            killers = evaluate_chain_killers(legs_for_calc, straight_pick=straight_pick, external_context=external_context)
            target_fit = _target_fit(legs_for_calc, target_payout, stake)
            chain_prob = comparison.chain_probability or 0.0
            avg_leg_quality = sum(score.leg_quality_score for score in leg_scores) / max(1, len(leg_scores))
            quality = round(avg_leg_quality * 0.45 + correlation.correlation_score * 0.25 + chain_prob * 100 * 0.20 - (_chain_risk(legs_for_calc) * 2), 2)
            rec = comparison.final_recommendation
            explanation = comparison.chain_better_reason
            if chain_prob < floor:
                rec = WATCH_ONLY if chain_prob >= 0.20 else NO_CHAIN_RECOMMENDED
                explanation = f"Adjusted probability {chain_prob:.1%} is below the {floor:.0%} client floor."
            if mode.startswith("conservative") and any(_is_hr_leg(leg) or _is_player_prop(leg) for leg in legs_for_calc):
                rec = WATCH_ONLY
                explanation = "Conservative profile blocks high-volatility player/HR add-ons."
            if killers.has_killer:
                rec = WATCH_ONLY
                explanation = killers.final_block_reason
            if target_fit and target_fit.target_fit_label in {"Excellent target fit", "Good target fit"} and (killers.has_killer or quality < 50):
                rec = GOOD_PAYOUT_BAD_CHAIN
                explanation = "Payout target fits, but chain quality/risk rules fail."
            result = ChainOptimizerResult(
                straight_pick=straight_pick,
                accepted_legs=accepted,
                rejected_legs=rejected,
                comparison=comparison,
                killers=killers,
                correlation=correlation,
                target_payout_fit=target_fit,
                chain_quality_score=max(0.0, min(100.0, quality)),
                probability_floor=floor,
                final_recommendation=rec,
                final_explanation=explanation,
            )
            if best is None or _rank_value(result) > _rank_value(best):
                best = result
    if best is None:
        comparison = compare_straight_bet_vs_chain(straight_pick, [])
        return ChainOptimizerResult(straight_pick, tuple(), tuple(), comparison, ChainKillerResult(True, ("No candidate legs",), False, "", "No candidate legs"), score_correlation_quality([]), None, 0.0, floor, NO_CHAIN_RECOMMENDED, "No candidate legs passed basic chain construction rules.")
    return best


def _rank_value(result: ChainOptimizerResult) -> float:
    rec_bonus = {SMALL_CHAIN: 20, BALANCED_CHAIN: 12, AGGRESSIVE_ONLY: 2, WATCH_ONLY: -10, GOOD_PAYOUT_BAD_CHAIN: -15, NO_CHAIN_RECOMMENDED: -25, STRAIGHT_BET_BETTER: -20}.get(result.final_recommendation, 0)
    killer_penalty = 35 if result.killers.has_killer else 0
    return result.chain_quality_score + rec_bonus - killer_penalty


def rank_chain_candidates(chains: Sequence[ChainOptimizerResult]) -> list[ChainOptimizerResult]:
    return sorted(chains, key=_rank_value, reverse=True)


def explain_chain_optimizer_result(result: ChainOptimizerResult) -> str:
    lines = [
        "CHAIN BET OPTIMIZER v2",
        f"Final Recommendation: {result.final_recommendation}",
        f"Chain Quality Score: {result.chain_quality_score:.1f}/100",
        f"Probability Floor: {result.probability_floor:.0%}",
        "",
        "Straight Bet vs Chain:",
        f"- Straight pick: {result.comparison.straight_pick}",
        f"- Straight probability: {result.comparison.straight_probability}",
        f"- Straight EV: {result.comparison.straight_ev}",
        f"- Straight risk: {result.comparison.straight_risk_score}",
        f"- Chain probability: {result.comparison.chain_probability}",
        f"- Chain EV: {result.comparison.chain_ev}",
        f"- Chain risk: {result.comparison.chain_risk_score}",
        f"- Verdict: {result.comparison.final_recommendation}",
        "",
        "Leg Quality:",
    ]
    for leg in result.accepted_legs + result.rejected_legs:
        lines.extend([
            f"- Leg: {leg.leg_name}",
            f"  - Purpose: {leg.purpose_score:.1f}/100",
            f"  - EV: {leg.ev}",
            f"  - Probability: {leg.model_probability}",
            f"  - Correlation: {leg.correlation_score:.1f}/100",
            f"  - Volatility: {leg.volatility_score:.1f}/100",
            f"  - Accepted / Rejected: {'Accepted' if leg.accepted else 'Rejected'}",
            f"  - Why it belongs: {leg.why_leg_belongs}",
            f"  - Why it could fail: {leg.why_leg_could_fail}",
        ])
        if leg.rejection_reason:
            lines.append(f"  - Rejection reason: {leg.rejection_reason}")
    lines.extend([
        "",
        "Chain Quality:",
        f"- Correlation label: {result.correlation.correlation_label}",
        f"- Target payout fit: {None if result.target_payout_fit is None else result.target_payout_fit.target_fit_label}",
        f"- Chain killer checks: {result.killers.final_block_reason or 'None'}",
        f"- Final recommendation: {result.final_recommendation}",
        "",
        result.safety_warning,
    ])
    return "\n".join(lines)
