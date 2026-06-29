import ast
from pathlib import Path

PAGE = Path("pages/proof_center.py")
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


def test_proof_center_page_imports_required_service_functions():
    assert "from autonomous_betting_agent import proof_center_control_service" in SOURCE
    assert "proof_center_control_service.preview_ledger_import" in SOURCE
    assert "proof_center_control_service.approve_ledger_import" in SOURCE
    assert "proof_center_control_service.get_ledger_health" in SOURCE
    assert "proof_center_control_service.get_dashboard_readiness" in SOURCE
    assert "proof_center_control_service.review_duplicate_rows" in SOURCE
    assert "proof_center_control_service.review_correction_rows" in SOURCE
    assert "proof_center_control_service.get_public_proof_exports" in SOURCE
    assert "proof_center_control_service.get_private_proof_exports" in SOURCE


def test_source_key_options_are_present():
    options = _assignment_value("PROOF_CENTER_SOURCE_KEY_OPTIONS")
    assert options == (
        "odds_lock",
        "pro_predictor",
        "report_studio",
        "proof_center",
        "learning_page",
        "uploaded_csv",
        "generated_pick",
        "manual_review",
    )
    assert "st.selectbox(t(\"source_key\"), PROOF_CENTER_SOURCE_KEY_OPTIONS" in SOURCE


def test_preview_flow_does_not_write_and_approve_is_explicit_only():
    preview_start = SOURCE.index("if st.button(t(\"dry_run_preview\")")
    approve_start = SOURCE.index("if st.button(t(\"approve_import\")")
    preview_block = SOURCE[preview_start:approve_start]
    approve_block = SOURCE[approve_start:]
    assert "preview_ledger_import" in preview_block
    assert "review_duplicate_rows" in preview_block
    assert "review_correction_rows" in preview_block
    assert "approve_ledger_import" not in preview_block
    assert "approve_ledger_import" in approve_block
    assert "key=\"proof_center_approve_import\"" in approve_block


def test_approval_confirmation_preview_hash_and_stale_blocks_exist():
    assert "proof_center_approval_confirmation" in SOURCE
    assert "approval confirmation is required" in SOURCE
    assert "PROOF_CENTER_INPUT_FINGERPRINT_KEY" in SOURCE
    assert "PROOF_CENTER_IMPORT_PREVIEW_KEY" in SOURCE
    assert "PROOF_CENTER_UPLOAD_SNAPSHOT_KEY" in SOURCE
    assert "preview_hash" in SOURCE
    assert "_preview_matches_current_input" in SOURCE
    assert "not _preview_matches_current_input(current_fingerprint)" in SOURCE
    assert "disabled=blocked" in SOURCE


def test_upload_validation_empty_malformed_and_missing_fields_are_handled():
    assert "def validate_uploaded_proof_csv" in SOURCE
    assert "pd.read_csv(io.BytesIO(data))" in SOURCE
    assert "except Exception as exc" in SOURCE
    assert "empty_upload" in SOURCE
    assert "malformed_upload" in SOURCE
    assert "missing_fields" in SOURCE
    assert "PROOF_CENTER_REQUIRED_UPLOAD_FIELDS" in SOURCE
    assert "PROOF_CENTER_ODDS_FIELDS" in SOURCE


def test_public_and_private_export_controls_exist():
    assert "get_public_proof_exports" in SOURCE
    assert "get_private_proof_exports" in SOURCE
    assert "download_public_csv" in SOURCE
    assert "download_public_json" in SOURCE
    assert "download_private_csv" in SOURCE
    assert "download_private_json" in SOURCE
    assert "public_safe_proof_export.csv" in SOURCE
    assert "private_proof_export.json" in SOURCE


def test_ledger_health_dashboard_duplicate_and_correction_display_contracts():
    assert "ledger_health" in SOURCE
    assert "dashboard_readiness" in SOURCE
    assert "duplicate_review" in SOURCE
    assert "correction_review" in SOURCE
    assert "_display_dict(t(\"ledger_health\")" in SOURCE
    assert "_display_dict(t(\"dashboard_readiness\")" in SOURCE
    assert "_display_dict(t(\"duplicate_review\")" in SOURCE
    assert "_display_dict(t(\"correction_review\")" in SOURCE


def test_english_and_spanish_text_keys_exist_for_new_ui():
    text = _text_dict()
    required = {
        "ledger_control",
        "ledger_workspace_id",
        "source_key",
        "upload_csv",
        "upload_status",
        "rows_detected",
        "columns_detected",
        "missing_fields",
        "empty_upload",
        "malformed_upload",
        "no_upload",
        "dry_run_preview",
        "approve_import",
        "approval_confirmation",
        "approval_reason",
        "preview_summary",
        "approval_metadata",
        "ledger_health",
        "dashboard_readiness",
        "duplicate_review",
        "correction_review",
        "public_exports",
        "private_exports",
        "download_public_csv",
        "download_public_json",
        "download_private_csv",
        "download_private_json",
        "approval_blocked",
        "stale_preview",
        "preview_ready",
        "writes_warning",
        "proof_packages",
        "package_workspace_id",
        "package_type",
        "build_package_preview",
        "package_caption",
        "redaction_status",
        "verification_manifest",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])
    assert len(text["en"]["tabs"]) == 7
    assert len(text["es"]["tabs"]) == 7


def test_no_fake_demo_data_and_no_automatic_write_signals():
    assert "John Doe" not in SOURCE
    assert "NY Liberty -120" not in SOURCE
    assert "fake" not in SOURCE.lower()
    assert "demo rows" not in SOURCE.lower()
    assert "auto_approve" not in SOURCE
    assert "approve_ledger_import(upload_frame" not in SOURCE
