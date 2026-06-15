from __future__ import annotations

from typing import Any

import pandas as pd

OFFICIAL_PICK_COLUMNS = [
    'event',
    'sport',
    'market_type',
    'prediction',
    'model_probability',
    'decimal_price',
    'american_odds',
    'bookmaker',
    'odds_source',
    'prediction_timestamp',
    'known_start_utc',
    'decision',
    'confidence_tier',
    'api_coverage_score',
    'books',
    'computed_ev_decimal',
    'result_status',
    'result_source_url',
    'final_score',
    'winner',
    'stake_units',
    'profit_units',
    'closing_decimal_price',
    'graded_at_utc',
    'notes',
]

REQUIRED_BEFORE_START = [
    'event',
    'prediction',
    'model_probability',
    'decimal_price',
    'bookmaker',
    'odds_source',
    'prediction_timestamp',
]

REQUIRED_AFTER_RESULT = [
    'result_status',
    'final_score',
    'winner',
    'profit_units',
    'graded_at_utc',
]

OPTIONAL_BUT_VALUABLE = [
    'closing_decimal_price',
    'api_coverage_score',
    'books',
    'computed_ev_decimal',
]


def empty_template(rows: int = 10) -> pd.DataFrame:
    rows = max(1, int(rows))
    return pd.DataFrame([{column: '' for column in OFFICIAL_PICK_COLUMNS} for _ in range(rows)])


def example_template() -> pd.DataFrame:
    return pd.DataFrame([
        {
            'event': 'Team A at Team B',
            'sport': 'Example League',
            'market_type': 'moneyline',
            'prediction': 'Team B',
            'model_probability': 0.62,
            'decimal_price': 1.95,
            'american_odds': -105,
            'bookmaker': 'ExampleBook',
            'odds_source': 'Odds API',
            'prediction_timestamp': '2026-06-15T18:00:00Z',
            'known_start_utc': '2026-06-15T22:00:00Z',
            'decision': 'play',
            'confidence_tier': 'A',
            'api_coverage_score': 0.9,
            'books': 8,
            'computed_ev_decimal': 0.209,
            'result_status': '',
            'result_source_url': '',
            'final_score': '',
            'winner': '',
            'stake_units': 1,
            'profit_units': '',
            'closing_decimal_price': '',
            'graded_at_utc': '',
            'notes': 'Example pre-event row',
        }
    ])


def schema_dictionary() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for column in OFFICIAL_PICK_COLUMNS:
        if column in REQUIRED_BEFORE_START:
            timing = 'required_before_start'
            importance = 'critical'
        elif column in REQUIRED_AFTER_RESULT:
            timing = 'required_after_result'
            importance = 'critical_for_grading'
        elif column in OPTIONAL_BUT_VALUABLE:
            timing = 'optional_but_valuable'
            importance = 'high'
        else:
            timing = 'optional'
            importance = 'medium'
        rows.append({'column': column, 'timing': timing, 'importance': importance})
    return pd.DataFrame(rows)
