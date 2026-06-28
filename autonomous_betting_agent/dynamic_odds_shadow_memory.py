from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.dynamic_odds_predictor import build_lr_training_rows, learn_lr_multipliers
from autonomous_betting_agent.pick_hold_store import normalize_workspace_id

SCHEMA_VERSION = "dynamic_odds_shadow_model_v1"
SHADOW_ONLY = "SHADOW ONLY"
MODEL_DIR = Path("data/adaptive_repair/dynamic_odds_shadow_model")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _model_path(workspace_id: Any = "test_01") -> Path:
    return MODEL_DIR / f"dynamic_odds_shadow_model_{normalize_workspace_id(workspace_id)}.json"


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float):
        return round(value, 10)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    return str(value)


def safety_summary() -> dict[str, Any]:
    return {
        "dynamic_odds_predictor": SHADOW_ONLY,
        "dynamic_odds_live_activation": "OFF",
        "dynamic_odds_applied_live": 0,
        "dynamic_odds_applied_live_count": 0,
        "live_mutation": "FORBIDDEN",
        "model_training": "FORBIDDEN",
        "stored_data_mutation": "FORBIDDEN",
        "repair_activation": "OFF",
        "automatic_live_promotion": "FORBIDDEN",
    }


def train_dynamic_odds_shadow_model(rows: Sequence[Mapping[str, Any]], workspace_id: Any = "test_01", config: Mapping[str, Any] | None = None, source: str | None = None) -> dict[str, Any]:
    workspace = normalize_workspace_id(workspace_id)
    safe_rows = [deepcopy(dict(row)) for row in rows or [] if isinstance(row, Mapping)]
    training_rows = build_lr_training_rows(safe_rows, config)
    lr_model = learn_lr_multipliers(safe_rows, config)
    now = utc_now()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "workspace_id": workspace,
        "created_at_utc": now,
        "last_trained_at_utc": now,
        "updated_at_utc": now,
        "source": source or "graded_upload_shadow_trainer",
        "completed_rows_seen": len(training_rows),
        "training_rows_used": int(lr_model.get("training_rows") or 0),
        "feature_count": int(lr_model.get("feature_count") or 0),
        "baseline_success_rate": lr_model.get("baseline_success_rate"),
        "leakage_guard": "ON",
        "lr_model": deepcopy(dict(lr_model or {})),
    }
    payload.update(safety_summary())
    return payload


def save_dynamic_odds_shadow_model(model: Mapping[str, Any], workspace_id: Any = "test_01") -> dict[str, Any]:
    workspace = normalize_workspace_id(workspace_id or model.get("workspace_id", "test_01"))
    payload = deepcopy(dict(model or {}))
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload["workspace_id"] = workspace
    payload.setdefault("created_at_utc", utc_now())
    payload["updated_at_utc"] = utc_now()
    payload.setdefault("last_trained_at_utc", payload["updated_at_utc"])
    payload.update(safety_summary())
    path = _model_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return payload


def train_and_save_dynamic_odds_shadow_model(rows: Sequence[Mapping[str, Any]], workspace_id: Any = "test_01", config: Mapping[str, Any] | None = None, source: str | None = None) -> dict[str, Any]:
    return save_dynamic_odds_shadow_model(train_dynamic_odds_shadow_model(rows, workspace_id, config, source), workspace_id)


def load_dynamic_odds_shadow_model(workspace_id: Any = "test_01") -> dict[str, Any]:
    path = _model_path(workspace_id)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    payload.update(safety_summary())
    return payload


def delete_dynamic_odds_shadow_model(workspace_id: Any = "test_01") -> None:
    try:
        _model_path(workspace_id).unlink(missing_ok=True)
    except Exception:
        pass


def runtime_lr_model(model_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(model_payload or {})
    lr_model = deepcopy(dict(payload.get("lr_model") or {}))
    if not lr_model and "lr_by_feature" in payload:
        lr_model = deepcopy(payload)
    lr_model["workspace_id"] = payload.get("workspace_id", lr_model.get("workspace_id", ""))
    lr_model["model_source"] = "saved_shadow_model" if payload else "no_model"
    lr_model["last_trained_at_utc"] = payload.get("last_trained_at_utc", "")
    lr_model["dynamic_odds_applied_live_count"] = 0
    return lr_model


def infer_workspace_id(rows: Sequence[Mapping[str, Any]] | None, default: str = "test_01") -> str:
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        for key in ("workspace_id", "test_window_id", "active_test_ledger", "ledger_workspace_id"):
            value = str(row.get(key, "") or "").strip()
            if value:
                return normalize_workspace_id(value)
    return normalize_workspace_id(default)


def shadow_model_status(model_payload: Mapping[str, Any] | None, source: str = "saved_model") -> dict[str, Any]:
    payload = dict(model_payload or {})
    lr_model = dict(payload.get("lr_model") or payload)
    return {
        "model_loaded": int(lr_model.get("feature_count") or 0) > 0,
        "model_source": source if payload else "no_model",
        "workspace_id": payload.get("workspace_id", ""),
        "last_trained_at_utc": payload.get("last_trained_at_utc", ""),
        "training_rows_used": int(payload.get("training_rows_used") or lr_model.get("training_rows") or 0),
        "feature_count": int(payload.get("feature_count") or lr_model.get("feature_count") or 0),
        "baseline_success_rate": payload.get("baseline_success_rate") or lr_model.get("baseline_success_rate"),
        "leakage_guard": payload.get("leakage_guard", "ON"),
        "dynamic_odds_live_activation": "OFF",
        "dynamic_odds_applied_live_count": 0,
    }
