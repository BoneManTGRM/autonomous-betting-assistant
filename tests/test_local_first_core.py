from __future__ import annotations

from autonomous_betting_agent.explanations import build_pick_explanation
from autonomous_betting_agent.grading_rules import summarize_event_level, summarize_row_level
from autonomous_betting_agent.ledger_types import OFFICIAL_LEDGER, RESEARCH_LEDGER, classify_ledger_type, public_metric_allowed
from autonomous_betting_agent.report_exports import render_markdown_report, summarize_record


def _official_row(**overrides):
    row = {
        "proof_id": "P1",
        "locked_at_utc": "2026-06-23T10:00:00+00:00",
        "event_start_time": "2026-06-23T12:00:00+00:00",
        "event_name": "Team A vs Team B",
        "prediction": "Team A",
        "market": "moneyline",
        "odds_audit_status": "pass",
        "pattern_points": 82,
        "learned_model_probability": 0.64,
        "model_market_edge": 0.04,
        "bookmaker_count": 5,
    }
    row.update(overrides)
    return row


def test_official_row_classification_requires_forward_lock():
    row = _official_row()
    assert classify_ledger_type(row) == OFFICIAL_LEDGER
    assert public_metric_allowed(row)


def test_bad_or_research_row_is_not_public_metric():
    row = _official_row(research_only=True)
    assert classify_ledger_type(row) == RESEARCH_LEDGER
    assert not public_metric_allowed(row)


def test_pick_explanation_mentions_no_guarantee():
    text = build_pick_explanation(_official_row())
    assert "not a guaranteed outcome" in text.lower()
    assert "pattern points" in text.lower()


def test_report_summary_excludes_research_by_default():
    rows = [_official_row(grade="win"), _official_row(proof_id="P2", research_only=True, grade="loss")]
    summary = summarize_record(rows, official_only=True)
    assert summary["wins"] == 1
    assert summary["losses"] == 0


def test_event_level_does_not_count_duplicate_rows_as_multiple_games():
    rows = [
        _official_row(proof_id="P1", grade="win"),
        _official_row(proof_id="P2", market="spread", grade="push"),
    ]
    row_level = summarize_row_level(rows)
    event_level = summarize_event_level(rows)
    assert row_level["rows"] == 2
    assert event_level["events"] == 1


def test_markdown_report_has_disclaimer():
    report = render_markdown_report([_official_row(grade="win")])
    assert "does not guarantee" in report.lower()
    assert "Team A vs Team B" in report
