import ast
from pathlib import Path

PAGE = Path("pages/pro_recommendation_cards.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_pro_cards_page_imports_services():
    for token in (
        "build_pro_recommendation_cards_from_text",
        "export_recommendation_cards_json",
        "export_recommendation_cards_csv",
        "export_marco_cards_json",
        "export_completion_checks_csv",
        "export_recommendation_manifest_json",
    ):
        assert token in SOURCE


def test_pro_cards_page_exposes_controls():
    for token in (
        "pro_cards_workspace_id",
        "pro_cards_optimizer_json",
        "pro_cards_market_csv",
        "pro_cards_chain_csv",
        "pro_cards_context_csv",
        "pro_cards_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_pro_cards_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "cards_id",
        "cards_hash",
        "mode",
        "cards_status",
        "card_count",
        "bet_count",
        "watch_count",
        "avoid_count",
        "recommendation_cards",
        "marco_cards",
        "completion_checks",
        "safety_gates",
        "preview_only",
        "files_written",
        "live_changes",
    ):
        assert token in SOURCE


def test_pro_cards_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "optimizer_json",
        "market_csv",
        "chain_csv",
        "context_csv",
        "run",
        "summary",
        "cards",
        "marco",
        "checks",
        "safety",
        "download_json",
        "download_csv",
        "download_marco",
        "download_checks",
        "download_manifest",
        "preview_only",
        "no_files",
        "no_live",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_pro_cards_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
