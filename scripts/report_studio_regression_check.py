from __future__ import annotations

from pathlib import Path

import pandas as pd

from autonomous_betting_agent.app_feed_delivery import build_app_feed
from autonomous_betting_agent.report_export_service import build_report_export_bundle
from autonomous_betting_agent.report_feed_service import build_report_feed
from autonomous_betting_agent.report_image_export_service import PNG_HEADER, render_card_deck_png, render_card_png, render_magazine_summary_png
from autonomous_betting_agent.report_product_layer import MagazineBrand
from autonomous_betting_agent.report_studio_service import ReportStudioFilters, build_report_studio_state, report_studio_summary
from autonomous_betting_agent.report_studio_ui import render_premium_card_deck, render_status_dashboard

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _sample_rows() -> pd.DataFrame:
    return pd.DataFrame([
        {"event": "Official Edge", "sport": "MLB", "prediction": "Moneyline: A", "learned_model_probability": 0.62, "decimal_price": 2.10, "odds_source": "The Odds API", "proof_id": "P1", "grade": "WIN"},
        {"event": "High Probability Winner", "sport": "Boxing", "prediction": "Game total: Over 10.5", "learned_model_probability": 0.745, "decimal_price": 1.30, "odds_source": "The Odds API", "grade": "WIN"},
        {"event": "Negative Edge Loss", "sport": "Soccer", "prediction": "Game total: Under 2.5", "learned_model_probability": 0.70, "decimal_price": 1.40, "odds_source": "The Odds API", "grade": "LOSS"},
        {"event": "Missing Odds", "sport": "WNBA", "prediction": "Moneyline: B", "learned_model_probability": 0.66, "odds_source": "api limit", "grade": "PENDING"},
        {"event": "Unsupported Tennis", "sport": "tennis", "prediction": "Moneyline: C", "learned_model_probability": 0.72, "decimal_price": 2.00, "odds_source": "The Odds API", "grade": "WIN"},
        {"event": "Push Row", "sport": "MMA", "prediction": "Point spread: D +1.5", "learned_model_probability": 0.58, "decimal_price": 1.91, "odds_source": "The Odds API", "grade": "PUSH"},
    ])


def check_static_page_contract() -> None:
    page = _read("pages/report_studio.py")
    image_service = _read("autonomous_betting_agent/report_image_export_service.py")
    required_tokens = [
        "build_report_studio_state",
        "render_status_dashboard",
        "render_premium_card_deck",
        "save_app_feed",
        "save_report_feed",
        "report_image_export_service",
        "render_card_png",
        "render_card_deck_png",
        "render_magazine_summary_png",
        "card_image_filename",
        "Images",
        "Learning Audit",
        "Diagnostics",
        "official_publish_ready",
        "client_report_ready",
        "learning_ready",
        "report_studio_copy_tab_download",
        "report_studio_export_whatsapp",
        "report_studio_export_pdf",
        "report_studio_export_html",
        "report_studio_export_md",
        "report_studio_export_json",
        "report_studio_export_csv",
        "report_studio_image_deck_png",
        "report_studio_image_magazine_png",
        "report_studio_image_card_",
    ]
    for token in required_tokens:
        assert token in page, f"Report Studio missing required token: {token}"
    for token in ("render_card_png", "render_card_deck_png", "render_magazine_summary_png", "card_image_filename"):
        assert token in image_service, f"image export service missing {token}"
    download_button_count = page.count("download_button")
    download_key_count = page.count("key='report_studio_") + page.count("key=f'report_studio_")
    assert download_key_count >= download_button_count, "Every Report Studio download button needs a stable unique key"


def check_export_label_contract() -> None:
    export_service = _read("autonomous_betting_agent/report_export_service.py")
    pdf_service = _read("autonomous_betting_agent/pdf_report.py")
    assert "clean_legacy_report_labels" in export_service
    assert "Research / Learning" in export_service
    assert "Research / Learning" in pdf_service
    assert "Today's Official +EV" in pdf_service


def check_functional_contract() -> None:
    brand = MagazineBrand(brand_name="ABA Signal Pro", report_title="Regression Check", workspace_id="regression_check")
    state = build_report_studio_state(_sample_rows(), brand, filters=ReportStudioFilters(max_rows=75, language="en", mode="consumer"), source_note="regression")
    summary = report_studio_summary(state)
    assert summary["cards"] == 6
    assert summary["official_publish_ready"] == 1
    assert summary["client_report_ready"] == 4
    assert summary["learning_ready"] == 4
    assert summary["data_issues"] == 2
    assert "by_edge_bucket" in state.audit
    assert not state.audit["negative_edge_winners"].empty

    dashboard = render_status_dashboard(state.cards)
    premium = render_premium_card_deck(state.cards)
    assert "Official +EV Plays" in dashboard
    assert "Research / Learning" in dashboard
    assert "Price Watch / Research" in premium
    assert "No Play" not in premium

    unified_feed = build_report_feed(state.cards, brand)
    legacy_feed = build_app_feed(state.cards, brand)
    assert unified_feed["schema_version"] == "aba-report-feed-v2"
    assert legacy_feed["schema_version"] == "aba-report-feed-v1"
    assert unified_feed["counts"]["data_issues"] == 2
    assert "no_play" in legacy_feed["groups"]

    bundle = build_report_export_bundle(state.cards, brand)
    assert bundle.pdf_bytes.startswith(b"%PDF")
    for text in (bundle.html, bundle.markdown, bundle.whatsapp):
        assert "No Play" not in text

    first_card = state.cards.iloc[0].to_dict()
    for payload in (render_card_png(first_card, brand), render_card_deck_png(state.cards, brand), render_magazine_summary_png(state.cards, brand)):
        assert payload.startswith(PNG_HEADER)
        assert len(payload) > 5000


def run_regression_check() -> None:
    check_static_page_contract()
    check_export_label_contract()
    check_functional_contract()


if __name__ == "__main__":
    run_regression_check()
    print("report studio regression check passed")
