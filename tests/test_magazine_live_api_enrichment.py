from __future__ import annotations

from autonomous_betting_agent import magazine_live_api_enrichment as enrich


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
    assert "SDIO checked; no provider event ID in row." == row["sportsdataio_context"]
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
