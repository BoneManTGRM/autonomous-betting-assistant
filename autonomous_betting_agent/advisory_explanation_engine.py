from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Mapping, Sequence

import pandas as pd

EXPLAINED_PLAYABLE_PLUS_EV = "EXPLAINED_PLAYABLE_PLUS_EV"
EXPLAINED_WATCHLIST_VALUE = "EXPLAINED_WATCHLIST_VALUE"
EXPLAINED_PREDICTION_ONLY = "EXPLAINED_PREDICTION_ONLY"
EXPLAINED_BLOCKED = "EXPLAINED_BLOCKED"
EXPLAINED_STALE_OR_HISTORICAL = "EXPLAINED_STALE_OR_HISTORICAL"
EXPLAINED_SOURCE_BLOCKED = "EXPLAINED_SOURCE_BLOCKED"
EXPLAINED_MARKET_INCOMPLETE = "EXPLAINED_MARKET_INCOMPLETE"
EXPLAINED_NO_VIG_UNAVAILABLE = "EXPLAINED_NO_VIG_UNAVAILABLE"
EXPLAINED_THRESHOLD_DOWNGRADED = "EXPLAINED_THRESHOLD_DOWNGRADED"
EXPLAINED_SHADOW_UNDERTRAINED = "EXPLAINED_SHADOW_UNDERTRAINED"
EXPLAINED_UNKNOWN = "EXPLAINED_UNKNOWN"

PLAYABLE_PLUS_EV = "PLAYABLE_PLUS_EV"
WATCHLIST_VALUE = "WATCHLIST_VALUE"
PREDICTION_ONLY_NOT_PLUS_EV = "PREDICTION_ONLY_NOT_PLUS_EV"
COMPLETE_MARKET = "COMPLETE_MARKET"

EXPLANATION_COLUMNS = [
    "advisory_explanation_status",
    "advisory_explanation_summary",
    "advisory_explanation_primary_reason",
    "advisory_explanation_reason_codes",
    "advisory_explanation_supporting_factors",
    "advisory_explanation_blockers",
    "advisory_explanation_warnings",
    "advisory_explanation_next_action",
    "advisory_explanation_confidence_notes",
    "advisory_explanation_source_notes",
    "advisory_explanation_market_notes",
    "advisory_explanation_threshold_notes",
    "advisory_explanation_shadow_notes",
    "advisory_explanation_safety_notes",
]


def _records(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame | None) -> list[dict[str, Any]]:
    if rows_or_frame is None:
        return []
    if isinstance(rows_or_frame, pd.DataFrame):
        return rows_or_frame.to_dict("records")
    return [deepcopy(dict(row)) for row in rows_or_frame if isinstance(row, Mapping)]


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"none", "nan", "null", "nat"} else text


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"true", "1", "yes", "y", "available"}


def _csv(values: Sequence[str]) -> str:
    return ",".join(dict.fromkeys([value for value in values if value]))


def _status(row: Mapping[str, Any]) -> str:
    return _text(row.get("advisory_calibrated_playable_status")) or _text(row.get("advisory_playable_status"))


def _original_status(row: Mapping[str, Any]) -> str:
    return _text(row.get("advisory_original_playable_status_before_thresholds")) or _text(row.get("advisory_playable_status"))


def _is_stale_or_historical(row: Mapping[str, Any]) -> bool:
    stale = _text(row.get("advisory_stale_line_status"))
    reason = _text(row.get("advisory_stale_line_reason")) or _text(row.get("advisory_playable_reason"))
    return stale in {"STALE", "EVENT_STARTED", "HISTORICAL_ROW"} or reason == "event_start_time_is_not_future"


def _is_source_blocked(row: Mapping[str, Any]) -> bool:
    source_type = _text(row.get("advisory_sportsbook_source_type"))
    return source_type in {"CONSENSUS_ONLY", "UNKNOWN_SOURCE"} or _truthy(row.get("advisory_is_consensus_source"))


def _is_market_incomplete(row: Mapping[str, Any]) -> bool:
    completeness = _text(row.get("advisory_market_completeness_status"))
    return bool(completeness and completeness != COMPLETE_MARKET)


def _is_no_vig_unavailable(row: Mapping[str, Any]) -> bool:
    if "advisory_no_vig_available" not in row:
        return False
    return not _truthy(row.get("advisory_no_vig_available"))


