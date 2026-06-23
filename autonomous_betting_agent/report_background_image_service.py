from __future__ import annotations

from io import BytesIO
from textwrap import wrap
from typing import Any, Mapping

import pandas as pd
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .report_learning_layer_compat import apply_learning_layer_compat
from .report_product_layer import MagazineBrand, safe_text

PNG_HEADER = b"\x89PNG\r\n\x1a\n"
PAGE_W = 1080
PAGE_H = 1350
INK = (255, 255, 255)
MUTED = (225, 232, 244)
GOLD = (255, 204, 85)
PANEL = (8, 12, 22, 188)
PANEL_STRONG = (8, 12, 22, 220)
BORDER = (255, 255, 255, 165)


def _font(size: int = 42):
    for name in ("DejaVuSerif.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _bold(size: int = 42):
    for name in ("DejaVuSerif-Bold.ttf", "DejaVuSans-Bold.ttf", "DejaVuSerif.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _brand_value(brand: MagazineBrand | Mapping[str, Any] | None, key: str, default: str) -> str:
    if isinstance(brand, Mapping):
        return safe_text(brand.get(key)) or default
    if brand is not None:
        return safe_text(getattr(brand, key, "")) or default
    return default


def _background(background_bytes: bytes | None) -> Image.Image:
    if background_bytes:
        try:
            src = Image.open(BytesIO(background_bytes)).convert("RGB")
        except Exception:
            src = Image.new("RGB", (PAGE_W, PAGE_H), (38, 48, 70))
    else:
        src = Image.new("RGB", (PAGE_W, PAGE_H), (38, 48, 70))
    scale = max(PAGE_W / src.width, PAGE_H / src.height)
    resized = src.resize((int(src.width * scale), int(src.height * scale)))
    left = max(0, (resized.width - PAGE_W) // 2)
    top = max(0, (resized.height - PAGE_H) // 2)
    canvas = resized.crop((left, top, left + PAGE_W, top + PAGE_H))
    canvas = ImageEnhance.Color(canvas).enhance(0.82)
    canvas = ImageEnhance.Brightness(canvas).enhance(0.82)
    return canvas.filter(ImageFilter.GaussianBlur(radius=0.35)).convert("RGBA")


def _png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.convert("RGB").save(out, format="PNG", optimize=False)
    return out.getvalue()


def _measure(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _center(draw: ImageDraw.ImageDraw, y: int, text: str, font, fill=INK) -> int:
    w, h = _measure(draw, text, font)
    draw.text(((PAGE_W - w) // 2, y), text, font=font, fill=fill)
    return y + h


def _wrapped(draw: ImageDraw.ImageDraw, x: int, y: int, text: Any, font, *, width: int = 34, fill=INK, max_lines: int = 5, line_gap: int = 10) -> int:
    lines = wrap(safe_text(text), width=width)[:max_lines] or ["N/A"]
    step = _measure(draw, "Ag", font)[1] + line_gap
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += step
    return y


def _trend(row: Mapping[str, Any]) -> str:
    return safe_text(row.get("public_pick") or row.get("prediction") or row.get("consumer_action") or "Research / Learning")


def _bullets(row: Mapping[str, Any]) -> list[str]:
    fields = ("sports_context_summary", "market_read", "why_it_matters", "game_preview", "learning_status")
    out: list[str] = []
    for field in fields:
        text = safe_text(row.get(field))
        if text and "unavailable" not in text.lower() and text not in out:
            out.append(text)
        if len(out) >= 3:
            break
    return out or ["Price, model, and proof gates reviewed.", "This is client-safe research unless it passes official +EV rules."]


def render_custom_background_card_png(row: Mapping[str, Any], brand: MagazineBrand | Mapping[str, Any] | None = None, *, background_bytes: bytes | None = None, index: int = 0) -> bytes:
    row = dict(row or {})
    image = _background(background_bytes)
    draw = ImageDraw.Draw(image, "RGBA")
    brand_name = _brand_value(brand, "brand_name", "ABA Signal Pro")
    title = safe_text(row.get("event") or row.get("matchup")) or "Matchup"
    sport = safe_text(row.get("sport") or row.get("public_sport")) or "Sports"
    action = safe_text(row.get("consumer_action") or row.get("recommended_action")) or "Research / Learning"
    draw.rectangle((0, 0, PAGE_W, PAGE_H), fill=(0, 0, 0, 52))
    draw.rounded_rectangle((58, 58, PAGE_W - 58, PAGE_H - 58), radius=34, outline=BORDER, width=3, fill=(0, 0, 0, 34))
    draw.text((92, 92), brand_name.upper(), font=_bold(32), fill=GOLD)
    draw.text((92, 142), sport.upper(), font=_font(28), fill=MUTED)
    y = 222
    for line in wrap(title, width=20)[:3]:
        y = _center(draw, y, line, _bold(68), fill=INK) + 8
    y += 18
    draw.rounded_rectangle((135, y, PAGE_W - 135, y + 84), radius=30, fill=PANEL_STRONG, outline=BORDER, width=2)
    _center(draw, y + 18, action, _bold(38), fill=GOLD)
    y += 134
    for bullet in _bullets(row):
        draw.text((108, y), "•", font=_bold(48), fill=GOLD)
        y = _wrapped(draw, 168, y, bullet, _font(44), width=31, fill=INK, max_lines=3, line_gap=12)
        y += 34
        if y > 935:
            break
    draw.rounded_rectangle((210, 1026, PAGE_W - 210, 1186), radius=32, fill=PANEL_STRONG, outline=BORDER, width=2)
    _center(draw, 1052, "TENDENCY", _bold(42), fill=GOLD)
    _center(draw, 1120, _trend(row)[:27], _bold(47), fill=INK)
    return _png(image)


def render_custom_background_summary_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, background_bytes: bytes | None = None, top_n: int = 7) -> bytes:
    frame = apply_learning_layer_compat(pd.DataFrame(cards).copy()).head(top_n)
    if frame.empty:
        frame = pd.DataFrame([{"event": "No cards available", "prediction": "Research / Learning"}])
    image = _background(background_bytes)
    draw = ImageDraw.Draw(image, "RGBA")
    brand_name = _brand_value(brand, "brand_name", "ABA Signal Pro")
    title = _brand_value(brand, "report_title", "Daily Sports Analysis")
    draw.rectangle((0, 0, PAGE_W, PAGE_H), fill=(0, 0, 0, 48))
    _center(draw, 72, brand_name.upper(), _bold(43), fill=GOLD)
    _center(draw, 148, title, _bold(74), fill=INK)
    draw.text((80, 276), "TOP CARDS", font=_bold(51), fill=GOLD)
    y = 365
    for idx, (_, row) in enumerate(frame.iterrows(), start=1):
        item = row.to_dict()
        event = safe_text(item.get("event")) or "Matchup"
        pick = _trend(item)
        action = safe_text(item.get("consumer_action") or item.get("recommended_action")) or "Research / Learning"
        draw.rounded_rectangle((70, y, PAGE_W - 70, y + 122), radius=28, fill=PANEL, outline=BORDER, width=3)
        draw.text((108, y + 18), f"{idx}. {event[:36]}", font=_bold(34), fill=INK)
        draw.text((108, y + 70), pick[:37], font=_font(31), fill=MUTED)
        draw.text((PAGE_W - 400, y + 44), action[:23], font=_bold(30), fill=GOLD)
        y += 145
        if y > 1210:
            break
    return _png(image)


def render_custom_background_deck_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, background_bytes: bytes | None = None, max_cards: int = 8) -> bytes:
    frame = apply_learning_layer_compat(pd.DataFrame(cards).copy()).head(max_cards)
    if frame.empty:
        frame = pd.DataFrame([{"event": "No cards available", "prediction": "Research / Learning"}])
    pages = []
    for idx, (_, row) in enumerate(frame.iterrows()):
        page_bytes = render_custom_background_card_png(row.to_dict(), brand, background_bytes=background_bytes, index=idx)
        pages.append(Image.open(BytesIO(page_bytes)).convert("RGB"))
    deck = Image.new("RGB", (PAGE_W, PAGE_H * len(pages)), (20, 24, 34))
    for idx, page in enumerate(pages):
        deck.paste(page, (0, idx * PAGE_H))
    return _png(deck)
