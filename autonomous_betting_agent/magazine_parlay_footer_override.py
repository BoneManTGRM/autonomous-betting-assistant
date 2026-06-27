from __future__ import annotations

from typing import Any

from autonomous_betting_agent.multi_leg_report import format_items

_FLAG = "_ABA_PARLAY_FOOTER_OVERRIDE_V3"
_VERSION_SUFFIX = "_parlay_footer_v3"


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        data = value.to_dict()
        return dict(data) if isinstance(data, dict) else {}
    return dict(getattr(value, "__dict__", {}) or {})


def _bad(value: Any) -> bool:
    return value is None or str(value).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "--"}


def _split(value: Any) -> list[str]:
    if _bad(value):
        return []
    text = str(value).replace("•", "\n").replace(";", "\n").replace("|", "\n")
    return [part.strip(" -•") for part in text.splitlines() if part.strip(" -•")]


def _lang(row: dict[str, Any], explicit: str | None = None) -> str:
    text = str(explicit or row.get("report_language") or row.get("language") or row.get("lang") or "").lower()
    return "es" if text.startswith("es") or "español" in text or "espanol" in text else "en"


def parlay_review_items(row_value: Any, language: str = "en") -> list[str]:
    row = _row(row_value)
    explicit: list[str] = []
    for key in ("combo_magazine_items", "parlay_magazine_items", "combo_recommendation", "parlay_recommendation", "combo_note", "parlay_note"):
        explicit.extend(_split(row.get(key)))
    return explicit[:3] if explicit else format_items([row], language, 3)


def _repaint_footer(module: Any, image: Any, language: str) -> None:
    draw = module.ImageDraw.Draw(image, "RGBA")
    footer_y, footer_b = 1542, 1581
    draw.rectangle((20, footer_y, 1060, footer_b), fill=module.BLACK)
    footer = module._tr(module.SAFETY_FOOTER, language)
    font = module._fit(footer, module.PAGE_WIDTH - 90, 16, 10, False)
    draw.text((42, footer_y + 10), module._ellipsize_to_width(draw, footer, font, module.PAGE_WIDTH - 90), font=font, fill=module.CREAM)


def _repaint_parlay_box(module: Any, image: Any, row: dict[str, Any], language: str) -> None:
    draw = module.ImageDraw.Draw(image, "RGBA")
    x, y, width, height = 712, 1178, 348, 175
    module._section(draw, x, y, width, height, "CHAIN BETTING NOTES", module.BLUE, language)
    draw.rectangle((x + 10, y + 56, x + width - 10, y + height - 8), fill=module.CREAM)
    module._bullets_auto(draw, x + 24, y + 70, parlay_review_items(row, language), width - 48, height - 88, module.BLUE, 14, 7, 3, language)


def _set_chain_item_functions(module: Any) -> None:
    module.chain_items = lambda row: parlay_review_items(row, _lang(_row(row)))
    module._chain_items = module.chain_items


def _bump_style_version(module: Any) -> None:
    current = str(getattr(module, "MAGAZINE_STYLE_VERSION", ""))
    if _VERSION_SUFFIX not in current:
        module.MAGAZINE_STYLE_VERSION = f"{current}{_VERSION_SUFFIX}"


def _patch_sale_ready_apply_function() -> None:
    try:
        from autonomous_betting_agent import magazine_sale_ready_patch as sale_ready
    except Exception:
        return
    if getattr(sale_ready, "_ABA_SALE_READY_APPLY_RETURNS_PARLAY_FOOTER", False):
        return
    original = getattr(sale_ready, "apply_magazine_sale_ready_patch", None)
    if not callable(original):
        return

    def wrapped_apply(target_module: Any) -> Any:
        patched = original(target_module)
        try:
            patched = install(patched)
        except Exception:
            pass
        return patched

    sale_ready.apply_magazine_sale_ready_patch = wrapped_apply
    sale_ready._ABA_SALE_READY_APPLY_RETURNS_PARLAY_FOOTER = True


def install(module: Any) -> Any:
    _patch_sale_ready_apply_function()
    _set_chain_item_functions(module)
    if getattr(module, _FLAG, False):
        _bump_style_version(module)
        return module
    original = getattr(module, "render_full_pick_magazine_page", None)
    if callable(original):
        def wrapped_page(pick: Any, *args: Any, _original=original, **kwargs: Any):
            row = _row(pick)
            image = _original(row, *args, **kwargs)
            explicit = kwargs.get("language") if "language" in kwargs else (args[9] if len(args) > 9 else None)
            language = _lang(row, explicit)
            try:
                _repaint_parlay_box(module, image, row, language)
                _repaint_footer(module, image, language)
            except Exception:
                pass
            return image
        module.render_full_pick_magazine_page = wrapped_page
    original_png = getattr(module, "render_full_pick_magazine_page_png", None)
    if callable(original_png):
        def wrapped_png(pick: Any, *args: Any, **kwargs: Any):
            return module._png(module.render_full_pick_magazine_page(pick, *args, **kwargs))
        module.render_full_pick_magazine_page_png = wrapped_png
    _bump_style_version(module)
    setattr(module, _FLAG, True)
    return module