def _is_blocked(row: Mapping[str, Any]) -> bool:
    status = _status(row)
    reason = _text(row.get("advisory_playable_reason"))
    return status.startswith("BLOCKED") or reason in {"missing_decimal_odds", "invalid_model_probability", "event_start_time_is_not_future"}


def _is_threshold_adjusted(row: Mapping[str, Any]) -> bool:
    original = _original_status(row)
    calibrated = _text(row.get("advisory_calibrated_playable_status"))
    if not original or not calibrated:
        return False
    return original != calibrated or bool(_text(row.get("advisory_threshold_failed_reasons")))


def _shadow_note(row: Mapping[str, Any], codes: list[str]) -> str:
    shadow_status = _text(row.get("advisory_shadow_readiness_status"))
    if not shadow_status:
        return "Shadow/model readiness fields were not present on this row."
    if shadow_status == "SHADOW_READY":
        codes.append("shadow_ready")
    else:
        codes.append("shadow_undertrained")
    if _truthy(row.get("advisory_shadow_observation_only")):
        codes.append("shadow_observation_only")
    score = _text(row.get("advisory_shadow_readiness_score"))
    guidance = _text(row.get("advisory_shadow_training_guidance"))
    return f"Shadow/model readiness: {shadow_status}; score={score or 'unknown'}; guidance={guidance or 'none'}; live mutation allowed=False."


def advisory_next_action_for_row(row: Mapping[str, Any]) -> str:
    if _is_stale_or_historical(row):
        return "Use a fresh future-event slate with current odds."
    if _is_source_blocked(row):
        return "Use real sportsbook/bookmaker prices instead of consensus or unknown sources."
    if _is_market_incomplete(row):
        return "Add complete same-sportsbook market sides before no-vig review."
    if _is_no_vig_unavailable(row):
        return "Provide enough paired market sides for no-vig probability."
    if _is_blocked(row):
        return "Fix the blocked data issue before advisory value review."
    if _is_threshold_adjusted(row):
        return "Review failed threshold reasons and keep this advisory-only."
    status = _status(row)
    if status == PLAYABLE_PLUS_EV:
        return "Review as an advisory-only value candidate."
    if status == WATCHLIST_VALUE:
        return "Keep on watchlist until value, price, freshness, and market quality improve."
    if status == PREDICTION_ONLY_NOT_PLUS_EV:
        return "Treat as prediction-only unless the market price improves."
    return "Run the advisory value pipeline or upload a complete advisory CSV."


