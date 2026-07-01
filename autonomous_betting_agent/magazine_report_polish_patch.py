from __future__ import annotations

import re
from typing import Any, Iterable

_PATCH_VERSION = "magazine_report_display_polish_v1"

SOURCE_LABELS = {
    "Odds API": "Odds",
    "The Odds API": "Odds",
    "SportsDataIO": "SDIO",
    "WeatherAPI": "Weather",
    "API-Football": "API-FB",
    "Perplexity": "PPLX",
    "NewsAPI": "News",
}


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


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _fallback_row(row: Any) -> bool:
    data = _row(row)
    source = _clean(data.get("odds_source") or data.get("data_source")).lower()
    status = _clean(data.get("odds_status")).lower()
    return any(token in source or token in status for token in ("uploaded", "fallback", "cached", "missing"))


def _dedupe(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean(item)
        if text and not text.endswith("."):
            text += "."
        key = text.lower().rstrip(".")
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def _source_label(name: str) -> str:
    return SOURCE_LABELS.get(str(name).strip(), str(name).strip())


def _install_renderer_source_labels(module: Any) -> None:
    if getattr(module, "_ABA_SOURCE_LABEL_POLISH_VERSION", "") == _PATCH_VERSION:
        return
    original_api_provenance = getattr(module, "api_provenance", None)
    if not callable(original_api_provenance):
        return

    def polished_api_provenance_lines(row: Any) -> list[str]:
        prov = original_api_provenance(row)
        active = [_source_label(name) for name in prov.get("active_sources", [])]
        inactive = [_source_label(name) for name in prov.get("inactive_sources", [])]
        lines: list[str] = []
        if active:
            label = "Sources checked" if _fallback_row(row) else "Live sources"
            lines.append(label + ": " + " · ".join(active))
        if not lines and inactive:
            lines.append("Sources configured: " + " · ".join(inactive))
        return lines

    def polished_active_note(row: Any) -> str:
        lines = polished_api_provenance_lines(row)
        return lines[0] + "." if lines else "Sources checked: none."

    module.api_provenance_lines = polished_api_provenance_lines
    module._active_note = polished_active_note
    module._ABA_SOURCE_LABEL_POLISH_VERSION = _PATCH_VERSION


def install_sale_ready_polish() -> None:
    try:
        from autonomous_betting_agent import magazine_sale_ready_patch as sale
    except Exception:
        return

    if getattr(sale, "_ABA_DISPLAY_POLISH_VERSION", "") == _PATCH_VERSION:
        return

    def polished_matchup_items(row: Any) -> list[str]:
        lang = sale._impl._lang(row)
        data = sale._row(row)
        items: list[str] = []
        keys = (
            "perplexity_context",
            "perplexity_summary",
            "sports_context_summary",
            "preview_summary",
            "game_summary",
            "short_reason",
            "matchup_note",
        )
        for item in sale._source_items(data, keys, 1, 82):
            if "odds are not live" not in item.lower():
                items.append(item)
        if _fallback_row(data) and not any("fallback report" in item.lower() for item in items):
            items.insert(0, "Fallback report: verify current odds and news before entry.")
        try:
            items.extend(sale._compact_weather(str(data.get("weather_summary", "") or ""), lang)[:1])
        except Exception:
            pass
        if not items:
            items.append("Pregame context was not returned; verify odds and news before entry.")
        return sale._wrap(_dedupe(items)[:3], lang)

    def install_renderer(module: Any) -> Any:
        if module is None:
            return module
        try:
            module._matchup_items = polished_matchup_items
            module.matchup_items = polished_matchup_items
            _install_renderer_source_labels(module)
        except Exception:
            pass
        return module

    original_apply = getattr(sale, "apply_magazine_sale_ready_patch", None)
    if callable(original_apply) and getattr(original_apply, "_ABA_DISPLAY_POLISH_VERSION", "") != _PATCH_VERSION:
        def wrapped_apply(module: Any) -> Any:
            return install_renderer(original_apply(module))

        wrapped_apply._ABA_DISPLAY_POLISH_VERSION = _PATCH_VERSION
        sale.apply_magazine_sale_ready_patch = wrapped_apply

    sale.sale_ready_matchup_items = polished_matchup_items
    sale._ABA_DISPLAY_POLISH_VERSION = _PATCH_VERSION

    try:
        import autonomous_betting_agent.magazine_book_export as renderer
        install_renderer(renderer)
    except Exception:
        pass


def install_fresh_handoff_guard() -> None:
    try:
        from autonomous_betting_agent.report_studio_fresh_handoff_patch import install as install_guard
        install_guard()
    except Exception:
        pass


def install() -> None:
    install_sale_ready_polish()
    install_fresh_handoff_guard()


install()
