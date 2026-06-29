import ast
from pathlib import Path

PAGE = Path("pages/update_flow_control.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_update_flow_control_imports_services():
    for token in ("build_update_flow_report", "parse_update_csv_text", "build_dashboard_update_payload", "export_update_flow_json", "export_proposed_updates_csv"):
        assert token in SOURCE


def test_update_flow_control_exposes_controls_and_downloads():
    for token in ("update_flow_workspace_id", "update_flow_locked_csv", "update_flow_confirmation_csv", "update_flow_value_csv", "update_flow_run", "st.download_button"):
        assert token in SOURCE


def test_update_flow_control_displays_required_fields():
    for token in ("schema_version", "workspace_id", "status", "safe_to_export", "preview_only", "changed_records", "frozen_selection_logic", "row_count", "unique_events", "duplicate_row_count", "confirmation_payload_count", "value_payload_count", "ready_count", "review_count", "reconciliation_report_hash"):
        assert token in SOURCE


def test_update_flow_control_has_status_language():
    for token in ("READY TO EXPORT", "REVIEW REQUIRED", "NO ROWS", "PREVIEW ONLY", "NO RECORD CHANGE PERFORMED", "FROZEN SELECTION LOGIC"):
        assert token in SOURCE


def test_update_flow_control_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {"title", "caption", "workspace_id", "locked_csv", "confirmation_csv", "value_csv", "run_flow", "ready", "review", "empty", "preview_only", "no_change", "frozen_logic", "report_summary", "dashboard_payload", "proposed_exports", "download_json", "download_csv", "no_report"}
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_update_flow_control_has_no_external_call_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
