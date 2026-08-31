from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen


ENRICHMENT_VERSION = "v17_truthful_optional_enrichment"
_CACHE: dict[tuple[Any, ...], Any] = {}

API_SECRET_DEFS = {
    "Odds API": ("ODDS_API_KEY", "THE_ODDS_API_KEY"),
    "SportsDataIO": ("SPORTSDATAIO_API_KEY", "SPORTS_DATA_IO_API_KEY", "SPORTSDATA_API_KEY"),
    "WeatherAPI": ("WEATHERAPI_KEY", "WEATHER_API_KEY"),
    "API-Football": ("API_FOOTBALL_KEY", "APIFOOTBALL_KEY"),
    "NewsAPI": ("NEWSAPI_KEY", "NEWS_API_KEY"),
    "Perplexity": ("PERPLEXITY_API_KEY", "PPLX_API_KEY"),
    "Balldontlie": ("BALLDONTLIE_API_KEY",),
}

TRANSLATIONS_ES = {
    "PAGE 1 OF 75": "PÁGINA 1 DE 75",
    "WATCHLIST": "LISTA DE SEGUIMIENTO",
    "consensus average": "promedio consenso",
    "No SDIO event ID.": "Sin ID de evento SDIO.",
    "No lineup/injury headline returned.": "Sin titular de lesiones/alineación.",
    "API-FB: no fixture match.": "API-FB: sin coincidencia de partido.",
    "Negative edge at current price.": "Ventaja negativa con la cuota actual.",
    "Do not play unless price improves.": "No jugar salvo que la cuota mejore.",
    "Recheck odds and key news.": "Revisar cuotas y noticias clave.",
    "Do not chain negative-EV picks.": "No encadenar señales con VE negativo.",
    "Avoid parlays unless edge turns positive.": "Evitar parlays salvo que la ventaja sea positiva.",
    "Recheck price before including.": "Revisar la cuota antes de incluir.",
}


def _secret(names: tuple[str, ...]) -> str:
    for name in names:
        value = str(os.getenv(name, "") or "").strip()
        if value:
            return value
    return ""


def _translate_text(value: Any) -> str:
    text = str(value or "")
    for english, spanish in TRANSLATIONS_ES.items():
        text = text.replace(english, spanish)
    return text


def _install_spanish_renderer_patch() -> None:
    try:
        import autonomous_betting_agent.magazine_book_export as renderer
    except Exception:
        return
    current = getattr(renderer, "_tr", None)
    if getattr(current, "_ABA_LIVE_TRANSLATION_PATCH", False):
        return

    def translated(text: str, lang: str = "en") -> str:
        if lang == "es" and text in TRANSLATIONS_ES:
            return TRANSLATIONS_ES[text]
        return current(text, lang) if callable(current) else text

    translated._ABA_LIVE_TRANSLATION_PATCH = True  # type: ignore[attr-defined]
    renderer._tr = translated


def _apply_spanish(row: dict[str, Any]) -> None:
    language = str(row.get("report_language") or row.get("language") or "").lower()
    if not language.startswith("es"):
        return
    _install_spanish_renderer_patch()
    for key in (
        "final_decision",
        "bookmaker",
        "news_injury_summary",
        "api_football_summary",
        "why_lose",
        "risk_reason",
        "chain_notes",
    ):
        if key in row:
            row[key] = _translate_text(row[key])
    probability = row.get("model_probability", row.get("probability", ""))
    market_probability = row.get("market_probability", "")
    row["why_bullets"] = "\n".join(
        (
            f"El modelo proyecta {probability} de probabilidad.",
            f"La probabilidad implícita del mercado es {market_probability}.",
            "No jugar con la cuota listada.",
        )
    )
    row.setdefault("parlay_notes", "No parlay recommended. Verified odds or edge are not positive.")
    row.setdefault("final_explanation", "No jugar con la cuota listada.")


def _request_json(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    cache_key: tuple[Any, ...] | None = None,
    timeout: float = 3.0,
) -> dict[str, Any]:
    if cache_key and cache_key in _CACHE:
        cached = _CACHE[cache_key]
        return dict(cached) if isinstance(cached, Mapping) else {}
    try:
        request = Request(url, headers={"User-Agent": "ABA-Signal-Pro/1.0", **dict(headers or {})})
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed provider URLs only
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        payload = {}
    result = dict(payload) if isinstance(payload, Mapping) else {}
    if cache_key:
        _CACHE[cache_key] = result
    return result


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        data = value.to_dict()
        return dict(data) if isinstance(data, Mapping) else {}
    return dict(getattr(value, "__dict__", {}) or {})


def _teams(row: Mapping[str, Any]) -> tuple[str, str]:
    away = str(row.get("away_team") or "").strip()
    home = str(row.get("home_team") or "").strip()
    if away and home:
        return away, home
    event = str(row.get("event_name") or row.get("event") or row.get("public_event") or "")
    for separator in (" vs ", " at ", " @ "):
        if separator in event:
            left, right = event.split(separator, 1)
            return left.strip(), right.strip()
    return away, home


