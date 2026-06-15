from __future__ import annotations

from typing import Any

import pandas as pd

from .bankroll_tracker import bankroll_summary
from .duplicate_conflicts import duplicate_conflict_summary
from .line_movement import line_movement_summary
from .result_grader import grade_summary
from .row_normalizer import normalize_frame

VERSION_COLUMNS = ['model_version', 'calibration_version', 'memory_version', 'api_bundle_version']


def version_coverage(frame: pd.DataFrame) -> dict[str, int]:
    if frame is None or frame.empty:
        return {column: 0 for column in VERSION_COLUMNS}
    data = normalize_frame(frame)
    coverage: dict[str, int] = {}
    for column in VERSION_COLUMNS:
        if column not in data.columns:
            coverage[column] = 0
        else:
            coverage[column] = int(data[column].fillna('').astype(str).str.strip().ne('').sum())
    return coverage


def quality_score(report: dict[str, Any]) -> int:
    score = 100
    dup = report.get('duplicates', {})
    grading = report.get('grading', {})
    movement = report.get('line_movement', {})
    versions = report.get('version_coverage', {})

    score -= int(dup.get('exact_duplicates', 0)) * 5
    score -= int(dup.get('prediction_conflicts', 0)) * 10
    score -= int(dup.get('result_conflicts', 0)) * 10
    score -= int(grading.get('review_needed', 0)) * 4
    if int(movement.get('missing', 0)) > int(movement.get('ready', 0)):
        score -= 10
    if versions and any(value == 0 for value in versions.values()):
        score -= 8
    return max(0, min(100, score))


def quality_recommendations(report: dict[str, Any]) -> list[str]:
    items: list[str] = []
    dup = report.get('duplicates', {})
    grading = report.get('grading', {})
    movement = report.get('line_movement', {})
    bank = report.get('bankroll', {})
    versions = report.get('version_coverage', {})

    if int(dup.get('exact_duplicates', 0)):
        items.append('Remove exact duplicate rows before reporting performance.')
    if int(dup.get('prediction_conflicts', 0)) or int(dup.get('result_conflicts', 0)):
        items.append('Resolve conflicting predictions/results before using this data for reports.')
    if int(grading.get('review_needed', 0)):
        items.append('Review rows marked review_needed before counting them as clean results.')
    if int(movement.get('missing', 0)):
        items.append('Add closing_decimal_price where possible to improve line-movement analysis.')
    if bank.get('roi_percent') is None:
        items.append('Add stake_units and profit_units to enable ROI and drawdown tracking.')
    if versions and any(value == 0 for value in versions.values()):
        items.append('Add model_version, calibration_version, memory_version, and api_bundle_version to future exports.')
    if not items:
        items.append('No major quality-control issues detected from the available fields.')
    return items


def build_quality_control_report(frame: pd.DataFrame, *, starting_units: float = 100.0) -> dict[str, Any]:
    normalized = normalize_frame(frame)
    report: dict[str, Any] = {
        'rows': int(len(normalized)) if normalized is not None else 0,
        'duplicates': duplicate_conflict_summary(normalized),
        'grading': grade_summary(normalized),
        'line_movement': line_movement_summary(normalized),
        'bankroll': bankroll_summary(normalized, starting_units=starting_units),
        'version_coverage': version_coverage(normalized),
    }
    report['quality_score'] = quality_score(report)
    report['recommendations'] = quality_recommendations(report)
    return report
