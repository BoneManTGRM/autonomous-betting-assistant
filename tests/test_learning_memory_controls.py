from __future__ import annotations

from autonomous_betting_agent.learning_memory_controls import learning_safe_reason, reset_confirmation_matches, split_learning_safe_rows


def _row(**overrides):
    row = {
        "proof_id": "P1",
        "locked_at_utc": "2026-06-23T10:00:00+00:00",
        "event_start_time": "2026-06-23T12:00:00+00:00",
        "odds_audit_status": "pass",
        "grade": "win",
        "model_probability": 0.62,
        "decimal_price": 1.8,
    }
    row.update(overrides)
    return row


def test_learning_safe_row_passes():
    ok, reason = learning_safe_reason(_row())
    assert ok
    assert "Learning-safe" in reason


def test_quarantined_row_excluded():
    safe, blocked = split_learning_safe_rows([_row(odds_audit_status="quarantine")])
    assert not safe
    assert blocked[0]["learning_safe"] is False


def test_ungraded_row_excluded():
    ok, reason = learning_safe_reason(_row(grade="pending"))
    assert not ok
    assert "grade" in reason.lower()


def test_missing_probability_or_price_excluded():
    ok_prob, _ = learning_safe_reason(_row(model_probability=""))
    ok_price, _ = learning_safe_reason(_row(decimal_price=""))
    assert not ok_prob
    assert not ok_price


def test_reset_confirmation_exact_phrase():
    assert reset_confirmation_matches("RESET LEARNING MEMORY")
    assert not reset_confirmation_matches("reset")
