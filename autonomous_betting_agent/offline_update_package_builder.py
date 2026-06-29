from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.event_match_resolver import parse_csv_text, row_identity

SCHEMA_VERSION = "offline_update_package_v1"
PACKAGE_READY = "PACKAGE READY"
PACKAGE_REVIEW = "REVIEW REQUIRED"
PACKAGE_EMPTY = "NO ROWS"


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


def parse_json_object(text: str | None) -> dict[str, Any]:
    raw = _text(text)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {"parse_error": "invalid_json"}
    return dict(parsed) if isinstance(parsed, Mapping) else {"value": parsed}


def parse_json_rows(text: str | None) -> list[dict[str, Any]]:
    raw = _text(text)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return [{"parse_error": "invalid_json"}]
    if isinstance(parsed, list):
        return [dict(item) if isinstance(item, Mapping) else {"value": item} for item in parsed]
    if isinstance(parsed, Mapping):
        for key in ("rows", "data", "items", "payloads", "results", "confirmations", "values"):
            value = parsed.get(key)
            if isinstance(value, list):
                return [dict(item) if isinstance(item, Mapping) else {"value": item} for item in value]
        return [dict(parsed)]
    return [{"value": parsed}]


def csv_from_rows(rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str] | None = None) -> str:
    row_list = [dict(row) for row in rows or []]
    fields = list(fieldnames or [])
    if not fields:
        seen: list[str] = []
        for row in row_list:
            for key in row:
                if key not in seen:
                    seen.append(str(key))
        fields = seen
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in row_list:
        writer.writerow({field: row.get(field, "") for field in fields})
    return output.getvalue()


def row_id(row: Mapping[str, Any]) -> str:
    return row_identity(row, "locked")


