from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "autonomous_betting_agent" / "magazine_book_export.py"
PATCH_PATH = ROOT / "autonomous_betting_agent" / "magazine_api_sources.py"
SPEC = importlib.util.spec_from_file_location("magazine_book_export_base_api", MODULE_PATH)
PATCH_SPEC = importlib.util.spec_from_file_location("magazine_api_sources_under_test", PATCH_PATH)
assert SPEC is not None and SPEC.loader is not None
assert PATCH_SPEC is not None and PATCH_SPEC.loader is not None
magazine = importlib.util.module_from_spec(SPEC)
api_sources = importlib.util.module_from_spec(PATCH_SPEC)
SPEC.loader.exec_module(magazine)
PATCH_SPEC.loader.exec_module(api_sources)
api_sources.apply_magazine_api_patch(magazine)


def _clear_api_env(monkeypatch):
    for names in api_sources.API_SECRET_DEFS.values():
        for name in names:
            monkeypatch.delenv(name, raising=False)


def _set_four(monkeypatch):
    monkeypatch.setenv("SPORTSDATAIO_API_KEY", "x")
    monkeypatch.setenv("WEATHERAPI_KEY", "x")
    monkeypatch.setenv("API_FOOTBALL_KEY", "x")
    monkeypatch.setenv("NEWSAPI_KEY", "x")


def _row() -> dict[str, str]:
    return {
        "event_name": "Iraq vs France",
        "away_team": "Iraq",
        "home_team": "France",
        "sport": "FIFA WORLD CUP",
        "pick": "OVER 2.5",
        "decimal_price": "1.36",
        "odds_source": "The Odds API",
        "bookmaker": "consensus average",
        "risk": "VOLUME OK",
    }


def test_renderer_detects_four_active_apis(monkeypatch):
    _clear_api_env(monkeypatch)
    _set_four(monkeypatch)
    provenance = magazine.api_provenance(_row())
    assert provenance["active_sources"] == ["SportsDataIO", "WeatherAPI", "API-Football", "NewsAPI"]
    assert "Odds API" not in provenance["active_sources"]
    assert api_sources.odds_row_label(_row()) == "uploaded/cached row"


def test_cached_odds_key_does_not_make_odds_active(monkeypatch):
    _clear_api_env(monkeypatch)
    monkeypatch.setenv("ODDS_API_KEY", "x")
    _set_four(monkeypatch)
    provenance = magazine.api_provenance(_row())
    assert provenance["active_sources"] == ["SportsDataIO", "WeatherAPI", "API-Football", "NewsAPI"]
    assert "Odds API" not in provenance["active_sources"]
    assert api_sources.odds_row_label(_row()) == "uploaded/cached row"


def test_pairs_show_four_active_apis(monkeypatch):
    _clear_api_env(monkeypatch)
    monkeypatch.setenv("ODDS_API_KEY", "x")
    _set_four(monkeypatch)
    pairs = magazine._pairs(_row(), "en")
    pair_text = "\n".join(f"{k}: {v}" for k, v in pairs)
    assert "ODDS ROW: uploaded/cached row" in pair_text
    assert "ACTIVE APIS: SportsDataIO · WeatherAPI · API-Football · NewsAPI" in pair_text
    assert "ODDS ROW: The Odds API" not in pair_text


def test_fallbacks_mention_four_active_apis(monkeypatch):
    _clear_api_env(monkeypatch)
    monkeypatch.setenv("ODDS_API_KEY", "x")
    _set_four(monkeypatch)
    expected = "Active APIs checked: SportsDataIO · WeatherAPI · API-Football · NewsAPI."
    row = _row()
    assert any(expected in item for item in api_sources.team_items(row, "away"))
    assert any(expected in item for item in api_sources.injury_items(row, "home"))
    assert any(expected in item for item in api_sources.matchup_items(row))
