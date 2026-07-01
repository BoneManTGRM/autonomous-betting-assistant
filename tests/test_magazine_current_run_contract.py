from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _report_studio_text() -> str:
    return (ROOT / "pages" / "report_studio.py").read_text(encoding="utf-8")


def _polish_text() -> str:
    return (ROOT / "autonomous_betting_agent" / "magazine_report_polish_patch.py").read_text(encoding="utf-8")


def test_report_studio_full_feature_tabs_are_restored():
    page = _report_studio_text()
    for token in (
        't("cards")',
        't("magazine")',
        't("copy")',
        't("audit")',
        't("proof")',
        't("exports")',
        't("images")',
        't("profile_json")',
        't("feed_json")',
        't("diagnostics")',
        't("publisher")',
    ):
        assert token in page


def test_report_studio_source_priority_is_direct_not_startup_patch():
    page = _report_studio_text()
    assert "def load_current_session_rows" in page
    assert "def load_saved_handoff_rows" in page
    assert "def load_persistent_ledger_rows" in page
    assert "def choose_report_studio_source" in page
    assert "load_current_session_rows, lambda: load_saved_handoff_rows" in page
    assert "lambda: load_persistent_ledger_rows" in page
    assert page.find("load_current_session_rows") < page.find("load_saved_handoff_rows") < page.find("load_persistent_ledger_rows")


def test_report_studio_upload_priority_and_ledger_warning_contract():
    page = _report_studio_text()
    assert "choose_report_studio_source(saved_source, saved_rows, upload_source, upload_rows)" in page
    assert "if upload_rows is not None and not upload_rows.empty" in page
    assert "persistent_proof_ledger" in page
    assert "Magazine is using saved proof history because no current prediction rows were found" in page
    assert "Source mode:" in page


def test_startup_hooks_do_not_control_report_studio_source_selection():
    sitecustomize = (ROOT / "sitecustomize.py").read_text(encoding="utf-8")
    usercustomize = (ROOT / "usercustomize.py").read_text(encoding="utf-8")
    assert "intentionally does not monkey-patch Streamlit widgets" in sitecustomize
    assert "report_studio_fresh_handoff_patch" not in sitecustomize
    assert "report_studio_fresh_handoff_patch" not in usercustomize


def test_fallback_magazine_copy_is_presentation_safe():
    polish = _polish_text()
    for token in (
        "Watchlist only: current price and live context need verification.",
        "Live team feed not linked to this row.",
        "Lineup/injury feed not verified for this row.",
        "Fallback/watchlist only.",
        "Straight watchlist only.",
        "Do not parlay fallback rows.",
        "no verified live match",
    ):
        assert token in polish
    assert "module.api_provenance = polished_api_provenance" in polish
