from __future__ import annotations

from dataclasses import asdict, is_dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import math
import random
import re
from typing import Any, Iterable, Mapping
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

PAGE_WIDTH = 1080
PAGE_HEIGHT = 1620
MAGAZINE_STYLE_VERSION = "premium_v4_reference_compact_no_market_v7_headline_autosize"
NO_MARKET_EXPORT_VERSION = "no_market_metric_v6"
SAFETY_FOOTER = "No guarantees. Bet responsibly. This analysis is for informational purposes only."
ASSET_DIRS = (Path("assets/team_logos"), Path("assets/report_logos"), Path("assets/licensed_logos"))
TEAM_DATA_FALLBACK = "Data not available from uploaded row"
PLAYER_DATA_FALLBACK = "Player data not available in uploaded row"

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

HEADLINE_AREA = (20, 90, 610, 455)
AWAY_HEADLINE_BOX = (36, 100, 600, 200)
VS_BADGE_BOX = (36, 214, 104, 286)
HOME_HEADLINE_BOX = (112, 204, 600, 314)
SEASON_BAR_BOX = (36, 330, 506, 378)
CONTEXT_LINE_BOX = (42, 394, 600, 450)
HERO_IMAGE_BOX = (620, 105, 1050, 455)
METRIC_STRIP_BOX = (20, 456, 1060, 562)

