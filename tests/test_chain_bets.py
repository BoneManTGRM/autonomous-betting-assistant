from autonomous_betting_agent.chain_bets import build_small_chain_candidates, best_near_double_chains


def _row(game, bet, odds, probability, ev=0.08):
    return {
        "game": game,
        "sport": "MLB Baseball",
        "bet_type": "Moneyline",
        "exact_bet": bet,
        "sportsbook": "Caliente",
        "decimal_odds": odds,
        "model_probability": probability,
        "expected_value": ev,
        "why_pick": "Sports analysis and odds value both support this leg.",
        "why_lose": "Normal baseball variance can still beat the read.",
    }


def test_small_chain_builder_creates_positive_ev_chain_only():
    rows = [
        _row("Dodgers vs Padres", "Dodgers ML", 1.60, 0.72, 0.12),
        _row("Yankees vs Red Sox", "Yankees TT Over 3.5", 1.70, 0.70, 0.19),
        _row("Mets vs Phillies", "Mets F5 ML", 1.66, 0.69, 0.14),
    ]

    chains = build_small_chain_candidates(rows, min_legs=2, max_legs=2)

    assert chains
    assert chains[0]["bet_type"] == "Chain Bet"
    assert chains[0]["combined_adjusted_probability"] > 0
    assert chains[0]["expected_value"] > 0
    assert chains[0]["final_decision"] in {"SMALL BET", "AGGRESSIVE ONLY"}
    assert len(chains[0]["legs"]) == 2


def test_near_double_chains_are_ranked_by_distance_to_decimal_two():
    rows = [
        _row("Dodgers vs Padres", "Dodgers ML", 1.45, 0.80, 0.16),
        _row("Yankees vs Red Sox", "Yankees TT Over 3.5", 1.42, 0.80, 0.14),
        _row("Mets vs Phillies", "Mets F5 ML", 1.80, 0.66, 0.18),
    ]

    chains = best_near_double_chains(rows, limit=3)

    assert chains
    assert abs(chains[0]["decimal_odds"] - 2.0) <= abs(chains[-1]["decimal_odds"] - 2.0)
