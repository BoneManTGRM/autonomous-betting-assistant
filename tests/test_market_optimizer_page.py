import ast
from pathlib import Path

PAGE = Path("pages/market_optimizer.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_market_optimizer_page_imports_services():
    for token in (
        "build_market_optimizer_preview_from_text",
        "export_market_optimizer_json",
        "export_market_hunter_csv",
        "export_best_books_csv",
        "export_chain_builder_csv",
        "export_avoid_list_csv",
        "export_marco_mode_json",
        "export_market_optimizer_manifest_json",
    ):
        assert token in SOURCE


def test_market_optimizer_page_exposes_controls():
    for token in (
        "market_optimizer_workspace_id",
        "market_optimizer_bankroll",
        "market_optimizer_market_csv",
        "market_optimizer_history_csv",
        "market_optimizer_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_market_optimizer_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "optimizer_id",
        "optimizer_hash",
        "mode",
        "market_row_count",
        "history_row_count",
        "playable_count",
        "watch_count",
        "wait_count",
        "no_play_count",
        "market_hunter_rows",
        "best_book_rows",
        "chain_builder_rows",
        "avoid_list",
        "marco_mode",
        "safety_gates",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_market_optimizer_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "bankroll",
        "market_csv",
        "history_csv",
        "run",
        "summary",
        "hunter",
        "books",
        "chains",
        "avoid",
        "marco",
        "safety",
        "download_json",
        "download_hunter",
        "download_books",
        "download_chains",
        "download_avoid",
        "download_marco",
        "download_manifest",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_market_optimizer_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
