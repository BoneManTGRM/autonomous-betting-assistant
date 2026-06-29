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


def _package_section_source() -> str:
    marker = "with tabs[6]:"
    assert marker in SOURCE
    return SOURCE[SOURCE.index(marker):]


def test_proof_center_imports_proof_package_service_functions():
    for token in (
        "build_public_proof_package",
        "build_client_summary_package",
        "build_private_audit_package",
        "build_internal_review_package",
        "export_proof_package_json",
        "export_proof_package_markdown",
        "export_proof_package_csv_bundle",
        "validate_public_package_redactions",
        "package_is_proof_ready",
    ):
        assert token in SOURCE


def test_proof_center_exposes_package_type_selector_with_all_package_types():
    options = _assignment_value("PROOF_CENTER_PACKAGE_TYPE_OPTIONS")
    assert options == ("public", "client", "private", "internal_review")
    section = _package_section_source()
    assert "PROOF_CENTER_PACKAGE_TYPE_OPTIONS" in section
    assert "proof_center_package_type" in section


def test_proof_center_exposes_package_download_controls_and_current_hash_keys():
    section = _package_section_source()
    assert "st.download_button" in SOURCE
    assert "export_proof_package_json(package)" in SOURCE
    assert "export_proof_package_markdown(package)" in SOURCE
    assert "export_proof_package_csv_bundle(package)" in SOURCE
    assert "package_hash" in section
    assert "proof_center_package_json_{package_hash}" in SOURCE
    assert "proof_center_package_markdown_{package_hash}" in SOURCE
    assert "proof_center_package_csv_{package_hash}_{filename}" in SOURCE


def test_proof_center_shows_required_package_fields():
    section = _package_section_source()
    for token in (
        "package_id",
        "package_hash",
        "public_export_hash",
        "private_export_hash",
        "proof_ready",
        "proof_grade",
        "redaction_status",
        "verification_manifest",
        "warnings_errors",
    ):
        assert token in section
    assert "PROOF_CENTER_PRIVATE_PACKAGE_TYPES" in section


def test_proof_center_requires_private_confirmation_before_private_downloads():
    section = _package_section_source()
    assert "proof_center_private_package_confirmation" in section
    assert "private_confirmation" in section
    assert "private_confirmed" in SOURCE
    assert "is_private and not private_confirmed" in SOURCE


def test_proof_center_blocks_stale_package_downloads_and_uses_fingerprint():
    section = _package_section_source()
    assert "PROOF_CENTER_PACKAGE_FINGERPRINT_KEY" in SOURCE
    assert "PROOF_CENTER_PACKAGE_META_KEY" in SOURCE
    assert "proof_center_package_fingerprint" in SOURCE
    assert "package_input_fingerprint" in SOURCE
    assert "stale_package = not _package_matches_current(package, package_workspace, package_type)" in section
    assert "disabled = stale" in SOURCE


def test_proof_center_blocks_public_client_downloads_when_redaction_validation_fails():
    assert "validate_public_package_redactions(package)" in SOURCE
    assert "redaction_ok" in SOURCE
    assert "redaction_failed" in SOURCE
    assert "disabled = stale" in SOURCE


def test_proof_center_package_ui_does_not_call_import_approval_or_write_paths():
    section = _package_section_source()
    forbidden = (
        "append_performance_rows",
        "sync_rows_by_source",
        "approve_ledger_import",
        "preview_ledger_import",
        "mutate_result",
        "update_result",
        "delete_proof",
    )
    for token in forbidden:
        assert token not in section


def test_proof_center_public_client_downloads_use_service_exports_not_raw_private_exports():
    section = _package_section_source()
    assert "export_proof_package_json" in SOURCE
    assert "export_proof_package_markdown" in SOURCE
    assert "export_proof_package_csv_bundle" in SOURCE
    assert "private_export_csv" not in section
    assert "private_export_json" not in section


def test_proof_center_english_and_spanish_package_text_keys_exist():
    text = _text_dict()
    required = {
        "proof_packages",
        "package_workspace_id",
        "package_type",
        "build_package_preview",
        "package_caption",
        "package_preview_ready",
        "proof_ready_warning",
        "stale_package",
        "redaction_failed",
        "redaction_status",
        "verification_manifest",
        "warnings_errors",
        "private_confirmation",
        "private_package_warning",
        "download_package_json",
        "download_package_markdown",
        "download_package_csv",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])
    assert len(text["en"]["tabs"]) == 7
    assert len(text["es"]["tabs"]) == 7


def test_proof_center_package_ui_has_no_fake_demo_values():
    section = _package_section_source()
    for token in ("John Doe", "NY Liberty -120", "Aces vs Liberty", "+8.4%"):
        assert token not in section