def explain_advisory_row(row: Mapping[str, Any]) -> dict[str, Any]:
    item = deepcopy(dict(row))
    codes: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []
    factors: list[str] = []

    status = _status(item)
    original = _original_status(item)
    calibrated = _text(item.get("advisory_calibrated_playable_status"))
    source_type = _text(item.get("advisory_sportsbook_source_type"))
    completeness = _text(item.get("advisory_market_completeness_status"))
    no_vig = _truthy(item.get("advisory_no_vig_available")) if "advisory_no_vig_available" in item else None
    missing = [field for field in ["advisory_playable_status", "advisory_sportsbook_source_type", "advisory_market_completeness_status"] if field not in item]

    if source_type == "REAL_SPORTSBOOK" or _truthy(item.get("advisory_is_real_sportsbook")):
        codes.append("real_sportsbook_source_confirmed")
        factors.append("Real sportsbook source detected.")
    if source_type == "CONSENSUS_ONLY" or _truthy(item.get("advisory_is_consensus_source")):
        codes.append("consensus_only_source")
        blockers.append("Consensus-only source cannot become playable.")
    if source_type == "UNKNOWN_SOURCE":
        codes.append("unknown_sportsbook_source")
        blockers.append("Sportsbook source is unknown.")
    if completeness == COMPLETE_MARKET:
        codes.append("complete_market_confirmed")
        factors.append("Complete same-sportsbook market detected.")
    elif completeness:
        codes.append("incomplete_market")
        blockers.append(_text(item.get("advisory_no_vig_blocker_reason")) or "Market is incomplete.")
    if no_vig is True:
        codes.append("no_vig_available")
        factors.append("No-vig probability is available.")
    elif no_vig is False:
        codes.append("no_vig_unavailable")
        blockers.append(_text(item.get("advisory_no_vig_blocker_reason")) or "No-vig probability is unavailable.")
    if _text(item.get("advisory_threshold_failed_reasons")):
        codes.append("threshold_failed")
        warnings.append(_text(item.get("advisory_threshold_failed_reasons")))
    elif "advisory_threshold_passed" in item and _truthy(item.get("advisory_threshold_passed")):
        codes.append("threshold_passed")
        factors.append("Configured advisory thresholds passed.")
    if original and calibrated and original != calibrated:
        codes.append("threshold_adjusted")
        codes.append("threshold_downgraded")
        warnings.append(f"Original status {original} changed to calibrated status {calibrated}.")
    duplicate = _text(item.get("advisory_duplicate_event_status"))
    conflict = _text(item.get("advisory_conflict_status"))
    if (duplicate and duplicate != "UNIQUE_EVENT") or (conflict and conflict != "NO_CONFLICT"):
        codes.append("duplicate_conflict_warning")
        warnings.append("Duplicate or conflict warning is present.")

    shadow_notes = _shadow_note(item, codes)
    if "shadow_undertrained" in codes:
        warnings.append("Shadow/model readiness is not fully ready; this is context only.")

    if _is_stale_or_historical(item):
        explanation_status = EXPLAINED_STALE_OR_HISTORICAL
        primary = "stale_or_historical_event"
        codes.append(primary)
        summary = "This row is explained as stale or historical because the event/line is not a fresh future advisory slate."
    elif _is_source_blocked(item):
        explanation_status = EXPLAINED_SOURCE_BLOCKED
        primary = "source_blocked"
        summary = "This row is source-blocked because the sportsbook source is consensus-only or unknown."
    elif _is_market_incomplete(item):
        explanation_status = EXPLAINED_MARKET_INCOMPLETE
        primary = "incomplete_market"
        summary = "This row is blocked because the market is incomplete for same-sportsbook no-vig review."
    elif _is_no_vig_unavailable(item):
        explanation_status = EXPLAINED_NO_VIG_UNAVAILABLE
        primary = "no_vig_unavailable"
        summary = "This row is blocked because no-vig probability is unavailable."
    elif _is_blocked(item):
        explanation_status = EXPLAINED_BLOCKED
        primary = _text(item.get("advisory_playable_reason")) or "blocked"
        codes.append(primary)
        summary = "This row is blocked by a hard advisory data or safety gate."
    elif _is_threshold_adjusted(item):
        explanation_status = EXPLAINED_THRESHOLD_DOWNGRADED
        primary = "threshold_downgraded"
        summary = "This row was adjusted by advisory threshold calibration; hard blockers still cannot be overridden."
    elif status == PLAYABLE_PLUS_EV:
        explanation_status = EXPLAINED_PLAYABLE_PLUS_EV
        primary = "playable_positive_ev"
        codes.append(primary)
        summary = "This row is classified as playable advisory +EV because it passed available hard safety, source, market, no-vig, and threshold checks."
    elif status == WATCHLIST_VALUE:
        explanation_status = EXPLAINED_WATCHLIST_VALUE
        primary = "watchlist_close_value"
        codes.append(primary)
        summary = "This row is on the watchlist because it shows some value signal, but one or more playable requirements are not strong enough yet."
    elif status == PREDICTION_ONLY_NOT_PLUS_EV:
        explanation_status = EXPLAINED_PREDICTION_ONLY
        primary = "prediction_only_no_plus_ev"
        codes.append(primary)
        summary = "This row is prediction-only because the model may prefer the outcome, but the current price does not show enough positive expected value."
    elif missing:
        explanation_status = EXPLAINED_UNKNOWN
        primary = "missing_advisory_fields"
        warnings.append("Missing advisory fields: " + ",".join(missing))
        summary = "This row cannot be fully explained because expected advisory fields are missing."
    else:
        explanation_status = EXPLAINED_UNKNOWN
        primary = "unknown_advisory_state"
        summary = "This row has an unknown advisory explanation state."

    safety = "Advisory-only explanation; no official lock created; no proof ledger changed; no stake or bankroll action; no live action."
    out = deepcopy(item)
    out.update({
        "advisory_explanation_status": explanation_status,
        "advisory_explanation_summary": summary,
        "advisory_explanation_primary_reason": primary,
        "advisory_explanation_reason_codes": _csv(codes),
        "advisory_explanation_supporting_factors": " | ".join(dict.fromkeys(factors)),
        "advisory_explanation_blockers": " | ".join(dict.fromkeys(blockers)),
        "advisory_explanation_warnings": " | ".join(dict.fromkeys(warnings)),
        "advisory_explanation_next_action": advisory_next_action_for_row(item),
        "advisory_explanation_confidence_notes": "Confidence alone is not enough; price, source, market completeness, no-vig, and thresholds must support advisory value.",
        "advisory_explanation_source_notes": f"Sportsbook source type: {source_type or 'unknown'}.",
        "advisory_explanation_market_notes": f"Market completeness: {completeness or 'unknown'}; no-vig available: {no_vig}.",
        "advisory_explanation_threshold_notes": f"Original status: {original or 'unknown'}; calibrated status: {calibrated or status or 'unknown'}; threshold failures: {_text(item.get('advisory_threshold_failed_reasons')) or 'none'}.",
        "advisory_explanation_shadow_notes": shadow_notes,
        "advisory_explanation_safety_notes": safety,
    })
    return out


