import ast
from pathlib import Path

PAGE = Path("pages/workspace_isolation_audit.py")
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


def test_workspace_isolation_audit_imports_read_only_services():
    for token in (
        "build_workspace_isolation_report",
        "export_workspace_isolation_report_json",
        "validate_workspace_id",
        "validate_workspace_isolation_report",
        "build_public_proof_package",
        "build_client_summary_package",
        "build_proof_package_qa_report",
        "build_proof_archive_index",
    ):
        assert token in SOURCE


def test_workspace_isolation_audit_exposes_controls():
    for token in (
        "workspace_isolation_workspace_id",
        "workspace_isolation_build_artifacts",
        "workspace_isolation_run_audit",
        "WORKSPACE_ISOLATION_PREVIEW_KEY",
    ):
        assert token in SOURCE


def test_workspace_isolation_audit_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "report_id",
        "report_hash",
        "workspace_id_valid",
        "checked_artifact_count",
        "checked_object_count",
        "failed_object_count",
        "cross_workspace_leakage_count",
        "missing_workspace_count",
        "private_marker_count",
        "overall_passed",
        "object_results",
        "blocked_terms_count",
        "blocked_paths_count",
    ):
        assert token in SOURCE


def test_workspace_isolation_audit_has_clear_status_language():
    for token in (
        "WORKSPACE ISOLATION PASSED",
        "WORKSPACE ISOLATION FAILED",
        "NO CROSS-WORKSPACE LEAKAGE",
        "CROSS-WORKSPACE WARNING",
        "PUBLIC/CLIENT SAFE",
        "PUBLIC/CLIENT BLOCKED",
    ):
        assert token in SOURCE


def test_workspace_isolation_audit_download_is_memory_only_and_hash_keyed():
    assert "st.download_button" in SOURCE
    assert "export_workspace_isolation_report_json(report, public_safe=True).encode" in SOURCE
    assert "workspace_isolation_report_json_{safe_text(report.get('report_hash'))}" in SOURCE
    assert "_report_filename(report)" in SOURCE


def test_workspace_isolation_audit_sanitizes_object_results_for_ui():
    object_results_start = SOURCE.index("object_rows = []")
    object_results_section = SOURCE[object_results_start:SOURCE.index("with st.expander", object_results_start)]
    assert "error_count" in object_results_section
    assert "blocked_terms_count" in object_results_section
    assert "blocked_paths_count" in object_results_section
    assert "errors" not in object_results_section


def test_workspace_isolation_audit_has_no_write_or_mutation_paths():
    forbidden = (
        "approve_ledger_import",
        "preview_ledger_import",
        "append_performance_rows",
        "sync_rows_by_source",
        "update_result",
        "delete_proof",
        "write_text",
        "write_bytes",
        "open(",
    )
    for token in forbidden:
        assert token not in SOURCE


def test_workspace_isolation_audit_english_and_spanish_text_keys_exist():
    text = _text_dict()
    required = {
        "title",
        "caption",
        "workspace_id",
        "build_artifacts",
        "run_audit",
        "artifacts_ready",
        "audit_ready",
        "workspace_valid",
        "overall_passed",
        "checked_objects",
        "failed_objects",
        "cross_leakage",
        "private_markers",
        "public_client_mode",
        "isolation_passed",
        "isolation_failed",
        "no_cross_workspace",
        "cross_workspace_warning",
        "public_client_safe",
        "public_client_blocked",
        "audit_summary",
        "object_results",
        "validation",
        "download_report",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_workspace_isolation_audit_has_no_fake_demo_values():
    for token in ("John Doe", "NY Liberty -120", "Aces vs Liberty", "+8.4%"):
        assert token not in SOURCE
