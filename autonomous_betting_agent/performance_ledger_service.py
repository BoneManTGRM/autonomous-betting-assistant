import json
from typing import Any, Mapping, Sequence

import pandas as pd

from autonomous_betting_agent.profitability_metrics import profitability_summary
from autonomous_betting_agent.proof_performance_store import (
    PUBLIC_SAFE_FIELDS,
    SCHEMA_FIELDS,
    SCHEMA_VERSION,
    append_performance_rows as _append_performance_rows,
    build_duplicate_key,
    build_proof_id,
    build_row_hash,
    normalize_performance_record,
    read_performance_ledger as _read_performance_ledger,
    read_recent_rows as _read_recent_rows,
    read_workspace_rows as _read_workspace_rows,
    validate_ledger_integrity as _validate_ledger_integrity,
)


def append_performance_rows(
    rows: pd.DataFrame | Sequence[Mapping[str, Any]],
    workspace_id: str,
    source_key: str | None = None,
    source_file: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    return _append_performance_rows(rows, workspace_id, source_key=source_key, source_file=source_file, dry_run=dry_run)


def read_performance_ledger(workspace_id: str | None = None) -> pd.DataFrame:
    return _read_performance_ledger(workspace_id=workspace_id)


def read_workspace_rows(workspace_id: str) -> pd.DataFrame:
    frame = _read_workspace_rows(workspace_id)
    return frame if not frame.empty else _legacy_performance_frame(workspace_id)


def _workspace(value: Any) -> str:
    cleaned = str(value or "").strip().replace(" ", "_").lower()
    return cleaned or "default"


def _json_ready(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return [_json_ready(item) for item in value.to_dict(orient="records")]
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _legacy_performance_frame(workspace_id: str | None = None) -> pd.DataFrame:
    """Bridge the older Odds Lock proof ledger into the proof-package dashboard.

    The newer proof package stack reads proof_performance_ledger. Existing live
    deployments may still have their durable proof rows in the legacy persistent
    Odds Lock ledger. Treat those rows as ledger-backed dashboard rows instead of
    falling back to transient session rows.
    """
    workspace = _workspace(workspace_id)
    try:
        from autonomous_betting_agent.commercial_platform_tools import filter_locked_proof_rows, load_persistent_ledger
    except Exception:
        return pd.DataFrame(columns=SCHEMA_FIELDS)

    try:
        legacy = load_persistent_ledger(workspace_id=workspace, active_only=False)
        if legacy.empty and workspace != "default":
            legacy = load_persistent_ledger(active_only=False)
        locked = filter_locked_proof_rows(legacy)
    except Exception:
        return pd.DataFrame(columns=SCHEMA_FIELDS)
    if locked.empty:
        return pd.DataFrame(columns=SCHEMA_FIELDS)

    records: list[dict[str, Any]] = []
    for raw in locked.to_dict(orient="records"):
        row = dict(raw)
        source_key = str(row.get("source_key") or row.get("source_context") or "legacy_proof_ledger")
        source_file = str(row.get("source_file") or row.get("filename") or "legacy_persistent_ledger")
        record = normalize_performance_record(row, workspace, source_key=source_key, source_file=source_file)
        if not record.get("record_type"):
            record["record_type"] = "import"
        records.append(record)
    frame = pd.DataFrame(records)
    for field in SCHEMA_FIELDS:
        if field not in frame.columns:
            frame[field] = ""
    return frame[SCHEMA_FIELDS]


def _performance_or_legacy_frame(workspace_id: str | None = None) -> pd.DataFrame:
    frame = read_performance_ledger(workspace_id=workspace_id)
    if not frame.empty:
        return frame.copy(deep=True)
    return _legacy_performance_frame(workspace_id)


def read_recent_rows(workspace_id: str | None = None, limit: int = 100) -> pd.DataFrame:
    frame = _read_recent_rows(workspace_id=workspace_id, limit=limit)
    if frame.empty:
        frame = _legacy_performance_frame(workspace_id)
    if frame.empty:
        return frame
    ordered = frame.copy(deep=True)
    ordered["_seq"] = pd.to_numeric(ordered.get("ledger_sequence", 0), errors="coerce").fillna(0)
    return ordered.sort_values("_seq", ascending=False).drop(columns=["_seq"], errors="ignore").head(limit).reset_index(drop=True)


def _export_frame(workspace_id: str | None = None, public_safe: bool = False) -> pd.DataFrame:
    frame = _performance_or_legacy_frame(workspace_id)
    if public_safe:
        for field in PUBLIC_SAFE_FIELDS:
            if field not in frame.columns:
                frame[field] = ""
        return frame[PUBLIC_SAFE_FIELDS]
    return frame


def export_performance_csv(workspace_id: str | None = None, public_safe: bool = False) -> str:
    return _export_frame(workspace_id=workspace_id, public_safe=public_safe).to_csv(index=False)


def export_performance_json(workspace_id: str | None = None, public_safe: bool = False) -> str:
    frame = _export_frame(workspace_id=workspace_id, public_safe=public_safe)
    return json.dumps({"schema_version": SCHEMA_VERSION, "rows": _json_ready(frame.to_dict(orient="records"))}, indent=2, sort_keys=True)


def validate_ledger_integrity(workspace_id: str | None = None) -> dict[str, Any]:
    return _validate_ledger_integrity(workspace_id=workspace_id)


def _active_frame(frame: pd.DataFrame, include_corrections: bool = True) -> pd.DataFrame:
    if frame.empty or include_corrections:
        return frame.copy(deep=True)
    return frame[frame.get("record_type", "") != "correction"].copy(deep=True)


def rows_for_dashboard(workspace_id: str | None = None) -> pd.DataFrame:
    frame = _performance_or_legacy_frame(workspace_id)
    if frame.empty:
        return frame.copy(deep=True)
    rows = frame.copy(deep=True)
    rows["bookmaker"] = rows.get("sportsbook", "")
    rows["book"] = rows.get("sportsbook", "")
    rows["prediction"] = rows.get("pick", "")
    rows["public_pick"] = rows.get("pick", "")
    rows["public_event"] = rows.get("event", "")
    rows["model_market_edge"] = rows.get("edge", "")
    rows["expected_value_per_unit"] = rows.get("expected_value", "")
    rows["manual_clv"] = rows.get("clv", "")
    rows["decimal_price"] = rows.get("decimal_odds", "")
    rows["market"] = rows.get("market_type", "")
    return rows


def _last_updated(frame: pd.DataFrame) -> str:
    if frame.empty or "ingested_at_utc" not in frame.columns:
        return ""
    values = [str(value) for value in frame["ingested_at_utc"].tolist() if str(value).strip()]
    return max(values) if values else ""


def summarize_performance(workspace_id: str | None = None, include_corrections: bool = True) -> dict[str, Any]:
    ledger = _performance_or_legacy_frame(workspace_id=workspace_id)
    active = _active_frame(ledger, include_corrections=include_corrections)
    dashboard_rows = rows_for_dashboard(workspace_id=workspace_id)
    if not include_corrections and not dashboard_rows.empty:
        dashboard_rows = dashboard_rows[dashboard_rows.get("record_type", "") != "correction"].copy(deep=True)
    metrics = profitability_summary(dashboard_rows)
    integrity = validate_ledger_integrity(workspace_id=workspace_id)
    return {
        "total_rows": int(len(ledger)),
        "total_active_rows": int(len(active)),
        "unique_events": metrics.get("unique_event_count", 0),
        "duplicate_count": metrics.get("duplicate_count", 0),
        "correction_count": int((ledger.get("record_type", pd.Series(dtype=str)) == "correction").sum()) if not ledger.empty else 0,
        "wins": metrics.get("wins", 0),
        "losses": metrics.get("losses", 0),
        "pushes": metrics.get("pushes", 0),
        "cancels": metrics.get("cancels", 0),
        "win_rate_ex_push_cancel": metrics.get("win_rate_ex_push_cancel", 0.0),
        "profit_units": metrics.get("profit_units", 0.0),
        "risked_units": metrics.get("risked_units", 0.0),
        "roi": metrics.get("roi", 0.0),
        "average_odds": metrics.get("average_odds"),
        "average_edge": metrics.get("average_edge"),
        "average_no_vig_edge": metrics.get("average_no_vig_edge"),
        "average_clv": metrics.get("average_clv"),
        "playable_roi": metrics.get("playable_pick_roi", {}),
        "watchlist_roi": metrics.get("watchlist_pick_roi", {}),
        "avoid_tracking_result": metrics.get("avoid_pick_tracking_result", {}),
        "duplicate_adjusted_record": metrics.get("duplicate_adjusted_record", {}),
        "last_updated_timestamp": _last_updated(ledger),
        "schema_version": SCHEMA_VERSION,
        "ledger_integrity_status": integrity.get("status", "PASS"),
        "ledger_integrity": integrity,
    }
