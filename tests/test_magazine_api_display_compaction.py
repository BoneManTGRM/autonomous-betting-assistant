from __future__ import annotations

from autonomous_betting_agent import magazine_api_sources as api


def _row() -> dict[str, object]:
    return {
        "event_name": "Iraq vs France",
        "away_team": "Iraq",
        "home_team": "France",
        "sport": "FIFA WORLD CUP",
        "sportsdataio_team_summary": "SportsDataIO configured; soccer team/event endpoint data was not available for this row.",
        "sportsdataio_context": "SportsDataIO configured; soccer team/event endpoint data was not available for this row.",
        "api_football_team_summary": "API-Football: Iraq, Iraq, venue Basra International Stadium vs France, France, venue Groupama Stadium",
        "api_football_summary": "API-Football: Iraq, Iraq, venue Basra International Stadium vs France, France, venue Groupama Stadium",
        "newsapi_summary": "NewsAPI checked 'Iraq France FIFA WORLD CUP injury lineup news odds'; no recent matching articles were returned.",
        "news_injury_summary": "NewsAPI checked 'Iraq France FIFA WORLD CUP injury lineup news odds'; no injury/lineup headline was returned.",
        "weather_summary": "WeatherAPI: Partly cloudy; 22.8°C; wind 5.8 kph. Location: Philadelphia, Pennsylvania, United States of America.",
        "api_sources_active": "SportsDataIO|WeatherAPI|API-Football|NewsAPI",
        "api_sources_inactive": "Perplexity",
        "odds_source": "The " + "Odds" + " API",
    }


def test_team_items_are_deduped_and_compact() -> None:
    items = api.team_items(_row(), "away")
    assert items.count("SDIO checked; no provider event ID in row.") == 1
    assert "API-FB lookup only; fixture not verified." in items
    assert "News checked; no injury/lineup headline." in items
    assert all("SportsDataIO configured" not in item for item in items)
    assert all("API-Football:" not in item for item in items)


def test_injury_items_are_compact() -> None:
    items = api.injury_items(_row(), "away")
    assert items[0] == "News checked; no injury/lineup headline."
    assert all("NewsAPI checked" not in item for item in items)


def test_matchup_items_show_weather_location_and_lookup_label() -> None:
    items = api.matchup_items(_row())
    assert items == [
        "Weather: 22.8°C, partly cloudy, wind 5.8 kph.",
        "Location: Philadelphia, PA, USA.",
        "API-FB lookup only; fixture not verified.",
    ]


def test_pro_bettor_pairs_use_short_api_labels() -> None:
    class Module:
        NO_VERIFIED = "Data unavailable"

        @staticmethod
        def _tr(value, lang):
            return value

        @staticmethod
        def _clean(value, upper=False):
            return str(value).upper() if upper else str(value)

        @staticmethod
        def _get(row, *keys, default=""):
            for key in keys:
                if row.get(key):
                    return row[key]
            return default

        @staticmethod
        def render_full_pick_magazine_page(row, *args, **kwargs):
            return row

        @staticmethod
        def _png(value):
            return b"png"

        @staticmethod
        def _badge(*args, **kwargs):
            return None

        @staticmethod
        def _bullets_auto(*args, **kwargs):
            return None

        @staticmethod
        def _fit(*args, **kwargs):
            return None

        @staticmethod
        def _team_label(team, lang):
            return team

        @staticmethod
        def _teams(row):
            return row.get("away_team", ""), row.get("home_team", "")

        @staticmethod
        def _metric(*args, **kwargs):
            return None

    patched = api.apply_magazine_api_patch(Module)
    pairs = patched._pairs(_row(), "en")
    assert ("ACTIVE", "SDIO · Weather · API-FB · News") in pairs
    assert ("INACTIVE", "PPLX") in pairs
    assert not any(label == "ACTIVE APIS" for label, _ in pairs)
