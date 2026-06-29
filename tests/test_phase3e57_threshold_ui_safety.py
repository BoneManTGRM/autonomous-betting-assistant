from __future__ import annotations

from pathlib import Path


def test_advisory_threshold_page_imports_helpers_and_warning_text() -> None:
    text = Path("pages/advisory_odds_value.py").read_text(encoding="utf-8")
    assert "advisory_threshold_calibration" in text
    assert "Advisory Threshold Calibration" in text
    assert "This calibration panel changes advisory classifications only" in text
    assert "advisory_calibrated_playable_status" not in text or "apply_advisory_thresholds" in text


def test_threshold_page_does_not_call_forbidden_lock_or_ledger_functions() -> None:
    text = Path("pages/advisory_odds_value.py").read_text(encoding="utf-8")
    forbidden = [
        "lock_rows(",
        "research_lock_rows(",
        "publish_locked_rows(",
        "save_persistent_ledger(",
        "save_held_rows(",
        "place_bet(",
        "live_bet(",
    ]
    for token in forbidden:
        assert token not in text


def test_threshold_module_does_not_call_forbidden_lock_or_ledger_functions() -> None:
    text = Path("autonomous_betting_agent/advisory_threshold_calibration.py").read_text(encoding="utf-8")
    forbidden = [
        "lock_rows(",
        "research_lock_rows(",
        "publish_locked_rows(",
        "save_persistent_ledger(",
        "save_held_rows(",
        "place_bet(",
        "live_bet(",
    ]
    for token in forbidden:
        assert token not in text


def test_threshold_presets_are_static_controls_not_fitted_to_files() -> None:
    text = Path("autonomous_betting_agent/advisory_threshold_calibration.py").read_text(encoding="utf-8")
    assert "advisory_threshold_presets" in text
    assert "fit(" not in text
    assert "optimize" not in text.lower()
    assert "uploaded file" not in text.lower()