def explain_advisory_rows(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame) -> list[dict[str, Any]]:
    return [explain_advisory_row(row) for row in _records(rows_or_frame)]


def advisory_explanation_summary(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    rows = explain_advisory_rows(rows_or_frame)
    if not rows:
        return pd.DataFrame(columns=["explanation_status", "row_count", "most_common_primary_reason", "most_common_next_action"])
    frame = pd.DataFrame(rows)
    grouped = []
    for status, part in frame.groupby("advisory_explanation_status", dropna=False):
        reasons = Counter(part["advisory_explanation_primary_reason"].fillna("").astype(str)).most_common(1)
        actions = Counter(part["advisory_explanation_next_action"].fillna("").astype(str)).most_common(1)
        grouped.append({
            "explanation_status": status,
            "row_count": int(len(part)),
            "most_common_primary_reason": reasons[0][0] if reasons else "",
            "most_common_next_action": actions[0][0] if actions else "",
        })
    return pd.DataFrame(grouped).sort_values("row_count", ascending=False, ignore_index=True)


def advisory_explanation_reason_counts(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    counter: Counter[str] = Counter()
    for row in explain_advisory_rows(rows_or_frame):
        for code in _text(row.get("advisory_explanation_reason_codes")).split(","):
            if code:
                counter[code] += 1
    return pd.DataFrame([{"reason_code": code, "row_count": count} for code, count in counter.most_common()])


def advisory_explanation_report_section(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame) -> str:
    summary = advisory_explanation_summary(rows_or_frame)
    reasons = advisory_explanation_reason_counts(rows_or_frame)
    rows = explain_advisory_rows(rows_or_frame)
    blockers = Counter(_text(row.get("advisory_explanation_blockers")) for row in rows if _text(row.get("advisory_explanation_blockers"))).most_common(5)
    warnings = Counter(_text(row.get("advisory_explanation_warnings")) for row in rows if _text(row.get("advisory_explanation_warnings"))).most_common(5)
    lines = ["Advisory Explanation Engine", "- Explanations are advisory-only and do not change classifications."]
    if summary.empty:
        lines.append("- No explanation rows available.")
    else:
        lines.append("- Explanation status counts:")
        for item in summary.to_dict("records"):
            lines.append(f"  - {item.get('explanation_status')}: {item.get('row_count')} rows; top reason={item.get('most_common_primary_reason')}")
    if not reasons.empty:
        lines.append("- Top reason codes:")
        for item in reasons.head(10).to_dict("records"):
            lines.append(f"  - {item.get('reason_code')}: {item.get('row_count')}")
    if blockers:
        lines.append("- Top blockers:")
        for text, count in blockers:
            lines.append(f"  - {count}: {text}")
    if warnings:
        lines.append("- Top warnings:")
        for text, count in warnings:
            lines.append(f"  - {count}: {text}")
    lines.append("- Safety: advisory-only; no official lock, proof ledger, stake, bankroll, or live action changed.")
    return "\n".join(lines)
