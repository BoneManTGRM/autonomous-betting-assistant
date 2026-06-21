from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .learning import fit_probability_calibrator
from .learning_memory_tools import (
    build_memory_bank,
    build_segments,
    calibrator_json,
    clean_key,
    compact_row,
    make_ara_memory_csv,
    merge_dedupe_rows,
    prune_rows,
    read_compact_csv_bytes,
    rows_to_graded,
    valid_bank_row,
)
from .pick_hold_store import load_held_rows, normalize_workspace_id

REPO_ROOT = Path(__file__).resolve().parents[1]
LEARNED_STATE_PATH = REPO_ROOT / 'learned_state.json'
MEMORY_BANK_PATH = REPO_ROOT / 'data' / 'learning_memory_bank.json'
ARA_MEMORY_PATH = REPO_ROOT / 'data' / 'ara_learning_memory.csv'
AUTO_REPORT_PATH = REPO_ROOT / 'data' / 'auto_learning_cycle_report.json'
DEFAULT_REPO = 'BoneManTGRM/autonomous-betting-agent'
DEFAULT_BRANCH = 'main'
PROOF_SOURCES = ('odds_lock_pro_locked_rows', 'public_proof_dashboard_refresh_rows')


def _secret(*names: str) -> str:
    try:
        import streamlit as st
        for name in names:
            value = str(st.secrets.get(name, '')).strip()
            if value:
                return value
    except Exception:
        pass
    for name in names:
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


def _load_existing_rows() -> list[dict[str, Any]]:
    try:
        bank = json.loads(MEMORY_BANK_PATH.read_text(encoding='utf-8')) if MEMORY_BANK_PATH.exists() else {'compact_rows': []}
    except Exception:
        bank = {'compact_rows': []}
    return [row for row in (valid_bank_row(row) for row in bank.get('compact_rows', [])) if row]


