from autonomous_betting_agent.chain_optimizer_report import (
    chain_optimizer_results_to_rows,
    render_chain_optimizer_card,
    render_chain_optimizer_magazine_section,
    split_chain_optimizer_sections,
)
from autonomous_betting_agent.chain_optimizer_v2 import (
    BALANCED_CHAIN,
    NO_CHAIN_RECOMMENDED,
    STRAIGHT_BET_BETTER,
    explain_chain_optimizer_result,
    optimize_chain_candidates,
)


def straight(**overrides):
    row = {
        "selection": "Portugal moneyline",
        "market": "moneyline",
        "model_probability": 0.78,
        "decimal_odds": 1.28,
        "expected_value": -0.01,
        "risk_score": 2.8,
        "game_script": "favorite pressure",
    }
    row.update(overrides)
    return row


def leg(selection, market="team total", probability=0.76, odds=1.30, ev=0.02):
    return {
        "selection": selection,
        "market": market,
        "model_probability": probability,
        "decimal_odds": odds,
        "expected_value": ev,
    }


def make_result():
    return optimize_chain_candidates(
        straight(),
        [
            leg("Portugal team goals over 1.5", probability=0.82, odds=1.25, ev=0.025),
            leg("Uzbekistan cards over 0.5", market="cards", probability=0.78, odds=1.24, ev=0.015),
        ],
        client_profile={"risk_profile": "balanced"},
    )


def test_card_includes_title_straight_comparison_and_safety_warning():
    card = render_chain_optimizer_card(make_result())
    assert "CHAIN BET OPTIMIZER v2" in card
    assert "Straight Bet vs Chain" in card
    assert "This is not a guaranteed result" in card


def test_summary_splits_approved_chains_into_correct_section():
    result = make_result()
    sections = split_chain_optimizer_sections([result])
    if result.final_recommendation in {"SMALL CHAIN", BALANCED_CHAIN}:
        assert result in sections["Best Approved Chains"]
    else:
        assert sum(result in values for values in sections.values()) == 1


def test_straight_bet_better_section():
    result = optimize_chain_candidates(
        straight(expected_value=0.08, risk_score=2.0),
        [
            leg("Bad add-on", probability=0.45, odds=1.20, ev=-0.08),
            leg("Random filler", market="prop", probability=0.30, odds=2.0, ev=-0.10),
        ],
        client_profile={"risk_profile": "balanced"},
    )
    sections = split_chain_optimizer_sections([result])
    if result.final_recommendation == STRAIGHT_BET_BETTER or result.comparison.straight_bet_better:
        assert result in sections["Straight Bet Better Than Chain"]


def test_no_chain_recommended_section():
    result = optimize_chain_candidates(straight(), [], client_profile={"risk_profile": "balanced"})
    assert result.final_recommendation == NO_CHAIN_RECOMMENDED
    sections = split_chain_optimizer_sections([result])
    assert result in sections["No Chain Recommended"]


def test_csv_rows_include_chain_optimizer_fields():
    rows = chain_optimizer_results_to_rows([make_result()])
    assert rows
    row = rows[0]
    assert row["chain_optimizer_version"] == "v2"
    assert "final_recommendation" in row
    assert "straight_pick" in row
    assert "chain_probability" in row
    assert "safety_warning" in row


def test_magazine_section_includes_required_sections():
    text = render_chain_optimizer_magazine_section([make_result(), optimize_chain_candidates(straight(), [], client_profile={"risk_profile": "balanced"})])
    assert "## Chain Bet Optimizer v2" in text
    assert "### Best Approved Chains" in text
    assert "### No Chain Recommended" in text
    assert "This is not a guaranteed result" in text or "projected probabilities" in text


def test_existing_explainer_still_works():
    text = explain_chain_optimizer_result(make_result())
    assert "Straight Bet vs Chain" in text
