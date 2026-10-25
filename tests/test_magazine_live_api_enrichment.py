from __future__ import annotations

from autonomous_betting_agent import magazine_live_api_enrichment as enrich
from autonomous_betting_agent.magazine_api_sources import api_provenance, injury_items, matchup_items, team_items
from autonomous_betting_agent.magazine_second_page_patch import _page_two_sections


def _clear(monkeypatch) -> None:
    for names in enrich.API_SECRET_DEFS.values():
        for name in names:
            monkeypatch.delenv(name, raising=False)
    enrich._CACHE.clear()


def _row() -> dict[str, str]:
    return {
        "event_name": "Iraq vs France",
        "away_team": "Iraq",
        "home_team": "France",
        "sport": "FIFA WORLD CUP",
        "venue_note": "Neutral-site FIFA venue override matched by event teams and start time. Philadelphia, Pennsylvania, USA",
    }


def test_weather_news_api_football_and_sportsdataio_checked_details(monkeypatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("WEATHERAPI_KEY", "weather-secret")
    monkeypatch.setenv("NEWSAPI_KEY", "news-secret")
    monkeypatch.setenv("API_FOOTBALL_KEY", "football-secret")
    monkeypatch.setenv("SPORTSDATAIO_API_KEY", "sdio-secret")
    monkeypatch.setattr(enrich, "_sportsdata_context", lambda row, key: {
        "sportsdataio_status": "used",
        "sportsdataio_source_used": "yes",
        "sportsdataio_team_metadata_used": "yes",
        "sportsdataio_away_team_matched": "yes",
        "sportsdataio_home_team_matched": "yes",
        "sportsdataio_picked_team_injury_count": 0,
    })

    def fake_request(url, *, headers=None, cache_key=None, timeout=3.0):
        if cache_key and cache_key[0] == "weather":
            assert "weather-secret" in url
            return {
                "location": {"name": "Philadelphia", "region": "Pennsylvania", "country": "USA"},
                "current": {"temp_c": 22.0, "wind_kph": 8.0, "condition": {"text": "Clear"}},
            }
        if cache_key and cache_key[0] == "news":
            assert headers == {"X-Api-Key": "news-secret"}
            assert "Iraq" in url and "France" in url
            return {"articles": []}
        if cache_key and cache_key[0] == "api-football-team":
            return {"response": []}
        return {}

    monkeypatch.setattr(enrich, "_request_json", fake_request)
    row = enrich.enrich_row_with_live_api_data(_row())
    row_text = "\n".join(str(value) for value in row.values())

    assert "Weather: Clear, 22.0°C, wind 8.0 kph." in row["weather_summary"]
    assert "News checked; no recent matching articles." == row["newsapi_summary"]
    assert "News checked; no injury/lineup headline." == row["news_injury_summary"]
    assert "API-FB team lookup checked Iraq / France; no match returned." == row["api_football_summary"]
    assert "SportsDataIO matched away and home team metadata." in row["sportsdataio_context"]
    assert row["sportsdataio_live"] is True
    assert row["_live_api_enriched"] == enrich.ENRICHMENT_VERSION
    assert "weather-secret" not in row_text
    assert "news-secret" not in row_text
    assert "football-secret" not in row_text
    assert "sdio-secret" not in row_text


def test_api_football_lookup_is_not_labeled_as_verified_fixture(monkeypatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("API_FOOTBALL_KEY", "football-secret")

    def fake_request(url, *, headers=None, cache_key=None, timeout=3.0):
        team = "Iraq" if cache_key and "iraq" in cache_key[1] else "France"
        return {"response": [{"team": {"name": team}}]}

    monkeypatch.setattr(enrich, "_request_json", fake_request)
    row = enrich.enrich_row_with_live_api_data(_row())
    assert row["api_football_summary"] == "API-FB team lookup matched Iraq / France; fixture not verified."
    assert "verified fixture" not in row["api_football_summary"].lower()


def test_weather_checked_message_when_location_is_missing(monkeypatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("WEATHERAPI_KEY", "weather-secret")
    row = enrich.enrich_row_with_live_api_data({"event_name": "Iraq vs France", "sport": "FIFA WORLD CUP"})
    assert row["weather_summary"] == "Weather checked; no venue/location in row."


def test_install_wraps_magazine_renderer_without_network(monkeypatch) -> None:
    _clear(monkeypatch)

    class Module:
        MAGAZINE_STYLE_VERSION = "style"
        _LIVE_API_ENRICHMENT_PATCHED = False

        @staticmethod
        def _png(value):
            return b"png"

        @staticmethod
        def render_full_pick_magazine_page(row, *args, **kwargs):
            return row

    module = enrich.install(Module)
    rendered = module.render_full_pick_magazine_page({"event_name": "A vs B"})
    assert rendered["_live_api_enriched"] == enrich.ENRICHMENT_VERSION
    assert enrich.ENRICHMENT_VERSION in module.MAGAZINE_STYLE_VERSION


def test_all_configured_provider_results_reach_report_and_page_two(monkeypatch) -> None:
    _clear(monkeypatch)
    for name in (
        "ODDS_API_KEY", "SPORTSDATAIO_API_KEY", "WEATHERAPI_KEY", "API_FOOTBALL_KEY",
        "NEWSAPI_KEY", "PERPLEXITY_API_KEY", "BALLDONTLIE_API_KEY",
    ):
        monkeypatch.setenv(name, f"{name.lower()}-secret")

    monkeypatch.setattr(enrich, "_fetch_odds_payload", lambda key, sport: [{
        "id": "odds-event-1",
        "sport_key": sport,
        "commence_time": "2026-09-02T00:00:00Z",
        "away_team": "Alpha",
        "home_team": "Beta",
        "bookmakers": [{
            "title": "Exact Book",
            "last_update": "2026-09-01T23:50:00Z",
            "markets": [{"key": "h2h", "outcomes": [{"name": "Alpha", "price": 2.1}]}],
        }],
    }])
    monkeypatch.setattr(enrich, "_sportsdata_context", lambda row, key: {
        "sportsdataio_status": "used",
        "sportsdataio_source_used": "yes",
        "sportsdataio_team_metadata_used": "yes",
        "sportsdataio_away_team_matched": "yes",
        "sportsdataio_home_team_matched": "yes",
        "sportsdataio_picked_team_injury_count": 1,
        "stats_probability": 0.61,
    })

    def fake_get(url, *, headers=None, cache_key=None, timeout=3.0):
        kind = cache_key[0] if cache_key else ""
        if kind == "weather":
            return {"current": {"temp_c": 18, "wind_kph": 11, "condition": {"text": "Clear"}}}
        if kind == "news":
            return {"status": "ok", "articles": [{"title": "Alpha lineup update"}]}
        if kind == "api-football-team":
            team = "Alpha" if "alpha" in cache_key[1] else "Beta"
            return {"response": [{"team": {"id": 1 if team == "Alpha" else 2, "name": team}}]}
        if kind == "api-football-fixture":
            return {"response": [{
                "fixture": {"id": 77, "date": "2026-09-02T00:00:00Z", "venue": {"name": "Civic Field"}, "status": {"long": "Not Started"}},
                "teams": {"away": {"id": 1}, "home": {"id": 2}},
            }]}
        if kind == "api-football-injuries":
            return {"response": [{"player": {"name": "A Player"}}]}
        return {}

    monkeypatch.setattr(enrich, "_request_json", fake_get)
    monkeypatch.setattr(enrich, "_request_post_json", lambda *args, **kwargs: {
        "choices": [{"message": {"content": "Alpha and Beta are scheduled at Civic Field."}}],
        "citations": ["https://example.test/schedule"],
    })

    def fake_bdl(row):
        return {
            **row,
            "balldontlie_status": "LIVE",
            "balldontlie_team_summary": "BALLDONTLIE matched Alpha / Beta.",
            "balldontlie_injury_summary": "BALLDONTLIE returned 0 active injury rows.",
            "balldontlie_game_summary": "BALLDONTLIE matched game 99.",
            "balldontlie_props_summary": "BALLDONTLIE returned 2 player prop rows; model probability required.",
        }

    monkeypatch.setattr(enrich, "_enrich_balldontlie", fake_bdl)
    row = enrich.enrich_row_with_live_api_data({
        "event": "Alpha vs Beta",
        "away_team": "Alpha",
        "home_team": "Beta",
        "sport": "NBA",
        "sport_key": "basketball_nba",
        "selection": "Alpha",
        "market_type": "moneyline",
        "venue": "Civic Field",
        "event_start_utc": "2026-09-02T00:00:00Z",
        "model_probability": 0.6,
        "model_market_edge": 0.1238,
        "expected_value_per_unit": 0.26,
    })

    assert row["decimal_odds"] == 2.1
    assert row["bookmaker"] == "Exact Book"
    assert row["provider_event_id"] == "odds-event-1"
    assert row["sportsdataio_live"] is True
    assert row["weatherapi_live"] is True
    assert row["api_football_fixture_id"] == 77
    assert row["newsapi_live"] is True
    assert row["perplexity_status"] == "LIVE_UNVERIFIED_RESEARCH"
    assert row["balldontlie_live"] is True
    assert api_provenance(row)["active_sources"] == [
        "Odds API", "SportsDataIO", "WeatherAPI", "API-Football", "Perplexity", "NewsAPI", "BALLDONTLIE",
    ]
    assert any("SportsDataIO" in item for item in team_items(row, "away"))
    assert any("injury" in item.lower() for item in injury_items(row, "away"))
    assert any("Weather" in item for item in matchup_items(row))
    page_two_text = "\n".join(item for _title, items, _color in _page_two_sections(row, "en") for item in items)
    assert "API data: active Odds · SDIO · Weather · API-FB · PPLX · News · BDL" in page_two_text
    page_two_es = "\n".join(item for _title, items, _color in _page_two_sections(row, "es") for item in items)
    assert "Datos API: activos cuota · SDIO · Weather · API-FB · PPLX · News · BDL" in page_two_es
    assert all("secret" not in str(value).lower() for value in row.values())

    actual_app_row = enrich.enrich_rows_with_live_api_data([row])[0]
    assert actual_app_row["api_football_fixture_id"] == "77"
    assert actual_app_row["sportsdataio_match_status"] == "MATCHED_TEAM_DATA"
    assert actual_app_row["balldontlie_props_summary"].startswith("BALLDONTLIE returned 2")
    assert "perplexity_context" in actual_app_row["api_enrichment_fields"]


def test_configured_provider_empty_results_are_not_marked_live(monkeypatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("ODDS_API_KEY", "odds-secret")
    monkeypatch.setenv("WEATHERAPI_KEY", "weather-secret")
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-secret")
    monkeypatch.setattr(enrich, "_fetch_odds_payload", lambda key, sport: [])
    monkeypatch.setattr(enrich, "_request_json", lambda *args, **kwargs: {})
    monkeypatch.setattr(enrich, "_request_post_json", lambda *args, **kwargs: {"choices": []})

    row = enrich.enrich_row_with_live_api_data({
        "event": "Alpha vs Beta", "away_team": "Alpha", "home_team": "Beta",
        "sport_key": "basketball_nba", "selection": "Alpha", "venue": "Civic Field",
    })
    provenance = api_provenance(row)

    assert row["odds_api_live"] is False
    assert row["weatherapi_live"] is False
    assert row["perplexity_live"] is False
    assert "Odds API" in provenance["available_no_data_sources"]
    assert "WeatherAPI" in provenance["available_no_data_sources"]
    assert "Perplexity" in provenance["available_no_data_sources"]


def test_odds_api_requires_exact_line_and_traceability(monkeypatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("ODDS_API_KEY", "odds-secret")
    base = {
        "id": "event-1", "away_team": "Alpha", "home_team": "Beta",
        "bookmakers": [{"title": "Book", "last_update": "2026-09-01T20:00:00Z", "markets": [{
            "key": "totals", "outcomes": [{"name": "Over", "point": 3.5, "price": 2.05}],
        }]}],
    }
    monkeypatch.setattr(enrich, "_fetch_odds_payload", lambda key, sport: [base])

    wrong_line = enrich.enrich_row_with_live_api_data({
        "event": "Alpha vs Beta", "away_team": "Alpha", "home_team": "Beta",
        "sport_key": "soccer_test", "selection": "Over 2.5", "market_type": "total", "line": 2.5,
    })
    assert wrong_line["odds_api_live"] is False
    assert wrong_line["odds_api_status"] == "NO_EXACT_MARKET_MATCH"
    assert "decimal_odds" not in wrong_line

    no_timestamp = {**base, "bookmakers": [{
        "title": "Book", "markets": [{"key": "totals", "outcomes": [{"name": "Over", "point": 2.5, "price": 2.05}]}],
    }]}
    monkeypatch.setattr(enrich, "_fetch_odds_payload", lambda key, sport: [no_timestamp])
    missing_trace = enrich.enrich_row_with_live_api_data({
        "event": "Alpha vs Beta", "away_team": "Alpha", "home_team": "Beta",
        "sport_key": "soccer_test", "selection": "Over 2.5", "market_type": "total", "line": 2.5,
    })
    assert missing_trace["odds_api_live"] is False
    assert missing_trace["odds_api_status"] == "TRACEABILITY_MISSING:timestamp"
    assert "decimal_odds" not in missing_trace
