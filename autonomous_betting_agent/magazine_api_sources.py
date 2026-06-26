from __future__ import annotations

import builtins
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, is_dataclass
from typing import Any

API_SOURCE_DEFS = (
    ("Odds API", ("odds_api_live", "the_odds_api_live", "odds_api_enabled"), ("odds_api_summary", "live_odds_summary", "odds_api_context"), ("odds_source", "bookmaker", "sportsbook", "decimal_price", "odds", "best_price", "market_probability"), True),
    ("SportsDataIO", ("sportsdataio_live", "sportsdataio_enabled"), ("sportsdataio_team_summary", "sportsdataio_context", "sportsdataio_injury_summary", "sportsdataio_game_summary"), (), False),
    ("WeatherAPI", ("weatherapi_live", "weather_live", "weather_enabled"), ("weather_summary", "weather_location", "weather_risk", "venue_weather"), (), False),
    ("API-Football", ("api_football_live", "api_football_enabled"), ("api_football_summary", "api_football_context", "api_football_team_summary", "api_football_lineup_summary"), (), False),
    ("Perplexity", ("perplexity_live", "perplexity_enabled"), ("perplexity_summary", "perplexity_context", "perplexity_news_context"), (), True),
    ("NewsAPI", ("newsapi_live", "newsapi_enabled"), ("newsapi_summary", "news_summary", "news_injury_summary", "breaking_news_summary"), (), False),
)
API_SECRET_DEFS = {
    "Odds API": ("ODDS_API_KEY", "THE_ODDS_API_KEY"),
    "SportsDataIO": ("SPORTSDATAIO_API_KEY", "SPORTS_DATA_IO_API_KEY", "SPORTSDATA_API_KEY"),
    "WeatherAPI": ("WEATHERAPI_KEY", "WEATHER_API_KEY"),
    "API-Football": ("API_FOOTBALL_KEY", "APIFOOTBALL_KEY"),
    "Perplexity": ("PERPLEXITY_API_KEY", "PPLX_API_KEY"),
    "NewsAPI": ("NEWSAPI_KEY", "NEWS_API_KEY"),
}
API_SHORT_LABELS = {
    "Odds API": "Odds",
    "SportsDataIO": "SDIO",
    "WeatherAPI": "Weather",
    "API-Football": "API-FB",
    "Perplexity": "PPLX",
    "NewsAPI": "News",
}
API_SUMMARY_KEY_FRAGMENTS = ("api", "sportsdataio", "weather", "news", "perplexity")
_CURRENT_ROW: Mapping[str, Any] | None = None


def _row(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict"):
        data = value.to_dict()
        return data if isinstance(data, Mapping) else {}
    return getattr(value, "__dict__", {}) or {}


def _bad(value: Any) -> bool:
    return value is None or str(value).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


def _useful(value: Any) -> bool:
    if _bad(value):
        return False
    text = str(value).strip().lower()
    if text in {"false", "0", "no", "not available", "unavailable", "data unavailable", "none available"}:
        return False
    return not any(token in text for token in ("api key missing", "payment required"))


def _truthy(value: Any) -> bool | None:
    if _bad(value):
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "live", "active", "enabled", "ok", "available"}:
        return True
    if text in {"0", "false", "no", "n", "inactive", "disabled", "failed", "unavailable", "missing", "unpaid", "payment_required"}:
        return False
    return None


def _split(value: Any) -> list[str]:
    if _bad(value):
        return []
    return [p.strip(" -•") for p in str(value).replace("•", "\n").replace(";", "\n").replace("|", "\n").splitlines() if p.strip(" -•")]


