from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from autonomous_betting_agent.odds_lock_tools import (
    lock_status,
    now_utc,
    parse_datetime_utc,
    profit_units,
    proof_hash,
    proof_id_from_hash,
)


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _first_float(row: Mapping[str, Any], names: list[str]) -> float | None:
    for name in names:
        value = _safe_float(row.get(name))
        if value is not None:
            return value
    return None


def _stake_units(row: Mapping[str, Any], *, max_units: float) -> float:
    incoming = _first_float(row, ["stake_units", "recommended_stake_units"])
    if incoming is None or incoming <= 0:
        incoming = 1.0
    return round(max(0.0, min(float(max_units), incoming)), 2)


def build_all_reviewed_high_confidence_locks(
    frame: pd.DataFrame,
    *,
    analyst: str,
    max_units: float,
    workspace_id: str,
) -> pd.DataFrame:
    """Lock every reviewed row for internal testing.

    This is intentionally less strict than official +EV and research/test future-only
    locking. It preserves large test samples while marking the ledger as internal
    so non-future-safe rows do not pollute official public proof.
    """

    if frame is None or frame.empty:
        return pd.DataFrame()

    locked_time = now_utc()
    locked_dt = parse_datetime_utc(locked_time)
    rows: list[dict[str, Any]] = []

    for row in frame.to_dict(orient="records"):
        item = dict(row)
        item["locked_at_utc"] = locked_time
        item["analyst"] = analyst or "private_analyst"
        item["test_window_id"] = workspace_id
        item["ledger_type"] = "all_reviewed_high_confidence_internal_test"
        item["official_ev_pick"] = False
        item["official_lock_ready"] = False
        item["research_lock_ready"] = False
        item["all_reviewed_high_confidence_lock"] = True
        item["lock_blockers"] = ""
        item["stake_units"] = _stake_units(item, max_units=max_units)
        item["proof_status"] = lock_status(item, locked_at=locked_dt)
        item["public_confidence"] = "High Confidence / Internal Test"
        item["public_reason"] = (
            "All reviewed high-confidence row accepted for internal testing. "
            "Use proof_status/valid_before_start for public proof claims."
        )
        item["profit_units"] = profit_units(item)
        item["proof_hash"] = proof_hash(item)
        item["proof_id"] = proof_id_from_hash(item["proof_hash"])
        rows.append(item)

    return pd.DataFrame(rows)
