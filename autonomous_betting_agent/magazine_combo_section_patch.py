from __future__ import annotations

from typing import Any, Iterable

from autonomous_betting_agent.multi_leg_report import attach_multi_leg_review, format_items

_FLAG = "_ABA_MAGAZINE_COMBO_SECTION_PATCHED_V6"
_LAST_ITEMS = ""


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
    for key in ("combo_magazine_items", "parlay_magazine_items", "combo_recommendation", "parlay_recommendation", "combo_note", "parlay_note"):
        explicit.extend(_split_items(row.get(key)))
    if explicit:
        return explicit[:3]
    return format_items([row], _lang(row), 3)


def _attach(rows: Iterable[Any], language: str | None = None) -> list[dict[str, Any]]:
    global _LAST_ITEMS
    data = [_row(item) for item in rows]
    if not data:
        return []
    enriched = attach_multi_leg_review(data, _lang(data[0], language))
    _LAST_ITEMS = str(enriched[0].get("combo_magazine_items", "")) if enriched else ""
    return [dict(item, combo_magazine_items=item.get("combo_magazine_items", ""), parlay_magazine_items=item.get("parlay_magazine_items", "")) for item in enriched]


def _row_with_latest(row_value: Any) -> dict[str, Any]:
    row = _row(row_value)
    if _LAST_ITEMS and not row.get("combo_magazine_items"):
        row["combo_magazine_items"] = _LAST_ITEMS
        row["parlay_magazine_items"] = _LAST_ITEMS
    return row


def _paint_combo_box(module: Any, image: Any, row: dict[str, Any], language: str) -> Any:
    try:
        draw = module.ImageDraw.Draw(image, "RGBA")
        x, y, width, height = 712, 1178, 348, 175
        module._section(draw, x, y, width, height, "CHAIN BETTING NOTES", module.BLUE, language)
        draw.rectangle((x + 10, y + 56, x + width - 10, y + height - 8), fill=module.CREAM)
        module._bullets_auto(draw, x + 24, y + 70, combo_section_items(row), width - 48, height - 88, module.BLUE, 14, 7, 3, language)
    except Exception:
        return image
    return image


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
    original_page = getattr(module, "render_full_pick_magazine_page", None)
    if callable(original_page):
        def page_wrapper(pick: Any, *args: Any, _original=original_page, **kwargs: Any):
            row = _row_with_latest(pick)
            rendered = _original(row, *args, **kwargs)
            explicit = kwargs.get("language") if "language" in kwargs else (args[9] if len(args) > 9 else None)
            return _paint_combo_box(module, rendered, row, _lang(row, explicit))
        setattr(module, "render_full_pick_magazine_page", page_wrapper)
    original_png = getattr(module, "render_full_pick_magazine_page_png", None)
    if callable(original_png):
        def png_wrapper(pick: Any, *args: Any, _original=original_png, **kwargs: Any):
            return _original(_row_with_latest(pick), *args, **kwargs)
        setattr(module, "render_full_pick_magazine_page_png", png_wrapper)
    setattr(module, _FLAG, True)
    return module
