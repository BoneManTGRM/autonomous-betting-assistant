import ast
from pathlib import Path

PAGE = Path("pages/canonical_store_recovery.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_canonical_recovery_page_imports_services():
    for token in (
        "build_canonical_store_recovery_report_from_text",
        "export_canonical_recovery_json",
        "export_canonical_recovery_checks_csv",
        "export_canonical_recovery_store_summaries_csv",
        "export_canonical_recovery_rows_csv",
        "export_canonical_recovery_manifest_json",
    ):
        assert token in SOURCE


def test_canonical_recovery_page_exposes_controls():
    for token in (
        "canonical_recovery_workspace_id",
        "canonical_recovery_canonical_csv",
        "canonical_recovery_session_csv",
        "canonical_recovery_disk_csv",
        "canonical_recovery_local_json_csv",
        "canonical_recovery_predictor_csv",
        "canonical_recovery_odds_lock_csv",
        "canonical_recovery_dashboard_csv",
        "canonical_recovery_learning_csv",
        "canonical_recovery_reloaded_csv",
        "canonical_recovery_handoff_csv",
        "canonical_recovery_metadata_json",
        "canonical_recovery_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_canonical_recovery_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "recovery_id",
        "recovery_hash",
        "mode",
        "recovery_status",
        "resolved_store_name",
        "resolution_status",
        "resolved_row_count",
        "raw_row_count",
        "recovered_from_fallback",
        "duplicate_rows_removed",
        "pass_count",
        "warn_count",
        "fail_count",
        "recovery_checks",
        "store_summaries",
        "recovered_rows_preview",
        "duplicate_proof_id_groups",
        "workspace_mismatches",
        "safety_gates",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_canonical_recovery_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "canonical_csv",
        "session_csv",
        "disk_csv",
        "local_json_csv",
        "predictor_csv",
        "odds_lock_csv",
        "dashboard_csv",
        "learning_csv",
        "reloaded_csv",
        "handoff_csv",
        "metadata_json",
        "run",
        "summary",
        "checks",
        "stores",
        "recovered",
        "duplicates",
        "workspace_mismatches",
        "safety",
        "download_json",
        "download_checks",
        "download_stores",
        "download_rows",
        "download_manifest",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_canonical_recovery_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
