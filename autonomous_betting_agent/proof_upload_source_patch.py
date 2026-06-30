from __future__ import annotations

from typing import Any

import pandas as pd


def _has_value_series(frame: pd.DataFrame, column: str) -> bool:
    if column not in frame.columns:
        return False
    try:
        return bool(frame[column].map(lambda value: str(value or '').strip()).ne('').any())
    except Exception:
        return False


def _has_upload_identity(frame: pd.DataFrame) -> bool:
    if frame is None or frame.empty:
        return False
    if _has_value_series(frame, 'source_file'):
        return True
    if _has_value_series(frame, 'proof_source_type'):
        return True
    return False


def _status_mask(cpt: Any, frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=bool)
    grade_fields = [
        'verified_grade', 'verified_result', 'verified_status', 'verified_outcome',
        'grade', 'final_grade', 'proof_grade', 'pick_grade', 'row_grade',
        'result_grade', 'manual_grade', 'graded_result', 'win_loss',
    ]
    has_grade_source = any(field in frame.columns for field in grade_fields)
    if not has_grade_source:
        return pd.Series(False, index=frame.index)
    statuses = pd.Series([cpt.result_status(row) for row in frame.to_dict('records')], index=frame.index)
    return statuses.isin(['win', 'loss', 'void', 'pending'])


def install() -> None:
    try:
        from . import commercial_platform_tools as cpt
    except Exception:
        return
    if getattr(cpt, '_aba_upload_source_patch_v1', False):
        return

    def filter_locked_proof_rows(frame):
        raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
        out = cpt.update_profit_columns(raw) if raw is not None and not raw.empty else pd.DataFrame()
        if out.empty:
            return pd.DataFrame()
        proof_mask = pd.Series(False, index=out.index)
        if cpt.PROOF_REQUIRED_COLUMNS.issubset(out.columns):
            proof_mask = out['proof_id'].map(cpt.safe_text).ne('') & out['locked_at_utc'].map(cpt.safe_text).ne('')
        lock_mask = cpt._lock_ready_mask(out)
        if lock_mask.empty:
            lock_mask = pd.Series(False, index=out.index)
        grade_mask = _status_mask(cpt, out)
        mask = proof_mask | lock_mask.reindex(out.index, fill_value=False) | grade_mask.reindex(out.index, fill_value=False)
        if mask.empty or not bool(mask.any()):
            return pd.DataFrame()
        return cpt._ensure_lock_identity(out[mask].copy())

    def has_locked_proof_rows(frame) -> bool:
        return not filter_locked_proof_rows(frame).empty

    def latest_active_list(frame):
        out = filter_locked_proof_rows(frame)
        return out.copy() if not out.empty else pd.DataFrame()

    def _authoritative_last_upload(parts: list[pd.DataFrame]) -> pd.DataFrame | None:
        if len(parts) < 2:
            return None
        last = parts[-1]
        if last.empty or not _has_upload_identity(last):
            return None
        previous_max = max((len(part) for part in parts[:-1]), default=0)
        if len(last) >= previous_max:
            return last.copy()
        return None

    def merge_ledgers(*frames, active_only: bool = False):
        parts: list[pd.DataFrame] = []
        for frame in frames:
            if frame is None:
                continue
            raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
            if raw is None or raw.empty:
                continue
            proof_rows = filter_locked_proof_rows(raw)
            if not proof_rows.empty:
                parts.append(proof_rows)
        if not parts:
            return pd.DataFrame()
        authoritative = _authoritative_last_upload(parts)
        if authoritative is not None:
            out = authoritative
        else:
            out = pd.concat(parts, ignore_index=True, sort=False)
            out = cpt._sort_for_result_preservation(out)
            if 'proof_id' in out.columns:
                out = out.drop_duplicates(subset=['proof_id'], keep='last')
            cols = [col for col in ['event', 'prediction', 'event_start_utc', 'market_type', 'line_point'] if col in out.columns]
            if cols:
                out = out.drop_duplicates(subset=cols, keep='last')
            out = cpt._drop_helper_columns(out)
            out = filter_locked_proof_rows(out)
        return latest_active_list(out) if active_only else out

    cpt.filter_locked_proof_rows = filter_locked_proof_rows
    cpt.has_locked_proof_rows = has_locked_proof_rows
    cpt.latest_active_list = latest_active_list
    cpt.merge_ledgers = merge_ledgers
    cpt._aba_upload_source_patch_v1 = True