def _compact_from_rows(rows: list[dict[str, Any]], source: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    stats = {'input_rows': 0, 'usable_rows': 0, 'missing_probability': 0, 'missing_result': 0, 'fallback_probability_rows': 0, 'price_implied_probability_rows': 0, 'direct_probability_rows': 0, 'wins': 0, 'losses': 0}
    compact: list[dict[str, Any]] = []
    for row_number, raw in enumerate(rows, start=2):
        stats['input_rows'] += 1
        normalized = {clean_key(k): v for k, v in dict(raw).items() if k is not None}
        item = compact_row(normalized, row_number, source)
        if item is None:
            # Run the CSV parser fallback on a one-row CSV-like payload only when needed is too expensive;
            # compact_row already covers the same column rules used by Learning Memory.
            continue
        source_name = str(item.get('probability_source') or '')
        if source_name.startswith('fallback_'):
            stats['fallback_probability_rows'] += 1
        elif source_name == 'price_implied':
            stats['price_implied_probability_rows'] += 1
        else:
            stats['direct_probability_rows'] += 1
        stats['usable_rows'] += 1
        stats['wins'] += int(int(item['outcome']) == 1)
        stats['losses'] += int(int(item['outcome']) == 0)
        compact.append(item)
    stats['missing_probability'] = max(0, stats['input_rows'] - stats['usable_rows'])
    return compact, stats


def collect_resolved_training_rows(workspace_id: Any = 'test_01') -> tuple[list[dict[str, Any]], dict[str, Any]]:
    workspace = normalize_workspace_id(workspace_id)
    rows: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    for key in PROOF_SOURCES:
        loaded = load_held_rows(key, workspace)
        source_counts[key] = len(loaded)
        rows.extend(loaded)
    compact, stats = _compact_from_rows(rows, f'auto_learning_cycle:{workspace}')
    return compact, {'workspace_id': workspace, 'source_counts': source_counts, 'parse_stats': stats}


def _save_github(path: str, content: str, message: str) -> bool:
    token = _secret('GITHUB_TOKEN', 'GH_TOKEN')
    repo = _secret('GITHUB_REPOSITORY') or DEFAULT_REPO
    branch = _secret('GITHUB_BRANCH') or DEFAULT_BRANCH
    if not token or not repo:
        return False
    url = f'https://api.github.com/repos/{repo}/contents/{path}'
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    sha = None
    try:
        existing = requests.get(url, headers=headers, params={'ref': branch}, timeout=20)
        if existing.status_code == 200:
            sha = existing.json().get('sha')
        body: dict[str, Any] = {'message': message, 'branch': branch, 'content': base64.b64encode(content.encode('utf-8')).decode('ascii')}
        if sha:
            body['sha'] = sha
        response = requests.put(url, headers=headers, json=body, timeout=30)
        return response.status_code in {200, 201}
    except Exception:
        return False


def run_auto_learning_cycle(
    workspace_id: Any = 'test_01',
    *,
    min_new_rows: int = 5,
    min_total_rows: int = 10,
    max_rows: int = 50000,
    min_patterns: int = 3,
    max_patterns: int = 500,
    save_to_github: bool = True,
) -> dict[str, Any]:
    workspace = normalize_workspace_id(workspace_id)
    existing_rows = _load_existing_rows()
    uploaded_rows, collection = collect_resolved_training_rows(workspace)
    merged_rows, duplicates_removed = merge_dedupe_rows(existing_rows, uploaded_rows)
    new_unique_rows = max(0, len(merged_rows) - len(existing_rows))
    report: dict[str, Any] = {
        'version': 'auto-learning-cycle-v1',
        'workspace_id': workspace,
        'ran_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'existing_rows': len(existing_rows),
        'collected_usable_rows': len(uploaded_rows),
        'new_unique_rows': new_unique_rows,
        'duplicates_removed': duplicates_removed,
        **collection,
    }
    if len(merged_rows) < int(min_total_rows):
        report.update({'status': 'skipped', 'reason': 'not_enough_total_resolved_rows', 'rows_after_merge': len(merged_rows), 'required_total_rows': int(min_total_rows)})
        AUTO_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        AUTO_REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        return report
    if new_unique_rows < int(min_new_rows):
        report.update({'status': 'skipped', 'reason': 'not_enough_new_rows', 'rows_after_merge': len(merged_rows), 'required_new_rows': int(min_new_rows)})
        AUTO_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        AUTO_REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        return report
    pruned_rows, prune_report = prune_rows(merged_rows, int(max_rows))
    calibrator = fit_probability_calibrator(rows_to_graded(pruned_rows), min_events=int(min_total_rows), source=f'auto_learning_cycle:{workspace}')
    segments = build_segments(pruned_rows, int(min_patterns), int(max_patterns))
    ara_csv = make_ara_memory_csv(segments)
    memory_bank = build_memory_bank(
        compact_rows=pruned_rows,
        calibrator=calibrator,
        segments=segments,
        parse_stats=dict(collection.get('parse_stats') or {}),
        prune_report=prune_report,
        mode='auto_merge',
        existing_count=len(existing_rows),
        uploaded_count=len(uploaded_rows),
        duplicates_removed=duplicates_removed,
    )
    memory_bank['summary']['auto_learning_cycle'] = True
    memory_bank['summary']['workspace_id'] = workspace
    MEMORY_BANK_PATH.parent.mkdir(parents=True, exist_ok=True)
    learned_json = calibrator_json(calibrator)
    memory_json = json.dumps(memory_bank, indent=2, sort_keys=True) + '\n'
    LEARNED_STATE_PATH.write_text(learned_json, encoding='utf-8')
    MEMORY_BANK_PATH.write_text(memory_json, encoding='utf-8')
    ARA_MEMORY_PATH.write_text(ara_csv, encoding='utf-8')
    github_saved = False
    if save_to_github:
        today = datetime.now(timezone.utc).date().isoformat()
        ok1 = _save_github('learned_state.json', learned_json, f'Auto-update learned calibration {today}')
        ok2 = _save_github('data/learning_memory_bank.json', memory_json, f'Auto-update learning memory {today}')
        ok3 = _save_github('data/ara_learning_memory.csv', ara_csv, f'Auto-update ARA memory patterns {today}')
        github_saved = bool(ok1 and ok2 and ok3)
    report.update({
        'status': 'trained',
        'rows_after_merge': len(merged_rows),
        'rows_after_pruning': len(pruned_rows),
        'patterns_saved': len(segments),
        'github_saved': github_saved,
        'learning_summary': memory_bank.get('summary', {}),
    })
    AUTO_REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return report
