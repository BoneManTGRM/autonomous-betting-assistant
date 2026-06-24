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
PAGE_HEIGHT = 1620
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


def _teams(row: Any) -> tuple[str, str]:
    data = _row(row)
    home = _text(data, "home_team", "team_a", "favorite_team", "team1")
    away = _text(data, "away_team", "team_b", "underdog_team", "team2")
    event = _game(data)
    if home and away:
        return home, away
    if " at " in event:
        left, right = event.split(" at ", 1)
        return left.strip(), right.strip()
    if " vs " in event:
        left, right = event.split(" vs ", 1)
        return left.strip(), right.strip()
    if " v " in event:
        left, right = event.split(" v ", 1)
        return left.strip(), right.strip()
    return _text(data, "team", "selection_team", default="Team / Side A"), _text(data, "opponent", default="Opponent / Side B")


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


def _texture(size: tuple[int, int]) -> Image.Image:
    img = Image.new("RGB", size, (207, 188, 145))
    draw = ImageDraw.Draw(img, "RGBA")
    for x in range(0, size[0], 54):
        draw.line((x, 0, x - 240, size[1]), fill=(255, 255, 255, 12), width=16)
    for y in range(0, size[1], 46):
        draw.line((0, y, size[0], y + 80), fill=(82, 58, 34, 10), width=10)
    for x in range(36, size[0], 126):
        for y in range(24, size[1], 118):
            draw.ellipse((x, y, x + 5, y + 5), fill=(72, 50, 32, 34))
    return img


def _background(background_image: Any, size: tuple[int, int]) -> Image.Image:
    if background_image is None:
        return _texture(size)
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
        return _texture(size)
    ratio = max(size[0] / img.width, size[1] / img.height)
    resized = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.Resampling.LANCZOS)
    left = (resized.width - size[0]) // 2
    top = (resized.height - size[1]) // 2
    cropped = resized.crop((left, top, left + size[0], top + size[1])).convert("RGBA")
    overlay = Image.new("RGBA", size, (232, 214, 169, 160))
    cropped.alpha_composite(overlay)
    return cropped.convert("RGB")


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


def _draw_wrapped(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, font: ImageFont.ImageFont, fill: tuple[int, int, int], width: int, max_lines: int | None = None, gap: int = 8) -> int:
    for line in _wrap(draw, text, font, width, max_lines=max_lines):
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + gap
    return y


def _split_items(value: str) -> list[str]:
    normalized = str(value or "").replace("\r", "\n").replace("•", "\n").replace(";", "\n").replace("|", "\n")
    return [part.strip(" -•\t") for part in normalized.split("\n") if part.strip(" -•\t")]


def _bullet_text(row: Any, keys: tuple[str, ...], fallback: list[str], limit: int) -> list[str]:
    supplied = _text(row, *keys)
    return (_split_items(supplied) or fallback)[:limit]


def _available_notes(row: Any, key_labels: tuple[tuple[tuple[str, ...], str], ...], fallback: str, limit: int) -> list[str]:
    notes: list[str] = []
    for keys, label in key_labels:
        value = _text(row, *keys)
        if value:
            notes.append(f"{label}: {value}")
    return notes[:limit] or [fallback]


def _why_notes(row: Any) -> list[str]:
    notes = _bullet_text(row, ("why_bullets", "why_pick", "analysis_summary", "reason", "explanation"), [], 5)
    model_probability = _fmt_pct(_num(row, "model_probability", "learned_model_probability", "confidence"))
    market_probability = _fmt_pct(_num(row, "market_probability", "implied_probability"))
    edge = _fmt_edge(_num(row, "model_market_edge", "edge"))
    ev = _text(row, "expected_value_per_unit", "expected_value", "ev")
    odds = _text(row, "decimal_price", "decimal_odds", "odds")
    sport_context = _text(row, "sports_context_summary", "context", "note")
    if model_probability != "N/A":
        notes.append(f"Model probability: {model_probability}")
    if market_probability != "N/A":
        notes.append(f"Market probability: {market_probability}")
    if edge != "N/A":
        notes.append(f"Measured edge: {edge}")
    if ev:
        notes.append(f"Expected value signal: {ev}")
    if odds:
        notes.append(f"Available odds: {odds}")
    if sport_context:
        notes.append(sport_context)
    return notes[:5] or ["Data not available from uploaded row", "Recheck odds, injuries, lineups, and weather before final use"]


