"""Phase 3A Reparodynamics audit log helpers.

This module records observation-only audit events from real graded rows or
runner reports. It never activates live repairs, Shadow Mode, TGRM, RYE scoring,
confidence changes, bet-tier changes, bankroll changes, sportsbook changes, or
model mutation.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.adaptive_repair_runner_core import (
    AdaptiveRunnerReport,
    build_runner_report,
    hash_rows,
    uploaded_source,
    utc_timestamp,
)
from autonomous_betting_agent.reparodynamics_doctrine import get_reparodynamics_doctrine

REPARODYNAMICS_AUDIT_SCHEMA_VERSION = "reparodynamics_audit_phase_3a_v1"
REPARODYNAMICS_AUDIT_LOG_PATH = Path("data/adaptive_repair/reparodynamics_audit_log.jsonl")
REPARODYNAMICS_AUDIT_LATEST_PATH = Path("data/adaptive_repair/reparodynamics_audit_latest.json")
PHASE_3A_BLOCK_REASON = "Phase 3A observation-only"


@dataclass(frozen=True)
class ReparodynamicsAuditEvent:
    """Single observation-only audit event for the Reparodynamics page."""

    schema_version: str
    timestamp: str
    source: str
    rows_scanned: int
    unique_events_scanned: int
    duplicates_detected: int
    new_patterns_detected: int
    drift_detected: bool
    repair_candidates_generated: int
    shadow_mode: str
    live_mutation: str
    reason: str
    repair_activation: str = "OFF"
    tgrm_activation: str = "OFF"
    rye_activation: str = "OFF"
    confidence_changes: str = "OFF"
    bet_tier_changes: str = "OFF"
    bankroll_changes: str = "OFF"
    sportsbook_changes: str = "OFF"
    model_mutation: str = "FORBIDDEN"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def _row_event_gap(base_report: Mapping[str, Any]) -> float:
    row = base_report.get("row_level", {}) or {}
    event = base_report.get("unique_event_level", {}) or {}
    row_rate = row.get("win_rate")
    event_rate = event.get("win_rate")
    if row_rate is None or event_rate is None:
        return 0.0
    return abs(_to_float(row_rate) - _to_float(event_rate))


def observation_only_drift_detected(
    diagnostics: Mapping[str, Any],
    *,
    pattern_count: int,
    duplicates_detected: int,
    row_event_gap_threshold: float = 0.05,
) -> bool:
    """Return whether the observation-only audit sees drift or drift risk.

    This is a safety signal only. It does not authorize or apply repairs.
    """

    base = diagnostics.get("base_report", {}) or {}
    quality = diagnostics.get("data_quality", {}) or {}
    penalties = quality.get("penalties", []) or []
    mixed_events = _to_int(diagnostics.get("mixed_outcome_events"))
    gap = _row_event_gap(base)
    return bool(pattern_count or duplicates_detected or mixed_events or penalties or gap >= row_event_gap_threshold)


def _duplicates_detected(base_report: Mapping[str, Any], diagnostics: Mapping[str, Any]) -> int:
    total_rows = _to_int(base_report.get("total_rows"))
    event = base_report.get("unique_event_level", {}) or {}
    unique_events = _to_int(event.get("unique_events"))
    row_minus_event = max(total_rows - unique_events, 0)
    exact_duplicate_rows = _to_int(diagnostics.get("duplicate_rows"))
    duplicate_event_names = _to_int(base_report.get("duplicate_event_names"))
    duplicate_event_keys = _to_int(base_report.get("duplicate_event_keys"))
    return max(row_minus_event, exact_duplicate_rows, duplicate_event_names, duplicate_event_keys)


def audit_event_from_runner_report(
    report: AdaptiveRunnerReport,
    *,
    source: str | None = None,
) -> ReparodynamicsAuditEvent:
    """Build the visible Reparodynamics audit event from a runner report."""

    data = report.to_dict()
    diagnostics = data.get("diagnostics", {}) or {}
    base = diagnostics.get("base_report", {}) or {}
    event = base.get("unique_event_level", {}) or {}
    doctrine = get_reparodynamics_doctrine()

    rows_scanned = _to_int(base.get("total_rows"))
    unique_events_scanned = _to_int(event.get("unique_events"))
    duplicates = _duplicates_detected(base, diagnostics)
    patterns = len(data.get("pattern_candidates", []) or [])
    drift = observation_only_drift_detected(
        diagnostics,
        pattern_count=patterns,
        duplicates_detected=duplicates,
    )

    return ReparodynamicsAuditEvent(
        schema_version=REPARODYNAMICS_AUDIT_SCHEMA_VERSION,
        timestamp=str(data.get("timestamp") or utc_timestamp()),
        source=source or _source_label_from_report(data),
        rows_scanned=rows_scanned,
        unique_events_scanned=unique_events_scanned,
        duplicates_detected=duplicates,
        new_patterns_detected=patterns,
        drift_detected=drift,
        repair_candidates_generated=patterns,
        shadow_mode=str(doctrine.get("shadow_mode_activation", "OFF")),
        live_mutation=str(doctrine.get("live_mutation", "Forbidden")),
        reason=PHASE_3A_BLOCK_REASON,
        repair_activation=str(doctrine.get("repair_activation", "OFF")),
        tgrm_activation=str(doctrine.get("tgrm_activation", "OFF")),
        rye_activation=str(doctrine.get("rye_activation", "OFF")),
    )


def _source_label_from_report(data: Mapping[str, Any]) -> str:
    summary = data.get("source_summary", {}) or {}
    available = summary.get("available_sources", []) or []
    if available:
        return ", ".join(str(item) for item in available)
    return "No source available"


def build_reparodynamics_audit_event(
    rows: Sequence[Mapping[str, Any]],
    *,
    source: str = "Learning Page graded upload",
    timestamp: str | None = None,
) -> ReparodynamicsAuditEvent:
    """Analyze real rows and return a Phase 3A audit event without mutation."""

    safe_rows = [dict(row) for row in rows]
    source_hash = hash_rows(safe_rows) if safe_rows else ""
    scan_source = uploaded_source(source, safe_rows, source_hash=source_hash, source_path=source)
    report = build_runner_report(safe_rows, sources=[scan_source], timestamp=timestamp)
    return audit_event_from_runner_report(report, source=source)


def write_reparodynamics_audit_event(
    event: ReparodynamicsAuditEvent,
    *,
    log_path: Path = REPARODYNAMICS_AUDIT_LOG_PATH,
    latest_path: Path = REPARODYNAMICS_AUDIT_LATEST_PATH,
) -> ReparodynamicsAuditEvent:
    """Persist an audit event as append-only JSONL plus a latest snapshot."""

    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = event.to_dict()
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    latest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return event


def write_reparodynamics_audit_event_from_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    source: str = "Learning Page graded upload",
    timestamp: str | None = None,
    log_path: Path = REPARODYNAMICS_AUDIT_LOG_PATH,
    latest_path: Path = REPARODYNAMICS_AUDIT_LATEST_PATH,
) -> ReparodynamicsAuditEvent:
    """Build and persist an audit event from real graded/list rows."""

    event = build_reparodynamics_audit_event(rows, source=source, timestamp=timestamp)
    return write_reparodynamics_audit_event(event, log_path=log_path, latest_path=latest_path)


def write_reparodynamics_audit_event_from_runner_report(
    report: AdaptiveRunnerReport,
    *,
    source: str | None = None,
    log_path: Path = REPARODYNAMICS_AUDIT_LOG_PATH,
    latest_path: Path = REPARODYNAMICS_AUDIT_LATEST_PATH,
) -> ReparodynamicsAuditEvent:
    """Persist an audit event from an already-built runner report."""

    event = audit_event_from_runner_report(report, source=source)
    return write_reparodynamics_audit_event(event, log_path=log_path, latest_path=latest_path)


def _event_from_dict(data: Mapping[str, Any]) -> ReparodynamicsAuditEvent:
    return ReparodynamicsAuditEvent(
        schema_version=str(data.get("schema_version", REPARODYNAMICS_AUDIT_SCHEMA_VERSION)),
        timestamp=str(data.get("timestamp", "")),
        source=str(data.get("source", "")),
        rows_scanned=_to_int(data.get("rows_scanned")),
        unique_events_scanned=_to_int(data.get("unique_events_scanned")),
        duplicates_detected=_to_int(data.get("duplicates_detected")),
        new_patterns_detected=_to_int(data.get("new_patterns_detected")),
        drift_detected=bool(data.get("drift_detected", False)),
        repair_candidates_generated=_to_int(data.get("repair_candidates_generated")),
        shadow_mode=str(data.get("shadow_mode", "OFF")),
        live_mutation=str(data.get("live_mutation", "Forbidden")),
        reason=str(data.get("reason", PHASE_3A_BLOCK_REASON)),
        repair_activation=str(data.get("repair_activation", "OFF")),
        tgrm_activation=str(data.get("tgrm_activation", "OFF")),
        rye_activation=str(data.get("rye_activation", "OFF")),
        confidence_changes=str(data.get("confidence_changes", "OFF")),
        bet_tier_changes=str(data.get("bet_tier_changes", "OFF")),
        bankroll_changes=str(data.get("bankroll_changes", "OFF")),
        sportsbook_changes=str(data.get("sportsbook_changes", "OFF")),
        model_mutation=str(data.get("model_mutation", "FORBIDDEN")),
    )


def latest_reparodynamics_audit_event(
    *,
    latest_path: Path = REPARODYNAMICS_AUDIT_LATEST_PATH,
    log_path: Path = REPARODYNAMICS_AUDIT_LOG_PATH,
) -> ReparodynamicsAuditEvent | None:
    """Load the latest real audit event, or None when no run exists."""

    if latest_path.exists():
        try:
            return _event_from_dict(json.loads(latest_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    if not log_path.exists():
        return None
    try:
        lines = [line.strip() for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except OSError:
        return None
    if not lines:
        return None
    try:
        return _event_from_dict(json.loads(lines[-1]))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def audit_event_display_rows(event: ReparodynamicsAuditEvent) -> list[dict[str, str]]:
    """Return the exact rows displayed by the Reparodynamics page."""

    return [
        {"field": "Last Reparodynamics Run", "value": event.timestamp},
        {"field": "Source", "value": event.source},
        {"field": "Rows scanned", "value": str(event.rows_scanned)},
        {"field": "Unique events scanned", "value": str(event.unique_events_scanned)},
        {"field": "Duplicates detected", "value": str(event.duplicates_detected)},
        {"field": "New patterns detected", "value": str(event.new_patterns_detected)},
        {"field": "Drift detected", "value": "YES" if event.drift_detected else "NO"},
        {"field": "Repair candidates generated", "value": str(event.repair_candidates_generated)},
        {"field": "Shadow Mode", "value": event.shadow_mode},
        {"field": "Live Mutation", "value": event.live_mutation},
        {"field": "Reason", "value": event.reason},
    ]
