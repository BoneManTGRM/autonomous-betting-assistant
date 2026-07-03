from __future__ import annotations


def value_present() -> bool:
    try:
        from autonomous_betting_agent.balldontlie_integration import _secret
        return bool(_secret())
    except Exception:
        return False


def label() -> str:
    return "Enabled" if value_present() else "Missing"
