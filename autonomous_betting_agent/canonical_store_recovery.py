from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.odds_reparodynamics_upgrade_layer import event_key
from autonomous_betting_agent.row_normalizer import safe_text

SCHEMA_VERSION = "canonical_store_recovery_v1"
RECOVERY_SAFE = "CANONICAL RECOVERY SAFE"
REVIEW_REQUIRED = "REVIEW REQUIRED"
BLOCKED = "BLOCKED"
PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
SHADOW_ONLY = "SHADOW ONLY"
FORBIDDEN = "FORBIDDEN"

CANONICAL_STORE_KEYS = (
    "canonical_locked_ledger",
    "pro_predictor_latest_rows",
    "odds_lock_pro_locked_rows",
    "public_proof_dashboard_refresh_rows",
    "ara_latest_predictions",
)

RECOVERY_PRIORITY = (
    "canonical_store",
    "disk_fallback",
    "local_json_fallback",
    "session_state",
    "odds_lock",
    "dashboard",
    "predictor",
    "learning",
)

MINIMUM_REQUIRED_COLUMNS = ("proof_id", "event", "selection")
RESULT_COLUMNS = ("result", "status", "outcome", "grade")


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


def parse_json_object(json_text: str | None) -> dict[str, Any]:
    text = _text(json_text)
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {"parse_error": "invalid_json"}
    return value if isinstance(value, dict) else {"parse_error": "json_root_not_object"}


def normalize_workspace_id(value: Any) -> str:
    text = _text(value).lower().replace(" ", "_")
    return "".join(ch for ch in text if ch.isalnum() or ch in ("_", "-")) or "default"


def row_identifier(row: Mapping[str, Any], index: int = 0) -> str:
    for key in ("proof_id", "pick_id", "row_id", "id", "hash"):
        value = _text(row.get(key))
        if value:
            return value
    fallback = {"index": index, "event_key": event_key(row), "selection": row.get("selection") or row.get("pick") or row.get("team")}
    return stable_hash("row", fallback, 16)


def proof_id(row: Mapping[str, Any]) -> str:
    return _text(row.get("proof_id"))


def dataset_fingerprint(rows: Sequence[Mapping[str, Any]]) -> str:
    normalized = []
    for index, row in enumerate(rows or []):
        normalized.append({"row_id": row_identifier(row, index), "event_key": event_key(row), "row": dict(row)})
    return stable_hash("dataset", normalized, 32)


