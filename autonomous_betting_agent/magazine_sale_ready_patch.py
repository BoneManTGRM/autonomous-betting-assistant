from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from autonomous_betting_agent import magazine_api_sources as api_sources

_APPLIED_FLAG = "_ABA_SALE_READY_MAGAZINE_PATCHED"
_RENDER_FLAG = "_ABA_SALE_READY_RENDER_WRAPPED_V4"
_TRANSLATION_FLAG = "_ABA_SPANISH_COUNTRY_TRANSLATION_PATCHED"
_VERSION_SUFFIX = "_sale_ready_risk_chain_v4"

PROTECTED_BRANDS = (
    "The Odds API",
    "Odds API",
    "SportsDataIO",
    "WeatherAPI",
    "API-Football",
    "NewsAPI",
    "Perplexity",
    "Playdoit",
    "Caliente",
    "Codere",
)

COUNTRY_ES = {
    "albania": "Albania", "algeria": "Argelia", "angola": "Angola", "argentina": "Argentina",
    "australia": "Australia", "austria": "Austria", "belgium": "Bélgica", "bolivia": "Bolivia",
    "brazil": "Brasil", "bulgaria": "Bulgaria", "cameroon": "Camerún", "canada": "Canadá",
    "chile": "Chile", "china": "China", "colombia": "Colombia", "costa rica": "Costa Rica",
    "croatia": "Croacia", "curacao": "Curazao", "curaçao": "Curazao",
    "czech republic": "República Checa", "czechia": "Chequia", "denmark": "Dinamarca",
    "dominican republic": "República Dominicana", "ecuador": "Ecuador", "egypt": "Egipto",
    "england": "Inglaterra", "finland": "Finlandia", "france": "Francia", "germany": "Alemania",
    "ghana": "Ghana", "greece": "Grecia", "haiti": "Haití", "holland": "Países Bajos",
    "honduras": "Honduras", "hungary": "Hungría", "iceland": "Islandia", "iran": "Irán",
    "iraq": "Irak", "ireland": "Irlanda", "israel": "Israel", "italy": "Italia",
    "ivory coast": "Costa de Marfil", "cote d'ivoire": "Costa de Marfil", "côte d'ivoire": "Costa de Marfil",
    "jamaica": "Jamaica", "japan": "Japón", "jordan": "Jordania", "korea republic": "Corea del Sur",
    "mexico": "México", "morocco": "Marruecos", "netherlands": "Países Bajos", "new zealand": "Nueva Zelanda",
    "nigeria": "Nigeria", "northern ireland": "Irlanda del Norte", "norway": "Noruega", "panama": "Panamá",
    "paraguay": "Paraguay", "peru": "Perú", "poland": "Polonia", "portugal": "Portugal",
    "qatar": "Qatar", "romania": "Rumanía", "russia": "Rusia", "saudi arabia": "Arabia Saudita",
    "scotland": "Escocia", "senegal": "Senegal", "serbia": "Serbia", "slovakia": "Eslovaquia",
    "slovenia": "Eslovenia", "south africa": "Sudáfrica", "south korea": "Corea del Sur",
    "spain": "España", "sweden": "Suecia", "switzerland": "Suiza", "tunisia": "Túnez",
    "turkey": "Turquía", "uae": "Emiratos Árabes Unidos", "ukraine": "Ucrania",
    "united arab emirates": "Emiratos Árabes Unidos", "united states": "Estados Unidos",
    "united states of america": "Estados Unidos", "uruguay": "Uruguay", "usa": "Estados Unidos",
    "uzbekistan": "Uzbekistán", "wales": "Gales",
}

WEATHER_ES = (
    ("Moderate or heavy rain with thunder", "lluvia y tormenta"),
    ("moderate or heavy rain with thunder", "lluvia y tormenta"),
    ("Patchy rain nearby", "lluvia cercana"), ("patchy rain nearby", "lluvia cercana"),
    ("Partly cloudy", "parcialmente nublado"), ("partly cloudy", "parcialmente nublado"),
    ("Light rain", "lluvia ligera"), ("light rain", "lluvia ligera"),
    ("Overcast", "nublado"), ("overcast", "nublado"), ("Sunny", "soleado"),
    ("sunny", "soleado"), ("Clear", "despejado"), ("clear", "despejado"),
    ("Mist", "neblina"), ("mist", "neblina"), ("Weather:", "Clima:"),
    ("Location:", "Ubicación:"), ("weather checked", "clima revisado"),
    ("wind", "viento"), ("Pennsylvania", "Pensilvania"),
)

