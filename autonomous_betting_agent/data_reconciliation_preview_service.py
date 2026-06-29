from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "data_reconciliation_preview_v1"
REVIEW_STATUS = ("RECONCILED", "REVIEW REQUIRED", "MISSING CONFIRMATION", "NO ROWS")
SUPPORTED_MARKET_TYPES = {"moneyline", "spread", "total", "over_under", "winner"}


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


def row_key(row: Mapping[str, Any]) -> str:
    parts = [
        _text(row.get("sport") or row.get("league")).lower(),
        _text(row.get("event") or row.get("event_name") or row.get("matchup")).lower(),
        _text(row.get("event_start_utc") or row.get("event_start_time") or row.get("commence_time") or row.get("date")).lower(),
    ]
    return "|".join(parts).strip("|") or _text(row.get("proof_id") or row.get("id")).lower()


def normalize_confirmation(payload: Mapping[str, Any]) -> dict[str, Any]:
    primary_value = payload.get("primary_value", payload.get("home_value"))
    secondary_value = payload.get("secondary_value", payload.get("away_value"))
    has_confirmation = primary_value not in (None, "") and secondary_value not in (None, "")
    return {
        "row_key": row_key(payload),
        "source": _text(payload.get("source") or payload.get("provider")) or "manual_preview",
        "confirmation_value": f"{primary_value}-{secondary_value}" if has_confirmation else "",
        "primary_value": _float(primary_value, 0.0) if has_confirmation else None,
        "secondary_value": _float(secondary_value, 0.0) if has_confirmation else None,
        "confirmed_at_utc": _text(payload.get("confirmed_at_utc") or _now()),
        "confidence": max(0.0, min(1.0, _float(payload.get("confidence"), 1.0 if has_confirmation else 0.0))),
        "has_confirmation": has_confirmation,
    }


def normalize_value_snapshot(payload: Mapping[str, Any]) -> dict[str, Any]:
    original_value = _float(payload.get("original_value") or payload.get("locked_value"), 0.0)
    latest_value = _float(payload.get("latest_value") or payload.get("closing_value"), 0.0)
    delta = latest_value - original_value if original_value and latest_value else 0.0
    return {
        "row_key": row_key(payload),
        "market_type": _text(payload.get("market_type") or payload.get("market")).lower(),
        "source": _text(payload.get("source") or payload.get("provider")) or "manual_preview",
        "original_value": round(original_value, 6),
        "latest_value": round(latest_value, 6),
        "delta": round(delta, 6),
        "delta_percent": round((delta / original_value) if original_value else 0.0, 6),
        "has_latest_value": latest_value != 0.0,
    }


