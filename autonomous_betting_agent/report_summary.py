from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

REPORT_SUMMARY_FIELDS = [
    "report_summary_status",
    "report_summary_rows",
    "report_summary_unique_events",
    "report_summary_playable_count",
    "report_summary_watchlist_count",
    "report_summary_prediction_only_count",
    "report_summary_blocked_count",
    "report_summary_top_blockers",
    "report_summary_top_warnings",
    "report_summary_source_summary",
    "report_summary_market_summary",
    "report_summary_clv_summary",
    "report_summary_validation_summary",
    "report_summary_safety_notes",
]

SAFETY_NOTES = (
    "Report-only summary. No backend/server, database, scheduler, auth/login, billing, "
    "live betting, auto-betting, bankroll/staking change, proof mutation, result/grading "
    "mutation, model training, or official lock change is performed."
)

STATUS_COLUMNS = (
    "advisory_status", "report_summary_status", "official_status_label",
    "official_publish_status", "publish_status", "report_lane", "report_lane_v2",
    "recommended_action", "consumer_action", "public_action", "learning_status",
)
BLOCKER_COLUMNS = (
    "data_issue_reason", "blocked_reason", "blocker", "blockers",
    "advisory_blocker", "advisory_blockers", "candidate_blocker",
    "candidate_blockers", "market_blocker", "schema_mapper_missing_required_fields",
)
WARNING_COLUMNS = (
    "warning", "warnings", "advisory_warning", "advisory_warnings",
    "candidate_warning", "candidate_warnings", "correlation_warning",
    "market_warning", "risk_warning", "validation_warning",
)
EXPLANATION_COLUMNS = (
    "explanation", "explanation_summary", "client_safe_explanation",
    "pick_explanation", "rationale", "why_pick", "pattern_summary",
    "sports_context_summary", "api_context_summary",
)
SOURCE_COLUMNS = ("sportsbook", "bookmaker", "odds_source", "source", "source_file", "api_source")
MARKET_COLUMNS = ("market_type", "market", "market_name")
MARKET_COMPLETENESS_COLUMNS = (
    "market_completeness_status", "market_coverage_status", "market_complete",
    "has_all_market_sides", "missing_market_sides",
)
CLV_COLUMNS = (
    "manual_clv", "manual_clv_status", "manual_clv_summary", "manual_clv_notes",
    "clv", "clv_delta", "closing_line_value", "clv_result",
)
VALIDATION_COLUMNS = (
    "validation_status", "validation_summary", "schema_mapper_status", "odds_verified",
    "odds_validation_status", "market_validation_status", "data_issue_reason",
)
THRESHOLD_COLUMNS = (
    "threshold_status", "threshold_summary", "edge_threshold_status",
    "ev_threshold_status", "confidence_threshold_status", "model_probability",
    "model_market_edge", "expected_value_per_unit",
)
CANDIDATE_REVIEW_COLUMNS = (
    "manual_candidate_status", "candidate_review_status", "manual_review_status",
    "candidate_status", "review_status",
)
FRESH_SLATE_COLUMNS = (
    "fresh_slate_ready", "fresh_slate_status", "ready_for_fresh_slate",
    "schema_mapper_ready_for_advisory_pipeline",
)

_PLAYABLE_MARKERS = ("playable", "best play", "official +ev", "official ev", "publish ready", "client ready", "green")
_WATCHLIST_MARKERS = ("watchlist", "price watch", "watch", "monitor", "seguimiento")
_PREDICTION_ONLY_MARKERS = ("prediction only", "prediction-only", "research", "learning", "analysis only", "informational", "not official")
_BLOCKED_MARKERS = ("blocked", "no play", "removed", "do not play", "not playable", "red flag", "unsafe", "missing")
_TRUE_VALUES = {"1", "true", "yes", "y", "ready", "published", "pass", "passed", "complete", "completed"}
_FALSE_VALUES = {"0", "false", "no", "n", "", "none", "nan", "null", "nat"}


