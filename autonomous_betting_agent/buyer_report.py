from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .proof_ledger import ledger_summary, sport_breakdown, verify_hash_chain


def _pct(value: Any) -> str:
    if value is None or value == '':
        return 'N/A'
    try:
        return f'{float(value) * 100:.1f}%'
    except Exception:
        return 'N/A'


def buyer_demo_markdown(*, ledger: pd.DataFrame, memory_summary: dict[str, Any] | None = None, product_name: str = 'Autonomous Betting Agent') -> str:
    memory_summary = memory_summary or {}
    summary = ledger_summary(ledger)
    verification = verify_hash_chain(ledger)
    sports = sport_breakdown(ledger)
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    lines = [
        f'# {product_name} Buyer Demo Report',
        '',
        f'Generated: {generated}',
        '',
        '## Product Positioning',
        'Audited sports intelligence platform with timestamped predictions, odds capture, ROI tracking, local multi-user profiles, security checks, proof-ledger verification, and public performance dashboards.',
        '',
        '## Current Proof Ledger Summary',
        f'- Total picks: {summary["total_picks"]}',
        f'- Wins: {summary["wins"]}',
        f'- Losses: {summary["losses"]}',
        f'- Win rate: {_pct(summary["win_rate"])}',
        f'- Units: {summary["units"]}',
        f'- ROI: {"N/A" if summary["roi_percent"] is None else str(summary["roi_percent"]) + "%"}',
        f'- A+ picks: {summary["a_plus"]}',
        f'- Average decimal odds: {summary["avg_decimal_price"] or "N/A"}',
        f'- Hash chain: {"valid" if verification.valid else "warning"}',
        '',
        '## Learning Memory Summary',
        f'- Training mode: {memory_summary.get("training_mode", "N/A")}',
        f'- Uploaded usable rows: {memory_summary.get("uploaded_usable_rows", "N/A")}',
        f'- Rows after pruning: {memory_summary.get("rows_after_pruning", "N/A")}',
        f'- Fallback probability rows: {memory_summary.get("fallback_probability_rows", "N/A")}',
        '',
        '## Sport Breakdown',
    ]
    if sports.empty:
        lines.append('No sport breakdown available yet.')
    else:
        lines.append('| Sport | Picks | Wins | Losses | Win Rate | Units |')
        lines.append('|---|---:|---:|---:|---:|---:|')
        for row in sports.head(20).to_dict(orient='records'):
            lines.append(f'| {row.get("sport", "unknown")} | {row.get("picks", 0)} | {row.get("wins", 0)} | {row.get("losses", 0)} | {_pct(row.get("win_rate"))} | {row.get("units", 0)} |')
    lines.extend([
        '',
        '## Known Limitations',
        '- High win rate alone is not proof of profitability; ROI requires odds.',
        '- Rows missing odds/probability should not be counted as fully official betting proof.',
        '- Local profiles are not secure accounts until real authentication is added.',
        '- More forward-tested, timestamped picks are needed before making strong performance claims.',
        '',
        '## Next Commercial Steps',
        '1. Add real authentication and managed database.',
        '2. Add automated cross-sport result grading.',
        '3. Add subscription billing.',
        '4. Add alerts for A+ picks and graded results.',
        '5. Continue building the proof ledger with timestamped odds and ROI.',
    ])
    return '\n'.join(lines) + '\n'
