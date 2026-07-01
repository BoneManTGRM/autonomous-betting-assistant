from __future__ import annotations

import hashlib
import json
from typing import Any

_PATCHED = False

HANDOFF_KEYS = (
    "odds_lock_pro_locked_rows",
    "public_proof_dashboard_refresh_rows",
    "pro_predictor_high_confidence_rows",
    "pro_predictor_latest_rows",
    "what_are_the_odds_latest_rows",
    "ara_latest_predictions",
)

ROW_HINTS = {"event", "event_name", "game", "matchup", "selection", "pick", "prediction", "sport", "market_type", "confidence"}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _rowish(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    sample = [item for item in value[:8] if isinstance(item, dict)]
    if not sample:
        return False
    keys = {str(key).lower() for item in sample for key in item.keys()}
    return bool(keys & ROW_HINTS)


def _current_rows_from_session() -> tuple[str, list[dict[str, Any]]]:
    try:
        import streamlit as st
    except Exception:
        return "", []
    for key in HANDOFF_KEYS:
        rows = st.session_state.get(key) or []
        if _rowish(rows):
            return f"session:{key}", [dict(row) for row in rows if isinstance(row, dict)]
    for key, value in list(st.session_state.items()):
        text_key = str(key)
        if text_key.startswith("report_studio_") or text_key.startswith("proof_center_"):
            continue
        if _rowish(value):
            return f"session:{text_key}", [dict(row) for row in value if isinstance(row, dict)]
    try:
        from autonomous_betting_agent.pick_hold_store import load_first_available
        workspace_id = _safe_text(st.session_state.get("aba_test_window_id")) or "test_01"
        key, rows = load_first_available(HANDOFF_KEYS, workspace_id)
        if _rowish(rows):
            return f"saved:{key}", [dict(row) for row in rows if isinstance(row, dict)]
    except Exception:
        pass
    return "", []


def _has_fresh_handoff_rows() -> bool:
    source, rows = _current_rows_from_session()
    if not rows:
        return False
    try:
        import streamlit as st
        st.session_state["report_studio_preferred_source"] = source
        st.session_state["proof_center_preferred_source"] = source
    except Exception:
        pass
    return True


def _batch_id(source: str, rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(rows[:25], sort_keys=True, default=str)
    digest = hashlib.sha256((source + "|" + payload).encode("utf-8")).hexdigest()[:12]
    label = source.replace(":", "_").replace("/", "_") or "current"
    return f"{label}_{len(rows)}_{digest}"


def _stable_row_hash(row: dict[str, Any], index: int) -> str:
    payload = json.dumps(row, sort_keys=True, default=str)
    return hashlib.sha256(f"{index}|{payload}".encode("utf-8")).hexdigest()[:16]


def _with_batch_identity(rows: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    if not rows:
        return []
    batch = _batch_id(source, rows)
    out: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        item = dict(row)
        original_proof_id = _safe_text(item.get("proof_id"))
        item.setdefault("proof_batch_id", batch)
        item.setdefault("proof_source", source)
        item.setdefault("proof_source_type", "current_prediction_run")
        item.setdefault("source_file", source)
        if original_proof_id:
            item.setdefault("source_proof_id", original_proof_id)
            item["proof_id"] = f"{batch}:{original_proof_id}"
        else:
            item["proof_id"] = f"{batch}:{index}:{_stable_row_hash(item, index)}"
        out.append(item)
    return out


def _merge_current_first(current: list[dict[str, Any]], stored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in [*current, *stored]:
        if not isinstance(row, dict):
            continue
        proof_id = _safe_text(row.get("proof_id"))
        batch = _safe_text(row.get("proof_batch_id"))
        event = _safe_text(row.get("event") or row.get("event_name") or row.get("matchup")).lower()
        pick = _safe_text(row.get("prediction") or row.get("pick") or row.get("selection")).lower()
        market = _safe_text(row.get("market_type") or row.get("market")).lower()
        line = _safe_text(row.get("line_point") or row.get("line") or row.get("handicap") or row.get("total")).lower()
        start = _safe_text(row.get("event_start_utc") or row.get("event_start_time") or row.get("commence_time")).lower()
        key = proof_id or "|".join([batch, event, pick, market, line, start])
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(dict(row))
    return out


def _patch_local_storage() -> None:
    try:
        from autonomous_betting_agent.storage import LocalStorage
    except Exception:
        return
    original_load_rows = getattr(LocalStorage, "load_rows", None)
    if not callable(original_load_rows) or getattr(original_load_rows, "_ABA_CURRENT_ROWS_PATCH", False):
        return

    def load_rows_with_current_predictions(self: Any, *args: Any, **kwargs: Any):
        stored = original_load_rows(self, *args, **kwargs) or []
        source, rows = _current_rows_from_session()
        if not rows:
            return stored
        current = _with_batch_identity(rows, source)
        return _merge_current_first(current, [dict(row) for row in stored if isinstance(row, dict)])

    load_rows_with_current_predictions._ABA_CURRENT_ROWS_PATCH = True
    LocalStorage.load_rows = load_rows_with_current_predictions


def install() -> None:
    global _PATCHED
    if _PATCHED:
        return
    try:
        from autonomous_betting_agent import commercial_platform_tools as cpt
    except Exception:
        cpt = None
    if cpt is not None:
        original_load_persistent_ledger = getattr(cpt, "load_persistent_ledger", None)
        if callable(original_load_persistent_ledger) and not getattr(original_load_persistent_ledger, "_ABA_FRESH_HANDOFF_PATCH", False):
            def load_persistent_ledger_fresh_safe(*args: Any, **kwargs: Any):
                if _has_fresh_handoff_rows():
                    try:
                        import pandas as pd
                        return pd.DataFrame()
                    except Exception:
                        return None
                return original_load_persistent_ledger(*args, **kwargs)

            load_persistent_ledger_fresh_safe._ABA_FRESH_HANDOFF_PATCH = True
            cpt.load_persistent_ledger = load_persistent_ledger_fresh_safe
    _patch_local_storage()
    _PATCHED = True


install()
