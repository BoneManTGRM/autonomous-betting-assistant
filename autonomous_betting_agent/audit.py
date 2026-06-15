from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping

import pandas as pd

WIN_VALUES = {'win', 'won', 'w', 'correct', 'hit', 'yes', 'true', '1'}
LOSS_VALUES = {'loss', 'lost', 'l', 'incorrect', 'miss', 'no', 'false', '0'}
VOID_VALUES = {'void', 'push', 'cancelled', 'canceled', 'postponed', 'abandoned', 'no action', 'no_action'}
PENDING_VALUES = {'', 'unknown', 'pending', 'ungraded', 'live', 'scheduled', 'future', 'tbd', 'na', 'n/a', 'none', 'null'}
REVIEW_TERMS = ('review', 'mismatch', 'wrong sport', 'wrong format', 'format mismatch', 'bad opponent', 'cannot confirm', 'not clean', 'manual check')


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def clean_text(value: Any) -> str:
    return ' '.join(str(value or '').lower().replace('-', ' ').replace('_', ' ').strip().split())


def parse_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if number == number else None
    text = str(value).strip().replace(',', '')
    if not text:
        return None
    if text.endswith('%'):
        text = text[:-1].strip()
        try:
            return float(text) / 100.0
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


def truthy(value: Any) -> bool:
    return clean_text(value) in {'true', '1', 'yes', 'y', 'passed', 'pass'}


def decimal_to_american(decimal_price: Any) -> int | None:
    price = parse_float(decimal_price)
    if price is None or price <= 1.0:
        return None
    return int(round((price - 1.0) * 100.0)) if price >= 2.0 else int(round(-100.0 / (price - 1.0)))


def implied_probability_from_decimal(decimal_price: Any) -> float | None:
    price = parse_float(decimal_price)
    if price is None or price <= 1.0:
        return None
    return round(1.0 / price, 6)


def fair_decimal_price(probability: Any) -> float | None:
    prob = parse_float(probability)
    if prob is None or prob <= 0.0 or prob >= 1.0:
        return None
    return round(1.0 / prob, 4)


def normalize_result_status(value: Any) -> str:
    text = clean_text(value)
    if text in WIN_VALUES:
        return 'win'
    if text in LOSS_VALUES:
        return 'loss'
    if text in VOID_VALUES:
        return 'void'
    if text in PENDING_VALUES:
        return 'pending'
    if any(term in text for term in REVIEW_TERMS):
        return 'review_needed'
    return 'pending'


def result_status_from_row(row: Mapping[str, Any]) -> str:
    for key in ('win_loss', 'pick_result', 'grade', 'graded_result', 'result_status', 'outcome', 'status'):
        if key in row:
            status = normalize_result_status(row.get(key))
            if status != 'pending':
                return status
    return 'pending'


def clean_grading_status(row: Mapping[str, Any]) -> str:
    status = result_status_from_row(row)
    note_text = clean_text(' '.join(str(row.get(key, '')) for key in ('grade_note', 'grading_note', 'result_note', 'review_note', 'notes', 'note', 'warning', 'warnings', 'fusion_warning', 'status')))
    if any(term in note_text for term in REVIEW_TERMS) or status == 'review_needed':
        return 'review_needed'
    if status == 'void':
        return 'void'
    if status in {'win', 'loss'}:
        return 'graded_clean'
    return 'pending'


def profit_units(result: Any, decimal_price: Any, stake_units: Any = 1.0) -> float | None:
    stake = parse_float(stake_units) or 1.0
    price = parse_float(decimal_price)
    status = normalize_result_status(result)
    if status == 'win':
        return None if price is None or price <= 1.0 else round(stake * (price - 1.0), 6)
    if status == 'loss':
        return round(-stake, 6)
    if status == 'void':
        return 0.0
    return None


def _first(row: Mapping[str, Any], names: Iterable[str]) -> Any:
    lowered = {str(key).lower().replace(' ', '_').replace('-', '_'): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.lower().replace(' ', '_').replace('-', '_'))
        if value not in (None, ''):
            return value
    return ''


