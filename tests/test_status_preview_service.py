import json

from autonomous_betting_agent import status_preview_service as svc


def _record(name="A", category="group"):
    return {"record_id": "r1", "category": category, "name": name, "time": "2026-06-29T20:00:00Z"}


def test_record_key_is_stable_across_payloads():
    assert svc.record_key(_record()) == svc.record_key({"category": "group", "name": "A", "time": "2026-06-29T20:00:00Z"})


def test_marker_and_snapshot_normalization():
    marker = svc.normalize_marker({**_record(), "source": "source_a", "primary": 2, "secondary": 0, "confidence": 0.9})
    snapshot = svc.normalize_snapshot({**_record(), "source": "source_b", "start_value": 2.0, "latest_value": 1.9})
    assert marker["marker"] == "2-0"
    assert marker["confidence"] == 0.9
    assert marker["has_marker"] is True
    assert snapshot["delta"] == -0.1
    assert snapshot["delta_ratio"] == -0.05


def test_report_ready_when_marker_and_snapshot_exist():
    record = _record()
    marker = {**record, "primary": 2, "secondary": 0, "confidence": 0.95}
    snapshot = {**record, "start_value": 2.0, "latest_value": 1.9}
    report = svc.build_status_preview_report("test_01", [record], [marker], [snapshot])
    assert report["overall_passed"] is True
    assert report["ready_count"] == 1
    assert report["review_count"] == 0
    assert report["status_rows"][0]["status"] == "READY"
    assert report["status_rows"][0]["locked_logic"] is True


def test_missing_marker_requires_review():
    report = svc.build_status_preview_report("test_01", [_record()], [], [])
    assert report["overall_passed"] is False
    assert report["review_count"] == 1
    assert report["status_rows"][0]["status"] == "MISSING"


def test_low_confidence_requires_review():
    record = _record()
    marker = {**record, "primary": 1, "secondary": 0, "confidence": 0.5}
    report = svc.build_status_preview_report("test_01", [record], [marker], [])
    assert report["overall_passed"] is False
    assert report["status_rows"][0]["review_required"] is True
    assert report["status_rows"][0]["reason_count"] >= 2


def test_unique_records_and_duplicates_are_separated():
    record_1 = _record()
    record_2 = {**_record(), "record_id": "r2"}
    report = svc.build_status_preview_report("test_01", [record_1, record_2], [], [])
    assert report["record_count"] == 2
    assert report["unique_records"] == 1
    assert report["duplicate_record_count"] == 1


def test_hash_stable_when_generated_at_changes():
    report = svc.build_status_preview_report("test_01", [_record()], [], [])
    changed_time = dict(report, generated_at_utc="2099-01-01T00:00:00Z")
    changed_count = dict(report, review_count=99)
    assert svc.build_status_preview_hash(report) == svc.build_status_preview_hash(changed_time)
    assert svc.build_status_preview_hash(report) != svc.build_status_preview_hash(changed_count)


def test_validate_blocks_overstated_pass_and_unlocked_logic():
    report = svc.build_status_preview_report("test_01", [_record()], [], [])
    overstated = dict(report, overall_passed=True)
    overstated["report_hash"] = svc.build_status_preview_hash(overstated)
    unlocked = dict(report, locked_logic=False)
    unlocked["report_hash"] = svc.build_status_preview_hash(unlocked)
    assert svc.validate_status_preview_report(overstated)["passed"] is False
    assert svc.validate_status_preview_report(unlocked)["passed"] is False


def test_sanitized_export_omits_raw_warnings_and_errors():
    report = svc.build_status_preview_report("test_01", [_record()], [], [])
    payload = json.loads(svc.export_status_preview_report_json(report, public_safe=True))
    assert "errors" not in payload
    assert "warnings" not in payload
    assert payload["review_count"] == 1


def test_service_has_no_network_write_or_mutation_paths():
    source = open("autonomous_betting_agent/status_preview_service.py", encoding="utf-8").read()
    for token in ("requests.", "httpx.", "urllib.", "approve_ledger_import", "append_performance_rows", "sync_rows_by_source", "update_result", "delete_proof", "write_text", "write_bytes"):
        assert token not in source
