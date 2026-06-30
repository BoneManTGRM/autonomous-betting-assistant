from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.subscriber_ledger import safe_float

SCHEMA_VERSION = "subscriber_export_center_v1"
PREVIEW_ONLY = "PREVIEW ONLY"
FORBIDDEN = "FORBIDDEN"
READY = "EXPORT CENTER READY"
REVIEW = "REVIEW REQUIRED"
BLOCKED = "BLOCKED"
PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

EXPORT_TYPES = (
    "subscriber_report_json",
    "subscriber_ledger_csv",
    "client_safe_summary_json",
    "admin_audit_json",
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


def check_row(check_id: str, title: str, status: str, details: str = "", expected: Any = "", actual: Any = "") -> dict[str, Any]:
    return {"check_id": check_id, "title": title, "status": status, "details": details, "expected": expected, "actual": actual}


def profile_rows_from_sources(intelligence_report: Mapping[str, Any], profile_rows: Sequence[Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    if profile_rows:
        return [dict(row) for row in profile_rows]
    rows = intelligence_report.get("profiles") or []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def subscriber_reports_from_intelligence(intelligence_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = intelligence_report.get("subscriber_reports") or []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def ledger_summaries_from_report(ledger_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = ledger_report.get("subscriber_summaries") or []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def ledger_rows_from_report(ledger_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = ledger_report.get("ledger_rows") or []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def subscriber_key(row: Mapping[str, Any]) -> str:
    return _text(row.get("subscriber_id") or row.get("id") or row.get("subscriber") or row.get("name")) or "unknown_subscriber"


def profile_map(profiles: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {subscriber_key(row): dict(row) for row in profiles or []}


def report_map(reports: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {subscriber_key(row): dict(row) for row in reports or []}


def ledger_summary_map(summaries: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {subscriber_key(row): dict(row) for row in summaries or [] if subscriber_key(row) != "GLOBAL"}


def ledger_rows_by_subscriber(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows or []:
        output[subscriber_key(row)].append(dict(row))
    return output


def safe_client_row(row: Mapping[str, Any]) -> dict[str, Any]:
    allowed = (
        "subscriber_id",
        "subscriber_name",
        "event",
        "sport",
        "sportsbook",
        "market_type",
        "selection",
        "decimal_odds",
        "minimum_playable_odds",
        "calibrated_probability",
        "ev",
        "edge",
        "risk_label",
        "personal_action",
        "filter_reason",
        "recommended_stake",
        "why",
        "why_not",
    )
    return {key: _safe(row.get(key)) for key in allowed if key in row}


def build_export_package(profile: Mapping[str, Any], report: Mapping[str, Any] | None, ledger_summary: Mapping[str, Any] | None, ledger_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    sid = subscriber_key(profile)
    recs = [dict(row) for row in (report or {}).get("recommendations") or []]
    client_rows = [safe_client_row(row) for row in recs]
    ledger_list = [dict(row) for row in ledger_rows or []]
    package = {
        "subscriber_id": sid,
        "subscriber_name": _text(profile.get("name") or (report or {}).get("subscriber_name")) or sid,
        "enabled": _text(profile.get("enabled") or "true").lower() not in {"false", "0", "disabled", "no"},
        "partner": _text(profile.get("partner") or "direct"),
        "plan": _text(profile.get("plan") or "starter"),
        "risk_level": _text(profile.get("risk_level") or "balanced"),
        "has_report": bool(report),
        "has_ledger": bool(ledger_summary),
        "recommendation_count": len(recs),
        "bet_count": int((report or {}).get("bet_count") or 0),
        "watch_count": int((report or {}).get("watch_count") or 0),
        "wait_count": int((report or {}).get("wait_count") or 0),
        "no_bet_count": int((report or {}).get("no_bet_count") or 0),
        "ledger_row_count": int((ledger_summary or {}).get("row_count") or len(ledger_list)),
        "unique_event_count": int((ledger_summary or {}).get("unique_event_count") or 0),
        "win_rate_ex_push_cancel": (ledger_summary or {}).get("win_rate_ex_push_cancel"),
        "roi": (ledger_summary or {}).get("roi"),
        "profit_loss": (ledger_summary or {}).get("profit_loss"),
        "stake": (ledger_summary or {}).get("stake"),
        "client_safe_rows": client_rows,
        "ledger_rows": ledger_list,
        "allowed_exports": list(EXPORT_TYPES),
        "package_status": "READY" if report and ledger_summary else "REVIEW REQUIRED",
    }
    package["subscriber_report_hash"] = (report or {}).get("report_hash") or stable_hash("empty_report", {"subscriber_id": sid}, 12)
    package["ledger_summary_hash"] = stable_hash("ledger_summary", ledger_summary or {}, 16)
    package["package_id"] = stable_hash("subscriber_package", package, 18)
    return package


def build_export_packages(profiles: Sequence[Mapping[str, Any]], subscriber_reports: Sequence[Mapping[str, Any]], ledger_summaries: Sequence[Mapping[str, Any]], ledger_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    profiles_by_id = profile_map(profiles)
    reports_by_id = report_map(subscriber_reports)
    ledgers_by_id = ledger_summary_map(ledger_summaries)
    rows_by_id = ledger_rows_by_subscriber(ledger_rows)
    all_ids = sorted(set(profiles_by_id) | set(reports_by_id) | set(ledgers_by_id) | set(rows_by_id))
    packages = []
    for sid in all_ids:
        profile = profiles_by_id.get(sid) or {"subscriber_id": sid, "name": sid, "enabled": True, "partner": "unknown", "plan": "unknown", "risk_level": "unknown"}
        packages.append(build_export_package(profile, reports_by_id.get(sid), ledgers_by_id.get(sid), rows_by_id.get(sid, [])))
    return packages


def package_index_rows(packages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for package in packages or []:
        rows.append({
            "package_id": package.get("package_id"),
            "subscriber_id": package.get("subscriber_id"),
            "subscriber_name": package.get("subscriber_name"),
            "partner": package.get("partner"),
            "plan": package.get("plan"),
            "risk_level": package.get("risk_level"),
            "package_status": package.get("package_status"),
            "has_report": package.get("has_report"),
            "has_ledger": package.get("has_ledger"),
            "recommendation_count": package.get("recommendation_count"),
            "bet_count": package.get("bet_count"),
            "no_bet_count": package.get("no_bet_count"),
            "ledger_row_count": package.get("ledger_row_count"),
            "unique_event_count": package.get("unique_event_count"),
            "win_rate_ex_push_cancel": package.get("win_rate_ex_push_cancel"),
            "roi": package.get("roi"),
            "profit_loss": package.get("profit_loss"),
            "allowed_exports": ",".join(package.get("allowed_exports") or []),
        })
    return rows


def partner_summary(packages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for package in packages or []:
        groups[_text(package.get("partner")) or "unknown"].append(package)
    rows = []
    for partner, group in sorted(groups.items()):
        rows.append({
            "partner": partner,
            "subscriber_count": len(group),
            "ready_packages": sum(1 for row in group if row.get("package_status") == "READY"),
            "bet_count": sum(int(row.get("bet_count") or 0) for row in group),
            "no_bet_count": sum(int(row.get("no_bet_count") or 0) for row in group),
            "profit_loss": round(sum(float(row.get("profit_loss") or 0.0) for row in group), 6),
            "stake": round(sum(float(row.get("stake") or 0.0) for row in group), 6),
        })
    return rows


def distribution_rows(packages: Sequence[Mapping[str, Any]], field: str) -> list[dict[str, Any]]:
    counts = Counter(_text(package.get(field)) or "unknown" for package in packages or [])
    return [{field: key, "subscriber_count": value} for key, value in sorted(counts.items())]


def admin_dashboard_summary(packages: Sequence[Mapping[str, Any]], intelligence_report: Mapping[str, Any], ledger_report: Mapping[str, Any]) -> dict[str, Any]:
    total_stake = sum(float(package.get("stake") or 0.0) for package in packages or [])
    total_pnl = sum(float(package.get("profit_loss") or 0.0) for package in packages or [])
    return {
        "subscriber_count": len(packages),
        "ready_package_count": sum(1 for package in packages if package.get("package_status") == "READY"),
        "review_required_count": sum(1 for package in packages if package.get("package_status") != "READY"),
        "total_recommendation_rows": sum(int(package.get("recommendation_count") or 0) for package in packages),
        "total_bet_count": sum(int(package.get("bet_count") or 0) for package in packages),
        "total_no_bet_count": sum(int(package.get("no_bet_count") or 0) for package in packages),
        "total_ledger_rows": sum(int(package.get("ledger_row_count") or 0) for package in packages),
        "total_unique_events": sum(int(package.get("unique_event_count") or 0) for package in packages),
        "total_profit_loss": round(total_pnl, 6),
        "total_stake": round(total_stake, 6),
        "portfolio_roi": round(total_pnl / total_stake, 6) if total_stake > 0 else None,
        "source_subscriber_hash": intelligence_report.get("subscriber_hash"),
        "source_ledger_hash": ledger_report.get("ledger_hash"),
    }


def validate_export_center(intelligence_report: Mapping[str, Any], ledger_report: Mapping[str, Any], packages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    checks = []
    checks.append(check_row("intelligence_report_present", "Subscriber intelligence report supplied", PASS if intelligence_report else FAIL))
    checks.append(check_row("ledger_report_present", "Subscriber ledger report supplied", PASS if ledger_report else FAIL))
    checks.append(check_row("export_packages_created", "Subscriber export packages created", PASS if packages else FAIL, details=f"packages={len(packages)}"))
    missing_report = [package.get("subscriber_id") for package in packages if not package.get("has_report")]
    missing_ledger = [package.get("subscriber_id") for package in packages if not package.get("has_ledger")]
    checks.append(check_row("missing_reports", "Every package has a report", PASS if not missing_report else WARN, actual=missing_report))
    checks.append(check_row("missing_ledgers", "Every package has a ledger summary", PASS if not missing_ledger else WARN, actual=missing_ledger))
    checks.append(check_row("client_safe_rows_created", "Client-safe rows generated", PASS if any(package.get("client_safe_rows") for package in packages) else WARN))
    checks.append(check_row("source_preview_only", "Source reports are preview-only", PASS if intelligence_report.get("preview_only", True) and ledger_report.get("preview_only", True) else FAIL))
    checks.append(check_row("no_live_changes", "No live changes reported", PASS if int(intelligence_report.get("live_changes") or 0) == 0 and int(ledger_report.get("live_changes") or 0) == 0 else FAIL))
    return checks


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
    return {"export_status": status, "pass_count": pass_count, "warn_count": warn_count, "fail_count": fail_count}


def build_subscriber_export_center(
    workspace_id: str | None = None,
    intelligence_report: Mapping[str, Any] | None = None,
    ledger_report: Mapping[str, Any] | None = None,
    profile_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    intelligence = dict(intelligence_report or {})
    ledger = dict(ledger_report or {})
    profiles = profile_rows_from_sources(intelligence, profile_rows)
    reports = subscriber_reports_from_intelligence(intelligence)
    ledger_summaries = ledger_summaries_from_report(ledger)
    ledger_rows = ledger_rows_from_report(ledger)
    packages = build_export_packages(profiles, reports, ledger_summaries, ledger_rows)
    index_rows = package_index_rows(packages)
    checks = validate_export_center(intelligence, ledger, packages)
    summary = summarize_checks(checks)
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or _text(intelligence.get("workspace_id") or ledger.get("workspace_id")) or "default",
        "mode": PREVIEW_ONLY,
        **summary,
        "admin_dashboard_summary": admin_dashboard_summary(packages, intelligence, ledger),
        "package_count": len(packages),
        "export_packages": packages,
        "package_index_rows": index_rows,
        "partner_summary_rows": partner_summary(packages),
        "plan_distribution_rows": distribution_rows(packages, "plan"),
        "risk_distribution_rows": distribution_rows(packages, "risk_level"),
        "export_checks": checks,
        "allowed_export_types": list(EXPORT_TYPES),
        "safety_gates": {
            "billing_charge_execution": FORBIDDEN,
            "api_key_exposure": FORBIDDEN,
            "live_wager_execution": FORBIDDEN,
            "account_access": FORBIDDEN,
            "funds_movement": FORBIDDEN,
            "automatic_proof_change": FORBIDDEN,
            "automatic_model_change": FORBIDDEN,
            "profit_guarantee": FORBIDDEN,
        },
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "warnings": [row for row in checks if row.get("status") == WARN],
        "errors": [row for row in checks if row.get("status") == FAIL],
    }
    report["export_run_id"] = stable_hash("subscriber_export", {"workspace_id": report["workspace_id"], "packages": index_rows}, 24)
    report["export_hash"] = stable_hash("subscriber_export_hash", {key: value for key, value in report.items() if key != "generated_at_utc"}, 32)
    return report


def build_subscriber_export_center_from_text(
    workspace_id: str | None = None,
    intelligence_json_text: str | None = None,
    ledger_json_text: str | None = None,
    profiles_csv_text: str | None = None,
) -> dict[str, Any]:
    return build_subscriber_export_center(workspace_id, parse_json_object(intelligence_json_text), parse_json_object(ledger_json_text), parse_csv_text(profiles_csv_text))


def export_subscriber_export_center_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_package_index_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("package_index_rows") or [])


def export_partner_summary_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("partner_summary_rows") or [])


def export_plan_distribution_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("plan_distribution_rows") or [])


def export_risk_distribution_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("risk_distribution_rows") or [])


def export_client_safe_rows_csv(report: Mapping[str, Any]) -> str:
    rows = []
    for package in report.get("export_packages") or []:
        for row in package.get("client_safe_rows") or []:
            rows.append({"package_id": package.get("package_id"), **dict(row)})
    return csv_from_rows(rows)


def export_admin_dashboard_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report.get("admin_dashboard_summary") or {}), sort_keys=True, indent=2)


def export_export_checks_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("export_checks") or [])


def export_export_manifest_json(report: Mapping[str, Any]) -> str:
    manifest = {key: report.get(key) for key in ("schema_version", "workspace_id", "export_run_id", "export_hash", "generated_at_utc", "export_status", "package_count", "preview_only", "files_written", "live_changes")}
    return json.dumps(_safe(manifest), sort_keys=True, indent=2)
