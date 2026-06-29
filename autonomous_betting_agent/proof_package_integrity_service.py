import copy
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from autonomous_betting_agent.proof_package_service import (
    EMPTY_GRADE,
    PRIVATE_PACKAGE_TYPES,
    PROOF_READY_GRADE,
    PROVISIONAL_GRADE,
    PUBLIC_PACKAGE_TYPES,
    build_client_summary_package,
    build_export_hash,
    build_internal_review_package,
    build_package_hash,
    build_private_audit_package,
    build_public_proof_package,
    export_proof_package_csv_bundle,
    export_proof_package_json,
    export_proof_package_markdown,
    package_is_proof_ready,
    validate_public_package_redactions,
)
from autonomous_betting_agent.report_publisher_service import build_report_publisher_payload

SUPPORTED_PACKAGE_TYPES = PUBLIC_PACKAGE_TYPES | PRIVATE_PACKAGE_TYPES
VALIDATOR_KEYS = ("passed", "checked_outputs", "warnings", "errors", "details")
BLOCKED_TERMS = (
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
BLOCKED_PATHS = ("/home/", "/mnt/", "c:\\", "data/private", ".env")
REQUIRED_PACKAGE_FIELDS = (
    "package_id",
    "package_hash",
    "generated_at_utc",
    "workspace_id",
    "package_type",
    "proof_grade",
    "proof_ready",
    "selected_source",
    "ledger_integrity_status",
    "dashboard_ready",
    "public_export_hash",
)
PACKAGE_BUILDERS: dict[str, Callable[[str | None], dict[str, Any]]] = {
    "public": build_public_proof_package,
    "client": build_client_summary_package,
    "private": build_private_audit_package,
    "internal_review": build_internal_review_package,
}
WRITE_MUTATION_TOKENS = (
    "append_" + "performance_rows",
    "sync_" + "rows_by_source",
    "approve_" + "ledger_import",
    "preview_" + "ledger_import",
    "create_" + "correction",
    "apply_" + "correction",
    "update_" + "result",
    "mutate_" + "result",
    "delete_" + "proof",
    "official_" + "lock_mutation",
    "retrain_" + "model",
    "op" + "en(",
    ".wr" + "ite(",
    "wr" + "ite_text(",
    "wr" + "ite_bytes(",
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


def _hash_text(prefix: str, value: str, length: int = 24) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:length]}"


def _result(passed: bool, checked_outputs: Sequence[str] | None = None, warnings: Sequence[str] | None = None, errors: Sequence[str] | None = None, details: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"passed": bool(passed), "checked_outputs": list(checked_outputs or []), "warnings": list(warnings or []), "errors": list(errors or []), "details": dict(details or {})}


def _unsupported(package_type: str) -> dict[str, Any]:
    return _result(False, ["package_type"], errors=[f"Unsupported package_type: {package_type}"], details={"package_type": package_type})


def _package_type(package: Mapping[str, Any]) -> str:
    return str(package.get("package_type") or "").strip().lower()


def _is_public(package: Mapping[str, Any]) -> bool:
    return _package_type(package) in PUBLIC_PACKAGE_TYPES


def _is_private(package: Mapping[str, Any]) -> bool:
    return _package_type(package) in PRIVATE_PACKAGE_TYPES


def _read_file_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception:
        return ""


def _scan_text(name: str, text: str) -> tuple[list[str], list[str]]:
    lowered = (text or "").lower()
    terms = [f"{name}:{term}" for term in BLOCKED_TERMS if term.lower() in lowered]
    paths = [f"{name}:{path}" for path in BLOCKED_PATHS if path.lower() in lowered]
    return terms, paths


def _scan_outputs(outputs: Mapping[str, str]) -> tuple[list[str], list[str]]:
    terms: list[str] = []
    paths: list[str] = []
    for name, text in outputs.items():
        output_terms, output_paths = _scan_text(name, text)
        terms.extend(output_terms)
        paths.extend(output_paths)
    return terms, paths


