"""Normal-hook, no-conftest, no-network report-accounting acceptance check.

Run with `python -I -B scripts/report_accounting_runtime_regression.py`.
The process cannot write files, launch subprocesses, or access the network.
All report inputs are synthetic, and all generated exports stay in memory.
"""
import copy
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
blocked = []


def read_only(event, args):
    if event == 'open':
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            blocked.append({'event': event, 'target': str(args[:2])})
            raise PermissionError('Report regression cannot write files')
    if event in {'os.mkdir', 'os.remove', 'os.rename', 'os.rmdir', 'os.chmod', 'os.chown', 'os.truncate', 'os.system', 'subprocess.Popen', 'socket.connect', 'socket.connect_ex', 'socket.bind', 'socket.getaddrinfo'}:
        blocked.append({'event': event, 'target': str(args[:2])})
        raise PermissionError('Report regression cannot mutate or use the network')


sys.addaudithook(read_only)
sys.path.insert(0, str(ROOT))
os.environ.pop('GITHUB_ACTIONS', None)
os.environ.pop('ABA_DISABLE_RUNTIME_PATCHES', None)
import sitecustomize
import usercustomize
import pandas as pd
from autonomous_betting_agent.report_studio_service import build_report_studio_state, ReportStudioFilters
from autonomous_betting_agent.report_product_layer import MagazineBrand

CASES = [
    ({'result': 'loss', 'units': 1}, 'LOSS', None),
    ({'result': 'loss', 'units': 1, 'profit_units': -1}, 'LOSS', -1),
    ({'result_status': 'win', 'profit_units': .8}, 'WIN', .8),
    ({'result_status': 'win', 'profit_units': 0}, 'WIN', 0),
    ({'result_status': 'pending', 'profit_units': .8}, 'PENDING', None),
    ({'result': 'win', 'verified_grade': 'loss', 'profit_units': .8}, 'UNKNOWN', None),
    ({'result': 'win', 'profit_units': 'inf', 'stake_units': 1}, 'WIN', None),
    ({'result': 'win', 'profit_units': 'nan', 'stake_units': 1}, 'WIN', None),
    ({'result': 'win', 'profit_units': float('nan'), 'stake_units': 1}, 'WIN', None),
    ({'result': 'win', 'profit_units': .8, 'net_profit': .6}, 'WIN', None),
    ({'result': 'loss', 'stake_units': 2}, 'LOSS', -2),
    ({'result': 'win', 'stake_units': 2, 'fees_units': .1}, 'WIN', 1.5),
    ({'result': 'win', 'stake_units': 1, 'fees_units': .05, 'profit_units': .75}, 'WIN', .75),
    ({'result': 'void', 'stake_units': 1, 'fees_units': .05}, 'PUSH', -.05),
    ({'result': 'cancelled', 'profit_units': -.05, 'fees_units': .05}, 'CANCELLED', -.05),
    ({'result': 'win', 'roi': .8, 'return_units': 1.8, 'units': 1}, 'WIN', None),
]
rows = [{'event': f'Synthetic {index} vs Control {index}', 'sport': 'MLB', 'prediction': 'Synthetic', 'model_probability': .7, 'decimal_price': 1.8, 'odds_source': 'uploaded', **extra} for index, (extra, _, _) in enumerate(CASES)]
before = copy.deepcopy(rows)
receipt = {'entrypoint': build_report_studio_state.__module__ + '.' + build_report_studio_state.__name__, 'languages': {}, 'normal_hooks': True, 'conftest': False}
for language, input_kind in (('en', 'records'), ('es', 'records'), ('en', 'frame'), ('es', 'frame')):
    sources = [pd.DataFrame([row]) for row in rows] if input_kind == 'frame' else [rows]
    states = []
    for source in sources:
        original_source = copy.deepcopy(source)
        states.append(build_report_studio_state(source, MagazineBrand(language=language, workspace_id='synthetic_read_only_accounting'), filters=ReportStudioFilters(language=language, include_sports_context=False, mode='proof'), source_note='uploaded:synthetic-audit'))
        if input_kind == 'frame':
            pd.testing.assert_frame_equal(source, original_source)
        else:
            assert source == original_source
    by_event = {r['event']: r for state in states for r in state.cards.to_dict('records')}
    exports = {r['event']: r for state in states for r in json.loads(state.exports.json_text)}
    findings = []
    for index, (_, grade, profit) in enumerate(CASES):
        row = by_event[rows[index]['event']]
        assert row['result_status'] == grade, (language, index, row['result_status'], grade)
        actual = row['profit_units']
        if profit is None:
            assert actual is None or math.isnan(actual), (language, index, actual)
        else:
            assert math.isclose(actual, profit, abs_tol=1e-9), (language, index, actual, profit)
        exported = exports[rows[index]['event']]
        assert exported['result_status'] == grade, (language, index, exported['result_status'])
        if profit is not None:
            assert math.isclose(exported['profit_units'], profit, abs_tol=1e-9)
        else:
            assert exported['profit_units'] in ('', None), (language, index, exported['profit_units'])
        findings.append({'case': index, 'grade': grade, 'net_profit': profit, 'basis': row['report_profit_basis']})
    if input_kind == 'records':
        assert states[0].audit['by_sport']['roi'].isna().all()
    receipt['languages'][language + '_' + input_kind] = findings
assert rows == before
# The real startup installers probe loopback support and prepare an auth folder.
# Both remain denied; no other mutation/network attempt is allowed in this check.
assert all(
    (item['event'] == 'socket.bind' and "'::1'" in item['target'])
    or (item['event'] == 'os.mkdir' and str(ROOT / 'data' / 'local_users') in item['target'])
    for item in blocked
), blocked
receipt['input_unchanged'] = True
receipt['blocked_operations'] = blocked
receipt['cases_passed'] = len(CASES) * 4
print(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False))
