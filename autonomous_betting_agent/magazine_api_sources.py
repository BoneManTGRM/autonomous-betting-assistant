from __future__ import annotations

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
    return not any(token in text for token in ("not returned", "not available", "no data", "api key missing", "payment required"))


def _truthy(value: Any) -> bool | None:
    if _bad(value):
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "live", "active", "enabled", "ok", "available"}:
        return True
    if text in {"0", "false", "no", "n", "inactive", "disabled", "failed", "unavailable", "missing", "unpaid"}:
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
        text = str(item).strip()
        key = text.lower().replace("the ", "")
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


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
        if _name_matches(name, explicit_inactive):
            inactive.append(name)
        elif _name_matches(name, explicit_active) or primary or (live is True and (primary or support)):
            active.append(name)
        elif live is True:
            no_data.append(name)
        elif requires_live and support:
            inactive.append(name)
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
        lines.append("Active APIs: " + " · ".join(prov["active_sources"]))
    if prov["available_no_data_sources"]:
        lines.append("No data: " + " · ".join(prov["available_no_data_sources"]))
    if prov["inactive_sources"]:
        lines.append("Inactive: " + " · ".join(prov["inactive_sources"]))
    return lines


def sport_kind(row: Any) -> str:
    data = _row(row)
    text = " ".join(str(data.get(key, "")) for key in ("sport", "league", "event", "game", "matchup")).lower()
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


def _team_fallback(row: Any) -> list[str]:
    kind = sport_kind(row)
    if kind == "soccer":
        return ["Team form data was not available from active soccer sources.", "Check lineup and news updates before publishing."]
    if kind == "baseball":
        return ["Team form data was not available from active baseball sources.", "Check lineup, bullpen, and news updates before publishing."]
    if kind == "combat":
        return ["Combat-sport profile data was not available from active sources.", "Confirm combat news before publishing."]
    return ["Data not available from uploaded row", "Use team form, injuries, and price movement before publishing."]


def _injury_fallback(row: Any) -> list[str]:
    kind = sport_kind(row)
    if kind == "soccer":
        return ["Lineup and injury data were not available from active soccer sources."]
    if kind == "baseball":
        return ["Lineup and injury data were not available from active baseball sources."]
    if kind == "combat":
        return ["Confirm combat news, injuries, and training status before betting."]
    return ["Player data not available in uploaded row", "Confirm lineup/injury news before placing the bet."]


def _items_from_keys(row: Any, keys: Iterable[str], fallback: list[str], limit: int) -> list[str]:
    data = _row(row)
    out: list[str] = []
    for key in keys:
        out += _split(data.get(key))
    return (filter_sport_text(out, row) or fallback)[:limit]


def team_items(row: Any, side: str = "") -> list[str]:
    keys = (f"{side}_team_form", f"{side}_team_record", f"{side}_recent_results", f"{side}_sportsdataio_team_summary", f"{side}_api_football_team_summary", "sportsdataio_team_summary", "sportsdataio_context", "api_football_team_summary", "api_football_context", "team_stats_summary", "home_team_form", "away_team_form", "recent_results", "news_summary", "newsapi_summary")
    return _items_from_keys(row, keys, _team_fallback(row), 4)


def injury_items(row: Any, prefix: str) -> list[str]:
    keys = (f"{prefix}_injuries", f"{prefix}_injury_report", f"{prefix}_lineup_status", f"{prefix}_player_notes", "injury_report", "injuries", "lineup_status", "key_players", "home_injuries", "away_injuries", "sportsdataio_injury_summary", "api_football_lineup_summary", "news_injury_summary")
    return _items_from_keys(row, keys, _injury_fallback(row), 3)


def matchup_items(row: Any) -> list[str]:
    keys = ("weather_summary", "venue_note", "weather_location", "weather_risk", "news_summary", "newsapi_summary", "api_football_context", "api_football_summary", "sportsdataio_context", "sportsdataio_game_summary", "sports_context_summary", "matchup_note", "matchup_notes", "perplexity_context", "perplexity_summary")
    return _items_from_keys(row, keys, ["Context unavailable.", "Confirm venue and start time.", "Recheck price before publishing."], 3)


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
        return 56, 32
    if width == 560 and start >= 100 and minimum >= 60:
        if length <= 6:
            return 86, 38
        if length <= 11:
            return 72, 34
        if length <= 17:
            return 58, 32
        return 46, 28
    return None