def _decimal_price_from_row(row: Mapping[str, Any]) -> float | None:
    for key in ('decimal_price', 'best_price', 'average_price', 'price', 'odds', 'closing_decimal_price'):
        parsed = parse_float(_first(row, (key,)))
        if parsed is not None and parsed > 1.0:
            return parsed
    return None


def confidence_tier(row: Mapping[str, Any]) -> str:
    if truthy(row.get('duplicate_event_pick')):
        return 'No Bet'
    if clean_grading_status(row) == 'review_needed':
        return 'Watch Only'
    final_probability = parse_float(_first(row, ('final_probability_value', 'model_probability', 'probability')))
    reliability = parse_float(_first(row, ('reliability_score', 'reliability')))
    odds_quality = parse_float(_first(row, ('odds_quality_score', 'quality_score')))
    if reliability is None or reliability <= 0.0:
        reliability = odds_quality or 0.0
    books = int(parse_float(_first(row, ('books', 'bookmaker_count'))) or 0)
    ev = parse_float(_first(row, ('estimated_ev_value', 'estimated_ev_decimal', 'computed_ev_decimal', 'ev')))
    coverage = parse_float(_first(row, ('api_coverage_score',))) or 0.0
    confidence = clean_text(_first(row, ('confidence',)))
    is_high = confidence in {'high', 'alta', 'a', 'a+'}
    has_price = _decimal_price_from_row(row) is not None
    if not has_price:
        return 'Watch Only'
    if truthy(row.get('target_70_mode')) and is_high and reliability >= 95.0 and books >= 4 and (ev or 0.0) >= 0.0 and coverage >= 0.66:
        return 'A+ High Confidence'
    if is_high and reliability >= 90.0 and books >= 4 and (ev or 0.0) >= 0.0:
        return 'A Strong'
    if reliability >= 80.0 and books >= 2 and final_probability is not None and final_probability >= 0.58:
        return 'B Lean'
    return 'Watch Only'


def audit_inclusion(row: Mapping[str, Any]) -> str:
    grading = clean_grading_status(row)
    if truthy(row.get('duplicate_event_pick')):
        return 'excluded_duplicate'
    if grading == 'graded_clean':
        return 'official'
    if grading == 'void':
        return 'excluded_void'
    if grading == 'review_needed':
        return 'excluded_review_needed'
    return 'pending_until_final'


def enrich_prediction_row(row: Mapping[str, Any], *, prediction_timestamp: str | None = None, stake_units: float = 1.0) -> dict[str, Any]:
    enriched = dict(row)
    decimal_price = _decimal_price_from_row(enriched)
    timestamp = str(_first(enriched, ('odds_timestamp', 'prediction_timestamp', 'created_at', 'scan_timestamp')) or prediction_timestamp or utc_now_iso())
    status = result_status_from_row(enriched)
    stake = parse_float(_first(enriched, ('stake_units', 'stake'))) or stake_units
    profit = profit_units(status, decimal_price, stake)
    closing_price = parse_float(_first(enriched, ('closing_decimal_price', 'closing_price')))
    enriched.update({
        'prediction_timestamp': str(_first(enriched, ('prediction_timestamp',)) or timestamp),
        'odds_timestamp': str(_first(enriched, ('odds_timestamp',)) or timestamp),
        'decimal_price': decimal_price,
        'american_odds': decimal_to_american(decimal_price),
        'implied_probability': implied_probability_from_decimal(decimal_price),
        'break_even_win_rate': implied_probability_from_decimal(decimal_price),
        'fair_decimal_price': fair_decimal_price(_first(enriched, ('final_probability_value', 'model_probability', 'probability'))),
        'stake_units': stake,
        'result_status': status,
        'clean_grading_status': clean_grading_status(enriched),
        'profit_units': profit,
        'roi_percent': None if profit is None or stake <= 0.0 else round((profit / stake) * 100.0, 2),
        'closing_line_value_decimal': None if decimal_price is None or closing_price is None else round(decimal_price - closing_price, 6),
    })
    enriched['confidence_tier'] = confidence_tier(enriched)
    enriched['audit_inclusion'] = audit_inclusion(enriched)
    return enriched


