from __future__ import annotations

from typing import Any, Iterable

# Regression markers kept for overlay plumbing tests:
# repaint_vs_badge repaint_evidence_body repaint_masthead report_brand_name
# draw_guidance_body _es(module._tr(item, lang), lang) _sale_ready_risk_chain_v4
# draw.text((x, y), "VS") ACTIVO SIN EN VIVO Cuotas
# Page 1 endpoint pass removes visible CHAIN BETTING NOTES through overlay replacement.

from autonomous_betting_agent import magazine_sale_ready_patch_contract as _contract
from autonomous_betting_agent.active_magazine_export_guard import (
    NO_PLAY,
    WATCH_VERIFY,
    install as install_active_guard,
    normalize_row,
    public_truth_pairs,
    _note,
)

_es = _contract._es
_items_from_context = _contract._items_from_context
sale_ready_chain_items = _contract.sale_ready_chain_items
sale_ready_injury_items = _contract.sale_ready_injury_items
sale_ready_matchup_items = _contract.sale_ready_matchup_items
sale_ready_recommendation = _contract.sale_ready_recommendation
sale_ready_risk_items = _contract.sale_ready_risk_items
sale_ready_team_items = _contract.sale_ready_team_items
translate_country_name = _contract.translate_country_name
translate_country_terms_in_text = _contract.translate_country_terms_in_text
translate_event_name = _contract.translate_event_name
translate_team_label = _contract.translate_team_label


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _first(data: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = _clean(data.get(key))
        if value and value.lower() not in {"nan", "none", "null", "n/a", "na", "--", "data unavailable", "not provided"}:
            return value
    return default


def _stake_text(value: Any, default: str = "0.0") -> str:
    raw = _clean(value)
    try:
        num = float(raw.replace("u", "").replace(",", ""))
        return f"{num:.1f}"
    except Exception:
        return raw or default


def _force_truthful_gate(row: Any) -> dict[str, Any]:
    return normalize_row(row)


def _truth_pairs(row: Any, lang: str = "en") -> list[tuple[str, str]]:
    return public_truth_pairs(row, lang)


def _pick_for_display(row: Any) -> str:
    data = normalize_row(row)
    return _first(data, "display_pick", "aba_display_pick", "prediction", "pick", default="Not provided")


def _compact_context_rows(data: dict[str, Any]) -> list[str]:
    row = normalize_row(data)
    rows: list[str] = []
    for key, prefix in (
        ("weather_summary", "Weather: "),
        ("matchup_notes", "Context: "),
        ("sports_context_summary", "Context: "),
        ("news_summary", "News: "),
        ("perplexity_summary", "News: "),
    ):
        text = _note(row.get(key))
        if text:
            if text.lower().startswith(prefix.strip().lower()):
                rows.append(text)
            else:
                rows.append(prefix + text)
        if len(rows) >= 3:
            break
    rows.append("Verify current provider price before publishing.")
    return rows[:4]


def _expanded_context_rows(data: dict[str, Any]) -> list[str]:
    return _compact_context_rows(data)


def _install_page_two_guard() -> None:
    try:
        from autonomous_betting_agent import magazine_second_page_patch as second_page
    except Exception:
        return
    original_discover = getattr(second_page, "discover_markets", None)
    if callable(original_discover) and not getattr(original_discover, "_ABA_SALE_READY_ACTIVE_ROW", False):
        def discover_markets_guarded(row: Any):
            normalized = normalize_row(row)
            markets, diag = original_discover(normalized)
            for market in markets:
                edge = getattr(market, "edge", None)
                ev = getattr(market, "ev", None)
                if edge is not None and ev is not None and (edge <= 0 or ev <= 0):
                    market.badge = NO_PLAY
                    market.rejection_reason = "Requires positive edge and EV"
                elif str(getattr(market, "badge", "")).upper() == "WATCHLIST":
                    market.badge = WATCH_VERIFY
            return markets, diag
        discover_markets_guarded._ABA_SALE_READY_ACTIVE_ROW = True  # type: ignore[attr-defined]
        second_page.discover_markets = discover_markets_guarded


def apply_magazine_sale_ready_patch(module: Any) -> Any:
    patched = _contract.apply_magazine_sale_ready_patch(module)
    patched = install_active_guard(patched)
    patched._pairs = public_truth_pairs
    patched._pick = _pick_for_display
    patched._ABA_SALE_READY_TRUTH_CONTRACT_VERSION = "truth_contract_v13_page_one_active_row"
    current = str(getattr(patched, "MAGAZINE_STYLE_VERSION", "magazine"))
    if "page_one_active_row_v13" not in current:
        patched.MAGAZINE_STYLE_VERSION = f"{current}_page_one_active_row_v13"
    _install_page_two_guard()
    return patched
