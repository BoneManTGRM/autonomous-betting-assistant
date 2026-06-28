from __future__ import annotations

import json
import statistics
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from autonomous_betting_agent.pick_hold_store import normalize_workspace_id

SCHEMA_VERSION = "reparodynamics_phase_3d_memory_v1"
PHASE_3D = "Phase 3D Repair Memory"
FORBIDDEN = "FORBIDDEN"
REPAIR_MEMORY_DIR = Path("data/adaptive_repair/repair_memory")

DEFAULT_CONFIG: dict[str, Any] = {
    "minimum_runs_for_promising": 2,
    "minimum_runs_for_phase4_candidate": 3,
    "minimum_total_completed_rows": 75,
    "minimum_average_ROI_delta": 0.03,
    "minimum_total_profit_units_delta": 2.0,
    "maximum_average_losses_delta": 0,
    "maximum_overfit_risk_allowed": "medium",
    "minimum_CLV_sample_total": 10,
    "severe_CLV_degradation": -0.02,
}

MEMORY_STATUSES = {
    "new",
    "watchlist",
    "keep_testing",
    "promising",
    "rejected",
    "manual_approved_for_future",
    "phase4_lockbox_candidate",
    "data_blocked",
}
MANUAL_DECISIONS = {"keep_testing", "reject", "watchlist", "manual_approved_for_future", "clear_manual_decision"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    merged = dict(DEFAULT_CONFIG)
    if config:
        merged.update(dict(config))
    return merged


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _key_text(value: Any) -> str:
    text = _text(value).lower().replace("|", " ").replace("/", " ")
    return "_".join("".join(ch if ch.isalnum() else "_" for ch in text).split("_"))


def _float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    text = _text(value).replace("%", "").replace(",", "")
    if not text:
        return default
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def _round(value: float | None) -> float | None:
    return round(float(value), 6) if value is not None else None


def _mean(values: Sequence[float]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return _round(sum(clean) / len(clean)) if clean else None


def _median(values: Sequence[float]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return _round(statistics.median(clean)) if clean else None


def _memory_path(workspace_id: Any = "test_01") -> Path:
    workspace = normalize_workspace_id(workspace_id)
    return REPAIR_MEMORY_DIR / f"reparodynamics_repair_memory_{workspace}.json"


def _new_memory(workspace_id: Any = "test_01") -> dict[str, Any]:
    now = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace_id": normalize_workspace_id(workspace_id),
        "created_at_utc": now,
        "updated_at_utc": now,
        "phase": PHASE_3D,
        "repairs_applied_live": 0,
        "live_repairs_applied_count": 0,
        "live_mutation": FORBIDDEN,
        "model_training": FORBIDDEN,
        "stored_data_mutation": FORBIDDEN,
        "repair_activation": "OFF",
        "automatic_live_promotion": "FORBIDDEN",
        "items": {},
        "events": [],
    }


def _safety(memory: dict[str, Any]) -> None:
    memory["phase"] = PHASE_3D
    memory["repairs_applied_live"] = 0
    memory["live_repairs_applied_count"] = 0
    memory["live_mutation"] = FORBIDDEN
    memory["model_training"] = FORBIDDEN
    memory["stored_data_mutation"] = FORBIDDEN
    memory["repair_activation"] = "OFF"
    memory["automatic_live_promotion"] = "FORBIDDEN"


def stable_repair_key(finding: Mapping[str, Any]) -> str:
    candidate = _key_text(finding.get("candidate_type") or finding.get("finding_type") or finding.get("title") or "unknown")
    sport = _key_text(finding.get("affected_sport") or "all")
    market = _key_text(finding.get("affected_market_type") or "all")
    title = _key_text(finding.get("title") or finding.get("decision_reason") or "repair")
    blockers = finding.get("data_blockers") or finding.get("unavailable_options") or []
    if isinstance(blockers, str):
        blockers_key = _key_text(blockers)
    else:
        blockers_key = "_".join(_key_text(item) for item in blockers if _text(item))
    parts = [sport or "all", market or "all", candidate or "unknown", title or "repair"]
    if blockers_key:
        parts.append(blockers_key)
    return "|".join(parts)[:180]


def normalize_phase3c_report(report: Mapping[str, Any]) -> dict[str, Any]:
    safe = deepcopy(dict(report or {}))
    safe.setdefault("phase", "Phase 3C Shadow Backtest")
    safe.setdefault("generated_at_utc", utc_now())
    safe.setdefault("summary_counts", {})
    for name in ("data_blockers", "watchlists", "repair_candidates", "shadow_tested_repairs", "rejected_repairs", "manual_review_queue"):
        value = safe.get(name, [])
        safe[name] = [dict(item) for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []
    return safe


def _memory_row(finding: Mapping[str, Any], section: str, source: str, observed_at: str) -> dict[str, Any]:
    comparison = dict(finding.get("comparison_metrics", {}) or {})
    baseline = dict(finding.get("baseline_metrics", {}) or {})
    row = {
        "repair_key": stable_repair_key(finding),
        "source": source,
        "section": section,
        "observed_at_utc": observed_at,
        "title": _text(finding.get("title") or section),
        "candidate_type": _text(finding.get("candidate_type") or finding.get("finding_type") or section),
        "finding_type": _text(finding.get("finding_type") or section),
        "affected_sport": _text(finding.get("affected_sport") or ""),
        "affected_market_type": _text(finding.get("affected_market_type") or ""),
        "sample_size": int(finding.get("sample_size") or baseline.get("sample_size") or 0),
        "completed_rows_used": int(finding.get("completed_rows_used") or baseline.get("completed_rows_used") or 0),
        "decision": _text(finding.get("decision") or comparison.get("decision") or finding.get("finding_type") or section),
        "decision_reason": _text(finding.get("decision_reason") or comparison.get("decision_reason") or ""),
        "eligible_for_manual_review": bool(finding.get("eligible_for_manual_review", False)),
        "data_blockers": list(finding.get("data_blockers", []) or []),
        "unavailable_options": list(finding.get("unavailable_options", []) or []),
        "has_shadow_backtest": bool(finding.get("has_shadow_backtest", False)),
        "ROI_delta": _float(comparison.get("ROI_delta")),
        "profit_units_delta": _float(comparison.get("profit_units_delta")),
        "losses_delta": _float(comparison.get("losses_delta")),
        "avoided_losses": _float(comparison.get("avoided_losses"), 0.0) or 0.0,
        "CLV_delta": _float(comparison.get("CLV_delta")),
        "CLV_sample_size": int(comparison.get("CLV_sample_size") or finding.get("clv_sample_size") or 0),
        "overfit_risk": _text(comparison.get("overfit_risk") or finding.get("overfit_risk") or ""),
        "confidence_level": _text(comparison.get("confidence_level") or finding.get("confidence_level") or ""),
        "live_mutation": FORBIDDEN,
        "model_training": FORBIDDEN,
        "stored_data_mutation": FORBIDDEN,
        "repairs_applied_live": 0,
    }
    return row


def extract_repair_memory_rows(phase3c_report: Mapping[str, Any], source: str | None = None) -> list[dict[str, Any]]:
    report = normalize_phase3c_report(phase3c_report)
    observed_at = _text(report.get("generated_at_utc")) or utc_now()
    label = source or "Phase 3C Shadow Backtest"
    rows: list[dict[str, Any]] = []
    sections = {
        "data_blockers": report["data_blockers"],
        "watchlists": report["watchlists"],
        "repair_candidates": report["repair_candidates"],
        "shadow_tested_repairs": report["shadow_tested_repairs"],
        "rejected_repairs": report["rejected_repairs"],
        "manual_review_queue": report["manual_review_queue"],
    }
    for section, findings in sections.items():
        for finding in findings:
            rows.append(_memory_row(finding, section, label, observed_at))
    return rows


def _history_values(history: Sequence[Mapping[str, Any]], field: str) -> list[float]:
    return [value for value in (_float(item.get(field)) for item in history) if value is not None]


def _risk_rank(value: str) -> int:
    return {"": 0, "low": 1, "medium": 2, "high": 3}.get(str(value).lower(), 0)


def _safety_intact(summary: Mapping[str, Any]) -> bool:
    return (
        summary.get("live_mutation", FORBIDDEN) == FORBIDDEN
        and summary.get("model_training", FORBIDDEN) == FORBIDDEN
        and summary.get("stored_data_mutation", FORBIDDEN) == FORBIDDEN
        and int(summary.get("repairs_applied_live", 0) or 0) == 0
    )


def classify_memory_status(summary: Mapping[str, Any], config: Mapping[str, Any] | None = None) -> str:
    cfg = _config(config)
    manual = _text(summary.get("manual_status"))
    if manual == "rejected":
        return "rejected"
    if manual == "manual_approved_for_future":
        eligible_phase4 = (
            int(summary.get("times_seen", 0) or 0) >= int(cfg["minimum_runs_for_phase4_candidate"])
            and int(summary.get("total_completed_rows_used", 0) or 0) >= int(cfg["minimum_total_completed_rows"])
            and (_float(summary.get("avg_ROI_delta"), 0.0) or 0.0) >= float(cfg["minimum_average_ROI_delta"])
            and (_float(summary.get("total_profit_units_delta"), 0.0) or 0.0) >= float(cfg["minimum_total_profit_units_delta"])
            and (_float(summary.get("avg_losses_delta"), 0.0) or 0.0) <= float(cfg["maximum_average_losses_delta"])
            and _risk_rank(_text(summary.get("overfit_risk_latest"))) <= _risk_rank(str(cfg["maximum_overfit_risk_allowed"]))
            and _safety_intact(summary)
        )
        clv_delta = summary.get("avg_CLV_delta")
        if clv_delta is not None and (_float(clv_delta, 0.0) or 0.0) < float(cfg["severe_CLV_degradation"]):
            eligible_phase4 = False
        return "phase4_lockbox_candidate" if eligible_phase4 else "manual_approved_for_future"
    if int(summary.get("times_data_blocked", 0) or 0) and not int(summary.get("times_shadow_tested", 0) or 0):
        return "data_blocked"
    if int(summary.get("times_rejected", 0) or 0) >= max(2, int(summary.get("times_seen", 0) or 0)):
        return "rejected"
    completed = int(summary.get("total_completed_rows_used", 0) or 0)
    times_seen = int(summary.get("times_seen", 0) or 0)
    if completed <= 0 or times_seen <= 1:
        return "new" if times_seen <= 1 else "watchlist"
    if completed < int(cfg["minimum_total_completed_rows"]):
        return "keep_testing" if times_seen >= 2 else "watchlist"
    avg_roi = _float(summary.get("avg_ROI_delta"), 0.0) or 0.0
    total_profit = _float(summary.get("total_profit_units_delta"), 0.0) or 0.0
    avg_losses = _float(summary.get("avg_losses_delta"), 0.0) or 0.0
    if avg_roi < 0 or total_profit < 0 or avg_losses > 0:
        return "rejected"
    if times_seen >= int(cfg["minimum_runs_for_promising"]) and avg_roi >= float(cfg["minimum_average_ROI_delta"]) and total_profit > 0 and avg_losses <= 0:
        return "promising"
    return "keep_testing"


def summarize_repair_memory(memory_rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in memory_rows or []:
        key = _text(row.get("repair_key")) or stable_repair_key(row)
        grouped.setdefault(key, []).append(dict(row, repair_key=key))
    summaries: dict[str, dict[str, Any]] = {}
    for key, history in grouped.items():
        first = history[0]
        latest = history[-1]
        roi_values = _history_values(history, "ROI_delta")
        profit_values = _history_values(history, "profit_units_delta")
        losses_values = _history_values(history, "losses_delta")
        clv_values = _history_values(history, "CLV_delta")
        summary: dict[str, Any] = {
            "repair_key": key,
            "title": latest.get("title") or first.get("title", ""),
            "candidate_type": latest.get("candidate_type") or first.get("candidate_type", ""),
            "affected_sport": latest.get("affected_sport") or first.get("affected_sport", ""),
            "affected_market_type": latest.get("affected_market_type") or first.get("affected_market_type", ""),
            "first_seen_utc": first.get("observed_at_utc", ""),
            "last_seen_utc": latest.get("observed_at_utc", ""),
            "times_seen": len(history),
            "times_shadow_tested": sum(1 for item in history if item.get("has_shadow_backtest")),
            "times_rejected": sum(1 for item in history if item.get("decision") == "rejected_repair"),
            "times_manual_review_eligible": sum(1 for item in history if item.get("eligible_for_manual_review")),
            "times_data_blocked": sum(1 for item in history if item.get("decision") == "data_blocked" or item.get("finding_type") == "data_blocker"),
            "times_watchlist": sum(1 for item in history if item.get("finding_type") == "watchlist"),
            "total_sample_size": sum(int(item.get("sample_size", 0) or 0) for item in history),
            "total_completed_rows_used": sum(int(item.get("completed_rows_used", 0) or 0) for item in history),
            "avg_ROI_delta": _mean(roi_values),
            "median_ROI_delta": _median(roi_values),
            "best_ROI_delta": max(roi_values) if roi_values else None,
            "worst_ROI_delta": min(roi_values) if roi_values else None,
            "avg_profit_units_delta": _mean(profit_values),
            "total_profit_units_delta": _round(sum(profit_values)) if profit_values else 0,
            "avg_losses_delta": _mean(losses_values),
            "total_avoided_losses": _round(sum(_float(item.get("avoided_losses"), 0.0) or 0.0 for item in history)) or 0,
            "avg_CLV_delta": _mean(clv_values),
            "CLV_sample_size_total": sum(int(item.get("CLV_sample_size", 0) or 0) for item in history),
            "overfit_risk_latest": latest.get("overfit_risk", ""),
            "confidence_level_latest": latest.get("confidence_level", ""),
            "latest_decision": latest.get("decision", ""),
            "latest_decision_reason": latest.get("decision_reason", ""),
            "manual_status": "",
            "manual_note": "",
            "reviewer": "",
            "manual_updated_at_utc": "",
            "live_mutation": FORBIDDEN,
            "model_training": FORBIDDEN,
            "stored_data_mutation": FORBIDDEN,
            "repairs_applied_live": 0,
            "eligible_for_phase4_lockbox": False,
            "history": history,
        }
        summary["memory_status"] = classify_memory_status(summary, config)
        summary["eligible_for_phase4_lockbox"] = summary["memory_status"] == "phase4_lockbox_candidate"
        summaries[key] = summary
    return summaries


def update_repair_memory(existing_memory: Mapping[str, Any] | None, phase3c_report: Mapping[str, Any], source: str | None = None, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    memory = deepcopy(dict(existing_memory or _new_memory()))
    if not memory.get("items"):
        memory.setdefault("items", {})
    memory.setdefault("events", [])
    memory.setdefault("created_at_utc", utc_now())
    _safety(memory)
    rows = extract_repair_memory_rows(phase3c_report, source=source)
    for row in rows:
        key = row["repair_key"]
        current = dict(memory["items"].get(key, {}))
        old_history = list(current.get("history", []) or [])
        old_manual = {
            "manual_status": current.get("manual_status", ""),
            "manual_note": current.get("manual_note", ""),
            "reviewer": current.get("reviewer", ""),
            "manual_updated_at_utc": current.get("manual_updated_at_utc", ""),
        }
        summary = summarize_repair_memory([*old_history, row], config).get(key, {})
        summary.update({k: v for k, v in old_manual.items() if v})
        summary["memory_status"] = classify_memory_status(summary, config)
        summary["eligible_for_phase4_lockbox"] = summary["memory_status"] == "phase4_lockbox_candidate"
        memory["items"][key] = summary
    memory["updated_at_utc"] = utc_now()
    memory["events"].append(
        {
            "event_id": sha256(f"phase3c_saved_to_memory|{memory['updated_at_utc']}|{len(rows)}".encode("utf-8")).hexdigest()[:16],
            "event_type": "phase3c_saved_to_memory",
            "workspace_id": memory.get("workspace_id", "test_01"),
            "rows_added": len(rows),
            "live_mutation": FORBIDDEN,
            "model_training": FORBIDDEN,
            "stored_data_mutation": FORBIDDEN,
            "repairs_applied_live": 0,
            "created_at_utc": memory["updated_at_utc"],
        }
    )
    return memory


def manual_review_decision(memory: Mapping[str, Any], repair_key: str, decision: str, reviewer: str | None = None, note: str | None = None, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if decision not in MANUAL_DECISIONS:
        raise ValueError(f"Unsupported manual review decision: {decision}")
    updated = deepcopy(dict(memory or _new_memory()))
    _safety(updated)
    items = updated.setdefault("items", {})
    key = _text(repair_key)
    if key not in items:
        raise KeyError(f"Repair key not found: {key}")
    item = dict(items[key])
    previous_status = item.get("memory_status", "")
    now = utc_now()
    if decision == "clear_manual_decision":
        item["manual_status"] = ""
        item["manual_note"] = ""
        item["reviewer"] = ""
        item["manual_updated_at_utc"] = now
    else:
        item["manual_status"] = "rejected" if decision == "reject" else decision
        item["manual_note"] = _text(note)
        item["reviewer"] = _text(reviewer or "manual")
        item["manual_updated_at_utc"] = now
    item["memory_status"] = classify_memory_status(item, config)
    item["eligible_for_phase4_lockbox"] = item["memory_status"] == "phase4_lockbox_candidate"
    items[key] = item
    event = {
        "event_id": sha256(f"manual_review_decision|{key}|{now}".encode("utf-8")).hexdigest()[:16],
        "event_type": "manual_review_decision",
        "workspace_id": updated.get("workspace_id", "test_01"),
        "repair_key": key,
        "decision": decision,
        "note": _text(note),
        "reviewer": _text(reviewer or "manual"),
        "previous_status": previous_status,
        "new_status": item["memory_status"],
        "live_mutation": FORBIDDEN,
        "model_training": FORBIDDEN,
        "stored_data_mutation": FORBIDDEN,
        "repairs_applied_live": 0,
        "created_at_utc": now,
    }
    updated.setdefault("events", []).append(event)
    updated["updated_at_utc"] = now
    return updated


def load_repair_memory(workspace_id: Any = "test_01") -> dict[str, Any]:
    path = _memory_path(workspace_id)
    if not path.exists():
        return _new_memory(workspace_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _new_memory(workspace_id)
        data.setdefault("workspace_id", normalize_workspace_id(workspace_id))
        data.setdefault("items", {})
        data.setdefault("events", [])
        _safety(data)
        return data
    except Exception:
        return _new_memory(workspace_id)


def save_repair_memory(memory: Mapping[str, Any], workspace_id: Any = "test_01") -> dict[str, Any]:
    payload = deepcopy(dict(memory or _new_memory(workspace_id)))
    payload["workspace_id"] = normalize_workspace_id(workspace_id or payload.get("workspace_id", "test_01"))
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload.setdefault("created_at_utc", utc_now())
    payload["updated_at_utc"] = utc_now()
    _safety(payload)
    path = _memory_path(payload["workspace_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)
    return payload


def append_repair_memory_event(event: Mapping[str, Any], workspace_id: Any = "test_01") -> dict[str, Any]:
    memory = load_repair_memory(workspace_id)
    payload = dict(event or {})
    payload.setdefault("event_id", sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16])
    payload.setdefault("event_type", "repair_memory_summary")
    payload.setdefault("workspace_id", memory.get("workspace_id", normalize_workspace_id(workspace_id)))
    payload.setdefault("created_at_utc", utc_now())
    payload["live_mutation"] = FORBIDDEN
    payload["model_training"] = FORBIDDEN
    payload["stored_data_mutation"] = FORBIDDEN
    payload["repairs_applied_live"] = 0
    memory.setdefault("events", []).append(payload)
    return save_repair_memory(memory, workspace_id)


def repair_memory_to_frames(memory: Mapping[str, Any]) -> dict[str, pd.DataFrame]:
    items = list((memory or {}).get("items", {}).values())
    summary_rows = []
    history_rows = []
    for item in items:
        clean = dict(item)
        history = list(clean.pop("history", []) or [])
        summary_rows.append(clean)
        for entry in history:
            history_rows.append(dict(entry, repair_key=item.get("repair_key", "")))
    return {
        "summary": pd.DataFrame(summary_rows),
        "history": pd.DataFrame(history_rows),
        "events": pd.DataFrame(list((memory or {}).get("events", []) or [])),
    }
