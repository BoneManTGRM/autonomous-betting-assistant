import json

from autonomous_betting_agent import proof_archive_service as archive


def test_build_proof_archive_snapshot_returns_required_public_fields():
    snapshot = archive.build_proof_archive_snapshot("test_01", "public")

    for field in (
        "schema_version",
        "archive_id",
        "archive_hash",
        "created_at_utc",
        "workspace_id",
        "package_type",
        "package_id",
        "package_hash",
        "public_export_hash",
        "qa_report_id",
        "qa_report_hash",
        "proof_ready",
        "proof_grade",
        "overall_passed",
        "archive_status",
    ):
        assert field in snapshot
    assert snapshot["package_type"] == "public"
    assert snapshot["archive_id"].startswith("archive_")
    assert snapshot["archive_hash"].startswith("archive_hash_")


def test_archive_hash_is_stable_when_only_created_at_changes():
    snapshot = archive.build_proof_archive_snapshot("test_01", "client")
    changed = dict(snapshot)
    changed["created_at_utc"] = "2099-01-01T00:00:00Z"

    assert archive.build_proof_archive_hash(snapshot) == archive.build_proof_archive_hash(changed)


def test_archive_hash_changes_when_package_or_qa_hash_changes():
    snapshot = archive.build_proof_archive_snapshot("test_01", "client")
    changed_package = dict(snapshot, package_hash="package_hash_changed")
    changed_qa = dict(snapshot, qa_report_hash="qa_hash_changed")

    assert archive.build_proof_archive_hash(snapshot) != archive.build_proof_archive_hash(changed_package)
    assert archive.build_proof_archive_hash(snapshot) != archive.build_proof_archive_hash(changed_qa)


def test_validate_public_client_snapshot_blocks_private_terms_and_private_hash():
    snapshot = archive.build_proof_archive_snapshot("test_01", "public")
    assert archive.validate_proof_archive_snapshot(snapshot)["passed"], archive.validate_proof_archive_snapshot(snapshot)["errors"]

    unsafe = dict(snapshot)
    unsafe["source_file"] = "/home/private/audit.csv"
    unsafe["private_export_hash"] = "export_hash_secret"
    result = archive.validate_proof_archive_snapshot(unsafe)

    assert result["passed"] is False
    joined = "\n".join(result["errors"])
    assert "blocked private terms" in joined or "private_export_hash" in joined


def test_private_internal_snapshot_includes_private_export_hash_and_validates():
    for package_type in ("private", "internal_review"):
        snapshot = archive.build_proof_archive_snapshot("test_01", package_type)
        assert snapshot["is_private_internal"] is True
        assert snapshot["private_export_hash"].startswith("export_hash_")
        result = archive.validate_proof_archive_snapshot(snapshot)
        assert result["passed"], result["errors"]


def test_public_json_export_is_sanitized_for_public_client_packages():
    snapshot = archive.build_proof_archive_snapshot("test_01", "client")
    unsafe = dict(snapshot)
    unsafe["private_export_hash"] = "export_hash_should_not_export"
    unsafe["source_file"] = "/mnt/private/file.csv"

    payload = json.loads(archive.export_proof_archive_snapshot_json(unsafe, public_safe=True))

    assert "private_export_hash" not in payload
    assert "source_file" not in payload
    assert "/mnt/" not in json.dumps(payload).lower()


def test_archive_index_covers_all_package_types_and_has_index_hash():
    index = archive.build_proof_archive_index("test_01")

    assert index["snapshot_count"] == 4
    assert index["archive_index_hash"].startswith("archive_index_hash_")
    assert {snapshot["package_type"] for snapshot in index["snapshots"]} == {"public", "client", "private", "internal_review"}
    assert len(index["archive_hashes"]) == 4
    assert len(index["package_hashes"]) == 4
    assert len(index["qa_report_hashes"]) == 4


def test_compare_proof_archive_snapshots_reports_version_changes():
    left = archive.build_proof_archive_snapshot("test_01", "public")
    right = dict(left)
    right["package_hash"] = "package_hash_changed"
    right["archive_hash"] = archive.build_proof_archive_hash(right)

    comparison = archive.compare_proof_archive_snapshots(left, right)

    assert comparison["same_archive_hash"] is False
    assert comparison["same_package_hash"] is False
    assert "package_hash" in comparison["changed_fields"]


def test_unsupported_package_type_fails_closed():
    snapshot = archive.build_proof_archive_snapshot("test_01", "bad")
    result = archive.validate_proof_archive_snapshot(snapshot)

    assert snapshot["overall_passed"] is False
    assert result["passed"] is False
    assert any("Unsupported package_type" in error for error in result["errors"])


def test_archive_service_has_no_write_or_mutation_paths():
    source = open("autonomous_betting_agent/proof_archive_service.py", encoding="utf-8").read()
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
