import json

from autonomous_betting_agent import data_reconciliation_preview_service as svc


def _row(event="A vs B", market="moneyline"):
    return {
        "proof_id": "p1",
        "sport": "tennis",
        "event": event,
        "event_start_utc": "2026-06-29T20:00:00Z",
        "selection": "A",
        "market_type": market,
    }


def test_row_key_is_stable_across_payload_types():
    base = _row()
    confirmation = {"sport": "tennis", "event": "A vs B", "event_start_utc": "2026-06-29T20:00:00Z"}

    assert svc.row_key(base) == svc.row_key(confirmation)


def test_normalize_confirmation_captures_source_value_and_confidence():
    confirmation = svc.normalize_confirmation({
        "sport": "tennis",
        "event": "A vs B",
        "event_start_utc": "2026-06-29T20:00:00Z",
        "source": "provider_a",
        "primary_value": 2,
        "secondary_value": 0,
        "confidence": 0.95,
    })

    assert confirmation["source"] == "provider_a"
    assert confirmation["confirmation_value"] == "2-0"
    assert confirmation["confidence"] == 0.95
    assert confirmation["has_confirmation"] is True


def test_normalize_value_snapshot_calculates_delta_percent():
    snapshot = svc.normalize_value_snapshot({
        "sport": "tennis",
        "event": "A vs B",
        "event_start_utc": "2026-06-29T20:00:00Z",
        "source": "provider_b",
        "original_value": 2.0,
        "latest_value": 1.9,
    })

    assert snapshot["source"] == "provider_b"
    assert snapshot["delta"] == -0.1
    assert snapshot["delta_percent"] == -0.05
    assert snapshot["has_latest_value"] is True


def test_report_reconciles_when_confirmation_and_value_exist():
    row = _row()
    confirmation = {**row, "source": "provider_a", "primary_value": 2, "secondary_value": 0, "confidence": 0.99}
    value = {**row, "source": "provider_b", "original_value": 2.0, "latest_value": 1.9}

    report = svc.build_data_reconciliation_report("test_01", [row], [confirmation], [value])

    assert report["overall_passed"] is True
    assert report["reconciled_count"] == 1
    assert report["review_count"] == 0
    result = report["reconciliation_rows"][0]
    assert result["status"] == "RECONCILED"
    assert result["confirmation_source"] == "provider_a"
    assert result["confirmation_value"] == "2-0"
    assert result["value_source"] == "provider_b"
    assert result["frozen_selection_logic"] is True


def test_missing_confirmation_requires_review():
    report = svc.build_data_reconciliation_report("test_01", [_row()], [], [])

    assert report["overall_passed"] is False
    assert report["review_count"] == 1
    assert report["reconciliation_rows"][0]["status"] == "MISSING CONFIRMATION"


def test_low_confidence_and_unsupported_market_require_review():
    row = _row(market="custom_market")
    confirmation = {**row, "primary_value": 1, "secondary_value": 0, "confidence": 0.5}
    report = svc.build_data_reconciliation_report("test_01", [row], [confirmation], [])

    assert report["overall_passed"] is False
    result = report["reconciliation_rows"][0]
    assert result["review_required"] is True
    assert result["review_reason_count"] >= 2


def test_unique_events_and_duplicate_rows_are_separated():
    row1 = _row()
    row2 = {**_row(), "proof_id": "p2", "market_type": "spread"}
    confirmation = {**row1, "primary_value": 2, "secondary_value": 0}
    report = svc.build_data_reconciliation_report("test_01", [row1, row2], [confirmation], [])

    assert report["row_count"] == 2
    assert report["unique_events"] == 1
    assert report["duplicate_row_count"] == 1


def test_report_hash_stable_when_generated_at_changes():
    report = svc.build_data_reconciliation_report("test_01", [_row()], [], [])
    changed_time = dict(report, generated_at_utc="2099-01-01T00:00:00Z")
    changed_count = dict(report, review_count=99)

    assert svc.build_data_reconciliation_hash(report) == svc.build_data_reconciliation_hash(changed_time)
    assert svc.build_data_reconciliation_hash(report) != svc.build_data_reconciliation_hash(changed_count)


def test_validate_report_blocks_overstated_pass_and_unfrozen_logic():
    report = svc.build_data_reconciliation_report("test_01", [_row()], [], [])
    overstated = dict(report, overall_passed=True)
    overstated["report_hash"] = svc.build_data_reconciliation_hash(overstated)
    unfrozen = dict(report, frozen_selection_logic=False)
    unfrozen["report_hash"] = svc.build_data_reconciliation_hash(unfrozen)

    assert svc.validate_data_reconciliation_report(overstated)["passed"] is False
    assert svc.validate_data_reconciliation_report(unfrozen)["passed"] is False


def test_sanitized_export_omits_raw_warnings_and_errors():
    report = svc.build_data_reconciliation_report("test_01", [_row()], [], [])
    payload = json.loads(svc.export_data_reconciliation_report_json(report, public_safe=True))

    assert "errors" not in payload
    assert "warnings" not in payload
    assert payload["review_count"] == 1
    assert payload["reconciliation_rows"][0]["confirmation_source"] == ""


def test_service_has_no_network_write_or_mutation_paths():
    source = open("autonomous_betting_agent/data_reconciliation_preview_service.py", encoding="utf-8").read()
    forbidden = (
        "requests.",
        "httpx.",
        "urllib.",
        "approve_ledger_import",
        "append_performance_rows",
        "sync_rows_by_source",
        "update_result",
        "delete_proof",
        "write_text",
        "write_bytes",
    )
    for token in forbidden:
        assert token not in source
