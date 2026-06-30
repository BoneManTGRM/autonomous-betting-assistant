import ast
from pathlib import Path

PAGE = Path("pages/subscriber_intelligence.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_subscriber_page_imports_services():
    for token in (
        "build_subscriber_intelligence_from_text",
        "export_subscriber_intelligence_json",
        "export_profiles_csv",
        "export_personalized_rows_csv",
        "export_subscriber_reports_json",
        "export_admin_summary_json",
        "export_subscriber_checks_csv",
        "export_subscriber_manifest_json",
    ):
        assert token in SOURCE


def test_subscriber_page_exposes_controls():
    for token in (
        "subscriber_intelligence_workspace_id",
        "subscriber_intelligence_profiles_csv",
        "subscriber_intelligence_optimizer_json",
        "subscriber_intelligence_market_csv",
        "subscriber_intelligence_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_subscriber_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "subscriber_run_id",
        "subscriber_hash",
        "mode",
        "subscriber_status",
        "subscriber_count",
        "enabled_subscriber_count",
        "market_row_count",
        "admin_summary",
        "profiles",
        "personalized_rows",
        "subscriber_reports",
        "subscriber_checks",
        "safety_gates",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_subscriber_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "profiles_csv",
        "optimizer_json",
        "market_csv",
        "run",
        "summary",
        "admin",
        "profiles",
        "rows",
        "reports",
        "checks",
        "safety",
        "download_json",
        "download_profiles",
        "download_rows",
        "download_reports",
        "download_admin",
        "download_checks",
        "download_manifest",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_subscriber_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
