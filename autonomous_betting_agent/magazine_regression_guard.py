from __future__ import annotations

from typing import Any, Iterable, Mapping

from autonomous_betting_agent.report_public_quality import (
    build_full_market_label,
    has_exact_market_line,
    public_action_label,
    public_recommendation_status,
    public_source_warning,
    to_float,
)

PATCH_VERSION = "magazine_regression_guard_v1"


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


def _enrich_pick(pick: Any) -> Any:
    data = _row(pick)
    if not data:
        return pick
    label = build_full_market_label(data)
    action = public_action_label(data)
    status = public_recommendation_status(data)

    data.setdefault("public_market_label", label)
    data.setdefault("verified_market_label", label)
    data.setdefault("full_market_label", label)
    data["prediction"] = label
    data["pick"] = label
    data["exact_bet"] = label
    data["final_recommendation_label"] = label
    data["final_decision"] = action
    data["recommendation"] = action
    data["consumer_action"] = action
    data["recommended_action"] = action
    data.setdefault("final_explanation", status)
    data.setdefault("recommendation_reason", status)
    if _negative_value(data):
        data["risk"] = "PRICE REJECTED"
        data["risk_label"] = "PRICE REJECTED"
        data["profit_guard_status"] = "PRICE REJECTED"
        data["final_explanation"] = "Negative edge or EV at current price. Do not publish as a pick."
        data["recommendation_reason"] = data["final_explanation"]
    if public_source_warning(data).startswith("Saved-source"):
        data["api_match_status"] = "Provider not matched"
        data["provider_match_status"] = "Provider not matched"
        data["verification_status"] = "Source saved"
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
    if not callable(original_discover):
        return

    def discover_with_guard(pick: Any):
        enriched = _enrich_pick(pick)
        markets, diag = original_discover(enriched)
        source_saved = public_source_warning(_row(enriched)).startswith("Saved-source")
        for market in markets:
            ev = getattr(market, "ev", None)
            edge = getattr(market, "edge", None)
            if ev is not None and edge is not None and (ev <= 0 or edge <= 0):
                market.badge = getattr(page2, "NO_BET", "NO BET / PRICE REJECTED")
                market.rejection_reason = "Requires positive edge and EV"
            if source_saved:
                if getattr(market, "badge", "") == getattr(page2, "VERIFIED", "VERIFIED CANDIDATE"):
                    market.badge = getattr(page2, "WATCHLIST", "WATCHLIST / VERIFY PRICE")
                if "provider match" in str(getattr(market, "rejection_reason", "")).lower():
                    market.rejection_reason = "Saved-source verification pending"
        if source_saved:
            diag["provider_state"] = "Source saved"
        return markets, diag

    page2.discover_markets = discover_with_guard
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

    module._ABA_MAGAZINE_REGRESSION_GUARD = PATCH_VERSION
    _patch_second_page()
    return module
