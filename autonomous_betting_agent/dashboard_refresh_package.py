from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.accuracy_decision_integration_preview import (
    build_accuracy_decision_integration_report,
    csv_from_rows,
    parse_csv_text,
)
from autonomous_betting_agent.odds_reparodynamics_upgrade_layer import (
    event_key,
    market_type,
    normalize_decimal_odds,
    sportsbook,
)
from autonomous_betting_agent.value_math import normalize_probability, safe_float

SCHEMA_VERSION = "dashboard_refresh_package_v1"
DASHBOARD_READY = "DASHBOARD READY"
REVIEW_REQUIRED = "REVIEW REQUIRED"
NO_ROWS = "NO ROWS"
SHADOW_ONLY = "SHADOW ONLY"
FORBIDDEN = "FORBIDDEN"
WIN = "win"
LOSS = "loss"
PUSH = "push"
CANCEL = "cancel"
PENDING = "pending"
UNKNOWN = "unknown"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _canonical(value: Any) -> str:
    return json.dumps(_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_hash(prefix: str, value: Any, length: int = 24) -> str:
    return f"{prefix}_{hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()[:length]}"


def result_status(row: Mapping[str, Any]) -> str:
    text = " ".join(_text(row.get(key)).lower() for key in ("result", "grade", "outcome", "official_result", "final_result", "status", "result_status"))
    if any(token in text for token in ("cancel", "void", "postpone", "abandon")):
        return CANCEL
    if any(token in text for token in ("push", "draw", "tie", "refund")):
        return PUSH
    if "pending" in text or "open" in text or "ungraded" in text or not text.strip():
        return PENDING
    if "loss" in text or "lost" in text or text.strip() == "l":
        return LOSS
    if "win" in text or "won" in text or text.strip() == "w":
        return WIN
    return UNKNOWN


def is_completed(status: str) -> bool:
    return status in {WIN, LOSS, PUSH, CANCEL}


def row_profit_units(row: Mapping[str, Any], status: str | None = None) -> float | None:
    for key in ("profit_units", "unit_profit", "pnl_units", "net_units", "profit", "net_profit"):
        value = safe_float(row.get(key))
        if value is not None:
            return round(value, 8)
    stake = safe_float(row.get("stake_units")) or safe_float(row.get("stake")) or 1.0
    decimal = normalize_decimal_odds(row)
    state = status or result_status(row)
    if state == WIN and decimal is not None:
        return round(stake * (decimal - 1.0), 8)
    if state == LOSS:
        return round(-stake, 8)
    if state in {PUSH, CANCEL}:
        return 0.0
    return None


def clv_delta(row: Mapping[str, Any]) -> float | None:
    for key in ("CLV_decimal_delta", "clv_decimal_delta", "closing_line_value", "clv"):
        value = safe_float(row.get(key))
        if value is not None:
            return round(value, 8)
    locked = normalize_decimal_odds(row)
    closing = safe_float(row.get("closing_decimal_odds") or row.get("closing_odds_decimal") or row.get("closing_price"))
    if locked is None or closing is None or closing <= 1.0:
        return None
    return round(locked - closing, 8)


def baseline_ev(row: Mapping[str, Any]) -> float | None:
    for key in ("baseline_EV", "baseline_ev", "expected_value", "EV", "ev"):
        value = safe_float(row.get(key))
        if value is not None:
            return round(value, 8)
    return None


def calibrated_ev(row: Mapping[str, Any]) -> float | None:
    for key in ("calibrated_EV", "calibrated_ev", "expected_value_calibrated"):
        value = safe_float(row.get(key))
        if value is not None:
            return round(value, 8)
    return None


def final_action(row: Mapping[str, Any]) -> str:
    for key in ("final_action", "action", "recommendation", "decision_action"):
        text = _text(row.get(key)).upper()
        if text:
            if "PLAY" in text:
                return "PLAYABLE VALUE"
            if "WAIT" in text:
                return "WAIT FOR BETTER ODDS"
            if "WATCH" in text:
                return "WATCH ONLY"
            if "NO" in text or "PASS" in text:
                return "NO BET"
            return text
    return "NO BET"


def blocker_list(row: Mapping[str, Any]) -> list[str]:
    value = row.get("final_blockers") or row.get("blockers") or row.get("decision_blockers") or row.get("decision_reason") or ""
    if isinstance(value, list):
        return [str(item) for item in value if _text(item)]
    text = _text(value)
    if not text:
        return []
    cleaned = text.replace("[", "").replace("]", "").replace("'", "").replace('"', "")
    parts = []
    for chunk in cleaned.replace(";", ",").split(","):
        item = _text(chunk)
        if item:
            parts.append(item)
    return parts


def row_segment(row: Mapping[str, Any], key: str) -> str:
    if key == "sport":
        return _text(row.get("sport") or row.get("sport_name") or "unknown")
    if key == "league":
        return _text(row.get("league") or row.get("league_name") or "unknown")
    if key == "market_type":
        return market_type(row)
    if key == "sportsbook":
        return sportsbook(row)
    return "unknown"


def summarize_records(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    records = [dict(row) for row in rows or []]
    statuses = [result_status(row) for row in records]
    counts = Counter(statuses)
    completed = len([status for status in statuses if is_completed(status)])
    graded = counts[WIN] + counts[LOSS]
    win_rate = round(counts[WIN] / graded, 8) if graded else None
    profits = [row_profit_units(row, result_status(row)) for row in records]
    valid_profits = [value for value in profits if value is not None]
    total_profit = round(sum(valid_profits), 8) if valid_profits else 0.0
    stake_total = 0.0
    for row, status in zip(records, statuses):
        if status in {WIN, LOSS, PUSH, CANCEL}:
            stake_total += safe_float(row.get("stake_units")) or safe_float(row.get("stake")) or 1.0
    roi = round(total_profit / stake_total, 8) if stake_total else None
    events = [event_key(row) for row in records]
    unique_events = len(set(events))
    duplicates = len([event for event, count in Counter(events).items() if count > 1])
    clv_values = [value for value in (clv_delta(row) for row in records) if value is not None]
    baseline_values = [value for value in (baseline_ev(row) for row in records) if value is not None]
    calibrated_values = [value for value in (calibrated_ev(row) for row in records) if value is not None]
    return {
        "row_count": len(records),
        "unique_event_count": unique_events,
        "duplicate_event_group_count": duplicates,
        "completed_count": completed,
        "pending_count": counts[PENDING],
        "unknown_count": counts[UNKNOWN],
        "wins": counts[WIN],
        "losses": counts[LOSS],
        "pushes": counts[PUSH],
        "cancels": counts[CANCEL],
        "win_rate_ex_push_cancel": win_rate,
        "total_profit_units": total_profit,
        "stake_units": round(stake_total, 8),
        "roi": roi,
        "average_CLV_decimal_delta": round(sum(clv_values) / len(clv_values), 8) if clv_values else None,
        "positive_CLV_count": len([value for value in clv_values if value > 0]),
        "negative_CLV_count": len([value for value in clv_values if value < 0]),
        "average_baseline_EV": round(sum(baseline_values) / len(baseline_values), 8) if baseline_values else None,
        "average_calibrated_EV": round(sum(calibrated_values) / len(calibrated_values), 8) if calibrated_values else None,
    }


def action_breakdown(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(final_action(row) for row in rows or [])
    total = max(1, sum(counts.values()))
    return [{"final_action": key, "count": value, "share": round(value / total, 8)} for key, value in sorted(counts.items())]


def blocker_breakdown(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for row in rows or []:
        counts.update(blocker_list(row))
    return [{"blocker": key, "count": value} for key, value in counts.most_common()]


def event_breakdown(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows or []:
        groups[event_key(row)].append(dict(row))
    output = []
    for key, group in sorted(groups.items()):
        summary = summarize_records(group)
        output.append({"event_key": key, "row_count": len(group), "is_duplicate_group": len(group) > 1, **summary})
    return output


def segment_breakdown(rows: Sequence[Mapping[str, Any]], segment_keys: Sequence[str] = ("sport", "league", "market_type", "sportsbook")) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for segment in segment_keys:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows or []:
            groups[row_segment(row, segment)].append(dict(row))
        for value, group in sorted(groups.items()):
            summary = summarize_records(group)
            output.append({"segment_group": segment, "segment_value": value, **summary})
    return output


def enriched_dashboard_rows(proof_rows: Sequence[Mapping[str, Any]], decision_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    decision_by_id = {_text(row.get("row_id")): dict(row) for row in decision_rows or [] if _text(row.get("row_id"))}
    decision_by_index = {int(row.get("row_index", index)): dict(row) for index, row in enumerate(decision_rows or []) if isinstance(row, Mapping)}
    output: list[dict[str, Any]] = []
    for index, row in enumerate(proof_rows or []):
        source = dict(row)
        row_id = _text(source.get("proof_id") or source.get("pick_id") or source.get("row_id") or source.get("id") or f"row_{index}")
        decision = decision_by_id.get(row_id) or decision_by_index.get(index, {})
        status = result_status(source)
        merged = {
            "row_index": index,
            "row_id": row_id,
            "event_key": event_key(source),
            "event": source.get("event") or source.get("event_name") or source.get("matchup") or source.get("event_id") or "",
            "selection": source.get("selection") or source.get("pick") or source.get("prediction") or "",
            "sport": source.get("sport") or source.get("sport_name") or "unknown",
            "league": source.get("league") or source.get("league_name") or "unknown",
            "market_type": market_type(source),
            "sportsbook": sportsbook(source),
            "result_status": status,
            "decimal_odds": normalize_decimal_odds(source),
            "model_probability": normalize_probability(source.get("model_probability") or source.get("confidence") or source.get("probability")),
            "profit_units": row_profit_units(source, status),
            "CLV_decimal_delta": clv_delta({**source, **decision}),
            "baseline_EV": baseline_ev({**source, **decision}),
            "calibrated_EV": calibrated_ev({**source, **decision}),
            "final_action": final_action(decision or source),
            "final_blockers": blocker_list(decision or source),
            "decision_reason": decision.get("decision_reason", source.get("decision_reason", "")) if decision else source.get("decision_reason", ""),
            "price_quality": decision.get("price_quality", source.get("price_quality", "")) if decision else source.get("price_quality", ""),
            "calibration_status": decision.get("calibration_status", source.get("calibration_status", "")) if decision else source.get("calibration_status", ""),
            "simulated_stake_fraction": safe_float(decision.get("simulated_stake_fraction")) if decision else safe_float(source.get("simulated_stake_fraction")),
        }
        output.append(merged)
    return output


def build_dashboard_manifest(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report.get("schema_version"),
        "workspace_id": report.get("workspace_id"),
        "dashboard_refresh_id": report.get("dashboard_refresh_id"),
        "dashboard_refresh_hash": report.get("dashboard_refresh_hash"),
        "generated_at_utc": report.get("generated_at_utc"),
        "status": report.get("status"),
        "mode": report.get("mode"),
        "source_row_count": report.get("source_row_count"),
        "decision_row_count": report.get("decision_row_count"),
        "preview_only": report.get("preview_only"),
        "files_written": report.get("files_written"),
        "live_changes": report.get("live_changes"),
    }


def build_dashboard_refresh_package(
    workspace_id: str | None = None,
    proof_rows: Sequence[Mapping[str, Any]] | None = None,
    history_rows: Sequence[Mapping[str, Any]] | None = None,
    decision_preview_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    proof = [dict(row) for row in proof_rows or []]
    history = [dict(row) for row in history_rows or []]
    supplied_decisions = [dict(row) for row in decision_preview_rows or []]
    generated_decision_report = None
    if supplied_decisions:
        decisions = supplied_decisions
    else:
        generated_decision_report = build_accuracy_decision_integration_report(workspace_id, proof, history)
        decisions = [dict(row) for row in generated_decision_report.get("decision_preview_rows") or []]
    enriched = enriched_dashboard_rows(proof, decisions)
    summary = summarize_records(enriched)
    action_rows = action_breakdown(enriched)
    blocker_rows = blocker_breakdown(enriched)
    event_rows = event_breakdown(enriched)
    duplicate_rows = [row for row in event_rows if row.get("is_duplicate_group")]
    segment_rows = segment_breakdown(enriched)
    review_reasons: list[str] = []
    if summary["row_count"] == 0:
        status = NO_ROWS
        review_reasons.append("no_source_rows")
    else:
        status = DASHBOARD_READY
    if summary["unknown_count"]:
        status = REVIEW_REQUIRED
        review_reasons.append("unknown_result_rows")
    if duplicate_rows:
        review_reasons.append("duplicate_event_groups_present")
    if blocker_rows:
        review_reasons.append("blocked_decision_rows_present")
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "dashboard_refresh_id": "",
        "mode": SHADOW_ONLY,
        "status": status,
        "review_reasons": review_reasons,
        "source_row_count": len(proof),
        "history_row_count": len(history),
        "decision_row_count": len(decisions),
        **summary,
        "action_breakdown": action_rows,
        "blocker_breakdown": blocker_rows,
        "dashboard_rows": enriched,
        "event_breakdown": event_rows,
        "duplicate_event_groups": duplicate_rows,
        "segment_breakdown": segment_rows,
        "decision_summary": {key: value for key, value in (generated_decision_report or {}).items() if key not in {"decision_preview_rows", "repair_feedback"}},
        "safety_gates": {"live_mutation": FORBIDDEN, "model_training": FORBIDDEN, "stored_data_mutation": FORBIDDEN, "automatic_live_promotion": FORBIDDEN, "proof_overwrite": FORBIDDEN},
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "warnings": review_reasons,
        "errors": [] if proof else ["no proof rows supplied"],
    }
    report["dashboard_refresh_id"] = stable_hash("dashboard_refresh", {"workspace_id": workspace_id, "rows": enriched, "summary": summary}, 24)
    report["dashboard_refresh_hash"] = stable_hash("dashboard_refresh_hash", {k: v for k, v in report.items() if k != "generated_at_utc"}, 32)
    report["manifest"] = build_dashboard_manifest(report)
    return report


def build_dashboard_refresh_package_from_text(
    workspace_id: str | None = None,
    proof_csv_text: str | None = None,
    history_csv_text: str | None = None,
    decision_preview_csv_text: str | None = None,
) -> dict[str, Any]:
    return build_dashboard_refresh_package(
        workspace_id,
        parse_csv_text(proof_csv_text),
        parse_csv_text(history_csv_text),
        parse_csv_text(decision_preview_csv_text),
    )


def export_dashboard_refresh_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_dashboard_summary_csv(report: Mapping[str, Any]) -> str:
    keys = [
        "workspace_id", "status", "source_row_count", "unique_event_count", "duplicate_event_group_count", "completed_count", "pending_count", "wins", "losses", "pushes", "cancels", "win_rate_ex_push_cancel", "total_profit_units", "stake_units", "roi", "average_CLV_decimal_delta", "average_baseline_EV", "average_calibrated_EV", "playable_rows", "no_bet_rows",
    ]
    row = {key: report.get(key) for key in keys}
    action_counts = {item.get("final_action"): item.get("count") for item in report.get("action_breakdown") or []}
    row["playable_rows"] = action_counts.get("PLAYABLE VALUE", 0)
    row["no_bet_rows"] = action_counts.get("NO BET", 0)
    return csv_from_rows([row])


def export_dashboard_rows_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("dashboard_rows") or [])


def export_event_breakdown_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("event_breakdown") or [])


def export_duplicate_groups_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("duplicate_event_groups") or [])


def export_segment_breakdown_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("segment_breakdown") or [])


def export_blocker_breakdown_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("blocker_breakdown") or [])


def export_dashboard_manifest_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report.get("manifest") or build_dashboard_manifest(report)), sort_keys=True, indent=2)
