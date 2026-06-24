"""Result grading helpers with row-level vs event-level separation."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

WINS = {"win", "won", "w"}
LOSSES = {"loss", "lost", "l"}
PUSHES = {"push", "void", "draw", "no action"}
CANCELS = {"cancel", "cancelled", "canceled", "postponed"}
PENDING = {"", "pending", "open", "ungraded"}


def normalize_grade(value: Any) -> str:
    raw = "" if value is None else str(value).strip().lower()
    if raw in WINS:
        return "win"
    if raw in LOSSES:
        return "loss"
    if raw in PUSHES:
        return "push"
    if raw in CANCELS:
        return "cancel"
    return "pending"


def event_key(row: Mapping[str, Any]) -> str:
    return "|".join(
        str(row.get(key) or "").strip().lower()
        for key in ("sport", "event_name", "event", "matchup", "event_start_time")
    )


def summarize_row_level(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {"wins": 0, "losses": 0, "pushes": 0, "cancels": 0, "pending": 0, "rows": 0}
    for row in rows:
        out["rows"] += 1
        grade = normalize_grade(row.get("grade") or row.get("result"))
        if grade == "win":
            out["wins"] += 1
        elif grade == "loss":
            out["losses"] += 1
        elif grade == "push":
            out["pushes"] += 1
        elif grade == "cancel":
            out["cancels"] += 1
        else:
            out["pending"] += 1
    return out


def summarize_event_level(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[event_key(row)].append(row)
    out = {"wins": 0, "losses": 0, "pushes": 0, "cancels": 0, "pending": 0, "events": 0}
    for group in grouped.values():
        out["events"] += 1
        grades = {normalize_grade(row.get("grade") or row.get("result")) for row in group}
        if "loss" in grades:
            out["losses"] += 1
        elif "win" in grades:
            out["wins"] += 1
        elif "push" in grades:
            out["pushes"] += 1
        elif "cancel" in grades:
            out["cancels"] += 1
        else:
            out["pending"] += 1
    return out


def detect_grade_conflict(existing_grade: Any, new_grade: Any) -> bool:
    old = normalize_grade(existing_grade)
    new = normalize_grade(new_grade)
    return old != "pending" and new != "pending" and old != new
