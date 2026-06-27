from __future__ import annotations

from typing import Any, Iterable

from autonomous_betting_agent.multi_leg_report import attach_multi_leg_review, format_items

_FLAG = "_ABA_MAGAZINE_COMBO_SECTION_PATCHED_V3"


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        data = value.to_dict()
        return dict(data) if isinstance(data, dict) else {}
    return dict(getattr(value, "__dict__", {}) or {})


def _lang(row: dict[str, Any], explicit: str | None = None) -> str:
    text = str(explicit or row.get("report_language") or row.get("language") or row.get("lang") or "").lower()
    return "es" if text.startswith("es") or "español" in text or "espanol" in text else "en"


def _split_items(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "null", "n/a", "na", "--"}:
        return []
    for sep in ("|", ";", "\n", "•"):
        text = text.replace(sep, "\n")
    return [part.strip(" -•") for part in text.splitlines() if part.strip(" -•")]


def combo_section_items(row_value: Any) -> list[str]:
    row = _row(row_value)
    explicit: list[str] = []
    for key in ("combo_magazine_items", "combo_recommendation", "combo_note"):
        explicit.extend(_split_items(row.get(key)))
    if explicit:
        return explicit[:3]
    return format_items([row], _lang(row), 3)


def _attach(rows: Iterable[Any], language: str | None = None) -> list[dict[str, Any]]:
    data = [_row(item) for item in rows]
    if not data:
        return []
    enriched = attach_multi_leg_review(data, _lang(data[0], language))
    return [dict(item, combo_magazine_items=item.get("combo_magazine_items", "")) for item in enriched]


def install(module: Any) -> Any:
    if getattr(module, _FLAG, False):
        return module
    module.chain_items = combo_section_items
    module._chain_items = combo_section_items
    for name in ("render_full_magazine_book_pdf", "render_full_magazine_book_png", "render_full_magazine_zip"):
        original = getattr(module, name, None)
        if callable(original):
            def wrapper(picks: Iterable[Any], *args: Any, _original=original, **kwargs: Any):
                return _original(_attach(picks, kwargs.get("language")), *args, **kwargs)
            setattr(module, name, wrapper)
    setattr(module, _FLAG, True)
    return module
