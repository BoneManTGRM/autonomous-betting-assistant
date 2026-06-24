"""JSON-safe local store for chain learning results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from autonomous_betting_agent.chain_learning import ChainResultBreakdown, grade_chain_result, summarize_chain_learning

DEFAULT_MEMORY_PATH = Path("data/chain_learning_memory.json")
DEFAULT_MEMORY = {
    "chain_learning_summary": {},
    "leg_failure_patterns": {},
    "successful_chain_patterns": {},
    "bad_filler_leg_patterns": {},
    "straight_bet_better_patterns": {},
    "target_payout_chase_patterns": {},
    "game_script_accuracy_patterns": {},
    "graded_results": [],
}


def _path(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else DEFAULT_MEMORY_PATH


def _safe_memory(memory: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(DEFAULT_MEMORY)
    if memory:
        for key, value in memory.items():
            data[key] = value
    return data


def load_chain_learning_memory(path: str | Path | None = None) -> dict[str, Any]:
    target = _path(path)
    if not target.exists():
        return dict(DEFAULT_MEMORY)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_MEMORY)
    return _safe_memory(payload if isinstance(payload, Mapping) else {})


def save_chain_learning_memory(memory: Mapping[str, Any], path: str | Path | None = None) -> dict[str, Any]:
    target = _path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = _safe_memory(memory)
    target.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return data


def _increment(bucket: dict[str, int], key: str, amount: int = 1) -> None:
    if key:
        bucket[key] = int(bucket.get(key, 0)) + amount


def _apply_result(memory: dict[str, Any], result: ChainResultBreakdown) -> dict[str, Any]:
    memory.setdefault("graded_results", []).append(result.as_dict())
    if result.chain_status == "win":
        _increment(memory.setdefault("successful_chain_patterns", {}), result.game)
    for leg in result.leg_results:
        if leg.status == "loss":
            _increment(memory.setdefault("leg_failure_patterns", {}), leg.market)
        if leg.was_filler_leg:
            _increment(memory.setdefault("bad_filler_leg_patterns", {}), leg.market)
    if result.straight_bet_would_have_won and result.chain_status == "loss":
        _increment(memory.setdefault("straight_bet_better_patterns", {}), result.game)
    if result.target_payout_chase_detected:
        _increment(memory.setdefault("target_payout_chase_patterns", {}), result.game)
    if result.game_script_correct is not None:
        key = "correct" if result.game_script_correct else "wrong"
        _increment(memory.setdefault("game_script_accuracy_patterns", {}), key)
    memory["chain_learning_summary"] = summarize_chain_learning([
        ChainResultBreakdown(**{**item, "leg_results": tuple()}) if isinstance(item, dict) and "leg_results" not in item else result
        for item in [result.as_dict()]
    ])
    return memory


def append_chain_learning_result(result: Mapping[str, Any] | ChainResultBreakdown, path: str | Path | None = None) -> dict[str, Any]:
    memory = load_chain_learning_memory(path)
    breakdown = result if isinstance(result, ChainResultBreakdown) else grade_chain_result(result)
    memory = _apply_result(memory, breakdown)
    return save_chain_learning_memory(memory, path)


def summarize_chain_learning_memory(memory: Mapping[str, Any] | None) -> dict[str, Any]:
    data = _safe_memory(memory)
    results = data.get("graded_results", []) or []
    return {
        "graded_result_count": len(results),
        "leg_failure_patterns": data.get("leg_failure_patterns", {}),
        "successful_chain_patterns": data.get("successful_chain_patterns", {}),
        "bad_filler_leg_patterns": data.get("bad_filler_leg_patterns", {}),
        "straight_bet_better_patterns": data.get("straight_bet_better_patterns", {}),
        "target_payout_chase_patterns": data.get("target_payout_chase_patterns", {}),
        "game_script_accuracy_patterns": data.get("game_script_accuracy_patterns", {}),
        "message": "No chain learning memory yet. Grade completed chains to build memory." if not results else "Chain learning memory loaded.",
    }
