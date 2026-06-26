from types import SimpleNamespace

import autonomous_betting_agent.magazine_api_sources as api_sources


def _row():
    return {
        "bookmaker": "consensus average",
        "sportsdataio_live": "true",
        "weatherapi_live": "true",
        "api_football_live": "true",
        "newsapi_live": "true",
        "perplexity_live": "false",
        "sportsdataio_team_summary": "SDIO checked; no provider event ID in row.",
        "sportsdataio_context": "SDIO checked; no provider event ID in row.",
        "weather_summary": "WeatherAPI: Partly cloudy; 22.8°C; wind 5.8 kph. Location: Philadelphia, Pennsylvania, United States of America.",
        "api_football_summary": "API-Football: Iraq / France lookup",
        "newsapi_summary": "NewsAPI checked; no injury/lineup headline.",
        "event": "Iraq vs France",
        "sport": "soccer",
    }


def _patched_module():
    return SimpleNamespace(
        _DYNAMIC_API_SOURCE_PATCHED=True,
        _pairs=lambda _row, _lang: [("ACTIVE APIS", "old")],
        _get=lambda row, *keys, default="": next((str(row[key]) for key in keys if row.get(key)), default),
        _clean=lambda value, *_args: str(value),
        _tr=lambda value, _lang: str(value),
        NO_VERIFIED="NO VERIFIED",
    )


def test_apply_patch_early_return_refreshes_pairs():
    module = _patched_module()

    assert module._pairs({}, "en") == [("ACTIVE APIS", "old")]

    api_sources.apply_magazine_api_patch(module)

    labels = [label for label, _value in module._pairs(_row(), "en")]
    assert labels == ["ODDS ROW", "BOOK", "ACTIVE", "NO LIVE", "INACTIVE"]
    assert "ACTIVE APIS" not in labels


def test_compact_pairs_use_active_no_live_inactive_labels():
    module = _patched_module()
    api_sources.apply_magazine_api_patch(module)

    pairs = module._pairs(_row(), "en")

    assert pairs == [
        ("ODDS ROW", "uploaded/cached row"),
        ("BOOK", "consensus average"),
        ("ACTIVE", "SDIO · Weather · API-FB · News"),
        ("NO LIVE", "Odds"),
        ("INACTIVE", "PPLX"),
    ]


def test_matchup_notes_are_shortened():
    assert api_sources.matchup_items(_row()) == [
        "Weather: 22.8°C, partly cloudy, wind 5.8 kph.",
        "Location: Philadelphia, PA, USA.",
        "API-FB lookup only; fixture not verified.",
    ]


def test_sportsdataio_duplicate_lines_are_removed():
    items = api_sources._compact_items(
        [
            "SDIO checked; no provider event ID in row.",
            "SportsDataIO configured; no provider event ID in row.",
        ],
        _row(),
        "team",
        4,
    )

    assert items == ["SDIO checked; no provider event ID in row."]


def test_api_fb_remains_lookup_only_not_fixture_verified():
    message = api_sources.compact_api_message("API-Football: Iraq / France lookup", _row(), "matchup")

    assert message == ["API-FB lookup only; fixture not verified."]
    assert "team lookup matched" not in message[0]
