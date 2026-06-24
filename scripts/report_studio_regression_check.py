from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from autonomous_betting_agent.app_feed_delivery import build_app_feed
from autonomous_betting_agent.magazine_book_export import (
    pick_full_page_filename,
    render_full_magazine_book_pdf,
    render_full_magazine_book_png,
    render_full_magazine_zip,
    render_full_pick_magazine_page_png,
    sanitize_image_filename,
)
from autonomous_betting_agent.report_background_image_service import PNG_HEADER as BACKGROUND_PNG_HEADER, render_custom_background_summary_png
from autonomous_betting_agent.report_export_service import build_report_export_bundle
from autonomous_betting_agent.report_feed_service import build_report_feed
from autonomous_betting_agent.report_image_export_service import PNG_HEADER, render_magazine_summary_png
from autonomous_betting_agent.report_magazine_pdf_service import PDF_HEADER, render_vintage_magazine_pdf
from autonomous_betting_agent.report_product_layer import MagazineBrand
from autonomous_betting_agent.report_studio_service import ReportStudioFilters, build_report_studio_state, report_studio_summary
from autonomous_betting_agent.report_studio_ui import render_premium_card_deck, render_status_dashboard

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS_DIR = ROOT / "diagnostics"


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


def _json_safe(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return value.head(25).to_dict(orient="records")
    if isinstance(value, pd.Series):
        return value.head(25).to_dict()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def _write_diagnostics(name: str, payload: dict[str, Any]) -> None:
    DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
    path = DIAGNOSTICS_DIR / name
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True), encoding="utf-8")


def check_static_page_contract() -> None:
    page = _read("pages/report_studio.py")
    image_service = _read("autonomous_betting_agent/report_image_export_service.py")
    background_service = _read("autonomous_betting_agent/report_background_image_service.py")
    magazine_pdf_service = _read("autonomous_betting_agent/report_magazine_pdf_service.py")
    magazine_book_service = _read("autonomous_betting_agent/magazine_book_export.py")
    required_tokens = [
        "build_report_studio_state",
        "render_status_dashboard",
        "render_premium_card_deck",
        "save_app_feed",
        "save_report_feed",
        "report_image_export_service",
        "render_magazine_summary_png",
        "render_vintage_magazine_pdf",
        "magazine_book_export",
        "render_full_magazine_book_png",
        "render_full_magazine_book_pdf",
        "render_full_magazine_zip",
        "render_full_pick_magazine_page_png",
        "pick_full_page_filename",
        "sanitize_image_filename",
        "render_custom_background_summary_png",
        "report_studio_profile_background_upload",
        "report_studio_image_background_upload",
        "report_background_bytes",
        "magazine_tab_png = render_custom_background_summary_png",
        "background_bytes=report_background_bytes",
        "magazine_pdf",
        "Images",
        "Learning Audit",
        "Diagnostics",
        "official_publish_ready",
        "client_report_ready",
        "learning_ready",
        "report_studio_copy_tab_download",
        "report_studio_export_whatsapp",
        "report_studio_export_pdf",
        "report_studio_export_magazine_pdf",
        "report_studio_export_html",
        "report_studio_export_md",
        "report_studio_export_json",
        "report_studio_export_csv",
        "report_studio_magazine_pdf",
        "report_studio_image_magazine_png",
        "report_studio_full_book_png",
        "report_studio_full_book_pdf",
        "report_studio_full_book_zip",
        "report_studio_image_full_page_",
        "Download Full Magazine Book PNG",
        "Download Full Magazine Book PDF",
        "Download Full Magazine ZIP",
        "Download Full Magazine Page",
    ]
    forbidden_tokens = [
        "report_studio_image_deck_png",
        "report_studio_image_card_",
        "Download full card deck PNG",
        "Download Card Image",
        "Compact card image",
    ]
    token_presence = {token: token in page for token in required_tokens}
    forbidden_presence = {token: token in page for token in forbidden_tokens}
    image_token_presence = {token: token in image_service for token in ("render_magazine_summary_png",)}
    background_token_presence = {token: token in background_service for token in ("render_custom_background_summary_png", "ImageEnhance.Brightness", "draw.rectangle")}
    magazine_pdf_token_presence = {token: token in magazine_pdf_service for token in ("render_vintage_magazine_pdf", "_cover_page", "_divider_page", "_matchup_page")}
    magazine_book_token_presence = {token: token in magazine_book_service for token in ("render_full_pick_magazine_page_png", "render_full_magazine_book_png", "render_full_magazine_book_pdf", "render_full_magazine_zip", "pick_full_page_filename", "sanitize_image_filename")}
    download_button_count = page.count("download_button")
    download_key_count = page.count("key='report_studio_") + page.count("key=f'report_studio_") + page.count('key="report_studio_') + page.count('key=f"report_studio_')
    _write_diagnostics("report_studio_static_contract.json", {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "required_tokens": token_presence,
        "forbidden_tokens": forbidden_presence,
        "image_service_tokens": image_token_presence,
        "background_service_tokens": background_token_presence,
        "magazine_pdf_service_tokens": magazine_pdf_token_presence,
        "magazine_book_service_tokens": magazine_book_token_presence,
        "download_button_count": download_button_count,
        "download_key_count": download_key_count,
    })
    for token, present in token_presence.items():
        assert present, f"Report Studio missing required token: {token}"
    for token, present in forbidden_presence.items():
        assert not present, f"Report Studio still contains removed compact/deck token: {token}"
    for token, present in image_token_presence.items():
        assert present, f"image export service missing {token}"
    for token, present in background_token_presence.items():
        assert present, f"background image export service missing {token}"
    for token, present in magazine_pdf_token_presence.items():
        assert present, f"magazine PDF service missing {token}"
    for token, present in magazine_book_token_presence.items():
        assert present, f"magazine book export service missing {token}"
    assert download_key_count >= download_button_count, f"Every Report Studio download button needs a stable unique key: buttons={download_button_count}, keys={download_key_count}"


