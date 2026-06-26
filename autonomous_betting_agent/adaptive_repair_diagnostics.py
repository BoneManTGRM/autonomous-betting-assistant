"""Enhanced diagnostics for ABA Adaptive Repair Engine Phase 0-2.

This module keeps the first Adaptive Repair stage safe. It adds data-quality,
column-coverage, exact duplicate-row, and same-event diagnostics around the
base simulation report without activating repairs or changing live picks.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.adaptive_repair_engine import (
    EVENT_COLUMNS,
    MARKET_COLUMNS,
    RESULT_COLUMNS,
    SPORT_COLUMNS,
    build_simulation_report,
    read_csv_rows,
    report_to_markdown,
    status_from_row,
    unique_event_key,
)

ODDS_COLUMNS = ("odds", "american_odds", "decimal_odds", "price", "line_price", "book_odds")
CLOSING_ODDS_COLUMNS = ("closing_odds", "close_odds", "closing_price", "closing_line", "clv_close")
CONFIDENCE_COLUMNS = ("confidence", "confidence_score", "model_confidence", "probability", "win_probability")
EDGE_COLUMNS = ("edge", "edge_score", "expected_value", "ev", "value_score")
START_COLUMNS = ("event_start_time", "known_start_utc", "start_time", "commence_time", "game_time", "date")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _token(value: Any) -> str:
    return " ".join(_text(value).lower().replace("_", " ").replace("-", " ").split())


def _lowered_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key).strip().lower(): value for key, value in row.items()}


def _first_value(row: Mapping[str, Any], columns: Sequence[str]) -> str:
    lowered = _lowered_row(row)
    for column in columns:
        value = _text(lowered.get(column.lower()))
        if value:
            return value
    return ""


def _matched_column(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> str | None:
    available = {str(key).strip().lower() for row in rows for key in row.keys()}
    for column in columns:
        if column.lower() in available:
            return column
    return None


def _non_empty_count(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> int:
    return sum(1 for row in rows if _first_value(row, columns))


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def row_fingerprint(row: Mapping[str, Any]) -> str:
    """Stable exact-row fingerprint for duplicate-row detection."""
    return "|".join(
        f"{_token(key)}={_token(value)}"
        for key, value in sorted(row.items(), key=lambda item: str(item[0]).lower())
    )


def column_coverage(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    fields = {
        "result": RESULT_COLUMNS,
        "event": EVENT_COLUMNS,
        "start_time": START_COLUMNS,
        "sport": SPORT_COLUMNS,
        "market": MARKET_COLUMNS,
        "odds": ODDS_COLUMNS,
        "closing_odds": CLOSING_ODDS_COLUMNS,
        "confidence": CONFIDENCE_COLUMNS,
        "edge": EDGE_COLUMNS,
    }
    total = len(rows)
    coverage: dict[str, dict[str, Any]] = {}
    for name, columns in fields.items():
        non_empty = _non_empty_count(rows, columns)
        rate = None if total == 0 else non_empty / total
        coverage[name] = {
            "matched_column": _matched_column(rows, columns),
            "non_empty_rows": non_empty,
            "coverage_rate": rate,
            "coverage_display": _pct(rate),
        }
    return coverage


def duplicate_row_details(rows: Sequence[Mapping[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    fingerprints = Counter(row_fingerprint(row) for row in rows)
    duplicates = {fingerprint: count for fingerprint, count in fingerprints.items() if count > 1}
    examples = []
    for fingerprint, count in sorted(duplicates.items(), key=lambda item: (-item[1], item[0]))[:10]:
        example_row = next(row for row in rows if row_fingerprint(row) == fingerprint)
        examples.append(
            {
                "row_count": count,
                "event": _first_value(example_row, EVENT_COLUMNS),
                "sport": _first_value(example_row, SPORT_COLUMNS),
                "result": _first_value(example_row, RESULT_COLUMNS),
            }
        )
    duplicate_extra_rows = sum(count - 1 for count in duplicates.values())
    return duplicate_extra_rows, examples


def same_event_group_details(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        key = unique_event_key(row) or f"missing-event-{len(grouped) + 1}"
        grouped[key].append(row)

    groups = []
    for event_key_value, event_rows in grouped.items():
        if len(event_rows) <= 1:
            continue
        statuses = sorted({status_from_row(row) for row in event_rows})
        markets = sorted({_first_value(row, MARKET_COLUMNS) or "unknown" for row in event_rows})
        first = event_rows[0]
        groups.append(
            {
                "event_key": event_key_value,
                "event": _first_value(first, EVENT_COLUMNS),
                "row_count": len(event_rows),
                "statuses": statuses,
                "markets": markets,
                "mixed_outcome": len(statuses) > 1,
                "multi_market": len(markets) > 1,
            }
        )
    return sorted(groups, key=lambda item: (-item["row_count"], item["event_key"]))[:20]


def missing_required_field_examples(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    examples = []
    for index, row in enumerate(rows, start=1):
        missing = []
        if not _first_value(row, EVENT_COLUMNS):
            missing.append("event")
        if not _first_value(row, RESULT_COLUMNS):
            missing.append("result")
        if not _first_value(row, SPORT_COLUMNS):
            missing.append("sport")
        if missing:
            examples.append({"row_number": index, "missing": missing, "event": _first_value(row, EVENT_COLUMNS)})
        if len(examples) >= 10:
            break
    return examples


def compute_data_quality(
    rows: Sequence[Mapping[str, Any]],
    row_level: Mapping[str, Any],
    coverage: Mapping[str, Mapping[str, Any]],
    duplicate_rows: int,
    duplicate_event_names: int,
) -> dict[str, Any]:
    total = max(len(rows), 1)
    score = 100.0
    penalties = []

    for field_name in ("result", "event", "sport"):
        missing_rate = 1.0 - float(coverage[field_name]["coverage_rate"] or 0.0)
        if missing_rate > 0:
            penalty = min(25.0, missing_rate * 25.0)
            score -= penalty
            penalties.append(f"{field_name} missing on {missing_rate:.1%} of rows (-{penalty:.1f})")

    non_completed = sum(
        int(row_level.get(key, 0))
        for key in ("pushes", "voids", "cancels", "pending", "unknown")
    )
    if non_completed:
        penalty = min(20.0, (non_completed / total) * 20.0)
        score -= penalty
        penalties.append(f"{non_completed} non-win/loss row(s) excluded from win rate (-{penalty:.1f})")

    if duplicate_rows:
        penalty = min(15.0, (duplicate_rows / total) * 30.0)
        score -= penalty
        penalties.append(f"{duplicate_rows} exact duplicate extra row(s) detected (-{penalty:.1f})")

    if duplicate_event_names:
        penalty = min(10.0, (duplicate_event_names / total) * 10.0)
        score -= penalty
        penalties.append(f"{duplicate_event_names} duplicate event name(s) require event-level review (-{penalty:.1f})")

    if not coverage["odds"]["matched_column"]:
        score -= 5.0
        penalties.append("odds column missing; ROI and value simulation limited (-5.0)")
    if not coverage["closing_odds"]["matched_column"]:
        score -= 5.0
        penalties.append("closing odds column missing; CLV simulation unavailable (-5.0)")
    if not coverage["confidence"]["matched_column"]:
        score -= 5.0
        penalties.append("confidence column missing; calibration simulation unavailable (-5.0)")

    score = max(0.0, min(100.0, score))
    if score >= 85:
        status = "high"
    elif score >= 70:
        status = "medium"
    elif score >= 50:
        status = "low"
    else:
        status = "needs_review"

    return {
        "score": round(score, 2),
        "status": status,
        "penalties": penalties,
        "repairs_allowed": False,
        "shadow_mode_allowed": status in {"high", "medium"},
        "notes": "Phase 0-2 never activates production repairs. This score only determines readiness for later Shadow Mode.",
    }


@dataclass
class EnhancedSimulationDiagnostics:
    base_report: dict[str, Any]
    data_quality: dict[str, Any]
    column_coverage: dict[str, dict[str, Any]]
    duplicate_rows: int
    duplicate_row_examples: list[dict[str, Any]] = field(default_factory=list)
    same_event_groups: list[dict[str, Any]] = field(default_factory=list)
    missing_required_field_examples: list[dict[str, Any]] = field(default_factory=list)
    production_repairs_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def build_enhanced_diagnostics(rows: list[Mapping[str, Any]], dataset_name: str = "uploaded_rows") -> EnhancedSimulationDiagnostics:
    base = build_simulation_report(rows, dataset_name=dataset_name)
    coverage = column_coverage(rows)
    duplicate_rows, duplicate_examples = duplicate_row_details(rows)
    data_quality = compute_data_quality(
        rows=rows,
        row_level=base.row_level,
        coverage=coverage,
        duplicate_rows=duplicate_rows,
        duplicate_event_names=base.duplicate_event_names,
    )
    return EnhancedSimulationDiagnostics(
        base_report=base.to_dict(),
        data_quality=data_quality,
        column_coverage=coverage,
        duplicate_rows=duplicate_rows,
        duplicate_row_examples=duplicate_examples,
        same_event_groups=same_event_group_details(rows),
        missing_required_field_examples=missing_required_field_examples(rows),
        production_repairs_active=False,
    )


def simulate_csv_diagnostics(path: str | Path) -> EnhancedSimulationDiagnostics:
    path = Path(path)
    return build_enhanced_diagnostics(read_csv_rows(path), dataset_name=path.name)


def diagnostics_to_markdown(diagnostics: EnhancedSimulationDiagnostics) -> str:
    base = diagnostics.base_report
    event = base["unique_event_level"]
    quality = diagnostics.data_quality
    lines = [
        report_to_markdown(build_simulation_report_from_dict(base)).rstrip(),
        "",
        "## Enhanced data-quality diagnostics",
        "",
        f"- Data-quality score: {quality['score']}",
        f"- Data-quality status: {quality['status']}",
        f"- Shadow Mode allowed later: {quality['shadow_mode_allowed']}",
        f"- Production repairs allowed now: {quality['repairs_allowed']}",
        f"- Exact duplicate extra rows: {diagnostics.duplicate_rows}",
        f"- Mixed-outcome unique events: {event.get('mixed_outcome_events', 0)}",
        f"- Multi-market unique events: {event.get('multi_market_events', 0)}",
        "",
        "## Column coverage",
        "",
    ]
    for field_name, details in diagnostics.column_coverage.items():
        matched = details.get("matched_column") or "missing"
        lines.append(f"- {field_name}: {details.get('coverage_display')} via `{matched}`")
    if quality.get("penalties"):
        lines.extend(["", "## Data-quality penalties", ""])
        lines.extend(f"- {penalty}" for penalty in quality["penalties"])
    if diagnostics.same_event_groups:
        lines.extend(["", "## Same-event review examples", ""])
        lines.extend(
            f"- {group['event'] or group['event_key']}: {group['row_count']} rows, statuses={group['statuses']}, markets={group['markets']}"
            for group in diagnostics.same_event_groups[:10]
        )
    if diagnostics.missing_required_field_examples:
        lines.extend(["", "## Missing required field examples", ""])
        lines.extend(
            f"- Row {item['row_number']}: missing {', '.join(item['missing'])}"
            for item in diagnostics.missing_required_field_examples
        )
    lines.extend(
        [
            "",
            "## Safety state",
            "",
            "Production repairs remain inactive. Enhanced diagnostics only improve simulation review and later Shadow Mode readiness.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_simulation_report_from_dict(data: Mapping[str, Any]):
    """Rehydrate enough of the base dataclass for existing Markdown rendering."""
    from autonomous_betting_agent.adaptive_repair_engine import SimulationReport

    allowed = set(SimulationReport.__dataclass_fields__.keys())
    return SimulationReport(**{key: value for key, value in data.items() if key in allowed})