_FONT_CACHE: dict[tuple[int, bool], ImageFont.ImageFont] = {}
FONT_ROOTS = tuple(Path(p) for p in (
    "/usr/share/fonts", "/usr/local/share/fonts", "/opt/render/project/.apt/usr/share/fonts",
    "/app/.apt/usr/share/fonts", "~/.local/share/fonts",
))
BOLD_NAMES = ("DejaVuSansCondensed-Bold.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "Arial Bold.ttf")
REG_NAMES = ("DejaVuSansCondensed.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf", "Arial.ttf")

ES = {
    "DAILY SPORTS ANALYSIS": "ANÁLISIS DEPORTIVO DIARIO", "PAGE": "PÁGINA", "OF": "DE",
    "TREND": "TENDENCIA", "ODDS": "CUOTA", "CONFIDENCE": "CONFIANZA", "EDGE": "VENTAJA",
    "EV": "VE", "UNITS": "UNIDADES", "RISK": "RIESGO", "WHY WE PICKED IT": "POR QUÉ LO ELEGIMOS",
    "PRO BETTOR EVIDENCE": "EVIDENCIA PRO", "TEAM SNAPSHOTS": "RESUMEN EQUIPOS",
    "PLAYER / INJURY NOTES": "JUGADORES / LESIONES", "RISK DESK": "RIESGO",
    "MATCHUP NOTES": "NOTAS DEL PARTIDO", "CHAIN BETTING NOTES": "NOTAS PARLAY",
    "FINAL": "FINAL", "RECOMMENDATION": "RECOMENDACIÓN", "SOURCE": "FUENTE", "BOOK": "CASA",
    "LINE": "LÍNEA", "PUBLIC": "PÚBLICO", "PRO": "PRO", "LOW": "BAJO", "MEDIUM": "MEDIO",
    "HIGH": "ALTO", "VOLUME OK": "VOLUMEN OK", "VOLUME_OK": "VOLUMEN OK",
    "PLAY SMALL": "JUGAR PEQUEÑO", "PLAY STANDARD": "JUGAR NORMAL", "NO PLAY": "NO JUGAR",
    SAFETY_FOOTER: "No garantizamos resultados. Apuesta responsablemente. Este análisis es solo informativo.",
}

COUNTRY_ES = {
    "iraq": "Irak", "iran": "Irán", "france": "Francia", "germany": "Alemania",
    "ecuador": "Ecuador", "australia": "Australia", "paraguay": "Paraguay",
    "netherlands": "Países Bajos", "tunisia": "Túnez", "egypt": "Egipto",
    "ivory coast": "Costa de Marfil", "curacao": "Curazao", "curaçao": "Curazao",
    "senegal": "Senegal", "norway": "Noruega", "algeria": "Argelia", "jordan": "Jordania",
    "argentina": "Argentina", "spain": "España", "england": "Inglaterra",
    "united states": "Estados Unidos", "usa": "Estados Unidos", "us": "Estados Unidos",
    "mexico": "México", "italy": "Italia", "brazil": "Brasil", "portugal": "Portugal",
    "canada": "Canadá", "japan": "Japón", "south korea": "Corea del Sur",
    "new zealand": "Nueva Zelanda", "czech republic": "República Checa",
}


def _row(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict"):
        data = value.to_dict()
        return data if isinstance(data, Mapping) else {}
    return getattr(value, "__dict__", {}) or {}


def _bad(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value)) or str(value).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


def _get(row: Any, *keys: str, default: str = "") -> str:
    data = _row(row)
    for key in keys:
        value = data.get(key)
        if not _bad(value):
            return str(value).strip()
    return default


def _num(row: Any, *keys: str) -> float | None:
    for key in keys:
        value = _row(row).get(key)
        if _bad(value):
            continue
        try:
            return float(str(value).replace("%", "").replace(",", ""))
        except Exception:
            continue
    return None


def _lang(row: Any = None, explicit: str | None = None) -> str:
    raw = explicit or _get(row, "report_language", "language", "lang", default="")
    text = str(raw or "").lower()
    return "es" if text.startswith("es") or "español" in text or "espanol" in text else "en"


def _team_label(team: str, lang: str) -> str:
    text = str(team or "").strip()
    return COUNTRY_ES.get(text.lower(), text) if lang == "es" else text


def _tr(value: Any, lang: str) -> str:
    if _bad(value):
        return NO_VERIFIED if lang == "en" else "Dato no disponible"
    text = str(value)
    if lang != "es":
        return text.replace("TENDENCIA", "TREND")
    if text in ES:
        return ES[text]
    low = text.strip().lower()
    if low in COUNTRY_ES:
        return COUNTRY_ES[low]
    text = re.sub(r"\bFIFA WORLD CUP\b", "COPA MUNDIAL FIFA", text, flags=re.I)
    text = re.sub(r"\bREGULAR SEASON\b", "TEMPORADA REGULAR", text, flags=re.I)
    text = re.sub(r"\bGAME TOTAL\b", "TOTAL DEL PARTIDO", text, flags=re.I)
    text = re.sub(r"\bOVER\b", "MÁS DE", text, flags=re.I)
    text = re.sub(r"\bUNDER\b", "MENOS DE", text, flags=re.I)
    return text


def _clean(value: Any, upper: bool = False) -> str:
    if _bad(value):
        return NO_VERIFIED
    text = re.sub(r"\s+", " ", str(value).replace("_", " ").strip())
    return text.upper() if upper else text


def _fmt(value: Any, kind: str = "") -> str:
    if _bad(value):
        return NO_VERIFIED
    try:
        num = float(str(value).replace("%", "").replace(",", ""))
        if kind == "odds":
            if abs(num) >= 100 and num.is_integer():
                return f"{int(num):+d}" if num > 0 else str(int(num))
            return f"{num:.2f}".rstrip("0").rstrip(".")
        if kind == "ev":
            return f"{num:+.3f}" if abs(num) < 1 else f"{num:+.2f}"
        if kind == "unit":
            return f"{num:.1f}" if abs(num) < 10 else f"{num:.0f}"
        return f"{num:.2f}".rstrip("0").rstrip(".")
    except Exception:
        return _clean(value, kind == "risk")


def _pct(num: float | None) -> str:
    if num is None:
        return NO_VERIFIED
    num = num / 100 if abs(num) > 1 else num
    return f"{num:.0%}"


def _edge(num: float | None) -> str:
    if num is None:
        return NO_VERIFIED
    num = num / 100 if abs(num) > 1 else num
    return f"{num:+.1%}"


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    key = (max(1, int(size)), bool(bold))
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    names = BOLD_NAMES if bold else REG_NAMES
    for name in names:
        try:
            font = ImageFont.truetype(name, key[0])
            _FONT_CACHE[key] = font
            return font
        except Exception:
            pass
    for root in FONT_ROOTS:
        root = root.expanduser()
        if not root.exists():
            continue
        for name in names:
            for path in root.rglob(name):
                try:
                    font = ImageFont.truetype(str(path), key[0])
                    _FONT_CACHE[key] = font
                    return font
                except Exception:
                    pass
    raise RuntimeError("No scalable TTF font found for magazine rendering. Install DejaVu or Liberation fonts; refusing PIL default tiny bitmap font.")


def _fit(text: str, width: int, start: int, minimum: int = 12, bold: bool = True) -> ImageFont.ImageFont:
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    for size in range(int(start), max(1, int(minimum)) - 1, -1):
        font = _font(size, bold)
        if draw.textbbox((0, 0), str(text), font=font)[2] <= width:
            return font
    return _font(max(1, int(minimum)), bold)


def _line_height(font: ImageFont.ImageFont) -> int:
    return getattr(font, "size", 18) + 4


def _rect_w(rect: tuple[int, int, int, int]) -> int:
    return rect[2] - rect[0]


def _rect_h(rect: tuple[int, int, int, int]) -> int:
    return rect[3] - rect[1]


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), str(text), font=font)
    return int(box[2] - box[0])


def _intersects(a: tuple[int, int, int, int], b: tuple[int, int, int, int], padding: int = 0) -> bool:
    return not (a[2] + padding <= b[0] or b[2] + padding <= a[0] or a[3] + padding <= b[1] or b[3] + padding <= a[1])


def _contained(outer: tuple[int, int, int, int], inner: tuple[int, int, int, int]) -> bool:
    return inner[0] >= outer[0] and inner[1] >= outer[1] and inner[2] <= outer[2] and inner[3] <= outer[3]


