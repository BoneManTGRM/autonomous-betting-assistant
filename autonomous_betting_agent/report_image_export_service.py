from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

import autonomous_betting_agent.magazine_book_export as magazine_book_export
from autonomous_betting_agent.magazine_sale_ready_patch import apply_magazine_sale_ready_patch
from .mobile_png_layout import render_mobile_deck_png
from .report_product_layer import MagazineBrand, safe_text
from .report_vintage_image_service import PNG_HEADER, render_vintage_card_png

magazine_book_export = apply_magazine_sale_ready_patch(magazine_book_export)


def safe_filename_part(value: Any, *, fallback: str = "item", limit: int = 70) -> str:
    text = safe_text(value).lower() or fallback
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    cleaned = cleaned.strip("_") or fallback
    return cleaned[:limit]


def _brand_value(brand: MagazineBrand | Mapping[str, Any] | None, key: str, default: str) -> str:
    if brand is None:
        return default
    if isinstance(brand, Mapping):
        return safe_text(brand.get(key)) or default
    return safe_text(getattr(brand, key, "")) or default


def _language(brand: MagazineBrand | Mapping[str, Any] | None) -> str:
    raw = _brand_value(brand, "language", "en")
    return "es" if raw.lower().startswith("es") else "en"


def _rows(cards: pd.DataFrame, max_cards: int = 75) -> list[dict[str, Any]]:
    frame = pd.DataFrame(cards).head(max_cards)
    if frame.empty:
        return [{"event": "No cards available", "sport": "Sports", "consumer_action": "Research / Learning"}]
    return [dict(row) for _, row in frame.iterrows()]


def _stamp_brand(row: dict[str, Any], brand: MagazineBrand | Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(row or {})
    data.setdefault("report_brand_name", _brand_value(brand, "brand_name", "ABA Signal Pro"))
    data.setdefault("report_title", _brand_value(brand, "report_title", "Daily Sports Analysis"))
    data.setdefault("report_language", _language(brand))
    return data


def card_image_filename(row: Mapping[str, Any], *, workspace: str = "report", index: int = 0) -> str:
    event = safe_filename_part(row.get("event") or row.get("matchup"), fallback="card")
    workspace_part = safe_filename_part(workspace, fallback="report")
    return f"{workspace_part}_{index + 1:03d}_{event}.png"


def render_card_png(row: Mapping[str, Any], brand: MagazineBrand | Mapping[str, Any] | None = None, *, width: int = 1080) -> bytes:
    """Render one readable card PNG."""
    return render_vintage_card_png(row, brand)


def render_card_deck_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, max_cards: int = 75, width: int = 1080) -> bytes:
    """Render all cards as readable 3-card pages stacked into one deck PNG."""
    return render_mobile_deck_png(pd.DataFrame(cards), brand, cards_per_page=3, max_cards=max_cards)


def render_magazine_summary_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, top_n: int = 3, width: int = 1080) -> bytes:
    """Render the Magazine Report tab with the full-pick magazine page design."""
    rows = [_stamp_brand(row, brand) for row in _rows(cards, max_cards=max(1, int(top_n or 1)))]
    report_name = _brand_value(brand, "brand_name", "ABA Signal Pro")
    return magazine_book_export.render_full_pick_magazine_page_png(rows[0], report_name=report_name, page_number=1, total_pages=len(rows), language=_language(brand))
