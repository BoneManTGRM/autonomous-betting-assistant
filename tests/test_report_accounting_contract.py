import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

import pandas as pd
import pytest

from autonomous_betting_agent.report_accounting import accounting_result, preserve_accounting_input
from autonomous_betting_agent.report_learning_layer import apply_learning_layer, summarize_group, calibration_audit


@pytest.mark.parametrize('row,grade,profit', [
    ({'result': 'loss', 'units': 1}, 'LOSS', None),
    ({'result': 'loss', 'units': 1, 'profit_units': -1}, 'LOSS', -1),
    ({'result_status': 'win', 'profit_units': .8}, 'WIN', .8),
    ({'result_status': 'win', 'profit_units': 0}, 'WIN', 0),
    ({'result_status': 0, 'profit_units': -1}, 'LOSS', -1),
    ({'verified_grade': 'win', 'result': 'loss', 'profit_units': .8}, 'UNKNOWN', None),
    ({'result': 'pending', 'profit_units': 1}, 'PENDING', None),
    ({'result_status': 'win', 'profit_units': float('inf'), 'stake_units': 1, 'decimal_price': 1.8}, 'WIN', None),
    ({'result_status': 'win', 'profit_units': float('nan'), 'stake_units': 1, 'decimal_price': 1.8}, 'WIN', None),
    ({'result': 'win', 'profit_units': .8, 'net_profit': .6}, 'WIN', None),
    ({'result': 'loss', 'profit_units': 1}, 'LOSS', None),
    ({'result': 'push', 'profit_units': .1}, 'PUSH', None),
    ({'result': 'loss', 'stake_units': 2}, 'LOSS', -2),
    ({'result': 'win', 'stake_units': 2, 'decimal_price': 1.8}, 'WIN', 1.6),
    ({'result': 'win', 'stake_units': 1, 'decimal_price': 1.8, 'fees_units': .05}, 'WIN', .75),
    ({'result': 'win', 'profit_units': .75, 'fees_units': .05, 'stake_units': 1, 'decimal_price': 1.8}, 'WIN', .75),
    ({'result': 'win', 'profit_units': -.05, 'fees_units': .85}, 'WIN', -.05),
    ({'result': 'void', 'stake_units': 1, 'fees_units': .05}, 'PUSH', -.05),
    ({'result': 'cancelled', 'profit_units': -.05, 'fees_units': .05}, 'CANCELLED', -.05),
    ({'result': 'win', 'roi': .8, 'return_units': 1.8, 'units': 1}, 'WIN', None),
    ({'result': 'win', 'stake_units': 0, 'decimal_price': 1.8}, 'WIN', None),
    ({'result': 'win', 'stake_units': 1, 'decimal_price': float('inf')}, 'WIN', None),
    ({'result': 'not_a_result', 'profit_units': 1}, 'UNKNOWN', None),
])
def test_accounting_contract(row, grade, profit):
    actual = accounting_result(row)
    assert actual['result_status'] == grade
    if profit is None:
        assert actual['profit_units'] is None
    else:
        assert actual['profit_units'] == pytest.approx(profit)


def test_input_provenance_prevents_normalizer_stake_alias_and_repeat_drift():
    row = {'result': 'loss', 'units': 1}
    original = copy.deepcopy(row)
    preserved = preserve_accounting_input(row)
    preserved['profit_units'] = 1  # legacy normalize_frame units alias
    assert accounting_result(preserved)['profit_units'] is None
    assert row == original


def test_report_learning_layer_is_idempotent_and_does_not_rewrite_inputs():
    raw = pd.DataFrame([preserve_accounting_input({'event': 'Synthetic', 'result_status': 'win', 'profit_units': .8})])
    original = raw.copy(deep=True)
    once = apply_learning_layer(raw)
    twice = apply_learning_layer(once)
    pd.testing.assert_frame_equal(raw, original)
    assert twice.iloc[0]['result_status'] == 'WIN'
    assert twice.iloc[0]['profit_units'] == .8
    assert once.iloc[0]['report_accounting_input_json'] == twice.iloc[0]['report_accounting_input_json']


def test_roi_requires_complete_explicit_stake_and_profit_not_decision_count():
    rows = [
        {'sport': 'MLB', 'result_status': 'LOSS', 'profit_units': -2, 'report_stake_units': 2},
        {'sport': 'MLB', 'result_status': 'WIN', 'profit_units': 1, 'report_stake_units': 1},
    ]
    summary = summarize_group(pd.DataFrame(rows), 'sport').iloc[0]
    assert summary['roi'] == pytest.approx(-1 / 3)
    rows[0]['profit_units'] = None
    summary = summarize_group(pd.DataFrame(rows), 'sport').iloc[0]
    assert pd.isna(summary['roi'])
    assert summary['suggestion'] == 'Incomplete accounting / no promotion'


