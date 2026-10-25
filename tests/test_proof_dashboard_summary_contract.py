"""The runtime ROI hook must preserve the locked-pick summary API."""
from __future__ import annotations

import builtins
import importlib
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest
import requests
import streamlit as st
from streamlit.delta_generator import DeltaGenerator
from streamlit.testing.v1 import AppTest

from autonomous_betting_agent import odds_lock_tools, proof_dashboard_patch, proof_roi_tools

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_KEYS = {
    'locked_picks', 'resolved_picks', 'wins', 'losses', 'pushes', 'hit_rate',
    'total_staked_units', 'profit_units', 'roi', 'avg_decimal_price',
    'avg_model_probability', 'avg_edge', 'valid_before_start',
}


@pytest.fixture
def runtime_tools(monkeypatch):
    # CI disables usercustomize; install the same hook explicitly there. Restore
    # its assignments afterwards so unrelated tests keep their normal API.
    if not getattr(st, '_proof_roi_patch_v1', False):
        monkeypatch.setattr(st, '_proof_roi_patch_v1', False, raising=False)
        for owner, names in (
            (st, ('json',)),
            (DeltaGenerator, ('json',)),
            (odds_lock_tools, ('update_profit_columns', 'summarize_locked_picks',
                               'performance_by_group', 'cumulative_profit_frame')),
        ):
            for name in names:
                monkeypatch.setattr(owner, name, getattr(owner, name, None), raising=False)
        proof_dashboard_patch.install_proof_dashboard_patch()
    return odds_lock_tools


@pytest.mark.parametrize('frame', [None, [], pd.DataFrame()])
def test_empty_runtime_summary_keeps_original_keys(runtime_tools, frame):
    summary = runtime_tools.summarize_locked_picks(frame)
    assert SUMMARY_KEYS <= summary.keys()
    assert summary['locked_picks'] == summary['valid_before_start'] == 0
    assert summary['total_staked_units'] == summary['profit_units'] == 0.0
    for key in ('hit_rate', 'roi', 'avg_decimal_price', 'avg_model_probability', 'avg_edge'):
        assert summary[key] is None
    assert summary['flat_roi'] is None


@pytest.mark.parametrize('proof_status, timestamps, expected', [
    ('locked_before_start', {}, 1),
    ('invalid_after_start', {}, 0),
    ('locked_without_verified_start', {}, 0),
    ('missing_lock_time', {}, 0),
    (None, {}, 0),
    ('', {'locked_at_utc': '2026-01-01T00:00:00Z', 'event_start_utc': '2026-01-02T00:00:00Z'}, 0),
    ('invalid_after_start', {'locked_at_utc': '2026-01-01T00:00:00Z', 'event_start_utc': '2026-01-02T00:00:00Z'}, 0),
])
def test_validity_counts_explicit_status_not_inferred_timestamps(runtime_tools, proof_status, timestamps, expected):
    row = {'event': 'Synthetic A at B', **timestamps}
    if proof_status is not None:
        row['proof_status'] = proof_status
    before = deepcopy(row)
    summary = runtime_tools.summarize_locked_picks([row])
    assert summary['locked_picks'] == 1
    assert summary['valid_before_start'] == expected
    assert row == before


