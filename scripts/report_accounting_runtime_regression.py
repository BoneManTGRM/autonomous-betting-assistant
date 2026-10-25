"""Normal-hook, no-conftest, no-network report-accounting acceptance check.

Run with `python -I -B scripts/report_accounting_runtime_regression.py`.
The launcher copies Python source only into an owned temporary workspace and
creates a synthetic local-user fixture. The runtime child cannot write files,
launch subprocesses, or access the network. It never imports from repository
data directories. All report inputs and the local-user profile are synthetic;
all generated exports stay in memory. The launcher removes its workspace after
the guarded child exits.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SOURCE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATA = (SOURCE_ROOT / 'data', SOURCE_ROOT / '.aba_state')


def source_data_path(path):
    if not isinstance(path, (str, bytes, os.PathLike)):
        return False
    resolved = Path(os.fsdecode(path)).resolve()
    return any(resolved == root or root in resolved.parents for root in SOURCE_DATA)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files():
    """Allowlist executable source, not data, config, secrets, or symlinks."""
    yield from (p for p in SOURCE_ROOT.glob('*.py') if not p.is_symlink())
    for name in ('autonomous_betting_agent', 'pages', 'src'):
        folder = SOURCE_ROOT / name
        if not folder.is_dir() or folder.is_symlink():
            continue
        for directory, dirs, files in os.walk(folder, followlinks=False):
            dirs[:] = [d for d in dirs if d not in {'data', '.aba_state', '__pycache__'}
                       and not (Path(directory) / d).is_symlink()]
            for name in files:
                path = Path(directory) / name
                if path.suffix == '.py' and not path.is_symlink():
                    yield path


def launch_isolated_runtime():
    source_access_attempts = []

    def preparation_guard(event, args):
        if event in {'open', 'os.listdir', 'os.scandir'} and source_data_path(args[0]):
            source_access_attempts.append(event)
            raise PermissionError('The fixture must not inspect repository data')
        if event in {'socket.connect', 'socket.connect_ex', 'socket.bind', 'socket.getaddrinfo', 'socket.sendto'}:
            raise PermissionError('Fixture setup cannot access the network')
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            mode, flags = args[1], args[2]
            writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if writing and (path == SOURCE_ROOT or SOURCE_ROOT in path.parents):
                raise PermissionError('Fixture setup cannot write repository files')

    sys.addaudithook(preparation_guard)
    with tempfile.TemporaryDirectory(prefix='aba-accounting-runtime-') as temporary:
        runtime = Path(temporary).resolve()
        assert runtime != SOURCE_ROOT and SOURCE_ROOT not in runtime.parents
        originals = {}
        for source in source_files():
            relative = source.relative_to(SOURCE_ROOT)
            originals[str(relative)] = digest(source)
            target = runtime / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        profile = runtime / 'data' / 'local_users' / 'owner' / 'profile.json'
        profile.parent.mkdir(parents=True)
        for name in ('exports', 'ledgers', 'uploads'):
            (profile.parent / name).mkdir()
        profile.write_text(json.dumps({'user_id': 'owner', 'display_name': 'Synthetic accounting fixture',
                                      'created_at_utc': '2024-01-01T00:00:00Z',
                                      'notes': 'Synthetic runtime fixture; never a source user profile.'}), encoding='utf-8')
        for name in ('home', 'tmp'):
            (runtime / name).mkdir()
        before = {str(p.relative_to(runtime)): digest(p) for p in runtime.rglob('*') if p.is_file()}
        env = {'HOME': str(runtime / 'home'), 'USERPROFILE': str(runtime / 'home'),
               'TMPDIR': str(runtime / 'tmp'), 'TEMP': str(runtime / 'tmp'), 'TMP': str(runtime / 'tmp'),
               'PATH': str(Path(sys.executable).parent) + os.pathsep + os.defpath,
               'PYTHONDONTWRITEBYTECODE': '1', 'STREAMLIT_BROWSER_GATHER_USAGE_STATS': 'false'}
        result = subprocess.run([sys.executable, '-I', '-B', str(Path(__file__).resolve()),
                                 '--isolated-runtime', str(runtime)], cwd=runtime, env=env,
                                capture_output=True, text=True, timeout=50)
        after = {str(p.relative_to(runtime)): digest(p) for p in runtime.rglob('*') if p.is_file()}
        assert before == after, 'The guarded runtime changed its source or synthetic fixture'
        assert all(digest(SOURCE_ROOT / p) == value for p, value in originals.items())
        assert not source_access_attempts, source_access_attempts
        if result.returncode:
            sys.stderr.write(result.stderr)
            sys.stdout.write(result.stdout)
            return result.returncode
        receipt = json.loads(result.stdout)
        receipt['fixture'] = {'isolated_temporary_workspace': True, 'created_before_runtime_guard': True,
                              'source_python_files': len(originals), 'source_files_unchanged': True,
                              'runtime_files_unchanged': True, 'source_data_access_attempts': source_access_attempts,
                              'synthetic_profile_sha256': digest(profile),
                              'source_data_or_secrets_copied': False}
        print(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False))
        return 0


if len(sys.argv) == 1:
    raise SystemExit(launch_isolated_runtime())
if len(sys.argv) != 3 or sys.argv[1] != '--isolated-runtime':
    raise SystemExit('Use python -I -B scripts/report_accounting_runtime_regression.py')
ROOT = Path(sys.argv[2]).resolve()
assert ROOT != SOURCE_ROOT and SOURCE_ROOT not in ROOT.parents
assert ROOT.name.startswith('aba-accounting-runtime-')
blocked = []


def read_only(event, args):
    if event in {'open', 'os.listdir', 'os.scandir'} and source_data_path(args[0]):
        blocked.append({'event': event, 'target': 'repository data access forbidden'})
        raise PermissionError('Runtime cannot read or write repository data')
    if event == 'open':
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            blocked.append({'event': event, 'target': str(args[:2])})
            raise PermissionError('Report regression cannot write files')
    if event in {'os.mkdir', 'os.remove', 'os.rename', 'os.rmdir', 'os.chmod', 'os.chown', 'os.truncate', 'os.system', 'subprocess.Popen', 'socket.connect', 'socket.connect_ex', 'socket.bind', 'socket.getaddrinfo', 'socket.sendto'}:
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
from autonomous_betting_agent import local_users

# The real module resolves auth data relative to __file__, not the current cwd.
assert local_users.BASE_DATA_DIR == ROOT / 'data'
assert Path(sitecustomize.__file__).resolve() == ROOT / 'sitecustomize.py'
assert Path(usercustomize.__file__).resolve() == ROOT / 'usercustomize.py'
assert local_users.load_user_profile('owner').display_name == 'Synthetic accounting fixture'

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
