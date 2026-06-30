import json

from autonomous_betting_agent import proof_hardening_closeout as closeout


def _canonical():
    return {
        "schema_version": "canonical_store_recovery_v1",
        "recovery_status": "CANONICAL RECOVERY SAFE",
        "resolved_store_name": "canonical_store",
        "resolved_row_count": 2,
        "save_reload_verification": {"row_count_match": True},
        "duplicate_proof_id_groups": [],
        "workspace_mismatches": [],
        "safety_gates": {"live_mutation": "FORBIDDEN", "model_training": "FORBIDDEN", "stored_data_mutation": "FORBIDDEN", "automatic_live_promotion": "FORBIDDEN", "proof_overwrite": "FORBIDDEN"},
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "recovery_hash": "rh",
    }


def _restart():
    return {
        "schema_version": "restart_regression_package_v1",
        "restart_status": "RESTART SAFE",
        "restart_checks": [{"check_id": "save_reload", "status": "PASS"}],
        "safety_gates": {"live_mutation": "FORBIDDEN", "model_training": "FORBIDDEN"},
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "restart_hash": "sh",
    }


def _readonly():
    return {
        "schema_version": "proof_ledger_readonly_audit_v1",
        "audit_status": "READ ONLY SAFE",
        "audit_checks": [{"check_id": "workspace", "status": "PASS"}, {"check_id": "duplicate", "status": "PASS"}],
        "safety_gates": {"proof_mutation": "FORBIDDEN", "live_mutation": "FORBIDDEN"},
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "audit_hash": "ah",
    }


def _wiring():
    return {
        "schema_version": "real_page_wiring_audit_v1",
        "system_status": "CANONICAL WIRING READY",
        "page_results": [],
        "system_checks": [],
        "safety_gates": {"proof_mutation": "FORBIDDEN", "automatic_live_promotion": "FORBIDDEN"},
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "wiring_hash": "wh",
    }


def _dashboard():
    return {
        "schema_version": "dashboard_refresh_package_v1",
        "dashboard_status": "DASHBOARD READY",
        "dashboard_cards": {"row_count": 2},
        "safety_gates": {"automatic_proof_change": "FORBIDDEN"},
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "dashboard_hash": "dh",
    }


def _local_review():
    return {
        "schema_version": "local_review_checklist_v1",
        "readiness_status": "READY TO REVIEW",
        "checklist_rows": [],
        "safety_gates": {"automatic_model_change": "FORBIDDEN"},
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "checklist_hash": "lh",
    }


def _all_evidence():
    return {
        "canonical_recovery": _canonical(),
        "restart_regression": _restart(),
        "readonly_audit": _readonly(),
        "page_wiring": _wiring(),
        "dashboard_refresh": _dashboard(),
        "local_review": _local_review(),
    }


def test_closeout_ready_when_all_evidence_and_acknowledged():
    report = closeout.build_proof_hardening_closeout("test_01", **_all_evidence(), operator_acknowledged=True)

    assert report["schema_version"] == "proof_hardening_closeout_v1"
    assert report["closeout_status"] == "READY TO CLOSE"
    assert report["issue_21_recommendation"] == "READY TO CLOSE"
    assert report["fail_count"] == 0
    assert report["preview_only"] is True
    assert report["files_written"] == 0
    assert report["live_changes"] == 0


def test_closeout_keeps_open_without_operator_acknowledgment():
    report = closeout.build_proof_hardening_closeout("test_01", **_all_evidence(), operator_acknowledged=False)

    assert report["closeout_status"] == "REVIEW REQUIRED"
    assert report["issue_21_recommendation"] == "KEEP OPEN"
    assert any("acknowledgment" in action.lower() for action in report["next_actions"])


def test_closeout_blocks_missing_required_evidence():
    evidence = _all_evidence()
    evidence["restart_regression"] = {}
    report = closeout.build_proof_hardening_closeout("test_01", **evidence, operator_acknowledged=True)

    assert report["closeout_status"] == "BLOCKED"
    assert report["issue_21_recommendation"] == "KEEP OPEN"
    assert any(row["check_id"] == "evidence_restart_regression" and row["status"] == "FAIL" for row in report["closeout_checks"])


def test_closeout_blocks_unsafe_live_changes():
    evidence = _all_evidence()
    evidence["canonical_recovery"] = dict(evidence["canonical_recovery"], live_changes=1)
    report = closeout.build_proof_hardening_closeout("test_01", **evidence, operator_acknowledged=True)

    assert report["closeout_status"] == "BLOCKED"
    assert any(row["check_id"] == "no_live_changes_canonical_recovery" and row["status"] == "FAIL" for row in report["closeout_checks"])


def test_closeout_from_text_and_exports():
    evidence = _all_evidence()
    report = closeout.build_proof_hardening_closeout_from_text(
        "test_01",
        json.dumps(evidence["canonical_recovery"]),
        json.dumps(evidence["restart_regression"]),
        json.dumps(evidence["readonly_audit"]),
        json.dumps(evidence["page_wiring"]),
        json.dumps(evidence["dashboard_refresh"]),
        json.dumps(evidence["local_review"]),
        True,
    )
    payload = json.loads(closeout.export_closeout_json(report))

    assert payload["closeout_status"] == "READY TO CLOSE"
    assert "check_id" in closeout.export_closeout_checks_csv(report)
    assert "evidence_id" in closeout.export_evidence_summary_csv(report)
    assert "closeout_hash" in closeout.export_closeout_manifest_json(report)


def test_proof_hardening_closeout_has_no_external_client_paths():
    source = open("autonomous_betting_agent/proof_hardening_closeout.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
