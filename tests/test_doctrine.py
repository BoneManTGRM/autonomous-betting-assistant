from autonomous_betting_agent.reparodynamics_doctrine import get_reparodynamics_doctrine


def test_doctrine_phase_values():
    doctrine = get_reparodynamics_doctrine()
    assert doctrine["current_phase"] == "Phase 3C Shadow Backtest"
    assert doctrine["operating_mode"] == "Shadow Backtest comparison"
    assert doctrine["live_mutation"] == "FORBIDDEN"
    assert doctrine["repair_activation"] == "OFF"
    assert doctrine["shadow_mode_activation"] == "ON"
    assert doctrine["tgrm_activation"] == "SHADOW ONLY"
    assert doctrine["rye_activation"] == "SHADOW ONLY"
    assert doctrine["model_training"] == "FORBIDDEN"
    assert doctrine["stored_data_mutation"] == "FORBIDDEN"
    assert doctrine["repairs_applied_live"] == 0
    assert doctrine["live_repairs_applied"] == 0
