from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from autonomous_betting_agent.adaptive_learning_intake_router import build_adaptive_learning_intake
from autonomous_betting_agent.api_smoke_test_service import analyze_provider_payload, parse_json_payload
from autonomous_betting_agent.event_match_resolver import build_event_match_report, parse_csv_text, parse_json_records
from autonomous_betting_agent.offline_update_package_builder import build_offline_update_package, parse_json_rows

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


def build_smoke_summary(provider_payloads: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payloads = dict(provider_payloads or {})
    analyses = [
        analyze_provider_payload("the_odds_api", payloads.get("the_odds_api")),
        analyze_provider_payload("sportsdataio", payloads.get("sportsdataio")),
        analyze_provider_payload("weatherapi", payloads.get("weatherapi")),
    ]
    ready = [row for row in analyses if row.get("status") == "API READY"]
    review = [row for row in analyses if row.get("status") == "REVIEW REQUIRED"]
    empty = [row for row in analyses if row.get("status") == "NO SAMPLE RESPONSE"]
    return {
        "status": "API READY" if ready and not review and not empty else "REVIEW REQUIRED" if review else "NO SAMPLE RESPONSE",
        "ready_provider_count": len(ready),
        "review_provider_count": len(review),
        "no_sample_count": len(empty),
        "payload_analysis": analyses,
    }


def build_local_update_simulation(
    workspace_id: str | None = None,
    locked_rows: list[dict[str, Any]] | None = None,
    provider_events: list[dict[str, Any]] | None = None,
    confirmation_rows: list[dict[str, Any]] | None = None,
    value_rows: list[dict[str, Any]] | None = None,
    provider_payloads: Mapping[str, Any] | None = None,
    shadow_rows: list[dict[str, Any]] | None = None,
    review_rows: list[dict[str, Any]] | None = None,
    *,
    match_threshold: float = 0.82,
    review_threshold: float = 0.68,
    verified_confidence: float = 0.82,
    review_confidence: float = 0.50,
) -> dict[str, Any]:
    locked = [dict(row) for row in locked_rows or []]
    events = [dict(row) for row in provider_events or []]
    confirmations = [dict(row) for row in confirmation_rows or []]
    values = [dict(row) for row in value_rows or []]
    smoke = build_smoke_summary(provider_payloads or {})
    match_report = build_event_match_report(
        workspace_id,
        locked,
        events,
        match_threshold=match_threshold,
        review_threshold=review_threshold,
    )
    package = build_offline_update_package(workspace_id, locked, match_report, confirmations, values)
    intake = build_adaptive_learning_intake(
        workspace_id,
        package,
        shadow_rows=shadow_rows or [],
        review_rows=review_rows or [],
        verified_confidence=verified_confidence,
        review_confidence=review_confidence,
    )
    review_flags = []
    if not locked:
        review_flags.append("no locked rows supplied")
    if smoke.get("status") != "API READY":
        review_flags.append("provider smoke summary is not fully ready")
    if match_report.get("manual_review_count", 0):
        review_flags.append("event matching has manual review rows")
    if package.get("manual_review_count", 0):
        review_flags.append("offline package has manual review rows")
    if intake.get("review_count", 0) or intake.get("quarantine_count", 0):
        review_flags.append("intake has review or quarantine rows")
    status = SIM_EMPTY if not locked else SIM_REVIEW if review_flags else SIM_READY
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "simulation_id": "",
        "status": status,
        "locked_row_count": len(locked),
        "provider_event_count": len(events),
        "ready_provider_count": smoke.get("ready_provider_count", 0),
        "matched_count": match_report.get("matched_count", 0),
        "match_review_count": match_report.get("manual_review_count", 0),
        "package_changed_count": package.get("changed_row_count", 0),
        "package_review_count": package.get("manual_review_count", 0),
        "intake_verified_count": intake.get("verified_count", 0),
        "intake_review_count": intake.get("review_count", 0),
        "intake_shadow_count": intake.get("shadow_count", 0),
        "intake_quarantine_count": intake.get("quarantine_count", 0),
        "preview_only": True,
        "files_written": 0,
        "proof_rows_changed": 0,
        "smoke_summary": smoke,
        "match_report": match_report,
        "offline_package": package,
        "adaptive_intake": intake,
        "review_flags": review_flags,
        "warnings": review_flags,
        "errors": [] if locked else ["no locked rows supplied"],
    }
    report["simulation_id"] = stable_hash("local_sim", {"workspace_id": workspace_id, "match": match_report.get("package_hash"), "intake": intake.get("intake_hash")}, 24)
    report["simulation_hash"] = stable_hash("local_sim_hash", {k: v for k, v in report.items() if k != "generated_at_utc"}, 32)
    return report


def build_local_update_simulation_from_text(
    workspace_id: str | None = None,
    locked_csv_text: str | None = None,
    provider_events_json_text: str | None = None,
    confirmation_json_text: str | None = None,
    value_json_text: str | None = None,
    odds_payload_json_text: str | None = None,
    sportsdata_payload_json_text: str | None = None,
    weather_payload_json_text: str | None = None,
    shadow_csv_text: str | None = None,
    review_json_text: str | None = None,
    *,
    match_threshold: float = 0.82,
    review_threshold: float = 0.68,
    verified_confidence: float = 0.82,
    review_confidence: float = 0.50,
) -> dict[str, Any]:
    return build_local_update_simulation(
        workspace_id,
        parse_csv_text(locked_csv_text),
        parse_json_records(provider_events_json_text),
        parse_json_rows(confirmation_json_text),
        parse_json_rows(value_json_text),
        {
            "the_odds_api": parse_json_payload(odds_payload_json_text),
            "sportsdataio": parse_json_payload(sportsdata_payload_json_text),
            "weatherapi": parse_json_payload(weather_payload_json_text),
        },
        parse_csv_text(shadow_csv_text),
        parse_json_rows(review_json_text),
        match_threshold=match_threshold,
        review_threshold=review_threshold,
        verified_confidence=verified_confidence,
        review_confidence=review_confidence,
    )


def export_simulation_manifest_json(report: Mapping[str, Any]) -> str:
    compact = dict(report or {})
    package = dict(compact.get("offline_package") or {})
    for key in ("backup_csv", "updated_csv_preview", "rollback_csv"):
        package.pop(key, None)
    compact["offline_package"] = package
    return json.dumps(_safe(compact), sort_keys=True, indent=2)
