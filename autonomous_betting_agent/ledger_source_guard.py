from __future__ import annotations

import pandas as pd

MIN_KEEP_RATIO = 0.85


def install() -> None:
    try:
        from . import commercial_platform_tools as tools
    except Exception:
        return
    if getattr(tools, '_aba_ledger_source_guard_v1', False):
        return

    original_merge = tools.merge_ledgers

    def _part(value) -> pd.DataFrame:
        if value is None:
            return pd.DataFrame()
        raw = pd.DataFrame(value) if isinstance(value, list) else value
        if raw is None or raw.empty:
            return pd.DataFrame()
        return tools.filter_locked_proof_rows(raw)

    def merge_ledgers(*values, active_only: bool = False):
        parts = [part for part in (_part(value) for value in values) if not part.empty]
        merged = original_merge(*values, active_only=False)
        if parts:
            largest = max(parts, key=lambda part: len(part)).copy()
            minimum_rows = int(len(largest) * MIN_KEEP_RATIO)
            if merged.empty or len(merged) < minimum_rows:
                merged = largest
        return tools.latest_active_list(merged) if active_only else merged

    tools.merge_ledgers = merge_ledgers
    tools._aba_ledger_source_guard_v1 = True
