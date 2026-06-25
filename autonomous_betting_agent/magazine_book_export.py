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
MAGAZINE_STYLE_VERSION = "premium_v4_reference_compact_no_market_v4"
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

_FONT_CACHE: dict[tuple[int, bool], ImageFont.ImageFont] = {}
FONT_ROOTS = tuple(Path(p) for p in (
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    "/opt/render/project/.apt/usr/share/fonts",
    "/app/.apt/usr/share/fonts",
    "~/.local/share/fonts",
))
BOLD_NAMES = ("DejaVuSansCondensed-Bold.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "Arial Bold.ttf")
REG_NAMES = ("DejaVuSansCondensed.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf", "Arial.ttf")

COUNTRY_ES = {
    "iraq": "Irak",
    "iran": "Irán",
    "france": "Francia",
    "germany": "Alemania",
    "ecuador": "Ecuador",
    "australia": "Australia",
    "paraguay": "Paraguay",
    "netherlands": "Países Bajos",
    "tunisia": "Túnez",
    "egypt": "Egipto",
    "ivory coast": "Costa de Marfil",
    "curacao": "Curazao",
    "curaçao": "Curazao",
    "senegal": "Senegal",
    "norway": "Noruega",
    "algeria": "Argelia",
    "jordan": "Jordania",
    "argentina": "Argentina",
    "spain": "España",
    "england": "Inglaterra",
    "united states": "Estados Unidos",
    "usa": "Estados Unidos",
    "us": "Estados Unidos",
    "mexico": "México",
    "italy": "Italia",
    "brazil": "Brasil",
    "portugal": "Portugal",
    "canada": "Canadá",
    "japan": "Japón",
    "south korea": "Corea del Sur",
    "new zealand": "Nueva Zelanda",
    "czech republic": "República Checa",
}

ES = {
    "DAILY SPORTS ANALYSIS": "ANÁLISIS DEPORTIVO DIARIO",
    "PAGE": "PÁGINA",
    "OF": "DE",
    "REGULAR SEASON": "TEMPORADA REGULAR",
    "TREND": "TENDENCIA",
    "TENDENCIA": "TENDENCIA",
    "ODDS": "CUOTA",
    "CONFIDENCE": "CONFIANZA",
    "EDGE": "VENTAJA",
    "EV": "VE",
    "UNITS": "UNIDADES",
    "RISK": "RIESGO",
    "WHY WE PICKED IT": "POR QUÉ LO ELEGIMOS",
    "PRO BETTOR EVIDENCE": "EVIDENCIA PRO",
    "TEAM SNAPSHOTS": "RESUMEN EQUIPOS",
    "PLAYER / INJURY NOTES": "JUGADORES / LESIONES",
    "RISK DESK": "RIESGO",
    "MATCHUP NOTES": "NOTAS DEL PARTIDO",
    "CHAIN BETTING NOTES": "NOTAS PARLAY",
    "FINAL": "FINAL",
    "RECOMMENDATION": "RECOMENDACIÓN",
    "SOURCE": "FUENTE",
    "BOOK": "CASA",
    "LINE": "LÍNEA",
    "PUBLIC": "PÚBLICO",
    "PRO": "PRO",
    "Context unavailable.": "Contexto no disponible.",
    "Confirm price and lineup news before entry.": "Confirma momio y alineaciones antes de entrar.",
    TEAM_DATA_FALLBACK: "Datos del equipo no disponibles en la fila cargada",
    PLAYER_DATA_FALLBACK: "Datos de jugadores no disponibles en la fila cargada",
    "Use team form, injuries, and market movement before publishing.": "Usa forma del equipo, lesiones y movimiento del mercado antes de publicar.",
    "Confirm lineup/injury news before placing the bet.": "Confirma alineaciones y lesiones antes de apostar.",
    "Market and model evidence support this read.": "El mercado y el modelo respaldan esta lectura.",
    "Recheck odds before entry.": "Revisa el momio antes de entrar.",
    "Avoid if major lineup/weather news changes.": "Evita si cambian alineaciones, clima o noticias clave.",
    "Confirm venue and start time.": "Confirma sede y hora de inicio.",
    "Recheck market movement before publishing.": "Revisa el movimiento del mercado antes de publicar.",
    "Better as an individual straight analysis unless another verified edge exists.": "Mejor como análisis individual salvo que exista otra ventaja verificada.",
    "Do not add weak legs just to increase payout.": "No agregues selecciones débiles solo para subir el pago.",
    "Use only if the line remains playable and key news does not change.": "Usar solo si la línea sigue jugable y no cambia la información clave.",
    "Use only while the line remains playable.": "Usar solo mientras la línea siga jugable.",
    SAFETY_FOOTER: "No garantizamos resultados. Apuesta responsablemente. Este análisis es solo informativo.",
    "VOLUME OK": "VOLUMEN OK",
    "VOLUME_OK": "VOLUMEN OK",
    "LOW": "BAJO",
    "MEDIUM": "MEDIO",
    "HIGH": "ALTO",
    "TOTALS": "TOTALES",
    "MONEYLINE": "GANADOR",
    "SPREAD": "HÁNDICAP",
    "PLAY SMALL": "JUGAR PEQUEÑO",
    "PLAY STANDARD": "JUGAR NORMAL",
    "NO PLAY": "NO JUGAR",
    "consensus average": "promedio consenso",
    "Consensus average": "promedio consenso",
    "Philadelphia, Pennsylvania, USA": "Filadelfia, Pensilvania, EE. UU.",
    "Neutral-site FIFA venue override matched by event teams and start time.": "Sede neutral FIFA detectada por equipos y hora de inicio.",
    "Venue was not provided by the available API.": "La API disponible no proporcionó sede.",
}


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
    return v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


def _get(r: Any, *keys: str, default: str = "") -> str:
    d = _row(r)
    for k in keys:
        v = d.get(k)
        if not _bad(v):
            return str(v).strip()
    return default


def _lang(r: Any = None, explicit: str | None = None) -> str:
    raw = explicit or _get(r, "report_language", "language", "lang", default="")
    text = str(raw or "").lower()
    return "es" if text.startswith("es") or "español" in text or "espanol" in text else "en"


def _team_label(team: str, lang: str) -> str:
    if lang != "es":
        return str(team or "")
    return COUNTRY_ES.get(str(team or "").strip().lower(), str(team or ""))


def _tr(v: Any, lang: str) -> str:
    if _bad(v):
        return NO_VERIFIED if lang == "en" else "Dato no disponible"
    text = str(v)
    if lang != "es":
        text = text.replace("TENDENCIA", "TREND").replace("Contexto no disponible.", "Context unavailable.")
        text = re.sub(r"\bTOTAL DEL PARTIDO\b", "GAME TOTAL", text, flags=re.I)
        text = re.sub(r"\bMÁS DE\b", "OVER", text, flags=re.I)
        text = re.sub(r"\bMENOS DE\b", "UNDER", text, flags=re.I)
        return text
    if text in ES:
        return ES[text]
    low = text.strip().lower()
    if low in COUNTRY_ES:
        return COUNTRY_ES[low]
    if text.startswith("PAGE ") and " OF " in text:
        return text.replace("PAGE ", "PÁGINA ", 1).replace(" OF ", " DE ")
    text = re.sub(r"\bFIFA WORLD CUP\b", "COPA MUNDIAL FIFA", text, flags=re.I)
    text = re.sub(r"\bREGULAR SEASON\b", "TEMPORADA REGULAR", text, flags=re.I)
    text = re.sub(r"\bGAME TOTAL\b", "TOTAL DEL PARTIDO", text, flags=re.I)
    text = re.sub(r"\bOVER\b", "MÁS DE", text, flags=re.I)
    text = re.sub(r"\bUNDER\b", "MENOS DE", text, flags=re.I)
    text = re.sub(r"\bTOTALS\b", "TOTALES", text, flags=re.I)
    text = re.sub(r"\bMONEYLINE\b", "GANADOR", text, flags=re.I)
    text = re.sub(r"\bSPREAD\b", "HÁNDICAP", text, flags=re.I)
    text = text.replace("VOLUME OK", "VOLUMEN OK").replace("VOLUME_OK", "VOLUMEN OK")
    if text.startswith("Risk status:"):
        text = text.replace("Risk status:", "Estado de riesgo:")
    if text.startswith("Model projects "):
        text = re.sub(r"Model projects ([^ ]+) probability for (.+)\.", r"El modelo proyecta \1 de probabilidad para \2.", text)
    if text.startswith("Market-implied probability checks at "):
        text = text.replace("Market-implied probability checks at ", "La probabilidad implícita del mercado es ")
    if text.startswith("Measured edge:"):
        text = text.replace("Measured edge:", "Ventaja medida:")
    if text.startswith("Expected value:"):
        text = text.replace("Expected value:", "Valor esperado:")
    return text


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
            if abs(n) >= 100 and n.is_integer():
                return f"{int(n):+d}" if n > 0 else str(int(n))
            return f"{n:.2f}".rstrip("0").rstrip(".")
        if kind == "ev":
            return f"{n:+.3f}" if abs(n) < 1 else f"{n:+.2f}"
        if kind == "unit":
            return f"{n:.1f}" if abs(n) < 10 else f"{n:.0f}"
        return f"{n:.2f}".rstrip("0").rstrip(".")
    except Exception:
        return _clean(v, kind in {"risk", "market"})


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


def _exists(p: Path) -> bool:
    try:
        return p.expanduser().exists()
    except OSError:
        return False


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    size = max(1, int(size))
    key = (size, bool(bold))
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    names = BOLD_NAMES if bold else REG_NAMES
    for name in names:
        try:
            f = ImageFont.truetype(name, size)
            _FONT_CACHE[key] = f
            return f
        except Exception:
            pass
    for root in FONT_ROOTS:
        root = root.expanduser()
        if not _exists(root):
            continue
        for name in names:
            try:
                matches = list(root.rglob(name))
            except OSError:
                matches = []
            for path in matches:
                try:
                    f = ImageFont.truetype(str(path), size)
                    _FONT_CACHE[key] = f
                    return f
                except Exception:
                    pass
    raise RuntimeError("No scalable TTF font found for magazine rendering. Install DejaVu or Liberation fonts; refusing PIL default tiny bitmap font.")


def _fit(text: str, width: int, start: int, minimum: int = 16, bold: bool = True) -> ImageFont.ImageFont:
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    for size in range(int(start), int(minimum) - 1, -2):
        f = _font(size, bold)
        if d.textbbox((0, 0), str(text), font=f)[2] <= width:
            return f
    return _font(minimum, bold)


def _headline_font(text: str, width: int, preferred: int, minimum: int) -> ImageFont.ImageFont:
    text = str(text or "").upper()
    start = preferred if len(text) <= 8 else min(preferred, 116)
    return _fit(text, width, start, minimum, True)


def _line_height(font: ImageFont.ImageFont) -> int:
    return getattr(font, "size", 18) + 4


def _wrap(d: ImageDraw.ImageDraw, text: str, f: ImageFont.ImageFont, width: int, max_lines: int | None = None) -> list[str]:
    out: list[str] = []
    cur = ""
    words = str(text or "").replace("\n", " ").split()
    for word in words:
        trial = word if not cur else f"{cur} {word}"
        if d.textbbox((0, 0), trial, font=f)[2] <= width:
            cur = trial
        else:
            if cur:
                out.append(cur)
            cur = word
            if max_lines is not None and len(out) >= max_lines:
                return out
    if cur and (max_lines is None or len(out) < max_lines):
        out.append(cur)
    return out


def _txt(d: ImageDraw.ImageDraw, x: int, y: int, text: str, f: ImageFont.ImageFont, fill: Any, width: int, max_lines: int = 1) -> int:
    for line in _wrap(d, text, f, width, max_lines):
        d.text((x, y), line, font=f, fill=fill)
        y += _line_height(f)
    return y


def _txt_auto(d: ImageDraw.ImageDraw, x: int, y: int, text: str, width: int, height: int, start: int, minimum: int, fill: Any, bold: bool = False, max_lines: int | None = None) -> int:
    text = str(text or "")
    if max_lines == 1:
        f = _fit(text, width, start, minimum, bold)
        d.text((x, y), text, font=f, fill=fill)
        return y + _line_height(f)
    for size in range(int(start), int(minimum) - 1, -1):
        f = _font(size, bold)
        lines = _wrap(d, text, f, width, max_lines)
        if lines and len(lines) * _line_height(f) <= height:
            for line in lines:
                d.text((x, y), line, font=f, fill=fill)
                y += _line_height(f)
            return y
    f = _font(minimum, bold)
    bottom = y + height
    for line in _wrap(d, text, f, width, max_lines):
        if y + _line_height(f) > bottom:
            break
        d.text((x, y), line, font=f, fill=fill)
        y += _line_height(f)
    return y


def _split(v: Any) -> list[str]:
    if _bad(v):
        return []
    return [p.strip(" -•") for p in str(v).replace("•", "\n").replace(";", "\n").replace("|", "\n").splitlines() if p.strip(" -•")]


def _game(r: Any) -> str:
    return _get(r, "event", "game", "event_name", "matchup", default="Unknown Matchup")


def _teams(r: Any) -> tuple[str, str]:
    a = _get(r, "away_team", "team_a", "team1")
    b = _get(r, "home_team", "team_b", "team2")
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
        if not _exists(folder):
            continue
        for v in variants:
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                p = folder / f"{v}{ext}"
                if _exists(p):
                    return p
    return None


def _load_image(v: Any) -> Image.Image | None:
    try:
        if isinstance(v, (bytes, bytearray)):
            return Image.open(BytesIO(v)).convert("RGBA")
        if isinstance(v, Image.Image):
            return v.convert("RGBA")
        if isinstance(v, (str, Path)) and _exists(Path(v)):
            return Image.open(v).convert("RGBA")
    except Exception:
        return None
    return None


def _resample() -> int:
    return getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def _cover(img: Image.Image, size: tuple[int, int], anchor_y: float = 0.5) -> Image.Image:
    w, h = size
    scale = max(w / max(1, img.width), h / max(1, img.height))
    r = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), _resample())
    x = max(0, (r.width - w) // 2)
    y = int(max(0, r.height - h) * max(0, min(1, anchor_y)))
    return r.crop((x, y, x + w, y + h))


def _contain(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    r = img.copy()
    r.thumbnail(size, _resample())
    return r


def _paper(seed: int) -> Image.Image:
    rng = random.Random(seed)
    img = Image.new("RGBA", (PAGE_WIDTH, PAGE_HEIGHT), PAPER + (255,))
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(130):
        x, y = rng.randint(0, PAGE_WIDTH - 1), rng.randint(0, PAGE_HEIGHT - 1)
        q = rng.randint(20, 125)
        d.rectangle((x, y, x + 1, y + 1), fill=(q, q, q, rng.randint(4, 14)))
    d.rectangle((10, 10, PAGE_WIDTH - 10, PAGE_HEIGHT - 10), outline=RED + (230,), width=4)
    d.rectangle((17, 17, PAGE_WIDTH - 17, PAGE_HEIGHT - 17), outline=BLACK + (200,), width=2)
    return img


def _hero(img: Image.Image, bg: Any, mode: str, opacity: float) -> None:
    d = ImageDraw.Draw(img, "RGBA")
    loaded = _load_image(bg)
    mode = str(mode or "hero_right").lower()
    if loaded and mode == "full_page":
        layer = _cover(loaded, (PAGE_WIDTH, PAGE_HEIGHT)).filter(ImageFilter.GaussianBlur(0.8))
        layer = ImageEnhance.Color(layer).enhance(0.4)
        layer.putalpha(int(255 * min(max(opacity, 0.08), 0.12)))
        img.alpha_composite(layer, (0, 0))
        img.alpha_composite(Image.new("RGBA", (PAGE_WIDTH, PAGE_HEIGHT), PAPER + (155,)), (0, 0))
    elif loaded and mode == "watermark":
        mark = _contain(loaded, (560, 420))
        mark.putalpha(int(255 * min(max(opacity, 0.10), 0.15)))
        img.alpha_composite(mark, (PAGE_WIDTH - mark.width - 34, 120))
    elif loaded and mode != "none":
        slot = _cover(loaded, (430, 350), 0.18)
        slot = ImageEnhance.Color(slot).enhance(1.05)
        slot = ImageEnhance.Contrast(slot).enhance(1.15)
        slot.putalpha(Image.new("L", (430, 350), int(255 * min(max(opacity, 0.90), 0.98))))
        img.alpha_composite(slot, (620, 105))
        d.rectangle((620, 105, 1050, 455), outline=BLACK + (205,), width=3)
    else:
        d.rectangle((620, 105, 1050, 455), fill=BLUE + (90,), outline=BLACK + (185,), width=3)
        for i in range(12):
            d.line((620 + i * 25, 420, 850 + i * 25, 120), fill=RED + (76,), width=9)


def _initials(s: str) -> str:
    p = re.findall(r"[A-Za-z0-9]+", str(s).upper())
    return "".join(x[0] for x in p[:3]) or "TM"


def _badge(img: Image.Image, d: ImageDraw.ImageDraw, label: str, x: int, y: int, w: int, h: int, color: tuple[int, int, int], use_logo: bool = True) -> None:
    logo = _load_image(find_local_team_logo(label)) if use_logo else None
    if logo:
        d.rounded_rectangle((x, y, x + w, y + h), radius=8, fill=CREAM + (245,), outline=color, width=2)
        logo = _contain(logo, (w - 8, h - 8))
        img.alpha_composite(logo, (x + (w - logo.width) // 2, y + (h - logo.height) // 2))
        return
    d.rounded_rectangle((x, y, x + w, y + h), radius=8, fill=color, outline=CREAM, width=2)
    t = _initials(label)[:3]
    f = _fit(t, w - 8, max(20, h // 2), 13, True)
    box = d.textbbox((0, 0), t, font=f)
    d.text((x + (w - box[2] + box[0]) / 2, y + (h - box[3] + box[1]) / 2 - 2), t, font=f, fill="white")


def _section(d: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, title: str, color: tuple[int, int, int], lang: str = "en") -> None:
    title = _tr(title, lang).upper()
    d.rounded_rectangle((x, y, x + w, y + h), radius=14, fill=CREAM + (255,), outline=BLACK + (238,), width=3)
    d.rounded_rectangle((x, y, x + w, y + 56), radius=10, fill=color)
    d.text((x + 18, y + 11), title, font=_fit(title, w - 36, 33, 21, True), fill=CREAM)


def _bullets_auto(d: ImageDraw.ImageDraw, x: int, y: int, items: list[str], width: int, height: int, color: tuple[int, int, int], start: int = 22, minimum: int = 11, limit: int | None = None, lang: str = "en") -> None:
    data = [_tr(item, lang) for item in (items[:limit] if limit is not None else items)]
    chosen: ImageFont.ImageFont | None = None
    chosen_lines: list[list[str]] = []
    for size in range(start, minimum - 1, -1):
        f = _font(size)
        blocks = [_wrap(d, item, f, width - 30, None) for item in data]
        need = sum(max(1, len(block)) * _line_height(f) + 8 for block in blocks)
        if need <= height:
            chosen, chosen_lines = f, blocks
            break
    if chosen is None:
        chosen = _font(minimum)
        chosen_lines = [_wrap(d, item, chosen, width - 30, None) for item in data]
    bottom = y + height
    for block in chosen_lines:
        if y + _line_height(chosen) > bottom:
            break
        d.ellipse((x, y + 8, x + 12, y + 20), fill=color)
        for line in block:
            if y + _line_height(chosen) > bottom:
                break
            d.text((x + 25, y), line, font=chosen, fill=TEXT)
            y += _line_height(chosen)
        y += 8


def _items(r: Any, keys: Iterable[str], fallback: str | list[str], limit: int) -> list[str]:
    out: list[str] = []
    for k in keys:
        out += _split(_row(r).get(k))
    if out:
        return out[:limit]
    return (fallback if isinstance(fallback, list) else [fallback])[:limit]


def _why(r: Any, lang: str = "en") -> list[str]:
    out: list[str] = []
    for k in ("why_bullets", "why_pick", "analysis_summary", "reason", "explanation"):
        out += _split(_row(r).get(k))
    if out:
        return [_tr(x, lang) for x in out[:4]]
    pick = _tr(_pick(r), lang)
    vals = [
        f"Model projects {_pct(_num(r, 'learned_model_probability', 'model_probability_clean', 'model_probability', 'final_probability'))} probability for {pick}.",
        f"Market-implied probability checks at {_pct(_num(r, 'market_probability', 'market_implied_probability'))}.",
        f"Measured edge: {_edge(_num(r, 'model_market_edge', 'edge'))}.",
        f"Expected value: {_fmt(_get(r, 'expected_value_per_unit', 'profit_expected_value', 'expected_value', 'ev'), 'ev')}.",
    ]
    return [_tr(v, lang) for v in vals if NO_VERIFIED not in v] or [_tr("Use only while the line remains playable.", lang)]


def _pairs(r: Any, lang: str = "en") -> list[tuple[str, str]]:
    rows = [
        ("SOURCE", _get(r, "odds_source", "data_source", default=NO_VERIFIED)),
        ("BOOK", _get(r, "bookmaker", "sportsbook", default=NO_VERIFIED)),
        ("LINE", _get(r, "line_movement", "price_movement", "market_move", default=NO_VERIFIED)),
        ("PUBLIC", _pct(_num(r, "public_percent", "public_bet_percent", "public_pct"))),
        ("PRO", _pct(_num(r, "pro_percent", "sharp_percent", "smart_money_percent"))),
    ]
    return [(_tr(a, lang), _tr(_clean(b), lang)) for a, b in rows if b != NO_VERIFIED][:5]


def _team_snapshot(img: Image.Image, d: ImageDraw.ImageDraw, x: int, y: int, width: int, team: str, color: tuple[int, int, int], use_logo: bool, lang: str) -> None:
    label = _team_label(team, lang)
    _badge(img, d, label, x, y, 50, 50, color, use_logo)
    d.text((x + 66, y + 9), label.upper(), font=_fit(label.upper(), width - 70, 25, 14, True), fill=color)
    _bullets_auto(d, x, y + 76, [TEAM_DATA_FALLBACK, "Use team form, injuries, and market movement before publishing."], width - 10, 165, color, 18, 10, 4, lang)


def _looks_like_combat_measurement(text: str) -> bool:
    low = str(text or "").lower()
    measurement_terms = ("stance:", "reach:", "height:", "weight:", "orthodox", "southpaw", "switch")
    team_terms = ("injur", "lineup", "out", "doubtful", "questionable", "probable", "day-to-day", "suspended")
    return any(term in low for term in measurement_terms) and not any(term in low for term in team_terms)


def _player_items(r: Any, prefix: str) -> list[str]:
    keys = (
        f"{prefix}_injuries",
        f"{prefix}_injury_report",
        f"{prefix}_lineup_status",
        f"{prefix}_player_notes",
        "injury_report",
        "injuries",
        "lineup_status",
        "key_players",
    )
    out: list[str] = []
    for key in keys:
        for item in _split(_row(r).get(key)):
            if not _looks_like_combat_measurement(item):
                out.append(item)
    if out:
        return out[:3]
    return [PLAYER_DATA_FALLBACK, "Confirm lineup/injury news before placing the bet."]


def _player_notes(d: ImageDraw.ImageDraw, x: int, y: int, width: int, team: str, prefix: str, color: tuple[int, int, int], r: Any, lang: str, note_height: int = 98) -> None:
    label = _team_label(team, lang)
    d.text((x, y), label.upper(), font=_fit(label.upper(), width, 21, 12, True), fill=color)
    _bullets_auto(d, x, y + 32, _player_items(r, prefix), width, note_height, color, 16, 8, 3, lang)


def _metric(d: ImageDraw.ImageDraw, x: int, y: int, w: int, label: str, value: str, color: tuple[int, int, int], lang: str = "en") -> None:
    w = min(w, max(52, PAGE_WIDTH - 20 - x))
    label = _tr(label, lang)
    value = _tr(value, lang)
    d.rectangle((x, y, x + w, y + 94), fill=BLACK, outline=(230, 224, 204), width=1)
    d.text((x + 7, y + 10), label, font=_fit(label, w - 12, 17, 9, True), fill=(232, 230, 220))
    clean = _clean(value, True)
    _txt_auto(d, x + 7, y + 43, clean, w - 12, 38, 36, 8, color, True, 1)


def render_full_pick_magazine_page(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> Image.Image:
    lang = _lang(pick, language)
    away, home = _teams(pick)
    away_label, home_label = _team_label(away, lang), _team_label(home, lang)
    sport = _get(pick, "sport", "league", default="Sport N/A")
    img = _paper(int(sha256(_game(pick).encode()).hexdigest()[:8], 16))
    _hero(img, background_image, background_mode, background_opacity)
    d = ImageDraw.Draw(img, "RGBA")

    d.rectangle((18, 18, PAGE_WIDTH - 18, 82), fill=BLACK)
    d.rectangle((28, 24, 308, 74), fill=RED)
    d.text((43, 29), "ABA SIGNAL PRO", font=_fit("ABA SIGNAL PRO", 250, 38, 25, True), fill="white")
    daily = _tr("DAILY SPORTS ANALYSIS", lang)
    d.text((330, 28), daily, font=_fit(daily, 470, 38, 20, True), fill="white")
    d.rounded_rectangle((840, 24, 1050, 74), radius=5, fill=CREAM, outline=BLACK)
    page_label = _tr(f"PAGE {page_number} OF {total_pages}", lang)
    d.text((862, 32), page_label, font=_fit(page_label, 174, 28, 16, True), fill=BLACK)

    d.text((36, 105), away_label.upper(), font=_headline_font(away_label, 590, 140, 72), fill=RED)
    d.text((40, 246), "VS", font=_font(50, True), fill=BLACK)
    d.line((40, 306, 106, 306), fill=BLACK, width=4)
    d.text((112, 220), home_label.upper(), font=_headline_font(home_label, 560, 112, 62), fill=BLUE)
    season = _tr(_get(pick, "season_label", "event_stage", "competition_round", default=f"{sport} REGULAR SEASON"), lang)
    d.rectangle((36, 330, 506, 378), fill=BLACK)
    _txt(d, 54, 339, season.upper(), _fit(season.upper(), 432, 28, 15, True), CREAM, 432, 1)
    cy = 394
    ctx: list[str] = []
    for k in ("preview_summary", "game_summary", "sports_context_summary", "short_reason", "decision_reasons"):
        ctx += _split(_row(pick).get(k))
    for line in (ctx or ["Context unavailable.", "Confirm price and lineup news before entry."])[:2]:
        cy = _txt_auto(d, 42, cy, _tr(line, lang), 565, 28, 20, 12, TEXT, False, 1)

    sy = 456
    d.rounded_rectangle((20, sy, PAGE_WIDTH - 20, sy + 106), radius=13, fill=BLACK, outline=CREAM, width=3)
    trend = _tr("TREND", lang)
    d.text((50, sy + 16), trend, font=_fit(trend, 190, 25, 14, True), fill=RED)
    pick_text = _tr(_clean(_pick(pick), True), lang).upper()
    _txt_auto(d, 50, sy + 52, pick_text, 210, 38, 30, 8, CREAM, True, 1)
    _badge(img, d, home_label, 268, sy + 27, 58, 50, BLUE, use_team_logo)

    odds = _fmt(_get(pick, "american_odds", "odds_american", "decimal_price", "odds_at_pick", "best_price", "odds"), "odds")
    conf = _pct(_num(pick, "learned_model_probability", "model_probability_clean", "model_probability", "final_probability"))
    edge = _edge(_num(pick, "model_market_edge", "edge"))
    ev = _fmt(_get(pick, "expected_value_per_unit", "profit_expected_value", "expected_value", "ev"), "ev")
    units = _fmt(_get(pick, "recommended_stake_units", "suggested_stake_units", "units", default="1.0"), "unit")
    risk = _tr(_clean(_get(pick, "risk", "risk_level", "risk_label", "profit_guard_status", default=NO_VERIFIED), True), lang)
    x = 344
    labels = [("ODDS", odds, CREAM), ("CONFIDENCE", conf, GREEN), ("EDGE", edge, DANGER if edge.startswith("-") else GREEN), ("EV", ev, DANGER if ev.startswith("-") else GREEN), ("UNITS", units, CREAM), ("RISK", risk, GREEN)]
    metric_widths = [98, 140, 108, 108, 96, (PAGE_WIDTH - 20) - (344 + 98 + 140 + 108 + 108 + 96)]
    for (lab, val, col), w in zip(labels, metric_widths):
        _metric(d, x, sy + 6, w, lab, val, col, lang)
        x += w
    # Defensive cleanup: the removed MARKET/TOTALS metric must never render, and the risk cell must consume the old slot.
    d.line((PAGE_WIDTH - 20, sy + 7, PAGE_WIDTH - 20, sy + 99), fill=(230, 224, 204), width=1)

    left_x, left_w, right_x, right_w = 20, 320, 352, 708
    _section(d, left_x, 585, left_w, 300, "WHY WE PICKED IT", RED, lang)
    _bullets_auto(d, left_x + 24, 655, _why(pick, lang), left_w - 44, 210, RED, 22, 10, 4, lang)
    _section(d, left_x, 905, left_w, 225, "PRO BETTOR EVIDENCE", BLUE, lang)
    ry = 974
    for lab, val in (_pairs(pick, lang) or [(_tr("SOURCE", lang), _tr(_get(pick, "odds_source", default="Agent row"), lang)), (_tr("BOOK", lang), NO_VERIFIED)])[:5]:
        d.text((left_x + 24, ry), f"{lab}:", font=_fit(f"{lab}:", 82, 17, 9, True), fill=BLACK)
        _txt_auto(d, left_x + 112, ry, val, left_w - 128, 22, 17, 9, BLACK, True, 1)
        ry += 31
    d.rectangle((left_x + 8, 1088, left_x + left_w - 8, 1120), fill=BLUE)
    _txt_auto(d, left_x + 22, 1093, _tr(_get(pick, "evidence_summary", default="Market and model evidence support this read."), lang), left_w - 44, 26, 16, 7, CREAM, True, None)

    _section(d, right_x, 585, right_w, 365, "TEAM SNAPSHOTS", BLUE, lang)
    divider = right_x + right_w // 2
    d.line((divider, 660, divider, 922), fill=BLACK + (170,), width=1)
    snap_w = right_w // 2 - 52
    _team_snapshot(img, d, right_x + 24, 675, snap_w, away, RED, use_team_logo, lang)
    _team_snapshot(img, d, divider + 24, 675, snap_w, home, BLUE, use_team_logo, lang)

    player_y, player_h = 952, 208
    _section(d, right_x, player_y, right_w, player_h, "PLAYER / INJURY NOTES", BLUE, lang)
    d.line((divider, player_y + 66, divider, player_y + player_h - 22), fill=BLACK + (160,), width=1)
    _player_notes(d, right_x + 24, player_y + 74, snap_w, away, "away", RED, pick, lang, note_height=106)
    _player_notes(d, divider + 24, player_y + 74, snap_w, home, "home", BLUE, pick, lang, note_height=106)

    low_y, low_h = 1178, 175
    _section(d, 20, low_y, 320, low_h, "RISK DESK", RED, lang)
    _bullets_auto(d, 44, low_y + 70, _items(pick, ("why_lose", "risk_reason", "hidden_risk", "risk_notes"), [f"Risk status: {risk}", "Recheck odds before entry.", "Avoid if major lineup/weather news changes."], 3), 272, low_h - 88, RED, 16, 8, 3, lang)
    _section(d, 354, low_y, 344, low_h, "MATCHUP NOTES", BLUE, lang)
    _bullets_auto(d, 378, low_y + 70, _items(pick, ("matchup_note", "matchup_notes", "head_to_head", "h2h", "venue_note", "weather_location", "sports_context_summary"), ["Context unavailable.", "Confirm venue and start time.", "Recheck market movement before publishing."], 3), 296, low_h - 88, BLUE, 16, 8, 3, lang)
    _section(d, 712, low_y, 348, low_h, "CHAIN BETTING NOTES", BLUE, lang)
    _bullets_auto(d, 736, low_y + 70, _items(pick, ("chain_notes", "main_read", "add_on_legs", "parlay_notes"), ["Better as an individual straight analysis unless another verified edge exists.", "Do not add weak legs just to increase payout."], 2), 300, low_h - 88, BLUE, 16, 8, 2, lang)

    action = _tr(_clean(_get(pick, "final_decision", "agent_decision", "recommendation", "consumer_action", "recommended_action", default="PLAY STANDARD"), True), lang)
    expl = _tr(_get(pick, "final_explanation", "action_reason", "recommendation_reason", "decision_reasons", default="Use only if the line remains playable and key news does not change."), lang)
    fy, fb = 1374, 1532
    d.rounded_rectangle((20, fy, PAGE_WIDTH - 20, fb), radius=14, fill=BLACK, outline=RED, width=3)
    d.rectangle((20, fy, 250, fb), fill=RED)
    d.text((40, fy + 30), _tr("FINAL", lang), font=_font(30, True), fill=CREAM)
    rec = _tr("RECOMMENDATION", lang)
    d.text((40, fy + 76), rec, font=_fit(rec, 190, 24, 14, True), fill=CREAM)
    d.text((284, fy + 18), action.upper(), font=_fit(action.upper(), 340, 66, 22, True), fill=GREEN)
    _txt_auto(d, 284, fy + 92, pick_text, 360, 34, 46, 10, CREAM, True, 1)
    _txt_auto(d, 670, fy + 38, expl, 340, 82, 20, 10, CREAM, False, None)

    footer_y, footer_b = 1542, 1581
    d.rectangle((20, footer_y, PAGE_WIDTH - 20, footer_b), fill=BLACK)
    footer = _tr(SAFETY_FOOTER, lang)
    f = _fit(footer, PAGE_WIDTH - 70, 16, 10, False)
    box = d.textbbox((0, 0), footer, font=f)
    d.text(((PAGE_WIDTH - (box[2] - box[0])) / 2, footer_y + 10), footer, font=f, fill=CREAM)
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
    pages = [p.convert("RGB") for p in render_full_magazine_book_pages(picks, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)]
    out = BytesIO()
    pages[0].save(out, format="PDF", save_all=True, append_images=pages[1:], resolution=100.0)
    return out.getvalue()


def render_full_magazine_zip(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
    rows = list(picks)
    pages = render_full_magazine_book_pages(rows, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
    out = BytesIO()
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as z:
        z.writestr("full_magazine_book.png", render_full_magazine_book_png(rows, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))
        z.writestr("full_magazine_book.pdf", render_full_magazine_book_pdf(rows, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))
        for i, page in enumerate(pages):
            z.writestr(pick_full_page_filename(rows[i] if i < len(rows) else {"event": "No Picks"}, i), _png(page))
    return out.getvalue()
