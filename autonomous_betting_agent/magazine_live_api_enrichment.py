from __future__ import annotations

import builtins
import hashlib
import importlib
import json
import math
import os
import re
import time
from collections.abc import Iterable, Mapping
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

ENRICHMENT_VERSION = "live_api_enrichment_v14_direct_renderer_cleanup"
_TIMEOUT_SECONDS = 3.0
_CACHE: dict[tuple[str, str], Any] = {}
_RUN_COUNTER = 0
_RELOAD_MARKER = "_aba_magazine_reload_patch_v14"

API_SECRET_DEFS = {
    "Odds API": ("ODDS_API_KEY", "THE_ODDS_API_KEY"),
    "SportsDataIO": ("SPORTSDATAIO_API_KEY", "SPORTS_DATA_IO_API_KEY", "SPORTSDATA_API_KEY"),
    "WeatherAPI": ("WEATHERAPI_KEY", "WEATHER_API_KEY"),
    "API-Football": ("API_FOOTBALL_KEY", "APIFOOTBALL_KEY"),
    "NewsAPI": ("NEWSAPI_KEY", "NEWS_API_KEY"),
    "Perplexity": ("PERPLEXITY_API_KEY", "PPLX_API_KEY"),
}

FALLBACK_TOKENS = (
    "context unavailable", "no sdio event id", "sdio checked", "no provider event id",
    "api-fb lookup checked", "api-fb team lookup checked", "no fixture match", "no match returned",
    "simple news aggregator", "uploaded/cached row", "uploaded row", "no live",
    "not returned for this event", "data not returned", "player data not returned",
    "api key missing", "payment required",
)
WRONG_SPORT_TOKENS = ("api-mma", "api mma", "matching fight", "fighter data", "weight cut", "camp updates", "fight news")
MOJIBAKE_REPLACEMENTS = {
    "Ã¡": "á", "Ã©": "é", "Ã­": "í", "Ã³": "ó", "Ãº": "ú", "Ã±": "ñ", "Ã¼": "ü",
    "ÃÁ": "Á", "Ã‰": "É", "Ã‘": "Ñ", "Ã": "", "Â": "",
    "â€™": "'", "â€œ": '"', "â€�": '"', "â€“": "-", "â€”": "-", "â€¦": "…", "�": "",
}
ES = {
    "PAGE 1 OF 75": "PÁGINA 1 DE 75",
    "WATCHLIST": "LISTA DE SEGUIMIENTO",
    "No SDIO event ID.": "Sin ID de evento SDIO.",
    "No lineup/injury headline returned.": "Sin titular de lesiones/alineación.",
    "API-FB: no fixture match.": "API-FB: sin coincidencia de partido.",
    "API-FB lookup checked; no fixture match.": "API-FB revisada; sin coincidencia de partido.",
    "consensus average": "promedio consenso",
    "Negative edge at current price.": "Ventaja negativa con la cuota actual.",
    "Do not play unless price improves.": "No jugar salvo que la cuota mejore.",
    "Recheck odds and key news.": "Revisar cuotas y noticias clave.",
    "Do not chain negative-EV picks.": "No encadenar señales con VE negativo.",
    "Avoid parlays unless edge turns positive.": "Evitar parlays salvo que la ventaja sea positiva.",
    "Recheck price before including.": "Revisar la cuota antes de incluir.",
    "Price check required before entry.": "Revisar cuota antes de entrar.",
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


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    for old, new in MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(old, new)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _bad(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value)) or str(value).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


def _useful(value: Any) -> bool:
    if _bad(value):
        return False
    text = _clean_text(value).lower()
    if text in {"false", "0", "no", "not available", "unavailable", "data unavailable", "none available"}:
        return False
    return not any(token in text for token in FALLBACK_TOKENS)


def _get(row: Mapping[str, Any] | Any, *keys: str, default: str = "") -> str:
    data = _row(row)
    for key in keys:
        value = data.get(key)
        if not _bad(value):
            return _clean_text(value)
    return default


def _safe_float(value: Any) -> float | None:
    if _bad(value):
        return None
    try:
        return float(str(value).replace("%", "").replace(",", ""))
    except Exception:
        return None


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


def _mask(value: str) -> str:
    text = str(value or "")
    return "" if not text else ("***" if len(text) <= 8 else f"{text[:4]}...{text[-4:]}")


def check_api_health(mask_secrets: bool = True) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for name, keys in API_SECRET_DEFS.items():
        key = _secret(*keys)
        out[name] = {"status": "CONFIGURED" if key else "API_KEY_MISSING", "key": _mask(key) if mask_secrets and key else ("present" if key else "")}
    return out


