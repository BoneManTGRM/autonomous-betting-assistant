import ast
from pathlib import Path

PAGE = Path("pages/report_studio.py")
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


def _publisher_section_source() -> str:
    marker = "with tabs[10]:"
    assert marker in SOURCE
    return SOURCE[SOURCE.index(marker):]


def test_report_studio_imports_report_publisher_service_function():
    assert "from autonomous_betting_agent.report_publisher_service import build_report_publisher_payload" in SOURCE
    assert "build_report_publisher_payload(" in SOURCE


def test_report_studio_exposes_only_public_client_package_types_for_publisher():
    options = _assignment_value("REPORT_STUDIO_PUBLISHER_PACKAGE_TYPE_OPTIONS")
    assert options == ("public", "client")
    section = _publisher_section_source()
    assert "REPORT_STUDIO_PUBLISHER_PACKAGE_TYPE_OPTIONS" in section
    assert "report_studio_publisher_package_type" in section
    assert '"internal_review"' not in section
    assert "build_private_audit_package" not in SOURCE
    assert "build_internal_review_package" not in SOURCE


def test_report_studio_shows_required_publisher_summaries_and_manifest():
    section = _publisher_section_source()
    for token in (
        "headline_summary",
        "performance_summary",
        "roi_summary",
        "clv_summary",
        "risk_summary",
        "top_positive_ev_summary",
        "proof_disclaimer",
        "verification_manifest",
    ):
        assert token in section


def test_report_studio_download_controls_use_current_package_hash():
    section = _publisher_section_source()
    assert "REPORT_STUDIO_PUBLISHER_FINGERPRINT_KEY" in SOURCE
    assert "publisher_input_fingerprint" in SOURCE
    assert "report_publisher_input_fingerprint" in SOURCE
    assert "_publisher_matches_current" in SOURCE
    assert "stale = not _publisher_matches_current(payload, publisher_workspace, publisher_type)" in section
    assert "_render_publisher_downloads(payload, stale)" in section
    assert "report_studio_publisher_json_{package_hash}" in SOURCE
    assert "report_studio_publisher_markdown_{package_hash}" in SOURCE
    assert "report_studio_publisher_csv_{package_hash}_{filename}" in SOURCE


def test_report_studio_blocks_redaction_failed_public_client_downloads():
    section = _publisher_section_source()
    assert "_publisher_redaction_passed" in SOURCE
    assert "redaction_ok" in SOURCE
    assert "redaction_failed" in SOURCE
    assert "disabled = stale or not redaction_ok" in SOURCE
    assert "_publisher_redaction_passed(payload)" in section


def test_report_studio_does_not_expose_private_internal_package_options_in_publisher_section():
    section = _publisher_section_source()
    forbidden = (
        "private_export_csv",
        "private_export_json",
        "private_export_hash",
        "previous_row_hash",
        "correction_reason",
        '"internal_review"',
    )
    for token in forbidden:
        assert token not in section


def test_report_studio_has_no_import_approval_or_write_paths():
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
        assert token not in SOURCE


def test_report_studio_english_and_spanish_publisher_text_keys_exist():
    text = _text_dict()
    required = {
        "publisher",
        "publisher_workspace_id",
        "package_type",
        "build_publisher_payload",
        "publisher_caption",
        "publisher_preview_ready",
        "stale_publisher",
        "redaction_failed",
        "headline_summary",
        "performance_summary",
        "roi_summary",
        "clv_summary",
        "risk_summary",
        "top_positive_ev_summary",
        "proof_disclaimer",
        "verification_manifest",
        "download_report_json",
        "download_report_markdown",
        "download_report_csv",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_report_studio_existing_tabs_remain_and_publisher_tab_is_added():
    assert "t(\"cards\")" in SOURCE
    assert "t(\"magazine\")" in SOURCE
    assert "t(\"diagnostics\")" in SOURCE
    assert "t(\"publisher\")" in SOURCE
    assert "with tabs[10]:" in SOURCE


def test_report_studio_publisher_ui_has_no_fake_demo_values():
    section = _publisher_section_source()
    for token in ("John Doe", "NY Liberty -120", "Aces vs Liberty", "+8.4%"):
        assert token not in section
