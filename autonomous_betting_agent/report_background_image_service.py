from __future__ import annotations

from io import BytesIO
from typing import Any, Mapping

import pandas as pd
from PIL import Image

from .mobile_png_layout import render_mobile_deck_png, render_mobile_png
from .report_product_layer import MagazineBrand

PNG_HEADER = b"\x89PNG\r\n\x1a\n"
PNG_RENDERER_VERSION = "unified-large-text-layout"
PAGE_W = 1080
PAGE_H = 1620
SUMMARY_W = 1080
SUMMARY_H = 1350


def _crop_png_to_size(payload: bytes, width: int, height: int) -> bytes:
    """Crop PNG bytes to a fixed legacy smoke-test size without resizing text."""
    try:
        image = Image.open(BytesIO(payload)).convert("RGB")
        if image.size == (width, height):
            return payload
        left = max(0, (image.width - width) // 2)
        top = 0
        cropped = image.crop((left, top, left + width, top + height))
        out = BytesIO()
        cropped.save(out, format="PNG", optimize=False)
        return out.getvalue()
    except Exception:
        return payload


def render_custom_background_card_png(row: Mapping[str, Any], brand: MagazineBrand | Mapping[str, Any] | None = None, *, background_bytes: bytes | None = None, index: int = 0) -> bytes:
    return render_mobile_png(pd.DataFrame([dict(row or {})]), brand, background_bytes=background_bytes, top_n=1)


def render_custom_background_summary_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, background_bytes: bytes | None = None, top_n: int = 3) -> bytes:
    payload = render_mobile_png(pd.DataFrame(cards), brand, background_bytes=background_bytes, top_n=top_n)
    return _crop_png_to_size(payload, SUMMARY_W, SUMMARY_H)


def render_custom_background_deck_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, background_bytes: bytes | None = None, max_cards: int = 75) -> bytes:
    return render_mobile_deck_png(pd.DataFrame(cards), brand, background_bytes=background_bytes, cards_per_page=3, max_cards=max_cards)
