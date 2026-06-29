from __future__ import annotations

from pathlib import Path


def test_advisory_explanation_page_imports_helpers_and_warning_text() -> None:
    text = Path("pages/advisory_odds_value.py").read_text(encoding="utf-8")
    assert "advisory_explanation_engine" in text
    assert "Advisory Explanation Engine" in text
    assert "Explanations are advisory-only" in text
    assert "explain_advisory_rows" in text


def test_explanation_module_does_not_call_lock_publish_training_or_storage_functions() -> None:
    text = Path("autonomous_betting_agent/advisory_explanation_engine.py").read_text(encoding="utf-8")
    forbidden = [
        "lock_rows(",
        "research_lock_rows(",
        "publish_locked_rows(",
        "save_persistent_ledger(",
        "save_held_rows(",
        "place_bet(",
        "live_bet(",
        "fit(",
        "predict_proba(",
        "joblib.dump(",
        "to_pickle(",
        "to_csv(",
        "FastAPI",
        "uvicorn",
        "supabase",
        "firebase",
        "stripe",
        "billing",
        "login",
        "cron",
    ]
    for token in forbidden:
        assert token not in text


def test_advisory_page_does_not_call_forbidden_write_or_execution_functions() -> None:
    text = Path("pages/advisory_odds_value.py").read_text(encoding="utf-8")
    forbidden = [
        "lock_rows(",
        "research_lock_rows(",
        "publish_locked_rows(",
        "save_persistent_ledger(",
        "save_held_rows(",
        "place_bet(",
        "live_bet(",
        "fit(",
        "joblib.dump(",
    ]
    for token in forbidden:
        assert token not in text
