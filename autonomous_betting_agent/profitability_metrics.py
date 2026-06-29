from typing import Any, Mapping, Sequence

import pandas as pd

PLAYABLE_STATUS = "playable"
WATCHLIST_STATUS = "watchlist"
AVOID_STATUS = "avoid"
PREDICTION_ONLY_STATUS = "prediction_only"
TRUE_VALUES = {"1", "true", "yes", "y", "ready", "published", "pass", "passed", "complete", "completed"}
RESULTS = {"w": "win", "won": "win", "win": "win", "l": "loss", "lost": "loss", "loss": "loss", "push": "push", "tie": "push", "draw": "push", "void": "cancel", "cancel": "cancel", "cancelled": "cancel", "canceled": "cancel", "pending": "pending", "open": "pending", "": "pending"}
WATCH = ("watchlist", "price watch", "watch", "monitor")
INFO = ("prediction only", "prediction-only", "research", "learning", "analysis only", "informational")
BAD = ("blocked", "avoid", "no play", "not playable", "removed", "unsafe", "missing", "red flag")


def text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    value = str(value).strip()
    return "" if value.lower() in {"none", "nan", "null", "nat"} else value


def truthy(value: Any) -> bool:
    return text(value).lower() in TRUE_VALUES


def num(value: Any) -> float | None:
    raw = text(value)
    if not raw:
        return None
    try:
        return float(raw.replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def first(row: Mapping[str, Any], names: Sequence[str]) -> Any:
    for name in names:
        if text(row.get(name)):
            return row.get(name)
    return None


def prob(value: Any) -> float | None:
    value = num(value)
    if value is None:
        return None
    value = value / 100 if value > 1 else value
    return value if 0 <= value <= 1 else None


def dec_odds(value: Any) -> float | None:
    value = num(value)
    if value is None:
        return None
    if value >= 100:
        return round(value / 100 + 1, 6)
    if value <= -100:
        return round(100 / abs(value) + 1, 6)
    return value if value > 1 else None


def normalize_result(value: Any) -> str:
    key = text(value).lower().replace(" ", "_").replace("-", "_")
    return RESULTS.get(key, key or "pending")


def event_key(row: Mapping[str, Any]) -> str:
    return text(first(row, ("proof_id", "event_id", "event", "public_event", "event_name", "matchup", "game", "fixture")))


def pick_key(row: Mapping[str, Any]) -> str:
    return "|".join(text(first(row, names)) for names in (("event", "public_event", "event_name", "matchup", "game", "fixture"), ("prediction", "public_pick", "pick", "selection"), ("market_type", "market", "market_name"), ("bookmaker", "sportsbook", "book")))


def status_text(row: Mapping[str, Any]) -> str:
    fields = ("advisory_status", "official_status_label", "official_publish_status", "publish_status", "report_lane", "report_lane_v2", "recommended_action", "consumer_action", "learning_status", "data_issue_reason", "blocked_reason", "blocker", "blockers", "market_blocker")
    return " | ".join(text(row.get(field)) for field in fields if text(row.get(field))).lower()


def blocker_reason(row: Mapping[str, Any]) -> str:
    for name in ("data_issue_reason", "blocked_reason", "blocker", "blockers", "market_blocker", "schema_mapper_missing_required_fields"):
        if text(row.get(name)):
            return text(row.get(name))
    return "blocked marker" if any(marker in status_text(row) for marker in BAD) else ""


def row_values(row: Mapping[str, Any]) -> dict[str, Any]:
    odds = dec_odds(first(row, ("decimal_odds", "decimal_price", "best_price", "average_price", "avg_price", "odds_decimal", "odds", "price", "odds_at_pick")))
    model = prob(first(row, ("learned_model_probability", "final_adjusted_probability", "adjusted_model_probability", "model_probability_clean", "model_probability", "probability", "confidence")))
    market = prob(first(row, ("no_vig_implied_probability", "market_probability_no_vig", "market_probability", "raw_implied_probability", "implied_probability"))) or (1 / odds if odds and odds > 1 else None)
    edge = num(first(row, ("edge", "model_market_edge", "raw_edge", "market_edge")))
    edge = (edge / 100 if edge is not None and abs(edge) > 1 else edge) if edge is not None else (model - market if model is not None and market is not None else None)
    no_vig_edge = num(first(row, ("no_vig_edge", "novig_edge", "no_vig_market_edge")))
    no_vig_edge = no_vig_edge / 100 if no_vig_edge is not None and abs(no_vig_edge) > 1 else no_vig_edge
    if no_vig_edge is None:
        no_vig_market = prob(first(row, ("no_vig_implied_probability", "market_probability_no_vig")))
        no_vig_edge = model - no_vig_market if model is not None and no_vig_market is not None else edge
    ev = num(first(row, ("expected_value_per_unit", "ev", "expected_value", "roi_edge")))
    ev = ev / 100 if ev is not None and abs(ev) > 1 else ev
    if ev is None and model is not None and odds is not None:
        ev = model * odds - 1
    clv = num(first(row, ("manual_clv", "clv", "clv_delta", "closing_line_value_delta")))
    clv = clv / 100 if clv is not None and abs(clv) > 1 else clv
    if clv is None:
        close_odds = dec_odds(first(row, ("closing_decimal_odds", "closing_odds", "close_odds")))
        clv = close_odds - odds if odds is not None and close_odds is not None else None
    source = text(first(row, ("odds_source", "bookmaker", "sportsbook", "book"))).lower()
    verified = (truthy(row.get("odds_verified")) or truthy(row.get("price_verified")) or bool(source)) and odds is not None and not any(token in source for token in ("missing", "unavailable", "api limit", "rate limit", "offline", "model_only", "simulated"))
    blocked = bool(blocker_reason(row)) or truthy(row.get("blocked")) or truthy(row.get("tennis_blocked"))
    lane_text = status_text(row)
    playable_gate = verified and model is not None and edge is not None and no_vig_edge is not None and ev is not None and edge > 0 and no_vig_edge > 0 and ev > 0 and not blocked
    status = PLAYABLE_STATUS if playable_gate else WATCHLIST_STATUS if any(marker in lane_text for marker in WATCH) else PREDICTION_ONLY_STATUS if any(marker in lane_text for marker in INFO) else AVOID_STATUS
    result = normalize_result(first(row, ("result", "result_status", "grade", "outcome", "pick_result")))
    units = num(first(row, ("stake_units", "units", "risk_units", "recommended_units", "unit_size"))) or 1.0
    explicit_profit = num(first(row, ("profit_units", "net_units", "pnl_units", "return_units")))
    if explicit_profit is not None:
        profit = explicit_profit
    elif result == "win":
        profit = (odds - 1) * units if odds is not None else units
    elif result == "loss":
        profit = -units
    else:
        profit = 0.0
    settled_units = units if result in {"win", "loss"} else 0.0
    return {"status": status, "result": result, "event_key": event_key(row), "decimal_odds": odds, "model_probability": model, "market_probability": market, "edge": edge, "no_vig_edge": no_vig_edge, "expected_value": ev, "clv": clv, "stake_units": units, "profit_units": profit, "settled_stake_units": settled_units, "odds_verified": verified, "blocker": blocker_reason(row)}


def rnd(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(float(value), digits)


def avg(values: Sequence[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return sum(clean) / len(clean) if clean else None


def record(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    wins = sum(row.get("result") == "win" for row in rows)
    losses = sum(row.get("result") == "loss" for row in rows)
    pushes = sum(row.get("result") == "push" for row in rows)
    cancels = sum(row.get("result") == "cancel" for row in rows)
    settled = wins + losses
    return {"wins": wins, "losses": losses, "pushes": pushes, "cancels": cancels, "win_rate_ex_push_cancel": rnd(wins / settled) if settled else None}


def roi(rows: Sequence[Mapping[str, Any]]) -> float | None:
    stake = sum(float(row.get("settled_stake_units") or 0) for row in rows)
    return sum(float(row.get("profit_units") or 0) for row in rows) / stake if stake > 0 else None


def summarize_profitability(rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    frame = pd.DataFrame() if rows is None else rows.copy(deep=True) if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows))
    source_rows = [dict(row) for _, row in frame.iterrows()]
    metrics = [row_values(row) for row in source_rows]
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for index, source in enumerate(source_rows):
        key = pick_key(source) or metrics[index].get("event_key") or str(index)
        if key not in seen:
            seen.add(key)
            deduped.append(metrics[index])
    playable = [row for row in metrics if row["status"] == PLAYABLE_STATUS]
    watchlist = [row for row in metrics if row["status"] == WATCHLIST_STATUS]
    avoid = [row for row in metrics if row["status"] == AVOID_STATUS]
    prediction_only = [row for row in metrics if row["status"] == PREDICTION_ONLY_STATUS]
    base_record = record(metrics)
    deduped_record = record(deduped)
    profit = sum(float(row.get("profit_units") or 0) for row in metrics)
    settled = sum(float(row.get("settled_stake_units") or 0) for row in metrics)
    event_keys = {row.get("event_key") for row in metrics if row.get("event_key")}
    return {"total_picks": len(metrics), "wins": base_record["wins"], "losses": base_record["losses"], "pushes": base_record["pushes"], "cancels": base_record["cancels"], "win_rate_ex_push_cancel": base_record["win_rate_ex_push_cancel"], "profit_units": rnd(profit), "staked_units": rnd(settled), "roi": rnd(profit / settled) if settled > 0 else None, "average_odds": rnd(avg([row.get("decimal_odds") for row in metrics])), "average_edge": rnd(avg([row.get("edge") for row in metrics])), "average_no_vig_edge": rnd(avg([row.get("no_vig_edge") for row in metrics])), "average_clv": rnd(avg([row.get("clv") for row in metrics])), "playable_pick_roi": rnd(roi(playable)), "watchlist_pick_roi": rnd(roi(watchlist)), "avoid_pick_tracking_result": {"count": len(avoid), **record(avoid), "profit_units": rnd(sum(float(row.get("profit_units") or 0) for row in avoid)), "roi": rnd(roi(avoid))}, "duplicate_adjusted_record": {**deduped_record, "total_picks": len(deduped), "profit_units": rnd(sum(float(row.get("profit_units") or 0) for row in deduped)), "roi": rnd(roi(deduped))}, "unique_event_count": len(event_keys) if event_keys else len(metrics), "duplicate_count": max(0, len(metrics) - len(seen)), "status_counts": {PLAYABLE_STATUS: len(playable), WATCHLIST_STATUS: len(watchlist), AVOID_STATUS: len(avoid), PREDICTION_ONLY_STATUS: len(prediction_only)}, "row_metrics": metrics}
