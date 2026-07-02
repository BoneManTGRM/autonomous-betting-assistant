from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from .two_page_decision_engine import (
    DATA_UNAVAILABLE,
    FLASH_UNAVAILABLE,
    NO_BET,
    SAFETY_LANGUAGE,
    TwoPageDecisionBundle,
    append_two_page_decision_columns,
    build_two_page_decision_engine,
)


@dataclass(frozen=True)
class TwoPageDecisionExport:
    cards: pd.DataFrame
    markdown: str
    diagnostics_csv_text: str
    provider_capability_csv_text: str
    page1: dict[str, Any]
    page2: dict[str, Any]
    provider_capabilities: list[dict[str, Any]]


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "none", "nan", "null", "nat"} else text


def _fmt_number(value: Any, digits: int = 3) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return DATA_UNAVAILABLE


def _fmt_percent(value: Any) -> str:
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return DATA_UNAVAILABLE


def _csv(frame: pd.DataFrame | None) -> str:
    if frame is None or frame.empty:
        return "status\nData unavailable\n"
    return frame.to_csv(index=False)


def _parlay_lines(title: str, parlay: Mapping[str, Any]) -> list[str]:
    if not parlay:
        return [f"### {title}", f"- Status: {DATA_UNAVAILABLE}"]
    lines = [f"### {title}"]
    lines.append(f"- Status: {_text(parlay.get('status')) or DATA_UNAVAILABLE}")
    lines.append(f"- Correlation: {_text(parlay.get('correlation_rating')) or DATA_UNAVAILABLE}")
    if parlay.get("combined_parlay_odds") is not None:
        lines.append(f"- Parlay odds: {_fmt_number(parlay.get('combined_parlay_odds'))}")
    if parlay.get("parlay_implied_probability") is not None:
        lines.append(f"- Implied probability: {_fmt_percent(parlay.get('parlay_implied_probability'))}")
    if parlay.get("combined_model_probability") is not None:
        lines.append(f"- Combined model probability: {_fmt_percent(parlay.get('combined_model_probability'))}")
    if parlay.get("parlay_EV") is not None:
        lines.append(f"- Parlay EV: {_fmt_number(parlay.get('parlay_EV'))}")
    if parlay.get("estimated_parlay_price") is not None:
        lines.append(f"- Price source: {'estimated from legs' if parlay.get('estimated_parlay_price') else 'sportsbook provided'}")
    rejection = _text(parlay.get("rejection_reason"))
    if rejection:
        lines.append(f"- Rejection reason: {rejection}")
    return lines


def render_two_page_decision_markdown(bundle: TwoPageDecisionBundle) -> str:
    page1 = bundle.page1 or {}
    page2 = bundle.page2 or {}
    conservative = page2.get("best_conservative_parlay") or {}
    aggressive = page2.get("best_aggressive_parlay") or {}

    lines = [
        "## Two-Page Betting Decision Engine",
        "",
        "### Page 1 — Straight Bet Decision",
        f"- Status: {_text(page1.get('bet_status')) or NO_BET}",
        f"- Event key: {_text(page1.get('unique_event_key')) or DATA_UNAVAILABLE}",
        f"- Pick key: {_text(page1.get('unique_pick_key')) or DATA_UNAVAILABLE}",
        f"- Market: {_text(page1.get('market_category')) or DATA_UNAVAILABLE}",
        f"- Sportsbook / source: {_text(page1.get('sportsbook')) or DATA_UNAVAILABLE}",
        f"- Odds: {_fmt_number(page1.get('decimal_odds'))}",
        f"- Model probability: {_fmt_percent(page1.get('model_probability'))}",
        f"- Implied probability: {_fmt_percent(page1.get('implied_probability'))}",
        f"- Edge: {_fmt_percent(page1.get('edge'))}",
        f"- EV: {_fmt_number(page1.get('EV'))}",
        f"- Line-shopping status: {_text(page1.get('line_shopping_status')) or DATA_UNAVAILABLE}",
        f"- Dynamic learning: {_text(page1.get('dynamic_learning_status')) or DATA_UNAVAILABLE}",
        f"- Why selected: {_text(page1.get('why_selected') or page1.get('summary')) or DATA_UNAVAILABLE}",
        "",
    ]
    lines.extend(_parlay_lines("Page 2 — Conservative Parlay", conservative))
    lines.append("")
    lines.extend(_parlay_lines("Page 2 — Aggressive Parlay", aggressive))
    lines += [
        "",
        "### Page 2 — Prop / Qualification / Flash Status",
        f"- Prop opportunity: {_text(page2.get('best_prop_opportunity')) or DATA_UNAVAILABLE}",
        f"- Team qualification / advancement: {_text(page2.get('team_qualification_advancement')) or DATA_UNAVAILABLE}",
        f"- Live flash-bet trigger: {_text(page2.get('best_live_flash_bet_trigger')) or FLASH_UNAVAILABLE}",
        "",
        "### Provider Capability Audit",
    ]
    for cap in bundle.provider_capabilities or []:
        lines.append(
            "- "
            + f"{_text(cap.get('sport')) or 'unknown'}: "
            + f"pregame_odds={bool(cap.get('pregame_odds_available'))}, "
            + f"live_odds={bool(cap.get('live_odds_available'))}, "
            + f"book_level={bool(cap.get('sportsbook_level_odds_available'))}, "
            + f"player_props={bool(cap.get('player_props_available'))}, "
            + f"team_props={bool(cap.get('team_props_available'))}, "
            + f"qualification={bool(cap.get('qualification_markets_available'))}, "
            + f"freshness={_text(cap.get('latency_freshness_limitations')) or DATA_UNAVAILABLE}"
        )
    lines += ["", f"Safety: {SAFETY_LANGUAGE}"]
    return "\n".join(lines).strip()


def build_two_page_decision_export(cards: pd.DataFrame) -> TwoPageDecisionExport:
    source = cards.copy(deep=True) if isinstance(cards, pd.DataFrame) else pd.DataFrame(cards)
    bundle = build_two_page_decision_engine(source)
    cards_with_decisions = append_two_page_decision_columns(source)
    return TwoPageDecisionExport(
        cards=cards_with_decisions,
        markdown=render_two_page_decision_markdown(bundle),
        diagnostics_csv_text=_csv(bundle.diagnostics_frame if isinstance(bundle.diagnostics_frame, pd.DataFrame) else pd.DataFrame(bundle.diagnostics)),
        provider_capability_csv_text=_csv(bundle.provider_capabilities_frame if isinstance(bundle.provider_capabilities_frame, pd.DataFrame) else pd.DataFrame(bundle.provider_capabilities)),
        page1=bundle.page1,
        page2=bundle.page2,
        provider_capabilities=bundle.provider_capabilities,
    )
