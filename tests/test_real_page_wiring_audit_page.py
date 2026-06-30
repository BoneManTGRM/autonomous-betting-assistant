import ast
from pathlib import Path

PAGE = Path("pages/real_page_wiring_audit.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_real_page_wiring_page_imports_services():
    for token in (
        "build_real_page_wiring_audit_from_text",
        "export_wiring_audit_json",
        "export_wiring_page_summary_csv",
        "export_wiring_risk_summary_csv",
        "export_wiring_checks_csv",
        "export_wiring_manifest_json",
    ):
        assert token in SOURCE


def test_real_page_wiring_page_exposes_controls():
    for token in (
        "real_page_wiring_workspace_id",
        "real_page_wiring_inventory_csv",
        "real_page_wiring_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_real_page_wiring_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "wiring_id",
        "wiring_hash",
        "mode",
        "system_status",
        "page_count",
        "wired_count",
        "partial_count",
        "review_required_count",
        "blocked_count",
        "pass_count",
        "warn_count",
        "fail_count",
        "system_checks",
        "page_results",
        "risk_summary",
        "next_actions",
        "safety_gates",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_real_page_wiring_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "page_inventory_csv",
        "run",
        "summary",
        "checks",
        "pages",
        "risks",
        "actions",
        "safety",
        "download_json",
        "download_pages",
        "download_risks",
        "download_checks",
        "download_manifest",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_real_page_wiring_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