def _split_long_word_to_width(draw: ImageDraw.ImageDraw, word: str, font: ImageFont.ImageFont, max_width: int, remaining: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for ch in str(word):
        trial = current + ch
        if _text_width(draw, trial, font) <= max_width or not current:
            current = trial
        else:
            chunks.append(current)
            if len(chunks) >= remaining:
                return chunks
            current = ch
    if current and len(chunks) < remaining:
        chunks.append(current)
    return chunks


def _wrap_text_to_box(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int, max_lines: int) -> list[str]:
    words = str(text or "").replace("\n", " ").split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if _text_width(draw, trial, font) <= max_width:
            current = trial
            continue
        if current:
            lines.append(current)
            if len(lines) >= max_lines:
                return lines[:max_lines]
            current = ""
        if _text_width(draw, word, font) <= max_width:
            current = word
            continue
        broken = _split_long_word_to_width(draw, word, font, max_width, max_lines - len(lines))
        lines.extend(broken[:-1])
        if len(lines) >= max_lines:
            return lines[:max_lines]
        current = broken[-1] if broken else ""
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines or [""]


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int, max_lines: int | None = None) -> list[str]:
    return _wrap_text_to_box(draw, text, font, width, max_lines or 999)


def _ellipsize_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    text = str(text or "")
    if _text_width(draw, text, font) <= max_width:
        return text
    suffix = "…"
    while text and _text_width(draw, text + suffix, font) > max_width:
        text = text[:-1]
    return f"{text}{suffix}" if text else suffix


def _fit_lines_to_box(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int], max_font: int, min_font: int, max_lines: int, bold: bool = True) -> tuple[ImageFont.ImageFont, list[str]]:
    label = " ".join(str(text or "").upper().split())
    for size in range(int(max_font), int(min_font) - 1, -1):
        font = _font(size, bold)
        line_sets = [[label]] if _text_width(draw, label, font) <= _rect_w(box) else []
        line_sets.append(_wrap_text_to_box(draw, label, font, _rect_w(box), max_lines))
        for lines in line_sets:
            if not lines or len(lines) > max_lines:
                continue
            if len(lines) * _line_height(font) > _rect_h(box):
                continue
            if all(_text_width(draw, line, font) <= _rect_w(box) for line in lines):
                return font, lines
    font = _font(max(1, int(min_font)), bold)
    lines = _wrap_text_to_box(draw, label, font, _rect_w(box), max_lines)
    return font, [_ellipsize_to_width(draw, line, font, _rect_w(box)) for line in lines[:max_lines]]


def _draw_headline_name(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int], color: tuple[int, int, int], max_font: int, min_font: int = 6, max_lines: int = 2) -> list[tuple[int, int, int, int]]:
    font, lines = _fit_lines_to_box(draw, text, box, max_font, min_font, max_lines, True)
    line_h = _line_height(font)
    total_h = min(_rect_h(box), len(lines) * line_h)
    y = box[1] + max(0, (_rect_h(box) - total_h) // 2)
    boxes: list[tuple[int, int, int, int]] = []
    for line in lines:
        if y + line_h > box[3]:
            break
        safe_line = _ellipsize_to_width(draw, line, font, _rect_w(box))
        width = _text_width(draw, safe_line, font)
        draw.text((box[0], y), safe_line, font=font, fill=color)
        boxes.append((box[0], y, box[0] + width, y + line_h))
        y += line_h
    return boxes


def _draw_small_text_box(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int], color: tuple[int, int, int], max_font: int, min_font: int = 8, bold: bool = False, max_lines: int = 2) -> list[tuple[int, int, int, int]]:
    font, lines = _fit_lines_to_box(draw, text, box, max_font, min_font, max_lines, bold)
    y = box[1]
    line_h = _line_height(font)
    boxes: list[tuple[int, int, int, int]] = []
    for line in lines:
        if y + line_h > box[3]:
            break
        safe_line = _ellipsize_to_width(draw, line, font, _rect_w(box))
        width = _text_width(draw, safe_line, font)
        draw.text((box[0], y), safe_line, font=font, fill=color)
        boxes.append((box[0], y, box[0] + width, y + line_h))
        y += line_h
    return boxes


def _headline_context_lines(row: Any) -> list[str]:
    ctx: list[str] = []
    for key in ("preview_summary", "game_summary", "sports_context_summary", "short_reason", "decision_reasons"):
        ctx += _split(_row(row).get(key))
    return ctx or ["Context unavailable."]


def _draw_matchup_headlines(draw: ImageDraw.ImageDraw, away_label: str, home_label: str, sport: str, row: Any, lang: str) -> dict[str, list[tuple[int, int, int, int]]]:
    draw.rectangle(HEADLINE_AREA, fill=PAPER)
    away_boxes = _draw_headline_name(draw, away_label, AWAY_HEADLINE_BOX, RED, 60, 6, 2)
    draw.rounded_rectangle(VS_BADGE_BOX, radius=7, fill=CREAM, outline=BLACK, width=2)
    _draw_headline_name(draw, "V", (VS_BADGE_BOX[0] + 14, VS_BADGE_BOX[1] + 10, VS_BADGE_BOX[2] - 14, VS_BADGE_BOX[3] - 10), BLACK, 34, 10, 1)
    home_boxes = _draw_headline_name(draw, home_label, HOME_HEADLINE_BOX, BLUE, 52, 6, 2)
    season = _tr(_get(row, "season_label", "event_stage", "competition_round", default=f"{sport} REGULAR SEASON"), lang).upper()
    draw.rectangle(SEASON_BAR_BOX, fill=BLACK)
    season_boxes = _draw_small_text_box(draw, season, (SEASON_BAR_BOX[0] + 18, SEASON_BAR_BOX[1] + 9, SEASON_BAR_BOX[2] - 14, SEASON_BAR_BOX[3] - 6), CREAM, 25, 8, True, 1)
    context_boxes = _draw_small_text_box(draw, _tr(_headline_context_lines(row)[0], lang), CONTEXT_LINE_BOX, TEXT, 18, 8, False, 2)
    return {"away": away_boxes, "home": home_boxes, "season": season_boxes, "context": context_boxes}


