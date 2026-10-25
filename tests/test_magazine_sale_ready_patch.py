from __future__ import annotations

from io import BytesIO

from PIL import Image

from autonomous_betting_agent import magazine_book_export
from autonomous_betting_agent.magazine_sale_ready_patch import (
    _page_one_provider_rows,
    _page_one_trace_pairs,
    _decimal_text,
    _force_truthful_gate,
    apply_magazine_sale_ready_patch,
    sale_ready_chain_items,
    sale_ready_injury_items,
    sale_ready_matchup_items,
    sale_ready_recommendation,
    sale_ready_risk_items,
    sale_ready_team_items,
)


def _row(**overrides):
    row = {
        "event_name": "Iraq vs France",
        "away_team": "Iraq",
        "home_team": "France",
        "sport": "FIFA WORLD CUP",
        "pick": "Game total: Over 2.5",
        "final_decision": "PLAY SMALL",
        "model_market_edge": "-0.021",
        "expected_value_per_unit": "-0.029",
        "sportsdataio_team_summary": "SDIO checked; no provider event ID in row.",
        "api_football_summary": "API-FB lookup checked Iraq / France; no match returned.",
        "api_football_team_summary": "API-FB lookup checked Iraq / France; no match returned.",
        "newsapi_summary": "News checked; no injury/lineup headline.",
        "news_injury_summary": "News checked; no injury/lineup headline.",
        "weather_summary": "Weather: Partly cloudy, 23.3°C, wind 5.8 kph. Partly cloudy, 23.3°C, wind 5.8 kph. Location: Philadelphia, Pennsylvania, United States of America.",
        "api_sources_active": "SportsDataIO|WeatherAPI|API-Football|NewsAPI",
        "api_sources_inactive": "Perplexity",
        "odds_source": "The Odds API",
    }
    row.update(overrides)
    return row


def _provider_terms():
    return (
        "No SDIO event ID returned",
        "API-FB lookup checked",
        "No lineup/injury headline returned",
        "SportsDataIO",
        "NewsAPI",
        "SDIO checked; no provider event ID in row",
        "News checked; no injury/lineup headline",
        "API-FB lookup checked; no match returned",
    )


def _live_provider_row(**overrides):
    row = _row(
        odds_api_live=True,
        odds_status="LIVE",
        odds_source="The Odds API",
        bookmaker="Book One",
        provider_event_id="evt-123",
        price_timestamp="2026-09-01T18:30:00Z",
        sportsdataio_live=True,
        sportsdataio_team_summary="SportsDataIO matched away and home team metadata; model statistic 61%.",
        sportsdataio_injury_summary="SportsDataIO returned 1 matched-team injury row.",
        weatherapi_live=True,
        weather_summary="Weather: Clear, 22.0°C, wind 8.0 kph. Location: Paris, France.",
        api_football_live=True,
        api_football_fixture_id="77",
        api_football_team_summary="API-Football matched teams: Iraq / France.",
        api_football_context="API-Football fixture 77 matched; Stade de France; Not Started.",
        api_football_lineup_summary="API-Football returned 2 injury/absence rows for fixture 77.",
        newsapi_live=True,
        newsapi_summary="NewsAPI returned 2 relevant articles.",
        news_injury_summary="France confirms its final squad before the match.",
        perplexity_live=True,
        perplexity_status="LIVE_UNVERIFIED_RESEARCH",
        perplexity_context="Unverified research context (not a verification source): schedule note with citations.",
        perplexity_summary="Perplexity returned research context with 2 citations; verify against primary sources.",
        balldontlie_live=True,
        balldontlie_team_summary="BALLDONTLIE matched Iraq / France team records.",
        balldontlie_injury_summary="BALLDONTLIE returned 1 active injury row.",
        balldontlie_game_summary="BALLDONTLIE matched game 99.",
        balldontlie_odds_summary="BALLDONTLIE returned Book Two moneyline odds.",
        balldontlie_props_summary="BALLDONTLIE returned 2 player prop rows; model probability required.",
        api_sources_active="Odds API|SportsDataIO|WeatherAPI|API-Football|NewsAPI|Perplexity|BALLDONTLIE",
    )
    row.update(overrides)
    return row


def test_page_one_live_provider_contract_preserves_all_seven_api_outputs():
    row = _live_provider_row()
    rendered_information = "\n".join(
        sale_ready_team_items(row, "away")
        + sale_ready_team_items(row, "home")
        + sale_ready_injury_items(row, "away")
        + sale_ready_injury_items(row, "home")
        + _page_one_provider_rows(row)
        + [f"{label}: {value}" for label, value in _page_one_trace_pairs(row, "en")]
    )

    for required in (
        "The Odds API",
        "Book One",
        "evt-123",
        "2026-09-01T18:30:00Z",
        "SportsDataIO",
        "Weather",
        "API-Football",
        "NewsAPI",
        "Perplexity UNVERIFIED",
        "citations",
        "BALLDONTLIE",
    ):
        assert required in rendered_information
    assert "not a verification source" in rendered_information


def test_page_one_provider_rows_do_not_promote_configured_or_failed_sources():
    row = _live_provider_row(
        newsapi_live=False,
        newsapi_summary="NewsAPI checked; provider response was unavailable.",
        news_injury_summary="News checked; no injury/lineup headline.",
        perplexity_live=False,
        perplexity_context="",
        perplexity_summary="Perplexity checked; provider response was unavailable.",
    )

    text = "\n".join(_page_one_provider_rows(row))

    assert "provider response was unavailable" not in text
    assert "no injury/lineup headline" not in text


