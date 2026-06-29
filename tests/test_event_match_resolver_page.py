import ast
from pathlib import Path

PAGE = Path("pages/event_match_resolver.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def test_event_match_page_imports_services():
    for token in ("build_event_match_report_from_text", "export_event_match_report_json"):
        assert token in SOURCE


def test_event_match_page_exposes_controls():
    for token in (
        "event_match_workspace_id",
        "event_match_threshold",
        "event_review_threshold",
        "event_match_locked_csv",
        "event_match_provider_json",
        "event_match_run",
        "st.download_button",
    ):
        assert token in SOURCE


def test_event_match_page_displays_required_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "status",
        "locked_row_count",
        "provider_event_count",
        "matched_count",
        "low_confidence_count",
        "no_match_count",
        "duplicate_match_count",
        "manual_review_count",
        "match_threshold",
        "review_threshold",
        "preview_only",
        "proof_rows_changed",
        "match_rows",
        "top_candidates",
    ):
        assert token in SOURCE


def test_event_match_page_has_status_language():
    for token in ("MATCHED", "LOW CONFIDENCE", "NO MATCH", "DUPLICATE MATCH", "MANUAL REVIEW", "PREVIEW ONLY", "NO PROOF ROWS CHANGED"):
        assert token in SOURCE


def test_event_match_page_text_keys_exist():
    text = _assignment_value("TEXT")
    required = {
        "title",
        "caption",
        "workspace_id",
        "locked_csv",
        "provider_json",
        "match_threshold",
        "review_threshold",
        "run",
        "matched",
        "low",
        "none",
        "duplicate",
        "manual",
        "preview_only",
        "proof_safe",
        "summary",
        "rows",
        "candidates",
        "download",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_event_match_page_uses_preview_only_contract():
    assert "proof_rows_changed" in SOURCE
    assert "preview_only" in SOURCE
    assert "safe_text(report.get('status'))" in SOURCE


def test_event_match_page_has_no_external_client_paths():
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in SOURCE
