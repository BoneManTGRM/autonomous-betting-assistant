from collections import Counter
from typing import Any, Mapping, Sequence

import pandas as pd

RESULT_WIN = "win"
RESULT_LOSS = "loss"
RESULT_PUSH = "push"
RESULT_CANCEL = "cancel"
RESULT_PENDING = "pending"

PLAYABLE_STATUSES = ("playable", "best_play", "best plays", "best_plays", "official +ev", "official ev", "publish ready", "green")
WATCHLIST_STATUSES = ("watchlist", "watch", "price watch", "monitor")
AVOID_STATUSES = ("avoid", "no_play", "no play", "blocked", "removed", "red", "data blocked", "not playable")
PREDICTION_ONLY_STATUSES = ("prediction only", "prediction-only", "research", "learning", "analysis only", "informational")
FALSE_TEXT = {"", "0", "false", "no", "none", "nan", "null", "nat", "n/a"}
TRUE_TEXT = {"1", "true", "yes", "y", "ready", "passed", "verified", "complete"}


def as_frame(rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None) -> pd.DataFrame:
    if rows is None:
        return pd.DataFrame()
    if isinstance(rows, pd.DataFrame):
        return rows.copy(deep=True)
    return pd.DataFrame(list(rows))


def text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    value_text = str(value).strip()
    return "" if value_text.lower() in FALSE_TEXT else value_text


def lower_text(value: Any) -> str:
    return text(value).lower()


def truthy(value: Any) -> bool:
    return lower_text(value) in TRUE_TEXT


def falsey(value: Any) -> bool:
    return lower_text(value) in FALSE_TEXT


