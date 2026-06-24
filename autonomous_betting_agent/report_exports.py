"""Local-first Report Studio export helpers.

Provides Markdown, HTML, and copy/paste client delivery formats without a cloud
server. PDF can be layered on later by callers if a local renderer is available.
"""

from __future__ import annotations

import html
from collections import Counter
from typing import Any, Iterable, Mapping

from .explanations import build_client_safe_pick_summary
from .ledger_types import public_metric_allowed

_NON_DECISIONS = {"push", "void", "cancel", "cancelled", "canceled", "pending", "no action", "draw"}
_WINS = {"win", "won", "w"}
_LOSSES = {"loss", "lost", "l"}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _lower(value: Any) -> str:
    return _text(value).lower()


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize_record(rows: Iterable[Mapping[str, Any]], official_only: bool = True) -> dict[str, Any]:
    filtered = [row for row in rows if (public_metric_allowed(row) or not official_only)]
    counts = Counter(_lower(row.get("grade") or row.get("result") or "pending") or "pending" for row in filtered)
    wins = sum(counts[key] for key in _WINS)
    losses = sum(counts[key] for key in _LOSSES)
    pushes = sum(counts[key] for key in {"push", "void", "draw", "no action"})
    cancels = sum(counts[key] for key in {"cancel", "cancelled", "canceled"})
    pending = counts["pending"]
    resolved = wins + losses
    win_rate = wins / resolved if resolved else None

    total_profit = 0.0
    total_stake = 0.0
    has_profit = False
    for row in filtered:
        stake = _float(row.get("stake") or row.get("units") or 1)
        if stake is None:
            stake = 1.0
        grade = _lower(row.get("grade") or row.get("result"))
        price = _float(row.get("decimal_price") or row.get("odds_at_pick"))
        if grade in _WINS and price:
            total_profit += stake * (price - 1.0)
            total_stake += stake
            has_profit = True
        elif grade in _LOSSES:
            total_profit -= stake
            total_stake += stake
            has_profit = True
    roi = total_profit / total_stake if has_profit and total_stake else None
    return {
        "rows": len(filtered),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "cancels": cancels,
        "pending": pending,
        "resolved_decisions": resolved,
        "win_rate": win_rate,
        "profit_units": total_profit if has_profit else None,
        "roi": roi,
    }


def breakdown(rows: Iterable[Mapping[str, Any]], field: str) -> list[tuple[str, int]]:
    counts = Counter(_text(row.get(field)) or "Unknown" for row in rows)
    return counts.most_common()


def render_markdown_report(
    rows: Iterable[Mapping[str, Any]],
    title: str = "ABA Signal Pro Report",
    client_name: str = "",
    public_safe: bool = True,
) -> str:
    selected = [row for row in rows if (public_metric_allowed(row) or not public_safe)]
    summary = summarize_record(selected, official_only=public_safe)
    lines = [f"# {title}", ""]
    if client_name:
        lines += [f"**Client:** {client_name}", ""]
    lines += [
        "**Disclaimer:** This is sports analytics and proof tracking only. It does not guarantee wins, returns, or outcomes.",
        "",
        "## Summary",
        "",
        f"- Rows: {summary['rows']}",
        f"- Wins: {summary['wins']}",
        f"- Losses: {summary['losses']}",
        f"- Pushes/void/draws: {summary['pushes']}",
        f"- Canceled: {summary['cancels']}",
        f"- Pending: {summary['pending']}",
    ]
    if summary["win_rate"] is not None:
        lines.append(f"- Win rate excluding pushes/cancels/pending: {summary['win_rate']:.1%}")
    if summary["roi"] is not None:
        lines.append(f"- ROI from available stake/odds fields: {summary['roi']:.1%}")
        lines.append(f"- Profit units from available stake/odds fields: {summary['profit_units']:.2f}")
    lines += ["", "## Sport breakdown", ""]
    for key, count in breakdown(selected, "sport"):
        lines.append(f"- {key}: {count}")
    lines += ["", "## Recent picks", ""]
    for row in selected[:25]:
        lines.append(f"- {build_client_safe_pick_summary(row)}")
    return "\n".join(lines).strip() + "\n"


def render_html_report(
    rows: Iterable[Mapping[str, Any]],
    title: str = "ABA Signal Pro Report",
    client_name: str = "",
    background_image_url: str = "",
    public_safe: bool = True,
) -> str:
    markdown = render_markdown_report(rows, title=title, client_name=client_name, public_safe=public_safe)
    bg = ""
    if background_image_url:
        bg = f"background-image: linear-gradient(rgba(255,255,255,.90), rgba(255,255,255,.90)), url('{html.escape(background_image_url)}'); background-size: cover; background-attachment: fixed;"
    body = "\n".join(f"<p>{html.escape(line)}</p>" if line else "<br>" for line in markdown.splitlines())
    return f"""<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.45; {bg} }}
    p {{ max-width: 980px; }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def render_messenger_report(rows: Iterable[Mapping[str, Any]], title: str = "ABA Signal Pro Update") -> str:
    summary = summarize_record(rows, official_only=True)
    win_rate = "N/A" if summary["win_rate"] is None else f"{summary['win_rate']:.1%}"
    return (
        f"{title}\n"
        f"Record: {summary['wins']}-{summary['losses']} | Push/void: {summary['pushes']} | Pending: {summary['pending']}\n"
        f"Win rate excl. push/cancel/pending: {win_rate}\n"
        "Analytics/research only. No guaranteed outcomes."
    )
