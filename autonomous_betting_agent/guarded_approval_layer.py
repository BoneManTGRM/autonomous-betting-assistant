from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "guarded_approval_layer_v1"
APPROVED = "APPROVED PACKAGE"
BLOCKED = "APPROVAL BLOCKED"
EMPTY = "NO ROWS"
REQUIRED_PHRASE = "APPROVE VERIFIED ROWS"


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


def csv_from_rows(rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str] | None = None) -> str:
    row_list = [dict(row) for row in rows or []]
    fields = list(fieldnames or [])
    if not fields:
        seen: list[str] = []
        for row in row_list:
            for key in row:
                if str(key) not in seen:
                    seen.append(str(key))
        fields = seen
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    if fields:
        writer.writeheader()
        for row in row_list:
            writer.writerow({field: row.get(field, "") for field in fields})
    return output.getvalue()


def parse_json_object(text: str | None) -> dict[str, Any]:
    raw = _text(text)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {"parse_error": "invalid_json"}
    return dict(parsed) if isinstance(parsed, Mapping) else {"value": parsed}


def _row_key(row: Mapping[str, Any], index: int) -> str:
    for key in ("proof_id", "locked_row_id", "row_id", "id", "event_id"):
        if _text(row.get(key)):
            return _text(row.get(key))
    return f"row_{index}"


def _fieldnames(*row_groups: Sequence[Mapping[str, Any]]) -> list[str]:
    seen: list[str] = []
    for group in row_groups:
        for row in group or []:
            for key in row:
                if str(key) not in seen:
                    seen.append(str(key))
    return seen


def compare_csv_rows(base_rows: Sequence[Mapping[str, Any]], candidate_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    base = [dict(row) for row in base_rows or []]
    candidate = [dict(row) for row in candidate_rows or []]
    count = max(len(base), len(candidate))
    diffs: list[dict[str, Any]] = []
    for index in range(count):
        before = base[index] if index < len(base) else {}
        after = candidate[index] if index < len(candidate) else {}
        keys = sorted(set(before) | set(after))
        changes = {key: {"before": before.get(key, ""), "after": after.get(key, "")} for key in keys if _text(before.get(key)) != _text(after.get(key))}
        if changes:
            diffs.append({
                "row_index": index,
                "row_key": _row_key(after or before, index),
                "change_count": len(changes),
                "changes": changes,
            })
    return diffs


def validate_approval_inputs(
    package_manifest: Mapping[str, Any],
    base_rows: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
    approval_phrase: str | None,
    operator_name: str | None,
    *,
    required_phrase: str = REQUIRED_PHRASE,
) -> list[str]:
    errors: list[str] = []
    if not base_rows:
        errors.append("missing base rows")
    if not candidate_rows:
        errors.append("missing candidate rows")
    if _text(approval_phrase) != required_phrase:
        errors.append("approval phrase mismatch")
    if not _text(operator_name):
        errors.append("operator name required")
    if package_manifest.get("parse_error") == "invalid_json":
        errors.append("manifest json invalid")
    for key in ("manual_review_count", "review_lane_count", "quarantine_lane_count"):
        try:
            if int(package_manifest.get(key) or 0) > 0:
                errors.append(f"blocked by {key}")
        except Exception:
            errors.append(f"invalid {key}")
    return errors


def build_guarded_approval_package(
    workspace_id: str | None = None,
    base_rows: Sequence[Mapping[str, Any]] | None = None,
    candidate_rows: Sequence[Mapping[str, Any]] | None = None,
    package_manifest: Mapping[str, Any] | None = None,
    approval_phrase: str | None = None,
    operator_name: str | None = None,
    approval_note: str | None = None,
) -> dict[str, Any]:
    base = [dict(row) for row in base_rows or []]
    candidate = [dict(row) for row in candidate_rows or []]
    manifest = dict(package_manifest or {})
    diffs = compare_csv_rows(base, candidate)
    errors = validate_approval_inputs(manifest, base, candidate, approval_phrase, operator_name)
    status = EMPTY if not base and not candidate else BLOCKED if errors else APPROVED
    fields = _fieldnames(base, candidate)
    backup_csv = csv_from_rows(base, fields)
    approved_csv = csv_from_rows(candidate, fields)
    rollback_csv = backup_csv
    audit = {
        "workspace_id": _text(workspace_id) or "default",
        "operator_name": _text(operator_name),
        "approval_note": _text(approval_note),
        "required_phrase": REQUIRED_PHRASE,
        "approval_phrase_matched": _text(approval_phrase) == REQUIRED_PHRASE,
        "base_hash": stable_hash("base", base),
        "candidate_hash": stable_hash("candidate", candidate),
        "diff_hash": stable_hash("diff", diffs),
        "changed_row_count": len(diffs),
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
    }
    package = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "approval_id": stable_hash("approval", {"workspace_id": workspace_id, "audit": audit}, 24),
        "status": status,
        "base_row_count": len(base),
        "candidate_row_count": len(candidate),
        "changed_row_count": len(diffs),
        "blocked_reason_count": len(errors),
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "approval_phrase_required": REQUIRED_PHRASE,
        "approval_phrase_matched": _text(approval_phrase) == REQUIRED_PHRASE,
        "backup_csv": backup_csv,
        "approved_csv": approved_csv if status == APPROVED else "",
        "rollback_csv": rollback_csv,
        "audit_json": json.dumps(_safe(audit), sort_keys=True, indent=2),
        "diff_rows": diffs,
        "blocked_reasons": errors,
        "warnings": [] if status == APPROVED else ["approval blocked until all checks pass"],
        "errors": errors,
    }
    package["approval_hash"] = stable_hash("approval_hash", {k: v for k, v in package.items() if k != "generated_at_utc"}, 32)
    return package


def build_guarded_approval_package_from_text(
    workspace_id: str | None = None,
    base_csv_text: str | None = None,
    candidate_csv_text: str | None = None,
    package_manifest_json_text: str | None = None,
    approval_phrase: str | None = None,
    operator_name: str | None = None,
    approval_note: str | None = None,
) -> dict[str, Any]:
    return build_guarded_approval_package(
        workspace_id,
        parse_csv_text(base_csv_text),
        parse_csv_text(candidate_csv_text),
        parse_json_object(package_manifest_json_text),
        approval_phrase,
        operator_name,
        approval_note,
    )


def export_approval_manifest_json(package: Mapping[str, Any]) -> str:
    manifest = {key: value for key, value in dict(package or {}).items() if key not in {"backup_csv", "approved_csv", "rollback_csv"}}
    return json.dumps(_safe(manifest), sort_keys=True, indent=2)
