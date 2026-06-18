from __future__ import annotations

import builtins
import os


def get_secret(*names: str) -> str:
    try:
        import streamlit as st
    except Exception:
        st = None
    for name in names:
        if not name:
            continue
        if st is not None:
            try:
                value = str(st.secrets.get(name, '')).strip()
                if value:
                    return value
            except Exception:
                pass
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


builtins.get_secret = get_secret


def _running_in_ci() -> bool:
    return os.getenv('CI', '').lower() == 'true' or os.getenv('GITHUB_ACTIONS', '').lower() == 'true'


def _install_runtime_helpers() -> None:
    if _running_in_ci():
        return
    try:
        from autonomous_betting_agent.pro_predictor_defaults_patch import install_pro_predictor_defaults_patch
        install_pro_predictor_defaults_patch()
    except Exception:
        pass
    try:
        from autonomous_betting_agent.odds_input_normalizer import install_odds_breakdown_normalizer
        install_odds_breakdown_normalizer()
    except Exception:
        pass
    try:
        from autonomous_betting_agent.proof_dashboard_patch import install_proof_dashboard_patch
        install_proof_dashboard_patch()
    except Exception:
        pass
    try:
        from autonomous_betting_agent.local_users import install_streamlit_local_user_selector
        install_streamlit_local_user_selector()
    except Exception:
        pass


_install_runtime_helpers()
