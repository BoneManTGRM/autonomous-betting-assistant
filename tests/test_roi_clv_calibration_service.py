import json

from autonomous_betting_agent import roi_clv_calibration_service as cal


def test_normalize_result_groups_win_loss_push_cancel():
    assert cal.normalize_result("W") == "win"
    assert cal.normalize_result("lost") == "loss"
    assert cal.normalize_result("void") == "push"
    assert cal.normalize_result("canceled") == "cancel"
    assert cal.normalize_result("open") == "pending"
    assert cal.normalize_result("weird") == "unknown"


def test_decimal_price_supports_decimal_and_american_odds():
    assert cal.decimal_price({"decimal_odds": 1.91}) == 1.91
    assert cal.decimal_price({"american_odds": 150}) == 2.5
    assert round(cal.decimal_price({"american_odds": -120}), 6) == round(1 + 100 / 120, 6)


def test_normalize_calibration_row_calculates_profit_and_clv():
    row = cal.normalize_calibration_row({
        "event": "Team A vs Team B",
        "pick": "Team A",
        "result": "win",
        "stake": 1,
        "decimal_odds": 2.0,
        "closing_decimal_odds": 1.9,
    })

    assert row["result"] == "win"
    assert row["profit_units"] == 1.0
    assert row["CLV_decimal"] == -0.1
    assert row["CLV_percent"] == -0.05
    assert row["playable_result"] is True


def test_summarize_roi_clv_rows_excludes_push_cancel_from_win_rate():
    summary = cal.summarize_roi_clv_rows([
        {"event": "A", "result": "win", "stake": 1, "decimal_odds": 2.0, "closing_decimal_odds": 1.9},
        {"event": "B", "result": "loss", "stake": 1, "decimal_odds": 2.0, "closing_decimal_odds": 2.1},
        {"event": "C", "result": "push", "stake": 1, "decimal_odds": 2.0},
        {"event": "D", "result": "cancel", "stake": 1, "decimal_odds": 2.0},
    ])

    assert summary["row_count"] == 4
    assert summary["playable_count"] == 2
    assert summary["wins"] == 1
    assert summary["losses"] == 1
    assert summary["push_cancel_count"] == 2
    assert summary["win_rate_ex_push_cancel"] == 0.5
    assert summary["ROI"] == 0.0


def test_summarize_roi_clv_rows_separates_unique_events_from_row_count():
    summary = cal.summarize_roi_clv_rows([
        {"event": "A vs B", "market_type": "moneyline", "result": "win", "decimal_odds": 2.0},
        {"event": "A vs B", "market_type": "spread", "result": "loss", "decimal_odds": 2.0},
        {"event": "C vs D", "market_type": "total", "result": "win", "decimal_odds": 1.8},
    ])

    assert summary["row_count"] == 3
    assert summary["unique_events"] == 2
    assert summary["duplicate_row_count"] == 1


def test_validate_roi_clv_calibration_warns_on_low_clv_sample_and_duplicates():
    summary = cal.summarize_roi_clv_rows([
        {"event": "A", "result": "win", "decimal_odds": 2.0},
        {"event": "A", "result": "loss", "decimal_odds": 2.0},
    ])
    result = cal.validate_roi_clv_calibration(summary)

    assert result["passed"] is True
    assert result["status"] == "CALIBRATION WARNING"
    assert "CLV sample size is below calibration target" in result["warnings"]
    assert "row-level picks include duplicate event exposure" in result["warnings"]


def test_validate_roi_clv_calibration_fails_no_rows():
    summary = cal.summarize_roi_clv_rows([])
    result = cal.validate_roi_clv_calibration(summary)

    assert result["passed"] is False
    assert result["status"] == "CALIBRATION FAILED"
    assert "no rows available for ROI/CLV calibration" in result["errors"]


def test_build_roi_clv_calibration_report_has_required_fields():
    report = cal.build_roi_clv_calibration_report("client-a", [{"event": "A", "result": "win", "decimal_odds": 2.0}])

    for field in (
        "schema_version",
        "workspace_id",
        "report_id",
        "report_hash",
        "status",
        "overall_passed",
        "row_count",
        "unique_events",
        "playable_count",
        "ROI",
        "win_rate_ex_push_cancel",
        "average_CLV_percent",
    ):
        assert field in report
    assert report["report_hash"].startswith("roi_clv_calibration_hash_")


def test_roi_clv_calibration_hash_stable_when_generated_at_changes():
    report = cal.build_roi_clv_calibration_report("client-a", [{"event": "A", "result": "win", "decimal_odds": 2.0}])
    changed_time = dict(report, generated_at_utc="2099-01-01T00:00:00Z")
    changed_roi = dict(report, ROI=99)

    assert cal.build_roi_clv_calibration_hash(report) == cal.build_roi_clv_calibration_hash(changed_time)
    assert cal.build_roi_clv_calibration_hash(report) != cal.build_roi_clv_calibration_hash(changed_roi)


def test_validate_report_blocks_overstated_pass():
    report = cal.build_roi_clv_calibration_report("client-a", [])
    overstated = dict(report, overall_passed=True)
    overstated["report_hash"] = cal.build_roi_clv_calibration_hash(overstated)

    result = cal.validate_roi_clv_calibration_report(overstated)

    assert result["passed"] is False
    assert any("overall_passed" in error for error in result["errors"])


def test_sanitized_export_omits_row_summaries_and_raw_errors():
    report = cal.build_roi_clv_calibration_report("client-a", [])
    payload = json.loads(cal.export_roi_clv_calibration_report_json(report, public_safe=True))

    assert "row_summaries" not in payload
    assert "errors" not in payload
    assert payload["error_count"] >= 1


def test_roi_clv_calibration_service_has_no_write_network_or_tuning_paths():
    source = open("autonomous_betting_agent/roi_clv_calibration_service.py", encoding="utf-8").read()
    forbidden = (
        "requests.",
        "httpx.",
        "urllib.",
        "append_performance_rows",
        "sync_rows_by_source",
        "approve_ledger_import",
        "update_result",
        "delete_proof",
        "fit(",
        "train(",
        "write_text",
        "write_bytes",
    )
    for token in forbidden:
        assert token not in source