def _hash_payload(value: Any) -> str:
    try:
        text = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
    except Exception:
        text = str(value)
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _new_run_meta(rows: list[Any] | tuple[Any, ...]) -> tuple[str, str]:
    global _RUN_COUNTER
    _RUN_COUNTER += 1
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return f"aba_mag_{int(time.time())}_{_RUN_COUNTER}_{_hash_payload(rows)}", ts


def _normalize_text(value: Any) -> str:
    text = _clean_text(value).lower()
    text = re.sub(r"\s+(?:at|vs|v|@)\s+", " vs ", text)
    text = re.sub(r"[^a-z0-9áéíóúüñ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _split_teams(row: Mapping[str, Any]) -> tuple[str, str]:
    away = _get(row, "away_team", "team_a", "team1")
    home = _get(row, "home_team", "team_b", "team2")
    if away and home:
        return away, home
    event = _get(row, "public_event", "event", "game", "event_name", "matchup")
    for sep in (" at ", " vs ", " VS ", " v ", " @ "):
        if sep in event:
            left, right = event.split(sep, 1)
            return left.strip(), right.strip()
    return _get(row, "team", default=""), _get(row, "opponent", default="")


def _event_key(row: Mapping[str, Any]) -> str:
    away, home = _split_teams(row)
    event = _get(row, "public_event", "event", "game", "event_name", "matchup") or f"{away} vs {home}".strip()
    return "|".join(part for part in (_normalize_text(event), _normalize_text(_get(row, "sport", "league")), _get(row, "event_date", "event_start_utc", "start_time", "commence_time")[:10]) if part) or "unknown_event"


def _sport_kind(row: Mapping[str, Any] | Any) -> str:
    data = _row(row)
    text = " ".join(str(data.get(key, "")) for key in ("sport", "league", "event", "game", "matchup", "event_name")).lower()
    if any(token in text for token in ("mma", "ufc", "boxing", "fighter")):
        return "combat"
    if any(token in text for token in ("soccer", "fifa", "football", "world cup", "uefa", "liga")):
        return "soccer"
    if any(token in text for token in ("mlb", "baseball")):
        return "baseball"
    return "generic"


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


def _request_post_json(url: str, payload: Mapping[str, Any], *, headers: Mapping[str, str] | None = None, cache_key: tuple[str, str] | None = None, timeout: float = _TIMEOUT_SECONDS) -> Any:
    key = cache_key or ("post", url + _hash_payload(payload))
    if key in _CACHE:
        return _CACHE[key]
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, method="POST", headers={"User-Agent": "ABA-Signal-Pro/1.0", "Content-Type": "application/json", **dict(headers or {})})
    try:
        with urlopen(req, timeout=timeout) as response:  # noqa: S310 - controlled API URL only
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
        row.setdefault("weather_status", "API_KEY_MISSING")
        row.setdefault("weather_failure_reason", "WeatherAPI key missing")
        return
    location = _candidate_location(row)
    if not location:
        row["weather_status"] = "NO_LOCATION"
        row["weather_failure_reason"] = "No venue/location in row"
        row["weather_summary"] = "Weather checked; no venue/location in row."
        return
    url = "https://api.weatherapi.com/v1/current.json?" + urlencode({"key": key, "q": location, "aqi": "no"})
    data = _request_json(url, cache_key=("weather", location.lower()))
    current = data.get("current") if isinstance(data, Mapping) else None
    place = data.get("location") if isinstance(data, Mapping) else None
    if not isinstance(current, Mapping):
        row["weather_status"] = "API_ERROR" if isinstance(data, Mapping) and data.get("_error") else "NO_LIVE_PAYLOAD"
        row["weather_failure_reason"] = str(data.get("_error") if isinstance(data, Mapping) else "No live weather payload")
        row["weather_summary"] = f"Weather checked: {location}; no live payload."
        return
    condition = current.get("condition") if isinstance(current.get("condition"), Mapping) else {}
    condition_text = str(condition.get("text", "conditions available"))
    weather = f"Weather: {condition_text}, {current.get('temp_c')}°C, wind {current.get('wind_kph')} kph."
    place_name = ", ".join(str(place.get(k)) for k in ("name", "region", "country") if isinstance(place, Mapping) and place.get(k))
    row["weather_status"] = "LIVE"
    row["weather_summary"] = weather + (f" Location: {place_name}." if place_name else "")


def _news_query(row: Mapping[str, Any]) -> str:
    away, home = _split_teams(row)
    event = _get(row, "event", "game", "event_name", "matchup")
    base = f"{away} {home}".strip() or event
    terms = " injury camp news" if _sport_kind(row) == "combat" else " injury lineup news odds"
    return (base + terms).strip()


