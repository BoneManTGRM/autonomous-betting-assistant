from __future__ import annotations

try:
    from autonomous_betting_agent.odds_input_normalizer import install_odds_breakdown_normalizer

    install_odds_breakdown_normalizer()
except Exception:
    pass
