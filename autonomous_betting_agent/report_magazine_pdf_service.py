from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

import autonomous_betting_agent.magazine_book_export as magazine_book_export
from autonomous_betting_agent.magazine_sale_ready_patch import apply_magazine_sale_ready_patch
from .report_learning_layer_compat import apply_learning_layer_compat
from .report_product_layer import MagazineBrand, safe_text

magazine_book_export = apply_magazine_sale_ready_patch(magazine_book_export)

PDF_HEADER = b"%PDF"


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


def _rows(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None, max_cards: int) -> list[dict[str, Any]]:
    frame = apply_learning_layer_compat(pd.DataFrame(cards).copy()).head(max_cards)
    if frame.empty:
        frame = pd.DataFrame([{"event": "No cards available", "sport": "Sports", "consumer_action": "Research / Learning"}])
    return [_stamp_brand(row.to_dict(), brand) for _, row in frame.iterrows()]


def render_vintage_magazine_pdf(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, max_cards: int = 75) -> bytes:
    """Render the Magazine Report PDF with the current full-pick magazine renderer.

    The public function name is kept for backwards compatibility with Report Studio,
    but the output is now the same premium one-pick-per-page magazine design used by
    the Full Magazine Book export.
    """
    report_name = _brand_value(brand, "brand_name", "ABA Signal Pro")
    return magazine_book_export.render_full_magazine_book_pdf(_rows(cards, brand, max_cards), report_name=report_name, language=_language(brand))