def _enrich_news(row: dict[str, Any]) -> None:
    key = _secret(*API_SECRET_DEFS["NewsAPI"])
    if not key:
        row.setdefault("news_status", "API_KEY_MISSING")
        row.setdefault("news_failure_reason", "NewsAPI key missing")
        return
    query = _news_query(row)
    if not query:
        row["news_status"] = "NO_QUERY"
        row["news_failure_reason"] = "No event/team query available"
        return
    params = {"apiKey": key, "q": query, "language": "en", "sortBy": "publishedAt", "pageSize": "3"}
    data = _request_json("https://newsapi.org/v2/everything?" + urlencode(params), cache_key=("news", query.lower()))
    articles = data.get("articles") if isinstance(data, Mapping) else None
    if not isinstance(articles, list) or not articles:
        row["news_status"] = "NO_RECENT_MATCHES"
        row["news_failure_reason"] = "No recent matching articles returned"
        row["newsapi_summary"] = "News checked; no recent matching articles."
        row["news_summary"] = row["newsapi_summary"]
        row["news_injury_summary"] = "News checked; no injury/lineup headline."
        return
    titles = [_clean_text(item.get("title", "")) for item in articles if isinstance(item, Mapping) and item.get("title")]
    titles = [title for title in titles if title][:3]
    if not titles:
        row["news_status"] = "NO_TITLE"
        row["news_failure_reason"] = "Articles returned without usable titles"
        return
    first = titles[0][:88].rstrip() + ("…" if len(titles[0]) > 88 else "")
    row["news_status"] = "LIVE"
    row["newsapi_summary"] = "News: " + first
    row["news_summary"] = row["newsapi_summary"]
    row["news_injury_summary"] = "News: " + first


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
    return str(team_data.get("name") or team) if isinstance(team_data, Mapping) else ""


def _enrich_api_football(row: dict[str, Any]) -> None:
    if _sport_kind(row) != "soccer":
        row.setdefault("api_football_match_status", "SPORT_UNSUPPORTED")
        row.setdefault("api_football_failure_reason", "Not a soccer/FIFA row")
        return
    key = _secret(*API_SECRET_DEFS["API-Football"])
    if not key:
        row.setdefault("api_football_match_status", "API_KEY_MISSING")
        row.setdefault("api_football_failure_reason", "API-Football key missing")
        return
    away, home = _split_teams(row)
    away_result = _api_football_team_search(away, key)
    home_result = _api_football_team_search(home, key)
    if away_result or home_result:
        matched = " / ".join(part for part in (away_result or away, home_result or home) if part)
        summary = f"API-FB team lookup matched {matched}; fixture not verified."
        row["api_football_match_status"] = "TEAM_MATCHED_FIXTURE_UNVERIFIED"
    else:
        summary = f"API-FB team lookup checked {away or 'away'} / {home or 'home'}; no match returned."
        row["api_football_match_status"] = "NO_MATCH_TEAM_NAME"
        row["api_football_failure_reason"] = "Team lookup returned no match"
    row["api_football_team_summary"] = summary
    row["api_football_summary"] = summary


def _enrich_sportsdataio(row: dict[str, Any]) -> None:
    if not _secret(*API_SECRET_DEFS["SportsDataIO"]):
        row.setdefault("sportsdataio_match_status", "API_KEY_MISSING")
        row.setdefault("sportsdataio_failure_reason", "SportsDataIO key missing")
        return
    existing = _get(row, "sportsdataio_team_summary", "sportsdataio_context", "sportsdataio_injury_summary", "sportsdataio_game_summary")
    if existing:
        row["sportsdataio_match_status"] = "ROW_ALREADY_HAS_CONTEXT"
        return
    row["sportsdataio_match_status"] = "NO_PROVIDER_EVENT_ID"
    row["sportsdataio_failure_reason"] = "No provider event ID in row"
    row["sportsdataio_context"] = "SDIO checked; no provider event ID in row."
    row["sportsdataio_team_summary"] = row["sportsdataio_context"]