def _csv_ok(filename: str, csv_text: str) -> tuple[bool, str]:
    if str(csv_text or "") == "":
        return True, "empty"
    try:
        rows = list(csv.DictReader(io.StringIO(str(csv_text))))
    except Exception as exc:
        return False, f"{filename}: {exc}"
    return True, f"{len(rows)} rows"


def _required_missing(package: Mapping[str, Any]) -> list[str]:
    missing = [field for field in REQUIRED_PACKAGE_FIELDS if field not in package]
    if _is_private(package) and "private_export_hash" not in package:
        missing.append("private_export_hash")
    return missing


def validate_package_export_integrity(package: Mapping[str, Any]) -> dict[str, Any]:
    package_type = _package_type(package)
    if package_type not in SUPPORTED_PACKAGE_TYPES:
        return _unsupported(package_type)
    errors = [f"Missing required field: {field}" for field in _required_missing(package)]
    details: dict[str, Any] = {"package_type": package_type}
    try:
        json_text = export_proof_package_json(package)
        parsed = json.loads(json_text)
        if not isinstance(parsed, Mapping):
            errors.append("JSON export did not deserialize to an object.")
        else:
            for key in ("package_id", "package_hash", "proof_grade"):
                if parsed.get(key) != package.get(key):
                    errors.append(f"JSON {key} does not match package preview.")
    except Exception as exc:
        json_text = ""
        errors.append(f"JSON export could not be parsed: {exc}")
    try:
        markdown_text = export_proof_package_markdown(package)
        for token in (str(package.get("package_id") or ""), str(package.get("proof_grade") or ""), str(package.get("proof_ready") or ""), str(package.get("package_hash") or ""), "Performance Summary", "Disclaimer"):
            if token and token not in markdown_text:
                errors.append(f"Markdown export missing token: {token}")
    except Exception as exc:
        markdown_text = ""
        errors.append(f"Markdown export could not be generated: {exc}")
    try:
        csv_bundle = export_proof_package_csv_bundle(package)
        if not isinstance(csv_bundle, Mapping):
            errors.append("CSV bundle is not filename -> CSV string mapping.")
            csv_bundle = {}
        csv_details = {}
        for filename, csv_text in csv_bundle.items():
            ok, message = _csv_ok(str(filename), str(csv_text))
            csv_details[str(filename)] = message
            if not ok:
                errors.append(f"CSV bundle member is not parseable: {message}")
        details["csv_parse_results"] = csv_details
    except Exception as exc:
        csv_bundle = {}
        errors.append(f"CSV bundle could not be generated: {exc}")
    if not package.get("package_hash"):
        errors.append("package_hash is missing.")
    else:
        rebuilt = build_package_hash(package)
        details["rebuilt_package_hash"] = rebuilt
        if rebuilt != package.get("package_hash"):
            errors.append("package_hash does not match rebuilt package hash.")
    try:
        public_export_hash = build_export_hash(str(package.get("public_export_csv") or ""), str(package.get("public_export_json") or ""))
        details["rebuilt_public_export_hash"] = public_export_hash
        if package.get("public_export_hash") and public_export_hash != package.get("public_export_hash"):
            errors.append("public_export_hash does not match current public export contents.")
    except Exception as exc:
        errors.append(f"public_export_hash could not be verified: {exc}")
    if package_type in PRIVATE_PACKAGE_TYPES:
        if not package.get("private_export_hash"):
            errors.append("private_export_hash is missing for private/internal package.")
        else:
            rebuilt_private = build_export_hash(str(package.get("private_export_csv") or ""), str(package.get("private_export_json") or ""))
            details["rebuilt_private_export_hash"] = rebuilt_private
            if rebuilt_private != package.get("private_export_hash"):
                errors.append("private_export_hash does not match current private export contents.")
    elif package.get("private_export_hash"):
        errors.append("private_export_hash must not be present for public/client packages.")
    if _is_public(package):
        terms, paths = _scan_outputs({"json": json_text, "markdown": markdown_text, "csv_bundle": "\n".join(str(value) for value in csv_bundle.values())})
        details["blocked_terms_found"] = terms
        details["blocked_paths_found"] = paths
        if terms or paths:
            errors.append("Public/client exports expose blocked private fields or paths.")
    return _result(not errors, ["json", "markdown", "csv_bundle", "package_hash", "export_hash"], errors=errors, details=details)