def test_spanish_page_one_preserves_provider_brand_and_unverified_label():
    text = "\n".join(_page_one_provider_rows(_live_provider_row(report_language="es-MX"), "es"))

    assert "API-Football" in text
    assert "API-FÚTBOL AMERICANO" not in text
    assert "NO VERIFICADO" in text


def test_negative_edge_or_ev_cannot_play_small():
    action, explanation, playable = sale_ready_recommendation(_row())

    assert action == "WATCHLIST"
    assert playable is False
    assert "Do not play" in explanation
    assert action != "PLAY SMALL"


def test_positive_thin_edge_can_play_small():
    action, _explanation, playable = sale_ready_recommendation(
        _row(model_market_edge="0.010", expected_value_per_unit="0.010")
    )

    assert action == "PLAY SMALL"
    assert playable is True


def test_team_and_injury_fallbacks_are_professional_and_compact():
    team_items = sale_ready_team_items(_row(), "away")
    injury_items = sale_ready_injury_items(_row(), "away")
    text = "\n".join(team_items + injury_items)

    assert "No live team snapshot returned." in team_items
    assert "No verified lineup/injury update returned." in text
    assert "SDIO checked; no provider event ID in row." not in text
    assert "News checked; no injury/lineup headline." not in text
    assert "team lookup matched" not in text


def test_matchup_weather_location_and_api_fb_are_compact():
    items = sale_ready_matchup_items(_row())
    text = "\n".join(items)

    assert "Weather: 23.3°C, partly cloudy, wind 5.8 kph." in items
    assert "Weather: 23.3°C, partly cloudy, wind 5.8 kph. Partly cloudy." not in text
    assert "Location: Philadelphia, PA, USA." in items
    assert "API-FB lookup checked; no fixture match." in items
    assert text.count("Partly cloudy") <= 1
    assert "Pennsylvania, United States of America" not in text
    assert "team lookup matched" not in text


def test_negative_edge_risk_and_chain_notes_are_not_provider_fallbacks():
    risk_items = sale_ready_risk_items(_row())
    chain_items = sale_ready_chain_items(_row())
    text = "\n".join(risk_items + chain_items)

    assert risk_items == [
        "Negative edge at current price.",
        "Do not play unless price improves.",
        "Recheck odds and key news.",
    ]
    assert chain_items == [
        "No parlay recommended",
        "Negative edge at current price.",
        "Use as straight-bet research only.",
    ]
    assert "Do not chain" not in text
    assert "turns positive" not in text
    assert "before including" not in text
    assert all(term not in text for term in _provider_terms())


def test_missing_edge_risk_and_chain_notes_are_research_only():
    row = _row(model_market_edge="", expected_value_per_unit="")
    text = "\n".join(sale_ready_risk_items(row) + sale_ready_chain_items(row))

    assert "Research only: edge incomplete." in text
    assert "Do not combine unverified picks." in text
    assert all(term not in text for term in _provider_terms())


def test_positive_edge_risk_and_chain_notes_are_operational():
    row = _row(model_market_edge="0.035", expected_value_per_unit="0.050", risk="volume_ok")
    text = "\n".join(sale_ready_risk_items(row) + sale_ready_chain_items(row))

    assert "Risk status: VOLUME OK." in text
    assert "Straight only: research." in text
    assert all(term not in text for term in _provider_terms())


def test_uploaded_positive_ev_row_is_forced_to_watchlist_not_play():
    row = _row(
        event_name="Bosnia & Herzegovina vs USA",
        away_team="Bosnia & Herzegovina",
        home_team="USA",
        final_decision="PLAY",
        recommendation="PLAY",
        consumer_action="PLAY",
        recommended_action="PLAY",
        risk="FALLBACK MODE",
        risk_level="FALLBACK MODE",
        odds_source="uploaded row",
        odds_status="UPLOADED_ROW",
        american_odds="-256",
        model_market_edge="0.013",
        expected_value_per_unit="0.018",
        units="0.2",
    )

    gated = _force_truthful_gate(row)

    assert gated["final_decision"] == "WATCHLIST"
    assert gated["recommendation"] == "WATCHLIST"
    assert gated["consumer_action"] == "WATCHLIST"
    assert gated["risk"] == "VERIFY PRICE"
    assert gated["risk"] != "FALLBACK MODE"
    assert gated["target_stake_units"] == "0.2"
    assert gated["live_verified_stake_units"] == "0.0"
    assert gated["units"] == "0.2"
    assert gated["display_decimal_odds"] == "1.39"
    assert "NO LIVE ODDS MATCH" in gated["report_truth_severity"]


def test_american_odds_convert_to_decimal_for_magazine_display():
    assert _decimal_text("-256") == "1.39"
    assert _decimal_text("+150") == "2.50"
    assert _decimal_text("1.91") == "1.91"


def test_magazine_preview_and_book_are_two_pages_per_pick():
    renderer = apply_magazine_sale_ready_patch(magazine_book_export)
    row = _row(
        final_decision="PLAY",
        risk="FALLBACK MODE",
        odds_source="uploaded row",
        odds_status="UPLOADED_ROW",
        model_market_edge="0.013",
        expected_value_per_unit="0.018",
    )

    pages = renderer.render_full_magazine_book_pages([row], report_name="ABA Signal Pro", language="en")
    assert len(pages) == 2

    png = renderer.render_full_pick_magazine_page_png(row, report_name="ABA Signal Pro", page_number=1, total_pages=1, language="en")
    image = Image.open(BytesIO(png))
    assert image.height >= magazine_book_export.PAGE_HEIGHT * 2
