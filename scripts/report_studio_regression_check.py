from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autonomous_betting_agent.magazine_book_export import (
    pick_full_page_filename,
    render_full_magazine_book_pdf,
    render_full_magazine_book_png,
    render_full_magazine_zip,
    render_full_pick_magazine_page_png,
    sanitize_image_filename,
)
from autonomous_betting_agent.report_image_export_service import PNG_HEADER
from autonomous_betting_agent.report_magazine_pdf_service import PDF_HEADER

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS_DIR = ROOT / "diagnostics"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _write_diagnostics(name: str, payload: dict[str, Any]) -> None:
    DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
    (DIAGNOSTICS_DIR / name).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


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
        "TEAM ANALYSIS",
        "PLAYER NOTES",
        "PRO BETTOR EVIDENCE",
        "RISK DESK",
        "CHAIN BETTING NOTES",
        "FINAL RECOMMENDATION",
        "TENDENCIA",
        "Player data not available in uploaded row",
        "Data not available from uploaded row",
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
    assert page_png.startswith(PNG_HEADER), "full magazine page PNG did not start with PNG header"
    assert len(page_png) > 10000, f"full magazine page PNG was too small: {len(page_png)} bytes"
    assert book_png.startswith(PNG_HEADER), "full magazine book PNG did not start with PNG header"
    assert len(book_png) > 10000, f"full magazine book PNG was too small: {len(book_png)} bytes"
    assert book_pdf.startswith(PDF_HEADER), "full magazine book PDF did not start with PDF header"
    assert len(book_pdf) > 5000, f"full magazine book PDF was too small: {len(book_pdf)} bytes"
    assert book_zip.startswith(b"PK"), "full magazine ZIP did not start with ZIP header"
    assert len(book_zip) > 5000, f"full magazine ZIP was too small: {len(book_zip)} bytes"
    assert page_filename.endswith(".png")
    assert book_filename.endswith(".png")


def run_regression_check() -> None:
    check_static_page_contract()
    check_functional_contract()


if __name__ == "__main__":
    try:
        run_regression_check()
    except Exception as exc:
        print(f"report studio regression check failed: {type(exc).__name__}: {exc}", flush=True)
        raise
    print("report studio regression check passed")
