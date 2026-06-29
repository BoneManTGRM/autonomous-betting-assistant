from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import pandas as pd

from autonomous_betting_agent.profitability_metrics import (
    AVOID_STATUS,
    PLAYABLE_STATUS,
    PREDICTION_ONLY_STATUS,
    WATCHLIST_STATUS,
    num,
    pick_key,
    row_values,
    summarize_profitability,
    text,
)

DASHBOARD_FIELDS = (
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
)


def _frame(rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None) -> pd.DataFrame:
    if rows is None:
        return pd.DataFrame()
    if isinstance(rows, pd.DataFrame):
        return rows.copy(deep=True)
    return pd.DataFrame(list(rows))


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(float(value), digits)


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [dict(row) for _, row in frame.iterrows()]


def _label_percent(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:+.1f}%"


def _row_label(source: Mapping[str, Any]) -> dict[str, str]:
    return {
        "event": text(source.get("public_event") or source.get("event") or source.get("event_name") or source.get("matchup") or source.get("game")),
        "pick": text(source.get("public_pick") or source.get("prediction") or source.get("pick") or source.get("selection")),
        "market": text(source.get("market_type") or source.get("market") or source.get("market_name")),
        "book": text(source.get("bookmaker") or source.get("sportsbook") or source.get("book")),
    }


