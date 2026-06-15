from __future__ import annotations

from typing import Any

import pandas as pd

from .data_intake_gate import intake_gate
from .performance_segments import top_segments
from .quality_control import build_quality_control_report
from .row_normalizer import normalize_frame
from .stat_validation import roi_scenarios, statistical_summary


def build_review_packet(frame: pd.DataFrame, *, starting_units: float = 100.0) -> dict[str, Any]:
    normalized = normalize_frame(frame)
    intake = intake_gate(normalized)
    quality = build_quality_control_report(normalized, starting_units=starting_units)
    stats = statistical_summary(normalized)
    top = top_segments(normalized, min_resolved=1, limit=10)
    scenarios = roi_scenarios(int(stats.get('wins', 0)), int(stats.get('losses', 0)))
    return {
        'rows': int(len(normalized)),
        'intake': intake,
        'quality': quality,
        'statistics': stats,
        'top_segments': top.to_dict(orient='records') if not top.empty else [],
        'roi_scenarios': scenarios.to_dict(orient='records') if not scenarios.empty else [],
        'limitations': [
            'Rows without pre-event timestamps should not be treated as locked forward evidence.',
            'Rows without decimal_price cannot support ROI analysis.',
            'Small samples should be treated as early signal only.',
        ],
    }


def packet_markdown(packet: dict[str, Any]) -> str:
    stats = packet.get('statistics', {})
    quality = packet.get('quality', {})
    intake = packet.get('intake', {})
    lines = [
        '# Review Packet',
        '',
        f"Rows reviewed: {packet.get('rows', 0)}",
        f"Intake status: {intake.get('overall_status', 'unknown')}",
        f"Quality score: {quality.get('quality_score', 'N/A')}/100",
        '',
        '## Result Summary',
        f"Wins: {stats.get('wins', 0)}",
        f"Losses: {stats.get('losses', 0)}",
        f"Resolved total: {stats.get('total', 0)}",
        f"Observed hit rate: {stats.get('observed_win_rate')}",
        f"95% low: {stats.get('wilson_low_95')}",
        f"95% high: {stats.get('wilson_high_95')}",
        '',
        '## Recommendations',
    ]
    for item in quality.get('recommendations', []):
        lines.append(f'- {item}')
    lines.extend(['', '## Limitations'])
    for item in packet.get('limitations', []):
        lines.append(f'- {item}')
    return '\n'.join(lines) + '\n'
