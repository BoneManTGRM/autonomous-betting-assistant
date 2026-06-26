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
            return {
                "location": {"name": "Philadelphia", "region": "Pennsylvania", "country": "USA"},
                "current": {"temp_c": 22.0, "wind_kph": 8.0, "condition": {"text": "Clear"}},
            }
        if cache_key and cache_key[0] == "news":
            return {"articles": []}
        if cache_key and cache_key[0] == "api-football-team":
            return {"response": []}
        return {}

    monkeypatch.setattr(enrich, "_request_json", fake_request)
    row = enrich.enrich_row_with_live_api_data(_row())
    row_text = "\n".join(str(value) for value in row.values())

    assert "WeatherAPI: Clear" in row["weather_summary"]
    assert "NewsAPI checked" in row["newsapi_summary"]
    assert "no recent matching articles" in row["newsapi_summary"]
    assert "API-Football checked team lookup for Iraq and France" in row["api_football_summary"]
    assert "SportsDataIO configured" in row["sportsdataio_context"]
    assert row["_live_api_enriched"] == enrich.ENRICHMENT_VERSION
    assert "weather-secret" not in row_text
    assert "news-secret" not in row_text
    assert "football-secret" not in row_text
    assert "sdio-secret" not in row_text


def test_weather_checked_message_when_location_is_missing(monkeypatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("WEATHERAPI_KEY", "weather-secret")
    row = enrich.enrich_row_with_live_api_data({"event_name": "Iraq vs France", "sport": "FIFA WORLD CUP"})
    assert row["weather_summary"] == "WeatherAPI configured; no venue/location field was available for this row."


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
