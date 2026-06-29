from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from collections import Counter
from typing import Any, Mapping, Sequence

import pandas as pd

PLAYABLE_PLUS_EV = "PLAYABLE_PLUS_EV"
WATCHLIST_VALUE = "WATCHLIST_VALUE"
PREDICTION_ONLY_NOT_PLUS_EV = "PREDICTION_ONLY_NOT_PLUS_EV"
COMPLETE_MARKET = "COMPLETE_MARKET"

THRESHOLD_COLUMNS = [
    "advisory_threshold_preset",
    "advisory_threshold_config_json",
    "advisory_threshold_min_raw_ev",
    "advisory_threshold_min_best_price_ev",
    "advisory_threshold_min_no_vig_edge",
    "advisory_threshold_max_market_hold",
    "advisory_threshold_min_model_probability",
    "advisory_threshold_min_line_shopping_gain",
    "advisory_threshold_max_odds_age_minutes",
    "advisory_threshold_watchlist_min_raw_ev",
    "advisory_threshold_watchlist_min_no_vig_edge",
    "advisory_threshold_max_risk_flags",
    "advisory_threshold_passed",
    "advisory_threshold_failed_reasons",
    "advisory_threshold_decision_reason",
    "advisory_calibrated_playable_status",
    "advisory_calibrated_value_tier",
    "advisory_original_playable_status_before_thresholds",
    "advisory_threshold_risk_flag_count",
    "advisory_threshold_risk_flags",
]

NUMERIC_THRESHOLD_KEYS = {
    "advisory_threshold_min_raw_ev": (-1.0, 1.0),
    "advisory_threshold_min_best_price_ev": (-1.0, 1.0),
    "advisory_threshold_min_no_vig_edge": (-1.0, 1.0),
    "advisory_threshold_max_market_hold": (0.0, 1.0),
    "advisory_threshold_min_model_probability": (0.0, 1.0),
    "advisory_threshold_min_line_shopping_gain": (-1.0, 1.0),
    "advisory_threshold_max_odds_age_minutes": (0.0, 1440.0),
    "advisory_threshold_watchlist_min_raw_ev": (-1.0, 1.0),
    "advisory_threshold_watchlist_min_no_vig_edge": (-1.0, 1.0),
    "advisory_threshold_max_risk_flags": (0.0, 25.0),
}

HARD_BLOCK_REASONS = {
    "event_start_time_is_not_future",
    "row_has_historical_or_graded_result",
    "missing_decimal_odds",
    "invalid_model_probability",
    "market_source_is_not_real_sportsbook",
    "consensus_only_source_not_playable",
    "unknown_sportsbook_source_not_playable",
    "market_incomplete_no_vig_unavailable",
    "missing_required_market_side",
    "mismatched_total_line",
    "mismatched_spread_line",
    "mixed_sportsbook_market",
    "unknown_market_structure",
    "futures_market_incomplete",
    "missing_selection",
    "missing_line_value",
    "missing_or_invalid_decimal_odds_for_required_sides",
}

HARD_BLOCK_STATUSES = {
    "BLOCKED_STALE_LINE",
    "BLOCKED_MISSING_ODDS",
    "BLOCKED_INVALID_PROBABILITY",
    "BLOCKED_INCOMPLETE_MARKET",
    "BLOCKED_DUPLICATE_CONFLICT",
}

ODDS_TIMESTAMP_FIELDS = ("odds_timestamp", "odds_last_update", "last_update", "pulled_at_utc", "created_at_utc")
PROBABILITY_FIELDS = ("model_probability", "model_probability_clean", "final_probability", "probability", "confidence_probability")


def _records(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame | None) -> list[dict[str, Any]]:
    if rows_or_frame is None:
        return []
    if isinstance(rows_or_frame, pd.DataFrame):
        return rows_or_frame.to_dict("records")
    return [deepcopy(dict(row)) for row in rows_or_frame if isinstance(row, Mapping)]


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"nan", "none", "null", "nat"}:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    parsed = _to_float(value)
    return None if parsed is None else int(round(parsed))


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "nat"}:
        return None
    text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _first_value(row: Mapping[str, Any], fields: Sequence[str]) -> Any:
    for field in fields:
        value = row.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() not in {"nan", "none", "null", "nat"}:
            return value
    return None


