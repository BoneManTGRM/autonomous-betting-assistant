from autonomous_betting_agent.chain_optimizer_integration import (
    build_chain_optimizer_results,
    select_best_straight_pick,
    select_candidate_chain_legs,
)


def row(selection, market, probability, odds, ev, **extra):
    data = {
        "game": "Portugal vs Uzbekistan",
        "selection": selection,
        "market": market,
        "model_probability": probability,
        "decimal_odds": odds,
        "expected_value": ev,
        "risk_score": 4,
    }
    data.update(extra)
    return data


def test_select_best_straight_pick_prefers_ev_and_core_market():
    rows = [
        row("Player home run", "player prop", 0.25, 5.0, 0.10),
        row("Portugal moneyline", "moneyline", 0.78, 1.28, 0.02),
        row("Random filler", "prop", 0.70, 1.10, 0.03),
    ]
    best = select_best_straight_pick(rows)
    assert best is not None
    assert best["selection"] == "Portugal moneyline"


def test_select_candidate_chain_legs_excludes_duplicate_and_result_rows():
    straight = row("Portugal moneyline", "moneyline", 0.78, 1.28, 0.02)
    rows = [
        straight,
        row("Portugal moneyline", "moneyline", 0.78, 1.28, 0.02),
        row("Portugal team goals over 1.5", "team total", 0.75, 1.30, 0.03),
        row("Finished leg", "cards", 0.75, 1.20, 0.02, result_status="win"),
    ]
    legs = select_candidate_chain_legs(rows, straight)
    assert len(legs) == 1
    assert legs[0]["selection"] == "Portugal team goals over 1.5"


def test_build_chain_optimizer_results_groups_by_game():
    rows = [
        row("Portugal moneyline", "moneyline", 0.78, 1.28, 0.02),
        row("Portugal team goals over 1.5", "team total", 0.76, 1.30, 0.03),
        row("Uzbekistan cards over 0.5", "cards", 0.74, 1.25, 0.01),
    ]
    results = build_chain_optimizer_results(rows, client_profile={"risk_profile": "balanced"})
    assert len(results) == 1
    assert results[0].comparison.straight_pick