def _enrich_perplexity(row: dict[str, Any]) -> None:
    existing = _get(row, "perplexity_context", "perplexity_summary", "pplx_context", "pplx_summary")
    if _useful(existing):
        row["perplexity_status"] = "LIVE"
        row["perplexity_context"] = existing
        return
    key = _secret(*API_SECRET_DEFS["Perplexity"])
    if not key:
        row["perplexity_status"] = "API_KEY_MISSING"
        row["perplexity_failure_reason"] = "Perplexity key missing"
        return
    event = _get(row, "public_event", "event", "event_name", "matchup", "game")
    pick = _get(row, "public_pick", "prediction", "pick", "selection", "recommended_action")
    if not event and not pick:
        row["perplexity_status"] = "NO_QUERY"
        row["perplexity_failure_reason"] = "No event/pick query available"
        return
    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "Write one concise sports research sentence. Do not invent unverified injury, lineup, or odds data."},
            {"role": "user", "content": f"Event: {event}. Pick: {pick}. Sport/league: {_get(row, 'sport', 'league')}. Give concise context only."},
        ],
        "max_tokens": 80,
        "temperature": 0.1,
    }
    data = _request_post_json("https://api.perplexity.ai/chat/completions", payload, headers={"Authorization": f"Bearer {key}"}, cache_key=("perplexity", _event_key(row)))
    if isinstance(data, Mapping) and data.get("_error"):
        row["perplexity_status"] = "API_ERROR"
        row["perplexity_failure_reason"] = str(data.get("_error"))
        return
    content = ""
    choices = data.get("choices") if isinstance(data, Mapping) else None
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") if isinstance(choices[0], Mapping) else None
        if isinstance(msg, Mapping):
            content = _clean_text(msg.get("content") or "")
    if _useful(content):
        row["perplexity_status"] = "LIVE"
        row["perplexity_context"] = content[:260]
    else:
        row["perplexity_status"] = "NO_LIVE_CONTEXT_RETURNED"
        row["perplexity_failure_reason"] = "Perplexity returned no usable context for this row"


def _probability(row: Mapping[str, Any]) -> tuple[float | None, str]:
    for key in ("learned_model_probability", "model_probability_clean", "model_probability", "final_probability", "probability", "confidence"):
        value = _safe_float(row.get(key))
        if value is not None:
            value = value / 100 if abs(value) > 1 else value
            if 0 <= value <= 1:
                return value, key
    return None, "MISSING"


def _decimal_odds(row: Mapping[str, Any]) -> tuple[float | None, str]:
    for key in ("decimal_odds", "decimal_price", "best_price", "average_price", "avg_price", "odds_decimal", "odds_at_pick"):
        value = _safe_float(row.get(key))
        if value is not None and value > 1:
            return value, key
    american = _safe_float(row.get("american_odds") or row.get("odds_american") or row.get("odds"))
    if american is not None and abs(american) >= 100:
        decimal = (american / 100 + 1) if american > 0 else (100 / abs(american) + 1)
        return decimal, "american_odds"
    return None, "MISSING"


def _american_from_decimal(decimal: float | None) -> str:
    if decimal is None:
        return ""
    if decimal >= 2:
        return f"+{round((decimal - 1) * 100):.0f}"
    return f"-{round(100 / max(decimal - 1, 0.001)):.0f}"


def _bad_context(value: Any, row: Mapping[str, Any]) -> bool:
    text = _clean_text(value).lower()
    if not text:
        return True
    if _sport_kind(row) != "combat" and any(token in text for token in WRONG_SPORT_TOKENS):
        return True
    return not _useful(text)


def _split_sentences(value: Any) -> list[str]:
    text = _clean_text(value)
    if not text:
        return []
    return [_clean_text(part).strip(" .•-") for part in re.split(r"(?:\n|•|;|\s+-\s+|(?<=[.!?])\s+)", text) if _clean_text(part).strip(" .•-")]


def _shorten(text: str, max_chars: int = 86) -> str:
    text = _clean_text(text)
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars - 1].rsplit(" ", 1)[0].strip()
    return (cut or text[: max_chars - 1]).rstrip(".,;:") + "…"


def _clean_items(row: Mapping[str, Any], values: Iterable[Any], *, limit: int = 3, max_chars: int = 86) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        for sentence in _split_sentences(value):
            if _bad_context(sentence, row):
                continue
            item = _shorten(sentence, max_chars=max_chars)
            key = item.lower()
            if key and key not in seen:
                out.append(item)
                seen.add(key)
            if len(out) >= limit:
                return out
    return out


def resolve_magazine_context(row: Mapping[str, Any]) -> tuple[str, str]:
    for source, key in (("Perplexity", "perplexity_context"), ("Perplexity", "perplexity_summary"), ("NewsAPI", "newsapi_summary"), ("NewsAPI", "news_summary"), ("WeatherAPI", "weather_summary"), ("Input", "sports_context_summary"), ("Input", "preview_summary"), ("Input", "game_summary"), ("Input", "short_reason")):
        value = row.get(key)
        if not _bad_context(value, row):
            return source, _shorten(str(value), 180)
    reasons = [str(row.get(k)) for k in ("perplexity_failure_reason", "news_failure_reason", "api_football_failure_reason", "sportsdataio_failure_reason", "weather_failure_reason", "odds_failure_reason") if row.get(k)]
    return "EMPTY_WITH_REASON", "Context unavailable because: " + ("; ".join(reasons[:3]) or "no live context returned by configured sources") + "."


