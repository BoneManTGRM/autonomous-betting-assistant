import pandas as pd

from autonomous_betting_agent.report_product_layer import event_text, value_text
from autonomous_betting_agent.report_studio_service import (
    ReportStudioFilters,
    _card_dedupe_key,
    build_report_studio_cards,
)
from autonomous_betting_agent.ui_i18n import localize_dataframe, localize_options


def test_spanish_event_text_translates_both_country_sides():
    assert event_text("Canada vs Switzerland", "es") == "Canadá vs Suiza"
    assert event_text("Belgium vs New Zealand", "es") == "Bélgica vs Nueva Zelanda"
    assert event_text("Saudi Arabia at Cape Verde", "es") == "Arabia Saudita vs Cabo Verde"
    assert event_text("Scotland at Portugal", "es") == "Escocia vs Portugal"
    assert event_text("Uzbekistan at Portugal", "es") == "Uzbekistán vs Portugal"
    assert event_text("Austria at Algeria", "es") == "Austria vs Argelia"


def test_core_value_text_translates_report_market_labels():
    assert value_text("totals", "es") == "totales"
    assert value_text("spreads", "es") == "hándicaps"
    assert value_text("moneyline", "es") == "ganador"
    assert value_text("Price Watch / Research", "es") == "Seguimiento de momio / investigación"
    assert value_text("Full magazine analysis", "es") == "Análisis completo de revista"


def test_shared_spanish_dataframe_localization_translates_screen_table_values():
    frame = pd.DataFrame(
        [
            {"event": "Iran at Egypt", "sport": "FIFA World Cup", "market_type": "totals", "status": "ready_for_lock_or_learning"},
            {"event": "Belgium at New Zealand", "sport": "FIFA World Cup", "market_type": "spreads", "status": "lock_first"},
        ]
    )

    out = localize_dataframe(frame, "es")

    assert out["evento"].tolist() == ["Irán vs Egipto", "Bélgica vs Nueva Zelanda"]
    assert out["deporte"].tolist() == ["Copa Mundial FIFA", "Copa Mundial FIFA"]
    assert out["tipo_mercado"].tolist() == ["totales", "hándicaps"]
    assert out["estado"].tolist() == ["listo para bloqueo o aprendizaje", "bloquear primero"]


def test_shared_spanish_options_localize_report_actions():
    display, reverse = localize_options(["Price Watch / Research", "Research / Track for Learning"], "es")

    assert display == ["Seguimiento de precio / investigación", "Investigación / seguimiento para aprendizaje"]
    assert reverse["Seguimiento de precio / investigación"] == "Price Watch / Research"
    assert reverse["Investigación / seguimiento para aprendizaje"] == "Research / Track for Learning"


def test_report_studio_research_dedupe_collapses_same_event_even_with_market_variants():
    base = {
        "public_event": "Irak vs Francia",
        "public_pick": "Irak",
        "market": "spread",
        "line_point": 1.5,
        "decimal_price": 1.91,
        "public_action": "Seguimiento de momio / investigación",
        "report_lane": "no_play",
    }
    same_event_new_market = {**base, "market": "total", "line_point": 2.5, "decimal_price": 1.95}

    assert _card_dedupe_key(base) == _card_dedupe_key(same_event_new_market)


def test_report_studio_official_dedupe_preserves_real_market_and_line_identity():
    base = {
        "public_event": "Irak vs Francia",
        "public_pick": "Irak",
        "market": "spread",
        "line_point": 1.5,
        "decimal_price": 1.91,
        "public_action": "Jugada oficial +EV",
        "report_lane": "best_play",
        "official_publish_ready": True,
    }
    same_pick_new_price = {**base, "decimal_price": 1.95}
    different_line = {**base, "line_point": 2.5, "decimal_price": 1.91}
    different_market = {**base, "market": "team_total", "line_point": 2.5}

    assert _card_dedupe_key(base) == _card_dedupe_key(same_pick_new_price)
    assert _card_dedupe_key(base) != _card_dedupe_key(different_line)
    assert _card_dedupe_key(base) != _card_dedupe_key(different_market)


def test_report_studio_cards_collapse_duplicate_research_pages_for_same_event():
    rows = [
        {
            "sport": "Soccer",
            "event": "Iraq vs France",
            "prediction": "Iraq",
            "market": "moneyline",
            "decimal_price": 1.3,
            "model_probability": 0.50,
        },
        {
            "sport": "Soccer",
            "event": "Iraq vs France",
            "prediction": "France",
            "market": "totals",
            "line_point": 2.5,
            "decimal_price": 1.4,
            "model_probability": 0.50,
        },
        {
            "sport": "Soccer",
            "event": "Germany vs Ecuador",
            "prediction": "Germany",
            "market": "moneyline",
            "decimal_price": 1.3,
            "model_probability": 0.50,
        },
    ]

    _, _, _, cards = build_report_studio_cards(
        rows,
        filters=ReportStudioFilters(language="es", include_sports_context=False),
    )

    assert len(cards) == 2
    assert cards["public_event"].tolist() == ["Irak vs Francia", "Alemania vs Ecuador"]


def test_report_studio_cards_preserve_separate_official_markets():
    rows = [
        {
            "sport": "Soccer",
            "event": "Iraq vs France",
            "prediction": "Iraq",
            "market": "moneyline",
            "odds_source": "verified_book",
            "decimal_price": 2.2,
            "model_probability": 0.56,
            "proof_id": "proof-1",
        },
        {
            "sport": "Soccer",
            "event": "Iraq vs France",
            "prediction": "Iraq Over 2.5",
            "market": "team_total",
            "line_point": 2.5,
            "odds_source": "verified_book",
            "decimal_price": 2.2,
            "model_probability": 0.56,
            "proof_id": "proof-2",
        },
    ]

    _, _, _, cards = build_report_studio_cards(
        rows,
        filters=ReportStudioFilters(language="es", include_sports_context=False),
    )

    assert len(cards) == 2
    assert cards["public_event"].tolist() == ["Irak vs Francia"] * 2
