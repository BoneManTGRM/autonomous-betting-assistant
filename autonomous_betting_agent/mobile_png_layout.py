from __future__ import annotations

from io import BytesIO
from pathlib import Path
from textwrap import wrap
from typing import Any, Mapping

import pandas as pd
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from .report_product_layer import MagazineBrand, safe_text

W = 1080
BG = (35, 42, 62)
WHITE = (255, 255, 255)
SOFT = (226, 233, 245)
GOLD = (255, 214, 79)
GREEN = (125, 245, 180)
PANEL = (18, 22, 35)

FONT_DIRS = [
    Path('/usr/share/fonts/truetype/dejavu'),
    Path('/usr/local/share/fonts'),
    Path('/usr/share/fonts'),
]


def _font_candidates(bold_weight: bool) -> list[str]:
    names = ['DejaVuSans-Bold.ttf', 'DejaVuSerif-Bold.ttf', 'Arial Bold.ttf'] if bold_weight else ['DejaVuSans.ttf', 'DejaVuSerif.ttf', 'Arial.ttf']
    out = names[:]
    for directory in FONT_DIRS:
        for name in names:
            out.append(str(directory / name))
    return out


def font(size: int):
    for name in _font_candidates(False):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def bold(size: int):
    for name in _font_candidates(True):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def brand_value(brand: MagazineBrand | Mapping[str, Any] | None, key: str, default: str) -> str:
    if isinstance(brand, Mapping):
        return safe_text(brand.get(key)) or default
    if brand is not None:
        return safe_text(getattr(brand, key, '')) or default
    return default


def first(row: Mapping[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = safe_text(row.get(name))
        if value:
            return value
    return ''


def card_text(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    event = safe_text(row.get('event') or row.get('matchup')) or 'Matchup'
    pick = first(row, ('public_pick', 'prediction', 'consumer_action', 'recommended_action')) or 'Research / Learning'
    status = first(row, ('consumer_action', 'recommended_action', 'official_status_label', 'price_value_label')) or 'Research'
    sport = first(row, ('public_sport', 'sport', 'league')) or 'Sports'
    market = first(row, ('market_type', 'market')) or 'Market'
    price = safe_text(row.get('decimal_price') or row.get('best_price') or row.get('odds_decimal')) or 'N/A'
    detail = f'{sport}  |  {market}  |  Price {price}'
    return event, pick, status, detail


def panel(image: Image.Image, box: tuple[int, int, int, int], *, alpha: int = 132) -> None:
    overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, 'RGBA')
    draw.rounded_rectangle(box, radius=34, fill=(*PANEL, alpha), outline=(*WHITE, 225), width=4)
    image.paste(Image.alpha_composite(image.convert('RGBA'), overlay).convert('RGB'))


def write_wrap(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, fnt, width: int, max_lines: int, fill=WHITE, gap: int = 8) -> int:
    bbox = draw.textbbox((0, 0), 'Ag', font=fnt)
    h = (bbox[3] - bbox[1]) + gap
    for line in (wrap(safe_text(text), width=width)[:max_lines] or ['N/A']):
        draw.text((x, y), line, font=fnt, fill=fill)
        y += h
    return y


def _crop_background(background_bytes: bytes | None, height: int) -> Image.Image:
    try:
        bg = Image.open(BytesIO(background_bytes or b'')).convert('RGB') if background_bytes else Image.new('RGB', (W, height), BG)
        scale = max(W / bg.width, height / bg.height)
        bg = bg.resize((int(bg.width * scale), int(bg.height * scale)))
        left = max(0, (bg.width - W) // 2)
        top = max(0, (bg.height - height) // 2)
        return bg.crop((left, top, left + W, top + height))
    except Exception:
        return Image.new('RGB', (W, height), BG)


def render_mobile_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, background_bytes: bytes | None = None, top_n: int = 3) -> bytes:
    frame = pd.DataFrame(cards).head(min(int(top_n or 3), 3))
    if frame.empty:
        frame = pd.DataFrame([{'event': 'No rows available', 'prediction': 'Research / Learning'}])
    card_h = 305
    header_h = 285
    gap = 34
    height = header_h + len(frame) * (card_h + gap) + 78
    bg = _crop_background(background_bytes, height)
    img = ImageEnhance.Brightness(bg).enhance(0.78)
    img = ImageEnhance.Color(img).enhance(1.05)

    panel(img, (42, 38, W - 42, 246), alpha=118)
    draw = ImageDraw.Draw(img)
    title = brand_value(brand, 'report_title', 'Daily Sports Analysis')
    name = brand_value(brand, 'brand_name', 'ABA Signal Pro')
    draw.text((82, 70), name.upper()[:30], font=bold(44), fill=GOLD)
    draw.text((82, 130), title[:32], font=bold(54), fill=WHITE)
    draw.text((82, 196), 'Mobile readable report - 3 cards per image', font=font(30), fill=SOFT)

    y = header_h
    for idx, (_, row) in enumerate(frame.iterrows(), start=1):
        event, pick, status, detail = card_text(row.to_dict())
        panel(img, (58, y, W - 58, y + card_h), alpha=132)
        draw = ImageDraw.Draw(img)
        write_wrap(draw, 96, y + 24, f'{idx}. {event}', bold(42), 38, 2, WHITE, gap=5)
        draw.text((96, y + 116), 'PICK', font=bold(30), fill=SOFT)
        write_wrap(draw, 188, y + 106, pick, bold(48), 29, 2, GOLD, gap=4)
        draw.text((96, y + 206), status[:32], font=bold(34), fill=GREEN)
        write_wrap(draw, 96, y + 252, detail, bold(29), 48, 1, SOFT)
        y += card_h + gap

    out = BytesIO()
    img.save(out, format='PNG', optimize=False)
    return out.getvalue()
