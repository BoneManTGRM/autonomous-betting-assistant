from __future__ import annotations

from autonomous_betting_agent.multi_leg_report import attach_multi_leg_review, build, decimal_price, format_items, market, model_probability
from autonomous_betting_agent.magazine_combo_section_patch import combo_section_items


def row(event: str, pick: str = "Over 2.5 Goals", price: float = 1.6, prob: float = 0.66, edge: float = 0.02, ev: float = 0.03, **extra):
    data = {
        "event": event,
        "pick": pick,
        "decimal_price": price,
        "model_probability": prob,
        "model_market_edge": edge,
        "expected_value_per_unit": ev,
    }
    data.update(extra)
    return data


def test_builds_valid_two_leg_review_and_calculates_numbers():
    built = build([row("A vs B", price=1.6, prob=0.66), row("C vs D", price=1.7, prob=0.64)])
    assert built is not None
    assert built["lane"] == "safe_two"
    assert round(built["price"], 2) == 2.72
    assert round(built["confidence"], 4) == round(0.66 * 0.64 * 0.92, 4)


def test_rejects_negative_ev_and_negative_edge():
    assert build([row("A vs B", ev=-0.01), row("C vs D")]) is None
    assert build([row("A vs B", edge=-0.01), row("C vs D")]) is None


def test_rejects_duplicate_events_unless_same_game_allowed():
    assert build([row("A vs B", pick="Over 2.5"), row("A vs B", pick="Home")]) is None
    assert build([row("A vs B", pick="Over 2.5"), row("A vs B", pick="Home", same_game_parlay_compatible=True)]) is not None


def test_rejects_blocked_stale_research_only_no_play_rows():
    assert build([row("A vs B", learning_status="blocked"), row("C vs D")]) is None
    assert build([row("A vs B", data_issue_reason="stale line"), row("C vs D")]) is None
    assert build([row("A vs B", consumer_action="research only"), row("C vs D")]) is None
    assert build([row("A vs B", recommended_action="no play"), row("C vs D")]) is None


def test_english_and_spanish_items():
    rows = [row("A vs B", price=1.6, prob=0.66), row("C vs D", pick="Home", price=1.7, prob=0.64)]
    en = format_items(rows, "en", 4)
    es = format_items(rows, "es", 4)
    assert en[0] == "Safer 2-leg parlay"
    assert any("Combined odds" in item for item in en)
    assert any("Estimated probability" in item for item in en)
    assert es[0] == "Parlay más seguro de 2 selecciones"
    assert any("Cuota combinada" in item for item in es)
    assert any("Probabilidad estimada" in item for item in es)


def test_spanish_market_labels():
    assert market(row("A", pick="Corners over 8.5"), "es") == "Córners"
    assert market(row("A", pick="Home"), "es") == "Local/Visitante"
    assert market(row("A", pick="Over 2.5"), "es") == "Más/Menos"
    assert market(row("A", pick="BTTS yes"), "es") == "Ambos equipos anotan"
    assert market(row("A", pick="Double Chance 1X"), "es") == "Doble oportunidad"


def test_no_combo_spanish_output_and_attachment_to_every_row():
    rows = [row("A vs B", ev=-0.01), row("C vs D", ev=-0.01)]
    assert format_items(rows, "es", 3)[0] == "No se recomienda parlay"
    attached = attach_multi_leg_review(rows, "es")
    assert len(attached) == 2
    assert attached[0]["combo_magazine_items"] == attached[1]["combo_magazine_items"]
    assert "No se recomienda parlay" in attached[0]["combo_magazine_items"]


def test_combo_section_uses_explicit_items_when_present():
    items = combo_section_items({"combo_magazine_items": "A|B|C", "report_language": "es"})
    assert items == ["A", "B", "C"]


def test_number_helpers():
    assert decimal_price({"decimal_price": 1.91}) == 1.91
    assert model_probability({"model_probability": "66%"}) == 0.66
