from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.market_optimizer_preview import safe_float
from autonomous_betting_agent.row_normalizer import safe_text

SCHEMA_VERSION = "subscriber_ledger_v1"
PREVIEW_ONLY = "PREVIEW ONLY"
FORBIDDEN = "FORBIDDEN"
READY = "LEDGER REPORTS READY"
REVIEW = "REVIEW REQUIRED"
BLOCKED = "BLOCKED"
PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

RESULT_WIN = "win"
RESULT_LOSS = "loss"
RESULT_PUSH = "push"
RESULT_CANCEL = "cancel"
RESULT_PENDING = "pending"
RESULT_UNKNOWN = "unknown"
SETTLED_RESULTS = {RESULT_WIN, RESULT_LOSS, RESULT_PUSH, RESULT_CANCEL}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any) -> str:
    return safe_text(value)


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


def parse_csv_text(csv_text: str | None) -> list[dict[str, str]]:
    text = _text(csv_text)
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    return [{_text(key): _text(value) for key, value in row.items() if _text(key)} for row in reader]


def parse_json_object(json_text: str | None) -> dict[str, Any]:
    text = _text(json_text)
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {"parse_error": "invalid_json"}
    return value if isinstance(value, dict) else {"parse_error": "json_root_not_object"}


def csv_from_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    row_list = [dict(row) for row in rows or []]
    fieldnames: list[str] = []
    for row in row_list:
        for key in row:
            if str(key) not in fieldnames:
                fieldnames.append(str(key))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    if fieldnames:
        writer.writeheader()
        for row in row_list:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return output.getvalue()


def result_status(value: Any) -> str:
    text = _text(value).lower()
    if text in {"win", "won", "w", "1"}:
        return RESULT_WIN
    if text in {"loss", "lost", "l", "-1"}:
        return RESULT_LOSS
    if text in {"push", "void", "tie"}:
        return RESULT_PUSH
    if text in {"cancel", "cancelled", "canceled", "no action", "postponed"}:
        return RESULT_CANCEL
    if text in {"pending", "open", "unsettled"}:
        return RESULT_PENDING
    return RESULT_UNKNOWN


def event_key(row: Mapping[str, Any]) -> str:
    for key in ("event_id", "event_key", "game_id", "match_id"):
        value = _text(row.get(key))
        if value:
            return value
    event = _text(row.get("event") or row.get("matchup") or row.get("game"))
    date = _text(row.get("date") or row.get("event_date") or row.get("start_time"))
    return stable_hash("event", {"event": event, "date": date}, 16)


def subscriber_id(row: Mapping[str, Any]) -> str:
    return _text(row.get("subscriber_id") or row.get("subscriber") or row.get("client_id") or row.get("name")) or "unknown_subscriber"


def decimal_odds(row: Mapping[str, Any]) -> float | None:
    value = safe_float(row.get("decimal_odds") or row.get("odds") or row.get("odds_taken"))
    if value is not None and value > 1:
        return value
    american = safe_float(row.get("american_odds") or row.get("odds_american"))
    if american is None or american == 0:
        return None
    if american > 0:
        return round(1.0 + american / 100.0, 6)
    return round(1.0 + 100.0 / abs(american), 6)


def stake(row: Mapping[str, Any]) -> float:
    return max(0.0, safe_float(row.get("stake") or row.get("recommended_stake") or row.get("amount")) or 0.0)


def profit_loss(row: Mapping[str, Any]) -> float:
    explicit = safe_float(row.get("profit_loss") or row.get("profit") or row.get("pnl") or row.get("unit_profit"))
    if explicit is not None:
        return round(explicit, 6)
    amount = stake(row)
    dec = decimal_odds(row)
    result = result_status(row.get("result") or row.get("status") or row.get("grade"))
    if result == RESULT_WIN and dec is not None:
        return round(amount * (dec - 1.0), 6)
    if result == RESULT_LOSS:
        return round(-amount, 6)
    return 0.0