def test_fee_adjusted_profit_does_not_regrade_sport_outcome():
    actual = accounting_result({'result': 'win', 'profit_units': -.1, 'fees_units': 1})
    assert actual['result_status'] == 'WIN'
    assert actual['profit_units'] == -.1
    assert actual['report_profit_basis'] == 'explicit_net_profit'


def test_conflicts_are_quarantined_from_report_learning_and_publication():
    row = preserve_accounting_input({'result': 'win', 'verified_grade': 'loss', 'profit_units': .8, 'model_probability': .7, 'decimal_price': 1.8, 'odds_source': 'The Odds API', 'publish_ready': True})
    card = apply_learning_layer(pd.DataFrame([row])).iloc[0]
    assert card['result_status'] == 'UNKNOWN'
    assert not card['learning_ready']
    assert not card['official_publish_ready']
    assert card['data_issue_reason'] == 'Accounting review required'
    assert card['official_status_label'] == 'Data Blocked'
    assert card['publish_ready']  # source readiness is not rewritten


def test_accounting_quarantine_is_excluded_from_report_calibration_metrics():
    raw = pd.DataFrame([{'sport': 'MLB', 'result_status': 'win', 'profit_units': .8, 'stake_units': 1, 'fees_units': -1, 'model_probability': .7, 'decimal_price': 1.8, 'odds_source': 'The Odds API'}])
    cards = apply_learning_layer(raw)
    assert cards.iloc[0]['report_accounting_quarantined']
    assert not cards.iloc[0]['learning_ready']
    audit = calibration_audit(raw)
    assert not audit or audit['by_sport'].empty or audit['by_sport']['sample_size'].sum() == 0
    assert summarize_group(cards, 'sport')['sample_size'].sum() == 0


@pytest.mark.parametrize('profits,stakes', [
    ([float('inf')], [1]),
    ([1], [float('inf')]),
    ([1e308] * 30, [1] * 30),
    ([1e308], [1e-308]),
])
def test_nonfinite_or_overflowed_group_metrics_cannot_promote(profits, stakes):
    frame = pd.DataFrame({'sport': 'MLB', 'result_status': 'WIN', 'profit_units': profits, 'report_stake_units': stakes, 'decimal_price': 2})
    summary = summarize_group(frame, 'sport')
    assert pd.isna(summary.iloc[0]['roi'])
    assert summary.iloc[0]['roi_basis'] == 'unavailable'
    assert summary.iloc[0]['suggestion'] == 'Incomplete accounting / no promotion'
    serialized = summary.to_json(orient='records')
    assert 'NaN' not in serialized and 'Infinity' not in serialized


