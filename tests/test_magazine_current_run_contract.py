from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_report_studio_runtime_patch_loads_before_pages():
    sitecustomize = (ROOT / "sitecustomize.py").read_text(encoding="utf-8")
    usercustomize = (ROOT / "usercustomize.py").read_text(encoding="utf-8")
    assert "report_studio_fresh_handoff_patch" in sitecustomize
    assert "report_studio_fresh_handoff_patch" in usercustomize


def test_report_studio_current_run_patch_contract():
    patch = (ROOT / "autonomous_betting_agent" / "report_studio_fresh_handoff_patch.py").read_text(encoding="utf-8")
    assert "HANDOFF_KEYS" in patch
    assert "pro_predictor_latest_rows" in patch
    assert "pro_predictor_high_confidence_rows" in patch
    assert "odds_lock_pro_locked_rows" in patch
    assert "_patch_report_studio_ledger_source" in patch
    assert "_called_from_report_studio" in patch
    assert "pages/report_studio.py" in patch
    assert "_patch_local_storage" in patch


def test_report_studio_warns_when_only_ledger_history_is_available():
    page = (ROOT / "pages" / "report_studio.py").read_text(encoding="utf-8")
    assert "persistent_proof_ledger" in page
    assert "rows_from_saved_sources" in page
    assert "Source" in page or "source" in page
