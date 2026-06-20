from __future__ import annotations

import ast
import py_compile
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_STREAMLIT_ASSIGNMENTS = {
    'button',
    'download_button',
    'file_uploader',
    'form',
    'form_submit_button',
    'number_input',
    'multiselect',
    'radio',
    'selectbox',
}


def iter_python_files() -> list[Path]:
    ignored_parts = {'.git', '.venv', 'venv', '__pycache__'}
    files: list[Path] = []
    for path in ROOT.rglob('*.py'):
        if ignored_parts.intersection(path.parts):
            continue
        files.append(path)
    return sorted(files)


def compile_all_python() -> None:
    for path in iter_python_files():
        py_compile.compile(str(path), doraise=True)


def scan_for_widget_monkey_patches() -> None:
    violations: list[str] = []
    for path in iter_python_files():
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets.extend(node.targets)
            elif isinstance(node, ast.AnnAssign):
                targets.append(node.target)
            elif isinstance(node, ast.AugAssign):
                targets.append(node.target)
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr in FORBIDDEN_STREAMLIT_ASSIGNMENTS:
                    owner = ast.unparse(target.value) if hasattr(ast, 'unparse') else ''
                    if owner in {'st', 'streamlit', 'DeltaGenerator', 'st.sidebar'} or 'DeltaGenerator' in owner:
                        violations.append(f'{path.relative_to(ROOT)}:{node.lineno} assigns {owner}.{target.attr}')
    if violations:
        raise AssertionError('Forbidden Streamlit widget monkey-patch assignments:\n' + '\n'.join(violations))


def test_large_list_defaults() -> None:
    from autonomous_betting_agent.pro_predictor_defaults_patch import MULTI_DEFAULTS, PROFILE_VALUES

    expected = {
        'baseline_accuracy_min_books': 1,
        'baseline_accuracy_min_model_prob': 0.58,
        'baseline_accuracy_min_edge': -0.03,
        'baseline_accuracy_strong_edge': 0.04,
        'baseline_accuracy_min_strength': 38.0,
        'baseline_accuracy_use_high_conf': False,
        'baseline_accuracy_max_high_conf': 300,
        'baseline_accuracy_min_high_prob': 0.58,
        'baseline_accuracy_min_high_edge': -0.03,
        'baseline_accuracy_min_high_strength': 38.0,
        'baseline_accuracy_min_high_agent': 35.0,
    }
    for key, value in expected.items():
        if PROFILE_VALUES.get(key) != value:
            raise AssertionError(f'{key} expected {value!r}, got {PROFILE_VALUES.get(key)!r}')
    if MULTI_DEFAULTS.get('Bookmaker regions') != ['us', 'us2', 'eu', 'uk']:
        raise AssertionError('Bookmaker regions defaults changed unexpectedly')


def test_locked_pick_persistence() -> None:
    from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, save_persistent_ledger
    from autonomous_betting_agent.pick_hold_store import load_held_rows

    row = {
        'proof_id': 'smoke-proof-001',
        'proof_hash': 'smoke-hash-001',
        'locked_at_utc': '2099-01-01T00:00:00Z',
        'event_start_utc': '2099-01-02T00:00:00Z',
        'event': 'Smoke Away at Smoke Home',
        'prediction': 'Smoke Home',
        'market_type': 'h2h',
        'model_probability': 0.61,
        'decimal_price': 1.91,
        'stake_units': 1.0,
        'result_status': 'pending',
    }
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / 'ledger.csv'
        saved = save_persistent_ledger(pd.DataFrame([row]), path=path, workspace_id='smoke_test')
        if saved.empty or len(saved) != 1:
            raise AssertionError('save_persistent_ledger did not keep the locked row')
        loaded = load_persistent_ledger(path=path, workspace_id='smoke_test')
        if loaded.empty or 'smoke-proof-001' not in set(loaded['proof_id'].astype(str)):
            raise AssertionError('load_persistent_ledger did not reload the locked row')
        held = load_held_rows('odds_lock_pro_locked_rows', 'smoke_test')
        if not held:
            raise AssertionError('locked rows were not written to hold store')


def test_core_modules_import() -> None:
    import autonomous_betting_agent.commercial_platform_tools  # noqa: F401
    import autonomous_betting_agent.pick_hold_store  # noqa: F401
    import autonomous_betting_agent.pro_predictor_defaults_patch  # noqa: F401
    import autonomous_betting_agent.sidebar_nav  # noqa: F401
    import autonomous_betting_agent.tool_sidebar  # noqa: F401


def main() -> None:
    compile_all_python()
    scan_for_widget_monkey_patches()
    test_core_modules_import()
    test_large_list_defaults()
    test_locked_pick_persistence()
    print('SMOKE_SCAN_OK')


if __name__ == '__main__':
    main()