def build_reconciliation_row(row: Mapping[str, Any], confirmations: Mapping[str, Mapping[str, Any]], values: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    key = row_key(row)
    confirmation = confirmations.get(key, {})
    value_snapshot = values.get(key, {})
    market_type = _text(row.get("market_type") or row.get("market")).lower()
    confidence = _float(confirmation.get("confidence"), 0.0)
    review_reasons: list[str] = []
    if not confirmation.get("has_confirmation"):
        review_reasons.append("missing confirmation")
    if confidence < 0.75:
        review_reasons.append("low confidence")
    if market_type and market_type not in SUPPORTED_MARKET_TYPES:
        review_reasons.append("unsupported market type")
    if not value_snapshot.get("has_latest_value"):
        review_reasons.append("missing latest value")
    status = "RECONCILED" if not review_reasons else "REVIEW REQUIRED"
    if "missing confirmation" in review_reasons:
        status = "MISSING CONFIRMATION"
    return {
        "proof_id": _text(row.get("proof_id") or row.get("id")),
        "row_key": key,
        "event": _text(row.get("event") or row.get("event_name") or row.get("matchup")),
        "selection": _text(row.get("pick") or row.get("prediction") or row.get("selection")),
        "market_type": market_type,
        "status": status,
        "review_required": bool(review_reasons),
        "review_reason_count": len(review_reasons),
        "confirmation_source": confirmation.get("source", ""),
        "confirmation_value": confirmation.get("confirmation_value", ""),
        "confirmed_at_utc": confirmation.get("confirmed_at_utc", ""),
        "confidence": confidence,
        "value_source": value_snapshot.get("source", ""),
        "latest_value": value_snapshot.get("latest_value", 0.0),
        "delta": value_snapshot.get("delta", 0.0),
        "delta_percent": value_snapshot.get("delta_percent", 0.0),
        "frozen_selection_logic": True,
    }


def build_data_reconciliation_report(workspace_id: str | None = None, locked_rows: Sequence[Mapping[str, Any]] | None = None, confirmations: Sequence[Mapping[str, Any]] | None = None, value_snapshots: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    workspace = _text(workspace_id) or "default"
    rows = list(locked_rows or [])
    normalized_confirmations = [normalize_confirmation(item) for item in confirmations or []]
    normalized_values = [normalize_value_snapshot(item) for item in value_snapshots or []]
    confirmation_map = {item["row_key"]: item for item in normalized_confirmations if item.get("row_key")}
    value_map = {item["row_key"]: item for item in normalized_values if item.get("row_key")}
    reconciliation_rows = [build_reconciliation_row(row, confirmation_map, value_map) for row in rows]
    review_count = len([row for row in reconciliation_rows if row["review_required"]])
    reconciled_count = len([row for row in reconciliation_rows if row["status"] == "RECONCILED"])
    unique_events = len({row["row_key"] for row in reconciliation_rows if row["row_key"]})
    status = "RECONCILED" if rows and review_count == 0 else "REVIEW REQUIRED" if rows else "NO ROWS"
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": workspace,
        "report_id": "",
        "report_hash": "",
        "status": status,
        "overall_passed": bool(rows) and review_count == 0,
        "row_count": len(rows),
        "unique_events": unique_events,
        "duplicate_row_count": max(0, len(rows) - unique_events),
        "confirmation_payload_count": len(normalized_confirmations),
        "value_payload_count": len(normalized_values),
        "reconciled_count": reconciled_count,
        "review_count": review_count,
        "frozen_selection_logic": True,
        "reconciliation_rows": reconciliation_rows,
        "warnings": ["review rows remain"] if review_count else [],
        "errors": [] if rows else ["no locked rows supplied"],
    }
    report["report_id"] = _hash("data_reconciliation", {"workspace_id": workspace, "rows": reconciliation_rows}, 24)
    report["report_hash"] = build_data_reconciliation_hash(report)
    return report


def build_data_reconciliation_hash(report: Mapping[str, Any]) -> str:
    stable = {k: v for k, v in dict(report).items() if k not in {"generated_at_utc", "report_hash"}}
    return _hash("data_reconciliation_hash", stable)


def validate_data_reconciliation_report(report: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    required = ("schema_version", "workspace_id", "report_id", "report_hash", "status", "overall_passed", "row_count", "unique_events", "reconciliation_rows", "frozen_selection_logic")
    for field in required:
        if field not in report:
            errors.append(f"missing field: {field}")
    if report.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported data reconciliation schema_version")
    if report.get("status") not in REVIEW_STATUS:
        errors.append("unsupported data reconciliation status")
    if report.get("report_hash") and build_data_reconciliation_hash(report) != report.get("report_hash"):
        errors.append("report_hash does not match report contents")
    if report.get("overall_passed") and report.get("review_count"):
        errors.append("overall_passed is overstated")
    if int(report.get("unique_events") or 0) > int(report.get("row_count") or 0):
        errors.append("unique_events cannot exceed row_count")
    if report.get("frozen_selection_logic") is not True:
        errors.append("frozen_selection_logic must remain true")
    return {"passed": not errors, "checked_outputs": ["schema_version", "report_hash", "review_status", "event_row_math", "frozen_selection_logic"], "warnings": [], "errors": errors, "details": {"rebuilt_report_hash": build_data_reconciliation_hash(report) if report.get("report_hash") else ""}}


def sanitize_data_reconciliation_report(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report.get("schema_version"),
        "workspace_id": report.get("workspace_id"),
        "report_id": report.get("report_id"),
        "report_hash": report.get("report_hash"),
        "status": report.get("status"),
        "overall_passed": report.get("overall_passed"),
        "row_count": report.get("row_count", 0),
        "unique_events": report.get("unique_events", 0),
        "duplicate_row_count": report.get("duplicate_row_count", 0),
        "confirmation_payload_count": report.get("confirmation_payload_count", 0),
        "value_payload_count": report.get("value_payload_count", 0),
        "reconciled_count": report.get("reconciled_count", 0),
        "review_count": report.get("review_count", 0),
        "frozen_selection_logic": report.get("frozen_selection_logic"),
        "reconciliation_rows": [
            {
                "proof_id": row.get("proof_id"),
                "row_key": row.get("row_key"),
                "status": row.get("status"),
                "review_required": row.get("review_required"),
                "review_reason_count": row.get("review_reason_count"),
                "confirmation_source": row.get("confirmation_source"),
                "confirmation_value": row.get("confirmation_value"),
                "confirmed_at_utc": row.get("confirmed_at_utc"),
                "confidence": row.get("confidence"),
                "value_source": row.get("value_source"),
                "latest_value": row.get("latest_value"),
                "delta_percent": row.get("delta_percent"),
                "frozen_selection_logic": row.get("frozen_selection_logic"),
            }
            for row in report.get("reconciliation_rows") or []
        ],
        "warning_count": len(report.get("warnings") or []),
        "error_count": len(report.get("errors") or []),
    }


def export_data_reconciliation_report_json(report: Mapping[str, Any], public_safe: bool = True) -> str:
    payload = sanitize_data_reconciliation_report(report) if public_safe else dict(report)
    return json.dumps(_safe(payload), sort_keys=True, indent=2)
