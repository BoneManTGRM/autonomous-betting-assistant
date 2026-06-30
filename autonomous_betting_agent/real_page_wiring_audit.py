from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.row_normalizer import safe_text

SCHEMA_VERSION = "real_page_wiring_audit_v1"
CANONICAL_WIRING_READY = "CANONICAL WIRING READY"
REVIEW_REQUIRED = "REVIEW REQUIRED"
BLOCKED = "BLOCKED"
WIRED = "WIRED"
PARTIAL = "PARTIAL"
PAGE_REVIEW_REQUIRED = "REVIEW REQUIRED"
PAGE_BLOCKED = "BLOCKED"
PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
SHADOW_ONLY = "SHADOW ONLY"
FORBIDDEN = "FORBIDDEN"

CANONICAL_KEYS = (
    "canonical_locked_ledger",
    "pro_predictor_latest_rows",
    "odds_lock_pro_locked_rows",
    "public_proof_dashboard_refresh_rows",
    "ara_latest_predictions",
)

RECOVERY_TOKENS = (
    "canonical_store_recovery",
    "recover",
    "fallback",
    "disk_fallback",
    "local_json",
    "reload",
    "save_reload",
    "row_count_match",
    "fingerprint",
)

SESSION_TOKENS = ("st.session_state", "session_state")
UNSAFE_TOKENS = (
    "unsafe_write",
    "source_over" + "write",
    "silent_row_change",
    "forced_live",
    "client_secret",
    "book_action",
    "book_login",
)
NO_ROWS_TOKENS = ("no rows found", "no proof rows", "input source: none", "no rows")
REQUIRED_ROLES = ("predictor", "odds_lock", "dashboard", "learning")


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


def source_text(row: Mapping[str, Any]) -> str:
    parts = []
    for key in ("page", "name", "role", "path", "source", "source_text", "snippet", "notes", "recovery", "store", "risk", "mode"):
        value = row.get(key)
        if value:
            parts.append(_text(value))
    return "\n".join(parts)


def page_name(row: Mapping[str, Any], index: int = 0) -> str:
    return _text(row.get("page") or row.get("name") or row.get("path") or f"page_{index}")


def page_role(row: Mapping[str, Any]) -> str:
    text = _text(row.get("role") or row.get("page_role") or row.get("page") or row.get("name") or row.get("path")).lower()
    for role in REQUIRED_ROLES:
        if role in text:
            return role
    if "proof" in text and "dashboard" in text:
        return "dashboard"
    if "lock" in text:
        return "odds_lock"
    if "predict" in text:
        return "predictor"
    if "learn" in text:
        return "learning"
    return _text(row.get("role") or "unknown") or "unknown"


def detected_tokens(text: str, tokens: Sequence[str]) -> list[str]:
    lowered = text.lower()
    return [token for token in tokens if token.lower() in lowered]


def canonical_key_hits(text: str) -> list[str]:
    return detected_tokens(text, CANONICAL_KEYS)


def recovery_hits(text: str) -> list[str]:
    return detected_tokens(text, RECOVERY_TOKENS)


def unsafe_hits(text: str) -> list[str]:
    return detected_tokens(text, UNSAFE_TOKENS)


def no_rows_without_recovery(text: str) -> bool:
    lowered = text.lower()
    has_no_rows = any(token in lowered for token in NO_ROWS_TOKENS)
    has_recovery = bool(recovery_hits(text))
    return has_no_rows and not has_recovery


