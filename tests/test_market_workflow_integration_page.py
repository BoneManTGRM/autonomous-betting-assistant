import ast
from pathlib import Path

PAGE = Path("pages/market_workflow_integration.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_market_workflow_page_imports_services():
    for token in (
        "build_market_workflow_integration_from_text",
        "export_workflow_integration_json",
        "export_flow_steps_csv",
        "export_step_status_csv",
        "export_workflow_checks_csv",
        "export_handoff_manifest_json",
        "export_workflow_manifest_json",
    ):
        assert token in SOURCE


def test_market_workflow_page_exposes_controls():
    for token in (
        "market_workflow_workspace_id",
        "market_workflow_optimizer_json",
        "market_workflow_bridge_json",
        "market_workflow_sidebar_text",
        "market_workflow_page_inventory_csv",
        "market_workflow_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_market_workflow_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "workflow_id",
        "workflow_hash",
        "mode",
        "workflow_status",
        "optimizer_hash",
        "bridge_hash",
        "tracking_row_count",
        "handoff_row_count",
        "flow_steps",
        "step_status_rows",
        "workflow_checks",
        "next_actions",
        "handoff_manifest",
        "safety_gates",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_market_workflow_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "optimizer_json",
        "bridge_json",
        "sidebar_text",
        "page_inventory_csv",
        "run",
        "summary",
        "steps",
        "step_status",
        "checks",
        "actions",
        "handoff",
        "safety",
        "download_json",
        "download_steps",
        "download_status",
        "download_checks",
        "download_handoff",
        "download_manifest",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_market_workflow_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
