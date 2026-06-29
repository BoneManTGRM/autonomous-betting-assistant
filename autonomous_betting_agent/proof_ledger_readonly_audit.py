from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.dashboard_refresh_package import result_status
from autonomous_betting_agent.odds_reparodynamics_upgrade_layer import event_key, market_type, sportsbook
from autonomous_betting_agent.value_math import safe_float

SCHEMA_VERSION = "proof_ledger_readonly_audit_v1"
READ_ONLY_SAFE = "READ ONLY SAFE"
REVIEW_REQUIRED = "REVIEW REQUIRED"
BLOCKED = "BLOCKED"
PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
SHADOW_ONLY = "SHADOW ONLY"
FORBIDDEN = "FORBIDDEN"


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


def parse_json_object(json_text: str | None) -> dict[str, Any]:
    text = _text(json_text)
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {"parse_error": "invalid_json"}
    return value if isinstance(value, dict) else {"parse_error": "json_root_not_object"}


def row_identifier(row: Mapping[str, Any], index: int) -> str:
    for key in ("proof_id", "pick_id", "row_id", "id", "hash"):
        if _text(row.get(key)):
            return _text(row.get(key))
    return f"row_{index}"


def dataset_fingerprint(rows: Sequence[Mapping[str, Any]]) -> str:
    normalized = []
    for index, row in enumerate(rows or []):
        normalized.append({"row_id": row_identifier(row, index), "event_key": event_key(row), "status": result_status(row), "row": dict(row)})
    return stable_hash("dataset", normalized, 32)


