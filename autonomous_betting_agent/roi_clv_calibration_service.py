from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "roi_clv_calibration_v1"
STATUS_VALUES = ("CALIBRATION OK", "CALIBRATION WARNING", "CALIBRATION FAILED", "INSUFFICIENT DATA")
WIN_VALUES = {"win", "won", "w"}
LOSS_VALUES = {"loss", "lost", "l"}
PUSH_VALUES = {"push", "pushed", "void", "tie"}
CANCEL_VALUES = {"cancel", "cancelled", "canceled", "no_action"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _canonical(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(prefix: str, payload: Mapping[str, Any], length: int = 32) -> str:
    return f"{prefix}_{hashlib.sha256(_canonical(payload).encode('utf-8')).hexdigest()[:length]}"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def normalize_result(value: Any) -> str:
    text = _text(value).lower().replace(" ", "_")
    if text in WIN_VALUES:
        return "win"
    if text in LOSS_VALUES:
        return "loss"
    if text in PUSH_VALUES:
        return "push"
    if text in CANCEL_VALUES:
        return "cancel"
    if text in {"pending", "open", "ungraded", ""}:
        return "pending"
    return "unknown"


def decimal_price(row: Mapping[str, Any]) -> float:
    value = _float(row.get("decimal_odds") or row.get("odds"), 0.0)
    if value > 1.0:
        return value
    american = _float(row.get("american_odds"), 0.0)
    if american > 0:
        return 1.0 + american / 100.0
    if american < 0:
        return 1.0 + 100.0 / abs(american)
    return 0.0


def closing_decimal_price(row: Mapping[str, Any]) -> float:
    value = _float(row.get("closing_decimal_odds") or row.get("closing_odds") or row.get("close_decimal_odds"), 0.0)
    if value > 1.0:
        return value
    american = _float(row.get("closing_american_odds"), 0.0)
    if american > 0:
        return 1.0 + american / 100.0
    if american < 0:
        return 1.0 + 100.0 / abs(american)
    return 0.0


def _event_key(row: Mapping[str, Any]) -> str:
    parts = [
        _text(row.get("sport") or row.get("league")).lower(),
        _text(row.get("event") or row.get("event_name") or row.get("matchup")).lower(),
        _text(row.get("event_start_utc") or row.get("event_start_time") or row.get("commence_time") or row.get("date")).lower(),
    ]
    key = "|".join(parts).strip("|")
    return key or _text(row.get("proof_id") or row.get("id")).lower()


def normalize_calibration_row(row: Mapping[str, Any]) -> dict[str, Any]:
    result = normalize_result(row.get("result") or row.get("grade") or row.get("outcome"))
    stake = max(0.0, _float(row.get("stake") or row.get("unit_size") or row.get("units"), 1.0))
    price = decimal_price(row)
    close_price = closing_decimal_price(row)
    profit = _float(row.get("profit_units") or row.get("profit") or row.get("pnl_units"), 0.0)
    if profit == 0.0 and result == "win" and price > 1.0:
        profit = stake * (price - 1.0)
    elif profit == 0.0 and result == "loss":
        profit = -stake
    elif result in {"push", "cancel"}:
        profit = 0.0
    clv_decimal = close_price - price if close_price > 1.0 and price > 1.0 else 0.0
    return {
        "event_key": _event_key(row),
        "result": result,
        "stake": round(stake, 6),
        "decimal_odds": round(price, 6),
        "closing_decimal_odds": round(close_price, 6),
        "profit_units": round(profit, 6),
        "CLV_decimal": round(clv_decimal, 6),
        "CLV_percent": round((clv_decimal / price) if price > 1.0 else 0.0, 6),
        "has_closing_odds": close_price > 1.0,
        "playable_result": result in {"win", "loss"},
        "push_cancel": result in {"push", "cancel"},
        "pending_or_unknown": result in {"pending", "unknown"},
    }


def summarize_roi_clv_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = [normalize_calibration_row(row) for row in rows or []]
    playable = [row for row in normalized if row["playable_result"]]
    clv_rows = [row for row in normalized if row["has_closing_odds"]]
    wins = len([row for row in playable if row["result"] == "win"])
    losses = len([row for row in playable if row["result"] == "loss"])
    stake_total = round(sum(row["stake"] for row in playable), 6)
    profit_units = round(sum(row["profit_units"] for row in playable), 6)
    unique_events = len({row["event_key"] for row in normalized if row["event_key"]})
    return {
        "rows": normalized,
        "row_count": len(normalized),
        "unique_events": unique_events,
        "duplicate_row_count": max(0, len(normalized) - unique_events),
        "playable_count": len(playable),
        "wins": wins,
        "losses": losses,
        "push_cancel_count": len([row for row in normalized if row["push_cancel"]]),
        "pending_unknown_count": len([row for row in normalized if row["pending_or_unknown"]]),
        "stake_total": stake_total,
        "profit_units": profit_units,
        "ROI": round(profit_units / stake_total, 6) if stake_total else 0.0,
        "win_rate_ex_push_cancel": round(wins / len(playable), 6) if playable else 0.0,
        "clv_sample_count": len(clv_rows),
        "average_CLV_percent": round(sum(row["CLV_percent"] for row in clv_rows) / len(clv_rows), 6) if clv_rows else 0.0,
        "positive_CLV_count": len([row for row in clv_rows if row["CLV_percent"] > 0]),
        "negative_CLV_count": len([row for row in clv_rows if row["CLV_percent"] < 0]),
    }


def validate_roi_clv_calibration(summary: Mapping[str, Any], min_clv_sample: int = 10) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    if int(summary.get("row_count") or 0) == 0:
        errors.append("no rows available for ROI/CLV calibration")
    if int(summary.get("playable_count") or 0) == 0 and int(summary.get("row_count") or 0) > 0:
        errors.append("no playable win/loss rows available")
    if int(summary.get("clv_sample_count") or 0) < min_clv_sample and int(summary.get("row_count") or 0) > 0:
        warnings.append("CLV sample size is below calibration target")
    if int(summary.get("duplicate_row_count") or 0) > 0:
        warnings.append("row-level picks include duplicate event exposure")
    if int(summary.get("unique_events") or 0) > int(summary.get("row_count") or 0):
        errors.append("unique event count cannot exceed row count")
    if not 0.0 <= float(summary.get("win_rate_ex_push_cancel") or 0.0) <= 1.0:
        errors.append("win rate is outside valid probability range")
    if abs(float(summary.get("ROI") or 0.0)) > 10.0:
        warnings.append("ROI magnitude is unusually large and should be reviewed")
    if float(summary.get("average_CLV_percent") or 0.0) < -0.02 and int(summary.get("clv_sample_count") or 0) >= min_clv_sample:
        warnings.append("average CLV is materially negative")
    status = "CALIBRATION FAILED" if errors else "CALIBRATION WARNING" if warnings else "CALIBRATION OK"
    if int(summary.get("row_count") or 0) == 0 or int(summary.get("playable_count") or 0) == 0:
        status = "INSUFFICIENT DATA" if not errors else status
    return {"passed": not errors, "status": status, "checked_outputs": ["ROI", "win_rate_ex_push_cancel", "push_cancel_handling", "unique_events", "CLV"], "warnings": sorted(set(warnings)), "errors": sorted(set(errors))}


def build_roi_clv_calibration_report(workspace_id: str | None = None, rows: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    workspace = _text(workspace_id) or "default"
    summary = summarize_roi_clv_rows(rows or [])
    validation = validate_roi_clv_calibration(summary)
    report = {"schema_version": SCHEMA_VERSION, "generated_at_utc": _utc_now(), "workspace_id": workspace, "report_id": "", "report_hash": "", "status": validation["status"], "overall_passed": validation["passed"], **{k: v for k, v in summary.items() if k != "rows"}, "checked_outputs": validation["checked_outputs"], "warnings": validation["warnings"], "errors": validation["errors"], "row_summaries": summary["rows"]}
    report["report_id"] = _hash("roi_clv_calibration", {"workspace_id": workspace, "rows": summary["rows"]}, 24)
    report["report_hash"] = build_roi_clv_calibration_hash(report)
    return report


def build_roi_clv_calibration_hash(report: Mapping[str, Any]) -> str:
    stable = {k: v for k, v in dict(report).items() if k not in {"generated_at_utc", "report_hash"}}
    return _hash("roi_clv_calibration_hash", stable)


def validate_roi_clv_calibration_report(report: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    required = ("schema_version", "workspace_id", "report_id", "report_hash", "status", "overall_passed", "row_count", "unique_events", "playable_count", "ROI", "win_rate_ex_push_cancel", "average_CLV_percent")
    for field in required:
        if field not in report:
            errors.append(f"missing field: {field}")
    if report.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported ROI/CLV calibration schema_version")
    if report.get("status") not in STATUS_VALUES:
        errors.append("unsupported ROI/CLV calibration status")
    if report.get("report_hash") and build_roi_clv_calibration_hash(report) != report.get("report_hash"):
        errors.append("report_hash does not match report contents")
    if report.get("overall_passed") and report.get("errors"):
        errors.append("overall_passed is overstated")
    if int(report.get("unique_events") or 0) > int(report.get("row_count") or 0):
        errors.append("unique_events cannot exceed row_count")
    return {"passed": not errors, "checked_outputs": ["schema_version", "report_hash", "status", "overall_passed", "event_row_math"], "warnings": [], "errors": errors, "details": {"rebuilt_report_hash": build_roi_clv_calibration_hash(report) if report.get("report_hash") else ""}}


def sanitize_roi_clv_calibration_report(report: Mapping[str, Any]) -> dict[str, Any]:
    keys = ("schema_version", "workspace_id", "report_id", "report_hash", "status", "overall_passed", "row_count", "unique_events", "duplicate_row_count", "playable_count", "wins", "losses", "push_cancel_count", "pending_unknown_count", "stake_total", "profit_units", "ROI", "win_rate_ex_push_cancel", "clv_sample_count", "average_CLV_percent", "positive_CLV_count", "negative_CLV_count")
    payload = {key: report.get(key, 0) for key in keys}
    payload["warning_count"] = len(report.get("warnings") or [])
    payload["error_count"] = len(report.get("errors") or [])
    return payload


def export_roi_clv_calibration_report_json(report: Mapping[str, Any], public_safe: bool = True) -> str:
    payload = sanitize_roi_clv_calibration_report(report) if public_safe else dict(report)
    return json.dumps(_json_safe(payload), sort_keys=True, indent=2)
