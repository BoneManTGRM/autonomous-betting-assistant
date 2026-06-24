"""Full pick magazine book image exports for Report Studio.

Local rendering only: no live API calls, no API keys, no wager execution, and no guaranteed outcomes.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from io import BytesIO
import re
from typing import Any, Iterable, Mapping
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw, ImageFont

PAGE_WIDTH = 1080
PAGE_HEIGHT = 1920
SAFETY_FOOTER = "Analytics only. No guaranteed wins or profit. No wager execution."


def _row(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict"):
        data = value.to_dict()
        return data if isinstance(data, Mapping) else {}
    if hasattr(value, "as_dict"):
        data = value.as_dict()
        return data if isinstance(data, Mapping) else {}
    if hasattr(value, "__dict__"):
        return value.__dict__
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


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    if value > 1:
        value /= 100.0
    return f"{value:.0%}"


def _fmt_edge(value: float | None) -> str:
    if value is None:
        return "N/A"
    if abs(value) > 1:
        value /= 100.0
    return f"{value:+.1%}"


def _game(row: Any) -> str:
    return _text(row, "event", "game", "event_name", "matchup", default="Unknown Game")


def _pick(row: Any) -> str:
    return _text(row, "prediction", "exact_bet", "pick", "selection", "recommended_action", default="Pick not specified")


def sanitize_image_filename(value: str, suffix: str = "", extension: str = "png") -> str:
    clean = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "magazine").lower()).strip("_") or "magazine"
    suffix_clean = re.sub(r"[^A-Za-z0-9]+", "_", str(suffix or "").lower()).strip("_")
    if suffix_clean:
        clean = f"{clean}_{suffix_clean}"
    return f"{clean}.{(extension or 'png').lstrip('.')}"


def pick_full_page_filename(pick: Any, index: int, extension: str = "png") -> str:
    return sanitize_image_filename(f"pick_{index + 1:02d}_{_game(pick)}", "full_page", extension)


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        return ImageFont.truetype(path, size=size)
    except Exception:
        return ImageFont.load_default()


def _background(background_image: Any, size: tuple[int, int]) -> Image.Image:
    if background_image is None:
        return Image.new("RGB", size, (18, 22, 32))
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
        return Image.new("RGB", size, (18, 22, 32))
    ratio = max(size[0] / img.width, size[1] / img.height)
    resized = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.Resampling.LANCZOS)
    left = (resized.width - size[0]) // 2
    top = (resized.height - size[1]) // 2
    return resized.crop((left, top, left + size[0], top + size[1]))


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int, max_lines: int | None = None) -> list[str]:
    words = str(text or "").replace("\n", " ").split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = word if not current else f"{current} {word}"
        if draw.textbbox((0, 0), test, font=font)[2] <= width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
            if max_lines and len(lines) >= max_lines:
                break
    if current and (max_lines is None or len(lines) < max_lines):
        lines.append(current)
    if max_lines and len(lines) == max_lines and len(words) > len(" ".join(lines).split()):
        lines[-1] = lines[-1].rstrip(".,;") + "..."
    return lines


def _draw_wrapped(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, font: ImageFont.ImageFont, fill: tuple[int, int, int], width: int, max_lines: int | None = None, gap: int = 7) -> int:
    for line in _wrap(draw, text, font, width, max_lines=max_lines):
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + gap
    return y


def _bullet_text(row: Any, keys: tuple[str, ...], fallback: list[str], limit: int) -> list[str]:
    supplied = _text(row, *keys)
    items: list[str] = []
    if supplied:
        normalized = supplied.replace("\r", "\n").replace("•", "\n").replace(";", "\n").replace("|", "\n")
        items = [part.strip(" -•\t") for part in normalized.split("\n") if part.strip(" -•\t")]
    return (items or fallback)[:limit]


def _pro_evidence(row: Any) -> list[str]:
    evidence: list[str] = []
    for keys, label in (
        (("market_movement", "line_movement", "sharp_money_signal"), "Market movement"),
        (("injury_report", "starting_lineups", "lineup_status"), "Injury/lineup status"),
        (("weather_impact", "wind_speed", "wind_direction"), "Weather/wind"),
        (("team_form", "player_form", "recent_trend"), "Team/player form"),
        (("matchup_edge", "offensive_efficiency", "defensive_efficiency"), "Matchup edge"),
        (("travel_fatigue", "rest_advantage", "back_to_back"), "Travel/fatigue"),
        (("sportsbook_discrepancy", "line_shopping_edge", "best_price_edge"), "Sportsbook price gap"),
        (("public_betting", "news_signal", "news_sentiment"), "Market/public signal"),
    ):
        value = _text(row, *keys)
        if value:
            evidence.append(f"{label}: {value}")
    return evidence[:10] or ["Professional evidence pending from uploaded data", "Recheck odds, injuries, lineups, and weather before using this report."]


def render_full_pick_magazine_page(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1) -> Image.Image:
    img = _background(background_image, (PAGE_WIDTH, PAGE_HEIGHT)).convert("RGBA")
    img.alpha_composite(Image.new("RGBA", img.size, (0, 0, 0, 118)))
    draw = ImageDraw.Draw(img)
    white = (245, 245, 245)
    yellow = (248, 211, 80)
    green = (102, 220, 154)
    muted = (215, 215, 215)
    draw.rounded_rectangle((54, 48, PAGE_WIDTH - 54, PAGE_HEIGHT - 56), radius=34, fill=(10, 12, 18, 188), outline=white, width=3)
    draw.text((88, 86), "ABA SIGNAL PRO", font=_font(36, True), fill=yellow)
    draw.text((88, 134), report_name or "Full Pick Magazine Report", font=_font(42), fill=white)
    meta = f"Page {page_number}/{total_pages} | {_text(pick, 'sport', 'league', default='Sport N/A')} | {_text(pick, 'start_time', 'commence_time', default='Time N/A')} | {_text(pick, 'bookmaker', 'sportsbook', default='Best available')}"
    _draw_wrapped(draw, 88, 190, meta, _font(22), muted, PAGE_WIDTH - 176, max_lines=2)
    y = 238
    draw.rounded_rectangle((78, y, PAGE_WIDTH - 78, y + 220), radius=24, fill=(0, 0, 0, 125), outline=white, width=2)
    draw.text((112, y + 28), _game(pick), font=_font(40, True), fill=white)
    draw.text((112, y + 94), "PICK", font=_font(24), fill=white)
    _draw_wrapped(draw, 220, y + 80, _pick(pick), _font(44, True), yellow, PAGE_WIDTH - 310, max_lines=2)
    detail = " | ".join([
        f"Odds: {_text(pick, 'decimal_price', 'decimal_odds', 'odds', default='N/A')}",
        f"Confidence: {_fmt_pct(_num(pick, 'model_probability', 'confidence'))}",
        f"Edge: {_fmt_edge(_num(pick, 'model_market_edge', 'edge'))}",
        f"EV: {_text(pick, 'expected_value_per_unit', 'expected_value', 'ev', default='N/A')}",
        f"Units: {_text(pick, 'suggested_stake_units', 'recommended_units', default='Review manually')}",
        f"Risk: {_text(pick, 'risk_level', 'risk_label', default='N/A')}",
    ])
    _draw_wrapped(draw, 112, y + 166, detail, _font(20), muted, PAGE_WIDTH - 224, max_lines=2)
    y += 258
    sections = [
        ("WHY WE PICKED IT", _bullet_text(pick, ("why_bullets", "why_pick", "analysis_summary", "reason", "explanation"), ["Model projects edge from uploaded data", "Market should be rechecked before final use", "Professional evidence pending from uploaded data"], 10), 360),
        ("PRO BETTOR EVIDENCE", _pro_evidence(pick), 360),
        ("RISK DESK", _bullet_text(pick, ("why_lose", "risk_reason", "hidden_risk"), ["Avoid if injury or lineup data changes", "Avoid if odds move below playable threshold", "Recheck weather and market movement before start"], 5), 260),
        ("CHAIN BETTING NOTES", _bullet_text(pick, ("chain_notes", "main_read", "add_on_legs"), ["CHAIN VERDICT: Better as straight analysis. Do not add weak filler legs."], 6), 245),
    ]
    for title, items, height in sections:
        draw.rounded_rectangle((78, y, PAGE_WIDTH - 78, y + height), radius=24, fill=(0, 0, 0, 108), outline=white, width=2)
        draw.text((112, y + 22), title, font=_font(27, True), fill=green)
        line_y = y + 66
        for item in items:
            if line_y > y + height - 42:
                break
            line_y = _draw_wrapped(draw, 122, line_y, f"• {item}", _font(22), white, PAGE_WIDTH - 244, max_lines=2 if len(items) <= 5 else 1)
        y += height + 24
    final_top = PAGE_HEIGHT - 240
    draw.rounded_rectangle((78, final_top, PAGE_WIDTH - 78, PAGE_HEIGHT - 104), radius=24, fill=(0, 0, 0, 132), outline=white, width=2)
    draw.text((112, final_top + 24), "FINAL RECOMMENDATION", font=_font(28, True), fill=yellow)
    draw.text((112, final_top + 72), _text(pick, "final_decision", "agent_decision", "recommendation", default="WATCH ONLY"), font=_font(34, True), fill=white)
    _draw_wrapped(draw, 112, final_top + 122, "Action: Use only if line remains playable and injury/lineup data does not change.", _font(21), muted, PAGE_WIDTH - 224, max_lines=2)
    draw.text((120, PAGE_HEIGHT - 82), SAFETY_FOOTER, font=_font(18), fill=muted)
    return img.convert("RGB")


def render_full_pick_magazine_page_png(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1) -> bytes:
    return _png_bytes(render_full_pick_magazine_page(pick, background_image, report_name, page_number, total_pages))


def render_full_magazine_book_pages(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None) -> list[Image.Image]:
    pick_list = list(picks)
    total = len(pick_list) or 1
    return [render_full_pick_magazine_page(pick, background_image, report_name, index + 1, total) for index, pick in enumerate(pick_list)]


def render_full_magazine_book_png(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None) -> bytes:
    pages = render_full_magazine_book_pages(picks, background_image, report_name) or [render_full_pick_magazine_page({"event": "No Picks", "prediction": "NO PICK"}, background_image, report_name, 1, 1)]
    combined = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT * len(pages)), (8, 10, 14))
    for index, page in enumerate(pages):
        combined.paste(page.convert("RGB"), (0, PAGE_HEIGHT * index))
    return _png_bytes(combined)


def render_full_magazine_book_pdf(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None) -> bytes:
    pages = [page.convert("RGB") for page in render_full_magazine_book_pages(picks, background_image, report_name)] or [render_full_pick_magazine_page({"event": "No Picks", "prediction": "NO PICK"}, background_image, report_name, 1, 1)]
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
        for index, page in enumerate(pages):
            archive.writestr(pick_full_page_filename(pick_list[index], index), _png_bytes(page))
    return buffer.getvalue()
