import json

from autonomous_betting_agent import market_optimizer_preview as opt


def _market_rows():
    return [
        {"event_id": "e1", "event": "A vs B", "sport": "tennis", "league": "atp", "sportsbook": "Book A", "market_type": "moneyline", "selection": "A", "decimal_odds": "2.10", "model_probability": "60%", "calibrated_probability": "58%"},
        {"event_id": "e1", "event": "A vs B", "sport": "tennis", "league": "atp", "sportsbook": "Book B", "market_type": "moneyline", "selection": "A", "decimal_odds": "2.20", "model_probability": "60%", "calibrated_probability": "58%"},
        {"event_id": "e2", "event": "C vs D", "sport": "wnba", "league": "wnba", "sportsbook": "Book A", "market_type": "spread", "selection": "C -2.5", "decimal_odds": "1.95", "model_probability": "57%", "calibrated_probability": "56%"},
        {"event_id": "e3", "event": "E vs F", "sport": "soccer", "league": "liga", "sportsbook": "Book C", "market_type": "correct_score", "selection": "1-0", "decimal_odds": "6.00", "model_probability": "12%", "calibrated_probability": "10%"},
        {"event_id": "e4", "event": "G vs H", "sport": "tennis", "league": "atp", "sportsbook": "Book A", "market_type": "moneyline", "selection": "G", "decimal_odds": "1.60", "model_probability": "55%", "calibrated_probability": "54%", "line_status": "stale"},
    ]


def _history_rows():
    return [
        {"sport": "soccer", "league": "liga", "sportsbook": "Book C", "market_type": "correct_score", "result": "loss", "closing_line_value": "-0.03", "profit_units": "-1"},
        {"sport": "soccer", "league": "liga", "sportsbook": "Book C", "market_type": "correct_score", "result": "loss", "closing_line_value": "-0.02", "profit_units": "-1"},
        {"sport": "soccer", "league": "liga", "sportsbook": "Book C", "market_type": "correct_score", "result": "loss", "closing_line_value": "-0.01", "profit_units": "-1"},
        {"sport": "soccer", "league": "liga", "sportsbook": "Book C", "market_type": "correct_score", "result": "loss", "closing_line_value": "-0.04", "profit_units": "-1"},
        {"sport": "soccer", "league": "liga", "sportsbook": "Book C", "market_type": "correct_score", "result": "win", "closing_line_value": "-0.01", "profit_units": "2"},
    ]


def test_decimal_odds_supports_american_conversion():
    assert opt.decimal_odds({"american_odds": "+150"}) == 2.5
    assert round(opt.decimal_odds({"american_odds": "-200"}), 2) == 1.5


def test_score_market_row_marks_positive_value_playable():
    scored = opt.score_market_row(_market_rows()[1], [])

    assert scored["final_action"] == "PLAYABLE VALUE"
    assert scored["ev"] > 0
    assert scored["chain_eligible"] is True
    assert scored["suggested_stake_fraction"] <= 0.03


def test_score_market_row_blocks_stale_line():
    scored = opt.score_market_row(_market_rows()[4], [])

    assert scored["final_action"] == "NO BET"
    assert scored["stale_line"] is True
    assert any("stale" in blocker for blocker in scored["blockers"])


def test_score_market_row_blocks_unsupported_or_bad_ev():
    scored = opt.score_market_row(_market_rows()[3], _history_rows())

    assert scored["final_action"] == "NO BET"
    assert scored["unsupported_market"] is True
    assert scored["segment_risk_score"] > 0


def test_best_book_chooses_highest_price_for_same_market():
    report = opt.build_market_optimizer_preview("test_01", _market_rows()[:2], [], bankroll=100)
    best = report["best_book_rows"][0]

    assert best["best_sportsbook"] == "Book B"
    assert best["best_decimal_odds"] == 2.2


def test_avoid_list_flags_bad_segments():
    report = opt.build_market_optimizer_preview("test_01", _market_rows(), _history_rows())

    assert report["avoid_list"]
    assert any(row["market_type"] == "correct_score" for row in report["avoid_list"])


def test_chain_preview_uses_only_positive_eligible_legs():
    report = opt.build_market_optimizer_preview("test_01", _market_rows()[:3], [], bankroll=100)
    chains = report["chain_builder_rows"]

    assert chains
    assert all(row["leg_count"] in (2, 3) for row in chains)
    assert any(row["final_action"] == "CHAIN PREVIEW" for row in chains)


def test_market_optimizer_report_exports_and_marco_mode_are_client_safe():
    market_csv = opt.csv_from_rows(_market_rows())
    history_csv = opt.csv_from_rows(_history_rows())
    report = opt.build_market_optimizer_preview_from_text("test_01", market_csv, history_csv, bankroll=200)
    payload = json.loads(opt.export_market_optimizer_json(report))
    marco = json.loads(opt.export_marco_mode_json(report))

    assert payload["schema_version"] == "market_optimizer_preview_v1"
    assert payload["preview_only"] is True
    assert payload["files_written"] == 0
    assert payload["live_changes"] == 0
    assert marco["client_safe"] is True
    assert marco["api_keys_included"] is False
    assert marco["profit_guarantee"] is False
    assert "market_id" not in json.dumps(marco)
    assert "market_id" in opt.export_market_hunter_csv(report)
    assert "best_sportsbook" in opt.export_best_books_csv(report)
    assert "avoid_reasons" in opt.export_avoid_list_csv(report)
    assert "chain_id" in opt.export_chain_builder_csv(report)
    assert "optimizer_hash" in opt.export_market_optimizer_manifest_json(report)


def test_market_optimizer_preview_has_no_external_client_paths():
    source = open("autonomous_betting_agent/market_optimizer_preview.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
