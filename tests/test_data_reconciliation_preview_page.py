import ast
from pathlib import Path

PAGE = Path("pages/data_reconciliation_preview.py")
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


def test_data_reconciliation_page_imports_read_only_services():
    for token in (
        "build_data_reconciliation_report",
        "export_data_reconciliation_report_json",
        "validate_data_reconciliation_report",
    ):
        assert token in SOURCE


def test_data_reconciliation_page_exposes_controls():
    for token in (
        "reconciliation_workspace_id",
        "reconciliation_sport",
        "reconciliation_event",
        "reconciliation_market_type",
        "reconciliation_selection",
        "reconciliation_source",
        "reconciliation_primary_value",
        "reconciliation_secondary_value",
        "reconciliation_confidence",
        "reconciliation_original_value",
        "reconciliation_latest_value",
        "reconciliation_add_locked_row",
        "reconciliation_add_confirmation",
        "reconciliation_add_value",
        "reconciliation_clear_preview",
        "reconciliation_run_preview",
    ):
        assert token in SOURCE


def test_data_reconciliation_page_displays_required_report_fields():
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
        "confirmation_payload_count",
        "value_payload_count",
        "reconciled_count",
        "review_count",
        "frozen_selection_logic",
        "warning_count",
        "error_count",
    ):
        assert token in SOURCE


def test_data_reconciliation_page_has_status_language():
    for token in (
        "RECONCILED",
        "REVIEW REQUIRED",
        "MISSING CONFIRMATION",
        "NO ROWS",
        "FROZEN SELECTION LOGIC",
    ):
        assert token in SOURCE


def test_data_reconciliation_page_download_is_memory_only_and_hash_keyed():
    assert "st.download_button" in SOURCE
    assert "export_data_reconciliation_report_json(report, public_safe=True).encode" in SOURCE
    assert "data_reconciliation_report_json_{safe_text(report.get('report_hash'))}" in SOURCE
    assert "_report_filename(report)" in SOURCE


def test_data_reconciliation_page_uses_in_memory_rows_only():
    assert "LOCKED_ROWS_KEY" in SOURCE
    assert "CONFIRMATION_ROWS_KEY" in SOURCE
    assert "VALUE_ROWS_KEY" in SOURCE
    assert "st.session_state" in SOURCE
    assert "write_text" not in SOURCE
    assert "write_bytes" not in SOURCE


def test_data_reconciliation_page_has_no_network_or_mutation_paths():
    forbidden = (
        "requests.",
        "httpx.",
        "urllib.",
        "approve_ledger_import",
        "append_performance_rows",
        "sync_rows_by_source",
        "update_result",
        "delete_proof",
        "open(",
    )
    for token in forbidden:
        assert token not in SOURCE


def test_data_reconciliation_page_english_and_spanish_text_keys_exist():
    text = _text_dict()
    required = {
        "title",
        "caption",
        "workspace_id",
        "event",
        "sport",
        "market_type",
        "selection",
        "source",
        "primary_value",
        "secondary_value",
        "confidence",
        "original_value",
        "latest_value",
        "add_locked_row",
        "add_confirmation",
        "add_value",
        "clear_preview",
        "run_preview",
        "row_ready",
        "confirmation_ready",
        "value_ready",
        "cleared",
        "report_ready",
        "reconciled",
        "review_required",
        "missing_confirmation",
        "no_rows",
        "frozen_logic",
        "locked_rows",
        "confirmation_rows",
        "value_rows",
        "reconciliation_rows",
        "report_summary",
        "validation",
        "download_report",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_data_reconciliation_page_has_no_fake_demo_values():
    for token in ("John Doe", "NY Liberty -120", "Aces vs Liberty", "+8.4%"):
        assert token not in SOURCE
