from __future__ import annotations

import builtins
import json
import os
import re
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from typing import Any
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

ENRICHMENT_VERSION = "live_api_enrichment_v2_checked_details"
_TIMEOUT_SECONDS = 3.0
_CACHE: dict[tuple[str, str], Any] = {}

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
    return not any(token in text for token in ("api key missing",))


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
        r"([A-Z][A-Za-z .'-]+,\s*[A-Z][A-Za-z .'-]+,\s*(?:USA|United States|Mexico|Canada))",
        r"([A-Z][A-Za-z .'-]+,\s*(?:USA|United States|Mexico|Canada))",
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
    location = _candidate_location(row)
    if not location:
        _set_if_empty(row, "weather_summary", "WeatherAPI configured; no venue/location field was available for this row.")
        return
    url = "https://api.weatherapi.com/v1/current.json?" + urlencode({"key": key, "q": location, "aqi": "no"})
    data = _request_json(url, cache_key=("weather", location.lower()))
    current = data.get("current") if isinstance(data, Mapping) else None
    place = data.get("location") if isinstance(data, Mapping) else None
    if not isinstance(current, Mapping):
        _set_if_empty(row, "weather_summary", f"WeatherAPI checked {location}; live weather payload was not returned.")
        return
    condition = current.get("condition") if isinstance(current.get("condition"), Mapping) else {}
    place_name = ", ".join(str(place.get(k)) for k in ("name", "region", "country") if isinstance(place, Mapping) and place.get(k))
    summary = f"WeatherAPI: {condition.get('text', 'conditions available')}; {current.get('temp_c')}°C; wind {current.get('wind_kph')} kph."
    if place_name:
        summary += f" Location: {place_name}."
    _set_if_empty(row, "weather_summary", summary)
    _set_if_empty(row, "venue_weather", summary)


def _news_query(row: Mapping[str, Any]) -> str:
    away, home = _split_teams(row)
    event = _get(row, "event", "game", "event_name", "matchup")
    base = f"{away} {home}".strip() or event
    kind = _sport_kind(row)
    terms = " injuries lineup news odds" if kind != "combat" else " injuries camp news"
    return (base + terms).strip()


def _enrich_news(row: dict[str, Any]) -> None:
    key = _secret(*API_SECRET_DEFS["NewsAPI"])
    if not key:
        return
    query = _news_query(row)
    if not query:
        return
    params = {"apiKey": key, "q": query, "language": "en", "sortBy": "publishedAt", "pageSize": "3"}
    data = _request_json("https://newsapi.org/v2/everything?" + urlencode(params), cache_key=("news", query.lower()))
    articles = data.get("articles") if isinstance(data, Mapping) else None
    if not isinstance(articles, list) or not articles:
        summary = f"NewsAPI checked '{query}'; no recent matching articles were returned."
        _set_if_empty(row, "newsapi_summary", summary)
        _set_if_empty(row, "news_injury_summary", summary)
        return
    titles = [str(item.get("title", "")).strip() for item in articles if isinstance(item, Mapping) and item.get("title")]
    titles = [title for title in titles if title][:3]
    if not titles:
        return
    summary = "NewsAPI: " + " | ".join(titles)
    _set_if_empty(row, "newsapi_summary", summary)
    if any(any(token in title.lower() for token in ("injury", "injured", "lineup", "out", "questionable")) for title in titles):
        _set_if_empty(row, "news_injury_summary", summary)
    else:
        _set_if_empty(row, "news_injury_summary", "NewsAPI checked recent news; no injury/lineup headline was returned.")


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
    venue = item.get("venue") if isinstance(item, Mapping) else None
    if not isinstance(team_data, Mapping):
        return ""
    name = team_data.get("name") or team
    country = team_data.get("country") or ""
    stadium = venue.get("name") if isinstance(venue, Mapping) else ""
    bits = [str(name)]
    if country:
        bits.append(str(country))
    if stadium:
        bits.append(f"venue {stadium}")
    return ", ".join(bits)


def _enrich_api_football(row: dict[str, Any]) -> None:
    if _sport_kind(row) != "soccer":
        return
    key = _secret(*API_SECRET_DEFS["API-Football"])
    if not key:
        return
    away, home = _split_teams(row)
    away_result = _api_football_team_search(away, key)
    home_result = _api_football_team_search(home, key)
    if away_result or home_result:
        summary = "API-Football: " + " vs ".join(part for part in (away_result, home_result) if part)
        _set_if_empty(row, "api_football_team_summary", summary)
        _set_if_empty(row, "api_football_summary", summary)
    else:
        summary = f"API-Football checked team lookup for {away or 'away team'} and {home or 'home team'}; no matching team payload was returned."
        _set_if_empty(row, "api_football_team_summary", summary)
        _set_if_empty(row, "api_football_summary", summary)


def _enrich_sportsdataio(row: dict[str, Any]) -> None:
    if not _secret(*API_SECRET_DEFS["SportsDataIO"]):
        return
    existing = _get(row, "sportsdataio_team_summary", "sportsdataio_context", "sportsdataio_injury_summary", "sportsdataio_game_summary")
    if existing:
        return
    kind = _sport_kind(row)
    if kind == "baseball":
        summary = "SportsDataIO configured; MLB event-specific provider id was not available in this row."
    elif kind == "soccer":
        summary = "SportsDataIO configured; soccer team/event endpoint data was not available for this row."
    elif kind == "combat":
        summary = "SportsDataIO configured; combat event endpoint data was not available for this row."
    else:
        summary = "SportsDataIO configured; event-specific provider id was not available in this row."
    _set_if_empty(row, "sportsdataio_context", summary)
    _set_if_empty(row, "sportsdataio_team_summary", summary)


def enrich_row_with_live_api_data(row_like: Any) -> dict[str, Any]:
    row = _row(row_like)
    if row.get("_live_api_enriched") == ENRICHMENT_VERSION:
        return row
    before = set(k for k, v in row.items() if _useful(v))
    _enrich_sportsdataio(row)
    _enrich_weather(row)
    _enrich_api_football(row)
    _enrich_news(row)
    after = set(k for k, v in row.items() if _useful(v))
    added = sorted(after - before)
    row["_live_api_enriched"] = ENRICHMENT_VERSION
    if added:
        row["api_enrichment_fields"] = " · ".join(added[:8])
    return row


def enrich_rows_with_live_api_data(rows: list[Any] | tuple[Any, ...]) -> list[dict[str, Any]]:
    return [enrich_row_with_live_api_data(row) for row in rows]


def install(module: Any) -> Any:
    if getattr(module, "_LIVE_API_ENRICHMENT_PATCHED", False):
        return module
    original_render = module.render_full_pick_magazine_page
    original_png = module._png
    original_team_snapshot = getattr(module, "_team_snapshot", None)

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
            items = []
            try:
                items = module._team_items(row, side_arg)
            except Exception:
                items = ["Data not returned for this event"]
            module._bullets_auto(draw, x, y + 76, items, width - 10, 165, color, 18, 10, 4, lang)

    module.render_full_pick_magazine_page = render
    module.render_full_pick_magazine_page_png = render_png
    module._team_snapshot = team_snapshot
    module.enrich_row_with_live_api_data = enrich_row_with_live_api_data
    module.enrich_rows_with_live_api_data = enrich_rows_with_live_api_data
    module.MAGAZINE_STYLE_VERSION = f"{module.MAGAZINE_STYLE_VERSION}_{ENRICHMENT_VERSION}"
    module._LIVE_API_ENRICHMENT_PATCHED = True
    return module