def apply_magazine_api_patch(module: Any) -> Any:
    if getattr(module, "_DYNAMIC_API_SOURCE_PATCHED", False):
        return module
    original_render = module.render_full_pick_magazine_page
    original_png = module._png
    original_metric = module._metric
    original_badge = module._badge
    original_bullets = module._bullets_auto
    original_fit = module._fit
    original_tr = module._tr
    original_clean = module._clean
    original_get = module._get
    original_team_label = module._team_label
    original_teams = module._teams

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
        try:
            return original_render(pick, *args, **kwargs)
        finally:
            _CURRENT_ROW = previous

    def patched_png(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
        return original_png(module.render_full_pick_magazine_page(pick, background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))

    def patched_pairs(row: Any, lang: str) -> list[tuple[str, str]]:
        prov = api_provenance(row)
        pairs = [("ODDS ROW", odds_row_label(row)), ("BOOK", original_get(row, "bookmaker", "sportsbook", default=module.NO_VERIFIED)), ("LINE", original_get(row, "line_movement", "price_movement", "market_move", default=module.NO_VERIFIED))]
        if prov["active_sources"]:
            pairs.append(("ACTIVE APIS", " · ".join(prov["active_sources"])))
        if prov["inactive_sources"]:
            pairs.append(("INACTIVE", " · ".join(prov["inactive_sources"])))
        return [(original_tr(label, lang), original_tr(original_clean(value), lang)) for label, value in pairs if value != module.NO_VERIFIED][:5]

    def patched_team_snapshot(img: Any, draw: Any, x: int, y: int, width: int, team: str, color: Any, lang: str) -> None:
        row = _CURRENT_ROW or {}
        away, _home = original_teams(row)
        side = "away" if str(team).strip().lower() == str(away).strip().lower() else "home"
        label = original_team_label(team, lang)
        original_badge(img, draw, label, x, y, 50, 50, color)
        draw.text((x + 66, y + 9), label.upper(), font=original_fit(label.upper(), width - 70, 25, 14, True), fill=color)
        original_bullets(draw, x, y + 76, team_items(row, side), width - 10, 165, color, 18, 10, 4, lang)

    def patched_items(row: Any, keys: Iterable[str], fallback: list[str], limit: int) -> list[str]:
        key_tuple = tuple(keys)
        if "matchup_note" in key_tuple or "sports_context_summary" in key_tuple:
            return matchup_items(row)[:limit]
        return _items_from_keys(row, key_tuple, filter_sport_text(fallback, row) or fallback, limit)

    def patched_metric(draw: Any, x: int, y: int, width: int, label: str, value: str, color: Any, lang: str) -> None:
        if label.upper() in {"MARKET", "MARKE", "TOTALS", "SPREADS"}:
            return
        original_metric(draw, x, y, width, label, value, color, lang)

    module.render_full_pick_magazine_page = patched_render
    module.render_full_pick_magazine_page_png = patched_png
    module._fit = patched_fit
    module._pairs = patched_pairs
    module._team_snapshot = patched_team_snapshot
    module._player_items = injury_items
    module._items = patched_items
    module._metric = patched_metric
    module.api_provenance = api_provenance
    module.api_provenance_lines = api_provenance_lines
    module.magazine_metric_cells = lambda odds, conf, edge, ev, units, risk: magazine_metric_cells(odds, conf, edge, ev, units, risk, {"DANGER": module.DANGER, "GREEN": module.GREEN, "CREAM": module.CREAM})
    module.MAGAZINE_STYLE_VERSION = f"{module.MAGAZINE_STYLE_VERSION}_dynamic_api_sources_v1_title_autosize"
    module._DYNAMIC_API_SOURCE_PATCHED = True
    return module
