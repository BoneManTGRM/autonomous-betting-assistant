import json

from autonomous_betting_agent import reparodynamics_shadow_scoring as scoring


def _dynamic(**overrides):
    base = {
        "decision": "future_manual_review",
        "lr_evaluation_rows": 120,
        "completed_rows_used": 120,
        "train_test_overlap_count": 0,
        "unsafe_feature_count": 0,
        "summary_counts": {"data_blockers_count": 0},
        "comparison_metrics": {
            "profit_units_delta": 3.0,
            "ROI_delta": 0.12,
            "losses_delta": -2,
            "calibration_delta": 0.03,
            "CLV_delta": 0.01,
        },
        "manual_review_queue": [
            {"title": "Dynamic Odds Predictor Shadow Layer", "decision": "future_manual_review", "sample_size": 120, "completed_rows_used": 120}
        ],
    }
    base.update(overrides)
    return base


def _odds(**overrides):
    base = {"row_count": 10, "playable_count": 4, "blocked_count": 1}
    base.update(overrides)
    return base


def test_parse_helpers():
    obj = scoring.parse_json_object('{"a": 1}')
    rows = scoring.parse_csv_text("title,sample_size\nA,10\n")

    assert obj["a"] == 1
    assert rows[0]["title"] == "A"


def test_score_shadow_candidate_manual_review_when_clean_and_beneficial():
    candidate = _dynamic()["manual_review_queue"][0]
    result = scoring.score_shadow_candidate(candidate, _dynamic(), _odds())

    assert result["decision"] == "MANUAL REVIEW"
    assert result["RYE_score"] > 20
    assert result["shadow_only"] is True
    assert result["live_mutation"] == "FORBIDDEN"


def test_score_shadow_candidate_rejects_overlap():
    candidate = {"title": "bad", "sample_size": 120, "completed_rows_used": 120}
    result = scoring.score_shadow_candidate(candidate, _dynamic(train_test_overlap_count=1), _odds())

    assert result["decision"] == "REJECT"
    assert "train_test_overlap_detected" in result["blockers"]


def test_score_shadow_candidate_rejects_degradation():
    candidate = {"title": "bad", "sample_size": 120, "completed_rows_used": 120}
    dynamic = _dynamic(comparison_metrics={"profit_units_delta": -1, "ROI_delta": -0.01, "losses_delta": 1})
    result = scoring.score_shadow_candidate(candidate, dynamic, _odds())

    assert result["decision"] == "REJECT"
    assert "profit_or_roi_degraded" in result["blockers"]


def test_build_reparodynamics_shadow_scoring_report_counts_candidates():
    report = scoring.build_reparodynamics_shadow_scoring_report("test_01", _dynamic(), _odds())

    assert report["schema_version"] == "reparodynamics_shadow_scoring_v1"
    assert report["mode"] == "SHADOW ONLY"
    assert report["candidate_count"] >= 1
    assert report["manual_review_count"] >= 1
    assert report["preview_only"] is True
    assert report["files_written"] == 0
    assert report["live_changes"] == 0
    assert report["safety_gates"]["automatic_live_promotion"] == "FORBIDDEN"
    assert report["shadow_scoring_hash"].startswith("reparodynamics_shadow_hash_")


def test_build_reparodynamics_shadow_scoring_report_from_text_exports():
    report = scoring.build_reparodynamics_shadow_scoring_report_from_text(
        "test_01",
        json.dumps(_dynamic()),
        json.dumps(_odds()),
        "title,sample_size,completed_rows_used\nOperator Candidate,80,80\n",
    )
    payload = json.loads(scoring.export_shadow_scoring_json(report))
    rows_csv = scoring.export_scored_candidates_csv(report)

    assert payload["candidate_count"] >= 2
    assert "RYE_score" in rows_csv


def test_reparodynamics_scoring_has_no_external_client_paths():
    source = open("autonomous_betting_agent/reparodynamics_shadow_scoring.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