def number(value: Any) -> float | None:
    raw = text(value)
    if not raw:
        return None
    try:
        return float(raw.replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def probability(value: Any) -> float | None:
    parsed = number(value)
    if parsed is None:
        return None
    if parsed > 1:
        parsed = parsed / 100.0
    if 0 <= parsed <= 1:
        return parsed
    return None


def decimal_odds(row: Mapping[str, Any]) -> float | None:
    for key in ("decimal_odds", "decimal_price", "best_price", "average_price", "avg_price", "odds_decimal", "odds_at_pick", "odds"):
        parsed = number(row.get(key))
        if parsed is None:
            continue
        if parsed >= 100:
            return round(parsed / 100.0 + 1.0, 6)
        if parsed <= -100:
            return round(100.0 / abs(parsed) + 1.0, 6)
        if parsed > 1:
            return parsed
    return None


def stake_units(row: Mapping[str, Any], default: float = 1.0) -> float:
    for key in ("stake_units", "risk_units", "units", "stake", "unit_size"):
        parsed = number(row.get(key))
        if parsed is not None and parsed >= 0:
            return parsed
    return default


def result_status(row: Mapping[str, Any]) -> str:
    for key in ("result", "grade", "outcome", "pick_result", "result_status", "status"):
        raw = lower_text(row.get(key))
        if not raw:
            continue
        normalized = raw.replace("_", " ").replace("-", " ")
        if normalized in {"w", "won", "winner", "win", "ganada"}:
            return RESULT_WIN
        if normalized in {"l", "lost", "loser", "loss", "perdida"}:
            return RESULT_LOSS
        if normalized in {"push", "tie", "draw"}:
            return RESULT_PUSH
        if normalized in {"cancel", "cancelled", "canceled", "void", "postponed"}:
            return RESULT_CANCEL
        if normalized in {"pending", "open", "ungraded"}:
            return RESULT_PENDING
    return RESULT_PENDING


def profit_units(row: Mapping[str, Any]) -> float:
    explicit = number(row.get("profit_units"))
    if explicit is not None:
        return explicit
    result = result_status(row)
    stake = stake_units(row)
    odds = decimal_odds(row)
    if result == RESULT_WIN and odds is not None:
        return round(stake * (odds - 1.0), 6)
    if result == RESULT_LOSS:
        return round(-stake, 6)
    return 0.0


def edge(row: Mapping[str, Any]) -> float | None:
    for key in ("model_market_edge", "edge", "raw_edge", "current_edge"):
        parsed = probability(row.get(key))
        if parsed is not None:
            return parsed
        parsed_number = number(row.get(key))
        if parsed_number is not None:
            return parsed_number
    model = probability(row.get("model_probability"))
    market = probability(row.get("market_probability")) or probability(row.get("raw_implied_probability"))
    if model is not None and market is not None:
        return model - market
    return None


def no_vig_edge(row: Mapping[str, Any]) -> float | None:
    for key in ("no_vig_edge", "model_no_vig_edge", "novig_edge"):
        parsed = probability(row.get(key))
        if parsed is not None:
            return parsed
        parsed_number = number(row.get(key))
        if parsed_number is not None:
            return parsed_number
    model = probability(row.get("model_probability"))
    no_vig = probability(row.get("no_vig_implied_probability")) or probability(row.get("no_vig_market_probability"))
    if model is not None and no_vig is not None:
        return model - no_vig
    return None


def expected_value(row: Mapping[str, Any]) -> float | None:
    for key in ("expected_value_per_unit", "ev", "expected_value", "value_ev"):
        parsed = probability(row.get(key))
        if parsed is not None:
            return parsed
        parsed_number = number(row.get(key))
        if parsed_number is not None:
            return parsed_number
    model = probability(row.get("model_probability"))
    odds = decimal_odds(row)
    if model is not None and odds is not None:
        return model * odds - 1.0
    return None


def clv(row: Mapping[str, Any]) -> float | None:
    for key in ("manual_clv", "manual_clv_value", "clv", "clv_delta", "closing_line_value", "clv_result"):
        parsed = number(row.get(key))
        if parsed is not None:
            return parsed
    return None


def model_probability(row: Mapping[str, Any]) -> float | None:
    for key in ("learned_model_probability", "final_adjusted_probability", "adjusted_model_probability", "model_probability", "probability", "confidence"):
        parsed = probability(row.get(key))
        if parsed is not None:
            return parsed
    return None


def event_key(row: Mapping[str, Any]) -> str:
    for key in ("event", "public_event", "event_name", "matchup", "game", "fixture"):
        value = text(row.get(key))
        if value:
            return value
    return ""


def market_key(row: Mapping[str, Any]) -> str:
    for key in ("market_type", "market", "market_name", "bet_type"):
        value = text(row.get(key))
        if value:
            return value
    return ""


def pick_key(row: Mapping[str, Any]) -> str:
    for key in ("prediction", "public_pick", "pick", "selection", "bet_selection"):
        value = text(row.get(key))
        if value:
            return value
    return ""


def bookmaker_key(row: Mapping[str, Any]) -> str:
    for key in ("bookmaker", "sportsbook", "book", "odds_source", "source"):
        value = text(row.get(key))
        if value:
            return value
    return ""


def lane(row: Mapping[str, Any]) -> str:
    combined = " ".join(
        lower_text(row.get(key))
        for key in (
            "report_lane", "report_lane_v2", "official_status_label", "advisory_status",
            "consumer_action", "recommended_action", "status", "report_summary_status",
        )
    )
    if truthy(row.get("tennis_blocked")) or truthy(row.get("blocked")) or text(row.get("data_issue_reason")):
        return "avoid"
    if any(marker in combined for marker in AVOID_STATUSES):
        return "avoid"
    if any(marker in combined for marker in WATCHLIST_STATUSES):
        return "watchlist"
    if truthy(row.get("official_publish_ready")) or truthy(row.get("publish_ready")) or truthy(row.get("client_report_ready")):
        return "playable"
    if any(marker in combined for marker in PLAYABLE_STATUSES):
        return "playable"
    if any(marker in combined for marker in PREDICTION_ONLY_STATUSES):
        return "prediction_only"
    return "prediction_only"


def odds_verified(row: Mapping[str, Any]) -> bool:
    if "odds_verified" in row:
        return truthy(row.get("odds_verified"))
    source = bookmaker_key(row).lower()
    if any(token in source for token in ("missing", "unverified", "simulated", "unavailable", "limit", "offline")):
        return False
    return decimal_odds(row) is not None


def unique_pick_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy(deep=True)
    out = frame.copy(deep=True)
    out["_event_key"] = out.apply(lambda row: event_key(row.to_dict()), axis=1)
    out["_market_key"] = out.apply(lambda row: market_key(row.to_dict()), axis=1)
    out["_pick_key"] = out.apply(lambda row: pick_key(row.to_dict()), axis=1)
    out["_bookmaker_key"] = out.apply(lambda row: bookmaker_key(row.to_dict()), axis=1)
    subset = [key for key in ("_event_key", "_market_key", "_pick_key", "_bookmaker_key") if key in out.columns]
    return out.drop_duplicates(subset=subset, keep="first") if subset else out.drop_duplicates(keep="first")


def roi_for_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    graded = [row for row in rows if result_status(row) in {RESULT_WIN, RESULT_LOSS, RESULT_PUSH, RESULT_CANCEL}]
    wins = sum(result_status(row) == RESULT_WIN for row in rows)
    losses = sum(result_status(row) == RESULT_LOSS for row in rows)
    pushes = sum(result_status(row) == RESULT_PUSH for row in rows)
    cancels = sum(result_status(row) == RESULT_CANCEL for row in rows)
    risked = sum(stake_units(row) for row in rows if result_status(row) in {RESULT_WIN, RESULT_LOSS, RESULT_PUSH})
    profit = sum(profit_units(row) for row in rows)
    denominator = wins + losses
    return {
        "total_picks": len(rows),
        "graded_picks": len(graded),
        "wins": int(wins),
        "losses": int(losses),
        "pushes": int(pushes),
        "cancels": int(cancels),
        "win_rate_ex_push_cancel": round(wins / denominator, 6) if denominator else 0.0,
        "profit_units": round(profit, 6),
        "risked_units": round(risked, 6),
        "roi": round(profit / risked, 6) if risked else 0.0,
    }


def average(values: Sequence[float | None]) -> float | None:
    usable = [value for value in values if value is not None]
    if not usable:
        return None
    return round(sum(usable) / len(usable), 6)


def summarize_clv(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = [clv(row) for row in rows]
    usable = [value for value in values if value is not None]
    return {
        "count": len(usable),
        "average_clv": average(usable),
        "positive_clv_count": sum(value > 0 for value in usable),
        "negative_clv_count": sum(value < 0 for value in usable),
        "flat_clv_count": sum(value == 0 for value in usable),
    }


def pick_rank_score(row: Mapping[str, Any]) -> float:
    ev_value = expected_value(row) or 0.0
    no_vig_value = no_vig_edge(row)
    edge_value = edge(row)
    clv_value = clv(row) or 0.0
    prob_value = model_probability(row) or 0.0
    verified_bonus = 0.01 if odds_verified(row) else -1.0
    no_vig_component = no_vig_value if no_vig_value is not None else 0.0
    edge_component = edge_value if edge_value is not None else 0.0
    return round(ev_value * 1000 + no_vig_component * 250 + edge_component * 150 + clv_value * 20 + prob_value + verified_bonus, 6)


def is_positive_ev_playable(row: Mapping[str, Any]) -> bool:
    if lane(row) != "playable":
        return False
    if not odds_verified(row):
        return False
    ev_value = expected_value(row)
    edge_value = edge(row)
    no_vig_value = no_vig_edge(row)
    if ev_value is None or ev_value <= 0:
        return False
    if edge_value is not None and edge_value <= 0:
        return False
    if no_vig_value is not None and no_vig_value <= 0:
        return False
    odds = decimal_odds(row)
    return odds is not None and odds > 1


def top_positive_ev_picks(rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None, limit: int = 10) -> list[dict[str, Any]]:
    frame = as_frame(rows)
    if frame.empty:
        return []
    candidates: list[dict[str, Any]] = []
    for _, series in frame.iterrows():
        row = series.to_dict()
        if not is_positive_ev_playable(row):
            continue
        candidates.append({
            "event": event_key(row),
            "market": market_key(row),
            "pick": pick_key(row),
            "book": bookmaker_key(row),
            "odds": decimal_odds(row),
            "model_probability": model_probability(row),
            "edge": edge(row),
            "no_vig_edge": no_vig_edge(row),
            "expected_value": expected_value(row),
            "clv": clv(row),
            "confidence": text(row.get("confidence_tier")) or text(row.get("confidence")),
            "status": "PLAYABLE",
            "rank_score": pick_rank_score(row),
        })
    return sorted(candidates, key=lambda item: item["rank_score"], reverse=True)[:limit]


def bankroll_summary(rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None, bankroll: float = 1000.0, unit_size: float = 10.0, max_daily_fraction: float = 0.05) -> dict[str, Any]:
    frame = as_frame(rows)
    row_dicts = [row.to_dict() for _, row in frame.iterrows()]
    playable_rows = [row for row in row_dicts if is_positive_ev_playable(row)]
    total_units = sum(stake_units(row) for row in playable_rows)
    exposure = total_units * unit_size
    bankroll_value = bankroll if bankroll and bankroll > 0 else 0.0
    exposure_fraction = exposure / bankroll_value if bankroll_value else 0.0
    if exposure_fraction > max_daily_fraction * 2:
        risk = "Blocked"
    elif exposure_fraction > max_daily_fraction:
        risk = "High"
    elif exposure_fraction > max_daily_fraction / 2:
        risk = "Moderate"
    else:
        risk = "Low"
    kelly_values: list[float] = []
    for row in playable_rows:
        prob = model_probability(row)
        odds = decimal_odds(row)
        if prob is None or odds is None or odds <= 1:
            continue
        b = odds - 1.0
        raw_kelly = ((b * prob) - (1.0 - prob)) / b
        kelly_values.append(max(0.0, min(raw_kelly * 0.25, 0.05)))
    recommended_kelly = average(kelly_values) if kelly_values else 0.0
    return {
        "current_bankroll": round(bankroll_value, 6),
        "unit_size": round(unit_size, 6),
        "recommended_bets": len(playable_rows),
        "total_units_risked": round(total_units, 6),
        "daily_exposure": round(exposure, 6),
        "daily_exposure_fraction": round(exposure_fraction, 6),
        "max_daily_fraction": round(max_daily_fraction, 6),
        "risk_level": risk,
        "kelly_fraction": round(recommended_kelly or 0.0, 6),
    }


def profitability_summary(rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    frame = as_frame(rows)
    if frame.empty:
        empty_roi = roi_for_rows([])
        return {
            **empty_roi,
            "average_odds": None,
            "average_edge": None,
            "average_no_vig_edge": None,
            "average_clv": None,
            "playable_pick_roi": roi_for_rows([]),
            "watchlist_pick_roi": roi_for_rows([]),
            "avoid_pick_tracking_result": roi_for_rows([]),
            "duplicate_adjusted_record": roi_for_rows([]),
            "unique_event_count": 0,
            "duplicate_count": 0,
            "lane_counts": {"playable": 0, "watchlist": 0, "avoid": 0, "prediction_only": 0},
            "clv_summary": summarize_clv([]),
        }
    rows_list = [series.to_dict() for _, series in frame.iterrows()]
    unique_events = {event_key(row) for row in rows_list if event_key(row)}
    unique_frame = unique_pick_frame(frame)
    unique_rows = [series.to_dict() for _, series in unique_frame.iterrows()]
    lane_counter = Counter(lane(row) for row in rows_list)
    playable_rows = [row for row in rows_list if lane(row) == "playable"]
    watchlist_rows = [row for row in rows_list if lane(row) == "watchlist"]
    avoid_rows = [row for row in rows_list if lane(row) == "avoid"]
    roi = roi_for_rows(rows_list)
    return {
        **roi,
        "average_odds": average([decimal_odds(row) for row in rows_list]),
        "average_edge": average([edge(row) for row in rows_list]),
        "average_no_vig_edge": average([no_vig_edge(row) for row in rows_list]),
        "average_clv": average([clv(row) for row in rows_list]),
        "playable_pick_roi": roi_for_rows(playable_rows),
        "watchlist_pick_roi": roi_for_rows(watchlist_rows),
        "avoid_pick_tracking_result": roi_for_rows(avoid_rows),
        "duplicate_adjusted_record": roi_for_rows(unique_rows),
        "unique_event_count": len(unique_events) if unique_events else len(unique_frame),
        "duplicate_count": max(0, len(frame) - len(unique_frame)),
        "lane_counts": {
            "playable": int(lane_counter.get("playable", 0)),
            "watchlist": int(lane_counter.get("watchlist", 0)),
            "avoid": int(lane_counter.get("avoid", 0)),
            "prediction_only": int(lane_counter.get("prediction_only", 0)),
        },
        "clv_summary": summarize_clv(rows_list),
    }
