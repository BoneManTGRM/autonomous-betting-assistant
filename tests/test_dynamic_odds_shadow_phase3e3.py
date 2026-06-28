from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

import autonomous_betting_agent.ui_i18n_phase3e  # noqa: F401
from autonomous_betting_agent.dynamic_odds_display import (
    build_dynamic_odds_shadow_rows,
    dynamic_odds_feature_influence_rows,
    dynamic_odds_shadow_learning_summary,
)
from autonomous_betting_agent.dynamic_odds_shadow_memory import (
    clear_dynamic_odds_shadow_model,
    export_dynamic_odds_shadow_model_json,
    import_dynamic_odds_shadow_model_json,
    load_dynamic_odds_shadow_model,
    protected_baseline_metrics,
    train_and_save_dynamic_odds_shadow_model,
    training_result_stats,
)
from autonomous_betting_agent.ui_i18n import localize_dataframe


def row(result: str | None = None, workspace: str = "phase3e3", sport: str = "soccer") -> dict[str, object]:
    data: dict[str, object] = {
        "event": "Team A at Team B",
        "prediction": "Team A",
        "sport": sport,
        "league": "test_league",
        "market_type": "h2h",
        "bookmaker": "TestBook",
        "decimal_price": 2.5,
        "model_probability": 0.70,
        "model_market_edge": 0.30,
        "expected_value_per_unit": 0.75,
        "test_window_id": workspace,
        "lock_ready": True,
        "publish_ready": True,
        "proof_hash": "abc123",
    }
    if result is not None:
        data["result_status"] = result
    return data


def result_rows(wins: int, losses: int, pushes: int = 0, workspace: str = "phase3e3") -> list[dict[str, object]]:
    return [row("win", workspace) for _ in range(wins)] + [row("loss", workspace, sport="basketball") for _ in range(losses)] + [row("push", workspace) for _ in range(pushes)]


def test_protected_baseline_never_falls_below_floor_when_sample_is_weak() -> None:
    metrics = protected_baseline_metrics(wins=29, losses=21)
    assert metrics["global_baseline"] == 0.70
    assert metrics["baseline_floor"] == 0.68
    assert metrics["protected_baseline"] >= 0.68
    assert metrics["baseline_floor_active"] is True
    assert metrics["segment_underperforming"] is True


def test_strong_underperforming_segment_does_not_change_global_baseline() -> None:
    metrics = protected_baseline_metrics(wins=174, losses=126)
    assert metrics["segment_baseline"] == 0.58
    assert metrics["global_baseline"] == 0.70
    assert metrics["segment_underperforming"] is True
    assert metrics["baseline_source"] == "strong_segment_observed_with_global_prior"


def test_model_quality_thresholds_and_push_exclusion() -> None:
    stats = training_result_stats(result_rows(29, 21, pushes=7))
    assert stats["completed_rows_seen"] == 50
    assert stats["wins"] == 29
    assert stats["losses"] == 21
    assert stats["pushes_excluded"] == 7
    model = train_and_save_dynamic_odds_shadow_model(result_rows(29, 21, pushes=7, workspace="phase3e3_quality"), workspace_id="phase3e3_quality")
    assert model["model_quality_label"] == "WEAK SAMPLE"
    assert model["protected_baseline"] >= 0.68
    assert model["dynamic_odds_live_activation"] == "OFF"
    assert model["dynamic_odds_applied_live_count"] == 0


def test_saved_model_loads_for_pending_rows_and_does_not_mutate_live_fields() -> None:
    workspace = "phase3e3_pending"
    clear_dynamic_odds_shadow_model(workspace)
    train_and_save_dynamic_odds_shadow_model(result_rows(80, 30, workspace=workspace), workspace_id=workspace)
    pending = row(None, workspace)
    before = deepcopy(pending)
    shadow = build_dynamic_odds_shadow_rows([pending])
    assert pending == before
    assert shadow[0]["lr_model_loaded"] is True
    assert shadow[0]["lr_model_source"] == "saved_shadow_model"
    assert shadow[0]["dynamic_odds_applied_live_count"] == 0
    assert before["model_probability"] == 0.70
    assert before["expected_value_per_unit"] == 0.75
    assert before["lock_ready"] is True
    assert before["publish_ready"] is True
    assert before["proof_hash"] == "abc123"


def test_import_rejects_unsafe_shadow_model_json() -> None:
    workspace = "phase3e3_import"
    payload = train_and_save_dynamic_odds_shadow_model(result_rows(80, 20, workspace=workspace), workspace_id=workspace)
    unsafe = deepcopy(payload)
    unsafe["dynamic_odds_live_activation"] = "ON"
    with pytest.raises(ValueError):
        import_dynamic_odds_shadow_model_json(__import__("json").dumps(unsafe), workspace_id=workspace)
    unsafe = deepcopy(payload)
    unsafe["dynamic_odds_applied_live_count"] = 1
    with pytest.raises(ValueError):
        import_dynamic_odds_shadow_model_json(__import__("json").dumps(unsafe), workspace_id=workspace)


def test_clear_model_only_removes_shadow_model_file() -> None:
    workspace = "phase3e3_clear"
    train_and_save_dynamic_odds_shadow_model(result_rows(40, 10, workspace=workspace), workspace_id=workspace)
    assert load_dynamic_odds_shadow_model(workspace)
    clear_dynamic_odds_shadow_model(workspace)
    assert load_dynamic_odds_shadow_model(workspace) == {}


def test_feature_influence_and_comparison_summary() -> None:
    workspace = "phase3e3_influence"
    model = train_and_save_dynamic_odds_shadow_model(result_rows(90, 30, workspace=workspace), workspace_id=workspace)
    influence = dynamic_odds_feature_influence_rows(model)
    assert influence
    assert {"LR", "sample_size", "wins", "losses", "reason"}.issubset(influence[0])
    summary = dynamic_odds_shadow_learning_summary([row(None, workspace)])
    assert "average_EV_delta" in summary
    assert "average_probability_delta" in summary
    assert summary["dynamic_odds_live_activation"] == "OFF"
    assert summary["dynamic_odds_applied_live_count"] == 0


def test_spanish_labels_and_page_markers() -> None:
    frame = pd.DataFrame([{
        "global_baseline": 0.70,
        "protected_baseline": 0.68,
        "model_quality_label": "WEAK SAMPLE",
        "shadow_decision_label": "shadow_blocked_by_baseline_guard",
        "pushes_excluded": 3,
    }])
    localized = localize_dataframe(frame, "es")
    assert "Base global" in localized.columns
    assert "Base protegida" in localized.columns
    assert "Pushes excluidos" in localized.columns
    reparodynamics = Path("pages/reparodynamics.py").read_text(encoding="utf-8")
    odds_lock = Path("pages/odds_lock_pro.py").read_text(encoding="utf-8")
    assert "Dynamic Odds Shadow Model Status" in reparodynamics
    assert "Train Dynamic Odds Shadow Model from Graded CSV" in reparodynamics
    assert "Dynamic Odds Shadow Math" in odds_lock


def test_export_model_json_preserves_safety() -> None:
    workspace = "phase3e3_export"
    train_and_save_dynamic_odds_shadow_model(result_rows(80, 25, workspace=workspace), workspace_id=workspace)
    exported = export_dynamic_odds_shadow_model_json(workspace)
    assert '"dynamic_odds_live_activation": "OFF"' in exported
    assert '"dynamic_odds_applied_live_count": 0' in exported
    assert '"shadow_model_training": "OFFLINE_ONLY"' in exported
