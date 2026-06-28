from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from autonomous_betting_agent.value_math import (
    assess_value_pick,
    decimal_odds_from,
    model_probability_from,
    no_vig_probability_from,
    raw_implied_probability,
    safe_float,
)

PHASE_3E = "Phase 3E Dynamic Odds Predictor Shadow"
FORBIDDEN = "FORBIDDEN"
OFF = "OFF"
SHADOW_ONLY = "SHADOW ONLY"

DEFAULT_CONFIG: dict[str, Any] = {
    "minimum_lr_sample": 25,
    "strong_lr_sample": 100,
    "minimum_lr_training_rows": 50,
    "minimum_lr_evaluation_rows": 30,
    "min_LR": 0.50,
    "max_LR": 2.00,
    "default_LR": 1.00,
    "recency_lambda": 0.01,
    "max_dynamic_probability": 0.95,
    "min_dynamic_probability": 0.02,
    "minimum_dynamic_edge": 0.02,
    "minimum_dynamic_no_vig_edge": 0.01,
    "minimum_dynamic_EV": 0.02,
    "minimum_completed_rows_for_evaluation": 50,
    "minimum_CLV_sample_for_promotion": 10,
    "severe_CLV_degradation": -0.02,
    "maximum_overfit_risk_allowed": "medium",
    "maximum_single_lr_contribution": 0.35,
    "train_fraction": 0.70,
}

SAFE_FEATURE_GROUPS = (
    "sport",
    "league",
    "market_type",
    "odds_band",
    "confidence_bucket",
    "edge_bucket",
    "price_quality_bucket",
    "sportsbook",
    "home_away",
    "rest_bucket",
    "weather_bucket",
    "injury_bucket",
    "market_move_bucket",
    "calibration_bucket",
)

UNSAFE_FEATURE_TOKENS = (
    "result",
    "grade",
    "outcome",
    "official_result",
    "final_result",
    "profit",
    "roi",
    "win",
    "loss",
    "push",
    "void",
    "postgame",
    "post_game",
    "after_game",
    "after_grading",
    "settled",
    "payout",
    "closing_result",
)

RESULT_KEYS = (
    "result",
    "grade",
    "outcome",
    "official_result",
    "final_result",
    "result_status",
)

TIMESTAMP_KEYS = (
    "event_start_utc",
    "commence_time",
    "created_at_utc",
    "locked_at_utc",
    "prediction_timestamp",
    "odds_timestamp",
)


def _config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    merged = dict(DEFAULT_CONFIG)
    if config:
        merged.update(dict(config))
    return merged


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _key(value: Any) -> str:
    return "_".join("".join(ch if ch.isalnum() else "_" for ch in _text(value).lower()).split("_"))


def _float(value: Any, default: float | None = None) -> float | None:
    parsed = safe_float(value)
    return parsed if parsed is not None else default


def _prob(value: Any) -> float | None:
    parsed = _float(value)
    if parsed is None:
        return None
    parsed = parsed / 100.0 if parsed > 1 else parsed
    return parsed if 0 <= parsed <= 1 else None


def _round(value: float | None) -> float | None:
    return round(float(value), 6) if value is not None else None


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, float):
        return round(value, 10)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    return str(value)


def _stable_hash(value: Any) -> str:
    payload = json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _row_id(row: Mapping[str, Any]) -> str:
    for key in ("proof_id", "pick_id", "row_id", "event_id", "id"):
        if _text(row.get(key)):
            return f"{key}:{_text(row.get(key))}"
    return _stable_hash(row)[:24]


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


def _row_time(row: Mapping[str, Any]) -> datetime | None:
    for key in TIMESTAMP_KEYS:
        parsed = _parse_time(row.get(key))
        if parsed is not None:
            return parsed
    return None


def _is_unsafe_feature_key(key: str) -> bool:
    lowered = str(key).lower().replace(" ", "_")
    if "closing" in lowered and "pre_lock" not in lowered and "before_lock" not in lowered:
        return True
    return any(token in lowered for token in UNSAFE_FEATURE_TOKENS)


def _result_value(row: Mapping[str, Any]) -> str:
    for key in RESULT_KEYS:
        text = _text(row.get(key)).lower()
        if text:
            return text
    return ""


