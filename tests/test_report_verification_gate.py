from __future__ import annotations

import importlib


def test_report_gate_imports_and_classifies_row():
    gate = importlib.import_module("autonomous_betting_agent.report_verification_gate")
    row = {
        "event": "A vs C",
        "provider_event_id": "evt1",
        "market_type": "moneyline",
        "selection": "A",
        "decimal_price": 2.0,
        "model_probability": 0.56,
        "model_market_edge": 0.06,
        "expected_value_per_unit": 0.12,
        "provider_verified": "true",
        "timestamp": "now",
        "book": "Book A",
    }
    out = gate.classify_report_row(row)
    assert out["report_verification_class"] == gate.VERIFIED_BUYER_PICK
    assert len(gate.build_report_rows([row])) == 1


def test_report_gate_requires_provider_match_for_default_report():
    gate = importlib.import_module("autonomous_betting_agent.report_verification_gate")
    row = {
        "event": "A vs C",
        "provider_event_id": "evt1",
        "market_type": "moneyline",
        "selection": "A",
        "decimal_price": 2.0,
        "model_probability": 0.56,
        "model_market_edge": 0.06,
        "expected_value_per_unit": 0.12,
        "timestamp": "now",
        "book": "Book A",
    }
    status = gate.classify_report_row(row)["report_verification_class"]
    assert status == gate.WATCHLIST_VERIFY_PRICE
    rows = gate.build_report_rows([row])
    assert rows[0]["event"] == gate.NO_VERIFIED_MESSAGE


def test_report_gate_rejects_negative_value():
    gate = importlib.import_module("autonomous_betting_agent.report_verification_gate")
    row = {
        "event": "A vs C",
        "provider_event_id": "evt1",
        "market_type": "moneyline",
        "selection": "A",
        "decimal_price": 2.0,
        "model_probability": 0.48,
        "model_market_edge": -0.02,
        "expected_value_per_unit": -0.04,
        "provider_verified": "true",
        "timestamp": "now",
        "book": "Book A",
    }
    out = gate.classify_report_row(row)
    assert out["report_verification_class"] == gate.NO_PRICE_REJECTED
    assert out["risk"] == "PRICE REJECTED"


def test_report_gate_requires_exact_market_line():
    gate = importlib.import_module("autonomous_betting_agent.report_verification_gate")
    row = {
        "event": "A vs C",
        "provider_event_id": "evt1",
        "market_type": "spread",
        "selection": "A",
        "prediction": "Spread: A",
        "decimal_price": 2.0,
        "model_probability": 0.56,
        "model_market_edge": 0.06,
        "expected_value_per_unit": 0.12,
        "provider_verified": "true",
        "timestamp": "now",
        "book": "Book A",
    }
    assert gate.classify_report_row(row)["report_verification_class"] == gate.RESEARCH_ONLY


def test_report_gate_top_hundred_limit():
    gate = importlib.import_module("autonomous_betting_agent.report_verification_gate")
    rows = []
    for index in range(120):
        rows.append({
            "event": f"A{index} vs C{index}",
            "provider_event_id": f"evt{index}",
            "market_type": "moneyline",
            "selection": f"A{index}",
            "decimal_price": 2.0,
            "model_probability": 0.56,
            "model_market_edge": 0.06,
            "expected_value_per_unit": 0.12 + index / 1000,
            "provider_verified": "true",
            "timestamp": "now",
            "book": "Book A",
        })
    assert len(gate.build_report_rows(rows)) == 100


def test_report_gate_page_two_requires_verified_advanced_market():
    gate = importlib.import_module("autonomous_betting_agent.report_verification_gate")
    row = {
        "event": "A vs C",
        "provider_event_id": "evt1",
        "market_type": "moneyline",
        "selection": "A",
        "decimal_price": 2.0,
        "model_probability": 0.56,
        "model_market_edge": 0.06,
        "expected_value_per_unit": 0.12,
        "provider_verified": "true",
        "timestamp": "now",
        "book": "Book A",
    }
    assert not gate.should_render_page_two(row)
    row["verified_advanced_market"] = "true"
    assert gate.should_render_page_two(row)
    marker = gate.build_report_rows([row])[0]["report_renderer_marker"]
    assert f"Renderer: {gate.VERSION}" in marker


