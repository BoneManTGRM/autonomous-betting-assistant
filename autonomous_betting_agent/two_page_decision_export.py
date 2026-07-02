from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from .report_public_quality import (
    LIVE_TRIGGER_UNAVAILABLE,
    MISSING_EXACT_MARKET_LINE,
    NO_VERIFIED_PARLAY,
    build_full_market_label,
    public_diagnostic_banned_terms,
    sanitize_public_text,
)
from .two_page_decision_engine import (
    DATA_UNAVAILABLE,
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


def _public_line(value: Any) -> str:
    cleaned = sanitize_public_text(value)
    return cleaned or DATA_UNAVAILABLE


def _parlay_lines(title: str, parlay: Mapping[str, Any]) -> list[str]:
    if not parlay:
        return [f"### {title}", f"- Status: {NO_VERIFIED_PARLAY}"]
    lines = [f"### {title}"]
    status = _text(parlay.get("status")) or DATA_UNAVAILABLE
    rejection = _text(parlay.get("rejection_reason"))
    if status == DATA_UNAVAILABLE or "fewer than two" in rejection.lower():
        lines.append(f"- Status: {NO_VERIFIED_PARLAY}")
    else:
        lines.append(f"- Status: {_public_line(status)}")
    lines.append(f"- Correlation: {_public_line(parlay.get('correlation_rating'))}")
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
    if rejection and "fewer than two" not in rejection.lower():
        lines.append(f"- Rejection reason: {_public_line(rejection)}")
    return lines


def _best_row_for_page1(bundle: TwoPageDecisionBundle) -> Mapping[str, Any]:
    key = _text((bundle.page1 or {}).get("unique_pick_key"))
    for row in bundle.diagnostics or []:
        if _text(row.get("unique_pick_key")) == key:
            return row
    return bundle.page1 or {}


def render_two_page_decision_markdown(bundle: TwoPageDecisionBundle) -> str:
    page1 = bundle.page1 or {}
    page2 = bundle.page2 or {}
    page1_row = _best_row_for_page1(bundle)
    market_label = build_full_market_label(page1_row)
    if market_label == "Missing market selection" and page1.get("market_category"):
        market_label = _text(page1.get("market_category")) or MISSING_EXACT_MARKET_LINE
    conservative = page2.get("best_conservative_parlay") or {}
    aggressive = page2.get("best_aggressive_parlay") or {}
    lines = [
        "## Two-Page Betting Decision Engine",
        "",
        "### Page 1 — Straight Pick Decision",
        f"- Status: {_public_line(page1.get('bet_status') or NO_BET)}",
        f"- Market: {_public_line(market_label)}",
        f"- Event key: {_public_line(page1.get('unique_event_key'))}",
        f"- Pick key: {_public_line(page1.get('unique_pick_key'))}",
        f"- Market category: {_public_line(page1.get('market_category'))}",
        f"- Sportsbook / source: {_public_line(page1.get('sportsbook'))}",
        f"- Odds: {_fmt_number(page1.get('decimal_odds'))}",
        f"- Model probability: {_fmt_percent(page1.get('model_probability'))}",
        f"- Implied probability: {_fmt_percent(page1.get('implied_probability'))}",
        f"- Edge: {_fmt_percent(page1.get('edge'))}",
        f"- EV: {_fmt_number(page1.get('EV'))}",
        f"- Line-shopping status: {_public_line(page1.get('line_shopping_status'))}",
        f"- Dynamic learning: {_public_line(page1.get('dynamic_learning_status'))}",
        f"- Why selected: {_public_line(page1.get('why_selected') or page1.get('summary'))}",
        "",
    ]
    lines.extend(_parlay_lines("Page 2 — Conservative Parlay", conservative))
    lines.append("")
    lines.extend(_parlay_lines("Page 2 — Aggressive Parlay", aggressive))
    lines += [
        "",
        "### Page 2 — Prop / Qualification / Live Status",
        f"- Prop opportunity: {_public_line(page2.get('best_prop_opportunity'))}",
        f"- Team qualification / advancement: {_public_line(page2.get('team_qualification_advancement'))}",
        f"- Live trigger: {_public_line(page2.get('best_live_flash_bet_trigger') or LIVE_TRIGGER_UNAVAILABLE)}",
        "",
        "### Provider Capability Audit",
    ]
    for cap in bundle.provider_capabilities or []:
        lines.append(
            "- "
            + f"{_public_line(cap.get('sport') or 'unknown')}: "
            + f"pregame_odds={bool(cap.get('pregame_odds_available'))}, "
            + f"live_odds={bool(cap.get('live_odds_available'))}, "
            + f"book_level={bool(cap.get('sportsbook_level_odds_available'))}, "
            + f"player_props={bool(cap.get('player_props_available'))}, "
            + f"team_props={bool(cap.get('team_props_available'))}, "
            + f"qualification={bool(cap.get('qualification_markets_available'))}, "
            + f"freshness={_public_line(cap.get('latency_freshness_limitations'))}"
        )
    lines += ["", f"Safety: {SAFETY_LANGUAGE}"]
    rendered = "\n".join(lines).strip()
    for banned in public_diagnostic_banned_terms():
        rendered = rendered.replace(banned, "")
    return rendered


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
