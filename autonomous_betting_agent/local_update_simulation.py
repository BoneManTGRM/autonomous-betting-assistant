from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from autonomous_betting_agent.adaptive_learning_intake_router import (
    build_adaptive_learning_intake,
    export_intake_manifest_json,
    lane_csv,
    parse_csv_text,
    parse_json_rows,
)
from autonomous_betting_agent.api_smoke_test_service import build_api_smoke_report, parse_json_payload
from autonomous_betting_agent.event_match_resolver import build_event_match_report, parse_json_records
from autonomous_betting_agent.offline_update_package_builder import build_offline_update_package, export_package_manifest_json

SCHEMA_VERSION = "local_update_simulation_v1"
SIM_READY = "SIMULATION READY"
SIM_REVIEW = "REVIEW REQUIRED"
SIM_EMPTY = "NO ROWS"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _canonical(value: Any) -> str:
    return json.dumps(_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_hash(prefix: str, value: Any, length: int = 24) -> str:
    return f"{prefix}_{hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()[:length]}"


def _stage_status(report: Mapping[str, Any], key: str = "status") -> str:
    return _text(report.get(key)) or "NOT RUN"


def _simulation_status(locked_count: int, match_report: Mapping[str, Any], package: Mapping[str, Any], intake: Mapping[str, Any]) -> str:
    if locked_count == 0:
        return SIM_EMPTY
    review_count = int(match_report.get("manual_review_count") or 0) + int(package.get("manual_review_count") or 0) + int(intake.get("review_count") or 0) + int(intake.get("quarantine_count") or 0)
    return SIM_REVIEW if review_count else SIM_READY


def build_stage_summary(smoke: Mapping[str, Any], match: Mapping[str, Any], package: Mapping[str, Any], intake: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "stage": "api_smoke",
            "status": _stage_status(smoke),
            "ready_provider_count": smoke.get("ready_provider_count", 0),
            "review_provider_count": smoke.get("review_provider_count", 0),
            "missing_key_count": smoke.get("missing_key_count", 0),
        },
        {
            "stage": "event_match",
            "status": _stage_status(match),
            "matched_count": match.get("matched_count", 0),
            "manual_review_count": match.get("manual_review_count", 0),
            "provider_event_count": match.get("provider_event_count", 0),
        },
        {
            "stage": "offline_package",
            "status": _stage_status(package),
            "changed_row_count": package.get("changed_row_count", 0),
            "manual_review_count": package.get("manual_review_count", 0),
            "verified_learning_count": package.get("verified_learning_count", 0),
        },
        {
            "stage": "adaptive_intake",
            "status": _stage_status(intake),
            "verified_count": intake.get("verified_count", 0),
            "review_count": intake.get("review_count", 0),
            "shadow_count": intake.get("shadow_count", 0),
            "quarantine_count": intake.get("quarantine_count", 0),
        },
    ]


