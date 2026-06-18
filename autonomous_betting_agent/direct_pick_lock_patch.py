from __future__ import annotations

from typing import Any

import pandas as pd

from .commercial_platform_tools import load_persistent_ledger, merge_ledgers, normalize_workspace_id, save_persistent_ledger
from .odds_lock_tools import lock_status, now_utc, proof_hash, proof_id_from_hash


def _float_or_blank(value: Any) -> Any:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return ''
    if pd.isna(parsed) or parsed <= 0:
        return ''
    return parsed


def _probability(value: Any) -> Any:
    parsed = _float_or_blank(value)
    if parsed == '':
        return ''
    return round(parsed / 100.0 if parsed > 1 else parsed, 6)


def _render_manual_hold(st: Any) -> None:
    if st.session_state.get('_aba_direct_manual_hold_rendered_v2'):
        return
    st.session_state['_aba_direct_manual_hold_rendered_v2'] = True
    with st.expander('Manual pick hold / Guardar pick manual', expanded=True):
        st.caption('This saves one pick directly into the active test ledger. It does not require Pro Predictor or What Are the Odds handoff.')
        with st.form('aba_manual_direct_hold_form_v2', clear_on_submit=False):
            c1, c2 = st.columns(2)
            event = c1.text_input('Game / event', key='manual_hold_event')
            pick = c2.text_input('Pick / prediction', key='manual_hold_pick')
            c3, c4, c5 = st.columns(3)
            sport = c3.text_input('Sport / league', key='manual_hold_sport')
            market = c4.selectbox('Market', ['h2h', 'spreads', 'totals', 'prop', 'other'], key='manual_hold_market')
            start = c5.text_input('Event start UTC', key='manual_hold_start')
            c6, c7, c8 = st.columns(3)
            probability = c6.number_input('Model probability %', min_value=0.0, max_value=100.0, value=0.0, step=0.5, key='manual_hold_prob')
            price = c7.number_input('Decimal odds', min_value=0.0, max_value=1000.0, value=0.0, step=0.01, key='manual_hold_price')
            book = c8.text_input('Bookmaker/source', key='manual_hold_book')
            notes = st.text_area('Notes', key='manual_hold_notes', height=80)
            submit = st.form_submit_button('Hold this pick now', type='primary', use_container_width=True)
        if not submit:
            return
        if not event.strip() or not pick.strip():
            st.error('Enter at least the game/event and pick.')
            return
        workspace_id = normalize_workspace_id(st.session_state.get('aba_test_window_id') or 'test_01')
        locked_at = now_utc()
        row = {
            'event': event.strip(),
            'sport': sport.strip() or 'manual_entry',
            'market_type': market,
            'prediction': pick.strip(),
            'event_start_utc': start.strip(),
            'model_probability': _probability(probability),
            'decimal_price': _float_or_blank(price),
            'bookmaker': book.strip() or 'manual_entry',
            'odds_source': book.strip() or 'manual_entry',
            'manual_context_notes': notes.strip(),
            'locked_at_utc': locked_at,
            'test_window_id': workspace_id,
            'ledger_type': 'manual_direct_hold',
            'official_ev_pick': False,
            'agent_decision': 'manual_direct_hold',
            'stake_units': 1.0,
            'result_status': 'pending',
            'public_confidence': 'Manual Hold',
            'public_reason': 'Manually held research pick. Not official +EV proof unless completed before start with full odds/probability fields.',
            'lock_blockers': '',
        }
        row['proof_status'] = lock_status(row)
        row['proof_hash'] = proof_hash(row)
        row['proof_id'] = proof_id_from_hash(row['proof_hash'])
        existing = load_persistent_ledger(workspace_id=workspace_id)
        saved = save_persistent_ledger(merge_ledgers(existing, pd.DataFrame([row])), workspace_id=workspace_id)
        records = saved.to_dict('records')
        st.session_state['odds_lock_pro_locked_rows'] = records
        st.session_state['public_proof_dashboard_refresh_rows'] = records
        st.session_state['ara_latest_predictions'] = records
        st.success(f'Pick held and saved to {workspace_id}. Rows saved: {len(records)}')


def install_direct_pick_lock_patch() -> None:
    try:
        import streamlit as st
    except Exception:
        return
    if getattr(st, '_aba_direct_pick_lock_patch_v2', False):
        return
    original_title = st.title

    def patched_title(body: Any, *args: Any, **kwargs: Any) -> Any:
        result = original_title(body, *args, **kwargs)
        if str(body).strip().lower() == 'odds lock pro':
            _render_manual_hold(st)
        return result

    st.title = patched_title
    st._aba_direct_pick_lock_patch_v2 = True
