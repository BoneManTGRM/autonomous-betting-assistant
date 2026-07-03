from __future__ import annotations

from typing import Any, Mapping, Sequence

MODEL_PROBABILITY_FIELDS = (
    "learned_model_probability",
    "final_adjusted_probability",
    "adjusted_model_probability",
    "model_probability_clean",
    "model_probability",
    "probability",
    "confidence_probability",
)
PRICE_FIELDS = (
    "decimal_price",
    "best_price",
    "average_price",
    "avg_price",
    "decimal_odds",
    "odds_decimal",
    "odds_at_pick",
    "odds",
    "price",
)
EDGE_FIELDS = (
    "model_market_edge",
    "model_edge",
    "edge_probability",
    "edge",
    "expected_value_per_unit",
    "computed_ev_decimal",
    "estimated_ev_decimal",
)
MARKET_BASELINE_TOKENS = (
    "base_market_probability",
    "market_probability_no_learning",
    "market_baseline_only",
)
FRESH_ODDS_KEYS = {"fresh_odds_slate_builder_rows"}
REPORT_HANDOFF_KEYS = (
    "odds_lock_pro_locked_rows",
    "public_proof_dashboard_refresh_rows",
    "pro_predictor_high_confidence_rows",
    "pro_predictor_latest_rows",
    "what_are_the_odds_latest_rows",
    "ara_latest_predictions",
    "fresh_odds_slate_builder_rows",
)
STALE_SAVED_TOKENS = (
    "uploaded / saved",
    "uploaded/saved",
    "saved-source",
    "saved source",
    "saved row",
    "saved-row",
    "uploaded row",
    "uploaded_row",
    "source saved",
    "source_saved",
)
VERIFY_ONLY_TOKENS = (
    "verify price",
    "verify_price",
    "uploaded_row",
    "uploaded row",
    "source saved",
    "source_saved",
)
PROOF_TIME_FIELDS = ("locked_at_utc", "locked_at", "proof_locked_at_utc")
PROOF_ID_FIELDS = ("proof_id", "proof_hash")
CURRENT_SOURCE_TOKENS = (
    "live_api",
    "live api",
    "current run",
    "current-run",
    "diagnostic",
    "pro_predictor_filter_diagnostic",
    "odds_lock",
    "locked",
    "proof",
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "none", "nan", "null", "nat", "n/a", "na"} else text


def _float(value: Any) -> float | None:
    text = _text(value).replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed


def _probability(value: Any) -> float | None:
    parsed = _float(value)
    if parsed is None:
        return None
    if 1.0 < parsed <= 100.0:
        parsed /= 100.0
    return parsed if 0.0 < parsed < 1.0 else None


def _rows_from_any(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    try:
        import pandas as pd

        if isinstance(value, pd.DataFrame):
            return [] if value.empty else [dict(row) for row in value.to_dict(orient="records")]
    except Exception:
        pass
    return []


def _combined_text(row: Mapping[str, Any], fields: Sequence[str]) -> str:
    return " | ".join(_text(row.get(field)).lower() for field in fields if _text(row.get(field)))


def _has_proof_identity(row: Mapping[str, Any]) -> bool:
    has_id = any(bool(_text(row.get(field))) for field in PROOF_ID_FIELDS)
    has_time = any(bool(_text(row.get(field))) for field in PROOF_TIME_FIELDS)
    return has_id and has_time


def _row_is_current_or_locked(row: Mapping[str, Any]) -> bool:
    if _has_proof_identity(row):
        return True
    text = _combined_text(
        row,
        (
            "report_source",
            "source_mode",
            "source_type",
            "proof_source_type",
            "odds_source",
            "verification_status",
            "odds_status",
            "decision_signals",
            "recommendation_tier",
        ),
    )
    return any(token in text for token in CURRENT_SOURCE_TOKENS)


def row_is_stale_saved_handoff(row: Mapping[str, Any]) -> bool:
    """True for old saved/uploaded handoff rows that should not drive a fresh report.

    These rows can contain odds, edge, and EV, so ordinary value-based scoring can
    mistake them for usable current rows. They are not removed if they have a real
    proof lock identity or an explicit current/live/diagnostic source marker.
    """
    if not isinstance(row, Mapping):
        return True
    if _row_is_current_or_locked(row):
        return False
    source_text = _combined_text(
        row,
        (
            "report_source",
            "data_scope",
            "source_mode",
            "source_type",
            "source_file",
            "odds_source",
            "truth",
            "report_truth_severity",
        ),
    )
    status_text = _combined_text(
        row,
        (
            "odds_status",
            "verification_status",
            "recommendation_tier",
            "blocker_reason",
            "truth",
            "report_truth_severity",
        ),
    )
    saved_source = any(token in source_text for token in STALE_SAVED_TOKENS)
    verify_only = any(token in status_text for token in VERIFY_ONLY_TOKENS)
    return saved_source and verify_only


def _row_has_independent_probability(row: Mapping[str, Any]) -> bool:
    source = _text(row.get("model_probability_source")).lower()
    if any(token in source for token in MARKET_BASELINE_TOKENS):
        return False
    market_probability = _probability(row.get("market_probability") or row.get("market_implied_probability") or row.get("raw_market_implied_probability"))
    for field in MODEL_PROBABILITY_FIELDS:
        prob = _probability(row.get(field))
        if prob is None:
            continue
        if market_probability is not None and abs(prob - market_probability) < 0.000001 and field not in {"learned_model_probability", "final_adjusted_probability", "adjusted_model_probability"}:
            continue
        return True
    return False


def _row_has_price(row: Mapping[str, Any]) -> bool:
    for field in PRICE_FIELDS:
        value = _float(row.get(field))
        if value is not None and value > 1.0:
            return True
    return False


def _row_has_edge_or_ev(row: Mapping[str, Any]) -> bool:
    return any(_float(row.get(field)) is not None for field in EDGE_FIELDS)


def _source_priority(key: str, original_index: int) -> int:
    if "pro_predictor" in key:
        return 90
    if "what_are_the_odds" in key:
        return 80
    if "ara_latest_predictions" in key:
        return 70
    if "odds_lock_pro" in key or "public_proof" in key:
        return 60
    if key in FRESH_ODDS_KEYS:
        return 20
    return max(0, 50 - original_index)


def usable_report_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if isinstance(row, Mapping) and not row_is_stale_saved_handoff(row)]