def _apply_odds_truth(row: dict[str, Any], refresh_time: str) -> None:
    prob, prob_source = _probability(row)
    decimal, decimal_source = _decimal_odds(row)
    row["model_probability_source"] = row.get("model_probability_source") or prob_source
    row["confidence_source"] = row.get("confidence_source") or prob_source
    row["confidence_status"] = "LIVE_OR_INPUT" if prob is not None else "MISSING"
    if prob is not None:
        row["model_probability"] = prob
    live_marker = str(row.get("odds_status") or row.get("odds_source") or row.get("odds_api_status") or "").strip().lower()
    live_odds = live_marker in {"live", "live_api", "odds api", "the odds api", "live_source"}
    if not _secret(*API_SECRET_DEFS["Odds API"]):
        row.setdefault("odds_api_status", "API_KEY_MISSING")
    elif not live_odds:
        row.setdefault("odds_api_status", "CONFIGURED_NO_LIVE_MATCH")
    if decimal is None:
        row["odds_status"] = "MISSING"
        row["odds_source"] = "MISSING"
        row["odds_failure_reason"] = f"No usable decimal odds field found; checked {decimal_source}."
        row["ev_status"] = "UNVERIFIED_ODDS_MISSING"
        return
    row["decimal_odds"] = decimal
    row["decimal_price"] = decimal
    row["american_odds"] = row.get("american_odds") or row.get("odds_american") or _american_from_decimal(decimal)
    row["raw_implied_probability"] = 1 / decimal
    row["market_probability"] = 1 / decimal
    row["odds_status"] = "LIVE" if live_odds else "UPLOADED_ROW"
    row["odds_source"] = "LIVE_API" if live_odds else "UPLOADED_ROW"
    if live_odds:
        row["odds_last_refresh"] = row.get("odds_last_refresh") or refresh_time
    else:
        row["odds_failure_reason"] = row.get("odds_failure_reason") or "No live Odds API match; using uploaded row price."
    if prob is not None:
        edge = prob - (1 / decimal)
        ev = prob * decimal - 1
        row["edge"] = edge
        row["model_market_edge"] = edge
        row["EV"] = ev
        row["expected_value_per_unit"] = ev
        row["fair_odds"] = 1 / prob if prob > 0 else ""
        row["ev_status"] = "RECALCULATED"
        row["ev_source"] = "LIVE" if live_odds else "FALLBACK_CALCULATED"
        row.setdefault("recommendation_status", "BET CANDIDATE" if ev > 0 and live_odds else "WATCHLIST")
        row.setdefault("final_decision", "BET CANDIDATE" if ev > 0 and live_odds else "WATCHLIST")
    else:
        row["ev_status"] = "UNVERIFIED_MODEL_PROBABILITY_MISSING"


def _apply_truth_fields(row: dict[str, Any], report_run_id: str, refresh_time: str) -> None:
    row["event_key"] = row.get("event_key") or _event_key(row)
    row["raw_input_hash"] = row.get("raw_input_hash") or _hash_payload({k: v for k, v in row.items() if not str(k).startswith("_")})
    row["enrichment_input_hash"] = row.get("enrichment_input_hash") or _hash_payload({"event_key": row.get("event_key"), "api_health": check_api_health(True)})
    row["report_source"] = "final_enriched_picks_df"
    row["report_run_id"] = report_run_id
    row["last_api_refresh_time"] = refresh_time
    row["cache_status"] = row.get("cache_status") or "LIVE_REFRESH"
    row["data_freshness_status"] = row.get("data_freshness_status") or "CURRENT_REPORT_RUN"
    row["enrichment_status"] = row.get("enrichment_status") or "FINAL_ENRICHED"
    _apply_odds_truth(row, refresh_time)
    source, context = resolve_magazine_context(row)
    row["context_source"] = source
    row["context_status"] = "LIVE_OR_SOURCE_BACKED" if source != "EMPTY_WITH_REASON" else "EMPTY_WITH_REASON"
    if source == "EMPTY_WITH_REASON":
        row["context_failure_reason"] = context
    for key in ("sports_context_summary", "preview_summary", "game_summary", "short_reason"):
        if _bad_context(row.get(key), row):
            row[key] = context
    fallback = row.get("odds_status") != "LIVE" or source == "EMPTY_WITH_REASON"
    row["fallback_used"] = str(bool(fallback))
    if fallback:
        parts = []
        if row.get("odds_status") != "LIVE":
            parts.append(f"odds_status={row.get('odds_status')}")
        if source == "EMPTY_WITH_REASON":
            parts.append("context_empty")
        row["fallback_reason"] = row.get("fallback_reason") or "; ".join(parts)
    row["field_provenance_json"] = json.dumps({"report_source": "final_enriched_picks_df", "odds": row.get("odds_source"), "ev": row.get("ev_source") or row.get("ev_status"), "context": source}, sort_keys=True)
    row["source_trace_json"] = json.dumps({"report_run_id": report_run_id, "event_key": row.get("event_key"), "fallback_used": row.get("fallback_used"), "fallback_reason": row.get("fallback_reason")}, sort_keys=True)
    row["api_health_json"] = json.dumps(check_api_health(True), sort_keys=True)
    row["api_sources_active"] = " · ".join([name for name, data in check_api_health(True).items() if data.get("status") == "CONFIGURED"])


