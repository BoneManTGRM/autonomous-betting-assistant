from autonomous_betting_agent.report_source_quality_guard import source_quality_score


def test_source_quality_prefers_independent_model_rows_over_plain_odds_rows():
    stale_locked = [
        {
            "event": "A vs B",
            "prediction": "A",
            "decimal_price": 1.91,
            "model_probability_source": "market_baseline_only",
            "market_probability": 0.52356,
            "model_probability": 0.52356,
        }
    ]
    fresh_predictor = [
        {
            "event": "C vs D",
            "prediction": "C",
            "decimal_price": 2.05,
            "model_probability_clean": 0.61,
            "model_market_edge": 0.122,
            "model_probability_source": "pro_predictor_fusion",
        }
    ]

    assert source_quality_score("pro_predictor_latest_rows", fresh_predictor, 1) > source_quality_score("odds_lock_pro_locked_rows", stale_locked, 0)


def test_source_quality_does_not_promote_exact_market_probability_copy():
    rows = [
        {
            "event": "A vs B",
            "prediction": "A",
            "decimal_price": 2.0,
            "market_probability": 0.5,
            "model_probability": 0.5,
        }
    ]

    assert source_quality_score("fresh_odds_slate_builder_rows", rows, 0)[0] == 0


def test_source_quality_accepts_explicit_learned_probability_even_when_near_market():
    rows = [
        {
            "event": "A vs B",
            "prediction": "A",
            "decimal_price": 2.0,
            "market_probability": 0.5,
            "learned_model_probability": 0.5,
        }
    ]

    assert source_quality_score("pro_predictor_latest_rows", rows, 0)[0] == 1