@dataclass(frozen=True)
class ReportSummaryBundle:
    rows: pd.DataFrame
    table: dict[str, Any]
    markdown: str
    csv_text: str


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in _FALSE_VALUES else text


def _lower(value: Any) -> str:
    return _text(value).lower()


def _truthy(value: Any) -> bool:
    return _lower(value) in _TRUE_VALUES


def _to_float(value: Any) -> float | None:
    text = _text(value)
    if not text:
        return None
    try:
        return float(text.replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def _first_present(row: Mapping[str, Any], columns: Sequence[str]) -> str:
    for column in columns:
        value = _text(row.get(column))
        if value:
            return value
    return ""


def _row_text(row: Mapping[str, Any], columns: Sequence[str]) -> str:
    return " | ".join(_text(row.get(column)) for column in columns if _text(row.get(column)))


def _has_marker(row: Mapping[str, Any], columns: Sequence[str], markers: Sequence[str]) -> bool:
    text = _row_text(row, columns).lower()
    return any(marker in text for marker in markers)


def _split_notes(value: Any) -> list[str]:
    text = _text(value)
    if not text:
        return []
    for sep in ("|", ";", "\n"):
        text = text.replace(sep, ",")
    return [part.strip() for part in text.split(",") if part.strip()]


def _collect_notes(rows: Iterable[Mapping[str, Any]], columns: Sequence[str]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        for column in columns:
            for note in _split_notes(row.get(column)):
                counter[note] += 1
    return counter


def _top(counter: Counter[str], limit: int = 5) -> str:
    if not counter:
        return "none"
    return "; ".join(f"{name} ({count})" for name, count in counter.most_common(limit))


def _count_values(rows: Iterable[Mapping[str, Any]], columns: Sequence[str], limit: int = 6) -> str:
    counter: Counter[str] = Counter()
    for row in rows:
        value = _first_present(row, columns)
        if value:
            counter[value] += 1
    return _top(counter, limit=limit)


def _event_key(row: Mapping[str, Any]) -> str:
    return _first_present(row, ("public_event", "event", "event_name", "matchup", "game", "fixture"))


def _is_playable(row: Mapping[str, Any]) -> bool:
    if _truthy(row.get("official_publish_ready")) or _truthy(row.get("publish_ready")) or _truthy(row.get("client_report_ready")):
        return True
    return _has_marker(row, STATUS_COLUMNS, _PLAYABLE_MARKERS)


def _is_watchlist(row: Mapping[str, Any]) -> bool:
    return _has_marker(row, STATUS_COLUMNS, _WATCHLIST_MARKERS)


def _is_prediction_only(row: Mapping[str, Any]) -> bool:
    return _has_marker(row, STATUS_COLUMNS, _PREDICTION_ONLY_MARKERS)


def _is_blocked(row: Mapping[str, Any]) -> bool:
    if _truthy(row.get("tennis_blocked")) or _truthy(row.get("blocked")):
        return True
    if _row_text(row, BLOCKER_COLUMNS):
        return True
    return _has_marker(row, STATUS_COLUMNS, _BLOCKED_MARKERS)


def _fresh_slate_summary(rows: list[Mapping[str, Any]]) -> str:
    if not rows:
        return "No report rows available for fresh slate readiness review."
    ready = sum(any(_truthy(row.get(column)) for column in FRESH_SLATE_COLUMNS) for row in rows)
    statuses = _count_values(rows, FRESH_SLATE_COLUMNS)
    if statuses != "none":
        return f"Fresh slate fields found: {statuses}; ready rows: {ready}/{len(rows)}."
    return "Fresh slate readiness fields were not present; export remains report-only."


def _threshold_summary(rows: list[Mapping[str, Any]]) -> str:
    statuses = _count_values(rows, THRESHOLD_COLUMNS)
    if statuses != "none":
        return statuses
    probabilities = [_to_float(row.get("model_probability")) for row in rows]
    probabilities = [value for value in probabilities if value is not None]
    if probabilities:
        return f"model_probability present on {len(probabilities)} rows; average={sum(probabilities) / len(probabilities):.3f}"
    return "No threshold fields present."


def _explanation_summary(rows: list[Mapping[str, Any]]) -> str:
    explained = 0
    first = ""
    for row in rows:
        value = _first_present(row, EXPLANATION_COLUMNS)
        if value:
            explained += 1
            if not first:
                first = value[:180]
    if not rows:
        return "No rows available for explanation summary."
    if not explained:
        return "No explanation/rationale fields were present."
    return f"Explanation fields present on {explained}/{len(rows)} rows. First explanation: {first}"


def _market_summary(rows: list[Mapping[str, Any]]) -> str:
    markets = _count_values(rows, MARKET_COLUMNS)
    completeness = _count_values(rows, MARKET_COMPLETENESS_COLUMNS)
    missing_side_rows = sum(bool(_text(row.get("missing_market_sides"))) for row in rows)
    parts = [f"markets: {markets}"]
    if completeness != "none":
        parts.append(f"completeness: {completeness}")
    if missing_side_rows:
        parts.append(f"rows with missing market sides: {missing_side_rows}")
    return "; ".join(parts)


def _clv_summary(rows: list[Mapping[str, Any]]) -> str:
    statuses = _count_values(rows, CLV_COLUMNS)
    values: list[float] = []
    for row in rows:
        for column in ("manual_clv", "clv", "clv_delta", "closing_line_value"):
            value = _to_float(row.get(column))
            if value is not None:
                values.append(value)
                break
    if values:
        avg = sum(values) / len(values)
        return f"manual/available CLV values on {len(values)} rows; average={avg:.3f}; statuses: {statuses}"
    if statuses != "none":
        return statuses
    return "No manual CLV fields present."


def _validation_summary(rows: list[Mapping[str, Any]]) -> str:
    statuses = _count_values(rows, VALIDATION_COLUMNS)
    verified = sum(_truthy(row.get("odds_verified")) for row in rows)
    if statuses == "none" and not verified:
        return "No validation fields present."
    return f"{statuses}; odds_verified={verified}/{len(rows)}"


def _status_from_counts(total: int, playable: int, watchlist: int, blocked: int) -> str:
    if total == 0:
        return "NO_REPORT_ROWS"
    if blocked >= total:
        return "ALL_ROWS_BLOCKED"
    if playable:
        return "REPORT_READY_WITH_PLAYABLE_ROWS"
    if watchlist:
        return "WATCHLIST_ONLY"
    return "PREDICTION_ONLY_OR_RESEARCH"


def build_report_summary_table(frame: pd.DataFrame | Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    if frame is None:
        source = pd.DataFrame()
    elif isinstance(frame, pd.DataFrame):
        source = frame.copy(deep=True)
    else:
        source = pd.DataFrame(list(frame))
    rows = [dict(row) for _, row in source.iterrows()]
    row_count = int(len(rows))
    event_keys = {_event_key(row) for row in rows if _event_key(row)}
    playable = sum(_is_playable(row) for row in rows)
    watchlist = sum(_is_watchlist(row) for row in rows)
    prediction_only = sum(_is_prediction_only(row) for row in rows)
    blocked = sum(_is_blocked(row) for row in rows)
    return {
        "report_summary_status": _status_from_counts(row_count, playable, watchlist, blocked),
        "report_summary_rows": row_count,
        "report_summary_unique_events": len(event_keys) if event_keys else row_count,
        "report_summary_playable_count": int(playable),
        "report_summary_watchlist_count": int(watchlist),
        "report_summary_prediction_only_count": int(prediction_only),
        "report_summary_blocked_count": int(blocked),
        "report_summary_top_blockers": _top(_collect_notes(rows, BLOCKER_COLUMNS)),
        "report_summary_top_warnings": _top(_collect_notes(rows, WARNING_COLUMNS)),
        "report_summary_source_summary": _count_values(rows, SOURCE_COLUMNS),
        "report_summary_market_summary": _market_summary(rows),
        "report_summary_clv_summary": _clv_summary(rows),
        "report_summary_validation_summary": _validation_summary(rows),
        "report_summary_safety_notes": SAFETY_NOTES,
        "fresh_slate_readiness_summary": _fresh_slate_summary(rows),
        "advisory_status_counts": _count_values(rows, STATUS_COLUMNS),
        "threshold_summary": _threshold_summary(rows),
        "explanation_summary": _explanation_summary(rows),
        "manual_candidate_review_summary": _count_values(rows, CANDIDATE_REVIEW_COLUMNS) if _count_values(rows, CANDIDATE_REVIEW_COLUMNS) != "none" else "No manual candidate review fields present.",
    }


def append_report_summary_columns(frame: pd.DataFrame | Sequence[Mapping[str, Any]] | None) -> pd.DataFrame:
    if frame is None:
        output = pd.DataFrame(columns=REPORT_SUMMARY_FIELDS)
    elif isinstance(frame, pd.DataFrame):
        output = frame.copy(deep=True)
    else:
        output = pd.DataFrame(list(frame))
    summary = build_report_summary_table(output)
    if output.empty:
        return pd.DataFrame([{field: summary[field] for field in REPORT_SUMMARY_FIELDS}])
    for field in REPORT_SUMMARY_FIELDS:
        output[field] = summary[field]
    return output


def render_report_summary_markdown(table: Mapping[str, Any]) -> str:
    return "\n".join([
        "## Executive Summary",
        f"- Status: {table.get('report_summary_status')}",
        f"- Rows: {table.get('report_summary_rows')} | Unique events: {table.get('report_summary_unique_events')}",
        f"- Playable: {table.get('report_summary_playable_count')} | Watchlist: {table.get('report_summary_watchlist_count')} | Prediction-only: {table.get('report_summary_prediction_only_count')} | Blocked: {table.get('report_summary_blocked_count')}",
        "", "## Fresh Slate Readiness Summary", f"- {table.get('fresh_slate_readiness_summary')}",
        "", "## Advisory Status Counts", f"- {table.get('advisory_status_counts')}",
        "", "## Threshold Summary", f"- {table.get('threshold_summary')}",
        "", "## Explanation Summary", f"- {table.get('explanation_summary')}",
        "", "## Top Blockers", f"- {table.get('report_summary_top_blockers')}",
        "", "## Top Warnings", f"- {table.get('report_summary_top_warnings')}",
        "", "## Sportsbook Source Summary", f"- {table.get('report_summary_source_summary')}",
        "", "## Market Completeness Summary", f"- {table.get('report_summary_market_summary')}",
        "", "## Manual Candidate Review Summary", f"- {table.get('manual_candidate_review_summary')}",
        "", "## Manual CLV Summary", f"- {table.get('report_summary_clv_summary')}",
        "", "## Validation Summary", f"- {table.get('report_summary_validation_summary')}",
        "", "## Row-Level Appendix / Export", f"- CSV/JSON row export includes: {', '.join(REPORT_SUMMARY_FIELDS)}",
        "", "## Safety Notes", f"- {table.get('report_summary_safety_notes')}",
    ]).strip() + "\n"


def build_report_summary_bundle(frame: pd.DataFrame | Sequence[Mapping[str, Any]] | None) -> ReportSummaryBundle:
    table = build_report_summary_table(frame)
    rows = append_report_summary_columns(frame)
    return ReportSummaryBundle(rows=rows, table=table, markdown=render_report_summary_markdown(table), csv_text=rows.to_csv(index=False))
