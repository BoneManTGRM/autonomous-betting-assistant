from __future__ import annotations

from io import BytesIO
from typing import Any, Iterable
import hashlib
import re

PATCH_VERSION = "direct_second_page_v4_truth_contract"
GOLD = (241, 184, 45)

ES = {
    "ADVANCED MARKET ANALYSIS": "ANÁLISIS AVANZADO DE MERCADO",
    "PAGE": "PÁGINA",
    "OF": "DE",
    "VERIFIED": "VERIFICADO",
    "VERIFY SOURCE": "VERIFICAR FUENTE",
    "HISTORY ONLY": "SOLO HISTORIAL",
    "PRICE": "CUOTA",
    "Primary Anchor": "Ancla principal",
    "Chain Map": "Mapa parlay",
    "Live Watch": "Monitoreo en vivo",
    "Prop Board": "Tablero props",
    "Quality Gate": "Filtro de calidad",
    "All-Sport Menu": "Menú multi-deporte",
    "ADVANCED MARKETS NEED VERIFICATION": "MERCADOS AVANZADOS REQUIEREN VERIFICACIÓN",
    "ADVANCED MARKETS READY FOR REVIEW": "MERCADOS AVANZADOS LISTOS PARA REVISIÓN",
    "This page never creates a source claim from missing data and is safe for review.": "Esta página no crea afirmaciones desde datos faltantes y es segura para revisión.",
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        try:
            data = value.to_dict()
            return dict(data) if isinstance(data, dict) else {}
        except Exception:
            return {}
    return dict(getattr(value, "__dict__", {}) or {})


def _lang(data: dict[str, Any], language: str | None = None) -> str:
    text = _clean(language or data.get("report_language") or data.get("language") or data.get("lang")).lower()
    return "es" if text.startswith("es") or "español" in text or "espanol" in text else "en"


def _tr(value: Any, lang: str) -> str:
    text = _clean(value)
    if lang != "es":
        return text
    if text in ES:
        return ES[text]
    replacements = (
        ("Primary read", "Lectura principal"),
        ("Page one remains the official anchor", "La página uno sigue siendo el ancla oficial"),
        ("Add-ons require exact event and line match", "Los agregados requieren coincidencia exacta de evento y línea"),
        ("Missing feeds stay verification-only", "Feeds faltantes quedan solo para verificación"),
        ("No verified chain notes attached", "Sin notas parlay verificadas"),
        ("No compatible add-on selections attached", "Sin selecciones agregadas compatibles"),
        ("Use as watchlist until source match is verified", "Usar como lista de seguimiento hasta verificar la fuente"),
        ("No verified in-game trigger attached", "Sin gatillo en vivo verificado"),
        ("Refresh source data before use", "Actualizar datos fuente antes de usar"),
        ("Use only after event and market match", "Usar solo tras coincidir evento y mercado"),
        ("Source gate", "Filtro fuente"),
        ("Value gate", "Filtro valor"),
        ("Market gate", "Filtro mercado"),
        ("Context gate", "Filtro contexto"),
        ("requires positive EV and edge", "requiere EV y ventaja positivos"),
        ("requires exact event, line, selection", "requiere evento, línea y selección exactos"),
        ("requires current news/status check", "requiere revisión actual de noticias/estado"),
        ("Prop ideas are menu-only until live odds and context are verified", "Las props son solo menú hasta verificar cuotas y contexto en vivo"),
        ("No advanced prop recommendation without source match", "Sin recomendación prop avanzada sin coincidencia de fuente"),
        ("Use Page 1 straight-bet anchor only", "Usar solo el ancla de apuesta directa de Página 1"),
    )
    for old, new in replacements:
        text = re.sub(re.escape(old), new, text, flags=re.I)
    return text


def _get(data: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        text = _clean(data.get(key))
        if text and text.lower() not in {"nan", "none", "null", "n/a", "na", "--"}:
            return text
    return default


def _split(value: Any) -> list[str]:
    text = str(value or "").replace("•", "\n").replace(";", "\n").replace("|", "\n")
    return [_clean(part).strip(" -•") for part in text.splitlines() if _clean(part).strip(" -•")]


def _decimal_text(value: Any) -> str | None:
    raw = _clean(value).replace("−", "-").replace("–", "-").replace("—", "-").replace(",", "")
    if not raw:
        return None
    try:
        num = float(raw)
    except Exception:
        return None
    if num <= -100:
        num = 1.0 + 100.0 / abs(num)
    elif num >= 100:
        num = 1.0 + num / 100.0
    elif num <= 1:
        return None
    return f"{num:.2f}".rstrip("0").rstrip(".")


def _ok(data: dict[str, Any]) -> bool:
    status = _get(data, "odds_status", "odds_api_status").lower()
    flag = _get(data, "odds_api_live", "the_odds_api_live").lower()
    mode = _get(data, "report_source_mode").lower()
    return mode == "current-run" and (status in {"live", "live_match", "live_api", "odds_api_live_match"} or flag in {"1", "true", "yes", "live"})


def _source_status(data: dict[str, Any], lang: str) -> tuple[str, tuple[int, int, int]]:
    mode = _get(data, "report_source_mode").lower()
    if mode == "ledger-history":
        return _tr("HISTORY ONLY", lang), GOLD
    if _ok(data):
        return _tr("VERIFIED", lang), (61, 205, 84)
    return _tr("VERIFY SOURCE", lang), GOLD


def _items(data: dict[str, Any], keys: tuple[str, ...], fallback: list[str], lang: str = "en") -> list[str]:
    out: list[str] = []
    for key in keys:
        out.extend(_split(data.get(key)))
    out = [item for item in out if not any(token in item.lower() for token in ("not returned", "data unavailable", "context unavailable"))]
    return [_tr(item, lang) for item in (out or fallback)[:4]]


def _source_rows(data: dict[str, Any], lang: str) -> list[str]:
    return [
        _tr("Source: ", lang) + _tr(_get(data, "report_source_label", "report_source_mode", default="VERIFY"), lang),
        _tr("Scope: ", lang) + _tr(_get(data, "report_data_scope", default="VERIFY"), lang),
        _tr("Odds: ", lang) + _tr(_get(data, "odds_status", "odds_source", default="VERIFY"), lang),
        _tr("Context: ", lang) + _tr(_get(data, "context_status", "context_source", default="VERIFY"), lang),
    ]


def _png(image: Any) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _draw_second_page(module: Any, pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 2, total_pages: int = 2, language: str | None = None):
    from PIL import ImageDraw
    data = _row(pick)
    lang = _lang(data, language)
    black = getattr(module, "BLACK", (13, 14, 16))
    red = getattr(module, "RED", (190, 30, 28))
    blue = getattr(module, "BLUE", (19, 66, 108))
    cream = getattr(module, "CREAM", (255, 248, 230))
    paper = getattr(module, "PAPER", (244, 235, 211))
    seed = int(hashlib.sha256((_get(data, "event", "game", "matchup", default="advanced") + "page2").encode()).hexdigest()[:8], 16)
    img = module._paper(seed).convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle((18, 18, 1062, 82), fill=black)
    draw.rectangle((28, 24, 308, 74), fill=red)
    draw.text((43, 29), "ABA SIGNAL PRO", font=module._fit("ABA SIGNAL PRO", 250, 38, 25, True), fill="white")
    title = _tr("ADVANCED MARKET ANALYSIS", lang)
    draw.text((330, 28), title, font=module._fit(title, 500, 34, 15, True), fill="white")
    page_text = f"{_tr('PAGE', lang)} {page_number} {_tr('OF', lang)} {total_pages}"
    draw.rounded_rectangle((840, 24, 1050, 74), radius=5, fill=cream, outline=black)
    draw.text((862, 32), page_text, font=module._fit(page_text, 174, 28, 16, True), fill=black)
    away, home = module._teams(data)
    pick_text = module._pick(data)
    matchup = f"{away} vs {home}".upper()
    draw.text((42, 106), matchup, font=module._fit(matchup, 690, 58, 20, True), fill=red)
    draw.text((42, 176), _tr(pick_text.upper(), lang), font=module._fit(_tr(pick_text.upper(), lang), 650, 42, 16, True), fill=blue)
    status, status_color = _source_status(data, lang)
    draw.rounded_rectangle((710, 106, 1042, 224), radius=14, fill=black, outline=status_color, width=3)
    draw.text((730, 124), status, font=module._fit(status, 292, 25, 11, True), fill=status_color)
    price = _decimal_text(_get(data, "decimal_price", "decimal_odds", "odds", "best_price", "odds_at_pick", "american_odds", "odds_american")) or "N/A"
    price_text = f"{_tr('PRICE', lang)} {price}"
    draw.text((730, 164), price_text, font=module._fit(price_text, 250, 30, 13, True), fill=cream)

    def box(x: int, y: int, w: int, h: int, title: str, rows: list[str], color: tuple[int, int, int]) -> None:
        draw.rounded_rectangle((x, y, x + w, y + h), radius=14, fill=paper + (255,), outline=black + (220,), width=3)
        draw.rounded_rectangle((x, y, x + w, y + 52), radius=10, fill=color)
        label = _tr(title, lang).upper()
        draw.text((x + 16, y + 10), label, font=module._fit(label, w - 32, 28, 12, True), fill=cream)
        cy = y + 72
        for item in rows[:4]:
            if cy > y + h - 32:
                break
            draw.ellipse((x + 18, cy + 6, x + 31, cy + 19), fill=color)
            module._txt_auto(draw, x + 42, cy, _tr(item, lang), w - 62, 44, 17, 7, black, False, 2)
            cy += 54

    note = _get(data, "report_truth_warning", default="Page two adds advanced market context without changing the page one straight-bet anchor.")
    draw.rounded_rectangle((42, 248, 1042, 312), radius=12, fill=GOLD + (245,), outline=black, width=2)
    module._txt_auto(draw, 64, 264, _tr(note, lang), 956, 32, 22, 9, black, True, 1)
    box(42, 340, 488, 300, "Primary Anchor", ["Primary read: " + pick_text + ".", "Page one remains the official anchor.", *_source_rows(data, lang)[:2]], red)
    box(552, 340, 488, 300, "Chain Map", _items(data, ("chain_notes", "main_read", "add_on_legs", "parlay_notes"), ["No verified chain notes attached.", "No compatible add-on selections attached.", "Use as watchlist until source match is verified."], lang), blue)
    box(42, 668, 488, 318, "Live Watch", _items(data, ("live_betting_notes", "flash_market_notes", "in_game_notes"), ["No verified in-game trigger attached.", "Refresh source data before use.", "Use only after event and market match."], lang), GOLD)
    prop_fallback = ["Prop ideas are menu-only until live odds and context are verified.", "No advanced prop recommendation without source match.", "Use Page 1 straight-bet anchor only."]
    prop_rows = _items(data, ("prop_market_notes", "advanced_market_notes", "player_prop_notes"), prop_fallback, lang) if _ok(data) else [_tr(item, lang) for item in prop_fallback]
    box(552, 668, 488, 318, "Prop Board", prop_rows, blue)
    box(42, 1014, 488, 300, "Quality Gate", ["Source gate: " + status, "Value gate: requires positive EV and edge.", "Market gate: requires exact event, line, selection.", "Context gate: requires current news/status check."], red)
    menu = ["Soccer: cards, corners, throw-ins, free kicks, next score, qualifying.", "Baseball: pitcher Ks, first five, team totals, player bases.", "Basketball/football/hockey: player props, team totals, line movement."]
    box(552, 1014, 488, 300, "All-Sport Menu", [_tr(item, lang) for item in menu], blue)
    draw.rounded_rectangle((42, 1340, 1042, 1518), radius=16, fill=black, outline=status_color, width=4)
    verdict = _tr("ADVANCED MARKETS READY FOR REVIEW" if _ok(data) else "ADVANCED MARKETS NEED VERIFICATION", lang)
    draw.text((68, 1364), verdict, font=module._fit(verdict, 914, 44, 16, True), fill=status_color)
    module._txt_auto(draw, 68, 1430, _tr("This page never creates a source claim from missing data and is safe for review.", lang), 914, 58, 23, 8, cream, False, 2)
    draw.rectangle((20, 1542, 1060, 1581), fill=black)
    module._txt_auto(draw, 42, 1550, getattr(module, "SAFETY_FOOTER", "Informational only."), 890, 20, 15, 8, cream, False, 1)
    return img.convert("RGB")


def install(module: Any | None = None) -> Any:
    if module is None:
        try:
            import autonomous_betting_agent.magazine_book_export as module
        except Exception:
            return None
    if getattr(module, "_ABA_DIRECT_SECOND_PAGE_PATCH", "") == PATCH_VERSION:
        return module
    original_fmt = getattr(module, "_fmt", None)
    if callable(original_fmt) and not getattr(original_fmt, "_ABA_DECIMAL_ODDS_DIRECT", False):
        def fmt_decimal_first(value: Any, kind: str = "") -> str:
            if kind == "odds":
                decimal = _decimal_text(value)
                if decimal:
                    return decimal
            return original_fmt(value, kind)
        fmt_decimal_first._ABA_DECIMAL_ODDS_DIRECT = True  # type: ignore[attr-defined]
        module._fmt = fmt_decimal_first
    original_cells = getattr(module, "magazine_metric_cells", None)
    if callable(original_cells) and not getattr(original_cells, "_ABA_GOLD_WATCHLIST_DIRECT", False):
        def metric_cells(odds: str, conf: str, edge: str, ev: str, units: str, risk: str):
            fixed = []
            for label, value, color, x, width in list(original_cells(odds, conf, edge, ev, units, risk)):
                if str(label).upper() == "RISK" and any(token in str(risk).lower() for token in ("fallback", "verify", "watch", "volume")):
                    color = GOLD
                fixed.append((label, value, color, x, width))
            return fixed
        metric_cells._ABA_GOLD_WATCHLIST_DIRECT = True  # type: ignore[attr-defined]
        module.magazine_metric_cells = metric_cells
    original_page_png = getattr(module, "render_full_pick_magazine_page_png", None)
    if callable(original_page_png) and not getattr(original_page_png, "_ABA_TWO_PAGE_DIRECT", False):
        def two_page_png(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
            page_total = max(2, int(total_pages or 1) * 2)
            first = max(1, int(page_number or 1) * 2 - 1)
            page_one = module.render_full_pick_magazine_page(pick, background_image, report_name, first, page_total, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
            page_two = _draw_second_page(module, pick, background_image, report_name, first + 1, page_total, language)
            from PIL import Image
            book = Image.new("RGB", (page_one.width, page_one.height * 2), getattr(module, "PAPER", (244, 235, 211)))
            book.paste(page_one.convert("RGB"), (0, 0))
            book.paste(page_two.convert("RGB"), (0, page_one.height))
            return _png(book)
        two_page_png._ABA_TWO_PAGE_DIRECT = True  # type: ignore[attr-defined]
        module.render_full_pick_magazine_page_png = two_page_png
    def render_pages(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> list[Any]:
        rows = list(picks) or [{"event": "No Picks", "prediction": "NO PICK"}]
        total = len(rows) * 2
        pages: list[Any] = []
        for index, row in enumerate(rows):
            pages.append(module.render_full_pick_magazine_page(row, background_image, report_name, index * 2 + 1, total, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))
            pages.append(_draw_second_page(module, row, background_image, report_name, index * 2 + 2, total, language))
        return pages
    module.render_full_magazine_book_pages = render_pages
    module._ABA_DIRECT_SECOND_PAGE_PATCH = PATCH_VERSION
    if "direct_two_page" not in str(getattr(module, "MAGAZINE_STYLE_VERSION", "")):
        module.MAGAZINE_STYLE_VERSION = f"{getattr(module, 'MAGAZINE_STYLE_VERSION', 'magazine')}_direct_two_page"
    return module


install()