def summarize_dataset(name: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    records = [dict(row) for row in rows or []]
    statuses = [result_status(row) for row in records]
    status_counts = Counter(statuses)
    events = [event_key(row) for row in records]
    duplicate_count = len([event for event, count in Counter(events).items() if count > 1])
    profit_values = []
    for row in records:
        for key in ("profit_units", "unit_profit", "pnl_units", "net_units", "profit", "net_profit"):
            value = safe_float(row.get(key))
            if value is not None:
                profit_values.append(value)
                break
    return {
        "dataset_name": name,
        "row_count": len(records),
        "unique_event_count": len(set(events)),
        "duplicate_event_group_count": duplicate_count,
        "wins": status_counts.get("win", 0),
        "losses": status_counts.get("loss", 0),
        "pushes": status_counts.get("push", 0),
        "cancels": status_counts.get("cancel", 0),
        "pending": status_counts.get("pending", 0),
        "unknown": status_counts.get("unknown", 0),
        "profit_units_sum": round(sum(profit_values), 8) if profit_values else None,
        "dataset_fingerprint": dataset_fingerprint(records),
    }


def check_row(check_id: str, title: str, status: str, details: str = "", expected: Any = "", actual: Any = "") -> dict[str, Any]:
    return {"check_id": check_id, "title": title, "status": status, "details": details, "expected": expected, "actual": actual}


def compare_summaries(source: Mapping[str, Any], other: Mapping[str, Any], fields: Sequence[str]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    name = _text(other.get("dataset_name")) or "dataset"
    for field in fields:
        expected = source.get(field)
        actual = other.get(field)
        status = PASS if expected == actual else WARN
        checks.append(check_row(f"{name}_{field}", f"{name} matches source {field}", status, expected=expected, actual=actual))
    return checks


def page_inventory_checks(page_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    pages = [dict(row) for row in page_rows or []]
    checks: list[dict[str, Any]] = []
    expected_roles = ("predictor", "odds_lock", "dashboard", "learning")
    role_text = " ".join(_text(row.get("role") or row.get("page_role") or row.get("page") or row.get("name")).lower() for row in pages)
    for role in expected_roles:
        checks.append(check_row(f"page_role_{role}", f"Page role present: {role}", PASS if role in role_text else WARN, actual=role_text))
    mutation_flags = []
    for row in pages:
        flag_text = " ".join(_text(row.get(key)).lower() for key in ("mutation_flag", "mutates", "mode", "notes", "risk"))
        if any(token in flag_text for token in ("mutate", "overwrite", "delete", "destructive", "live change")):
            mutation_flags.append(row)
    checks.append(check_row("page_inventory_present", "Page inventory supplied", PASS if pages else WARN, details=f"pages={len(pages)}"))
    checks.append(check_row("page_mutation_flags", "No page mutation flags", FAIL if mutation_flags else PASS, details=f"mutation_flags={len(mutation_flags)}"))
    canonical_count = len([row for row in pages if "canonical" in _text(row).lower() or "shared" in _text(row).lower()])
    checks.append(check_row("canonical_source_declared", "Canonical/shared source declared", PASS if canonical_count else WARN, details=f"canonical_mentions={canonical_count}"))
    return checks


def store_inventory_checks(store_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    stores = [dict(row) for row in store_rows or []]
    checks = [check_row("store_inventory_present", "Store inventory supplied", PASS if stores else WARN, details=f"stores={len(stores)}")]
    canonical = [row for row in stores if "canonical" in _text(row).lower() or "primary" in _text(row).lower()]
    checks.append(check_row("store_canonical_present", "Canonical store identified", PASS if canonical else WARN, details=f"canonical_stores={len(canonical)}"))
    unsafe = []
    for row in stores:
        mode = " ".join(_text(row.get(key)).lower() for key in ("mode", "risk", "notes", "mutation_flag"))
        if any(token in mode for token in ("overwrite", "delete", "destructive", "mutable live")):
            unsafe.append(row)
    checks.append(check_row("store_unsafe_flags", "No unsafe store flags", FAIL if unsafe else PASS, details=f"unsafe_stores={len(unsafe)}"))
    return checks


def handoff_checks(source_summary: Mapping[str, Any], dataset_summaries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    fields = ("row_count", "unique_event_count", "wins", "losses", "pushes", "cancels")
    for summary in dataset_summaries:
        if summary.get("dataset_name") == source_summary.get("dataset_name") or not summary.get("row_count"):
            continue
        checks.extend(compare_summaries(source_summary, summary, fields))
    return checks


def duplicate_event_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(rows or []):
        groups[event_key(row)].append({"row_index": index, "row_id": row_identifier(row, index), "event_key": event_key(row), "market_type": market_type(row), "sportsbook": sportsbook(row), "status": result_status(row)})
    return [{"event_key": key, "row_count": len(group), "rows": group} for key, group in sorted(groups.items()) if len(group) > 1]


def summarize_checks(checks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    pass_count = len([row for row in checks or [] if row.get("status") == PASS])
    warn_count = len([row for row in checks or [] if row.get("status") == WARN])
    fail_count = len([row for row in checks or [] if row.get("status") == FAIL])
    if fail_count:
        status = BLOCKED
    elif warn_count:
        status = REVIEW_REQUIRED
    else:
        status = READ_ONLY_SAFE
    return {"audit_status": status, "pass_count": pass_count, "warn_count": warn_count, "fail_count": fail_count}


def build_proof_ledger_readonly_audit(
    workspace_id: str | None = None,
    proof_rows: Sequence[Mapping[str, Any]] | None = None,
    learning_rows: Sequence[Mapping[str, Any]] | None = None,
    dashboard_rows: Sequence[Mapping[str, Any]] | None = None,
    decision_rows: Sequence[Mapping[str, Any]] | None = None,
    page_inventory_rows: Sequence[Mapping[str, Any]] | None = None,
    store_inventory_rows: Sequence[Mapping[str, Any]] | None = None,
    dashboard_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    proof = [dict(row) for row in proof_rows or []]
    learning = [dict(row) for row in learning_rows or []]
    dashboard = [dict(row) for row in dashboard_rows or []]
    decision = [dict(row) for row in decision_rows or []]
    page_inventory = [dict(row) for row in page_inventory_rows or []]
    store_inventory = [dict(row) for row in store_inventory_rows or []]
    summaries = [
        summarize_dataset("proof", proof),
        summarize_dataset("learning", learning),
        summarize_dataset("dashboard", dashboard),
        summarize_dataset("decision", decision),
    ]
    source_summary = summaries[0]
    checks: list[dict[str, Any]] = []
    checks.append(check_row("proof_rows_present", "Proof/source rows supplied", PASS if proof else FAIL, details=f"proof_rows={len(proof)}"))
    checks.append(check_row("dashboard_report_safe", "Dashboard report remains read-only", PASS if not dashboard_report or (dashboard_report.get("preview_only", True) is True and int(dashboard_report.get("live_changes") or 0) == 0) else FAIL, details=f"preview_only={(dashboard_report or {}).get('preview_only', True)}"))
    checks.extend(handoff_checks(source_summary, summaries))
    checks.extend(page_inventory_checks(page_inventory))
    checks.extend(store_inventory_checks(store_inventory))
    duplicates = duplicate_event_rows(proof)
    checks.append(check_row("duplicate_event_groups", "Duplicate event groups identified", WARN if duplicates else PASS, details=f"duplicate_event_groups={len(duplicates)}"))
    report_parse_error = dashboard_report.get("parse_error") if isinstance(dashboard_report, Mapping) else None
    checks.append(check_row("dashboard_json_parse", "Dashboard JSON parse check", FAIL if report_parse_error else PASS, details=_text(report_parse_error)))
    summary = summarize_checks(checks)
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "audit_id": "",
        "mode": SHADOW_ONLY,
        **summary,
        "proof_row_count": len(proof),
        "learning_row_count": len(learning),
        "dashboard_row_count": len(dashboard),
        "decision_row_count": len(decision),
        "page_inventory_count": len(page_inventory),
        "store_inventory_count": len(store_inventory),
        "dataset_summaries": summaries,
        "audit_checks": checks,
        "duplicate_event_groups": duplicates,
        "page_inventory": page_inventory,
        "store_inventory": store_inventory,
        "safety_gates": {"live_mutation": FORBIDDEN, "model_training": FORBIDDEN, "stored_data_mutation": FORBIDDEN, "automatic_live_promotion": FORBIDDEN, "source_change": FORBIDDEN},
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "warnings": [row for row in checks if row.get("status") == WARN],
        "errors": [row for row in checks if row.get("status") == FAIL],
    }
    report["audit_id"] = stable_hash("proof_audit", {"workspace_id": workspace_id, "checks": checks, "summaries": summaries}, 24)
    report["audit_hash"] = stable_hash("proof_audit_hash", {key: value for key, value in report.items() if key != "generated_at_utc"}, 32)
    return report


def build_proof_ledger_readonly_audit_from_text(
    workspace_id: str | None = None,
    proof_csv_text: str | None = None,
    learning_csv_text: str | None = None,
    dashboard_csv_text: str | None = None,
    decision_csv_text: str | None = None,
    page_inventory_csv_text: str | None = None,
    store_inventory_csv_text: str | None = None,
    dashboard_json_text: str | None = None,
) -> dict[str, Any]:
    return build_proof_ledger_readonly_audit(
        workspace_id,
        parse_csv_text(proof_csv_text),
        parse_csv_text(learning_csv_text),
        parse_csv_text(dashboard_csv_text),
        parse_csv_text(decision_csv_text),
        parse_csv_text(page_inventory_csv_text),
        parse_csv_text(store_inventory_csv_text),
        parse_json_object(dashboard_json_text),
    )


def export_proof_audit_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_proof_audit_checks_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("audit_checks") or [])


def export_proof_audit_summaries_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("dataset_summaries") or [])


def export_proof_audit_duplicates_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("duplicate_event_groups") or [])


def export_proof_audit_manifest_json(report: Mapping[str, Any]) -> str:
    manifest = {key: report.get(key) for key in ("schema_version", "workspace_id", "audit_id", "audit_hash", "generated_at_utc", "audit_status", "pass_count", "warn_count", "fail_count", "preview_only", "files_written", "live_changes")}
    return json.dumps(_safe(manifest), sort_keys=True, indent=2)
