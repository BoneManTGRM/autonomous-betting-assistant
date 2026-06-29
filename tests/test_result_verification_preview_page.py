import ast
from pathlib import Path

PAGE = Path("pages/result_verification_preview.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def _text_dict():
    return _assignment_value("TEXT")


def test_result_verification_preview_page_imports_read_only_services():
    for token in (
        "build_verification_preview_report",
        "export_verification_preview_report_json",
        "validate_verification_preview_report",
    ):
        assert token in SOURCE


def test_result_verification_preview_page_exposes_controls():
    for token in (
        "verification_workspace_id",
        "verification_sport",
        "verification_event",
        "verification_market_type",
        "verification_pick",
        "verification_source",
        "verification_home_score",
        "verification_away_score",
        "verification_confidence",
        "verification_locked_odds",
        "verification_closing_odds",
        "verification_add_proof_row",
        "verification_add_score_payload",
        "verification_add_clv_payload",
        "verification_clear_preview",
        "verification_run_preview",
    ):
        assert token in SOURCE


def test_result_verification_preview_page_displays_required_report_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "report_id",
        "report_hash",
        "status",
        "overall_passed",
        "row_count",
        "unique_events",
        "duplicate_row_count",
        "score_payload_count",
        "clv_payload_count",
        "ready_count",
        "manual_review_count",
        "frozen_pick_logic",
        "warning_count",
        "error_count",
    ):
        assert token in SOURCE


def test_result_verification_preview_page_has_safeguard_status_language():
    for token in (
        "VERIFICATION READY",
        "MANUAL REVIEW REQUIRED",
        "NO ROWS",
        "FROZEN PICK LOGIC",
    ):
        assert token in SOURCE


def test_result_verification_preview_page_download_is_memory_only_and_hash_keyed():
    assert "st.download_button" in SOURCE
    assert "export_verification_preview_report_json(report, public_safe=True).encode" in SOURCE
    assert "result_verification_report_json_{safe_text(report.get('report_hash'))}" in SOURCE
    assert "_report_filename(report)" in SOURCE


def test_result_verification_preview_page_uses_in_memory_rows_only():
    assert "PROOF_ROWS_KEY" in SOURCE
    assert "SCORE_ROWS_KEY" in SOURCE
    assert "CLV_ROWS_KEY" in SOURCE
    assert "st.session_state" in SOURCE
    assert "write_text" not in SOURCE
    assert "write_bytes" not in SOURCE


def test_result_verification_preview_page_has_no_network_or_mutation_paths():
    forbidden = (
        "requests.",
        "httpx.",
        "urllib.",
        "approve_ledger_import",
        "append_performance_rows",
        "sync_rows_by_source",
        "update_result",
        "delete_proof",
        "open(",
    )
    for token in forbidden:
        assert token not in SOURCE


def test_result_verification_preview_page_english_and_spanish_text_keys_exist():
    text = _text_dict()
    required = {
        "title",
        "caption",
        "workspace_id",
        "event",
        "sport",
        "market_type",
        "pick",
        "source",
        "home_score",
        "away_score",
        "confidence",
        "locked_odds",
        "closing_odds",
        "add_proof_row",
        "add_score_payload",
        "add_clv_payload",
        "clear_preview",
        "run_preview",
        "row_ready",
        "score_ready",
        "clv_ready",
        "cleared",
        "report_ready",
        "verification_ready",
        "manual_review_required",
        "no_rows",
        "frozen_logic",
        "event_rows",
        "score_rows",
        "clv_rows",
        "verification_rows",
        "report_summary",
        "validation",
        "download_report",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_result_verification_preview_page_has_no_fake_demo_values():
    for token in ("John Doe", "NY Liberty -120", "Aces vs Liberty", "+8.4%"):
        assert token not in SOURCE