def _metric(row: Mapping[str, Any], *names: str) -> float | None:
    for name in names:
        value = _to_float(row.get(name))
        if value is not None:
            return value
    return None


def advisory_threshold_presets() -> dict[str, dict[str, Any]]:
    return {
        "Conservative": {
            "advisory_threshold_preset": "Conservative",
            "advisory_threshold_min_raw_ev": 0.05,
            "advisory_threshold_min_best_price_ev": 0.06,
            "advisory_threshold_min_no_vig_edge": 0.03,
            "advisory_threshold_max_market_hold": 0.055,
            "advisory_threshold_min_model_probability": 0.55,
            "advisory_threshold_min_line_shopping_gain": 0.01,
            "advisory_threshold_max_odds_age_minutes": 60,
            "advisory_threshold_watchlist_min_raw_ev": 0.01,
            "advisory_threshold_watchlist_min_no_vig_edge": 0.005,
            "advisory_threshold_max_risk_flags": 1,
        },
        "Balanced": {
            "advisory_threshold_preset": "Balanced",
            "advisory_threshold_min_raw_ev": 0.03,
            "advisory_threshold_min_best_price_ev": 0.04,
            "advisory_threshold_min_no_vig_edge": 0.02,
            "advisory_threshold_max_market_hold": 0.075,
            "advisory_threshold_min_model_probability": 0.52,
            "advisory_threshold_min_line_shopping_gain": 0.00,
            "advisory_threshold_max_odds_age_minutes": 120,
            "advisory_threshold_watchlist_min_raw_ev": 0.00,
            "advisory_threshold_watchlist_min_no_vig_edge": 0.00,
            "advisory_threshold_max_risk_flags": 2,
        },
        "Aggressive": {
            "advisory_threshold_preset": "Aggressive",
            "advisory_threshold_min_raw_ev": 0.01,
            "advisory_threshold_min_best_price_ev": 0.02,
            "advisory_threshold_min_no_vig_edge": 0.005,
            "advisory_threshold_max_market_hold": 0.10,
            "advisory_threshold_min_model_probability": 0.50,
            "advisory_threshold_min_line_shopping_gain": 0.00,
            "advisory_threshold_max_odds_age_minutes": 180,
            "advisory_threshold_watchlist_min_raw_ev": -0.01,
            "advisory_threshold_watchlist_min_no_vig_edge": -0.005,
            "advisory_threshold_max_risk_flags": 3,
        },
    }


def default_advisory_threshold_config() -> dict[str, Any]:
    return dict(advisory_threshold_presets()["Balanced"])


def normalize_threshold_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    presets = advisory_threshold_presets()
    supplied = dict(config or {})
    preset = str(supplied.get("advisory_threshold_preset") or supplied.get("preset") or "Balanced")
    base = dict(presets.get(preset, presets["Balanced"]))
    if preset not in presets:
        base["advisory_threshold_preset"] = "Custom"
    base.update({k: v for k, v in supplied.items() if k in NUMERIC_THRESHOLD_KEYS or k == "advisory_threshold_preset"})
    for key, (low, high) in NUMERIC_THRESHOLD_KEYS.items():
        parsed = _to_float(base.get(key))
        if parsed is None:
            parsed = _to_float(default_advisory_threshold_config().get(key)) or low
        parsed = max(low, min(high, parsed))
        base[key] = int(parsed) if key == "advisory_threshold_max_risk_flags" else float(parsed)
    if base.get("advisory_threshold_preset") not in presets:
        base["advisory_threshold_preset"] = "Custom"
    return base


def _config_json(config: Mapping[str, Any]) -> str:
    safe = {key: config.get(key) for key in ["advisory_threshold_preset", *NUMERIC_THRESHOLD_KEYS.keys()]}
    return json.dumps(safe, sort_keys=True, separators=(",", ":"))