def source_quality_score(key: str, rows: Sequence[Mapping[str, Any]], original_index: int = 0) -> tuple[int, int, int, int, int, int]:
    clean_rows = usable_report_rows(rows)
    if not clean_rows:
        return (0, 0, 0, 0, 0, -original_index)
    independent = sum(1 for row in clean_rows if _row_has_independent_probability(row))
    priced = sum(1 for row in clean_rows if _row_has_price(row))
    edges = sum(1 for row in clean_rows if _row_has_edge_or_ev(row))
    usable = min(independent, priced)
    return (
        1 if usable > 0 else 0,
        usable,
        independent,
        priced,
        edges,
        _source_priority(str(key), original_index),
    )


def best_source_key(candidates: Sequence[tuple[str, Any]]) -> str:
    scored: list[tuple[tuple[int, int, int, int, int, int], int, str]] = []
    for index, (key, value) in enumerate(candidates):
        rows = _rows_from_any(value)
        if not rows:
            continue
        scored.append((source_quality_score(key, rows, index), -index, key))
    if not scored:
        return ""
    best = max(scored, key=lambda item: item[:2])
    return best[2] if best[0][0] > 0 else ""


def _patch_held_key_sets(store: Any) -> None:
    try:
        store.HELD_KEYS = set(getattr(store, "HELD_KEYS", set())) | FRESH_ODDS_KEYS
        store.LATEST_ALIAS_KEYS = set(getattr(store, "LATEST_ALIAS_KEYS", set())) | FRESH_ODDS_KEYS
    except Exception:
        return


def _patch_load_first_available(store: Any) -> None:
    if getattr(store, "_aba_report_source_quality_store_patch_v3", False):
        return

    def quality_first_available(keys: list[str] | tuple[str, ...], workspace_id: Any = "test_01") -> tuple[str, list[dict[str, Any]]]:
        candidates: list[tuple[tuple[int, int, int, int, int, int], int, str, list[dict[str, Any]]]] = []
        for index, key in enumerate(keys):
            rows = store.load_held_rows(key, workspace_id)
            if rows:
                usable_rows = [dict(row) for row in usable_report_rows(rows)]
                score = source_quality_score(key, usable_rows, index)
                candidates.append((score, -index, key, usable_rows))
        if not candidates:
            return "", []
        best = max(candidates, key=lambda item: item[:2])
        if best[0][0] > 0:
            return best[2], best[3]
        return "", []

    store.load_first_available = quality_first_available
    store._aba_report_source_quality_store_patch_v3 = True


def _patch_streamlit_session_get() -> None:
    """Make Report Studio skip stale saved/uploaded session rows when selecting a source."""
    try:
        import streamlit.runtime.state.session_state_proxy as proxy
    except Exception:
        return
    session_cls = getattr(proxy, "SessionStateProxy", None)
    original_get = getattr(session_cls, "get", None)
    if session_cls is None or not callable(original_get):
        return
    if getattr(original_get, "_aba_report_source_quality_session_patch_v3", False):
        return

    def quality_guarded_get(self: Any, key: Any, default: Any = None) -> Any:
        if key not in REPORT_HANDOFF_KEYS:
            return original_get(self, key, default)
        try:
            candidates = [(handoff_key, original_get(self, handoff_key, [])) for handoff_key in REPORT_HANDOFF_KEYS]
            winner = best_source_key(candidates)
            if winner:
                if key != winner:
                    return default
                rows = usable_report_rows(_rows_from_any(original_get(self, key, default)))
                return rows if rows else default
            if any(_rows_from_any(value) for _candidate_key, value in candidates):
                return default
        except Exception:
            return original_get(self, key, default)
        return original_get(self, key, default)

    quality_guarded_get._aba_report_source_quality_session_patch_v3 = True  # type: ignore[attr-defined]
    session_cls.get = quality_guarded_get


def install() -> None:
    try:
        from autonomous_betting_agent import pick_hold_store as store
    except Exception:
        return
    _patch_held_key_sets(store)
    _patch_load_first_available(store)
    _patch_streamlit_session_get()
    store._aba_report_source_quality_guard_v3 = True