def _render_cleanup(row_like: Any) -> dict[str, Any]:
    row = _row(row_like)
    for key, value in list(row.items()):
        if isinstance(value, str):
            row[key] = _clean_text(value)
    matchup_items = _renderer_matchup_items(row)
    row["matchup_notes"] = "\n".join(matchup_items)
    source, context = resolve_magazine_context(row)
    if _bad_context(row.get("sports_context_summary"), row):
        row["sports_context_summary"] = context if not _bad_context(context, row) else matchup_items[-1]
    odds_status = str(row.get("odds_status") or row.get("odds_source") or "").strip().upper()
    ev = _safe_float(row.get("expected_value_per_unit") or row.get("EV") or row.get("ev") or row.get("expected_value"))
    if odds_status != "LIVE":
        row["risk"] = "FALLBACK MODE"
        row["risk_level"] = "FALLBACK MODE"
        row["risk_label"] = "FALLBACK MODE"
        row["why_lose"] = "Fallback data used.\nVerify live odds before betting.\nDo not play until the price is confirmed."
        row["risk_notes"] = row["why_lose"]
        row["final_decision"] = "WATCHLIST"
    elif ev is not None and ev < 0:
        row["risk"] = "NEGATIVE EV"
        row["risk_level"] = "NEGATIVE EV"
        row["risk_label"] = "NEGATIVE EV"
        row["why_lose"] = "Negative edge at current price.\nDo not play unless price improves.\nRecheck odds and key news."
        row["risk_notes"] = row["why_lose"]
        row["final_decision"] = "WATCHLIST"
    if ev is not None and ev < 0:
        row["chain_notes"] = "No parlay recommended.\nNot enough compatible selections.\nVerified odds or edge are not positive."
    return row


def _renderer_team_items(row_like: Any, side: str = "") -> list[str]:
    row = _row(row_like)
    keys = (f"{side}_team_form", f"{side}_team_record", f"{side}_recent_results", f"{side}_sportsdataio_team_summary", f"{side}_api_football_team_summary", "team_stats_summary", "recent_results", "news_summary", "newsapi_summary", "perplexity_context")
    values = [row.get(key) for key in keys]
    items = _clean_items(row, values, limit=3, max_chars=62)
    return items or ["Team data not matched to a live provider.", "Verify lineup/news before entry."]


def _renderer_injury_items(row_like: Any, prefix: str) -> list[str]:
    row = _row(row_like)
    keys = (f"{prefix}_injuries", f"{prefix}_injury_report", f"{prefix}_lineup_status", f"{prefix}_player_notes", "injury_report", "injuries", "lineup_status", "key_players", "sportsdataio_injury_summary", "api_football_lineup_summary", "news_injury_summary", "perplexity_context")
    values = [row.get(key) for key in keys]
    items = _clean_items(row, values, limit=2, max_chars=66)
    return items or ["No verified lineup/injury note returned.", "Verify before betting."]


def _renderer_matchup_items(row_like: Any) -> list[str]:
    row = _row(row_like)
    keys = ("perplexity_context", "perplexity_summary", "newsapi_summary", "news_summary", "weather_summary", "sports_context_summary", "preview_summary", "game_summary", "short_reason", "matchup_note", "matchup_notes")
    values = [row.get(key) for key in keys]
    items = _clean_items(row, values, limit=3, max_chars=82)
    odds_status = str(row.get("odds_status") or row.get("odds_source") or "").strip().upper()
    if odds_status and odds_status != "LIVE" and not any("odds" in item.lower() for item in items):
        items.insert(0, "Odds are not live; verify current price before betting.")
    return (items or ["Live context was not returned; verify odds and news before entry."])[:3]


def _renderer_pairs(row_like: Any, lang: str) -> list[tuple[str, str]]:
    row = _row(row_like)
    return [("REPORT SOURCE", _get(row, "report_source", default="final_enriched_picks_df")), ("ODDS ROW", _get(row, "odds_source", default="UPLOADED_ROW")), ("CONTEXT", _get(row, "context_source", default="EMPTY_WITH_REASON")), ("RUN", _get(row, "report_run_id", default="no_run_id")[:22]), ("REFRESH", _get(row, "last_api_refresh_time", default="no_refresh")[:22])]


def _is_spanish(row: Mapping[str, Any]) -> bool:
    text = _get(row, "report_language", "language", "lang").lower()
    return text.startswith("es") or "spanish" in text or "español" in text or "espanol" in text


