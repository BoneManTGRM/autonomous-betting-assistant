from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.row_normalizer import safe_text

SCHEMA_VERSION = "proof_hardening_closeout_v1"
READY_TO_CLOSE = "READY TO CLOSE"
KEEP_OPEN = "KEEP OPEN"
BLOCKED = "BLOCKED"
PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
PREVIEW_ONLY = "PREVIEW ONLY"
FORBIDDEN = "FORBIDDEN"

REQUIRED_EVIDENCE = (
    ("canonical_recovery", "Canonical store recovery evidence"),
    ("restart_regression", "Restart/reload regression evidence"),
    ("readonly_audit", "Proof ledger read-only audit evidence"),
    ("page_wiring", "Real page wiring audit evidence"),
    ("dashboard_refresh", "Dashboard refresh package evidence"),
    ("local_review", "Local review checklist evidence"),
)

SAFETY_KEYS = (
    "live_mutation",
    "model_training",
    "stored_data_mutation",
    "automatic_live_promotion",
    "proof_overwrite",
    "proof_mutation",
    "source_update",
    "automatic_proof_change",
    "automatic_model_change",
    "live_changes",
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any) -> str:
    return safe_text(value)


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


def parse_json_object(json_text: str | None) -> dict[str, Any]:
    text = _text(json_text)
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {"parse_error": "invalid_json"}
    return value if isinstance(value, dict) else {"parse_error": "json_root_not_object"}


def parse_csv_text(csv_text: str | None) -> list[dict[str, str]]:
    text = _text(csv_text)
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    return [{_text(key): _text(value) for key, value in row.items() if _text(key)} for row in reader]


def csv_from_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    row_list = [dict(row) for row in rows or []]
    fieldnames: list[str] = []
    for row in row_list:
        for key in row:
            if str(key) not in fieldnames:
                fieldnames.append(str(key))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    if fieldnames:
        writer.writeheader()
        for row in row_list:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return output.getvalue()


def check_row(check_id: str, title: str, status: str, details: str = "", evidence_id: str = "", expected: Any = "", actual: Any = "") -> dict[str, Any]:
    return {
        "check_id": check_id,
        "title": title,
        "status": status,
        "details": details,
        "evidence_id": evidence_id,
        "expected": expected,
        "actual": actual,
    }


