from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

CLIENT_ACCESS_SCHEMA_VERSION = "client_access_roles_v1"
CLIENT_ACCESS_ROLES = ("admin", "operator", "client", "demo", "public")
CLIENT_ACCESS_PACKAGE_TYPES = ("public", "client", "private", "internal_review")
CLIENT_ACCESS_ACTIONS = (
    "view",
    "download_json",
    "download_markdown",
    "download_csv",
    "run_qa",
    "run_e2e_qa",
    "approve_import",
    "view_private_audit",
    "view_public_share",
    "view_client_viewer",
    "view_archive",
    "view_workspace_audit",
)
CLIENT_ACCESS_RESOURCES = (
    "dashboard",
    "proof_center",
    "report_studio",
    "public_proof_share",
    "client_proof_viewer",
    "proof_archive_viewer",
    "workspace_isolation_audit",
    "proof_package",
    "qa_report",
    "archive_snapshot",
)
PRIVATE_PACKAGE_TYPES = {"private", "internal_review"}
PUBLIC_CLIENT_PACKAGE_TYPES = {"public", "client"}

ROLE_POLICIES: dict[str, dict[str, Any]] = {
    "admin": {
        "description": "Full local operator role. Can view private/internal proof surfaces and approve imports.",
        "resources": set(CLIENT_ACCESS_RESOURCES),
        "actions": set(CLIENT_ACCESS_ACTIONS),
        "package_types": set(CLIENT_ACCESS_PACKAGE_TYPES),
        "private_internal_allowed": True,
    },
    "operator": {
        "description": "Proof operator role. Can run QA and view private/internal review surfaces but cannot approve imports by policy prep.",
        "resources": {"dashboard", "proof_center", "report_studio", "proof_archive_viewer", "workspace_isolation_audit", "proof_package", "qa_report", "archive_snapshot"},
        "actions": {"view", "download_json", "download_markdown", "download_csv", "run_qa", "run_e2e_qa", "view_private_audit", "view_archive", "view_workspace_audit"},
        "package_types": set(CLIENT_ACCESS_PACKAGE_TYPES),
        "private_internal_allowed": True,
    },
    "client": {
        "description": "Client role. Can view client-safe proof, public proof, client viewer, and sanitized archives only.",
        "resources": {"dashboard", "public_proof_share", "client_proof_viewer", "proof_archive_viewer", "proof_package", "archive_snapshot"},
        "actions": {"view", "download_json", "download_markdown", "download_csv", "view_public_share", "view_client_viewer", "view_archive"},
        "package_types": {"public", "client"},
        "private_internal_allowed": False,
    },
    "demo": {
        "description": "Demo role. Can view public-safe proof surfaces only; no downloads of private/internal material.",
        "resources": {"dashboard", "public_proof_share", "proof_package"},
        "actions": {"view", "view_public_share"},
        "package_types": {"public"},
        "private_internal_allowed": False,
    },
    "public": {
        "description": "Public verification role. Can view public proof share only.",
        "resources": {"public_proof_share", "proof_package"},
        "actions": {"view", "view_public_share"},
        "package_types": {"public"},
        "private_internal_allowed": False,
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (set, tuple, list)):
        return [_json_safe(item) for item in sorted(value) if isinstance(value, set)] if isinstance(value, set) else [_json_safe(item) for item in value]
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


def normalize_client_role(role: str | None) -> str:
    value = str(role or "public").strip().lower().replace(" ", "_")
    aliases = {
        "owner": "admin",
        "super_admin": "admin",
        "ops": "operator",
        "proof_operator": "operator",
        "subscriber": "client",
        "customer": "client",
        "viewer": "demo",
        "guest": "public",
    }
    return aliases.get(value, value if value in CLIENT_ACCESS_ROLES else "public")


def get_role_access_policy(role: str | None) -> dict[str, Any]:
    normalized = normalize_client_role(role)
    policy = ROLE_POLICIES[normalized]
    return {
        "schema_version": CLIENT_ACCESS_SCHEMA_VERSION,
        "role": normalized,
        "description": policy["description"],
        "resources": sorted(policy["resources"]),
        "actions": sorted(policy["actions"]),
        "package_types": sorted(policy["package_types"]),
        "private_internal_allowed": bool(policy["private_internal_allowed"]),
    }


def validate_role_access(role: str | None, resource: str, action: str = "view", package_type: str | None = None) -> dict[str, Any]:
    normalized = normalize_client_role(role)
    policy = get_role_access_policy(normalized)
    selected_resource = str(resource or "").strip().lower()
    selected_action = str(action or "view").strip().lower()
    selected_package_type = str(package_type or "public").strip().lower()
    errors: list[str] = []
    warnings: list[str] = []
    if selected_resource not in CLIENT_ACCESS_RESOURCES:
        errors.append("unsupported resource")
    if selected_action not in CLIENT_ACCESS_ACTIONS:
        errors.append("unsupported action")
    if selected_package_type not in CLIENT_ACCESS_PACKAGE_TYPES:
        errors.append("unsupported package_type")
    if selected_resource not in policy["resources"]:
        errors.append("role cannot access resource")
    if selected_action not in policy["actions"]:
        errors.append("role cannot perform action")
    if selected_package_type not in policy["package_types"]:
        errors.append("role cannot access package_type")
    if selected_package_type in PRIVATE_PACKAGE_TYPES and not policy["private_internal_allowed"]:
        errors.append("role cannot access private/internal package types")
    if selected_action in {"approve_import", "view_private_audit"} and not policy["private_internal_allowed"]:
        errors.append("role cannot access private/internal operations")
    if normalized == "operator" and selected_action == "approve_import":
        errors.append("operator role cannot approve imports in SaaS-prep policy")
    if normalized in {"client", "demo", "public"} and selected_resource in {"proof_center", "workspace_isolation_audit"}:
        warnings.append("client/demo/public role is blocked from operator-only surfaces")
    return {
        "passed": not errors,
        "role": normalized,
        "resource": selected_resource,
        "action": selected_action,
        "package_type": selected_package_type,
        "allowed": not errors,
        "checked_outputs": ["role", "resource", "action", "package_type", "private_internal_access"],
        "warnings": warnings,
        "errors": errors,
    }


def build_client_access_role_matrix() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for role in CLIENT_ACCESS_ROLES:
        for resource in CLIENT_ACCESS_RESOURCES:
            for package_type in CLIENT_ACCESS_PACKAGE_TYPES:
                result = validate_role_access(role, resource, "view", package_type)
                rows.append({
                    "role": role,
                    "resource": resource,
                    "action": "view",
                    "package_type": package_type,
                    "allowed": result["allowed"],
                    "error_count": len(result["errors"]),
                })
    matrix = {
        "schema_version": CLIENT_ACCESS_SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "roles": list(CLIENT_ACCESS_ROLES),
        "resources": list(CLIENT_ACCESS_RESOURCES),
        "package_types": list(CLIENT_ACCESS_PACKAGE_TYPES),
        "rows": rows,
    }
    matrix["matrix_hash"] = _hash_payload("client_access_matrix", {key: value for key, value in matrix.items() if key != "generated_at_utc"})
    return matrix


def build_client_access_audit_report(role: str | None = "client") -> dict[str, Any]:
    normalized = normalize_client_role(role)
    checks = [
        validate_role_access(normalized, "public_proof_share", "view_public_share", "public"),
        validate_role_access(normalized, "client_proof_viewer", "view_client_viewer", "client"),
        validate_role_access(normalized, "proof_package", "download_json", "client"),
        validate_role_access(normalized, "proof_package", "download_json", "private"),
        validate_role_access(normalized, "qa_report", "run_qa", "public"),
        validate_role_access(normalized, "workspace_isolation_audit", "view_workspace_audit", "public"),
        validate_role_access(normalized, "proof_center", "approve_import", "private"),
    ]
    denied_private = [check for check in checks if check["package_type"] in PRIVATE_PACKAGE_TYPES and not check["allowed"]]
    unexpected_private_allows = [check for check in checks if check["package_type"] in PRIVATE_PACKAGE_TYPES and check["allowed"] and normalized not in {"admin", "operator"}]
    failed_checks = [check for check in checks if not check["allowed"] and normalized in {"admin"}]
    report = {
        "schema_version": CLIENT_ACCESS_SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "report_id": "",
        "report_hash": "",
        "role": normalized,
        "policy": get_role_access_policy(normalized),
        "check_count": len(checks),
        "allowed_count": len([check for check in checks if check["allowed"]]),
        "denied_count": len([check for check in checks if not check["allowed"]]),
        "private_denial_count": len(denied_private),
        "unexpected_private_allow_count": len(unexpected_private_allows),
        "overall_passed": not unexpected_private_allows and not failed_checks,
        "checks": checks,
        "warnings": [],
        "errors": [error for check in failed_checks for error in check.get("errors", [])],
    }
    report["report_id"] = _hash_payload("client_access_audit", {"role": normalized, "checks": checks}, length=24)
    report["report_hash"] = build_client_access_report_hash(report)
    return report


def build_client_access_report_hash(report: Mapping[str, Any]) -> str:
    stable = {key: value for key, value in dict(report).items() if key not in {"generated_at_utc", "report_hash"}}
    return _hash_payload("client_access_hash", stable)


def validate_client_access_audit_report(report: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    required = (
        "schema_version",
        "report_id",
        "report_hash",
        "role",
        "policy",
        "check_count",
        "allowed_count",
        "denied_count",
        "unexpected_private_allow_count",
        "overall_passed",
        "checks",
    )
    for field in required:
        if field not in report:
            errors.append(f"missing field: {field}")
    if report.get("schema_version") != CLIENT_ACCESS_SCHEMA_VERSION:
        errors.append("unsupported client access schema_version")
    if report.get("report_hash") and build_client_access_report_hash(report) != report.get("report_hash"):
        errors.append("report_hash does not match report contents")
    if report.get("overall_passed") and report.get("unexpected_private_allow_count"):
        errors.append("overall_passed is overstated")
    return {
        "passed": not errors,
        "checked_outputs": ["schema_version", "report_hash", "overall_passed", "private_access"],
        "warnings": [],
        "errors": errors,
        "details": {"rebuilt_report_hash": build_client_access_report_hash(report) if report.get("report_hash") else ""},
    }


def sanitize_client_access_audit_report(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report.get("schema_version"),
        "report_id": report.get("report_id"),
        "report_hash": report.get("report_hash"),
        "role": report.get("role"),
        "check_count": report.get("check_count", 0),
        "allowed_count": report.get("allowed_count", 0),
        "denied_count": report.get("denied_count", 0),
        "private_denial_count": report.get("private_denial_count", 0),
        "unexpected_private_allow_count": report.get("unexpected_private_allow_count", 0),
        "overall_passed": report.get("overall_passed"),
        "policy": {
            "role": (report.get("policy") or {}).get("role"),
            "resources": (report.get("policy") or {}).get("resources", []),
            "actions": (report.get("policy") or {}).get("actions", []),
            "package_types": (report.get("policy") or {}).get("package_types", []),
            "private_internal_allowed": (report.get("policy") or {}).get("private_internal_allowed"),
        },
        "checks": [
            {
                "role": check.get("role"),
                "resource": check.get("resource"),
                "action": check.get("action"),
                "package_type": check.get("package_type"),
                "allowed": check.get("allowed"),
                "error_count": len(check.get("errors") or []),
                "warning_count": len(check.get("warnings") or []),
            }
            for check in report.get("checks") or []
        ],
        "warning_count": len(report.get("warnings") or []),
        "error_count": len(report.get("errors") or []),
    }


def export_client_access_audit_report_json(report: Mapping[str, Any], *, public_safe: bool = True) -> str:
    payload = sanitize_client_access_audit_report(report) if public_safe else dict(report)
    return json.dumps(_json_safe(payload), sort_keys=True, indent=2)
