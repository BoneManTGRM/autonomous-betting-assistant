"""Scoring helpers."""

from __future__ import annotations


def level(score):
    if score is None:
        return "unknown"
    return "Low" if score <= 3 else "Medium" if score <= 6 else "High" if score <= 8 else "Very High"
