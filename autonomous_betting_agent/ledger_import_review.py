import hashlib
import json
from typing import Any, Mapping, Sequence

import pandas as pd

from autonomous_betting_agent.ledger_sync_service import SYNC_SOURCE_REGISTRY, sync_rows_by_source
from autonomous_betting_agent.performance_ledger_service import read_performance_ledger
from autonomous_betting_agent.proof_performance_store import build_duplicate_key, normalize_performance_record


def _workspace(value: Any) -> str:
    text = str(value or "").strip().replace(" ", "_").lower()
    return text or "default"


def _source_key(value: str) -> str:
    key = str(value or "").strip().lower()
    if key not in SYNC_SOURCE_REGISTRY:
        raise ValueError(f"Unsupported source_key: {value}")
    return key


def _rows_frame(rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None) -> pd.DataFrame:
    if rows is None:
        return pd.DataFrame()
    if isinstance(rows, pd.DataFrame):
        return rows.copy(deep=True)
    return pd.DataFrame([dict(row) for row in rows])


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def build_preview_hash(preview: Mapping[str, Any]) -> str:
    stable = {
        "source_key": preview.get("source_key"),
        "source_file": preview.get("source_file"),
        "workspace_id": preview.get("workspace_id"),
        "rows_seen": preview.get("rows_seen"),
        "rows_to_add": preview.get("rows_to_add"),
        "duplicates_detected": preview.get("duplicates_detected"),
        "rejected_rows": preview.get("rejected_rows"),
        "correction_rows_detected": preview.get("correction_rows_detected"),
        "duplicate_keys": sorted(str(row.get("duplicate_key", "")) for row in preview.get("duplicate_rows", []) or []),
        "rejected_reasons": sorted(str(row.get("reason", "")) for row in preview.get("rejected_row_details", []) or []),
        "input_fingerprint": preview.get("input_fingerprint"),
    }
    return "preview_" + hashlib.sha256(_stable_json(stable).encode("utf-8")).hexdigest()[:24]


def _input_fingerprint(rows: pd.DataFrame, workspace_id: str, source_key: str, source_file: str | None) -> str:
    records = rows.to_dict(orient="records") if not rows.empty else []
    payload = {
        "workspace_id": _workspace(workspace_id),
        "source_key": source_key,
        "source_file": source_file or "",
        "rows": records,
    }
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()[:32]


def review_correction_rows(rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None, workspace_id: str, source_key: str, source_file: str | None = None) -> dict[str, Any]:
    key = _source_key(source_key)
    frame = _rows_frame(rows)
    workspace = _workspace(workspace_id)
    existing = read_performance_ledger(workspace)
    existing_proofs = set(existing.get("proof_id", pd.Series(dtype=str)).astype(str).tolist()) if not existing.empty else set()
    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    correction_count = 0
    for _, series in frame.iterrows():
        raw = series.to_dict()
        if str(raw.get("record_type", "")).strip().lower() != "correction":
            continue
        correction_count += 1
        record = normalize_performance_record(raw, workspace, source_key=key, source_file=source_file)
        if not str(record.get("corrected_from_proof_id", "")).strip():
            rejected.append({"reason": "missing corrected_from_proof_id", "row": record})
            errors.append("correction row missing corrected_from_proof_id")
            continue
        if not str(record.get("correction_reason", "")).strip():
            rejected.append({"reason": "missing correction_reason", "row": record})
            errors.append("correction row missing correction_reason")
            continue
        if existing_proofs and str(record.get("corrected_from_proof_id")) not in existing_proofs:
            warnings.append(f"corrected_from_proof_id not found: {record.get('corrected_from_proof_id')}")
        valid.append(record)
    return {
        "source_key": key,
        "source_file": source_file,
        "workspace_id": workspace,
        "correction_row_count": correction_count,
        "valid_corrections": valid,
        "rejected_corrections": rejected,
        "warnings": warnings,
        "errors": errors,
    }