SPANISH_VISIBLE_TEXT = {
    "No recent matching Noticias returned.": "Sin noticias recientes relacionadas.",
    "No recent matching news returned.": "Sin noticias recientes relacionadas.",
    "No lineup/injury headline returned.": "Sin titular de lesiones/alineación.",
    "No SDIO event ID.": "Sin ID de evento SDIO.",
    "No SDIO event ID returned.": "Sin ID de evento SDIO.",
    "API-FB: no fixture match.": "API-FB: sin coincidencia de partido.",
    "API-FB lookup checked; no fixture match.": "API-FB: sin coincidencia de partido.",
    "ACTIVE": "ACTIVO", "ACTIVE:": "ACTIVO:", "ACTIVE APIS": "APIS ACTIVAS",
    "NO LIVE": "SIN EN VIVO", "NO LIVE:": "SIN EN VIVO:", "Odds": "Cuotas", "ODDS": "CUOTAS",
    "Price check required before entry.": "Revisar cuota antes de entrar.",
    "Negative edge at current price.": "Ventaja negativa con la cuota actual.",
    "Do not play unless price improves.": "No jugar salvo que la cuota mejore.",
    "Recheck odds and key news.": "Revisar cuotas y noticias clave.",
    "Do not chain negative-EV picks.": "No encadenar señales con VE negativo.",
    "Avoid parlays unless edge turns positive.": "Evitar parlays salvo que la ventaja sea positiva.",
    "Recheck price before including.": "Revisar la cuota antes de incluir.",
    "Do not play at the listed price. Recheck only if the line improves or new information changes the edge.": "Revisar si mejora la línea.",
    "WATCHLIST": "LISTA DE SEGUIMIENTO", "RESEARCH ONLY": "SOLO INVESTIGACIÓN",
}


def _row(value: Any) -> Mapping[str, Any]:
    return api_sources._row(value)


def _split(value: Any) -> list[str]:
    splitter = getattr(api_sources, "_split", None)
    if callable(splitter):
        try:
            return splitter(value)
        except Exception:
            pass
    if _bad(value):
        return []
    return [p.strip(" -•") for p in str(value).replace("•", "\n").replace(";", "\n").replace("|", "\n").splitlines() if p.strip(" -•")]


def _bad(value: Any) -> bool:
    return value is None or str(value).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


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


def _normalize_country_key(value: Any) -> str:
    text = str(value or "").replace("’", "'").replace("`", "'").strip()
    return re.sub(r"\s+", " ", text).casefold()


def translate_country_name(value: Any, lang: str = "es") -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if lang != "es" or not text:
        return text
    return COUNTRY_ES.get(_normalize_country_key(text), text)


def translate_team_label(value: Any, lang: str = "es") -> str:
    return translate_country_name(value, lang)


def _protect_brands(value: str) -> tuple[str, dict[str, str]]:
    protected: dict[str, str] = {}
    text = value.replace("The Cuotas API", "The Odds API").replace("Cuotas API", "Odds API")
    for brand in sorted(PROTECTED_BRANDS, key=len, reverse=True):
        pattern = re.compile(re.escape(brand), flags=re.I)

        def repl(match: re.Match[str]) -> str:
            token = f"__ABA_BRAND_{len(protected)}__"
            protected[token] = match.group(0)
            return token

        text = pattern.sub(repl, text)
    return text, protected


def _restore_brands(value: str, protected: dict[str, str]) -> str:
    text = value
    for token, brand in protected.items():
        text = text.replace(token, brand)
    return text


def translate_country_terms_in_text(value: Any, lang: str = "es") -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if lang != "es" or not text:
        return text
    text, protected = _protect_brands(text)
    aliases = sorted(COUNTRY_ES, key=len, reverse=True)
    pattern = re.compile(r"(?<![\w])(" + "|".join(re.escape(alias) for alias in aliases) + r")(?![\w])", flags=re.I)

    def repl(match: re.Match[str]) -> str:
        return COUNTRY_ES.get(_normalize_country_key(match.group(0)), match.group(0))

    text = pattern.sub(repl, text)
    return _restore_brands(text, protected)


