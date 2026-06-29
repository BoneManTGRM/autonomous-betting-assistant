import hashlib
from typing import Any, Mapping

from autonomous_betting_agent.proof_package_service import (
    EMPTY_GRADE,
    NO_PLAYABLE_POSITIVE_EV_MESSAGE,
    PRIVATE_PACKAGE_TYPES,
    PROOF_READY_GRADE,
    PUBLIC_PACKAGE_TYPES,
    build_client_summary_package,
    build_internal_review_package,
    build_private_audit_package,
    build_public_proof_package,
    export_proof_package_csv_bundle,
    export_proof_package_json,
    export_proof_package_markdown,
)

PACKAGE_BUILDERS = {
    "public": build_public_proof_package,
    "client": build_client_summary_package,
    "private": build_private_audit_package,
    "internal_review": build_internal_review_package,
}


def _hash_text(prefix: str, value: str, length: int = 24) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:length]}"


def _package_builder(package_type: str):
    key = str(package_type or "public").strip().lower()
    if key not in PACKAGE_BUILDERS:
        raise ValueError(f"Unsupported package_type: {package_type}")
    return key, PACKAGE_BUILDERS[key]


def _headline(package: Mapping[str, Any]) -> str:
    if package.get("proof_grade") == PROOF_READY_GRADE:
        return "ABA Signal Pro proof package is ledger-backed and proof-ready."
    if package.get("proof_grade") == EMPTY_GRADE:
        return "ABA Signal Pro proof package is empty and not proof-ready."
    return "ABA Signal Pro proof package is provisional and not final proof."


def _performance_summary(package: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "proof_grade": package.get("proof_grade"),
        "proof_ready": package.get("proof_ready"),
        "ledger_backed": package.get("ledger_backed"),
        "selected_source": package.get("selected_source"),
        "total_rows": package.get("total_rows", 0),
        "unique_events": package.get("unique_events", 0),
        "wins": package.get("wins", 0),
        "losses": package.get("losses", 0),
        "pushes": package.get("pushes", 0),
        "cancels": package.get("cancels", 0),
        "win_rate_ex_push_cancel": package.get("win_rate_ex_push_cancel", 0.0),
        "profit_units": package.get("profit_units", 0.0),
        "ROI": package.get("ROI", 0.0),
        "average_CLV": package.get("average_CLV"),
        "duplicate_count": package.get("duplicate_count", 0),
        "correction_count": package.get("correction_count", 0),
    }


def _risk_summary(package: Mapping[str, Any]) -> dict[str, Any]:
    warnings = list(package.get("warnings", []) or [])
    errors = list(package.get("errors", []) or [])
    return {
        "ledger_integrity_status": package.get("ledger_integrity_status"),
        "dashboard_ready": package.get("dashboard_ready"),
        "redaction_passed": (package.get("redaction_status") or {}).get("passed", False),
        "warning_count": len(warnings),
        "error_count": len(errors),
        "warnings": warnings,
        "errors": errors,
    }


def _top_positive_ev_summary(package: Mapping[str, Any]) -> dict[str, Any]:
    picks = list(package.get("top_positive_ev_picks") or [])
    return {
        "count": len(picks),
        "message": NO_PLAYABLE_POSITIVE_EV_MESSAGE if not picks else f"{len(picks)} playable positive-EV picks available.",
        "picks": picks,
    }


def _proof_disclaimer(package: Mapping[str, Any]) -> str:
    if not package.get("proof_ready"):
        return "This package is not final proof. Fallback/session/upload data is provisional unless ledger-backed proof readiness passes."
    return "This package is ledger-backed proof-ready based on the current proof ledger and redaction validation."


def _export_files(package: Mapping[str, Any]) -> dict[str, Any]:
    json_text = export_proof_package_json(package)
    markdown_text = export_proof_package_markdown(package)
    csv_bundle = export_proof_package_csv_bundle(package)
    return {
        "json": {
            "filename": f"aba_proof_package_{package.get('workspace_id', 'default')}_{package.get('package_type', 'public')}.json",
            "content": json_text,
        },
        "markdown": {
            "filename": f"aba_proof_package_{package.get('workspace_id', 'default')}_{package.get('package_type', 'public')}.md",
            "content": markdown_text,
        },
        "csv_bundle": csv_bundle,
    }


def build_report_publisher_payload(workspace_id: str | None = None, package_type: str = "public") -> dict[str, Any]:
    selected_type, builder = _package_builder(package_type)
    package = builder(workspace_id)
    export_files = _export_files(package)
    report_seed = "|".join(
        [
            str(package.get("workspace_id", "default")),
            selected_type,
            str(package.get("package_id", "")),
            str(package.get("package_hash", "")),
        ]
    )
    payload = {
        "report_id": _hash_text("report", report_seed, length=24),
        "package_id": package.get("package_id", ""),
        "package_hash": package.get("package_hash", ""),
        "generated_at_utc": package.get("generated_at_utc", ""),
        "workspace_id": package.get("workspace_id", "default"),
        "package_type": selected_type,
        "proof_grade": package.get("proof_grade", ""),
        "proof_ready": package.get("proof_ready", False),
        "ledger_backed": package.get("ledger_backed", False),
        "headline_summary": _headline(package),
        "performance_summary": _performance_summary(package),
        "proof_summary": package.get("proof_summary", {}),
        "roi_summary": package.get("roi_summary", {}),
        "clv_summary": package.get("clv_summary", {}),
        "risk_summary": _risk_summary(package),
        "top_positive_ev_summary": _top_positive_ev_summary(package),
        "proof_disclaimer": _proof_disclaimer(package),
        "verification_manifest": package.get("verification_manifest", {}),
        "export_files": export_files,
    }
    if selected_type in PUBLIC_PACKAGE_TYPES:
        payload["public_package"] = package
    if selected_type in PRIVATE_PACKAGE_TYPES:
        payload["private_package"] = package
    return payload
