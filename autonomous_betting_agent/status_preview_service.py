from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "status_preview_v1"
STATUS_VALUES = ("READY", "REVIEW", "MISSING", "EMPTY")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


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


def _dump(value: Any) -> str:
    return json.dumps(_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(prefix: str, payload: Mapping[str, Any], length: int = 32) -> str:
    return f"{prefix}_{hashlib.sha256(_dump(payload).encode('utf-8')).hexdigest()[:length]}"


def record_key(row: Mapping[str, Any]) -> str:
    parts = [
        _text(row.get("group") or row.get("category")).lower(),
        _text(row.get("name") or row.get("event") or row.get("title")).lower(),
        _text(row.get("time") or row.get("date")).lower(),
    ]
    key = "|".join(parts).strip("|")
    return key or _text(row.get("record_id") or row.get("id")).lower()


def normalize_marker(payload: Mapping[str, Any]) -> dict[str, Any]:
    primary = payload.get("primary")
    secondary = payload.get("secondary")
    has_marker = primary not in (None, "") and secondary not in (None, "")
    return {
        "record_key": record_key(payload),
        "source": _text(payload.get("source")) or "manual",
        "marker": f"{primary}-{secondary}" if has_marker else "",
        "confidence": max(0.0, min(1.0, _float(payload.get("confidence"), 1.0 if has_marker else 0.0))),
        "checked_at_utc": _text(payload.get("checked_at_utc") or _now()),
        "has_marker": has_marker,
    }


def normalize_snapshot(payload: Mapping[str, Any]) -> dict[str, Any]:
    start_value = _float(payload.get("start_value"), 0.0)
    latest_value = _float(payload.get("latest_value"), 0.0)
    delta = latest_value - start_value if start_value and latest_value else 0.0
    return {
        "record_key": record_key(payload),
        "source": _text(payload.get("source")) or "manual",
        "start_value": round(start_value, 6),
        "latest_value": round(latest_value, 6),
        "delta": round(delta, 6),
        "delta_ratio": round((delta / start_value) if start_value else 0.0, 6),
        "has_latest_value": latest_value != 0.0,
    }


def build_status_row(row: Mapping[str, Any], markers: Mapping[str, Mapping[str, Any]], snapshots: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    key = record_key(row)
    marker = markers.get(key, {})
    snapshot = snapshots.get(key, {})
    reasons: list[str] = []
    if not marker.get("has_marker"):
        reasons.append("missing marker")
    if _float(marker.get("confidence"), 0.0) < 0.75:
        reasons.append("low confidence")
    if not snapshot.get("has_latest_value"):
        reasons.append("missing latest value")
    status = "READY" if not reasons else "REVIEW"
    if "missing marker" in reasons:
        status = "MISSING"
    return {
        "record_id": _text(row.get("record_id") or row.get("id")),
        "record_key": key,
        "name": _text(row.get("name") or row.get("event") or row.get("title")),
        "status": status,
        "review_required": bool(reasons),
        "reason_count": len(reasons),
        "marker_source": marker.get("source", ""),
        "marker": marker.get("marker", ""),
        "checked_at_utc": marker.get("checked_at_utc", ""),
        "confidence": _float(marker.get("confidence"), 0.0),
        "snapshot_source": snapshot.get("source", ""),
        "latest_value": snapshot.get("latest_value", 0.0),
        "delta_ratio": snapshot.get("delta_ratio", 0.0),
        "locked_logic": True,
    }


def build_status_preview_report(workspace_id: str | None = None, records: Sequence[Mapping[str, Any]] | None = None, markers: Sequence[Mapping[str, Any]] | None = None, snapshots: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    workspace = _text(workspace_id) or "default"
    record_list = list(records or [])
    marker_list = [normalize_marker(item) for item in markers or []]
    snapshot_list = [normalize_snapshot(item) for item in snapshots or []]
    marker_map = {item["record_key"]: item for item in marker_list if item.get("record_key")}
    snapshot_map = {item["record_key"]: item for item in snapshot_list if item.get("record_key")}
    status_rows = [build_status_row(row, marker_map, snapshot_map) for row in record_list]
    review_count = len([row for row in status_rows if row["review_required"]])
    ready_count = len([row for row in status_rows if row["status"] == "READY"])
    unique_records = len({row["record_key"] for row in status_rows if row["record_key"]})
    status = "READY" if record_list and review_count == 0 else "REVIEW" if record_list else "EMPTY"
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": workspace,
        "report_id": "",
        "report_hash": "",
        "status": status,
        "overall_passed": bool(record_list) and review_count == 0,
        "record_count": len(record_list),
        "unique_records": unique_records,
        "duplicate_record_count": max(0, len(record_list) - unique_records),
        "marker_count": len(marker_list),
        "snapshot_count": len(snapshot_list),
        "ready_count": ready_count,
        "review_count": review_count,
        "locked_logic": True,
        "status_rows": status_rows,
        "warnings": ["review rows remain"] if review_count else [],
        "errors": [] if record_list else ["no records supplied"],
    }
    report["report_id"] = _hash("status_preview", {"workspace_id": workspace, "rows": status_rows}, 24)
    report["report_hash"] = build_status_preview_hash(report)
    return report


def build_status_preview_hash(report: Mapping[str, Any]) -> str:
    stable = {k: v for k, v in dict(report).items() if k not in {"generated_at_utc", "report_hash"}}
    return _hash("status_preview_hash", stable)


def validate_status_preview_report(report: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    for field in ("schema_version", "workspace_id", "report_id", "report_hash", "status", "overall_passed", "record_count", "unique_records", "status_rows", "locked_logic"):
        if field not in report:
            errors.append(f"missing field: {field}")
    if report.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported status preview schema_version")
    if report.get("status") not in STATUS_VALUES:
        errors.append("unsupported status preview status")
    if report.get("report_hash") and build_status_preview_hash(report) != report.get("report_hash"):
        errors.append("report_hash does not match report contents")
    if report.get("overall_passed") and report.get("review_count"):
        errors.append("overall_passed is overstated")
    if int(report.get("unique_records") or 0) > int(report.get("record_count") or 0):
        errors.append("unique_records cannot exceed record_count")
    if report.get("locked_logic") is not True:
        errors.append("locked_logic must remain true")
    return {"passed": not errors, "checked_outputs": ["schema_version", "report_hash", "review_status", "record_math", "locked_logic"], "warnings": [], "errors": errors, "details": {"rebuilt_report_hash": build_status_preview_hash(report) if report.get("report_hash") else ""}}


def sanitize_status_preview_report(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report.get("schema_version"),
        "workspace_id": report.get("workspace_id"),
        "report_id": report.get("report_id"),
        "report_hash": report.get("report_hash"),
        "status": report.get("status"),
        "overall_passed": report.get("overall_passed"),
        "record_count": report.get("record_count", 0),
        "unique_records": report.get("unique_records", 0),
        "duplicate_record_count": report.get("duplicate_record_count", 0),
        "marker_count": report.get("marker_count", 0),
        "snapshot_count": report.get("snapshot_count", 0),
        "ready_count": report.get("ready_count", 0),
        "review_count": report.get("review_count", 0),
        "locked_logic": report.get("locked_logic"),
        "status_rows": [{"record_id": row.get("record_id"), "record_key": row.get("record_key"), "status": row.get("status"), "review_required": row.get("review_required"), "reason_count": row.get("reason_count"), "marker_source": row.get("marker_source"), "marker": row.get("marker"), "checked_at_utc": row.get("checked_at_utc"), "confidence": row.get("confidence"), "snapshot_source": row.get("snapshot_source"), "latest_value": row.get("latest_value"), "delta_ratio": row.get("delta_ratio"), "locked_logic": row.get("locked_logic")} for row in report.get("status_rows") or []],
        "warning_count": len(report.get("warnings") or []),
        "error_count": len(report.get("errors") or []),
    }


def export_status_preview_report_json(report: Mapping[str, Any], public_safe: bool = True) -> str:
    payload = sanitize_status_preview_report(report) if public_safe else dict(report)
    return json.dumps(_safe(payload), sort_keys=True, indent=2)