def translate_event_name(value: Any, lang: str = "es") -> str:
    return translate_country_terms_in_text(value, lang)


def _es(text: Any, lang: str) -> str:
    value = re.sub(r"\s+", " ", str(text or "").strip())
    if lang != "es" or not value:
        return value
    if value in SPANISH_VISIBLE_TEXT:
        return SPANISH_VISIBLE_TEXT[value]
    value, protected = _protect_brands(value)
    value = re.sub(r"No recent matching\s+(?:Noticias|news)\s+returned\.", "Sin noticias recientes relacionadas.", value, flags=re.I)
    value = re.sub(r"No lineup/injury headline returned\.", "Sin titular de lesiones/alineación.", value, flags=re.I)
    value = re.sub(r"No SDIO event ID(?: returned)?\.", "Sin ID de evento SDIO.", value, flags=re.I)
    value = re.sub(r"API-FB(?: lookup checked;)? no fixture match\.", "API-FB: sin coincidencia de partido.", value, flags=re.I)
    value = re.sub(r"\bACTIVE\b", "ACTIVO", value)
    value = re.sub(r"\bNO LIVE\b", "SIN EN VIVO", value)
    for old, new in SPANISH_VISIBLE_TEXT.items():
        value = value.replace(old, new)
    for old, new in WEATHER_ES:
        value = value.replace(old, new)
    value = _restore_brands(value, protected)
    return translate_country_terms_in_text(value, lang)


def _num(row: Any, *keys: str) -> float | None:
    for key in keys:
        value = _row(row).get(key)
        if _bad(value):
            continue
        try:
            text = str(value).strip().replace("%", "").replace(",", "")
            num = float(text)
            if "%" in str(value) and abs(num) > 1:
                num /= 100
            return num
        except Exception:
            continue
    return None


def _edge_state(row: Any) -> tuple[float | None, float | None, bool, bool]:
    edge = _num(row, "model_market_edge", "edge")
    ev = _num(row, "expected_value_per_unit", "profit_expected_value", "expected_value", "ev")
    negative = (edge is not None and edge < 0) or (ev is not None and ev < 0)
    missing = edge is None or ev is None
    return edge, ev, negative, missing


def sale_ready_recommendation(row: Any) -> tuple[str, str, bool]:
    edge, ev, negative, missing = _edge_state(row)
    requested = _get(row, "final_decision", "agent_decision", "recommendation", "consumer_action", "recommended_action", default="").strip().upper()
    if negative:
        return "WATCHLIST", "Do not play at the listed price. Recheck only if the line improves or new information changes the edge.", False
    if missing:
        return "RESEARCH ONLY", "Critical price or edge context is missing. Confirm the line, injury/news context, and value before publishing.", False
    if requested and not any(word in requested for word in ("PLAY", "BET", "SMALL", "STANDARD")):
        return requested, _get(row, "final_explanation", "action_reason", "recommendation_reason", default="Use only after independent review."), False
    if edge is not None and ev is not None and (edge < 0.015 or ev < 0.02):
        return "PLAY SMALL", "Thin positive edge. Use only if the line remains playable and key news does not change.", True
    return "PLAY", "Positive edge confirmed at the listed price. Recheck odds and key news before entry.", True


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


def _short_location(location: str) -> str:
    return (
        re.sub(r"\s+", " ", str(location or "").strip(" ."))
        .replace("Pennsylvania, United States of America", "PA, USA")
        .replace("United States of America", "USA")
        .replace("United States", "USA")
    )


def _clean_provider_item(text: str) -> str:
    value = re.sub(r"\s+", " ", str(text or "").strip())
    low = value.lower()
    if not value:
        return ""
    if low.startswith("sdio checked") or low.startswith("sportsdataio configured"):
        return "No SDIO event ID."
    if low.startswith("api-fb lookup checked") or low.startswith("api-football checked") or low.startswith("api-fb lookup only"):
        return "API-FB: no fixture match."
    if low.startswith("news checked") or low.startswith("newsapi checked"):
        if "injury" in low or "lineup" in low:
            return "No lineup/injury headline returned."
        return "No recent matching news returned."
    return value.replace("Pennsylvania, United States of America", "PA, USA")


