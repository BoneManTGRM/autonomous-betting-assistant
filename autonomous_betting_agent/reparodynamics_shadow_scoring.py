from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "reparodynamics_shadow_scoring_v1"
SHADOW_ONLY = "SHADOW ONLY"
KEEP_TESTING = "KEEP TESTING"
MANUAL_REVIEW = "MANUAL REVIEW"
REJECT = "REJECT"
DATA_BLOCKED = "DATA BLOCKED"
FORBIDDEN = "FORBIDDEN"


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


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(str(value).replace("%", ""))
    except Exception:
        return default


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"true", "1", "yes", "y", "on"}


def parse_json_object(text: str | None) -> dict[str, Any]:
    raw = _text(text)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {"parse_error": "invalid_json"}
    return dict(parsed) if isinstance(parsed, Mapping) else {"value": parsed}


def parse_csv_text(csv_text: str | None) -> list[dict[str, str]]:
    text = _text(csv_text)
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    return [{_text(key): _text(value) for key, value in row.items() if _text(key)} for row in reader]


def csv_from_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    row_list = [dict(row) for row in rows or []]
    fields: list[str] = []
    for row in row_list:
        for key in row:
            if str(key) not in fields:
                fields.append(str(key))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    if fields:
        writer.writeheader()
        for row in row_list:
            writer.writerow({field: row.get(field, "") for field in fields})
    return output.getvalue()


def _comparison(report: Mapping[str, Any]) -> dict[str, Any]:
    value = report.get("comparison_metrics")
    return dict(value) if isinstance(value, Mapping) else {}


def _summary(report: Mapping[str, Any]) -> dict[str, Any]:
    value = report.get("summary_counts")
    return dict(value) if isinstance(value, Mapping) else {}


