import ast
from pathlib import Path

PAGE = Path("pages/dashboard_refresh_package.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_dashboard_page_imports_services():
    for token in (
        "build_dashboard_refresh_package_from_text",
        "export_dashboard_refresh_json",
        "export_dashboard_summary_csv",
        "export_dashboard_rows_csv",
        "export_event_breakdown_csv",
        "export_duplicate_groups_csv",
        "export_segment_breakdown_csv",
        "export_blocker_breakdown_csv",
        "export_dashboard_manifest_json",
    ):
        assert token in SOURCE


def test_dashboard_page_exposes_controls():
    for token in (
        "dashboard_refresh_workspace_id",
        "dashboard_refresh_proof_csv",
        "dashboard_refresh_history_csv",
        "dashboard_refresh_decision_csv",
        "dashboard_refresh_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_dashboard_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "dashboard_refresh_id",
        "dashboard_refresh_hash",
        "status",
        "review_reasons",
        "source_row_count",
        "history_row_count",
        "decision_row_count",
        "unique_event_count",
        "duplicate_event_group_count",
        "completed_count",
        "pending_count",
        "wins",
        "losses",
        "pushes",
        "cancels",
        "win_rate_ex_push_cancel",
        "total_profit_units",
        "stake_units",
        "roi",
        "average_CLV_decimal_delta",
        "average_baseline_EV",
        "average_calibrated_EV",
        "dashboard_rows",
        "action_breakdown",
        "blocker_breakdown",
        "event_breakdown",
        "duplicate_event_groups",
        "segment_breakdown",
        "manifest",
        "safety_gates",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_dashboard_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "proof_csv",
        "history_csv",
        "decision_csv",
        "run",
        "summary",
        "rows",
        "actions",
        "blockers",
        "events",
        "duplicates",
        "segments",
        "manifest",
        "safety",
        "download_json",
        "download_summary",
        "download_rows",
        "download_events",
        "download_duplicates",
        "download_segments",
        "download_blockers",
        "download_manifest",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_dashboard_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