def _pro_evidence(row: Any) -> list[str]:
    return _available_notes(row, (
        (("odds_source", "data_source"), "Odds source"),
        (("bookmaker", "sportsbook"), "Sportsbook"),
        (("market_movement", "line_movement", "sharp_money_signal"), "Market movement"),
        (("sportsbook_discrepancy", "line_shopping_edge", "best_price_edge"), "Line shopping"),
        (("public_betting", "public_split", "pro_split"), "Public/pro split"),
    ), "Professional evidence pending from uploaded data", 5)


def _team_notes(row: Any) -> list[str]:
    team_a, team_b = _teams(row)
    notes = [f"{team_a} snapshot: {_text(row, 'team_a_snapshot', 'home_team_snapshot', default='Data not available from uploaded row')}", f"{team_b} snapshot: {_text(row, 'team_b_snapshot', 'away_team_snapshot', default='Data not available from uploaded row')}"]
    notes.extend(_available_notes(row, (
        (("team_form", "recent_trend", "form_note"), "Team form"),
        (("matchup_history", "h2h", "head_to_head"), "Matchup history"),
        (("offensive_efficiency", "offense_note"), "Offense"),
        (("defensive_efficiency", "defense_note"), "Defense"),
        (("travel_fatigue", "rest_advantage", "schedule_spot"), "Travel/rest"),
        (("weather_impact", "wind_speed", "weather_note"), "Weather"),
    ), "Additional team context not available from uploaded row", 5))
    return notes[:6]


def _player_notes(row: Any) -> list[str]:
    return _available_notes(row, (
        (("key_players", "players", "participant_notes"), "Key players"),
        (("player_form", "star_player_form"), "Player form"),
        (("injury_report", "injuries", "lineup_status", "starting_lineups"), "Injury/lineup"),
        (("pitcher_matchup", "goalie_matchup", "starter_matchup"), "Participant matchup"),
    ), "Player data not available in uploaded row", 4)


def _risk_notes(row: Any) -> list[str]:
    notes = _bullet_text(row, ("why_lose", "risk_reason", "hidden_risk"), [], 4)
    notes.extend([
        "Confirm injury and lineup status before use.",
        "Avoid if odds move below the playable threshold.",
        "Check weather and venue conditions when relevant.",
        "Use conservative unit sizing; never assume guaranteed profit.",
    ])
    push = _text(row, "push_note", "cancel_note", "void_note")
    if push:
        notes.append(f"Push/cancel note: {push}")
    return notes[:5]


def _chain_notes(row: Any) -> list[str]:
    supplied = _bullet_text(row, ("chain_notes", "main_read", "add_on_legs", "parlay_notes"), [], 5)
    if supplied:
        return supplied[:5]
    return ["Better as straight analysis. Do not add weak filler legs."]


def _recommendation(row: Any) -> tuple[str, str]:
    action = _text(row, "final_decision", "agent_decision", "recommendation", "consumer_action", "recommended_action", default="research_only")
    explanation = _text(row, "final_explanation", "action_reason", "recommendation_reason", default="Use only if the line remains playable and key news does not change.")
    return action, explanation


def _panel(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], fill: tuple[int, int, int, int] = (244, 229, 190, 210)) -> None:
    draw.rounded_rectangle(xy, radius=26, fill=fill, outline=(65, 46, 28), width=3)


def _draw_section(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, title: str, items: list[str], height: int, title_color: tuple[int, int, int] = (34, 95, 65)) -> int:
    _panel(draw, (x, y, x + w, y + height))
    draw.text((x + 28, y + 20), title, font=_font(26, True), fill=title_color)
    line_y = y + 66
    for item in items:
        if line_y > y + height - 38:
            break
        line_y = _draw_wrapped(draw, x + 44, line_y, f"• {item}", _font(23), (28, 24, 20), w - 76, max_lines=2, gap=6)
    return y + height + 18


