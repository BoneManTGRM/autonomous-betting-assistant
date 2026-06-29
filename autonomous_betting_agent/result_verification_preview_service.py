from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "result_verification_preview_v1"
DECISION_VALUES = ("GRADE READY", "MANUAL REVIEW", "NO SCORE", "NO CLV", "UNMATCHED")
SUPPORTED_MARKETS = {"moneyline", "spread", "total", "over_under", "winner"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


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


def event_key(row: Mapping[str, Any]) -> str:
    parts = [
        _text(row.get("sport") or row.get("league")).lower(),
        _text(row.get("event") or row.get("event_name") or row.get("matchup")).lower(),
        _text(row.get("event_start_utc") or row.get("event_start_time") or row.get("commence_time") or row.get("date")).lower(),
    ]
    return "|".join(parts).strip("|") or _text(row.get("proof_id") or row.get("id")).lower()


def decimal_price(row: Mapping[str, Any], *keys: str) -> float:
    for key in keys or ("decimal_odds", "odds"):
        value = _float(row.get(key), 0.0)
        if value > 1.0:
            return value
    american = _float(row.get("american_odds"), 0.0)
    if american > 0:
        return 1.0 + american / 100.0
    if american < 0:
        return 1.0 + 100.0 / abs(american)
    return 0.0


def normalize_score_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    key = event_key(payload)
    home_score = payload.get("home_score", payload.get("score_home"))
    away_score = payload.get("away_score", payload.get("score_away"))
    has_score = home_score not in (None, "") and away_score not in (None, "")
    return {
        "event_key": key,
        "source": _text(payload.get("source") or payload.get("provider")) or "manual_preview",
        "final_score": f"{home_score}-{away_score}" if has_score else "",
        "home_score": _float(home_score, 0.0) if has_score else None,
        "away_score": _float(away_score, 0.0) if has_score else None,
        "status": _text(payload.get("status") or payload.get("event_status") or "finished").lower(),
        "fetched_at_utc": _text(payload.get("fetched_at_utc") or payload.get("checked_at_utc") or _utc_now()),
        "result_confidence": max(0.0, min(1.0, _float(payload.get("result_confidence"), 1.0 if has_score else 0.0))),
        "has_score": has_score,
    }


def normalize_clv_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    locked_price = decimal_price(payload, "locked_decimal_odds", "decimal_odds", "odds")
    closing_price = decimal_price(payload, "closing_decimal_odds", "closing_odds", "close_decimal_odds")
    clv_decimal = closing_price - locked_price if locked_price > 1.0 and closing_price > 1.0 else 0.0
    return {
        "event_key": event_key(payload),
        "market_type": _text(payload.get("market_type") or payload.get("market")).lower(),
        "sportsbook": _text(payload.get("sportsbook") or payload.get("book") or payload.get("bookmaker")),
        "source": _text(payload.get("source") or payload.get("provider")) or "manual_preview",
        "locked_decimal_odds": round(locked_price, 6),
        "closing_decimal_odds": round(closing_price, 6),
        "CLV_decimal": round(clv_decimal, 6),
        "CLV_percent": round((clv_decimal / locked_price) if locked_price > 1.0 else 0.0, 6),
        "has_closing_line": closing_price > 1.0,
    }


def build_verification_row(row: Mapping[str, Any], scores_by_event: Mapping[str, Mapping[str, Any]], clv_by_event: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    key = event_key(row)
    score = scores_by_event.get(key, {})
    clv = clv_by_event.get(key, {})
    market = _text(row.get("market_type") or row.get("market")).lower()
    confidence = _float(score.get("result_confidence"), 0.0)
    manual_review = False
    reasons: list[str] = []
    decision = "GRADE READY"
    if not score.get("has_score"):
        decision = "NO SCORE"
        manual_review = True
        reasons.append("missing final score")
    if market and market not in SUPPORTED_MARKETS:
        decision = "MANUAL REVIEW"
        manual_review = True
        reasons.append("unsupported market type")
    if confidence < 0.75:
        decision = "MANUAL REVIEW"
        manual_review = True
        reasons.append("low result confidence")
    if not clv.get("has_closing_line"):
        reasons.append("missing closing line")
    return {
        "proof_id": _text(row.get("proof_id") or row.get("id")),
        "event_key": key,
        "event": _text(row.get("event") or row.get("event_name") or row.get("matchup")),
        "pick": _text(row.get("pick") or row.get("prediction") or row.get("selection")),
        "market_type": market,
        "sportsbook": _text(row.get("sportsbook") or row.get("book") or row.get("bookmaker")),
        "verification_decision": decision,
        "manual_review_required": manual_review,
        "manual_review_reasons": reasons,
        "final_score_source": score.get("source", ""),
        "final_score": score.get("final_score", ""),
        "graded_at_utc": _utc_now() if score.get("has_score") else "",
        "result_confidence": confidence,
        "clv_source": clv.get("source", ""),
        "closing_decimal_odds": clv.get("closing_decimal_odds", 0.0),
        "CLV_decimal": clv.get("CLV_decimal", 0.0),
        "CLV_percent": clv.get("CLV_percent", 0.0),
        "frozen_pick_logic": True,
    }


def build_verification_preview_report(workspace_id: str | None = None, proof_rows: Sequence[Mapping[str, Any]] | None = None, score_payloads: Sequence[Mapping[str, Any]] | None = None, clv_payloads: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    workspace = _text(workspace_id) or "default"
    rows = list(proof_rows or [])
    scores = [normalize_score_payload(item) for item in score_payloads or []]
    clvs = [normalize_clv_payload(item) for item in clv_payloads or []]
    scores_by_event = {item["event_key"]: item for item in scores if item.get("event_key")}
    clv_by_event = {item["event_key"]: item for item in clvs if item.get("event_key")}
    verification_rows = [build_verification_row(row, scores_by_event, clv_by_event) for row in rows]
    manual_review_count = len([row for row in verification_rows if row["manual_review_required"]])
    ready_count = len([row for row in verification_rows if row["verification_decision"] == "GRADE READY"])
    unique_events = len({row["event_key"] for row in verification_rows if row["event_key"]})
    status = "VERIFICATION READY" if rows and manual_review_count == 0 else "MANUAL REVIEW REQUIRED" if rows else "NO ROWS"
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "workspace_id": workspace,
        "report_id": "",
        "report_hash": "",
        "status": status,
        "overall_passed": bool(rows) and manual_review_count == 0,
        "row_count": len(rows),
        "unique_events": unique_events,
        "duplicate_row_count": max(0, len(rows) - unique_events),
        "score_payload_count": len(scores),
        "clv_payload_count": len(clvs),
        "ready_count": ready_count,
        "manual_review_count": manual_review_count,
        "frozen_pick_logic": True,
        "verification_rows": verification_rows,
        "warnings": ["manual review rows remain"] if manual_review_count else [],
        "errors": [] if rows else ["no proof rows supplied"],
    }
    report["report_id"] = _hash("verification_preview", {"workspace_id": workspace, "rows": verification_rows}, 24)
    report["report_hash"] = build_verification_preview_hash(report)
    return report


def build_verification_preview_hash(report: Mapping[str, Any]) -> str:
    stable = {k: v for k, v in dict(report).items() if k not in {"generated_at_utc", "report_hash"}}
    return _hash("verification_preview_hash", stable)


def validate_verification_preview_report(report: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    required = ("schema_version", "workspace_id", "report_id", "report_hash", "status", "overall_passed", "row_count", "unique_events", "verification_rows", "frozen_pick_logic")
    for field in required:
        if field not in report:
            errors.append(f"missing field: {field}")
    if report.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported verification preview schema_version")
    if report.get("report_hash") and build_verification_preview_hash(report) != report.get("report_hash"):
        errors.append("report_hash does not match report contents")
    if report.get("overall_passed") and report.get("manual_review_count"):
        errors.append("overall_passed is overstated")
    if int(report.get("unique_events") or 0) > int(report.get("row_count") or 0):
        errors.append("unique_events cannot exceed row_count")
    if report.get("frozen_pick_logic") is not True:
        errors.append("frozen_pick_logic must remain true")
    return {"passed": not errors, "checked_outputs": ["schema_version", "report_hash", "manual_review", "event_row_math", "frozen_pick_logic"], "warnings": [], "errors": errors, "details": {"rebuilt_report_hash": build_verification_preview_hash(report) if report.get("report_hash") else ""}}


def sanitize_verification_preview_report(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report.get("schema_version"),
        "workspace_id": report.get("workspace_id"),
        "report_id": report.get("report_id"),
        "report_hash": report.get("report_hash"),
        "status": report.get("status"),
        "overall_passed": report.get("overall_passed"),
        "row_count": report.get("row_count", 0),
        "unique_events": report.get("unique_events", 0),
        "duplicate_row_count": report.get("duplicate_row_count", 0),
        "score_payload_count": report.get("score_payload_count", 0),
        "clv_payload_count": report.get("clv_payload_count", 0),
        "ready_count": report.get("ready_count", 0),
        "manual_review_count": report.get("manual_review_count", 0),
        "frozen_pick_logic": report.get("frozen_pick_logic"),
        "verification_rows": [
            {
                "proof_id": row.get("proof_id"),
                "event_key": row.get("event_key"),
                "verification_decision": row.get("verification_decision"),
                "manual_review_required": row.get("manual_review_required"),
                "final_score_source": row.get("final_score_source"),
                "final_score": row.get("final_score"),
                "graded_at_utc": row.get("graded_at_utc"),
                "result_confidence": row.get("result_confidence"),
                "clv_source": row.get("clv_source"),
                "closing_decimal_odds": row.get("closing_decimal_odds"),
                "CLV_percent": row.get("CLV_percent"),
                "frozen_pick_logic": row.get("frozen_pick_logic"),
            }
            for row in report.get("verification_rows") or []
        ],
        "warning_count": len(report.get("warnings") or []),
        "error_count": len(report.get("errors") or []),
    }


def export_verification_preview_report_json(report: Mapping[str, Any], public_safe: bool = True) -> str:
    payload = sanitize_verification_preview_report(report) if public_safe else dict(report)
    return json.dumps(_json_safe(payload), sort_keys=True, indent=2)
