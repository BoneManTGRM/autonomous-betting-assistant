from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from autonomous_betting_agent.magazine_book_export import (
    pick_full_page_filename,
    render_full_magazine_book_pdf,
    render_full_magazine_book_png,
    render_full_magazine_zip,
    render_full_pick_magazine_page_png,
    sanitize_image_filename,
)
from autonomous_betting_agent.mobile_png_layout import render_mobile_png
from autonomous_betting_agent.pdf_report import _pdf_lines, render_report_pdf
from autonomous_betting_agent.report_export_service import render_whatsapp_report
from autonomous_betting_agent.report_image_export_service import PNG_HEADER
from autonomous_betting_agent.report_magazine_pdf_service import PDF_HEADER, render_vintage_magazine_pdf
from autonomous_betting_agent.report_product_layer import (
    MagazineBrand,
    enrich_rows,
    event_text,
    pick_text,
    render_consumer_magazine_html,
    sport_text,
    value_text,
)
from autonomous_betting_agent.report_studio_ui import render_premium_card_deck

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS_DIR = ROOT / "diagnostics"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _write_diagnostics(name: str, payload: dict[str, Any]) -> None:
    DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
    (DIAGNOSTICS_DIR / name).write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")


def check_static_page_contract() -> None:
    page = _read("pages/report_studio.py")
    renderer = _read("autonomous_betting_agent/magazine_book_export.py")
    required_page_tokens = [
        "magazine_book_export",
        "cached_render_full_pick_magazine_page_png",
        "Build Full Magazine Book",
        "Download Full Magazine Book PNG",
        "Download Full Magazine Book PDF",
        "Download Full Magazine ZIP",
        "Download Full Magazine Page",
        "report_studio_full_book_png",
        "report_studio_full_book_pdf",
        "report_studio_full_book_zip",
        "report_studio_image_full_page_",
    ]
    forbidden_page_tokens = [
        "Download full card deck PNG",
        "Download Card Image",
        "report_studio_image_card_",
        "report_studio_image_deck_png",
        "Compact card image",
        "Save Magazine Page PNG",
    ]
    required_renderer_tokens = [
        "WHY WE PICKED IT",
        "TEAM SNAPSHOTS",
        "PLAYER / INJURY NOTES",
        "PRO BETTOR EVIDENCE",
        "RISK DESK",
        "MATCHUP NOTES",
        "CHAIN BETTING NOTES",
        "TENDENCIA",
        "Player data not returned for this event",
        "Data not returned for this event",
    ]
    diagnostics = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "required_page_tokens": {token: token in page for token in required_page_tokens},
        "forbidden_page_tokens": {token: token in page for token in forbidden_page_tokens},
        "required_renderer_tokens": {token: token in renderer for token in required_renderer_tokens},
    }
    _write_diagnostics("report_studio_static_contract.json", diagnostics)
    for token, present in diagnostics["required_page_tokens"].items():
        assert present, f"Report Studio missing required token: {token}"
    for token, present in diagnostics["forbidden_page_tokens"].items():
        assert not present, f"Report Studio still contains removed token: {token}"
    for token, present in diagnostics["required_renderer_tokens"].items():
        assert present, f"Magazine renderer missing required token: {token}"


def check_functional_contract() -> None:
    rows = [
        {
            "event": "Team Alpha at Team Beta",
            "sport": "Baseball",
            "prediction": "Team Beta ML",
            "decimal_price": "1.91",
            "model_probability": "0.61",
            "market_probability": "0.55",
            "model_market_edge": "0.06",
            "expected_value_per_unit": "0.10",
            "odds_source": "Uploaded row",
            "team_form": "Team Beta has the stronger recent profile.",
            "key_players": "Lineup data should be confirmed before publishing.",
            "final_decision": "play_small",
        },
        {
            "event": "Team Gamma vs Team Delta",
            "sport": "Soccer",
            "prediction": "Over 2.5",
            "decimal_price": "2.05",
            "model_probability": "0.58",
            "odds_source": "Uploaded row",
        },
    ]
    page_png = render_full_pick_magazine_page_png(rows[0], report_name="Regression Check", page_number=1, total_pages=len(rows))
    book_png = render_full_magazine_book_png(rows, report_name="Regression Check")
    book_pdf = render_full_magazine_book_pdf(rows, report_name="Regression Check")
    book_zip = render_full_magazine_zip(rows, report_name="Regression Check")
    page_filename = pick_full_page_filename(rows[0], 0)
    book_filename = sanitize_image_filename("Regression Check", extension="png")
    diagnostics = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "page_png_size": len(page_png),
        "book_png_size": len(book_png),
        "book_pdf_size": len(book_pdf),
        "book_zip_size": len(book_zip),
        "page_filename": page_filename,
        "book_filename": book_filename,
    }
    _write_diagnostics("report_studio_functional_contract.json", diagnostics)
    assert page_png.startswith(PNG_HEADER)
    assert len(page_png) > 10000
    assert book_png.startswith(PNG_HEADER)
    assert len(book_png) > 10000
    assert book_pdf.startswith(PDF_HEADER)
    assert len(book_pdf) > 5000
    assert book_zip.startswith(b"PK")
    assert len(book_zip) > 5000
    assert page_filename.endswith(".png")
    assert book_filename.endswith(".png")