def required_column_report(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    records = [dict(row) for row in rows or []]
    columns = set()
    for row in records:
        columns.update(str(key) for key in row.keys())
    missing_minimum = [column for column in MINIMUM_REQUIRED_COLUMNS if column not in columns]
    has_result_column = any(column in columns for column in RESULT_COLUMNS)
    return {
        "available_columns": sorted(columns),
        "missing_minimum_columns": missing_minimum,
        "has_result_column": has_result_column,
        "missing_result_column": not has_result_column,
    }


def duplicate_proof_id_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for index, row in enumerate(rows or []):
        pid = proof_id(row)
        if not pid:
            continue
        groups.setdefault(pid, []).append({"row_index": index, "proof_id": pid, "event_key": event_key(row), "row": dict(row)})
    return [{"proof_id": key, "row_count": len(group), "rows": group} for key, group in sorted(groups.items()) if len(group) > 1]


def dedupe_by_proof_id(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    deduped: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows or []):
        record = dict(row)
        pid = proof_id(record)
        if pid and pid in seen:
            duplicates.append({"row_index": index, "proof_id": pid, "event_key": event_key(record), "dropped": record})
            continue
        if pid:
            seen.add(pid)
        deduped.append(record)
    return {"rows": deduped, "duplicates": duplicates, "duplicate_count": len(duplicates)}


def workspace_mismatches(rows: Sequence[Mapping[str, Any]], workspace_id: str) -> list[dict[str, Any]]:
    target = normalize_workspace_id(workspace_id)
    mismatches = []
    for index, row in enumerate(rows or []):
        row_workspace = normalize_workspace_id(row.get("workspace_id") or row.get("workspace") or row.get("test_window_id") or target)
        if row_workspace != target:
            mismatches.append({"row_index": index, "row_workspace_id": row_workspace, "expected_workspace_id": target, "row_id": row_identifier(row, index)})
    return mismatches


def summarize_store(name: str, rows: Sequence[Mapping[str, Any]], workspace_id: str | None = None) -> dict[str, Any]:
    records = [dict(row) for row in rows or []]
    required = required_column_report(records)
    deduped = dedupe_by_proof_id(records)
    return {
        "store_name": name,
        "row_count": len(records),
        "deduped_row_count": len(deduped["rows"]),
        "unique_event_count": len({event_key(row) for row in records}),
        "duplicate_proof_id_count": deduped["duplicate_count"],
        "missing_minimum_columns": required["missing_minimum_columns"],
        "missing_result_column": required["missing_result_column"],
        "workspace_mismatch_count": len(workspace_mismatches(records, workspace_id or "default")),
        "dataset_fingerprint": dataset_fingerprint(records),
        "deduped_fingerprint": dataset_fingerprint(deduped["rows"]),
    }


def check_row(check_id: str, title: str, status: str, details: str = "", expected: Any = "", actual: Any = "") -> dict[str, Any]:
    return {"check_id": check_id, "title": title, "status": status, "details": details, "expected": expected, "actual": actual}


def resolve_canonical_store(store_map: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    snapshots = {name: [dict(row) for row in rows or []] for name, rows in store_map.items()}
    for name in RECOVERY_PRIORITY:
        rows = snapshots.get(name) or []
        if rows:
            deduped = dedupe_by_proof_id(rows)
            recovered_from_fallback = name != "canonical_store"
            return {
                "resolved_store_name": name,
                "resolved_rows": deduped["rows"],
                "resolved_row_count": len(deduped["rows"]),
                "raw_row_count": len(rows),
                "recovered_from_fallback": recovered_from_fallback,
                "duplicate_rows_removed": deduped["duplicate_count"],
                "resolution_status": "RECOVERED" if recovered_from_fallback else "CANONICAL",
                "resolution_hash": stable_hash("resolution", {"name": name, "rows": deduped["rows"]}, 24),
            }
    return {
        "resolved_store_name": "",
        "resolved_rows": [],
        "resolved_row_count": 0,
        "raw_row_count": 0,
        "recovered_from_fallback": False,
        "duplicate_rows_removed": 0,
        "resolution_status": "EMPTY",
        "resolution_hash": stable_hash("resolution", {"name": "", "rows": []}, 24),
    }


def save_reload_verification(expected_rows: Sequence[Mapping[str, Any]], reloaded_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    expected = [dict(row) for row in expected_rows or []]
    reloaded = [dict(row) for row in reloaded_rows or []]
    expected_deduped = dedupe_by_proof_id(expected)["rows"]
    reloaded_deduped = dedupe_by_proof_id(reloaded)["rows"]
    expected_hash = dataset_fingerprint(expected_deduped)
    reloaded_hash = dataset_fingerprint(reloaded_deduped)
    row_count_match = len(expected_deduped) == len(reloaded_deduped)
    fingerprint_match = expected_hash == reloaded_hash
    return {
        "expected_row_count": len(expected_deduped),
        "reloaded_row_count": len(reloaded_deduped),
        "expected_hash": expected_hash,
        "reloaded_hash": reloaded_hash,
        "row_count_match": row_count_match,
        "fingerprint_match": fingerprint_match,
        "verification_status": PASS if row_count_match and fingerprint_match else FAIL,
    }


def handoff_inventory_checks(page_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in page_rows or []]
    role_text = " ".join(_text(row.get("role") or row.get("page_role") or row.get("page") or row.get("name")).lower() for row in rows)
    checks = [check_row("handoff_inventory_supplied", "Page handoff inventory supplied", PASS if rows else WARN, details=f"rows={len(rows)}")]
    for role in ("predictor", "odds_lock", "dashboard", "learning"):
        checks.append(check_row(f"handoff_role_{role}", f"Handoff role present: {role}", PASS if role in role_text else WARN, actual=role_text))
    unsafe = []
    for row in rows:
        text = " ".join(_text(row.get(key)).lower() for key in ("mode", "risk", "mutation_flag", "notes"))
        if any(token in text for token in ("overwrite", "delete", "destructive", "live mutation", "live change")):
            unsafe.append(row)
    checks.append(check_row("handoff_no_unsafe_flags", "No unsafe handoff flags", FAIL if unsafe else PASS, details=f"unsafe_flags={len(unsafe)}"))
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
        status = RECOVERY_SAFE
    return {"recovery_status": status, "pass_count": pass_count, "warn_count": warn_count, "fail_count": fail_count}


def build_canonical_store_recovery_report(
    workspace_id: str | None = None,
    canonical_rows: Sequence[Mapping[str, Any]] | None = None,
    session_rows: Sequence[Mapping[str, Any]] | None = None,
    disk_rows: Sequence[Mapping[str, Any]] | None = None,
    local_json_rows: Sequence[Mapping[str, Any]] | None = None,
    predictor_rows: Sequence[Mapping[str, Any]] | None = None,
    odds_lock_rows: Sequence[Mapping[str, Any]] | None = None,
    dashboard_rows: Sequence[Mapping[str, Any]] | None = None,
    learning_rows: Sequence[Mapping[str, Any]] | None = None,
    reloaded_rows: Sequence[Mapping[str, Any]] | None = None,
    handoff_inventory_rows: Sequence[Mapping[str, Any]] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    workspace = normalize_workspace_id(workspace_id)
    store_map = {
        "canonical_store": [dict(row) for row in canonical_rows or []],
        "disk_fallback": [dict(row) for row in disk_rows or []],
        "local_json_fallback": [dict(row) for row in local_json_rows or []],
        "session_state": [dict(row) for row in session_rows or []],
        "odds_lock": [dict(row) for row in odds_lock_rows or []],
        "dashboard": [dict(row) for row in dashboard_rows or []],
        "predictor": [dict(row) for row in predictor_rows or []],
        "learning": [dict(row) for row in learning_rows or []],
    }
    resolution = resolve_canonical_store(store_map)
    resolved_rows = resolution["resolved_rows"]
    verification = save_reload_verification(resolved_rows, reloaded_rows if reloaded_rows is not None else resolved_rows)
    required = required_column_report(resolved_rows)
    duplicate_groups = duplicate_proof_id_rows(resolved_rows)
    mismatches = workspace_mismatches(resolved_rows, workspace)
    store_summaries = [summarize_store(name, rows, workspace) for name, rows in store_map.items()]

    checks: list[dict[str, Any]] = []
    checks.append(check_row("canonical_or_fallback_rows_present", "Canonical or fallback rows available", PASS if resolved_rows else FAIL, details=f"resolved_rows={len(resolved_rows)}"))
    checks.append(check_row("session_empty_recovery", "Session-empty recovery path available", PASS if store_map["session_state"] or resolved_rows else FAIL, details=f"session_rows={len(store_map['session_state'])}; resolved_store={resolution['resolved_store_name']}"))
    checks.append(check_row("fallback_used_only_when_needed", "Fallback recovery clearly identified", PASS if not resolution["recovered_from_fallback"] or resolution["resolved_row_count"] else FAIL, details=resolution["resolution_status"]))
    checks.append(check_row("save_reload_row_count", "Save/reload row count verified", PASS if verification["row_count_match"] else FAIL, expected=verification["expected_row_count"], actual=verification["reloaded_row_count"]))
    checks.append(check_row("save_reload_fingerprint", "Save/reload fingerprint verified", PASS if verification["fingerprint_match"] else FAIL, expected=verification["expected_hash"], actual=verification["reloaded_hash"]))
    checks.append(check_row("minimum_required_columns", "Minimum proof columns present", PASS if not required["missing_minimum_columns"] else WARN, details=",".join(required["missing_minimum_columns"])))
    checks.append(check_row("result_column_present", "Result/status column present", PASS if required["has_result_column"] else WARN))
    checks.append(check_row("duplicate_proof_ids_removed", "Duplicate proof IDs deduped", WARN if resolution["duplicate_rows_removed"] or duplicate_groups else PASS, details=f"removed={resolution['duplicate_rows_removed']}; groups={len(duplicate_groups)}"))
    checks.append(check_row("workspace_consistency", "Workspace IDs match active workspace", PASS if not mismatches else WARN, details=f"mismatches={len(mismatches)}", expected=workspace))
    checks.extend(handoff_inventory_checks(handoff_inventory_rows or []))

    parse_error = metadata.get("parse_error") if isinstance(metadata, Mapping) else None
    checks.append(check_row("metadata_parse", "Metadata JSON parse check", FAIL if parse_error else PASS, details=_text(parse_error)))

    summary = summarize_checks(checks)
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": workspace,
        "mode": SHADOW_ONLY,
        **summary,
        "canonical_store_keys": list(CANONICAL_STORE_KEYS),
        "resolved_store_name": resolution["resolved_store_name"],
        "resolution_status": resolution["resolution_status"],
        "resolved_row_count": resolution["resolved_row_count"],
        "raw_row_count": resolution["raw_row_count"],
        "recovered_from_fallback": resolution["recovered_from_fallback"],
        "duplicate_rows_removed": resolution["duplicate_rows_removed"],
        "resolution_hash": resolution["resolution_hash"],
        "store_summaries": store_summaries,
        "save_reload_verification": verification,
        "required_column_report": required,
        "duplicate_proof_id_groups": duplicate_groups,
        "workspace_mismatches": mismatches,
        "handoff_inventory": [dict(row) for row in handoff_inventory_rows or []],
        "recovered_rows_preview": resolved_rows[:50],
        "recovery_checks": checks,
        "safety_gates": {
            "live_mutation": FORBIDDEN,
            "model_training": FORBIDDEN,
            "stored_data_mutation": FORBIDDEN,
            "automatic_live_promotion": FORBIDDEN,
            "proof_overwrite": FORBIDDEN,
        },
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "warnings": [row for row in checks if row.get("status") == WARN],
        "errors": [row for row in checks if row.get("status") == FAIL],
    }
    report["recovery_id"] = stable_hash("canonical_recovery", {"workspace_id": workspace, "resolution": resolution, "checks": checks}, 24)
    report["recovery_hash"] = stable_hash("canonical_recovery_hash", {key: value for key, value in report.items() if key != "generated_at_utc"}, 32)
    return report


def build_canonical_store_recovery_report_from_text(
    workspace_id: str | None = None,
    canonical_csv_text: str | None = None,
    session_csv_text: str | None = None,
    disk_csv_text: str | None = None,
    local_json_csv_text: str | None = None,
    predictor_csv_text: str | None = None,
    odds_lock_csv_text: str | None = None,
    dashboard_csv_text: str | None = None,
    learning_csv_text: str | None = None,
    reloaded_csv_text: str | None = None,
    handoff_inventory_csv_text: str | None = None,
    metadata_json_text: str | None = None,
) -> dict[str, Any]:
    return build_canonical_store_recovery_report(
        workspace_id,
        parse_csv_text(canonical_csv_text),
        parse_csv_text(session_csv_text),
        parse_csv_text(disk_csv_text),
        parse_csv_text(local_json_csv_text),
        parse_csv_text(predictor_csv_text),
        parse_csv_text(odds_lock_csv_text),
        parse_csv_text(dashboard_csv_text),
        parse_csv_text(learning_csv_text),
        parse_csv_text(reloaded_csv_text) if _text(reloaded_csv_text) else None,
        parse_csv_text(handoff_inventory_csv_text),
        parse_json_object(metadata_json_text),
    )


def export_canonical_recovery_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_canonical_recovery_checks_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("recovery_checks") or [])


def export_canonical_recovery_store_summaries_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("store_summaries") or [])


def export_canonical_recovery_rows_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("recovered_rows_preview") or [])


def export_canonical_recovery_manifest_json(report: Mapping[str, Any]) -> str:
    manifest = {
        key: report.get(key)
        for key in (
            "schema_version",
            "workspace_id",
            "recovery_id",
            "recovery_hash",
            "generated_at_utc",
            "recovery_status",
            "resolved_store_name",
            "resolution_status",
            "resolved_row_count",
            "recovered_from_fallback",
            "duplicate_rows_removed",
            "pass_count",
            "warn_count",
            "fail_count",
            "preview_only",
            "files_written",
            "live_changes",
        )
    }
    return json.dumps(_safe(manifest), sort_keys=True, indent=2)
