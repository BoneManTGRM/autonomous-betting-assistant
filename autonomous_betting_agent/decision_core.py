"""Decision gates for ABA Signal Pro recommendations.

This module evaluates candidate rows before they can become client-facing picks.
It is local-first and does not place bets or guarantee outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .baseball_analysis import build_baseball_reason, score_baseball_game
from .client_profiles import client_allows_pick, client_risk_limit
from .home_run_engine import is_home_run_market
from .model_score import calculate_blended_score
from .odds_value import analyze_odds_value, row_ev, row_model_probability


@dataclass(frozen=True)
class GateResult:
    passed: bool
    label: str
    score: float | None
    reason: str
    blocking: bool = True


@dataclass(frozen=True)
class RecommendationGateSummary:
    gates: tuple[GateResult, ...]
    final_decision: str
    eligible_for_65_catalog: bool
    reason: str

    @property
    def passed(self) -> bool:
        return all(gate.passed or not gate.blocking for gate in self.gates)


def _explicit_gate(row: Mapping[str, Any]) -> str:
    for key in ("sports_analysis_gate", "analysis_gate"):
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip().lower()
    return ""


def evaluate_sports_analysis_gate(row: Mapping[str, Any]) -> GateResult:
    explicit = _explicit_gate(row)
    if explicit in {"pass", "passed", "true", "yes", "supported"}:
        return GateResult(True, "Sports Analysis Gate", None, "Sports analysis is explicitly supported.")
    if explicit in {"fail", "failed", "false", "no", "unsupported"}:
        return GateResult(False, "Sports Analysis Gate", None, "Sports analysis is explicitly unsupported.")
    score = score_baseball_game(row)
    passed = score >= 55 or bool(row.get("why_pick") or row.get("why_we_are_picking") or row.get("analysis_summary"))
    return GateResult(passed, "Sports Analysis Gate", score, build_baseball_reason(row))


def evaluate_odds_value_gate(row: Mapping[str, Any]) -> GateResult:
    value = analyze_odds_value(row)
    return GateResult(value.label == "GOOD READ, GOOD PRICE", "Odds Value Gate", value.expected_value, value.reason)


def evaluate_probability_gate(row: Mapping[str, Any], threshold: float = 0.65) -> GateResult:
    probability = row_model_probability(row)
    if probability is None:
        return GateResult(False, "Probability Gate", None, "Projected model probability is missing.")
    return GateResult(probability >= threshold, "Probability Gate", probability, f"Projected model probability is {probability:.1%}; threshold is {threshold:.1%}.")


def evaluate_ev_gate(row: Mapping[str, Any]) -> GateResult:
    ev = row_ev(row)
    if ev is None:
        return GateResult(False, "EV Gate", None, "Expected value is missing.")
    return GateResult(ev > 0, "EV Gate", ev, "EV is positive." if ev > 0 else "EV is not positive.")


def evaluate_risk_gate(row: Mapping[str, Any], subscriber: Mapping[str, Any] | None = None) -> GateResult:
    score = calculate_blended_score(row, subscriber)
    limit = client_risk_limit(subscriber)
    return GateResult(score <= limit, "Risk Gate", score, f"Risk score is {score:.1f}/10; client limit is {limit:.1f}/10.")


def evaluate_subscriber_fit_gate(row: Mapping[str, Any], subscriber: Mapping[str, Any] | None = None) -> GateResult:
    passed = client_allows_pick(row, subscriber)
    return GateResult(passed, "Subscriber Fit Gate", None, "Pick fits subscriber profile." if passed else "Pick is blocked by subscriber profile.")


def _is_chain(row: Mapping[str, Any]) -> bool:
    market = " ".join(str(row.get(key, "")).lower() for key in ("bet_type", "market", "market_type", "exact_bet", "pick", "selection"))
    return bool(row.get("legs")) or any(word in market for word in ("chain", "parlay", "sgp"))


def _decision(row: Mapping[str, Any], gates: tuple[GateResult, ...]) -> str:
    by_label = {gate.label: gate for gate in gates}
    if not by_label["Subscriber Fit Gate"].passed:
        return "WATCH ONLY"
    if not by_label["Sports Analysis Gate"].passed:
        return "WATCH ONLY"
    if not by_label["Odds Value Gate"].passed:
        odds_label = analyze_odds_value(row).label
        return "BAD VALUE" if odds_label == "BAD VALUE" else "GOOD READ, BAD PRICE"
    if not by_label["EV Gate"].passed:
        return "BAD VALUE"
    if not by_label["Risk Gate"].passed:
        return "AGGRESSIVE ONLY"
    if _is_chain(row):
        return "CHAIN ONLY" if by_label["Probability Gate"].passed else "SMALL BET"
    if is_home_run_market(row):
        return "SMALL BET" if by_label["Probability Gate"].passed else "AGGRESSIVE ONLY"
    if not by_label["Probability Gate"].passed:
        return "WATCH ONLY"
    score = by_label["Risk Gate"].score
    return "SMALL BET" if score is not None and score > 6 else "BET"


def evaluate_all_gates(row: Mapping[str, Any], subscriber: Mapping[str, Any] | None = None, threshold: float = 0.65) -> RecommendationGateSummary:
    gates = (
        evaluate_sports_analysis_gate(row),
        evaluate_odds_value_gate(row),
        evaluate_probability_gate(row, threshold),
        evaluate_ev_gate(row),
        evaluate_risk_gate(row, subscriber),
        evaluate_subscriber_fit_gate(row, subscriber),
    )
    decision = _decision(row, gates)
    probability = row_model_probability(row)
    eligible = bool(probability is not None and probability >= threshold and decision in {"BET", "SMALL BET"})
    failed = [gate.label for gate in gates if not gate.passed and gate.blocking]
    reason = f"Decision {decision}; failed gates: {', '.join(failed)}." if failed else f"Decision {decision}; all gates passed."
    return RecommendationGateSummary(gates, decision, eligible, reason)