def _page2_row(**extra):
    row = {
        "event": "Seattle Storm vs Phoenix Mercury",
        "provider_event_id": "wnba-1",
        "sport": "WNBA",
        "market_type": "spread",
        "prediction": "Spread: Phoenix Mercury -1.5",
        "selection": "Phoenix Mercury",
        "line": "-1.5",
        "spread_line": "-1.5",
        "decimal_price": 1.65,
        "model_probability": 0.64,
        "model_market_edge": 0.034,
        "expected_value_per_unit": 0.056,
        "provider_verified": "true",
        "timestamp": "now",
        "provider": "Odds API",
        "book": "Book A",
        "sportsbook": "Book A",
    }
    row.update(extra)
    return row


def test_page2_returns_straight_anchor_only_when_no_second_leg():
    page2 = importlib.import_module("autonomous_betting_agent.magazine_second_page_patch")
    parlays, diag = page2.generate_parlay_candidates(_page2_row())
    assert diag["eligible_legs"] == 1
    assert not [p for p in parlays if p.status == page2.PARLAY_PLAYABLE]
    title, detail, _color = page2._final_status(_page2_row(), "en")
    assert title == page2.STRAIGHT_ANCHOR_ONLY
    assert "Straight anchor only" in detail


def test_page2_generates_cross_game_two_leg_when_second_verified_leg_exists():
    page2 = importlib.import_module("autonomous_betting_agent.magazine_second_page_patch")
    row = _page2_row(advanced_market_rows=[{
        "event_id": "wnba-2",
        "provider_event_id": "wnba-2",
        "market": "moneyline",
        "selection": "New York Liberty",
        "line": "moneyline",
        "decimal_odds": 1.8,
        "model_probability": 0.62,
        "edge": 0.064,
        "ev": 0.116,
        "provider": "Odds API",
        "sportsbook": "Book A",
        "timestamp": "now",
        "provider_verified": "true",
    }])
    parlays, diag = page2.generate_parlay_candidates(row)
    conditional = [p for p in parlays if p.status == page2.PARLAY_WATCHLIST]
    assert diag["eligible_legs"] >= 2
    assert conditional
    assert conditional[0].pricing_source == page2.SYNTHETIC_PRODUCT_PRICE


def test_same_game_without_sgp_price_is_blocked():
    page2 = importlib.import_module("autonomous_betting_agent.magazine_second_page_patch")
    row = _page2_row(advanced_market_rows=[{
        "event_id": "wnba-1",
        "provider_event_id": "wnba-1",
        "market": "team total",
        "selection": "Phoenix Mercury over",
        "line": "82.5",
        "decimal_odds": 1.9,
        "model_probability": 0.58,
        "edge": 0.054,
        "ev": 0.102,
        "provider": "Odds API",
        "sportsbook": "Book A",
        "timestamp": "now",
        "provider_verified": "true",
    }])
    parlays, _diag = page2.generate_parlay_candidates(row)
    same_game = [p for p in parlays if "same-game" in p.parlay_type]
    assert same_game
    assert all(p.status != page2.PARLAY_PLAYABLE for p in same_game)
    assert any("Same-game correlation cannot be priced" in p.reason for p in same_game)


def test_player_prop_without_model_probability_is_not_playable():
    page2 = importlib.import_module("autonomous_betting_agent.magazine_second_page_patch")
    row = _page2_row(player_prop_markets=[{
        "event_id": "wnba-2",
        "provider_event_id": "wnba-2",
        "market": "player points",
        "selection": "Player A over",
        "line": "18.5",
        "decimal_odds": 1.9,
        "provider": "Odds API",
        "sportsbook": "Book A",
        "timestamp": "now",
        "provider_verified": "true",
    }])
    markets, _diag = page2.discover_markets(row)
    player_markets = [m for m in markets if m.normalized_market == "player_props"]
    assert player_markets
    assert all(page2._leg_is_eligible(m)[0] is False for m in player_markets)