def _dedupe(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = re.sub(r"\s+", " ", str(item or "").strip())
        key = text.lower().replace("the ", "")
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def short_api_name(name: str) -> str:
    return API_SHORT_LABELS.get(str(name), str(name))


def short_api_list(names: Iterable[str]) -> str:
    return " · ".join(short_api_name(name) for name in names)


def _secret_value(names: Iterable[str]) -> str:
    names = tuple(names)
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
        secrets = getattr(st, "secrets", {})
        for name in names:
            try:
                value = str(secrets.get(name, "") or "").strip()
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


def configured_api_sources() -> list[str]:
    return [name for name, *_ in API_SOURCE_DEFS if _secret_value(API_SECRET_DEFS.get(name, ())) ]


def _configured(name: str) -> bool:
    return bool(_secret_value(API_SECRET_DEFS.get(name, ())))


def _any_useful(row: Any, keys: Iterable[str]) -> bool:
    data = _row(row)
    return any(_useful(data.get(key)) for key in keys)


def _name_matches(name: str, values: Iterable[str]) -> bool:
    target = name.lower().replace("the ", "")
    return any(target in value.lower().replace("the ", "") for value in values)


def api_provenance(row: Any) -> dict[str, list[str]]:
    data = _row(row)
    explicit_active = _split(data.get("api_sources_active") or data.get("api_sources_used"))
    explicit_inactive = _split(data.get("api_sources_inactive"))
    active: list[str] = []
    no_data: list[str] = []
    inactive: list[str] = []
    for name, live_keys, data_keys, support_keys, requires_live in API_SOURCE_DEFS:
        live_values = [_truthy(data.get(key)) for key in live_keys if key in data]
        live = next((value for value in live_values if value is not None), None)
        primary = _any_useful(row, data_keys)
        support = _any_useful(row, support_keys)
        configured = _configured(name)
        if _name_matches(name, explicit_inactive) or live is False:
            inactive.append(name)
        elif _name_matches(name, explicit_active):
            active.append(name)
        elif requires_live:
            if primary or live is True:
                active.append(name)
            elif configured or support:
                no_data.append(name)
            else:
                inactive.append(name)
        elif primary or configured or live is True:
            active.append(name)
        else:
            inactive.append(name)
    active = _dedupe(active)
    no_data = _dedupe(name for name in no_data if name not in active)
    inactive = _dedupe(name for name in inactive if name not in active and name not in no_data)
    return {"active_sources": active, "available_no_data_sources": no_data, "inactive_sources": inactive}


def api_provenance_lines(row: Any) -> list[str]:
    prov = api_provenance(row)
    lines: list[str] = []
    if prov["active_sources"]:
        lines.append("Active: " + short_api_list(prov["active_sources"]))
    if prov["available_no_data_sources"]:
        lines.append("No live: " + short_api_list(prov["available_no_data_sources"]))
    if prov["inactive_sources"]:
        lines.append("Inactive: " + short_api_list(prov["inactive_sources"]))
    return lines


def sport_kind(row: Any) -> str:
    data = _row(row)
    text = " ".join(str(data.get(key, "")) for key in ("sport", "league", "event", "game", "matchup", "event_name")).lower()
    if any(token in text for token in ("mma", "ufc", "boxing", "fighter")):
        return "combat"
    if any(token in text for token in ("soccer", "fifa", "football", "world cup", "uefa", "liga")):
        return "soccer"
    if any(token in text for token in ("mlb", "baseball", "dodgers", "twins", "yankees")):
        return "baseball"
    return "generic"


def _blocked_terms() -> tuple[str, ...]:
    return ("api-" + "mma", "fight" + " news", "weight" + " cut", "camp" + " updates")


def filter_sport_text(items: Iterable[str], row: Any) -> list[str]:
    if sport_kind(row) == "combat":
        return [str(item) for item in items if _useful(item)]
    return [str(item) for item in items if _useful(item) and not any(term in str(item).lower() for term in _blocked_terms())]


def _get(row: Any, *keys: str, default: str = "") -> str:
    data = _row(row)
    for key in keys:
        value = data.get(key)
        if not _bad(value):
            return str(value).strip()
    return default


def _teams(row: Any) -> tuple[str, str]:
    away = _get(row, "away_team", "team_a", "team1")
    home = _get(row, "home_team", "team_b", "team2")
    if away and home:
        return away, home
    event = _get(row, "event", "game", "event_name", "matchup")
    for sep in (" at ", " vs ", " VS ", " v ", " @ "):
        if sep in event:
            left, right = event.split(sep, 1)
            return left.strip(), right.strip()
    return _get(row, "team", default="away team"), _get(row, "opponent", default="home team")


def _candidate_location(row: Any) -> str:
    explicit = _get(row, "weather_location", "venue_weather_location", "venue", "event_location", "location", "city")
    if explicit:
        return explicit
    joined = " | ".join(str(_row(row).get(key, "")) for key in ("venue_note", "matchup_note", "matchup_notes", "sports_context_summary", "weather_summary", "event", "event_name"))
    patterns = (
        r"([A-Z][A-Za-z .'-]+,\s*[A-Z][A-Za-z .'-]+,\s*(?:USA|United States|United States of America|Mexico|Canada))",
        r"([A-Z][A-Za-z .'-]+,\s*(?:USA|United States|United States of America|Mexico|Canada))",
    )
    for pattern in patterns:
        match = re.search(pattern, joined)
        if match:
            return match.group(1).strip(" .")
    return ""


def _news_query(row: Any) -> str:
    away, home = _teams(row)
    sport = _get(row, "sport", "league")
    terms = "injury camp news" if sport_kind(row) == "combat" else "injury lineup news odds"
    return " ".join(part for part in (away, home, sport, terms) if part).strip()


def _api_fb_lookup_text(row: Any, matched: bool) -> str:
    away, home = _teams(row)
    if matched:
        return f"API-FB team lookup matched {away} / {home}; fixture not verified."
    return f"API-FB team lookup checked {away} / {home}; no match returned."


def _compact_weather_message(text: str) -> list[str]:
    value = re.sub(r"\s+", " ", text).strip()
    if value.startswith("WeatherAPI:"):
        body = value.split(":", 1)[1].strip()
        location = ""
        if " Location: " in body:
            body, location = body.split(" Location: ", 1)
            location = location.rstrip(".")
        bits = [part.strip(" .") for part in body.split(";") if part.strip(" .")]
        weather = "Weather: " + ", ".join(bits[:3]) + "."
        out = [weather]
        if location:
            out.append("Location: " + location + ".")
        return out
    if value.startswith("WeatherAPI checked"):
        location = value.replace("WeatherAPI checked", "", 1).split(";", 1)[0].strip()
        return [f"Weather checked: {location}; no live payload."] if location else ["Weather checked; no live payload."]
    if value.startswith("WeatherAPI configured"):
        return ["Weather checked; no venue/location in row."]
    return [value]


def compact_api_message(text: Any, row: Any, area: str = "team") -> list[str]:
    value = re.sub(r"\s+", " ", str(text or "").strip())
    if not value:
        return []
    low = value.lower()
    if low.startswith("sportsdataio configured") or low.startswith("sdio checked"):
        return ["SDIO checked; no provider event ID in row."]
    if low.startswith("api-football:") or low.startswith("api-fb team lookup matched"):
        return [_api_fb_lookup_text(row, matched=True)]
    if low.startswith("api-football checked") or low.startswith("api-fb team lookup checked"):
        return [_api_fb_lookup_text(row, matched=False)]
    if low.startswith("weatherapi"):
        return _compact_weather_message(value)
    if low.startswith("weather:") or low.startswith("weather checked"):
        return _compact_weather_message(value.replace("Weather:", "WeatherAPI:", 1) if value.startswith("Weather:") else value)
    if low.startswith("location:"):
        return [value]
    if low.startswith("newsapi:"):
        title = value.split(":", 1)[1].strip().split(" | ", 1)[0]
        title = title[:88].rstrip() + ("…" if len(title) > 88 else "")
        return ["News: " + title] if title else ["News checked; no recent matching articles."]
    if low.startswith("newsapi checked") or low.startswith("news checked"):
        if area in {"team", "injury"} or "injury" in low or "lineup" in low:
            return ["News checked; no injury/lineup headline."]
        return ["News checked; no recent matching articles."]
    return [value]


def _compact_items(items: Iterable[str], row: Any, area: str, limit: int) -> list[str]:
    compacted: list[str] = []
    for item in items:
        compacted.extend(compact_api_message(item, row, area))
    return _dedupe(filter_sport_text(compacted, row))[:limit]


def _api_checked_details(row: Any, area: str) -> list[str]:
    prov = api_provenance(row)
    active = set(prov["active_sources"])
    kind = sport_kind(row)
    details: list[str] = []
    if "SportsDataIO" in active:
        details.append("SDIO checked; no provider event ID in row.")
    if "API-Football" in active and kind == "soccer":
        details.append(_api_fb_lookup_text(row, matched=False))
    if "WeatherAPI" in active and area == "matchup":
        location = _candidate_location(row)
        if location:
            details.append(f"Weather checked: {location}; no live payload.")
        else:
            details.append("Weather checked; no venue/location in row.")
    if "NewsAPI" in active:
        if area in {"team", "injury"}:
            details.append("News checked; no injury/lineup headline.")
        else:
            details.append("News checked; no recent matching articles.")
    return _dedupe(details)


def _active_note(row: Any) -> str:
    active = short_api_list(api_provenance(row)["active_sources"])
    return f"Active APIs checked: {active}." if active else "No active API source was detected for this row."


def _team_fallback(row: Any) -> list[str]:
    checked = _api_checked_details(row, "team")
    return (checked + ["Team form payload not returned by active APIs."]) if checked else ["Data not returned for this event", _active_note(row)]


def _injury_fallback(row: Any) -> list[str]:
    checked = _api_checked_details(row, "injury")
    return (checked + ["Lineup payload not returned by active APIs."]) if checked else ["Player data not returned for this event", _active_note(row)]


def _matchup_fallback(row: Any) -> list[str]:
    checked = _api_checked_details(row, "matchup")
    return checked or ["Context unavailable.", _active_note(row), "Recheck price before publishing."]


def _values_for_key(data: Mapping[str, Any], key: str) -> list[str]:
    value = data.get(key)
    if _bad(value):
        return []
    if any(fragment in key.lower() for fragment in API_SUMMARY_KEY_FRAGMENTS):
        return [str(value)]
    return _split(value)


def _items_from_keys(row: Any, keys: Iterable[str], fallback: list[str], limit: int, area: str = "team") -> list[str]:
    data = _row(row)
    out: list[str] = []
    for key in keys:
        out += _values_for_key(data, key)
    return _compact_items(out, row, area, limit) or _compact_items(fallback, row, area, limit)


def team_items(row: Any, side: str = "") -> list[str]:
    keys = (f"{side}_team_form", f"{side}_team_record", f"{side}_recent_results", f"{side}_sportsdataio_team_summary", f"{side}_api_football_team_summary", "sportsdataio_team_summary", "sportsdataio_context", "api_football_team_summary", "api_football_context", "team_stats_summary", "home_team_form", "away_team_form", "recent_results", "news_summary", "newsapi_summary")
    return _items_from_keys(row, keys, _team_fallback(row), 4, "team")


def injury_items(row: Any, prefix: str) -> list[str]:
    keys = (f"{prefix}_injuries", f"{prefix}_injury_report", f"{prefix}_lineup_status", f"{prefix}_player_notes", "injury_report", "injuries", "lineup_status", "key_players", "home_injuries", "away_injuries", "sportsdataio_injury_summary", "api_football_lineup_summary", "news_injury_summary")
    return _items_from_keys(row, keys, _injury_fallback(row), 3, "injury")


def matchup_items(row: Any) -> list[str]:
    keys = ("weather_summary", "api_football_summary", "api_football_context", "newsapi_summary", "news_summary", "sportsdataio_game_summary", "sportsdataio_context", "perplexity_context", "perplexity_summary")
    return _items_from_keys(row, keys, _matchup_fallback(row), 3, "matchup")


def odds_row_label(row: Any) -> str:
    if "Odds API" in api_provenance(row)["active_sources"]:
        source = _row(row).get("odds_source") or _row(row).get("data_source")
        return str(source or "Odds API")
    source = str(_row(row).get("odds_source") or _row(row).get("data_source") or "").strip()
    if source and "odds api" not in source.lower():
        return source
    return "uploaded/cached row"


def magazine_metric_cells(odds: str, conf: str, edge: str, ev: str, units: str, risk: str, palette: Mapping[str, Any]) -> list[tuple[str, str, Any, int, int]]:
    danger, green, cream = palette["DANGER"], palette["GREEN"], palette["CREAM"]
    return [("ODDS", odds, cream, 345, 98), ("CONFIDENCE", conf, green, 443, 145), ("EDGE", edge, danger if str(edge).startswith("-") else green, 588, 112), ("EV", ev, danger if str(ev).startswith("-") else green, 700, 112), ("UNITS", units, cream, 812, 100), ("RISK", risk, green, 912, 148)]


def _title_fit_start(text: str, width: int, start: int, minimum: int) -> tuple[int, int] | None:
    clean = " ".join(str(text or "").replace("\n", " ").split())
    length = len(clean)
    if width == 590 and start >= 120 and minimum >= 70:
        if length <= 5:
            return 104, 44
        if length <= 9:
            return 88, 40
        if length <= 14:
            return 72, 36
        return 56, 28
    if width == 560 and start >= 100 and minimum >= 60:
        if length <= 6:
            return 86, 38
        if length <= 11:
            return 72, 34
        if length <= 17:
            return 58, 30
        return 46, 24
    return None


def _language_from_args(module: Any, pick: Any, args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> str:
    language = kwargs.get("language")
    if language is None and len(args) >= 11:
        language = args[10]
    return module._lang(pick, language)


def _repaint_units_risk(module: Any, img: Any, pick: Any, lang: str) -> None:
    draw = module.ImageDraw.Draw(img, "RGBA")
    draw.rectangle((812, 462, 1060, 556), fill=module.BLACK)
    units = module._fmt(module._get(pick, "recommended_stake_units", "suggested_stake_units", "units", default="1.0"), "unit")
    risk = module._tr(module._clean(module._get(pick, "risk", "risk_level", "risk_label", "profit_guard_status", default=module.NO_VERIFIED), True), lang)
    module._metric(draw, 812, 462, 100, "UNITS", units, module.CREAM, lang)
    module._metric(draw, 912, 462, 148, "RISK", risk, module.GREEN, lang)


def apply_magazine_api_patch(module: Any) -> Any:
    if getattr(module, "_DYNAMIC_API_SOURCE_PATCHED", False):
        module.api_provenance = api_provenance
        module.api_provenance_lines = api_provenance_lines
        module.configured_api_sources = configured_api_sources
        module.team_items = team_items
        module.injury_items = injury_items
        module.matchup_items = matchup_items
        module._team_items = team_items
        module._injury_items = injury_items
        module._matchup_items = matchup_items
        return module
    original_render = module.render_full_pick_magazine_page
    original_png = module._png
    original_badge = module._badge
    original_bullets = module._bullets_auto
    original_fit = module._fit
    original_metric = module._metric
    original_tr = module._tr
    original_clean = module._clean
    original_get = module._get
    original_team_label = module._team_label
    original_teams = module._teams

    def compatible_badge(img: Any, draw: Any, label: str, x: int, y: int, width: int, height: int, color: Any, *_args: Any, **_kwargs: Any) -> None:
        original_badge(img, draw, label, x, y, width, height, color)

    def patched_fit(text: str, width: int, start: int, minimum: int = 12, bold: bool = True):
        capped = _title_fit_start(text, width, start, minimum)
        if bold and capped is not None:
            capped_start, capped_minimum = capped
            return original_fit(text, width, min(start, capped_start), min(minimum, capped_minimum), bold)
        return original_fit(text, width, start, minimum, bold)

    def patched_render(pick: Any, *args: Any, **kwargs: Any):
        global _CURRENT_ROW
        previous = _CURRENT_ROW
        _CURRENT_ROW = _row(pick)
        module._badge = compatible_badge
        try:
            img = original_render(pick, *args, **kwargs)
            _repaint_units_risk(module, img, pick, _language_from_args(module, pick, args, kwargs))
            return img
        finally:
            _CURRENT_ROW = previous

    def patched_png(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
        return original_png(module.render_full_pick_magazine_page(pick, background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))

    def patched_pairs(row: Any, lang: str) -> list[tuple[str, str]]:
        prov = api_provenance(row)
        pairs = [("ODDS ROW", odds_row_label(row)), ("BOOK", original_get(row, "bookmaker", "sportsbook", default=module.NO_VERIFIED)), ("LINE", original_get(row, "line_movement", "price_movement", "market_move", default=module.NO_VERIFIED))]
        if prov["active_sources"]:
            pairs.append(("ACTIVE", short_api_list(prov["active_sources"])))
        if prov["available_no_data_sources"]:
            pairs.append(("NO LIVE", short_api_list(prov["available_no_data_sources"])))
        if prov["inactive_sources"]:
            pairs.append(("INACTIVE", short_api_list(prov["inactive_sources"])))
        return [(original_tr(label, lang), original_tr(original_clean(value), lang)) for label, value in pairs if value != module.NO_VERIFIED][:5]

    def patched_team_snapshot(img: Any, draw: Any, x: int, y: int, width: int, team: str, color: Any, lang: str, row_arg: Any | None = None, side_arg: str = "", *extra: Any, **kwargs: Any) -> None:
        row = _row(row_arg) if row_arg else (_CURRENT_ROW or {})
        away, _home = original_teams(row)
        side = side_arg or ("away" if str(team).strip().lower() == str(away).strip().lower() else "home")
        label = original_team_label(team, lang)
        compatible_badge(img, draw, label, x, y, 50, 50, color)
        draw.text((x + 66, y + 9), label.upper(), font=original_fit(label.upper(), width - 70, 25, 7, True), fill=color)
        original_bullets(draw, x, y + 76, team_items(row, side), width - 10, 165, color, 18, 10, 4, lang)

    def patched_items(row: Any, keys: Iterable[str], fallback: list[str], limit: int) -> list[str]:
        key_tuple = tuple(keys)
        if "matchup_note" in key_tuple or "sports_context_summary" in key_tuple:
            return matchup_items(row)[:limit]
        if "injury_report" in key_tuple or "lineup_status" in key_tuple:
            return injury_items(row, "away")[:limit]
        return _items_from_keys(row, key_tuple, fallback, limit, "team")

    def patched_metric(draw: Any, x: int, y: int, width: int, label: str, value: str, color: Any, lang: str) -> None:
        forbidden = {"MAR" + "KET", "MAR" + "KE", "TOT" + "ALS", "SPR" + "EADS"}
        if label.upper() in forbidden:
            return
        original_metric(draw, x, y, width, label, value, color, lang)

    module.render_full_pick_magazine_page = patched_render
    module.render_full_pick_magazine_page_png = patched_png
    module._fit = patched_fit
    module._badge = compatible_badge
    module._pairs = patched_pairs
    module._team_snapshot = patched_team_snapshot
    module._player_items = injury_items
    module._items = patched_items
    module._metric = patched_metric
    module.api_provenance = api_provenance
    module.api_provenance_lines = api_provenance_lines
    module.configured_api_sources = configured_api_sources
    module.team_items = team_items
    module.injury_items = injury_items
    module.matchup_items = matchup_items
    module._team_items = team_items
    module._injury_items = injury_items
    module._matchup_items = matchup_items
    module.magazine_metric_cells = lambda odds, conf, edge, ev, units, risk: magazine_metric_cells(odds, conf, edge, ev, units, risk, {"DANGER": module.DANGER, "GREEN": module.GREEN, "CREAM": module.CREAM})
    module.MAGAZINE_STYLE_VERSION = f"{module.MAGAZINE_STYLE_VERSION}_dynamic_api_sources_v7_compact_display"
    module._DYNAMIC_API_SOURCE_PATCHED = True
    return module
