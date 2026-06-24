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
    assert pick.why_pick_bullets
    assert "Final Confidence" in pick.evidence_scores
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
    assert "Final Recommendation" in magazine
    assert "SMALL BET" in magazine


def test_magazine_pro_evidence_uses_sport_specific_fields():
    row = {
        "game": "Yankees vs Red Sox",
        "sport": "MLB Baseball",
        "bet_type": "Moneyline",
        "exact_bet": "Yankees ML",
        "sportsbook": "Caliente",
        "decimal_odds": 1.72,
        "model_probability": 0.69,
        "injury_report": "Opponent cleanup hitter out",
        "starting_lineups": "Projected starters confirmed",
        "pitcher_handedness": "LHP vs RHB-heavy lineup",
        "bullpen_fatigue": "Boston used top relievers yesterday",
        "wind_speed": "12 mph blowing out",
        "market_movement": "Moved -125 to -135",
        "line_shopping_score": 82,
    }

    pick = build_catalog_pick(row)
    card = render_betting_magazine([row])

    assert any("Injury edge" in bullet for bullet in pick.why_pick_bullets)
    assert any("L/R split" in bullet for bullet in pick.why_pick_bullets)
    assert "Why We Picked It" in card
    assert "Evidence Scores" in card
    assert "Pro Notes" in card