def _clean_matchup_item(text: str) -> list[str]:
    value = re.sub(r"\s+", " ", str(text or "").strip())
    low = value.lower()
    if not value:
        return []
    if low.startswith("api-fb lookup checked") or low.startswith("api-football checked") or low.startswith("api-fb lookup only"):
        return ["API-FB lookup checked; no fixture match."]
    if low.startswith("location:"):
        return ["Location: " + _short_location(value.split(":", 1)[1]) + "."]
    if low.startswith("weather:") or low.startswith("weatherapi:"):
        body = value.split(":", 1)[1].strip()
        location = ""
        loc_match = re.search(r"\bLocation:\s*(.+)$", body, flags=re.I)
        if loc_match:
            location = loc_match.group(1).strip(" .")
            body = body[: loc_match.start()].strip(" .")
        temp_match = re.search(r"(-?\d+(?:\.\d+)?)\s*°\s*([CF])\b", body, flags=re.I)
        wind_match = re.search(r"wind\s+\d+(?:\.\d+)?\s*kph", body, flags=re.I)
        condition = ""
        for part in re.split(r"[.,;]", body):
            clean = part.strip()
            if clean and not re.search(r"°\s*[CF]\b", clean, re.I) and "wind" not in clean.lower():
                condition = clean[:1].lower() + clean[1:]
                break
        pieces = []
        if temp_match:
            pieces.append(f"{temp_match.group(1)}°{temp_match.group(2).upper()}")
        if condition:
            pieces.append(condition)
        if wind_match:
            pieces.append(wind_match.group(0).lower())
        out = ["Weather: " + ", ".join(pieces[:3]) + "."] if pieces else [value]
        if location:
            out.append("Location: " + _short_location(location) + ".")
        return out
    return [_clean_provider_item(value)]


def sale_ready_team_items(row: Any, side: str = "") -> list[str]:
    lang = _lang(row)
    raw = [_clean_provider_item(item) for item in api_sources.team_items(row, side)]
    if not raw:
        raw = ["No SDIO event ID.", "API-FB: no fixture match.", "No recent matching news returned."]
    return [_es(item, lang) for item in _dedupe(raw)[:3]]


def sale_ready_injury_items(row: Any, prefix: str = "") -> list[str]:
    lang = _lang(row)
    raw = [_clean_provider_item(item) for item in api_sources.injury_items(row, prefix)] or ["No lineup/injury headline returned."]
    return [_es(item, lang) for item in _dedupe(raw)[:2]]


def sale_ready_matchup_items(row: Any) -> list[str]:
    lang = _lang(row)
    cleaned: list[str] = []
    for item in api_sources.matchup_items(row):
        cleaned.extend(_clean_matchup_item(item))
    return [_es(item, lang) for item in _dedupe(cleaned)[:3]]


def sale_ready_risk_items(row: Any) -> list[str]:
    _edge, _ev, negative, missing = _edge_state(row)
    if negative:
        return ["Negative edge at current price.", "Do not play unless price improves.", "Recheck odds and key news."]
    if missing:
        return ["Research only: edge incomplete.", "Confirm price before entry.", "Wait for verified context."]
    return ["Risk status: VOLUME OK.", "Recheck odds before entry.", "Avoid if key news changes."]


def sale_ready_chain_items(row: Any) -> list[str]:
    _edge, _ev, negative, missing = _edge_state(row)
    if negative:
        return ["Do not chain negative-EV picks.", "Avoid parlays unless edge turns positive.", "Recheck price before including."]
    if missing:
        return ["Do not combine unverified picks.", "Wait for complete edge data.", "Straight-only review."]
    return ["Straight only: research.", "Do not combine without verification.", "Wait for better context or price."]


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
    elif any(key in key_tuple for key in ("chain_note", "chain_notes", "parlay_note", "parlay_notes", "combo_note", "main_read", "add_on_legs")):
        items = sale_ready_chain_items(row)
    elif "matchup_note" in key_tuple or "sports_context_summary" in key_tuple or "weather_summary" in key_tuple:
        items = sale_ready_matchup_items(row)
    elif "injury_report" in key_tuple or "lineup_status" in key_tuple or "key_players" in key_tuple:
        items = sale_ready_injury_items(row, "away")
    else:
        items = sale_ready_team_items(row)
    return [_es(item, lang) for item in items[:limit]]


