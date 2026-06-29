import ast
from pathlib import Path

PAGE = Path("pages/client_proof_viewer.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
SIDEBAR = Path("autonomous_betting_agent/sidebar_nav.py").read_text(encoding="utf-8")


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def _text_dict():
    return _assignment_value("TEXT")


def test_client_proof_viewer_imports_client_safe_read_only_services():
    for token in (
        "build_client_summary_package",
        "build_proof_package_qa_report",
        "export_proof_package_json",
        "export_proof_package_markdown",
        "export_proof_package_csv_bundle",
        "package_is_proof_ready",
        "validate_public_package_redactions",
    ):
        assert token in SOURCE


def test_client_proof_viewer_is_client_only_and_no_private_builders():
    assert _assignment_value("CLIENT_VIEWER_PACKAGE_TYPE") == "client"
    assert "build_public_proof_package" not in SOURCE
    assert "build_private_audit_package" not in SOURCE
    assert "build_internal_review_package" not in SOURCE
    assert "internal_review" not in SOURCE.replace('"internal_review",', "")


def test_client_proof_viewer_uses_fingerprint_and_blocks_stale_downloads():
    assert "CLIENT_VIEWER_FINGERPRINT_KEY" in SOURCE
    assert "def client_viewer_fingerprint" in SOURCE
    assert "CLIENT_VIEWER_PACKAGE_TYPE" in SOURCE
    assert "package_id" in SOURCE
    assert "package_hash" in SOURCE
    assert "stale = not _preview_matches(package, workspace_id)" in SOURCE
    assert "disabled = stale or not redaction_ok" in SOURCE
    assert "stale_preview" in SOURCE


def test_client_proof_viewer_download_keys_and_filenames_include_package_hash():
    assert "client_proof_viewer_json_{package_hash}" in SOURCE
    assert "client_proof_viewer_markdown_{package_hash}" in SOURCE
    assert "client_proof_viewer_csv_{package_hash}_{filename}" in SOURCE
    assert "aba_client_proof_viewer_{workspace_id}_client_{_hash_fragment(package)}" in SOURCE
    assert "_filename(package" in SOURCE


def test_client_proof_viewer_blocks_redaction_failed_downloads():
    assert "validate_public_package_redactions(package)" in SOURCE
    assert "redaction_ok = _redaction_passed(package)" in SOURCE
    assert "if not redaction_ok:" in SOURCE
    assert "redaction_failed" in SOURCE
    assert "disabled = stale or not redaction_ok" in SOURCE


def test_client_proof_viewer_shows_required_client_proof_fields():
    for token in (
        "proof_ready",
        "proof_grade",
        "ledger_backed",
        "selected_source",
        "ledger_integrity_status",
        "dashboard_ready",
        "duplicate_count",
        "correction_count",
        "package_id",
        "package_hash",
        "public_export_hash",
        "qa_report_hash",
        "win_rate_ex_push_cancel",
        "ROI",
        "profit_units",
        "average_CLV",
        "proof_summary",
        "roi_summary",
        "clv_summary",
        "verification_manifest",
        "redaction_status",
        "qa_status",
        "top_positive_ev_picks",
    ):
        assert token in SOURCE


def test_client_proof_viewer_never_renders_private_fields():
    forbidden = (
        "private_export_csv",
        "private_export_json",
        "private_export_hash",
        "previous_row_hash",
        "correction_reason",
        "source_file",
        "api_key",
        "secret",
        "token",
        "bearer",
        "password",
        "/home/",
        "/mnt/",
        "data/private",
    )
    render_source = SOURCE[SOURCE.find("def client_viewer_fingerprint") :]
    for token in forbidden:
        assert token not in render_source


def test_client_proof_viewer_has_no_write_or_mutation_paths():
    forbidden = (
        "append_performance_rows",
        "sync_rows_by_source",
        "approve_ledger_import",
        "preview_ledger_import",
        "create_correction",
        "update_result",
        "delete_proof",
        "write_text",
        "write_bytes",
        "open(",
    )
    for token in forbidden:
        assert token not in SOURCE


def test_client_proof_viewer_english_and_spanish_text_keys_exist():
    text = _text_dict()
    required = {
        "title",
        "caption",
        "client_caption",
        "workspace_id",
        "build_preview",
        "preview_ready",
        "no_preview",
        "stale_preview",
        "redaction_failed",
        "not_proof_ready",
        "proof_ready",
        "proof_grade",
        "ledger_backed",
        "selected_source",
        "ledger_integrity_status",
        "dashboard_ready",
        "package_id",
        "package_hash",
        "public_export_hash",
        "qa_report_hash",
        "record",
        "win_rate",
        "roi",
        "profit_units",
        "average_clv",
        "unique_events",
        "duplicate_count",
        "correction_count",
        "top_ev",
        "no_top_ev",
        "proof_summary",
        "roi_summary",
        "clv_summary",
        "verification_manifest",
        "redaction_status",
        "qa_status",
        "warnings_errors",
        "download_json",
        "download_markdown",
        "download_csv",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_client_proof_viewer_sidebar_navigation_contract_is_expected():
    # Phase 3E.18 expects this page to be reachable via Streamlit's native pages directory.
    # A sidebar link may be added separately when the navigation file can be safely patched.
    assert PAGE.exists()
    assert "pages/client_proof_viewer.py" not in SIDEBAR or "Client Proof Viewer" in SIDEBAR


def test_client_proof_viewer_has_no_fake_demo_values():
    for token in ("John Doe", "NY Liberty -120", "Aces vs Liberty", "+8.4%"):
        assert token not in SOURCE
