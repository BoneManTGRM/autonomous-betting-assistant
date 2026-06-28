from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Sequence

PHASE_3C = "Phase 3C Shadow Backtest"
FORBIDDEN = "FORBIDDEN"
SHADOW_ON = "ON"

DEFAULT_CONFIG: dict[str, Any] = {
    "minimum_sample_for_candidate": 25,
    "minimum_sample_for_manual_review": 50,
    "minimum_ROI_improvement": 0.03,
    "minimum_profit_units_improvement": 1.0,
    "maximum_overfit_risk": "medium",
    "minimum_CLV_sample": 10,
    "severe_CLV_degradation": -0.02,
    "high_overfit_sample_ceiling": 10,
    "soccer_low_price_threshold": 1.80,
    "soccer_small_edge_threshold": 0.03,
}

ENTRY_ODDS_COLUMNS = (
    "decimal_price",
    "odds",
    "price",
    "best_price",
    "locked_decimal_price",
    "open_decimal_price",
)
CLOSING_ODDS_COLUMNS = (
    "closing_decimal_price",
    "closing_odds",
    "close_decimal_price",
    "close_odds",
    "market_close_decimal",
    "closing_price",
    "close_price",
)
CLV_COLUMNS = ("clv", "clv_percent", "closing_line_value")
RESULT_COLUMNS = ("result", "grade", "outcome", "result_status", "official_result", "final_result")
MARKET_COLUMNS = ("market_type", "market", "bet_type")
SPORT_COLUMNS = ("sport", "league", "competition", "sport_key")
PICK_COLUMNS = ("prediction", "pick", "selection", "market", "market_type")


