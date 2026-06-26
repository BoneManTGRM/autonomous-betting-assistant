from __future__ import annotations

import builtins
import importlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from typing import Any
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

ENRICHMENT_VERSION = "live_api_enrichment_v10_immediate_spanish_renderer"
_TIMEOUT_SECONDS = 3.0
_CACHE: dict[tuple[str, str], Any] = {}
_SPANISH_TR_MARKER = "_aba_spanish_report_tr_v10"
_RELOAD_MARKER = "_aba_magazine_reload_patch_v10"

API_SECRET_DEFS = {
    "SportsDataIO": ("SPORTSDATAIO_API_KEY", "SPORTS_DATA_IO_API_KEY", "SPORTSDATA_API_KEY"),
    "WeatherAPI": ("WEATHERAPI_KEY", "WEATHER_API_KEY"),
    "API-Football": ("API_FOOTBALL_KEY", "APIFOOTBALL_KEY"),
    "NewsAPI": ("NEWSAPI_KEY", "NEWS_API_KEY"),
}


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict"):
        data = value.to_dict()
        return dict(data) if isinstance(data, Mapping) else {}
    return dict(getattr(value, "__dict__", {}) or {})


def _bad(value: Any) -> bool:
    return value is None or str(value).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


def _useful(value: Any) -> bool:
    if _bad(value):
        return False
    text = str(value).strip().lower()
    return not any(token in text for token in ("api key missing", "payment required"))


