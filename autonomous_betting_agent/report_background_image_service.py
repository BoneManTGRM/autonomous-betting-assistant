from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

import autonomous_betting_agent.magazine_book_export as magazine_book_export
from autonomous_betting_agent.magazine_sale_ready_patch import apply_magazine_sale_ready_patch
from .mobile_png_layout import render_mobile_deck_png, render_mobile_png
from .report_product_layer import MagazineBrand, safe_text

magazine_book_export = apply_magazine_sale_ready_patch(magazine_book_export)

PNG_HEADER = b"\x89PNG\r\n\x1a\n"
PNG_RENDERER_VERSION = "full-pick-magazine-page-v1"
PAGE_W = 1080
PAGE_H = 1620
SUMMARY_W = 1080
SUMMARY_H = 1620


def _brand_value(brand: MagazineBrand | Mapping[str, Any] | None, key: str, default: str) -> str:
    if brand is None:
        return default
    if isinstance(brand, Mapping):
        return safe_text(brand.get(key)) or default
    return safe_text(getattr(brand, key, "")) or default


def _language(brand: MagazineBrand | Mapping[str, Any] | None) -> str:
    raw = _brand_value(brand, "language", "en")
    return "es" if raw.lower().startswith("es") else "en"


def _stamp_brand(row: Mapping[str, Any], brand: MagazineBrand | Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(row or {})
    data.setdefault("report_brand_name", _brand_value(brand, "brand_name", "ABA Signal Pro"))
    data.setdefault("report_title", _brand_value(brand, "report_title", "Daily Sports Analysis"))
    data.setdefault("report_language", _language(brand))
    return data


def _first_row(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None) -> dict[str, Any]:
    frame = pd.DataFrame(cards)
    if frame.empty:
        return _stamp_brand({"event": "No cards available", "sport": "Sports", "consumer_action": "Research / Learning"}, brand)
    return _stamp_brand(dict(frame.iloc[0].to_dict()), brand)


def render_custom_background_card_png(row: Mapping[str, Any], brand: MagazineBrand | Mapping[str, Any] | None = None, *, background_bytes: bytes | None = None, index: int = 0) -> bytes:
    return render_mobile_png(pd.DataFrame([dict(row or {})]), brand, background_bytes=background_bytes, top_n=1)


def render_custom_background_summary_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, background_bytes: bytes | None = None, top_n: int = 3) -> bytes:
    report_name = _brand_value(brand, "brand_name", "ABA Signal Pro")
    return magazine_book_export.render_full_pick_magazine_page_png(_first_row(cards, brand), background_image=background_bytes, report_name=report_name, page_number=1, total_pages=max(1, len(pd.DataFrame(cards).head(top_n or 1))), language=_language(brand))


def render_custom_background_deck_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, background_bytes: bytes | None = None, max_cards: int = 75) -> bytes:
    return render_mobile_deck_png(pd.DataFrame(cards), brand, background_bytes=background_bytes, cards_per_page=3, max_cards=max_cards)