def _cfg(config: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = dict(DEFAULT_CONFIG)
    if config:
        merged.update(dict(config))
    return merged


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _key(value: Any) -> str:
    return _text(value).lower().replace("-", "_").replace(" ", "_")


def _first(row: Mapping[str, Any], names: Sequence[str], default: Any = "") -> Any:
    for name in names:
        if name in row and _text(row.get(name)) != "":
            return row.get(name)
    lower = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        if name.lower() in lower and _text(lower.get(name.lower())) != "":
            return lower.get(name.lower())
    return default


def _float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    text = _text(value).replace("%", "").replace(",", "")
    if text == "":
        return default
    if text.startswith("+") and text[1:].replace(".", "", 1).isdigit():
        # Do not silently convert American odds. Treat as not decimal.
        return default
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def _safe_decimal(value: Any) -> float | None:
    number = _float(value)
    if number is None:
        return None
    if 1.01 <= number <= 100:
        return number
    return None


def _result_value(row: Mapping[str, Any]) -> str:
    return _key(_first(row, RESULT_COLUMNS))


def _result_category(row: Mapping[str, Any]) -> str:
    result = _result_value(row)
    if result in {"win", "won", "winner", "w"}:
        return "win"
    if result in {"loss", "lost", "loser", "l"}:
        return "loss"
    if result in {"push", "void", "cancel", "canceled", "cancelled", "refunded"}:
        return "push" if result == "push" else "void"
    return "missing"


def _stake(row: Mapping[str, Any]) -> float:
    value = _float(_first(row, ("stake_units", "stake", "unit_size", "units")))
    return value if value is not None and value > 0 else 1.0


def _profit(row: Mapping[str, Any]) -> float:
    explicit = _float(_first(row, ("profit_units", "profit", "pnl_units", "net_units")))
    if explicit is not None:
        return explicit
    stake = _stake(row)
    result = _result_category(row)
    price = _safe_decimal(_first(row, ENTRY_ODDS_COLUMNS))
    if result == "win":
        return stake * ((price or 1.0) - 1.0)
    if result == "loss":
        return -stake
    return 0.0


def _average(values: Sequence[float]) -> float | None:
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _round_or_none(value: float | None) -> float | None:
    return round(value, 6) if value is not None else None


def _drawdown(profits: Sequence[float]) -> float:
    running = 0.0
    peak = 0.0
    max_dd = 0.0
    for profit in profits:
        running += profit
        peak = max(peak, running)
        max_dd = min(max_dd, running - peak)
    return round(abs(max_dd), 6)


def _row_id(row: Mapping[str, Any], index: int) -> str:
    basis = "|".join(str(row.get(k, "")) for k in ("event", "event_id", "prediction", "market", "market_type", "decimal_price", "result"))
    if not basis.strip("|"):
        basis = str(index)
    return sha256(basis.encode("utf-8")).hexdigest()[:12]


def calculate_clv(row: Mapping[str, Any]) -> float | None:
    for column in CLV_COLUMNS:
        explicit = _float(row.get(column))
        if explicit is not None:
            if column in {"clv_percent", "closing_line_value"} and abs(explicit) > 1:
                return explicit / 100.0
            return explicit
    entry = _safe_decimal(_first(row, ENTRY_ODDS_COLUMNS))
    close = _safe_decimal(_first(row, CLOSING_ODDS_COLUMNS))
    if entry is None or close is None or close <= 0:
        return None
    market = _text(_first(row, MARKET_COLUMNS)).lower()
    if market and any(token in market for token in ("spread", "total", "handicap")):
        line = _first(row, ("line_point", "line", "point", "spread"))
        if _text(line) == "":
            return None
    return round(entry / close - 1.0, 6)


def normalize_backtest_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(rows or []):
        row = dict(raw or {})
        result = _result_category(row)
        entry_decimal = _safe_decimal(_first(row, ENTRY_ODDS_COLUMNS))
        closing_decimal = _safe_decimal(_first(row, CLOSING_ODDS_COLUMNS))
        stake = _stake(row)
        profit = _profit(row)
        row["_phase3c_row_id"] = _row_id(row, index)
        row["_result_category"] = result
        row["_completed"] = result in {"win", "loss", "push", "void"}
        row["_entry_decimal"] = entry_decimal
        row["_closing_decimal"] = closing_decimal
        row["_stake_units"] = stake
        row["_profit_units"] = profit
        row["_clv"] = calculate_clv(row)
        normalized.append(row)
    return normalized


def baseline_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = normalize_backtest_rows(rows)
    completed = [row for row in normalized if row["_completed"]]
    wins = sum(1 for row in completed if row["_result_category"] == "win")
    losses = sum(1 for row in completed if row["_result_category"] == "loss")
    pushes = sum(1 for row in completed if row["_result_category"] == "push")
    voids = sum(1 for row in completed if row["_result_category"] == "void")
    stake_units = sum(float(row["_stake_units"]) for row in completed)
    profits = [float(row["_profit_units"]) for row in completed]
    profit_units = sum(profits)
    prices = [row["_entry_decimal"] for row in completed if row.get("_entry_decimal") is not None]
    clvs = [row["_clv"] for row in completed if row.get("_clv") is not None]
    model_probs = [_float(_first(row, ("model_probability", "probability", "confidence"))) for row in completed]
    edges = [_float(_first(row, ("edge", "model_market_edge", "no_vig_edge"))) for row in completed]
    evs = [_float(_first(row, ("EV", "ev", "expected_value", "expected_value_per_unit"))) for row in completed]
    completed_count = len(completed)
    missing_result_count = len(normalized) - completed_count
    missing_odds_count = sum(1 for row in normalized if row.get("_entry_decimal") is None)
    roi = profit_units / stake_units if stake_units > 0 else None
    return {
        "sample_size": len(normalized),
        "completed_rows_used": completed_count,
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "voids": voids,
        "win_rate": round(wins / (wins + losses), 6) if wins + losses else None,
        "stake_units": round(stake_units, 6),
        "profit_units": round(profit_units, 6),
        "ROI": round(roi, 6) if roi is not None else None,
        "average_model_probability": _round_or_none(_average([v for v in model_probs if v is not None])),
        "average_edge": _round_or_none(_average([v for v in edges if v is not None])),
        "average_EV": _round_or_none(_average([v for v in evs if v is not None])),
        "average_decimal_price": _round_or_none(_average(prices)),
        "average_CLV": _round_or_none(_average(clvs)),
        "CLV_sample_size": len(clvs),
        "max_drawdown_units": _drawdown(profits),
        "loss_count": losses,
        "bad_pick_count": losses,
        "missing_result_count": missing_result_count,
        "missing_odds_count": missing_odds_count,
    }


def _is_soccer(row: Mapping[str, Any]) -> bool:
    full = " ".join(str(row.get(k, "")) for k in (*SPORT_COLUMNS, "event", "league")).lower()
    return any(token in full for token in ("soccer", "football", "futbol", "fútbol", "fifa", "uefa", "liga", "league"))


def _is_draw(row: Mapping[str, Any]) -> bool:
    text = " ".join(str(row.get(k, "")) for k in ("result", "grade", "outcome", "final_result", "winner", "prediction", "pick")).lower()
    return "draw" in text or "tie" in text or "empate" in text


def _is_soccer_draw_risk(row: Mapping[str, Any], config: Mapping[str, Any]) -> bool:
    market = _text(_first(row, MARKET_COLUMNS)).lower()
    if not _is_soccer(row) or "moneyline" not in market:
        return False
    price = _safe_decimal(_first(row, ENTRY_ODDS_COLUMNS))
    edge = _float(_first(row, ("edge", "model_market_edge", "no_vig_edge")), 0.0) or 0.0
    probability = _float(_first(row, ("model_probability", "probability", "confidence")), 0.0) or 0.0
    return bool(
        _is_draw(row)
        or (price is not None and price <= float(config["soccer_low_price_threshold"]))
        or edge <= float(config["soccer_small_edge_threshold"])
        or probability >= 0.58 and _result_category(row) == "loss"
    )


def _is_combat(row: Mapping[str, Any]) -> bool:
    text = " ".join(str(row.get(k, "")) for k in (*SPORT_COLUMNS, *MARKET_COLUMNS, *PICK_COLUMNS)).lower()
    return any(token in text for token in ("boxing", "mma", "ufc", "combat", "fight", "method", "round", "ko", "submission", "decision", "prop"))


def _finding(title: str, finding_type: str, **extra: Any) -> dict[str, Any]:
    basis = f"{title}|{finding_type}|{extra.get('sample_size', 0)}|{extra.get('affected_sport', '')}|{extra.get('affected_market_type', '')}"
    result = {
        "finding_id": sha256(basis.encode("utf-8")).hexdigest()[:12],
        "finding_type": finding_type,
        "candidate_type": finding_type,
        "title": title,
        "description": extra.pop("description", title.replace("_", " ")),
        "affected_sport": extra.pop("affected_sport", ""),
        "affected_market_type": extra.pop("affected_market_type", ""),
        "sample_size": int(extra.pop("sample_size", 0) or 0),
        "completed_rows_used": int(extra.pop("completed_rows_used", 0) or 0),
        "minimum_required_sample": int(extra.pop("minimum_required_sample", DEFAULT_CONFIG["minimum_sample_for_candidate"])),
        "has_result_data": bool(extra.pop("has_result_data", False)),
        "has_closing_odds": bool(extra.pop("has_closing_odds", False)),
        "has_clv": bool(extra.pop("has_clv", False)),
        "clv_sample_size": int(extra.pop("clv_sample_size", 0) or 0),
        "has_shadow_backtest": bool(extra.pop("has_shadow_backtest", False)),
        "data_blockers": list(extra.pop("data_blockers", [])),
        "unavailable_options": list(extra.pop("unavailable_options", [])),
        "baseline_metrics": extra.pop("baseline_metrics", {}),
        "shadow_metrics": extra.pop("shadow_metrics", {}),
        "comparison_metrics": extra.pop("comparison_metrics", {}),
        "decision": extra.pop("decision", finding_type),
        "decision_reason": extra.pop("decision_reason", ""),
        "eligible_for_manual_review": bool(extra.pop("eligible_for_manual_review", False)),
        "live_mutation": FORBIDDEN,
        "model_training": FORBIDDEN,
        "stored_data_mutation": FORBIDDEN,
        "phase": PHASE_3C,
    }
    result.update(extra)
    return result


def detect_data_blockers(rows: Sequence[Mapping[str, Any]], candidates: Sequence[Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    normalized = normalize_backtest_rows(rows)
    metrics = baseline_metrics(normalized)
    blockers: list[dict[str, Any]] = []
    if normalized and metrics["CLV_sample_size"] == 0:
        blockers.append(_finding("missing_closing_odds", "data_blocker", sample_size=len(normalized), description="Closing odds or comparable CLV data are unavailable for CLV-based evaluation."))
    if metrics["missing_result_count"]:
        blockers.append(_finding("missing_result_or_grade", "data_blocker", sample_size=metrics["missing_result_count"], description="Rows are missing completed result/grade data."))
    if metrics["missing_odds_count"]:
        blockers.append(_finding("missing_decimal_odds", "data_blocker", sample_size=metrics["missing_odds_count"], description="Rows are missing decimal odds needed for price-based simulation."))
    if metrics["completed_rows_used"] < int(DEFAULT_CONFIG["minimum_sample_for_candidate"]):
        blockers.append(_finding("insufficient_completed_result_rows", "data_blocker", sample_size=metrics["completed_rows_used"], description="Completed result rows are below the candidate threshold."))
    soccer_rows = [row for row in normalized if _is_soccer(row)]
    if soccer_rows:
        if not any(_text(row.get("draw_no_bet_odds")) or _text(row.get("dnb_odds")) for row in soccer_rows):
            blockers.append(_finding("missing_draw_no_bet_odds", "data_blocker", sample_size=len(soccer_rows), description="DNB repair option cannot be simulated without draw-no-bet odds."))
        if not any(_text(row.get("double_chance_odds")) or _text(row.get("dc_odds")) for row in soccer_rows):
            blockers.append(_finding("missing_double_chance_odds", "data_blocker", sample_size=len(soccer_rows), description="Double-chance repair option cannot be simulated without double-chance odds."))
    return blockers


def detect_watchlists(rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = _cfg(config)
    normalized = normalize_backtest_rows(rows)
    metrics = baseline_metrics(normalized)
    watchlists: list[dict[str, Any]] = []
    if metrics["completed_rows_used"] < int(cfg["minimum_sample_for_candidate"]):
        watchlists.append(_finding("insufficient_sample_size", "watchlist", sample_size=metrics["completed_rows_used"], description="Keep collecting completed rows before repair candidacy."))
    combat = [row for row in normalized if _is_combat(row)]
    if combat and len(combat) < int(cfg["minimum_sample_for_candidate"]):
        watchlists.append(_finding("combat_method_round_volatility", "watchlist", affected_sport="combat", affected_market_type="method_round_prop", sample_size=len(combat), description="Combat method/round markets remain capped to watchlist until sample size and ROI gates are met."))
    soccer = [row for row in normalized if _is_soccer_draw_risk(row, cfg)]
    if soccer and len(soccer) < int(cfg["minimum_sample_for_candidate"]):
        watchlists.append(_finding("soccer_draw_risk_watchlist", "watchlist", affected_sport="soccer", affected_market_type="moneyline", sample_size=len(soccer), description="Soccer draw-risk signal needs more completed market data before repair candidacy."))
    if normalized and metrics["CLV_sample_size"] == 0:
        watchlists.append(_finding("clv_unavailable_watchlist", "watchlist", sample_size=len(normalized), description="CLV is unavailable; use ROI-only shadow testing until closing odds exist."))
    return watchlists


def classify_findings(rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = _cfg(config)
    normalized = normalize_backtest_rows(rows)
    metrics = baseline_metrics(normalized)
    findings = []
    findings.extend(detect_data_blockers(normalized))
    findings.extend(detect_watchlists(normalized, cfg))
    if metrics["completed_rows_used"] >= int(cfg["minimum_sample_for_candidate"]):
        findings.append(
            _finding(
                "phase3c_shadow_repair_candidate",
                "repair_candidate",
                sample_size=metrics["completed_rows_used"],
                completed_rows_used=metrics["completed_rows_used"],
                description="Enough completed rows exist for Shadow Backtest simulation.",
                has_result_data=True,
                has_closing_odds=metrics["CLV_sample_size"] > 0,
                has_clv=metrics["CLV_sample_size"] > 0,
                clv_sample_size=metrics["CLV_sample_size"],
            )
        )
    return findings


def _simulate_no_play(rows: Sequence[Mapping[str, Any]], risky_ids: set[str]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows if row.get("_phase3c_row_id") not in risky_ids]


def _simulate_reduce_stake(rows: Sequence[Mapping[str, Any]], risky_ids: set[str], factor: float = 0.5) -> list[dict[str, Any]]:
    shadow = []
    for row in rows:
        clean = dict(row)
        if clean.get("_phase3c_row_id") in risky_ids:
            clean["_stake_units"] = float(clean.get("_stake_units", 1.0)) * factor
            clean["_profit_units"] = float(clean.get("_profit_units", 0.0)) * factor
            clean["stake_units"] = clean["_stake_units"]
            clean["profit_units"] = clean["_profit_units"]
        shadow.append(clean)
    return shadow


def simulate_shadow_repairs(rows: Sequence[Mapping[str, Any]], candidates: Sequence[Mapping[str, Any]] | None = None, config: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = _cfg(config)
    normalized = normalize_backtest_rows(rows)
    if not normalized:
        return []
    risky_soccer = {row["_phase3c_row_id"] for row in normalized if _is_soccer_draw_risk(row, cfg)}
    if not risky_soccer:
        risky_soccer = {row["_phase3c_row_id"] for row in normalized if _result_category(row) == "loss"}
    options: list[dict[str, Any]] = []
    for option, shadow_rows, unavailable in [
        ("no_play", _simulate_no_play(normalized, risky_soccer), []),
        ("reduce_stake_50_percent", _simulate_reduce_stake(normalized, risky_soccer, 0.5), []),
        ("draw_no_bet_if_available", normalized, ["missing_draw_no_bet_odds"]),
        ("double_chance_if_available", normalized, ["missing_double_chance_odds"]),
    ]:
        baseline = baseline_metrics(normalized)
        shadow = baseline_metrics(shadow_rows)
        comparison = compare_baseline_to_shadow(baseline, shadow)
        decision = "data_blocked" if unavailable else classify_shadow_decision(comparison, cfg)["decision"]
        options.append(
            {
                "finding_id": sha256(option.encode("utf-8")).hexdigest()[:12],
                "finding_type": "shadow_tested_repair" if not unavailable else "data_blocker",
                "candidate_type": option,
                "title": option,
                "description": f"Shadow simulation for {option}.",
                "affected_sport": "soccer" if risky_soccer else "",
                "affected_market_type": "moneyline" if risky_soccer else "",
                "sample_size": int(baseline["completed_rows_used"]),
                "completed_rows_used": int(baseline["completed_rows_used"]),
                "minimum_required_sample": int(cfg["minimum_sample_for_candidate"]),
                "has_result_data": int(baseline["completed_rows_used"]) > 0,
                "has_closing_odds": int(baseline["CLV_sample_size"]) > 0,
                "has_clv": int(baseline["CLV_sample_size"]) > 0,
                "clv_sample_size": int(baseline["CLV_sample_size"]),
                "has_shadow_backtest": not unavailable,
                "data_blockers": list(unavailable),
                "unavailable_options": [option] if unavailable else [],
                "baseline_metrics": baseline,
                "shadow_metrics": shadow,
                "comparison_metrics": comparison,
                "decision": decision,
                "decision_reason": "Required market odds are unavailable." if unavailable else comparison["decision_reason"],
                "eligible_for_manual_review": decision == "future_manual_review",
                "live_mutation": FORBIDDEN,
                "model_training": FORBIDDEN,
                "stored_data_mutation": FORBIDDEN,
                "phase": PHASE_3C,
            }
        )
    return options


def compare_baseline_to_shadow(baseline: Mapping[str, Any], shadow: Mapping[str, Any]) -> dict[str, Any]:
    baseline_roi = baseline.get("ROI")
    shadow_roi = shadow.get("ROI")
    baseline_clv = baseline.get("average_CLV")
    shadow_clv = shadow.get("average_CLV")
    comparison = {
        "baseline_sample_size": baseline.get("completed_rows_used", 0),
        "shadow_sample_size": shadow.get("completed_rows_used", 0),
        "baseline_win_rate": baseline.get("win_rate"),
        "shadow_win_rate": shadow.get("win_rate"),
        "win_rate_delta": _delta(shadow.get("win_rate"), baseline.get("win_rate")),
        "baseline_profit_units": baseline.get("profit_units", 0.0),
        "shadow_profit_units": shadow.get("profit_units", 0.0),
        "profit_units_delta": _delta(shadow.get("profit_units"), baseline.get("profit_units")),
        "baseline_ROI": baseline_roi,
        "shadow_ROI": shadow_roi,
        "ROI_delta": _delta(shadow_roi, baseline_roi),
        "baseline_losses": baseline.get("losses", 0),
        "shadow_losses": shadow.get("losses", 0),
        "losses_delta": _delta(shadow.get("losses"), baseline.get("losses")),
        "avoided_losses": max(int(baseline.get("losses", 0) or 0) - int(shadow.get("losses", 0) or 0), 0),
        "avoided_bad_picks": max(int(baseline.get("bad_pick_count", 0) or 0) - int(shadow.get("bad_pick_count", 0) or 0), 0),
        "baseline_CLV": baseline_clv,
        "shadow_CLV": shadow_clv,
        "CLV_delta": _delta(shadow_clv, baseline_clv),
        "CLV_sample_size": min(int(baseline.get("CLV_sample_size", 0) or 0), int(shadow.get("CLV_sample_size", 0) or 0)),
        "confidence_level": _confidence_level(int(baseline.get("completed_rows_used", 0) or 0)),
        "overfit_risk": _overfit_risk(int(baseline.get("completed_rows_used", 0) or 0)),
    }
    decision = classify_shadow_decision(comparison)
    comparison.update(decision)
    return comparison


def _delta(new: Any, old: Any) -> float | None:
    a = _float(new)
    b = _float(old)
    if a is None or b is None:
        return None
    return round(a - b, 6)


def _confidence_level(sample_size: int) -> str:
    if sample_size >= 100:
        return "high"
    if sample_size >= 50:
        return "medium"
    if sample_size >= 25:
        return "low"
    return "very_low"


def _overfit_risk(sample_size: int) -> str:
    if sample_size <= int(DEFAULT_CONFIG["high_overfit_sample_ceiling"]):
        return "high"
    if sample_size < int(DEFAULT_CONFIG["minimum_sample_for_manual_review"]):
        return "medium"
    return "low"


def _delta_value(comparison: Mapping[str, Any], key: str) -> float:
    return _float(comparison.get(key), 0.0) or 0.0


def classify_shadow_decision(comparison: Mapping[str, Any], config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = _cfg(config)
    sample = int(comparison.get("baseline_sample_size", 0) or 0)
    roi_delta = _delta_value(comparison, "ROI_delta")
    profit_delta = _delta_value(comparison, "profit_units_delta")
    losses_delta = _delta_value(comparison, "losses_delta")
    clv_delta = comparison.get("CLV_delta")
    overfit = str(comparison.get("overfit_risk", "high"))
    if sample < int(cfg["minimum_sample_for_manual_review"]):
        return {"decision": "rejected_repair", "decision_reason": "insufficient_sample_size"}
    if roi_delta < float(cfg["minimum_ROI_improvement"]):
        return {"decision": "rejected_repair", "decision_reason": "ROI improvement below gate"}
    if profit_delta < float(cfg["minimum_profit_units_improvement"]):
        return {"decision": "rejected_repair", "decision_reason": "profit improvement below gate"}
    if losses_delta > 0:
        return {"decision": "rejected_repair", "decision_reason": "losses increased"}
    if clv_delta is not None and clv_delta < float(cfg["severe_CLV_degradation"]):
        return {"decision": "rejected_repair", "decision_reason": "CLV worsened materially"}
    if overfit == "high":
        return {"decision": "rejected_repair", "decision_reason": "high_overfit_risk"}
    return {"decision": "future_manual_review", "decision_reason": "Shadow metrics improved and safety gates remain closed."}


def build_phase3c_report(rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = _cfg(config)
    safe_rows = [dict(row) for row in rows or []]
    normalized = normalize_backtest_rows(safe_rows)
    baseline = baseline_metrics(normalized)
    findings = classify_findings(normalized, cfg)
    blockers = [item for item in findings if item.get("finding_type") == "data_blocker"]
    watchlists = [item for item in findings if item.get("finding_type") == "watchlist"]
    repair_candidates = [item for item in findings if item.get("finding_type") == "repair_candidate"]
    shadow_tests = simulate_shadow_repairs(normalized, repair_candidates, cfg)
    rejected = [item for item in shadow_tests if item.get("decision") == "rejected_repair"]
    manual = [item for item in shadow_tests if item.get("decision") == "future_manual_review"]
    summary_counts = {
        "data_blockers_count": len(blockers),
        "watchlists_count": len(watchlists),
        "repair_candidates_count": len(repair_candidates),
        "shadow_tested_repairs_count": len([item for item in shadow_tests if item.get("has_shadow_backtest")]),
        "manual_review_eligible_count": len(manual),
        "rejected_repairs_count": len(rejected),
        "live_repairs_applied_count": 0,
    }
    return {
        "phase": PHASE_3C,
        "shadow_mode": SHADOW_ON,
        "live_mutation": FORBIDDEN,
        "model_training": FORBIDDEN,
        "stored_data_mutation": FORBIDDEN,
        "repairs_applied_live": 0,
        "rows_scanned": len(safe_rows),
        "completed_rows_used": baseline["completed_rows_used"],
        "baseline_metrics": baseline,
        "data_blockers": blockers,
        "watchlists": watchlists,
        "repair_candidates": repair_candidates,
        "shadow_tested_repairs": shadow_tests,
        "rejected_repairs": rejected,
        "manual_review_queue": manual,
        "safety_gates": {
            "live_mutation": FORBIDDEN,
            "model_training": FORBIDDEN,
            "stored_data_mutation": FORBIDDEN,
            "repair_activation": "OFF",
            "live_repairs_applied_count": 0,
        },
        "summary_counts": summary_counts,
        "generated_at_utc": _utc_now(),
    }
