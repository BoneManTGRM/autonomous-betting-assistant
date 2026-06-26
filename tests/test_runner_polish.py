from autonomous_betting_agent.adaptive_repair_runner import RUNNER_SCHEMA_VERSION, run_adaptive_repair_scan


def test_runner_schema_activation_gate_and_candidate_ids():
    rows = [
        {"sport": "Soccer", "event": "A vs B", "result": "Won", "market": "moneyline"},
        {"sport": "Soccer", "event": "A vs B", "result": "Lost", "market": "total"},
    ]
    first = run_adaptive_repair_scan(uploaded_rows=rows, include_system_sources=False, timestamp="2026-06-26T15:00:00Z")
    second = run_adaptive_repair_scan(uploaded_rows=rows, include_system_sources=False, timestamp="2026-06-26T15:01:00Z")

    assert first.schema_version == RUNNER_SCHEMA_VERSION
    assert first.activation_gate["gate_status"] == "CLOSED"
    assert first.activation_gate["repair_activation"] == "OFF"
    assert first.activation_gate["checks"]["live_repair_allowed"] is False
    assert first.pattern_candidates
    assert all(candidate.get("candidate_id") for candidate in first.pattern_candidates)
    assert [candidate["candidate_id"] for candidate in first.pattern_candidates] == [candidate["candidate_id"] for candidate in second.pattern_candidates]
    assert first.production_repairs_active is False
    assert first.shadow_mode_active is False
    assert first.live_pick_changes is False


def test_partial_csv_source_failure_is_reported_without_losing_good_rows(tmp_path):
    ledger_dir = tmp_path / "ledgers"
    ledger_dir.mkdir(parents=True)
    (ledger_dir / "good.csv").write_text("sport,event,result\nTennis,A vs B,Won\n", encoding="utf-8")
    (ledger_dir / "bad.csv").write_bytes(b"\xff\xfe\x00\x00")

    report = run_adaptive_repair_scan(include_system_sources=True, data_root=tmp_path, timestamp="2026-06-26T15:02:00Z")
    source = next(item for item in report.sources if item["name"] == "local_csv_ledgers")

    assert source["available"] is True
    assert source["row_count"] == 1
    assert source["loaded_files"] == 1
    assert source["failed_files"] == 1
    assert source["file_results"]
    assert "local_csv_ledgers" not in report.source_summary["failed_sources"]
    assert "local_csv_ledgers" in report.source_summary["sources_with_warnings"]
    assert report.source_summary["loaded_files"] == 1
    assert report.source_summary["failed_files"] == 1
    assert report.production_repairs_active is False
    assert report.live_pick_changes is False
