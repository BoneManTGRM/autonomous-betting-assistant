"""Offline production-source seams; no live app, provider or production data."""
import ast
from copy import deepcopy
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import requests
from streamlit.testing.v1 import AppTest

from autonomous_betting_agent import prediction_stage_evidence as stage
from autonomous_betting_agent.multi_source_fusion import fuse_row
from autonomous_betting_agent.scanner_strength import score_scanner_frame

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError('No network allowed')
    monkeypatch.setattr(requests.sessions.Session, 'request', deny)


@pytest.mark.parametrize('language', ['en', 'es'])
@pytest.mark.parametrize('route', ['pro_predictor', 'pro_predictor_volume'])
def test_bilingual_download_rerun_and_empty(language, route):
    snapshot = stage.capture_stage_evidence([{'model_probability': .61}], origin_route=route, now=NOW)
    script = """
import streamlit as st
from autonomous_betting_agent.prediction_capture_ui import render_stage_evidence
render_stage_evidence(st.session_state.get('snapshot'), st.session_state.get('language', 'en'), status=st.session_state.get('status'))
"""
    app = AppTest.from_string(script)
    app.session_state['snapshot'] = snapshot
    app.session_state['language'] = language
    app.run()
    assert not app.exception
    assert len(app.get('download_button')) == 1
    label = app.get('download_button')[0].proto.label
    assert ('Descargar' if language == 'es' else 'Download') in label
    assert route in '\n'.join(x.value for x in app.caption)
    app.run()
    assert app.session_state['snapshot'] == snapshot
    app.session_state['snapshot'] = None
    app.session_state['status'] = 'capture_failed'
    app.run()
    assert app.warning and not app.get('download_button') and not app.exception
    app.session_state['status'] = 'no_built_rows'
    app.run()
    assert app.info and not app.get('download_button')


class StopRun(Exception):
    pass


class UI:
    def __init__(self, state):
        self.session_state = state
    def button(self, *args, **kwargs):
        return True
    def stop(self):
        raise StopRun()
    def progress(self, *args):
        return self
    def empty(self):
        pass
    def info(self, *args):
        pass
    warning = error = info


def production_seam(route, rows, *, baseline=False, key='synthetic', scan_error=False, capture=stage.capture_stage_evidence):
    """Execute the real run block through persistence with all external seams fake.

    Baseline removes only the new evidence statements from the same source;
    reviewer additionally binds the unchanged pipeline to the exact base diff.
    Volume's actual required text transformations are applied, not reimplemented.
    """
    source = (ROOT / 'pages/pro_predictor.py').read_text()
    if route == 'pro_predictor_volume':
        volume = ast.parse((ROOT / 'pages/pro_predictor_volume.py').read_text())
        ns = {'code': source}
        replacement = [node for node in volume.body if isinstance(node, ast.FunctionDef) and node.name == '_replace_required']
        transforms = [node for node in volume.body if isinstance(node, ast.Assign) and
                      isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == '_replace_required']
        exec(compile(ast.Module(body=replacement + transforms, type_ignores=[]), '<volume-transforms>', 'exec'), ns)
        source = ns['code']
    tree = ast.parse(source)
    block = next(node for node in tree.body if isinstance(node, ast.If) and
                 isinstance(node.test, ast.Call) and isinstance(node.test.func, ast.Attribute) and node.test.func.attr == 'button')
    if baseline:
        # Only evidence additions: no pipeline operation is replaced or omitted.
        block.body = [n for n in block.body if 'aba_pre_ranking' not in ast.unparse(n) and
                      'SESSION_KEY' not in ast.unparse(n) and 'capture_stage_evidence' not in ast.unparse(n)]
    state = {stage.SESSION_KEY: 'STALE', 'aba_pre_ranking_evidence_status': 'captured'}
    calls = []
    def scan(*args, **kwargs):
        calls.append(('scan', args, kwargs))
        if scan_error:
            raise ValueError('synthetic failure')
        return ['synthetic-event']
    def score(frame, **kwargs):
        out = frame.copy()
        out['model_probability_clean'] = .8
        out['learned_agent_score'] = 80
        out['agent_score'] = 80
        out['scanner_strength_score'] = 80
        out['model_market_edge'] = .2
        out['lock_ready'] = True
        out['pattern_points'] = 80
        return out
    def persist(**kwargs):
        calls.append(('persist', {key: value.to_dict('records') for key, value in kwargs.items()}))
        raise StopRun()
    ns = dict(st=UI(state), SESSION_KEY=stage.SESSION_KEY, capture_stage_evidence=capture,
        Any=Any, Path=Path, __file__=str(ROOT / f'pages/{route}.py'), pd=pd,
        t=lambda value: value, LANG='en', odds_key=key, sports_key='', weather_key='',
        api_football_key='', perplexity_key='', newsapi_key='', balldontlie_key='',
        list_sports=lambda *a, **k: [], labels=['all', 'one', 'team', 'manual'], chosen='manual',
        manual_keys=['synthetic'], DEFAULT_SPORT_KEYS=['synthetic'],
        LiveAPIContextBuilder=lambda **kw: None, regions=['us'], max_events=25, markets=['h2h'],
        scan_market=scan, build_rows=lambda events, *a, **k: deepcopy(rows) if events else [],
        team_filter='', latest_event_date=date(2030, 1, 2), min_books=1,
        score_scanner_frame=lambda frame: frame.copy(), add_large_list_scores=score,
        strong_edge=.04, min_prob=.5, min_edge=0, min_signal=0, min_agent=0,
        max_rows=100, send_large=True, persist_handoff=persist,
        filter_profit_guard=lambda frame, mode: frame, profit_mode='Research', pattern_mode='Research')
    try:
        exec(compile(ast.Module(body=[block], type_ignores=[]), '<production-run>', 'exec'), ns)
    except StopRun:
        pass
    return state, calls


