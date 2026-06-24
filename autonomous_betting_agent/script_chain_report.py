"""Report helpers for game-script and target-payout chains."""

from __future__ import annotations

from typing import Iterable

from .bet_catalog import fmt_prob
from .script_chain_core import ScriptChainResult, chain_quality_reason


def render_script_chain_card(chain: ScriptChainResult) -> str:
    required = "N/A" if chain.required_decimal_odds is None else f"{chain.required_decimal_odds:.2f}"
    lines = [
        f"### {chain.game} — {chain.final_recommendation}",
        f"- Game Script: {chain.script}",
        f"- Stake: {chain.stake:.2f}",
        f"- Target Payout: {chain.target_payout:.2f}",
        f"- Required Odds: {required}",
        f"- Actual Odds: {chain.total_decimal_odds:.2f}",
        f"- Estimated Payout: {chain.estimated_payout:.2f}",
        f"- Distance From Target: {chain.target_distance:.2f}",
        f"- Chain Quality Score: {chain.chain_quality_score:.1f}/100",
        f"- Chain Quality Reason: {chain_quality_reason(chain)}",
        f"- Raw Combined Probability: {fmt_prob(chain.raw_combined_probability)}",
        f"- Adjusted Probability: {fmt_prob(chain.adjusted_probability)}",
        f"- EV: {chain.ev:.3f}",
        f"- Risk Score: {chain.risk_score:.1f}/10",
        f"- Correlation Label: {chain.correlation_label}",
        f"- Correlation Reason: {chain.correlation_reason}",
        f"- Why Chain Makes Sense: {chain.why_chain}",
        f"- Why Chain Could Lose: {chain.why_chain_could_lose}",
        "",
        "#### Leg-by-leg explanation",
        "",
    ]
    for idx, leg in enumerate(chain.leg_explanations, start=1):
        lines += [
            f"**Leg {idx}: {leg.leg}**",
            f"- Market: {leg.market}",
            f"- Odds: {'N/A' if leg.odds is None else f'{leg.odds:.2f}'}",
            f"- Implied Probability: {fmt_prob(leg.implied_probability)}",
            f"- Model Probability: {fmt_prob(leg.model_probability)}",
            f"- Game-Script Reason: {leg.game_script_reason}",
            f"- EV: {'N/A' if leg.ev is None else f'{leg.ev:.3f}'}",
            f"- Risk Contribution: {leg.risk_contribution:.1f}/10",
            f"- Why It Could Lose: {leg.why_it_could_lose}",
        ]
        if leg.rejected:
            lines.append(f"- Rejection: {leg.rejection_reason}")
        lines.append("")
    lines.append(f"- Final Recommendation: {chain.final_recommendation}")
    return "\n".join(lines)


def render_game_script_chain_section(chains: Iterable[ScriptChainResult]) -> str:
    chain_list = list(chains)
    lines = ["## Best Game-Script Chains", ""]
    if not chain_list:
        lines += ["NO CHAIN RECOMMENDED", ""]
        return "\n".join(lines)
    for chain in sorted(chain_list, key=lambda item: (-item.chain_quality_score, item.risk_score, -item.ev)):
        lines.append(render_script_chain_card(chain))
        lines.append("")
    return "\n".join(lines).strip() + "\n"
