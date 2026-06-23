from autonomous_betting_agent.report_card_value_math import (
    market_probability_from_decimal_odds,
    normalize_probability,
    pct_label,
    probability_edge,
    value_rating,
)


def test_market_probability_from_decimal_odds():
    assert round(market_probability_from_decimal_odds(1.85), 4) == 0.5405
    assert round(market_probability_from_decimal_odds('1.30'), 4) == 0.7692
    assert market_probability_from_decimal_odds(1.0) is None
    assert market_probability_from_decimal_odds('') is None


def test_normalize_probability_from_percent_or_decimal():
    assert normalize_probability(0.615) == 0.615
    assert normalize_probability(61.5) == 0.615
    assert normalize_probability(0) == 0
    assert normalize_probability(101) is None
    assert normalize_probability('not-a-number') is None


def test_edge_and_labels_for_official_pick_example():
    edge = probability_edge(0.615, 1.85)
    assert round(edge, 3) == 0.074
    assert pct_label(edge, signed=True) == '+7.4%'
    assert value_rating(edge, 'en') == 'Strong Value'


def test_neutral_edge_when_model_matches_market():
    edge = probability_edge(0.758, 1.32)
    assert abs(edge) < 0.01
    assert value_rating(edge, 'en') == 'Neutral'