def render_full_pick_magazine_page(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1) -> Image.Image:
    img = _background(background_image, (PAGE_WIDTH, PAGE_HEIGHT)).convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")
    black = (18, 15, 12)
    red = (150, 34, 31)
    green = (34, 104, 70)
    gold = (176, 126, 32)
    team_a, team_b = _teams(pick)
    sport = _text(pick, "sport", "league", default="Sport N/A")
    source = _text(pick, "odds_source", "bookmaker", "sportsbook", default="Uploaded row")

    draw.rectangle((0, 0, PAGE_WIDTH, 22), fill=red)
    draw.rectangle((0, PAGE_HEIGHT - 26, PAGE_WIDTH, PAGE_HEIGHT), fill=red)
    for x in range(18, PAGE_WIDTH, 38):
        draw.arc((x, -22, x + 34, 40), 0, 180, fill=(235, 222, 190), width=4)
        draw.arc((x, PAGE_HEIGHT - 42, x + 34, PAGE_HEIGHT + 22), 180, 360, fill=(235, 222, 190), width=4)

    draw.text((54, 50), "ABA SIGNAL PRO", font=_font(22, True), fill=gold)
    _draw_wrapped(draw, 54, 86, report_name or "Full Pick Magazine", _font(24), black, 470, max_lines=1)
    draw.text((54, 132), f"Page {page_number}/{total_pages} | {sport} | {source}", font=_font(20), fill=(55, 48, 38))

    draw.text((54, 190), team_a, font=_font(46, True), fill=black)
    draw.text((54, 244), "VS", font=_font(40, True), fill=red)
    _draw_wrapped(draw, 54, 292, team_b, _font(46, True), black, 560, max_lines=2)

    _panel(draw, (606, 164, PAGE_WIDTH - 50, 372), fill=(250, 240, 212, 230))
    draw.text((638, 192), "TENDENCIA", font=_font(33, True), fill=red)
    _draw_wrapped(draw, 638, 244, _pick(pick), _font(34, True), black, 370, max_lines=3)

    metrics = [
        f"Odds: {_text(pick, 'decimal_price', 'decimal_odds', 'odds', default='N/A')}",
        f"Confidence: {_fmt_pct(_num(pick, 'model_probability', 'learned_model_probability', 'confidence'))}",
        f"Edge: {_fmt_edge(_num(pick, 'model_market_edge', 'edge'))}",
        f"EV: {_text(pick, 'expected_value_per_unit', 'expected_value', 'ev', default='N/A')}",
        f"Units: {_text(pick, 'suggested_stake_units', 'recommended_units', default='Review manually')}",
        f"Risk: {_text(pick, 'risk_level', 'risk_label', default='N/A')}",
        f"Market: {_text(pick, 'market', 'bet_type', 'market_type', default='N/A')}",
    ]
    y = 404
    _panel(draw, (54, y, PAGE_WIDTH - 54, y + 104), fill=(250, 240, 212, 225))
    _draw_wrapped(draw, 84, y + 24, "  |  ".join(metrics), _font(22), black, PAGE_WIDTH - 168, max_lines=2)
    y += 132

    y = _draw_section(draw, 54, y, 472, "WHY WE PICKED IT", _why_notes(pick), 276, green)
    y_left = _draw_section(draw, 54, y, 472, "TEAM ANALYSIS", _team_notes(pick), 420, green)
    y_left = _draw_section(draw, 54, y_left, 472, "RISK DESK", _risk_notes(pick), 290, green)

    y_right = 536
    y_right = _draw_section(draw, 554, y_right, 472, "PLAYER NOTES", _player_notes(pick), 258, green)
    y_right = _draw_section(draw, 554, y_right, 472, "PRO BETTOR EVIDENCE", _pro_evidence(pick), 308, green)
    y_right = _draw_section(draw, 554, y_right, 472, "CHAIN BETTING NOTES", _chain_notes(pick), 214, green)

    action, explanation = _recommendation(pick)
    final_top = PAGE_HEIGHT - 202
    _panel(draw, (54, final_top, PAGE_WIDTH - 54, PAGE_HEIGHT - 62), fill=(250, 240, 212, 235))
    draw.text((84, final_top + 22), "FINAL RECOMMENDATION", font=_font(28, True), fill=red)
    _draw_wrapped(draw, 84, final_top + 64, action, _font(34, True), black, 900, max_lines=1)
    _draw_wrapped(draw, 84, final_top + 108, explanation, _font(22), black, 900, max_lines=2)
    draw.text((72, PAGE_HEIGHT - 50), SAFETY_FOOTER, font=_font(17), fill=(42, 36, 30))
    return img.convert("RGB")


def render_full_pick_magazine_page_png(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1) -> bytes:
    return _png_bytes(render_full_pick_magazine_page(pick, background_image, report_name, page_number, total_pages))


def render_full_magazine_book_pages(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None) -> list[Image.Image]:
    pick_list = list(picks)
    total = len(pick_list) or 1
    return [render_full_pick_magazine_page(pick, background_image, report_name, index + 1, total) for index, pick in enumerate(pick_list)]


def render_full_magazine_book_png(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None) -> bytes:
    pages = render_full_magazine_book_pages(picks, background_image, report_name) or [render_full_pick_magazine_page({"event": "No Picks", "prediction": "NO PICK"}, background_image, report_name, 1, 1)]
    combined = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT * len(pages)), (232, 214, 169))
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
