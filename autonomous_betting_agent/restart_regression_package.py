from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.dashboard_refresh_package import (
    build_dashboard_refresh_package,
    csv_from_rows,
    parse_csv_text,
)
from autonomous_betting_agent.local_review_checklist import build_local_review_checklist

SCHEMA_VERSION = "restart_regression_package_v1"
RESTART_SAFE = "RESTART SAFE"
REVIEW_REQUIRED = "REVIEW REQUIRED"
BLOCKED = "BLOCKED"
PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
SHADOW_ONLY = "SHADOW ONLY"
FORBIDDEN = "FORBIDDEN"
VOLATILE_FINGERPRINT_KEYS = {
    "generated_at_utc",
    "dashboard_refresh_id",
    "dashboard_refresh_hash",
    "local_review_id",
    "local_review_hash",
    "restart_regression_id",
    "restart_regression_hash",
}


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


def _stable_without_volatile(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _stable_without_volatile(v) for k, v in sorted(value.items(), key=lambda item: str(item[0])) if str(k) not in VOLATILE_FINGERPRINT_KEYS}
    if isinstance(value, (list, tuple)):
        return [_stable_without_volatile(v) for v in value]
    if isinstance(value, set):
        return [_stable_without_volatile(v) for v in sorted(value, key=lambda item: str(item))]
    return _safe(value)


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


def export_restart_regression_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def package_fingerprint(value: Mapping[str, Any] | None) -> str:
    return stable_hash("fingerprint", _stable_without_volatile(dict(value or {})), 32)


def check_row(check_id: str, title: str, status: str, details: str = "", expected: Any = "", actual: Any = "") -> dict[str, Any]:
    return {
        "check_id": check_id,
        "title": title,
        "status": status,
        "details": details,
        "expected": expected,
        "actual": actual,
    }


def compare_field(package_name: str, original: Mapping[str, Any], rebuilt: Mapping[str, Any], field: str, *, required: bool = True) -> dict[str, Any]:
    expected = original.get(field)
    actual = rebuilt.get(field)
    if expected == actual:
        status = PASS
    elif required:
        status = FAIL
    else:
        status = WARN
    return check_row(f"{package_name}_{field}", f"{package_name} field stable: {field}", status, expected=expected, actual=actual)


