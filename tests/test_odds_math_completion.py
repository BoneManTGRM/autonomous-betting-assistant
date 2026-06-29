import json

from autonomous_betting_agent import odds_math_completion as odds


def _row(**overrides):
    base = {
        "proof_id": "p1",
        "event": "A vs B",
        "selection": "A",
        "sportsbook": "testbook",
        "american_odds": "+150",
        "model_probability": "50%",
    }
    base.update(overrides)
    return base


def test_american_decimal_conversions():
    assert odds.decimal_from_american("+150") == 2.5
    assert odds.decimal_from_american("-200") == 1.5
    assert odds.american_from_decimal(2.5) == 150
    assert odds.american_from_decimal(1.5) == -200


def test_implied_overround_and_no_vig():
    values = [1.91, 1.91]
    assert odds.implied_probability(2.0) == 0.5
    assert odds.market_overround(values) > 1.0
    no_vig = odds.no_vig_probabilities(values)
    assert round(sum(value for value in no_vig if value), 6) == 1.0


def test_fair_minimum_ev_and_kelly():
    assert odds.fair_decimal_odds(0.5) == 2.0
    assert odds.minimum_playable_decimal_odds(0.5, ev_buffer=0.05, safety_margin=0.02) == 2.12
    assert odds.expected_value(0.5, 2.5) == 0.25
    assert odds.edge(0.55, 0.50) == 0.05
    assert odds.fractional_kelly_stake_fraction(0.5, 2.5, fraction=0.25, cap=0.03) > 0


def test_assess_completed_odds_row_playable_value():
    result = odds.assess_completed_odds_row(_row())

    assert result["decimal_odds"] == 2.5
    assert result["american_odds"] == 150
    assert result["expected_value"] == 0.25
    assert result["action"] == "PLAYABLE VALUE"
    assert result["stake_fraction"] <= 0.03


def test_assess_completed_odds_row_blocks_bad_price():
    result = odds.assess_completed_odds_row(_row(american_odds="-300", model_probability="50%"))

    assert result["action"] in {"NO BET", "WATCH ONLY"}
    assert "ev_below_buffer" in result["blockers"] or "edge_not_positive" in result["blockers"]


def test_build_market_no_vig_report():
    report = odds.build_market_no_vig_report([_row(selection="A", decimal_odds=1.91), _row(selection="B", decimal_odds=1.91)])

    assert report["market_side_count"] == 2
    assert report["bookmaker_margin"] > 0
    assert len(report["no_vig_rows"]) == 2


def test_build_odds_math_completion_report_from_text_exports():
    csv_text = "proof_id,event,selection,american_odds,model_probability\np1,A vs B,A,+150,50%\n"
    report = odds.build_odds_math_completion_report_from_text("test_01", csv_text, csv_text)
    payload = json.loads(odds.export_odds_math_json(report))
    rows_csv = odds.export_odds_rows_csv(report)

    assert payload["schema_version"] == "odds_math_completion_v1"
    assert payload["row_count"] == 1
    assert payload["playable_count"] == 1
    assert "minimum_playable_odds" in rows_csv
    assert payload["preview_only"] is True
    assert payload["files_written"] == 0
    assert payload["live_changes"] == 0


def test_odds_math_has_no_external_client_paths():
    source = open("autonomous_betting_agent/odds_math_completion.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
