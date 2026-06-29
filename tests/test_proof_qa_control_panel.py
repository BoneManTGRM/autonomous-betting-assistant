import ast
from pathlib import Path

PAGE = Path("pages/proof_center.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)

QA_STATUS_FIELDS = (
    "export_integrity_passed",
    "redaction_passed",
    "public_client_safety_passed",
    "private_internal_isolation_passed",
    "report_publisher_integrity_passed",
    "hash_stability_passed",
    "proof_grade_rules_passed",
    "top_positive_ev_safety_passed",
    "download_bundle_passed",
    "stale_preview_contract_passed",
    "no_write_paths_detected",
)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def _text_dict():
    return _assignment_value("TEXT")


def _qa_section() -> str:
    marker = "st.subheader(t(\"proof_qa_control_panel\"))"
    assert marker in SOURCE
    return SOURCE[SOURCE.index(marker):]


def _package_section() -> str:
    marker = "with tabs[6]:"
    assert marker in SOURCE
    return SOURCE[SOURCE.index(marker):]


def _function_source(name: str, next_name: str | None = None) -> str:
    start = SOURCE.index(f"def {name}")
    if next_name is None:
        return SOURCE[start:]
    end = SOURCE.index(f"def {next_name}", start)
    return SOURCE[start:end]


def test_proof_center_imports_phase_3e16_qa_services():
    assert "build_proof_package_qa_report" in SOURCE
    assert "run_e2e_proof_package_checks" in SOURCE
    assert "from autonomous_betting_agent.proof_package_integrity_service import build_proof_package_qa_report, run_e2e_proof_package_checks" in SOURCE


def test_proof_center_exposes_selected_and_full_e2e_qa_controls():
    section = _qa_section()
    assert "proof_qa_control_panel" in section
    assert "proof_center_qa_workspace_id" in section
    assert "proof_center_qa_package_type" in section
    assert "proof_center_run_selected_package_qa" in section
    assert "proof_center_run_full_e2e_qa" in section
    assert "build_proof_package_qa_report(qa_workspace, qa_package_type)" in section
    assert "run_e2e_proof_package_checks(qa_workspace)" in section


def test_proof_center_qa_package_type_selector_has_all_package_types():
    assert _assignment_value("PROOF_CENTER_PACKAGE_TYPE_OPTIONS") == ("public", "client", "private", "internal_review")
    assert "PROOF_CENTER_PACKAGE_TYPE_OPTIONS" in _qa_section()


def test_selected_package_qa_display_includes_required_fields():
    display_function = _function_source("_render_selected_qa_report", "_render_e2e_qa_report")
    for token in (
        "qa_report_id",
        "qa_report_hash",
        "generated_at_utc",
        "workspace_id",
        "package_type",
        "package_id",
        "package_hash",
        "public_export_hash",
        "proof_ready",
        "proof_grade",
        "selected_source",
        "ledger_backed",
        "ledger_integrity_status",
        "dashboard_ready",
        "overall_passed",
        "checked_outputs",
        "warning_count",
        "error_count",
    ):
        assert token in display_function or token in SOURCE


def test_private_export_hash_is_only_for_private_internal_display_logic():
    section = _package_section()
    assert "private_export_hash" in section
    assert "if package_type in PROOF_CENTER_PRIVATE_PACKAGE_TYPES else \"\"" in section
    assert "if package_type in PROOF_CENTER_PRIVATE_PACKAGE_TYPES:" in section
    assert "PRIVATE/INTERNAL ONLY" in SOURCE


def test_qa_status_display_includes_every_required_passed_field():
    assert _assignment_value("QA_STATUS_FIELDS") == QA_STATUS_FIELDS
    status_function = _function_source("_render_qa_status_checks", "_render_selected_qa_report")
    selected_function = _function_source("_render_selected_qa_report", "_render_e2e_qa_report")
    for field in QA_STATUS_FIELDS:
        assert field in SOURCE
    assert "_render_qa_status_checks(report)" in selected_function
    assert "QA_STATUS_FIELDS" in status_function


def test_full_e2e_qa_displays_all_package_types_and_failed_checks():
    e2e_function = _function_source("_render_e2e_qa_report", "_render_package_downloads")
    assert "package_type_results" in e2e_function
    assert "for package_type in PROOF_CENTER_PACKAGE_TYPE_OPTIONS" in SOURCE
    assert "failed_checks" in e2e_function
    assert "warning_count" in e2e_function
    assert "error_count" in e2e_function


def test_selected_and_e2e_qa_fingerprints_block_stale_views():
    section = _qa_section()
    assert "PROOF_CENTER_QA_FINGERPRINT_KEY" in SOURCE
    assert "PROOF_CENTER_E2E_QA_FINGERPRINT_KEY" in SOURCE
    assert "def proof_center_qa_fingerprint" in SOURCE
    assert "def proof_center_e2e_qa_fingerprint" in SOURCE
    assert "qa_input_fingerprint" in section
    assert "e2e_input_fingerprint" in section
    assert "stale_qa = not _qa_matches_current(selected_qa_report, qa_workspace, qa_package_type)" in section
    assert "stale_e2e = not _e2e_qa_matches_current(e2e_qa_result, qa_workspace)" in section
    assert "stale_qa" in SOURCE
    assert "stale_e2e_qa" in SOURCE


def test_qa_downloads_use_qa_report_hash_and_disable_when_stale():
    selected_function = _function_source("_render_selected_qa_report", "_render_e2e_qa_report")
    e2e_function = _function_source("_render_e2e_qa_report", "_render_package_downloads")
    assert "download_selected_qa_json" in selected_function
    assert "download_e2e_qa_json" in e2e_function
    assert "proof_center_selected_qa_json_{safe_text(report.get('qa_report_hash'))}" in SOURCE
    assert "proof_center_e2e_qa_json_{e2e_hash}" in SOURCE
    assert "_qa_download_filename(report)" in SOURCE
    assert "_e2e_download_filename(workspace_id, e2e_result)" in SOURCE
    assert "disabled=stale" in selected_function
    assert "disabled=stale" in e2e_function
    assert "json.dumps" in SOURCE


def test_qa_panel_does_not_call_or_import_write_mutation_functions():
    section = _qa_section()
    forbidden = (
        "approve_ledger_import",
        "preview_ledger_import",
        "append_performance_rows",
        "sync_rows_by_source",
        "mutate_result",
        "update_result",
        "delete_proof",
        "write_text",
        "write_bytes",
        "open(",
    )
    for token in forbidden:
        assert token not in section


def test_public_client_qa_display_uses_sanitized_summary_not_raw_results():
    selected_function = _function_source("_render_selected_qa_report", "_render_e2e_qa_report")
    safe_summary_function = _function_source("_qa_safe_summary", "_qa_private_summary")
    assert "_qa_safe_summary" in SOURCE
    assert "_qa_report_download_payload" in SOURCE
    assert "_display_dict(t(\"qa_safe_summary\"), _qa_safe_summary(report))" in selected_function
    assert "validation_results" not in safe_summary_function
    assert "blocked_terms_count" in SOURCE
    assert "blocked_paths_count" in SOURCE
    assert "generic_redaction_warning" in SOURCE


def test_private_internal_qa_can_show_deeper_details_under_private_label():
    assert "_qa_private_summary" in SOURCE
    assert "_display_dict(t(\"qa_private_details\"), _qa_private_summary(report))" in SOURCE
    assert "private_internal_only" in SOURCE
    assert "PRIVATE/INTERNAL ONLY" in SOURCE


def test_public_client_qa_section_does_not_render_raw_private_export_payloads():
    section = _qa_section()
    assert "private_export_csv" not in section
    assert "private_export_json" not in section
    assert "raw CSV" not in section
    assert "raw JSON" not in section
    assert "raw Markdown" not in section


def test_public_client_private_field_names_are_not_rendered_in_safe_summary():
    safe_summary = _function_source("_qa_safe_summary", "_qa_private_summary")
    forbidden = (
        "source_file",
        "previous_row_hash",
        "correction_reason",
        "api_key",
        "secret",
        "token",
        "bearer",
        "password",
        "/home/",
        "/mnt/",
        "data/private",
    )
    for token in forbidden:
        assert token not in safe_summary


def test_qa_visual_status_and_enforcement_messages_exist():
    for token in (
        "QA PASSED",
        "QA FAILED",
        "PUBLIC/CLIENT SAFE",
        "PUBLIC/CLIENT BLOCKED",
        "PRIVATE/INTERNAL ONLY",
        "PROOF READY",
        "NOT PROOF READY",
        "EXPORT VALID",
        "EXPORT FAILED",
        "REDACTION PASSED",
        "REDACTION FAILED",
        "HASH STABLE",
        "HASH FAILED",
        "NO WRITE PATHS",
        "WRITE PATH WARNING",
        "This package failed QA and must not be treated as final proof.",
        "This package is not proof-ready. It may be provisional, empty, fallback-backed, or blocked by integrity checks.",
        "Public/client exports are blocked because redaction validation failed.",
        "Read-only safety failed. Review write/mutation path warnings before release.",
    ):
        assert token in SOURCE


def test_existing_proof_center_package_ui_contracts_remain_present():
    section = _package_section()
    assert "proof_center_private_package_confirmation" in section
    assert "stale_package = not _package_matches_current(package, package_workspace, package_type)" in section
    assert "_render_package_downloads(package, stale_package, private_confirmed)" in section
    assert "proof_center_package_json_{package_hash}" in SOURCE
    assert "proof_center_package_markdown_{package_hash}" in SOURCE
    assert "proof_center_package_csv_{package_hash}_{filename}" in SOURCE


def test_english_and_spanish_qa_text_keys_exist():
    text = _text_dict()
    required = {
        "proof_qa_control_panel",
        "qa_caption",
        "qa_workspace_id",
        "qa_package_type",
        "run_selected_package_qa",
        "run_full_e2e_qa",
        "selected_package_qa",
        "full_e2e_qa",
        "stale_qa",
        "stale_e2e_qa",
        "qa_passed",
        "qa_failed",
        "public_client_safe",
        "public_client_blocked",
        "private_internal_only",
        "proof_ready_status",
        "not_proof_ready_status",
        "export_valid",
        "export_failed",
        "redaction_passed_status",
        "redaction_failed_status",
        "hash_stable",
        "hash_failed",
        "no_write_paths",
        "write_path_warning",
        "failed_qa_final_warning",
        "not_proof_ready_qa_warning",
        "redaction_blocked_warning",
        "read_only_failed_warning",
        "generic_redaction_warning",
        "qa_status_checks",
        "qa_safe_summary",
        "qa_private_details",
        "failed_checks",
        "warning_count",
        "error_count",
        "blocked_terms_count",
        "blocked_paths_count",
        "checked_outputs",
        "download_selected_qa_json",
        "download_e2e_qa_json",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_no_demo_values_in_qa_panel():
    section = _qa_section()
    for token in ("John Doe", "NY Liberty -120", "Aces vs Liberty", "+8.4%"):
        assert token not in section
