from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from .mobile_png_layout import render_mobile_png
from .report_product_layer import MagazineBrand

PNG_RENDERER_VERSION = "unified-large-text-layout"
PAGE_W = 1080
PAGE_H = 1620


def render_custom_background_card_png(row: Mapping[str, Any], brand: MagazineBrand | Mapping[str, Any] | None = None, *, background_bytes: bytes | None = None, index: int = 0) -> bytes:
    return render_mobile_png(pd.DataFrame([dict(row or {})]), brand, background_bytes=background_bytes, top_n=1)


def render_custom_background_summary_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, background_bytes: bytes | None = None, top_n: int = 3) -> bytes:
    return render_mobile_png(pd.DataFrame(cards), brand, background_bytes=background_bytes, top_n=3)


def render_custom_background_deck_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, background_bytes: bytes | None = None, max_cards: int = 3) -> bytes:
    return render_mobile_png(pd.DataFrame(cards), brand, background_bytes=background_bytes, top_n=3)