def _candidate_rows(dynamic_report: Mapping[str, Any], odds_report: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for key in ("manual_review_queue", "repair_candidates", "shadow_tested_repairs", "rejected_dynamic_rules", "rejected_repairs"):
        value = dynamic_report.get(key)
        for item in value or []:
            if isinstance(item, Mapping):
                row = dict(item)
                row["candidate_source"] = key
                output.append(row)
    if not output:
        output.append({"title": "dynamic odds shadow layer", "candidate_source": "synthetic_summary", "decision": dynamic_report.get("decision", "keep_testing"), "decision_reason": dynamic_report.get("decision_reason", "no candidate rows supplied")})
    odds = dict(odds_report or {})
    if odds:
        output.append({"title": "odds math completion observation", "candidate_source": "odds_math", "decision": "keep_testing", "decision_reason": "odds math report available", "sample_size": odds.get("row_count", 0), "playable_count": odds.get("playable_count", 0), "blocked_count": odds.get("blocked_count", 0)})
    return output


def score_shadow_candidate(candidate: Mapping[str, Any], dynamic_report: Mapping[str, Any], odds_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    comparison = _comparison(dynamic_report)
    summary = _summary(dynamic_report)
    sample_size = int(_float(candidate.get("sample_size"), _float(dynamic_report.get("lr_evaluation_rows"), 0)))
    completed = int(_float(candidate.get("completed_rows_used"), _float(dynamic_report.get("completed_rows_used"), 0)))
    profit_delta = _float(comparison.get("profit_units_delta"), 0.0)
    roi_delta = _float(comparison.get("ROI_delta"), 0.0)
    losses_delta = _float(comparison.get("losses_delta"), 0.0)
    calibration_delta = _float(comparison.get("calibration_delta"), 0.0)
    clv_delta = _float(comparison.get("CLV_delta"), 0.0)
    overlap = int(_float(dynamic_report.get("train_test_overlap_count"), 0))
    unsafe_count = int(_float(dynamic_report.get("unsafe_feature_count"), 0))
    data_blockers = int(_float(summary.get("data_blockers_count"), len(dynamic_report.get("data_blockers") or [])))
    odds = dict(odds_report or {})
    playable_ratio = 0.0
    if odds.get("row_count"):
        playable_ratio = _float(odds.get("playable_count"), 0.0) / max(1.0, _float(odds.get("row_count"), 1.0))
    benefit = profit_delta * 12.0 + roi_delta * 100.0 + calibration_delta * 20.0 + clv_delta * 20.0 + playable_ratio * 5.0
    risk = max(0, losses_delta) * 10.0 + overlap * 50.0 + unsafe_count * 1.5 + data_blockers * 6.0
    evidence = min(20.0, completed / 5.0) + min(20.0, sample_size / 5.0)
    rye_score = round(benefit + evidence - risk, 6)
    blockers: list[str] = []
    if sample_size < 30:
        blockers.append("insufficient_shadow_sample")
    if completed < 30:
        blockers.append("insufficient_completed_rows")
    if overlap > 0:
        blockers.append("train_test_overlap_detected")
    if unsafe_count > 0:
        blockers.append("unsafe_features_blocked")
    if data_blockers > 0:
        blockers.append("data_blockers_present")
    if losses_delta > 0:
        blockers.append("losses_increased")
    if profit_delta < 0 or roi_delta < 0:
        blockers.append("profit_or_roi_degraded")
    decision = KEEP_TESTING
    if "train_test_overlap_detected" in blockers or "profit_or_roi_degraded" in blockers or "losses_increased" in blockers:
        decision = REJECT
    elif not blockers and rye_score > 20 and profit_delta > 0 and roi_delta > 0:
        decision = MANUAL_REVIEW
    elif sample_size == 0 and completed == 0:
        decision = DATA_BLOCKED
    return {
        "candidate_id": stable_hash("shadow_candidate", candidate, 16),
        "title": candidate.get("title") or candidate.get("candidate_type") or "shadow candidate",
        "candidate_source": candidate.get("candidate_source", "unknown"),
        "input_decision": candidate.get("decision", dynamic_report.get("decision", "")),
        "sample_size": sample_size,
        "completed_rows_used": completed,
        "profit_units_delta": profit_delta,
        "ROI_delta": roi_delta,
        "losses_delta": losses_delta,
        "calibration_delta": calibration_delta,
        "CLV_delta": clv_delta,
        "playable_ratio": round(playable_ratio, 6),
        "benefit_score": round(benefit, 6),
        "risk_score": round(risk, 6),
        "evidence_score": round(evidence, 6),
        "RYE_score": rye_score,
        "decision": decision,
        "decision_reason": "; ".join(blockers) if blockers else "shadow_candidate_passed_review_thresholds",
        "blockers": blockers,
        "live_mutation": FORBIDDEN,
        "model_training": FORBIDDEN,
        "stored_data_mutation": FORBIDDEN,
        "shadow_only": True,
    }


def build_reparodynamics_shadow_scoring_report(
    workspace_id: str | None = None,
    dynamic_report: Mapping[str, Any] | None = None,
    odds_report: Mapping[str, Any] | None = None,
    operator_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    dynamic = dict(dynamic_report or {})
    odds = dict(odds_report or {})
    candidates = _candidate_rows(dynamic, odds) + [dict(row) for row in operator_rows or []]
    scored = [score_shadow_candidate(candidate, dynamic, odds) for candidate in candidates]
    manual = len([row for row in scored if row["decision"] == MANUAL_REVIEW])
    rejected = len([row for row in scored if row["decision"] == REJECT])
    blocked = len([row for row in scored if row["decision"] == DATA_BLOCKED])
    keep = len([row for row in scored if row["decision"] == KEEP_TESTING])
    status = MANUAL_REVIEW if manual else REJECT if rejected else DATA_BLOCKED if blocked and not keep else KEEP_TESTING
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "shadow_scoring_id": "",
        "status": status,
        "mode": SHADOW_ONLY,
        "candidate_count": len(scored),
        "manual_review_count": manual,
        "rejected_count": rejected,
        "data_blocked_count": blocked,
        "keep_testing_count": keep,
        "average_RYE_score": round(sum(row["RYE_score"] for row in scored) / len(scored), 6) if scored else 0.0,
        "scored_candidates": scored,
        "safety_gates": {
            "live_mutation": FORBIDDEN,
            "model_training": FORBIDDEN,
            "stored_data_mutation": FORBIDDEN,
            "automatic_live_promotion": FORBIDDEN,
            "repairs_applied_live": 0,
        },
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "warnings": ["manual review candidates exist"] if manual else [],
        "errors": [] if dynamic else ["no dynamic report supplied"],
    }
    report["shadow_scoring_id"] = stable_hash("reparodynamics_shadow", {"workspace_id": workspace_id, "candidates": scored}, 24)
    report["shadow_scoring_hash"] = stable_hash("reparodynamics_shadow_hash", {k: v for k, v in report.items() if k != "generated_at_utc"}, 32)
    return report


def build_reparodynamics_shadow_scoring_report_from_text(
    workspace_id: str | None = None,
    dynamic_report_json_text: str | None = None,
    odds_report_json_text: str | None = None,
    operator_csv_text: str | None = None,
) -> dict[str, Any]:
    return build_reparodynamics_shadow_scoring_report(
        workspace_id,
        parse_json_object(dynamic_report_json_text),
        parse_json_object(odds_report_json_text),
        parse_csv_text(operator_csv_text),
    )


def export_shadow_scoring_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_scored_candidates_csv(report: Mapping[str, Any]) -> str:
    rows = []
    for row in report.get("scored_candidates") or []:
        if isinstance(row, Mapping):
            rows.append({key: value for key, value in row.items() if key not in {"blockers"}})
    return csv_from_rows(rows)