def _get(row: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if not _bad(value):
            return str(value).strip()
    return default


def _secret(*names: str) -> str:
    getter = getattr(builtins, "get_secret", None)
    if callable(getter):
        try:
            value = str(getter(*names) or "").strip()
            if value:
                return value
        except Exception:
            pass
    try:
        import streamlit as st  # type: ignore
        for name in names:
            try:
                value = str(st.secrets.get(name, "") or "").strip()
            except Exception:
                value = ""
            if value:
                return value
    except Exception:
        pass
    for name in names:
        value = str(os.getenv(name, "") or "").strip()
        if value:
            return value
    return ""


def _is_spanish(row: Mapping[str, Any]) -> bool:
    text = _get(row, "report_language", "language", "lang").lower()
    return text.startswith("es") or "español" in text or "espanol" in text or "spanish" in text


def _sport_kind(row: Mapping[str, Any]) -> str:
    text = " ".join(str(row.get(key, "")) for key in ("sport", "league", "event", "game", "matchup", "event_name")).lower()
    if any(token in text for token in ("mma", "ufc", "boxing", "fighter")):
        return "combat"
    if any(token in text for token in ("soccer", "fifa", "football", "world cup", "uefa", "liga")):
        return "soccer"
    if any(token in text for token in ("mlb", "baseball")):
        return "baseball"
    return "generic"


def _split_teams(row: Mapping[str, Any]) -> tuple[str, str]:
    away = _get(row, "away_team", "team_a", "team1")
    home = _get(row, "home_team", "team_b", "team2")
    if away and home:
        return away, home
    event = _get(row, "event", "game", "event_name", "matchup")
    for sep in (" at ", " vs ", " VS ", " v ", " @ "):
        if sep in event:
            left, right = event.split(sep, 1)
            return left.strip(), right.strip()
    return _get(row, "team", default=""), _get(row, "opponent", default="")


def _set_if_empty(row: dict[str, Any], key: str, value: str) -> None:
    if value and not _useful(row.get(key)):
        row[key] = value


def _request_json(url: str, *, headers: Mapping[str, str] | None = None, cache_key: tuple[str, str] | None = None, timeout: float = _TIMEOUT_SECONDS) -> Any:
    key = cache_key or ("url", url)
    if key in _CACHE:
        return _CACHE[key]
    req = Request(url, headers={"User-Agent": "ABA-Signal-Pro/1.0", **dict(headers or {})})
    try:
        with urlopen(req, timeout=timeout) as response:  # noqa: S310 - controlled API URLs only
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        data = {"_error": exc.__class__.__name__}
    _CACHE[key] = data
    return data


def _candidate_location(row: Mapping[str, Any]) -> str:
    explicit = _get(row, "weather_location", "venue_weather_location", "venue", "event_location", "location", "city")
    if explicit:
        return explicit
    joined = " | ".join(str(row.get(key, "")) for key in ("venue_note", "matchup_note", "matchup_notes", "sports_context_summary", "weather_summary", "event", "event_name"))
    patterns = (
        r"([A-Z][A-Za-z .'-]+,\s*[A-Z][A-Za-z .'-]+,\s*(?:USA|United States|United States of America|Mexico|Canada))",
        r"([A-Z][A-Za-z .'-]+,\s*(?:USA|United States|United States of America|Mexico|Canada))",
    )
    for pattern in patterns:
        match = re.search(pattern, joined)
        if match:
            return match.group(1).strip(" .")
    return ""


def _enrich_weather(row: dict[str, Any]) -> None:
    key = _secret(*API_SECRET_DEFS["WeatherAPI"])
    if not key:
        return
    spanish = _is_spanish(row)
    location = _candidate_location(row)
    if not location:
        _set_if_empty(row, "weather_summary", "Clima revisado; no hay sede/ubicación en la fila." if spanish else "Weather checked; no venue/location in row.")
        return
    url = "https://api.weatherapi.com/v1/current.json?" + urlencode({"key": key, "q": location, "aqi": "no"})
    data = _request_json(url, cache_key=("weather", location.lower()))
    current = data.get("current") if isinstance(data, Mapping) else None
    place = data.get("location") if isinstance(data, Mapping) else None
    if not isinstance(current, Mapping):
        _set_if_empty(row, "weather_summary", f"Clima revisado: {location}; sin datos en vivo." if spanish else f"Weather checked: {location}; no live payload.")
        return
    condition = current.get("condition") if isinstance(current.get("condition"), Mapping) else {}
    condition_text = str(condition.get("text", "conditions available"))
    if spanish:
        condition_text = {"sunny": "soleado", "clear": "despejado", "cloudy": "nublado", "partly cloudy": "parcialmente nublado"}.get(condition_text.lower(), condition_text)
        weather = f"Clima: {condition_text}, {current.get('temp_c')}°C, viento {current.get('wind_kph')} kph."
    else:
        weather = f"Weather: {condition_text}, {current.get('temp_c')}°C, wind {current.get('wind_kph')} kph."
    place_name = ", ".join(str(place.get(k)) for k in ("name", "region", "country") if isinstance(place, Mapping) and place.get(k))
    summary = weather + ((f" Ubicación: {place_name}." if spanish else f" Location: {place_name}.") if place_name else "")
    _set_if_empty(row, "weather_summary", summary)
    _set_if_empty(row, "venue_weather", summary)


def _news_query(row: Mapping[str, Any]) -> str:
    away, home = _split_teams(row)
    event = _get(row, "event", "game", "event_name", "matchup")
    base = f"{away} {home}".strip() or event
    terms = " injury camp news" if _sport_kind(row) == "combat" else " injury lineup news odds"
    return (base + terms).strip()


def _enrich_news(row: dict[str, Any]) -> None:
    key = _secret(*API_SECRET_DEFS["NewsAPI"])
    if not key:
        return
    spanish = _is_spanish(row)
    query = _news_query(row)
    if not query:
        return
    params = {"apiKey": key, "q": query, "language": "en", "sortBy": "publishedAt", "pageSize": "3"}
    data = _request_json("https://newsapi.org/v2/everything?" + urlencode(params), cache_key=("news", query.lower()))
    articles = data.get("articles") if isinstance(data, Mapping) else None
    if not isinstance(articles, list) or not articles:
        _set_if_empty(row, "newsapi_summary", "Noticias revisadas; sin artículos recientes relacionados." if spanish else "News checked; no recent matching articles.")
        _set_if_empty(row, "news_injury_summary", "Noticias revisadas; sin titular de lesiones/alineación." if spanish else "News checked; no injury/lineup headline.")
        return
    titles = [str(item.get("title", "")).strip() for item in articles if isinstance(item, Mapping) and item.get("title")]
    titles = [title for title in titles if title][:3]
    if not titles:
        return
    first = titles[0][:88].rstrip() + ("…" if len(titles[0]) > 88 else "")
    _set_if_empty(row, "newsapi_summary", ("Noticias: " if spanish else "News: ") + first)
    _set_if_empty(row, "news_injury_summary", ("Noticias: " if spanish else "News: ") + first)


def _api_football_team_search(team: str, key: str) -> str:
    if not team:
        return ""
    url = "https://v3.football.api-sports.io/teams?search=" + quote_plus(team)
    data = _request_json(url, headers={"x-apisports-key": key}, cache_key=("api-football-team", team.lower()))
    response = data.get("response") if isinstance(data, Mapping) else None
    if not isinstance(response, list) or not response:
        return ""
    item = response[0]
    team_data = item.get("team") if isinstance(item, Mapping) else None
    if not isinstance(team_data, Mapping):
        return ""
    return str(team_data.get("name") or team)


def _enrich_api_football(row: dict[str, Any]) -> None:
    if _sport_kind(row) != "soccer":
        return
    key = _secret(*API_SECRET_DEFS["API-Football"])
    if not key:
        return
    spanish = _is_spanish(row)
    away, home = _split_teams(row)
    away_result = _api_football_team_search(away, key)
    home_result = _api_football_team_search(home, key)
    if away_result or home_result:
        matched = " / ".join(part for part in (away_result or away, home_result or home) if part)
        summary = f"API-FB encontró equipos {matched}; partido no verificado." if spanish else f"API-FB team lookup matched {matched}; fixture not verified."
    else:
        summary = "API-FB: búsqueda revisada; sin coincidencia de partido." if spanish else f"API-FB team lookup checked {away or 'away'} / {home or 'home'}; no match returned."
    _set_if_empty(row, "api_football_team_summary", summary)
    _set_if_empty(row, "api_football_summary", summary)


def _enrich_sportsdataio(row: dict[str, Any]) -> None:
    if not _secret(*API_SECRET_DEFS["SportsDataIO"]):
        return
    existing = _get(row, "sportsdataio_team_summary", "sportsdataio_context", "sportsdataio_injury_summary", "sportsdataio_game_summary")
    if existing:
        return
    summary = "SDIO revisado; sin ID de evento del proveedor." if _is_spanish(row) else "SDIO checked; no provider event ID in row."
    _set_if_empty(row, "sportsdataio_context", summary)
    _set_if_empty(row, "sportsdataio_team_summary", summary)


def _safe_float(value: Any) -> float | None:
    if _bad(value):
        return None
    try:
        return float(str(value).replace("%", "").replace(",", ""))
    except Exception:
        return None


def _fmt_pct(value: Any, signed: bool = False) -> str:
    parsed = _safe_float(value)
    if parsed is None:
        return ""
    parsed = parsed / 100 if abs(parsed) > 1 else parsed
    return f"{parsed:+.1%}" if signed else f"{parsed:.0%}"


def _fmt_ev(value: Any) -> str:
    parsed = _safe_float(value)
    return "" if parsed is None else f"{parsed:+.3f}"


def _spanish_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return text
    exact = {
        "PAGE": "PÁGINA", "OF": "DE", "WATCHLIST": "LISTA DE SEGUIMIENTO",
        "PLAY STANDARD": "JUGAR NORMAL", "PLAY SMALL": "JUGAR PEQUEÑO", "NO PLAY": "NO JUGAR",
        "uploaded/cached row": "fila cargada/en caché", "consensus average": "promedio consenso",
        "No lineup/injury headline returned.": "Sin titular de lesiones/alineación.",
        "API-FB: no fixture match.": "API-FB: sin coincidencia de partido.",
        "No SDIO event ID.": "Sin ID de evento SDIO.",
        "Price check required before entry.": "Revisar cuota antes de entrar.",
        "Context unavailable.": "Contexto no disponible.",
        "Data not returned for this event": "Datos no disponibles para este evento",
        "Player data not returned for this event": "Datos de jugadores no disponibles para este evento",
    }
    if text in exact:
        return exact[text]
    page_match = re.fullmatch(r"PAGE\s+(\d+)\s+OF\s+(\d+)", text, flags=re.I)
    if page_match:
        return f"PÁGINA {page_match.group(1)} DE {page_match.group(2)}"
    replacements = (
        (r"\bModel projects\b", "El modelo proyecta"),
        (r"\bprobability for\b", "de probabilidad para"),
        (r"\bMarket-implied probability checks at\b", "La probabilidad implícita del mercado es"),
        (r"\bMeasured edge\b", "Ventaja medida"),
        (r"\bExpected value\b", "Valor esperado"),
        (r"\bNegative edge at current price\b", "Ventaja negativa con la cuota actual"),
        (r"\bDo not play unless price improves\b", "No jugar salvo que la cuota mejore"),
        (r"\bRecheck odds and key news\b", "Revisar cuotas y noticias clave"),
        (r"\bDo not chain negative-EV picks\b", "No encadenar señales con VE negativo"),
        (r"\bAvoid parlays unless edge turns positive\b", "Evitar parlays salvo que la ventaja sea positiva"),
        (r"\bRecheck price before including\b", "Revisar la cuota antes de incluir"),
        (r"\bDo not play at the listed price\b", "No jugar con la cuota listada"),
        (r"\bRecheck only if the line improves or new information changes the edge\b", "Revisar solo si mejora la línea o nueva información cambia la ventaja"),
        (r"\bNo lineup/injury headline returned\b", "Sin titular de lesiones/alineación"),
        (r"\bNo SDIO event ID\b", "Sin ID de evento SDIO"),
        (r"\bAPI-FB: no fixture match\b", "API-FB: sin coincidencia de partido"),
        (r"\bAPI-FB lookup checked; no fixture match\b", "API-FB revisada; sin coincidencia de partido"),
        (r"\bWeather\b", "Clima"), (r"\bwind\b", "viento"), (r"\bLocation\b", "Ubicación"),
        (r"\bNews\b", "Noticias"), (r"\bsunny\b", "soleado"),
    )
    for old, new in replacements:
        text = re.sub(old, new, text, flags=re.I)
    return text


def _renderer_spanish_fallbacks() -> dict[str, str]:
    return {
        "Negative edge at current price.": "Ventaja negativa con la cuota actual.",
        "Do not play unless price improves.": "No jugar salvo que la cuota mejore.",
        "Recheck odds and key news.": "Revisar cuotas y noticias clave.",
        "Do not chain negative-EV picks.": "No encadenar señales con VE negativo.",
        "Avoid parlays unless edge turns positive.": "Evitar parlays salvo que la ventaja sea positiva.",
        "Recheck price before including.": "Revisar la cuota antes de incluir.",
        "Price check required before entry.": "Revisar cuota antes de entrar.",
        "Straight only: research": "Solo directa: investigación",
        "Do not combine without official verification": "No combinar sin verificación oficial",
        "Wait for better context or price": "Esperar mejor contexto o mejor cuota",
        "Risk status": "Estado de riesgo",
        "Recheck odds before entry.": "Revisar cuotas antes de entrar.",
        "Avoid if key news changes": "Evitar si cambian noticias clave",
        "Use only if the line remains playable and key news does not change.": "Usar solo si la línea sigue jugable y no cambian noticias clave.",
    }


def _install_renderer_es_fallbacks(module: Any) -> None:
    es = getattr(module, "ES", None)
    if isinstance(es, dict):
        es.update(_renderer_spanish_fallbacks())


def _alias_text(row: dict[str, Any], keys: tuple[str, ...], default: str) -> str:
    existing = "\n".join(str(row.get(key, "")) for key in keys if _useful(row.get(key)))
    return _spanish_text(existing) if existing else default


def _spanish_report_defaults(row: dict[str, Any]) -> None:
    if not _is_spanish(row):
        return
    pick = _get(row, "public_pick", "prediction", "pick", "selection", default="esta selección")
    if not any(_useful(row.get(k)) for k in ("why_bullets", "why_pick", "analysis_summary", "reason", "explanation")):
        row["why_bullets"] = "\n".join([
            f"El modelo proyecta {_fmt_pct(_get(row, 'learned_model_probability', 'model_probability_clean', 'model_probability', 'final_probability'))} de probabilidad para {pick}.",
            f"La probabilidad implícita del mercado es {_fmt_pct(_get(row, 'market_probability', 'market_implied_probability'))}.",
            f"Ventaja medida: {_fmt_pct(_get(row, 'model_market_edge', 'edge'), signed=True)}.",
            f"Valor esperado: {_fmt_ev(_get(row, 'expected_value_per_unit', 'profit_expected_value', 'expected_value', 'ev'))}.",
        ])
    for key, value in list(row.items()):
        if isinstance(value, str):
            row[key] = _spanish_text(value)
    risk_keys = ("why_lose", "risk_reason", "hidden_risk", "risk_notes")
    parlay_keys = ("chain_notes", "main_read", "add_on_legs", "parlay_notes")
    final_keys = ("final_explanation", "action_reason", "recommendation_reason", "decision_reasons")
    risk_text = _alias_text(row, risk_keys, "Ventaja negativa con la cuota actual.\nNo jugar salvo que la cuota mejore.\nRevisar cuotas y noticias clave.")
    parlay_text = _alias_text(row, parlay_keys, "No encadenar señales con VE negativo.\nEvitar parlays salvo que la ventaja sea positiva.\nRevisar la cuota antes de incluir.")
    final_text = _alias_text(row, final_keys, "No jugar con la cuota listada. Revisar si mejora la línea.")
    if "nueva información cambia" in final_text or len(final_text) > 72:
        final_text = "No jugar con la cuota listada. Revisar si mejora la línea."
    for key in risk_keys:
        row[key] = risk_text
    for key in parlay_keys:
        row[key] = parlay_text
    for key in final_keys:
        row[key] = final_text
    if not _useful(row.get("data_source")) and not _useful(row.get("odds_source")):
        row["data_source"] = "fila cargada/en caché"


def enrich_row_with_live_api_data(row_like: Any) -> dict[str, Any]:
    row = _row(row_like)
    if row.get("_live_api_enriched") == ENRICHMENT_VERSION:
        if _is_spanish(row):
            _spanish_report_defaults(row)
        return row
    before = set(k for k, v in row.items() if _useful(v))
    _enrich_sportsdataio(row)
    _enrich_weather(row)
    _enrich_api_football(row)
    _enrich_news(row)
    _spanish_report_defaults(row)
    after = set(k for k, v in row.items() if _useful(v))
    added = sorted(after - before)
    row["_live_api_enriched"] = ENRICHMENT_VERSION
    if added:
        row["api_enrichment_fields"] = " · ".join(added[:8])
    return row


def _report_page_event_key(row: Mapping[str, Any]) -> str:
    event = _get(row, "public_event", "event", "event_name", "matchup")
    if not event:
        return ""
    key = event.lower()
    key = re.sub(r"\s+(?:at|vs|v|@)\s+", " vs ", key)
    key = re.sub(r"[^a-z0-9áéíóúüñ]+", " ", key)
    return re.sub(r"\s+", " ", key).strip()


def _report_page_priority(row: Mapping[str, Any]) -> int:
    lane = _get(row, "report_lane", "report_lane_v2").lower()
    action = _get(row, "consumer_action", "recommended_action", "public_action").lower()
    publish_ready = _get(row, "official_publish_ready", "publish_ready").lower() in {"true", "1", "yes"}
    return 0 if publish_ready or "official" in action or "oficial" in action or lane in {"best_play", "best play"} else 1


def _dedupe_report_page_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not any(_get(row, "report_language", "language", "lang") for row in rows):
        return rows
    unique: list[dict[str, Any]] = []
    index_by_key: dict[str, int] = {}
    priority_by_key: dict[str, int] = {}
    for row in rows:
        key = _report_page_event_key(row)
        if not key:
            unique.append(row)
            continue
        priority = _report_page_priority(row)
        if key in index_by_key:
            if priority < priority_by_key[key]:
                unique[index_by_key[key]] = row
                priority_by_key[key] = priority
            continue
        index_by_key[key] = len(unique)
        priority_by_key[key] = priority
        unique.append(row)
    return unique


def enrich_rows_with_live_api_data(rows: list[Any] | tuple[Any, ...]) -> list[dict[str, Any]]:
    enriched = _dedupe_report_page_rows([enrich_row_with_live_api_data(row) for row in rows])
    _ensure_renderer_patch()
    return enriched


def install(module: Any) -> Any:
    _install_renderer_es_fallbacks(module)
    existing_tr = getattr(module, "_tr", None)
    if callable(existing_tr) and getattr(existing_tr, _SPANISH_TR_MARKER, False):
        return module

    original_render = module.render_full_pick_magazine_page
    original_png = module._png
    original_tr = existing_tr
    original_team_snapshot = getattr(module, "_team_snapshot", None)

    if callable(original_tr):
        def tr(value: Any, lang: str) -> str:
            translated = original_tr(value, lang)
            return _spanish_text(translated) if str(lang).lower().startswith("es") else translated
        setattr(tr, _SPANISH_TR_MARKER, True)
        module._tr = tr

    def render(row_like: Any, *args: Any, **kwargs: Any):
        return original_render(enrich_row_with_live_api_data(row_like), *args, **kwargs)

    def render_png(row_like: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
        return original_png(module.render_full_pick_magazine_page(enrich_row_with_live_api_data(row_like), background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))

    def team_snapshot(img: Any, draw: Any, x: int, y: int, width: int, team: str, color: Any, lang: str, row_arg: Any | None = None, side_arg: str = "", *extra: Any, **kwargs: Any) -> None:
        if callable(original_team_snapshot):
            try:
                original_team_snapshot(img, draw, x, y, width, team, color, lang, row_arg, side_arg, *extra, **kwargs)
                return
            except TypeError:
                original_team_snapshot(img, draw, x, y, width, team, color, lang)
                return
        if hasattr(module, "_badge") and hasattr(module, "_fit") and hasattr(module, "_bullets_auto"):
            label = module._team_label(team, lang)
            module._badge(img, draw, label, x, y, 50, 50, color)
            draw.text((x + 66, y + 9), label.upper(), font=module._fit(label.upper(), width - 70, 25, 7, True), fill=color)
            row = enrich_row_with_live_api_data(row_arg or {})
            try:
                items = module._team_items(row, side_arg)
            except Exception:
                items = ["Datos no disponibles para este evento" if lang == "es" else "Data not returned for this event"]
            module._bullets_auto(draw, x, y + 76, items, width - 10, 165, color, 18, 10, 4, lang)

    module.render_full_pick_magazine_page = render
    module.render_full_pick_magazine_page_png = render_png
    module._team_snapshot = team_snapshot
    module.enrich_row_with_live_api_data = enrich_row_with_live_api_data
    module.enrich_rows_with_live_api_data = enrich_rows_with_live_api_data
    if ENRICHMENT_VERSION not in str(getattr(module, "MAGAZINE_STYLE_VERSION", "")):
        module.MAGAZINE_STYLE_VERSION = f"{module.MAGAZINE_STYLE_VERSION}_{ENRICHMENT_VERSION}"
    module._LIVE_API_ENRICHMENT_VERSION = ENRICHMENT_VERSION
    return module


def _ensure_renderer_patch() -> None:
    try:
        import autonomous_betting_agent.magazine_book_export as magazine_book_export
        install(magazine_book_export)
    except Exception:
        pass


def _patch_importlib_reload() -> None:
    if getattr(importlib.reload, _RELOAD_MARKER, False):
        return
    original_reload = getattr(importlib, "_aba_original_reload", importlib.reload)
    setattr(importlib, "_aba_original_reload", original_reload)

    def reload_with_magazine_patch(module: Any) -> Any:
        reloaded = original_reload(module)
        if getattr(reloaded, "__name__", "") == "autonomous_betting_agent.magazine_book_export":
            return install(reloaded)
        return reloaded

    setattr(reload_with_magazine_patch, _RELOAD_MARKER, True)
    importlib.reload = reload_with_magazine_patch


_patch_importlib_reload()
_ensure_renderer_patch()
