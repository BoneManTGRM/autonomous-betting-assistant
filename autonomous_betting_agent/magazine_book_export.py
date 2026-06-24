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
    for separator in (" at ", " vs ", " v ", " VS ", " @ "):
        if separator in event:
            left, right = event.split(separator, 1)
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
    img = Image.new("RGB", size, (238, 224, 190))
    draw = ImageDraw.Draw(img, "RGBA")
    for x in range(-220, size[0], 58):
        draw.line((x, 0, x + 260, size[1]), fill=(113, 66, 45, 9), width=14)
    for y in range(0, size[1], 56):
        draw.line((0, y, size[0], y + 34), fill=(255, 255, 255, 14), width=8)
    for x in range(24, size[0], 92):
        for y in range(16, size[1], 86):
            draw.rectangle((x, y, x + 2, y + 2), fill=(56, 38, 24, 30))
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
    veil = Image.new("RGBA", size, (238, 224, 190, 125))
    cropped.alpha_composite(veil)
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


def _team_stats(row: Any, team_prefix: str) -> list[tuple[str, str]]:
    fields = (
        ("Record", (f"{team_prefix}_record", f"{team_prefix}_season_record")),
        ("Last 10", (f"{team_prefix}_last_10", f"{team_prefix}_recent_form")),
        ("Avg", (f"{team_prefix}_avg", f"{team_prefix}_team_avg", f"{team_prefix}_runs_per_game", f"{team_prefix}_points_per_game")),
        ("Offense", (f"{team_prefix}_offense", f"{team_prefix}_offense_note")),
        ("Defense", (f"{team_prefix}_defense", f"{team_prefix}_defense_note")),
    )
    stats: list[tuple[str, str]] = []
    for label, keys in fields:
        value = _text(row, *keys)
        if value:
            stats.append((label, value))
    return stats


def _team_notes(row: Any) -> list[str]:
    team_a, team_b = _teams(row)
    notes = [
        f"{team_a}: {_text(row, 'team_a_snapshot', 'home_team_snapshot', default='Team snapshot data not available from uploaded row')}",
        f"{team_b}: {_text(row, 'team_b_snapshot', 'away_team_snapshot', default='Team snapshot data not available from uploaded row')}",
    ]
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


def _matchup_notes(row: Any) -> list[str]:
    return _available_notes(row, (
        (("matchup_note", "matchup_notes", "head_to_head", "h2h"), "Matchup"),
        (("style_matchup", "pace_note", "total_trend"), "Style/pace"),
        (("venue_note", "weather_note", "travel_note"), "Venue/travel"),
        (("pitcher_matchup", "goalie_matchup", "starter_matchup"), "Starter matchup"),
    ), "Matchup detail not available from uploaded row", 4)


def _chain_notes(row: Any) -> list[str]:
    supplied = _bullet_text(row, ("chain_notes", "main_read", "add_on_legs", "parlay_notes"), [], 5)
    if supplied:
        return supplied[:5]
    return ["Better as individual straight analysis. Do not add weak filler legs."]


def _recommendation(row: Any) -> tuple[str, str]:
    action = _text(row, "final_decision", "agent_decision", "recommendation", "consumer_action", "recommended_action", default="research_only")
    explanation = _text(row, "final_explanation", "action_reason", "recommendation_reason", default="Use only if the line remains playable and key news does not change.")
    return action, explanation


def _fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, start_size: int, min_size: int = 34, bold: bool = True) -> ImageFont.ImageFont:
    for size in range(start_size, min_size - 1, -2):
        font = _font(size, bold)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return font
    return _font(min_size, bold)


def _panel(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], fill: tuple[int, int, int, int] = (250, 241, 213, 238), outline: tuple[int, int, int] = (15, 23, 35)) -> None:
    draw.rounded_rectangle(xy, radius=16, fill=fill, outline=outline, width=3)


def _header_bar(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], title: str, color: tuple[int, int, int]) -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle((x1, y1, x2, y2), radius=8, fill=color)
    draw.text((x1 + 16, y1 + 8), title, font=_font(26, True), fill=(255, 246, 220))


def _draw_bullet_list(draw: ImageDraw.ImageDraw, x: int, y: int, items: list[str], width: int, max_items: int, font_size: int = 22, dot_color: tuple[int, int, int] = (153, 32, 28)) -> int:
    font = _font(font_size)
    for item in items[:max_items]:
        lines = _wrap(draw, item, font, width - 28, max_lines=2)
        if not lines:
            continue
        draw.ellipse((x, y + 9, x + 10, y + 19), fill=dot_color)
        text_y = y
        for line in lines:
            draw.text((x + 24, text_y), line, font=font, fill=(18, 21, 26))
            text_y += font_size + 5
        y = text_y + 8
    return y


def _draw_metric(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, label: str, value: str, value_color: tuple[int, int, int] = (63, 214, 90)) -> None:
    draw.rectangle((x, y, x + w, y + 86), fill=(20, 22, 23), outline=(222, 215, 196), width=1)
    draw.text((x + 12, y + 10), label.upper(), font=_font(18, True), fill=(239, 231, 209))
    _draw_wrapped(draw, x + 12, y + 38, value, _font(26, True), value_color, w - 24, max_lines=1, gap=2)