def review_duplicate_rows(rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None, workspace_id: str, source_key: str, source_file: str | None = None) -> dict[str, Any]:
    key = _source_key(source_key)
    frame = _rows_frame(rows)
    workspace = _workspace(workspace_id)
    existing = read_performance_ledger(workspace)
    existing_by_duplicate: dict[str, dict[str, Any]] = {}
    if not existing.empty:
        for _, series in existing.iterrows():
            row = series.to_dict()
            existing_by_duplicate[str(row.get("duplicate_key", ""))] = row
    seen: dict[str, dict[str, Any]] = {}
    duplicates: list[dict[str, Any]] = []
    for _, series in frame.iterrows():
        record = normalize_performance_record(series.to_dict(), workspace, source_key=key, source_file=source_file)
        duplicate_key = str(record.get("duplicate_key") or build_duplicate_key(record))
        existing_record = existing_by_duplicate.get(duplicate_key)
        if existing_record:
            duplicates.append({
                "duplicate_key": duplicate_key,
                "proof_id": existing_record.get("proof_id"),
                "row": record,
                "existing_row": existing_record,
            })
            continue
        if duplicate_key in seen:
            duplicates.append({
                "duplicate_key": duplicate_key,
                "proof_id": seen[duplicate_key].get("proof_id"),
                "row": record,
                "existing_row": seen[duplicate_key],
            })
            continue
        seen[duplicate_key] = record
    return {
        "source_key": key,
        "source_file": source_file,
        "workspace_id": workspace,
        "duplicate_row_count": len(duplicates),
        "duplicate_keys": [item["duplicate_key"] for item in duplicates],
        "proof_ids": [item.get("proof_id") for item in duplicates if item.get("proof_id")],
        "duplicate_rows": duplicates,
        "warnings": [],
        "errors": [],
    }


def preview_ledger_import(rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None, workspace_id: str, source_key: str, source_file: str | None = None) -> dict[str, Any]:
    key = _source_key(source_key)
    workspace = _workspace(workspace_id)
    frame = _rows_frame(rows)
    raw_result = sync_rows_by_source(frame, workspace, key, source_file=source_file, dry_run=True)
    correction_review = review_correction_rows(frame, workspace, key, source_file=source_file)
    duplicate_review = review_duplicate_rows(frame, workspace, key, source_file=source_file)
    errors = list(raw_result.get("errors", []) or []) + list(correction_review.get("errors", []) or [])
    warnings = list(raw_result.get("warnings", []) or []) + list(correction_review.get("warnings", []) or [])
    preview = {
        "source_key": key,
        "source_file": source_file,
        "workspace_id": workspace,
        "dry_run": True,
        "rows_seen": int(raw_result.get("rows_seen", 0) or 0),
        "rows_to_add": int(raw_result.get("rows_to_add", 0) or 0),
        "duplicates_detected": int(raw_result.get("duplicates_detected", 0) or 0),
        "rejected_rows": int(raw_result.get("rejected_rows", 0) or 0),
        "correction_rows_detected": int(raw_result.get("correction_rows_detected", 0) or 0),
        "warnings": warnings,
        "errors": errors,
        "duplicate_rows": list(raw_result.get("duplicate_rows", []) or []) or list(duplicate_review.get("duplicate_rows", []) or []),
        "rejected_row_details": list(raw_result.get("rejected_row_details", []) or []),
        "correction_row_details": {
            "valid_corrections": correction_review.get("valid_corrections", []),
            "rejected_corrections": correction_review.get("rejected_corrections", []),
        },
        "preview_summary": dict(raw_result.get("summary", {}) or {}),
        "approval_required": int(raw_result.get("rows_to_add", 0) or 0) > 0,
        "input_fingerprint": _input_fingerprint(frame, workspace, key, source_file),
    }
    preview["preview_hash"] = build_preview_hash(preview)
    return preview
