from autonomous_betting_agent.reparodynamics_doctrine import get_reparodynamics_doctrine


def test_doctrine_phase_values():
    doctrine = get_reparodynamics_doctrine()
    assert doctrine["current_phase"] == "Phase 3A"
    assert doctrine["operating_mode"] == "Observation-only"
    assert doctrine["live_mutation"] == "Forbidden"
    assert doctrine["repair_activation"] == "OFF"
    assert doctrine["shadow_mode_activation"] == "OFF"
    assert doctrine["tgrm_activation"] == "OFF"
    assert doctrine["rye_activation"] == "OFF"
