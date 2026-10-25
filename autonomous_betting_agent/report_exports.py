"""Local-first Report Studio export helpers.

Provides Markdown, HTML, print-to-PDF-ready HTML, and copy/paste client delivery
formats without a cloud server. Users can open the HTML report and use the
browser print dialog to save as PDF.
"""

from __future__ import annotations

import html
import math
from collections import Counter
from typing import Any, Iterable, Mapping

from .explanations import build_client_safe_pick_summary
from .grading_rules import grade_from_row
from .ledger_types import public_metric_allowed

_NON_DECISIONS = {"push", "void", "cancel", "cancelled", "canceled", "pending", "no action", "draw"}
_WINS = {"win", "won", "w"}
_LOSSES = {"loss", "lost", "l"}

PRINT_TO_PDF_NOTE = "Open this HTML report in a browser, then use Print or Save as PDF for a local PDF copy."


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _lower(value: Any) -> str:
    return _text(value).lower()


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _first_value(row: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    """Choose a populated field without replacing an explicit zero or bad value."""
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return value
    return default


def summarize_record(rows: Iterable[Mapping[str, Any]], official_only: bool = True) -> dict[str, Any]:
    filtered = [row for row in rows if (public_metric_allowed(row) or not official_only)]
    counts = Counter(grade_from_row(row) for row in filtered)
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
    financial_overflow = False
    for row in filtered:
        stake = _float(_first_value(row, "stake", "stake_units", "units", default=1))
        # Keep the legacy one-unit default only for absent stake fields. Invalid
        # or zero stakes must not manufacture financial performance.
        if stake is None or stake <= 0:
            continue
        grade = grade_from_row(row)
        price = _float(_first_value(row, "decimal_price", "odds_at_pick"))
        if grade in _WINS and price is not None and price > 1:
            total_profit += stake * (price - 1.0)
            total_stake += stake
            has_profit = True
        elif grade in _LOSSES:
            total_profit -= stake
            total_stake += stake
            has_profit = True
        if not math.isfinite(total_profit) or not math.isfinite(total_stake):
            financial_overflow = True
            break
    if financial_overflow:
        # Do not present a partial or infinite record when totals exceed the
        # numeric representation. Outcome counts above are still valid.
        has_profit = False
    roi = total_profit / total_stake if has_profit and total_stake else None
    if roi is not None and not math.isfinite(roi):
        roi = None
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


def _print_ready_css(background_image_url: str = "") -> str:
    bg = ""
    if background_image_url:
        bg = f"background-image: linear-gradient(rgba(255,255,255,.90), rgba(255,255,255,.90)), url('{html.escape(background_image_url)}'); background-size: cover; background-attachment: fixed;"
    return f"""
    :root {{ color-scheme: light; }}
    body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.45; color: #111; {bg} }}
    main {{ max-width: 980px; }}
    p {{ max-width: 980px; margin: 0 0 .55rem 0; }}
    .print-note {{ border: 1px solid #ddd; padding: .75rem 1rem; border-radius: .5rem; background: #fafafa; margin-bottom: 1rem; }}
    @page {{ size: auto; margin: 0.55in; }}
    @media print {{
      body {{ margin: 0; background: #fff !important; color: #000; }}
      .print-note {{ display: none; }}
      a {{ color: #000; text-decoration: none; }}
      p {{ page-break-inside: avoid; }}
    }}
    """


def render_html_report(
    rows: Iterable[Mapping[str, Any]],
    title: str = "ABA Signal Pro Report",
    client_name: str = "",
    background_image_url: str = "",
    public_safe: bool = True,
) -> str:
    markdown = render_markdown_report(rows, title=title, client_name=client_name, public_safe=public_safe)
    body = "\n".join(f"<p>{html.escape(line)}</p>" if line else "<br>" for line in markdown.splitlines())
    return f"""<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{html.escape(title)}</title>
  <style>{_print_ready_css(background_image_url)}</style>
</head>
<body>
<main>
<div class=\"print-note\">{html.escape(PRINT_TO_PDF_NOTE)}</div>
{body}
</main>
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