def _txt_auto(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, width: int, height: int, start: int, minimum: int, fill: Any, bold: bool = False, max_lines: int | None = None) -> int:
    if max_lines == 1:
        font = _fit(str(text), width, start, minimum, bold)
        draw.text((x, y), _ellipsize_to_width(draw, str(text), font, width), font=font, fill=fill)
        return y + _line_height(font)
    for size in range(start, minimum - 1, -1):
        font = _font(size, bold)
        lines = _wrap(draw, str(text), font, width, max_lines)
        if lines and len(lines) * _line_height(font) <= height:
            for line in lines:
                draw.text((x, y), _ellipsize_to_width(draw, line, font, width), font=font, fill=fill)
                y += _line_height(font)
            return y
    font = _font(minimum, bold)
    bottom = y + height
    for line in _wrap(draw, str(text), font, width, max_lines):
        if y + _line_height(font) > bottom:
            break
        draw.text((x, y), _ellipsize_to_width(draw, line, font, width), font=font, fill=fill)
        y += _line_height(font)
    return y


def _split(value: Any) -> list[str]:
    if _bad(value):
        return []
    return [part.strip(" -•") for part in str(value).replace("•", "\n").replace(";", "\n").replace("|", "\n").splitlines() if part.strip(" -•")]


def _game(row: Any) -> str:
    return _get(row, "event", "game", "event_name", "matchup", default="Unknown Matchup")


def _teams(row: Any) -> tuple[str, str]:
    away = _get(row, "away_team", "team_a", "team1")
    home = _get(row, "home_team", "team_b", "team2")
    if away and home:
        return away, home
    game = _game(row)
    for sep in (" at ", " vs ", " VS ", " v ", " @ "):
        if sep in game:
            left, right = game.split(sep, 1)
            return left.strip(), right.strip()
    return _get(row, "team", default="Team A"), _get(row, "opponent", default="Team B")


def _pick(row: Any) -> str:
    return _get(row, "prediction", "exact_bet", "pick", "selection", "recommended_action", "consumer_action", default=NOT_PROVIDED)


def sanitize_image_filename(value: str, suffix: str = "", extension: str = "png") -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "magazine").lower()).strip("_") or "magazine"
    extra = re.sub(r"[^A-Za-z0-9]+", "_", str(suffix or "").lower()).strip("_")
    return f"{base + '_' + extra if extra else base}.{(extension or 'png').lstrip('.')}"


def pick_full_page_filename(pick: Any, index: int, extension: str = "png") -> str:
    return sanitize_image_filename(f"pick_{index + 1:02d}_{_game(pick)}", "full_page", extension)


def _load_image(value: Any) -> Image.Image | None:
    try:
        if isinstance(value, (bytes, bytearray)):
            return Image.open(BytesIO(value)).convert("RGBA")
        if isinstance(value, Image.Image):
            return value.convert("RGBA")
        if isinstance(value, (str, Path)) and Path(value).expanduser().exists():
            return Image.open(value).convert("RGBA")
    except Exception:
        return None
    return None


