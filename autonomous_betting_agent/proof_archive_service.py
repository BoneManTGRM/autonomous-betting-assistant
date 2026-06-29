from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.proof_package_integrity_service import build_proof_package_qa_report
from autonomous_betting_agent.proof_package_service import (
    PRIVATE_PACKAGE_TYPES,
    PUBLIC_PACKAGE_TYPES,
    build_client_summary_package,
    build_internal_review_package,
    build_private_audit_package,
    build_public_proof_package,
    validate_public_package_redactions,
)

PROOF_ARCHIVE_SCHEMA_VERSION = "proof_archive_v1"
PROOF_ARCHIVE_PACKAGE_TYPES = ("public", "client", "private", "internal_review")
PROOF_ARCHIVE_PRIVATE_PACKAGE_TYPES = set(PRIVATE_PACKAGE_TYPES)
PROOF_ARCHIVE_PUBLIC_PACKAGE_TYPES = set(PUBLIC_PACKAGE_TYPES)
PROOF_ARCHIVE_BLOCKED_PUBLIC_TERMS = (
    "source_file",
    "previous_row_hash",
    "correction_reason",
    "private_export_csv",
    "private_export_json",
    "private_export_hash",
    "api_key",
    "secret",
    "token",
    "bearer",
    "password",
    "/home/",
    "/mnt/",
    "data/private",
    ".env",
)
PACKAGE_BUILDERS = {
    "public": build_public_proof_package,
    "client": build_client_summary_package,
    "private": build_private_audit_package,
    "internal_review": build_internal_review_package,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _canonical_dumps(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash_payload(prefix: str, payload: Mapping[str, Any], length: int = 32) -> str:
    return f"{prefix}_{hashlib.sha256(_canonical_dumps(payload).encode('utf-8')).hexdigest()[:length]}"


def _package_type(package_type: str | None) -> str:
    return str(package_type or "public").strip().lower()


def _safe_error_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    errors = list(report.get("errors") or [])
    warnings = list(report.get("warnings") or [])
    failed_checks = [
        key for key, value in report.items()
        if key.endswith("_passed") and value is False
    ]
    return {
        "error_count": len(errors),
        "warning_count": len(warnings),
        "failed_checks": sorted(set(failed_checks)),
    }


def _public_archive_fields(package: Mapping[str, Any], qa_report: Mapping[str, Any]) -> dict[str, Any]:
    redaction_status = validate_public_package_redactions(package)
    return {
        "schema_version": PROOF_ARCHIVE_SCHEMA_VERSION,
        "workspace_id": package.get("workspace_id"),
        "package_type": package.get("package_type"),
        "package_id": package.get("package_id"),
        "package_hash": package.get("package_hash"),
        "public_export_hash": package.get("public_export_hash"),
        "qa_report_id": qa_report.get("qa_report_id"),
        "qa_report_hash": qa_report.get("qa_report_hash"),
        "proof_ready": package.get("proof_ready"),
        "proof_grade": package.get("proof_grade"),
        "ledger_backed": package.get("ledger_backed"),
        "selected_source": package.get("selected_source"),
        "ledger_integrity_status": package.get("ledger_integrity_status"),
        "dashboard_ready": package.get("dashboard_ready"),
        "overall_passed": qa_report.get("overall_passed"),
        "redaction_passed": redaction_status.get("passed"),
        "row_count": package.get("total_rows", 0),
        "unique_events": package.get("unique_events", 0),
        "wins": package.get("wins", 0),
        "losses": package.get("losses", 0),
        "pushes": package.get("pushes", 0),
        "cancels": package.get("cancels", 0),
        "ROI": package.get("ROI", 0),
        "profit_units": package.get("profit_units", 0),
        "average_CLV": package.get("average_CLV"),
        "warning_error_summary": _safe_error_summary(qa_report),
    }


def build_proof_archive_snapshot(workspace_id: str | None = None, package_type: str = "public", *, package: Mapping[str, Any] | None = None, qa_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    selected_type = _package_type(package_type)
    if selected_type not in PACKAGE_BUILDERS:
        snapshot = {
            "schema_version": PROOF_ARCHIVE_SCHEMA_VERSION,
            "archive_id": "",
            "archive_hash": "",
            "created_at_utc": _utc_now(),
            "workspace_id": workspace_id or "default",
            "package_type": selected_type,
            "package_id": "",
            "package_hash": "",
            "qa_report_hash": "",
            "proof_ready": False,
            "proof_grade": "EMPTY / NOT PROOF READY",
            "overall_passed": False,
            "redaction_passed": False,
            "archive_status": "UNSUPPORTED PACKAGE TYPE",
            "is_private_internal": False,
            "is_public_client": False,
            "warnings": [],
            "errors": [f"Unsupported package_type: {selected_type}"],
        }
        snapshot["archive_id"] = _hash_payload("archive", snapshot, length=24)
        snapshot["archive_hash"] = _hash_payload("archive_hash", snapshot)
        return snapshot

    built_package = dict(package or PACKAGE_BUILDERS[selected_type](workspace_id))
    built_report = dict(qa_report or build_proof_package_qa_report(workspace_id, selected_type))
    base = _public_archive_fields(built_package, built_report)
    base.update({
        "archive_id": "",
        "archive_hash": "",
        "created_at_utc": _utc_now(),
        "is_private_internal": selected_type in PROOF_ARCHIVE_PRIVATE_PACKAGE_TYPES,
        "is_public_client": selected_type in PROOF_ARCHIVE_PUBLIC_PACKAGE_TYPES,
        "archive_status": "ARCHIVE READY" if built_report.get("overall_passed") else "ARCHIVE QA FAILED",
        "warnings": list(built_report.get("warnings") or []),
        "errors": list(built_report.get("errors") or []),
    })
    if selected_type in PROOF_ARCHIVE_PRIVATE_PACKAGE_TYPES:
        base["private_export_hash"] = built_package.get("private_export_hash")
    base["archive_id"] = _hash_payload("archive", {
        "workspace_id": base.get("workspace_id"),
        "package_type": base.get("package_type"),
        "package_id": base.get("package_id"),
        "package_hash": base.get("package_hash"),
        "qa_report_hash": base.get("qa_report_hash"),
    }, length=24)
    base["archive_hash"] = build_proof_archive_hash(base)
    return base


def build_proof_archive_hash(snapshot: Mapping[str, Any]) -> str:
    stable = {key: value for key, value in dict(snapshot).items() if key not in {"created_at_utc", "archive_hash"}}
    return _hash_payload("archive_hash", stable)


def validate_proof_archive_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    package_type = _package_type(snapshot.get("package_type"))
    required = (
        "schema_version",
        "archive_id",
        "archive_hash",
        "created_at_utc",
        "workspace_id",
        "package_type",
        "package_id",
        "package_hash",
        "public_export_hash",
        "qa_report_hash",
        "proof_ready",
        "proof_grade",
        "overall_passed",
        "archive_status",
    )
    missing = [field for field in required if field not in snapshot]
    errors.extend(f"Missing archive field: {field}" for field in missing)
    if snapshot.get("schema_version") != PROOF_ARCHIVE_SCHEMA_VERSION:
        errors.append("Unsupported archive schema_version.")
    if package_type not in PROOF_ARCHIVE_PACKAGE_TYPES:
        errors.append(f"Unsupported package_type: {package_type}")
    rebuilt_hash = build_proof_archive_hash(snapshot) if snapshot.get("archive_hash") else ""
    if snapshot.get("archive_hash") and rebuilt_hash != snapshot.get("archive_hash"):
        errors.append("archive_hash does not match archive contents.")
    if package_type in PROOF_ARCHIVE_PUBLIC_PACKAGE_TYPES:
        text = _canonical_dumps(snapshot).lower()
        blocked = [term for term in PROOF_ARCHIVE_BLOCKED_PUBLIC_TERMS if term.lower() in text]
        if blocked:
            errors.append("Public/client archive snapshot contains blocked private terms or paths.")
        if snapshot.get("private_export_hash"):
            errors.append("Public/client archive snapshot exposes private_export_hash.")
    if package_type in PROOF_ARCHIVE_PRIVATE_PACKAGE_TYPES and "private_export_hash" not in snapshot:
        errors.append("Private/internal archive snapshot missing private_export_hash.")
    return {
        "passed": not errors,
        "checked_outputs": ["archive_snapshot", "archive_hash", "public_client_redaction", "private_internal_hash"],
        "warnings": [],
        "errors": errors,
        "details": {"package_type": package_type, "rebuilt_archive_hash": rebuilt_hash},
    }


def build_proof_archive_index(workspace_id: str | None = None) -> dict[str, Any]:
    snapshots = [build_proof_archive_snapshot(workspace_id, package_type) for package_type in PROOF_ARCHIVE_PACKAGE_TYPES]
    index = {
        "schema_version": PROOF_ARCHIVE_SCHEMA_VERSION,
        "workspace_id": workspace_id or "default",
        "generated_at_utc": _utc_now(),
        "snapshot_count": len(snapshots),
        "snapshots": snapshots,
        "archive_hashes": [snapshot.get("archive_hash") for snapshot in snapshots],
        "package_hashes": [snapshot.get("package_hash") for snapshot in snapshots],
        "qa_report_hashes": [snapshot.get("qa_report_hash") for snapshot in snapshots],
    }
    index["archive_index_hash"] = _hash_payload("archive_index_hash", {key: value for key, value in index.items() if key != "generated_at_utc"})
    return index


def compare_proof_archive_snapshots(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    changed_fields = []
    ignored = {"created_at_utc"}
    keys = sorted((set(left) | set(right)) - ignored)
    for key in keys:
        if left.get(key) != right.get(key):
            changed_fields.append(key)
    return {
        "left_archive_id": left.get("archive_id"),
        "right_archive_id": right.get("archive_id"),
        "left_archive_hash": left.get("archive_hash"),
        "right_archive_hash": right.get("archive_hash"),
        "same_archive_hash": left.get("archive_hash") == right.get("archive_hash"),
        "same_package_hash": left.get("package_hash") == right.get("package_hash"),
        "same_qa_report_hash": left.get("qa_report_hash") == right.get("qa_report_hash"),
        "changed_fields": changed_fields,
        "changed_field_count": len(changed_fields),
    }


def sanitize_public_archive_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "schema_version",
        "archive_id",
        "archive_hash",
        "created_at_utc",
        "workspace_id",
        "package_type",
        "package_id",
        "package_hash",
        "public_export_hash",
        "qa_report_id",
        "qa_report_hash",
        "proof_ready",
        "proof_grade",
        "ledger_backed",
        "selected_source",
        "ledger_integrity_status",
        "dashboard_ready",
        "overall_passed",
        "redaction_passed",
        "row_count",
        "unique_events",
        "wins",
        "losses",
        "pushes",
        "cancels",
        "ROI",
        "profit_units",
        "average_CLV",
        "warning_error_summary",
        "archive_status",
        "is_public_client",
    }
    return {key: value for key, value in dict(snapshot).items() if key in allowed}


def export_proof_archive_snapshot_json(snapshot: Mapping[str, Any], *, public_safe: bool = True) -> str:
    payload = sanitize_public_archive_snapshot(snapshot) if public_safe and _package_type(snapshot.get("package_type")) in PROOF_ARCHIVE_PUBLIC_PACKAGE_TYPES else dict(snapshot)
    return json.dumps(_json_safe(payload), sort_keys=True, indent=2)


def export_proof_archive_index_json(index: Mapping[str, Any], *, public_safe: bool = True) -> str:
    snapshots = []
    for snapshot in index.get("snapshots") or []:
        snapshots.append(sanitize_public_archive_snapshot(snapshot) if public_safe and _package_type(snapshot.get("package_type")) in PROOF_ARCHIVE_PUBLIC_PACKAGE_TYPES else dict(snapshot))
    payload = dict(index)
    payload["snapshots"] = snapshots
    return json.dumps(_json_safe(payload), sort_keys=True, indent=2)
