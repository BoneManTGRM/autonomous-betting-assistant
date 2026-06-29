import copy
import json

from autonomous_betting_agent import proof_package_integrity_service as integrity
from autonomous_betting_agent.proof_package_service import PROOF_READY_GRADE, build_export_hash, build_package_hash, export_proof_package_csv_bundle, export_proof_package_json, export_proof_package_markdown


def test_only_package(package_type="public"):
    public_csv = "proof_id,event,pick,report_lane,expected_value\nproof-alpha,Alpha vs Beta,Alpha ML,playable,0.20\n"
    public_json = json.dumps({"rows": [{"proof_id": "proof-alpha", "event": "Alpha vs Beta"}]}, sort_keys=True)
    package = {
        "package_id": f"pkg_test_01_{package_type}_fixture",
        "package_schema_version": "test-only-fixture",
        "package_hash": "",
        "public_export_hash": build_export_hash(public_csv, public_json),
        "generated_at_utc": "2026-06-29T12:00:00Z",
        "workspace_id": "test_01",
        "package_type": package_type,
        "proof_grade": PROOF_READY_GRADE,
        "proof_ready": True,
        "ledger_backed": True,
        "selected_source": "ledger",
        "ledger_integrity_status": "PASS",
        "dashboard_ready": True,
        "total_rows": 1,
        "unique_events": 1,
        "wins": 1,
        "losses": 0,
        "pushes": 0,
        "cancels": 0,
        "public_safe_rows": [{"proof_id": "proof-alpha", "event": "Alpha vs Beta", "report_lane": "playable", "expected_value": 0.20}],
        "top_positive_ev_picks": [{"event": "Alpha vs Beta", "pick": "Alpha ML", "report_lane": "playable", "expected_value": 0.20}],
        "top_positive_ev_message": "",
        "source_disclaimer": "Ledger-backed metrics are proof-grade only when proof_ready=true.",
        "redaction_status": {"passed": True, "blocked_terms_found": [], "blocked_paths_found": [], "checked_outputs": ["json", "markdown", "csv_bundle"], "warnings": [], "errors": []},
        "verification_manifest": {},
        "warnings": [],
        "errors": [],
        "public_export_csv": public_csv,
        "public_export_json": public_json,
    }
    if package_type in {"private", "internal_review"}:
        package["private_export_csv"] = "source_file,event\naudit.csv,Alpha vs Beta\n"
        package["private_export_json"] = json.dumps({"rows": [{"source_file": "audit.csv"}]}, sort_keys=True)
        package["private_export_hash"] = build_export_hash(package["private_export_csv"], package["private_export_json"])
    package["package_hash"] = build_package_hash(package)
    return package


def publisher_payload(package):
    export_files = {
        "json": {"filename": "test.json", "content": export_proof_package_json(package)},
        "markdown": {"filename": "test.md", "content": export_proof_package_markdown(package)},
        "csv_bundle": export_proof_package_csv_bundle(package),
    }
    payload = {
        "report_id": f"report_{package['package_type']}_fixture",
        "package_id": package["package_id"],
        "package_hash": package["package_hash"],
        "generated_at_utc": package["generated_at_utc"],
        "workspace_id": package["workspace_id"],
        "package_type": package["package_type"],
        "proof_grade": package["proof_grade"],
        "proof_ready": package["proof_ready"],
        "ledger_backed": package["ledger_backed"],
        "headline_summary": "ABA Signal Pro proof package is ledger-backed and proof-ready.",
        "performance_summary": {"proof_ready": package["proof_ready"], "total_rows": 1},
        "proof_summary": {"total_rows": 1},
        "roi_summary": {"ROI": 1.10},
        "clv_summary": {"average_CLV": 0.02},
        "risk_summary": {"ledger_integrity_status": "PASS"},
        "top_positive_ev_summary": {"count": 1, "message": "1 playable positive-EV picks available.", "picks": package["top_positive_ev_picks"]},
        "proof_disclaimer": "This package is ledger-backed proof-ready based on the current proof ledger and redaction validation.",
        "verification_manifest": {"package_hash": package["package_hash"], "public_export_hash": package["public_export_hash"]},
        "export_files": export_files,
    }
    if package["package_type"] in {"public", "client"}:
        payload["public_package"] = package
    else:
        payload["private_package"] = package
    return payload


def patch_builders(monkeypatch):
    packages = {package_type: test_only_package(package_type) for package_type in ("public", "client", "private", "internal_review")}
    monkeypatch.setattr(integrity, "PACKAGE_BUILDERS", {package_type: (lambda workspace_id=None, package=package: package) for package_type, package in packages.items()})
    monkeypatch.setattr(integrity, "build_report_publisher_payload", lambda workspace_id=None, package_type="public": publisher_payload(packages[package_type]))
    return packages


def test_build_proof_package_qa_report_checks_only_selected_package_type(monkeypatch):
    packages = patch_builders(monkeypatch)

    report = integrity.build_proof_package_qa_report("test_01", package_type="client")

    assert report["package_type"] == "client"
    assert report["package_id"] == packages["client"]["package_id"]
    assert report["overall_passed"] is True, report["errors"]
    assert report["export_integrity_passed"] is True
    assert report["public_client_safety_passed"] is True
    assert report["report_publisher_integrity_passed"] is True
    assert report["stale_preview_contract_passed"] is True
    assert report["no_write_paths_detected"] is True
    assert report["qa_report_hash"].startswith("qa_hash_")


def test_run_e2e_proof_package_checks_checks_all_package_types(monkeypatch):
    patch_builders(monkeypatch)

    result = integrity.run_e2e_proof_package_checks("test_01")

    assert set(result["package_type_results"]) == {"public", "client", "private", "internal_review"}
    assert result["overall_passed"] is True, result["errors"]


def test_unsupported_package_type_fails_closed():
    report = integrity.build_proof_package_qa_report("test_01", package_type="bad")

    assert report["overall_passed"] is False
    assert report["package_type"] == "bad"
    assert report["qa_report_hash"].startswith("qa_hash_")
    assert any("Unsupported package_type" in error for error in report["errors"])


def test_qa_report_hash_is_stable_without_generated_at_and_changes_with_validation_results(monkeypatch):
    patch_builders(monkeypatch)
    report = integrity.build_proof_package_qa_report("test_01", package_type="public")
    changed_time = dict(report)
    changed_time["generated_at_utc"] = "2099-01-01T00:00:00Z"
    stable_hash = integrity._qa_report_hash(report)

    assert stable_hash == integrity._qa_report_hash(changed_time)

    changed_result = copy.deepcopy(report)
    changed_result["validation_results"]["export_integrity"]["passed"] = False
    assert stable_hash != integrity._qa_report_hash(changed_result)


def test_report_publisher_payload_integrity_validates_exports_and_top_ev():
    package = test_only_package("public")
    payload = publisher_payload(package)

    result = integrity.validate_report_publisher_payload_integrity(payload)

    assert result["passed"], result["errors"]

    bad = copy.deepcopy(payload)
    bad["top_positive_ev_summary"]["picks"] = [{"event": "Bad", "report_lane": "avoid", "expected_value": 0.20}]
    assert integrity.validate_report_publisher_payload_integrity(bad)["passed"] is False
