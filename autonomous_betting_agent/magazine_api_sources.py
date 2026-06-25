from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, is_dataclass
from typing import Any

EXPECTED_API_ORDER = (
    "Odds API",
    "SportsDataIO",
    "WeatherAPI",
    "API-Football",
    "Perplexity",
    "NewsAPI",
)

API_SOURCE_DEFS = (
    {
        "name": "Odds API",
        "live_keys": ("odds_api_live", "the_odds_api_live", "odds_api_enabled"),
        "data_keys": ("odds_api_summary", "live_odds_summary", "odds_api_context"),
        "support_keys": ("odds_source", "bookmaker", "sportsbook", "decimal_price", "odds", "best_price", "market_probability"),
        "requires_live": True,
    },
    {
        "name": "SportsDataIO",
        "live_keys": ("sportsdataio_live", "sportsdataio_enabled"),
        "data_keys": ("sportsdataio_team_summary", "sportsdataio_context", "sportsdataio_injury_summary", "sportsdataio_game_summary"),
        "support_keys": (),
        "requires_live": False,
    },
    {
        "name": "WeatherAPI",
        "live_keys": ("weatherapi_live", "weather_live", "weather_enabled"),
        "data_keys": ("weather_summary", "weather_location", "weather_risk", "venue_weather"),
        "support_keys": (),
        "requires_live": False,
    },
    {
        "name": "API-Football",
        "live_keys": ("api_football_live", "api_football_enabled"),
        "data_keys": ("api_football_summary", "api_football_context", "api_football_team_summary", "api_football_lineup_summary"),
        "support_keys": (),
        "requires_live": False,
    },
    {
        "name": "Perplexity",
        "live_keys": ("perplexity_live", "perplexity_enabled"),
        "data_keys": ("perplexity_summary", "perplexity_context", "perplexity_news_context"),
        "support_keys": (),
        "requires_live": True,
    },
    {
        "name": "NewsAPI",
        "live_keys": ("newsapi_live", "newsapi_enabled"),
        "data_keys": ("newsapi_summary", "news_summary", "news_injury_summary", "breaking_news_summary"),
        "support_keys": (),
        "requires_live": False,
    },
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
    if value is None:
        return True
    text = str(value).strip().lower()
    return text in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


def _useful(value: Any) -> bool:
    if _bad(value):
        return False
    text = str(value).strip().lower()
    if text in {"false", "0", "no", "not available", "unavailable", "data unavailable", "none available"}:
        return False
    if any(token in text for token in ("not returned", "not available", "no data", "api key missing", "payment required")):
        return False
    return True


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
    return [part.strip(" -•") for part in str(value).replace("•", "\n").replace(";", "\n").replace("|", "\n").splitlines() if part.strip(" -•")]


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


def _source_name_matches(name: str, explicit: Iterable[str]) -> bool:
    target = name.lower().replace("the ", "")
    return any(target in item.lower().replace("the ", "") for item in explicit)


def api_provenance(row: Any) -> dict[str, list[str]]:
    data = _row(row)
    explicit_active = _split(data.get("api_sources_active") or data.get("api_sources_used"))
    explicit_inactive = _split(data.get("api_sources_inactive"))
    active: list[str] = []
    available_no_data: list[str] = []
    inactive: list[str] = []

    for spec in API_SOURCE_DEFS:
        name = str(spec["name"])
        live_values = [_truthy(data.get(key)) for key in spec["live_keys"] if key in data]
        live = next((value for value in live_values if value is not None), None)
        has_primary_data = _any_useful(row, spec["data_keys"])
        has_support_data = _any_useful(row, spec["support_keys"])
        explicit_name_active = _source_name_matches(name, explicit_active)
        explicit_name_inactive = _source_name_matches(name, explicit_inactive)

        if explicit_name_inactive:
            inactive.append(name)
        elif explicit_name_active or has_primary_data or (live is True and (has_primary_data or has_support_data)):
            active.append(name)
        elif live is True:
            available_no_data.append(name)
        elif spec.get("requires_live") and has_support_data:
            inactive.append(name)
        else:
            inactive.append(name)

    active = _dedupe(active)
    available_no_data = _dedupe(name for name in available_no_data if name not in active)
    inactive = _dedupe(name for name in inactive if name not in active and name not in available_no_data)
    return {
        "active_sources": active,
        "available_no_data_sources": available_no_data,
        "inactive_sources": inactive,
    }


def api_provenance_lines(row: Any) -> list[str]:
    provenance = api_provenance(row)
    lines: list[str] = []
    if provenance["active_sources"]:
        lines.append("Active APIs: " + " · ".join(provenance["active_sources"]))
    if provenance["available_no_data_sources"]:
        lines.append("No data: " + " · ".join(provenance["available_no_data_sources"]))
    if provenance["inactive_sources"]:
        lines.append("Inactive: " + " · ".join(provenance["inactive_sources"]))
    return lines


def sport_kind(row: Any) -> str:
    data = _row(row)
    text = " ".join(str(data.get(key, "")) for key in ("sport", "league", "event", "game", "matchup")).lower()
    if any(token in text for token in ("mma", "ufc", "fight", "boxing", "fighter")):
        return "combat"
    if any(token in text for token in ("soccer", "fifa", "football", "world cup", "uefa", "liga")):
        return "soccer"
    if any(token in text for token in ("mlb", "baseball", "dodgers", "twins", "yankees")):
        return "baseball"
    return "generic"


def filter_sport_text(items: Iterable[str], row: Any) -> list[str]:
    if sport_kind(row) == "combat":
        return [str(item) for item in items if _useful(item)]
    forbidden = ("api-mma", "fight news", "weight cut", "camp updates")
    return [str(item) for item in items if _useful(item) and not any(token in str(item).lower() for token in forbidden)]


def _team_fallback(row: Any) -> list[str]:
    kind = sport_kind(row)
    if kind == "soccer":
        return ["Team form data was not available from active soccer sources.", "Check lineup and news updates before publishing."]
    if kind == "baseball":
        return ["Team form data was not available from active baseball sources.", "Check lineup, bullpen, and news updates before publishing."]
    if kind == "combat":
        return ["Fighter data was not available from active combat-sport sources.", "Confirm fight news before publishing."]
    return ["Data not available from uploaded row", "Use team form, injuries, and market movement before publishing."]


def _injury_fallback(row: Any) -> list[str]:
    kind = sport_kind(row)
    if kind == "soccer":
        return ["Lineup and injury data were not available from active soccer sources."]
    if kind == "baseball":
        return ["Lineup and injury data were not available from active baseball sources."]
    if kind == "combat":
        return ["Confirm fight news, injuries, weight cut, and camp updates before betting."]
    return ["Player data not available in uploaded row", "Confirm lineup/injury news before placing the bet."]


def _items_from_keys(row: Any, keys: Iterable[str], fallback: list[str], limit: int) -> list[str]:
    data = _row(row)
    out: list[str] = []
    for key in keys:
        out += _split(data.get(key))
    return (filter_sport_text(out, row) or fallback)[:limit]


def team_items(row: Any, side: str = "") -> list[str]:
    keys = (
        f"{side}_team_form",
        f"{side}_team_record",
        f"{side}_recent_results",
        f"{side}_sportsdataio_team_summary",
        f"{side}_api_football_team_summary",
        "sportsdataio_team_summary",
        "sportsdataio_context",
        "api_football_team_summary",
        "api_football_context",
        "team_stats_summary",
        "home_team_form",
        "away_team_form",
        "recent_results",
        "news_summary",
        "newsapi_summary",
    )
    return _items_from_keys(row, keys, _team_fallback(row), 4)


def injury_items(row: Any, prefix: str) -> list[str]:
    keys = (
        f"{prefix}_injuries",
        f"{prefix}_injury_report",
        f"{prefix}_lineup_status",
        f"{prefix}_player_notes",
        "injury_report",
        "injuries",
        "lineup_status",
        "key_players",
        "home_injuries",
        "away_injuries",
        "sportsdataio_injury_summary",
        "api_football_lineup_summary",
        "news_injury_summary",
    )
    return _items_from_keys(row, keys, _injury_fallback(row), 3)


def matchup_items(row: Any) -> list[str]:
    keys = (
        "weather_summary",
        "venue_note",
        "weather_location",
        "weather_risk",
        "news_summary",
        "newsapi_summary",
        "api_football_context",
        "api_football_summary",
        "sportsdataio_context",
        "sportsdataio_game_summary",
        "sports_context_summary",
        "matchup_note",
        "matchup_notes",
        "perplexity_context",
        "perplexity_summary",
    )
    return _items_from_keys(row, keys, ["Context unavailable.", "Confirm venue and start time.", "Recheck price before publishing."], 3)


def odds_row_label(row: Any) -> str:
    provenance = api_provenance(row)
    if "Odds API" in provenance["active_sources"]:
        source = _row(row).get("odds_source") or _row(row).get("data_source")
        return str(source or "Odds API")
    source = str(_row(row).get("odds_source") or _row(row).get("data_source") or "").strip()
    if source and "odds api" not in source.lower():
        return source
    return "uploaded/cached row"


def magazine_metric_cells(odds: str, conf: str, edge: str, ev: str, units: str, risk: str, palette: Mapping[str, Any]) -> list[tuple[str, str, Any, int, int]]:
    danger = palette["DANGER"]
    green = palette["GREEN"]
    cream = palette["CREAM"]
    edge_color = danger if str(edge).startswith("-") else green
    ev_color = danger if str(ev).startswith("-") else green
    return [
        ("ODDS", odds, cream, 345, 98),
        ("CONFIDENCE", conf, green, 443, 145),
        ("EDGE", edge, edge_color, 588, 112),
        ("EV", ev, ev_color, 700, 112),
        ("UNITS", units, cream, 812, 100),
        ("RISK", risk, green, 912, 148),
    ]


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
    original_section = module._section
    original_items = module._items

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
        provenance = api_provenance(row)
        pairs = [
            ("ODDS ROW", odds_row_label(row)),
            ("BOOK", original_get(row, "bookmaker", "sportsbook", default=module.NO_VERIFIED)),
            ("LINE", original_get(row, "line_movement", "price_movement", "market_move", default=module.NO_VERIFIED)),
        ]
        if provenance["active_sources"]:
            pairs.append(("ACTIVE APIS", " · ".join(provenance["active_sources"])))
        if provenance["inactive_sources"]:
            pairs.append(("INACTIVE", " · ".join(provenance["inactive_sources"])))
        return [(original_tr(label, lang), original_tr(original_clean(value), lang)) for label, value in pairs if value != module.NO_VERIFIED][:5]

    def patched_team_snapshot(img: Any, draw: Any, x: int, y: int, width: int, team: str, color: Any, lang: str) -> None:
        row = _CURRENT_ROW or {}
        away, home = original_teams(row)
        side = "away" if str(team).strip().lower() == str(away).strip().lower() else "home"
        label = original_team_label(team, lang)
        original_badge(img, draw, label, x, y, 50, 50, color)
        draw.text((x + 66, y + 9), label.upper(), font=original_fit(label.upper(), width - 70, 25, 14, True), fill=color)
        original_bullets(draw, x, y + 76, team_items(row, side), width - 10, 165, color, 18, 10, 4, lang)

    def patched_player_items(row: Any, prefix: str) -> list[str]:
        return injury_items(row, prefix)

    def patched_items(row: Any, keys: Iterable[str], fallback: list[str], limit: int) -> list[str]:
        key_tuple = tuple(keys)
        if "matchup_note" in key_tuple or "sports_context_summary" in key_tuple:
            return matchup_items(row)[:limit]
        return _items_from_keys(row, key_tuple, filter_sport_text(fallback, row) or fallback, limit)

    def patched_metric_cells(odds: str, conf: str, edge: str, ev: str, units: str, risk: str) -> list[tuple[str, str, Any, int, int]]:
        return magazine_metric_cells(odds, conf, edge, ev, units, risk, {"DANGER": module.DANGER, "GREEN": module.GREEN, "CREAM": module.CREAM})

    def patched_metric(draw: Any, x: int, y: int, width: int, label: str, value: str, color: Any, lang: str) -> None:
        if label.upper() in {"MARKET", "MARKE", "TOTALS", "SPREADS"}:
            return
        original_metric(draw, x, y, width, label, value, color, lang)

    def patched_render_with_sources(pick: Any, *args: Any, **kwargs: Any):
        return patched_render(pick, *args, **kwargs)

    module.render_full_pick_magazine_page = patched_render_with_sources
    module.render_full_pick_magazine_page_png = patched_png
    module._pairs = patched_pairs
    module._team_snapshot = patched_team_snapshot
    module._player_items = patched_player_items
    module._items = patched_items
    module._metric = patched_metric
    module.api_provenance = api_provenance
    module.api_provenance_lines = api_provenance_lines
    module.magazine_metric_cells = patched_metric_cells
    module.MAGAZINE_STYLE_VERSION = f"{module.MAGAZINE_STYLE_VERSION}_dynamic_api_sources_v1"
    module._DYNAMIC_API_SOURCE_PATCHED = True
    return module
