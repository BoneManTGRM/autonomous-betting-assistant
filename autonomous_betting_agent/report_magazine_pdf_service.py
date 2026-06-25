from __future__ import annotations

import random
from datetime import datetime, timezone
from io import BytesIO
from textwrap import wrap
from typing import Any, Mapping

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from .report_learning_layer_compat import apply_learning_layer_compat
from .report_product_layer import MagazineBrand, event_text, pick_text, safe_text, sport_text, value_text

PDF_HEADER = b"%PDF"
PAGE_W = 768
PAGE_H = 1024
PAPER = (204, 184, 140)
PAPER_DARK = (137, 112, 78)
INK = (34, 28, 22)
MUTED = (84, 70, 54)
RED = (178, 35, 35)
BLACK = (18, 18, 18)
WHITE = (247, 241, 226)
PANEL = (229, 213, 171)
SHADOW = (110, 92, 72)


def _font(size: int = 24) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSerif.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except Exception:
            return ImageFont.load_default()


def _bold(size: int = 24) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSerif-Bold.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
        except Exception:
            return _font(size)


def _brand_value(brand: MagazineBrand | Mapping[str, Any] | None, key: str, default: str) -> str:
    if brand is None:
        return default
    if isinstance(brand, Mapping):
        return safe_text(brand.get(key)) or default
    return safe_text(getattr(brand, key, "")) or default


def _language(brand: MagazineBrand | Mapping[str, Any] | None) -> str:
    raw = _brand_value(brand, "language", "en")
    return "es" if raw.lower().startswith("es") else "en"


def _as_date() -> str:
    return datetime.now(timezone.utc).strftime("%d %b %Y")


def _background(seed: int = 0) -> Image.Image:
    rng = random.Random(seed)
    image = Image.new("RGB", (PAGE_W, PAGE_H), PAPER)
    draw = ImageDraw.Draw(image)
    for _ in range(2600):
        x = rng.randrange(PAGE_W)
        y = rng.randrange(PAGE_H)
        delta = rng.randrange(-24, 25)
        base = tuple(max(0, min(255, c + delta)) for c in PAPER)
        draw.point((x, y), fill=base)
    for _ in range(70):
        x = rng.randrange(-80, PAGE_W)
        y = rng.randrange(-80, PAGE_H)
        r = rng.randrange(12, 95)
        color = (*PAPER_DARK,)
        draw.ellipse((x, y, x + r, y + r), outline=color, width=1)
    return image