def _ranked_rows(source_rows: list[dict[str, Any]], metrics: list[dict[str, Any]], status: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    combined = []
    for source, metric in zip(source_rows, metrics):
        if status and metric.get("status") != status:
            continue
        labels = _row_label(source)
        combined.append({
            **labels,
            "odds": metric.get("decimal_odds"),
            "model_probability": metric.get("model_probability"),
            "edge": metric.get("edge"),
            "no_vig_edge": metric.get("no_vig_edge"),
            "expected_value": metric.get("expected_value"),
            "clv": metric.get("clv"),
            "status": metric.get("status"),
            "odds_verified": bool(metric.get("odds_verified")),
            "ranking_score": _ranking_score(metric),
        })
    return sorted(combined, key=lambda row: row["ranking_score"], reverse=True)[:limit]


def _ranking_score(metric: Mapping[str, Any]) -> float:
    ev = float(metric.get("expected_value") or 0)
    no_vig = float(metric.get("no_vig_edge") or 0)
    edge = float(metric.get("edge") or 0)
    clv = float(metric.get("clv") or 0)
    verified_bonus = 0.01 if metric.get("odds_verified") else 0
    return ev * 1000 + no_vig * 100 + edge * 10 + clv + verified_bonus


def _best_edge_today(source_rows: list[dict[str, Any]], metrics: list[dict[str, Any]]) -> dict[str, Any]:
    rows = _ranked_rows(source_rows, metrics, PLAYABLE_STATUS, limit=1)
    if not rows:
        return {"value": None, "label": "N/A", "event": "", "pick": "", "book": ""}
    row = rows[0]
    value = row.get("no_vig_edge") if row.get("no_vig_edge") is not None else row.get("edge")
    return {"value": _round(value), "label": _label_percent(value), "event": row.get("event", ""), "pick": row.get("pick", ""), "book": row.get("book", "")}


def _api_usage(api_usage: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(api_usage or {})
    used = num(data.get("used_calls") or data.get("used") or data.get("calls_used")) or 0
    limit = num(data.get("call_limit") or data.get("limit") or data.get("monthly_limit")) or 0
    pct = (used / limit) if limit > 0 else 0
    return {"used_calls": int(used), "call_limit": int(limit), "usage_pct": _round(pct), "label": f"{pct * 100:.0f}%" if limit > 0 else "0%"}


def _bankroll_summary(source_rows: list[dict[str, Any]], metrics: list[dict[str, Any]], bankroll: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(bankroll or {})
    current = num(data.get("current_bankroll") or data.get("bankroll")) or 1000.0
    limit_pct = num(data.get("daily_bankroll_limit_pct")) or 0.05
    kelly = num(data.get("kelly_fraction")) or 0.25
    open_statuses = {"pending", "open", ""}
    active_units = sum(float(metric.get("stake_units") or 0) for metric in metrics if metric.get("status") == PLAYABLE_STATUS and str(metric.get("result") or "pending").lower() in open_statuses)
    settled_units = sum(float(metric.get("settled_stake_units") or 0) for metric in metrics)
    exposure_dollars = active_units
    exposure_pct = exposure_dollars / current if current > 0 else 0
    if current <= 0 or exposure_pct > limit_pct:
        risk = "Blocked"
    elif exposure_pct >= 0.03:
        risk = "High"
    elif exposure_pct >= 0.01:
        risk = "Moderate"
    else:
        risk = "Low"
    return {"current_bankroll": _round(current, 2), "daily_exposure_units": _round(active_units), "settled_units_risked": _round(settled_units), "exposure_pct": _round(exposure_pct), "daily_limit_pct": _round(limit_pct), "kelly_fraction": _round(kelly), "recommended_kelly_fraction": min(_round(kelly) or 0.25, 0.25), "risk_level": risk}


def _learning_rows_scanned(rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None, source_rows: list[dict[str, Any]]) -> int:
    learning = _frame(rows)
    if not learning.empty:
        return int(len(learning))
    for row in source_rows:
        value = num(row.get("learning_rows_scanned") or row.get("rows_scanned"))
        if value is not None:
            return int(value)
    return sum(bool(text(row.get("learning_status"))) for row in source_rows)


def _drift_status(source_rows: list[dict[str, Any]]) -> str:
    for row in source_rows:
        drift = text(row.get("drift_status") or row.get("reparodynamics_drift_status") or row.get("reparodynamics_status"))
        if drift:
            return "Drift Detected" if "drift" in drift.lower() and "no" not in drift.lower() else drift
        if text(row.get("drift_detected")).lower() in {"yes", "true", "1"}:
            return "Drift Detected"
    return "No Drift"


def _model_status(metrics: list[dict[str, Any]]) -> str:
    if not metrics:
        return "No Data"
    blocked = sum(row.get("status") == AVOID_STATUS for row in metrics)
    playable = sum(row.get("status") == PLAYABLE_STATUS for row in metrics)
    if playable:
        return "Stable"
    if blocked == len(metrics):
        return "Blocked"
    return "Needs Review"


def _odds_lock_summary(top_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not top_rows:
        return {"status": "NO_PLAYABLE_LOCK", "message": "No verified positive-EV lock candidate.", "best_candidate": None}
    row = top_rows[0]
    fair_odds = (1 / row["model_probability"]) if row.get("model_probability") else None
    target_lock = fair_odds + 0.02 if fair_odds else None
    return {"status": "PLAYABLE", "best_candidate": row, "fair_odds": _round(fair_odds, 3), "target_lock_odds": _round(target_lock, 3), "message": "Best value candidate ranked by EV, no-vig edge, edge, CLV, and verified price."}


def _proof_summary(metrics_summary: Mapping[str, Any]) -> dict[str, Any]:
    counts = dict(metrics_summary.get("status_counts") or {})
    return {"total_picks": metrics_summary.get("total_picks", 0), "unique_events": metrics_summary.get("unique_event_count", 0), "duplicates_detected": metrics_summary.get("duplicate_count", 0), "playable": counts.get(PLAYABLE_STATUS, 0), "watchlist": counts.get(WATCHLIST_STATUS, 0), "avoid": counts.get(AVOID_STATUS, 0), "prediction_only": counts.get(PREDICTION_ONLY_STATUS, 0), "duplicate_adjusted_record": metrics_summary.get("duplicate_adjusted_record", {})}


def _clv_summary(metrics_summary: Mapping[str, Any]) -> dict[str, Any]:
    return {"average_clv": metrics_summary.get("average_clv"), "status": "Tracked" if metrics_summary.get("average_clv") is not None else "Missing", "sample_rows": sum(1 for row in metrics_summary.get("row_metrics", []) if row.get("clv") is not None)}


def _roi_summary(metrics_summary: Mapping[str, Any]) -> dict[str, Any]:
    return {"profit_units": metrics_summary.get("profit_units"), "staked_units": metrics_summary.get("staked_units"), "roi": metrics_summary.get("roi"), "win_rate_ex_push_cancel": metrics_summary.get("win_rate_ex_push_cancel"), "playable_pick_roi": metrics_summary.get("playable_pick_roi"), "watchlist_pick_roi": metrics_summary.get("watchlist_pick_roi"), "avoid_pick_tracking_result": metrics_summary.get("avoid_pick_tracking_result")}


def _recent_activity(metrics_summary: Mapping[str, Any], supplied: Sequence[Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    if supplied:
        return [dict(item) for item in supplied]
    return [{"type": "dashboard", "message": f"Generated dashboard data for {metrics_summary.get('total_picks', 0)} rows."}, {"type": "proof", "message": f"Unique events: {metrics_summary.get('unique_event_count', 0)}; duplicates: {metrics_summary.get('duplicate_count', 0)}."}, {"type": "roi", "message": f"ROI: {metrics_summary.get('roi')} profit units: {metrics_summary.get('profit_units')}."}]


def _upcoming_events(source_rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    events = []
    for row in source_rows:
        start = text(row.get("event_start_utc") or row.get("commence_time") or row.get("start_time") or row.get("game_time"))
        if start and text(row.get("result") or row.get("result_status") or "pending").lower() in {"", "pending", "open"}:
            labels = _row_label(row)
            events.append({"event": labels["event"], "market": labels["market"], "book": labels["book"], "start_time": start})
    return events[:limit]


def build_dashboard_data(rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None, *, learning_rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None = None, api_usage: Mapping[str, Any] | None = None, bankroll: Mapping[str, Any] | None = None, recent_activity: Sequence[Mapping[str, Any]] | None = None, generated_at_utc: str | None = None) -> dict[str, Any]:
    frame = _frame(rows)
    source_rows = _records(frame)
    metrics_summary = summarize_profitability(frame)
    metrics = list(metrics_summary.get("row_metrics", []))
    counts = dict(metrics_summary.get("status_counts") or {})
    top_rows = _ranked_rows(source_rows, metrics, PLAYABLE_STATUS, limit=5)
    bankroll_summary = _bankroll_summary(source_rows, metrics, bankroll)
    dashboard = {
        "events_scanned": metrics_summary.get("unique_event_count", 0),
        "positive_ev_picks": counts.get(PLAYABLE_STATUS, 0),
        "watchlist_picks": counts.get(WATCHLIST_STATUS, 0),
        "avoid_picks": counts.get(AVOID_STATUS, 0),
        "best_edge_today": _best_edge_today(source_rows, metrics),
        "model_status": _model_status(metrics),
        "drift_status": _drift_status(source_rows),
        "learning_rows_scanned": _learning_rows_scanned(learning_rows, source_rows),
        "bankroll_risk": bankroll_summary["risk_level"],
        "api_usage": _api_usage(api_usage),
        "top_positive_ev_picks": top_rows,
        "odds_lock_summary": _odds_lock_summary(top_rows),
        "bankroll_summary": bankroll_summary,
        "recent_activity": _recent_activity(metrics_summary, recent_activity),
        "upcoming_events": _upcoming_events(source_rows),
        "proof_summary": _proof_summary(metrics_summary),
        "clv_summary": _clv_summary(metrics_summary),
        "roi_summary": _roi_summary(metrics_summary),
        "generated_at_utc": generated_at_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "safety": {"report_only": True, "places_wagers": False, "mutates_proof": False, "trains_model": False},
    }
    for field in DASHBOARD_FIELDS:
        dashboard.setdefault(field, None)
    return dashboard


def dashboard_json(rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None, **kwargs: Any) -> dict[str, Any]:
    return build_dashboard_data(rows, **kwargs)
