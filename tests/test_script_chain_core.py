from autonomous_betting_agent.script_chain_core import (
    SCRIPT_DOMINANT_FAVORITE,
    build_target_payout_chain,
    calculate_required_decimal_odds,
    classify_game_script,
    find_game_script_legs,
)


def event_row():
    return {
        "game": "Portugal vs Uzbekistan",
        "favorite": "Portugal",
        "underdog": "Uzbekistan",
        "favorite_probability": 0.78,
        "possession_edge": 0.7,
        "decimal_odds": 1.28,
        "expected_value": -0.02,
    }


def market(label, probability, odds, ev=0.02):
    return {
        "game": "Portugal vs Uzbekistan",
        "market": label,
        "exact_bet": label,
        "model_probability": probability,
        "decimal_odds": odds,
        "expected_value": ev,
    }


def portugal_markets():
    return [
        market("Portugal moneyline", 0.78, 1.28, -0.02),
        market("Portugal team goals over 1.5", 0.67, 1.35, 0.03),
        market("Uzbekistan corners over 1.5", 0.64, 1.32, 0.02),
        market("Uzbekistan cards over 0.5", 0.72, 1.22, 0.01),
        market("Random filler long shot", 0.12, 9.00, -0.4),
    ]


def test_classifies_portugal_style_dominant_favorite_script():
    assert classify_game_script(event_row()) == SCRIPT_DOMINANT_FAVORITE


def test_leg_finder_rejects_random_filler():
    legs = find_game_script_legs(event_row(), portugal_markets())
    accepted = [leg for leg in legs if not leg.rejected]
    rejected = [leg for leg in legs if leg.rejected]
    assert len(accepted) >= 3
    assert any("Random filler" in leg.leg for leg in rejected)


def test_required_decimal_odds_for_target_payout():
    assert calculate_required_decimal_odds(75000, 150000) == 2.0


def test_target_payout_chain_builds_leg_explanations():
    result = build_target_payout_chain(event_row(), portugal_markets(), 75000, 143000, {"risk_profile": "balanced", "max_chain_legs": 4}, minimum_probability=0.20, maximum_risk_score=9.0)
    assert not isinstance(result, str)
    assert result.chain_quality_score >= 60
    assert result.leg_explanations
    assert "guarantee" not in result.why_chain.lower()