def test_complete_report_state_with_real_runtime_hooks_no_conftest_or_io(tmp_path):
    script = Path(__file__).resolve().parents[1] / 'scripts' / 'report_accounting_runtime_regression.py'
    result = subprocess.run([sys.executable, '-I', '-B', str(script)], cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt['normal_hooks'] and not receipt['conftest']
    assert receipt['cases_passed'] == 64
    assert receipt['input_unchanged']
    assert receipt['fixture']['isolated_temporary_workspace']
    assert receipt['fixture']['created_before_runtime_guard']
    assert receipt['fixture']['source_files_unchanged']
    assert receipt['fixture']['runtime_files_unchanged']
    assert receipt['fixture']['source_data_access_attempts'] == []
    assert not receipt['fixture']['source_data_or_secrets_copied']


@pytest.mark.parametrize('existing_profile', [False, True])
def test_runtime_fixture_never_uses_or_changes_source_profile_or_history(tmp_path, existing_profile):
    source = Path(__file__).resolve().parents[1]
    checkout = tmp_path / 'checkout'
    checkout.mkdir()
    paths = list(source.glob('*.py'))
    for folder in ('autonomous_betting_agent', 'pages', 'src'):
        paths.extend((source / folder).rglob('*.py'))
    paths.append(source / 'scripts' / 'report_accounting_runtime_regression.py')
    for path in paths:
        if path.is_symlink() or '__pycache__' in path.parts:
            continue
        target = checkout / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)

    # Match a clean CI checkout after other tests prepared local-user folders,
    # then repeat with a preexisting source profile. Neither is runtime input.
    profile = checkout / 'data/local_users/owner/profile.json'
    profile.parent.mkdir(parents=True)
    for name in ('exports', 'ledgers', 'uploads'):
        (profile.parent / name).mkdir()
    source_profile = b'{"user_id":"owner","display_name":"SOURCE PROFILE MUST NOT BE READ"}'
    if existing_profile:
        profile.write_bytes(source_profile)
    canaries = [checkout / 'data/history-canary.json', checkout / '.aba_state/history-canary.json']
    for path in canaries:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'SYNTHETIC SOURCE HISTORY: MUST NOT BE READ OR COPIED')
    outside_cwd = tmp_path / 'unrelated-cwd'
    outside_cwd.mkdir()
    result = subprocess.run([sys.executable, '-I', '-B', str(checkout / 'scripts/report_accounting_runtime_regression.py')],
                            cwd=outside_cwd, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt['normal_hooks'] and not receipt['conftest']
    assert receipt['cases_passed'] == 64 and receipt['input_unchanged']
    assert receipt['fixture']['source_data_access_attempts'] == []
    assert receipt['fixture']['runtime_files_unchanged']
    assert receipt['fixture']['source_files_unchanged']
    assert not receipt['fixture']['source_data_or_secrets_copied']
    assert all(item['event'] != 'open' for item in receipt['blocked_operations'])
    assert profile.exists() is existing_profile
    if existing_profile:
        assert profile.read_bytes() == source_profile
    for path in canaries:
        assert path.read_bytes() == b'SYNTHETIC SOURCE HISTORY: MUST NOT BE READ OR COPIED'


def test_sparse_dataframe_nan_net_receipt_cannot_be_inferred_as_missing():
    from autonomous_betting_agent.report_studio_service import build_report_studio_state, ReportStudioFilters
    from autonomous_betting_agent.report_product_layer import MagazineBrand
    base = {'sport': 'MLB', 'prediction': 'Synthetic', 'model_probability': .7, 'decimal_price': 1.8, 'odds_source': 'uploaded', 'result_status': 'win', 'stake_units': 1}
    raw = pd.DataFrame([{**base, 'event': 'Synthetic A', 'profit_units': .8}, {**base, 'event': 'Synthetic B'}])
    before = raw.copy(deep=True)
    state = build_report_studio_state(raw, MagazineBrand(), filters=ReportStudioFilters(include_sports_context=False), source_note='uploaded:synthetic')
    card = state.cards[state.cards['event'].eq('Synthetic B')].iloc[0]
    assert pd.isna(card['profit_units'])
    assert card['report_accounting_quarantined']
    assert 'invalid_or_conflicting_net_profit' in card['report_accounting_issues']
    pd.testing.assert_frame_equal(raw, before)


@pytest.mark.parametrize('language', ['en', 'es'])
def test_provider_verification_cannot_override_accounting_quarantine_in_exports(language):
    from autonomous_betting_agent.report_studio_service import build_report_studio_state, ReportStudioFilters
    from autonomous_betting_agent.report_product_layer import MagazineBrand
    row = {'event': 'Synthetic A vs B', 'sport': 'MLB', 'prediction': 'Synthetic A', 'selection': 'Synthetic A', 'market_type': 'h2h', 'model_probability': .7, 'decimal_price': 2, 'model_market_edge': .2, 'expected_value_per_unit': .4, 'odds_source': 'The Odds API', 'provider': 'The Odds API', 'book': 'Synthetic Book', 'current_provider_verified': True, 'provider_event_id': 'synthetic-123', 'event_id': 'synthetic-123', 'price_timestamp': datetime.now(timezone.utc).isoformat(), 'result': 'win', 'verified_grade': 'loss', 'profit_units': .8}
    original = copy.deepcopy(row)
    state = build_report_studio_state([row], MagazineBrand(language=language), filters=ReportStudioFilters(language=language, include_sports_context=False, mode='proof'), source_note='current_provider:synthetic')
    exported = json.loads(state.exports.json_text)[0]
    assert exported['report_verification_class'] == 'AUDIT_ONLY'
    assert exported['consumer_action'] == 'AUDIT ONLY'
    assert not exported['automated_live_provider_verified']
    assert 'Accounting review required' in exported['verification_reason']
    assert b'Action: VERIFIED' not in state.exports.pdf_bytes
    assert b'Acci\xf3n: VERIFIED' not in state.exports.pdf_bytes
    if language == 'en':
        assert b'Action: AUDIT ONLY' in state.exports.pdf_bytes
    assert row == original