def normalize_ledger_row(row: Mapping[str, Any], index: int = 0) -> dict[str, Any]:
    result = result_status(row.get("result") or row.get("status") or row.get("grade"))
    normalized = {
        "ledger_id": _text(row.get("ledger_id")) or stable_hash("ledger", {"row": row, "index": index}, 18),
        "subscriber_id": subscriber_id(row),
        "subscriber_name": _text(row.get("subscriber_name") or row.get("name")),
        "date": _text(row.get("date") or row.get("event_date") or row.get("created_at")),
        "sport": _text(row.get("sport")).lower(),
        "league": _text(row.get("league")).lower(),
        "event_id": event_key(row),
        "event": _text(row.get("event") or row.get("matchup") or row.get("game")),
        "market_type": _text(row.get("market_type") or row.get("market") or row.get("bet_type")).lower(),
        "selection": _text(row.get("selection") or row.get("pick") or row.get("recommended_bet")),
        "sportsbook": _text(row.get("sportsbook") or row.get("book") or row.get("casino")).lower(),
        "odds_taken": decimal_odds(row),
        "stake": stake(row),
        "result": result,
        "profit_loss": profit_loss(row),
        "risk_level": _text(row.get("risk_level") or row.get("risk_label")).lower(),
        "ev": safe_float(row.get("ev")),
        "edge": safe_float(row.get("edge") or row.get("calibrated_edge")),
        "clv": safe_float(row.get("clv") or row.get("closing_line_value")),
        "source_recommendation_id": _text(row.get("recommendation_id") or row.get("proof_id") or row.get("tracking_id")),
    }
    normalized["row_hash"] = stable_hash("ledger_row", normalized, 18)
    return normalized


def outcome_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(row.get("result") for row in rows or [])
    return {
        "wins": counts.get(RESULT_WIN, 0),
        "losses": counts.get(RESULT_LOSS, 0),
        "pushes": counts.get(RESULT_PUSH, 0),
        "cancels": counts.get(RESULT_CANCEL, 0),
        "pending": counts.get(RESULT_PENDING, 0),
        "unknown": counts.get(RESULT_UNKNOWN, 0),
    }


def win_rate(rows: Sequence[Mapping[str, Any]]) -> float | None:
    counts = outcome_counts(rows)
    graded = counts["wins"] + counts["losses"]
    if graded <= 0:
        return None
    return round(counts["wins"] / graded, 6)


def roi(rows: Sequence[Mapping[str, Any]]) -> float | None:
    total_stake = sum(float(row.get("stake") or 0.0) for row in rows or [] if row.get("result") in SETTLED_RESULTS)
    pnl = sum(float(row.get("profit_loss") or 0.0) for row in rows or [] if row.get("result") in SETTLED_RESULTS)
    if total_stake <= 0:
        return None
    return round(pnl / total_stake, 6)


