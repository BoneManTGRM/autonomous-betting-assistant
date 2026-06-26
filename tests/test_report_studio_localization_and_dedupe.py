from autonomous_betting_agent.report_product_layer import event_text
from autonomous_betting_agent.report_studio_service import ReportStudioFilters, build_report_studio_cards


def test_spanish_event_text_translates_both_country_sides():
    assert event_text("Canada vs Switzerland", "es") == "Canadá vs Suiza"
    assert event_text("Belgium vs New Zealand", "es") == "Bélgica vs Nueva Zelanda"
    assert event_text("Saudi Arabia at Cape Verde", "es") == "Arabia Saudita vs Cabo Verde"


def test_report_studio_cards_dedupe_duplicate_event_pick_market_rows():
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
        {
            "sport": "Soccer",
            "event": "Iraq vs France",
            "prediction": "Iraq",
            "market": "spread",
            "line_point": 1.5,
            "odds_source": "verified_book",
            "decimal_price": 1.91,
            "model_probability": 0.54,
        },
        {
            "sport": "Soccer",
            "event": "Iraq vs France",
            "prediction": "Iraq",
            "market": "spread",
            "line_point": 1.5,
            "odds_source": "verified_book",
            "decimal_price": 1.95,
            "model_probability": 0.54,
        },
        {
            "sport": "Soccer",
            "event": "Iraq vs France",
            "prediction": "Iraq",
            "market": "spread",
            "line_point": 2.5,
            "odds_source": "verified_book",
            "decimal_price": 1.91,
            "model_probability": 0.54,
        },
    ]

    _, _, _, cards = build_report_studio_cards(
        rows,
        filters=ReportStudioFilters(language="es", include_sports_context=False),
    )

    assert len(cards) == 4
    assert cards["public_event"].tolist() == ["Irak vs Francia"] * 4
    assert set(cards["market"].tolist()) == {"moneyline", "team_total", "spread"}
    assert cards[cards["market"].eq("spread")]["line_point"].tolist() == [1.5, 2.5]
