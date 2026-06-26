"""ABA Adaptive Repair Engine Phase 0-2 simulation utilities.

Phase 0-2 is intentionally safe: it ingests graded rows, separates row-level
and unique-event performance, reports data-quality issues, and never activates
production repairs.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

WIN_TOKENS = {"win", "won", "w", "winner", "winning", "hit", "cash", "cashed", "success", "graded win"}
LOSS_TOKENS = {"loss", "lost", "l", "loser", "losing", "miss", "bust", "failed", "graded loss"}
PUSH_TOKENS = {"push", "pushed", "tie", "draw", "refund", "refunded"}
VOID_TOKENS = {"void", "voided", "no action", "no-action", "cancelled/refunded"}
CANCEL_TOKENS = {"cancel", "canceled", "cancelled", "postponed", "abandoned", "suspended"}
UNKNOWN_TOKENS = {"unknown", "n/a", "na", "none", "null"}
PENDING_TOKENS = {"", "pending", "open", "ungraded", "needs grading", "needs_grading", "research", "not official"}

RESULT_COLUMNS = (
    "grade",
    "result",
    "final_result",
    "result_status",
    "outcome",
    "pick_result",
    "bet_result",
    "graded_result",
    "settlement_status",
    "status",
    "win_loss",
    "learning_result",
    "official_result",
    "public_result",
)
EVENT_COLUMNS = ("event_name", "event", "matchup", "game", "fixture", "match")
START_COLUMNS = ("event_start_time", "known_start_utc", "start_time", "commence_time", "game_time", "date")
SPORT_COLUMNS = ("sport", "league", "competition")
MARKET_COLUMNS = ("market", "prop_type", "bet_type", "pick_type")
SPORT_STYLE_HINTS = ("fifa", "soccer", "football", "league of ireland", "série", "serie", "veikkausliiga", "super league")
COMBAT_HINTS = ("ufc", "mma", "boxing", "combat")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _token(value: Any) -> str:
    return " ".join(_text(value).lower().replace("_", " ").replace("-", " ").split())


def _compact(value: str) -> str:
    return value.replace(" ", "")


def _first_value(row: Mapping[str, Any], columns: Sequence[str]) -> str:
    lowered = {str(key).strip().lower(): value for key, value in row.items()}
    for column in columns:
        value = _text(lowered.get(column.lower()))
        if value:
            return value
    return ""


def normalize_result_status(value: Any) -> str:
    """Normalize result labels while preserving void and unknown separately."""
    raw = _token(value)
    compact = _compact(raw)
    if raw in WIN_TOKENS or compact in {"win", "won", "winner", "gradedwin"} or raw.startswith("win ") or raw.endswith(" win"):
        return "win"
    if raw in LOSS_TOKENS or compact in {"loss", "lost", "loser", "gradedloss"} or raw.startswith("loss ") or raw.endswith(" loss"):
        return "loss"
    if raw in VOID_TOKENS or compact in {"void", "voided", "noaction"}:
        return "void"
    if raw in CANCEL_TOKENS or compact in {"cancel", "canceled", "cancelled", "postponed"}:
        return "cancel"
    if raw in PUSH_TOKENS or compact in {"push", "pushed", "tie", "draw"}:
        return "push"
    if raw in UNKNOWN_TOKENS:
        return "unknown"
    if raw in PENDING_TOKENS:
        return "pending"
    return "unknown"


def status_from_row(row: Mapping[str, Any]) -> str:
    value = _first_value(row, RESULT_COLUMNS)
    return normalize_result_status(value) if value else "pending"


def normalized_event_name(row: Mapping[str, Any]) -> str:
    return re.sub(r"\s+", " ", _first_value(row, EVENT_COLUMNS)).strip().lower()


def unique_event_key(row: Mapping[str, Any]) -> str:
    sport = _token(_first_value(row, SPORT_COLUMNS))
    event = normalized_event_name(row)
    start = _token(_first_value(row, START_COLUMNS))
    return "|".join(part for part in (sport, event, start) if part)


def win_rate(wins: int, losses: int) -> float | None:
    return None if wins + losses == 0 else wins / (wins + losses)


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


@dataclass
class ResultSummary:
    rows: int = 0
    wins: int = 0
    losses: int = 0
    mixed: int = 0
    pushes: int = 0
    voids: int = 0
    cancels: int = 0
    pending: int = 0
    unknown: int = 0

    @property
    def completed(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float | None:
        return win_rate(self.wins, self.losses)

    def add_status(self, status: str) -> None:
        self.rows += 1
        if status == "win":
            self.wins += 1
        elif status == "loss":
            self.losses += 1
        elif status == "mixed":
            self.mixed += 1
        elif status == "push":
            self.pushes += 1
        elif status == "void":
            self.voids += 1
        elif status == "cancel":
            self.cancels += 1
        elif status == "unknown":
            self.unknown += 1
        else:
            self.pending += 1

    def as_report(self) -> dict[str, Any]:
        data = asdict(self)
        data["completed"] = self.completed
        data["win_rate"] = self.win_rate
        data["win_rate_display"] = _pct(self.win_rate)
        return data


@dataclass
class SimulationReport:
    dataset_name: str
    total_rows: int
    row_level: dict[str, Any]
    unique_event_level: dict[str, Any]
    duplicate_event_names: int
    duplicate_event_keys: int
    sport_level: dict[str, dict[str, Any]] = field(default_factory=dict)
    market_level: dict[str, dict[str, Any]] = field(default_factory=dict)
    prop_type_level: dict[str, dict[str, Any]] = field(default_factory=dict)
    candidate_patterns: list[dict[str, Any]] = field(default_factory=list)
    candidate_repairs: list[dict[str, Any]] = field(default_factory=list)
    accepted_simulated_repairs: list[dict[str, Any]] = field(default_factory=list)
    watchlist_patterns: list[dict[str, Any]] = field(default_factory=list)
    rejected_patterns: list[dict[str, Any]] = field(default_factory=list)
    grading_issues: list[str] = field(default_factory=list)
    duplicate_event_examples: list[dict[str, Any]] = field(default_factory=list)
    final_recommendation: str = "safe_to_code_phase_0_2_only"
    production_repairs_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def summarize_rows(rows: Iterable[Mapping[str, Any]]) -> ResultSummary:
    summary = ResultSummary()
    for row in rows:
        summary.add_status(status_from_row(row))
    return summary


def _group_summary(rows: list[Mapping[str, Any]], columns: Sequence[str]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        label = _first_value(row, columns) or "unknown"
        groups[label].append(row)
    return {key: summarize_rows(value).as_report() for key, value in sorted(groups.items())}


def summarize_unique_events(rows: list[Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, list[Mapping[str, Any]]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        key = unique_event_key(row) or f"missing-event-{len(grouped) + 1}"
        grouped[key].append(row)

    summary = ResultSummary()
    for event_rows in grouped.values():
        statuses = {status_from_row(row) for row in event_rows}
        if "win" in statuses and "loss" in statuses:
            summary.add_status("mixed")
        elif "loss" in statuses:
            summary.add_status("loss")
        elif "win" in statuses:
            summary.add_status("win")
        elif "push" in statuses:
            summary.add_status("push")
        elif "void" in statuses:
            summary.add_status("void")
        elif "cancel" in statuses:
            summary.add_status("cancel")
        elif "unknown" in statuses:
            summary.add_status("unknown")
        else:
            summary.add_status("pending")
    data = summary.as_report()
    data["unique_events"] = data.pop("rows")
    data["mixed_events"] = data.get("mixed", 0)
    return data, grouped


def _soccer_draw_trap_candidate(rows: list[Mapping[str, Any]]) -> dict[str, Any] | None:
    soccer_rows = []
    soccer_losses = 0
    draw_losses = 0
    for row in rows:
        sport_blob = " ".join(_token(_first_value(row, (column,))) for column in ("sport", "league", "competition"))
        if not any(hint in sport_blob for hint in SPORT_STYLE_HINTS):
            continue
        soccer_rows.append(row)
        if status_from_row(row) == "loss":
            soccer_losses += 1
            lowered = {str(key).strip().lower(): value for key, value in row.items()}
            note = _token(lowered.get("result_note") or lowered.get("notes") or lowered.get("explanation") or "")
            if "draw" in note or any(score in note for score in ("0-0", "1-1", "2-2", "3-3")):
                draw_losses += 1
    if not soccer_rows or soccer_losses == 0 or draw_losses == 0:
        return None
    return {
        "pattern_name": "soccer_draw_trap_watchlist",
        "pattern_type": "draw_trap",
        "status": "watchlist",
        "sample_size": len(soccer_rows),
        "soccer_losses": soccer_losses,
        "draw_losses": draw_losses,
        "draw_loss_share": draw_losses / soccer_losses,
        "rye_status": "watchlist_only",
        "recommendation": "Do not lower all soccer picks. Flag elevated soccer draw risk and suggest draw-no-bet/double-chance/reduced unit when supporting odds data exists.",
    }


def _combat_volatility_candidate(rows: list[Mapping[str, Any]]) -> dict[str, Any] | None:
    estimated = []
    combat_method = []
    for row in rows:
        prop = _token(_first_value(row, ("prop_type", "market", "bet_type")))
        sport = _token(_first_value(row, ("sport", "league")))
        if prop == "estimated score":
            estimated.append(row)
        if "round" in prop or "method" in prop or any(hint in sport for hint in COMBAT_HINTS):
            combat_method.append(row)
    if not estimated or not combat_method:
        return None
    estimated_summary = summarize_rows(estimated)
    combat_summary = summarize_rows(combat_method)
    if combat_summary.completed == 0 or estimated_summary.completed == 0:
        return None
    if (combat_summary.win_rate or 0) >= (estimated_summary.win_rate or 0):
        return None
    return {
        "pattern_name": "combat_round_method_volatility_watchlist",
        "pattern_type": "volatility",
        "status": "watchlist",
        "estimated_score_record": f"{estimated_summary.wins}-{estimated_summary.losses}",
        "estimated_score_win_rate": estimated_summary.win_rate,
        "round_method_record": f"{combat_summary.wins}-{combat_summary.losses}",
        "round_method_win_rate": combat_summary.win_rate,
        "rye_status": "watchlist_only",
        "recommendation": "Keep combat method/round picks playable only with confidence caps or reduced units until more sample size validates the pattern.",
    }


def detect_candidate_patterns(rows: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    patterns = [candidate for candidate in (_soccer_draw_trap_candidate(rows), _combat_volatility_candidate(rows)) if candidate]
    return patterns, list(patterns)


def build_simulation_report(rows: list[Mapping[str, Any]], dataset_name: str = "uploaded_rows") -> SimulationReport:
    row_summary = summarize_rows(rows).as_report()
    unique_summary, _ = summarize_unique_events(rows)
    event_name_counts = Counter(normalized_event_name(row) for row in rows if normalized_event_name(row))
    event_key_counts = Counter(unique_event_key(row) for row in rows if unique_event_key(row))
    duplicate_names = {key: value for key, value in event_name_counts.items() if value > 1}
    duplicate_keys = {key: value for key, value in event_key_counts.items() if value > 1}
    patterns, watchlist = detect_candidate_patterns(rows)

    grading_issues = []
    if row_summary["completed"] == 0:
        grading_issues.append("No completed win/loss rows were detected.")
    if row_summary["unknown"]:
        grading_issues.append(f"{row_summary['unknown']} row(s) are unknown and excluded from win/loss rate.")
    if row_summary["voids"]:
        grading_issues.append(f"{row_summary['voids']} void row(s) are excluded from win/loss rate.")
    if duplicate_names:
        grading_issues.append(f"{len(duplicate_names)} duplicate event name(s) need row-level vs unique-event review.")
    if unique_summary.get("mixed_events"):
        grading_issues.append(f"{unique_summary['mixed_events']} unique event(s) have mixed win/loss row outcomes and are excluded from unique-event win rate.")

    return SimulationReport(
        dataset_name=dataset_name,
        total_rows=len(rows),
        row_level=row_summary,
        unique_event_level=unique_summary,
        duplicate_event_names=len(duplicate_names),
        duplicate_event_keys=len(duplicate_keys),
        sport_level=_group_summary(rows, ("sport", "league")),
        market_level=_group_summary(rows, MARKET_COLUMNS),
        prop_type_level=_group_summary(rows, ("prop_type", "market", "bet_type")),
        candidate_patterns=patterns,
        watchlist_patterns=watchlist,
        duplicate_event_examples=[
            {"event": key, "row_count": count}
            for key, count in sorted(duplicate_names.items(), key=lambda item: (-item[1], item[0]))[:10]
        ],
        grading_issues=grading_issues,
    )


def simulate_csv(path: str | Path) -> SimulationReport:
    path = Path(path)
    return build_simulation_report(read_csv_rows(path), dataset_name=path.name)


def report_to_markdown(report: SimulationReport) -> str:
    row = report.row_level
    event = report.unique_event_level
    lines = [
        f"# ABA Adaptive Repair Simulation: {report.dataset_name}",
        "",
        "Production repairs active: **No**",
        "",
        "## Core counts",
        "",
        f"- Total rows: {report.total_rows}",
        f"- Completed row-level win/loss rows: {row['completed']}",
        f"- Row-level record: {row['wins']}-{row['losses']}",
        f"- Row-level win rate: {row['win_rate_display']}",
        f"- Unique events: {event['unique_events']}",
        f"- Unique-event record: {event['wins']}-{event['losses']}",
        f"- Unique-event win rate: {event['win_rate_display']}",
        f"- Mixed unique events: {event.get('mixed_events', event.get('mixed', 0))}",
        f"- Pushes: {row['pushes']}",
        f"- Voids: {row['voids']}",
        f"- Cancels: {row['cancels']}",
        f"- Pending: {row['pending']}",
        f"- Unknown: {row['unknown']}",
        f"- Duplicate event names: {report.duplicate_event_names}",
        f"- Duplicate event keys: {report.duplicate_event_keys}",
        "",
        "## Final recommendation",
        "",
        f"{report.final_recommendation}. Repairs remain inactive until later Shadow Mode validation.",
    ]
    if report.grading_issues:
        lines.extend(["", "## Grading/counting issues", ""])
        lines.extend(f"- {issue}" for issue in report.grading_issues)
    if report.watchlist_patterns:
        lines.extend(["", "## Watchlist patterns", ""])
        lines.extend(f"- {pattern['pattern_name']}: {pattern['recommendation']}" for pattern in report.watchlist_patterns)
    return "\n".join(lines) + "\n"
