from autonomous_betting_agent.reparodynamics_audit import (
    audit_event_display_rows,
    build_reparodynamics_audit_event,
    latest_reparodynamics_audit_event,
    write_reparodynamics_audit_event_from_rows,
)


def _duplicate_event_rows():
    return [
        {"sport": "Soccer", "event": "Team A vs Team B", "known_start_utc": "2026-06-27T20:00:00Z", "market": "moneyline", "result": "Won", "confidence": "0.72", "odds": "+110", "closing_odds": "+105"},
        {"sport": "Soccer", "event": "Team A vs Team B", "known_start_utc": "2026-06-27T20:00:00Z", "market": "total", "result": "Lost", "confidence": "0.61", "odds": "-105", "closing_odds": "-110"},
        {"sport": "Tennis", "event": "Player C vs Player D", "known_start_utc": "2026-06-27T21:00:00Z", "market": "moneyline", "result": "Won", "confidence": "0.68", "odds": "+120", "closing_odds": "+115"},
    ]


def test_audit_counts_rows_unique_events_and_duplicates_separately():
    event = build_reparodynamics_audit_event(
        _duplicate_event_rows(),
        source="Learning Page graded upload",
        timestamp="2026-06-27T04:39:00Z",
    )

    assert event.rows_scanned == 3
    assert event.unique_events_scanned == 2
    assert event.duplicates_detected == 1
    assert event.source == "Learning Page graded upload"
    assert event.reason == "Phase 3A observation-only"


def test_audit_log_updates_after_learning_page_ingestion(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    latest_path = tmp_path / "latest.json"

    write_reparodynamics_audit_event_from_rows(
        _duplicate_event_rows()[:1],
        source="Learning Page graded upload",
        timestamp="2026-06-27T04:39:00Z",
        log_path=log_path,
        latest_path=latest_path,
    )
    write_reparodynamics_audit_event_from_rows(
        _duplicate_event_rows(),
        source="Learning Page graded upload",
        timestamp="2026-06-27T04:40:00Z",
        log_path=log_path,
        latest_path=latest_path,
    )

    latest = latest_reparodynamics_audit_event(log_path=log_path, latest_path=latest_path)

    assert latest is not None
    assert latest.timestamp == "2026-06-27T04:40:00Z"
    assert latest.rows_scanned == 3
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 2


def test_phase_3a_activation_and_mutation_controls_stay_off():
    event = build_reparodynamics_audit_event(_duplicate_event_rows(), timestamp="2026-06-27T04:39:00Z")

    assert event.repair_activation == "OFF"
    assert event.shadow_mode == "OFF"
    assert event.tgrm_activation == "OFF"
    assert event.rye_activation == "OFF"
    assert event.live_mutation == "Forbidden"
    assert event.model_mutation == "FORBIDDEN"
    assert event.confidence_changes == "OFF"
    assert event.bet_tier_changes == "OFF"
    assert event.bankroll_changes == "OFF"
    assert event.sportsbook_changes == "OFF"


def test_display_rows_include_requested_visible_fields():
    event = build_reparodynamics_audit_event(_duplicate_event_rows(), timestamp="2026-06-27T04:39:00Z")
    fields = {row["field"] for row in audit_event_display_rows(event)}

    assert "Last Reparodynamics Run" in fields
    assert "Source" in fields
    assert "Rows scanned" in fields
    assert "Unique events scanned" in fields
    assert "Duplicates detected" in fields
    assert "New patterns detected" in fields
    assert "Drift detected" in fields
    assert "Repair candidates generated" in fields
    assert "Shadow Mode" in fields
    assert "Live Mutation" in fields
    assert "Reason" in fields
