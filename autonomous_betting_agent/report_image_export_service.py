from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from .report_product_layer import MagazineBrand, safe_text
from .report_vintage_image_service import (
    PNG_HEADER,
    render_vintage_card_deck_png,
    render_vintage_card_png,
    render_vintage_summary_png,
)


def safe_filename_part(value: Any, *, fallback: str = "item", limit: int = 70) -> str:
    text = safe_text(value).lower() or fallback
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    cleaned = cleaned.strip("_") or fallback
    return cleaned[:limit]


def card_image_filename(row: Mapping[str, Any], *, workspace: str = "report", index: int = 0) -> str:
    event = safe_filename_part(row.get("event") or row.get("matchup"), fallback="card")
    workspace_part = safe_filename_part(workspace, fallback="report")
    return f"{workspace_part}_{index + 1:03d}_{event}.png"


def render_card_png(row: Mapping[str, Any], brand: MagazineBrand | Mapping[str, Any] | None = None, *, width: int = 1100) -> bytes:
    """Render one readable, magazine-style PNG card.

    The width parameter is accepted for backward compatibility. The output uses
    a fixed portrait magazine canvas so text remains readable on mobile.
    """
    return render_vintage_card_png(row, brand)


def render_card_deck_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, max_cards: int = 20, width: int = 1100) -> bytes:
    """Render a tall share image containing multiple magazine-style cards."""
    return render_vintage_card_deck_png(cards, brand, max_cards=min(int(max_cards or 8), 8))


def render_magazine_summary_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, top_n: int = 8, width: int = 1200) -> bytes:
    """Render a readable parchment-style magazine summary PNG."""
    return render_vintage_summary_png(pd.DataFrame(cards).head(top_n), brand)
