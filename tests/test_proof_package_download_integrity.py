from pathlib import Path

PROOF_CENTER = Path("pages/proof_center.py").read_text(encoding="utf-8")
REPORT_STUDIO = Path("pages/report_studio.py").read_text(encoding="utf-8")
INTEGRITY_SERVICE = Path("autonomous_betting_agent/proof_package_integrity_service.py").read_text(encoding="utf-8")


def _report_publisher_section() -> str:
    marker = "with tabs[10]:"
    assert marker in REPORT_STUDIO
    return REPORT_STUDIO[REPORT_STUDIO.index(marker):]


def _proof_package_section() -> str:
    marker = "with tabs[6]:"
    assert marker in PROOF_CENTER
    return PROOF_CENTER[PROOF_CENTER.index(marker):]


def test_proof_center_download_keys_and_filenames_use_package_hash():
    section = _proof_package_section()
    assert "proof_center_package_json_{package_hash}" in PROOF_CENTER
    assert "proof_center_package_markdown_{package_hash}" in PROOF_CENTER
    assert "proof_center_package_csv_{package_hash}_{filename}" in PROOF_CENTER
    assert "_download_filename(package" in PROOF_CENTER
    assert "workspace_id" in section
    assert "package_type" in section
    assert "_hash_fragment(package)" in PROOF_CENTER


def test_report_studio_download_keys_and_filenames_use_package_hash():
    section = _report_publisher_section()
    assert "report_studio_publisher_json_{package_hash}" in REPORT_STUDIO
    assert "report_studio_publisher_markdown_{package_hash}" in REPORT_STUDIO
    assert "report_studio_publisher_csv_{package_hash}_{filename}" in REPORT_STUDIO
    assert "_publisher_filename(payload" in REPORT_STUDIO
    assert "workspace_id" in section
    assert "package_type" in section
    assert "_hash_fragment(payload.get('package_hash'))" in REPORT_STUDIO


def test_proof_center_stale_preview_and_redaction_blocks_exist():
    section = _proof_package_section()
    assert "proof_center_package_fingerprint" in PROOF_CENTER
    assert "package_input_fingerprint" in PROOF_CENTER
    assert "stale_package = not _package_matches_current(package, package_workspace, package_type)" in section
    assert "redaction_failed" in section
    assert "disabled = stale or (not redaction_ok) or (is_private and not private_confirmed)" in PROOF_CENTER


def test_report_studio_stale_preview_and_redaction_blocks_exist():
    section = _report_publisher_section()
    assert "report_publisher_input_fingerprint" in REPORT_STUDIO
    assert "publisher_input_fingerprint" in REPORT_STUDIO
    assert "stale = not _publisher_matches_current(payload, publisher_workspace, publisher_type)" in section
    assert "redaction_failed" in section
    assert "disabled = stale or not redaction_ok" in REPORT_STUDIO


def test_private_internal_downloads_remain_proof_center_only_with_confirmation():
    proof_section = _proof_package_section()
    report_section = _report_publisher_section()
    assert "PROOF_CENTER_PACKAGE_TYPE_OPTIONS = (\"public\", \"client\", \"private\", \"internal_review\")" in PROOF_CENTER
    assert "private_package_confirmation" in proof_section
    assert "private_confirmation" in proof_section
    assert "private_export_hash" in proof_section
    assert "REPORT_STUDIO_PUBLISHER_PACKAGE_TYPE_OPTIONS = (\"public\", \"client\")" in REPORT_STUDIO
    assert "private_export_hash" not in report_section
    assert "private_export_csv" not in report_section
    assert "private_export_json" not in report_section
    assert "internal_review" not in report_section


def test_public_client_ui_does_not_expose_private_fields_in_report_studio():
    report_section = _report_publisher_section()
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
        assert token not in report_section


def test_integrity_service_contains_required_service_functions():
    for token in (
        "validate_package_export_integrity",
        "validate_public_client_package_safety",
        "validate_private_internal_package_isolation",
        "validate_report_publisher_payload_integrity",
        "validate_package_hash_stability",
        "validate_package_download_bundle",
        "validate_proof_grade_rules",
        "validate_top_positive_ev_safety",
        "build_proof_package_qa_report",
        "run_e2e_proof_package_checks",
    ):
        assert f"def {token}" in INTEGRITY_SERVICE


def test_integrity_service_is_read_only_and_has_no_demo_values():
    forbidden = (
        "append_performance_rows",
        "sync_rows_by_source",
        "approve_ledger_import",
        "preview_ledger_import",
        "create_correction",
        "update_result",
        "delete_proof",
        "John Doe",
        "NY Liberty -120",
        "Aces vs Liberty",
        "+8.4%",
    )
    for token in forbidden:
        assert token not in INTEGRITY_SERVICE
