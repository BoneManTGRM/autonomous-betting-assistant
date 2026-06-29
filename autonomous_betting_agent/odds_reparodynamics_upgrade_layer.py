from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.odds_math_completion import (
    american_from_decimal,
    build_odds_math_completion_report,
    expected_value,
    implied_probability,
    minimum_playable_decimal_odds,
    normalize_decimal_odds,
)
from autonomous_betting_agent.reparodynamics_shadow_scoring import build_reparodynamics_shadow_scoring_report
from autonomous_betting_agent.value_math import normalize_probability, safe_float

SCHEMA_VERSION = "odds_reparodynamics_upgrade_v1"
SHADOW_ONLY = "SHADOW ONLY"
KEEP_TESTING = "KEEP TESTING"
MANUAL_REVIEW = "MANUAL REVIEW"
REJECT = "REJECT"
DATA_BLOCKED = "DATA BLOCKED"
FORBIDDEN = "FORBIDDEN"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any) -> str:
    return str(value or "").strip()


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


def _key(value: Any) -> str:
    return "_".join("".join(ch if ch.isalnum() else "_" for ch in _text(value).lower()).split("_")) or "unknown"


def event_key(row: Mapping[str, Any]) -> str:
    for key in ("event_id", "provider_event_id", "proof_event_id", "event", "event_name", "matchup"):
        if _text(row.get(key)):
            return _key(row.get(key))
    return stable_hash("event", row, 10)


def market_type(row: Mapping[str, Any]) -> str:
    for key in ("market_type", "bet_type", "market"):
        if _text(row.get(key)):
            return _key(row.get(key))
    return "moneyline"


def sportsbook(row: Mapping[str, Any]) -> str:
    for key in ("sportsbook", "bookmaker", "book"):
        if _text(row.get(key)):
            return _key(row.get(key))
    return "unknown_book"


def selection_key(row: Mapping[str, Any]) -> str:
    for key in ("selection", "pick", "outcome", "team", "player"):
        if _text(row.get(key)):
            return _key(row.get(key))
    return stable_hash("selection", row, 8)


def group_key(row: Mapping[str, Any]) -> str:
    return "|".join((event_key(row), sportsbook(row), market_type(row)))


def best_book_key(row: Mapping[str, Any]) -> str:
    return "|".join((event_key(row), market_type(row), selection_key(row)))


