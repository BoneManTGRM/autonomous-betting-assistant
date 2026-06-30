from __future__ import annotations

try:
    from autonomous_betting_agent.proof_persistence_patch import install_proof_persistence_patch
    install_proof_persistence_patch()
except Exception:
    pass

try:
    from autonomous_betting_agent.sidebar_tools import install_sidebar_tools
    install_sidebar_tools()
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
