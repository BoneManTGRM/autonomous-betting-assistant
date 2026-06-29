from __future__ import annotations

from copy import deepcopy

from autonomous_betting_agent.advisory_market_completeness import (
    COMPLETE_MARKET,
    FUTURES_OUTRIGHT_INCOMPLETE,
    MISMATCHED_SPREAD_LINE,
    MISMATCHED_TOTAL_LINE,
    MISSING_LINE_VALUE,
    MISSING_MARKET_SIDE,
    MISSING_SELECTION,
    MIXED_SPORTSBOOK_MARKET,
    UNKNOWN_MARKET_STRUCTURE,
    market_completeness_diagnostics,
    market_completeness_summary,
)
from autonomous_betting_agent.advisory_odds_value_display import (
    advisory_csv_frame,
    advisory_report_text,
    advisory_rows,
    fresh_slate_readiness_check,
    proof_safety_comparison,
)
from autonomous_betting_agent.odds_value_engine import PLAYABLE_PLUS_EV


def _row(**overrides):
    base = {
        "event": "Team A vs Team B",
        "sport": "basketball",
        "market_type": "h2h",
        "bookmaker": "Caliente",
        "event_start_utc": "2099-01-01T00:00:00Z",
        "odds_timestamp": "2098-12-31T23:55:00Z",
        "decimal_odds": 2.10,
        "model_probability": 0.60,
        "lr_model_loaded": True,
        "model_quality_label": "STRONG SAMPLE",
    }
    base.update(overrides)
    return base


def _statuses(rows):
    return {row["advisory_market_completeness_status"] for row in market_completeness_diagnostics(rows)}


def test_h2h_complete_same_real_sportsbook():
    rows = [_row(selection="Team A"), _row(selection="Team B")]
    assert _statuses(rows) == {COMPLETE_MARKET}
    assert all(row["advisory_no_vig_available"] for row in market_completeness_diagnostics(rows))


def test_h2h_missing_side():
    rows = [_row(selection="Team A")]
    assert _statuses(rows) == {MISSING_MARKET_SIDE}


def test_soccer_1x2_complete_and_missing_draw():
    complete = [
        _row(sport="soccer", market_type="1x2", selection="home"),
        _row(sport="soccer", market_type="1x2", selection="draw", decimal_odds=3.20),
        _row(sport="soccer", market_type="1x2", selection="away", decimal_odds=3.70),
    ]
    assert _statuses(complete) == {COMPLETE_MARKET}
    missing_draw = [
        _row(sport="soccer", market_type="1x2", selection="home"),
        _row(sport="soccer", market_type="1x2", selection="away", decimal_odds=3.70),
    ]
    assert _statuses(missing_draw) == {MISSING_MARKET_SIDE}


def test_totals_same_line_complete_and_mismatched_line():
    complete = [
        _row(market_type="totals", selection="Over 2.5", total=2.5),
        _row(market_type="totals", selection="Under 2.5", total=2.5),
    ]
    assert _statuses(complete) == {COMPLETE_MARKET}
    mismatched = [
        _row(market_type="totals", selection="Over 2.5", total=2.5),
        _row(market_type="totals", selection="Under 3.5", total=3.5),
    ]
    assert _statuses(mismatched) == {MISMATCHED_TOTAL_LINE}


def test_spreads_matching_absolute_line_complete_and_mismatched():
    complete = [
        _row(market_type="spread", selection="Team A", spread=-1.5),
        _row(market_type="spread", selection="Team B", spread=1.5),
    ]
    assert _statuses(complete) == {COMPLETE_MARKET}
    mismatched = [
        _row(market_type="spread", selection="Team A", spread=-1.5),
        _row(market_type="spread", selection="Team B", spread=2.5),
    ]
    assert _statuses(mismatched) == {MISMATCHED_SPREAD_LINE}


