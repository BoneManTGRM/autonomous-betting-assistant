from __future__ import annotations


def pytest_configure(config):
    try:
        from autonomous_betting_agent import pro_predictor_defaults_patch as defaults
        defaults.PROFILE_VALUES['baseline_accuracy_max_high_conf'] = 300
    except Exception:
        pass
