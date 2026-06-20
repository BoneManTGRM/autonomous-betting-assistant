import json

import pandas as pd

from autonomous_betting_agent.adaptive_learning import apply_adaptive_learning


def test_adaptive_learning_boosts_matching_positive_pattern(tmp_path):
    memory = {
        "patterns": [
            {
                "area_type": "sport_market",
                "group_value": "nba|spreads",
                "records": 120,
                "smoothed_edge": 0.08,
                "reliability": 0.9,
            }
        ]
    }
    path = tmp_path / "learning_memory_bank.json"
    path.write_text(json.dumps(memory), encoding="utf-8")
    frame = pd.DataFrame([
        {
            "sport": "NBA",
            "market_type": "spreads",
            "model_probability_clean": 0.62,
            "model_market_edge": 0.03,
            "decimal_price": 1.91,
            "books": 20,
            "api_coverage_score": 1.0,
            "agent_score": 50,
        }
    ])

    out = apply_adaptive_learning(frame, memory_path=path)

    assert out.loc[0, "learning_pattern_count"] >= 1
    assert out.loc[0, "learning_adjustment_score"] > 0
    assert out.loc[0, "learned_agent_score"] > 50


def test_adaptive_learning_penalizes_matching_negative_pattern(tmp_path):
    memory = {
        "patterns": [
            {
                "area_type": "sport_market",
                "group_value": "nba|totals",
                "records": 120,
                "smoothed_edge": -0.08,
                "reliability": 0.9,
            }
        ]
    }
    path = tmp_path / "learning_memory_bank.json"
    path.write_text(json.dumps(memory), encoding="utf-8")
    frame = pd.DataFrame([
        {
            "sport": "NBA",
            "market_type": "totals",
            "model_probability_clean": 0.62,
            "model_market_edge": 0.03,
            "decimal_price": 1.91,
            "books": 20,
            "api_coverage_score": 1.0,
            "agent_score": 50,
        }
    ])

    out = apply_adaptive_learning(frame, memory_path=path)

    assert out.loc[0, "learning_pattern_count"] >= 1
    assert out.loc[0, "learning_adjustment_score"] < 0
    assert out.loc[0, "learned_agent_score"] < 50


def test_adaptive_learning_without_memory_keeps_base_score(tmp_path):
    frame = pd.DataFrame([{"agent_score": 55, "model_probability_clean": 0.61}])

    out = apply_adaptive_learning(frame, memory_path=tmp_path / "missing.json")

    assert out.loc[0, "learning_pattern_count"] == 0
    assert out.loc[0, "learning_adjustment_score"] == 0.0
    assert out.loc[0, "learned_agent_score"] == 55
