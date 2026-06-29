from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.odds_reparodynamics_upgrade_layer import (
    best_book_by_selection,
    event_key,
    expected_value,
    market_type,
    minimum_playable_decimal_odds,
    normalize_decimal_odds,
    odds_band,
    selection_key,
    sportsbook,
)
from autonomous_betting_agent.value_math import normalize_probability, safe_float

SCHEMA_VERSION = "accuracy_calibration_repair_feedback_v1"
SHADOW_ONLY = "SHADOW ONLY"
KEEP_TESTING = "KEEP TESTING"
MANUAL_REVIEW = "MANUAL REVIEW"
REJECT = "REJECT"
DATA_BLOCKED = "DATA BLOCKED"
FORBIDDEN = "FORBIDDEN"
PLAYABLE = "PLAYABLE VALUE"
WATCH = "WATCH ONLY"
WAIT = "WAIT FOR BETTER ODDS"
NO_BET = "NO BET"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _key(value: Any) -> str:
    return "_".join("".join(ch if ch.isalnum() else "_" for ch in _text(value).lower()).split("_")) or "unknown"


def _safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _canonical(value: Any) -> str:
    return json.dumps(_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_hash(prefix: str, value: Any, length: int = 24) -> str:
    return f"{prefix}_{hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()[:length]}"


def parse_csv_text(csv_text: str | None) -> list[dict[str, str]]:
    text = _text(csv_text)
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    return [{_text(key): _text(value) for key, value in row.items() if _text(key)} for row in reader]


def csv_from_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    row_list = [dict(row) for row in rows or []]
    fieldnames: list[str] = []
    for row in row_list:
        for key in row:
            if str(key) not in fieldnames:
                fieldnames.append(str(key))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    if fieldnames:
        writer.writeheader()
        for row in row_list:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return output.getvalue()


def model_probability(row: Mapping[str, Any]) -> float | None:
    for key in ("model_probability", "final_probability", "adjusted_model_probability", "learned_model_probability", "probability", "confidence"):
        value = normalize_probability(row.get(key))
        if value is not None:
            return value
    return None


def confidence_band(probability: float | None) -> str:
    if probability is None:
        return "missing_confidence"
    bucket = int(max(0, min(9, math.floor(probability * 10))))
    return f"confidence_{bucket * 10}_{bucket * 10 + 9}"


def segment_key(row: Mapping[str, Any], segment: str) -> str:
    if segment == "sport":
        return _key(row.get("sport") or row.get("sport_name"))
    if segment == "league":
        return _key(row.get("league") or row.get("league_name"))
    if segment == "market_type":
        return market_type(row)
    if segment == "sportsbook":
        return sportsbook(row)
    if segment == "odds_band":
        return odds_band(normalize_decimal_odds(row))
    if segment == "confidence_band":
        return confidence_band(model_probability(row))
    return "unknown"


def result_value(row: Mapping[str, Any]) -> str:
    for key in ("result", "grade", "outcome", "official_result", "final_result", "result_status"):
        text = _text(row.get(key)).lower()
        if text:
            return text
    return ""


def is_win(row: Mapping[str, Any]) -> bool | None:
    text = result_value(row)
    if text in {"win", "won", "w", "true", "1"} or "win" in text or "won" in text:
        return True
    if text in {"loss", "lost", "l", "false", "0"} or "loss" in text or "lost" in text:
        return False
    return None


def parse_time(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def row_time(row: Mapping[str, Any]) -> datetime | None:
    for key in ("event_start_utc", "commence_time", "created_at_utc", "locked_at_utc", "prediction_timestamp"):
        parsed = parse_time(row.get(key))
        if parsed is not None:
            return parsed
    return None


def split_train_eval(rows: Sequence[Mapping[str, Any]], train_fraction: float = 0.70) -> dict[str, Any]:
    completed = [dict(row) for row in rows or [] if is_win(row) is not None and model_probability(row) is not None]
    if len(completed) < 2:
        return {"training_rows": [], "evaluation_rows": [], "mode": "data_blocked", "reason": "insufficient_completed_rows"}
    timed = [(row, row_time(row)) for row in completed]
    if all(ts is not None for _row, ts in timed):
        ordered = [row for row, _ts in sorted(timed, key=lambda item: item[1])]
        mode = "chronological_holdout"
        reason = "timestamp_split"
    else:
        ordered = sorted(completed, key=lambda row: stable_hash("row", row, 12))
        mode = "stable_hash_holdout"
        reason = "timestamp_missing_hash_split"
    split_at = max(1, min(len(ordered) - 1, int(len(ordered) * train_fraction)))
    return {"training_rows": ordered[:split_at], "evaluation_rows": ordered[split_at:], "mode": mode, "reason": reason}


def brier_score(rows: Sequence[Mapping[str, Any]], probability_key: str) -> float | None:
    values: list[float] = []
    for row in rows or []:
        win = is_win(row)
        prob = normalize_probability(row.get(probability_key))
        if win is None or prob is None:
            continue
        values.append((prob - (1.0 if win else 0.0)) ** 2)
    return round(sum(values) / len(values), 8) if values else None


def log_loss(rows: Sequence[Mapping[str, Any]], probability_key: str) -> float | None:
    values: list[float] = []
    for row in rows or []:
        win = is_win(row)
        prob = normalize_probability(row.get(probability_key))
        if win is None or prob is None:
            continue
        p = min(0.999999, max(0.000001, prob))
        values.append(-(math.log(p) if win else math.log(1.0 - p)))
    return round(sum(values) / len(values), 8) if values else None


def calibration_error(rows: Sequence[Mapping[str, Any]], probability_key: str) -> float | None:
    values: list[float] = []
    for row in rows or []:
        win = is_win(row)
        prob = normalize_probability(row.get(probability_key))
        if win is None or prob is None:
            continue
        values.append(abs(prob - (1.0 if win else 0.0)))
    return round(sum(values) / len(values), 8) if values else None


def learn_calibration_model(rows: Sequence[Mapping[str, Any]], *, min_segment_rows: int = 8, shrinkage: float = 20.0) -> dict[str, Any]:
    training = [dict(row) for row in rows or [] if is_win(row) is not None and model_probability(row) is not None]
    wins = sum(1 for row in training if is_win(row) is True)
    global_rate = wins / len(training) if training else 0.5
    global_mean_prob = sum(model_probability(row) or 0.0 for row in training) / len(training) if training else 0.5
    global_bias = global_rate - global_mean_prob
    segments = ("sport", "league", "market_type", "sportsbook", "odds_band", "confidence_band")
    corrections: dict[str, dict[str, Any]] = {}
    for segment in segments:
        values = sorted({segment_key(row, segment) for row in training})
        for value in values:
            group = [row for row in training if segment_key(row, segment) == value]
            sample = len(group)
            if sample <= 0:
                continue
            group_wins = sum(1 for row in group if is_win(row) is True)
            observed = group_wins / sample
            predicted = sum(model_probability(row) or 0.0 for row in group) / sample
            raw_bias = observed - predicted
            weight = sample / (sample + float(shrinkage or 0.0))
            correction = raw_bias * weight
            status = "trusted" if sample >= min_segment_rows else "low_sample"
            if sample < min_segment_rows:
                correction = global_bias * min(0.25, weight)
            corrections[f"{segment}|{value}"] = {
                "segment_group": segment,
                "segment_value": value,
                "sample_size": sample,
                "wins": group_wins,
                "observed_win_rate": round(observed, 8),
                "mean_predicted_probability": round(predicted, 8),
                "raw_bias": round(raw_bias, 8),
                "shrinkage_weight": round(weight, 8),
                "probability_correction": round(correction, 8),
                "status": status,
            }
    return {
        "model_type": "segment_bias_shrunk_calibration",
        "training_rows": len(training),
        "global_observed_win_rate": round(global_rate, 8),
        "global_mean_predicted_probability": round(global_mean_prob, 8),
        "global_bias": round(global_bias, 8),
        "segment_corrections": corrections,
        "min_segment_rows": int(min_segment_rows),
        "shrinkage": float(shrinkage),
    }


def apply_calibration(row: Mapping[str, Any], model: Mapping[str, Any], *, max_total_adjustment: float = 0.12) -> dict[str, Any]:
    base = model_probability(row)
    if base is None:
        return {"baseline_probability": None, "calibrated_probability": None, "calibration_adjustment": None, "calibration_breakdown": [], "calibration_status": "missing_probability"}
    corrections = model.get("segment_corrections", {}) if isinstance(model.get("segment_corrections", {}), Mapping) else {}
    breakdown: list[dict[str, Any]] = []
    adjustment = 0.0
    for segment in ("sport", "league", "market_type", "sportsbook", "odds_band", "confidence_band"):
        value = segment_key(row, segment)
        key = f"{segment}|{value}"
        item = dict(corrections.get(key, {}))
        if item:
            corr = float(item.get("probability_correction") or 0.0)
            adjustment += corr
            breakdown.append({"segment_group": segment, "segment_value": value, "probability_correction": round(corr, 8), "sample_size": item.get("sample_size", 0), "status": item.get("status", "")})
    adjustment = max(-abs(max_total_adjustment), min(abs(max_total_adjustment), adjustment))
    calibrated = max(0.01, min(0.99, base + adjustment))
    status = "downgraded" if adjustment < -0.005 else "upgraded" if adjustment > 0.005 else "unchanged"
    return {"baseline_probability": round(base, 8), "calibrated_probability": round(calibrated, 8), "calibration_adjustment": round(adjustment, 8), "calibration_breakdown": breakdown, "calibration_status": status}


def calibrated_decision(row: Mapping[str, Any], calibrated_probability: float | None, *, ev_buffer: float = 0.0, safety_margin: float = 0.02) -> dict[str, Any]:
    decimal = normalize_decimal_odds(row)
    best = best_book_by_selection([row]).get("|".join((event_key(row), market_type(row), selection_key(row))), {})
    best_decimal = best.get("best_decimal_odds") or decimal
    ev = expected_value(calibrated_probability, best_decimal)
    min_playable = minimum_playable_decimal_odds(calibrated_probability, ev_buffer=ev_buffer, safety_margin=safety_margin)
    blockers: list[str] = []
    if calibrated_probability is None:
        blockers.append("missing_calibrated_probability")
    if best_decimal is None:
        blockers.append("missing_best_odds")
    if min_playable is not None and best_decimal is not None and best_decimal < min_playable:
        blockers.append("below_calibrated_minimum_playable_odds")
    if calibrated_probability is not None and calibrated_probability < 0.50:
        blockers.append("calibrated_probability_below_threshold")
    if ev is not None and ev <= ev_buffer:
        blockers.append("calibrated_ev_below_buffer")
    if blockers:
        action = WAIT if blockers == ["below_calibrated_minimum_playable_odds"] else NO_BET
    elif ev is not None and ev > ev_buffer:
        action = PLAYABLE
    else:
        action = WATCH
    return {
        "best_decimal_odds": best_decimal,
        "expected_value_calibrated": ev,
        "minimum_playable_odds_calibrated": min_playable,
        "decision_action": action,
        "decision_blockers": blockers,
    }


def build_calibrated_preview_rows(rows: Sequence[Mapping[str, Any]], model: Mapping[str, Any], *, ev_buffer: float = 0.0, safety_margin: float = 0.02) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, row in enumerate(rows or []):
        source = dict(row)
        calibrated = apply_calibration(source, model)
        decision = calibrated_decision(source, calibrated.get("calibrated_probability"), ev_buffer=ev_buffer, safety_margin=safety_margin)
        output.append({
            "row_index": index,
            "event_key": event_key(source),
            "market_type": market_type(source),
            "sportsbook": sportsbook(source),
            "selection_key": selection_key(source),
            "decimal_odds": normalize_decimal_odds(source),
            **calibrated,
            **decision,
            "shadow_only": True,
        })
    return output


def evaluate_calibration_shadow(rows: Sequence[Mapping[str, Any]], *, min_segment_rows: int = 8, shrinkage: float = 20.0, train_fraction: float = 0.70) -> dict[str, Any]:
    split = split_train_eval(rows, train_fraction=train_fraction)
    train = split["training_rows"]
    evaluation = split["evaluation_rows"]
    model = learn_calibration_model(train, min_segment_rows=min_segment_rows, shrinkage=shrinkage)
    eval_preview = []
    for row in evaluation:
        applied = apply_calibration(row, model)
        eval_preview.append({**dict(row), "calibrated_probability": applied.get("calibrated_probability"), "baseline_probability": applied.get("baseline_probability")})
    baseline_brier = brier_score([{**row, "baseline_probability": model_probability(row)} for row in evaluation], "baseline_probability")
    calibrated_brier = brier_score(eval_preview, "calibrated_probability")
    baseline_log = log_loss([{**row, "baseline_probability": model_probability(row)} for row in evaluation], "baseline_probability")
    calibrated_log = log_loss(eval_preview, "calibrated_probability")
    baseline_calibration_error = calibration_error([{**row, "baseline_probability": model_probability(row)} for row in evaluation], "baseline_probability")
    calibrated_calibration_error = calibration_error(eval_preview, "calibrated_probability")
    brier_gain = None if baseline_brier is None or calibrated_brier is None else round(baseline_brier - calibrated_brier, 8)
    log_gain = None if baseline_log is None or calibrated_log is None else round(baseline_log - calibrated_log, 8)
    calibration_gain = None if baseline_calibration_error is None or calibrated_calibration_error is None else round(baseline_calibration_error - calibrated_calibration_error, 8)
    if not train or not evaluation:
        decision = DATA_BLOCKED
        reason = "missing_train_or_evaluation_rows"
    elif (brier_gain or 0) > 0 and (log_gain or 0) >= -0.005:
        decision = MANUAL_REVIEW
        reason = "calibration_improved_shadow_holdout"
    elif (brier_gain or 0) < -0.005 or (log_gain or 0) < -0.01:
        decision = REJECT
        reason = "calibration_degraded_shadow_holdout"
    else:
        decision = KEEP_TESTING
        reason = "calibration_shadow_inconclusive"
    return {
        "split_mode": split["mode"],
        "split_reason": split["reason"],
        "training_rows": len(train),
        "evaluation_rows": len(evaluation),
        "calibration_model": model,
        "baseline_brier_score": baseline_brier,
        "calibrated_brier_score": calibrated_brier,
        "brier_improvement": brier_gain,
        "baseline_log_loss": baseline_log,
        "calibrated_log_loss": calibrated_log,
        "log_loss_improvement": log_gain,
        "baseline_calibration_error": baseline_calibration_error,
        "calibrated_calibration_error": calibrated_calibration_error,
        "calibration_error_improvement": calibration_gain,
        "decision": decision,
        "decision_reason": reason,
        "evaluation_preview_rows": build_calibrated_preview_rows(evaluation, model),
    }


def repair_feedback_from_calibration(shadow: Mapping[str, Any], preview_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    model = dict(shadow.get("calibration_model") or {})
    corrections = model.get("segment_corrections", {}) if isinstance(model.get("segment_corrections", {}), Mapping) else {}
    candidates: list[dict[str, Any]] = []
    for key, item in corrections.items():
        if not isinstance(item, Mapping):
            continue
        correction = float(item.get("probability_correction") or 0.0)
        sample = int(item.get("sample_size") or 0)
        if sample < int(model.get("min_segment_rows") or 0):
            continue
        if abs(correction) < 0.03:
            continue
        category = "calibration" if item.get("segment_group") in {"confidence_band", "sport", "league"} else "market_filter"
        candidates.append({
            "candidate_id": stable_hash("calibration_feedback", {"key": key, "item": item}, 16),
            "repair_category": category,
            "segment_group": item.get("segment_group"),
            "segment_value": item.get("segment_value"),
            "sample_size": sample,
            "probability_correction": round(correction, 8),
            "direction": "downgrade" if correction < 0 else "upgrade",
            "decision": MANUAL_REVIEW if shadow.get("decision") == MANUAL_REVIEW else KEEP_TESTING,
            "decision_reason": shadow.get("decision_reason", "calibration_feedback"),
            "suggested_action": "lower_segment_probability" if correction < 0 else "raise_segment_probability",
            "live_mutation": FORBIDDEN,
            "model_training": FORBIDDEN,
            "stored_data_mutation": FORBIDDEN,
            "shadow_only": True,
        })
    blocked = len([row for row in preview_rows if row.get("decision_action") == NO_BET])
    if blocked:
        candidates.append({
            "candidate_id": stable_hash("decision_feedback", {"blocked": blocked}, 16),
            "repair_category": "stake_sizing",
            "segment_group": "decision_action",
            "segment_value": "no_bet",
            "sample_size": blocked,
            "probability_correction": 0.0,
            "direction": "risk_down",
            "decision": KEEP_TESTING,
            "decision_reason": "calibrated_decision_preview_blocked_rows",
            "suggested_action": "zero_stake_for_blocked_rows",
            "live_mutation": FORBIDDEN,
            "model_training": FORBIDDEN,
            "stored_data_mutation": FORBIDDEN,
            "shadow_only": True,
        })
    return candidates


def build_accuracy_calibration_feedback_report(
    workspace_id: str | None = None,
    current_rows: Sequence[Mapping[str, Any]] | None = None,
    history_rows: Sequence[Mapping[str, Any]] | None = None,
    *,
    min_segment_rows: int = 8,
    shrinkage: float = 20.0,
    ev_buffer: float = 0.0,
    safety_margin: float = 0.02,
) -> dict[str, Any]:
    current = [dict(row) for row in current_rows or []]
    history = [dict(row) for row in history_rows or []]
    shadow = evaluate_calibration_shadow(history or current, min_segment_rows=min_segment_rows, shrinkage=shrinkage)
    model = shadow["calibration_model"]
    preview = build_calibrated_preview_rows(current, model, ev_buffer=ev_buffer, safety_margin=safety_margin)
    feedback = repair_feedback_from_calibration(shadow, preview)
    playable = len([row for row in preview if row.get("decision_action") == PLAYABLE])
    blocked = len([row for row in preview if row.get("decision_action") == NO_BET])
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "calibration_id": "",
        "mode": SHADOW_ONLY,
        "current_row_count": len(current),
        "history_row_count": len(history),
        "training_rows": shadow.get("training_rows", 0),
        "evaluation_rows": shadow.get("evaluation_rows", 0),
        "baseline_brier_score": shadow.get("baseline_brier_score"),
        "calibrated_brier_score": shadow.get("calibrated_brier_score"),
        "brier_improvement": shadow.get("brier_improvement"),
        "baseline_log_loss": shadow.get("baseline_log_loss"),
        "calibrated_log_loss": shadow.get("calibrated_log_loss"),
        "log_loss_improvement": shadow.get("log_loss_improvement"),
        "calibration_error_improvement": shadow.get("calibration_error_improvement"),
        "decision": shadow.get("decision"),
        "decision_reason": shadow.get("decision_reason"),
        "playable_count": playable,
        "blocked_count": blocked,
        "repair_feedback_count": len(feedback),
        "calibration_model": model,
        "calibrated_preview_rows": preview,
        "evaluation_preview_rows": shadow.get("evaluation_preview_rows", []),
        "repair_feedback": feedback,
        "safety_gates": {"live_mutation": FORBIDDEN, "model_training": FORBIDDEN, "stored_data_mutation": FORBIDDEN, "automatic_live_promotion": FORBIDDEN, "repairs_applied_live": 0},
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "warnings": ["manual review required before any calibration change"] if shadow.get("decision") == MANUAL_REVIEW else [],
        "errors": [] if current or history else ["no rows supplied"],
    }
    report["calibration_id"] = stable_hash("accuracy_calibration", {"workspace_id": workspace_id, "preview": preview, "shadow": shadow}, 24)
    report["calibration_hash"] = stable_hash("accuracy_calibration_hash", {k: v for k, v in report.items() if k != "generated_at_utc"}, 32)
    return report


def build_accuracy_calibration_feedback_report_from_text(
    workspace_id: str | None = None,
    current_csv_text: str | None = None,
    history_csv_text: str | None = None,
    *,
    min_segment_rows: int = 8,
    shrinkage: float = 20.0,
    ev_buffer: float = 0.0,
    safety_margin: float = 0.02,
) -> dict[str, Any]:
    return build_accuracy_calibration_feedback_report(
        workspace_id,
        parse_csv_text(current_csv_text),
        parse_csv_text(history_csv_text),
        min_segment_rows=min_segment_rows,
        shrinkage=shrinkage,
        ev_buffer=ev_buffer,
        safety_margin=safety_margin,
    )


def export_accuracy_calibration_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_calibrated_preview_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("calibrated_preview_rows") or [])


def export_evaluation_preview_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("evaluation_preview_rows") or [])


def export_repair_feedback_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("repair_feedback") or [])
