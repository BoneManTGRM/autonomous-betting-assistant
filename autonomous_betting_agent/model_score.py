"""Model score helpers."""

from __future__ import annotations


def level(score):
    if score is None:
        return "unknown"
    return "Low" if score <= 3 else "Medium" if score <= 6 else "High" if score <= 8 else "Very High"


def calculate_blended_score(row, client_profile=None):
    value = row.get("score") or row.get("blended_score") or row.get("risk_score")
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 6.0
    return round(max(1.0, min(10.0, value)), 1)
