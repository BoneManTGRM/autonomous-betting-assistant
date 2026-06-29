import json

from autonomous_betting_agent import workspace_isolation_service as isolation


def test_validate_workspace_id_accepts_safe_workspace_and_blocks_reserved_values():
    assert isolation.validate_workspace_id("client-01")["passed"] is True
    assert isolation.validate_workspace_id("client_01.audit")["passed"] is True

    assert isolation.validate_workspace_id("../client")["passed"] is False
    assert isolation.validate_workspace_id("all")["passed"] is False
    assert isolation.validate_workspace_id("*")["passed"] is False


def test_validate_workspace_object_passes_matching_workspace():
    item = {
        "workspace_id": "client-01",
        "package_id": "pkg_1",
        "package_hash": "package_hash_abc",
    }

    result = isolation.validate_workspace_object("client-01", item)

    assert result["passed"] is True
    assert result["object_type"] == "package"
    assert result["object_workspace_id"] == "client-01"


def test_validate_workspace_object_blocks_cross_workspace_leakage():
    item = {
        "workspace_id": "client-b",
        "package_id": "pkg_1",
        "package_hash": "package_hash_abc",
    }

    result = isolation.validate_workspace_object("client-a", item)

    assert result["passed"] is False
    assert "object workspace_id does not match requested workspace." in result["errors"]


def test_validate_workspace_object_blocks_missing_workspace_id():
    result = isolation.validate_workspace_object("client-a", {"package_id": "pkg_1"})

    assert result["passed"] is False
    assert "object missing workspace_id." in result["errors"]


def test_public_client_mode_blocks_private_markers_and_paths():
    item = {
        "workspace_id": "client-a",
        "source_file": "/mnt/private/client-a.csv",
        "private_export_hash": "export_hash_secret",
    }

    result = isolation.validate_workspace_object("client-a", item, public_client=True)

    assert result["passed"] is False
    assert result["details"]["blocked_terms_count"] >= 1
    assert result["details"]["blocked_paths_count"] >= 1


def test_private_mode_allows_private_markers_but_still_checks_workspace():
    item = {
        "workspace_id": "client-a",
        "source_file": "/mnt/private/client-a.csv",
        "private_export_hash": "export_hash_secret",
    }

    assert isolation.validate_workspace_object("client-a", item, public_client=False)["passed"] is True
    assert isolation.validate_workspace_object("client-b", item, public_client=False)["passed"] is False


def test_filter_workspace_objects_keeps_only_matching_safe_objects():
    items = [
        {"workspace_id": "client-a", "proof_id": "row-1"},
        {"workspace_id": "client-b", "proof_id": "row-2"},
        {"workspace_id": "client-a", "source_file": "/home/private.csv"},
    ]

    result = isolation.filter_workspace_objects("client-a", items, public_client=True)

    assert result["kept_count"] == 1
    assert result["rejected_count"] == 2
    assert result["passed"] is False


def test_build_workspace_isolation_report_detects_leakage_and_private_markers():
    artifacts = {
        "packages": [
            {"workspace_id": "client-a", "package_id": "pkg-a", "package_hash": "hash-a"},
            {"workspace_id": "client-b", "package_id": "pkg-b", "package_hash": "hash-b"},
        ],
        "rows": [
            {"workspace_id": "client-a", "proof_id": "row-a"},
            {"workspace_id": "client-a", "source_file": "/mnt/private.csv"},
        ],
    }

    report = isolation.build_workspace_isolation_report("client-a", artifacts)

    assert report["overall_passed"] is False
    assert report["checked_artifact_count"] == 2
    assert report["checked_object_count"] == 4
    assert report["failed_object_count"] >= 2
    assert report["cross_workspace_leakage_count"] >= 1
    assert report["private_marker_count"] >= 1
    assert report["report_hash"].startswith("workspace_isolation_hash_")


def test_build_workspace_isolation_report_passes_clean_payloads():
    artifacts = {
        "packages": [{"workspace_id": "client-a", "package_id": "pkg-a", "package_hash": "hash-a"}],
        "qa_reports": [{"workspace_id": "client-a", "qa_report_hash": "qa-a", "overall_passed": True}],
    }

    report = isolation.build_workspace_isolation_report("client-a", artifacts)

    assert report["overall_passed"] is True
    assert report["failed_object_count"] == 0
    assert report["cross_workspace_leakage_count"] == 0
    assert report["private_marker_count"] == 0


def test_workspace_isolation_hash_stable_when_generated_at_changes_and_changes_with_results():
    report = isolation.build_workspace_isolation_report("client-a", {"rows": [{"workspace_id": "client-a"}]})
    changed_time = dict(report, generated_at_utc="2099-01-01T00:00:00Z")
    changed_count = dict(report, failed_object_count=99)

    assert isolation.build_workspace_isolation_hash(report) == isolation.build_workspace_isolation_hash(changed_time)
    assert isolation.build_workspace_isolation_hash(report) != isolation.build_workspace_isolation_hash(changed_count)


def test_validate_workspace_isolation_report_blocks_overstated_pass():
    report = isolation.build_workspace_isolation_report("client-a", {"rows": [{"workspace_id": "client-b"}]})
    overstated = dict(report, overall_passed=True)
    overstated["report_hash"] = isolation.build_workspace_isolation_hash(overstated)

    result = isolation.validate_workspace_isolation_report(overstated)

    assert result["passed"] is False
    assert any("overall_passed is overstated" in error for error in result["errors"])


def test_sanitized_workspace_isolation_export_omits_raw_private_errors():
    report = isolation.build_workspace_isolation_report(
        "client-a",
        {"rows": [{"workspace_id": "client-a", "source_file": "/mnt/private.csv", "api_key": "secret"}]},
    )

    payload = json.loads(isolation.export_workspace_isolation_report_json(report, public_safe=True))
    text = json.dumps(payload).lower()

    assert "source_file" not in text
    assert "/mnt/" not in text
    assert "api_key" not in text
    assert "secret" not in text
    assert payload["private_marker_count"] >= 1
    assert payload["object_results"][0]["error_count"] >= 1


def test_workspace_isolation_service_has_no_write_or_mutation_paths():
    source = open("autonomous_betting_agent/workspace_isolation_service.py", encoding="utf-8").read()
    forbidden = (
        "approve_ledger_import",
        "preview_ledger_import",
        "append_performance_rows",
        "sync_rows_by_source",
        "update_result",
        "delete_proof",
        "write_text",
        "write_bytes",
    )
    for token in forbidden:
        assert token not in source