@pytest.mark.parametrize('as_frame', [False, True])
def test_compatibility_preserves_canonical_grades_and_roi(runtime_tools, as_frame):
    rows = [
        {'result_status': 'win', 'result': 'loss', 'stake_units': 2.5, 'profit_units': 0.75,
         'decimal_price': 2.0, 'model_probability': 60, 'model_edge': 0.10, 'proof_status': 'locked_before_start'},
        {'result_status': 'loss', 'result': 'win', 'stake_units': 0.5, 'profit_units': -0.5,
         'decimal_price': 3.0, 'model_probability': 0.50, 'model_edge': 0.20, 'proof_status': 'invalid_after_start'},
        {'result_status': 'void', 'stake_units': 4, 'profit_units': 111, 'proof_status': 'locked_before_start'},
        {'result_status': 'pending', 'stake_units': 8, 'profit_units': 222, 'proof_status': 'locked_without_verified_start'},
    ]
    frame = pd.DataFrame(rows, index=[8, 3, 17, 2]) if as_frame else rows
    before = deepcopy(frame)
    summary = runtime_tools.summarize_locked_picks(frame)
    assert SUMMARY_KEYS <= summary.keys()
    # The ROI extension remains authoritative for all its existing fields.
    extension = proof_roi_tools.summarize(frame)
    assert {key: summary[key] for key in extension} == extension
    assert (summary['wins'], summary['losses'], summary['pushes'], summary['resolved_picks']) == (1, 1, 1, 2)
    assert summary['total_staked_units'] == 3.0
    assert summary['profit_units'] == 0.25
    assert summary['roi'] == 0.083333
    assert summary['flat_profit_units'] == summary['flat_roi'] == 0.0
    assert summary['valid_before_start'] == 2
    assert summary['avg_decimal_price'] == 2.5
    assert summary['avg_model_probability'] == 0.55
    assert summary['avg_edge'] == 0.15
    if as_frame:
        pd.testing.assert_frame_equal(frame, before)
    else:
        assert frame == before


def test_runtime_summary_install_is_idempotent_after_reload(runtime_tools):
    original = runtime_tools.summarize_locked_picks
    rows = [{'proof_status': 'locked_before_start'}]
    before = original(rows)
    proof_dashboard_patch.install_proof_dashboard_patch()
    importlib.reload(proof_dashboard_patch).install_proof_dashboard_patch()
    assert runtime_tools.summarize_locked_picks is original
    assert runtime_tools.summarize_locked_picks(rows) == before


@pytest.mark.parametrize('language', ['en', 'es'])
@pytest.mark.parametrize('populated', [False, True])
def test_odds_lock_page_renders_with_runtime_summary(runtime_tools, language, populated, monkeypatch, tmp_path):
    from autonomous_betting_agent import commercial_platform_tools as cpt, pick_hold_store

    attempts = []
    def no_requests(*args, **kwargs):
        attempts.append((args, kwargs))
        raise AssertionError('Synthetic summary rendering must not contact providers')
    monkeypatch.setattr(requests.sessions.Session, 'request', no_requests)
    monkeypatch.setattr(builtins, 'get_secret', lambda *names: '', raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pick_hold_store, 'DATA_DIR', tmp_path / 'held')
    original_path = cpt.persistent_ledger_path
    monkeypatch.setattr(cpt, 'persistent_ledger_path',
                        lambda workspace_id='', path=None: original_path(workspace_id, path=tmp_path / 'ledger.csv'))
    rows = [{
        'event': 'Synthetic A at B', 'prediction': 'B', 'model_probability': 0.64,
        'decimal_price': 2.05, 'stake_units': 0.25, 'result_status': 'pending',
        'proof_id': 'SYNTHETIC-ONLY', 'proof_hash': 'synthetic-only',
        'locked_at_utc': '2026-01-01T00:00:00Z', 'event_start_utc': '',
        'proof_status': 'locked_without_verified_start',
    }] if populated else []
    app = AppTest.from_file(str(ROOT / 'streamlit_app.py'))
    app.session_state['aba_test_window_id'] = 'synthetic_summary_contract'
    app.session_state['odds_lock_pro_locked_rows'] = rows
    app.session_state['public_proof_dashboard_refresh_rows'] = rows
    app.run(timeout=60)
    if language == 'es':
        app.radio(key='aba_radio_global_language').set_value('Español').run(timeout=60)
    app.switch_page('pages/odds_lock_pro.py').run(timeout=60)
    assert not app.exception
    if populated:
        label = 'Valid pre-start locks' if language == 'en' else 'Bloqueos validos antes del inicio'
        assert any(metric.label == label and metric.value == '0' for metric in app.metric)
    else:
        assert app.warning
    assert attempts == []
