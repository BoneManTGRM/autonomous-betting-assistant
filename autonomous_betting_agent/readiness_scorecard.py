from __future__ import annotations

from typing import Any

import pandas as pd

from .data_intake_gate import intake_gate
from .performance_segments import build_segment_frame
from .quality_control import build_quality_control_report
from .row_normalizer import normalize_frame
from .stat_validation import statistical_summary

MILESTONES = [
    {'name': 'Data usable', 'points': 10},
    {'name': 'Clean quality score', 'points': 15},
    {'name': 'Resolved sample >= 25', 'points': 10},
    {'name': 'Resolved sample >= 100', 'points': 15},
    {'name': 'Odds captured', 'points': 10},
    {'name': 'Unit profit tracked', 'points': 10},
    {'name': 'Positive units', 'points': 10},
    {'name': 'Line movement available', 'points': 10},
    {'name': 'Version fields present', 'points': 5},
    {'name': 'Segment analytics available', 'points': 5},
]


def _coverage_count(frame: pd.DataFrame, column: str) -> int:
    if frame is None or frame.empty or column not in frame.columns:
        return 0
    return int(frame[column].fillna('').astype(str).str.strip().ne('').sum())


def build_readiness_scorecard(frame: pd.DataFrame, *, starting_units: float = 100.0) -> dict[str, Any]:
    data = normalize_frame(frame)
    intake = intake_gate(data)
    quality = build_quality_control_report(data, starting_units=starting_units)
    stats = statistical_summary(data)
    segments = build_segment_frame(data)

    rows = int(len(data))
    resolved = int(stats.get('total', 0))
    quality_score = int(quality.get('quality_score', 0))
    net_units = float(quality.get('bankroll', {}).get('net_units', 0) or 0)
    odds_rows = _coverage_count(data, 'decimal_price')
    profit_rows = _coverage_count(data, 'profit_units')
    line_ready = int(quality.get('line_movement', {}).get('ready', 0))
    version_coverage = quality.get('version_coverage', {})
    version_ready = bool(version_coverage) and all(int(v) > 0 for v in version_coverage.values())

    checks = [
        {'name': 'Data usable', 'ready': intake.get('overall_status') in {'usable', 'strong'}, 'points': 10, 'details': intake.get('summary')},
        {'name': 'Clean quality score', 'ready': quality_score >= 80, 'points': 15, 'details': f'Quality score {quality_score}/100'},
        {'name': 'Resolved sample >= 25', 'ready': resolved >= 25, 'points': 10, 'details': f'{resolved} resolved rows'},
        {'name': 'Resolved sample >= 100', 'ready': resolved >= 100, 'points': 15, 'details': f'{resolved} resolved rows'},
        {'name': 'Odds captured', 'ready': odds_rows > 0, 'points': 10, 'details': f'{odds_rows} rows with decimal_price'},
        {'name': 'Unit profit tracked', 'ready': profit_rows > 0, 'points': 10, 'details': f'{profit_rows} rows with profit_units'},
        {'name': 'Positive units', 'ready': net_units > 0, 'points': 10, 'details': f'Net units {net_units}'},
        {'name': 'Line movement available', 'ready': line_ready > 0, 'points': 10, 'details': f'{line_ready} rows with line movement'},
        {'name': 'Version fields present', 'ready': version_ready, 'points': 5, 'details': str(version_coverage)},
        {'name': 'Segment analytics available', 'ready': not segments.empty, 'points': 5, 'details': f'{len(segments)} segment rows'},
    ]
    earned = sum(int(item['points']) for item in checks if item['ready'])
    max_points = sum(int(item['points']) for item in checks)
    score = round(earned / max_points * 100, 2) if max_points else 0

    if score >= 85 and resolved >= 100:
        status = 'strong'
    elif score >= 70:
        status = 'near_ready'
    elif score >= 50:
        status = 'developing'
    else:
        status = 'early'

    next_actions = [item for item in checks if not item['ready']]
    return {
        'rows': rows,
        'readiness_score': score,
        'readiness_status': status,
        'earned_points': earned,
        'max_points': max_points,
        'checks': checks,
        'next_actions': next_actions,
        'intake_status': intake.get('overall_status'),
        'quality_score': quality_score,
        'resolved_rows': resolved,
        'net_units': net_units,
        'observed_hit_rate': stats.get('observed_win_rate'),
        'wilson_low_95': stats.get('wilson_low_95'),
    }


def checks_frame(scorecard: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(scorecard.get('checks', []))


def next_actions_frame(scorecard: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(scorecard.get('next_actions', []))
