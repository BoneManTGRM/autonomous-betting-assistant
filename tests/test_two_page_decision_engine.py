import math

import pandas as pd

from autonomous_betting_agent.two_page_decision_engine import (
    DATA_UNAVAILABLE,
    FLASH_UNAVAILABLE,
    NO_BET,
    PLAYABLE,
    REJECTED,
    WATCHLIST,
    american_to_decimal,
    append_two_page_decision_columns,
    build_parlay_candidate,
    build_two_page_decision_engine,
    decimal_to_american,
    expected_value,
    implied_probability,
)


def test_odds_math_foundation_decimal_and_american():
    assert round(american_to_decimal(-150), 3) == 1.667
    assert round(american_to_decimal(200), 3) == 3.0
    assert decimal_to_american(2.5) == 150
    assert decimal_to_american(1.5) == -200
    assert round(implied_probability(2.5), 3) == 0.4
    assert round(expected_value(0.5, 2.5), 3) == 0.25


def test_page1_selects_positive_ev_not_highest_confidence_only():
    rows = pd.DataFrame([
        {
            "event": "Mexico vs Ecuador",
            "sport": "soccer",
            "prediction": "Mexico ML",
            "market_type": "moneyline",
            "decimal_odds": 1.5,
            "model_probability": 0.72,
            "market_completeness_status": "complete",
            "sportsbook": "Book A",
            "sportsbook_count": 3,
        },
        {
            "event": "Brazil vs Chile",
            "sport": "soccer",
            "prediction": "Brazil ML",
            "market_type": "moneyline",
            "decimal_odds": 2.2,
            "model_probability": 0.55,
            "market_completeness_status": "complete",
            "sportsbook": "Book B",
            "sportsbook_count": 3,
        },
    ])

    bundle = build_two_page_decision_engine(rows)

    assert bundle.page1["unique_event_key"] == "brazil vs chile"
    assert bundle.page1["EV"] > 0
    assert bundle.page1["model_probability"] == 0.55


def test_no_bet_blocks_stale_started_negative_ev_and_incomplete_market():
    rows = pd.DataFrame([
        {
            "event": "A vs B",
            "sport": "basketball",
            "prediction": "A ML",
            "decimal_odds": 1.2,
            "model_probability": 0.70,
            "market_completeness_status": "incomplete",
            "event_started": True,
            "odds_stale": True,
        }
    ])

    bundle = build_two_page_decision_engine(rows)

    diag = bundle.diagnostics[0]
    assert diag["bet_status"] == NO_BET
    assert "event already started" in diag["no_bet_reasons"]
    assert "stale odds" in diag["no_bet_reasons"]
    assert "incomplete market" in diag["no_bet_reasons"]
    assert "negative EV" in diag["no_bet_reasons"]


def test_consensus_only_is_watchlist_not_fake_line_shopping():
    rows = pd.DataFrame([
        {
            "event": "C vs D",
            "sport": "tennis",
            "prediction": "C ML",
            "decimal_odds": 2.1,
            "model_probability": 0.52,
            "market_completeness_status": "complete",
            "sportsbook": "consensus_average",
        }
    ])

    bundle = build_two_page_decision_engine(rows)

    diag = bundle.diagnostics[0]
    assert diag["bet_status"] == WATCHLIST
    assert diag["line_shopping_available"] is False
    assert "consensus-only" in diag["line_shopping_status"]


def test_page2_independent_parlay_calculates_combined_odds_probability_and_ev():
    rows = pd.DataFrame([
        {
            "event": "E1",
            "sport": "soccer",
            "prediction": "Leg 1",
            "market_type": "moneyline",
            "decimal_odds": 2.0,
            "model_probability": 0.6,
            "market_completeness_status": "complete",
            "sportsbook": "Book A",
            "sportsbook_count": 2,
        },
        {
            "event": "E2",
            "sport": "basketball",
            "prediction": "Leg 2",
            "market_type": "spread",
            "decimal_odds": 1.9,
            "model_probability": 0.58,
            "market_completeness_status": "complete",
            "sportsbook": "Book B",
            "sportsbook_count": 2,
        },
    ])

    bundle = build_two_page_decision_engine(rows)
    parlay = bundle.page2["best_conservative_parlay"]

    assert parlay["status"] == PLAYABLE
    assert round(parlay["combined_parlay_odds"], 3) == 3.8
    assert round(parlay["combined_model_probability"], 3) == 0.348
    assert round(parlay["parlay_EV"], 3) == 0.322
    assert parlay["estimated_parlay_price"] is True
    assert parlay["sportsbook_parlay_price_available"] is False


def test_page2_rejects_same_game_correlated_parlay_when_joint_probability_unavailable():
    legs = [
        {
            "unique_event_key": "mexico vs ecuador",
            "unique_pick_key": "mexico vs ecuador|moneyline|mexico",
            "decimal_odds": 1.7,
            "model_probability": 0.65,
        },
        {
            "unique_event_key": "mexico vs ecuador",
            "unique_pick_key": "mexico vs ecuador|total|over 2.5",
            "decimal_odds": 1.8,
            "model_probability": 0.60,
        },
    ]

    parlay = build_parlay_candidate(legs, "same-game test")

    assert parlay["status"] == REJECTED
    assert parlay["correlation_rating"] == "same-game correlated"
    assert "joint probability unavailable" in parlay["rejection_reason"]


def test_provider_capability_prevents_fake_flash_and_unsupported_props():
    rows = pd.DataFrame([
        {
            "event": "Mexico vs Ecuador",
            "sport": "soccer",
            "market_type": "moneyline",
            "decimal_odds": 2.0,
            "model_probability": 0.55,
            "market_completeness_status": "complete",
            "sportsbook": "Book A",
            "sportsbook_count": 2,
        }
    ])

    bundle = build_two_page_decision_engine(rows)

    assert bundle.provider_capabilities[0]["player_props_available"] is False
    assert bundle.provider_capabilities[0]["live_odds_available"] is False
    assert bundle.page2["best_prop_opportunity"] == DATA_UNAVAILABLE
    assert bundle.page2["best_live_flash_bet_trigger"] == FLASH_UNAVAILABLE


def test_append_two_page_decision_columns_does_not_mutate_source():
    source = pd.DataFrame([
        {
            "event": "E1",
            "sport": "soccer",
            "prediction": "Leg 1",
            "decimal_odds": 2.0,
            "model_probability": 0.6,
            "market_completeness_status": "complete",
        }
    ])
    original_columns = list(source.columns)

    enriched = append_two_page_decision_columns(source)

    assert list(source.columns) == original_columns
    assert "two_page_raw_EV" in enriched.columns
    assert math.isclose(enriched.loc[0, "two_page_raw_EV"], 0.2)
