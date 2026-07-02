from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

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


def _row_has_independent_probability(row: Mapping[str, Any]) -> bool:
    source = _text(row.get("model_probability_source")).lower()
    if any(token in source for token in MARKET_BASELINE_TOKENS):
        return False
    market_probability = _probability(row.get("market_probability") or row.get("market_implied_probability") or row.get("raw_market_implied_probability"))
    for field in MODEL_PROBABILITY_FIELDS:
        prob = _probability(row.get(field))
        if prob is None:
            continue
        # Treat exact market-probability copies as non-independent unless a learned source is explicit.
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


def source_quality_score(key: str, rows: Sequence[Mapping[str, Any]], original_index: int = 0) -> tuple[int, int, int, int, int, int]:
    clean_rows = [row for row in rows if isinstance(row, Mapping)]
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


def _patch_held_key_sets(store: Any) -> None:
    try:
        store.HELD_KEYS = set(getattr(store, "HELD_KEYS", set())) | FRESH_ODDS_KEYS
        store.LATEST_ALIAS_KEYS = set(getattr(store, "LATEST_ALIAS_KEYS", set())) | FRESH_ODDS_KEYS
    except Exception:
        return


def install() -> None:
    try:
        from autonomous_betting_agent import pick_hold_store as store
    except Exception:
        return
    if getattr(store, "_aba_report_source_quality_guard_v1", False):
        return
    _patch_held_key_sets(store)
    original_load_first_available = store.load_first_available

    def quality_first_available(keys: list[str] | tuple[str, ...], workspace_id: Any = "test_01") -> tuple[str, list[dict[str, Any]]]:
        candidates: list[tuple[tuple[int, int, int, int, int, int], int, str, list[dict[str, Any]]]] = []
        for index, key in enumerate(keys):
            rows = store.load_held_rows(key, workspace_id)
            if rows:
                score = source_quality_score(key, rows, index)
                candidates.append((score, -index, key, rows))
        if not candidates:
            return "", []
        best = max(candidates, key=lambda item: item[:2])
        if best[0][0] > 0:
            return best[2], best[3]
        return original_load_first_available(keys, workspace_id)

    store.load_first_available = quality_first_available
    store._aba_report_source_quality_guard_v1 = True
