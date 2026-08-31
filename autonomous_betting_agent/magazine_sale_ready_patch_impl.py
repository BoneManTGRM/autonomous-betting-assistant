from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from autonomous_betting_agent import magazine_api_sources as api_sources
from autonomous_betting_agent.multi_leg_report import format_items as multi_leg_items

_APPLIED_FLAG = "_ABA_SALE_READY_DIRECT_MULTI_LEG_APPLIED"
_RENDER_FLAG = "_ABA_SALE_READY_DIRECT_MULTI_LEG_V3"
_VERSION_SUFFIX = "_sale_ready_direct_multileg_v3"

COUNTRY_ES = {
    "france": "Francia",
    "iraq": "Irak",
    "iran": "Irán",
    "haiti": "Haití",
    "mexico": "México",
    "united states": "Estados Unidos",
    "united states of america": "Estados Unidos",
    "usa": "Estados Unidos",
    "germany": "Alemania",
    "spain": "España",
    "england": "Inglaterra",
    "brazil": "Brasil",
    "argentina": "Argentina",
    "canada": "Canadá",
    "new zealand": "Nueva Zelanda",
    "south korea": "Corea del Sur",
}

TEXT_ES = {
    "No recent matching news returned.": "Sin noticias recientes relacionadas.",
    "No lineup/injury headline returned.": "Sin titular de lesiones/alineación.",
    "No SDIO event ID.": "Sin ID de evento SDIO.",
    "API-FB: no fixture match.": "API-FB: sin coincidencia de partido.",
    "Price check required before entry.": "Revisar cuota antes de entrar.",
    "Negative edge at current price.": "Ventaja negativa con la cuota actual.",
    "Recheck odds and key news.": "Revisar cuotas y noticias clave.",
    "WATCHLIST": "LISTA DE SEGUIMIENTO",
    "RESEARCH ONLY": "SOLO INVESTIGACIÓN",
    "NO PLAY": "NO JUGAR",
    "PLAY": "JUGAR",
}


def _row(value: Any) -> Mapping[str, Any]:
    return api_sources._row(value)


def _bad(value: Any) -> bool:
    return value is None or str(value).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


def _split(value: Any) -> list[str]:
    if _bad(value):
        return []
    return [p.strip(" -•") for p in str(value).replace("•", "\n").replace(";", "\n").replace("|", "\n").splitlines() if p.strip(" -•")]


def _get(row: Any, *keys: str, default: str = "") -> str:
    data = _row(row)
    for key in keys:
        value = data.get(key)
        if not _bad(value):
            return str(value).strip()
    return default


def _lang(row: Any = None, explicit: str | None = None) -> str:
    raw = explicit or _get(row, "report_language", "language", "lang", default="")
    text = str(raw or "").lower()
    return "es" if text.startswith("es") or "español" in text or "espanol" in text else "en"


def translate_country_name(value: Any, lang: str = "es") -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return COUNTRY_ES.get(text.casefold(), text) if lang == "es" else text


def translate_team_label(value: Any, lang: str = "es") -> str:
    return translate_country_name(value, lang)


def translate_country_terms_in_text(value: Any, lang: str = "es") -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if lang != "es" or not text:
        return text
    for old, new in sorted(COUNTRY_ES.items(), key=lambda item: len(item[0]), reverse=True):
        text = re.sub(r"(?<![\w])" + re.escape(old) + r"(?![\w])", new, text, flags=re.I)
    return text


def translate_event_name(value: Any, lang: str = "es") -> str:
    return translate_country_terms_in_text(value, lang)


