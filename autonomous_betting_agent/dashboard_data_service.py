from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import pandas as pd

from autonomous_betting_agent.profitability_metrics import (
    RESULT_PENDING,
    as_frame,
    bankroll_summary,
    bookmaker_key,
    clv,
    edge,
    event_key,
    expected_value,
    is_positive_ev_playable,
    lane,
    market_key,
    model_probability,
    no_vig_edge,
    odds_verified,
    pick_key,
    profitability_summary,
    result_status,
    stake_units,
    text,
    top_positive_ev_picks,
    truthy,
)

DASHBOARD_FIELDS = [
    "events_scanned",
    "positive_ev_picks",
    "watchlist_picks",
    "avoid_picks",
    "best_edge_today",
    "model_status",
    "drift_status",
    "learning_rows_scanned",
    "bankroll_risk",
    "api_usage",
    "top_positive_ev_picks",
    "odds_lock_summary",
    "bankroll_summary",
    "recent_activity",
    "upcoming_events",
    "proof_summary",
    "clv_summary",
    "roi_summary",
]


def percent_display(value: float | None, signed: bool = False) -> str:
    if value is None:
        return "N/A"
    if signed:
        return f"{value * 100:+.1f}%"
    return f"{value * 100:.1f}%"


def _row_dicts(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [series.to_dict() for _, series in frame.iterrows()]


def _active_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy(deep=True)
    mask = frame.apply(lambda row: result_status(row.to_dict()) == RESULT_PENDING, axis=1)
    return frame[mask].copy(deep=True)


def api_usage_summary(api_usage: Mapping[str, Any] | None = None) -> dict[str, Any]:
    data = dict(api_usage or {})
    used = data.get("used_calls", data.get("used", data.get("calls_used", 0)))
    limit = data.get("call_limit", data.get("limit", data.get("calls_limit", 0)))
    try:
        used_number = float(used or 0)
    except (TypeError, ValueError):
        used_number = 0.0
    try:
        limit_number = float(limit or 0)
    except (TypeError, ValueError):
        limit_number = 0.0
    pct = used_number / limit_number if limit_number else 0.0
    if pct >= 0.9:
        status = "High"
    elif pct >= 0.7:
        status = "Moderate"
    else:
        status = "Normal"
    return {
        "used_calls": int(used_number),
        "call_limit": int(limit_number),
        "usage_fraction": round(pct, 6),
        "usage_display": percent_display(pct),
        "status": status,
        "sources": list(data.get("sources", [])) if isinstance(data.get("sources", []), (list, tuple)) else [],
    }


def model_status_summary(rows: Sequence[Mapping[str, Any]], explicit_status: str | None = None) -> str:
    if explicit_status:
        return explicit_status
    if not rows:
        return "Needs Data"
    active_rows = [row for row in rows if result_status(row) == RESULT_PENDING]
    if not active_rows:
        return "Historical Proof"
    blocked = sum(lane(row) == "avoid" for row in active_rows)
    playable = sum(is_positive_ev_playable(row) for row in active_rows)
    if blocked == len(active_rows):
        return "Blocked"
    if playable:
        return "Stable"
    return "Watching"


def drift_status_summary(rows: Sequence[Mapping[str, Any]], explicit_status: str | None = None) -> str:
    if explicit_status:
        return explicit_status
    for row in rows:
        for key in ("drift_detected", "reparodynamics_drift", "model_drift", "drift"):
            value = row.get(key)
            if truthy(value) or text(value).lower() in {"yes", "drift", "detected", "true"}:
                return "Drift Detected"
    return "No Drift" if rows else "No Data"


def proof_summary(rows: Sequence[Mapping[str, Any]], metrics: Mapping[str, Any]) -> dict[str, Any]:
    proof_rows = sum(bool(text(row.get("proof_id"))) for row in rows)
    locked_rows = sum(bool(text(row.get("locked_at_utc")) or text(row.get("locked_at"))) for row in rows)
    verified = sum(odds_verified(row) for row in rows)
    official_ready = sum(truthy(row.get("official_publish_ready")) or truthy(row.get("publish_ready")) for row in rows)
    return {
        "total_rows": len(rows),
        "unique_events": metrics.get("unique_event_count", 0),
        "proof_rows": int(proof_rows),
        "locked_rows": int(locked_rows),
        "verified_odds_rows": int(verified),
        "official_ready_rows": int(official_ready),
        "duplicate_count": metrics.get("duplicate_count", 0),
    }


def clv_summary_for_dashboard(rows: Sequence[Mapping[str, Any]], metrics: Mapping[str, Any]) -> dict[str, Any]:
    base = dict(metrics.get("clv_summary", {}))
    base["average_clv_display"] = percent_display(base.get("average_clv"), signed=True) if base.get("average_clv") is not None else "N/A"
    base["best_clv"] = None
    values: list[tuple[float, Mapping[str, Any]]] = []
    for row in rows:
        value = clv(row)
        if value is not None:
            values.append((value, row))
    if values:
        best_value, best_row = sorted(values, key=lambda item: item[0], reverse=True)[0]
        base["best_clv"] = {
            "event": event_key(best_row),
            "pick": pick_key(best_row),
            "clv": best_value,
            "clv_display": percent_display(best_value, signed=True),
        }
    return base


def roi_summary_for_dashboard(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "total_picks": metrics.get("total_picks", 0),
        "wins": metrics.get("wins", 0),
        "losses": metrics.get("losses", 0),
        "pushes": metrics.get("pushes", 0),
        "cancels": metrics.get("cancels", 0),
        "win_rate_ex_push_cancel": metrics.get("win_rate_ex_push_cancel", 0.0),
        "win_rate_display": percent_display(metrics.get("win_rate_ex_push_cancel", 0.0)),
        "profit_units": metrics.get("profit_units", 0.0),
        "risked_units": metrics.get("risked_units", 0.0),
        "roi": metrics.get("roi", 0.0),
        "roi_display": percent_display(metrics.get("roi", 0.0), signed=True),
        "average_odds": metrics.get("average_odds"),
        "average_edge": metrics.get("average_edge"),
        "average_no_vig_edge": metrics.get("average_no_vig_edge"),
        "average_clv": metrics.get("average_clv"),
        "playable_pick_roi": metrics.get("playable_pick_roi", {}),
        "watchlist_pick_roi": metrics.get("watchlist_pick_roi", {}),
        "avoid_pick_tracking_result": metrics.get("avoid_pick_tracking_result", {}),
        "duplicate_adjusted_record": metrics.get("duplicate_adjusted_record", {}),
    }


def best_edge_today(top_picks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not top_picks:
        return {"edge": None, "edge_display": "N/A", "event": "", "pick": "", "book": ""}
    best = sorted(top_picks, key=lambda item: item.get("edge") or item.get("expected_value") or 0, reverse=True)[0]
    edge_value = best.get("edge") if best.get("edge") is not None else best.get("expected_value")
    return {
        "edge": edge_value,
        "edge_display": percent_display(edge_value, signed=True),
        "event": best.get("event", ""),
        "pick": best.get("pick", ""),
        "book": best.get("book", ""),
    }


def odds_lock_summary(top_picks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not top_picks:
        return {
            "status": "NO_PLAYABLE_LOCK",
            "best_value_now": None,
            "market": "",
            "aba_fair_odds": None,
            "best_current_odds": None,
            "target_lock": "",
            "current_edge": None,
            "current_edge_display": "N/A",
        }
    best = top_picks[0]
    probability_value = best.get("model_probability")
    fair_odds = round(1.0 / probability_value, 6) if probability_value else None
    current_odds = best.get("odds")
    target = round(fair_odds + 0.02, 3) if fair_odds else None
    return {
        "status": "PLAYABLE",
        "best_value_now": best.get("event"),
        "market": " ".join(part for part in (best.get("event"), best.get("market")) if part),
        "pick": best.get("pick"),
        "book": best.get("book"),
        "aba_fair_odds": fair_odds,
        "best_current_odds": current_odds,
        "target_lock": f"{target} or better" if target else "",
        "current_edge": best.get("edge"),
        "current_edge_display": percent_display(best.get("edge"), signed=True),
    }


def recent_activity(rows: Sequence[Mapping[str, Any]], metrics: Mapping[str, Any], learning_rows_scanned: int, generated_at: str | None = None) -> list[dict[str, Any]]:
    timestamp = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lane_counts = metrics.get("lane_counts", {})
    tracking = int(lane_counts.get("watchlist", 0) or 0) + int(lane_counts.get("prediction_only", 0) or 0)
    activity = [
        {
            "type": "picks",
            "title": f"Tracking {tracking} active rows; {lane_counts.get('playable', 0)} official playable picks",
            "detail": f"{metrics.get('unique_event_count', 0)} unique events scanned",
            "timestamp": timestamp,
        },
        {
            "type": "profitability",
            "title": "Profitability metrics refreshed",
            "detail": f"ROI {percent_display(metrics.get('roi', 0.0), signed=True)} | Profit {metrics.get('profit_units', 0.0)} units",
            "timestamp": timestamp,
        },
    ]
    if learning_rows_scanned:
        activity.append({
            "type": "learning",
            "title": "Learning rows scanned",
            "detail": f"{learning_rows_scanned} rows available for calibration review",
            "timestamp": timestamp,
        })
    if rows:
        activity.append({
            "type": "proof",
            "title": "Proof summary generated",
            "detail": f"{metrics.get('wins', 0)}W-{metrics.get('losses', 0)}L | {metrics.get('duplicate_count', 0)} duplicates",
            "timestamp": timestamp,
        })
    return activity


def upcoming_events(rows: Sequence[Mapping[str, Any]], explicit_events: Sequence[Mapping[str, Any]] | None = None, limit: int = 5) -> list[dict[str, Any]]:
    if explicit_events is not None:
        return [dict(item) for item in list(explicit_events)[:limit]]
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    active_rows = [row for row in rows if result_status(row) == RESULT_PENDING] or list(rows)
    for row in active_rows:
        event = event_key(row)
        if not event or event in seen:
            continue
        seen.add(event)
        start = ""
        for key in ("event_start_utc", "commence_time", "start_time", "game_time", "event_time"):
            start = text(row.get(key))
            if start:
                break
        events.append({
            "event": event,
            "sport": text(row.get("sport")) or text(row.get("league")),
            "market": market_key(row),
            "start_time": start,
            "pick": pick_key(row),
        })
        if len(events) >= limit:
            break
    return events


def dashboard_pick_counts(rows: Sequence[Mapping[str, Any]], top_picks: Sequence[Mapping[str, Any]], metrics: Mapping[str, Any]) -> dict[str, int]:
    active_rows = [row for row in rows if result_status(row) == RESULT_PENDING]
    if not active_rows:
        return {"positive_ev_picks": 0, "watchlist_picks": 0, "avoid_picks": 0}
    lane_counts = metrics.get("lane_counts", {})
    watchlist = int(lane_counts.get("watchlist", 0) or 0)
    prediction_only = int(lane_counts.get("prediction_only", 0) or 0)
    avoid = int(lane_counts.get("avoid", 0) or 0)
    tracking_rows = watchlist + prediction_only
    return {
        "positive_ev_picks": len(top_picks),
        "watchlist_picks": tracking_rows,
        "avoid_picks": avoid,
    }


def build_dashboard_data(
    rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None,
    *,
    learning_rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None = None,
    api_usage: Mapping[str, Any] | None = None,
    bankroll: float = 1000.0,
    unit_size: float = 10.0,
    max_daily_fraction: float = 0.05,
    model_status: str | None = None,
    drift_status: str | None = None,
    explicit_upcoming_events: Sequence[Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    frame = as_frame(rows)
    row_dicts = _row_dicts(frame)
    active = _active_frame(frame)
    active_rows = _row_dicts(active)
    learning_frame = as_frame(learning_rows)
    learning_count = int(len(learning_frame))
    metrics = profitability_summary(frame)
    active_metrics = profitability_summary(active)
    top_picks = top_positive_ev_picks(active, limit=10)
    bank = bankroll_summary(active, bankroll=bankroll, unit_size=unit_size, max_daily_fraction=max_daily_fraction)
    counts = dashboard_pick_counts(active_rows, top_picks, active_metrics)
    api = api_usage_summary(api_usage)
    dashboard = {
        "events_scanned": metrics.get("unique_event_count", 0),
        "positive_ev_picks": counts["positive_ev_picks"],
        "watchlist_picks": counts["watchlist_picks"],
        "avoid_picks": counts["avoid_picks"],
        "best_edge_today": best_edge_today(top_picks),
        "model_status": model_status_summary(row_dicts, explicit_status=model_status),
        "drift_status": drift_status_summary(row_dicts, explicit_status=drift_status),
        "learning_rows_scanned": learning_count,
        "bankroll_risk": bank.get("risk_level", "Low"),
        "api_usage": api,
        "top_positive_ev_picks": top_picks,
        "odds_lock_summary": odds_lock_summary(top_picks),
        "bankroll_summary": bank,
        "recent_activity": recent_activity(active_rows, active_metrics, learning_count, generated_at=generated_at),
        "upcoming_events": upcoming_events(row_dicts, explicit_events=explicit_upcoming_events),
        "proof_summary": proof_summary(row_dicts, metrics),
        "clv_summary": clv_summary_for_dashboard(row_dicts, metrics),
        "roi_summary": roi_summary_for_dashboard(metrics),
        "active_rows_scanned": len(active),
        "historical_rows_scanned": max(0, len(frame) - len(active)),
    }
    for field in DASHBOARD_FIELDS:
        dashboard.setdefault(field, None)
    return dashboard
