from __future__ import annotations

from typing import Any

import pandas as pd


def install() -> None:
    try:
        import autonomous_betting_agent.report_studio_service as rss
        from autonomous_betting_agent.row_normalizer import result_status, safe_text
    except Exception:
        return
    if getattr(rss, '_ABA_REPORT_STUDIO_FRESH_LEDGER_GUARD_V1', False):
        return
    original_build_state = rss.build_report_studio_state

    def _mode(source_note: str) -> str:
        try:
            return rss._source_mode(source_note)
        except Exception:
            return 'none'

    def _frame(rows: Any) -> pd.DataFrame:
        if rows is None:
            return pd.DataFrame()
        if isinstance(rows, pd.DataFrame):
            return rows.copy()
        try:
            return pd.DataFrame(list(rows))
        except Exception:
            return pd.DataFrame()

    def _dt(frame: pd.DataFrame, names: tuple[str, ...]) -> pd.Series:
        out = pd.Series(pd.NaT, index=frame.index, dtype='datetime64[ns, UTC]')
        for name in names:
            if name in frame.columns:
                parsed = pd.to_datetime(frame[name], errors='coerce', utc=True)
                out = out.where(out.notna(), parsed)
        return out

    def _fresh_rows(rows: Any, source_note: str) -> tuple[Any, dict[str, Any]]:
        frame = _frame(rows)
        meta = {
            'report_source_selection_policy': 'freshest_locked_batch_v1',
            'stale_source_blocked': False,
            'source_selection_reason': 'not_ledger_source',
            'newest_locked_at_utc': '',
            'newest_event_start_utc': '',
        }
        if frame.empty or _mode(source_note) != 'ledger-history' or 'locked_at_utc' not in frame.columns:
            return rows, meta
        locked = _dt(frame, ('locked_at_utc',))
        starts = _dt(frame, ('event_start_utc', 'event_start_time', 'commence_time', 'start_time'))
        proof = frame.get('proof_status', pd.Series('', index=frame.index)).map(safe_text).str.lower()
        ledger = frame.get('ledger_type', pd.Series('', index=frame.index)).map(safe_text).str.lower()
        research = ledger.str.contains('research', na=False) | frame.get('research_lock_ready', pd.Series(False, index=frame.index)).astype(str).str.lower().isin({'true', '1', 'yes'})
        statuses = frame.apply(lambda row: result_status(row.to_dict()), axis=1)
        valid = locked.notna() & (proof.eq('locked_before_start') | research)
        pending_or_future = statuses.isin({'pending', 'unknown', 'scheduled', 'live', 'needs_review', ''}) | starts.gt(pd.Timestamp.utcnow())
        candidates = frame[valid & pending_or_future].copy()
        candidate_locks = locked[valid & pending_or_future]
        if candidates.empty:
            meta['source_selection_reason'] = 'no_pending_future_locked_batch'
            return rows, meta
        newest = candidate_locks.max()
        fresh = candidates[candidate_locks.reindex(candidates.index).ge(newest - pd.Timedelta(minutes=30))].copy()
        fresh_starts = starts.reindex(fresh.index)
        meta.update({
            'stale_source_blocked': bool(len(fresh) < len(frame)),
            'source_selection_reason': 'freshest_locked_batch_selected_stale_rows_blocked' if len(fresh) < len(frame) else 'freshest_locked_batch_selected',
            'newest_locked_at_utc': newest.isoformat() if pd.notna(newest) else '',
            'newest_event_start_utc': fresh_starts.max().isoformat() if not fresh_starts.empty and pd.notna(fresh_starts.max()) else '',
        })
        return fresh.reset_index(drop=True), meta

    def build_state_fresh_first(raw_rows: Any, brand: Any, *, filters: Any = None, source_note: str = ''):
        selected_rows, meta = _fresh_rows(raw_rows, source_note)
        state = original_build_state(selected_rows, brand, filters=filters, source_note=source_note)
        try:
            if meta.get('stale_source_blocked'):
                object.__setattr__(state, 'context_note', state.context_note + ' · Fresh locked ledger batch selected; older rows blocked.')
        except Exception:
            pass
        return state

    rss.build_report_studio_state = build_state_fresh_first
    rss._ABA_REPORT_STUDIO_FRESH_LEDGER_GUARD_V1 = True