def validate_public_client_package_safety(package: Mapping[str, Any]) -> dict[str, Any]:
    package_type = _package_type(package)
    if package_type not in SUPPORTED_PACKAGE_TYPES:
        return _unsupported(package_type)
    if package_type in PRIVATE_PACKAGE_TYPES:
        return _result(True, ["package_type"], warnings=["Private/internal package: public/client safety is not applicable."], details={"package_type": package_type})
    outputs = {
        "package": json.dumps(package, sort_keys=True, default=str),
        "json": export_proof_package_json(package),
        "markdown": export_proof_package_markdown(package),
        "csv_bundle": "\n".join(str(value) for value in export_proof_package_csv_bundle(package).values()),
    }
    terms, paths = _scan_outputs(outputs)
    redaction = validate_public_package_redactions(package)
    errors: list[str] = []
    if terms:
        errors.append(f"Blocked terms found: {terms}")
    if paths:
        errors.append(f"Blocked paths found: {paths}")
    if not redaction.get("passed", False):
        errors.append("validate_public_package_redactions did not pass.")
    return _result(not errors, list(outputs.keys()), errors=errors, details={"blocked_terms_found": terms, "blocked_paths_found": paths, "redaction_status": redaction})


def validate_private_internal_package_isolation(package: Mapping[str, Any]) -> dict[str, Any]:
    package_type = _package_type(package)
    if package_type not in SUPPORTED_PACKAGE_TYPES:
        return _unsupported(package_type)
    proof_center = _read_file_text("pages/proof_center.py")
    report_studio = _read_file_text("pages/report_studio.py")
    publisher_section = report_studio[report_studio.find("with tabs[10]:"):] if "with tabs[10]:" in report_studio else report_studio
    errors: list[str] = []
    if package_type in PRIVATE_PACKAGE_TYPES:
        if not package.get("private_export_hash"):
            errors.append("Private/internal package missing private_export_hash.")
        if not package.get("private_export_csv") and not package.get("private_export_json"):
            errors.append("Private/internal package missing private audit exports.")
    else:
        for field in ("private_export_hash", "private_export_csv", "private_export_json"):
            if package.get(field):
                errors.append(f"Public/client package exposes {field}.")
    if "private_package_confirmation" not in proof_center and "private_confirmation" not in proof_center:
        errors.append("Proof Center private/internal confirmation contract not found.")
    if 'REPORT_STUDIO_PUBLISHER_PACKAGE_TYPE_OPTIONS = ("public", "client")' not in report_studio:
        errors.append("Report Studio publisher package options are not limited to public/client.")
    for forbidden in ("internal_review", "private_export_csv", "private_export_json", "private_export_hash", "previous_row_hash", "correction_reason"):
        if forbidden in publisher_section:
            errors.append(f"Report Studio publisher section exposes private/internal token: {forbidden}")
    return _result(not errors, ["package", "pages/proof_center.py", "pages/report_studio.py"], errors=errors, details={"package_type": package_type})