@pytest.mark.parametrize('route', ['pro_predictor', 'pro_predictor_volume'])
def test_actual_run_boundary_preserves_handoff_and_earlier_stage(route):
    rows = [{'event_id': 'a', 'model_probability': .61, 'model_probability_clean': .61},
            {'event_id': 'a', 'model_probability': .62, 'model_probability_clean': .62}]
    before = deepcopy(rows)
    baseline, baseline_calls = production_seam(route, rows, baseline=True)
    current, calls = production_seam(route, rows)
    assert rows == before and calls == baseline_calls
    for key, value in baseline.items():
        if key not in {stage.SESSION_KEY, 'aba_pre_ranking_evidence_status', 'ara_latest_predictions_saved_at'}:
            assert current[key] == value
    evidence = json.loads(current[stage.SESSION_KEY])
    assert evidence['origin_route'] == route
    assert [r['fields']['stage_model_probability_clean'] for r in evidence['rows']] == [.61, .62]
    assert all(r['model_probability_clean'] == .8 for r in current['pro_predictor_all_rows'])
    assert not any('stage_' in key for row in current['pro_predictor_all_rows'] for key in row)


@pytest.mark.parametrize('route', ['pro_predictor', 'pro_predictor_volume'])
@pytest.mark.parametrize('case', ['no_key', 'empty', 'scan_error', 'over_limit', 'bad_value', 'custom_scalar'])
def test_new_run_clears_stale_and_capture_failure_does_not_change_pipeline(route, case):
    rows = [{'model_probability': .61}]
    if case == 'empty': rows = []
    if case == 'over_limit': rows = rows * 1001
    if case == 'bad_value': rows = [{'model_probability': {'invalid': True}}]
    if case == 'custom_scalar':
        class CustomInt(int):
            def __int__(self):
                raise RuntimeError('Must not convert custom scalar')
        rows = [{'bookmaker_count': CustomInt(1)}]
    options = dict(key='' if case == 'no_key' else 'synthetic', scan_error=case == 'scan_error')
    current, calls = production_seam(route, rows, **options)
    _, baseline_calls = production_seam(route, rows, baseline=True, **options)
    assert stage.SESSION_KEY not in current
    assert calls == baseline_calls
    if case in {'over_limit', 'bad_value', 'custom_scalar'}:
        assert current['aba_pre_ranking_evidence_status'] == 'capture_failed'


@pytest.mark.parametrize("with_memory", [False, True])
def test_stage_capture_does_not_change_real_adaptive_values(monkeypatch, with_memory):
    from autonomous_betting_agent import adaptive_learning as adaptive
    patterns = {'sport:basketball': {'area_type': 'sport', 'group_value': 'basketball', 'records': 100, 'effective_records': 100, 'reliability': 1, 'smoothed_edge': .1}} if with_memory else {}
    monkeypatch.setattr(adaptive, 'load_pattern_index', lambda *a: patterns)
    monkeypatch.setattr(adaptive, 'learning_drift_summary', lambda *a: {'score_adjustment': 0})
    frame = pd.DataFrame([{'sport': 'basketball', 'model_probability_clean': .61, 'agent_score': 55, 'recommended_stake_units': .1}])
    before = adaptive.apply_adaptive_learning(frame)
    saved = stage.capture_stage_evidence(frame.to_dict('records'), origin_route='pro_predictor', now=NOW)
    pd.testing.assert_frame_equal(adaptive.apply_adaptive_learning(frame), before)
    assert json.loads(saved)['rows'][0]['fields']['stage_model_probability_clean'] == .61

    if with_memory:
        assert before.iloc[0]['learned_model_probability'] != .61