def evaluate_page_wiring(row: Mapping[str, Any], index: int = 0) -> dict[str, Any]:
    text = source_text(row)
    canonical = canonical_key_hits(text)
    recovery = recovery_hits(text)
    session = detected_tokens(text, SESSION_TOKENS)
    unsafe = unsafe_hits(text)
    no_rows_gap = no_rows_without_recovery(text)
    session_only = bool(session) and not canonical and not recovery
    has_canonical = bool(canonical)
    has_recovery = bool(recovery)

    issues: list[str] = []
    risks: list[dict[str, Any]] = []
    if not has_canonical:
        issues.append("missing canonical key/store reference")
        risks.append({"risk_id": "missing_canonical", "severity": WARN, "details": "No canonical proof store key detected."})
    if not has_recovery:
        issues.append("missing recovery/fallback path")
        risks.append({"risk_id": "missing_recovery", "severity": WARN, "details": "No recovery, fallback, reload, or verification path detected."})
    if session_only:
        issues.append("session-state only dependency")
        risks.append({"risk_id": "session_only", "severity": FAIL, "details": "Page appears to use session state without canonical recovery."})
    if no_rows_gap:
        issues.append("no-rows path lacks recovery attempt")
        risks.append({"risk_id": "no_rows_without_recovery", "severity": FAIL, "details": "No rows messaging detected without recovery tokens."})
    if unsafe:
        issues.append("unsafe source-write indicator")
        risks.append({"risk_id": "unsafe_indicator", "severity": FAIL, "details": ",".join(unsafe)})

    if any(risk["severity"] == FAIL for risk in risks):
        status = PAGE_BLOCKED
    elif has_canonical and has_recovery:
        status = WIRED
    elif has_canonical or has_recovery:
        status = PARTIAL
    else:
        status = PAGE_REVIEW_REQUIRED

    return {
        "page_index": index,
        "page_name": page_name(row, index),
        "page_role": page_role(row),
        "path": _text(row.get("path")),
        "status": status,
        "has_canonical_store_reference": has_canonical,
        "has_recovery_path": has_recovery,
        "uses_session_state": bool(session),
        "session_state_only": session_only,
        "no_rows_without_recovery": no_rows_gap,
        "unsafe_indicator_count": len(unsafe),
        "canonical_key_hits": canonical,
        "recovery_hits": recovery,
        "session_hits": session,
        "unsafe_hits": unsafe,
        "issues": issues,
        "risk_count": len(risks),
        "risks": risks,
        "page_hash": stable_hash("page_wiring", {"page": row, "status": status, "issues": issues}, 20),
    }