def validate_report_publisher_payload_integrity(payload: Mapping[str, Any]) -> dict[str, Any]:
    package_type = str(payload.get("package_type") or "").strip().lower()
    if package_type not in SUPPORTED_PACKAGE_TYPES:
        return _unsupported(package_type)
    required = ("report_id", "package_id", "package_hash", "workspace_id", "package_type", "proof_grade", "proof_ready", "export_files", "verification_manifest")
    errors = [f"Missing required payload field: {field}" for field in required if field not in payload]
    export_files = payload.get("export_files") or {}
    try:
        json_content = ((export_files.get("json") or {}).get("content")) or "{}"
        parsed = json.loads(json_content)
        if parsed.get("package_id") != payload.get("package_id"):
            errors.append("Publisher JSON package_id does not match payload.")
        if parsed.get("package_hash") != payload.get("package_hash"):
            errors.append("Publisher JSON package_hash does not match payload.")
    except Exception as exc:
        errors.append(f"Publisher JSON export could not be parsed: {exc}")
    markdown_content = str(((export_files.get("markdown") or {}).get("content")) or "")
    for token in (str(payload.get("package_id") or ""), str(payload.get("proof_grade") or ""), "Performance Summary", "Disclaimer"):
        if token and token not in markdown_content:
            errors.append(f"Publisher Markdown missing token: {token}")
    csv_bundle = export_files.get("csv_bundle") or {}
    if not isinstance(csv_bundle, Mapping):
        errors.append("Publisher CSV bundle is not filename -> CSV mapping.")
        csv_bundle = {}
    for filename, csv_text in csv_bundle.items():
        ok, message = _csv_ok(str(filename), str(csv_text))
        if not ok:
            errors.append(f"Publisher CSV bundle member is not parseable: {message}")
    if package_type in PUBLIC_PACKAGE_TYPES and "public_package" not in payload:
        errors.append("Public/client publisher payload missing public_package.")
    if package_type in PRIVATE_PACKAGE_TYPES and "private_package" not in payload:
        errors.append("Private/internal publisher payload missing private_package.")
    for pick in (payload.get("top_positive_ev_summary") or {}).get("picks") or []:
        lane = str(pick.get("report_lane") or pick.get("status") or "").lower()
        if "watch" in lane or "avoid" in lane:
            errors.append("Publisher Top +EV summary contains watchlist/avoid pick.")
    return _result(not errors, ["payload", "export_files", "top_positive_ev_summary"], errors=errors, details={"package_type": package_type})


def validate_package_hash_stability(package: Mapping[str, Any]) -> dict[str, Any]:
    package_type = _package_type(package)
    if package_type not in SUPPORTED_PACKAGE_TYPES:
        return _unsupported(package_type)
    errors: list[str] = []
    base_hash = build_package_hash(package)
    time_changed = dict(package)
    time_changed["generated_at_utc"] = "2099-01-01T00:00:00Z"
    time_hash = build_package_hash(time_changed)
    row_changed = copy.deepcopy(dict(package))
    row_changed["public_safe_rows"] = list(row_changed.get("public_safe_rows") or []) + [{"proof_id": "test_only_integrity_change", "row_hash": "test_only_hash"}]
    row_hash = build_package_hash(row_changed)
    type_changed = dict(package)
    type_changed["package_type"] = "client" if package_type != "client" else "public"
    type_hash = build_package_hash(type_changed)
    if package.get("package_hash") and base_hash != package.get("package_hash"):
        errors.append("Stored package_hash does not match rebuilt hash.")
    if base_hash != time_hash:
        errors.append("package_hash changed when only generated_at_utc changed.")
    if base_hash == row_hash:
        errors.append("package_hash did not change when public-safe rows changed.")
    if base_hash == type_hash:
        errors.append("package_hash did not change when package_type changed.")
    return _result(not errors, ["package_hash", "generated_at_utc", "public_safe_rows", "package_type"], errors=errors, details={"base_hash": base_hash, "time_hash": time_hash, "row_hash": row_hash, "type_hash": type_hash})


