import json
from typing import Any, Mapping, Sequence

import pandas as pd

STATUS_CARD_KEYS = (
    ("events_scanned", "Events Scanned"),
    ("positive_ev_picks", "Positive EV Picks"),
    ("watchlist_picks", "Watchlist Picks"),
    ("avoid_picks", "Avoid Picks"),
    ("best_edge_today", "Best Edge Today"),
    ("model_status", "Model Status"),
    ("drift_status", "Drift Status"),
    ("learning_rows_scanned", "Learning Rows"),
    ("bankroll_risk", "Bankroll Risk"),
    ("api_usage", "API Usage"),
)

TOP_PICK_COLUMNS = [
    "event",
    "market",
    "pick",
    "book",
    "odds",
    "model_probability",
    "edge",
    "no_vig_edge",
    "expected_value",
    "clv",
    "confidence",
    "status",
]

SUMMARY_SECTION_KEYS = (
    "odds_lock_summary",
    "bankroll_summary",
    "proof_summary",
    "clv_summary",
    "roi_summary",
)

LIST_SECTION_KEYS = (
    "top_positive_ev_picks",
    "recent_activity",
    "upcoming_events",
)


def _safe(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _percent(value: Any, *, signed: bool = False) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"
    return f"{number * 100:+.1f}%" if signed else f"{number * 100:.1f}%"


def _money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "N/A"


def metric_value(key: str, value: Any) -> str:
    if key == "best_edge_today" and isinstance(value, Mapping):
        return _safe(value.get("edge_display")) or "N/A"
    if key == "api_usage" and isinstance(value, Mapping):
        return _safe(value.get("usage_display")) or "0.0%"
    if isinstance(value, float):
        return f"{value:.3f}"
    return _safe(value) or "0"


def metric_help(key: str, value: Any) -> str:
    if key == "best_edge_today" and isinstance(value, Mapping):
        return " | ".join(part for part in (_safe(value.get("event")), _safe(value.get("pick")), _safe(value.get("book"))) if part)
    if key == "api_usage" and isinstance(value, Mapping):
        used = value.get("used_calls", 0)
        limit = value.get("call_limit", 0)
        return f"{used} / {limit} calls"
    if key == "bankroll_risk":
        return "Risk from bankroll exposure rules"
    if key == "model_status":
        return "Derived from current rows unless explicitly supplied"
    if key == "drift_status":
        return "Derived from drift fields unless explicitly supplied"
    return ""


def status_cards(dashboard: Mapping[str, Any]) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for key, label in STATUS_CARD_KEYS:
        value = dashboard.get(key)
        cards.append({
            "key": key,
            "label": label,
            "value": metric_value(key, value),
            "help": metric_help(key, value),
        })
    return cards


def _serializable(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, Mapping):
        return {str(key): _serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def dashboard_json_text(dashboard: Mapping[str, Any]) -> str:
    return json.dumps(_serializable(dict(dashboard or {})), indent=2, sort_keys=True)


def table_from_records(records: Sequence[Mapping[str, Any]] | None, preferred_columns: Sequence[str] | None = None) -> pd.DataFrame:
    frame = pd.DataFrame([dict(item) for item in records or []])
    if frame.empty:
        return frame
    if preferred_columns:
        ordered = [column for column in preferred_columns if column in frame.columns]
        remainder = [column for column in frame.columns if column not in ordered]
        frame = frame[ordered + remainder]
    return frame


def summary_table(summary: Mapping[str, Any] | None) -> pd.DataFrame:
    if not summary:
        return pd.DataFrame(columns=["metric", "value"])
    rows = []
    for key, value in dict(summary).items():
        if isinstance(value, Mapping):
            rows.append({"metric": key, "value": json.dumps(_serializable(value), sort_keys=True)})
        elif isinstance(value, (list, tuple)):
            rows.append({"metric": key, "value": json.dumps(_serializable(value), sort_keys=True)})
        elif key.endswith("fraction") or key in {"roi", "win_rate_ex_push_cancel", "average_edge", "average_no_vig_edge", "average_clv", "usage_fraction", "daily_exposure_fraction", "max_daily_fraction", "kelly_fraction"}:
            rows.append({"metric": key, "value": _percent(value, signed=key in {"roi", "average_edge", "average_no_vig_edge", "average_clv"})})
        elif key in {"current_bankroll", "daily_exposure"}:
            rows.append({"metric": key, "value": _money(value)})
        else:
            rows.append({"metric": key, "value": value})
    return pd.DataFrame(rows)


def dashboard_tables(dashboard: Mapping[str, Any]) -> dict[str, pd.DataFrame]:
    return {
        "top_positive_ev_picks": table_from_records(dashboard.get("top_positive_ev_picks") or [], TOP_PICK_COLUMNS),
        "recent_activity": table_from_records(dashboard.get("recent_activity") or [], ["type", "title", "detail", "timestamp"]),
        "upcoming_events": table_from_records(dashboard.get("upcoming_events") or [], ["start_time", "sport", "event", "market", "pick"]),
        "odds_lock_summary": summary_table(dashboard.get("odds_lock_summary") or {}),
        "bankroll_summary": summary_table(dashboard.get("bankroll_summary") or {}),
        "proof_summary": summary_table(dashboard.get("proof_summary") or {}),
        "clv_summary": summary_table(dashboard.get("clv_summary") or {}),
        "roi_summary": summary_table(dashboard.get("roi_summary") or {}),
    }


def missing_dashboard_fields(dashboard: Mapping[str, Any], required_fields: Sequence[str]) -> list[str]:
    return [field for field in required_fields if field not in dashboard]


def assert_no_demo_dashboard_values(dashboard: Mapping[str, Any]) -> bool:
    """Return True when the dashboard object does not contain known demo-only mock values.

    This checks specific sample strings from the design image so tests can verify the helper
    output is driven by caller-supplied data, not cosmetic placeholders.
    """
    payload = dashboard_json_text(dashboard)
    demo_tokens = ("John Doe", "NY Liberty -120", "Aces vs Liberty", "Events Scanned\": 184", "Avoid Picks\": 158", "+8.4%")
    return not any(token in payload for token in demo_tokens)
