"""Full pick magazine book image exports.

The functions in this module render local, subscriber-facing magazine images from
already-supplied pick rows. They do not fetch live data, place bets, expose API
keys, or guarantee outcomes.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from io import BytesIO
import re
from typing import Any, Iterable, Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw, ImageFont

PAGE_WIDTH = 1080
PAGE_HEIGHT = 1920
CARD_WIDTH = 1080
CARD_HEIGHT = 620
COMPACT_MAGAZINE_CARDS = 3
BRAND_YELLOW = (248, 211, 80)
SECTION_GREEN = (102, 220, 154)
TEXT_WHITE = (245, 245, 245)
TEXT_MUTED = (215, 215, 215)
BORDER_WHITE = (245, 245, 245)
DARK_OVERLAY = (12, 14, 22, 185)
SAFETY_FOOTER = "Analytics only. No guaranteed wins or profit. No bet execution."


def _row(row: Any) -> Mapping[str, Any]:
    if isinstance(row, Mapping):
        return row
    if is_dataclass(row):
        return asdict(row)
    if hasattr(row, "as_dict"):
        data = row.as_dict()
        return data if isinstance(data, Mapping) else {}
    if hasattr(row, "__dict__"):
        return row.__dict__
    return {}


def _text(row: Any, *keys: str, default: str = "") -> str:
    data = _row(row)
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _num(row: Any, *keys: str) -> float | None:
    data = _row(row)
    for key in keys:
        value = data.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _prob(row: Any, *keys: str) -> float | None:
    value = _num(row, *keys)
    if value is None:
        return None
    if value > 1:
        value /= 100.0
    return max(0.0, min(1.0, value))


def _fmt_pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.0%}"


def _fmt_edge(value: float | None) -> str:
    if value is None:
        return "N/A"
    if abs(value) > 1:
        value /= 100.0
    return f"{value:+.1%}"


def _fmt_num(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.3f}"


def _game(row: Any) -> str:
    return _text(row, "game", "event", "event_name", "matchup", default="Unknown Game")


def _pick(row: Any) -> str:
    return _text(row, "exact_bet", "pick", "selection", "prediction", default="Pick not specified")


def sanitize_image_filename(value: str, suffix: str = "", extension: str = "png") -> str:
    clean = re.sub(r"[^A-Za-z0-9]+", "_", (value or "magazine").strip().lower()).strip("_")
    if not clean:
        clean = "magazine"
    if suffix:
        suffix_clean = re.sub(r"[^A-Za-z0-9]+", "_", suffix.strip().lower()).strip("_")
        if suffix_clean:
            clean = f"{clean}_{suffix_clean}"
    ext = (extension or "png").strip().lstrip(".") or "png"
    return f"{clean}.{ext}"


def pick_full_page_filename(pick: Any, index: int, extension: str = "png") -> str:
    return sanitize_image_filename(f"pick_{index:02d}_{_game(pick)}", "full_page", extension)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _load_background(background_image: Any, size: tuple[int, int]) -> Image.Image:
    if background_image is None:
        base = Image.new("RGB", size, (22, 24, 32))
        draw = ImageDraw.Draw(base)
        for y in range(size[1]):
            shade = int(28 + 28 * y / max(size[1], 1))
            draw.line([(0, y), (size[0], y)], fill=(shade, shade, shade + 10))
        return base
    try:
        if isinstance(background_image, Image.Image):
            img = background_image.convert("RGB")
        elif isinstance(background_image, (bytes, bytearray)):
            img = Image.open(BytesIO(background_image)).convert("RGB")
        elif hasattr(background_image, "read"):
            img = Image.open(background_image).convert("RGB")
        else:
            img = Image.open(str(background_image)).convert("RGB")
    except Exception:
        return _load_background(None, size)
    img_ratio = img.width / img.height
    target_ratio = size[0] / size[1]
    if img_ratio > target_ratio:
        new_height = size[1]
        new_width = int(new_height * img_ratio)
    else:
        new_width = size[0]
        new_height = int(new_width / img_ratio)
    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    left = max(0, (new_width - size[0]) // 2)
    top = max(0, (new_height - size[1]) // 2)
    return img.crop((left, top, left + size[0], top + size[1]))


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _draw_rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], *, radius: int = 28, fill=DARK_OVERLAY, outline=BORDER_WHITE, width: int = 3) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int, max_lines: int | None = None) -> list[str]:
    words = str(text or "").replace("\n", " ").split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = word if not current else f"{current} {word}"
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
            if max_lines and len(lines) >= max_lines:
                break
    if current and (max_lines is None or len(lines) < max_lines):
        lines.append(current)
    if max_lines and len(lines) == max_lines and len(" ".join(words)) > len(" ".join(lines)):
        lines[-1] = lines[-1].rstrip(".,;") + "..."
    return lines


def _draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font: ImageFont.ImageFont, fill=TEXT_WHITE, max_width: int | None = None, max_lines: int | None = None, line_gap: int = 8) -> int:
    x, y = xy
    if max_width is None:
        draw.text((x, y), str(text), font=font, fill=fill)
        return y + draw.textbbox((x, y), str(text), font=font)[3] - y + line_gap
    for line in _wrap(draw, str(text), font, max_width, max_lines=max_lines):
        draw.text((x, y), line, font=font, fill=fill)
        y += draw.textbbox((x, y), line, font=font)[3] - y + line_gap
    return y


def _bullets_from(row: Any, *, fallback: str, max_items: int = 8) -> list[str]:
    supplied = _text(row, "why_bullets", "why_we_picked_it", "why_pick", "analysis_summary", "reason", "explanation")
    bullets: list[str] = []
    if supplied:
        normalized = supplied.replace("\r", "\n").replace("•", "\n").replace(";", "\n").replace("|", "\n")
        bullets.extend(part.strip(" -•\t") for part in normalized.split("\n") if part.strip(" -•\t"))
    if not bullets:
        confidence = _fmt_pct(_prob(row, "model_probability", "confidence", "confidence_score"))
        edge = _fmt_edge(_num(row, "edge", "expected_value", "ev"))
        bullets = [
            f"Model projects {confidence} confidence from uploaded data",
            f"Market edge checks at {edge}",
            "Odds and market should be rechecked before lock",
            "Professional evidence pending from uploaded data",
            fallback,
        ]
    return bullets[:max_items]


def _pro_evidence(row: Any) -> list[str]:
    fields = [
        (("market_movement", "line_movement", "sharp_money_signal"), "Market movement"),
        (("injury_report", "starting_lineups", "lineup_status"), "Injury/lineup status"),
        (("weather_impact", "wind_speed", "wind_direction"), "Weather/wind"),
        (("team_form", "player_form", "recent_trend"), "Team/player form"),
        (("matchup_edge", "offensive_efficiency", "defensive_efficiency"), "Matchup edge"),
        (("travel_fatigue", "rest_advantage", "back_to_back"), "Travel/fatigue"),
        (("sportsbook_discrepancy", "line_shopping_edge", "best_price_edge"), "Sportsbook price gap"),
        (("public_betting", "news_signal", "news_sentiment"), "Sharp/public signal"),
        (("pitcher_handedness", "left_right_split", "pitcher_vs_batter_handedness"), "L/R split"),
        (("bullpen_fatigue", "bullpen_usage_last_3_days"), "Bullpen fatigue"),
        (("park_factor", "stadium_factor"), "Park factor"),
        (("umpire_tendency", "referee_tendency"), "Ref/umpire tendency"),
    ]
    evidence: list[str] = []
    for keys, label in fields:
        value = _text(row, *keys)
        if value:
            evidence.append(f"{label}: {value}")
    if not evidence:
        evidence.append("Professional evidence pending from uploaded data")
        evidence.append("Recheck odds, injuries, lineups, and weather before betting")
    return evidence[:10]


def _risk_bullets(row: Any) -> list[str]:
    supplied = _text(row, "why_lose", "risk_reason", "hidden_risk", "risk_bullets")
    if supplied:
        normalized = supplied.replace("\r", "\n").replace("•", "\n").replace(";", "\n").replace("|", "\n")
        return [part.strip(" -•\t") for part in normalized.split("\n") if part.strip(" -•\t")][:5]
    return [
        "Avoid if injury or lineup data changes",
        "Avoid if odds move below playable threshold",
        "Recheck weather and market movement before start",
        "Small stake only if key data remains uncertain",
    ]


def _chain_notes(row: Any) -> list[str]:
    notes = []
    for keys, label in (
        (("main_read", "primary_leg"), "Main Read"),
        (("add_on_legs", "secondary_legs"), "Add-On Legs"),
        (("filler_leg_risk",), "Filler Leg Risk"),
        (("correlation_label", "correlation"), "Correlation"),
        (("straight_bet_alternative", "better_straight_or_chain"), "Better Straight or Chain"),
        (("chain_probability", "combined_adjusted_probability"), "Chain Confidence"),
    ):
        value = _text(row, *keys)
        if value:
            notes.append(f"{label}: {value}")
    if not notes:
        notes.append("CHAIN VERDICT: Better as straight bet. Do not add weak filler legs.")
    return notes[:6]


def render_card_image(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1) -> Image.Image:
    image = _load_background(background_image, (CARD_WIDTH, CARD_HEIGHT)).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 95))
    image.alpha_composite(overlay)
    draw = ImageDraw.Draw(image)
    _draw_rounded(draw, (42, 36, CARD_WIDTH - 42, CARD_HEIGHT - 36), radius=26, fill=(10, 12, 18, 178), width=3)
    title_font = _font(34, True)
    pick_font = _font(42, False)
    small_font = _font(23)
    y = 72
    draw.text((76, y), f"{page_number}. {_game(pick)}", font=title_font, fill=TEXT_WHITE)
    y += 64
    draw.text((76, y), "PICK", font=small_font, fill=TEXT_WHITE)
    draw.text((180, y - 12), _pick(pick), font=pick_font, fill=BRAND_YELLOW)
    y += 72
    draw.text((76, y), "Price Watch / Research", font=_font(30), fill=SECTION_GREEN)
    y += 44
    details = f"Teams: {_game(pick)}  |  Market: {_text(pick, 'market', 'bet_type', default='N/A')}  |  Odds: {_text(pick, 'current_odds', 'odds', 'decimal_odds', 'american_odds', default='N/A')}"
    y = _draw_text(draw, (76, y), details, small_font, TEXT_WHITE, max_width=CARD_WIDTH - 152, max_lines=2)
    why = _bullets_from(pick, fallback="Wins if the listed pick condition is met", max_items=1)[0]
    _draw_text(draw, (76, y + 6), why, small_font, TEXT_MUTED, max_width=CARD_WIDTH - 152, max_lines=2)
    return image.convert("RGB")


def render_card_image_png(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1) -> bytes:
    return _png_bytes(render_card_image(pick, background_image, report_name, page_number))


def render_compact_magazine_png(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, cards_per_page: int = COMPACT_MAGAZINE_CARDS) -> bytes:
    pick_list = list(picks)[: max(1, cards_per_page)]
    image = _load_background(background_image, (PAGE_WIDTH, PAGE_HEIGHT)).convert("RGBA")
    image.alpha_composite(Image.new("RGBA", image.size, (0, 0, 0, 105)))
    draw = ImageDraw.Draw(image)
    _draw_rounded(draw, (50, 62, PAGE_WIDTH - 50, 260), radius=28, fill=(10, 12, 18, 155), width=3)
    draw.text((82, 104), "ABA SIGNAL PRO", font=_font(36, True), fill=BRAND_YELLOW)
    draw.text((82, 154), report_name or "Daily Sports Analysis", font=_font(44), fill=TEXT_WHITE)
    draw.text((82, 210), "Mobile readable report - 3 cards per image", font=_font(24), fill=TEXT_MUTED)
    y = 330
    for index, pick in enumerate(pick_list, start=1):
        box_h = 410
        _draw_rounded(draw, (70, y, PAGE_WIDTH - 70, y + box_h), radius=26, fill=(10, 12, 18, 180), width=3)
        draw.text((106, y + 36), f"{index}. {_game(pick)}", font=_font(34, True), fill=TEXT_WHITE)
        draw.text((106, y + 112), "PICK", font=_font(22), fill=TEXT_WHITE)
        draw.text((196, y + 100), _pick(pick), font=_font(38), fill=BRAND_YELLOW)
        draw.text((106, y + 174), "Price Watch / Research", font=_font(28), fill=SECTION_GREEN)
        detail = f"Teams: {_game(pick)} | Market: {_text(pick, 'market', 'bet_type', default='N/A')} | Odds: {_text(pick, 'current_odds', 'odds', 'decimal_odds', default='N/A')}"
        _draw_text(draw, (106, y + 220), detail, _font(22), TEXT_WHITE, max_width=PAGE_WIDTH - 212, max_lines=2)
        _draw_text(draw, (106, y + 286), _bullets_from(pick, fallback="Wins if pick condition is met", max_items=1)[0], _font(22), TEXT_MUTED, max_width=PAGE_WIDTH - 212, max_lines=2)
        y += box_h + 48
    draw.text((PAGE_WIDTH // 2 - 190, PAGE_HEIGHT - 72), "Generated Magazine PNG preview", font=_font(24), fill=TEXT_MUTED)
    return _png_bytes(image.convert("RGB"))


def render_full_pick_magazine_page(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1) -> Image.Image:
    image = _load_background(background_image, (PAGE_WIDTH, PAGE_HEIGHT)).convert("RGBA")
    image.alpha_composite(Image.new("RGBA", image.size, (0, 0, 0, 118)))
    draw = ImageDraw.Draw(image)
    margin = 54
    _draw_rounded(draw, (margin, 48, PAGE_WIDTH - margin, PAGE_HEIGHT - 56), radius=34, fill=(10, 12, 18, 188), width=3)
    y = 86
    draw.text((88, y), "ABA SIGNAL PRO", font=_font(36, True), fill=BRAND_YELLOW)
    draw.text((88, y + 48), report_name or "Full Pick Magazine Report", font=_font(42), fill=TEXT_WHITE)
    meta = f"Page {page_number}/{total_pages} | {_text(pick, 'sport_league', 'league', 'sport', default='Sport N/A')} | {_text(pick, 'start_time', 'commence_time', default='Time N/A')} | {_text(pick, 'sportsbook', 'sportsbook_casino', 'best_bookmaker', default='Best available')}"
    _draw_text(draw, (88, y + 104), meta, _font(22), TEXT_MUTED, max_width=PAGE_WIDTH - 176, max_lines=2)
    y = 238
    _draw_rounded(draw, (78, y, PAGE_WIDTH - 78, y + 220), radius=24, fill=(0, 0, 0, 120), width=2)
    draw.text((112, y + 28), _game(pick), font=_font(40, True), fill=TEXT_WHITE)
    draw.text((112, y + 94), "PICK", font=_font(24), fill=TEXT_WHITE)
    _draw_text(draw, (220, y + 80), _pick(pick), _font(44, True), BRAND_YELLOW, max_width=PAGE_WIDTH - 310, max_lines=2)
    details = [
        f"Odds: {_text(pick, 'current_odds', 'odds', 'decimal_odds', 'american_odds', default='N/A')}",
        f"Confidence: {_fmt_pct(_prob(pick, 'model_probability', 'confidence', 'confidence_score'))}",
        f"Edge: {_fmt_edge(_num(pick, 'edge', 'model_market_edge'))}",
        f"EV: {_fmt_num(_num(pick, 'expected_value', 'ev'))}",
        f"Units: {_text(pick, 'recommended_units', 'recommended_stake', 'stake', default='Review manually')}",
        f"Risk: {_text(pick, 'risk_level', default='N/A')}",
        f"Playable Line: {_text(pick, 'minimum_playable_odds', 'playable_line', default='Recheck market')}",
    ]
    _draw_text(draw, (112, y + 166), " | ".join(details), _font(20), TEXT_MUTED, max_width=PAGE_WIDTH - 224, max_lines=2)
    y += 258
    sections = [
        ("WHY WE PICKED IT", _bullets_from(pick, fallback="Recheck odds, injuries, lineups, and weather before betting", max_items=10), 360),
        ("PRO BETTOR EVIDENCE", _pro_evidence(pick), 360),
        ("RISK DESK", _risk_bullets(pick), 260),
        ("CHAIN BETTING NOTES", _chain_notes(pick), 245),
    ]
    for title, bullets, height in sections:
        _draw_rounded(draw, (78, y, PAGE_WIDTH - 78, y + height), radius=24, fill=(0, 0, 0, 105), width=2)
        draw.text((112, y + 22), title, font=_font(27, True), fill=SECTION_GREEN)
        line_y = y + 66
        bullet_font = _font(22)
        max_lines_each = 2 if len(bullets) <= 5 else 1
        for bullet in bullets:
            if line_y > y + height - 42:
                break
            line_y = _draw_text(draw, (122, line_y), f"• {bullet}", bullet_font, TEXT_WHITE, max_width=PAGE_WIDTH - 244, max_lines=max_lines_each, line_gap=6)
        y += height + 24
    final_box_top = PAGE_HEIGHT - 240
    _draw_rounded(draw, (78, final_box_top, PAGE_WIDTH - 78, PAGE_HEIGHT - 104), radius=24, fill=(0, 0, 0, 130), width=2)
    draw.text((112, final_box_top + 24), "FINAL RECOMMENDATION", font=_font(28, True), fill=BRAND_YELLOW)
    recommendation = _text(pick, "final_decision", "recommendation", "decision", default="WATCH ONLY")
    draw.text((112, final_box_top + 72), recommendation, font=_font(34, True), fill=TEXT_WHITE)
    _draw_text(draw, (112, final_box_top + 122), "Action: Bet only if line remains playable and injury/lineup data does not change.", _font(21), TEXT_MUTED, max_width=PAGE_WIDTH - 224, max_lines=2)
    draw.text((120, PAGE_HEIGHT - 82), SAFETY_FOOTER, font=_font(18), fill=TEXT_MUTED)
    return image.convert("RGB")


def render_full_pick_magazine_page_png(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1) -> bytes:
    return _png_bytes(render_full_pick_magazine_page(pick, background_image, report_name, page_number, total_pages))


def render_full_magazine_book_pages(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None) -> list[Image.Image]:
    pick_list = list(picks)
    total = len(pick_list)
    return [render_full_pick_magazine_page(pick, background_image, report_name, index, total) for index, pick in enumerate(pick_list, start=1)]


def render_full_magazine_book_png(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None) -> bytes:
    pages = render_full_magazine_book_pages(picks, background_image, report_name)
    if not pages:
        pages = [render_full_pick_magazine_page({"game": "No Picks", "exact_bet": "NO BET"}, background_image, report_name, 1, 1)]
    combined = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT * len(pages)), (8, 10, 14))
    for index, page in enumerate(pages):
        combined.paste(page.convert("RGB"), (0, PAGE_HEIGHT * index))
    return _png_bytes(combined)


def render_full_magazine_book_pdf(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None) -> bytes:
    pages = [page.convert("RGB") for page in render_full_magazine_book_pages(picks, background_image, report_name)]
    if not pages:
        pages = [render_full_pick_magazine_page({"game": "No Picks", "exact_bet": "NO BET"}, background_image, report_name, 1, 1).convert("RGB")]
    buffer = BytesIO()
    pages[0].save(buffer, format="PDF", save_all=True, append_images=pages[1:], resolution=100.0)
    return buffer.getvalue()


def render_full_magazine_zip(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None) -> bytes:
    pick_list = list(picks)
    pages = render_full_magazine_book_pages(pick_list, background_image, report_name)
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("full_magazine_book.png", render_full_magazine_book_png(pick_list, background_image, report_name))
        archive.writestr("full_magazine_book.pdf", render_full_magazine_book_pdf(pick_list, background_image, report_name))
        for index, page in enumerate(pages, start=1):
            archive.writestr(pick_full_page_filename(pick_list[index - 1], index), _png_bytes(page))
    return buffer.getvalue()
