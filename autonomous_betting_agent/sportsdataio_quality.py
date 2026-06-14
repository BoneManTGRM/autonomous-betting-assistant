from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

QUALITY_STATUS_RANK = {"FAIL": 0, "WATCH": 1, "PASS": 2}


@dataclass(frozen=True)
class PipelineQualityGate:
    status: str
    score: float
    reasons: list[str]
    required_actions: list[str]
    metrics: dict[str, float | int | str]


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 4)


def _count(counts: Mapping[str, Any], key: str) -> int:
    try:
        return int(counts.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _add_issue(status_score: dict[str, float], reasons: list[str], actions: list[str], *, severity: str, reason: str, action: str) -> None:
    reasons.append(f"{severity}: {reason}")
    actions.append(action)
    if severity == "FAIL":
        status_score["score"] -= 25.0
        status_score["failed"] = 1.0
    elif severity == "WATCH":
        status_score["score"] -= 10.0
    else:
        status_score["score"] -= 4.0


def quality_gate_allows(gate: PipelineQualityGate | None, *, minimum_status: str = "WATCH") -> bool:
    """Return whether a quality gate is good enough for automated continuation.

    `minimum_status="WATCH"` allows PASS and WATCH but blocks FAIL.
    `minimum_status="PASS"` allows only PASS.
    `minimum_status="FAIL"` allows every completed quality status.
    """
    if gate is None:
        return False
    required = QUALITY_STATUS_RANK.get(minimum_status.upper())
    actual = QUALITY_STATUS_RANK.get(gate.status.upper())
    if required is None:
        raise ValueError(f"Unknown minimum quality status: {minimum_status}")
    if actual is None:
        return False
    return actual >= required


def evaluate_pipeline_quality(
    *,
    steps_run: list[str],
    warnings: list[str],
    counts: Mapping[str, Any],
    min_prediction_match_rate: float = 0.95,
    min_player_feature_match_rate: float = 0.85,
    min_player_feature_ready_rate: float = 0.80,
) -> PipelineQualityGate:
    """Evaluate whether a SportsDataIO pipeline run is usable for model/tracker decisions."""
    reasons: list[str] = []
    actions: list[str] = []
    metrics: dict[str, float | int | str] = {}
    state = {"score": 100.0, "failed": 0.0}

    if warnings:
        _add_issue(
            state,
            reasons,
            actions,
            severity="WATCH",
            reason=f"pipeline produced {len(warnings)} warning(s)",
            action="Review pipeline warnings before trusting the output.",
        )

    prediction_rows = _count(counts, "prediction_rows")
    if prediction_rows:
        matched = _count(counts, "prediction_match_matched")
        ambiguous = _count(counts, "prediction_match_ambiguous")
        unmatched = _count(counts, "prediction_match_unmatched")
        not_final = _count(counts, "prediction_match_not_final")
        match_rate = _ratio(matched, prediction_rows)
        metrics["prediction_match_rate"] = match_rate if match_rate is not None else 0.0
        metrics["prediction_rows"] = prediction_rows
        metrics["prediction_matched_rows"] = matched
        metrics["prediction_ambiguous_rows"] = ambiguous
        metrics["prediction_unmatched_rows"] = unmatched
        metrics["prediction_not_final_rows"] = not_final
        if match_rate is not None and match_rate < min_prediction_match_rate:
            severity = "FAIL" if match_rate < 0.80 else "WATCH"
            _add_issue(
                state,
                reasons,
                actions,
                severity=severity,
                reason=f"prediction result match rate is {match_rate:.1%}",
                action="Improve SportsDataIO game IDs, event names, start times, and team mappings before grading performance.",
            )
        if ambiguous:
            _add_issue(
                state,
                reasons,
                actions,
                severity="FAIL",
                reason=f"{ambiguous} prediction row(s) had ambiguous SportsDataIO matches",
                action="Add stable SportsDataIO game IDs to prediction rows to avoid false grading.",
            )
        if unmatched:
            _add_issue(
                state,
                reasons,
                actions,
                severity="WATCH",
                reason=f"{unmatched} prediction row(s) were unmatched",
                action="Normalize team names and include event IDs for unmatched prediction rows.",
            )
    elif "apply_game_results" in steps_run:
        _add_issue(
            state,
            reasons,
            actions,
            severity="WATCH",
            reason="game result step ran but no prediction rows were counted",
            action="Check the predictions CSV input and header names.",
        )

    feature_records = _count(counts, "player_feature_records")
    if feature_records:
        ready = _count(counts, "player_feature_ready")
        ready_rate = _ratio(ready, feature_records)
        metrics["player_feature_ready_rate"] = ready_rate if ready_rate is not None else 0.0
        metrics["player_feature_records"] = feature_records
        metrics["player_feature_ready_rows"] = ready
        if ready_rate is not None and ready_rate < min_player_feature_ready_rate:
            severity = "FAIL" if ready_rate < 0.60 else "WATCH"
            _add_issue(
                state,
                reasons,
                actions,
                severity=severity,
                reason=f"player feature ready rate is {ready_rate:.1%}",
                action="Inspect feature_quality_flags and fetch richer player-stat endpoints before scoring props.",
            )

    prop_rows = _count(counts, "player_prop_rows")
    if prop_rows:
        matched = _count(counts, "player_feature_match_matched")
        ambiguous = _count(counts, "player_feature_match_ambiguous")
        unmatched = _count(counts, "player_feature_match_unmatched")
        match_rate = _ratio(matched, prop_rows)
        metrics["player_prop_feature_match_rate"] = match_rate if match_rate is not None else 0.0
        metrics["player_prop_rows"] = prop_rows
        metrics["player_prop_feature_matched_rows"] = matched
        metrics["player_prop_feature_ambiguous_rows"] = ambiguous
        metrics["player_prop_feature_unmatched_rows"] = unmatched
        if match_rate is not None and match_rate < min_player_feature_match_rate:
            severity = "FAIL" if match_rate < 0.60 else "WATCH"
            _add_issue(
                state,
                reasons,
                actions,
                severity=severity,
                reason=f"player prop feature match rate is {match_rate:.1%}",
                action="Add SportsDataIO player IDs to prop rows and normalize player names.",
            )
        if ambiguous:
            _add_issue(
                state,
                reasons,
                actions,
                severity="FAIL",
                reason=f"{ambiguous} prop row(s) had ambiguous player feature matches",
                action="Use SportsDataIO player IDs instead of player names for ambiguous prop rows.",
            )
        if unmatched:
            _add_issue(
                state,
                reasons,
                actions,
                severity="WATCH",
                reason=f"{unmatched} prop row(s) were not enriched with player features",
                action="Fetch the correct SportsDataIO player-stat endpoint for those prop players.",
            )

    profit_finished = _count(counts, "profit_goal_finished_rows")
    if profit_finished:
        metrics["profit_goal_finished_rows"] = profit_finished
        metrics["profit_goal_wins"] = _count(counts, "profit_goal_wins")
        metrics["profit_goal_losses"] = _count(counts, "profit_goal_losses")
        if _count(counts, "profit_goal_status_goal_met"):
            reasons.append("PASS: profit goal currently met for the reviewed sample")
        elif _count(counts, "profit_goal_status_not_met_yet"):
            _add_issue(
                state,
                reasons,
                actions,
                severity="WATCH",
                reason="profit goal is not met yet",
                action="Keep tracking until win rate, average odds, ROI, CLV, duplicates and sample size all pass together.",
            )
        elif _count(counts, "profit_goal_status_no_finished_data"):
            _add_issue(
                state,
                reasons,
                actions,
                severity="WATCH",
                reason="profit goal has no finished data",
                action="Wait for finished, graded picks before evaluating profitability.",
            )
        critical_false_checks = [
            "profit_goal_check_positive_roi_false",
            "profit_goal_check_average_odds_above_minimum_false",
            "profit_goal_check_no_duplicate_padding_false",
        ]
        for check in critical_false_checks:
            if _count(counts, check):
                _add_issue(
                    state,
                    reasons,
                    actions,
                    severity="FAIL",
                    reason=f"{check} triggered",
                    action="Do not treat the sample as profitable until this profit-goal check passes.",
                )

    score = round(max(0.0, min(100.0, state["score"])), 1)
    if state["failed"]:
        status = "FAIL"
    elif score < 90 or warnings:
        status = "WATCH"
    else:
        status = "PASS"

    if not reasons:
        reasons.append("PASS: no pipeline quality issues detected")
    if not actions:
        actions.append("No immediate action required beyond normal sample-size and CLV tracking.")
    metrics["steps_run"] = ",".join(steps_run)
    return PipelineQualityGate(status=status, score=score, reasons=reasons, required_actions=list(dict.fromkeys(actions)), metrics=metrics)
