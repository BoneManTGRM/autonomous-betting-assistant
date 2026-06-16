from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Mapping

import pandas as pd

from .commercial_platform_tools import DEFAULT_LEDGER_PATH, load_persistent_ledger, proof_audit_summary
from .live_odds import looks_like_placeholder_key

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_PAGES = [
    'pages/scanner_pro.py',
    'pages/pro_predictor.py',
    'pages/what_are_the_odds.py',
    'pages/odds_lock_pro.py',
    'pages/public_proof_dashboard.py',
    'pages/learn_memory.py',
]
OPTIONAL_PAGES = [
    'pages/00_start_here.py',
    'pages/01_tool_command_center.py',
    'pages/02_daily_operator_checklist.py',
    'pages/03_private_beta_sales_dashboard.py',
    'pages/04_game_intelligence_center.py',
    'pages/deployment_health.py',
    'pages/auto_result_grading.py',
    'pages/daily_workflow.py',
    'pages/buyer_demo_mode.py',
    'pages/monthly_license_readiness.py',
]
KEY_GROUPS = {
    'Odds data': ['THE_ODDS_API_KEY', 'ODDS_API_KEY'],
    'Sports context': ['SPORTSDATAIO_API_KEY'],
    'Weather context': ['WEATHERAPI_KEY', 'WEATHER_API_KEY'],
    'Repository save': ['GITHUB_TOKEN', 'GH_TOKEN'],
}


def secret_status(value: Any) -> str:
    text = str(value or '').strip()
    if not text:
        return 'missing'
    if looks_like_placeholder_key(text):
        return 'placeholder_or_invalid'
    return 'configured'


def _configured(names: list[str], getter: Callable[[str], Any] | None = None) -> tuple[str, str]:
    for name in names:
        value = ''
        if getter is not None:
            try:
                value = str(getter(name) or '').strip()
            except Exception:
                value = ''
        if not value:
            value = os.getenv(name, '').strip()
        status = secret_status(value)
        if status != 'missing':
            return name, status
    return names[0], 'missing'


def api_status_frame(getter: Callable[[str], Any] | None = None) -> pd.DataFrame:
    rows = []
    for label, names in KEY_GROUPS.items():
        name, status = _configured(names, getter)
        rows.append({'component': label, 'name': name, 'status': status})
    return pd.DataFrame(rows)


def file_status_frame(root: Path = REPO_ROOT) -> pd.DataFrame:
    rows = []
    for path in CORE_PAGES + OPTIONAL_PAGES:
        rows.append({'path': path, 'status': 'present' if (root / path).exists() else 'missing', 'core': path in CORE_PAGES})
    return pd.DataFrame(rows)


def ledger_status(path: Path = DEFAULT_LEDGER_PATH) -> dict[str, Any]:
    ledger = load_persistent_ledger(path)
    audit = proof_audit_summary(ledger)
    return {
        'ledger_file_exists': bool(path.exists()),
        'locked_rows': int(len(ledger)),
        'proof_quality_score': audit.get('proof_quality_score', 0.0),
        'needs_review': audit.get('needs_review', 0),
        'hash_mismatch': audit.get('hash_mismatch', 0),
    }


def deployment_summary(getter: Callable[[str], Any] | None = None, root: Path = REPO_ROOT, ledger_path: Path = DEFAULT_LEDGER_PATH) -> dict[str, Any]:
    api = api_status_frame(getter)
    files = file_status_frame(root)
    ledger = ledger_status(ledger_path)
    missing_core = int(files[(files['core'] == True) & (files['status'] != 'present')].shape[0])
    odds_status = str(api.loc[api['component'].eq('Odds data'), 'status'].iloc[0]) if not api.empty else 'missing'
    score = 100
    if odds_status != 'configured':
        score -= 25
    score -= missing_core * 20
    score -= int(ledger.get('needs_review', 0)) * 5
    score -= int(ledger.get('hash_mismatch', 0)) * 10
    score = max(0, min(100, score))
    status = 'healthy' if score >= 85 else 'usable_with_warnings' if score >= 60 else 'needs_attention'
    return {'deployment_status': status, 'deployment_score': score, 'odds_data_status': odds_status, 'missing_core_pages': missing_core, **ledger}


def action_items(summary: Mapping[str, Any]) -> list[str]:
    items = []
    if summary.get('odds_data_status') != 'configured':
        items.append('Add the real odds-data key in Streamlit secrets before running live scans.')
    if int(summary.get('missing_core_pages', 0)) > 0:
        items.append('Restore missing core pages.')
    if int(summary.get('hash_mismatch', 0)) > 0:
        items.append('Review proof hash mismatches in the proof audit tab.')
    if int(summary.get('locked_rows', 0)) == 0:
        items.append('Create and save locked proof rows.')
    elif int(summary.get('locked_rows', 0)) < 25:
        items.append('Keep collecting future-only locked proof rows before charging monthly clients.')
    if float(summary.get('proof_quality_score', 0.0) or 0.0) < 90 and int(summary.get('locked_rows', 0)) > 0:
        items.append('Improve proof quality before using the dashboard in a paid client pitch.')
    if not items:
        items.append('Deployment looks ready for the no-password daily workflow and monthly-license review.')
    return items
