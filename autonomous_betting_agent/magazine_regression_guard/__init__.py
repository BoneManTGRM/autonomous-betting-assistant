from __future__ import annotations

from typing import Any, Iterable

from autonomous_betting_agent.active_magazine_export_guard import install as _active_install, normalize_row, NO_PLAY, _note

PATCH_VERSION = "magazine_regression_guard_package_active_v2"


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        try:
            data = value.to_dict()
            return dict(data) if isinstance(data, dict) else {}
        except Exception:
            return {}
    return dict(getattr(value, "__dict__", {}) or {})


def _clean_public_note(value: Any) -> str:
    return _note(value)


def _clean_public_rows(rows: Iterable[Any], fallback: list[str] | None = None) -> list[str]:
    out: list[str] = []
    for row in rows:
        text = _note(row)
        low = text.lower()
        if not text or "markets discovered" in low or "provider consensus_average" in low or "endpoint unknown" in low or "status code unknown" in low or "rows returned" in low:
            continue
        if text not in out:
            out.append(text)
    return out or list(fallback or [])


def _enrich_pick(pick: Any) -> Any:
    return normalize_row(pick)


def _patch_second_page() -> None:
    try:
        from autonomous_betting_agent import magazine_second_page_patch as page2
    except Exception:
        return
    if getattr(page2, "_ABA_REGRESSION_GUARD_DISCOVER", "") == PATCH_VERSION:
        return
    original_discover = getattr(page2, "discover_markets", None)
    if callable(original_discover):
        def discover_with_guard(pick: Any):
            row = normalize_row(pick)
            markets, diag = original_discover(row)
            for market in markets:
                if getattr(market, "edge", None) is not None and getattr(market, "ev", None) is not None and (market.edge <= 0 or market.ev <= 0):
                    market.badge = NO_PLAY
                    market.rejection_reason = "Requires positive edge and EV"
            return markets, diag
        page2.discover_markets = discover_with_guard
    page2._ABA_REGRESSION_GUARD_DISCOVER = PATCH_VERSION


def install(module: Any | None = None) -> Any | None:
    if module is None:
        try:
            import autonomous_betting_agent.magazine_book_export as module
        except Exception:
            return None
    _active_install(module)
    _patch_second_page()
    return module