def flatten_page_risks(page_results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in page_results or []:
        for risk in page.get("risks") or []:
            rows.append({
                "page_name": page.get("page_name"),
                "page_role": page.get("page_role"),
                "page_status": page.get("status"),
                "risk_id": risk.get("risk_id"),
                "severity": risk.get("severity"),
                "details": risk.get("details"),
            })
    return rows


def check_row(check_id: str, title: str, status: str, details: str = "", expected: Any = "", actual: Any = "") -> dict[str, Any]:
    return {"check_id": check_id, "title": title, "status": status, "details": details, "expected": expected, "actual": actual}


def system_checks(page_results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    pages = [dict(row) for row in page_results or []]
    statuses = Counter(row.get("status") for row in pages)
    role_text = " ".join(_text(row.get("page_role")).lower() for row in pages)
    checks = [check_row("page_inventory_present", "Page inventory supplied", PASS if pages else FAIL, details=f"pages={len(pages)}")]
    for role in REQUIRED_ROLES:
        checks.append(check_row(f"required_role_{role}", f"Required role present: {role}", PASS if role in role_text else WARN, actual=role_text))
    checks.append(check_row("no_blocked_pages", "No blocked page wiring", PASS if not statuses.get(PAGE_BLOCKED) else FAIL, details=f"blocked={statuses.get(PAGE_BLOCKED, 0)}"))
    checks.append(check_row("canonical_pages_present", "At least one page references canonical store", PASS if any(row.get("has_canonical_store_reference") for row in pages) else WARN))
    checks.append(check_row("recovery_pages_present", "At least one page references recovery/fallback", PASS if any(row.get("has_recovery_path") for row in pages) else WARN))
    checks.append(check_row("no_session_only_pages", "No session-state-only pages", PASS if not any(row.get("session_state_only") for row in pages) else FAIL))
    checks.append(check_row("no_unrecovered_no_rows_paths", "No unrecovered no-rows paths", PASS if not any(row.get("no_rows_without_recovery") for row in pages) else FAIL))
    checks.append(check_row("no_unsafe_indicators", "No unsafe source-write indicators", PASS if not any(int(row.get("unsafe_indicator_count") or 0) for row in pages) else FAIL))
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
        status = CANONICAL_WIRING_READY
    return {"system_status": status, "pass_count": pass_count, "warn_count": warn_count, "fail_count": fail_count}


def next_actions(page_results: Sequence[Mapping[str, Any]], checks: Sequence[Mapping[str, Any]]) -> list[str]:
    actions: list[str] = []
    if not page_results:
        actions.append("Provide page inventory rows or source snippets before treating wiring as verified.")
    for page in page_results or []:
        name = _text(page.get("page_name"))
        if page.get("session_state_only"):
            actions.append(f"Wire {name} through canonical recovery before relying on session state.")
        if not page.get("has_canonical_store_reference"):
            actions.append(f"Add canonical store key reference to {name} or document its shared source.")
        if not page.get("has_recovery_path"):
            actions.append(f"Add fallback/recovery/reload verification path to {name}.")
        if page.get("no_rows_without_recovery"):
            actions.append(f"Replace unrecovered 'no rows' path in {name} with recovery attempt first.")
        if int(page.get("unsafe_indicator_count") or 0):
            actions.append(f"Review unsafe source-write indicators in {name} before promotion.")
    if any(row.get("status") == FAIL for row in checks or []):
        actions.append("Do not close proof persistence hardening until blocked wiring checks are cleared.")
    return list(dict.fromkeys(actions))[:25]


def build_real_page_wiring_audit(workspace_id: str | None = None, page_rows: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    pages = [dict(row) for row in page_rows or []]
    page_results = [evaluate_page_wiring(row, index) for index, row in enumerate(pages)]
    checks = system_checks(page_results)
    summary = summarize_checks(checks)
    risks = flatten_page_risks(page_results)
    status_counts = Counter(row.get("status") for row in page_results)
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "mode": SHADOW_ONLY,
        **summary,
        "page_count": len(page_results),
        "wired_count": status_counts.get(WIRED, 0),
        "partial_count": status_counts.get(PARTIAL, 0),
        "review_required_count": status_counts.get(PAGE_REVIEW_REQUIRED, 0),
        "blocked_count": status_counts.get(PAGE_BLOCKED, 0),
        "canonical_key_inventory": list(CANONICAL_KEYS),
        "required_roles": list(REQUIRED_ROLES),
        "page_results": page_results,
        "system_checks": checks,
        "risk_summary": risks,
        "next_actions": next_actions(page_results, checks),
        "safety_gates": {
            "live_path": FORBIDDEN,
            "learning_path": FORBIDDEN,
            "stored_data_change": FORBIDDEN,
            "promotion": FORBIDDEN,
            "proof_write": FORBIDDEN,
            "book_action": FORBIDDEN,
            "external_api_calls": FORBIDDEN,
        },
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "warnings": [row for row in checks if row.get("status") == WARN],
        "errors": [row for row in checks if row.get("status") == FAIL],
    }
    report["wiring_id"] = stable_hash("page_wiring", {"workspace_id": workspace_id, "pages": page_results, "checks": checks}, 24)
    report["wiring_hash"] = stable_hash("page_wiring_hash", {key: value for key, value in report.items() if key != "generated_at_utc"}, 32)
    return report


def build_real_page_wiring_audit_from_text(workspace_id: str | None = None, page_inventory_csv_text: str | None = None) -> dict[str, Any]:
    return build_real_page_wiring_audit(workspace_id, parse_csv_text(page_inventory_csv_text))


def export_wiring_audit_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_wiring_page_summary_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("page_results") or [])


def export_wiring_risk_summary_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("risk_summary") or [])


def export_wiring_checks_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("system_checks") or [])


def export_wiring_manifest_json(report: Mapping[str, Any]) -> str:
    manifest = {key: report.get(key) for key in ("schema_version", "workspace_id", "wiring_id", "wiring_hash", "generated_at_utc", "system_status", "page_count", "wired_count", "partial_count", "review_required_count", "blocked_count", "pass_count", "warn_count", "fail_count", "preview_only", "files_written", "live_changes")}
    return json.dumps(_safe(manifest), sort_keys=True, indent=2)
