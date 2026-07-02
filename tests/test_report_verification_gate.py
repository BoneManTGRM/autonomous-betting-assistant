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