def validate_package_download_bundle(package: Mapping[str, Any]) -> dict[str, Any]:
    package_type = _package_type(package)
    if package_type not in SUPPORTED_PACKAGE_TYPES:
        return _unsupported(package_type)
    errors: list[str] = []
    try:
        bundle = export_proof_package_csv_bundle(package)
    except Exception as exc:
        return _result(False, ["csv_bundle"], errors=[f"CSV bundle export failed: {exc}"], details={})
    if not isinstance(bundle, Mapping):
        return _result(False, ["csv_bundle"], errors=["CSV bundle is not filename -> CSV string mapping."], details={})
    parse_results = {}
    for filename, csv_text in bundle.items():
        ok, message = _csv_ok(str(filename), str(csv_text))
        parse_results[str(filename)] = message
        if not ok:
            errors.append(f"CSV bundle member is not parseable: {message}")
    if package_type in PUBLIC_PACKAGE_TYPES:
        for filename in bundle:
            if "private" in str(filename).lower() or "audit" in str(filename).lower():
                errors.append("Public/client CSV bundle includes private audit file.")
    if package_type in PRIVATE_PACKAGE_TYPES and "private_audit_proof_rows.csv" not in bundle:
        errors.append("Private/internal CSV bundle missing private audit rows file.")
    source = Path("autonomous_betting_agent/proof_package_service.py").read_text(encoding="utf-8")
    for token in ("op" + "en(", ".wr" + "ite(", "wr" + "ite_text(", "wr" + "ite_bytes("):
        if token in source:
            errors.append(f"Potential file write token found in proof package service: {token}")
    return _result(not errors, ["csv_bundle", "proof_package_service.py"], errors=errors, details={"csv_parse_results": parse_results})


def validate_proof_grade_rules(package: Mapping[str, Any]) -> dict[str, Any]:
    package_type = _package_type(package)
    if package_type not in SUPPORTED_PACKAGE_TYPES:
        return _unsupported(package_type)
    errors: list[str] = []
    proof_grade = str(package.get("proof_grade") or "")
    selected_source = str(package.get("selected_source") or "")
    total_rows = int(package.get("total_rows") or 0)
    proof_ready = bool(package.get("proof_ready"))
    if proof_grade == PROOF_READY_GRADE and not package_is_proof_ready(package):
        errors.append("proof_grade overstates readiness.")
    if selected_source != "ledger" and proof_grade not in {PROVISIONAL_GRADE, EMPTY_GRADE}:
        errors.append("Fallback/session/upload package is not labeled provisional or empty.")
    if total_rows <= 0 and proof_grade != EMPTY_GRADE:
        errors.append("Empty package is not labeled EMPTY / NOT PROOF READY.")
    if package.get("ledger_integrity_status") != "PASS" and proof_ready:
        errors.append("ledger_integrity_status failure did not force proof_ready false.")
    if not package.get("dashboard_ready") and proof_ready:
        errors.append("dashboard_ready false did not force proof_ready false.")
    if package_type in PUBLIC_PACKAGE_TYPES and not (package.get("redaction_status") or {}).get("passed", False) and proof_ready:
        errors.append("Public/client redaction failure did not force proof_ready false.")
    return _result(not errors, ["proof_grade", "proof_ready", "selected_source", "ledger_integrity_status", "dashboard_ready"], errors=errors, details={"package_type": package_type})


def validate_top_positive_ev_safety(package: Mapping[str, Any]) -> dict[str, Any]:
    package_type = _package_type(package)
    if package_type not in SUPPORTED_PACKAGE_TYPES:
        return _unsupported(package_type)
    errors: list[str] = []
    picks = list(package.get("top_positive_ev_picks") or [])
    for idx, pick in enumerate(picks):
        lane = str(pick.get("report_lane") or pick.get("status") or pick.get("lane") or "").lower()
        try:
            ev = float(pick.get("expected_value", pick.get("ev", 0)) or 0)
        except (TypeError, ValueError):
            ev = 0.0
        if "watch" in lane or "avoid" in lane:
            errors.append(f"Top +EV pick {idx} contains watchlist/avoid lane.")
        if ev <= 0:
            errors.append(f"Top +EV pick {idx} is not positive EV.")
    if not picks:
        message = str(package.get("top_positive_ev_message") or "")
        if message and "No playable positive-EV picks available" not in message:
            errors.append("Empty Top +EV state is not honest.")
    return _result(not errors, ["top_positive_ev_picks"], errors=errors, details={"pick_count": len(picks)})


