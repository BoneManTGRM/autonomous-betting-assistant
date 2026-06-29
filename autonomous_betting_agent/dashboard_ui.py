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

OPERATOR_STATUS_CARD_KEYS = (
    "dashboard_data_source",
    "ledger_rows",
    "selected_rows",
    "dashboard_ready",
    "ledger_integrity_status",
    "model_status",
    "drift_status",
)

PRIMARY_KPI_KEYS = (
    "events_scanned",
    "positive_ev_picks",
    "watchlist_picks",
    "avoid_picks",
    "best_edge_today",
    "win_rate_ex_push_cancel",
    "roi",
    "profit_units",
    "average_clv",
)

PROOF_PERFORMANCE_KEYS = (
    "unique_events",
    "wins",
    "losses",
    "pushes",
    "cancels",
    "duplicate_count",
    "correction_count",
    "last_updated_timestamp",
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

OPERATOR_TOP_EV_COLUMNS = [
    "event",
    "pick",
    "market",
    "sportsbook",
    "decimal_odds",
    "model_probability",
    "edge",
    "no_vig_edge",
    "expected_value",
    "clv",
    "report_lane",
    "odds_verified",
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

PROOF_READY = "PROOF READY"
NOT_PROOF_READY = "NOT PROOF READY"
LEDGER_HEALTHY = "LEDGER HEALTHY"
LEDGER_WARNING = "LEDGER WARNING"
LEDGER_FAIL = "LEDGER FAIL"
DASHBOARD_LEDGER_BACKED = "DASHBOARD LEDGER-BACKED"
DASHBOARD_FALLBACK = "DASHBOARD FALLBACK"
DASHBOARD_EMPTY = "DASHBOARD EMPTY"
RISK_OK = "RISK OK"
RISK_ELEVATED = "RISK ELEVATED"
RISK_HIGH = "RISK HIGH"
API_OK = "API OK"
API_WARNING = "API WARNING"
API_HIGH_USAGE = "API HIGH USAGE"
LEDGER_BACKED_PROOF_GRADE = "Ledger-backed proof-grade"
PROVISIONAL_FALLBACK_NOT_FINAL_PROOF = "Provisional fallback — not final proof"


def _safe(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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
    if key in {"win_rate_ex_push_cancel", "roi", "average_clv"}:
        return _percent(value, signed=key in {"roi", "average_clv"})
    if key == "profit_units":
        return f"{_number(value):+.2f}u"
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


def source_status_label(selected_source: str) -> str:
    source = _safe(selected_source).lower()
    if source == "ledger":
        return DASHBOARD_LEDGER_BACKED
    if source in {"session", "uploaded"}:
        return DASHBOARD_FALLBACK
    return DASHBOARD_EMPTY


def proof_grade_label(selected_source: str) -> str:
    return LEDGER_BACKED_PROOF_GRADE if _safe(selected_source).lower() == "ledger" else PROVISIONAL_FALLBACK_NOT_FINAL_PROOF


def ledger_health_label(ledger_health: Mapping[str, Any] | None) -> str:
    status = _safe((ledger_health or {}).get("status")).upper()
    errors = (ledger_health or {}).get("errors") or []
    warnings = (ledger_health or {}).get("warnings") or []
    if status not in {"", "PASS"} or errors:
        return LEDGER_FAIL
    if warnings:
        return LEDGER_WARNING
    return LEDGER_HEALTHY


def risk_status_label(bankroll_summary: Mapping[str, Any] | None, bankroll_risk: Any = None) -> str:
    text = _safe(bankroll_risk or (bankroll_summary or {}).get("risk_status")).lower()
    exposure = _number((bankroll_summary or {}).get("daily_exposure_fraction"), 0.0)
    if "high" in text or exposure >= 0.10:
        return RISK_HIGH
    if "elevated" in text or "moderate" in text or exposure >= 0.05:
        return RISK_ELEVATED
    return RISK_OK


def api_status_label(api_usage: Mapping[str, Any] | None) -> str:
    usage = api_usage or {}
    fraction = _number(usage.get("usage_fraction"), 0.0)
    if fraction >= 0.90:
        return API_HIGH_USAGE
    if fraction >= 0.75:
        return API_WARNING
    return API_OK


def proof_status_label(selected_source: str, dashboard_ready: bool, ledger_health: Mapping[str, Any] | None) -> str:
    if _safe(selected_source).lower() == "ledger" and dashboard_ready and ledger_health_label(ledger_health) == LEDGER_HEALTHY:
        return PROOF_READY
    return NOT_PROOF_READY


def operator_traffic_light_statuses(
    dashboard: Mapping[str, Any],
    proof_status: Mapping[str, Any] | None,
    ledger_health: Mapping[str, Any] | None,
    dashboard_readiness: Mapping[str, Any] | None,
    sync_summary: Mapping[str, Any] | None,
) -> dict[str, str]:
    selected_source = _safe((sync_summary or {}).get("selected_source") or (dashboard_readiness or {}).get("dashboard_selected_source"))
    dashboard_ready = bool((dashboard_readiness or {}).get("dashboard_ready"))
    return {
        "proof_status": proof_status_label(selected_source, dashboard_ready, ledger_health),
        "ledger_status": ledger_health_label(ledger_health),
        "dashboard_source_status": source_status_label(selected_source),
        "risk_status": risk_status_label(dashboard.get("bankroll_summary"), dashboard.get("bankroll_risk")),
        "api_status": api_status_label(dashboard.get("api_usage")),
        "proof_grade": proof_grade_label(selected_source),
    }


def operator_status_cards(
    dashboard: Mapping[str, Any],
    proof_status: Mapping[str, Any] | None,
    ledger_health: Mapping[str, Any] | None,
    dashboard_readiness: Mapping[str, Any] | None,
    sync_summary: Mapping[str, Any] | None,
) -> list[dict[str, str]]:
    sync = dict(sync_summary or {})
    ready = dict(dashboard_readiness or {})
    health = dict(ledger_health or {})
    traffic = operator_traffic_light_statuses(dashboard, proof_status, ledger_health, dashboard_readiness, sync_summary)
    return [
        {"key": "dashboard_data_source", "label": "Dashboard Data Source", "value": traffic["dashboard_source_status"], "help": _safe(sync.get("selected_source"))},
        {"key": "ledger_rows", "label": "Ledger Rows", "value": _safe(sync.get("ledger_rows", ready.get("ledger_rows", 0)))},
        {"key": "selected_rows", "label": "Selected Rows", "value": _safe(sync.get("selected_rows", ready.get("dashboard_rows", 0)))},
        {"key": "dashboard_ready", "label": "Dashboard Ready", "value": _safe(ready.get("dashboard_ready", False))},
        {"key": "ledger_integrity_status", "label": "Ledger Integrity Status", "value": _safe(health.get("status", (proof_status or {}).get("ledger_integrity_status", "PASS")))},
        {"key": "model_status", "label": "Model Status", "value": metric_value("model_status", dashboard.get("model_status"))},
        {"key": "drift_status", "label": "Drift Status", "value": metric_value("drift_status", dashboard.get("drift_status"))},
    ]


def primary_kpi_cards(dashboard: Mapping[str, Any], proof_status: Mapping[str, Any] | None) -> list[dict[str, str]]:
    proof = dict(proof_status or {})
    return [
        {"key": "events_scanned", "label": "Events Scanned", "value": metric_value("events_scanned", dashboard.get("events_scanned"))},
        {"key": "positive_ev_picks", "label": "Positive EV Picks", "value": metric_value("positive_ev_picks", dashboard.get("positive_ev_picks"))},
        {"key": "watchlist_picks", "label": "Watchlist Picks", "value": metric_value("watchlist_picks", dashboard.get("watchlist_picks"))},
        {"key": "avoid_picks", "label": "Avoid Picks", "value": metric_value("avoid_picks", dashboard.get("avoid_picks"))},
        {"key": "best_edge_today", "label": "Best Edge Today", "value": metric_value("best_edge_today", dashboard.get("best_edge_today")), "help": metric_help("best_edge_today", dashboard.get("best_edge_today"))},
        {"key": "win_rate_ex_push_cancel", "label": "Win Rate Ex Push/Cancel", "value": metric_value("win_rate_ex_push_cancel", proof.get("win_rate_ex_push_cancel"))},
        {"key": "roi", "label": "ROI", "value": metric_value("roi", proof.get("roi"))},
        {"key": "profit_units", "label": "Profit Units", "value": metric_value("profit_units", proof.get("profit_units"))},
        {"key": "average_clv", "label": "Average CLV", "value": metric_value("average_clv", proof.get("average_clv"))},
    ]


def proof_performance_cards(proof_status: Mapping[str, Any] | None) -> list[dict[str, str]]:
    proof = dict(proof_status or {})
    labels = {
        "unique_events": "Unique Events",
        "wins": "Wins",
        "losses": "Losses",
        "pushes": "Pushes",
        "cancels": "Cancels",
        "duplicate_count": "Duplicate Count",
        "correction_count": "Correction Count",
        "last_updated_timestamp": "Last Updated Timestamp",
    }
    return [{"key": key, "label": label, "value": metric_value(key, proof.get(key))} for key, label in labels.items()]


def _is_playable_positive_ev(row: Mapping[str, Any]) -> bool:
    lane = _safe(row.get("report_lane") or row.get("status") or row.get("lane")).lower()
    if "watch" in lane or "avoid" in lane:
        return False
    if lane and "playable" not in lane and "positive" not in lane:
        return False
    ev = _number(row.get("expected_value", row.get("ev", 0.0)), 0.0)
    return ev > 0


def operator_top_positive_ev_picks(records: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in records or []:
        row = dict(item)
        if not _is_playable_positive_ev(row):
            continue
        rows.append({
            "event": row.get("event") or row.get("public_event") or row.get("matchup") or "",
            "pick": row.get("pick") or row.get("public_pick") or row.get("prediction") or "",
            "market": row.get("market") or row.get("market_type") or "",
            "sportsbook": row.get("sportsbook") or row.get("book") or row.get("bookmaker") or "",
            "decimal_odds": row.get("decimal_odds") or row.get("decimal_price") or row.get("odds") or "",
            "model_probability": row.get("model_probability") or row.get("confidence") or "",
            "edge": row.get("edge") or row.get("model_market_edge") or "",
            "no_vig_edge": row.get("no_vig_edge") or "",
            "expected_value": row.get("expected_value") or row.get("ev") or "",
            "clv": row.get("clv") or row.get("manual_clv") or "",
            "report_lane": row.get("report_lane") or row.get("status") or "playable",
            "odds_verified": row.get("odds_verified") or row.get("verified_odds") or "",
        })
    return rows


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


def operator_top_positive_ev_table(records: Sequence[Mapping[str, Any]] | None) -> pd.DataFrame:
    return table_from_records(operator_top_positive_ev_picks(records), OPERATOR_TOP_EV_COLUMNS)


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