def check_export_label_contract() -> None:
    export_service = _read("autonomous_betting_agent/report_export_service.py")
    pdf_service = _read("autonomous_betting_agent/pdf_report.py")
    label_contract = {
        "export_cleaner": "clean_legacy_report_labels" in export_service,
        "export_research_learning": "Research / Learning" in export_service,
        "pdf_research_learning": "Research / Learning" in pdf_service,
        "pdf_official_ev": "Today's Official +EV" in pdf_service,
    }
    _write_diagnostics("report_studio_label_contract.json", {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "label_contract": label_contract,
    })
    assert label_contract["export_cleaner"]
    assert label_contract["export_research_learning"]
    assert label_contract["pdf_research_learning"]
    assert label_contract["pdf_official_ev"]


def check_functional_contract() -> None:
    brand = MagazineBrand(brand_name="ABA Signal Pro", report_title="Regression Check", workspace_id="regression_check")
    state = build_report_studio_state(_sample_rows(), brand, filters=ReportStudioFilters(max_rows=75, language="en", mode="consumer"), source_note="regression")
    summary = report_studio_summary(state)

    dashboard = render_status_dashboard(state.cards)
    premium = render_premium_card_deck(state.cards)
    unified_feed = build_report_feed(state.cards, brand)
    legacy_feed = build_app_feed(state.cards, brand)
    bundle = build_report_export_bundle(state.cards, brand)
    magazine_pdf = render_vintage_magazine_pdf(state.cards, brand)
    card_rows = [row.to_dict() for _, row in state.cards.iterrows()]
    first_card = card_rows[0]
    image_payloads = {
        "magazine_summary_png": render_magazine_summary_png(state.cards, brand),
        "custom_background_summary_png": render_custom_background_summary_png(state.cards, brand, background_bytes=None),
        "full_magazine_page_png": render_full_pick_magazine_page_png(first_card, background_image=None, report_name="Regression Check", page_number=1, total_pages=len(card_rows)),
        "full_magazine_book_png": render_full_magazine_book_png(card_rows, background_image=None, report_name="Regression Check"),
    }
    book_pdf = render_full_magazine_book_pdf(card_rows, background_image=None, report_name="Regression Check")
    book_zip = render_full_magazine_zip(card_rows, background_image=None, report_name="Regression Check")
    page_filename = pick_full_page_filename(first_card, 0)
    book_filename = sanitize_image_filename("Regression Check", extension="png")

    _write_diagnostics("report_studio_functional_contract.json", {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "diagnostics": state.diagnostics.__dict__,
        "cards_preview": state.cards.head(10),
        "report_lane_counts": state.cards.get("report_lane", pd.Series(dtype=str)).value_counts(dropna=False).to_dict(),
        "report_lane_v2_counts": state.cards.get("report_lane_v2", pd.Series(dtype=str)).value_counts(dropna=False).to_dict(),
        "data_issue_counts": state.cards.get("data_issue_reason", pd.Series(dtype=str)).value_counts(dropna=False).to_dict(),
        "audit_keys": sorted(state.audit.keys()),
        "negative_edge_winners_rows": int(len(state.audit.get("negative_edge_winners", pd.DataFrame()))),
        "dashboard_contains": {"Official +EV Plays": "Official +EV Plays" in dashboard, "Research / Learning": "Research / Learning" in dashboard},
        "premium_contains": {"Price Watch / Research": "Price Watch / Research" in premium, "No Play": "No Play" in premium},
        "feed_versions": {"unified": unified_feed.get("schema_version"), "legacy": legacy_feed.get("schema_version")},
        "feed_counts": unified_feed.get("counts", {}),
        "legacy_groups": sorted(legacy_feed.get("groups", {}).keys()),
        "export_contains_no_play": {"html": "No Play" in bundle.html, "markdown": "No Play" in bundle.markdown, "whatsapp": "No Play" in bundle.whatsapp},
        "image_payload_sizes": {key: len(value) for key, value in image_payloads.items()},
        "image_headers_ok": {key: value.startswith(PNG_HEADER) or value.startswith(BACKGROUND_PNG_HEADER) for key, value in image_payloads.items()},
        "magazine_pdf_size": len(magazine_pdf),
        "magazine_pdf_header_ok": magazine_pdf.startswith(PDF_HEADER),
        "full_book_pdf_size": len(book_pdf),
        "full_book_zip_size": len(book_zip),
        "page_filename": page_filename,
        "book_filename": book_filename,
    })

    assert summary["cards"] == 6, f"cards expected 6, got {summary['cards']}"
    assert summary["official_publish_ready"] == 1, f"official_publish_ready expected 1, got {summary['official_publish_ready']}"
    assert summary["client_report_ready"] == 4, f"client_report_ready expected 4, got {summary['client_report_ready']}"
    assert summary["learning_ready"] == 4, f"learning_ready expected 4, got {summary['learning_ready']}"
    assert summary["data_issues"] == 2, f"data_issues expected 2, got {summary['data_issues']}"
    assert "by_edge_bucket" in state.audit, f"audit missing by_edge_bucket; keys={sorted(state.audit.keys())}"
    assert not state.audit["negative_edge_winners"].empty, "negative_edge_winners should not be empty"
    assert "Official +EV Plays" in dashboard
    assert "Research / Learning" in dashboard
    assert "Price Watch / Research" in premium
    assert "No Play" not in premium
    assert unified_feed["schema_version"] == "aba-report-feed-v2"
    assert legacy_feed["schema_version"] == "aba-report-feed-v1"
    assert unified_feed["counts"]["data_issues"] == 2
    assert "no_play" in legacy_feed["groups"]
    assert bundle.pdf_bytes.startswith(b"%PDF")
    for name, text in {"html": bundle.html, "markdown": bundle.markdown, "whatsapp": bundle.whatsapp}.items():
        assert "No Play" not in text, f"legacy No Play label still present in {name} export"
    assert magazine_pdf.startswith(PDF_HEADER), "magazine PDF did not start with PDF header"
    assert len(magazine_pdf) > 20000, f"magazine PDF was too small: {len(magazine_pdf)} bytes"
    for name, payload in image_payloads.items():
        assert payload.startswith(PNG_HEADER) or payload.startswith(BACKGROUND_PNG_HEADER), f"{name} did not start with PNG header"
        assert len(payload) > 5000, f"{name} was too small: {len(payload)} bytes"
    assert book_pdf.startswith(PDF_HEADER), "full magazine book PDF did not start with PDF header"
    assert len(book_pdf) > 5000, f"full magazine book PDF was too small: {len(book_pdf)} bytes"
    assert book_zip.startswith(b"PK"), "full magazine ZIP did not start with ZIP header"
    assert len(book_zip) > 5000, f"full magazine ZIP was too small: {len(book_zip)} bytes"
    assert page_filename.endswith(".png")
    assert book_filename.endswith(".png")


def _run_step(name: str, func: Any) -> None:
    print(f"starting: {name}", flush=True)
    func()
    print(f"passed: {name}", flush=True)


def run_regression_check() -> None:
    _run_step("static page contract", check_static_page_contract)
    _run_step("export label contract", check_export_label_contract)
    _run_step("functional contract", check_functional_contract)


if __name__ == "__main__":
    try:
        run_regression_check()
    except Exception as exc:
        print(f"report studio regression check failed: {type(exc).__name__}: {exc}", flush=True)
        raise
    print("report studio regression check passed")
