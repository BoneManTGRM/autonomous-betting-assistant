from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from .audit import parse_float

ALIASES = {
    'event': ('event', 'event_name', 'game', 'match', 'fixture'),
    'sport': ('sport', 'sport_title', 'league', 'competition'),
    'market_type': ('market_type', 'market', 'bet_type'),
    'prediction': ('prediction', 'pick', 'selection', 'predicted_side', 'predicted_winner', 'favorite'),
    'model_probability': ('model_probability', 'final_probability', 'final_probability_value', 'calibrated_probability', 'probability', 'pick_probability', 'confidence_probability'),
    'decimal_price': ('decimal_price', 'best_price', 'decimal_odds', 'odds_decimal', 'odds', 'price', 'sportsbook_odds', 'average_price', 'avg_price'),
    'american_odds': ('american_odds', 'american_price', 'moneyline'),
    'bookmaker': ('bookmaker', 'best_bookmaker', 'sportsbook'),
    'odds_source': ('odds_source', 'source', 'source_file'),
    'prediction_timestamp': ('prediction_timestamp', 'locked_at_utc', 'odds_timestamp', 'created_at', 'scan_timestamp', 'known_start_utc', 'start'),
    'odds_timestamp': ('odds_timestamp', 'price_timestamp', 'last_odds_update', 'last_update'),
    'result_status': ('result_status', 'outcome', 'result', 'win_loss', 'graded_result', 'status'),
    'winner': ('winner', 'actual_winner', 'winning_side', 'final_winner'),
    'final_score': ('final_score', 'score', 'actual_score'),
    'stake_units': ('stake_units', 'stake'),
    'profit_units': ('profit_units', 'units'),
    'decision': ('decision',),
    'confidence_tier': ('confidence_tier', 'confidence', 'confidence_bucket'),
    'api_coverage_score': ('api_coverage_score', 'api_coverage'),
    'books': ('books', 'bookmaker_count', 'source_count', 'bookmakers'),
    'computed_ev_decimal': ('computed_ev_decimal', 'estimated_ev_decimal', 'estimated_ev_value', 'estimated_ev'),
    'closing_decimal_price': ('closing_decimal_price', 'closing_price', 'close_decimal', 'closing_odds'),
}

RESULT_MAP = {
    'won': 'win',
    'win': 'win',
    'w': 'win',
    'correct': 'win',
    'hit': 'win',
    'true': 'win',
    'yes': 'win',
    '1': 'win',
    'lost': 'loss',
    'loss': 'loss',
    'l': 'loss',
    'incorrect': 'loss',
    'miss': 'loss',
    'false': 'loss',
    'no': 'loss',
    '0': 'loss',
    'void': 'void',
    'push': 'void',
    'cancelled': 'void',
    'canceled': 'void',
    'postponed': 'void',
    'abandoned': 'void',
    'pending': 'pending',
    'unknown': 'pending',
    'scheduled': 'pending',
    'live': 'pending',
}


def clean_key(value: Any) -> str:
    return str(value or '').strip().lower().replace(' ', '_').replace('-', '_')


def safe_text(value: Any) -> str:
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in {'nan', 'none', 'null', 'n/a', 'na'}:
        return ''
    return text


def normalized_mapping(row: Mapping[str, Any]) -> dict[str, Any]:
    return {clean_key(key): value for key, value in row.items()}


def first_value(row: Mapping[str, Any], aliases: tuple[str, ...]) -> Any:
    normalized = normalized_mapping(row)
    for alias in aliases:
        value = normalized.get(clean_key(alias))
        if safe_text(value):
            return value
    return ''


def first_text(row: Mapping[str, Any], canonical_name: str) -> str:
    return safe_text(first_value(row, ALIASES.get(canonical_name, (canonical_name,))))


def numeric_value(row: Mapping[str, Any], canonical_name: str) -> float | None:
    return parse_float(first_value(row, ALIASES.get(canonical_name, (canonical_name,))))


def probability_value(row: Mapping[str, Any], canonical_name: str = 'model_probability') -> float | None:
    value = numeric_value(row, canonical_name)
    if value is None:
        return None
    if 1.0 < value <= 100.0:
        value /= 100.0
    if 0.0 < value < 1.0:
        return value
    return None


def result_status(row: Mapping[str, Any]) -> str:
    raw = first_text(row, 'result_status').lower()
    if raw in RESULT_MAP:
        return RESULT_MAP[raw]
    pick = first_text(row, 'prediction').lower()
    winner = first_text(row, 'winner').lower()
    if pick and winner:
        return 'win' if pick == winner else 'loss'
    return raw or 'pending'


def normalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    out = {name: first_text(row, name) for name in ALIASES}
    prob = probability_value(row, 'model_probability')
    if prob is not None:
        out['model_probability'] = round(prob, 6)
    price = numeric_value(row, 'decimal_price')
    if price is not None:
        out['decimal_price'] = round(price, 6)
    coverage = numeric_value(row, 'api_coverage_score')
    if coverage is not None:
        out['api_coverage_score'] = round(coverage / 100.0 if coverage > 1.0 else coverage, 6)
    out['result_status'] = result_status(row)
    return out


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    rows = []
    for raw in frame.to_dict(orient='records'):
        item = dict(raw)
        normalized = normalize_row(raw)
        for key, value in normalized.items():
            if key not in item or not safe_text(item.get(key)):
                item[key] = value
        rows.append(item)
    return pd.DataFrame(rows)
