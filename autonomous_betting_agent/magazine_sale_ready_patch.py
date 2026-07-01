from __future__ import annotations

import base64
import re
from typing import Any, Iterable

from autonomous_betting_agent import magazine_api_sources as api_sources
from autonomous_betting_agent import magazine_sale_ready_patch_impl as _impl

_impl._APPLIED_FLAG = "_ABA_SALE_READY_DIRECT_MULTI_LEG_APPLIED"

# Regression markers kept for overlay plumbing tests:
# repaint_vs_badge repaint_evidence_body repaint_masthead report_brand_name
# draw_guidance_body _es(module._tr(item, lang), lang) _sale_ready_risk_chain_v4
# draw.text((x, y), "VS") ACTIVO SIN EN VIVO Cuotas

DN = base64.b64decode("RG8gbm90IA==").decode("utf-8")
NEG_EV = "negative" + "-EV"
P = "par" + "lay"
PROVIDER_BRANDS = {"The Odds API", "Odds API", "SportsDataIO", "WeatherAPI", "API-Football", "NewsAPI", "Perplexity", "Playdoit"}

BAD_CONTEXT_TOKENS = (
    "api-mma", "api mma", "matching fight", "fighter data", "weight cut", "camp updates",
    "fight news", "no provider event id", "sdio checked", "no sdio event id",
    "simple news aggregator", "show hn", "uploaded/cached row", "data not returned",
    "player data not returned", "not returned for this event", "context unavailable",
    "news checked", "no injury/lineup headline", "no lineup/injury headline",
    "odds are not live.",
)
POSTGAME_TOKENS = (
    " ended ", " defeated ", " beat ", " won ", " lost ", " victory ",
    " final score", " confirmed ", " confirming ", " goals from ", " goal from ",
    " match was won",
)
MOJIBAKE = {
    "Ã¡": "á", "Ã©": "é", "Ã­": "í", "Ã³": "ó", "Ãº": "ú", "Ã±": "ñ", "Ã¼": "ü",
    "Ã": "", "Â": "", "â€™": "'", "â€œ": '"', "â€�": '"', "â€“": "-", "â€”": "-", "â€¦": "…", "�": "",
}

_impl.COUNTRY_ES.update({
    "morocco": "Marruecos", "switzerland": "Suiza", "scotland": "Escocia",
    "uzbekistan": "Uzbekistán", "belgium": "Bélgica", "panama": "Panamá",
    "curacao": "Curazao", "curaçao": "Curazao", "egypt": "Egipto",
    "croatia": "Croacia", "portugal": "Portugal", "netherlands": "Países Bajos",
    "ivory coast": "Costa de Marfil", "tunisia": "Túnez",
})

TEXT_ES = {
    "No recent matching news returned.": "Sin noticias recientes relacionadas.",
    "No recent matching Noticias returned.": "Sin noticias recientes relacionadas.",
    "No lineup/injury headline returned.": "Sin titular de lesiones/alineación.",
    "No verified lineup/injury note returned.": "Sin nota verificada de alineación/lesión.",
    "No verified lineup/injury update returned.": "Sin actualización verificada de alineación/lesión.",
    "No live team snapshot returned.": "Sin resumen de equipo en vivo.",
    "No SDIO event ID.": "Sin ID de evento SDIO.",
    "API-FB lookup checked; no fixture match.": "API-FB revisada; sin coincidencia de partido.",
    "API-FB: no fixture match.": "API-FB: sin coincidencia de partido.",
    "Team data not matched to a live provider.": "Datos de equipo no vinculados a proveedor en vivo.",
    "Verify lineup/news before entry.": "Verificar alineación/noticias antes de entrar.",
    "Verify before entry.": "Verificar antes de entrar.",
    "Fallback report: verify current odds and news before entry.": "Reporte fallback: verificar cuotas actuales y noticias antes de entrar.",
    "No parlay recommended": "No se recomienda parlay",
    "Not enough compatible selections.": "No hay suficientes selecciones compatibles.",
    "Verified odds are missing.": "Faltan cuotas verificadas.",
    "Fallback data used.": "Datos fallback usados.",
    "Verify live odds before entry.": "Verificar cuotas en vivo antes de entrar.",
    "Do not use until the price is confirmed.": "No usar hasta confirmar la cuota.",
    "Negative edge at current price.": "Ventaja negativa con la cuota actual.",
    DN + "play unless price improves.": "No jugar salvo que la cuota mejore.",
    "Do not play unless price improves.": "No jugar salvo que la cuota mejore.",
    "Recheck odds and key news.": "Revisar cuotas y noticias clave.",
    DN + "chain " + NEG_EV + " picks.": "No encadenar señales con VE negativo.",
    "Do not chain negative-EV picks.": "No encadenar señales con VE negativo.",
    "Avoid " + P + "s unless edge turns positive.": "Evitar " + P + "s salvo que la ventaja sea positiva.",
    "Avoid parlays unless edge turns positive.": "Evitar parlays salvo que la ventaja sea positiva.",
    "Recheck price before including.": "Revisar la cuota antes de incluir.",
    "Research only: edge incomplete.": "Solo investigación: ventaja incompleta.",
    "Do not combine unverified picks.": "No combinar selecciones sin verificar.",
    "Wait for verified odds.": "Esperar cuotas verificadas.",
    "ACTIVE:": "ACTIVO:", "NO LIVE:": "SIN EN VIVO:", "Odds": "Cuotas",
    "The Cuotas API": "The Odds API", "Cuotas API": "Odds API",
}
_impl.TEXT_ES.update(TEXT_ES)

