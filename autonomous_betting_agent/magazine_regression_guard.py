from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from autonomous_betting_agent.report_public_quality import (
    LIVE_TRIGGER_UNAVAILABLE,
    NO_VERIFIED_PARLAY,
    build_full_market_label,
    has_exact_market_line,
    public_action_label,
    public_recommendation_status,
    public_source_warning,
    sanitize_public_text,
    to_float,
    trim_complete_sentence,
)

PATCH_VERSION = "magazine_regression_guard_v2"
NOTE_KEYS = (
    "weather_summary", "venue_note", "weather_location", "weather_risk", "news_summary", "newsapi_summary",
    "sportsdataio_context", "sportsdataio_game_summary", "sports_context_summary", "matchup_note", "matchup_notes",
    "perplexity_context", "perplexity_summary", "preview_summary", "game_summary", "short_reason", "decision_reasons",
    "why_bullets", "why_pick", "analysis_summary", "reason", "explanation", "risk_reason", "risk_notes", "hidden_risk",
    "chain_notes", "main_read", "add_on_legs", "parlay_notes",
)
RAW_PUBLIC_SNIPPETS = ("markets discovered", "provider consensus_average", "endpoint unknown", "status code unknown", "rows returned")


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        try:
            data = value.to_dict()
            return dict(data) if isinstance(data, Mapping) else {}
        except Exception:
            return {}
    return dict(getattr(value, "__dict__", {}) or {})


def _value_numbers(row: Mapping[str, Any]) -> tuple[float | None, float | None]:
    ev = next((to_float(row.get(key)) for key in ("expected_value_per_unit", "profit_expected_value", "expected_value", "ev", "EV", "raw_EV", "two_page_raw_EV") if to_float(row.get(key)) is not None), None)
    edge = next((to_float(row.get(key)) for key in ("model_market_edge", "edge", "raw_edge", "two_page_raw_edge") if to_float(row.get(key)) is not None), None)
    if edge is not None and abs(edge) > 1.0 and abs(edge) <= 100.0:
        edge /= 100.0
    return ev, edge


def _negative_value(row: Mapping[str, Any]) -> bool:
    ev, edge = _value_numbers(row)
    return ev is not None and edge is not None and (ev <= 0 or edge <= 0)