def test_futures_unknown_missing_selection_and_missing_line():
    assert _statuses([_row(market_type="futures", selection="Team A")]) == {FUTURES_OUTRIGHT_INCOMPLETE}
    assert _statuses([_row(market_type="player_prop", selection="Team A")]) == {UNKNOWN_MARKET_STRUCTURE}
    assert _statuses([_row(market_type="h2h", selection="")]) == {MISSING_SELECTION}
    assert _statuses([_row(market_type="totals", selection="Over")]) == {MISSING_LINE_VALUE}


def test_mixed_sportsbook_sides_do_not_complete_market():
    rows = [
        _row(selection="Team A", bookmaker="Caliente"),
        _row(selection="Team B", bookmaker="Codere"),
    ]
    assert _statuses(rows) == {MIXED_SPORTSBOOK_MARKET}
    assert all(not row["advisory_no_vig_available"] for row in market_completeness_diagnostics(rows))


def test_consensus_only_rows_do_not_create_no_vig_market():
    rows = [
        _row(selection="Team A", bookmaker="consensus_average"),
        _row(selection="Team B", bookmaker="consensus_average"),
    ]
    diagnostics = advisory_rows(rows, config={"allow_playable_without_shadow_model": True})
    assert {row["advisory_market_completeness_status"] for row in diagnostics} != {COMPLETE_MARKET}
    assert all(not row["advisory_no_vig_available"] for row in diagnostics)
    assert all(row["advisory_playable_status"] != PLAYABLE_PLUS_EV for row in diagnostics)


def test_incomplete_and_mismatched_markets_cannot_become_playable():
    rows = [_row(selection="Team A")]
    out = advisory_rows(rows, config={"allow_playable_without_shadow_model": True})
    assert out[0]["advisory_playable_status"] != PLAYABLE_PLUS_EV
    assert out[0]["advisory_no_vig_available"] is False

    mismatched = [
        _row(market_type="totals", selection="Over 2.5", total=2.5),
        _row(market_type="totals", selection="Under 3.5", total=3.5),
    ]
    out = advisory_rows(mismatched, config={"allow_playable_without_shadow_model": True})
    assert all(row["advisory_playable_status"] != PLAYABLE_PLUS_EV for row in out)


def test_csv_report_readiness_and_summary_include_market_completeness():
    rows = [_row(selection="Team A"), _row(selection="Team B")]
    csv = advisory_csv_frame(rows)
    assert "advisory_market_completeness_status" in csv.columns
    assert "advisory_no_vig_available" in csv.columns

    report = advisory_report_text(rows)
    assert "Market Completeness Summary" in report
    assert "COMPLETE_MARKET" in report

    readiness = fresh_slate_readiness_check(rows, now="2098-12-31T23:56:00Z")
    assert readiness["complete_market_count"] > 0

    incomplete_readiness = fresh_slate_readiness_check([_row(selection="Team A")], now="2098-12-31T23:56:00Z")
    assert incomplete_readiness["readiness_status"] == "NEEDS_COMPLETE_MARKETS"

    summary = market_completeness_summary(rows)
    assert not summary.empty
    assert set(summary["completeness_status"]) == {COMPLETE_MARKET}


def test_market_completeness_does_not_mutate_proof_or_official_fields():
    rows = [
        _row(
            selection="Team A",
            proof_hash="abc",
            proof_id="proof_1",
            locked_at_utc="2098-01-01T00:00:00Z",
            lock_ready=True,
            official_lock_ready=True,
            publish_ready=True,
            official_ev_pick=True,
            stake_units=2,
        )
    ]
    original = deepcopy(rows)
    out = advisory_rows(rows)
    assert rows == original
    result = proof_safety_comparison(rows, out)
    assert result["passed"] is True


def test_previously_playable_rows_are_downgraded_when_no_vig_unavailable():
    rows = [
        {
            **_row(selection="Team A"),
            "advisory_playable_status": "PLAYABLE_PLUS_EV",
            "advisory_playable_reason": "previously_playable",
            "advisory_odds_value_tier": "PLAYABLE",
        }
    ]
    out = advisory_rows(rows)
    assert out[0]["advisory_playable_status"] != "PLAYABLE_PLUS_EV"
    assert out[0]["advisory_odds_value_tier"] == "WATCHLIST"