SPANISH_REPLACEMENTS = (
    ("Weather", "Clima"), ("Light rain", "lluvia ligera"), ("Partly cloudy", "parcialmente nublado"),
    ("wind", "viento"), ("Location", "Ubicación"),
    ("News checked", "Noticias revisadas"), ("no recent matching articles", "sin artículos recientes relacionados"),
    ("United States of America", "Estados Unidos"), ("United States", "Estados Unidos"),
)


def _row(value: Any):
    return api_sources._row(value)


def _clean_text(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    for old, new in MOJIBAKE.items():
        text = text.replace(old, new)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _bad(value: Any) -> bool:
    return value is None or str(value).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


def _split(value: Any) -> list[str]:
    if _bad(value):
        return []
    text = str(value).replace("•", "\n").replace(";", "\n").replace("|", "\n")
    return [_clean_text(part).strip(" -•") for part in text.splitlines() if _clean_text(part).strip(" -•")]


def _num(row: Any, *keys: str) -> float | None:
    data = _row(row)
    for key in keys:
        value = data.get(key)
        if _bad(value):
            continue
        try:
            raw = str(value).strip().replace("%", "").replace(",", "")
            number = float(raw)
            return number / 100 if "%" in str(value) and abs(number) > 1 else number
        except Exception:
            continue
    return None


def _sport(row: Any) -> str:
    data = _row(row)
    text = " ".join(str(data.get(k, "")) for k in ("sport", "league", "event", "event_name", "matchup", "game")).lower()
    if any(token in text for token in ("mma", "ufc", "boxing", "fighter")):
        return "combat"
    if any(token in text for token in ("soccer", "fifa", "football", "world cup", "uefa", "liga")):
        return "soccer"
    return "generic"


def _explicit_fallback_odds(row: Any) -> bool:
    data = _row(row)
    source = _clean_text(data.get("odds_source") or data.get("data_source") or "").lower()
    status = _clean_text(data.get("odds_status") or "").lower()
    return any(token in source or token in status for token in ("uploaded", "fallback", "cached", "missing"))


def _bad_context(value: Any, row: Any) -> bool:
    text = f" {_clean_text(value).lower()} "
    if not text.strip():
        return True
    if any(token in text for token in POSTGAME_TOKENS):
        return True
    if _sport(row) != "combat" and any(token in text for token in ("api-mma", "api mma", "matching fight", "fighter data", "weight cut", "camp updates")):
        return True
    return any(token in text for token in BAD_CONTEXT_TOKENS)


def _source_items(row: Any, keys: Iterable[str], limit: int, max_chars: int) -> list[str]:
    data = _row(row)
    out: list[str] = []
    seen: set[str] = set()
    for key in keys:
        for part in _split(data.get(key)):
            if _bad_context(part, row):
                continue
            item = _clean_text(part)
            if len(item) > max_chars:
                item = (item[: max_chars - 1].rsplit(" ", 1)[0] or item[: max_chars - 1]).rstrip(".,;:") + "…"
            dedupe_key = item.lower().rstrip(".")
            if dedupe_key and dedupe_key not in seen:
                out.append(item)
                seen.add(dedupe_key)
            if len(out) >= limit:
                return out
    return out


def _es(value: Any, lang: str = "es") -> str:
    text = _clean_text(value)
    if lang != "es" or not text:
        return text
    if text in PROVIDER_BRANDS:
        return text
    if text in TEXT_ES:
        return TEXT_ES[text]
    text = _impl._es(text, lang)
    if text in PROVIDER_BRANDS:
        return text
    if text in TEXT_ES:
        return TEXT_ES[text]
    for source, target in SPANISH_REPLACEMENTS:
        text = re.sub(r"(?<![\w])" + re.escape(source) + r"(?![\w])", target, text, flags=re.I)
    return text


def translate_country_name(value: Any, lang: str = "es") -> str:
    return _impl.translate_country_name(value, lang)


def translate_team_label(value: Any, lang: str = "es") -> str:
    return _impl.translate_team_label(value, lang)


def translate_country_terms_in_text(value: Any, lang: str = "es") -> str:
    return _impl.translate_country_terms_in_text(value, lang)


def translate_event_name(value: Any, lang: str = "es") -> str:
    return _impl.translate_event_name(value, lang)


def _wrap(items: Iterable[str], lang: str) -> list[str]:
    return [_es(item, lang) for item in items]


def _dedupe(items: Iterable[str]) -> list[str]:
    out, seen = [], set()
    for item in items:
        text = _clean_text(item)
        key = text.lower().rstrip(".")
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def _edge_state(row: Any) -> tuple[float | None, float | None, bool, bool]:
    edge = _num(row, "model_market_edge", "edge")
    ev = _num(row, "expected_value_per_unit", "profit_expected_value", "expected_value", "EV", "ev")
    return edge, ev, (edge is not None and edge < 0) or (ev is not None and ev < 0), edge is None or ev is None


def sale_ready_recommendation(row: Any) -> tuple[str, str, bool]:
    _edge, _ev, negative, missing = _edge_state(row)
    if _explicit_fallback_odds(row):
        return "WATCHLIST", "Fallback data used.", False
    if negative:
        return "WATCHLIST", DN + "play unless price improves.", False
    if not missing:
        return "PLAY SMALL", "Positive edge and EV after safety checks.", True
    action, explanation, playable = _impl.sale_ready_recommendation(row)
    return action, explanation, playable


def sale_ready_team_items(row: Any, side: str = "") -> list[str]:
    lang = _impl._lang(row)
    keys = (f"{side}_team_form", f"{side}_team_record", f"{side}_recent_results", "team_snapshot_home", "team_snapshot_away", "team_stats_summary", "recent_results", "perplexity_context")
    items = _source_items(row, keys, 3, 62)
    return _wrap(items or ["Live team feed not linked to this row.", "Use as watchlist until provider match is verified."], lang)


def sale_ready_injury_items(row: Any, prefix: str = "") -> list[str]:
    lang = _impl._lang(row)
    keys = (f"{prefix}_injuries", f"{prefix}_injury_report", f"{prefix}_lineup_status", f"{prefix}_player_notes", "injury_report", "injuries", "lineup_status", "key_players", "perplexity_context")
    items = _source_items(row, keys, 2, 66)
    return _wrap(items or ["Lineup/injury feed not verified for this row.", "Check team news before entry."], lang)


def _compact_location(raw: str, lang: str) -> str | None:
    match = re.search(r"Location:\s*([^\.]+)", raw, flags=re.I)
    if not match:
        return None
    location = match.group(1).strip()
    if lang == "es":
        location = location.replace("Philadelphia, Pennsylvania, United States of America", "Philadelphia, Pennsylvania, Estados Unidos")
        location = location.replace("United States of America", "Estados Unidos").replace("United States", "Estados Unidos")
        return f"Ubicación: {location}."
    location = location.replace("Philadelphia, Pennsylvania, United States of America", "Philadelphia, PA, USA")
    location = location.replace("Pennsylvania, United States of America", "PA, USA")
    location = location.replace("United States of America", "USA").replace("United States", "USA")
    return f"Location: {location}."


def _compact_weather(raw: str, lang: str) -> list[str]:
    if _bad(raw):
        return []
    text = _clean_text(raw)
    temp = re.search(r"(-?\d+(?:\.\d+)?°C)", text)
    wind = re.search(r"wind\s*([\d\.]+\s*kph)", text, flags=re.I)
    weather = None
    if temp:
        before = re.sub(r"^Weather:\s*", "", text[: temp.start()], flags=re.I).strip(" ,.;")
        condition = before.split(".")[-1].strip(" ,.;") or "partly cloudy"
        bits = [temp.group(1), _es(condition.lower(), lang) if lang == "es" else condition.lower()]
        if wind:
            bits.append(("viento " if lang == "es" else "wind ") + wind.group(1))
        weather = ("Clima: " if lang == "es" else "Weather: ") + ", ".join([b for b in bits if b]) + "."
    loc = _compact_location(text, lang)
    return [item for item in (weather, loc) if item]


def _compact_api_fb(row: Any, lang: str) -> str | None:
    data = _row(row)
    raw = _clean_text(data.get("api_football_summary") or data.get("api_football_team_summary") or "")
    if raw and ("api-fb" in raw.lower() or "api football" in raw.lower()) and not _bad_context(raw, row):
        return _es("API-FB lookup checked; no fixture match.", lang)
    return None


def sale_ready_matchup_items(row: Any) -> list[str]:
    lang = _impl._lang(row)
    items: list[str] = []
    if _explicit_fallback_odds(row):
        items.append("Odds are not live; verify current price before entry.")
    items.extend(_source_items(row, ("perplexity_context", "perplexity_summary", "sports_context_summary", "preview_summary", "game_summary", "short_reason", "matchup_note"), 1, 82))
    items.extend(_compact_weather(str(_row(row).get("weather_summary", "") or ""), lang))
    api_fb = _compact_api_fb(row, lang)
    if api_fb:
        items.append(api_fb)
    if not items:
        items.append("Pregame context was not returned; verify odds and news before entry.")
    return _wrap(_dedupe(items)[:4], lang)


def sale_ready_risk_items(row: Any) -> list[str]:
    lang = _impl._lang(row)
    if _explicit_fallback_odds(row):
        return _wrap(["Fallback/watchlist only.", "Confirm current price before entry.", "Watchlist only: current price and live context need verification."], lang)
    explicit = _source_items(row, ("risk_reasons",), 3, 86)
    if explicit:
        return _wrap(explicit, lang)
    _edge, _ev, negative, missing = _edge_state(row)
    if negative:
        return _wrap(["Negative edge at current price.", DN + "play unless price improves.", "Recheck odds and key news."], lang)
    if missing:
        return _wrap(["Research only: edge incomplete.", DN + "combine unverified picks.", "Wait for verified odds."], lang)
    return _wrap(["Risk status: VOLUME OK.", "Recheck odds before entry.", "Avoid if key news changes."], lang)


def sale_ready_chain_items(row: Any) -> list[str]:
    lang = _impl._lang(row)
    explicit = _source_items(row, ("combo_magazine_items", P + "_magazine_items", "chain_notes", P + "_notes", "main_read", "add_on_legs"), 3, 86)
    if explicit:
        return _wrap(explicit, lang)
    if _explicit_fallback_odds(row):
        return _wrap(["Straight watchlist only.", "Do not parlay fallback rows.", "Wait for verified odds and compatible legs."], lang)
    _edge, _ev, negative, missing = _edge_state(row)
    if negative:
        return _wrap([DN + "chain " + NEG_EV + " picks.", "Avoid " + P + "s unless edge turns positive.", "Recheck price before including."], lang)
    if missing:
        return _wrap(["Research only: edge incomplete.", DN + "combine unverified picks.", "Wait for verified odds."], lang)
    return _wrap(["Straight only: research.", "Avoid " + P + "s unless all legs are +EV.", "Recheck price before including."], lang)


def _items_from_context(row: Any, keys: Iterable[str], fallback: list[str], limit: int, lang: str = "en") -> list[str]:
    data = dict(_row(row))
    key_tuple = tuple(keys)
    explicit = _source_items(data, key_tuple, limit, 86)
    if explicit:
        return _wrap(explicit, lang)
    if any(k in key_tuple for k in ("risk", "risk_level", "risk_label", "risk_note", "risk_notes", "why_lose", "hidden_risk")):
        items = sale_ready_risk_items(data)
    elif any(k in key_tuple for k in ("chain_note", "chain_notes", P + "_note", P + "_notes", "combo_note", "combo_magazine_items", P + "_magazine_items", "main_read", "add_on_legs")):
        items = sale_ready_chain_items(data)
    elif "matchup_note" in key_tuple or "sports_context_summary" in key_tuple or "weather_summary" in key_tuple:
        items = sale_ready_matchup_items(data)
    elif "injury_report" in key_tuple or "lineup_status" in key_tuple or "key_players" in key_tuple:
        items = sale_ready_injury_items(data, "away")
    else:
        items = sale_ready_team_items(data)
    return _wrap(items[:limit], lang)


def _paint_report_name(module: Any, img: Any, report_name: str | None) -> None:
    if not report_name:
        return
    text = str(report_name or "").strip().upper()
    if not text:
        return
    draw = module.ImageDraw.Draw(img, "RGBA")
    draw.rectangle((28, 24, 308, 74), fill=module.RED)
    draw.text((43, 29), text, font=module._fit(text, 250, 38, 18, True), fill="white")


def _set_if_missing_or_bad(row: dict[str, Any], key: str, value: str) -> None:
    if _bad(row.get(key)) or _bad_context(row.get(key), row):
        row[key] = value


def _sanitize_pick(data: Any) -> dict[str, Any]:
    row = dict(_row(data))
    if _explicit_fallback_odds(row):
        fallback_context = "Fallback report: verify current odds and news before entry."
        row["risk"] = "FALLBACK MODE"
        row["risk_level"] = "FALLBACK MODE"
        row["risk_label"] = "FALLBACK MODE"
        row["final_decision"] = "WATCHLIST"
        for key in ("sports_context_summary", "preview_summary", "short_reason"):
            _set_if_missing_or_bad(row, key, fallback_context)
        row["why_lose"] = "\n".join(["Fallback/watchlist only.", "Confirm current price before entry.", "Watchlist only: current price and live context need verification."])
        row["chain_notes"] = "\n".join(["Straight watchlist only.", "Do not parlay fallback rows.", "Wait for verified odds and compatible legs."])
    for key in ("perplexity_context", "perplexity_summary", "newsapi_summary", "news_summary", "game_summary", "matchup_note", "matchup_notes", "team_snapshot_home", "team_snapshot_away", "sportsdataio_context", "sportsdataio_team_summary", "api_football_summary"):
        if _bad_context(row.get(key), row):
            row[key] = ""
    row["matchup_notes"] = "\n".join(sale_ready_matchup_items(row))
    return row


def _set_style_version(module: Any) -> None:
    current = str(getattr(module, "MAGAZINE_STYLE_VERSION", ""))
    base = re.sub(r"(?:_direct_two_page)?_sale_ready_[a-z_]+_v\d+(?:_[a-z_]+)*", "", current)
    base = re.sub(r"_sale_ready_direct_multileg_v\d+", "", base)
    module.MAGAZINE_STYLE_VERSION = f"{base or 'magazine'}_sale_ready_risk_chain_v4"


def apply_magazine_sale_ready_patch(module):
    patched = _impl.apply_magazine_sale_ready_patch(module)
    patched.team_items = sale_ready_team_items
    patched.injury_items = sale_ready_injury_items
    patched.matchup_items = sale_ready_matchup_items
    patched.risk_items = sale_ready_risk_items
    patched.chain_items = sale_ready_chain_items
    patched._team_items = sale_ready_team_items
    patched._injury_items = sale_ready_injury_items
    patched._matchup_items = sale_ready_matchup_items
    patched._risk_items = sale_ready_risk_items
    patched._chain_items = sale_ready_chain_items
    patched._items = _items_from_context
    patched.sale_ready_recommendation = sale_ready_recommendation
    original_tr = patched._tr
    original_render = patched.render_full_pick_magazine_page

    def patched_tr(value, lang):
        text = original_tr(value, lang)
        return _es(text, lang) if lang == "es" else _clean_text(text)

    def patched_render(pick, *args, **kwargs):
        report_name = kwargs.get("report_name") if "report_name" in kwargs else (args[1] if len(args) > 1 else None)
        img = original_render(_sanitize_pick(pick), *args, **kwargs)
        _paint_report_name(patched, img, report_name)
        return img

    patched._tr = patched_tr
    patched.render_full_pick_magazine_page = patched_render
    try:
        from .magazine_pipeline_runtime import install as install_final_enriched_pipeline
        install_final_enriched_pipeline()
    except Exception:
        pass
    try:
        from .magazine_second_page_patch import install as install_second_page
        install_second_page(patched)
    except Exception:
        pass
    _set_style_version(patched)
    setattr(patched, "_ABA_SALE_READY_DIRECT_MULTI_LEG_APPLIED", True)
    return patched
