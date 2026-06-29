from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id

WORKSPACE_ISOLATION_SCHEMA_VERSION = "workspace_isolation_v1"
WORKSPACE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{1,62}[a-zA-Z0-9]$|^[a-zA-Z0-9]$")
WORKSPACE_PRIVATE_KEYS = (
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
)
WORKSPACE_PRIVATE_PATH_MARKERS = (
    "/home/",
    "/mnt/",
    "data/private",
    ".env",
    "C:\\",
)
WORKSPACE_OBJECT_TYPES = (
    "row",
    "package",
    "qa_report",
    "archive_snapshot",
    "archive_index",
    "dashboard_payload",
    "report_publisher_payload",
)


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


def normalize_workspace_scope(workspace_id: str | None) -> str:
    value = normalize_workspace_id(workspace_id or "default")
    return str(value or "default").strip() or "default"


def validate_workspace_id(workspace_id: str | None) -> dict[str, Any]:
    raw = str(workspace_id or "default").strip()
    normalized = normalize_workspace_scope(workspace_id)
    errors: list[str] = []
    warnings: list[str] = []
    raw_lowered = raw.lower()
    if raw_lowered in {"all", "global", "*", "any", "none", "null"}:
        errors.append("workspace_id uses a reserved cross-workspace value.")
    if ".." in raw or "/" in raw or "\\" in raw:
        errors.append("workspace_id must not contain path separators or traversal markers.")
    if raw != normalized and any(marker in raw for marker in ("/", "\\", "..", "*")):
        errors.append("workspace_id contains unsafe raw characters before normalization.")
    if not WORKSPACE_ID_PATTERN.match(normalized):
        errors.append("workspace_id contains unsupported characters or length.")
    lowered = normalized.lower()
    if lowered in {"all", "global", "*", "any", "none", "null"}:
        errors.append("workspace_id uses a reserved cross-workspace value.")
    if ".." in normalized or "/" in normalized or "\\" in normalized:
        errors.append("workspace_id must not contain path separators or traversal markers.")
    if normalized == "default":
        warnings.append("default workspace should be used only for local/single-tenant mode.")
    return {
        "passed": not errors,
        "workspace_id": normalized,
        "checked_outputs": ["workspace_id", "reserved_values", "path_traversal", "raw_input"],
        "warnings": warnings,
        "errors": sorted(set(errors)),
        "details": {"pattern": WORKSPACE_ID_PATTERN.pattern},
    }


def _object_type(item: Mapping[str, Any], fallback: str = "row") -> str:
    for key in ("object_type", "payload_type", "record_type"):
        value = str(item.get(key) or "").strip().lower()
        if value in WORKSPACE_OBJECT_TYPES:
            return value
    if "package_hash" in item and "qa_report_hash" in item and "archive_hash" in item:
        return "archive_snapshot"
    if "package_type_results" in item or "qa_report_hash" in item:
        return "qa_report"
    if "package_hash" in item or "package_id" in item:
        return "package"
    return fallback


def _workspace_value(item: Mapping[str, Any]) -> str:
    for key in ("workspace_id", "client_workspace_id", "tenant_id", "client_id"):
        value = item.get(key)
        if value not in (None, ""):
            return normalize_workspace_scope(str(value))
    return ""


def _contains_private_markers(value: Any) -> tuple[list[str], list[str]]:
    text = _canonical_dumps(value).lower()
    key_hits = [marker for marker in WORKSPACE_PRIVATE_KEYS if marker.lower() in text]
    path_hits = [marker for marker in WORKSPACE_PRIVATE_PATH_MARKERS if marker.lower() in text]
    return key_hits, path_hits