def _is_completed(row: Mapping[str, Any]) -> bool:
    text = _result_value(row)
    return any(token in text for token in ("win", "won", "loss", "lost", "push", "void", "cancel"))


def _is_win(row: Mapping[str, Any]) -> bool | None:
    text = _result_value(row)
    if text in {"win", "won", "w", "true", "1"} or "win" in text or "won" in text:
        return True
    if text in {"loss", "lost", "l", "false", "0"} or "loss" in text or "lost" in text:
        return False
    return None


def _profit_units(row: Mapping[str, Any], selected: bool = True) -> float:
    if not selected:
        return 0.0
    explicit = _float(row.get("profit_units"))
    if explicit is not None:
        return explicit
    win = _is_win(row)
    if win is None:
        return 0.0
    odds = decimal_odds_from(row) or 2.0
    return odds - 1.0 if win else -1.0


def decimal_to_raw_implied_probability(decimal_odds: float | None) -> float | None:
    return raw_implied_probability(decimal_odds)


def decimal_to_book_odds_ratio(decimal_odds: float | None) -> float | None:
    if decimal_odds is None or decimal_odds <= 1:
        return None
    return 1.0 / (decimal_odds - 1.0)


def odds_ratio_to_probability(odds_ratio: float | None) -> float | None:
    if odds_ratio is None or odds_ratio < 0:
        return None
    return odds_ratio / (1.0 + odds_ratio)


def safe_logit(probability: float | None) -> float | None:
    if probability is None or probability <= 0 or probability >= 1:
        return None
    return math.log(probability / (1.0 - probability))


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def recency_decay(data_age_hours: float | None, lambda_value: float = 0.0) -> float:
    age = max(0.0, float(data_age_hours or 0.0))
    return math.exp(-float(lambda_value or 0.0) * age)


def apply_lr_multipliers(
    base_odds_ratio: float | None,
    lr_breakdown: Sequence[Mapping[str, Any]] | Mapping[str, Any] | None,
    data_age_hours: float = 0.0,
    lambda_value: float = 0.0,
) -> dict[str, Any]:
    if base_odds_ratio is None or base_odds_ratio <= 0:
        return {"dynamic_odds_ratio": None, "dynamic_probability": None, "recency_decay_factor": recency_decay(data_age_hours, lambda_value)}
    if isinstance(lr_breakdown, Mapping):
        items = list(lr_breakdown.values())
    else:
        items = list(lr_breakdown or [])
    log_odds = math.log(base_odds_ratio)
    total_multiplier = 1.0
    safe_items = []
    for item in items:
        if isinstance(item, Mapping):
            lr = _float(item.get("capped_lr") or item.get("LR") or item.get("lr") or item.get("value"), 1.0) or 1.0
            safe = dict(item)
        else:
            lr = _float(item, 1.0) or 1.0
            safe = {"capped_lr": lr}
        lr = max(0.000001, lr)
        log_odds += math.log(lr)
        total_multiplier *= lr
        safe["capped_lr"] = lr
        safe_items.append(safe)
    decay = recency_decay(data_age_hours, lambda_value)
    log_odds += math.log(max(decay, 0.000001))
    dynamic_ratio = math.exp(max(-50.0, min(50.0, log_odds)))
    return {
        "dynamic_odds_ratio": dynamic_ratio,
        "dynamic_probability": odds_ratio_to_probability(dynamic_ratio),
        "total_LR_multiplier": total_multiplier,
        "recency_decay_factor": decay,
        "LR_breakdown": safe_items,
    }


def _bucket_probability(value: float | None, prefix: str) -> str:
    if value is None:
        return "missing"
    bucket = int(max(0, min(9, math.floor(value * 10))))
    return f"{prefix}_{bucket * 10}_{bucket * 10 + 9}"


def _odds_band(odds: float | None) -> str:
    if odds is None:
        return "missing"
    if odds < 1.5:
        return "heavy_favorite"
    if odds < 2.0:
        return "favorite"
    if odds < 3.0:
        return "mid_price"
    if odds < 5.0:
        return "underdog"
    return "longshot"


