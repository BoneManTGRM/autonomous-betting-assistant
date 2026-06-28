from autonomous_betting_agent.reparodynamics_doctrine import get_reparodynamics_doctrine


def test_doctrine_phase_values():
    doctrine = get_reparodynamics_doctrine()
    assert doctrine["current_phase"] == "Phase 3D Repair Memory"
    assert doctrine["repair_activation"] == "OFF"
    assert doctrine["shadow_mode_activation"] == "ON"
    assert doctrine["repairs_applied_live"] == 0
