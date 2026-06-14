from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Mapping


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _fmt(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text if text else default


def _existing_columns(rows: list[Mapping[str, Any]], columns: list[str]) -> list[str]:
    available = {key for row in rows for key in row.keys()}
    return [column for column in columns if column in available]


def _table(rows: list[Mapping[str, Any]], columns: list[str], *, limit: int = 25) -> str:
    if not rows:
        return "No rows.\n"
    columns = _existing_columns(rows, columns) or columns[:8]
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, sep]
    for row in rows[:limit]:
        lines.append("| " + " | ".join(_fmt(row.get(column)).replace("|", "/") for column in columns) + " |")
    if len(rows) > limit:
        lines.append(f"\nShowing {limit} of {len(rows)} rows.\n")
    return "\n".join(lines) + "\n"


def _count_by(rows: list[Mapping[str, Any]], column: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = _fmt(row.get(column), "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _counts_lines(title: str, counts: dict[str, int]) -> str:
    if not counts:
        return f"### {title}\n\nNo data.\n"
    lines = [f"### {title}", ""]
    for key, value in counts.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


def build_daily_markdown_report(
    *,
    final_bets_csv: str | Path,
    watchlist_csv: str | Path,
    rejected_picks_csv: str | Path,
    output_md: str | Path,
    title: str = "Daily Betting Agent Summary",
    warnings: list[str] | None = None,
) -> str:
    final_bets = read_csv_rows(final_bets_csv)
    watchlist = read_csv_rows(watchlist_csv)
    rejected = read_csv_rows(rejected_picks_csv)
    total_stake = 0.0
    for row in final_bets:
        try:
            total_stake += float(str(row.get("recommended_stake_units") or "0"))
        except ValueError:
            pass

    common_columns = [
        "sport",
        "league",
        "market",
        "selection",
        "best_price",
        "market_probability",
        "stats_adjustment",
        "injury_adjustment",
        "weather_adjustment",
        "ara_memory_adjustment",
        "final_probability",
        "calibrated_probability",
        "confidence",
        "reliability_score",
        "ensemble_score",
        "profile_trust_level",
        "recommended_stake_units",
        "risk_tier",
    ]
    rejected_columns = [
        "sport",
        "league",
        "market",
        "selection",
        "final_probability",
        "confidence",
        "reliability_score",
        "ensemble_status",
        "validation_errors",
        "do_not_bet_reason",
        "rejection_reason",
        "fusion_warning",
    ]

    lines = [
        f"# {title}",
        "",
        "## Snapshot",
        "",
        f"- Final bets: {len(final_bets)}",
        f"- Watchlist: {len(watchlist)}",
        f"- Rejected picks: {len(rejected)}",
        f"- Total recommended stake units: {round(total_stake, 4)}",
        "",
    ]

    warnings = warnings or []
    if warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")

    lines.extend([
        _counts_lines("Final bets by sport", _count_by(final_bets, "sport")),
        _counts_lines("Final bets by market", _count_by(final_bets, "market")),
        _counts_lines("Final bets by confidence", _count_by(final_bets, "confidence")),
        "## Final Bets",
        "",
        _table(final_bets, common_columns),
        "## Watchlist",
        "",
        _table(watchlist, common_columns),
        "## Rejected Picks",
        "",
        _table(rejected, rejected_columns),
        "## Notes",
        "",
        "- This report is generated from CSV outputs and is meant for review before any action.",
        "- Multi-source fusion starts from market probability and caps how far extra APIs can move the pick.",
        "- A row in final_bets.csv is still not a guarantee; it only passed the current filters.",
        "- Watchlist and rejected rows should remain tracked for learning, but not mixed into final-bet performance claims.",
        "",
    ])
    markdown = "\n".join(lines)
    output = Path(output_md)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    return markdown
