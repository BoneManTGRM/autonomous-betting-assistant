from __future__ import annotations

import random
from io import BytesIO
from textwrap import wrap
from typing import Any, Mapping

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from .report_learning_layer_compat import apply_learning_layer_compat
from .report_product_layer import MagazineBrand, safe_text

PAGE_W, PAGE_H = 768, 1024
PAPER = (207, 188, 143)
PAPER_DARK = (135, 112, 79)
INK = (31, 25, 20)
MUTED = (85, 70, 54)
RED = (178, 35, 35)
WHITE = (247, 241, 226)
PANEL = (229, 213, 171)
SHADOW = (110, 92, 72)
BLACK = (18, 18, 18)
PNG_HEADER = b"\x89PNG\r\n\x1a\n"


def _font(size: int = 24):
    for name in ("DejaVuSerif.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _bold(size: int = 24):
    for name in ("DejaVuSerif-Bold.ttf", "DejaVuSans-Bold.ttf", "DejaVuSerif.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _brand(brand: MagazineBrand | Mapping[str, Any] | None, key: str, default: str) -> str:
    if isinstance(brand, Mapping):
        return safe_text(brand.get(key)) or default
    if brand is not None:
        return safe_text(getattr(brand, key, "")) or default
    return default


def _png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG", optimize=False)
    return out.getvalue()


def _paper(seed: int) -> Image.Image:
    rng = random.Random(seed)
    image = Image.new("RGB", (PAGE_W, PAGE_H), PAPER)
    draw = ImageDraw.Draw(image)
    for _ in range(2600):
        x, y = rng.randrange(PAGE_W), rng.randrange(PAGE_H)
        d = rng.randrange(-25, 26)
        draw.point((x, y), fill=tuple(max(0, min(255, c + d)) for c in PAPER))
    for _ in range(80):
        x, y, r = rng.randrange(-90, PAGE_W), rng.randrange(-90, PAGE_H), rng.randrange(10, 100)
        draw.ellipse((x, y, x + r, y + r), outline=PAPER_DARK, width=1)
    return image


def _measure(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _center(draw: ImageDraw.ImageDraw, y: int, text: str, font, fill=INK) -> int:
    w, h = _measure(draw, text, font)
    draw.text(((PAGE_W - w) // 2, y), text, font=font, fill=fill)
    return y + h


def _wrap(draw: ImageDraw.ImageDraw, x: int, y: int, text: Any, font, fill=INK, width: int = 36, max_lines: int = 4) -> int:
    lines = wrap(safe_text(text), width=width)[:max_lines] or ["N/A"]
    step = _measure(draw, "Ag", font)[1] + 8
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += step
    return y


def _logo(draw: ImageDraw.ImageDraw, brand: str) -> None:
    draw.rounded_rectangle((590, 925, 722, 973), radius=10, fill=RED, outline=BLACK, width=2)
    draw.text((602, 934), brand[:13], font=_bold(16), fill=WHITE)


def _stitches(draw: ImageDraw.ImageDraw, y: int) -> None:
    for x in range(-10, PAGE_W + 10, 18):
        draw.line((x, y, x + 10, y + 18), fill=RED, width=3)
        draw.line((x + 10, y, x, y + 18), fill=RED, width=3)


def _trend(row: Mapping[str, Any]) -> str:
    return safe_text(row.get("public_pick") or row.get("prediction") or row.get("consumer_action") or "Research / Learning")


def _bullets(row: Mapping[str, Any]) -> list[str]:
    fields = ("sports_context_summary", "market_read", "why_it_matters", "game_preview", "learning_status")
    out: list[str] = []
    for field in fields:
        text = safe_text(row.get(field))
        if text and "unavailable" not in text.lower() and text not in out:
            out.append(text)
        if len(out) >= 4:
            break
    return out or ["Model, price, and proof gates reviewed.", "Official +EV status is separate from research tracking."]


def _sport_title(value: Any) -> str:
    text = safe_text(value) or "Sports"
    return text.title()[:18]


def vintage_card_image(row: Mapping[str, Any], brand: MagazineBrand | Mapping[str, Any] | None = None, index: int = 0) -> Image.Image:
    row = dict(row or {})
    image = _paper(100 + index)
    draw = ImageDraw.Draw(image)
    _stitches(draw, 8)
    _stitches(draw, 998)
    brand_name = _brand(brand, "brand_name", "ABA Signal Pro")
    title = safe_text(row.get("event") or row.get("matchup")) or "Matchup"
    sport = _sport_title(row.get("sport") or row.get("public_sport"))
    draw.rectangle((42, 112, 244, 942), fill=(205, 199, 187))
    draw.rectangle((44, 114, 242, 940), outline=WHITE, width=2)
    for y in range(145, 900, 46):
        draw.ellipse((70, y, 216, y + 92), outline=(165, 160, 150), width=3)
    draw.text((72, 520), sport.upper(), font=_bold(25), fill=(96, 91, 84))
    text_x, y = 290, 80
    for line in wrap(title, width=22)[:3]:
        w, _ = _measure(draw, line, _bold(37))
        draw.text((text_x + max(0, (390 - w) // 2), y), line, font=_bold(37), fill=INK)
        y += 47
    draw.text((text_x + 160, y), "VS" if " vs " in title.lower() or " at " in title.lower() else "PICK", font=_bold(25), fill=INK)
    y += 58
    for bullet in _bullets(row):
        draw.text((text_x, y), "•", font=_bold(31), fill=BLACK)
        y = _wrap(draw, text_x + 36, y, bullet, _font(25), width=33, max_lines=4)
        y += 20
        if y > 700:
            break
    draw.rounded_rectangle((340, 760, 690, 876), radius=18, fill=PANEL, outline=SHADOW, width=2)
    draw.text((382, 778), "Tendency", font=_bold(35), fill=INK)
    _wrap(draw, 382, 822, _trend(row), _bold(25), width=24, max_lines=2)
    _logo(draw, brand_name)
    return image


def render_vintage_card_png(row: Mapping[str, Any], brand: MagazineBrand | Mapping[str, Any] | None = None, *, index: int = 0) -> bytes:
    return _png(vintage_card_image(row, brand, index))


def render_vintage_card_deck_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, max_cards: int = 8) -> bytes:
    frame = apply_learning_layer_compat(pd.DataFrame(cards).copy()).head(max_cards)
    if frame.empty:
        frame = pd.DataFrame([{"event": "No cards available", "sport": "Sports", "consumer_action": "Research / Learning"}])
    pages = [vintage_card_image(row.to_dict(), brand, i) for i, (_, row) in enumerate(frame.iterrows())]
    deck = Image.new("RGB", (PAGE_W, PAGE_H * len(pages)), PAPER)
    for i, page in enumerate(pages):
        deck.paste(page, (0, i * PAGE_H))
    return _png(deck)


def render_vintage_summary_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None) -> bytes:
    frame = apply_learning_layer_compat(pd.DataFrame(cards).copy()).head(8)
    if frame.empty:
        frame = pd.DataFrame([{"event": "No cards available", "prediction": "Research / Learning"}])
    image = _paper(7)
    draw = ImageDraw.Draw(image)
    brand_name = _brand(brand, "brand_name", "ABA Signal Pro")
    report_title = _brand(brand, "report_title", "Daily Sports Analysis")
    _center(draw, 60, brand_name.upper(), _bold(30), fill=RED)
    _center(draw, 112, report_title, _bold(46), fill=INK)
    draw.text((78, 178), "Top Cards", font=_bold(31), fill=MUTED)
    y = 230
    for idx, (_, row) in enumerate(frame.iterrows(), start=1):
        item = row.to_dict()
        event = safe_text(item.get("event")) or "Matchup"
        pick = _trend(item)
        action = safe_text(item.get("consumer_action") or item.get("recommended_action")) or "Research / Learning"
        draw.rounded_rectangle((78, y, 690, y + 76), radius=14, fill=PANEL, outline=SHADOW, width=1)
        draw.text((98, y + 10), f"{idx}. {event[:40]}", font=_bold(20), fill=INK)
        draw.text((98, y + 42), pick[:45], font=_font(19), fill=MUTED)
        draw.text((482, y + 28), action[:23], font=_bold(16), fill=RED if "Official" in action else BLACK)
        y += 88
        if y > 900:
            break
    _logo(draw, brand_name)
    return _png(image)
