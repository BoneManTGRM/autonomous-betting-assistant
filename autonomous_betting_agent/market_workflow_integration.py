from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.row_normalizer import safe_text

SCHEMA_VERSION = "market_workflow_integration_v1"
READY = "WORKFLOW READY"
REVIEW = "REVIEW REQUIRED"
BLOCKED = "BLOCKED"
PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
PREVIEW_ONLY = "PREVIEW ONLY"
FORBIDDEN = "FORBIDDEN"

FLOW_STEPS = (
    ("market_optimizer", "Market Optimizer", "pages/market_optimizer.py"),
    ("market_dashboard_bridge", "Market Dashboard Bridge", "pages/market_dashboard_bridge.py"),
    ("local_review_checklist", "Local Review Checklist", "pages/local_review_checklist.py"),
    ("proof_center", "Proof Center", "pages/proof_center.py"),
    ("dashboard", "Dashboard", "pages/dashboard.py"),
)

REQUIRED_NAV_PATHS = (
    "pages/market_optimizer.py",
    "pages/market_dashboard_bridge.py",
    "pages/market_workflow_integration.py",
    "pages/real_page_wiring_audit.py",
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


def parse_csv_text(csv_text: str | None) -> list[dict[str, str]]:
    text = _text(csv_text)
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    return [{_text(key): _text(value) for key, value in row.items() if _text(key)} for row in reader]


def parse_json_object(json_text: str | None) -> dict[str, Any]:
    text = _text(json_text)
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {"parse_error": "invalid_json"}
    return value if isinstance(value, dict) else {"parse_error": "json_root_not_object"}


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


def check_row(check_id: str, title: str, status: str, details: str = "", expected: Any = "", actual: Any = "") -> dict[str, Any]:
    return {"check_id": check_id, "title": title, "status": status, "details": details, "expected": expected, "actual": actual}


def page_inventory_paths(page_rows: Sequence[Mapping[str, Any]]) -> set[str]:
    paths = set()
    for row in page_rows or []:
        for key in ("path", "page_path", "source", "notes"):
            text = _text(row.get(key))
            for required in REQUIRED_NAV_PATHS:
                if required in text:
                    paths.add(required)
    return paths


def optimizer_checks(optimizer_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not optimizer_report:
        return [check_row("optimizer_report_present", "Market Optimizer report supplied", FAIL)]
    parse_error = optimizer_report.get("parse_error")
    rows = optimizer_report.get("market_hunter_rows") or []
    return [
        check_row("optimizer_json_parse", "Market Optimizer JSON parse", FAIL if parse_error else PASS, details=_text(parse_error)),
        check_row("optimizer_preview_only", "Market Optimizer output is preview-only", PASS if optimizer_report.get("preview_only", True) is True else FAIL),
        check_row("optimizer_rows_present", "Market Hunter rows present", PASS if rows else WARN, details=f"rows={len(rows)}"),
        check_row("optimizer_exports_ready", "Optimizer export identifiers present", PASS if optimizer_report.get("optimizer_hash") or optimizer_report.get("optimizer_id") else WARN),
    ]


def bridge_checks(bridge_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not bridge_report:
        return [check_row("bridge_report_present", "Market Dashboard Bridge report supplied", FAIL)]
    parse_error = bridge_report.get("parse_error")
    tracking_rows = bridge_report.get("tracking_rows") or []
    handoff_rows = bridge_report.get("proof_handoff_rows") or []
    return [
        check_row("bridge_json_parse", "Market Dashboard Bridge JSON parse", FAIL if parse_error else PASS, details=_text(parse_error)),
        check_row("bridge_preview_only", "Dashboard Bridge output is preview-only", PASS if bridge_report.get("preview_only", True) is True else FAIL),
        check_row("tracking_rows_present", "Tracking schema rows present", PASS if tracking_rows else WARN, details=f"rows={len(tracking_rows)}"),
        check_row("handoff_rows_present", "Proof-flow handoff rows present", PASS if handoff_rows else WARN, details=f"rows={len(handoff_rows)}"),
        check_row("bridge_status_ready", "Bridge status is dashboard-ready or reviewable", PASS if _text(bridge_report.get("bridge_status")) in {"DASHBOARD READY", "REVIEW REQUIRED"} else WARN, actual=bridge_report.get("bridge_status")),
    ]


def navigation_checks(sidebar_text: str | None, page_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    text = _text(sidebar_text)
    inventory = page_inventory_paths(page_rows)
    checks = []
    for path in REQUIRED_NAV_PATHS:
        detected = path in text or path in inventory
        checks.append(check_row(f"nav_{path.replace('/', '_').replace('.', '_')}", f"Navigation path present: {path}", PASS if detected else WARN, expected=path))
    return checks


def step_rows(checks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_step = {
        "market_optimizer": [row for row in checks if row.get("check_id", "").startswith("optimizer")],
        "market_dashboard_bridge": [row for row in checks if row.get("check_id", "").startswith("bridge") or row.get("check_id") in {"tracking_rows_present", "handoff_rows_present"}],
        "navigation": [row for row in checks if row.get("check_id", "").startswith("nav_")],
    }
    output = []
    for step_id, rows in by_step.items():
        fail_count = len([row for row in rows if row.get("status") == FAIL])
        warn_count = len([row for row in rows if row.get("status") == WARN])
        if fail_count:
            status = BLOCKED
        elif warn_count:
            status = REVIEW
        else:
            status = PASS
        output.append({"step_id": step_id, "status": status, "check_count": len(rows), "warn_count": warn_count, "fail_count": fail_count})
    for step_id, title, path in FLOW_STEPS:
        if step_id not in {row["step_id"] for row in output}:
            output.append({"step_id": step_id, "title": title, "path": path, "status": "DOCUMENTED", "check_count": 0, "warn_count": 0, "fail_count": 0})
    return output


def summarize_checks(checks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    pass_count = len([row for row in checks or [] if row.get("status") == PASS])
    warn_count = len([row for row in checks or [] if row.get("status") == WARN])
    fail_count = len([row for row in checks or [] if row.get("status") == FAIL])
    if fail_count:
        status = BLOCKED
    elif warn_count:
        status = REVIEW
    else:
        status = READY
    return {"workflow_status": status, "pass_count": pass_count, "warn_count": warn_count, "fail_count": fail_count}


def next_actions(checks: Sequence[Mapping[str, Any]]) -> list[str]:
    actions: list[str] = []
    for row in checks or []:
        status = row.get("status")
        check_id = _text(row.get("check_id"))
        if status == FAIL:
            actions.append(f"Fix blocking workflow check: {check_id}.")
        elif status == WARN:
            actions.append(f"Review workflow check: {check_id}.")
    if not actions:
        actions.append("Run Optimizer, export Bridge, then review proof handoff rows before any public proof update.")
    return actions[:20]


def build_market_workflow_integration(
    workspace_id: str | None = None,
    optimizer_report: Mapping[str, Any] | None = None,
    bridge_report: Mapping[str, Any] | None = None,
    sidebar_text: str | None = None,
    page_inventory_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    optimizer = dict(optimizer_report or {})
    bridge = dict(bridge_report or {})
    page_rows = [dict(row) for row in page_inventory_rows or []]
    checks = []
    checks.extend(optimizer_checks(optimizer))
    checks.extend(bridge_checks(bridge))
    checks.extend(navigation_checks(sidebar_text, page_rows))
    summary = summarize_checks(checks)
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or _text(optimizer.get("workspace_id") or bridge.get("workspace_id")) or "default",
        "mode": PREVIEW_ONLY,
        **summary,
        "flow_steps": [{"step_id": step_id, "title": title, "path": path, "order": index + 1} for index, (step_id, title, path) in enumerate(FLOW_STEPS)],
        "step_status_rows": step_rows(checks),
        "workflow_checks": checks,
        "required_navigation_paths": list(REQUIRED_NAV_PATHS),
        "optimizer_hash": optimizer.get("optimizer_hash"),
        "bridge_hash": bridge.get("bridge_hash"),
        "tracking_row_count": len(bridge.get("tracking_rows") or []),
        "handoff_row_count": len(bridge.get("proof_handoff_rows") or []),
        "next_actions": next_actions(checks),
        "handoff_manifest": {
            "optimizer_hash": optimizer.get("optimizer_hash"),
            "bridge_hash": bridge.get("bridge_hash"),
            "tracking_row_count": len(bridge.get("tracking_rows") or []),
            "handoff_row_count": len(bridge.get("proof_handoff_rows") or []),
            "operator_review_required": True,
            "source_update_allowed": False,
        },
        "safety_gates": {
            "live_execution": FORBIDDEN,
            "account_access": FORBIDDEN,
            "funds_movement": FORBIDDEN,
            "automatic_proof_change": FORBIDDEN,
            "automatic_model_change": FORBIDDEN,
            "key_exposure": FORBIDDEN,
            "external_api_calls": FORBIDDEN,
        },
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "warnings": [row for row in checks if row.get("status") == WARN],
        "errors": [row for row in checks if row.get("status") == FAIL],
    }
    report["workflow_id"] = stable_hash("market_workflow", {"workspace_id": report["workspace_id"], "checks": checks}, 24)
    report["workflow_hash"] = stable_hash("market_workflow_hash", {key: value for key, value in report.items() if key != "generated_at_utc"}, 32)
    return report


def build_market_workflow_integration_from_text(
    workspace_id: str | None = None,
    optimizer_json_text: str | None = None,
    bridge_json_text: str | None = None,
    sidebar_text: str | None = None,
    page_inventory_csv_text: str | None = None,
) -> dict[str, Any]:
    return build_market_workflow_integration(
        workspace_id,
        parse_json_object(optimizer_json_text),
        parse_json_object(bridge_json_text),
        sidebar_text,
        parse_csv_text(page_inventory_csv_text),
    )


def export_workflow_integration_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_workflow_checks_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("workflow_checks") or [])


def export_step_status_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("step_status_rows") or [])


def export_flow_steps_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("flow_steps") or [])


def export_handoff_manifest_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report.get("handoff_manifest") or {}), sort_keys=True, indent=2)


def export_workflow_manifest_json(report: Mapping[str, Any]) -> str:
    manifest = {key: report.get(key) for key in ("schema_version", "workspace_id", "workflow_id", "workflow_hash", "generated_at_utc", "workflow_status", "optimizer_hash", "bridge_hash", "tracking_row_count", "handoff_row_count", "preview_only", "files_written", "live_changes")}
    return json.dumps(_safe(manifest), sort_keys=True, indent=2)
