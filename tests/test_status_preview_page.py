import ast
from pathlib import Path

PAGE = Path("pages/status_preview.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_status_preview_page_imports_services():
    for token in ("build_status_preview_report", "export_status_preview_report_json", "validate_status_preview_report"):
        assert token in SOURCE


def test_status_preview_page_exposes_controls():
    for token in ("status_preview_workspace_id", "status_preview_category", "status_preview_name", "status_preview_source", "status_preview_primary", "status_preview_secondary", "status_preview_confidence", "status_preview_start_value", "status_preview_latest_value", "status_preview_add_record", "status_preview_add_marker", "status_preview_add_snapshot", "status_preview_clear", "status_preview_run"):
        assert token in SOURCE


def test_status_preview_page_displays_required_fields():
    for token in ("schema_version", "workspace_id", "report_id", "report_hash", "status", "overall_passed", "record_count", "unique_records", "duplicate_record_count", "marker_count", "snapshot_count", "ready_count", "review_count", "locked_logic", "warning_count", "error_count"):
        assert token in SOURCE


def test_status_preview_page_has_status_language():
    for token in ("READY", "REVIEW", "MISSING", "EMPTY", "LOCKED LOGIC"):
        assert token in SOURCE


def test_status_preview_page_download_is_memory_only_and_hash_keyed():
    assert "st.download_button" in SOURCE
    assert "export_status_preview_report_json(report, public_safe=True).encode" in SOURCE
    assert "status_preview_report_json_{safe_text(report.get('report_hash'))}" in SOURCE
    assert "_filename(report)" in SOURCE


def test_status_preview_page_uses_session_state_only():
    assert "RECORDS_KEY" in SOURCE
    assert "MARKERS_KEY" in SOURCE
    assert "SNAPSHOTS_KEY" in SOURCE
    assert "st.session_state" in SOURCE
    assert "write_text" not in SOURCE
    assert "write_bytes" not in SOURCE


def test_status_preview_page_has_no_network_or_mutation_paths():
    for token in ("requests.", "httpx.", "urllib.", "approve_ledger_import", "append_performance_rows", "sync_rows_by_source", "update_result", "delete_proof", "open("):
        assert token not in SOURCE


def test_status_preview_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {"title", "caption", "workspace_id", "category", "name", "source", "primary", "secondary", "confidence", "start_value", "latest_value", "add_record", "add_marker", "add_snapshot", "clear_preview", "run_preview", "ready", "review", "missing", "empty", "locked_logic", "records", "markers", "snapshots", "status_rows", "report_summary", "validation", "download_report", "no_report"}
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_status_preview_page_has_no_fake_demo_values():
    for token in ("John Doe", "NY Liberty -120", "Aces vs Liberty", "+8.4%"):
        assert token not in SOURCE
