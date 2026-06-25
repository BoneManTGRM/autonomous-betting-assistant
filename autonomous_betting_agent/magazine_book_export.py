from __future__ import annotations

from dataclasses import asdict, is_dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import math, re, random
from typing import Any, Iterable, Mapping
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

PAGE_WIDTH = 1080
PAGE_HEIGHT = 1620
MAGAZINE_STYLE_VERSION = "premium_v4_reference_compact"
SAFETY_FOOTER = "No guarantees. Bet responsibly. This analysis is for informational purposes only."
ASSET_DIRS = (Path("assets/team_logos"), Path("assets/report_logos"), Path("assets/licensed_logos"))

RED = (190, 30, 28)
BLUE = (19, 66, 108)
BLACK = (13, 14, 16)
PAPER = (244, 235, 211)
CREAM = (255, 248, 230)
GREEN = (61, 205, 84)
DANGER = (225, 67, 62)
TEXT = (14, 17, 21)
NO_VERIFIED = "Data unavailable"
NOT_PROVIDED = "Not provided"
TEAM_DATA_FALLBACK = "Data not available from uploaded row"
PLAYER_DATA_FALLBACK = "Player data not available in uploaded row"
_FONT_CACHE: dict[tuple[int, bool], ImageFont.ImageFont] = {}


def _row(v: Any) -> Mapping[str, Any]:
    if isinstance(v, Mapping):
        return v
    if is_dataclass(v):
        return asdict(v)
    if hasattr(v, "to_dict"):
        d = v.to_dict()
        return d if isinstance(d, Mapping) else {}
    return getattr(v, "__dict__", {}) or {}


def _bad(v: Any) -> bool:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return True
    return str(v).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


def _get(r: Any, *keys: str, default: str = "") -> str:
    d = _row(r)
    for k in keys:
        v = d.get(k)
        if not _bad(v):
            return str(v).strip()
    return default


def _clean(v: Any, upper: bool = False) -> str:
    if _bad(v):
        return NO_VERIFIED
    s = re.sub(r"\s+", " ", str(v).replace("_", " ").strip())
    return s.upper() if upper else s


def _num(r: Any, *keys: str) -> float | None:
    for k in keys:
        v = _row(r).get(k)
        if not _bad(v):
            try:
                return float(str(v).replace("%", "").replace(",", ""))
            except Exception:
                pass
    return None


def _fmt(v: Any, kind: str = "") -> str:
    if _bad(v):
        return NO_VERIFIED
    try:
        n = float(str(v).replace("%", "").replace(",", ""))
        if kind == "odds":
            return f"{int(n):+d}" if abs(n) >= 100 and n.is_integer() and n > 0 else (str(int(n)) if abs(n) >= 100 and n.is_integer() else f"{n:.2f}".rstrip("0").rstrip("."))
        if kind == "ev":
            return f"{n:+.3f}" if abs(n) < 1 else f"{n:+.2f}"
        if kind == "unit":
            return f"{n:.1f}" if abs(n) < 10 else f"{n:.0f}"
        return f"{n:.2f}".rstrip("0").rstrip(".")
    except Exception:
        return _clean(v, upper=kind in {"risk", "market"})


def _pct(n: float | None) -> str:
    if n is None:
        return NO_VERIFIED
    n = n / 100 if abs(n) > 1 else n
    return f"{n:.0%}"


def _edge(n: float | None) -> str:
    if n is None:
        return NO_VERIFIED
    n = n / 100 if abs(n) > 1 else n
    return f"{n:+.1%}"


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    key = (int(size), bool(bold))
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    names = ("DejaVuSansCondensed-Bold.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf") if bold else ("DejaVuSansCondensed.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf")
    for name in names:
        try:
            font = ImageFont.truetype(name, size)
            _FONT_CACHE[key] = font
            return font
        except Exception:
            pass
    for root in (Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), Path("/opt/render/project/.apt/usr/share/fonts"), Path("/app/.apt/usr/share/fonts")):
        if not root.exists():
            continue
        for name in names:
            try:
                font = ImageFont.truetype(str(next(root.rglob(name))), size)
                _FONT_CACHE[key] = font
                return font
            except Exception:
                pass
    font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