def _resample() -> int:
    return getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def _cover(img: Image.Image, size: tuple[int, int], anchor_y: float = 0.5) -> Image.Image:
    width, height = size
    scale = max(width / max(1, img.width), height / max(1, img.height))
    resized = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), _resample())
    x = max(0, (resized.width - width) // 2)
    y = int(max(0, resized.height - height) * max(0, min(1, anchor_y)))
    return resized.crop((x, y, x + width, y + height))


def _paper(seed: int) -> Image.Image:
    rng = random.Random(seed)
    img = Image.new("RGBA", (PAGE_WIDTH, PAGE_HEIGHT), PAPER + (255,))
    draw = ImageDraw.Draw(img, "RGBA")
    for _ in range(130):
        x, y = rng.randint(0, PAGE_WIDTH - 1), rng.randint(0, PAGE_HEIGHT - 1)
        tone = rng.randint(20, 125)
        draw.rectangle((x, y, x + 1, y + 1), fill=(tone, tone, tone, rng.randint(4, 14)))
    draw.rectangle((10, 10, PAGE_WIDTH - 10, PAGE_HEIGHT - 10), outline=RED + (230,), width=4)
    draw.rectangle((17, 17, PAGE_WIDTH - 17, PAGE_HEIGHT - 17), outline=BLACK + (200,), width=2)
    return img


def _hero(img: Image.Image, background: Any, mode: str, opacity: float) -> None:
    draw = ImageDraw.Draw(img, "RGBA")
    loaded = _load_image(background)
    mode = str(mode or "hero_right").lower()
    if loaded and mode == "full_page":
        layer = _cover(loaded, (PAGE_WIDTH, PAGE_HEIGHT)).filter(ImageFilter.GaussianBlur(0.8))
        layer = ImageEnhance.Color(layer).enhance(0.4)
        layer.putalpha(int(255 * min(max(opacity, 0.08), 0.12)))
        img.alpha_composite(layer, (0, 0))
        img.alpha_composite(Image.new("RGBA", (PAGE_WIDTH, PAGE_HEIGHT), PAPER + (155,)), (0, 0))
        return
    if loaded and mode != "none":
        slot = _cover(loaded, (430, 350), 0.18)
        slot = ImageEnhance.Color(slot).enhance(1.05)
        slot = ImageEnhance.Contrast(slot).enhance(1.15)
        slot.putalpha(Image.new("L", (430, 350), int(255 * min(max(opacity, 0.90), 0.98))))
        img.alpha_composite(slot, (620, 105))
        draw.rectangle((620, 105, 1050, 455), outline=BLACK + (205,), width=3)
        return
    draw.rectangle((620, 105, 1050, 455), fill=BLUE + (245,), outline=BLACK + (205,), width=3)
    for i in range(12):
        draw.line((620 + i * 25, 420, 850 + i * 25, 120), fill=RED + (210,), width=9)


def _initials(text: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", str(text).upper())
    return "".join(part[0] for part in parts[:3]) or "TM"


def _badge(img: Image.Image, draw: ImageDraw.ImageDraw, label: str, x: int, y: int, width: int, height: int, color: tuple[int, int, int], *_args: Any, **_kwargs: Any) -> None:
    draw.rounded_rectangle((x, y, x + width, y + height), radius=8, fill=color, outline=CREAM, width=2)
    text = _initials(label)[:3]
    font = _fit(text, width - 8, max(20, height // 2), 8, True)
    box = draw.textbbox((0, 0), text, font=font)
    draw.text((x + (width - box[2] + box[0]) / 2, y + (height - box[3] + box[1]) / 2 - 2), text, font=font, fill="white")


def _section(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, height: int, title: str, color: tuple[int, int, int], lang: str) -> None:
    label = _tr(title, lang).upper()
    draw.rounded_rectangle((x, y, x + width, y + height), radius=14, fill=CREAM + (255,), outline=BLACK + (238,), width=3)
    draw.rounded_rectangle((x, y, x + width, y + 56), radius=10, fill=color)
    draw.text((x + 18, y + 11), label, font=_fit(label, width - 36, 33, 18, True), fill=CREAM)


def _bullets_auto(draw: ImageDraw.ImageDraw, x: int, y: int, items: list[str], width: int, height: int, color: tuple[int, int, int], start: int = 22, minimum: int = 10, limit: int | None = None, lang: str = "en") -> None:
    data = [_tr(item, lang) for item in (items[:limit] if limit is not None else items)]
    chosen = _font(max(5, minimum))
    blocks: list[list[str]] = []
    for size in range(start, max(5, minimum) - 1, -1):
        font = _font(size)
        trial = [_wrap_text_to_box(draw, item, font, width - 30, 4) for item in data]
        needed = sum(max(1, len(block)) * _line_height(font) + 8 for block in trial)
        if needed <= height:
            chosen, blocks = font, trial
            break
    if not blocks:
        blocks = [_wrap_text_to_box(draw, item, chosen, width - 30, 4) for item in data]
    bottom = y + height
    for block in blocks:
        if y + _line_height(chosen) > bottom:
            break
        draw.ellipse((x, y + 8, x + 12, y + 20), fill=color)
        for line in block:
            if y + _line_height(chosen) > bottom:
                break
            draw.text((x + 25, y), _ellipsize_to_width(draw, line, chosen, width - 30), font=chosen, fill=TEXT)
            y += _line_height(chosen)
        y += 8


def _items(row: Any, keys: Iterable[str], fallback: list[str], limit: int) -> list[str]:
    out: list[str] = []
    for key in keys:
        out += _split(_row(row).get(key))
    return (out or fallback)[:limit]


def _why(row: Any, lang: str) -> list[str]:
    out: list[str] = []
    for key in ("why_bullets", "why_pick", "analysis_summary", "reason", "explanation"):
        out += _split(_row(row).get(key))
    if out:
        return out[:4]
    pick = _tr(_pick(row), lang)
    vals = [
        f"Model projects {_pct(_num(row, 'learned_model_probability', 'model_probability_clean', 'model_probability', 'final_probability'))} probability for {pick}.",
        f"Market-implied probability checks at {_pct(_num(row, 'market_probability', 'market_implied_probability'))}.",
        f"Measured edge: {_edge(_num(row, 'model_market_edge', 'edge'))}.",
        f"Expected value: {_fmt(_get(row, 'expected_value_per_unit', 'profit_expected_value', 'expected_value', 'ev'), 'ev')}.",
    ]
    return [value for value in vals if NO_VERIFIED not in value] or ["Use only while the line remains playable."]


def _pairs(row: Any, lang: str) -> list[tuple[str, str]]:
    rows = [
        ("SOURCE", _get(row, "odds_source", "data_source", default=NO_VERIFIED)),
        ("BOOK", _get(row, "bookmaker", "sportsbook", default=NO_VERIFIED)),
        ("LINE", _get(row, "line_movement", "price_movement", "price_move", default=NO_VERIFIED)),
        ("PUBLIC", _pct(_num(row, "public_percent", "public_bet_percent", "public_pct"))),
        ("PRO", _pct(_num(row, "pro_percent", "sharp_percent", "smart_money_percent"))),
    ]
    return [(_tr(label, lang), _tr(_clean(value), lang)) for label, value in rows if value != NO_VERIFIED][:5]


def _team_snapshot(img: Image.Image, draw: ImageDraw.ImageDraw, x: int, y: int, width: int, team: str, color: tuple[int, int, int], lang: str) -> None:
    label = _team_label(team, lang)
    _badge(img, draw, label, x, y, 50, 50, color)
    draw.text((x + 66, y + 9), label.upper(), font=_fit(label.upper(), width - 70, 25, 7, True), fill=color)
    _bullets_auto(draw, x, y + 76, [TEAM_DATA_FALLBACK, "Use team form, injuries, and price movement before publishing."], width - 10, 165, color, 18, 8, 4, lang)


def _looks_like_combat_measurement(text: str) -> bool:
    low = str(text or "").lower()
    measurement_terms = ("stance:", "reach:", "height:", "orthodox", "southpaw", "switch")
    team_terms = ("injur", "lineup", "out", "doubtful", "questionable", "probable", "day-to-day", "suspended")
    return any(term in low for term in measurement_terms) and not any(term in low for term in team_terms)


def _player_items(row: Any, prefix: str) -> list[str]:
    keys = (f"{prefix}_injuries", f"{prefix}_injury_report", f"{prefix}_lineup_status", f"{prefix}_player_notes", "injury_report", "injuries", "lineup_status", "key_players")
    out: list[str] = []
    for key in keys:
        for item in _split(_row(row).get(key)):
            if not _looks_like_combat_measurement(item):
                out.append(item)
    return out[:3] if out else [PLAYER_DATA_FALLBACK, "Confirm lineup/injury news before placing the bet."]


def _player_notes(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, team: str, prefix: str, color: tuple[int, int, int], row: Any, lang: str) -> None:
    label = _team_label(team, lang)
    draw.text((x, y), label.upper(), font=_fit(label.upper(), width, 21, 7, True), fill=color)
    _bullets_auto(draw, x, y + 32, _player_items(row, prefix), width, 106, color, 16, 7, 3, lang)


def _metric(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, label: str, value: str, color: tuple[int, int, int], lang: str) -> None:
    label = _tr(label, lang)
    value = _tr(value, lang)
    draw.rectangle((x, y, x + width, y + 94), fill=BLACK, outline=(230, 224, 204), width=1)
    draw.text((x + 7, y + 10), label, font=_fit(label, width - 14, 17, 7, True), fill=(232, 230, 220))
    _txt_auto(draw, x + 7, y + 43, _clean(value, True), width - 14, 38, 36, 7, color, True, 1)


def _headline_boxes(row: Any, language: str = "en") -> dict[str, list[tuple[int, int, int, int]]]:
    lang = _lang(row, language)
    away, home = _teams(row)
    img = Image.new("RGBA", (PAGE_WIDTH, PAGE_HEIGHT), PAPER + (255,))
    draw = ImageDraw.Draw(img, "RGBA")
    return _draw_matchup_headlines(draw, _team_label(away, lang), _team_label(home, lang), _get(row, "sport", "league", default="Sport N/A"), row, lang)


def validate_headline_layout(row: Any, language: str = "en") -> list[str]:
    boxes = _headline_boxes(row, language)
    warnings: list[str] = []
    for name, safe_box in (("away", AWAY_HEADLINE_BOX), ("home", HOME_HEADLINE_BOX)):
        for box in boxes.get(name, []):
            if not _contained(safe_box, box):
                warnings.append(f"{name}:outside_safe_box")
            if not _contained(HEADLINE_AREA, box):
                warnings.append(f"{name}:outside_headline_area")
            if _intersects(box, HERO_IMAGE_BOX):
                warnings.append(f"{name}:hero_overlap")
            if _intersects(box, SEASON_BAR_BOX):
                warnings.append(f"{name}:season_overlap")
            if _intersects(box, METRIC_STRIP_BOX):
                warnings.append(f"{name}:metric_overlap")
    for away_box in boxes.get("away", []):
        for home_box in boxes.get("home", []):
            if _intersects(away_box, home_box):
                warnings.append("headline:away_home_overlap")
    for home_box in boxes.get("home", []):
        if _intersects(home_box, VS_BADGE_BOX):
            warnings.append("home:vs_badge_overlap")
    return sorted(set(warnings))


def validate_magazine_layout_no_overflow(row: Any, language: str = "en") -> list[str]:
    return validate_headline_layout(row, language=language)


def render_full_pick_magazine_page(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> Image.Image:
    lang = _lang(pick, language)
    away, home = _teams(pick)
    away_label = _team_label(away, lang)
    home_label = _team_label(home, lang)
    sport = _get(pick, "sport", "league", default="Sport N/A")
    img = _paper(int(sha256(_game(pick).encode()).hexdigest()[:8], 16))
    _hero(img, background_image, background_mode, background_opacity)
    draw = ImageDraw.Draw(img, "RGBA")

    draw.rectangle((18, 18, PAGE_WIDTH - 18, 82), fill=BLACK)
    draw.rectangle((28, 24, 308, 74), fill=RED)
    draw.text((43, 29), "ABA SIGNAL PRO", font=_fit("ABA SIGNAL PRO", 250, 38, 25, True), fill="white")
    daily = _tr("DAILY SPORTS ANALYSIS", lang)
    draw.text((330, 28), daily, font=_fit(daily, 470, 38, 20, True), fill="white")
    draw.rounded_rectangle((840, 24, 1050, 74), radius=5, fill=CREAM, outline=BLACK)
    page_text = _tr(f"PAGE {page_number} OF {total_pages}", lang)
    draw.text((862, 32), page_text, font=_fit(page_text, 174, 28, 16, True), fill=BLACK)

    _draw_matchup_headlines(draw, away_label, home_label, sport, pick, lang)

    sy = 456
    draw.rounded_rectangle((20, sy, 1060, sy + 106), radius=13, fill=BLACK, outline=CREAM, width=3)
    trend = _tr("TREND", lang)
    draw.text((50, sy + 16), trend, font=_fit(trend, 190, 25, 14, True), fill=RED)
    pick_text = _tr(_clean(_pick(pick), True), lang).upper()
    _txt_auto(draw, 50, sy + 52, pick_text, 210, 38, 30, 7, CREAM, True, 1)
    _badge(img, draw, home_label, 268, sy + 27, 58, 50, BLUE)

    odds = _fmt(_get(pick, "american_odds", "odds_american", "decimal_price", "odds_at_pick", "best_price", "odds"), "odds")
    conf = _pct(_num(pick, "learned_model_probability", "model_probability_clean", "model_probability", "final_probability"))
    edge = _edge(_num(pick, "model_market_edge", "edge"))
    ev = _fmt(_get(pick, "expected_value_per_unit", "profit_expected_value", "expected_value", "ev"), "ev")
    units = _fmt(_get(pick, "recommended_stake_units", "suggested_stake_units", "units", default="1.0"), "unit")
    risk = _tr(_clean(_get(pick, "risk", "risk_level", "risk_label", "profit_guard_status", default=NO_VERIFIED), True), lang)
    edge_color = DANGER if edge.startswith("-") else GREEN
    ev_color = DANGER if ev.startswith("-") else GREEN
    metric_cells = [
        ("ODDS", odds, CREAM, 345, 98),
        ("CONFIDENCE", conf, GREEN, 443, 145),
        ("EDGE", edge, edge_color, 588, 112),
        ("EV", ev, ev_color, 700, 112),
        ("UNITS", units, CREAM, 812, 100),
        ("RISK", risk, GREEN, 912, 148),
    ]
    for label, value, color, x, width in metric_cells:
        _metric(draw, x, sy + 6, width, label, value, color, lang)
    draw.line((1060, sy + 7, 1060, sy + 99), fill=(230, 224, 204), width=1)

    left_x, left_w, right_x, right_w = 20, 320, 352, 708
    _section(draw, left_x, 585, left_w, 300, "WHY WE PICKED IT", RED, lang)
    _bullets_auto(draw, left_x + 24, 655, _why(pick, lang), left_w - 44, 210, RED, 22, 8, 4, lang)
    _section(draw, left_x, 905, left_w, 225, "PRO BETTOR EVIDENCE", BLUE, lang)
    y = 974
    for label, value in (_pairs(pick, lang) or [(_tr("SOURCE", lang), _tr(_get(pick, "odds_source", default="Agent row"), lang)), (_tr("BOOK", lang), NO_VERIFIED)])[:5]:
        draw.text((left_x + 24, y), f"{label}:", font=_fit(f"{label}:", 82, 17, 7, True), fill=BLACK)
        _txt_auto(draw, left_x + 112, y, value, left_w - 128, 22, 17, 7, BLACK, True, 1)
        y += 31
    draw.rectangle((left_x + 8, 1088, left_x + left_w - 8, 1120), fill=BLUE)
    _txt_auto(draw, left_x + 22, 1093, _tr(_get(pick, "evidence_summary", default="Market and model evidence support this read."), lang), left_w - 44, 26, 16, 6, CREAM, True, None)

    _section(draw, right_x, 585, right_w, 365, "TEAM SNAPSHOTS", BLUE, lang)
    divider = right_x + right_w // 2
    draw.line((divider, 660, divider, 922), fill=BLACK + (170,), width=1)
    snap_w = right_w // 2 - 52
    _team_snapshot(img, draw, right_x + 24, 675, snap_w, away, RED, lang)
    _team_snapshot(img, draw, divider + 24, 675, snap_w, home, BLUE, lang)

    player_y, player_h = 952, 208
    _section(draw, right_x, player_y, right_w, player_h, "PLAYER / INJURY NOTES", BLUE, lang)
    draw.line((divider, player_y + 66, divider, player_y + player_h - 22), fill=BLACK + (160,), width=1)
    _player_notes(draw, right_x + 24, player_y + 74, snap_w, away, "away", RED, pick, lang)
    _player_notes(draw, divider + 24, player_y + 74, snap_w, home, "home", BLUE, pick, lang)

    low_y, low_h = 1178, 175
    _section(draw, 20, low_y, 320, low_h, "RISK DESK", RED, lang)
    _bullets_auto(draw, 44, low_y + 70, _items(pick, ("why_lose", "risk_reason", "hidden_risk", "risk_notes"), [f"Risk status: {risk}", "Recheck odds before entry.", "Avoid if key news changes"], 3), 272, low_h - 88, RED, 16, 7, 3, lang)
    _section(draw, 354, low_y, 344, low_h, "MATCHUP NOTES", BLUE, lang)
    _bullets_auto(draw, 378, low_y + 70, _items(pick, ("matchup_note", "matchup_notes", "head_to_head", "h2h", "venue_note", "weather_location", "sports_context_summary"), ["Context unavailable.", "Confirm venue and start time.", "Recheck price before publishing."], 3), 296, low_h - 88, BLUE, 16, 7, 3, lang)
    _section(draw, 712, low_y, 348, low_h, "CHAIN BETTING NOTES", BLUE, lang)
    _bullets_auto(draw, 736, low_y + 70, _items(pick, ("chain_notes", "main_read", "add_on_legs", "parlay_notes"), ["Straight only: research", "Do not combine without official verification", "Wait for better context or price"], 3), 300, low_h - 88, BLUE, 16, 7, 3, lang)

    action = _tr(_clean(_get(pick, "final_decision", "agent_decision", "recommendation", "consumer_action", "recommended_action", default="PLAY STANDARD"), True), lang)
    explanation = _tr(_get(pick, "final_explanation", "action_reason", "recommendation_reason", "decision_reasons", default="Use only if the line remains playable and key news does not change."), lang)
    fy, fb = 1374, 1532
    draw.rounded_rectangle((20, fy, 1060, fb), radius=14, fill=BLACK, outline=RED, width=3)
    draw.rectangle((20, fy, 250, fb), fill=RED)
    draw.text((40, fy + 30), _tr("FINAL", lang), font=_font(30, True), fill=CREAM)
    rec = _tr("RECOMMENDATION", lang)
    draw.text((40, fy + 76), rec, font=_fit(rec, 190, 24, 12, True), fill=CREAM)
    draw.text((284, fy + 18), action.upper(), font=_fit(action.upper(), 340, 66, 18, True), fill=GREEN)
    _txt_auto(draw, 284, fy + 92, pick_text, 360, 34, 46, 8, CREAM, True, 1)
    _txt_auto(draw, 670, fy + 38, explanation, 340, 82, 20, 8, CREAM, False, None)

    footer_y, footer_b = 1542, 1581
    draw.rectangle((20, footer_y, 1060, footer_b), fill=BLACK)
    footer = _tr(SAFETY_FOOTER, lang)
    font = _fit(footer, PAGE_WIDTH - 190, 16, 10, False)
    draw.text((42, footer_y + 10), _ellipsize_to_width(draw, footer, font, PAGE_WIDTH - 190), font=font, fill=CREAM)
    version = "v6 no-market"
    vfont = _font(14, True)
    vbox = draw.textbbox((0, 0), version, font=vfont)
    draw.text((1048 - (vbox[2] - vbox[0]), footer_y + 10), version, font=vfont, fill=GREEN)
    return img.convert("RGB")


def _png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def render_full_pick_magazine_page_png(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
    return _png(render_full_pick_magazine_page(pick, background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))


def render_full_magazine_book_pages(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> list[Image.Image]:
    rows = list(picks) or [{"event": "No Picks", "prediction": "NO PICK"}]
    return [render_full_pick_magazine_page(row, background_image, report_name, i + 1, len(rows), logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language) for i, row in enumerate(rows)]


def render_full_magazine_book_png(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
    pages = render_full_magazine_book_pages(picks, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
    book = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT * len(pages)), PAPER)
    for i, page in enumerate(pages):
        book.paste(page, (0, PAGE_HEIGHT * i))
    return _png(book)


def render_full_magazine_book_pdf(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
    pages = [page.convert("RGB") for page in render_full_magazine_book_pages(picks, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)]
    out = BytesIO()
    pages[0].save(out, format="PDF", save_all=True, append_images=pages[1:], resolution=100.0)
    return out.getvalue()


def _versioned_page_filename(row: Any, index: int) -> str:
    base = pick_full_page_filename(row, index, extension="")
    return sanitize_image_filename(base, NO_MARKET_EXPORT_VERSION, "png")


def render_full_magazine_zip(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
    rows = list(picks)
    pages = render_full_magazine_book_pages(rows, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
    out = BytesIO()
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as zip_file:
        zip_file.writestr(f"full_magazine_book_{NO_MARKET_EXPORT_VERSION}.png", render_full_magazine_book_png(rows, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))
        zip_file.writestr(f"full_magazine_book_{NO_MARKET_EXPORT_VERSION}.pdf", render_full_magazine_book_pdf(rows, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))
        for index, page in enumerate(pages):
            row = rows[index] if index < len(rows) else {"event": "No Picks"}
            zip_file.writestr(_versioned_page_filename(row, index), _png(page))
    return out.getvalue()