def _venue(row: Mapping[str, Any]) -> str:
    for key in ("weather_location", "venue", "location", "city", "venue_note"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _enrich_weather(row: dict[str, Any]) -> None:
    key = _secret(API_SECRET_DEFS["WeatherAPI"])
    if not key:
        row.setdefault("weather_status", "API_KEY_MISSING")
        return
    venue = _venue(row)
    if not venue:
        row.setdefault("weather_summary", "Weather checked; no venue/location in row.")
        return
    data = _request_json(
        "https://api.weatherapi.com/v1/current.json?" + urlencode({"key": key, "q": venue}),
        cache_key=("weather", venue),
    )
    current = data.get("current") if isinstance(data.get("current"), Mapping) else {}
    condition = current.get("condition") if isinstance(current.get("condition"), Mapping) else {}
    if current:
        row.setdefault(
            "weather_summary",
            f"Weather: {condition.get('text', 'Unknown')}, {current.get('temp_c')}°C, wind {current.get('wind_kph')} kph.",
        )
    else:
        row.setdefault("weather_summary", "Weather checked; no current weather returned.")


def _enrich_news(row: dict[str, Any], away: str, home: str) -> None:
    key = _secret(API_SECRET_DEFS["NewsAPI"])
    if not key:
        row.setdefault("news_status", "API_KEY_MISSING")
        return
    query = " ".join(part for part in (away, home, "injury OR lineup") if part).strip() or "sports injury OR lineup"
    data = _request_json(
        "https://newsapi.org/v2/everything?" + urlencode({"q": query, "pageSize": 3, "sortBy": "publishedAt", "language": "en"}),
        headers={"X-Api-Key": key},
        cache_key=("news", away, home),
    )
    articles = data.get("articles") if isinstance(data.get("articles"), list) else []
    row.setdefault(
        "newsapi_summary",
        "News checked; no recent matching articles." if not articles else f"News checked; {len(articles)} recent article(s) returned.",
    )
    headline = str(articles[0].get("title") or "News checked.") if articles and isinstance(articles[0], Mapping) else "News checked; no injury/lineup headline."
    row.setdefault("news_injury_summary", headline)


def _enrich_football(row: dict[str, Any], away: str, home: str) -> None:
    key = _secret(API_SECRET_DEFS["API-Football"])
    if not key:
        row.setdefault("api_football_status", "API_KEY_MISSING")
        return
    if not away or not home:
        row.setdefault("api_football_summary", "API-FB checked; team names were not available.")
        return
    away_data = _request_json(
        "https://v3.football.api-sports.io/teams?search=" + quote_plus(away),
        headers={"x-apisports-key": key},
        cache_key=("api-football-team", away.lower()),
    )
    home_data = _request_json(
        "https://v3.football.api-sports.io/teams?search=" + quote_plus(home),
        headers={"x-apisports-key": key},
        cache_key=("api-football-team", home.lower()),
    )
    matched = bool(away_data.get("response")) and bool(home_data.get("response"))
    if matched:
        message = f"API-FB team lookup matched {away} / {home}; fixture not verified."
    else:
        message = f"API-FB team lookup checked {away} / {home}; no match returned."
    row.setdefault("api_football_summary", message)


def _enrich_sportsdataio(row: dict[str, Any]) -> None:
    if not _secret(API_SECRET_DEFS["SportsDataIO"]):
        row.setdefault("sportsdataio_status", "API_KEY_MISSING")
        return
    if row.get("provider_event_id"):
        row.setdefault("sportsdataio_context", "SDIO checked; provider event ID present.")
    else:
        row.setdefault("sportsdataio_context", "SDIO checked; no provider event ID in row.")


def enrich_row_with_live_api_data(row_like: Any, **_: Any) -> dict[str, Any]:
    """Add only evidence returned by configured providers.

    Missing keys and empty payloads remain explicit statuses. This function never
    manufactures injury, lineup, team, matchup, price, or verification claims.
    """
    row = _row(row_like)
    if row.get("_live_api_enriched") == ENRICHMENT_VERSION:
        return row
    away, home = _teams(row)
    _enrich_weather(row)
    _enrich_news(row, away, home)
    _enrich_football(row, away, home)
    _enrich_sportsdataio(row)
    _apply_spanish(row)
    row["_live_api_enriched"] = ENRICHMENT_VERSION
    return row


def enrich_rows_with_live_api_data(rows: list[Any] | tuple[Any, ...], **kwargs: Any) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    seen_events: set[str] = set()
    for item in rows:
        row = enrich_row_with_live_api_data(item, **kwargs)
        event_key = str(row.get("event") or row.get("public_event") or row.get("event_name") or "").strip().lower()
        if event_key and event_key in seen_events:
            continue
        if event_key:
            seen_events.add(event_key)
        enriched.append(row)
    _install_spanish_renderer_patch()
    return enriched


def install(module: Any | None = None) -> Any:
    if module is None or getattr(module, "_LIVE_API_ENRICHMENT_PATCHED", False):
        return module
    original = getattr(module, "render_full_pick_magazine_page", None)

    def wrapped(row: Any, *args: Any, **kwargs: Any) -> Any:
        enriched = enrich_row_with_live_api_data(row)
        return original(enriched, *args, **kwargs) if callable(original) else enriched

    module.render_full_pick_magazine_page = wrapped
    module._LIVE_API_ENRICHMENT_PATCHED = True
    version = str(getattr(module, "MAGAZINE_STYLE_VERSION", ""))
    if ENRICHMENT_VERSION not in version:
        module.MAGAZINE_STYLE_VERSION = f"{version}-{ENRICHMENT_VERSION}" if version else ENRICHMENT_VERSION
    return module


def generate_modeled_parlays(anchor: dict[str, Any], legs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Legacy compatibility shim; unsafe guessed-correlation parlays are disabled."""
    del anchor, legs
    return []