def _no_write_paths_detected() -> dict[str, Any]:
    source = Path("autonomous_betting_agent/proof_package_integrity_service.py").read_text(encoding="utf-8")
    found = [token for token in WRITE_MUTATION_TOKENS if token in source]
    return _result(not found, ["proof_package_integrity_service.py"], errors=[f"Write/mutation token found: {token}" for token in found], details={"found_tokens": found})


def _stale_preview_contract() -> dict[str, Any]:
    proof_center = _read_file_text("pages/proof_center.py")
    report_studio = _read_file_text("pages/report_studio.py")
    errors: list[str] = []
    for token in ("proof_center_package_fingerprint", "package_input_fingerprint", "proof_center_package_json_{package_hash}", "proof_center_package_markdown_{package_hash}", "proof_center_package_csv_{package_hash}_{filename}", "private_package_confirmation", "redaction_failed", "stale_package"):
        if token not in proof_center:
            errors.append(f"Proof Center missing stale/download contract token: {token}")
    for token in ("report_publisher_input_fingerprint", "publisher_input_fingerprint", "report_studio_publisher_json_{package_hash}", "report_studio_publisher_markdown_{package_hash}", "report_studio_publisher_csv_{package_hash}_{filename}", 'REPORT_STUDIO_PUBLISHER_PACKAGE_TYPE_OPTIONS = ("public", "client")', "redaction_failed", "stale_publisher"):
        if token not in report_studio:
            errors.append(f"Report Studio missing stale/download contract token: {token}")
    publisher_section = report_studio[report_studio.find("with tabs[10]:"):] if "with tabs[10]:" in report_studio else report_studio
    for forbidden in ("internal_review", "private_export_csv", "private_export_json", "private_export_hash"):
        if forbidden in publisher_section:
            errors.append(f"Report Studio publisher exposes private token: {forbidden}")
    return _result(not errors, ["pages/proof_center.py", "pages/report_studio.py"], errors=errors, details={})


def _qa_report_hash(report: Mapping[str, Any]) -> str:
    stable = {key: value for key, value in dict(report).items() if key not in {"generated_at_utc", "qa_report_hash"}}
    return _hash_text("qa_hash", _canonical_dumps(stable), length=32)


