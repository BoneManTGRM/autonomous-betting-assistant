from autonomous_betting_agent.bet_catalog import (
    build_bet_catalog,
    build_catalog_pick,
    render_betting_magazine,
)


def test_core_pick_passes_65_catalog_when_analysis_and_odds_value_pass():
    row = {
        "game": "Dodgers vs Padres",
        "sport": "MLB Baseball",
        "bet_type": "Moneyline",
        "exact_bet": "Dodgers Moneyline",
        "sportsbook": "Caliente",
        "decimal_odds": 1.75,
        "model_probability": 0.68,
        "why_pick": "Starting pitcher edge, bullpen rest, and lineup form support the Dodgers.",
        "why_lose": "Late lineup changes or bullpen variance could flip the edge.",
    }

    pick = build_catalog_pick(row)

    assert pick.passes_65_filter is True
    assert pick.final_decision == "BET"
    assert pick.game == "Dodgers vs Padres"
    assert "Dodgers Moneyline" in pick.exact_bet
    assert pick.edge is not None and pick.edge > 0
    assert build_bet_catalog([row])["Best 65%+ Singles"]


def test_good_read_bad_price_is_not_recommended():
    row = {
        "game": "Yankees vs Red Sox",
        "bet_type": "Moneyline",
        "exact_bet": "Yankees Moneyline",
        "decimal_odds": 1.30,
        "model_probability": 0.66,
        "why_pick": "The model likes the team side, but the market price is short.",
    }

    pick = build_catalog_pick(row)
    catalog = build_bet_catalog([row])

    assert pick.passes_65_filter is True
    assert pick.final_decision == "GOOD READ, BAD PRICE"
    assert catalog["Good Read / Bad Price"]
    assert not catalog["Best 65%+ Singles"]


def test_chain_probability_uses_combined_adjusted_probability_and_magazine_label():
    row = {
        "game": "Baseball Chain A",
        "bet_type": "Chain Bet",
        "exact_bet": "Dodgers ML + Yankees team total over 3.5",
        "decimal_odds": 2.65,
        "combined_adjusted_probability": 0.432,
        "why_pick": "Both legs pass analysis and odds gates, but combined probability is below 65%.",
        "legs": [
            {"exact_bet": "Dodgers ML", "model_probability": 0.68},
            {"exact_bet": "Yankees TT Over 3.5", "model_probability": 0.66},
        ],
    }

    pick = build_catalog_pick(row)
    magazine = render_betting_magazine([row])

    assert pick.passes_65_filter is False
    assert pick.chain_combined_probability == 0.432
    assert "Chain Combined Adjusted Probability: 43.2%" in magazine
    assert "Final Recommendation: SMALL BET" in magazine
