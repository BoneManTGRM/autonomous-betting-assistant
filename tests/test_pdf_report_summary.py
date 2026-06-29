import pandas as pd

from autonomous_betting_agent.pdf_report import render_report_pdf
from autonomous_betting_agent.report_export_service import build_report_export_bundle
from autonomous_betting_agent.report_product_layer import MagazineBrand


def _cards() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "event": "Aces vs Liberty",
                "prediction": "Aces ML",
                "public_event": "Aces vs Liberty",
                "public_pick": "Aces ML",
                "report_lane": "best_plays",
                "consumer_action": "Official +EV Play",
                "confidence_tier": "High",
                "risk_tier": "Low",
                "market_read": "Caliente h2h",
                "why_it_matters": "Verified price and complete market.",
                "game_preview": "Short preview.",
                "model_probability": 0.64,
                "market_probability": 0.58,
                "model_market_edge": 0.06,
                "expected_value_per_unit": 0.09,
                "decimal_price": 1.9,
                "proof_id": "proof-1",
                "official_publish_ready": True,
                "bookmaker": "Caliente",
                "market_type": "h2h",
                "manual_clv": "0.08",
                "validation_status": "passed",
                "odds_verified": True,
                "explanation_summary": "Positive edge with verified price and complete market.",
                "warning": "line movement",
            }
        ]
    )


def test_render_report_pdf_can_include_summary_markdown_text():
    pdf = render_report_pdf(
        _cards(),
        MagazineBrand(report_title="PDF Summary Test"),
        summary_markdown="## Executive Summary\n- Status: REPORT_READY_WITH_PLAYABLE_ROWS\n## Validation Summary\n- odds_verified=1/1\n",
    )

    assert pdf.startswith(b"%PDF-1.4")
    assert b"Report Summary / Explanations" in pdf
    assert b"Executive Summary" in pdf
    assert b"REPORT_READY_WITH_PLAYABLE_ROWS" in pdf
    assert b"Validation Summary" in pdf


def test_report_export_bundle_pdf_includes_generated_report_summary():
    bundle = build_report_export_bundle(_cards(), MagazineBrand(report_title="PDF Bundle Test"))

    assert bundle.pdf_bytes.startswith(b"%PDF-1.4")
    assert b"Report Summary / Explanations" in bundle.pdf_bytes
    assert b"Executive Summary" in bundle.pdf_bytes
    assert b"REPORT_READY_WITH_PLAYABLE_ROWS" in bundle.pdf_bytes
    assert b"report_summary_status" in bundle.csv_text.encode("latin-1", errors="replace")
