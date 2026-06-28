from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from autonomous_betting_agent.dynamic_odds_display import build_dynamic_odds_shadow_rows, dynamic_odds_shadow_learning_summary
from autonomous_betting_agent.dynamic_odds_shadow_memory import clear_dynamic_odds_shadow_model, load_dynamic_odds_shadow_model, train_and_save_dynamic_odds_shadow_model
from autonomous_betting_agent.odds_math_control_panel import control_panel_static_markers


def _row(result: str | None = None, workspace: str = "phase3e4") -> dict[str, object]:
    row: dict[str, object] = {
        "event": "Team A at Team B",
        "prediction": "Team A",
        "sport": "soccer",
        "market_type": "h2h",
        "bookmaker": "TestBook",
        "decimal_price": 2.4,
        "model_probability": 0.70,
        "model_market_edge": 0.28,
        "expected_value_per_unit": 0.68,
        "test_window_id": workspace,
        "lock_ready": True,
        "publish_ready": True,
        "proof_hash": "phase3e4-proof",
    }
    if result is not None:
        row["result_status"] = result
    return row


def _rows(wins: int, losses: int, workspace: str = "phase3e4") -> list[dict[str, object]]:
    return [_row("win", workspace) for _ in range(wins)] + [_row("loss", workspace) for _ in range(losses)]


def test_shadow_display_does_not_train_or_save_on_rerender_without_button_click() -> None:
    workspace = "phase3e4_idempotent"
    clear_dynamic_odds_shadow_model(workspace)
    rows = _rows(30, 20, workspace)

    summary = dynamic_odds_shadow_learning_summary(rows)
    assert summary["learning_source"] == "current_completed_rows_shadow_learning_unsaved"
    assert summary["dynamic_odds_live_activation"] == "OFF"
    assert summary["dynamic_odds_applied_live_count"] == 0
    assert load_dynamic_odds_shadow_model(workspace) == {}

    shadow_rows = build_dynamic_odds_shadow_rows(rows)
    assert shadow_rows
    assert load_dynamic_odds_shadow_model(workspace) == {}


def test_saved_shadow_model_still_loads_for_pending_rows_without_mutating_official_fields() -> None:
    workspace = "phase3e4_pending_saved"
    clear_dynamic_odds_shadow_model(workspace)
    train_and_save_dynamic_odds_shadow_model(_rows(90, 20, workspace), workspace_id=workspace)
    pending = _row(None, workspace)
    before = deepcopy(pending)

    shadow_rows = build_dynamic_odds_shadow_rows([pending])

    assert pending == before
    assert shadow_rows[0]["lr_model_loaded"] is True
    assert shadow_rows[0]["lr_model_source"] == "saved_shadow_model"
    assert shadow_rows[0]["dynamic_odds_applied_live_count"] == 0
    assert pending["model_probability"] == 0.70
    assert pending["expected_value_per_unit"] == 0.68
    assert pending["lock_ready"] is True
    assert pending["publish_ready"] is True
    assert pending["proof_hash"] == "phase3e4-proof"


def test_phase3e4_odds_lock_uses_shared_control_panel_with_namespaced_keys() -> None:
    odds_lock = Path("pages/odds_lock_pro.py").read_text(encoding="utf-8")
    reparodynamics = Path("pages/reparodynamics.py").read_text(encoding="utf-8")
    control_panel = Path("autonomous_betting_agent/odds_math_control_panel.py").read_text(encoding="utf-8")

    assert "from autonomous_betting_agent.odds_math_control_panel import render_dynamic_odds_control_panel" in odds_lock
    assert "render_dynamic_odds_control_panel(" in odds_lock
    assert "panel_key_prefix='odds_lock_pro_dynamic_odds_shadow'" in odds_lock
    assert "render_dynamic_odds_control_panel(uploaded_rows or [], workspace_id=workspace_id, language=LANG)" in reparodynamics
    assert "panel_key_prefix" in control_panel
    assert "def _key(panel_key_prefix: str, workspace_id: str, suffix: str)" in control_panel


def test_phase3e4_static_markers_cover_required_ui_and_safety_labels() -> None:
    markers = control_panel_static_markers()
    assert markers["status"] == "Dynamic Odds Shadow Model Status"
    assert markers["trainer"] == "Train Dynamic Odds Shadow Model from Graded CSV"
    assert markers["download"] == "Download Shadow Model JSON"
    assert markers["upload"] == "Upload Shadow Model JSON"
    assert markers["replace"] == "Replace Current Workspace Model"
    assert markers["clear"] == "Clear Shadow Model"
    assert markers["audit"] == "Shadow training audit summary"
    assert markers["live_off"] == "Live application: OFF"
    assert markers["advisory_only"] == "Dynamic odds math: Advisory only"


def test_phase3e4_private_paths_are_not_rendered_by_control_panel_helpers() -> None:
    control_panel = Path("autonomous_betting_agent/odds_math_control_panel.py").read_text(encoding="utf-8")
    assert "PRIVATE_EXPORT_KEYS" in control_panel
    assert "model_path" in control_panel
    assert "model_path_string" not in control_panel
    assert "private file paths" not in control_panel.lower()
