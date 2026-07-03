from __future__ import annotations


def value_present() -> bool:
    try:
        from autonomous_betting_agent.balldontlie_integration import _secret
        return bool(_secret())
    except Exception:
        return False


def health_status() -> str:
    if not value_present():
        return "Missing"
    try:
        from autonomous_betting_agent.balldontlie_integration import _data_list, _request_json
        payload = _request_json("nba", "/teams", {"per_page": 1})
        if isinstance(payload, dict) and payload.get("_error"):
            return "Failed"
        if _data_list(payload):
            return "Enabled"
        return "Failed"
    except Exception:
        return "Failed"


def label() -> str:
    return health_status()