def report_status(report: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = _text(report.get(key))
        if value:
            return value
    return ""


def report_has_blocker(report: Mapping[str, Any]) -> bool:
    text = json.dumps(_safe(report), sort_keys=True).lower()
    return '"fail_count":' in text and any(token in text for token in ('"fail_count":1', '"fail_count": 1', '"fail_count":2', '"fail_count": 2')) or "blocked" in text


def evidence_summary(evidence_id: str, report: Mapping[str, Any]) -> dict[str, Any]:
    status = report_status(
        report,
        (
            "recovery_status",
            "restart_status",
            "audit_status",
            "system_status",
            "dashboard_status",
            "checklist_status",
            "readiness_status",
            "bridge_status",
        ),
    )
    return {
        "evidence_id": evidence_id,
        "present": bool(report),
        "schema_version": report.get("schema_version"),
        "status": status,
        "hash": report.get("recovery_hash") or report.get("restart_hash") or report.get("audit_hash") or report.get("wiring_hash") or report.get("dashboard_hash") or report.get("checklist_hash"),
        "row_count": report.get("resolved_row_count") or report.get("row_count") or report.get("tracking_row_count") or report.get("page_count"),
        "fail_count": report.get("fail_count", 0),
        "warn_count": report.get("warn_count", 0),
        "preview_only": report.get("preview_only", True),
        "files_written": report.get("files_written", 0),
        "live_changes": report.get("live_changes", 0),
    }


def required_evidence_checks(evidence: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    checks = []
    for evidence_id, title in REQUIRED_EVIDENCE:
        report = evidence.get(evidence_id) or {}
        checks.append(check_row(f"evidence_{evidence_id}", title, PASS if report else FAIL, evidence_id=evidence_id, details=f"present={bool(report)}"))
    return checks


def status_checks(evidence: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    checks = []
    acceptable = {
        "CANONICAL RECOVERY SAFE",
        "RESTART SAFE",
        "READ ONLY SAFE",
        "CANONICAL WIRING READY",
        "DASHBOARD READY",
        "READY TO REVIEW",
        "ACTION REQUIRED",
        "REVIEW REQUIRED",
    }
    for evidence_id, report in evidence.items():
        if not report:
            continue
        status = evidence_summary(evidence_id, report).get("status") or ""
        if _text(status).upper() == BLOCKED:
            check_status = FAIL
        elif status in acceptable or status:
            check_status = PASS if status not in {"REVIEW REQUIRED", "ACTION REQUIRED"} else WARN
        else:
            check_status = WARN
        checks.append(check_row(f"status_{evidence_id}", f"Evidence status review: {evidence_id}", check_status, evidence_id=evidence_id, actual=status))
    return checks


def safety_checks(evidence: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    checks = []
    for evidence_id, report in evidence.items():
        if not report:
            continue
        safety = report.get("safety_gates") or {}
        preview_only = report.get("preview_only", True)
        files_written = int(report.get("files_written") or 0)
        live_changes = int(report.get("live_changes") or 0)
        checks.append(check_row(f"preview_only_{evidence_id}", f"Preview-only safety: {evidence_id}", PASS if preview_only is True else FAIL, evidence_id=evidence_id, actual=preview_only))
        checks.append(check_row(f"no_files_written_{evidence_id}", f"No files written: {evidence_id}", PASS if files_written == 0 else FAIL, evidence_id=evidence_id, actual=files_written))
        checks.append(check_row(f"no_live_changes_{evidence_id}", f"No live changes: {evidence_id}", PASS if live_changes == 0 else FAIL, evidence_id=evidence_id, actual=live_changes))
        for key, value in safety.items():
            if key in SAFETY_KEYS or "mutation" in key or "change" in key or "write" in key or "promotion" in key:
                checks.append(check_row(f"safety_{evidence_id}_{key}", f"Safety gate {key}: {evidence_id}", PASS if _text(value).upper() == FORBIDDEN else WARN, evidence_id=evidence_id, actual=value))
    return checks


def acceptance_checks(evidence: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    checks = []
    canonical = evidence.get("canonical_recovery") or {}
    restart = evidence.get("restart_regression") or {}
    wiring = evidence.get("page_wiring") or {}
    readonly = evidence.get("readonly_audit") or {}
    checklist = evidence.get("local_review") or {}
    dashboard = evidence.get("dashboard_refresh") or {}

    checks.append(check_row("accept_session_recovery", "Session-empty/disk recovery represented", PASS if canonical.get("resolved_store_name") or canonical.get("recovery_checks") else FAIL, evidence_id="canonical_recovery"))
    checks.append(check_row("accept_save_reload", "Save/reload verification represented", PASS if canonical.get("save_reload_verification") or restart.get("restart_checks") else FAIL, evidence_id="restart_regression"))
    checks.append(check_row("accept_dedupe", "Duplicate proof-id handling represented", PASS if "duplicate" in json.dumps(_safe(canonical)).lower() or "duplicate" in json.dumps(_safe(readonly)).lower() else FAIL, evidence_id="canonical_recovery"))
    checks.append(check_row("accept_workspace", "Workspace mismatch diagnostics represented", PASS if "workspace" in json.dumps(_safe(canonical)).lower() or "workspace" in json.dumps(_safe(readonly)).lower() else FAIL, evidence_id="readonly_audit"))
    checks.append(check_row("accept_real_page_wiring", "Real page wiring audit represented", PASS if wiring.get("page_results") is not None or wiring.get("system_checks") is not None else FAIL, evidence_id="page_wiring"))
    checks.append(check_row("accept_dashboard_refresh", "Dashboard refresh package represented", PASS if dashboard.get("dashboard_cards") or dashboard.get("event_breakdown") or dashboard.get("dashboard_rows") is not None else WARN, evidence_id="dashboard_refresh"))
    checks.append(check_row("accept_operator_review", "Operator review gate represented", PASS if checklist.get("checklist_rows") is not None or checklist.get("readiness_status") or checklist.get("review_checks") is not None else WARN, evidence_id="local_review"))
    return checks


def summarize_checks(checks: Sequence[Mapping[str, Any]], operator_acknowledged: bool) -> dict[str, Any]:
    pass_count = len([row for row in checks or [] if row.get("status") == PASS])
    warn_count = len([row for row in checks or [] if row.get("status") == WARN])
    fail_count = len([row for row in checks or [] if row.get("status") == FAIL])
    if fail_count:
        status = BLOCKED
        recommendation = KEEP_OPEN
    elif warn_count or not operator_acknowledged:
        status = REVIEW
        recommendation = KEEP_OPEN
    else:
        status = READY_TO_CLOSE
        recommendation = READY_TO_CLOSE
    return {
        "closeout_status": status,
        "issue_21_recommendation": recommendation,
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "operator_acknowledged": operator_acknowledged,
    }


def build_proof_hardening_closeout(
    workspace_id: str | None = None,
    canonical_recovery: Mapping[str, Any] | None = None,
    restart_regression: Mapping[str, Any] | None = None,
    readonly_audit: Mapping[str, Any] | None = None,
    page_wiring: Mapping[str, Any] | None = None,
    dashboard_refresh: Mapping[str, Any] | None = None,
    local_review: Mapping[str, Any] | None = None,
    operator_acknowledged: bool = False,
) -> dict[str, Any]:
    evidence = {
        "canonical_recovery": dict(canonical_recovery or {}),
        "restart_regression": dict(restart_regression or {}),
        "readonly_audit": dict(readonly_audit or {}),
        "page_wiring": dict(page_wiring or {}),
        "dashboard_refresh": dict(dashboard_refresh or {}),
        "local_review": dict(local_review or {}),
    }
    summaries = [evidence_summary(evidence_id, report) for evidence_id, report in evidence.items()]
    checks = []
    checks.extend(required_evidence_checks(evidence))
    checks.extend(status_checks(evidence))
    checks.extend(safety_checks(evidence))
    checks.extend(acceptance_checks(evidence))
    summary = summarize_checks(checks, operator_acknowledged)
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "mode": PREVIEW_ONLY,
        **summary,
        "evidence_summaries": summaries,
        "closeout_checks": checks,
        "required_evidence": [{"evidence_id": evidence_id, "title": title} for evidence_id, title in REQUIRED_EVIDENCE],
        "next_actions": next_actions(checks, operator_acknowledged),
        "safety_gates": {
            "live_mutation": FORBIDDEN,
            "model_training": FORBIDDEN,
            "stored_data_mutation": FORBIDDEN,
            "automatic_live_promotion": FORBIDDEN,
            "proof_overwrite": FORBIDDEN,
            "issue_close_requires_operator_ack": str(not operator_acknowledged),
        },
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "warnings": [row for row in checks if row.get("status") == WARN],
        "errors": [row for row in checks if row.get("status") == FAIL],
    }
    report["closeout_id"] = stable_hash("proof_closeout", {"workspace_id": report["workspace_id"], "checks": checks, "ack": operator_acknowledged}, 24)
    report["closeout_hash"] = stable_hash("proof_closeout_hash", {key: value for key, value in report.items() if key != "generated_at_utc"}, 32)
    return report


def next_actions(checks: Sequence[Mapping[str, Any]], operator_acknowledged: bool) -> list[str]:
    actions = []
    for row in checks or []:
        if row.get("status") == FAIL:
            actions.append(f"Fix blocking evidence: {row.get('check_id')}.")
        elif row.get("status") == WARN:
            actions.append(f"Review warning: {row.get('check_id')}.")
    if not operator_acknowledged:
        actions.append("Operator acknowledgment required before closing issue #21.")
    if not actions:
        actions.append("Close issue #21 as completed and track future production deployment work separately.")
    return actions[:25]


def build_proof_hardening_closeout_from_text(
    workspace_id: str | None = None,
    canonical_recovery_json: str | None = None,
    restart_regression_json: str | None = None,
    readonly_audit_json: str | None = None,
    page_wiring_json: str | None = None,
    dashboard_refresh_json: str | None = None,
    local_review_json: str | None = None,
    operator_acknowledged: bool = False,
) -> dict[str, Any]:
    return build_proof_hardening_closeout(
        workspace_id,
        parse_json_object(canonical_recovery_json),
        parse_json_object(restart_regression_json),
        parse_json_object(readonly_audit_json),
        parse_json_object(page_wiring_json),
        parse_json_object(dashboard_refresh_json),
        parse_json_object(local_review_json),
        operator_acknowledged,
    )


def export_closeout_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_closeout_checks_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("closeout_checks") or [])


def export_evidence_summary_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("evidence_summaries") or [])


def export_closeout_manifest_json(report: Mapping[str, Any]) -> str:
    manifest = {key: report.get(key) for key in ("schema_version", "workspace_id", "closeout_id", "closeout_hash", "generated_at_utc", "closeout_status", "issue_21_recommendation", "operator_acknowledged", "pass_count", "warn_count", "fail_count", "preview_only", "files_written", "live_changes")}
    return json.dumps(_safe(manifest), sort_keys=True, indent=2)