def _match_rows(match_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = match_report.get("match_rows") if isinstance(match_report, Mapping) else []
    return [dict(row) for row in rows or [] if isinstance(row, Mapping)]


def _row_lookup(rows: Sequence[Mapping[str, Any]], keys: Sequence[str]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        safe_row = dict(row)
        for key in keys:
            value = _text(safe_row.get(key))
            if value:
                lookup[value] = safe_row
    return lookup


def _confirmation_value(row: Mapping[str, Any]) -> str:
    direct = _text(row.get("confirmation_value") or row.get("final_score") or row.get("score"))
    if direct:
        return direct
    primary = row.get("primary_value", row.get("home_score"))
    secondary = row.get("secondary_value", row.get("away_score"))
    if _text(primary) and _text(secondary):
        return f"{primary}-{secondary}"
    return ""


def _value_delta(row: Mapping[str, Any]) -> tuple[str, str, str]:
    original = _text(row.get("original_value") or row.get("locked_value") or row.get("start_value"))
    latest = _text(row.get("latest_value") or row.get("closing_value") or row.get("current_value"))
    delta = _text(row.get("delta_percent") or row.get("clv_percent") or row.get("CLV_percent"))
    if not delta and original and latest:
        try:
            start = float(original)
            end = float(latest)
            delta = str(round((end - start) / start, 6)) if start else ""
        except Exception:
            delta = ""
    return original, latest, delta


def _can_package(match_row: Mapping[str, Any]) -> bool:
    return _text(match_row.get("status")) == "MATCHED" and not bool(match_row.get("manual_review_required"))


def build_package_rows(
    locked_rows: Sequence[Mapping[str, Any]],
    match_report: Mapping[str, Any],
    confirmation_rows: Sequence[Mapping[str, Any]] | None = None,
    value_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    locked = [dict(row) for row in locked_rows or []]
    matches = _match_rows(match_report)
    match_by_locked = {str(row.get("locked_row_id")): row for row in matches}
    confirmation_lookup = _row_lookup(confirmation_rows or [], ("provider_event_id", "event_id", "game_id", "GameID", "best_provider_event_id", "row_key"))
    value_lookup = _row_lookup(value_rows or [], ("provider_event_id", "event_id", "game_id", "GameID", "best_provider_event_id", "row_key"))
    updated_rows: list[dict[str, Any]] = []
    diff_rows: list[dict[str, Any]] = []
    learning_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    for index, row in enumerate(locked):
        current = dict(row)
        locked_id = row_id(row)
        match_row = match_by_locked.get(locked_id, {})
        provider_id = _text(match_row.get("best_provider_event_id"))
        confirmation = confirmation_lookup.get(provider_id, {})
        value = value_lookup.get(provider_id, {})
        if _can_package(match_row):
            confirmation_value = _confirmation_value(confirmation)
            original_value, latest_value, delta = _value_delta(value)
            current.update({
                "verification_status": "ready_for_manual_import",
                "matched_provider_event_id": provider_id,
                "matched_provider_event": match_row.get("best_provider_event", ""),
                "match_confidence": match_row.get("best_score", 0.0),
                "source_confirmation": confirmation.get("provider") or confirmation.get("source") or "",
                "confirmation_value": confirmation_value,
                "confirmed_at_utc": confirmation.get("confirmed_at_utc") or confirmation.get("checked_at_utc") or "",
                "source_value": value.get("provider") or value.get("source") or "",
                "original_value": original_value,
                "latest_value": latest_value,
                "value_delta_percent": delta,
            })
            changes = {key: {"before": row.get(key, ""), "after": current.get(key, "")} for key in current if _text(row.get(key)) != _text(current.get(key))}
            diff_rows.append({
                "locked_row_id": locked_id,
                "row_index": index,
                "status": "READY",
                "changed_field_count": len(changes),
                "changes": changes,
            })
            learning_rows.append({
                "locked_row_id": locked_id,
                "event": current.get("event") or current.get("event_name") or current.get("matchup"),
                "selection": current.get("selection") or current.get("pick") or current.get("prediction"),
                "confirmation_value": confirmation_value,
                "latest_value": latest_value,
                "value_delta_percent": delta,
                "match_confidence": match_row.get("best_score", 0.0),
                "learning_status": "verified_ready",
            })
        else:
            reason = match_row.get("reasons") or ["missing or unsafe match"]
            current.update({"verification_status": "manual_review_required"})
            review_rows.append({
                "locked_row_id": locked_id,
                "row_index": index,
                "status": match_row.get("status") or "NO MATCH",
                "reason": "; ".join(str(item) for item in reason),
                "best_score": match_row.get("best_score", 0.0),
            })
        updated_rows.append(current)
    return {
        "updated_rows": updated_rows,
        "diff_rows": diff_rows,
        "verified_learning_rows": learning_rows,
        "manual_review_rows": review_rows,
    }


def build_offline_update_package(
    workspace_id: str | None = None,
    locked_rows: Sequence[Mapping[str, Any]] | None = None,
    match_report: Mapping[str, Any] | None = None,
    confirmation_rows: Sequence[Mapping[str, Any]] | None = None,
    value_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    locked = [dict(row) for row in locked_rows or []]
    report = dict(match_report or {})
    built = build_package_rows(locked, report, confirmation_rows or [], value_rows or [])
    fieldnames = []
    for row in locked + built["updated_rows"]:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(str(key))
    backup_csv = csv_from_rows(locked, fieldnames)
    updated_csv = csv_from_rows(built["updated_rows"], fieldnames)
    rollback_csv = backup_csv
    changed_count = len(built["diff_rows"])
    review_count = len(built["manual_review_rows"])
    status = PACKAGE_READY if locked and changed_count and review_count == 0 else PACKAGE_REVIEW if locked else PACKAGE_EMPTY
    audit = {
        "workspace_id": _text(workspace_id) or "default",
        "locked_hash": stable_hash("locked", locked),
        "updated_hash": stable_hash("updated", built["updated_rows"]),
        "changed_count": changed_count,
        "manual_review_count": review_count,
        "verified_learning_count": len(built["verified_learning_rows"]),
        "preview_only": True,
        "files_written": 0,
    }
    package = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "package_id": stable_hash("offline_package", {"workspace_id": workspace_id, "audit": audit}, 24),
        "status": status,
        "locked_row_count": len(locked),
        "changed_row_count": changed_count,
        "manual_review_count": review_count,
        "verified_learning_count": len(built["verified_learning_rows"]),
        "preview_only": True,
        "files_written": 0,
        "backup_csv": backup_csv,
        "updated_csv_preview": updated_csv,
        "rollback_csv": rollback_csv,
        "audit_json": json.dumps(_safe(audit), sort_keys=True, indent=2),
        "diff_rows": built["diff_rows"],
        "manual_review_rows": built["manual_review_rows"],
        "verified_learning_rows": built["verified_learning_rows"],
        "warnings": ["manual review rows remain"] if review_count else [],
        "errors": [] if locked else ["no locked rows supplied"],
    }
    package["package_hash"] = stable_hash("offline_package_hash", {k: v for k, v in package.items() if k != "generated_at_utc"}, 32)
    return package


def build_offline_update_package_from_text(
    workspace_id: str | None = None,
    locked_csv_text: str | None = None,
    match_report_json_text: str | None = None,
    confirmation_json_text: str | None = None,
    value_json_text: str | None = None,
) -> dict[str, Any]:
    return build_offline_update_package(
        workspace_id,
        parse_csv_text(locked_csv_text),
        parse_json_object(match_report_json_text),
        parse_json_rows(confirmation_json_text),
        parse_json_rows(value_json_text),
    )


def export_package_manifest_json(package: Mapping[str, Any]) -> str:
    manifest = {key: value for key, value in package.items() if key not in {"backup_csv", "updated_csv_preview", "rollback_csv"}}
    return json.dumps(_safe(manifest), sort_keys=True, indent=2)