def _es(value: Any, lang: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if lang != "es" or not text:
        return text
    for old, new in TEXT_ES.items():
        text = text.replace(old, new)
    return translate_country_terms_in_text(text, lang)


def _num(row: Any, *keys: str) -> float | None:
    for key in keys:
        value = _row(row).get(key)
        if _bad(value):
            continue
        try:
            raw = str(value).strip().replace("%", "").replace(",", "")
            number = float(raw)
            return number / 100 if "%" in str(value) and abs(number) > 1 else number
        except Exception:
            continue
    return None


def _fallback_odds(row: Any) -> bool:
    source = _get(row, "odds_source", "data_source", default="").lower()
    status = _get(row, "odds_status", "odds_api_status", default="").lower()
    live_tokens = {"live", "live_api", "live_match", "odds_api_live_match", "live_source"}
    if source in {"live_api", "odds api", "the odds api", "live_source"} or status in live_tokens:
        return False
    return any(token in source or token in status for token in ("uploaded", "fallback", "cached", "missing"))


def _edge_state(row: Any) -> tuple[float | None, float | None, bool, bool]:
    edge = _num(row, "model_market_edge", "edge")
    ev = _num(row, "expected_value_per_unit", "profit_expected_value", "expected_value", "ev")
    return edge, ev, (edge is not None and edge < 0) or (ev is not None and ev < 0), edge is None or ev is None


def sale_ready_recommendation(row: Any) -> tuple[str, str, bool]:
    demo_text = " ".join(
        _get(row, key, default="").lower()
        for key in ("report_title", "report_data_scope", "report_truth_warning", "league")
    )
    if bool(_row(row).get("demonstration_mode")) or any(token in demo_text for token in ("demonstration", "demo only", "validation fixture")):
        return "DEMONSTRATION ONLY", "Not current betting advice.", False
    if _fallback_odds(row):
        return "WATCHLIST", "Fallback/watchlist only.", False
    _edge, _ev, negative, missing = _edge_state(row)
    if negative:
        return "WATCHLIST", "", False
    if missing:
        return "RESEARCH ONLY", "", False
    return "PLAY", "", True


def _dedupe(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = re.sub(r"\s+", " ", str(item or "").strip())
        key = text.lower().rstrip(".")
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def sale_ready_team_items(row: Any, side: str = "") -> list[str]:
    lang = _lang(row)
    raw = [str(item or "") for item in api_sources.team_items(row, side)] or ["No SDIO event ID.", "API-FB: no fixture match.", "No recent matching news returned."]
    return [_es(item, lang) for item in _dedupe(raw)[:3]]


def sale_ready_injury_items(row: Any, prefix: str = "") -> list[str]:
    lang = _lang(row)
    raw = [str(item or "") for item in api_sources.injury_items(row, prefix)] or ["No lineup/injury headline returned."]
    return [_es(item, lang) for item in _dedupe(raw)[:2]]


def sale_ready_matchup_items(row: Any) -> list[str]:
    lang = _lang(row)
    raw = [str(item or "") for item in api_sources.matchup_items(row)]
    return [_es(item, lang) for item in _dedupe(raw)[:3]]


def sale_ready_risk_items(row: Any) -> list[str]:
    if _fallback_odds(row):
        return ["Fallback/watchlist only.", "Confirm current price before entry.", "Watchlist only: current price and live context need verification."]
    _edge, _ev, negative, missing = _edge_state(row)
    if negative:
        return ["Negative edge at current price.", "Use watchlist until price improves.", "Recheck odds and key news."]
    if missing:
        return ["Research only: edge incomplete.", "Confirm price before entry.", "Wait for verified context."]
    return ["Risk status: VOLUME OK.", "Recheck odds before entry.", "Avoid if key news changes."]


def sale_ready_chain_items(row: Any) -> list[str]:
    lang = _lang(row)
    data = _row(row)
    explicit: list[str] = []
    for key in ("combo_magazine_items", "parlay_magazine_items", "combo_recommendation", "parlay_recommendation", "combo_note", "parlay_note"):
        explicit.extend(_split(data.get(key)))
    if explicit:
        return [_es(item, lang) for item in _dedupe(explicit)[:3]]
    if _fallback_odds(row):
        return [_es(item, lang) for item in ["Straight watchlist only.", "Do not parlay fallback rows.", "Wait for verified odds and compatible legs."]]
    return [_es(item, lang) for item in multi_leg_items([data], lang, 3)[:3]]


def _items_from_context(row: Any, keys: Iterable[str], fallback: list[str], limit: int, lang: str = "en") -> list[str]:
    key_tuple = tuple(keys)
    explicit: list[str] = []
    data = _row(row)
    for key in key_tuple:
        explicit.extend(_split(data.get(key)))
    if explicit:
        return [_es(item, lang) for item in explicit[:limit]]
    if any(key in key_tuple for key in ("risk", "risk_level", "risk_label", "profit_guard_status", "risk_note", "risk_notes", "why_lose", "hidden_risk")):
        items = sale_ready_risk_items(row)
    elif any(key in key_tuple for key in ("chain_note", "chain_notes", "parlay_note", "parlay_notes", "combo_note", "combo_magazine_items", "parlay_magazine_items", "main_read", "add_on_legs")):
        items = sale_ready_chain_items(row)
    elif "matchup_note" in key_tuple or "sports_context_summary" in key_tuple or "weather_summary" in key_tuple:
        items = sale_ready_matchup_items(row)
    elif "injury_report" in key_tuple or "lineup_status" in key_tuple or "key_players" in key_tuple:
        items = sale_ready_injury_items(row, "away")
    else:
        items = sale_ready_team_items(row)
    return [_es(item, lang) for item in items[:limit]]


def _patch_translation_layer(module: Any) -> None:
    original_team_label = getattr(module, "_team_label", None)
    original_tr = getattr(module, "_tr", None)

    def patched_team_label(team: str, lang: str) -> str:
        return translate_team_label(team, lang) if lang == "es" else (original_team_label(team, lang) if callable(original_team_label) else str(team or "").strip())

    def patched_tr(value: Any, lang: str) -> str:
        text = original_tr(value, lang) if callable(original_tr) else str(value or "")
        return _es(translate_country_terms_in_text(text, lang), lang) if lang == "es" else text

    module._team_label = patched_team_label
    module._tr = patched_tr
    module.translate_country_name = translate_country_name
    module.translate_team_label = translate_team_label
    module.translate_event_name = translate_event_name
    module.translate_country_terms_in_text = translate_country_terms_in_text


def _arg(args: tuple[Any, ...], kwargs: Mapping[str, Any], index: int, name: str, default: Any) -> Any:
    return kwargs.get(name) if name in kwargs else (args[index] if len(args) > index else default)


def _paint_vs_badge(module: Any, img: Any) -> None:
    draw = module.ImageDraw.Draw(img, "RGBA")
    box = getattr(module, "VS_BADGE_BOX", (46, 456, 106, 516))
    clear = (box[0] - 10, box[1] - 10, box[2] + 12, box[3] + 10)
    draw.rectangle(clear, fill=module.PAPER)
    draw.rounded_rectangle(box, radius=12, fill=module.BLACK, outline=module.CREAM, width=2)
    font = module._fit("VS", box[2] - box[0] - 12, 34, 14, True)
    tbox = draw.textbbox((0, 0), "VS", font=font)
    x = box[0] + ((box[2] - box[0]) - (tbox[2] - tbox[0])) / 2
    y = box[1] + ((box[3] - box[1]) - (tbox[3] - tbox[1])) / 2 - 2
    draw.text((x, y), "VS", font=font, fill=module.CREAM)


def _paint_footer(module: Any, img: Any, lang: str) -> None:
    draw = module.ImageDraw.Draw(img, "RGBA")
    y0, y1 = 1542, 1581
    draw.rectangle((20, y0, 1060, y1), fill=module.BLACK)
    footer = module._tr(module.SAFETY_FOOTER, lang)
    font = module._fit(footer, module.PAGE_WIDTH - 90, 16, 10, False)
    draw.text((42, y0 + 10), module._ellipsize_to_width(draw, footer, font, module.PAGE_WIDTH - 90), font=font, fill=module.CREAM)


def _paint_final(module: Any, img: Any, row: Any, lang: str) -> None:
    draw = module.ImageDraw.Draw(img, "RGBA")
    action, _explanation, playable = sale_ready_recommendation(row)
    pick_text = module._tr(module._clean(module._pick(row), True), lang).upper()
    fy, fb = 1374, 1532
    accent = module.GREEN if playable else (239, 182, 58)
    side = module.GREEN if playable else module.BLUE
    outline = module.GREEN if playable else module.RED
    draw.rounded_rectangle((20, fy, 1060, fb), radius=14, fill=module.BLACK, outline=outline, width=3)
    draw.rectangle((20, fy, 250, fb), fill=side)
    draw.text((40, fy + 30), module._tr("FINAL", lang), font=module._font(30, True), fill=module.CREAM)
    rec = module._tr("RECOMMENDATION", lang)
    draw.text((40, fy + 76), rec, font=module._fit(rec, 190, 24, 12, True), fill=module.CREAM)
    action_label = _es(module._tr(action, lang).upper(), lang)
    module._txt_auto(draw, 284, fy + 24, action_label, 720, 60, 46, 20, accent, True, 1)
    module._txt_auto(draw, 284, fy + 98, pick_text, 720, 34, 38, 10, module.CREAM, True, 1)


def _patch_visuals(module: Any) -> None:
    current = getattr(module, "render_full_pick_magazine_page", None)
    if getattr(current, _RENDER_FLAG, False):
        return
    original = current

    def patched_render(pick: Any, *args: Any, **kwargs: Any):
        img = original(pick, *args, **kwargs)
        explicit_lang = kwargs.get("language") if "language" in kwargs else _arg(args, kwargs, 10, "language", None)
        lang = module._lang(pick, explicit_lang)
        draw = module.ImageDraw.Draw(img, "RGBA")
        _paint_vs_badge(module, img)
        draw.rectangle((724, 1234, 1050, 1348), fill=module.CREAM)
        y = 1244
        for item in sale_ready_chain_items(pick)[:3]:
            draw.ellipse((736, y + 5, 748, y + 17), fill=module.BLUE)
            module._txt_auto(draw, 756, y, _es(module._tr(item, lang), lang), 280, 30, 15, 11, module.TEXT, False, 2)
            y += 30
        _paint_final(module, img, pick, lang)
        _paint_footer(module, img, lang)
        return img

    def patched_png(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
        return module._png(module.render_full_pick_magazine_page(pick, background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))

    setattr(patched_render, _RENDER_FLAG, True)
    setattr(patched_png, _RENDER_FLAG, True)
    module.render_full_pick_magazine_page = patched_render
    module.render_full_pick_magazine_page_png = patched_png


def apply_magazine_sale_ready_patch(module: Any) -> Any:
    api_sources.apply_magazine_api_patch(module)
    _patch_translation_layer(module)
    module.team_items = sale_ready_team_items
    module.injury_items = sale_ready_injury_items
    module.matchup_items = sale_ready_matchup_items
    module.risk_items = sale_ready_risk_items
    module.chain_items = sale_ready_chain_items
    module._team_items = sale_ready_team_items
    module._injury_items = sale_ready_injury_items
    module._matchup_items = sale_ready_matchup_items
    module._risk_items = sale_ready_risk_items
    module._chain_items = sale_ready_chain_items
    module._items = _items_from_context
    module.sale_ready_recommendation = sale_ready_recommendation
    _patch_visuals(module)
    base = re.sub(r"_sale_ready_[a-z_]+_v\d+$", "", str(getattr(module, "MAGAZINE_STYLE_VERSION", "")))
    module.MAGAZINE_STYLE_VERSION = f"{base}{_VERSION_SUFFIX}"
    setattr(module, _APPLIED_FLAG, True)
    return module
