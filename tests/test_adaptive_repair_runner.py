from pathlib import Path

from autonomous_betting_agent.adaptive_repair_runner import (
    _scan_source,
    column_mapping_preview,
    create_run_id,
    list_recent_simulation_runs,
    rows_from_csv_bytes,
    run_adaptive_repair_scan,
    runner_report_to_markdown,
    save_runner_report,
)


def _tracker_rows():
    rows = []
    for index in range(55):
        rows.append({"sport": "Tennis", "event": f"event win {index}", "known_start_utc": f"2026-06-{index % 25 + 1:02d}", "result": "Won"})
    for index in range(20):
        rows.append({"sport": "Tennis", "event": f"event loss {index}", "known_start_utc": f"2026-06-{index % 25 + 1:02d}", "result": "Lost"})
    for index in range(4):
        rows.append({"sport": "Tennis", "event": f"event unknown {index}", "known_start_utc": f"2026-06-{index + 1:02d}", "result": "Unknown"})
    for index in range(2):
        rows.append({"sport": "Tennis", "event": f"event void {index}", "known_start_utc": f"2026-06-{index + 1:02d}", "result": "Void"})
    return rows


def test_runner_scans_uploaded_rows_and_preserves_tracker_baseline(tmp_path):
    report = run_adaptive_repair_scan(
        uploaded_rows=_tracker_rows(),
        uploaded_filename="zero_tracker.csv",
        uploaded_bytes=b"tracker-bytes",
        include_system_sources=False,
        timestamp="2026-06-26T13:30:00Z",
    )

    base = report.diagnostics["base_report"]
    row = base["row_level"]
    event = base["unique_event_level"]

    assert base["total_rows"] == 81
    assert row["completed"] == 75
    assert row["wins"] == 55
    assert row["losses"] == 20
    assert row["unknown"] == 4
    assert row["voids"] == 2
    assert round(row["win_rate"], 4) == 0.7333
    assert event["unique_events"] == 81
    assert event["mixed_events"] == 0
    assert report.production_repairs_active is False
    assert report.shadow_mode_active is False
    assert report.live_pick_changes is False
    assert report.safety_state["Repair Mode"] == "OFF"
    assert report.readiness["RYE_activation"] is False
    assert report.readiness["Shadow_Mode_activation"] is False


def test_runner_handles_missing_system_sources_safely(tmp_path):
    report = run_adaptive_repair_scan(include_system_sources=True, data_root=tmp_path / "missing", timestamp="2026-06-26T13:31:00Z")

    assert report.source_summary["sources_scanned"] >= 1
    assert report.source_summary["failed_sources"] == []
    assert report.production_repairs_active is False
    assert report.live_pick_changes is False


def test_failed_source_is_isolated_and_recorded():
    def broken_loader():
        raise RuntimeError("boom secret=abc123456789")

    failed = _scan_source("broken_source", broken_loader, source_path="broken/path")

    assert failed.available is False
    assert failed.rows == []
    assert "RuntimeError" in failed.error
    assert "abc123456789" not in failed.summary()["error"]


def test_bad_csv_in_system_source_is_reported_not_silently_ignored(tmp_path):
    ledger_dir = tmp_path / "ledgers"
    ledger_dir.mkdir(parents=True)
    (ledger_dir / "bad.csv").write_bytes(b"\xff\xfe\x00\x00")

    report = run_adaptive_repair_scan(include_system_sources=True, data_root=tmp_path, timestamp="2026-06-26T13:31:30Z")

    assert "local_csv_ledgers" in report.source_summary["failed_sources"]
    ledger_source = next(source for source in report.sources if source["name"] == "local_csv_ledgers")
    assert ledger_source["available"] is False
    assert ledger_source["error"]
    assert report.production_repairs_active is False
    assert report.live_pick_changes is False


def test_runner_markdown_json_exports_and_recent_listing(tmp_path):
    report = run_adaptive_repair_scan(
        uploaded_rows=_tracker_rows()[:3],
        uploaded_filename="mini.csv",
        uploaded_bytes=b"mini",
        include_system_sources=False,
        timestamp="2026-06-26T13:32:00Z",
    )
    markdown = runner_report_to_markdown(report)
    json_text = report.to_json()

    assert "ABA Adaptive Repair Runner Scan" in markdown
    assert "Repair Mode: OFF" in markdown
    assert "production_repairs_active" in json_text
    assert "false" in json_text.lower()

    saved = save_runner_report(report, output_dir=tmp_path / "simulation_runs")
    assert Path(saved["json_path"]).exists()
    assert Path(saved["markdown_path"]).exists()
    recent = list_recent_simulation_runs(output_dir=tmp_path / "simulation_runs")
    assert len(recent) == 1
    assert recent[0]["run_id"] == report.run_id


def test_runner_csv_bytes_hash_mapping_and_secret_redaction():
    csv_bytes = b"Sport,Event,Result,Odds,Confidence,Notes\nTennis,A vs B,Won,+120,0.62,api_key=SECRET1234567890\n"
    rows = rows_from_csv_bytes(csv_bytes)
    report = run_adaptive_repair_scan(
        uploaded_rows=rows,
        uploaded_filename="secret.csv",
        uploaded_bytes=csv_bytes,
        include_system_sources=False,
        timestamp="2026-06-26T13:33:00Z",
    )

    mapping = column_mapping_preview(rows)
    assert mapping["result"] == "result"
    assert mapping["odds"] == "odds"
    assert mapping["confidence"] == "confidence"
    assert report.sources[0]["source_hash"]
    assert "SECRET1234567890" not in report.to_json()
    assert "api_key=" not in report.to_json()


def test_runner_reports_missing_market_data_and_watchlists_remain_inactive():
    rows = [
        {"sport": "Soccer", "event": "Team A vs Team B", "known_start_utc": "2026-06-20", "result": "Won", "market": "moneyline"},
        {"sport": "Soccer", "event": "Team A vs Team B", "known_start_utc": "2026-06-20", "result": "Lost", "market": "total"},
    ]
    report = run_adaptive_repair_scan(uploaded_rows=rows, include_system_sources=False, timestamp="2026-06-26T13:34:00Z")

    assert any("ROI simulation limited" in item for item in report.unavailable_data)
    assert any("CLV simulation unavailable" in item for item in report.unavailable_data)
    assert any("confidence calibration unavailable" in item for item in report.unavailable_data)
    assert report.diagnostics["mixed_outcome_events"] == 1
    assert any("mixed-outcome unique event" in item for item in report.diagnostics["data_quality"]["penalties"])
    assert report.pattern_candidates
    assert all(candidate["status"] == "watchlist" for candidate in report.pattern_candidates)
    assert all(candidate["repair_allowed"] is False for candidate in report.pattern_candidates)


def test_runner_deterministic_run_id_helper():
    first = create_run_id(timestamp="2026-06-26T13:35:00Z", source_hash="abc", total_rows=10, source_count=1)
    second = create_run_id(timestamp="2026-06-26T13:35:00Z", source_hash="abc", total_rows=10, source_count=1)
    assert first == second
    assert len(first) == 20
