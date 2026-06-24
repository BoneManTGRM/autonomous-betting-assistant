"""Report helpers for chain learning memory."""

from __future__ import annotations

from typing import Any, Mapping

from autonomous_betting_agent.chain_learning_store import summarize_chain_learning_memory

NO_MEMORY_MESSAGE = "No chain learning memory yet. Grade completed chains to build memory."


def _top_items(bucket: Mapping[str, Any], limit: int = 8) -> list[tuple[str, Any]]:
    return sorted(bucket.items(), key=lambda item: int(item[1] or 0), reverse=True)[:limit]


def render_chain_learning_summary(memory: Mapping[str, Any] | None) -> str:
    summary = summarize_chain_learning_memory(memory)
    if not summary.get("graded_result_count"):
        return f"## Chain Learning Summary\n\n{NO_MEMORY_MESSAGE}\n"
    lines = [
        "## Chain Learning Summary",
        "",
        f"Graded chains: {summary.get('graded_result_count', 0)}",
        "",
        "### Most Common Failed Legs",
    ]
    failed = _top_items(summary.get("leg_failure_patterns", {}))
    lines.extend([f"- {name}: {count}" for name, count in failed] or ["- None yet"])
    lines += ["", "### Best Chain Add-On Markets"]
    successful = _top_items(summary.get("successful_chain_patterns", {}))
    lines.extend([f"- {name}: {count}" for name, count in successful] or ["- None yet"])
    lines += ["", "### Worst Chain Add-On Markets"]
    lines.extend([f"- {name}: {count}" for name, count in failed] or ["- None yet"])
    lines += ["", "### Straight Bet Better Patterns"]
    straight = _top_items(summary.get("straight_bet_better_patterns", {}))
    lines.extend([f"- {name}: {count}" for name, count in straight] or ["- None yet"])
    lines += ["", "### Target Payout Mistake Patterns"]
    target = _top_items(summary.get("target_payout_chase_patterns", {}))
    lines.extend([f"- {name}: {count}" for name, count in target] or ["- None yet"])
    lines += ["", "### Game Script Accuracy"]
    script = summary.get("game_script_accuracy_patterns", {})
    lines.extend([f"- {name}: {count}" for name, count in _top_items(script)] or ["- None yet"])
    lines += ["", "### Recommended Adjustments"]
    if failed:
        lines.append("- Review and reduce exposure to the most common failed add-on markets until the sample improves.")
    if straight:
        lines.append("- When straight-bet-better patterns repeat, downgrade similar chains to watch-only.")
    if target:
        lines.append("- Penalize target-payout filler legs unless they have independent value.")
    if not (failed or straight or target):
        lines.append("- Keep collecting graded chain results before applying strong adjustments.")
    return "\n".join(lines).strip() + "\n"


def chain_learning_summary_to_rows(memory: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    summary = summarize_chain_learning_memory(memory)
    rows: list[dict[str, Any]] = []
    for bucket_name in (
        "leg_failure_patterns",
        "successful_chain_patterns",
        "bad_filler_leg_patterns",
        "straight_bet_better_patterns",
        "target_payout_chase_patterns",
        "game_script_accuracy_patterns",
    ):
        bucket = summary.get(bucket_name, {}) or {}
        for key, count in bucket.items():
            rows.append({"chain_learning_bucket": bucket_name, "pattern": key, "count": count})
    return rows