def _draw_team_snapshot(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, team_name: str, stats: list[tuple[str, str]], notes: list[str], accent: tuple[int, int, int]) -> None:
    draw.text((x, y), team_name.upper(), font=_font(24, True), fill=accent)
    stat_y = y + 38
    shown_stats = stats[:5] or [("Snapshot", "Data not available")]
    for label, value in shown_stats:
        draw.text((x, stat_y), label.upper(), font=_font(18, True), fill=(22, 26, 32))
        _draw_wrapped(draw, x + 160, stat_y - 1, value, _font(21, True), (22, 26, 32), w - 165, max_lines=1, gap=0)
        stat_y += 30
    draw.text((x, stat_y + 6), "NOTES", font=_font(18, True), fill=accent)
    _draw_bullet_list(draw, x, stat_y + 36, notes[:3], w, 3, font_size=18, dot_color=accent)


def _draw_section(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, title: str, items: list[str], color: tuple[int, int, int], max_items: int = 5, font_size: int = 22) -> None:
    _panel(draw, (x, y, x + w, y + h))
    _header_bar(draw, (x, y, x + w, y + 48), title, color)
    _draw_bullet_list(draw, x + 24, y + 70, items, w - 48, max_items=max_items, font_size=font_size, dot_color=color)


def _draw_abstract_player(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, sport: str) -> None:
    draw.rounded_rectangle((x, y, x + w, y + h), radius=20, fill=(21, 40, 70, 228), outline=(255, 246, 220), width=4)
    draw.rectangle((x + 18, y + 18, x + w - 18, y + h - 18), outline=(170, 37, 34), width=6)
    draw.ellipse((x + w // 2 - 52, y + 48, x + w // 2 + 52, y + 152), fill=(235, 222, 190))
    draw.rounded_rectangle((x + w // 2 - 84, y + 150, x + w // 2 + 84, y + 312), radius=38, fill=(31, 82, 147))
    draw.line((x + w // 2 - 84, y + 190, x + 40, y + 270), fill=(235, 222, 190), width=22)
    draw.line((x + w // 2 + 84, y + 190, x + w - 42, y + 250), fill=(235, 222, 190), width=22)
    draw.text((x + 28, y + h - 62), sport.upper()[:14], font=_font(30, True), fill=(255, 246, 220))


def render_full_pick_magazine_page(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1) -> Image.Image:
    img = _background(background_image, (PAGE_WIDTH, PAGE_HEIGHT)).convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")
    red = (159, 34, 30)
    navy = (19, 54, 92)
    black = (15, 18, 22)
    cream = (247, 238, 211)
    green = (42, 178, 72)
    team_a, team_b = _teams(pick)
    sport = _text(pick, "sport", "league", default="Sport N/A")
    source = _text(pick, "odds_source", "bookmaker", "sportsbook", default="Uploaded row")
    report = report_name or "Full Pick Magazine"

    # Top newspaper bar
    draw.rectangle((0, 0, PAGE_WIDTH, 58), fill=black)
    draw.rectangle((16, 10, 228, 50), fill=red)
    draw.text((28, 16), "ABA SIGNAL PRO", font=_font(26, True), fill=(255, 255, 255))
    draw.text((256, 15), "DAILY SPORTS ANALYSIS", font=_font(28, True), fill=(255, 246, 220))
    draw.rounded_rectangle((840, 8, PAGE_WIDTH - 18, 50), radius=5, fill=cream)
    draw.text((872, 15), f"PAGE {page_number} OF {total_pages}", font=_font(24, True), fill=black)

    draw.rectangle((0, 58, PAGE_WIDTH, 98), fill=(248, 239, 214, 245))
    meta = f"REPORT: {report}   |   SOURCE: {source}   |   SPORT: {sport}"
    _draw_wrapped(draw, 28, 68, meta, _font(21, True), black, 800, max_lines=1)
    draw.rounded_rectangle((900, 66, PAGE_WIDTH - 24, 128), radius=10, fill=navy)
    draw.text((922, 82), sport.upper()[:10], font=_font(27, True), fill=(255, 255, 255))

    # Hero headline and visual zone
    headline_font_a = _fit_font(draw, team_a.upper(), 630, 78, 44, True)
    headline_font_b = _fit_font(draw, team_b.upper(), 650, 64, 40, True)
    draw.text((36, 122), team_a.upper(), font=headline_font_a, fill=red)
    draw.text((38, 214), "VS", font=_font(38, True), fill=black)
    draw.line((35, 260, 104, 260), fill=black, width=3)
    draw.text((118, 218), team_b.upper(), font=headline_font_b, fill=navy)
    draw.rectangle((34, 318, 440, 362), fill=black)
    draw.text((48, 326), (_text(pick, "season_label", "sport_context_summary", default=f"{sport} ANALYSIS")).upper()[:28], font=_font(24, True), fill=cream)
    _draw_wrapped(draw, 36, 382, _text(pick, "game_summary", "preview_summary", "short_reason", default="Use uploaded row data and market checks to evaluate this game before publishing."), _font(22), black, 560, max_lines=3)
    _draw_abstract_player(draw, 668, 112, 368, 304, sport)

    # Recommendation and metrics strip
    strip_y = 450
    draw.rounded_rectangle((18, strip_y, PAGE_WIDTH - 18, strip_y + 94), radius=14, fill=black, outline=cream, width=3)
    draw.text((42, strip_y + 14), "TENDENCIA", font=_font(25, True), fill=red)
    _draw_wrapped(draw, 42, strip_y + 44, _pick(pick), _font(32, True), (255, 255, 255), 270, max_lines=1)
    metric_x = 334
    metric_w = 104
    metrics = [
        ("Odds", _text(pick, "american_odds", "decimal_price", "decimal_odds", "odds", default="N/A"), (255, 255, 255)),
        ("Conf", _fmt_pct(_num(pick, "model_probability", "learned_model_probability", "confidence")), green),
        ("Edge", _fmt_edge(_num(pick, "model_market_edge", "edge")), green),
        ("EV", _text(pick, "expected_value_per_unit", "expected_value", "ev", default="N/A"), green),
        ("Units", _text(pick, "suggested_stake_units", "recommended_units", default="Review"), (255, 255, 255)),
        ("Risk", _text(pick, "risk_level", "risk_label", default="N/A"), green),
        ("Market", _text(pick, "market", "bet_type", "market_type", default="N/A"), (255, 255, 255)),
    ]
    for label, value, color in metrics:
        _draw_metric(draw, metric_x, strip_y + 4, metric_w, label, value, color)
        metric_x += metric_w

    # Mid content grid
    left_x = 18
    right_x = 382
    y = 566
    _draw_section(draw, left_x, y, 338, 294, "WHY WE PICKED IT", _why_notes(pick), red, max_items=5, font_size=21)
    _draw_section(draw, left_x, 876, 338, 250, "PRO BETTOR EVIDENCE", _pro_evidence(pick), navy, max_items=5, font_size=20)

    # Team snapshots wide panel
    _panel(draw, (right_x, y, PAGE_WIDTH - 18, 936))
    _header_bar(draw, (right_x, y, PAGE_WIDTH - 18, y + 48), "TEAM SNAPSHOTS", navy)
    mid = right_x + 344
    draw.line((mid, y + 62, mid, 920), fill=(70, 70, 70), width=2)
    left_stats = _team_stats(pick, "team_a") or _team_stats(pick, "home_team")
    right_stats = _team_stats(pick, "team_b") or _team_stats(pick, "away_team")
    team_notes = _team_notes(pick)
    _draw_team_snapshot(draw, right_x + 24, y + 70, 300, team_a, left_stats, team_notes[:3], red)
    _draw_team_snapshot(draw, mid + 24, y + 70, 300, team_b, right_stats, team_notes[3:] or team_notes[:3], navy)

    # Player notes wide panel
    _panel(draw, (right_x, 952, PAGE_WIDTH - 18, 1126))
    _header_bar(draw, (right_x, 952, PAGE_WIDTH - 18, 1000), "PLAYER / INJURY NOTES", navy)
    _draw_bullet_list(draw, right_x + 24, 1020, _player_notes(pick), PAGE_WIDTH - right_x - 66, 4, font_size=20, dot_color=navy)

    # Bottom three boxes
    _draw_section(draw, 18, 1142, 338, 252, "RISK DESK", _risk_notes(pick), red, max_items=5, font_size=19)
    _draw_section(draw, 372, 1142, 338, 252, "MATCHUP NOTES", _matchup_notes(pick), navy, max_items=4, font_size=19)
    _draw_section(draw, 726, 1142, 336, 252, "CHAIN BETTING NOTES", _chain_notes(pick), navy, max_items=4, font_size=20)

    # Final recommendation bar
    action, explanation = _recommendation(pick)
    final_y = 1418
    draw.rounded_rectangle((18, final_y, PAGE_WIDTH - 18, PAGE_HEIGHT - 48), radius=12, fill=black, outline=red, width=4)
    draw.rectangle((18, final_y, 238, PAGE_HEIGHT - 48), fill=red)
    draw.text((34, final_y + 24), "FINAL", font=_font(26, True), fill=(255, 255, 255))
    draw.text((34, final_y + 58), "RECOMMENDATION", font=_font(22, True), fill=(255, 255, 255))
    _draw_wrapped(draw, 268, final_y + 18, action.upper(), _font(52, True), green, 350, max_lines=1)
    _draw_wrapped(draw, 268, final_y + 78, _pick(pick), _font(30, True), (255, 255, 255), 350, max_lines=1)
    _draw_wrapped(draw, 640, final_y + 26, explanation, _font(23), (255, 255, 255), 380, max_lines=3)
    draw.text((120, PAGE_HEIGHT - 34), SAFETY_FOOTER, font=_font(18), fill=(255, 246, 220))
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
