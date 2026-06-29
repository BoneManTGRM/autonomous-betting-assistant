import json

from autonomous_betting_agent import accuracy_decision_integration_preview as preview


def _history_rows():
    rows = []
    for index in range(40):
        rows.append({
            "event_id": f"h{index}",
            "event": f"History {index}",
            "sport": "tennis",
            "league": "atp",
            "market_type": "moneyline",
            "sportsbook": "book_a",
            "selection": "A",
            "decimal_odds": "2.00",
            "model_probability": "70%",
            "result": "win" if index < 20 else "loss",
            "locked_at_utc": f"2026-01-{(index % 28) + 1:02d}T00:00:00Z",
        })
    return rows


def _current_rows():
    return [
        {
            "proof_id": "p1",
            "event_id": "c1",
            "event": "A vs B",
            "sport": "tennis",
            "league": "atp",
            "market_type": "moneyline",
            "sportsbook": "book_a",
            "selection": "A",
            "decimal_odds": "2.00",
            "model_probability": "70%",
        },
        {
            "proof_id": "p2",
            "event_id": "c2",
            "event": "C vs D",
            "sport": "tennis",
            "league": "atp",
            "market_type": "moneyline",
            "sportsbook": "book_a",
            "selection": "C",
            "decimal_odds": "1.50",
            "model_probability": "55%",
        },
    ]


def test_parse_and_csv_helpers():
    rows = preview.parse_csv_text("proof_id,event\np1,A vs B\n")
    csv_text = preview.csv_from_rows(rows)

    assert rows[0]["proof_id"] == "p1"
    assert "event" in csv_text


def test_baseline_decision_blocks_bad_value():
    decision = preview._baseline_decision(0.50, 1.50, ev_buffer=0.0, safety_margin=0.02)

    assert decision["baseline_action"] == "NO BET"
    assert "below_minimum_playable_odds" in decision["baseline_blockers"]


def test_simulated_stake_zero_when_not_playable():
    assert preview.simulated_stake_fraction(0.70, 2.00, "NO BET") == 0.0
    assert preview.simulated_stake_fraction(0.70, 2.00, "PLAYABLE VALUE") > 0.0


def test_rank_scores_reward_calibrated_playable_rows():
    old = preview.old_rank_score(0.55, 2.0)
    new = preview.new_rank_score(0.60, 2.0, "PLAYABLE VALUE", [])

    assert new > old


def test_build_decision_preview_rows_combines_calibration_and_upgrade():
    calibration_rows = [
        {"row_index": 0, "calibrated_probability": 0.60, "calibration_status": "downgraded", "decision_blockers": []},
        {"row_index": 1, "calibrated_probability": 0.45, "calibration_status": "downgraded", "decision_blockers": ["calibrated_probability_below_threshold"]},
    ]
    upgraded_rows = [
        {"row_index": 0, "best_decimal_odds": 2.00, "best_sportsbook": "book_a", "blockers": [], "price_quality": "playable_price"},
        {"row_index": 1, "best_decimal_odds": 1.50, "best_sportsbook": "book_a", "blockers": ["below_minimum_playable_odds"], "price_quality": "bad_price"},
    ]
    rows = preview.build_decision_preview_rows(_current_rows(), calibration_rows, upgraded_rows)

    assert len(rows) == 2
    assert rows[0]["new_rank_score"] >= rows[1]["new_rank_score"]
    assert rows[1]["final_action"] == "NO BET"
    assert rows[1]["simulated_stake_fraction"] == 0.0


def test_summarize_decisions_counts_actions():
    summary = preview.summarize_decisions([
        {"final_action": "PLAYABLE VALUE"},
        {"final_action": "NO BET"},
        {"final_action": "WATCH ONLY"},
    ])

    assert summary["playable_count"] == 1
    assert summary["no_bet_count"] == 1
    assert summary["watch_count"] == 1


def test_build_accuracy_decision_integration_report_from_text_exports():
    current_csv = preview.csv_from_rows(_current_rows())
    history_csv = preview.csv_from_rows(_history_rows())
    report = preview.build_accuracy_decision_integration_report_from_text("test_01", current_csv, history_csv, min_segment_rows=4, shrinkage=10)
    payload = json.loads(preview.export_accuracy_decision_json(report))

    assert payload["schema_version"] == "accuracy_decision_integration_preview_v1"
    assert payload["current_row_count"] == 2
    assert payload["history_row_count"] == 40
    assert payload["decision_row_count"] == 2
    assert payload["preview_only"] is True
    assert payload["files_written"] == 0
    assert payload["live_changes"] == 0
    assert "final_action" in preview.export_decision_preview_csv(report)
    assert "repair_category" in preview.export_decision_repair_feedback_csv(report)


def test_decision_integration_has_no_external_client_paths():
    source = open("autonomous_betting_agent/accuracy_decision_integration_preview.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
