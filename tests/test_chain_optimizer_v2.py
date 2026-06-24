from autonomous_betting_agent.chain_optimizer_v2 import (
    AGGRESSIVE_ONLY,
    BALANCED_CHAIN,
    CONTRADICTORY_CORRELATION,
    NO_CHAIN_RECOMMENDED,
    POSITIVE_CORRELATION,
    SMALL_CHAIN,
    STRAIGHT_BET_BETTER,
    WATCH_ONLY,
    compare_straight_bet_vs_chain,
    evaluate_chain_killers,
    explain_chain_optimizer_result,
    optimize_chain_candidates,
    score_chain_leg,
    score_correlation_quality,
)


def straight_pick(**overrides):
    row = {
        "selection": "Portugal moneyline",
        "market": "moneyline",
        "model_probability": 0.78,
        "decimal_odds": 1.28,
        "expected_value": -0.0016,
        "risk_score": 2.8,
        "game_script": "dominant favorite pressure",
    }
    row.update(overrides)
    return row


def leg(selection, market="prop", probability=0.65, odds=1.35, ev=0.02):
    return {
        "selection": selection,
        "market": market,
        "model_probability": probability,
        "decimal_odds": odds,
        "expected_value": ev,
    }


def test_straight_bet_beats_bad_chain():
    chain = [
        leg("Portugal team goals over 1.5", probability=0.60, odds=1.25, ev=-0.08),
        leg("Random filler long shot", probability=0.18, odds=6.0, ev=-0.20),
    ]
    comparison = compare_straight_bet_vs_chain(straight_pick(expected_value=0.05), chain)
    assert comparison.final_recommendation in {STRAIGHT_BET_BETTER, NO_CHAIN_RECOMMENDED}


def test_chain_can_pass_when_probability_and_risk_justify_it():
    result = optimize_chain_candidates(
        straight_pick(expected_value=-0.01),
        [
            leg("Portugal team goals over 1.5", probability=0.88, odds=1.20, ev=0.04),
            leg("Uzbekistan cards over 0.5", probability=0.76, odds=1.25, ev=0.02),
        ],
        client_profile={"risk_profile": "balanced"},
    )
    assert result.final_recommendation in {SMALL_CHAIN, BALANCED_CHAIN, AGGRESSIVE_ONLY, WATCH_ONLY}
    assert result.comparison.chain_probability is not None


def test_random_filler_leg_rejected():
    scored = score_chain_leg(leg("Random filler long shot", probability=0.25, odds=5.0, ev=-0.20))
    assert scored.accepted is False
    assert "Random filler" in scored.rejection_reason


def test_duplicate_market_rejected_by_killer():
    chain = [
        leg("Portugal moneyline", market="moneyline", probability=0.78, odds=1.28, ev=0.01),
        leg("Portugal moneyline", market="moneyline", probability=0.78, odds=1.28, ev=0.01),
    ]
    killers = evaluate_chain_killers(chain, straight_pick=straight_pick())
    assert killers.has_killer
    assert any("Duplicate" in reason for reason in killers.killer_reasons)


def test_contradictory_correlation_rejected():
    chain = [
        leg("Portugal moneyline", market="moneyline", probability=0.78, odds=1.28, ev=0.01),
        leg("Portugal under 0.5 team goals", market="team total", probability=0.22, odds=4.0, ev=-0.12),
    ]
    correlation = score_correlation_quality(chain)
    assert correlation.correlation_label == CONTRADICTORY_CORRELATION
    assert evaluate_chain_killers(chain).has_killer


def test_conservative_client_blocks_aggressive_chain():
    result = optimize_chain_candidates(
        straight_pick(),
        [
            leg("Player home run", market="player prop", probability=0.22, odds=5.0, ev=0.01),
            leg("Portugal team goals over 1.5", probability=0.70, odds=1.35, ev=0.02),
            leg("Uzbekistan cards over 0.5", probability=0.70, odds=1.30, ev=0.01),
        ],
        client_profile={"risk_profile": "conservative"},
    )
    assert result.final_recommendation in {WATCH_ONLY, NO_CHAIN_RECOMMENDED, "GOOD PAYOUT FIT, BAD CHAIN — WATCH ONLY"}


def test_target_payout_fit_cannot_override_bad_ev():
    result = optimize_chain_candidates(
        straight_pick(expected_value=0.02),
        [
            leg("Bad value add-on", probability=0.55, odds=1.20, ev=-0.15),
            leg("Random filler payout", probability=0.40, odds=1.70, ev=-0.10),
        ],
        target_payout=200,
        stake=100,
        client_profile={"risk_profile": "balanced"},
    )
    assert result.final_recommendation in {WATCH_ONLY, NO_CHAIN_RECOMMENDED, STRAIGHT_BET_BETTER, "GOOD PAYOUT FIT, BAD CHAIN — WATCH ONLY"}


def test_below_twenty_percent_probability_watch_only_or_no_chain():
    result = optimize_chain_candidates(
        straight_pick(),
        [
            leg("Long shot one", probability=0.30, odds=3.0, ev=-0.10),
            leg("Long shot two", probability=0.30, odds=3.0, ev=-0.10),
            leg("Long shot three", probability=0.30, odds=3.0, ev=-0.10),
        ],
        client_profile={"risk_profile": "aggressive"},
    )
    assert result.comparison.chain_probability is None or result.comparison.chain_probability < 0.20
    assert result.final_recommendation in {WATCH_ONLY, NO_CHAIN_RECOMMENDED, STRAIGHT_BET_BETTER, "GOOD PAYOUT FIT, BAD CHAIN — WATCH ONLY"}


def test_positive_script_correlation_label():
    chain = [
        leg("Portugal moneyline", market="moneyline", probability=0.78, odds=1.28, ev=0.01),
        leg("Portugal team goals over 1.5", market="team total", probability=0.70, odds=1.40, ev=0.03),
    ]
    correlation = score_correlation_quality(chain, script="favorite pressure")
    assert correlation.correlation_label == POSITIVE_CORRELATION


def test_report_output_includes_straight_vs_chain_comparison():
    result = optimize_chain_candidates(
        straight_pick(expected_value=-0.01),
        [
            leg("Portugal team goals over 1.5", probability=0.82, odds=1.22, ev=0.02),
            leg("Uzbekistan cards over 0.5", probability=0.78, odds=1.24, ev=0.01),
        ],
        client_profile={"risk_profile": "balanced"},
    )
    report = explain_chain_optimizer_result(result)
    assert "Straight Bet vs Chain" in report
    assert "This is not a guaranteed result" in report
