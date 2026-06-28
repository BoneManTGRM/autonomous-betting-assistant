from autonomous_betting_agent.reparodynamics_doctrine import get_reparodynamics_doctrine


PHASE_3E_NAME = "Phase 3E Dynamic Odds Predictor Shadow"


def test_doctrine_phase_values():
    doctrine = get_reparodynamics_doctrine()

    assert doctrine["current_phase"] == PHASE_3E_NAME
    assert doctrine["shadow_mode_activation"] == "ON"
    assert doctrine["live_mutation"] == "FORBIDDEN"
    assert doctrine["model_training"] == "FORBIDDEN"
    assert doctrine["stored_data_mutation"] == "FORBIDDEN"
    assert doctrine["repair_activation"] == "OFF"
    assert doctrine["repairs_applied_live"] == 0
    assert doctrine["live_repairs_applied_count"] == 0
    assert doctrine["dynamic_odds_live_activation"] == "OFF"
    assert doctrine["dynamic_odds_applied_live"] == 0
    assert doctrine["dynamic_odds_applied_live_count"] == 0
    assert doctrine["automatic_live_promotion"] == "FORBIDDEN"
