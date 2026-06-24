"""Report, magazine, and export helpers for Chain Bet Optimizer v2."""

from __future__ import annotations

from typing import Any, Iterable

from autonomous_betting_agent.chain_optimizer_v2 import (
    AGGRESSIVE_ONLY,
    BALANCED_CHAIN,
    GOOD_PAYOUT_BAD_CHAIN,
    NO_CHAIN_RECOMMENDED,
    SAFETY_WARNING,
    SMALL_CHAIN,
    STRAIGHT_BET_BETTER,
    WATCH_ONLY,
    ChainOptimizerResult,
    explain_chain_optimizer_result,
)

SECTIONS = (
    "Best Approved Chains",
    "Straight Bet Better Than Chain",
    "Rejected Chains",
    "Aggressive Only Chains",
    "No Chain Recommended",
)


def _fmt(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _leg_label(leg: Any) -> str:
    return f"{leg.leg_name} ({leg.market}: {leg.selection})"


def _section_for(result: ChainOptimizerResult) -> str:
    rec = result.final_recommendation
    if rec in {SMALL_CHAIN, BALANCED_CHAIN}:
        return "Best Approved Chains"
    if rec == STRAIGHT_BET_BETTER or result.comparison.straight_bet_better:
        return "Straight Bet Better Than Chain"
    if rec == AGGRESSIVE_ONLY:
        return "Aggressive Only Chains"
    if rec == NO_CHAIN_RECOMMENDED:
        return "No Chain Recommended"
    if rec == GOOD_PAYOUT_BAD_CHAIN or rec == WATCH_ONLY or result.killers.has_killer:
        return "Rejected Chains"
    return "No Chain Recommended"


def split_chain_optimizer_sections(results: Iterable[ChainOptimizerResult]) -> dict[str, list[ChainOptimizerResult]]:
    sections = {section: [] for section in SECTIONS}
    for result in results:
        sections[_section_for(result)].append(result)
    return sections


def render_chain_optimizer_card(result: ChainOptimizerResult, *, max_legs: int = 6) -> str:
    fit = result.target_payout_fit
    comparison = result.comparison
    lines = [
        "### CHAIN BET OPTIMIZER v2",
        f"- Final Recommendation: {result.final_recommendation}",
        f"- Chain Quality Score: {result.chain_quality_score:.1f}/100",
        f"- Probability Floor: {result.probability_floor:.0%}",
        f"- Target Payout Fit: {'N/A' if fit is None else fit.target_fit_label}",
        f"- Safety Warning: {result.safety_warning or SAFETY_WARNING}",
        "",
        "**Straight Bet vs Chain:**",
        f"- Straight pick: {comparison.straight_pick}",
        f"- Straight probability: {_fmt(comparison.straight_probability)}",
        f"- Straight odds: {_fmt(comparison.straight_decimal_odds)}",
        f"- Straight EV: {_fmt(comparison.straight_ev)}",
        f"- Straight risk: {_fmt(comparison.straight_risk_score)}",
        f"- Chain probability: {_fmt(comparison.chain_probability)}",
        f"- Chain odds: {_fmt(comparison.chain_decimal_odds)}",
        f"- Chain EV: {_fmt(comparison.chain_ev)}",
        f"- Chain risk: {_fmt(comparison.chain_risk_score)}",
        f"- Probability drop: {_fmt(comparison.probability_drop)}",
        f"- Payout gain: {_fmt(comparison.payout_gain)}",
        f"- Risk increase: {_fmt(comparison.risk_increase)}",
        f"- Verdict: {comparison.final_recommendation}",
        "",
        "**Leg Quality:**",
    ]
    legs = list(result.accepted_legs + result.rejected_legs)
    if not legs:
        lines.append("- No candidate legs passed review.")
    for index, leg in enumerate(legs[:max_legs], start=1):
        lines += [
            f"{index}. Leg: {leg.leg_name}",
            f"   - Market: {leg.market}",
            f"   - Selection: {leg.selection}",
            f"   - Probability: {_fmt(leg.model_probability)}",
            f"   - EV: {_fmt(leg.ev)}",
            f"   - Purpose score: {leg.purpose_score:.1f}/100",
            f"   - Correlation score: {leg.correlation_score:.1f}/100",
            f"   - Volatility score: {leg.volatility_score:.1f}/100",
            f"   - Dependency risk: {leg.dependency_risk:.1f}/100",
            f"   - Leg quality score: {leg.leg_quality_score:.1f}/100",
            f"   - Accepted / Rejected: {'Accepted' if leg.accepted else 'Rejected'}",
            f"   - Rejection reason: {leg.rejection_reason or 'N/A'}",
            f"   - Why it belongs: {leg.why_leg_belongs}",
            f"   - Why it could fail: {leg.why_leg_could_fail}",
        ]
    if len(legs) > max_legs:
        lines.append(f"- {len(legs) - max_legs} additional legs hidden in summary view.")
    lines += [
        "",
        "**Chain Quality:**",
        f"- Correlation label: {result.correlation.correlation_label}",
        f"- Correlation reason: {result.correlation.correlation_reason}",
        f"- Chain killer checks: {'YES' if result.killers.has_killer else 'NO'}",
        f"- Final block reason: {result.killers.final_block_reason or 'N/A'}",
        f"- Final explanation: {result.final_explanation}",
    ]
    return "\n".join(lines)


def render_chain_optimizer_summary(results: Iterable[ChainOptimizerResult]) -> str:
    sections = split_chain_optimizer_sections(results)
    total = sum(len(items) for items in sections.values())
    lines = ["## Chain Bet Optimizer v2 Summary", "", SAFETY_WARNING, "", f"Total reviewed chains: {total}"]
    for section in SECTIONS:
        lines.append(f"- {section}: {len(sections[section])}")
    if total == 0:
        lines.append(NO_CHAIN_RECOMMENDED)
    return "\n".join(lines)


def render_chain_optimizer_magazine_section(results: Iterable[ChainOptimizerResult]) -> str:
    sections = split_chain_optimizer_sections(results)
    total = sum(len(items) for items in sections.values())
    lines = [
        "## Chain Bet Optimizer v2",
        "",
        "Chain bets are higher risk because one failed leg can lose the full ticket. These are projected probabilities, not guaranteed outcomes.",
        "",
    ]
    if total == 0:
        lines += [NO_CHAIN_RECOMMENDED, ""]
        return "\n".join(lines).strip() + "\n"
    for section in SECTIONS:
        lines += [f"### {section}", ""]
        items = sections[section]
        if not items:
            lines += [NO_CHAIN_RECOMMENDED if section == "No Chain Recommended" else "No chains in this section.", ""]
            continue
        for result in items:
            lines.append(render_chain_optimizer_card(result, max_legs=4))
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def chain_optimizer_results_to_rows(results: Iterable[ChainOptimizerResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        fit = result.target_payout_fit
        comparison = result.comparison
        rows.append({
            "chain_optimizer_version": "v2",
            "final_recommendation": result.final_recommendation,
            "chain_quality_score": result.chain_quality_score,
            "probability_floor": result.probability_floor,
            "straight_pick": comparison.straight_pick,
            "straight_probability": comparison.straight_probability,
            "straight_decimal_odds": comparison.straight_decimal_odds,
            "straight_ev": comparison.straight_ev,
            "straight_risk_score": comparison.straight_risk_score,
            "chain_probability": comparison.chain_probability,
            "chain_decimal_odds": comparison.chain_decimal_odds,
            "chain_ev": comparison.chain_ev,
            "chain_risk_score": comparison.chain_risk_score,
            "probability_drop": comparison.probability_drop,
            "payout_gain": comparison.payout_gain,
            "risk_increase": comparison.risk_increase,
            "ev_delta": comparison.ev_delta,
            "straight_bet_better": comparison.straight_bet_better,
            "correlation_label": result.correlation.correlation_label,
            "correlation_score": result.correlation.correlation_score,
            "target_fit_label": None if fit is None else fit.target_fit_label,
            "required_decimal_odds": None if fit is None else fit.required_decimal_odds,
            "estimated_payout": None if fit is None else fit.estimated_payout,
            "target_distance": None if fit is None else fit.target_distance,
            "has_chain_killer": result.killers.has_killer,
            "killer_reasons": "; ".join(result.killers.killer_reasons),
            "accepted_leg_count": len(result.accepted_legs),
            "rejected_leg_count": len(result.rejected_legs),
            "accepted_legs": "; ".join(_leg_label(leg) for leg in result.accepted_legs),
            "rejected_legs": "; ".join(_leg_label(leg) for leg in result.rejected_legs),
            "final_explanation": result.final_explanation,
            "safety_warning": result.safety_warning or SAFETY_WARNING,
        })
    return rows


__all__ = [
    "render_chain_optimizer_card",
    "render_chain_optimizer_summary",
    "render_chain_optimizer_magazine_section",
    "chain_optimizer_results_to_rows",
    "split_chain_optimizer_sections",
    "explain_chain_optimizer_result",
]