def validate_workspace_object(workspace_id: str | None, item: Mapping[str, Any], *, object_type: str | None = None, public_client: bool = True) -> dict[str, Any]:
    expected = normalize_workspace_scope(workspace_id)
    actual = _workspace_value(item)
    resolved_type = object_type or _object_type(item)
    errors: list[str] = []
    warnings: list[str] = []
    if not actual:
        errors.append("object missing workspace_id.")
    elif actual != expected:
        errors.append("object workspace_id does not match requested workspace.")
    if resolved_type not in WORKSPACE_OBJECT_TYPES:
        errors.append("unsupported object_type.")
    blocked_terms: list[str] = []
    blocked_paths: list[str] = []
    if public_client:
        blocked_terms, blocked_paths = _contains_private_markers(item)
        if blocked_terms or blocked_paths:
            errors.append("public/client workspace object contains private markers.")
    return {
        "passed": not errors,
        "workspace_id": expected,
        "object_workspace_id": actual,
        "object_type": resolved_type,
        "checked_outputs": ["workspace_match", "object_type", "public_client_safety"],
        "warnings": warnings,
        "errors": errors,
        "details": {
            "blocked_terms_count": len(blocked_terms),
            "blocked_paths_count": len(blocked_paths),
        },
    }


def filter_workspace_objects(workspace_id: str | None, items: Sequence[Mapping[str, Any]], *, public_client: bool = True) -> dict[str, Any]:
    expected = normalize_workspace_scope(workspace_id)
    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, item in enumerate(items or []):
        result = validate_workspace_object(expected, item, public_client=public_client)
        if result["passed"]:
            kept.append(dict(item))
        else:
            rejected.append({
                "index": index,
                "object_type": result.get("object_type"),
                "object_workspace_id": result.get("object_workspace_id"),
                "errors": list(result.get("errors") or []),
            })
    return {
        "workspace_id": expected,
        "input_count": len(items or []),
        "kept_count": len(kept),
        "rejected_count": len(rejected),
        "kept": kept,
        "rejected": rejected,
        "passed": not rejected,
    }


def build_workspace_isolation_report(workspace_id: str | None, artifacts: Mapping[str, Any] | None = None, *, public_client: bool = True) -> dict[str, Any]:
    expected = normalize_workspace_scope(workspace_id)
    workspace_check = validate_workspace_id(workspace_id)
    artifact_map = dict(artifacts or {})
    object_results: list[dict[str, Any]] = []
    leakage_count = 0
    missing_workspace_count = 0
    private_marker_count = 0
    checked_objects = 0

    for artifact_name, artifact_value in artifact_map.items():
        values = artifact_value if isinstance(artifact_value, list) else [artifact_value]
        for index, item in enumerate(values):
            if not isinstance(item, Mapping):
                object_results.append({
                    "artifact_name": artifact_name,
                    "index": index,
                    "passed": False,
                    "errors": ["artifact item is not a mapping."],
                    "object_type": "unknown",
                    "object_workspace_id": "",
                })
                leakage_count += 1
                continue
            checked_objects += 1
            result = validate_workspace_object(expected, item, public_client=public_client)
            row = {
                "artifact_name": artifact_name,
                "index": index,
                "passed": result.get("passed"),
                "object_type": result.get("object_type"),
                "object_workspace_id": result.get("object_workspace_id"),
                "errors": list(result.get("errors") or []),
                "warning_count": len(result.get("warnings") or []),
                "blocked_terms_count": (result.get("details") or {}).get("blocked_terms_count", 0),
                "blocked_paths_count": (result.get("details") or {}).get("blocked_paths_count", 0),
            }
            object_results.append(row)
            if not result.get("object_workspace_id"):
                missing_workspace_count += 1
            if result.get("object_workspace_id") and result.get("object_workspace_id") != expected:
                leakage_count += 1
            private_marker_count += int(row["blocked_terms_count"] or 0) + int(row["blocked_paths_count"] or 0)

    failed_objects = [row for row in object_results if not row.get("passed")]
    report = {
        "schema_version": WORKSPACE_ISOLATION_SCHEMA_VERSION,
        "workspace_id": expected,
        "generated_at_utc": _utc_now(),
        "report_id": "",
        "report_hash": "",
        "workspace_id_valid": workspace_check.get("passed"),
        "checked_artifact_count": len(artifact_map),
        "checked_object_count": checked_objects,
        "failed_object_count": len(failed_objects),
        "cross_workspace_leakage_count": leakage_count,
        "missing_workspace_count": missing_workspace_count,
        "private_marker_count": private_marker_count,
        "public_client_mode": bool(public_client),
        "overall_passed": bool(workspace_check.get("passed")) and not failed_objects and leakage_count == 0 and private_marker_count == 0,
        "object_results": object_results,
        "warnings": list(workspace_check.get("warnings") or []),
        "errors": list(workspace_check.get("errors") or []) + [error for row in failed_objects for error in row.get("errors", [])],
    }
    report["report_id"] = _hash_payload("workspace_isolation", {
        "workspace_id": expected,
        "object_results": object_results,
        "public_client_mode": bool(public_client),
    }, length=24)
    report["report_hash"] = build_workspace_isolation_hash(report)
    return report