def _measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _center(draw: ImageDraw.ImageDraw, y: int, text: str, font: ImageFont.ImageFont, *, fill=INK) -> int:
    w, h = _measure(draw, text, font)
    draw.text(((PAGE_W - w) // 2, y), text, font=font, fill=fill)
    return y + h


def _wrapped(draw: ImageDraw.ImageDraw, x: int, y: int, text: Any, *, font: ImageFont.ImageFont, fill=INK, width: int = 45, gap: int = 8, max_lines: int | None = None) -> int:
    raw = safe_text(text)
    lines = wrap(raw, width=width) if raw else []
    if not lines:
        lines = ["N/A"]
    if max_lines is not None:
        lines = lines[:max_lines]
    line_h = (_measure(draw, "Ag", font)[1] if hasattr(draw, "textbbox") else getattr(font, "size", 24)) + gap
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_h
    return y


def _logo(draw: ImageDraw.ImageDraw, brand_name: str, *, x: int = 590, y: int = 925) -> None:
    draw.rounded_rectangle((x, y, x + 132, y + 48), radius=10, fill=RED, outline=BLACK, width=2)
    draw.text((x + 12, y + 9), brand_name[:13], font=_bold(16), fill=WHITE)


def _stitches(draw: ImageDraw.ImageDraw, y: int) -> None:
    for x in range(-10, PAGE_W + 10, 18):
        draw.line((x, y, x + 10, y + 18), fill=RED, width=3)
        draw.line((x + 10, y, x, y + 18), fill=RED, width=3)


def _vertical_date(draw: ImageDraw.ImageDraw, date_text: str) -> None:
    txt = date_text.upper()
    font = _font(18)
    y = 82
    for ch in txt:
        draw.text((724, y), ch, font=font, fill=WHITE if ch != " " else PAPER)
        y += 21


def _cover_page(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None) -> Image.Image:
    lang = _language(brand)
    image = _background(3)
    draw = ImageDraw.Draw(image)
    brand_name = _brand_value(brand, "brand_name", "ABA Signal Pro")
    title = value_text(_brand_value(brand, "report_title", "Sports Analysis Magazine"), lang)
    tagline = value_text(_brand_value(brand, "tagline", "Premium betting intelligence"), lang)
    generated = _as_date()
    draw.rectangle((704, 0, PAGE_W, PAGE_H), fill=(54, 55, 58))
    _vertical_date(draw, generated)
    _center(draw, 110, brand_name.upper(), _bold(42), fill=RED)
    _center(draw, 168, title, _bold(48), fill=INK)
    _center(draw, 230, tagline, _font(22), fill=MUTED)
    draw.rounded_rectangle((116, 330, 652, 646), radius=32, fill=(232, 217, 180), outline=INK, width=4)
    _center(draw, 385, "OFICIAL +EV" if lang == "es" else "OFFICIAL +EV", _bold(40), fill=INK)
    _center(draw, 440, "INVESTIGACIÓN" if lang == "es" else "RESEARCH", _bold(50 if lang == "es" else 56), fill=RED)
    _center(draw, 512, "REVISTA" if lang == "es" else "MAGAZINE", _bold(48), fill=INK)
    draw.text((150, 595), f"{'Tarjetas' if lang == 'es' else 'Cards'}: {len(cards)}", font=_bold(24), fill=MUTED)
    draw.text((150, 628), f"{'Generado' if lang == 'es' else 'Generated'}: {generated}", font=_font(20), fill=MUTED)
    draw.rounded_rectangle((410, 785, 650, 890), radius=15, fill=BLACK)
    draw.text((432, 812), "DESCARGAR" if lang == "es" else "DOWNLOAD", font=_bold(20 if lang == "es" else 22), fill=WHITE)
    draw.text((432, 846), "PDF REPORTE" if lang == "es" else "REPORT PDF", font=_bold(22), fill=WHITE)
    _logo(draw, brand_name)
    return image


def _sport_title(sport: str, lang: str = "en") -> str:
    value = sport_text(sport, lang) or ("Deportes" if lang == "es" else "Sports")
    return value.title() if len(value) <= 18 else value[:18].title()


def _divider_page(sport: str, brand: MagazineBrand | Mapping[str, Any] | None, seed: int) -> Image.Image:
    lang = _language(brand)
    image = _background(seed)
    draw = ImageDraw.Draw(image)
    title = _sport_title(sport, lang)
    _center(draw, 92, title, _bold(62), fill=INK)
    draw.rounded_rectangle((96, 228, 672, 724), radius=10, fill=PANEL, outline=WHITE, width=7)
    draw.rectangle((132, 270, 636, 680), outline=INK, width=4)
    _center(draw, 365, "DEPORTES" if lang == "es" else "SPORTS", _bold(52 if lang == "es" else 58), fill=RED)
    _center(draw, 435, "ANÁLISIS" if lang == "es" else "ANALYSIS", _bold(52), fill=INK)
    _center(draw, 506, "GUÍA" if lang == "es" else "GUIDE", _bold(58), fill=RED)
    _logo(draw, _brand_value(brand, "brand_name", "ABA Signal Pro"))
    return image


def _bullet_lines(row: Mapping[str, Any], lang: str = "en") -> list[str]:
    candidates = [
        row.get("sports_context_summary"),
        row.get("market_read"),
        row.get("why_it_matters"),
        row.get("game_preview"),
        row.get("learning_status"),
    ]
    lines: list[str] = []
    for value in candidates:
        text = value_text(value, lang)
        if text and text not in lines and "unavailable" not in text.lower() and "no disponible" not in text.lower():
            lines.append(text)
        if len(lines) >= 4:
            break
    if not lines:
        lines = [
            "Modelo, precio y filtros de prueba revisados." if lang == "es" else "Model, price, and proof gates reviewed.",
            "Usa el estado oficial +EV separado del seguimiento de investigación." if lang == "es" else "Use official +EV status separately from research tracking.",
        ]
    return lines[:4]


def _trend(row: Mapping[str, Any], lang: str = "en") -> str:
    return pick_text(row.get("public_pick") or row.get("prediction") or row.get("consumer_action") or "Research / Learning", lang)


def _matchup_page(row: Mapping[str, Any], brand: MagazineBrand | Mapping[str, Any] | None, index: int) -> Image.Image:
    lang = _language(brand)
    image = _background(100 + index)
    draw = ImageDraw.Draw(image)
    _stitches(draw, 8)
    _stitches(draw, 998)
    title = event_text(row.get("public_event") or row.get("event") or row.get("matchup") or "Matchup", lang)
    sport = _sport_title(row.get("sport") or row.get("public_sport"), lang)

    # photo-style grayscale placeholder panel
    draw.rectangle((42, 112, 244, 942), fill=(205, 199, 187))
    draw.rectangle((44, 114, 242, 940), outline=WHITE, width=2)
    for y in range(145, 900, 46):
        shade = 165 + (y % 70)
        draw.ellipse((70, y, 216, y + 92), outline=(shade, shade, shade), width=3)
    draw.text((72, 520), sport.upper(), font=_bold(25), fill=(96, 91, 84))

    text_x = 290
    y = 82
    title_lines = wrap(title, width=22)[:3]
    for line in title_lines:
        w, _ = _measure(draw, line, _bold(37))
        draw.text((text_x + max(0, (390 - w) // 2), y), line, font=_bold(37), fill=INK)
        y += 47
    draw.text((text_x + 160, y), "VS" if " vs " in title.lower() else ("SELECCIÓN" if lang == "es" else "PICK"), font=_bold(22 if lang == "es" else 25), fill=INK)
    y += 58

    for bullet in _bullet_lines(row, lang):
        draw.text((text_x, y), "-", font=_bold(34), fill=BLACK)
        y = _wrapped(draw, text_x + 36, y, bullet, font=_font(25), fill=INK, width=33, gap=7, max_lines=4)
        y += 20
        if y > 695:
            break

    panel_y = 760
    draw.rounded_rectangle((text_x + 50, panel_y, 690, panel_y + 116), radius=18, fill=(226, 209, 166), outline=SHADOW, width=2)
    draw.text((text_x + 92, panel_y + 18), "Tendencia" if lang == "es" else "Tendency", font=_bold(35), fill=INK)
    _wrapped(draw, text_x + 92, panel_y + 62, _trend(row, lang), font=_bold(25), fill=BLACK, width=24, gap=5, max_lines=2)
    _logo(draw, _brand_value(brand, "brand_name", "ABA Signal Pro"))
    return image


def render_vintage_magazine_pdf(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, max_cards: int = 20) -> bytes:
    frame = apply_learning_layer_compat(pd.DataFrame(cards).copy()).head(max_cards)
    lang = _language(brand)
    if frame.empty:
        frame = pd.DataFrame([{"event": "No cards available", "sport": "Sports", "consumer_action": "Research / Learning"}])
    pages: list[Image.Image] = [_cover_page(frame, brand)]
    last_sport = None
    for idx, (_, row) in enumerate(frame.iterrows()):
        rowd = row.to_dict()
        sport = safe_text(rowd.get("sport") or rowd.get("public_sport")) or ("Deportes" if lang == "es" else "Sports")
        if sport != last_sport:
            pages.append(_divider_page(sport, brand, seed=20 + idx))
            last_sport = sport
        pages.append(_matchup_page(rowd, brand, idx))
    output = BytesIO()
    first, rest = pages[0], pages[1:]
    first.save(output, format="PDF", save_all=True, append_images=rest, resolution=144.0)
    return output.getvalue()
