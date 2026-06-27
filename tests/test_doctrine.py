from autonomous_betting_agent.reparodynamics_doctrine import get_reparodynamics_doctrine


def test_doctrine_phase_values():
    doctrine = get_reparodynamics_doctrine()
    assert doctrine["current_phase"] == "Phase 3B"
    assert doctrine["operating_mode"] == "Shadow Mode evaluation"
    assert doctrine["live_mutation"] == "Forbidden"
    assert doctrine["repair_activation"] == "OFF"
    assert doctrine["shadow_mode_activation"] == "ON"
    assert doctrine["tgrm_activation"] == "OFF"
    assert doctrine["rye_activation"] == "OFF"
