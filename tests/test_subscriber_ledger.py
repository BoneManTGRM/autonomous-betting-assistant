import json

from autonomous_betting_agent import subscriber_ledger as ledger


def _rows():
    return [
        {"subscriber_id": "s1", "date": "2026-06-30", "sport": "tennis", "event_id": "e1", "event": "A vs B", "market_type": "moneyline", "selection": "A", "sportsbook": "caliente", "decimal_odds": "2.10", "stake": "100", "result": "win", "risk_level": "low", "ev": "0.12"},
        {"subscriber_id": "s1", "date": "2026-06-30", "sport": "tennis", "event_id": "e1", "event": "A vs B", "market_type": "spread", "selection": "A -1.5", "sportsbook": "caliente", "decimal_odds": "1.90", "stake": "50", "result": "loss", "risk_level": "medium", "ev": "0.05"},
        {"subscriber_id": "s1", "date": "2026-06-30", "sport": "wnba", "event_id": "e2", "event": "C vs D", "market_type": "total", "selection": "Over", "sportsbook": "playdoit", "decimal_odds": "1.80", "stake": "40", "result": "push", "risk_level": "low"},
        {"subscriber_id": "s2", "date": "2026-06-30", "sport": "soccer", "event_id": "e3", "event": "E vs F", "market_type": "moneyline", "selection": "E", "sportsbook": "bet365", "decimal_odds": "2.50", "stake": "80", "result": "loss", "risk_level": "high"},
        {"subscriber_id": "s2", "date": "2026-06-30", "sport": "soccer", "event_id": "e4", "event": "G vs H", "market_type": "moneyline", "selection": "G", "sportsbook": "bet365", "decimal_odds": "2.20", "stake": "80", "result": "loss", "risk_level": "high"},
    ]


def test_result_status_normalizes_outcomes():
    assert ledger.result_status("won") == "win"
    assert ledger.result_status("lost") == "loss"
    assert ledger.result_status("void") == "push"
    assert ledger.result_status("cancelled") == "cancel"
    assert ledger.result_status("open") == "pending"


def test_profit_loss_calculates_from_odds_and_stake():
    win = ledger.normalize_ledger_row(_rows()[0])
    loss = ledger.normalize_ledger_row(_rows()[1])
    push = ledger.normalize_ledger_row(_rows()[2])

    assert win["profit_loss"] == 110
    assert loss["profit_loss"] == -50
    assert push["profit_loss"] == 0


def test_win_rate_excludes_pushes_and_cancels():
    rows = [ledger.normalize_ledger_row(row, i) for i, row in enumerate(_rows()[:3])]

    assert ledger.win_rate(rows) == 0.5
    assert ledger.outcome_counts(rows)["pushes"] == 1


def test_subscriber_summary_separates_rows_from_unique_events():
    rows = [ledger.normalize_ledger_row(row, i) for i, row in enumerate(_rows()[:3])]
    summary = ledger.subscriber_summary("s1", rows)

    assert summary["row_count"] == 3
    assert summary["unique_event_count"] == 2
    assert summary["win_rate_ex_push_cancel"] == 0.5
    assert summary["profit_loss"] == 60
    assert summary["stake"] == 190
    assert round(summary["roi"], 6) == round(60 / 190, 6)


def test_group_performance_and_mistake_patterns():
    rows = [ledger.normalize_ledger_row(row, i) for i, row in enumerate(_rows())]
    sport_perf = ledger.group_performance(rows, "sport")
    patterns = ledger.mistake_patterns([row for row in rows if row["subscriber_id"] == "s2"])

    assert any(row["sport"] == "tennis" and row["row_count"] == 2 for row in sport_perf)
    assert patterns
    assert any(pattern["reason"] in {"losses exceed wins", "segment ROI below -10%"} for pattern in patterns)


def test_build_subscriber_ledger_reports_exports():
    report = ledger.build_subscriber_ledger_reports("test_01", _rows())
    payload = json.loads(ledger.export_subscriber_ledger_json(report))

    assert payload["schema_version"] == "subscriber_ledger_v1"
    assert payload["ledger_status"] == "LEDGER REPORTS READY"
    assert payload["ledger_row_count"] == 5
    assert payload["subscriber_count"] == 2
    assert payload["unique_event_count"] == 4
    assert payload["global_summary"]["win_rate_ex_push_cancel"] == round(1 / 4, 6)
    assert payload["preview_only"] is True
    assert payload["files_written"] == 0
    assert payload["live_changes"] == 0
    assert "ledger_id" in ledger.export_ledger_rows_csv(report)
    assert "subscriber_id" in ledger.export_subscriber_summaries_csv(report)
    assert "sport" in ledger.export_sport_performance_csv(report)
    assert "market_type" in ledger.export_market_type_performance_csv(report)
    assert "sportsbook" in ledger.export_sportsbook_performance_csv(report)
    assert "pattern_id" in ledger.export_mistake_patterns_csv(report)
    assert "check_id" in ledger.export_ledger_checks_csv(report)
    assert "ledger_hash" in ledger.export_ledger_manifest_json(report)


def test_build_subscriber_ledger_reports_from_text():
    csv_text = ledger.csv_from_rows(_rows())
    report = ledger.build_subscriber_ledger_reports_from_text("test_01", csv_text)

    assert report["ledger_row_count"] == 5
    assert report["subscriber_count"] == 2
    assert report["ledger_status"] == "LEDGER REPORTS READY"


def test_build_subscriber_ledger_reports_blocks_empty_input():
    report = ledger.build_subscriber_ledger_reports("test_01", [])

    assert report["ledger_status"] == "BLOCKED"
    assert any(row["check_id"] == "ledger_rows_present" and row["status"] == "FAIL" for row in report["ledger_checks"])


def test_subscriber_ledger_has_no_external_client_paths():
    source = open("autonomous_betting_agent/subscriber_ledger.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