def group_performance(rows: Sequence[Mapping[str, Any]], field: str) -> list[dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows or []:
        groups[_text(row.get(field)) or "unknown"].append(row)
    output = []
    for key, group_rows in sorted(groups.items()):
        counts = outcome_counts(group_rows)
        settled = [row for row in group_rows if row.get("result") in SETTLED_RESULTS]
        output.append({
            field: key,
            "row_count": len(group_rows),
            "unique_event_count": len({row.get("event_id") for row in group_rows}),
            **counts,
            "win_rate_ex_push_cancel": win_rate(group_rows),
            "profit_loss": round(sum(float(row.get("profit_loss") or 0.0) for row in settled), 6),
            "stake": round(sum(float(row.get("stake") or 0.0) for row in settled), 6),
            "roi": roi(group_rows),
        })
    return sorted(output, key=lambda row: (row.get("profit_loss") or 0, row.get("roi") or -999), reverse=True)


def mistake_patterns(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    patterns = []
    for field in ("sport", "market_type", "sportsbook", "risk_level"):
        for perf in group_performance(rows, field):
            losses = int(perf.get("losses") or 0)
            wins = int(perf.get("wins") or 0)
            roi_value = perf.get("roi")
            if losses >= 2 and losses > wins:
                patterns.append({"pattern_id": f"loss_cluster_{field}_{perf.get(field)}", "field": field, "value": perf.get(field), "severity": "WARN", "reason": "losses exceed wins", "row_count": perf.get("row_count"), "roi": roi_value})
            if roi_value is not None and roi_value < -0.1:
                patterns.append({"pattern_id": f"negative_roi_{field}_{perf.get(field)}", "field": field, "value": perf.get(field), "severity": "WARN", "reason": "segment ROI below -10%", "row_count": perf.get("row_count"), "roi": roi_value})
    return patterns


def subscriber_summary(subscriber: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    settled = [row for row in rows if row.get("result") in SETTLED_RESULTS]
    counts = outcome_counts(rows)
    sports = group_performance(rows, "sport")
    markets = group_performance(rows, "market_type")
    books = group_performance(rows, "sportsbook")
    return {
        "subscriber_id": subscriber,
        "row_count": len(rows),
        "settled_row_count": len(settled),
        "unique_event_count": len({row.get("event_id") for row in rows}),
        **counts,
        "win_rate_ex_push_cancel": win_rate(rows),
        "profit_loss": round(sum(float(row.get("profit_loss") or 0.0) for row in settled), 6),
        "stake": round(sum(float(row.get("stake") or 0.0) for row in settled), 6),
        "roi": roi(rows),
        "best_sport": sports[0].get("sport") if sports else None,
        "worst_sport": sorted(sports, key=lambda row: (row.get("profit_loss") or 0, row.get("roi") or 0))[0].get("sport") if sports else None,
        "best_market_type": markets[0].get("market_type") if markets else None,
        "worst_market_type": sorted(markets, key=lambda row: (row.get("profit_loss") or 0, row.get("roi") or 0))[0].get("market_type") if markets else None,
        "best_sportsbook": books[0].get("sportsbook") if books else None,
        "worst_sportsbook": sorted(books, key=lambda row: (row.get("profit_loss") or 0, row.get("roi") or 0))[0].get("sportsbook") if books else None,
        "mistake_pattern_count": len(mistake_patterns(rows)),
    }


def build_subscriber_ledger_reports(workspace_id: str | None = None, ledger_rows: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    normalized = [normalize_ledger_row(row, index) for index, row in enumerate(ledger_rows or [])]
    by_subscriber: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in normalized:
        by_subscriber[row["subscriber_id"]].append(row)
    summaries = [subscriber_summary(subscriber, rows) for subscriber, rows in sorted(by_subscriber.items())]
    global_summary = subscriber_summary("GLOBAL", normalized) if normalized else {"subscriber_id": "GLOBAL", "row_count": 0, "unique_event_count": 0, "win_rate_ex_push_cancel": None, "roi": None, "profit_loss": 0.0}
    patterns = []
    for subscriber, rows in sorted(by_subscriber.items()):
        for pattern in mistake_patterns(rows):
            patterns.append({"subscriber_id": subscriber, **pattern})
    checks = validate_ledger(normalized, summaries)
    summary = summarize_checks(checks)
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "mode": PREVIEW_ONLY,
        **summary,
        "ledger_row_count": len(normalized),
        "subscriber_count": len(by_subscriber),
        "unique_event_count": len({row.get("event_id") for row in normalized}),
        "ledger_rows": normalized,
        "subscriber_summaries": summaries,
        "global_summary": global_summary,
        "sport_performance": group_performance(normalized, "sport"),
        "market_type_performance": group_performance(normalized, "market_type"),
        "sportsbook_performance": group_performance(normalized, "sportsbook"),
        "mistake_patterns": patterns,
        "ledger_checks": checks,
        "safety_gates": {
            "billing_charge_execution": FORBIDDEN,
            "api_key_exposure": FORBIDDEN,
            "live_wager_execution": FORBIDDEN,
            "account_access": FORBIDDEN,
            "funds_movement": FORBIDDEN,
            "automatic_proof_change": FORBIDDEN,
            "automatic_model_change": FORBIDDEN,
            "profit_guarantee": FORBIDDEN,
        },
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "warnings": [row for row in checks if row.get("status") == WARN],
        "errors": [row for row in checks if row.get("status") == FAIL],
    }
    report["ledger_run_id"] = stable_hash("subscriber_ledger", {"workspace_id": report["workspace_id"], "rows": normalized}, 24)
    report["ledger_hash"] = stable_hash("subscriber_ledger_hash", {key: value for key, value in report.items() if key != "generated_at_utc"}, 32)
    return report


def check_row(check_id: str, title: str, status: str, details: str = "", expected: Any = "", actual: Any = "") -> dict[str, Any]:
    return {"check_id": check_id, "title": title, "status": status, "details": details, "expected": expected, "actual": actual}


def validate_ledger(rows: Sequence[Mapping[str, Any]], summaries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    checks = [
        check_row("ledger_rows_present", "Ledger rows supplied", PASS if rows else FAIL, details=f"rows={len(rows)}"),
        check_row("subscriber_summaries_created", "Subscriber summaries created", PASS if summaries else FAIL, details=f"summaries={len(summaries)}"),
        check_row("unique_events_separated", "Unique event count separated from row count", PASS if all("unique_event_count" in summary and "row_count" in summary for summary in summaries) else FAIL),
        check_row("push_cancel_excluded_win_rate", "Win rate excludes pushes/cancels", PASS if all("win_rate_ex_push_cancel" in summary for summary in summaries) else FAIL),
        check_row("roi_present", "ROI present", PASS if all("roi" in summary for summary in summaries) else FAIL),
    ]
    unknown_count = sum(1 for row in rows if row.get("result") == RESULT_UNKNOWN)
    if unknown_count:
        checks.append(check_row("unknown_results", "Unknown result rows require review", WARN, actual=unknown_count))
    duplicate_ids = [item for item, count in Counter(row.get("ledger_id") for row in rows).items() if count > 1]
    checks.append(check_row("ledger_ids_unique", "Ledger IDs unique", PASS if not duplicate_ids else FAIL, actual=duplicate_ids))
    return checks


def summarize_checks(checks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    pass_count = len([row for row in checks or [] if row.get("status") == PASS])
    warn_count = len([row for row in checks or [] if row.get("status") == WARN])
    fail_count = len([row for row in checks or [] if row.get("status") == FAIL])
    if fail_count:
        status = BLOCKED
    elif warn_count:
        status = REVIEW
    else:
        status = READY
    return {"ledger_status": status, "pass_count": pass_count, "warn_count": warn_count, "fail_count": fail_count}


def build_subscriber_ledger_reports_from_text(workspace_id: str | None = None, ledger_csv_text: str | None = None) -> dict[str, Any]:
    return build_subscriber_ledger_reports(workspace_id, parse_csv_text(ledger_csv_text))


def export_subscriber_ledger_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_ledger_rows_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("ledger_rows") or [])


def export_subscriber_summaries_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("subscriber_summaries") or [])


def export_sport_performance_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("sport_performance") or [])


def export_market_type_performance_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("market_type_performance") or [])


def export_sportsbook_performance_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("sportsbook_performance") or [])


def export_mistake_patterns_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("mistake_patterns") or [])


def export_ledger_checks_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("ledger_checks") or [])


def export_ledger_manifest_json(report: Mapping[str, Any]) -> str:
    manifest = {key: report.get(key) for key in ("schema_version", "workspace_id", "ledger_run_id", "ledger_hash", "generated_at_utc", "ledger_status", "ledger_row_count", "subscriber_count", "unique_event_count", "preview_only", "files_written", "live_changes")}
    return json.dumps(_safe(manifest), sort_keys=True, indent=2)
