"""Compatibility entry point for observation-only learning-readiness review.

The former fitting/persistence behavior is intentionally disabled. Existing
weights and history are never normalized, deduplicated, pruned or overwritten.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .learning_evidence_admission import load_evidence_json, review_learning_records

REPO_ROOT = Path(__file__).resolve().parents[1]
LEARNED_STATE_PATH = REPO_ROOT / 'learned_state.json'
MEMORY_BANK_PATH = REPO_ROOT / 'data' / 'learning_memory_bank.json'
ARA_MEMORY_PATH = REPO_ROOT / 'data' / 'ara_learning_memory.csv'
AUTO_REPORT_PATH = REPO_ROOT / 'data' / 'auto_learning_cycle_report.json'
PROOF_SOURCES = ('odds_lock_pro_locked_rows', 'public_proof_dashboard_refresh_rows')


def _workspace(value: Any) -> str:
    text = str(value or 'test_01').strip().lower()
    text = ''.join(char if char.isalnum() or char in {'-', '_'} else '_' for char in text)
    return '_'.join(part for part in text.split('_') if part)[:48] or 'test_01'


def _json_rows(path: Path, field: str) -> list[Any]:
    if not path.exists():
        return []
    payload = load_evidence_json(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict) or not isinstance(payload.get(field), list):
        raise ValueError(f'{path.name}: expected an object containing a {field} list')
    return payload[field]


def _load_existing_rows() -> list[Any]:
    return _json_rows(MEMORY_BANK_PATH, 'compact_rows')


def collect_resolved_training_rows(workspace_id: Any = 'test_01') -> tuple[list[Any], dict[str, Any]]:
    """Read local raw snapshots, not lossy normalizers or remote/cache loaders.

    The name remains compatible. Pending/malformed records are deliberately
    retained for indexed rejection instead of being silently discarded.
    """
    workspace = _workspace(workspace_id)
    rows: list[Any] = []
    counts: dict[str, int] = {}
    errors: list[str] = []
    data = REPO_ROOT / 'data'
    suffix = '' if workspace in {'default', 'shared', 'main'} else f'_{workspace}'
    ledger = data / f'odds_lock_pro_ledger{suffix}.csv'
    try:
        if ledger.exists():
            with ledger.open(encoding='utf-8-sig', newline='') as handle:
                reader = csv.DictReader(handle)
                headers = reader.fieldnames or []
                normalized = [str(key).strip().lower().replace('-', '_').replace(' ', '_') for key in headers]
                if any(not key for key in normalized) or len(set(normalized)) != len(headers):
                    raise ValueError('duplicate CSV headers')
                original = list(reader)
                if any(None in row or any(value is None for value in row.values()) for row in original):
                    raise ValueError('CSV row/header length mismatch')
            counts[ledger.name] = len(original)
            rows.extend(original)
    except (OSError, ValueError, csv.Error) as exc:
        errors.append(f'{ledger.name}: {exc}')
    for key in PROOF_SOURCES:
        # Review both original local snapshots. Duplicate evidence is counted,
        # never used to inflate unique-event readiness or silently reconciled.
        for suffix in ('.json', '.backup.json'):
            path = data / f'held_picks_{workspace}_{key}{suffix}'
            try:
                original = _json_rows(path, 'rows')
                counts[path.name] = len(original)
                rows.extend(original)
            except (OSError, ValueError) as exc:
                errors.append(f'{path.name}: {exc}')
    return rows, {'workspace_id': workspace, 'source_counts': counts, 'source_errors': errors,
                  'learning_scope': 'local_raw_snapshots_only',
                  'coverage_note': 'Remote-only, session-only and SQLite-only records were not audited; no remote fetch or cache update was attempted.'}


def run_auto_learning_cycle(workspace_id: Any = 'test_01', *, min_new_rows: int = 5,
                            min_total_rows: int = 10, max_rows: int = 50000,
                            min_patterns: int = 3, max_patterns: int = 500,
                            save_to_github: bool = True) -> dict[str, Any]:
    """Return readiness only—even for complete claims or the 1-new/5-total call.

    Legacy tuning/publishing arguments remain accepted for caller compatibility;
    none permits fitting, pruning, artifact writes, or publication.
    """
    errors = []
    try:
        existing = _load_existing_rows()
    except (OSError, ValueError) as exc:
        existing = []
        errors.append(f'existing memory could not be reviewed: {exc}')
    collected, collection = collect_resolved_training_rows(workspace_id)
    report = review_learning_records([*existing, *collected], minimum_events=min_total_rows)
    report.update(collection)
    report.update({'existing_rows': len(existing), 'collected_rows': len(collected),
                   'github_saved': False, 'requested_min_new_rows': min_new_rows,
                   'legacy_write_options_ignored': True})
    errors.extend(collection.get('source_errors', []))
    if errors:
        report['status'] = 'BLOCKED'
        report['batch_admitted'] = False
        report['reason'] += '; source coverage incomplete: ' + '; '.join(errors)
    report['source_errors'] = errors
    return report