def _price_quality_bucket(row: Mapping[str, Any], raw: float | None) -> str:
    model_prob = model_probability_from(row)
    if model_prob is None or raw is None:
        return "missing"
    edge = model_prob - raw
    if edge >= 0.05:
        return "strong_positive_edge"
    if edge >= 0.02:
        return "positive_edge"
    if edge >= 0:
        return "thin_edge"
    if edge >= -0.03:
        return "slightly_negative_edge"
    return "negative_edge"


def _market_move_bucket(row: Mapping[str, Any]) -> str | None:
    open_odds = _float(row.get("opening_decimal_odds") or row.get("open_decimal_odds") or row.get("opening_price"))
    current = decimal_odds_from(row)
    if open_odds is None or current is None:
        return None
    # Closing odds are not used here. This is only open-to-current before lock.
    delta = current - open_odds
    if delta > 0.10:
        return "price_improved_before_lock"
    if delta < -0.10:
        return "price_worsened_before_lock"
    return "price_stable_before_lock"


def extract_pregame_safe_features(row: Mapping[str, Any], config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = dict(row or {})
    blocked = sorted([key for key in source if _is_unsafe_feature_key(str(key))])
    odds = decimal_odds_from(source)
    raw = raw_implied_probability(odds)
    model_prob = model_probability_from(source)
    features: dict[str, str] = {}
    direct_map = {
        "sport": ("sport", "sport_name"),
        "league": ("league", "league_name"),
        "market_type": ("market_type", "bet_type", "market"),
        "sportsbook": ("sportsbook", "bookmaker", "book"),
        "home_away": ("home_away", "venue_side"),
        "rest_bucket": ("rest_bucket", "rest_days_bucket"),
        "weather_bucket": ("weather_bucket", "weather_condition_bucket"),
        "injury_bucket": ("injury_bucket", "injury_status_bucket"),
        "calibration_bucket": ("historical_calibration_bucket", "prior_calibration_bucket"),
    }
    for group, keys in direct_map.items():
        for key in keys:
            if key in source and not _is_unsafe_feature_key(key) and _text(source.get(key)):
                features[group] = _key(source.get(key))
                break
    features.setdefault("odds_band", _odds_band(odds))
    features.setdefault("confidence_bucket", _bucket_probability(model_prob, "confidence"))
    edge = None if model_prob is None or raw is None else model_prob - raw
    features.setdefault("edge_bucket", _bucket_probability((edge + 0.50) if edge is not None else None, "edge"))
    features.setdefault("price_quality_bucket", _price_quality_bucket(source, raw))
    move = _market_move_bucket(source)
    if move:
        features["market_move_bucket"] = move
    safe_features = {group: value for group, value in features.items() if group in SAFE_FEATURE_GROUPS and value}
    return {
        "features": safe_features,
        "blocked_leakage_fields": blocked,
        "pregame_feature_whitelist_used": True,
        "pregame_safe_feature_count": len(safe_features),
        "unsafe_feature_count": len(blocked),
    }


def build_lr_training_rows(rows: Iterable[Mapping[str, Any]], config: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows or []:
        win = _is_win(row)
        if win is None:
            continue
        extracted = extract_pregame_safe_features(row, config)
        output.append(
            {
                "row_id": _row_id(row),
                "timestamp": _row_time(row).isoformat().replace("+00:00", "Z") if _row_time(row) else "",
                "features": extracted["features"],
                "win": bool(win),
                "blocked_leakage_fields": extracted["blocked_leakage_fields"],
            }
        )
    return output


def split_lr_train_evaluation_rows(rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = _config(config)
    completed = [dict(row) for row in rows or [] if _is_completed(row)]
    if not completed:
        return {"training_rows": [], "evaluation_rows": [], "evaluation_mode": "data_blocked", "leakage_guard_enabled": True, "train_test_overlap_count": 0, "leakage_guard_reason": "no_completed_rows", "walk_forward_windows_evaluated": 0}
    timed = [(row, _row_time(row)) for row in completed]
    if all(ts is not None for _row, ts in timed) and len(timed) >= 2:
        ordered = [row for row, _ts in sorted(timed, key=lambda item: item[1])]
        split_at = max(1, min(len(ordered) - 1, int(len(ordered) * float(cfg["train_fraction"]))))
        train, evaluation = ordered[:split_at], ordered[split_at:]
        mode = "chronological_holdout"
        reason = "timestamp_chronological_split"
    else:
        ordered = sorted(completed, key=lambda row: _stable_hash(row))
        split_at = max(1, min(len(ordered) - 1, int(len(ordered) * float(cfg["train_fraction"]))))
        train, evaluation = ordered[:split_at], ordered[split_at:]
        mode = "stable_hash_holdout"
        reason = "timestamps_unavailable_stable_hash_split"
    train_ids = {_row_id(row) for row in train}
    eval_ids = {_row_id(row) for row in evaluation}
    overlap = len(train_ids & eval_ids)
    enough = len(train) >= int(cfg["minimum_lr_training_rows"]) and len(evaluation) >= int(cfg["minimum_lr_evaluation_rows"])
    return {
        "training_rows": train,
        "evaluation_rows": evaluation,
        "evaluation_mode": mode,
        "leakage_guard_enabled": True,
        "train_test_overlap_count": overlap,
        "leakage_guard_reason": reason,
        "walk_forward_windows_evaluated": 1 if enough and mode == "chronological_holdout" else 0,
    }


def learn_lr_multipliers(rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = _config(config)
    training = build_lr_training_rows(rows, cfg)
    wins_total = sum(1 for row in training if row["win"])
    baseline = wins_total / len(training) if training else 0.5
    baseline = max(0.01, min(0.99, baseline))
    grouped: dict[tuple[str, str], dict[str, int]] = {}
    for row in training:
        for group, value in row["features"].items():
            key = (group, value)
            grouped.setdefault(key, {"sample_size": 0, "wins": 0, "losses": 0})
            grouped[key]["sample_size"] += 1
            if row["win"]:
                grouped[key]["wins"] += 1
            else:
                grouped[key]["losses"] += 1
    lr_by_feature: dict[str, dict[str, Any]] = {}
    for (group, value), stats in grouped.items():
        sample = stats["sample_size"]
        wins = stats["wins"]
        observed = (wins + baseline) / (sample + 1.0)
        raw_lr = observed / baseline
        weight = min(1.0, sample / float(cfg["strong_lr_sample"]))
        shrunk = 1.0 + (raw_lr - 1.0) * weight
        capped = max(float(cfg["min_LR"]), min(float(cfg["max_LR"]), shrunk))
        reason = "learned_from_training_rows"
        if sample < int(cfg["minimum_lr_sample"]):
            capped = float(cfg["default_LR"])
            reason = "insufficient_sample_default_lr"
        max_log = float(cfg.get("maximum_single_lr_contribution", 0.35))
        if max_log > 0:
            capped = math.exp(max(-max_log, min(max_log, math.log(max(capped, 0.000001)))))
        lr_by_feature[f"{group}|{value}"] = {
            "feature_group": group,
            "feature_value": value,
            "sample_size": sample,
            "wins": wins,
            "losses": stats["losses"],
            "baseline_success_rate": _round(baseline),
            "observed_success_rate": _round(observed),
            "raw_lr": _round(raw_lr),
            "shrunk_lr": _round(shrunk),
            "capped_lr": _round(capped),
            "reason": reason,
        }
    return {
        "lr_by_feature": lr_by_feature,
        "baseline_success_rate": _round(baseline),
        "training_rows": len(training),
        "feature_count": len(lr_by_feature),
        "default_LR": float(cfg["default_LR"]),
        "min_LR": float(cfg["min_LR"]),
        "max_LR": float(cfg["max_LR"]),
    }


def compute_dynamic_probability(row: Mapping[str, Any], lr_model: Mapping[str, Any] | None = None, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = _config(config)
    source = deepcopy(dict(row or {}))
    odds = decimal_odds_from(source)
    base_ratio = decimal_to_book_odds_ratio(odds)
    if base_ratio is None:
        return {"dynamic_probability": None, "dynamic_odds_ratio": None, "dynamic_signal_status": "no_odds", "LR_breakdown": [], "blocked_leakage_fields": []}
    extracted = extract_pregame_safe_features(source, cfg)
    model = dict(lr_model or {})
    lr_by_feature = model.get("lr_by_feature", {}) if isinstance(model.get("lr_by_feature", {}), Mapping) else {}
    breakdown: list[dict[str, Any]] = []
    for group, value in extracted["features"].items():
        key = f"{group}|{value}"
        learned = dict(lr_by_feature.get(key, {}))
        if learned:
            breakdown.append(learned)
        else:
            breakdown.append({"feature_group": group, "feature_value": value, "sample_size": 0, "capped_lr": float(cfg["default_LR"]), "reason": "no_lr_data_default_lr"})
    data_age = _float(source.get("data_age_hours") or source.get("odds_age_hours"), 0.0) or 0.0
    applied = apply_lr_multipliers(base_ratio, breakdown, data_age_hours=data_age, lambda_value=float(cfg["recency_lambda"]))
    probability = applied.get("dynamic_probability")
    if probability is not None:
        probability = max(float(cfg["min_dynamic_probability"]), min(float(cfg["max_dynamic_probability"]), float(probability)))
    return {
        **applied,
        "book_odds_ratio": base_ratio,
        "dynamic_probability": probability,
        "data_age_hours": data_age,
        "dynamic_signal_status": "shadow_only",
        **{k: extracted[k] for k in ("blocked_leakage_fields", "pregame_feature_whitelist_used", "pregame_safe_feature_count", "unsafe_feature_count")},
    }


def dynamic_value_metrics(row: Mapping[str, Any], dynamic_probability: float | None = None, lr_model: Mapping[str, Any] | None = None, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = _config(config)
    source = deepcopy(dict(row or {}))
    computed = compute_dynamic_probability(source, lr_model, cfg)
    dynamic_p = dynamic_probability if dynamic_probability is not None else computed.get("dynamic_probability")
    odds = decimal_odds_from(source)
    raw = raw_implied_probability(odds)
    no_vig = no_vig_probability_from(source, raw)
    current = assess_value_pick(source)
    dynamic_edge = None if dynamic_p is None or raw is None else dynamic_p - raw
    dynamic_no_vig_edge = None if dynamic_p is None or no_vig is None else dynamic_p - no_vig
    dynamic_ev = None if dynamic_p is None or odds is None else dynamic_p * odds - 1.0
    dynamic_fair_odds = None if dynamic_p is None or dynamic_p <= 0 else 1.0 / dynamic_p
    status = computed.get("dynamic_signal_status", "shadow_only")
    if odds is None:
        status = "no_odds"
    elif dynamic_p is None:
        status = "no_lr_data"
    elif dynamic_p <= 0 or dynamic_p >= 1:
        status = "unsafe_probability"
    elif dynamic_edge is not None and dynamic_no_vig_edge is not None and dynamic_ev is not None and dynamic_edge > float(cfg["minimum_dynamic_edge"]) and dynamic_no_vig_edge > float(cfg["minimum_dynamic_no_vig_edge"]) and dynamic_ev >= float(cfg["minimum_dynamic_EV"]):
        status = "dynamic_green"
    elif dynamic_ev is not None and dynamic_ev > 0:
        status = "dynamic_yellow"
    else:
        status = "dynamic_red"
    return {
        **computed,
        "decimal_odds": odds,
        "raw_implied_probability": raw,
        "no_vig_implied_probability": no_vig,
        "current_model_probability": current.model_probability,
        "current_edge": current.edge,
        "current_no_vig_edge": current.no_vig_edge,
        "current_EV": current.expected_value,
        "current_value_color": current.color,
        "dynamic_probability": dynamic_p,
        "dynamic_edge": dynamic_edge,
        "dynamic_no_vig_edge": dynamic_no_vig_edge,
        "dynamic_EV": dynamic_ev,
        "dynamic_fair_odds": dynamic_fair_odds,
        "dynamic_signal_status": status,
    }


def _brier(rows: Sequence[Mapping[str, Any]], probability_key: str) -> float | None:
    values = []
    for row in rows:
        win = _is_win(row)
        prob = _prob(row.get(probability_key))
        if win is None or prob is None:
            continue
        values.append((prob - (1.0 if win else 0.0)) ** 2)
    return _round(sum(values) / len(values)) if values else None


def _aggregate(rows: Sequence[Mapping[str, Any]], select_key: str) -> dict[str, Any]:
    selected = [row for row in rows if row.get(select_key)]
    resolved = [row for row in selected if _is_win(row) is not None]
    wins = sum(1 for row in resolved if _is_win(row) is True)
    losses = sum(1 for row in resolved if _is_win(row) is False)
    profit = sum(_profit_units(row, True) for row in resolved)
    roi = profit / len(resolved) if resolved else 0.0
    return {"selected_rows": len(selected), "resolved_rows": len(resolved), "wins": wins, "losses": losses, "win_rate": _round(wins / len(resolved)) if resolved else None, "profit_units": _round(profit), "ROI": _round(roi)}


def evaluate_dynamic_odds_shadow(rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = _config(config)
    all_rows = [deepcopy(dict(row)) for row in rows or []]
    split = split_lr_train_evaluation_rows(all_rows, cfg)
    train_rows = split["training_rows"]
    eval_rows = split["evaluation_rows"]
    lr_model = learn_lr_multipliers(train_rows, cfg)
    dynamic_rows: list[dict[str, Any]] = []
    data_blockers: list[dict[str, Any]] = []
    blocked_fields: set[str] = set()
    for row in eval_rows:
        metrics = dynamic_value_metrics(row, lr_model=lr_model, config=cfg)
        blocked_fields.update(metrics.get("blocked_leakage_fields", []) or [])
        output = {**deepcopy(row), **metrics}
        output["baseline_selected"] = metrics.get("current_value_color") == "GREEN"
        output["dynamic_selected"] = metrics.get("dynamic_signal_status") == "dynamic_green"
        if metrics.get("dynamic_signal_status") == "no_odds":
            data_blockers.append({"finding_type": "data_blocker", "title": "missing_decimal_odds", "decision": "data_blocked", "decision_reason": "rows_are_missing_decimal_odds_needed_for_dynamic_odds", "sample_size": 1, "completed_rows_used": 0, "has_shadow_backtest": False})
        dynamic_rows.append(output)
    baseline = _aggregate(dynamic_rows, "baseline_selected")
    dynamic = _aggregate(dynamic_rows, "dynamic_selected")
    baseline_brier = _brier(dynamic_rows, "current_model_probability")
    dynamic_brier = _brier(dynamic_rows, "dynamic_probability")
    comparison = {
        "baseline_win_rate": baseline.get("win_rate"),
        "dynamic_win_rate": dynamic.get("win_rate"),
        "win_rate_delta": None if baseline.get("win_rate") is None or dynamic.get("win_rate") is None else _round(dynamic["win_rate"] - baseline["win_rate"]),
        "baseline_profit_units": baseline.get("profit_units", 0),
        "dynamic_profit_units": dynamic.get("profit_units", 0),
        "profit_units_delta": _round((dynamic.get("profit_units") or 0) - (baseline.get("profit_units") or 0)),
        "baseline_ROI": baseline.get("ROI", 0),
        "dynamic_ROI": dynamic.get("ROI", 0),
        "ROI_delta": _round((dynamic.get("ROI") or 0) - (baseline.get("ROI") or 0)),
        "baseline_losses": baseline.get("losses", 0),
        "dynamic_losses": dynamic.get("losses", 0),
        "losses_delta": (dynamic.get("losses", 0) - baseline.get("losses", 0)),
        "avoided_losses": max(0, baseline.get("losses", 0) - dynamic.get("losses", 0)),
        "baseline_brier_score": baseline_brier,
        "dynamic_brier_score": dynamic_brier,
        "calibration_delta": None if baseline_brier is None or dynamic_brier is None else _round(baseline_brier - dynamic_brier),
        "baseline_CLV": None,
        "dynamic_CLV": None,
        "CLV_delta": None,
        "CLV_sample_size": 0,
    }
    completed = len([row for row in eval_rows if _is_completed(row)])
    overlap = int(split["train_test_overlap_count"])
    enough = completed >= int(cfg["minimum_completed_rows_for_evaluation"]) and len(train_rows) >= int(cfg["minimum_lr_training_rows"]) and len(eval_rows) >= int(cfg["minimum_lr_evaluation_rows"])
    profit_delta = comparison["profit_units_delta"] or 0
    roi_delta = comparison["ROI_delta"] or 0
    losses_delta = comparison["losses_delta"] or 0
    if not eval_rows or not train_rows:
        decision = "data_blocked"
        reason = "no_safe_train_evaluation_split"
    elif not enough:
        decision = "keep_testing"
        reason = "insufficient_heldout_sample"
    elif overlap > 0:
        decision = "rejected"
        reason = "train_test_leakage_detected"
    elif profit_delta > 0 and roi_delta > 0 and losses_delta <= 0:
        decision = "future_manual_review"
        reason = "dynamic_shadow_improved_on_heldout_rows"
    elif profit_delta < 0 or roi_delta < 0 or losses_delta > 0:
        decision = "rejected"
        reason = "dynamic_shadow_worse"
    else:
        decision = "keep_testing"
        reason = "dynamic_shadow_inconclusive"
    return {
        "rows_scanned": len(all_rows),
        "completed_rows_used": completed,
        "lr_training_rows": len(train_rows),
        "lr_evaluation_rows": len(eval_rows),
        "dynamic_rows_evaluated": len(dynamic_rows),
        "skipped_rows": max(0, len(all_rows) - len(train_rows) - len(eval_rows)),
        "missing_odds_count": sum(1 for row in dynamic_rows if row.get("decimal_odds") is None),
        "missing_result_count": sum(1 for row in all_rows if _is_win(row) is None),
        "missing_lr_feature_count": sum(1 for row in dynamic_rows if not row.get("LR_breakdown")),
        "train_test_overlap_count": overlap,
        "walk_forward_windows_evaluated": split.get("walk_forward_windows_evaluated", 0),
        "evaluation_mode": split["evaluation_mode"],
        "leakage_guard_enabled": split["leakage_guard_enabled"],
        "leakage_guard_reason": split["leakage_guard_reason"],
        "pregame_feature_whitelist_used": True,
        "blocked_leakage_fields": sorted(blocked_fields),
        "pregame_safe_feature_count": sum(int(row.get("pregame_safe_feature_count", 0) or 0) for row in dynamic_rows),
        "unsafe_feature_count": sum(int(row.get("unsafe_feature_count", 0) or 0) for row in dynamic_rows),
        "baseline_metrics": baseline,
        "dynamic_metrics": dynamic,
        "comparison_metrics": {**comparison, "decision": decision, "decision_reason": reason, "overfit_risk": "low" if overlap == 0 else "high", "confidence_level": "medium" if enough else "low"},
        "dynamic_rows": dynamic_rows,
        "lr_model_summary": lr_model,
        "data_blockers": data_blockers,
        "watchlists": [] if enough else [{"finding_type": "watchlist", "title": "dynamic_odds_needs_more_heldout_rows", "decision": "keep_testing", "decision_reason": "insufficient_heldout_sample", "sample_size": len(eval_rows), "completed_rows_used": completed, "has_shadow_backtest": False}],
        "decision": decision,
        "decision_reason": reason,
    }


def build_phase3e_report(rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    evaluation = evaluate_dynamic_odds_shadow(rows, config)
    comparison = evaluation["comparison_metrics"]
    dynamic_rows = evaluation["dynamic_rows"]
    greens = sum(1 for row in dynamic_rows if row.get("dynamic_signal_status") == "dynamic_green")
    yellows = sum(1 for row in dynamic_rows if row.get("dynamic_signal_status") == "dynamic_yellow")
    reds = sum(1 for row in dynamic_rows if row.get("dynamic_signal_status") == "dynamic_red")
    manual_review = []
    rejected = []
    shadow_finding = {
        "title": "Dynamic Odds Predictor Shadow Layer",
        "finding_type": "dynamic_odds_shadow",
        "candidate_type": "dynamic_odds_shadow_probability_layer",
        "affected_sport": "all",
        "affected_market_type": "all",
        "sample_size": evaluation["lr_evaluation_rows"],
        "completed_rows_used": evaluation["completed_rows_used"],
        "has_shadow_backtest": True,
        "decision": evaluation["decision"],
        "decision_reason": evaluation["decision_reason"],
        "eligible_for_manual_review": evaluation["decision"] == "future_manual_review",
        "live_mutation": FORBIDDEN,
        "model_training": FORBIDDEN,
        "stored_data_mutation": FORBIDDEN,
        "repairs_applied_live": 0,
        "comparison_metrics": comparison,
    }
    if evaluation["decision"] == "future_manual_review":
        manual_review.append(shadow_finding)
    if evaluation["decision"] == "rejected":
        rejected.append(shadow_finding)
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    report = {
        "phase": PHASE_3E,
        "shadow_mode": "ON",
        "live_mutation": FORBIDDEN,
        "model_training": FORBIDDEN,
        "stored_data_mutation": FORBIDDEN,
        "repair_activation": OFF,
        "dynamic_odds_predictor": SHADOW_ONLY,
        "dynamic_odds_live_activation": OFF,
        "dynamic_odds_applied_live": 0,
        "dynamic_odds_applied_live_count": 0,
        "repairs_applied_live": 0,
        "live_repairs_applied_count": 0,
        "rows_scanned": evaluation["rows_scanned"],
        "completed_rows_used": evaluation["completed_rows_used"],
        "lr_training_rows": evaluation["lr_training_rows"],
        "lr_evaluation_rows": evaluation["lr_evaluation_rows"],
        "evaluation_mode": evaluation["evaluation_mode"],
        "leakage_guard_enabled": evaluation["leakage_guard_enabled"],
        "leakage_guard_reason": evaluation["leakage_guard_reason"],
        "train_test_overlap_count": evaluation["train_test_overlap_count"],
        "pregame_feature_whitelist_used": evaluation["pregame_feature_whitelist_used"],
        "blocked_leakage_fields": evaluation["blocked_leakage_fields"],
        "walk_forward_windows_evaluated": evaluation["walk_forward_windows_evaluated"],
        "pregame_safe_feature_count": evaluation["pregame_safe_feature_count"],
        "unsafe_feature_count": evaluation["unsafe_feature_count"],
        "lr_model_summary": evaluation["lr_model_summary"],
        "dynamic_rows": evaluation["dynamic_rows"],
        "dynamic_value_summary": {"dynamic_green_count": greens, "dynamic_yellow_count": yellows, "dynamic_red_count": reds},
        "baseline_metrics": evaluation["baseline_metrics"],
        "dynamic_metrics": evaluation["dynamic_metrics"],
        "comparison_metrics": comparison,
        "data_blockers": evaluation["data_blockers"],
        "watchlists": evaluation["watchlists"],
        "rejected_dynamic_rules": rejected,
        "rejected_repairs": rejected,
        "manual_review_queue": manual_review,
        "repair_candidates": [] if evaluation["decision"] != "keep_testing" else [shadow_finding],
        "shadow_tested_repairs": [shadow_finding],
        "safety_gates": {
            "live_mutation": FORBIDDEN,
            "model_training": FORBIDDEN,
            "stored_data_mutation": FORBIDDEN,
            "repair_activation": OFF,
            "dynamic_odds_live_activation": OFF,
            "dynamic_odds_applied_live": 0,
            "dynamic_odds_applied_live_count": 0,
            "repairs_applied_live": 0,
            "automatic_live_promotion": FORBIDDEN,
        },
        "summary_counts": {
            "dynamic_rows_evaluated_count": evaluation["dynamic_rows_evaluated"],
            "data_blockers_count": len(evaluation["data_blockers"]),
            "watchlists_count": len(evaluation["watchlists"]),
            "rejected_dynamic_rules_count": len(rejected),
            "manual_review_eligible_count": len(manual_review),
            "dynamic_green_count": greens,
            "dynamic_yellow_count": yellows,
            "dynamic_red_count": reds,
            "dynamic_odds_applied_live_count": 0,
        },
        "generated_at_utc": generated,
    }
    run_payload = deepcopy(report)
    run_payload.pop("generated_at_utc", None)
    run_id = _stable_hash(run_payload)[:24]
    report["dynamic_shadow_run_id"] = run_id
    report["memory_run_id"] = run_id
    return report
