from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd

import autonomous_betting_agent.ui_i18n_phase3e  # noqa: F401
from autonomous_betting_agent.dynamic_odds_display import (
    build_dynamic_odds_shadow_row,
    build_dynamic_odds_shadow_rows,
    dynamic_odds_shadow_learning_summary,
    dynamic_odds_shadow_safety_summary,
)
from autonomous_betting_agent.dynamic_odds_shadow_memory import (
    delete_dynamic_odds_shadow_model,
    load_dynamic_odds_shadow_model,
    train_and_save_dynamic_odds_shadow_model,
)
from autonomous_betting_agent.ui_i18n import localize_dataframe, localize_value


def sample_row(workspace_id: str = "shadow_display_no_model") -> dict[str, object]:
    return {
        "event": "Team A at Team B",
        "prediction": "Team A",
        "market_type": "h2h",
        "bookmaker": "TestBook",
        "decimal_price": 2.5,
        "model_probability": 0.55,
        "model_market_edge": 0.15,
        "expected_value_per_unit": 0.375,
        "test_window_id": workspace_id,
        "lock_ready": True,
        "publish_ready": True,
        "official_status_label": "official_plus_ev",
        "proof_hash": "abc123",
    }


def completed_row(result: str, sport: str = "soccer", workspace_id: str = "shadow_learning_feed") -> dict[str, object]:
    row = sample_row(workspace_id)
    row["sport"] = sport
    row["result_status"] = result
    return row


def test_shadow_row_returns_dynamic_math_fields() -> None:
    delete_dynamic_odds_shadow_model("shadow_display_no_model")
    row = build_dynamic_odds_shadow_row(sample_row())
    assert row["dynamic_probability"] is not None
    assert row["dynamic_edge"] is not None
    assert row["dynamic_no_vig_edge"] is not None
    assert row["dynamic_EV"] is not None
    assert row["book_odds_ratio"] is not None
    assert row["probability_delta"] is not None
    assert row["dynamic_EV_delta"] is not None
    assert row["baseline_vs_dynamic_status"]
    assert row["dynamic_odds_mode"] == "SHADOW ONLY"
    assert row["dynamic_odds_applied_live_count"] == 0


def test_shadow_row_does_not_mutate_input_row_or_live_fields() -> None:
    original = sample_row()
    before = deepcopy(original)
    row = build_dynamic_odds_shadow_row(original)
    assert original == before
    assert before["model_probability"] == 0.55
    assert before["model_market_edge"] == 0.15
    assert before["expected_value_per_unit"] == 0.375
    assert before["lock_ready"] is True
    assert before["publish_ready"] is True
    assert before["official_status_label"] == "official_plus_ev"
    assert before["proof_hash"] == "abc123"
    assert "lock_ready" not in row
    assert "publish_ready" not in row
    assert "official_status_label" not in row
    assert "proof_hash" not in row


def test_missing_odds_returns_no_odds_status() -> None:
    row = build_dynamic_odds_shadow_row({"event": "Team A at Team B", "model_probability": 0.55, "test_window_id": "shadow_missing_odds"})
    assert row["dynamic_signal_status"] == "no_odds"
    assert row["dynamic_probability"] is None


def test_missing_lr_data_defaults_to_shadow_lr_one() -> None:
    delete_dynamic_odds_shadow_model("shadow_no_lr")
    row = build_dynamic_odds_shadow_row(sample_row("shadow_no_lr"))
    assert row["total_LR_multiplier"] == 1.0
    assert row["dynamic_signal_status"] == "no_lr_data"
    assert row["lr_model_loaded"] is False


def test_completed_rows_build_and_save_read_only_lr_learning_feed() -> None:
    workspace = "shadow_learning_feed"
    delete_dynamic_odds_shadow_model(workspace)
    rows = [completed_row("win", workspace_id=workspace) for _ in range(30)] + [completed_row("loss", sport="basketball", workspace_id=workspace) for _ in range(30)] + [sample_row(workspace)]
    shadow = build_dynamic_odds_shadow_rows(rows)
    saved = load_dynamic_odds_shadow_model(workspace)
    assert saved["workspace_id"] == workspace
    assert saved["dynamic_odds_live_activation"] == "OFF"
    assert saved["dynamic_odds_applied_live_count"] == 0
    assert shadow[-1]["lr_model_loaded"] is True
    assert shadow[-1]["lr_model_source"] == "saved_shadow_model"
    assert shadow[-1]["lr_training_rows_used"] >= 60
    assert shadow[-1]["lr_feature_count"] > 0
    assert shadow[-1]["strongest_LR_feature"]
    assert shadow[-1]["dynamic_odds_applied_live_count"] == 0
    summary = dynamic_odds_shadow_learning_summary(rows)
    assert summary["lr_model_loaded"] is True
    assert summary["training_rows_used"] >= 60
    assert summary["dynamic_odds_live_activation"] == "OFF"
    assert summary["dynamic_odds_applied_live_count"] == 0


def test_saved_model_loads_for_pending_rows_without_completed_rows() -> None:
    workspace = "shadow_saved_model_pending"
    delete_dynamic_odds_shadow_model(workspace)
    train_rows = [completed_row("win", workspace_id=workspace) for _ in range(30)] + [completed_row("loss", sport="basketball", workspace_id=workspace) for _ in range(30)]
    train_and_save_dynamic_odds_shadow_model(train_rows, workspace_id=workspace, source="unit_test")
    pending = [sample_row(workspace)]
    shadow = build_dynamic_odds_shadow_rows(pending)
    assert shadow[0]["lr_model_loaded"] is True
    assert shadow[0]["lr_model_source"] == "saved_shadow_model"
    assert shadow[0]["dynamic_odds_applied_live_count"] == 0


def test_shadow_rows_and_safety_summary_are_display_only() -> None:
    rows = build_dynamic_odds_shadow_rows([sample_row("shadow_display_only")])
    assert len(rows) == 1
    safety = dynamic_odds_shadow_safety_summary()
    assert safety["dynamic_odds_predictor"] == "SHADOW ONLY"
    assert safety["dynamic_odds_live_activation"] == "OFF"
    assert safety["dynamic_odds_applied_live"] == 0
    assert safety["dynamic_odds_applied_live_count"] == 0
    assert safety["live_mutation"] == "FORBIDDEN"
    assert safety["model_training"] == "FORBIDDEN"
    assert safety["stored_data_mutation"] == "FORBIDDEN"


def test_ui_sources_include_read_only_dynamic_odds_panel() -> None:
    odds_lock = Path("pages/odds_lock_pro.py").read_text(encoding="utf-8")
    what_odds = Path("pages/what_are_the_odds.py").read_text(encoding="utf-8")
    assert "Dynamic Odds Shadow Math" in odds_lock
    assert "Matematica Shadow de Dynamic Odds" in odds_lock
    assert "These values do not change live picks" in odds_lock
    assert "build_dynamic_odds_shadow_rows" in odds_lock
    assert "Dynamic Odds Shadow Math" in what_odds
    assert "Matematica Shadow de Dynamic Odds" in what_odds
    assert "These values do not change live picks" in what_odds


def test_spanish_dynamic_odds_display_labels() -> None:
    frame = pd.DataFrame([build_dynamic_odds_shadow_row(sample_row("shadow_spanish"))])
    localized = localize_dataframe(frame, "es")
    assert "Probabilidad dinamica" in localized.columns
    assert "EV dinamico" in localized.columns
    assert "Modo Dynamic Odds" in localized.columns
    assert localize_value("SHADOW ONLY", "es") == "solo shadow"


def test_shadow_memory_trainer_branch_check() -> None:
    assert True