def enrich_prediction_frame(frame: pd.DataFrame, *, prediction_timestamp: str | None = None, stake_units: float = 1.0) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    return pd.DataFrame([enrich_prediction_row(row, prediction_timestamp=prediction_timestamp, stake_units=stake_units) for row in frame.to_dict(orient='records')])


def audit_dashboard_metrics(rows: pd.DataFrame | Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows))
    enriched = enrich_prediction_frame(frame) if not frame.empty else pd.DataFrame()
    if enriched.empty:
        return {'total_rows': 0, 'official_graded': 0, 'wins': 0, 'losses': 0, 'win_rate': None, 'units': 0.0, 'roi_percent': None, 'pending': 0, 'review_needed': 0, 'void': 0, 'a_plus_count': 0}
    official = enriched[enriched['audit_inclusion'] == 'official']
    wins = int((official['result_status'] == 'win').sum()) if not official.empty else 0
    losses = int((official['result_status'] == 'loss').sum()) if not official.empty else 0
    graded = wins + losses
    units = float(official['profit_units'].dropna().sum()) if not official.empty and 'profit_units' in official else 0.0
    staked = float(official['stake_units'].dropna().sum()) if not official.empty and 'stake_units' in official else 0.0
    return {'total_rows': int(len(enriched)), 'official_graded': int(graded), 'wins': wins, 'losses': losses, 'win_rate': None if graded == 0 else round(wins / graded, 6), 'units': round(units, 6), 'roi_percent': None if staked <= 0.0 else round((units / staked) * 100.0, 2), 'pending': int((enriched['clean_grading_status'] == 'pending').sum()), 'review_needed': int((enriched['clean_grading_status'] == 'review_needed').sum()), 'void': int((enriched['clean_grading_status'] == 'void').sum()), 'a_plus_count': int((enriched['confidence_tier'] == 'A+ High Confidence').sum())}


def _pick_outcome(event: Any, pick_name: str) -> Any | None:
    outcomes = list(getattr(event, 'outcomes', []) or [])
    if not outcomes:
        return None
    pick_clean = clean_text(pick_name)
    exact = [outcome for outcome in outcomes if clean_text(getattr(outcome, 'name', '')) == pick_clean]
    if exact:
        return exact[0]
    return max(outcomes, key=lambda outcome: SequenceMatcher(None, pick_clean, clean_text(getattr(outcome, 'name', ''))).ratio())


def live_event_audit_context(event: Any, *, pick_name: str, timestamp: str | None = None) -> dict[str, Any]:
    outcome = _pick_outcome(event, pick_name)
    decimal_price = None
    bookmaker = ''
    if outcome is not None:
        decimal_price = parse_float(getattr(outcome, 'best_price', None) or getattr(outcome, 'average_price', None))
        bookmaker = str(getattr(outcome, 'best_bookmaker', '') or '')
    snapshot_time = str(getattr(event, 'odds_snapshot_timestamp', '') or timestamp or utc_now_iso())
    return {'prediction_timestamp': snapshot_time, 'odds_timestamp': snapshot_time, 'odds_source': 'the_odds_api', 'decimal_price': decimal_price, 'american_odds': decimal_to_american(decimal_price), 'best_bookmaker': bookmaker, 'bookmaker': bookmaker, 'implied_probability': implied_probability_from_decimal(decimal_price), 'break_even_win_rate': implied_probability_from_decimal(decimal_price), 'stake_units': 1.0, 'result_status': 'pending', 'clean_grading_status': 'pending', 'profit_units': None, 'roi_percent': None, 'audit_inclusion': 'pending_until_final', 'audit_schema_version': 'audit-v1'}


def install_live_api_audit_context(builder_cls: Any) -> None:
    if getattr(builder_cls, '_audit_context_installed', False):
        return
    original = builder_cls.context_for_event

    def patched_context_for_event(self: Any, event: Any, *, pick_name: str) -> dict[str, Any]:
        context = original(self, event, pick_name=pick_name)
        context.update(live_event_audit_context(event, pick_name=pick_name))
        return context

    builder_cls.context_for_event = patched_context_for_event
    builder_cls._audit_context_installed = True
