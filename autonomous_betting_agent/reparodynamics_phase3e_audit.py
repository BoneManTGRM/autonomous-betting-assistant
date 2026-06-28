from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from autonomous_betting_agent.reparodynamics_audit import REPARODYNAMICS_AUDIT_LATEST_PATH, REPARODYNAMICS_AUDIT_LOG_PATH
from autonomous_betting_agent.reparodynamics_repair_memory import utc_now

FORBIDDEN = "FORBIDDEN"


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def build_phase3e_dynamic_odds_audit_event(report: Mapping[str, Any], source: str = "Phase 3E Dynamic Odds Shadow") -> dict[str, Any]:
    safe = dict(report or {})
    counts = dict(safe.get("summary_counts", {}) or {})
    comparison = dict(safe.get("comparison_metrics", {}) or {})
    now = utc_now()
    run_id = str(safe.get("dynamic_shadow_run_id") or safe.get("memory_run_id") or now)
    return {
        "event_id": f"phase3e_dynamic_odds_shadow_run|{run_id}",
        "event_type": "phase3e_dynamic_odds_shadow_run",
        "phase": safe.get("phase", "Phase 3E Dynamic Odds Predictor Shadow"),
        "source": source,
        "timestamp": now,
        "created_at_utc": now,
        "workspace_id": safe.get("workspace_id", "test_01"),
        "dynamic_shadow_run_id": run_id,
        "memory_run_id": safe.get("memory_run_id", run_id),
        "rows_scanned": _to_int(safe.get("rows_scanned")),
        "completed_rows_used": _to_int(safe.get("completed_rows_used")),
        "lr_training_rows": _to_int(safe.get("lr_training_rows")),
        "lr_evaluation_rows": _to_int(safe.get("lr_evaluation_rows")),
        "evaluation_mode": safe.get("evaluation_mode", ""),
        "leakage_guard_enabled": bool(safe.get("leakage_guard_enabled", True)),
        "train_test_overlap_count": _to_int(safe.get("train_test_overlap_count")),
        "walk_forward_windows_evaluated": _to_int(safe.get("walk_forward_windows_evaluated")),
        "dynamic_rows_evaluated_count": _to_int(counts.get("dynamic_rows_evaluated_count")),
        "dynamic_green_count": _to_int(counts.get("dynamic_green_count")),
        "dynamic_yellow_count": _to_int(counts.get("dynamic_yellow_count")),
        "dynamic_red_count": _to_int(counts.get("dynamic_red_count")),
        "manual_review_eligible_count": _to_int(counts.get("manual_review_eligible_count")),
        "decision": comparison.get("decision", safe.get("decision", "")),
        "decision_reason": comparison.get("decision_reason", safe.get("decision_reason", "")),
        "dynamic_odds_live_activation": "OFF",
        "dynamic_odds_applied_live": 0,
        "dynamic_odds_applied_live_count": 0,
        "live_mutation": FORBIDDEN,
        "model_training": FORBIDDEN,
        "stored_data_mutation": FORBIDDEN,
        "repair_activation": "OFF",
        "repairs_applied_live": 0,
        "live_repairs_applied_count": 0,
        "automatic_live_promotion": FORBIDDEN,
    }


def write_phase3e_dynamic_odds_audit_event(
    report: Mapping[str, Any],
    *,
    source: str = "Phase 3E Dynamic Odds Shadow",
    log_path: Path = REPARODYNAMICS_AUDIT_LOG_PATH,
    latest_path: Path = REPARODYNAMICS_AUDIT_LATEST_PATH,
) -> dict[str, Any]:
    payload = build_phase3e_dynamic_odds_audit_event(report, source=source)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    latest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload
