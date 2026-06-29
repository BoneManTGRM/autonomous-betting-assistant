import ast
from pathlib import Path

PAGE = Path("pages/roi_clv_calibration_audit.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def _text_dict():
    return _assignment_value("TEXT")


def test_roi_clv_calibration_page_imports_read_only_services():
    for token in (
        "build_roi_clv_calibration_report",
        "export_roi_clv_calibration_report_json",
        "validate_roi_clv_calibration_report",
    ):
        assert token in SOURCE


def test_roi_clv_calibration_page_exposes_controls():
    for token in (
        "roi_clv_workspace_id",
        "roi_clv_event",
        "roi_clv_result",
        "roi_clv_stake",
        "roi_clv_decimal_odds",
        "roi_clv_closing_decimal_odds",
        "roi_clv_add_row",
        "roi_clv_clear_rows",
        "roi_clv_run_audit",
    ):
        assert token in SOURCE


def test_roi_clv_calibration_page_displays_required_report_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "report_id",
        "report_hash",
        "status",
        "overall_passed",
        "row_count",
        "unique_events",
        "duplicate_row_count",
        "playable_count",
        "wins",
        "losses",
        "push_cancel_count",
        "pending_unknown_count",
        "profit_units",
        "ROI",
        "win_rate_ex_push_cancel",
        "clv_sample_count",
        "average_CLV_percent",
        "warning_count",
        "error_count",
    ):
        assert token in SOURCE


def test_roi_clv_calibration_page_has_clear_status_language():
    for token in (
        "CALIBRATION OK",
        "CALIBRATION WARNING",
        "CALIBRATION FAILED",
        "INSUFFICIENT DATA",
        "ROI VALID",
        "ROI WARNING",
        "CLV VALID",
        "CLV WARNING",
    ):
        assert token in SOURCE


def test_roi_clv_calibration_page_download_is_memory_only_and_hash_keyed():
    assert "st.download_button" in SOURCE
    assert "export_roi_clv_calibration_report_json(report, public_safe=True).encode" in SOURCE
    assert "roi_clv_calibration_report_json_{safe_text(report.get('report_hash'))}" in SOURCE
    assert "_report_filename(report)" in SOURCE


def test_roi_clv_calibration_page_uses_in_memory_rows_only():
    assert "ROI_CLV_ROWS_KEY" in SOURCE
    assert "st.session_state" in SOURCE
    assert "write_text" not in SOURCE
    assert "write_bytes" not in SOURCE


def test_roi_clv_calibration_page_has_no_network_mutation_or_tuning_paths():
    forbidden = (
        "requests.",
        "httpx.",
        "urllib.",
        "append_performance_rows",
        "sync_rows_by_source",
        "approve_ledger_import",
        "update_result",
        "delete_proof",
        "fit(",
        "train(",
        "open(",
    )
    for token in forbidden:
        assert token not in SOURCE


def test_roi_clv_calibration_page_english_and_spanish_text_keys_exist():
    text = _text_dict()
    required = {
        "title",
        "caption",
        "workspace_id",
        "event",
        "result",
        "stake",
        "decimal_odds",
        "closing_decimal_odds",
        "add_row",
        "clear_rows",
        "run_audit",
        "row_ready",
        "rows_cleared",
        "report_ready",
        "calibration_ok",
        "calibration_warning",
        "calibration_failed",
        "insufficient_data",
        "roi_valid",
        "roi_warning",
        "clv_valid",
        "clv_warning",
        "event_rows",
        "report_summary",
        "validation",
        "download_report",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_roi_clv_calibration_page_has_no_fake_demo_values():
    for token in ("John Doe", "NY Liberty -120", "Aces vs Liberty", "+8.4%"):
        assert token not in SOURCE