def _clean_public_note(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\bWeather:\s*Weather:\s*", "Weather: ", text, flags=re.I)
    text = re.sub(r"\bContext:\s*Context:\s*", "Context: ", text, flags=re.I)
    text = sanitize_public_text(text)
    return trim_complete_sentence(text)


def _clean_public_rows(rows: Iterable[Any], fallback: list[str] | None = None) -> list[str]:
    out: list[str] = []
    for row in rows:
        text = _clean_public_note(row)
        if not text:
            continue
        lowered = text.lower()
        if any(snippet in lowered for snippet in RAW_PUBLIC_SNIPPETS):
            continue
        if text not in out:
            out.append(text)
    return out or list(fallback or [])


def _source_saved(row: Mapping[str, Any]) -> bool:
    return public_source_warning(row).startswith("Saved-source")


def _enrich_pick(pick: Any) -> Any:
    data = _row(pick)
    if not data:
        return pick
    for key in NOTE_KEYS:
        if key in data:
            cleaned = _clean_public_note(data.get(key))
            if cleaned:
                data[key] = cleaned
    label = build_full_market_label(data)
    action = public_action_label(data)
    status = public_recommendation_status(data)
    for key in ("public_market_label", "verified_market_label", "full_market_label", "market_label", "trend_label", "display_pick", "exact_bet", "final_recommendation_label", "final_label"):
        data[key] = label
    data["prediction"] = label
    data["pick"] = label
    for key in ("final_decision", "recommendation", "consumer_action", "recommended_action"):
        data[key] = action
    data.setdefault("final_explanation", status)
    data.setdefault("recommendation_reason", status)
    if _negative_value(data):
        data["risk"] = "PRICE REJECTED"
        data["risk_label"] = "PRICE REJECTED"
        data["risk_level"] = "PRICE REJECTED"
        data["profit_guard_status"] = "PRICE REJECTED"
        data["final_explanation"] = "Negative edge or EV at current price."
        data["recommendation_reason"] = data["final_explanation"]
        for key in ("final_decision", "recommendation", "consumer_action", "recommended_action"):
            data[key] = "NO BET / PRICE REJECTED"
    if _source_saved(data):
        data["api_match_status"] = "Provider not matched"
        data["provider_match_status"] = "Provider not matched"
        data["verification_status"] = "Source saved"
        data["source_match_status"] = "Saved-source only - current provider match required"
    if not has_exact_market_line(data):
        data.setdefault("data_issue_reason", "Missing exact market line")
    return data


def _patch_second_page() -> None:
    try:
        import autonomous_betting_agent.magazine_second_page_patch as page2
    except Exception:
        return
    if getattr(page2, "_ABA_REGRESSION_GUARD_DISCOVER", "") == PATCH_VERSION:
        return
    original_discover = getattr(page2, "discover_markets", None)
    if callable(original_discover):
        def discover_with_guard(pick: Any):
            enriched = _enrich_pick(pick)
            markets, diag = original_discover(enriched)
            source_saved = _source_saved(_row(enriched))
            for market in markets:
                if not getattr(market, "full_label", ""):
                    market.full_label = build_full_market_label(_row(enriched))
                ev = getattr(market, "ev", None)
                edge = getattr(market, "edge", None)
                if ev is not None and edge is not None and (ev <= 0 or edge <= 0):
                    market.badge = getattr(page2, "NO_BET", "NO BET / PRICE REJECTED")
                    market.rejection_reason = "Requires positive edge and EV"
                if source_saved:
                    if getattr(market, "badge", "") == getattr(page2, "VERIFIED", "VERIFIED CANDIDATE"):
                        market.badge = getattr(page2, "WATCHLIST", "WATCHLIST / VERIFY PRICE")
                    market.rejection_reason = re.sub(r"provider match required before verified status", "Saved-source only - current provider match required", str(getattr(market, "rejection_reason", "")), flags=re.I)
            if source_saved:
                diag["provider_state"] = "Source saved"
                diag["provider_called"] = "saved-source"
            return markets, diag
        page2.discover_markets = discover_with_guard
    original_sections = getattr(page2, "_page_two_sections", None)
    if callable(original_sections):
        def sections_with_guard(
            data: dict[str, Any],
            lang: str,
            *,
            parlays=None,
            diagnostics=None,
        ):
            enriched = _enrich_pick(data)
            sections = original_sections(
                enriched,
                lang,
                parlays=parlays,
                diagnostics=diagnostics,
            )
            guarded = []
            source_saved = _source_saved(_row(enriched))
            for title, rows, color in sections:
                cleaned = _clean_public_rows(rows)
                if title == "Parlay Builder" and not any("2-leg" in row.lower() and "verified" in row.lower() for row in cleaned):
                    cleaned = [NO_VERIFIED_PARLAY, "Need at least 2 independent current-provider positive-EV legs."]
                if title == "Flash Triggers" and not cleaned:
                    cleaned = [LIVE_TRIGGER_UNAVAILABLE]
                if title in {"Advanced Market Board", "Quality Gate"} and source_saved:
                    cleaned = [re.sub(r"Current provider match required before verified status|Provider match required before verified status", "Saved-source only - current provider match required", row, flags=re.I) for row in cleaned]
                    cleaned = [row.replace("Provider matched", "Source saved") for row in cleaned]
                guarded.append((title, cleaned, color))
            return guarded
        page2._page_two_sections = sections_with_guard
    page2._ABA_REGRESSION_GUARD_DISCOVER = PATCH_VERSION


def install(module: Any | None = None) -> Any | None:
    if module is None:
        try:
            import autonomous_betting_agent.magazine_book_export as module
        except Exception:
            return None
    if getattr(module, "_ABA_MAGAZINE_REGRESSION_GUARD", "") == PATCH_VERSION:
        _patch_second_page()
        return module
    original_page = getattr(module, "render_full_pick_magazine_page", None)
    if callable(original_page):
        def render_full_pick_magazine_page_guarded(pick: Any, *args: Any, **kwargs: Any):
            return original_page(_enrich_pick(pick), *args, **kwargs)
        module.render_full_pick_magazine_page = render_full_pick_magazine_page_guarded
    original_pages = getattr(module, "render_full_magazine_book_pages", None)
    if callable(original_pages):
        def render_full_magazine_book_pages_guarded(picks: Iterable[Any], *args: Any, **kwargs: Any):
            return original_pages([_enrich_pick(pick) for pick in list(picks)], *args, **kwargs)
        module.render_full_magazine_book_pages = render_full_magazine_book_pages_guarded
    original_items = getattr(module, "_items", None)
    if callable(original_items):
        def items_guarded(row: Any, keys: Iterable[str], fallback: list[str], limit: int, lang: str = "en") -> list[str]:
            return _clean_public_rows(original_items(_enrich_pick(row), keys, fallback, limit, lang), fallback)[:limit]
        module._items = items_guarded
    original_matchup = getattr(module, "_matchup_items", None)
    if callable(original_matchup):
        def matchup_items_guarded(row: Any) -> list[str]:
            return _clean_public_rows(original_matchup(_enrich_pick(row)), ["Context was not returned for this event."])[:3]
        module._matchup_items = matchup_items_guarded
    original_headline_context = getattr(module, "_headline_context_lines", None)
    if callable(original_headline_context):
        def headline_context_guarded(row: Any) -> list[str]:
            return _clean_public_rows(original_headline_context(_enrich_pick(row)), ["Context unavailable."])
        module._headline_context_lines = headline_context_guarded
    original_pairs = getattr(module, "_pairs", None)
    if callable(original_pairs):
        def pairs_guarded(row: Any, lang: str) -> list[tuple[str, str]]:
            enriched = _enrich_pick(row)
            pairs = []
            for label, value in original_pairs(enriched, lang):
                clean_label = "CONFIGURED APIS" if str(label).upper() == "ACTIVE APIS" else str(label)
                pairs.append((clean_label, _clean_public_note(value)))
            pairs.append(("MATCHED", "Source saved" if _source_saved(_row(enriched)) else "Provider matched"))
            return pairs[:5]
        module._pairs = pairs_guarded
    original_api_lines = getattr(module, "api_provenance_lines", None)
    if callable(original_api_lines):
        def api_lines_guarded(row: Any) -> list[str]:
            enriched = _enrich_pick(row)
            lines = [line.replace("Active APIs", "Configured APIs") for line in original_api_lines(enriched)]
            lines.append("Matched to this row: " + ("Source saved" if _source_saved(_row(enriched)) else "Provider matched"))
            return _clean_public_rows(lines)
        module.api_provenance_lines = api_lines_guarded
    module._ABA_MAGAZINE_REGRESSION_GUARD = PATCH_VERSION
    _patch_second_page()
    return module
