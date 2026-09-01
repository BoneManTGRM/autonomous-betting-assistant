from __future__ import annotations

import builtins
import json
import os
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen


ENRICHMENT_VERSION = "v18_all_provider_truthful_enrichment"
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
) -> Any:
    if cache_key and cache_key in _CACHE:
        cached = _CACHE[cache_key]
        return dict(cached) if isinstance(cached, Mapping) else list(cached) if isinstance(cached, list) else {}
    try:
        request = Request(url, headers={"User-Agent": "ABA-Signal-Pro/1.0", **dict(headers or {})})
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed provider URLs only
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        payload = {"_error": exc.__class__.__name__}
    result = dict(payload) if isinstance(payload, Mapping) else payload if isinstance(payload, list) else {}
    if cache_key:
        _CACHE[cache_key] = result
    return result


def _request_post_json(
    url: str,
    *,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout: float = 5.0,
) -> dict[str, Any]:
    try:
        request = Request(
            url,
            data=json.dumps(dict(payload)).encode("utf-8"),
            headers={"User-Agent": "ABA-Signal-Pro/1.0", "Content-Type": "application/json", **dict(headers)},
            method="POST",
        )
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed provider URL only
            decoded = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        return {"_error": exc.__class__.__name__}
    return dict(decoded) if isinstance(decoded, Mapping) else {"_error": "INVALID_RESPONSE"}


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


