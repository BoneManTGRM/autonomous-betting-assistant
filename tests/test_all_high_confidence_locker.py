from __future__ import annotations

from pathlib import Path

import pandas as pd

from autonomous_betting_agent.all_high_confidence_locker import lock_all_high_confidence_rows


def test_all_high_confidence_locker_rejects_tennis_and_marks_internal() -> None:
    rows = pd.DataFrame([
        {
            'event': 'A FC vs B FC',
            'sport': 'soccer',
            'market_type': 'h2h',
            'prediction': 'A FC',
            'model_probability': 0.62,
            'decimal_price': 1.95,
            'event_start_utc': '2099-01-01T00:00:00Z',
        },
        {
            'event': 'Player One vs Player Two',
            'sport': 'ATP Tennis',
            'market_type': 'h2h',
            'prediction': 'Player One',
            'model_probability': 0.64,
            'decimal_price': 1.80,
            'event_start_utc': '2099-01-01T01:00:00Z',
        },
    ])

    locked, rejected = lock_all_high_confidence_rows(rows, workspace_id='test_iso')

    assert len(locked) == 1
    assert len(rejected) == 1
    assert locked.iloc[0]['ledger_type'] == 'all_high_confidence_internal_test'
    assert locked.iloc[0]['official_ev_pick'] is False
    assert locked.iloc[0]['official_lock_ready'] is False
    assert locked.iloc[0]['research_lock_ready'] is True
    assert str(locked.iloc[0]['proof_id']).startswith('OLP-')
    assert rejected.iloc[0]['reject_reason'] == 'REJECT_UNSUPPORTED_MARKET'


def test_all_high_confidence_page_does_not_write_public_proof_keys() -> None:
    page = Path('pages/all_high_confidence_locker.py').read_text(encoding='utf-8')
    assert "st.session_state['odds_lock_pro_locked_rows']" not in page
    assert "st.session_state['public_proof_dashboard_refresh_rows']" not in page
    assert "save_held_rows('odds_lock_pro_locked_rows'" not in page
    assert "save_held_rows('public_proof_dashboard_refresh_rows'" not in page
