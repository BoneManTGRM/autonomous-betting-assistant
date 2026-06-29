import ast
from pathlib import Path

PAGE = Path("pages/client_access_roles_audit.py")
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


def test_client_access_roles_audit_imports_read_only_services():
    for token in (
        "build_client_access_audit_report",
        "build_client_access_role_matrix",
        "export_client_access_audit_report_json",
        "get_role_access_policy",
        "validate_client_access_audit_report",
        "validate_role_access",
    ):
        assert token in SOURCE


def test_client_access_roles_audit_exposes_controls():
    for token in (
        "client_access_role_selector",
        "client_access_resource_selector",
        "client_access_action_selector",
        "client_access_package_type_selector",
        "client_access_run_role_audit",
        "client_access_build_matrix",
    ):
        assert token in SOURCE


def test_client_access_roles_audit_displays_roles_resources_actions_and_package_types():
    for token in (
        "admin",
        "operator",
        "client",
        "demo",
        "public",
        "proof_center",
        "public_proof_share",
        "client_proof_viewer",
        "workspace_isolation_audit",
        "proof_package",
        "qa_report",
        "public",
        "client",
        "private",
        "internal_review",
        "download_json",
        "run_qa",
        "approve_import",
        "view_private_audit",
    ):
        assert token in SOURCE


def test_client_access_roles_audit_has_clear_status_language():
    for token in (
        "ACCESS ALLOWED",
        "ACCESS BLOCKED",
        "PRIVATE/INTERNAL ALLOWED",
        "PRIVATE/INTERNAL BLOCKED",
        "OPERATOR ONLY",
        "CLIENT SAFE",
    ):
        assert token in SOURCE


def test_client_access_roles_audit_displays_audit_hash_and_counts():
    for token in (
        "report_id",
        "report_hash",
        "overall_passed",
        "allowed_count",
        "denied_count",
        "private_denial_count",
        "unexpected_private_allow_count",
        "check_count",
        "matrix_hash",
    ):
        assert token in SOURCE


def test_client_access_roles_audit_download_is_memory_only_and_hash_keyed():
    assert "st.download_button" in SOURCE
    assert "export_client_access_audit_report_json(report, public_safe=True).encode" in SOURCE
    assert "client_access_roles_report_json_{safe_text(report.get('report_hash'))}" in SOURCE
    assert "_report_filename(report)" in SOURCE


def test_client_access_roles_audit_sanitizes_check_display():
    assert "_checks_frame" in SOURCE
    checks_function = SOURCE[SOURCE.index("def _checks_frame"):SOURCE.index("st.title")]
    assert "error_count" in checks_function
    assert "warning_count" in checks_function
    display_section = SOURCE[SOURCE.index("st.dataframe(_checks_frame(report)"):SOURCE.index("with st.expander(t(\"validation\")")]
    assert "errors" not in display_section
    assert "warnings" not in display_section


def test_client_access_roles_audit_has_no_write_or_mutation_paths():
    forbidden = (
        "approve_ledger_import(",
        "preview_ledger_import(",
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


def test_client_access_roles_audit_english_and_spanish_text_keys_exist():
    text = _text_dict()
    required = {
        "title",
        "caption",
        "role",
        "resource",
        "action",
        "package_type",
        "run_access_check",
        "run_role_audit",
        "build_matrix",
        "access_allowed",
        "access_blocked",
        "private_internal_allowed",
        "private_internal_blocked",
        "operator_only",
        "client_safe",
        "policy",
        "audit_summary",
        "checks",
        "matrix",
        "validation",
        "download_report",
        "report_ready",
        "matrix_ready",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_client_access_roles_audit_has_no_fake_demo_values():
    for token in ("John Doe", "NY Liberty -120", "Aces vs Liberty", "+8.4%"):
        assert token not in SOURCE