def _patch_translation_layer(module: Any) -> None:
    if getattr(module, _TRANSLATION_FLAG, False):
        try:
            if getattr(module, "_team_label")("Haiti", "es") == "Haití":
                return
        except Exception:
            pass
    try:
        module.COUNTRY_ES.update(COUNTRY_ES)
    except Exception:
        module.COUNTRY_ES = dict(COUNTRY_ES)
    original_team_label = getattr(module, "_team_label", None)
    original_tr = getattr(module, "_tr", None)

    def patched_team_label(team: str, lang: str) -> str:
        if lang == "es":
            return translate_team_label(team, lang)
        return original_team_label(team, lang) if callable(original_team_label) else str(team or "").strip()

    def patched_tr(value: Any, lang: str) -> str:
        text = original_tr(value, lang) if callable(original_tr) else str(value or "")
        if lang != "es":
            return text
        return _es(translate_country_terms_in_text(text, lang), lang)

    module._team_label = patched_team_label
    module._tr = patched_tr
    module.translate_country_name = translate_country_name
    module.translate_team_label = translate_team_label
    module.translate_event_name = translate_event_name
    module.translate_country_terms_in_text = translate_country_terms_in_text
    setattr(module, _TRANSLATION_FLAG, True)


def _clean_report_brand(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    text = re.split(r"\s+[—-]\s+", text, maxsplit=1)[0].strip()
    if text.lower() in {"full pick magazine", "magazine report", "report"}:
        return ""
    return text


def _arg(args: tuple[Any, ...], kwargs: Mapping[str, Any], index: int, name: str, default: Any) -> Any:
    return kwargs.get(name) if name in kwargs else (args[index] if len(args) > index else default)


def _patch_visuals(module: Any) -> None:
    current_render = getattr(module, "render_full_pick_magazine_page", None)
    if getattr(current_render, _RENDER_FLAG, False):
        return
    original_render = current_render

    def repaint_masthead(draw: Any, row: Any, lang: str, report_name: Any, page_number: Any, total_pages: Any) -> None:
        brand = _get(row, "report_brand_name", "brand_name", "tipster_name", default="") or _clean_report_brand(report_name) or "ABA Signal Pro"
        title = _get(row, "report_title", default="") or module._tr("DAILY SPORTS ANALYSIS", lang)
        title = module._tr(title, lang)
        try:
            page_no = int(page_number)
        except Exception:
            page_no = 1
        try:
            total = int(total_pages)
        except Exception:
            total = 1
        draw.rectangle((18, 18, module.PAGE_WIDTH - 18, 82), fill=module.BLACK)
        draw.rectangle((28, 24, 308, 74), fill=module.RED)
        brand_upper = str(brand).upper()
        title_upper = str(title).upper()
        draw.text((43, 29), brand_upper, font=module._fit(brand_upper, 250, 38, 15, True), fill="white")
        draw.text((330, 28), title_upper, font=module._fit(title_upper, 470, 38, 16, True), fill="white")
        draw.rounded_rectangle((840, 24, 1050, 74), radius=5, fill=module.CREAM, outline=module.BLACK)
        page_text = module._tr(f"PAGE {page_no} OF {total}", lang)
        draw.text((862, 32), page_text, font=module._fit(page_text, 174, 28, 16, True), fill=module.BLACK)

    def repaint_vs_badge(draw: Any) -> None:
        box = module.VS_BADGE_BOX
        draw.rectangle((box[0] - 6, box[1] - 6, box[2] + 8, box[3] + 6), fill=module.PAPER)
        draw.rounded_rectangle(box, radius=12, fill=module.BLACK, outline=module.CREAM, width=2)
        font = module._fit("VS", box[2] - box[0] - 12, 34, 14, True)
        tbox = draw.textbbox((0, 0), "VS", font=font)
        x = box[0] + ((box[2] - box[0]) - (tbox[2] - tbox[0])) / 2
        y = box[1] + ((box[3] - box[1]) - (tbox[3] - tbox[1])) / 2 - 2
        draw.text((x, y), "VS", font=font, fill=module.CREAM)

    def draw_guidance_body(draw: Any, box: tuple[int, int, int, int], items: list[str], color: Any, lang: str) -> None:
        draw.rectangle(box, fill=module.CREAM)
        y = box[1] + 10
        for item in items[:3]:
            draw.ellipse((box[0] + 12, y + 5, box[0] + 24, y + 17), fill=color)
            module._txt_auto(draw, box[0] + 32, y, _es(module._tr(item, lang), lang), box[2] - box[0] - 46, 30, 15, 11, module.TEXT, False, 2)
            y += 30

    def repaint_evidence_body(draw: Any, row: Any, lang: str) -> None:
        left_x, left_w = 20, 320
        draw.rectangle((left_x + 8, 970, left_x + left_w - 8, 1120), fill=module.CREAM)
        entries = [
            ("FILA DE MOMIO", _es(_get(row, "odds_source", "data_source", default="fila cargada/en caché"), lang)),
            ("CASA", _es(_get(row, "bookmaker", "sportsbook", default="promedio consenso"), lang)),
            ("ACTIVO", "SDIO · Clima · API-FB · Noticias"),
            ("SIN EN VIVO", "Cuotas"),
        ]
        y = 974
        for label, value in entries:
            draw.text((left_x + 24, y), f"{label}:", font=module._fit(f"{label}:", 92, 16, 7, True), fill=module.BLACK)
            module._txt_auto(draw, left_x + 122, y, value, left_w - 138, 22, 16, 7, module.BLACK, True, 1)
            y += 29
        draw.line((left_x + 12, 1088, left_x + left_w - 12, 1088), fill=module.BLACK + (135,), width=1)
        module._txt_auto(draw, left_x + 22, 1094, _es("Price check required before entry.", lang), left_w - 44, 22, 14, 9, module.BLACK, True, 1)

    def repaint_matchup_body(draw: Any, row: Any, lang: str) -> None:
        if lang != "es":
            return
        x, y, width, height = 354, 1178, 344, 175
        module._section(draw, x, y, width, height, "MATCHUP NOTES", module.BLUE, lang)
        draw.rectangle((x + 10, y + 56, x + width - 10, y + height - 8), fill=module.CREAM)
        font = module._font(11, False)
        line_h = module._line_height(font)
        cursor = y + 70
        bottom = y + height - 12
        for item in sale_ready_matchup_items(row)[:3]:
            item = re.sub(r"\bUbicación:\s*", "Ubic.: ", item)
            lines = module._wrap_text_to_box(draw, item, font, width - 60, 2)[:2]
            needed = max(1, len(lines)) * line_h + 6
            if cursor + needed > bottom:
                break
            draw.ellipse((x + 24, cursor + 7, x + 36, cursor + 19), fill=module.BLUE)
            for line in lines:
                draw.text((x + 48, cursor), module._ellipsize_to_width(draw, line, font, width - 62), font=font, fill=module.TEXT)
                cursor += line_h
            cursor += 6

    def repaint_final(img: Any, row: Any, lang: str) -> None:
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
        module._txt_auto(draw, 284, fy + 24, action_label, 500, 60, 52, 20, accent, True, 1)
        module._txt_auto(draw, 284, fy + 98, pick_text, 500, 34, 38, 10, module.CREAM, True, 1)

    def patched_render(pick: Any, *args: Any, **kwargs: Any):
        img = original_render(pick, *args, **kwargs)
        explicit_lang = kwargs.get("language") if "language" in kwargs else _arg(args, kwargs, 10, "language", None)
        lang = module._lang(pick, explicit_lang)
        draw = module.ImageDraw.Draw(img, "RGBA")
        repaint_masthead(draw, pick, lang, _arg(args, kwargs, 1, "report_name", None), _arg(args, kwargs, 2, "page_number", 1), _arg(args, kwargs, 3, "total_pages", 1))
        repaint_vs_badge(draw)
        repaint_evidence_body(draw, pick, lang)
        repaint_matchup_body(draw, pick, lang)
        draw_guidance_body(draw, (34, 1234, 326, 1348), sale_ready_risk_items(pick), module.RED, lang)
        draw_guidance_body(draw, (724, 1234, 1050, 1348), sale_ready_chain_items(pick), module.BLUE, lang)
        repaint_final(img, pick, lang)
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
    base_version = re.sub(r"_sale_ready_risk_chain_v\d+$", "", str(getattr(module, "MAGAZINE_STYLE_VERSION", "")))
    module.MAGAZINE_STYLE_VERSION = f"{base_version}{_VERSION_SUFFIX}"
    setattr(module, _APPLIED_FLAG, True)
    return module
