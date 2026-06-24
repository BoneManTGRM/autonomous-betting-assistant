from __future__ import annotations

from autonomous_betting_agent.report_exports import PRINT_TO_PDF_NOTE, render_html_report


def test_html_report_is_print_ready_and_local():
    row = {
        "proof_id": "P1",
        "locked_at_utc": "2026-06-23T10:00:00+00:00",
        "event_start_time": "2026-06-23T12:00:00+00:00",
        "event_name": "A vs B",
        "prediction": "A",
        "market": "moneyline",
        "odds_audit_status": "pass",
        "grade": "win",
    }
    html = render_html_report([row], title="Local Report")
    assert "@media print" in html
    assert "@page" in html
    assert PRINT_TO_PDF_NOTE in html
    assert "does not guarantee" in html
    assert "http://" not in html
    assert "https://" not in html
