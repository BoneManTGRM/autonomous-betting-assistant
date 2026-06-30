import ast
from pathlib import Path

PAGE = Path("pages/subscriber_ledger.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_subscriber_ledger_page_imports_services():
    for token in (
        "build_subscriber_ledger_reports_from_text",
        "export_subscriber_ledger_json",
        "export_ledger_rows_csv",
        "export_subscriber_summaries_csv",
        "export_sport_performance_csv",
        "export_market_type_performance_csv",
        "export_sportsbook_performance_csv",
        "export_mistake_patterns_csv",
        "export_ledger_checks_csv",
        "export_ledger_manifest_json",
    ):
        assert token in SOURCE


def test_subscriber_ledger_page_exposes_controls():
    for token in (
        "subscriber_ledger_workspace_id",
        "subscriber_ledger_csv",
        "subscriber_ledger_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_subscriber_ledger_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "ledger_run_id",
        "ledger_hash",
        "mode",
        "ledger_status",
        "ledger_row_count",
        "subscriber_count",
        "unique_event_count",
        "global_summary",
        "subscriber_summaries",
        "ledger_rows",
        "sport_performance",
        "market_type_performance",
        "sportsbook_performance",
        "mistake_patterns",
        "ledger_checks",
        "safety_gates",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_subscriber_ledger_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "ledger_csv",
        "run",
        "summary",
        "global",
        "subs",
        "rows",
        "sports",
        "markets",
        "books",
        "patterns",
        "checks",
        "safety",
        "download_json",
        "download_rows",
        "download_subs",
        "download_sports",
        "download_markets",
        "download_books",
        "download_patterns",
        "download_checks",
        "download_manifest",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_subscriber_ledger_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