def build_local_update_simulation(
    workspace_id: str | None = None,
    locked_rows: list[dict[str, Any]] | None = None,
    provider_events: list[dict[str, Any]] | None = None,
    confirmation_rows: list[dict[str, Any]] | None = None,
    value_rows: list[dict[str, Any]] | None = None,
    shadow_rows: list[dict[str, Any]] | None = None,
    review_rows: list[dict[str, Any]] | None = None,
    secrets: Mapping[str, Any] | None = None,
    *,
    match_threshold: float = 0.82,
    review_threshold: float = 0.68,
    verified_confidence: float = 0.82,
    intake_review_confidence: float = 0.50,
) -> dict[str, Any]:
    locked = [dict(row) for row in locked_rows or []]
    events = [dict(row) for row in provider_events or []]
    confirmations = [dict(row) for row in confirmation_rows or []]
    values = [dict(row) for row in value_rows or []]
    smoke = build_api_smoke_report(
        workspace_id,
        secrets or {},
        {
            "the_odds_api": events,
            "sportsdataio": confirmations,
            "weatherapi": {"location": {"name": "simulation"}, "current": {"temp_c": 20}},
        },
    )
    match = build_event_match_report(
        workspace_id,
        locked,
        events,
        match_threshold=match_threshold,
        review_threshold=review_threshold,
    )
    package = build_offline_update_package(workspace_id, locked, match, confirmations, values)
    intake = build_adaptive_learning_intake(
        workspace_id,
        package,
        shadow_rows=shadow_rows or [],
        review_rows=review_rows or [],
        verified_confidence=verified_confidence,
        review_confidence=intake_review_confidence,
    )
    stages = build_stage_summary(smoke, match, package, intake)
    status = _simulation_status(len(locked), match, package, intake)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "simulation_id": "",
        "status": status,
        "locked_row_count": len(locked),
        "provider_event_count": len(events),
        "matched_count": match.get("matched_count", 0),
        "package_changed_count": package.get("changed_row_count", 0),
        "verified_lane_count": intake.get("verified_count", 0),
        "review_lane_count": intake.get("review_count", 0),
        "shadow_lane_count": intake.get("shadow_count", 0),
        "quarantine_lane_count": intake.get("quarantine_count", 0),
        "official_metrics_row_count": intake.get("official_metrics_row_count", 0),
        "shadow_learning_row_count": intake.get("shadow_learning_row_count", 0),
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "stage_summary": stages,
        "api_smoke_report": smoke,
        "event_match_report": match,
        "offline_package_manifest": json.loads(export_package_manifest_json(package)),
        "adaptive_intake_manifest": json.loads(export_intake_manifest_json(intake)),
        "downloads": {
            "backup_csv": package.get("backup_csv", ""),
            "updated_csv_preview": package.get("updated_csv_preview", ""),
            "rollback_csv": package.get("rollback_csv", ""),
            "package_audit_json": package.get("audit_json", ""),
            "verified_lane_csv": lane_csv(intake, "VERIFIED LANE"),
            "review_lane_csv": lane_csv(intake, "REVIEW LANE"),
            "shadow_lane_csv": lane_csv(intake, "SHADOW LANE"),
            "quarantine_lane_csv": lane_csv(intake, "QUARANTINE LANE"),
        },
        "warnings": [item for report in (smoke, match, package, intake) for item in report.get("warnings", [])],
        "errors": [item for report in (smoke, match, package, intake) for item in report.get("errors", [])],
    }
    manifest["simulation_id"] = stable_hash("local_sim", {"workspace_id": workspace_id, "stages": stages}, 24)
    manifest["simulation_hash"] = stable_hash("local_sim_hash", {k: v for k, v in manifest.items() if k != "generated_at_utc"}, 32)
    return manifest


def build_local_update_simulation_from_text(
    workspace_id: str | None = None,
    locked_csv_text: str | None = None,
    provider_events_json_text: str | None = None,
    confirmation_json_text: str | None = None,
    value_json_text: str | None = None,
    shadow_csv_text: str | None = None,
    review_json_text: str | None = None,
    *,
    match_threshold: float = 0.82,
    review_threshold: float = 0.68,
    verified_confidence: float = 0.82,
    intake_review_confidence: float = 0.50,
) -> dict[str, Any]:
    return build_local_update_simulation(
        workspace_id,
        parse_csv_text(locked_csv_text),
        parse_json_records(provider_events_json_text),
        parse_json_rows(confirmation_json_text),
        parse_json_rows(value_json_text),
        parse_csv_text(shadow_csv_text),
        parse_json_rows(review_json_text),
        secrets={"ODDS_API_KEY": "local", "SPORTSDATAIO_API_KEY": "local", "WEATHERAPI_KEY": "local"},
        match_threshold=match_threshold,
        review_threshold=review_threshold,
        verified_confidence=verified_confidence,
        intake_review_confidence=intake_review_confidence,
    )


def export_simulation_manifest_json(report: Mapping[str, Any]) -> str:
    compact = dict(report or {})
    compact["downloads"] = {key: f"available:{bool(value)}" for key, value in dict(compact.get("downloads") or {}).items()}
    return json.dumps(_safe(compact), sort_keys=True, indent=2)