def _odds_age_minutes(row: Mapping[str, Any], *, now: datetime | None = None) -> float | None:
    odds_time = None
    for field in ODDS_TIMESTAMP_FIELDS:
        odds_time = _parse_datetime(row.get(field))
        if odds_time is not None:
            break
    if odds_time is None:
        return None
    current = now or datetime.now(timezone.utc)
    current = current if current.tzinfo else current.replace(tzinfo=timezone.utc)
    return max(0.0, (current.astimezone(timezone.utc) - odds_time.astimezone(timezone.utc)).total_seconds() / 60.0)


def _risk_flags(row: Mapping[str, Any], config: Mapping[str, Any]) -> list[str]:
    flags: list[str] = []
    stale = str(row.get("advisory_stale_line_status") or "").upper()
    if stale in {"STALE", "UNKNOWN"}:
        flags.append(f"odds_freshness_{stale.lower()}")
    duplicate = str(row.get("advisory_duplicate_event_status") or "UNIQUE_EVENT")
    conflict = str(row.get("advisory_conflict_status") or "NO_CONFLICT")
    if duplicate != "UNIQUE_EVENT" or conflict != "NO_CONFLICT":
        flags.append("duplicate_or_conflict_warning")
    hold = _metric(row, "advisory_market_hold")
    if hold is not None and hold > float(config["advisory_threshold_max_market_hold"]):
        flags.append("high_sportsbook_hold")
    if _metric(row, "advisory_best_available_decimal_odds") is None:
        flags.append("missing_best_price_comparison")
    if _metric(row, "advisory_line_shopping_gain") is None:
        flags.append("missing_line_shopping_gain")
    model_probability = _metric(row, "model_probability", "model_probability_clean", "final_probability", "probability", "confidence_probability")
    if model_probability is not None and model_probability > 1.0 and model_probability <= 100.0:
        model_probability = model_probability / 100.0
    if model_probability is not None and model_probability < float(config["advisory_threshold_min_model_probability"]):
        flags.append("weak_model_probability")
    for key, value in row.items():
        key_text = str(key)
        if key_text.startswith(("proof", "lock", "official", "result", "grade", "stake")):
            continue
        if key_text.endswith(("_warning", "_risk", "_flag")) and str(value).strip().lower() not in {"", "false", "0", "none", "nan"}:
            flags.append(key_text)
    return sorted(set(flags))


