import json

from autonomous_betting_agent import accuracy_calibration_repair_feedback as calib


def _history_rows():
    rows = []
    for index in range(40):
        rows.append({
            "event_id": f"h{index}",
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
            "event_id": "c1",
            "sport": "tennis",
            "league": "atp",
            "market_type": "moneyline",
            "sportsbook": "book_a",
            "selection": "A",
            "decimal_odds": "2.00",
            "model_probability": "70%",
        }
    ]


def test_parse_helpers_and_bands():
    rows = calib.parse_csv_text("event_id,model_probability\ne1,70%\n")

    assert rows[0]["event_id"] == "e1"
    assert calib.confidence_band(0.72) == "confidence_70_79"
    assert calib.segment_key(_current_rows()[0], "sportsbook") == "book_a"


def test_split_train_eval_uses_completed_rows():
    split = calib.split_train_eval(_history_rows())

    assert split["training_rows"]
    assert split["evaluation_rows"]
    assert split["mode"] in {"chronological_holdout", "stable_hash_holdout"}


def test_learn_calibration_model_detects_overconfidence():
    model = calib.learn_calibration_model(_history_rows(), min_segment_rows=4, shrinkage=10)
    corrections = model["segment_corrections"]
    confidence = corrections["confidence_band|confidence_70_79"]

    assert model["training_rows"] == 40
    assert confidence["sample_size"] == 40
    assert confidence["probability_correction"] < 0


def test_apply_calibration_downgrades_probability():
    model = calib.learn_calibration_model(_history_rows(), min_segment_rows=4, shrinkage=10)
    applied = calib.apply_calibration(_current_rows()[0], model)

    assert applied["baseline_probability"] == 0.7
    assert applied["calibrated_probability"] < 0.7
    assert applied["calibration_status"] == "downgraded"
    assert applied["calibration_breakdown"]


def test_calibrated_decision_blocks_overconfident_bad_value():
    decision = calib.calibrated_decision(_current_rows()[0], 0.50, ev_buffer=0.01, safety_margin=0.02)

    assert decision["decision_action"] in {"NO BET", "WAIT FOR BETTER ODDS"}
    assert decision["decision_blockers"]


def test_evaluate_calibration_shadow_returns_metrics():
    shadow = calib.evaluate_calibration_shadow(_history_rows(), min_segment_rows=4, shrinkage=10)

    assert shadow["training_rows"] > 0
    assert shadow["evaluation_rows"] > 0
    assert shadow["baseline_brier_score"] is not None
    assert shadow["calibrated_brier_score"] is not None
    assert shadow["decision"] in {"MANUAL REVIEW", "KEEP TESTING", "REJECT", "DATA BLOCKED"}


def test_repair_feedback_from_calibration_creates_shadow_feedback():
    shadow = calib.evaluate_calibration_shadow(_history_rows(), min_segment_rows=4, shrinkage=10)
    model = shadow["calibration_model"]
    preview = calib.build_calibrated_preview_rows(_current_rows(), model)
    feedback = calib.repair_feedback_from_calibration(shadow, preview)

    assert feedback
    assert all(item["live_mutation"] == "FORBIDDEN" for item in feedback)
    assert all(item["stored_data_mutation"] == "FORBIDDEN" for item in feedback)
    assert all(item["shadow_only"] is True for item in feedback)


def test_build_accuracy_calibration_feedback_report_exports():
    current_csv = calib.csv_from_rows(_current_rows())
    history_csv = calib.csv_from_rows(_history_rows())
    report = calib.build_accuracy_calibration_feedback_report_from_text("test_01", current_csv, history_csv, min_segment_rows=4, shrinkage=10)
    payload = json.loads(calib.export_accuracy_calibration_json(report))

    assert payload["schema_version"] == "accuracy_calibration_repair_feedback_v1"
    assert payload["current_row_count"] == 1
    assert payload["history_row_count"] == 40
    assert payload["preview_only"] is True
    assert payload["files_written"] == 0
    assert payload["live_changes"] == 0
    assert "calibrated_probability" in calib.export_calibrated_preview_csv(report)
    assert "baseline_probability" in calib.export_evaluation_preview_csv(report)
    assert "repair_category" in calib.export_repair_feedback_csv(report)


def test_accuracy_calibration_has_no_external_client_paths():
    source = open("autonomous_betting_agent/accuracy_calibration_repair_feedback.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