def _clean(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _first(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _event_date(row: Mapping[str, Any]) -> str:
    text = _first(row, "event_start_utc", "commence_time", "start_time", "event_date", "date")
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return match.group(0) if match else ""


def _float(value: Any) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _set_no_data(row: dict[str, Any], prefix: str, reason: str) -> None:
    row[f"{prefix}_live"] = False
    row[f"{prefix}_status"] = reason


def _fetch_odds_payload(api_key: str, sport_key: str) -> list[dict[str, Any]]:
    from .live_odds import fetch_odds

    payload = fetch_odds(api_key, sport_key)
    return [dict(item) for item in payload if isinstance(item, Mapping)]


def _market_key(row: Mapping[str, Any]) -> str:
    text = _clean(_first(row, "market_type", "market", "bet_type", "pick_type"))
    if "total" in text or "over" in text or "under" in text:
        return "totals"
    if "spread" in text or "handicap" in text or "run line" in text:
        return "spreads"
    return "h2h"


def _selection_and_line(row: Mapping[str, Any]) -> tuple[str, float | None]:
    selection = _first(row, "selection", "pick", "pick_name", "recommended_bet")
    line = _float(row.get("line") or row.get("point") or row.get("total"))
    if line is None:
        match = re.search(r"(?:over|under)?\s*([+-]?\d+(?:\.\d+)?)", selection, flags=re.I)
        line = _float(match.group(1)) if match else None
    return selection, line


def _match_odds_outcome(row: Mapping[str, Any], events: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    away, home = _teams(row)
    event = next(
        (
            item for item in events
            if {_clean(item.get("away_team")), _clean(item.get("home_team"))} == {_clean(away), _clean(home)}
        ),
        None,
    )
    if not event:
        return None, "NO_EVENT_MATCH"
    market_key = _market_key(row)
    selection, line = _selection_and_line(row)
    selection_clean = _clean(selection)
    if not selection_clean:
        return None, "SELECTION_MISSING"
    candidates: list[dict[str, Any]] = []
    for bookmaker in event.get("bookmakers", []) if isinstance(event.get("bookmakers"), list) else []:
        if not isinstance(bookmaker, Mapping):
            continue
        for market in bookmaker.get("markets", []) if isinstance(bookmaker.get("markets"), list) else []:
            if not isinstance(market, Mapping) or market.get("key") != market_key:
                continue
            for outcome in market.get("outcomes", []) if isinstance(market.get("outcomes"), list) else []:
                if not isinstance(outcome, Mapping):
                    continue
                name = _clean(outcome.get("name"))
                outcome_line = _float(outcome.get("point"))
                name_match = name in selection_clean or selection_clean in name
                if market_key in {"totals", "spreads"}:
                    line_match = line is not None and outcome_line is not None and abs(line - outcome_line) < 0.001
                else:
                    line_match = True
                price = _float(outcome.get("price"))
                if name_match and line_match and price is not None and price > 1.0:
                    candidates.append({
                        "price": price,
                        "bookmaker": str(bookmaker.get("title") or bookmaker.get("key") or ""),
                        "timestamp": str(market.get("last_update") or bookmaker.get("last_update") or ""),
                        "event_id": str(event.get("id") or ""),
                        "commence_time": str(event.get("commence_time") or ""),
                    })
    return (max(candidates, key=lambda item: item["price"]), "LIVE") if candidates else (None, "NO_EXACT_MARKET_MATCH")


def _enrich_odds(row: dict[str, Any]) -> None:
    key = _secret(API_SECRET_DEFS["Odds API"])
    if not key:
        _set_no_data(row, "odds_api", "API_KEY_MISSING")
        return
    sport_key = _first(row, "sport_key", "odds_sport_key")
    if not sport_key:
        _set_no_data(row, "odds_api", "SPORT_KEY_MISSING")
        return
    try:
        events = _fetch_odds_payload(key, sport_key)
    except Exception as exc:
        _set_no_data(row, "odds_api", f"API_ERROR:{exc.__class__.__name__}")
        return
    match, status = _match_odds_outcome(row, events)
    if not match:
        _set_no_data(row, "odds_api", status)
        row.setdefault("odds_api_summary", f"Odds API checked; {status.lower().replace('_', ' ')}.")
        return
    missing_trace = [name for name in ("bookmaker", "timestamp", "event_id") if not str(match.get(name) or "").strip()]
    if missing_trace:
        status = "TRACEABILITY_MISSING:" + ",".join(missing_trace)
        _set_no_data(row, "odds_api", status)
        row.setdefault("odds_api_summary", f"Odds API price returned but traceability was incomplete ({', '.join(missing_trace)}).")
        return
    row.update({
        "odds_api_live": True,
        "odds_api_status": "LIVE",
        "odds_api_summary": f"Odds API exact event and market match at {match['bookmaker']} ({match['price']:.2f}).",
        "decimal_odds": match["price"],
        "odds": match["price"],
        "bookmaker": match["bookmaker"],
        "sportsbook": match["bookmaker"],
        "odds_source": "The Odds API",
        "provider": "The Odds API",
        "provider_event_id": match["event_id"],
        "odds_timestamp": match["timestamp"],
        "price_timestamp": match["timestamp"],
        "odds_status": "LIVE",
        "event_start_utc": match["commence_time"] or row.get("event_start_utc", ""),
    })


def _venue(row: Mapping[str, Any]) -> str:
    for key in ("weather_location", "venue", "location", "city", "venue_note"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _enrich_weather(row: dict[str, Any]) -> None:
    key = _secret(API_SECRET_DEFS["WeatherAPI"])
    if not key:
        _set_no_data(row, "weatherapi", "API_KEY_MISSING")
        return
    venue = _venue(row)
    if not venue:
        row.setdefault("weather_summary", "Weather checked; no venue/location in row.")
        _set_no_data(row, "weatherapi", "LOCATION_MISSING")
        return
    data = _request_json(
        "https://api.weatherapi.com/v1/current.json?" + urlencode({"key": key, "q": venue}),
        cache_key=("weather", venue),
    )
    current = data.get("current") if isinstance(data.get("current"), Mapping) else {}
    condition = current.get("condition") if isinstance(current.get("condition"), Mapping) else {}
    if current:
        row["weather_summary"] = f"Weather: {condition.get('text', 'Unknown')}, {current.get('temp_c')}°C, wind {current.get('wind_kph')} kph."
        row["weatherapi_live"] = True
        row["weatherapi_status"] = "LIVE"
    else:
        row.setdefault("weather_summary", "Weather checked; no current weather returned.")
        error = str(data.get("_error") or "NO_CURRENT_DATA") if isinstance(data, Mapping) else "INVALID_RESPONSE"
        _set_no_data(row, "weatherapi", error)


def _enrich_news(row: dict[str, Any], away: str, home: str) -> None:
    key = _secret(API_SECRET_DEFS["NewsAPI"])
    if not key:
        _set_no_data(row, "newsapi", "API_KEY_MISSING")
        return
    query = " ".join(part for part in (away, home, "injury OR lineup") if part).strip() or "sports injury OR lineup"
    data = _request_json(
        "https://newsapi.org/v2/everything?" + urlencode({"q": query, "pageSize": 3, "sortBy": "publishedAt", "language": "en"}),
        headers={"X-Api-Key": key},
        cache_key=("news", away, home),
    )
    articles = data.get("articles") if isinstance(data.get("articles"), list) else []
    if data.get("_error") or (data.get("status") not in (None, "ok")):
        _set_no_data(row, "newsapi", str(data.get("_error") or data.get("code") or "API_ERROR"))
        row.setdefault("newsapi_summary", "NewsAPI checked; provider response was unavailable.")
        return
    row["newsapi_live"] = True
    row["newsapi_status"] = "LIVE"
    row.setdefault(
        "newsapi_summary",
        "News checked; no recent matching articles." if not articles else f"News checked; {len(articles)} recent article(s) returned.",
    )
    headline = str(articles[0].get("title") or "News checked.") if articles and isinstance(articles[0], Mapping) else "News checked; no injury/lineup headline."
    row.setdefault("news_injury_summary", headline)


def _enrich_football(row: dict[str, Any], away: str, home: str) -> None:
    key = _secret(API_SECRET_DEFS["API-Football"])
    if not key:
        _set_no_data(row, "api_football", "API_KEY_MISSING")
        return
    if not away or not home:
        row.setdefault("api_football_summary", "API-FB checked; team names were not available.")
        _set_no_data(row, "api_football", "TEAM_NAMES_MISSING")
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
    away_response = away_data.get("response") if isinstance(away_data.get("response"), list) else []
    home_response = home_data.get("response") if isinstance(home_data.get("response"), list) else []
    matched = bool(away_response) and bool(home_response)
    if not matched:
        row.setdefault("api_football_summary", f"API-FB team lookup checked {away} / {home}; no match returned.")
        _set_no_data(row, "api_football", "NO_TEAM_MATCH")
        return
    away_team = away_response[0].get("team", {}) if isinstance(away_response[0], Mapping) else {}
    home_team = home_response[0].get("team", {}) if isinstance(home_response[0], Mapping) else {}
    away_id, home_id = away_team.get("id"), home_team.get("id")
    row["api_football_live"] = True
    row["api_football_status"] = "TEAM_MATCH_NO_FIXTURE"
    row["api_football_team_summary"] = f"API-Football matched teams: {away_team.get('name', away)} / {home_team.get('name', home)}."
    row["api_football_summary"] = f"API-FB team lookup matched {away} / {home}; fixture not verified."
    if not away_id or not home_id:
        return
    date = _event_date(row)
    fixture_params = {"team": home_id, "date": date} if date else {"team": home_id, "next": 10}
    fixture_data = _request_json(
        "https://v3.football.api-sports.io/fixtures?" + urlencode(fixture_params),
        headers={"x-apisports-key": key},
        cache_key=("api-football-fixture", home_id, date or "next"),
    )
    fixtures = fixture_data.get("response") if isinstance(fixture_data.get("response"), list) else []
    fixture = next((item for item in fixtures if isinstance(item, Mapping) and {item.get("teams", {}).get("away", {}).get("id"), item.get("teams", {}).get("home", {}).get("id")} == {away_id, home_id}), None)
    if not fixture:
        return
    fixture_meta = fixture.get("fixture") if isinstance(fixture.get("fixture"), Mapping) else {}
    venue = fixture_meta.get("venue") if isinstance(fixture_meta.get("venue"), Mapping) else {}
    status = fixture_meta.get("status") if isinstance(fixture_meta.get("status"), Mapping) else {}
    fixture_id = fixture_meta.get("id")
    if not fixture_id:
        return
    row.update({
        "api_football_status": "LIVE",
        "api_football_fixture_id": fixture_id,
        "api_football_context": f"API-Football fixture {fixture_id} matched; {fixture_meta.get('date', 'time unavailable')} · {venue.get('name', 'venue unavailable')} · {status.get('long', 'status unavailable')}.",
        "api_football_summary": f"API-FB fixture matched {away} / {home}; ID {fixture_id}.",
    })
    if fixture_id:
        injuries_data = _request_json(
            "https://v3.football.api-sports.io/injuries?" + urlencode({"fixture": fixture_id}),
            headers={"x-apisports-key": key},
            cache_key=("api-football-injuries", fixture_id),
        )
        injuries = injuries_data.get("response") if isinstance(injuries_data.get("response"), list) else []
        row["api_football_lineup_summary"] = f"API-Football returned {len(injuries)} injury/absence row(s) for fixture {fixture_id}."


def _sportsdata_context(row: Mapping[str, Any], key: str) -> dict[str, Any]:
    from .live_api_context import LiveAPIContextBuilder

    away, home = _teams(row)
    sport_key = _first(row, "sport_key", "sport", "league")
    if any(token in sport_key.lower() for token in ("fifa", "world cup", "uefa", "soccer")):
        sport_key = "soccer"
    event = SimpleNamespace(
        sport_key=sport_key,
        sport_title=_first(row, "sport_title", "sport", "league"),
        home_team=home,
        away_team=away,
        commence_time=_first(row, "event_start_utc", "commence_time", "start_time"),
    )
    return LiveAPIContextBuilder(sportsdataio_key=key).context_for_event(event, pick_name=_first(row, "selection", "pick", "pick_name"))


def _enrich_sportsdataio(row: dict[str, Any]) -> None:
    key = _secret(API_SECRET_DEFS["SportsDataIO"])
    if not key:
        _set_no_data(row, "sportsdataio", "API_KEY_MISSING")
        return
    try:
        context = _sportsdata_context(row, key)
    except Exception as exc:
        _set_no_data(row, "sportsdataio", f"API_ERROR:{exc.__class__.__name__}")
        row.setdefault("sportsdataio_context", "SportsDataIO checked; provider request failed.")
        return
    status = str(context.get("sportsdataio_status") or "NO_DATA")
    used = str(context.get("sportsdataio_source_used") or "").lower() == "yes"
    team_match = str(context.get("sportsdataio_team_metadata_used") or "").lower() == "yes"
    if used or team_match:
        row["sportsdataio_live"] = True
        row["sportsdataio_status"] = "LIVE"
        matched = [side for side in ("away", "home") if str(context.get(f"sportsdataio_{side}_team_matched") or "").lower() == "yes"]
        row["sportsdataio_team_summary"] = f"SportsDataIO matched {' and '.join(matched) or 'available'} team metadata."
        injury_count = context.get("sportsdataio_picked_team_injury_count")
        row["sportsdataio_injury_summary"] = f"SportsDataIO returned {injury_count} matched-team injury row(s)." if injury_count is not None else "SportsDataIO injury feed returned no matched-team count."
        row["sportsdataio_context"] = row["sportsdataio_team_summary"] + " " + row["sportsdataio_injury_summary"]
        for field in ("stats_probability", "injury_risk_score", "venue_name", "venue_city", "venue_country"):
            if context.get(field) not in (None, ""):
                row[f"sportsdataio_{field}"] = context[field]
    else:
        _set_no_data(row, "sportsdataio", status.upper().replace(" ", "_"))
        row.setdefault("sportsdataio_context", f"SportsDataIO checked; {status}.")


def _enrich_perplexity(row: dict[str, Any], away: str, home: str) -> None:
    key = _secret(API_SECRET_DEFS["Perplexity"])
    if not key:
        _set_no_data(row, "perplexity", "API_KEY_MISSING")
        return
    event = " vs ".join(part for part in (away, home) if part) or _first(row, "event", "event_name")
    if not event:
        _set_no_data(row, "perplexity", "EVENT_MISSING")
        return
    data = _request_post_json(
        "https://api.perplexity.ai/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        payload={
            "model": "sonar",
            "temperature": 0,
            "messages": [{
                "role": "user",
                "content": f"Return a concise sourced status update for {event}: injuries, lineup, venue, and schedule only. State when a fact is unavailable. Do not provide betting advice.",
            }],
        },
    )
    if data.get("_error") or data.get("error"):
        _set_no_data(row, "perplexity", str(data.get("_error") or "API_ERROR"))
        row.setdefault("perplexity_summary", "Perplexity checked; provider response was unavailable.")
        return
    choices = data.get("choices") if isinstance(data.get("choices"), list) else []
    message = choices[0].get("message", {}) if choices and isinstance(choices[0], Mapping) else {}
    content = re.sub(r"\s+", " ", str(message.get("content") or "")).strip()
    if not content:
        _set_no_data(row, "perplexity", "NO_CONTENT")
        row.setdefault("perplexity_summary", "Perplexity checked; no research context returned.")
        return
    citations = data.get("citations") if isinstance(data.get("citations"), list) else []
    row["perplexity_live"] = True
    row["perplexity_status"] = "LIVE_UNVERIFIED_RESEARCH"
    row["perplexity_context"] = f"Unverified research context (not a verification source): {content[:420]}"
    row["perplexity_summary"] = f"Perplexity returned research context with {len(citations)} citation(s); verify against primary sources."
    row["perplexity_citations"] = citations[:8]


def _enrich_balldontlie(row: dict[str, Any]) -> dict[str, Any]:
    from .balldontlie_integration import enrich_row_with_balldontlie

    return enrich_row_with_balldontlie(row)


def enrich_row_with_live_api_data(row_like: Any, **_: Any) -> dict[str, Any]:
    """Add only evidence returned by configured providers.

    Missing keys and empty payloads remain explicit statuses. This function never
    manufactures injury, lineup, team, matchup, price, or verification claims.
    """
    row = _row(row_like)
    if row.get("_live_api_enriched") == ENRICHMENT_VERSION:
        return row
    away, home = _teams(row)
    _enrich_odds(row)
    _enrich_weather(row)
    _enrich_news(row, away, home)
    _enrich_football(row, away, home)
    _enrich_sportsdataio(row)
    _enrich_perplexity(row, away, home)
    row = _enrich_balldontlie(row)
    row["balldontlie_live"] = str(row.get("balldontlie_status") or "").upper() == "LIVE"
    _apply_spanish(row)
    fields = sorted(
        key for key, value in row.items()
        if value not in (None, "", False) and any(token in key.lower() for token in ("odds_api", "sportsdataio", "weather", "api_football", "newsapi", "perplexity", "balldontlie"))
    )
    row["api_enrichment_fields"] = ", ".join(fields)
    row["last_api_refresh_time"] = row.get("last_api_refresh_time") or datetime.now(timezone.utc).isoformat(timespec="seconds")
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
