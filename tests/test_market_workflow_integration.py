import json

from autonomous_betting_agent import market_workflow_integration as flow


def _optimizer_report():
    return {
        "workspace_id": "test_01",
        "preview_only": True,
        "optimizer_hash": "optimizer_abc",
        "market_hunter_rows": [{"event_id": "e1", "final_action": "PLAYABLE VALUE"}],
    }


def _bridge_report():
    return {
        "workspace_id": "test_01",
        "preview_only": True,
        "bridge_status": "DASHBOARD READY",
        "bridge_hash": "bridge_abc",
        "tracking_rows": [{"tracking_id": "t1", "event_id": "e1"}],
        "proof_handoff_rows": [{"tracking_id": "t1", "handoff_status": "READY FOR OPERATOR REVIEW"}],
    }


def _sidebar_text():
    return " ".join(flow.REQUIRED_NAV_PATHS)


def test_navigation_checks_pass_with_required_paths():
    checks = flow.navigation_checks(_sidebar_text(), [])

    assert checks
    assert all(row["status"] == "PASS" for row in checks)


def test_navigation_checks_warn_when_path_missing():
    checks = flow.navigation_checks("pages/market_optimizer.py", [])

    assert any(row["status"] == "WARN" for row in checks)


def test_optimizer_checks_require_preview_and_rows():
    checks = flow.optimizer_checks(_optimizer_report())

    assert all(row["status"] in {"PASS", "WARN"} for row in checks)
    assert not any(row["status"] == "FAIL" for row in checks)


def test_bridge_checks_require_tracking_and_handoff():
    checks = flow.bridge_checks(_bridge_report())

    assert all(row["status"] in {"PASS", "WARN"} for row in checks)
    assert not any(row["status"] == "FAIL" for row in checks)


def test_build_market_workflow_integration_ready():
    report = flow.build_market_workflow_integration("test_01", _optimizer_report(), _bridge_report(), _sidebar_text(), [])

    assert report["schema_version"] == "market_workflow_integration_v1"
    assert report["workflow_status"] == "WORKFLOW READY"
    assert report["tracking_row_count"] == 1
    assert report["handoff_row_count"] == 1
    assert report["handoff_manifest"]["operator_review_required"] is True
    assert report["handoff_manifest"]["source_update_allowed"] is False
    assert report["preview_only"] is True
    assert report["files_written"] == 0
    assert report["live_changes"] == 0


def test_build_market_workflow_integration_blocks_missing_reports():
    report = flow.build_market_workflow_integration("test_01", {}, {}, "", [])

    assert report["workflow_status"] == "BLOCKED"
    assert any(row["status"] == "FAIL" for row in report["workflow_checks"])


def test_build_market_workflow_integration_from_text_exports():
    report = flow.build_market_workflow_integration_from_text("test_01", json.dumps(_optimizer_report()), json.dumps(_bridge_report()), _sidebar_text(), "")
    payload = json.loads(flow.export_workflow_integration_json(report))

    assert payload["workflow_status"] == "WORKFLOW READY"
    assert "check_id" in flow.export_workflow_checks_csv(report)
    assert "step_id" in flow.export_step_status_csv(report)
    assert "path" in flow.export_flow_steps_csv(report)
    assert "operator_review_required" in flow.export_handoff_manifest_json(report)
    assert "workflow_hash" in flow.export_workflow_manifest_json(report)


def test_market_workflow_integration_has_no_external_client_paths():
    source = open("autonomous_betting_agent/market_workflow_integration.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
