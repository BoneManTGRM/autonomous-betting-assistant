from autonomous_betting_agent.chain_core import calculate_chain_probability
from autonomous_betting_agent.decision_core import evaluate_all_gates


def sample(name, price=1.8, p=0.68):
    return {
        "game": name,
        "sport": "MLB",
        "market": "Moneyline",
        "selection": name,
        "decimal_odds": price,
        "model_probability": p,
        "why_pick": "Available analysis supports this row.",
    }


def test_gate_summary_allows_supported_row():
    result = evaluate_all_gates(sample("A"), {"risk_profile": "balanced"})
    assert result.final_decision in {"BET", "SMALL BET"}


def test_chain_probability_multiplies_leg_probabilities():
    assert calculate_chain_probability([sample("A", p=0.70), sample("B", p=0.65)]) == 0.455
