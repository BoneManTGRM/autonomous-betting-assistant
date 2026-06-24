import os

from autonomous_betting_agent.api_config import available_api_sources, get_secret, has_api_football
from autonomous_betting_agent.api_football_client import normalize_api_football_fixture, normalize_api_football_odds
from autonomous_betting_agent.external_context import apply_context_to_pick, merge_context_signals
from autonomous_betting_agent.news_context import extract_news_risk_flags, summarize_news_context
from autonomous_betting_agent.perplexity_research import extract_research_flags, summarize_research_for_report


def test_missing_api_key_does_not_crash(monkeypatch):
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)
    assert has_api_football() is False
    assert "api-football" not in available_api_sources()


def test_config_reads_environment(monkeypatch):
    monkeypatch.setenv("API_FOOTBALL_KEY", "test-key")
    assert get_secret("API_FOOTBALL_KEY") == "test-key"
    assert has_api_football() is True


def test_api_football_fixture_normalization():
    raw = {
        "fixture": {"id": 123, "date": "2026-06-24T20:00:00Z"},
        "league": {"name": "World Cup"},
        "teams": {"home": {"name": "Portugal"}, "away": {"name": "Uzbekistan"}},
    }
    row = normalize_api_football_fixture(raw)
    assert row["game"] == "Portugal vs Uzbekistan"
    assert row["fixture_id"] == 123
    assert row["source"] == "api-football"


def test_api_football_odds_normalization():
    raw = {
        "fixture": {"id": 123, "date": "2026-06-24T20:00:00Z"},
        "league": {"name": "World Cup"},
        "teams": {"home": {"name": "Portugal"}, "away": {"name": "Uzbekistan"}},
        "bookmakers": [{"name": "Book", "bets": [{"name": "Winner", "values": [{"value": "Portugal", "odd": "1.25"}]}]}],
    }
    rows = normalize_api_football_odds(raw)
    assert rows[0]["selection"] == "Portugal"
    assert rows[0]["decimal_odds"] == 1.25


def test_perplexity_flag_extraction():
    text = "Starter is doubtful with injury. Lineup rotation is possible."
    flags = extract_research_flags(text)
    assert flags["injury_flags"]
    assert flags["lineup_flags"]
    summary = summarize_research_for_report(text)
    assert summary["confidence_adjustment"] < 0


def test_news_flag_extraction():
    articles = [{"title": "Key player injury concern", "description": "Lineup doubt before match", "source": {"name": "Test"}}]
    flags = extract_news_risk_flags(articles)
    assert flags["injury_news"]
    assert "Key player" in summarize_news_context(articles)


def test_external_context_merge_and_no_bet_flag():
    context = merge_context_signals(
        {"rows": [], "warnings": []},
        {"research_summary": "Player out injured", "injury_flags": ["Player out injured"], "confidence_adjustment": -0.04},
        {"news_summary": "Injury report", "injury_news": ["Player out"], "confidence_adjustment": -0.05},
    )
    assert context.context_effect == "weakened"
    assert context.risk_adjustment > 0
    assert context.no_bet_flags


def test_external_context_cannot_upgrade_bad_ev_to_bet():
    context = merge_context_signals({}, {"research_summary": "Healthy and full strength", "confidence_adjustment": 0.04}, {})
    row = {"game": "A vs B", "model_probability": 0.50, "expected_value": -0.2, "final_decision": "BAD VALUE"}
    enriched = apply_context_to_pick(row, context)
    assert enriched["final_decision"] == "BAD VALUE"