def _fit(text: str, width: int, start: int, minimum: int = 16, bold: bool = True) -> ImageFont.ImageFont:
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    for size in range(start, minimum - 1, -2):
        f = _font(size, bold)
        if d.textbbox((0, 0), str(text), font=f)[2] <= width:
            return f
    return _font(minimum, bold)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int, max_lines: int) -> list[str]:
    words = str(text or "").replace("\n", " ").split()
    out: list[str] = []
    cur = ""
    for w in words:
        trial = w if not cur else cur + " " + w
        if draw.textbbox((0, 0), trial, font=font)[2] <= width:
            cur = trial
        else:
            if cur:
                out.append(cur)
            cur = w
            if len(out) >= max_lines:
                break
    if cur and len(out) < max_lines:
        out.append(cur)
    if len(out) == max_lines and len(" ".join(out).split()) < len(words):
        out[-1] = out[-1].rstrip(".,;:") + "..."
    return out


def _txt(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, font: ImageFont.ImageFont, fill: Any, width: int, max_lines: int = 1) -> int:
    for line in _wrap(draw, text, font, width, max_lines):
        draw.text((x, y), line, font=font, fill=fill)
        y += getattr(font, "size", 18) + 5
    return y


def _split(v: Any) -> list[str]:
    if _bad(v):
        return []
    return [p.strip(" -•") for p in str(v).replace("•", "\n").replace(";", "\n").replace("|", "\n").splitlines() if p.strip(" -•")]


def _game(r: Any) -> str:
    return _get(r, "event", "game", "event_name", "matchup", default="Unknown Matchup")


def _teams(r: Any) -> tuple[str, str]:
    a, b = _get(r, "away_team", "team_a", "team1"), _get(r, "home_team", "team_b", "team2")
    if a and b:
        return a, b
    g = _game(r)
    for sep in (" at ", " vs ", " VS ", " v ", " @ "):
        if sep in g:
            x, y = g.split(sep, 1)
            return x.strip(), y.strip()
    return _get(r, "team", default="Team A"), _get(r, "opponent", default="Team B")


def _pick(r: Any) -> str:
    return _get(r, "prediction", "exact_bet", "pick", "selection", "recommended_action", "consumer_action", default=NOT_PROVIDED)


def _initials(s: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", str(s).upper())
    return "".join(p[0] for p in parts[:3]) or "TM"


def sanitize_image_filename(value: str, suffix: str = "", extension: str = "png") -> str:
    clean = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "magazine").lower()).strip("_") or "magazine"
    suff = re.sub(r"[^A-Za-z0-9]+", "_", str(suffix or "").lower()).strip("_")
    return f"{clean + '_' + suff if suff else clean}.{(extension or 'png').lstrip('.')}"


def pick_full_page_filename(pick: Any, index: int, extension: str = "png") -> str:
    return sanitize_image_filename(f"pick_{index + 1:02d}_{_game(pick)}", "full_page", extension)


def find_local_team_logo(team_name: str) -> Path | None:
    stem = re.sub(r"[^a-z0-9]+", "_", str(team_name).lower()).strip("_")
    variants = {stem, stem.replace("_", "-"), stem.replace("_", "")}
    for folder in ASSET_DIRS:
        for v in variants:
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                p = folder / f"{v}{ext}"
                if p.exists():
                    return p
    return None


def _load_image(v: Any) -> Image.Image | None:
    try:
        if isinstance(v, (bytes, bytearray)):
            return Image.open(BytesIO(v)).convert("RGBA")
        if isinstance(v, Image.Image):
            return v.convert("RGBA")
        if isinstance(v, (str, Path)) and Path(v).exists():
            return Image.open(v).convert("RGBA")
    except Exception:
        return None
    return None