def no_vig_by_market_group(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    source_rows = [dict(row) for row in rows or []]
    groups: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for index, row in enumerate(source_rows):
        groups.setdefault(group_key(row), []).append((index, row))
    group_summaries: list[dict[str, Any]] = []
    row_values: dict[int, dict[str, Any]] = {}
    for key, items in sorted(groups.items()):
        odds = [normalize_decimal_odds(row) for _index, row in items]
        implied = [implied_probability(value) for value in odds]
        valid = [value for value in implied if value is not None and value > 0]
        overround = round(sum(valid), 8) if valid else None
        margin = None if overround is None else round(overround - 1.0, 8)
        side_count = len(items)
        market_shape = "3-way" if side_count == 3 else "2-way" if side_count == 2 else "multi-way" if side_count > 3 else "single-side"
        for position, (index, row) in enumerate(items):
            no_vig = None
            if overround and implied[position] is not None:
                no_vig = round(float(implied[position]) / overround, 8)
            row_values[index] = {
                "market_group_key": key,
                "market_shape": market_shape,
                "market_side_count": side_count,
                "group_overround": overround,
                "bookmaker_margin": margin,
                "group_no_vig_probability": no_vig,
            }
        group_summaries.append({
            "market_group_key": key,
            "event_key": event_key(items[0][1]),
            "sportsbook": sportsbook(items[0][1]),
            "market_type": market_type(items[0][1]),
            "market_shape": market_shape,
            "market_side_count": side_count,
            "overround": overround,
            "bookmaker_margin": margin,
        })
    return {"groups": group_summaries, "row_values": row_values}


def best_book_by_selection(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        key = best_book_key(row)
        decimal = normalize_decimal_odds(row)
        if decimal is None:
            continue
        current = best.get(key)
        if current is None or decimal > float(current.get("best_decimal_odds") or 0):
            best[key] = {
                "best_book_key": key,
                "event_key": event_key(row),
                "market_type": market_type(row),
                "selection_key": selection_key(row),
                "best_sportsbook": sportsbook(row),
                "best_decimal_odds": decimal,
                "best_american_odds": american_from_decimal(decimal),
            }
    return best


def _prob(row: Mapping[str, Any]) -> float | None:
    for key in ("model_probability", "final_probability", "adjusted_model_probability", "learned_model_probability", "probability", "confidence"):
        value = normalize_probability(row.get(key))
        if value is not None:
            return value
    return None


def _parse_time(value: Any) -> datetime | None:
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


def _is_stale(row: Mapping[str, Any], max_age_minutes: int = 180) -> bool:
    status = " ".join(_text(row.get(key)).lower() for key in ("market_freshness_status", "odds_freshness_status", "edge_status", "odds_audit_status"))
    if "stale" in status or "expired" in status:
        return True
    timestamp = row.get("odds_timestamp") or row.get("price_timestamp") or row.get("prediction_timestamp")
    parsed = _parse_time(timestamp)
    if parsed is None:
        return False
    return (datetime.now(timezone.utc) - parsed).total_seconds() > max_age_minutes * 60


def closing_decimal_odds(row: Mapping[str, Any]) -> float | None:
    for key in ("closing_decimal_odds", "closing_odds_decimal", "close_decimal_odds", "closing_price"):
        value = safe_float(row.get(key))
        if value is not None and value > 1.0:
            return round(value, 6)
    return None


def clv_metrics(row: Mapping[str, Any]) -> dict[str, Any]:
    locked = normalize_decimal_odds(row)
    closing = closing_decimal_odds(row)
    locked_implied = implied_probability(locked)
    closing_implied = implied_probability(closing)
    if locked is None or closing is None or locked_implied is None or closing_implied is None:
        return {"closing_decimal_odds": closing, "CLV_decimal_delta": None, "CLV_probability_delta": None, "CLV_status": "unavailable"}
    decimal_delta = round(locked - closing, 8)
    probability_delta = round(closing_implied - locked_implied, 8)
    if decimal_delta > 0:
        status = "positive_CLV"
    elif decimal_delta < 0:
        status = "negative_CLV"
    else:
        status = "flat_CLV"
    return {"closing_decimal_odds": closing, "CLV_decimal_delta": decimal_delta, "CLV_probability_delta": probability_delta, "CLV_status": status}


def price_quality(row: Mapping[str, Any], min_playable: float | None, ev: float | None) -> str:
    decimal = normalize_decimal_odds(row)
    if decimal is None or min_playable is None:
        return "missing_price"
    if decimal >= min_playable + 0.15 and ev is not None and ev > 0.08:
        return "premium_price"
    if decimal >= min_playable:
        return "playable_price"
    if decimal >= max(1.01, min_playable - 0.05):
        return "fair_but_thin_price"
    return "bad_price"


def upgraded_odds_rows(rows: Sequence[Mapping[str, Any]], *, ev_buffer: float = 0.0, safety_margin: float = 0.02, max_age_minutes: int = 180) -> list[dict[str, Any]]:
    source_rows = [dict(row) for row in rows or []]
    grouped = no_vig_by_market_group(source_rows)
    best = best_book_by_selection(source_rows)
    output: list[dict[str, Any]] = []
    for index, row in enumerate(source_rows):
        decimal = normalize_decimal_odds(row)
        model_prob = _prob(row)
        raw = implied_probability(decimal)
        no_vig = grouped["row_values"].get(index, {}).get("group_no_vig_probability")
        ev = expected_value(model_prob, decimal)
        min_playable = minimum_playable_decimal_odds(model_prob, ev_buffer=ev_buffer, safety_margin=safety_margin)
        stale = _is_stale(row, max_age_minutes=max_age_minutes)
        best_info = best.get(best_book_key(row), {})
        best_decimal = best_info.get("best_decimal_odds")
        best_gap = None if decimal is None or best_decimal is None else round(float(best_decimal) - float(decimal), 8)
        blockers: list[str] = []
        if decimal is None:
            blockers.append("missing_decimal_odds")
        if model_prob is None:
            blockers.append("missing_model_probability")
        if stale:
            blockers.append("stale_line")
        if min_playable is not None and decimal is not None and decimal < min_playable:
            blockers.append("below_minimum_playable_odds")
        if best_gap is not None and best_gap > 0:
            blockers.append("not_best_available_book")
        clv = clv_metrics(row)
        quality = price_quality(row, min_playable, ev)
        action = "PLAYABLE VALUE" if not blockers and ev is not None and ev > ev_buffer else "WAIT FOR BETTER ODDS" if blockers == ["below_minimum_playable_odds"] else "NO BET" if blockers else "WATCH ONLY"
        output.append({
            "row_index": index,
            "event_key": event_key(row),
            "market_group_key": group_key(row),
            "best_book_key": best_book_key(row),
            "sportsbook": sportsbook(row),
            "market_type": market_type(row),
            "selection_key": selection_key(row),
            "decimal_odds": decimal,
            "american_odds": american_from_decimal(decimal),
            "model_probability": model_prob,
            "raw_implied_probability": raw,
            "group_no_vig_probability": no_vig,
            "raw_edge": None if model_prob is None or raw is None else round(model_prob - raw, 8),
            "no_vig_edge": None if model_prob is None or no_vig is None else round(model_prob - no_vig, 8),
            "expected_value": ev,
            "minimum_playable_odds": min_playable,
            "price_quality": quality,
            "best_sportsbook": best_info.get("best_sportsbook", sportsbook(row)),
            "best_decimal_odds": best_decimal or decimal,
            "best_price_gap": best_gap,
            "stale_line": stale,
            **grouped["row_values"].get(index, {}),
            **clv,
            "action": action,
            "blockers": blockers,
        })
    return output


def _result(row: Mapping[str, Any]) -> str:
    for key in ("result", "grade", "outcome", "official_result", "final_result", "result_status"):
        value = _text(row.get(key)).lower()
        if value:
            return value
    return ""


def _is_win(row: Mapping[str, Any]) -> bool | None:
    value = _result(row)
    if value in {"win", "won", "w"} or "win" in value or "won" in value:
        return True
    if value in {"loss", "lost", "l"} or "loss" in value or "lost" in value:
        return False
    return None


def _row_time(row: Mapping[str, Any]) -> datetime | None:
    for key in ("event_start_utc", "commence_time", "created_at_utc", "locked_at_utc", "prediction_timestamp"):
        parsed = _parse_time(row.get(key))
        if parsed is not None:
            return parsed
    return None


def odds_band(decimal: float | None) -> str:
    if decimal is None:
        return "missing_odds"
    if decimal < 1.5:
        return "heavy_favorite"
    if decimal < 2.0:
        return "favorite"
    if decimal < 3.0:
        return "mid_price"
    if decimal < 5.0:
        return "underdog"
    return "longshot"


def segment_keys(row: Mapping[str, Any]) -> dict[str, str]:
    decimal = normalize_decimal_odds(row)
    return {
        "sport": _key(row.get("sport") or row.get("sport_name")),
        "league": _key(row.get("league") or row.get("league_name")),
        "market_type": market_type(row),
        "sportsbook": sportsbook(row),
        "odds_band": odds_band(decimal),
    }


def wilson_interval(wins: int, total: int, z: float = 1.96) -> dict[str, float | None]:
    if total <= 0:
        return {"low": None, "high": None, "center": None}
    phat = wins / total
    denom = 1 + z * z / total
    center = (phat + z * z / (2 * total)) / denom
    half = z * math.sqrt((phat * (1 - phat) + z * z / (4 * total)) / total) / denom
    return {"low": round(max(0.0, center - half), 8), "high": round(min(1.0, center + half), 8), "center": round(phat, 8)}


def segment_drift_report(rows: Sequence[Mapping[str, Any]], *, min_segment_rows: int = 10, drift_threshold: float = 0.08) -> dict[str, Any]:
    completed = [dict(row) for row in rows or [] if _is_win(row) is not None]
    timed = [(row, _row_time(row)) for row in completed]
    if len(completed) < max(2, min_segment_rows):
        return {"segments": [], "drift_count": 0, "status": DATA_BLOCKED, "reason": "insufficient_completed_rows"}
    if all(ts is not None for _row, ts in timed):
        ordered = [row for row, _ts in sorted(timed, key=lambda item: item[1])]
    else:
        ordered = sorted(completed, key=lambda row: stable_hash("row", row, 12))
    split = max(1, min(len(ordered) - 1, int(len(ordered) * 0.70)))
    baseline_rows = ordered[:split]
    recent_rows = ordered[split:]
    results: list[dict[str, Any]] = []
    for group_name in ("sport", "league", "market_type", "sportsbook", "odds_band"):
        values = sorted({segment_keys(row)[group_name] for row in completed})
        for value in values:
            base = [row for row in baseline_rows if segment_keys(row)[group_name] == value]
            recent = [row for row in recent_rows if segment_keys(row)[group_name] == value]
            if len(base) < min_segment_rows or len(recent) < max(3, min_segment_rows // 3):
                continue
            base_wins = sum(1 for row in base if _is_win(row) is True)
            recent_wins = sum(1 for row in recent if _is_win(row) is True)
            base_rate = base_wins / len(base)
            recent_rate = recent_wins / len(recent)
            delta = recent_rate - base_rate
            interval = wilson_interval(recent_wins, len(recent))
            drift = delta <= -abs(drift_threshold)
            results.append({
                "segment_group": group_name,
                "segment_value": value,
                "baseline_rows": len(base),
                "recent_rows": len(recent),
                "baseline_win_rate": round(base_rate, 8),
                "recent_win_rate": round(recent_rate, 8),
                "win_rate_delta": round(delta, 8),
                "recent_wilson_low": interval["low"],
                "recent_wilson_high": interval["high"],
                "drift_detected": drift,
                "repair_category": "market_filter" if group_name in {"market_type", "sportsbook", "odds_band"} else "calibration",
                "decision": MANUAL_REVIEW if drift else KEEP_TESTING,
            })
    drift_count = len([row for row in results if row["drift_detected"]])
    return {"segments": results, "drift_count": drift_count, "status": MANUAL_REVIEW if drift_count else KEEP_TESTING, "reason": "segment_drift_evaluated"}


def repair_candidates_from_drift(drift: Mapping[str, Any], odds_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for segment in drift.get("segments") or []:
        if not isinstance(segment, Mapping) or not segment.get("drift_detected"):
            continue
        category = segment.get("repair_category", "calibration")
        candidates.append({
            "candidate_id": stable_hash("repair", segment, 16),
            "repair_category": category,
            "segment_group": segment.get("segment_group"),
            "segment_value": segment.get("segment_value"),
            "sample_size": int(segment.get("baseline_rows", 0) or 0) + int(segment.get("recent_rows", 0) or 0),
            "completed_rows_used": int(segment.get("recent_rows", 0) or 0),
            "decision": MANUAL_REVIEW,
            "decision_reason": "recent_segment_underperformed_baseline",
            "suggested_action": "tighten_filter" if category == "market_filter" else "recalibrate_probability_bucket",
            "live_mutation": FORBIDDEN,
            "shadow_only": True,
        })
    bad_price_count = len([row for row in odds_rows if row.get("price_quality") == "bad_price"])
    stale_count = len([row for row in odds_rows if row.get("stale_line")])
    if bad_price_count:
        candidates.append({"candidate_id": stable_hash("repair", {"bad_price_count": bad_price_count}, 16), "repair_category": "stake_sizing", "segment_group": "price_quality", "segment_value": "bad_price", "sample_size": bad_price_count, "completed_rows_used": 0, "decision": KEEP_TESTING, "decision_reason": "bad_price_rows_detected", "suggested_action": "lower_or_zero_stake_when_price_below_minimum", "live_mutation": FORBIDDEN, "shadow_only": True})
    if stale_count:
        candidates.append({"candidate_id": stable_hash("repair", {"stale_count": stale_count}, 16), "repair_category": "data_quality", "segment_group": "market_freshness", "segment_value": "stale_line", "sample_size": stale_count, "completed_rows_used": 0, "decision": MANUAL_REVIEW, "decision_reason": "stale_line_rows_detected", "suggested_action": "block_stale_lines_before_recommendation", "live_mutation": FORBIDDEN, "shadow_only": True})
    return candidates


def build_phase3e38_upgrade_report(
    workspace_id: str | None = None,
    odds_rows: Sequence[Mapping[str, Any]] | None = None,
    history_rows: Sequence[Mapping[str, Any]] | None = None,
    *,
    ev_buffer: float = 0.0,
    safety_margin: float = 0.02,
    max_age_minutes: int = 180,
    min_segment_rows: int = 10,
    drift_threshold: float = 0.08,
) -> dict[str, Any]:
    current_rows = [dict(row) for row in odds_rows or []]
    history = [dict(row) for row in history_rows or []]
    base_odds_report = build_odds_math_completion_report(workspace_id, current_rows, current_rows, ev_buffer=ev_buffer, safety_margin=safety_margin)
    upgraded_rows = upgraded_odds_rows(current_rows, ev_buffer=ev_buffer, safety_margin=safety_margin, max_age_minutes=max_age_minutes)
    grouped = no_vig_by_market_group(current_rows)
    best = list(best_book_by_selection(current_rows).values())
    drift = segment_drift_report(history or current_rows, min_segment_rows=min_segment_rows, drift_threshold=drift_threshold)
    repair_candidates = repair_candidates_from_drift(drift, upgraded_rows)
    synthetic_dynamic = {
        "decision": drift.get("status", KEEP_TESTING),
        "lr_evaluation_rows": len(history or current_rows),
        "completed_rows_used": len([row for row in history or current_rows if _is_win(row) is not None]),
        "train_test_overlap_count": 0,
        "unsafe_feature_count": 0,
        "summary_counts": {"data_blockers_count": len([row for row in upgraded_rows if row.get("blockers")])},
        "comparison_metrics": {"profit_units_delta": 0.0, "ROI_delta": 0.0, "losses_delta": 0.0, "calibration_delta": 0.0, "CLV_delta": 0.0},
        "repair_candidates": repair_candidates,
    }
    shadow = build_reparodynamics_shadow_scoring_report(workspace_id, synthetic_dynamic, base_odds_report, repair_candidates)
    playable = len([row for row in upgraded_rows if row.get("action") == "PLAYABLE VALUE"])
    blocked = len([row for row in upgraded_rows if row.get("blockers")])
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "upgrade_id": "",
        "mode": SHADOW_ONLY,
        "odds_row_count": len(current_rows),
        "history_row_count": len(history),
        "playable_count": playable,
        "blocked_count": blocked,
        "market_group_count": len(grouped["groups"]),
        "best_book_count": len(best),
        "drift_count": drift.get("drift_count", 0),
        "repair_candidate_count": len(repair_candidates),
        "upgraded_odds_rows": upgraded_rows,
        "market_groups": grouped["groups"],
        "best_book_rows": best,
        "segment_drift": drift,
        "repair_candidates": repair_candidates,
        "shadow_scoring": shadow,
        "base_odds_report": base_odds_report,
        "safety_gates": {"live_mutation": FORBIDDEN, "model_training": FORBIDDEN, "stored_data_mutation": FORBIDDEN, "automatic_live_promotion": FORBIDDEN, "repairs_applied_live": 0},
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "warnings": ["repair candidates require manual review"] if repair_candidates else [],
        "errors": [] if current_rows else ["no odds rows supplied"],
    }
    report["upgrade_id"] = stable_hash("phase3e38", {"workspace_id": workspace_id, "rows": upgraded_rows, "drift": drift}, 24)
    report["upgrade_hash"] = stable_hash("phase3e38_hash", {k: v for k, v in report.items() if k != "generated_at_utc"}, 32)
    return report


def build_phase3e38_upgrade_report_from_text(
    workspace_id: str | None = None,
    odds_csv_text: str | None = None,
    history_csv_text: str | None = None,
    *,
    ev_buffer: float = 0.0,
    safety_margin: float = 0.02,
    max_age_minutes: int = 180,
    min_segment_rows: int = 10,
    drift_threshold: float = 0.08,
) -> dict[str, Any]:
    return build_phase3e38_upgrade_report(
        workspace_id,
        parse_csv_text(odds_csv_text),
        parse_csv_text(history_csv_text),
        ev_buffer=ev_buffer,
        safety_margin=safety_margin,
        max_age_minutes=max_age_minutes,
        min_segment_rows=min_segment_rows,
        drift_threshold=drift_threshold,
    )


def export_phase3e38_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_upgraded_odds_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("upgraded_odds_rows") or [])


def export_market_groups_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("market_groups") or [])


def export_drift_csv(report: Mapping[str, Any]) -> str:
    drift = report.get("segment_drift") or {}
    return csv_from_rows(drift.get("segments") or [])


def export_repair_candidates_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("repair_candidates") or [])
