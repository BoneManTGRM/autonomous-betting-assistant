import json

from autonomous_betting_agent import local_review_checklist as review
from autonomous_betting_agent import dashboard_refresh_package as dash


def _proof_rows():
    return [
        {"proof_id": "p1", "event_id": "e1", "event": "A vs B", "selection": "A", "decimal_odds": "2.00", "model_probability": "60%", "result": "win", "sport": "tennis", "league": "atp"},
        {"proof_id": "p2", "event_id": "e1", "event": "A vs B", "selection": "B", "decimal_odds": "1.90", "model_probability": "45%", "result": "loss", "sport": "tennis", "league": "atp"},
    ]


def _decision_rows():
    return [
        {"row_id": "p1", "row_index": 0, "final_action": "PLAYABLE VALUE", "final_blockers": [], "baseline_EV": "0.10", "calibrated_EV": "0.20"},
        {"row_id": "p2", "row_index": 1, "final_action": "NO BET", "final_blockers": ["calibrated_ev_below_buffer"], "baseline_EV": "-0.05", "calibrated_EV": "-0.10"},
    ]


def test_parse_json_object_handles_good_and_bad_json():
    assert review.parse_json_object('{"a": 1}')["a"] == 1
    assert review.parse_json_object("not json")["parse_error"] == "invalid_json"


def test_required_field_checks_pass_for_complete_rows():
    checks = review.required_field_checks(_proof_rows())

    assert checks
    assert all(row["status"] == "PASS" for row in checks)


def test_required_field_checks_fails_missing_price():
    rows = [{"event": "A", "selection": "A", "model_probability": "60%", "result": "win"}]
    checks = review.required_field_checks(rows)
    price = [row for row in checks if row["check_id"] == "field_decimal_odds"][0]

    assert price["status"] == "FAIL"
    assert price["required"] is True


def test_dashboard_checks_detect_dashboard_status_and_safety():
    dashboard = dash.build_dashboard_refresh_package("test_01", _proof_rows(), _proof_rows(), _decision_rows())
    checks = review.dashboard_checks(dashboard)

    assert any(row["check_id"] == "dashboard_rows" and row["status"] == "PASS" for row in checks)
    assert any(row["check_id"] == "safe_gates" and row["status"] == "PASS" for row in checks)


def test_decision_checks_count_playable_rows():
    checks = review.decision_checks({}, _decision_rows())

    assert any(row["check_id"] == "decision_rows" and row["status"] == "PASS" for row in checks)
    assert any(row["check_id"] == "playable_review" and row["status"] == "PASS" for row in checks)


def test_ack_checks_warn_until_confirmed():
    checks = review.ack_checks({})

    assert all(row["status"] == "WARN" for row in checks)


def test_summarize_checklist_blocks_required_failures():
    summary = review.summarize_checklist([
        {"status": "PASS", "required": True},
        {"status": "FAIL", "required": True},
        {"status": "WARN", "required": False},
    ])

    assert summary["readiness_status"] == "BLOCKED"
    assert summary["required_failure_count"] == 1


def test_build_local_review_checklist_from_text_exports():
    proof_csv = review.csv_from_rows(_proof_rows())
    decision_csv = review.csv_from_rows(_decision_rows())
    ack_json = '{"inputs_reviewed": true, "duplicates_reviewed": true, "blockers_reviewed": true, "exports_downloaded": true}'
    report = review.build_local_review_checklist_from_text("test_01", proof_csv, proof_csv, decision_csv, "", "", ack_json)
    payload = json.loads(review.export_local_review_json(report))

    assert payload["schema_version"] == "local_review_checklist_v1"
    assert payload["proof_row_count"] == 2
    assert payload["decision_row_count"] == 2
    assert payload["preview_only"] is True
    assert payload["files_written"] == 0
    assert payload["live_changes"] == 0
    assert "check_id" in review.export_local_review_checklist_csv(report)
    assert "next_action" in review.export_local_review_next_actions_csv(report)
    assert "local_review_hash" in review.export_local_review_manifest_json(report)


def test_local_review_has_no_external_client_paths():
    source = open("autonomous_betting_agent/local_review_checklist.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