def check_spanish_localization_contract() -> None:
    rows = [
        {
            "event": "Iraq at France",
            "sport": "FIFA World Cup",
            "prediction": "Game total: Over 2.5",
            "consumer_action": "Price Watch / Research",
            "recommended_action": "Price Watch / Research",
            "confidence_tier": "Medium",
            "price_value_label": "Negative at listed odds",
            "official_status_label": "Research / Not Official",
            "result_status": "UNKNOWN",
            "learning_status": "Needs grading",
            "decimal_price": "1.36",
            "learned_model_probability": "0.71",
            "market_probability": "0.73",
            "model_market_edge": "-0.021",
            "expected_value_per_unit": "-0.029",
            "odds_source": "The Odds API",
            "bookmaker": "consensus average",
        },
        {
            "event": "Netherlands at Tunisia",
            "sport": "FIFA World Cup",
            "prediction": "Game total: Under 3",
            "consumer_action": "Price Watch / Research",
            "recommended_action": "Price Watch / Research",
            "confidence_tier": "Medium",
            "price_value_label": "Watchlist / thin value",
            "official_status_label": "Research / Not Official",
            "result_status": "PENDING",
            "learning_status": "Needs grading",
            "decimal_price": "1.90",
            "learned_model_probability": "0.52",
            "market_probability": "0.53",
            "model_market_edge": "-0.01",
            "expected_value_per_unit": "-0.012",
            "odds_source": "The Odds API",
            "bookmaker": "consensus average",
        },
    ]
    brand = MagazineBrand(language="es", report_title="Daily Sports Analysis", tagline="Powered by Reparodynamics")
    cards = enrich_rows(pd.DataFrame(rows), language="es")

    direct_checks = {
        "event_iraq_france": event_text("Iraq at France", "es"),
        "event_netherlands_tunisia": event_text("Netherlands at Tunisia", "es"),
        "pick_over": pick_text("Game total: Over 2.5", "es"),
        "sport_world_cup": sport_text("FIFA World Cup", "es"),
        "value_price_watch": value_text("Price Watch / Research", "es"),
        "value_needs_grading": value_text("Needs grading", "es"),
        "value_negative": value_text("Negative at listed odds", "es"),
    }
    assert direct_checks["event_iraq_france"] == "Irak vs Francia"
    assert direct_checks["event_netherlands_tunisia"] == "Países Bajos vs Túnez"
    assert direct_checks["pick_over"] == "Total del partido: Más de 2.5"
    assert direct_checks["sport_world_cup"] == "Copa Mundial FIFA"
    assert direct_checks["value_price_watch"] == "Seguimiento de momio / investigación"
    assert direct_checks["value_needs_grading"] == "Necesita calificación"
    assert direct_checks["value_negative"] == "Negativo con el momio actual"

    html = render_consumer_magazine_html(cards, brand, mode="consumer")
    deck_html = render_premium_card_deck(cards, language="es")
    whatsapp = render_whatsapp_report(cards, brand)
    pdf_lines = "\n".join(_pdf_lines(cards, brand, mode="consumer"))
    pdf = render_report_pdf(cards, brand, mode="consumer")
    mobile_png = render_mobile_png(cards, brand, top_n=2)
    vintage_pdf = render_vintage_magazine_pdf(cards, brand, max_cards=2)
    magazine_page = render_full_pick_magazine_page_png({**rows[0], "report_language": "es"}, report_name="Prueba", page_number=1, total_pages=2)

    combined_text = "\n".join([html, deck_html, whatsapp, pdf_lines])
    required_spanish = [
        "Irak vs Francia",
        "Países Bajos vs Túnez",
        "Copa Mundial FIFA",
        "Total del partido: Más de 2.5",
        "Seguimiento de momio / investigación",
        "Necesita calificación",
        "Negativo con el momio actual",
        "Investigación / no oficial",
    ]
    forbidden_english = [
        "Iraq at France",
        "Netherlands at Tunisia",
        "Game total: Over 2.5",
        "Price Watch / Research",
        "Negative at listed odds",
        "Needs grading",
        "Research / Not Official",
        "Daily Sports Analysis",
    ]
    diagnostics = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "direct_checks": direct_checks,
        "required_spanish": {token: token in combined_text for token in required_spanish},
        "forbidden_english": {token: token in combined_text for token in forbidden_english},
        "pdf_size": len(pdf),
        "mobile_png_size": len(mobile_png),
        "vintage_pdf_size": len(vintage_pdf),
        "magazine_page_size": len(magazine_page),
    }
    _write_diagnostics("report_studio_spanish_localization_contract.json", diagnostics)
    for token, present in diagnostics["required_spanish"].items():
        assert present, f"Spanish localization missing required text: {token}"
    for token, present in diagnostics["forbidden_english"].items():
        assert not present, f"Spanish localization leaked English text: {token}"
    assert pdf.startswith(PDF_HEADER)
    assert len(pdf) > 1500
    assert mobile_png.startswith(PNG_HEADER)
    assert len(mobile_png) > 10000
    assert vintage_pdf.startswith(PDF_HEADER)
    assert len(vintage_pdf) > 5000
    assert magazine_page.startswith(PNG_HEADER)
    assert len(magazine_page) > 10000


def run_regression_check() -> None:
    check_static_page_contract()
    check_functional_contract()
    check_spanish_localization_contract()


if __name__ == "__main__":
    try:
        run_regression_check()
    except Exception as exc:
        print(f"report studio regression check failed: {type(exc).__name__}: {exc}", flush=True)
        raise
    print("report studio regression check passed")
