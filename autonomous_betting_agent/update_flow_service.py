from __future__ import annotations

import csv
import io
import json
from typing import Any, Callable, Mapping, Sequence

from autonomous_betting_agent.data_reconciliation_preview_service import build_data_reconciliation_report, validate_data_reconciliation_report

Transport = Callable[[Mapping[str, Any]], Mapping[str, Any]]

SCHEMA_VERSION = "update_flow_v1"
FLOW_STATUS_READY = "READY TO EXPORT"
FLOW_STATUS_REVIEW = "REVIEW REQUIRED"
FLOW_STATUS_EMPTY = "NO ROWS"


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


def build_provider_requests(rows: Sequence[Mapping[str, Any]], request_type: str) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    for index, row in enumerate(rows or []):
        requests.append({
            "request_id": f"{request_type}_{index + 1}",
            "request_type": request_type,
            "sport": _text(row.get("sport") or row.get("league")),
            "event": _text(row.get("event") or row.get("event_name") or row.get("matchup")),
            "event_start_utc": _text(row.get("event_start_utc") or row.get("event_start_time") or row.get("commence_time") or row.get("date")),
            "market_type": _text(row.get("market_type") or row.get("market")),
            "selection": _text(row.get("pick") or row.get("prediction") or row.get("selection")),
            "source_row_id": _text(row.get("proof_id") or row.get("id") or row.get("record_id")),
        })
    return requests


def fetch_provider_payloads(requests: Sequence[Mapping[str, Any]], transport: Transport | None = None) -> list[dict[str, Any]]:
    if transport is None:
        return []
    payloads: list[dict[str, Any]] = []
    for request in requests or []:
        response = transport(request)
        if response:
            payload = dict(response)
            payload.setdefault("sport", request.get("sport"))
            payload.setdefault("event", request.get("event"))
            payload.setdefault("event_start_utc", request.get("event_start_utc"))
            payload.setdefault("market_type", request.get("market_type"))
            payload.setdefault("selection", request.get("selection"))
            payloads.append(payload)
    return payloads


def parse_update_csv_text(csv_text: str | None) -> list[dict[str, str]]:
    text = _text(csv_text)
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    return [{_text(k): _text(v) for k, v in row.items() if _text(k)} for row in reader]


def build_update_flow_report(
    workspace_id: str | None = None,
    locked_rows: Sequence[Mapping[str, Any]] | None = None,
    confirmation_payloads: Sequence[Mapping[str, Any]] | None = None,
    value_payloads: Sequence[Mapping[str, Any]] | None = None,
    confirmation_transport: Transport | None = None,
    value_transport: Transport | None = None,
) -> dict[str, Any]:
    rows = list(locked_rows or [])
    confirmations = list(confirmation_payloads or [])
    values = list(value_payloads or [])
    if confirmation_transport is not None:
        confirmations.extend(fetch_provider_payloads(build_provider_requests(rows, "confirmation"), confirmation_transport))
    if value_transport is not None:
        values.extend(fetch_provider_payloads(build_provider_requests(rows, "value"), value_transport))
    reconciliation = build_data_reconciliation_report(workspace_id, rows, confirmations, values)
    validation = validate_data_reconciliation_report(reconciliation)
    ready = bool(reconciliation.get("overall_passed")) and validation.get("passed") is True
    status = FLOW_STATUS_READY if ready else FLOW_STATUS_REVIEW if rows else FLOW_STATUS_EMPTY
    proposed_exports = [
        {
            "proof_id": row.get("proof_id"),
            "row_key": row.get("row_key"),
            "source": row.get("confirmation_source"),
            "confirmation_value": row.get("confirmation_value"),
            "confirmed_at_utc": row.get("confirmed_at_utc"),
            "confidence": row.get("confidence"),
            "latest_value": row.get("latest_value"),
            "delta_percent": row.get("delta_percent"),
            "review_required": row.get("review_required"),
            "frozen_selection_logic": row.get("frozen_selection_logic"),
        }
        for row in reconciliation.get("reconciliation_rows") or []
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace_id": _text(workspace_id) or "default",
        "status": status,
        "safe_to_export": ready,
        "preview_only": True,
        "changed_records": 0,
        "frozen_selection_logic": True,
        "row_count": reconciliation.get("row_count", 0),
        "unique_events": reconciliation.get("unique_events", 0),
        "duplicate_row_count": reconciliation.get("duplicate_row_count", 0),
        "confirmation_payload_count": len(confirmations),
        "value_payload_count": len(values),
        "ready_count": reconciliation.get("reconciled_count", 0),
        "review_count": reconciliation.get("review_count", 0),
        "reconciliation_report_hash": reconciliation.get("report_hash"),
        "validation_passed": validation.get("passed"),
        "proposed_exports": proposed_exports,
        "warnings": list(reconciliation.get("warnings") or []),
        "errors": list(reconciliation.get("errors") or []) + list(validation.get("errors") or []),
    }


def build_dashboard_update_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "workspace_id": report.get("workspace_id"),
        "row_count": report.get("row_count", 0),
        "unique_events": report.get("unique_events", 0),
        "duplicate_row_count": report.get("duplicate_row_count", 0),
        "ready_count": report.get("ready_count", 0),
        "review_count": report.get("review_count", 0),
        "safe_to_export": report.get("safe_to_export"),
        "preview_only": report.get("preview_only"),
        "changed_records": report.get("changed_records"),
        "frozen_selection_logic": report.get("frozen_selection_logic"),
        "reconciliation_report_hash": report.get("reconciliation_report_hash"),
    }


def export_update_flow_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_proposed_updates_csv(report: Mapping[str, Any]) -> str:
    rows = list(report.get("proposed_exports") or [])
    fields = ["proof_id", "row_key", "source", "confirmation_value", "confirmed_at_utc", "confidence", "latest_value", "delta_percent", "review_required", "frozen_selection_logic"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return output.getvalue()
