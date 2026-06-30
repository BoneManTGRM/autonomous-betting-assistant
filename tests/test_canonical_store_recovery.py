import json

from autonomous_betting_agent import canonical_store_recovery as recovery


def _rows():
    return [
        {"proof_id": "p1", "workspace_id": "test_01", "event": "A vs B", "event_id": "e1", "selection": "A", "result": "win"},
        {"proof_id": "p2", "workspace_id": "test_01", "event": "C vs D", "event_id": "e2", "selection": "C", "result": "loss"},
    ]


def _handoff_rows():
    return [
        {"page": "Pro Predictor", "role": "predictor", "source": "canonical store", "mode": "read only"},
        {"page": "Odds Lock Pro", "role": "odds_lock", "source": "canonical store", "mode": "read only"},
        {"page": "Public Proof Dashboard", "role": "dashboard", "source": "canonical store", "mode": "read only"},
        {"page": "Learning", "role": "learning", "source": "canonical store", "mode": "read only"},
    ]


def test_resolve_canonical_store_prefers_canonical_rows():
    resolved = recovery.resolve_canonical_store({"canonical_store": _rows(), "disk_fallback": _rows()[:1]})

    assert resolved["resolved_store_name"] == "canonical_store"
    assert resolved["resolution_status"] == "CANONICAL"
    assert resolved["resolved_row_count"] == 2
    assert resolved["recovered_from_fallback"] is False


def test_resolve_canonical_store_recovers_from_disk_when_session_empty():
    resolved = recovery.resolve_canonical_store({"session_state": [], "disk_fallback": _rows()})

    assert resolved["resolved_store_name"] == "disk_fallback"
    assert resolved["resolution_status"] == "RECOVERED"
    assert resolved["resolved_row_count"] == 2
    assert resolved["recovered_from_fallback"] is True


def test_save_reload_verification_passes_for_exact_round_trip():
    result = recovery.save_reload_verification(_rows(), _rows())

    assert result["verification_status"] == "PASS"
    assert result["row_count_match"] is True
    assert result["fingerprint_match"] is True


def test_save_reload_verification_fails_for_row_loss():
    result = recovery.save_reload_verification(_rows(), _rows()[:1])

    assert result["verification_status"] == "FAIL"
    assert result["row_count_match"] is False


def test_dedupe_by_proof_id_removes_later_duplicate():
    rows = _rows() + [{"proof_id": "p1", "event": "A vs B", "selection": "duplicate", "result": "loss"}]
    result = recovery.dedupe_by_proof_id(rows)

    assert result["duplicate_count"] == 1
    assert len(result["rows"]) == 2
    assert result["duplicates"][0]["proof_id"] == "p1"


def test_workspace_mismatches_are_reported():
    rows = _rows() + [{"proof_id": "p3", "workspace_id": "other", "event": "E vs F", "selection": "E", "result": "win"}]
    mismatches = recovery.workspace_mismatches(rows, "test_01")

    assert len(mismatches) == 1
    assert mismatches[0]["row_workspace_id"] == "other"


def test_required_column_report_warns_missing_columns():
    report = recovery.required_column_report([{"event": "A vs B"}])

    assert "proof_id" in report["missing_minimum_columns"]
    assert "selection" in report["missing_minimum_columns"]
    assert report["missing_result_column"] is True


def test_build_canonical_store_recovery_report_from_text_exports():
    rows_csv = recovery.csv_from_rows(_rows())
    handoff_csv = recovery.csv_from_rows(_handoff_rows())
    report = recovery.build_canonical_store_recovery_report_from_text(
        "test_01",
        "",
        "",
        rows_csv,
        "",
        "",
        "",
        "",
        "",
        rows_csv,
        handoff_csv,
        '{"operator": "local"}',
    )
    payload = json.loads(recovery.export_canonical_recovery_json(report))

    assert payload["schema_version"] == "canonical_store_recovery_v1"
    assert payload["resolved_store_name"] == "disk_fallback"
    assert payload["resolution_status"] == "RECOVERED"
    assert payload["resolved_row_count"] == 2
    assert payload["preview_only"] is True
    assert payload["files_written"] == 0
    assert payload["live_changes"] == 0
    assert "check_id" in recovery.export_canonical_recovery_checks_csv(report)
    assert "store_name" in recovery.export_canonical_recovery_store_summaries_csv(report)
    assert "proof_id" in recovery.export_canonical_recovery_rows_csv(report)
    assert "recovery_hash" in recovery.export_canonical_recovery_manifest_json(report)


def test_build_canonical_store_recovery_report_blocks_when_reload_mismatch():
    report = recovery.build_canonical_store_recovery_report(
        "test_01",
        canonical_rows=_rows(),
        reloaded_rows=_rows()[:1],
        handoff_inventory_rows=_handoff_rows(),
    )

    assert report["recovery_status"] == "BLOCKED"
    assert any(row["check_id"] == "save_reload_row_count" and row["status"] == "FAIL" for row in report["recovery_checks"])


def test_canonical_recovery_has_no_external_client_paths():
    source = open("autonomous_betting_agent/canonical_store_recovery.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