def _resample() -> int:
    return getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def _cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    w, h = size
    scale = max(w / max(1, img.width), h / max(1, img.height))
    r = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), _resample())
    x, y = max(0, (r.width - w) // 2), max(0, (r.height - h) // 2)
    return r.crop((x, y, x + w, y + h))


def _contain(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    r = img.copy()
    r.thumbnail(size, _resample())
    return r


def _paper(seed: int) -> Image.Image:
    rng = random.Random(seed)
    img = Image.new("RGBA", (PAGE_WIDTH, PAGE_HEIGHT), PAPER + (255,))
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(120):
        x, y = rng.randint(0, PAGE_WIDTH - 1), rng.randint(0, PAGE_HEIGHT - 1)
        q = rng.randint(35, 125)
        d.rectangle((x, y, x + 1, y + 1), fill=(q, q, q, rng.randint(4, 13)))
    for _ in range(10):
        x, y = rng.randint(0, PAGE_WIDTH), rng.randint(0, PAGE_HEIGHT)
        d.line((x, y, x + rng.randint(-55, 55), y + rng.randint(-10, 10)), fill=(80, 52, 34, rng.randint(4, 12)), width=1)
    d.rectangle((10, 10, PAGE_WIDTH - 10, PAGE_HEIGHT - 10), outline=RED + (220,), width=4)
    d.rectangle((16, 16, PAGE_WIDTH - 16, PAGE_HEIGHT - 16), outline=BLACK + (180,), width=2)
    return img


def _hero(img: Image.Image, bg: Any, mode: str, opacity: float) -> None:
    d = ImageDraw.Draw(img, "RGBA")
    loaded = _load_image(bg)
    mode = str(mode or "hero_right").lower()
    if loaded is not None and mode == "full_page":
        layer = _cover(loaded, (PAGE_WIDTH, PAGE_HEIGHT)).filter(ImageFilter.GaussianBlur(0.8))
        layer = ImageEnhance.Color(layer).enhance(0.4)
        layer.putalpha(int(255 * min(max(opacity, 0.08), 0.12)))
        img.alpha_composite(layer, (0, 0))
        img.alpha_composite(Image.new("RGBA", (PAGE_WIDTH, PAGE_HEIGHT), PAPER + (155,)), (0, 0))
    elif loaded is not None and mode == "watermark":
        mark = _contain(loaded, (560, 420))
        mark.putalpha(int(255 * min(max(opacity, 0.10), 0.15)))
        img.alpha_composite(mark, (PAGE_WIDTH - mark.width - 34, 120))
    elif loaded is not None and mode != "none":
        slot = _cover(loaded, (430, 350))
        slot = ImageEnhance.Color(slot).enhance(0.86)
        slot = ImageEnhance.Contrast(slot).enhance(1.08)
        mask = Image.new("L", (430, 350), int(255 * min(max(opacity, 0.82), 0.95)))
        rounded = Image.new("L", (430, 350), 0)
        ImageDraw.Draw(rounded).rounded_rectangle((0, 0, 430, 350), radius=16, fill=255)
        slot.putalpha(Image.composite(mask, Image.new("L", (430, 350), 0), rounded))
        img.alpha_composite(slot, (620, 105))
        d.rounded_rectangle((620, 105, 1050, 455), radius=16, outline=BLACK + (185,), width=2)
    else:
        d.ellipse((648, 118, 1110, 430), fill=BLUE + (84,))
        for i in range(12):
            d.line((620 + i * 25, 420, 850 + i * 25, 120), fill=RED + (76,), width=9)


def _logo_or_badge(img: Image.Image, d: ImageDraw.ImageDraw, label: str, x: int, y: int, w: int, h: int, color: tuple[int, int, int], use_team_logo: bool = True) -> None:
    d.rounded_rectangle((x, y, x + w, y + h), radius=8, fill=color, outline=CREAM, width=2)
    text = _initials(label)[:3]
    f = _fit(text, w - 8, max(20, h // 2), 13, True)
    box = d.textbbox((0, 0), text, font=f)
    d.text((x + (w - (box[2] - box[0])) / 2, y + (h - (box[3] - box[1])) / 2 - 2), text, font=f, fill="white")


def _section(d: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, title: str, color: tuple[int, int, int]) -> None:
    d.rounded_rectangle((x, y, x + w, y + h), radius=14, fill=CREAM + (255,), outline=BLACK + (238,), width=3)
    d.rounded_rectangle((x, y, x + w, y + 56), radius=10, fill=color)
    d.text((x + 18, y + 10), title.upper(), font=_fit(title.upper(), w - 36, 31, 20, True), fill=CREAM)


def _bullets(d: ImageDraw.ImageDraw, x: int, y: int, items: list[str], width: int, color: tuple[int, int, int], limit: int, fs: int = 20, lines: int = 2) -> None:
    f = _font(fs)
    for item in items[:limit]:
        d.ellipse((x, y + 8, x + 12, y + 20), fill=color)
        y = _txt(d, x + 25, y, item, f, TEXT, width - 30, lines)
        y += 8


def _why(r: Any) -> list[str]:
    out: list[str] = []
    for k in ("why_bullets", "why_pick", "analysis_summary", "reason", "explanation"):
        out += _split(_row(r).get(k))
    if out:
        return out[:4]
    vals = []
    prob = _pct(_num(r, "learned_model_probability", "model_probability_clean", "model_probability", "final_probability"))
    market = _pct(_num(r, "market_probability", "market_implied_probability"))
    edge = _edge(_num(r, "model_market_edge", "edge"))
    ev = _fmt(_get(r, "expected_value_per_unit", "profit_expected_value", "expected_value", "ev"), "ev")
    if prob != NO_VERIFIED:
        vals.append(f"Model projects {prob} probability for {_pick(r)}.")
    if market != NO_VERIFIED:
        vals.append(f"Market-implied probability checks at {market}.")
    if edge != NO_VERIFIED:
        vals.append(f"Measured edge: {edge}.")
    if ev != NO_VERIFIED:
        vals.append(f"Expected value: {ev}.")
    return (vals or ["Use only while the line remains playable."])[:4]


def _items(r: Any, keys: Iterable[str], fallback: str, limit: int) -> list[str]:
    out: list[str] = []
    for k in keys:
        out += _split(_row(r).get(k))
    return (out or [fallback])[:limit]


def _pairs(r: Any) -> list[tuple[str, str]]:
    rows = [("ODDS SOURCE", _get(r, "odds_source", "data_source", default=NO_VERIFIED)), ("SPORTSBOOK", _get(r, "bookmaker", "sportsbook", default=NO_VERIFIED)), ("LINE MOVE", _get(r, "line_movement", "price_movement", "market_move", default=NO_VERIFIED)), ("PUBLIC %", _pct(_num(r, "public_percent", "public_bet_percent", "public_pct"))), ("PRO %", _pct(_num(r, "pro_percent", "sharp_percent", "smart_money_percent")))]
    return [(a, _clean(b)) for a, b in rows if b != NO_VERIFIED][:5]


def _team_snapshot(img: Image.Image, d: ImageDraw.ImageDraw, x: int, y: int, width: int, team: str, prefix: str, color: tuple[int, int, int], r: Any, use_team_logo: bool) -> None:
    _logo_or_badge(img, d, team, x, y, 50, 50, color, use_team_logo)
    d.text((x + 66, y + 9), team.upper(), font=_fit(team.upper(), width - 70, 25, 16, True), fill=color)
    _bullets(d, x, y + 76, [TEAM_DATA_FALLBACK], width - 10, BLUE, 1, 20, 2)


def _player_notes(d: ImageDraw.ImageDraw, x: int, y: int, width: int, team: str, prefix: str, color: tuple[int, int, int], r: Any) -> None:
    d.text((x, y), team.upper(), font=_fit(team.upper(), width, 21, 15, True), fill=color)
    items = _items(r, (f"{prefix}_injuries", f"{prefix}_injury_report", f"{prefix}_lineup_status", f"{prefix}_player_notes", "injury_report", "injuries", "lineup_status", "key_players"), PLAYER_DATA_FALLBACK, 2)
    _bullets(d, x, y + 38, items, width, color, 2, 18, 2)


def _metric(d: ImageDraw.ImageDraw, x: int, y: int, w: int, label: str, value: str, color: tuple[int, int, int]) -> None:
    d.rectangle((x, y, x + w, y + 94), fill=BLACK, outline=(230, 224, 204), width=1)
    d.text((x + 10, y + 10), label, font=_font(18, True), fill=(232, 230, 220))
    _txt(d, x + 10, y + 42, _clean(value, True), _fit(_clean(value, True), w - 18, 34, 18, True), color, w - 18, 1)


def render_full_pick_magazine_page(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True) -> Image.Image:
    away, home = _teams(pick)
    sport = _get(pick, "sport", "league", default="Sport N/A")
    source = _get(pick, "odds_source", "data_source", "bookmaker", "sportsbook", default="Agent row")
    report = (report_name or "Full Pick Magazine").upper()
    date = _get(pick, "report_date", "event_date", "event_start_utc", default=NOT_PROVIDED)
    img = _paper(int(sha256(_game(pick).encode()).hexdigest()[:8], 16))
    _hero(img, background_image, background_mode, background_opacity)
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle((18, 18, PAGE_WIDTH - 18, 82), fill=BLACK)
    d.rectangle((28, 24, 308, 74), fill=RED)
    d.text((43, 33), "ABA SIGNAL PRO", font=_fit("ABA SIGNAL PRO", 250, 34, 25, True), fill="white")
    d.text((330, 31), "DAILY SPORTS ANALYSIS", font=_font(34, True), fill="white")
    d.rounded_rectangle((840, 24, 1050, 74), radius=5, fill=CREAM, outline=BLACK)
    d.text((872, 35), f"PAGE {page_number} OF {total_pages}", font=_font(27, True), fill=BLACK)
    _txt(d, 38, 96, f"REPORT: {report}", _font(21, True), BLACK, 290, 1)
    d.text((338, 96), "*", font=_font(21, True), fill=BLACK)
    _txt(d, 370, 96, f"SOURCE: {source.upper()}", _font(21, True), BLACK, 205, 1)
    d.text((588, 96), "|", font=_font(21, True), fill=BLACK)
    _txt(d, 620, 96, f"DATE: {date.upper()}", _font(21, True), BLACK, 240, 1)
    d.rounded_rectangle((910, 90, 1040, 174), radius=8, fill=BLACK, outline=CREAM, width=3)
    d.text((932, 106), sport.upper()[:12], font=_font(25, True), fill=CREAM)
    _logo_or_badge(img, d, sport, 948, 136, 66, 34, BLUE, use_team_logo)
    d.text((36, 124), away.upper(), font=_fit(away.upper(), 590, 124, 58, True), fill=RED)
    d.text((40, 248), "VS", font=_font(48, True), fill=BLACK)
    d.line((40, 306, 104, 306), fill=BLACK, width=4)
    d.text((112, 236), home.upper(), font=_fit(home.upper(), 560, 100, 48, True), fill=BLUE)
    season = _get(pick, "season_label", "event_stage", "competition_round", default=f"{sport} REGULAR SEASON")
    d.rectangle((36, 330, 506, 378), fill=BLACK)
    _txt(d, 54, 339, season.upper(), _fit(season.upper(), 432, 28, 20, True), CREAM, 432, 1)
    context: list[str] = []
    for key in ("preview_summary", "game_summary", "sports_context_summary", "short_reason", "decision_reasons"):
        context += _split(_row(pick).get(key))
    cy = 394
    for line in (context or ["Context unavailable.", "Confirm price and lineup news before entry."])[:2]:
        cy = _txt(d, 42, cy, line, _font(22), TEXT, 565, 1)
    sy = 456
    d.rounded_rectangle((20, sy, PAGE_WIDTH - 20, sy + 106), radius=13, fill=BLACK, outline=CREAM, width=3)
    d.text((50, sy + 16), "TENDENCIA", font=_font(27, True), fill=RED)
    pick_text = _clean(_pick(pick), True)
    d.text((50, sy + 52), pick_text, font=_fit(pick_text, 220, 36, 20, True), fill=CREAM)
    _logo_or_badge(img, d, home, 268, sy + 27, 58, 50, BLUE, use_team_logo)
    odds = _fmt(_get(pick, "american_odds", "odds_american", "decimal_price", "odds_at_pick", "best_price", "odds"), "odds")
    conf = _pct(_num(pick, "learned_model_probability", "model_probability_clean", "model_probability", "final_probability"))
    edge = _edge(_num(pick, "model_market_edge", "edge"))
    ev = _fmt(_get(pick, "expected_value_per_unit", "profit_expected_value", "expected_value", "ev"), "ev")
    units = _fmt(_get(pick, "recommended_stake_units", "suggested_stake_units", "units", default="1.0"), "unit")
    risk = _clean(_get(pick, "risk", "risk_level", "risk_label", "profit_guard_status", default=NO_VERIFIED), True)
    market = _clean(_get(pick, "market_type", "market", "bet_type", default=NO_VERIFIED), True)
    x = 344
    for (label, value, color), w in zip([("ODDS", odds, CREAM), ("CONFIDENCE", conf, GREEN), ("EDGE", edge, DANGER if edge.startswith("-") else GREEN), ("EV", ev, DANGER if ev.startswith("-") else GREEN), ("UNITS", units, CREAM), ("RISK", risk, GREEN), ("MARKET", market, CREAM)], [92, 138, 106, 112, 96, 104, 104]):
        _metric(d, x, sy + 6, w, label, value, color); x += w
    _section(d, 20, 585, 350, 300, "WHY WE PICKED IT", RED); _bullets(d, 44, 655, _why(pick), 306, RED, 4, 21, 2)
    _section(d, 20, 905, 350, 225, "PRO BETTOR EVIDENCE", BLUE)
    ry = 974
    for lab, val in _pairs(pick):
        d.text((44, ry), f"{lab}:", font=_font(19, True), fill=BLACK); _txt(d, 184, ry, val, _font(19, True), BLACK, 160, 1); ry += 33
    d.rectangle((28, 1088, 362, 1120), fill=BLUE); _txt(d, 42, 1095, _get(pick, "evidence_summary", default="Market and model evidence support this read."), _font(17, True), CREAM, 304, 1)
    _section(d, 386, 585, 674, 365, "TEAM SNAPSHOTS", BLUE); d.line((724, 660, 724, 922), fill=BLACK + (170,), width=1)
    _team_snapshot(img, d, 410, 675, 292, away, "away", RED, pick, use_team_logo); _team_snapshot(img, d, 746, 675, 292, home, "home", BLUE, pick, use_team_logo)
    _section(d, 386, 965, 674, 165, "PLAYER / INJURY NOTES", BLUE); d.line((724, 1028, 724, 1110), fill=BLACK + (160,), width=1)
    _player_notes(d, 410, 1036, 292, away, "away", RED, pick); _player_notes(d, 746, 1036, 292, home, "home", BLUE, pick)
    _section(d, 20, 1150, 340, 205, "RISK DESK", RED); _bullets(d, 44, 1222, _items(pick, ("why_lose", "risk_reason", "hidden_risk", "risk_notes"), f"Risk status: {risk}", 3), 292, RED, 3, 19, 2)
    _section(d, 374, 1150, 332, 205, "MATCHUP NOTES", BLUE); _bullets(d, 398, 1222, _items(pick, ("matchup_note", "matchup_notes", "head_to_head", "h2h", "venue_note", "weather_location", "sports_context_summary"), "Matchup context unavailable from current row/API feed.", 3), 284, BLUE, 3, 19, 2)
    _section(d, 720, 1150, 340, 205, "CHAIN BETTING NOTES", BLUE); _bullets(d, 744, 1222, _items(pick, ("chain_notes", "main_read", "add_on_legs", "parlay_notes"), "Better as an individual straight analysis unless another verified edge exists.", 2), 292, BLUE, 2, 19, 2)
    action = _clean(_get(pick, "final_decision", "agent_decision", "recommendation", "consumer_action", "recommended_action", default="PLAY STANDARD"), True)
    expl = _get(pick, "final_explanation", "action_reason", "recommendation_reason", "decision_reasons", default="Use only if the line remains playable and key news does not change.")
    fy = 1380
    d.rounded_rectangle((20, fy, PAGE_WIDTH - 20, 1562), radius=14, fill=BLACK, outline=RED, width=3); d.rectangle((20, fy, 250, 1562), fill=RED)
    d.text((40, fy + 36), "FINAL", font=_font(36, True), fill=CREAM); d.text((40, fy + 84), "RECOMMENDATION", font=_font(31, True), fill=CREAM)
    d.text((284, fy + 30), action, font=_fit(action, 320, 60, 36, True), fill=GREEN); _txt(d, 284, fy + 100, pick_text, _fit(pick_text, 340, 40, 26, True), CREAM, 340, 1); _txt(d, 660, fy + 44, expl, _font(23), CREAM, 350, 3)
    d.rectangle((20, 1568, PAGE_WIDTH - 20, 1606), fill=BLACK); box = d.textbbox((0, 0), SAFETY_FOOTER, font=_font(17)); d.text(((PAGE_WIDTH - (box[2] - box[0])) / 2, 1578), SAFETY_FOOTER, font=_font(17), fill=CREAM)
    return img.convert("RGB")


def _png(image: Image.Image) -> bytes:
    out = BytesIO(); image.save(out, format="PNG", optimize=True); return out.getvalue()


def render_full_pick_magazine_page_png(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True) -> bytes:
    return _png(render_full_pick_magazine_page(pick, background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo))


def render_full_magazine_book_pages(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True) -> list[Image.Image]:
    rows = list(picks) or [{"event": "No Picks", "prediction": "NO PICK"}]
    return [render_full_pick_magazine_page(row, background_image, report_name, i + 1, len(rows), logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo) for i, row in enumerate(rows)]


def render_full_magazine_book_png(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True) -> bytes:
    pages = render_full_magazine_book_pages(picks, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo)
    book = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT * len(pages)), PAPER)
    for i, page in enumerate(pages): book.paste(page, (0, PAGE_HEIGHT * i))
    return _png(book)


def render_full_magazine_book_pdf(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True) -> bytes:
    pages = [p.convert("RGB") for p in render_full_magazine_book_pages(picks, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo)]
    out = BytesIO(); pages[0].save(out, format="PDF", save_all=True, append_images=pages[1:], resolution=100.0); return out.getvalue()


def render_full_magazine_zip(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True) -> bytes:
    rows = list(picks); pages = render_full_magazine_book_pages(rows, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo); out = BytesIO()
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as z:
        z.writestr("full_magazine_book.png", render_full_magazine_book_png(rows, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo)); z.writestr("full_magazine_book.pdf", render_full_magazine_book_pdf(rows, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo))
        for i, page in enumerate(pages): z.writestr(pick_full_page_filename(rows[i] if i < len(rows) else {"event": "No Picks"}, i), _png(page))
    return out.getvalue()