def _tr_es(value: Any) -> str:
    text = _clean_text(value)
    if text in ES:
        return ES[text]
    m = re.fullmatch(r"PAGE\s+(\d+)\s+OF\s+(\d+)", text, flags=re.I)
    if m:
        return f"PÁGINA {m.group(1)} DE {m.group(2)}"
    replacements = (
        ("Model projects", "El modelo proyecta"),
        ("Market-implied probability checks at", "La probabilidad implícita del mercado es"),
        ("Measured edge", "Ventaja medida"),
        ("Expected value", "Valor esperado"),
        ("Negative edge at current price", "Ventaja negativa con la cuota actual"),
        ("Do not play unless price improves", "No jugar salvo que la cuota mejore"),
        ("Recheck odds and key news", "Revisar cuotas y noticias clave"),
        ("Do not chain negative-EV picks", "No encadenar señales con VE negativo"),
        ("Avoid parlays unless edge turns positive", "Evitar parlays salvo que la ventaja sea positiva"),
        ("Recheck price before including", "Revisar la cuota antes de incluir"),
        ("Do not play at the listed price", "No jugar con la cuota listada"),
    )
    for old, new in replacements:
        text = re.sub(re.escape(old), new, text, flags=re.I)
    return text


def _fmt_pct(value: Any, signed: bool = False) -> str:
    parsed = _safe_float(value)
    if parsed is None:
        return ""
    parsed = parsed / 100 if abs(parsed) > 1 else parsed
    return f"{parsed:+.1%}" if signed else f"{parsed:.0%}"


def _fmt_ev(value: Any) -> str:
    parsed = _safe_float(value)
    return "" if parsed is None else f"{parsed:+.3f}"


def _apply_spanish(row: dict[str, Any]) -> dict[str, Any]:
    if not _is_spanish(row):
        return row
    pick = _get(row, "public_pick", "prediction", "pick", "selection", default="esta selección")
    row["final_decision"] = _tr_es(row.get("final_decision", "")) or row.get("final_decision", "")
    row["bookmaker"] = _tr_es(row.get("bookmaker", "")) or row.get("bookmaker", "")
    for key in ("news_injury_summary", "api_football_summary", "why_lose", "risk_reason", "chain_notes", "parlay_notes", "final_explanation", "final_decision", "bookmaker"):
        if key in row and isinstance(row[key], str):
            row[key] = _tr_es(row[key])
    row["why_bullets"] = "\n".join([
        f"El modelo proyecta {_fmt_pct(_get(row, 'learned_model_probability', 'model_probability_clean', 'model_probability', 'final_probability'))} de probabilidad para {pick}.",
        f"La probabilidad implícita del mercado es {_fmt_pct(_get(row, 'market_probability', 'market_implied_probability'))}.",
        f"Ventaja medida: {_fmt_pct(_get(row, 'model_market_edge', 'edge'), signed=True)}.",
        f"Valor esperado: {_fmt_ev(_get(row, 'expected_value_per_unit', 'profit_expected_value', 'expected_value', 'ev'))}.",
    ])
    row.setdefault("final_explanation", "No jugar con la cuota listada. Revisar si mejora la línea.")
    if "No jugar con la cuota listada" not in str(row.get("final_explanation", "")):
        row["final_explanation"] = str(row.get("final_explanation", "")) + "\nNo jugar con la cuota listada."
    return row


def _install_spanish_renderer_patch() -> None:
    try:
        import autonomous_betting_agent.magazine_book_export as module
    except Exception:
        return
    original = getattr(module, "_tr", None)
    if callable(original) and getattr(original, "_aba_live_es_patch", False):
        return

    def patched_tr(value: Any, lang: str) -> str:
        if str(lang).lower().startswith("es"):
            return _tr_es(value)
        return original(value, lang) if callable(original) else _clean_text(value)

    setattr(patched_tr, "_aba_live_es_patch", True)
    module._tr = patched_tr


def enrich_row_with_live_api_data(row_like: Any, *, report_run_id: str | None = None, last_api_refresh_time: str | None = None) -> dict[str, Any]:
    row = _row(row_like)
    if row.get("_live_api_enriched") == ENRICHMENT_VERSION and row.get("report_source") == "final_enriched_picks_df":
        return _apply_spanish(_render_cleanup(row))
    report_run_id = report_run_id or f"aba_mag_{int(time.time())}_{_hash_payload(row)}"
    last_api_refresh_time = last_api_refresh_time or datetime.now(timezone.utc).isoformat(timespec="seconds")
    _enrich_sportsdataio(row)
    _enrich_weather(row)
    _enrich_api_football(row)
    _enrich_news(row)
    _enrich_perplexity(row)
    _apply_truth_fields(row, report_run_id, last_api_refresh_time)
    row["_live_api_enriched"] = ENRICHMENT_VERSION
    _install_spanish_renderer_patch()
    return _apply_spanish(_render_cleanup(row))


