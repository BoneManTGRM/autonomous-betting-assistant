"""Result grading helpers with row-level vs event-level separation."""

from __future__ import annotations

from collections import defaultdict
import math
from typing import Any, Iterable, Mapping

WINS = {"win", "won", "w", "winner", "winning", "graded_win", "graded winner", "success", "hit", "cash", "cashed", "✅", "✅ win"}
LOSSES = {"loss", "lost", "l", "loser", "losing", "graded_loss", "graded loss", "failed", "miss", "bust", "❌", "❌ loss"}
PUSHES = {"push", "pushed", "void", "draw", "tie", "no action", "refund", "refunded", "cancelled/refunded"}
CANCELS = {"cancel", "cancelled", "canceled", "postponed", "abandoned", "suspended", "cancel"}
PENDING = {"", "pending", "open", "ungraded", "unknown", "needs grading", "needs_grading", "research", "not official", "research / not official", "n/a", "na", "none", "null"}

GRADE_COLUMNS = (
    "grade",
    "result",
    "final_result",
    "result_status",
    "outcome",
    "pick_result",
    "bet_result",
    "wager_result",
    "graded_result",
    "settlement_status",
    "status",
    "win_loss",
    "learning_result",
    "official_result",
    "public_result",
)

PROFIT_COLUMNS = (
    "actual_profit_units",
    "resolved_profit_units",
    "graded_profit_units",
    "profit_units",
    "net_units",
    "pnl_units",
)

RESOLVED_COLUMNS = (
    "resolved",
    "is_resolved",
    "graded",
    "is_graded",
    "settled",
    "is_settled",
    "final",
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _truthy(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "yes", "y", "resolved", "graded", "settled", "final"}


def _token(value: Any) -> str:
    raw = _text(value).lower()
    raw = raw.replace("_", " ").replace("-", " ")
    raw = " ".join(raw.split())
    return raw


def normalize_grade(value: Any) -> str:
    raw = _token(value)
    if raw in WINS:
        return "win"
    if raw in LOSSES:
        return "loss"
    if raw in PUSHES:
        return "push"
    if raw in CANCELS:
        return "cancel"
    if raw in PENDING:
        return "pending"

    # Be tolerant of common formatted labels from CSV exports and UI rows.
    compact = raw.replace(" ", "")
    if compact in {"win", "won", "winner", "gradedwin"} or raw.startswith("win ") or raw.endswith(" win"):
        return "win"
    if compact in {"loss", "lost", "loser", "gradedloss"} or raw.startswith("loss ") or raw.endswith(" loss"):
        return "loss"
    if compact in {"push", "void", "noaction", "draw"}:
        return "push"
    if compact in {"cancel", "canceled", "cancelled", "postponed"}:
        return "cancel"
    return "pending"


def _profit_grade(row: Mapping[str, Any]) -> str:
    resolved_hint = any(_truthy(row.get(col)) for col in RESOLVED_COLUMNS)
    explicit_result = any(_text(row.get(col)) for col in GRADE_COLUMNS)
    for col in PROFIT_COLUMNS:
        raw = _text(row.get(col))
        if not raw:
            continue
        try:
            value = float(raw.replace("%", "").replace(",", ""))
        except ValueError:
            continue
        if not math.isfinite(value):
            continue
        # Only use profit as a fallback when the row appears settled or no explicit
        # result field exists. This prevents expected-value fields from being graded.
        if not resolved_hint and explicit_result:
            continue
        if value > 0:
            return "win"
        if value < 0:
            return "loss"
        return "push"
    return "pending"


def grade_from_row(row: Mapping[str, Any]) -> str:
    """Normalize a grade from proof, ledger, and learning-memory CSV columns."""
    for col in GRADE_COLUMNS:
        grade = normalize_grade(row.get(col))
        if grade != "pending":
            return grade
    return _profit_grade(row)


def event_key(row: Mapping[str, Any]) -> str:
    return "|".join(
        str(row.get(key) or "").strip().lower()
        for key in ("sport", "event_name", "event", "matchup", "event_start_time")
    )


def summarize_row_level(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out = {"wins": 0, "losses": 0, "pushes": 0, "cancels": 0, "pending": 0, "rows": 0}
    for row in rows:
        out["rows"] += 1
        grade = grade_from_row(row)
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
        grades = {grade_from_row(row) for row in group}
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