def dashboard_consistency_checks(original: Mapping[str, Any], rebuilt: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not original:
        return [check_row("dashboard_original_missing", "Original dashboard package available", WARN, "missing original dashboard package")]
    fields = (
        "schema_version",
        "workspace_id",
        "status",
        "source_row_count",
        "history_row_count",
        "decision_row_count",
        "row_count",
        "unique_event_count",
        "duplicate_event_group_count",
        "completed_count",
        "pending_count",
        "wins",
        "losses",
        "pushes",
        "cancels",
        "win_rate_ex_push_cancel",
        "total_profit_units",
        "stake_units",
        "roi",
        "average_CLV_decimal_delta",
        "average_baseline_EV",
        "average_calibrated_EV",
        "preview_only",
        "files_written",
        "live_changes",
    )
    checks = [compare_field("dashboard", original, rebuilt, field) for field in fields]
    checks.append(check_row("dashboard_fingerprint", "Dashboard stable fingerprint", PASS if package_fingerprint(original) == package_fingerprint(rebuilt) else FAIL, expected=package_fingerprint(original), actual=package_fingerprint(rebuilt)))
    return checks


def checklist_consistency_checks(original: Mapping[str, Any], rebuilt: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not original:
        return [check_row("checklist_original_missing", "Original checklist package available", WARN, "missing original checklist package")]
    fields = (
        "schema_version",
        "workspace_id",
        "readiness_status",
        "proof_row_count",
        "history_row_count",
        "decision_row_count",
        "dashboard_status",
        "pass_count",
        "warn_count",
        "fail_count",
        "required_failure_count",
        "preview_only",
        "files_written",
        "live_changes",
    )
    checks = [compare_field("checklist", original, rebuilt, field) for field in fields]
    checks.append(check_row("checklist_fingerprint", "Checklist stable fingerprint", PASS if package_fingerprint(original) == package_fingerprint(rebuilt) else FAIL, expected=package_fingerprint(original), actual=package_fingerprint(rebuilt)))
    return checks


def json_round_trip_check(package_name: str, package: Mapping[str, Any]) -> dict[str, Any]:
    if not package:
        return check_row(f"{package_name}_json_round_trip", f"{package_name} JSON round trip", WARN, "package missing")
    encoded = json.dumps(_safe(package), sort_keys=True)
    decoded = json.loads(encoded)
    return check_row(
        f"{package_name}_json_round_trip",
        f"{package_name} JSON round trip",
        PASS if package_fingerprint(package) == package_fingerprint(decoded) else FAIL,
        expected=package_fingerprint(package),
        actual=package_fingerprint(decoded),
    )


def export_reload_check(package_name: str, package: Mapping[str, Any]) -> dict[str, Any]:
    if not package:
        return check_row(f"{package_name}_export_reload", f"{package_name} export reload", WARN, "package missing")
    exported = export_restart_regression_json(package)
    reloaded = parse_json_object(exported)
    return check_row(
        f"{package_name}_export_reload",
        f"{package_name} export reload",
        PASS if package_fingerprint(package) == package_fingerprint(reloaded) else FAIL,
        expected=package_fingerprint(package),
        actual=package_fingerprint(reloaded),
    )


def safety_checks(packages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for index, package in enumerate(packages or []):
        if not package:
            continue
        name = package.get("schema_version") or f"package_{index}"
        checks.append(check_row(f"{name}_preview_only", f"{name} preview only", PASS if package.get("preview_only", True) is True else FAIL, actual=package.get("preview_only", True)))
        checks.append(check_row(f"{name}_files_written", f"{name} files not written", PASS if int(package.get("files_written") or 0) == 0 else FAIL, actual=package.get("files_written", 0)))
        checks.append(check_row(f"{name}_live_changes", f"{name} live changes blocked", PASS if int(package.get("live_changes") or 0) == 0 else FAIL, actual=package.get("live_changes", 0)))
    return checks


def summarize_checks(checks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    pass_count = len([row for row in checks or [] if row.get("status") == PASS])
    warn_count = len([row for row in checks or [] if row.get("status") == WARN])
    fail_count = len([row for row in checks or [] if row.get("status") == FAIL])
    if fail_count:
        status = BLOCKED
    elif warn_count:
        status = REVIEW_REQUIRED
    else:
        status = RESTART_SAFE
    return {"restart_status": status, "pass_count": pass_count, "warn_count": warn_count, "fail_count": fail_count}


def build_restart_regression_package(
    workspace_id: str | None = None,
    proof_rows: Sequence[Mapping[str, Any]] | None = None,
    history_rows: Sequence[Mapping[str, Any]] | None = None,
    decision_preview_rows: Sequence[Mapping[str, Any]] | None = None,
    dashboard_report: Mapping[str, Any] | None = None,
    checklist_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    proof = [dict(row) for row in proof_rows or []]
    history = [dict(row) for row in history_rows or []]
    decisions = [dict(row) for row in decision_preview_rows or []]
    original_dashboard = dict(dashboard_report or {})
    rebuilt_dashboard = build_dashboard_refresh_package(workspace_id, proof, history, decisions)
    if not original_dashboard:
        original_dashboard = rebuilt_dashboard
    original_checklist = dict(checklist_report or {})
    rebuilt_checklist = build_local_review_checklist(workspace_id, proof, history, decisions, rebuilt_dashboard)
    if not original_checklist:
        original_checklist = rebuilt_checklist
    checks: list[dict[str, Any]] = []
    checks.extend(dashboard_consistency_checks(original_dashboard, rebuilt_dashboard))
    checks.extend(checklist_consistency_checks(original_checklist, rebuilt_checklist))
    checks.append(json_round_trip_check("dashboard", original_dashboard))
    checks.append(json_round_trip_check("checklist", original_checklist))
    checks.append(export_reload_check("dashboard", original_dashboard))
    checks.append(export_reload_check("checklist", original_checklist))
    checks.extend(safety_checks([original_dashboard, rebuilt_dashboard, original_checklist, rebuilt_checklist]))
    summary = summarize_checks(checks)
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "restart_regression_id": "",
        "mode": SHADOW_ONLY,
        "proof_row_count": len(proof),
        "history_row_count": len(history),
        "decision_row_count": len(decisions),
        **summary,
        "check_rows": checks,
        "dashboard_original_fingerprint": package_fingerprint(original_dashboard),
        "dashboard_rebuilt_fingerprint": package_fingerprint(rebuilt_dashboard),
        "checklist_original_fingerprint": package_fingerprint(original_checklist),
        "checklist_rebuilt_fingerprint": package_fingerprint(rebuilt_checklist),
        "rebuilt_dashboard_manifest": rebuilt_dashboard.get("manifest") or {},
        "rebuilt_checklist_summary": {key: rebuilt_checklist.get(key) for key in ("readiness_status", "pass_count", "warn_count", "fail_count", "required_failure_count")},
        "safety_gates": {"live_mutation": FORBIDDEN, "model_training": FORBIDDEN, "stored_data_mutation": FORBIDDEN, "automatic_live_promotion": FORBIDDEN, "source_update": FORBIDDEN},
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "warnings": [row for row in checks if row.get("status") == WARN],
        "errors": [row for row in checks if row.get("status") == FAIL],
    }
    report["restart_regression_id"] = stable_hash("restart_regression", {"workspace_id": workspace_id, "checks": checks}, 24)
    report["restart_regression_hash"] = stable_hash("restart_regression_hash", {key: value for key, value in report.items() if key != "generated_at_utc"}, 32)
    return report


def build_restart_regression_package_from_text(
    workspace_id: str | None = None,
    proof_csv_text: str | None = None,
    history_csv_text: str | None = None,
    decision_preview_csv_text: str | None = None,
    dashboard_json_text: str | None = None,
    checklist_json_text: str | None = None,
) -> dict[str, Any]:
    return build_restart_regression_package(
        workspace_id,
        parse_csv_text(proof_csv_text),
        parse_csv_text(history_csv_text),
        parse_csv_text(decision_preview_csv_text),
        parse_json_object(dashboard_json_text),
        parse_json_object(checklist_json_text),
    )


def export_restart_checks_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("check_rows") or [])


def export_restart_manifest_json(report: Mapping[str, Any]) -> str:
    manifest = {key: report.get(key) for key in ("schema_version", "workspace_id", "restart_regression_id", "restart_regression_hash", "generated_at_utc", "restart_status", "pass_count", "warn_count", "fail_count", "preview_only", "files_written", "live_changes")}
    return json.dumps(_safe(manifest), sort_keys=True, indent=2)