def _report_page_priority(row: Mapping[str, Any]) -> int:
    lane = _get(row, "report_lane", "report_lane_v2").lower()
    action = _get(row, "consumer_action", "recommended_action", "public_action").lower()
    ready = _get(row, "official_publish_ready", "publish_ready").lower() in {"true", "1", "yes"}
    return 0 if ready or "official" in action or lane in {"best_play", "best play"} else 1


def _dedupe_report_page_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not any(_get(row, "report_language", "language", "lang") for row in rows):
        return rows
    unique: list[dict[str, Any]] = []
    index: dict[str, int] = {}
    priority: dict[str, int] = {}
    for row in rows:
        key = _event_key(row)
        p = _report_page_priority(row)
        if key in index:
            if p < priority[key]:
                unique[index[key]] = row
                priority[key] = p
            continue
        index[key] = len(unique)
        priority[key] = p
        unique.append(row)
    return unique


def enrich_rows_with_live_api_data(rows: list[Any] | tuple[Any, ...]) -> list[dict[str, Any]]:
    report_run_id, refresh_time = _new_run_meta(rows)
    enriched = _dedupe_report_page_rows([enrich_row_with_live_api_data(row, report_run_id=report_run_id, last_api_refresh_time=refresh_time) for row in rows])
    _ensure_renderer_patch()
    _install_spanish_renderer_patch()
    return enriched


def build_final_enriched_picks_df(raw_picks_df: Any, force_refresh: bool = False) -> Any:
    if force_refresh:
        _CACHE.clear()
    try:
        import pandas as pd  # type: ignore
        frame = raw_picks_df.copy() if hasattr(raw_picks_df, "copy") else pd.DataFrame(raw_picks_df)
        return pd.DataFrame(enrich_rows_with_live_api_data(frame.to_dict("records")))
    except Exception:
        return enrich_rows_with_live_api_data(list(raw_picks_df or []))


def install(module: Any) -> Any:
    if getattr(module, "_LIVE_API_ENRICHMENT_PATCHED_VERSION", "") == ENRICHMENT_VERSION:
        return module
    original_render = getattr(module, "render_full_pick_magazine_page", None)
    original_png = getattr(module, "_png", None)
    original_metric_cells = getattr(module, "magazine_metric_cells", None)
    if callable(original_metric_cells):
        def metric_cells(odds: str, conf: str, edge: str, ev: str, units: str, risk: str):
            cells = list(original_metric_cells(odds, conf, edge, ev, units, risk))
            fixed = []
            risk_text = str(risk or "").upper()
            danger = getattr(module, "DANGER", (225, 67, 62))
            green = getattr(module, "GREEN", (61, 205, 84))
            cream = getattr(module, "CREAM", (255, 248, 230))
            for label, value, color, x, width in cells:
                if str(label).upper() == "RISK":
                    if any(token in risk_text for token in ("LIVE", "VOLUME OK", "SAFE")):
                        color = green
                    elif any(token in risk_text for token in ("FALLBACK", "NEG", "MISSING", "WATCH", "NO")):
                        color = danger
                    else:
                        color = cream
                fixed.append((label, value, color, x, width))
            return fixed
        module.magazine_metric_cells = metric_cells
    if callable(original_render):
        def render(row_like: Any, *args: Any, **kwargs: Any):
            return original_render(_render_cleanup(enrich_row_with_live_api_data(row_like)), *args, **kwargs)
        module.render_full_pick_magazine_page = render
    if callable(original_png) and callable(getattr(module, "render_full_pick_magazine_page", None)):
        def render_png(row_like: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
            return original_png(module.render_full_pick_magazine_page(row_like, background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))
        module.render_full_pick_magazine_page_png = render_png
    module._useful = _useful
    module._team_items = _renderer_team_items
    module._injury_items = _renderer_injury_items
    module._matchup_items = _renderer_matchup_items
    module._pairs = _renderer_pairs
    module.enrich_row_with_live_api_data = enrich_row_with_live_api_data
    module.enrich_rows_with_live_api_data = enrich_rows_with_live_api_data
    module.build_final_enriched_picks_df = build_final_enriched_picks_df
    module.check_api_health = check_api_health
    module._LIVE_API_ENRICHMENT_VERSION = ENRICHMENT_VERSION
    module._LIVE_API_ENRICHMENT_PATCHED_VERSION = ENRICHMENT_VERSION
    if ENRICHMENT_VERSION not in str(getattr(module, "MAGAZINE_STYLE_VERSION", "")):
        module.MAGAZINE_STYLE_VERSION = f"{module.MAGAZINE_STYLE_VERSION}_{ENRICHMENT_VERSION}"
    _install_spanish_renderer_patch()
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
