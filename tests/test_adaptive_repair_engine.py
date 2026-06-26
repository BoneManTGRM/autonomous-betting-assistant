from autonomous_betting_agent.adaptive_repair_diagnostics import build_enhanced_diagnostics, diagnostics_to_markdown
from autonomous_betting_agent.adaptive_repair_engine import build_simulation_report, normalize_result_status, status_from_row


def test_result_status_preserves_void_and_unknown():
    assert normalize_result_status("Won") == "win"
    assert normalize_result_status("lost") == "loss"
    assert normalize_result_status("push") == "push"
    assert normalize_result_status("void") == "void"
    assert normalize_result_status("unknown") == "unknown"
    assert normalize_result_status("") == "pending"


def test_status_from_row_handles_case_insensitive_result_columns():
    assert status_from_row({"Result": "Won"}) == "win"
    assert status_from_row({"FINAL_RESULT": "Lost"}) == "loss"
    assert status_from_row({"result_status": "Void"}) == "void"


def test_uploaded_tracker_baseline_shape_counts():
    rows = []
    for index in range(55):
        rows.append({"sport": "Tennis", "event": f"event win {index}", "known_start_utc": f"2026-06-{index % 25 + 1:02d}", "result": "Won"})
    for index in range(20):
        rows.append({"sport": "Tennis", "event": f"event loss {index}", "known_start_utc": f"2026-06-{index % 25 + 1:02d}", "result": "Lost"})
    for index in range(4):
        rows.append({"sport": "Tennis", "event": f"event unknown {index}", "known_start_utc": f"2026-06-{index + 1:02d}", "result": "Unknown"})
    for index in range(2):
        rows.append({"sport": "Tennis", "event": f"event void {index}", "known_start_utc": f"2026-06-{index + 1:02d}", "result": "Void"})

    report = build_simulation_report(rows, dataset_name="synthetic_tracker")

    assert report.total_rows == 81
    assert report.row_level["completed"] == 75
    assert report.row_level["wins"] == 55
    assert report.row_level["losses"] == 20
    assert report.row_level["unknown"] == 4
    assert report.row_level["voids"] == 2
    assert report.duplicate_event_names == 0
    assert report.unique_event_level["unique_events"] == 81
    assert report.unique_event_level["mixed_events"] == 0
    assert round(report.row_level["win_rate"], 4) == 0.7333


def test_row_level_and_unique_event_tracking_split_duplicates():
    rows = [
        {"sport": "Soccer", "event": "Team A vs Team B", "known_start_utc": "2026-06-20", "result": "Won", "market": "moneyline"},
        {"sport": "Soccer", "event": "Team A vs Team B", "known_start_utc": "2026-06-20", "result": "Lost", "market": "total"},
        {"sport": "Tennis", "event": "Player C vs Player D", "known_start_utc": "2026-06-21", "result": "Void"},
    ]

    report = build_simulation_report(rows, dataset_name="duplicates")
    diagnostics = build_enhanced_diagnostics(rows, dataset_name="duplicates")
    markdown = diagnostics_to_markdown(diagnostics)

    assert report.row_level["rows"] == 3
    assert report.row_level["wins"] == 1
    assert report.row_level["losses"] == 1
    assert report.row_level["voids"] == 1
    assert report.duplicate_event_names == 1
    assert report.unique_event_level["unique_events"] == 2
    assert report.unique_event_level["wins"] == 0
    assert report.unique_event_level["losses"] == 0
    assert report.unique_event_level["mixed_events"] == 1
    assert report.unique_event_level["voids"] == 1
    assert diagnostics.same_event_groups[0]["mixed_outcome"] is True
    assert diagnostics.same_event_groups[0]["multi_market"] is True
    assert diagnostics.mixed_outcome_events == 1
    assert diagnostics.multi_market_events == 1
    assert any("mixed-outcome unique event" in penalty for penalty in diagnostics.data_quality["penalties"])
    assert "Mixed unique events: 1" in markdown
    assert "Mixed-outcome unique events: 1" in markdown
    assert "Multi-market unique events: 1" in markdown


def test_candidate_watchlists_do_not_activate_repairs():
    rows = [
        {"sport": "FIFA World Cup", "event": "A vs B", "known_start_utc": "2026-06-20", "result": "Lost", "result_note": "Finished in a 1-1 draw"},
        {"sport": "FIFA World Cup", "event": "C vs D", "known_start_utc": "2026-06-21", "result": "Won"},
        {"sport": "UFC", "event": "Fighter A vs Fighter B", "known_start_utc": "2026-06-22", "prop_type": "round/method", "result": "Lost"},
        {"sport": "Tennis", "event": "Player A vs Player B", "known_start_utc": "2026-06-23", "prop_type": "estimated_score", "result": "Won"},
    ]

    report = build_simulation_report(rows, dataset_name="watchlists")
    diagnostics = build_enhanced_diagnostics(rows, dataset_name="watchlists")

    assert report.production_repairs_active is False
    assert report.accepted_simulated_repairs == []
    assert diagnostics.production_repairs_active is False
    assert any(pattern["status"] == "watchlist" for pattern in report.watchlist_patterns)


def test_enhanced_data_quality_and_column_coverage_report_missing_fields():
    rows = [
        {"sport": "Tennis", "event": "A vs B", "result": "Won", "odds": "+120"},
        {"sport": "Tennis", "event": "A vs B", "result": "Won", "odds": "+120"},
        {"sport": "", "event": "", "result": "Unknown"},
    ]

    diagnostics = build_enhanced_diagnostics(rows, dataset_name="quality")

    assert diagnostics.duplicate_rows == 1
    assert diagnostics.column_coverage["odds"]["matched_column"] == "odds"
    assert diagnostics.column_coverage["closing_odds"]["matched_column"] is None
    assert diagnostics.data_quality["score"] < 100
    assert diagnostics.data_quality["repairs_allowed"] is False
    assert diagnostics.missing_required_field_examples
