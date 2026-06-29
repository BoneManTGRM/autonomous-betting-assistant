import json

from autonomous_betting_agent import client_access_roles_service as access


def test_normalize_client_role_aliases_and_unknowns():
    assert access.normalize_client_role("owner") == "admin"
    assert access.normalize_client_role("ops") == "operator"
    assert access.normalize_client_role("subscriber") == "client"
    assert access.normalize_client_role("guest") == "public"
    assert access.normalize_client_role("unknown") == "public"


def test_admin_can_access_private_internal_and_approve_imports():
    private_access = access.validate_role_access("admin", "proof_center", "view_private_audit", "private")
    import_access = access.validate_role_access("admin", "proof_center", "approve_import", "private")

    assert private_access["allowed"] is True
    assert import_access["allowed"] is True


def test_operator_can_run_qa_but_cannot_approve_imports():
    qa_access = access.validate_role_access("operator", "qa_report", "run_qa", "public")
    import_access = access.validate_role_access("operator", "proof_center", "approve_import", "private")

    assert qa_access["allowed"] is True
    assert import_access["allowed"] is False
    assert any("operator role cannot approve imports" in error for error in import_access["errors"])


def test_client_demo_public_cannot_access_private_internal_packages():
    for role in ("client", "demo", "public"):
        result = access.validate_role_access(role, "proof_package", "download_json", "private")
        assert result["allowed"] is False
        assert "role cannot access private/internal package types" in result["errors"]


def test_public_role_can_only_view_public_share_public_package():
    allowed = access.validate_role_access("public", "public_proof_share", "view_public_share", "public")
    blocked_client = access.validate_role_access("public", "client_proof_viewer", "view_client_viewer", "client")
    blocked_download = access.validate_role_access("public", "proof_package", "download_json", "public")

    assert allowed["allowed"] is True
    assert blocked_client["allowed"] is False
    assert blocked_download["allowed"] is False


def test_client_role_can_access_client_viewer_and_client_downloads():
    assert access.validate_role_access("client", "client_proof_viewer", "view_client_viewer", "client")["allowed"] is True
    assert access.validate_role_access("client", "proof_package", "download_json", "client")["allowed"] is True
    assert access.validate_role_access("client", "proof_center", "view", "client")["allowed"] is False


def test_role_access_matrix_covers_all_roles_resources_and_package_types():
    matrix = access.build_client_access_role_matrix()
    expected_rows = len(access.CLIENT_ACCESS_ROLES) * len(access.CLIENT_ACCESS_RESOURCES) * len(access.CLIENT_ACCESS_PACKAGE_TYPES)

    assert matrix["matrix_hash"].startswith("client_access_matrix_")
    assert len(matrix["rows"]) == expected_rows
    assert set(matrix["roles"]) == set(access.CLIENT_ACCESS_ROLES)
    assert set(matrix["package_types"]) == set(access.CLIENT_ACCESS_PACKAGE_TYPES)


def test_client_access_audit_report_flags_expected_private_denial_for_client():
    report = access.build_client_access_audit_report("client")

    assert report["role"] == "client"
    assert report["overall_passed"] is True
    assert report["private_denial_count"] >= 1
    assert report["unexpected_private_allow_count"] == 0
    assert report["report_hash"].startswith("client_access_hash_")


def test_client_access_audit_report_hash_stable_when_generated_at_changes():
    report = access.build_client_access_audit_report("client")
    changed_time = dict(report, generated_at_utc="2099-01-01T00:00:00Z")
    changed_count = dict(report, unexpected_private_allow_count=9)

    assert access.build_client_access_report_hash(report) == access.build_client_access_report_hash(changed_time)
    assert access.build_client_access_report_hash(report) != access.build_client_access_report_hash(changed_count)


def test_validate_client_access_audit_report_blocks_overstated_private_access():
    report = access.build_client_access_audit_report("client")
    overstated = dict(report, overall_passed=True, unexpected_private_allow_count=1)
    overstated["report_hash"] = access.build_client_access_report_hash(overstated)

    result = access.validate_client_access_audit_report(overstated)

    assert result["passed"] is False
    assert any("overall_passed is overstated" in error for error in result["errors"])


def test_export_client_access_audit_report_json_is_sanitized():
    report = access.build_client_access_audit_report("client")
    payload = json.loads(access.export_client_access_audit_report_json(report, public_safe=True))

    assert payload["role"] == "client"
    assert "checks" in payload
    assert all("errors" not in check for check in payload["checks"])
    assert all("error_count" in check for check in payload["checks"])
    assert "report_hash" in payload


def test_get_role_access_policy_is_json_safe():
    payload = access.get_role_access_policy("operator")
    dumped = json.dumps(payload, sort_keys=True)

    assert "operator" in dumped
    assert payload["private_internal_allowed"] is True


def test_client_access_roles_service_has_no_write_or_mutation_paths():
    source = open("autonomous_betting_agent/client_access_roles_service.py", encoding="utf-8").read()
    forbidden = (
        "approve_ledger_import(",
        "preview_ledger_import(",
        "append_performance_rows",
        "sync_rows_by_source",
        "update_result",
        "delete_proof",
        "write_text",
        "write_bytes",
    )
    for token in forbidden:
        assert token not in source
