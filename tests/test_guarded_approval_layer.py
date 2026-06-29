import json

from autonomous_betting_agent import guarded_approval_layer as approval


def _base():
    return [
        {
            "proof_id": "p1",
            "event": "A vs B",
            "selection": "A",
            "status": "pending",
        }
    ]


def _candidate():
    return [
        {
            "proof_id": "p1",
            "event": "A vs B",
            "selection": "A",
            "status": "complete",
            "verification_status": "ready_for_manual_import",
            "confirmation_value": "2-0",
        }
    ]


def _manifest(**overrides):
    base = {
        "manual_review_count": 0,
        "review_lane_count": 0,
        "quarantine_lane_count": 0,
    }
    base.update(overrides)
    return base


def test_parse_and_csv_helpers():
    rows = approval.parse_csv_text("proof_id,event\np1,A vs B\n")
    csv_text = approval.csv_from_rows(rows)

    assert rows[0]["proof_id"] == "p1"
    assert "proof_id" in csv_text


def test_compare_csv_rows_finds_changed_fields():
    diffs = approval.compare_csv_rows(_base(), _candidate())

    assert len(diffs) == 1
    assert diffs[0]["row_key"] == "p1"
    assert "status" in diffs[0]["changes"]


def test_validate_approval_inputs_blocks_missing_phrase():
    errors = approval.validate_approval_inputs(_manifest(), _base(), _candidate(), "wrong", "Cody")

    assert "approval phrase mismatch" in errors


def test_validate_approval_inputs_blocks_review_counts():
    errors = approval.validate_approval_inputs(_manifest(manual_review_count=1), _base(), _candidate(), "APPROVE VERIFIED ROWS", "Cody")

    assert "blocked by manual_review_count" in errors


def test_build_guarded_approval_package_approves_when_clean():
    package = approval.build_guarded_approval_package(
        "test_01",
        _base(),
        _candidate(),
        _manifest(),
        "APPROVE VERIFIED ROWS",
        "Cody",
        "manual approval test",
    )

    assert package["schema_version"] == "guarded_approval_layer_v1"
    assert package["status"] == "APPROVED PACKAGE"
    assert package["changed_row_count"] == 1
    assert package["blocked_reason_count"] == 0
    assert package["approval_phrase_matched"] is True
    assert package["preview_only"] is True
    assert package["files_written"] == 0
    assert package["live_changes"] == 0
    assert package["approved_csv"]
    assert package["rollback_csv"]
    assert package["approval_hash"].startswith("approval_hash_")


def test_build_guarded_approval_package_blocks_when_not_clean():
    package = approval.build_guarded_approval_package("test_01", _base(), _candidate(), _manifest(review_lane_count=2), "APPROVE VERIFIED ROWS", "Cody")

    assert package["status"] == "APPROVAL BLOCKED"
    assert package["approved_csv"] == ""
    assert package["errors"]


def test_build_guarded_approval_package_from_text_round_trips():
    base_csv = "proof_id,event,selection,status\np1,A vs B,A,pending\n"
    candidate_csv = "proof_id,event,selection,status,confirmation_value\np1,A vs B,A,complete,2-0\n"
    package = approval.build_guarded_approval_package_from_text(
        "test_01",
        base_csv,
        candidate_csv,
        json.dumps(_manifest()),
        "APPROVE VERIFIED ROWS",
        "Cody",
        "ok",
    )

    assert package["status"] == "APPROVED PACKAGE"
    assert "2-0" in package["approved_csv"]


def test_export_approval_manifest_excludes_large_csv_blocks():
    package = approval.build_guarded_approval_package("test_01", _base(), _candidate(), _manifest(), "APPROVE VERIFIED ROWS", "Cody")
    manifest = json.loads(approval.export_approval_manifest_json(package))

    assert "backup_csv" not in manifest
    assert "approved_csv" not in manifest
    assert "rollback_csv" not in manifest
    assert manifest["status"] == "APPROVED PACKAGE"


def test_guarded_approval_layer_has_no_external_client_paths():
    source = open("autonomous_betting_agent/guarded_approval_layer.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