def build_proof_package_qa_report(workspace_id: str | None = None, package_type: str = "public") -> dict[str, Any]:
    selected_type = str(package_type or "public").strip().lower()
    if selected_type not in PACKAGE_BUILDERS:
        report = {
            "qa_report_id": _hash_text("qa", f"{workspace_id or 'default'}|{selected_type}|unsupported", length=24),
            "qa_report_hash": "",
            "generated_at_utc": _utc_now(),
            "workspace_id": workspace_id or "default",
            "package_type": selected_type,
            "package_id": "",
            "package_hash": "",
            "public_export_hash": "",
            "proof_ready": False,
            "proof_grade": EMPTY_GRADE,
            "selected_source": "empty",
            "ledger_backed": False,
            "ledger_integrity_status": "UNKNOWN",
            "dashboard_ready": False,
            "export_integrity_passed": False,
            "redaction_passed": False,
            "public_client_safety_passed": False,
            "private_internal_isolation_passed": False,
            "report_publisher_integrity_passed": False,
            "hash_stability_passed": False,
            "proof_grade_rules_passed": False,
            "top_positive_ev_safety_passed": False,
            "download_bundle_passed": False,
            "stale_preview_contract_passed": False,
            "no_write_paths_detected": False,
            "checked_outputs": ["package_type"],
            "warnings": [],
            "errors": [f"Unsupported package_type: {selected_type}"],
            "overall_passed": False,
        }
        report["qa_report_hash"] = _qa_report_hash(report)
        return report
    package = PACKAGE_BUILDERS[selected_type](workspace_id)
    payload = build_report_publisher_payload(workspace_id, package_type=selected_type)
    validations = {
        "export_integrity": validate_package_export_integrity(package),
        "public_client_safety": validate_public_client_package_safety(package),
        "private_internal_isolation": validate_private_internal_package_isolation(package),
        "report_publisher_integrity": validate_report_publisher_payload_integrity(payload),
        "hash_stability": validate_package_hash_stability(package),
        "proof_grade_rules": validate_proof_grade_rules(package),
        "top_positive_ev_safety": validate_top_positive_ev_safety(package),
        "download_bundle": validate_package_download_bundle(package),
        "stale_preview_contract": _stale_preview_contract(),
        "no_write_paths": _no_write_paths_detected(),
    }
    warnings: list[str] = []
    errors: list[str] = []
    checked_outputs: list[str] = []
    for name, result in validations.items():
        checked_outputs.append(name)
        checked_outputs.extend(result.get("checked_outputs", []))
        warnings.extend(result.get("warnings", []))
        errors.extend(result.get("errors", []))
    redaction_status = package.get("redaction_status") or {}
    report = {
        "qa_report_id": _hash_text("qa", f"{package.get('workspace_id', 'default')}|{selected_type}|{package.get('package_hash', '')}", length=24),
        "qa_report_hash": "",
        "generated_at_utc": _utc_now(),
        "workspace_id": package.get("workspace_id", workspace_id or "default"),
        "package_type": selected_type,
        "package_id": package.get("package_id", ""),
        "package_hash": package.get("package_hash", ""),
        "public_export_hash": package.get("public_export_hash", ""),
        "proof_ready": package.get("proof_ready", False),
        "proof_grade": package.get("proof_grade", ""),
        "selected_source": package.get("selected_source", ""),
        "ledger_backed": package.get("ledger_backed", False),
        "ledger_integrity_status": package.get("ledger_integrity_status", ""),
        "dashboard_ready": package.get("dashboard_ready", False),
        "export_integrity_passed": validations["export_integrity"]["passed"],
        "redaction_passed": bool(redaction_status.get("passed", selected_type in PRIVATE_PACKAGE_TYPES)),
        "public_client_safety_passed": validations["public_client_safety"]["passed"],
        "private_internal_isolation_passed": validations["private_internal_isolation"]["passed"],
        "report_publisher_integrity_passed": validations["report_publisher_integrity"]["passed"],
        "hash_stability_passed": validations["hash_stability"]["passed"],
        "proof_grade_rules_passed": validations["proof_grade_rules"]["passed"],
        "top_positive_ev_safety_passed": validations["top_positive_ev_safety"]["passed"],
        "download_bundle_passed": validations["download_bundle"]["passed"],
        "stale_preview_contract_passed": validations["stale_preview_contract"]["passed"],
        "no_write_paths_detected": validations["no_write_paths"]["passed"],
        "checked_outputs": sorted(set(checked_outputs)),
        "warnings": warnings,
        "errors": errors,
        "overall_passed": not errors and all(result["passed"] for result in validations.values()),
        "validation_results": validations,
    }
    if package.get("private_export_hash"):
        report["private_export_hash"] = package.get("private_export_hash")
    report["qa_report_hash"] = _qa_report_hash(report)
    return report


def run_e2e_proof_package_checks(workspace_id: str | None = None) -> dict[str, Any]:
    package_type_results = {package_type: build_proof_package_qa_report(workspace_id, package_type=package_type) for package_type in ("public", "client", "private", "internal_review")}
    warnings: list[str] = []
    errors: list[str] = []
    for result in package_type_results.values():
        warnings.extend(result.get("warnings", []))
        errors.extend(result.get("errors", []))
    return {"overall_passed": not errors and all(result.get("overall_passed") for result in package_type_results.values()), "package_type_results": package_type_results, "warnings": warnings, "errors": errors}