def _hard_block_reasons(row: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    status = str(row.get("advisory_playable_status") or "")
    reason = str(row.get("advisory_playable_reason") or "")
    stale_status = str(row.get("advisory_stale_line_status") or "")
    stale_reason = str(row.get("advisory_stale_line_reason") or "")
    source_type = str(row.get("advisory_sportsbook_source_type") or "")
    completeness = str(row.get("advisory_market_completeness_status") or "")
    no_vig_available = bool(row.get("advisory_no_vig_available"))
    no_vig_blocker = str(row.get("advisory_no_vig_blocker_reason") or "")

    if status in HARD_BLOCK_STATUSES:
        reasons.append(status.lower())
    if reason in HARD_BLOCK_REASONS:
        reasons.append(reason)
    if stale_status in {"STALE", "EVENT_STARTED", "HISTORICAL_ROW"}:
        reasons.append(stale_reason or stale_status.lower())
    if source_type == "CONSENSUS_ONLY" or bool(row.get("advisory_is_consensus_source")):
        reasons.append("consensus_only_source_not_playable")
    if source_type == "UNKNOWN_SOURCE":
        reasons.append("unknown_sportsbook_source_not_playable")
    if not bool(row.get("advisory_is_real_sportsbook", False)):
        reasons.append("market_source_is_not_real_sportsbook")
    if completeness and completeness != COMPLETE_MARKET:
        reasons.append(no_vig_blocker or "market_incomplete_no_vig_unavailable")
    if not no_vig_available:
        reasons.append(no_vig_blocker or "market_incomplete_no_vig_unavailable")
    if _metric(row, "advisory_current_decimal_odds", "decimal_odds", "decimal_price", "odds") is None:
        reasons.append("missing_decimal_odds")
    model_probability = _metric(row, *PROBABILITY_FIELDS)
    if model_probability is None:
        reasons.append("invalid_model_probability")
    return sorted(set([r for r in reasons if r and r != "none"]))


def _soft_failures(row: Mapping[str, Any], config: Mapping[str, Any], *, now: datetime | None = None) -> list[str]:
    failures: list[str] = []
    checks = [
        ("raw_ev_below_threshold", _metric(row, "advisory_raw_EV"), config["advisory_threshold_min_raw_ev"], ">="),
        ("best_price_ev_below_threshold", _metric(row, "advisory_best_price_EV"), config["advisory_threshold_min_best_price_ev"], ">="),
        ("no_vig_edge_below_threshold", _metric(row, "advisory_no_vig_edge"), config["advisory_threshold_min_no_vig_edge"], ">="),
        ("market_hold_above_threshold", _metric(row, "advisory_market_hold"), config["advisory_threshold_max_market_hold"], "<="),
        ("model_probability_below_threshold", _metric(row, *PROBABILITY_FIELDS), config["advisory_threshold_min_model_probability"], ">="),
        ("line_shopping_gain_below_threshold", _metric(row, "advisory_line_shopping_gain"), config["advisory_threshold_min_line_shopping_gain"], ">="),
    ]
    for reason, actual, threshold, operator in checks:
        if actual is None:
            if reason == "line_shopping_gain_below_threshold":
                failures.append("line_shopping_gain_unavailable")
            elif reason == "best_price_ev_below_threshold":
                failures.append("best_price_ev_unavailable")
            else:
                failures.append(reason.replace("below_threshold", "unavailable").replace("above_threshold", "unavailable"))
            continue
        if reason == "model_probability_below_threshold" and actual > 1.0 and actual <= 100.0:
            actual = actual / 100.0
        if operator == ">=" and actual < float(threshold):
            failures.append(reason)
        if operator == "<=" and actual > float(threshold):
            failures.append(reason)
    age = _odds_age_minutes(row, now=now)
    if age is None:
        failures.append("odds_age_unavailable")
    elif age > float(config["advisory_threshold_max_odds_age_minutes"]):
        failures.append("odds_age_above_threshold")
    risks = _risk_flags(row, config)
    if len(risks) > int(config["advisory_threshold_max_risk_flags"]):
        failures.append("risk_flag_count_above_threshold")
    return sorted(set(failures))


def _near_watchlist(row: Mapping[str, Any], config: Mapping[str, Any]) -> bool:
    raw_ev = _metric(row, "advisory_raw_EV")
    no_vig_edge = _metric(row, "advisory_no_vig_edge")
    raw_ok = raw_ev is not None and raw_ev >= float(config["advisory_threshold_watchlist_min_raw_ev"])
    no_vig_ok = no_vig_edge is not None and no_vig_edge >= float(config["advisory_threshold_watchlist_min_no_vig_edge"])
    return bool(raw_ok or no_vig_ok)


def _value_tier(status: str) -> str:
    if status == PLAYABLE_PLUS_EV:
        return "PLAYABLE"
    if status == WATCHLIST_VALUE:
        return "WATCHLIST"
    if status == PREDICTION_ONLY_NOT_PLUS_EV:
        return "PREDICTION_ONLY"
    return "BLOCKED"


def apply_advisory_thresholds(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame, config: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = normalize_threshold_config(config)
    rows = _records(rows_or_frame)
    out: list[dict[str, Any]] = []
    for row in rows:
        item = deepcopy(row)
        original_status = str(item.get("advisory_playable_status") or "")
        hard_reasons = _hard_block_reasons(item)
        soft_reasons = _soft_failures(item, cfg)
        risk_flags = _risk_flags(item, cfg)
        if hard_reasons:
            calibrated = original_status if original_status.startswith("BLOCKED") else WATCHLIST_VALUE
            passed = False
            decision = "hard_block_preserved"
            failed = hard_reasons
        elif not soft_reasons:
            calibrated = PLAYABLE_PLUS_EV
            passed = True
            decision = "all_thresholds_passed"
            failed = []
        elif _near_watchlist(item, cfg):
            calibrated = WATCHLIST_VALUE
            passed = False
            decision = "soft_thresholds_failed_watchlist_only"
            failed = soft_reasons
        else:
            calibrated = PREDICTION_ONLY_NOT_PLUS_EV
            passed = False
            decision = "price_value_thresholds_not_met"
            failed = soft_reasons
        item.update({
            "advisory_threshold_preset": cfg["advisory_threshold_preset"],
            "advisory_threshold_config_json": _config_json(cfg),
            "advisory_threshold_min_raw_ev": cfg["advisory_threshold_min_raw_ev"],
            "advisory_threshold_min_best_price_ev": cfg["advisory_threshold_min_best_price_ev"],
            "advisory_threshold_min_no_vig_edge": cfg["advisory_threshold_min_no_vig_edge"],
            "advisory_threshold_max_market_hold": cfg["advisory_threshold_max_market_hold"],
            "advisory_threshold_min_model_probability": cfg["advisory_threshold_min_model_probability"],
            "advisory_threshold_min_line_shopping_gain": cfg["advisory_threshold_min_line_shopping_gain"],
            "advisory_threshold_max_odds_age_minutes": cfg["advisory_threshold_max_odds_age_minutes"],
            "advisory_threshold_watchlist_min_raw_ev": cfg["advisory_threshold_watchlist_min_raw_ev"],
            "advisory_threshold_watchlist_min_no_vig_edge": cfg["advisory_threshold_watchlist_min_no_vig_edge"],
            "advisory_threshold_max_risk_flags": cfg["advisory_threshold_max_risk_flags"],
            "advisory_threshold_passed": bool(passed),
            "advisory_threshold_failed_reasons": ",".join(failed),
            "advisory_threshold_decision_reason": decision,
            "advisory_calibrated_playable_status": calibrated,
            "advisory_calibrated_value_tier": _value_tier(calibrated),
            "advisory_original_playable_status_before_thresholds": original_status,
            "advisory_threshold_risk_flag_count": len(risk_flags),
            "advisory_threshold_risk_flags": ",".join(risk_flags),
        })
        out.append(item)
    return out


def threshold_impact_summary(baseline_rows: Sequence[Mapping[str, Any]] | pd.DataFrame, calibrated_rows: Sequence[Mapping[str, Any]] | pd.DataFrame) -> dict[str, Any]:
    baseline = _records(baseline_rows)
    calibrated = _records(calibrated_rows)
    original_statuses = [str(row.get("advisory_playable_status") or "") for row in baseline]
    calibrated_statuses = [str(row.get("advisory_calibrated_playable_status") or row.get("advisory_playable_status") or "") for row in calibrated]
    original_counts = Counter(original_statuses)
    calibrated_counts = Counter(calibrated_statuses)
    total = min(len(original_statuses), len(calibrated_statuses))
    upgraded = downgraded = unchanged = 0
    rank = {"": 0, PREDICTION_ONLY_NOT_PLUS_EV: 1, WATCHLIST_VALUE: 2, PLAYABLE_PLUS_EV: 3}
    for left, right in zip(original_statuses, calibrated_statuses):
        if left == right:
            unchanged += 1
        elif rank.get(right, 0) > rank.get(left, 0):
            upgraded += 1
        else:
            downgraded += 1
    return {
        "total_rows": len(calibrated),
        "original_PLAYABLE_PLUS_EV": int(original_counts[PLAYABLE_PLUS_EV]),
        "calibrated_PLAYABLE_PLUS_EV": int(calibrated_counts[PLAYABLE_PLUS_EV]),
        "original_WATCHLIST_VALUE": int(original_counts[WATCHLIST_VALUE]),
        "calibrated_WATCHLIST_VALUE": int(calibrated_counts[WATCHLIST_VALUE]),
        "original_prediction_only_rows": int(original_counts[PREDICTION_ONLY_NOT_PLUS_EV]),
        "calibrated_prediction_only_rows": int(calibrated_counts[PREDICTION_ONLY_NOT_PLUS_EV]),
        "blocked_rows": int(sum(1 for status in calibrated_statuses if status.startswith("BLOCKED"))),
        "downgraded_by_thresholds": int(downgraded),
        "upgraded_by_thresholds": int(upgraded),
        "unchanged_rows": int(unchanged + max(0, len(calibrated) - total)),
    }


def threshold_calibration_summary(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame, config: Mapping[str, Any] | None = None) -> pd.DataFrame:
    cfg = normalize_threshold_config(config)
    rows = apply_advisory_thresholds(rows_or_frame, cfg)
    records: list[dict[str, Any]] = []
    failed_reason_series = [str(row.get("advisory_threshold_failed_reasons") or "") for row in rows]
    for key in NUMERIC_THRESHOLD_KEYS:
        simple = key.replace("advisory_threshold_", "")
        passed = 0
        failed = 0
        reasons: list[str] = []
        for row in rows:
            failed_reasons = [part for part in str(row.get("advisory_threshold_failed_reasons") or "").split(",") if part]
            related = [reason for reason in failed_reasons if simple.replace("min_", "").replace("max_", "")[:8] in reason or key.split("advisory_threshold_")[-1].split("_")[0] in reason]
            if related:
                failed += 1
                reasons.extend(related)
            else:
                passed += 1
        common = Counter(reasons).most_common(1)
        records.append({
            "threshold_preset": cfg["advisory_threshold_preset"],
            "threshold_name": key,
            "threshold_value": cfg[key],
            "rows_passed": passed,
            "rows_failed": failed,
            "most_common_failed_reason": common[0][0] if common else "",
        })
    if not records and failed_reason_series:
        return pd.DataFrame()
    return pd.DataFrame(records)


def calibrated_status_table(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame, status: str, config: Mapping[str, Any] | None = None) -> pd.DataFrame:
    frame = pd.DataFrame(apply_advisory_thresholds(rows_or_frame, config))
    if frame.empty or "advisory_calibrated_playable_status" not in frame.columns:
        return pd.DataFrame()
    return frame[frame["advisory_calibrated_playable_status"].fillna("").astype(str) == status].copy()


def calibrated_blocked_reason_summary(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame, config: Mapping[str, Any] | None = None) -> pd.DataFrame:
    frame = pd.DataFrame(apply_advisory_thresholds(rows_or_frame, config))
    if frame.empty:
        return pd.DataFrame(columns=["advisory_calibrated_playable_status", "advisory_threshold_decision_reason", "advisory_threshold_failed_reasons", "row_count"])
    blocked = frame[frame["advisory_calibrated_playable_status"].fillna("").astype(str).str.startswith("BLOCKED")].copy()
    if blocked.empty:
        blocked = frame[frame["advisory_threshold_failed_reasons"].fillna("").astype(str).ne("")].copy()
    if blocked.empty:
        return pd.DataFrame(columns=["advisory_calibrated_playable_status", "advisory_threshold_decision_reason", "advisory_threshold_failed_reasons", "row_count"])
    return blocked.groupby(["advisory_calibrated_playable_status", "advisory_threshold_decision_reason", "advisory_threshold_failed_reasons"], dropna=False).size().reset_index(name="row_count").sort_values("row_count", ascending=False, ignore_index=True)


def threshold_report_text(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame, config: Mapping[str, Any] | None = None) -> str:
    cfg = normalize_threshold_config(config)
    baseline = _records(rows_or_frame)
    calibrated = apply_advisory_thresholds(baseline, cfg)
    impact = threshold_impact_summary(baseline, calibrated)
    summary = threshold_calibration_summary(calibrated, cfg)
    lines = [
        "Advisory Threshold Calibration",
        f"- Preset: {cfg['advisory_threshold_preset']}",
        "- Calibration is advisory-only. It does not change official locks, proof history, bankroll, staking, ledgers, or live betting.",
        "",
        "Threshold values",
    ]
    for key in NUMERIC_THRESHOLD_KEYS:
        lines.append(f"- {key}: {cfg[key]}")
    lines.extend(["", "Threshold impact"])
    for key, value in impact.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "Top threshold failure reasons"])
    if summary.empty:
        lines.append("- None")
    else:
        top = summary[summary["most_common_failed_reason"].astype(str).ne("")].head(10)
        if top.empty:
            lines.append("- None")
        else:
            for item in top.to_dict("records"):
                lines.append(f"- {item['threshold_name']}: {item['rows_failed']} failed — {item['most_common_failed_reason']}")
    return "\n".join(lines)