def build_workspace_isolation_hash(report: Mapping[str, Any]) -> str:
    stable = {key: value for key, value in dict(report).items() if key not in {"generated_at_utc", "report_hash"}}
    return _hash_payload("workspace_isolation_hash", stable)


def validate_workspace_isolation_report(report: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    required = (
        "schema_version",
        "workspace_id",
        "report_id",
        "report_hash",
        "workspace_id_valid",
        "checked_object_count",
        "failed_object_count",
        "cross_workspace_leakage_count",
        "private_marker_count",
        "overall_passed",
    )
    for field in required:
        if field not in report:
            errors.append(f"missing field: {field}")
    if report.get("schema_version") != WORKSPACE_ISOLATION_SCHEMA_VERSION:
        errors.append("unsupported workspace isolation schema_version.")
    if report.get("report_hash") and build_workspace_isolation_hash(report) != report.get("report_hash"):
        errors.append("report_hash does not match report contents.")
    if report.get("overall_passed") and (report.get("failed_object_count") or report.get("cross_workspace_leakage_count") or report.get("private_marker_count")):
        errors.append("overall_passed is overstated.")
    return {
        "passed": not errors,
        "checked_outputs": ["schema_version", "report_hash", "overall_passed", "leakage_counts"],
        "warnings": [],
        "errors": errors,
        "details": {"rebuilt_report_hash": build_workspace_isolation_hash(report) if report.get("report_hash") else ""},
    }


def sanitize_workspace_isolation_report(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report.get("schema_version"),
        "workspace_id": report.get("workspace_id"),
        "report_id": report.get("report_id"),
        "report_hash": report.get("report_hash"),
        "workspace_id_valid": report.get("workspace_id_valid"),
        "checked_artifact_count": report.get("checked_artifact_count", 0),
        "checked_object_count": report.get("checked_object_count", 0),
        "failed_object_count": report.get("failed_object_count", 0),
        "cross_workspace_leakage_count": report.get("cross_workspace_leakage_count", 0),
        "missing_workspace_count": report.get("missing_workspace_count", 0),
        "private_marker_count": report.get("private_marker_count", 0),
        "public_client_mode": report.get("public_client_mode"),
        "overall_passed": report.get("overall_passed"),
        "object_results": [
            {
                "artifact_name": row.get("artifact_name"),
                "index": row.get("index"),
                "passed": row.get("passed"),
                "object_type": row.get("object_type"),
                "object_workspace_id": row.get("object_workspace_id"),
                "error_count": len(row.get("errors") or []),
                "blocked_terms_count": row.get("blocked_terms_count", 0),
                "blocked_paths_count": row.get("blocked_paths_count", 0),
            }
            for row in report.get("object_results") or []
        ],
        "warning_count": len(report.get("warnings") or []),
        "error_count": len(report.get("errors") or []),
    }


def export_workspace_isolation_report_json(report: Mapping[str, Any], *, public_safe: bool = True) -> str:
    payload = sanitize_workspace_isolation_report(report) if public_safe else dict(report)
    return json.dumps(_json_safe(payload), sort_keys=True, indent=2)
