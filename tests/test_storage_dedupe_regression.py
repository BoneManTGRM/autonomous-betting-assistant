from __future__ import annotations

import pandas as pd

from autonomous_betting_agent.commercial_platform_tools import merge_ledgers
from autonomous_betting_agent.pick_hold_store import dedupe_rows, rows_from_any


def test_dedupe_rows_uses_proof_id():
    rows = [
        {'proof_id': 'P1', 'event': 'A vs B', 'prediction': 'A', 'decimal_price': 1.5},
        {'proof_id': 'P1', 'event': 'A vs B', 'prediction': 'A', 'decimal_price': 1.6},
        {'proof_id': 'P2', 'event': 'C vs D', 'prediction': 'C', 'decimal_price': 1.7},
    ]
    out = dedupe_rows(rows)
    assert len(out) == 2
    assert out[0]['decimal_price'] == 1.6


def test_dedupe_rows_uses_event_pick_fallback():
    rows = [
        {'event': 'A vs B', 'sport': 'Soccer', 'market_type': 'h2h', 'prediction': 'A', 'event_start_utc': '2099-01-01T00:00:00Z'},
        {'event': 'A vs B', 'sport': 'Soccer', 'market_type': 'h2h', 'prediction': 'A', 'event_start_utc': '2099-01-01T00:00:00Z'},
    ]
    assert len(rows_from_any(rows)) == 1


def test_merge_ledgers_counts_unique_proof_rows_not_physical_copies():
    frame = pd.DataFrame([
        {'proof_id': 'P1', 'locked_at_utc': '2026-01-01T00:00:00Z', 'event': 'A vs B', 'prediction': 'A', 'event_start_utc': '2099-01-01T00:00:00Z', 'market_type': 'h2h', 'decimal_price': 1.5},
        {'proof_id': 'P1', 'locked_at_utc': '2026-01-01T00:00:00Z', 'event': 'A vs B', 'prediction': 'A', 'event_start_utc': '2099-01-01T00:00:00Z', 'market_type': 'h2h', 'decimal_price': 1.5},
    ])
    assert len(merge_ledgers(frame, frame, frame)) == 1
