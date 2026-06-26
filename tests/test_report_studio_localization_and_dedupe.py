from autonomous_betting_agent.report_product_layer import event_text
from autonomous_betting_agent.report_studio_service import (
    ReportStudioFilters,
    _card_dedupe_key,
    build_report_studio_cards,
)


def test_spanish_event_text_translates_both_country_sides():
    assert event_text("Canada vs Switzerland", "es") == "Canadá vs Suiza"
    assert event_text("Belgium vs New Zealand", "es") == "Bélgica vs Nueva Zelanda"
    assert event_text("Saudi Arabia at Cape Verde", "es") == "Arabia Saudita vs Cabo Verde"


def test_report_studio_dedupe_key_ignores_price_but_preserves_line_identity():
    base = {
        "public_event": "Irak vs Francia",
        "public_pick": "Irak",
        "market": "spread",
        "line_point": 1.5,
        "decimal_price": 1.91,
        "public_action": "No jugar",
    }
    same_pick_new_price = {**base, "decimal_price": 1.95}
    different_line = {**base, "line_point": 2.5, "decimal_price": 1.91}

    assert _card_dedupe_key(base) == _card_dedupe_key(same_pick_new_price)
    assert _card_dedupe_key(base) != _card_dedupe_key(different_line)


def test_report_studio_cards_dedupe_exact_duplicate_rows_but_keep_different_markets():
    rows = [
        {
            "sport": "Soccer",
            "event": "Iraq vs France",
            "prediction": "Iraq",
            "market": "moneyline",
            "odds_source": "verified_book",
            "decimal_price": 2.1,
            "model_probability": 0.52,
        },
        {
            "sport": "Soccer",
            "event": "Iraq vs France",
            "prediction": "Iraq",
            "market": "moneyline",
            "odds_source": "verified_book",
            "decimal_price": 2.2,
            "model_probability": 0.52,
        },
        {
            "sport": "Soccer",
            "event": "Iraq vs France",
            "prediction": "Iraq",
            "market": "team_total",
            "line_point": 2.5,
            "odds_source": "verified_book",
            "decimal_price": 2.1,
            "model_probability": 0.52,
        },
    ]

    _, _, _, cards = build_report_studio_cards(
        rows,
        filters=ReportStudioFilters(language="es", include_sports_context=False),
    )

    assert len(cards) == 2
    assert cards["public_event"].tolist() == ["Irak vs Francia"] * 2
