from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd

from .row_normalizer import normalize_frame, probability_value, result_status, safe_text

PUBLIC_COLUMNS = [
    'proof_id', 'locked_at_utc', 'event_start_utc', 'event', 'sport', 'market_type',
    'prediction', 'decimal_price', 'bookmaker', 'odds_source', 'stake_units', 'public_confidence',
    'public_reason', 'result_status', 'profit_units',
]
PRIVATE_COLUMNS = [
    'proof_id', 'locked_at_utc', 'event_start_utc', 'event', 'sport', 'sport_key',
    'market_type', 'prediction', 'model_probability', 'decimal_price', 'implied_probability',
    'model_edge', 'bookmaker', 'odds_source', 'agent_decision', 'agent_score', 'scanner_strength_score',
    'stake_units', 'kelly_fraction', 'proof_hash', 'proof_status', 'result_status',
    'profit_units',
]
REQUIRED_OFFICIAL_LOCK_FIELDS = ['event', 'prediction', 'model_probability', 'decimal_price']


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def parse_datetime_utc(value: Any) -> datetime | None:
    text = safe_text(value)
    if not text:
        return None
    try:
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def decimal_to_implied(decimal_price: Any) -> float | None:
    try:
        price = float(decimal_price)
    except (TypeError, ValueError):
        return None
    if price <= 1.0:
        return None
    return round(1.0 / price, 6)


def bookmaker_or_source(row: Mapping[str, Any]) -> str:
    return safe_text(row.get('bookmaker')) or safe_text(row.get('odds_source')) or safe_text(row.get('source'))


def model_edge(row: Mapping[str, Any]) -> float | None:
    probability = probability_value(row, 'model_probability')
    implied = decimal_to_implied(row.get('decimal_price'))
    if probability is None or implied is None:
        return None
    return round(probability - implied, 6)


def kelly_fraction(probability: float | None, decimal_price: float | None) -> float:
    if probability is None or decimal_price is None or decimal_price <= 1.0:
        return 0.0
    b = decimal_price - 1.0
    q = 1.0 - probability
    fraction = (b * probability - q) / b
    return round(max(0.0, fraction), 6)


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def recommended_stake_units(row: Mapping[str, Any], *, max_units: float = 2.0, risk_multiplier: float = 0.25) -> float:
    probability = probability_value(row, 'model_probability')
    price = _safe_float(row.get('decimal_price'))
    fraction = kelly_fraction(probability, price)
    agent_decision = safe_text(row.get('agent_decision') or row.get('decision')).lower()
    agent_score = _safe_float(row.get('agent_score')) or 0.0
    scanner_score = _safe_float(row.get('scanner_strength_score')) or 0.0
    base_units = fraction * 10.0 * risk_multiplier
    if agent_decision == 'play_strong':
        base_units *= 1.25
    elif agent_decision == 'play_small':
        base_units *= 0.75
    elif agent_decision:
        base_units *= 0.25
    if agent_score >= 80:
        base_units *= 1.15
    if scanner_score >= 80:
        base_units *= 1.10
    if base_units <= 0 and agent_decision in {'play_strong', 'play_small'}:
        base_units = 0.25
    return round(max(0.0, min(float(max_units), base_units)), 2)


def proof_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        'locked_at_utc': safe_text(row.get('locked_at_utc')),
        'event_start_utc': safe_text(row.get('event_start_utc')),
        'event': safe_text(row.get('event')),
        'sport': safe_text(row.get('sport')),
        'market_type': safe_text(row.get('market_type')),
        'prediction': safe_text(row.get('prediction')),
        'model_probability': safe_text(row.get('model_probability')),
        'decimal_price': safe_text(row.get('decimal_price')),
        'bookmaker': bookmaker_or_source(row),
        'odds_source': safe_text(row.get('odds_source')),
        'agent_decision': safe_text(row.get('agent_decision') or row.get('decision')),
        'stake_units': safe_text(row.get('stake_units')),
    }
    return payload


def proof_hash(row: Mapping[str, Any]) -> str:
    payload = proof_payload(row)
    body = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


def proof_id_from_hash(hash_value: str) -> str:
    return f'OLP-{hash_value[:12].upper()}'


def lock_status(row: Mapping[str, Any], locked_at: datetime | None = None) -> str:
    start = parse_datetime_utc(row.get('event_start_utc'))
    locked = locked_at or parse_datetime_utc(row.get('locked_at_utc'))
    if start is None:
        return 'locked_without_verified_start'
    if locked is None:
        return 'missing_lock_time'
    if locked < start:
        return 'locked_before_start'
    return 'invalid_after_start'


def lock_blockers(row: Mapping[str, Any], *, require_future: bool = False, locked_at: datetime | None = None) -> list[str]:
    blockers: list[str] = []
    for field in REQUIRED_OFFICIAL_LOCK_FIELDS:
        if not safe_text(row.get(field)):
            blockers.append(f'missing_{field}')
    if not bookmaker_or_source(row):
        blockers.append('missing_bookmaker_or_odds_source')
    if probability_value(row, 'model_probability') is None:
        blockers.append('invalid_model_probability')
    if decimal_to_implied(row.get('decimal_price')) is None:
        blockers.append('invalid_decimal_price')
    status = lock_status(row, locked_at=locked_at)
    if require_future and status != 'locked_before_start':
        blockers.append(status)
    return sorted(set(blockers))


def _decision_candidate(row: Mapping[str, Any], *, include_watch: bool) -> bool:
    decision = safe_text(row.get('agent_decision') or row.get('decision')).lower()
    lock_ready = safe_text(row.get('lock_ready')).lower() in {'true', '1', 'yes', 'y'}
    if lock_ready or decision in {'play_strong', 'play_small'}:
        return True
    if include_watch:
        if decision in {'watch_only', 'watch'}:
            return True
        return bool(safe_text(row.get('event')) and safe_text(row.get('prediction')))
    return False


def prepare_lock_candidates(
    frame: pd.DataFrame | list[dict[str, Any]],
    *,
    include_watch: bool = False,
    strict: bool = False,
    require_future: bool = False,
) -> pd.DataFrame:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    normalized = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if normalized.empty:
        return pd.DataFrame()
    now = datetime.now(timezone.utc)
    rows = []
    for row in normalized.to_dict(orient='records'):
        if not _decision_candidate(row, include_watch=include_watch):
            continue
        item = dict(row)
        if not safe_text(item.get('agent_decision') or item.get('decision')) and include_watch:
            item['agent_decision'] = 'watch_only'
        if not safe_text(item.get('bookmaker')) and bookmaker_or_source(item):
            item['bookmaker'] = bookmaker_or_source(item)
        item['implied_probability'] = decimal_to_implied(item.get('decimal_price'))
        item['model_edge'] = model_edge(item)
        item['stake_units'] = recommended_stake_units(item)
        item['prelock_status'] = lock_status(item, locked_at=now)
        blockers = lock_blockers(item, require_future=require_future, locked_at=now)
        item['lock_blockers'] = '; '.join(blockers)
        item['official_lock_ready'] = not blockers
        item['public_confidence'] = public_confidence(item)
        item['public_reason'] = public_reason(item)
        if strict and blockers:
            continue
        rows.append(item)
    return pd.DataFrame(rows)


def lock_rows(
    frame: pd.DataFrame | list[dict[str, Any]],
    *,
    analyst: str = '',
    max_units: float = 2.0,
    include_watch: bool = False,
    strict: bool = False,
    require_future: bool = False,
) -> pd.DataFrame:
    candidates = prepare_lock_candidates(frame, include_watch=include_watch, strict=strict, require_future=require_future)
    if candidates.empty:
        return pd.DataFrame()
    locked_time = now_utc()
    locked_dt = parse_datetime_utc(locked_time)
    rows = []
    for row in candidates.to_dict(orient='records'):
        item = dict(row)
        if not safe_text(item.get('bookmaker')) and bookmaker_or_source(item):
            item['bookmaker'] = bookmaker_or_source(item)
        if strict:
            blockers = lock_blockers(item, require_future=require_future, locked_at=locked_dt)
            if blockers:
                continue
        item['locked_at_utc'] = locked_time
        item['analyst'] = analyst or 'private_analyst'
        item['stake_units'] = recommended_stake_units(item, max_units=max_units)
        item['implied_probability'] = decimal_to_implied(item.get('decimal_price'))
        item['model_edge'] = model_edge(item)
        price = _safe_float(item.get('decimal_price'))
        item['kelly_fraction'] = kelly_fraction(probability_value(item, 'model_probability'), price)
        item['proof_status'] = lock_status(item, locked_at=locked_dt)
        item['lock_blockers'] = ''
        item['official_lock_ready'] = True
        item['public_confidence'] = public_confidence(item)
        item['public_reason'] = public_reason(item)
        item['result_status'] = result_status(item)
        item['profit_units'] = profit_units(item)
        item['proof_hash'] = proof_hash(item)
        item['proof_id'] = proof_id_from_hash(item['proof_hash'])
        rows.append(item)
    return pd.DataFrame(rows)


def profit_units(row: Mapping[str, Any]) -> float | None:
    status = result_status(row)
    if status not in {'win', 'loss', 'void'}:
        return None
    stake = _safe_float(row.get('stake_units')) or 1.0
    price = _safe_float(row.get('decimal_price'))
    if status == 'void':
        return 0.0
    if status == 'loss':
        return round(-stake, 4)
    if price is None or price <= 1.0:
        return None
    return round(stake * (price - 1.0), 4)


def update_profit_columns(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    normalized = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if normalized.empty:
        return pd.DataFrame()
    rows = []
    for row in normalized.to_dict(orient='records'):
        item = dict(row)
        if not safe_text(item.get('bookmaker')) and bookmaker_or_source(item):
            item['bookmaker'] = bookmaker_or_source(item)
        item['result_status'] = result_status(item)
        item['profit_units'] = profit_units(item)
        item['implied_probability'] = decimal_to_implied(item.get('decimal_price'))
        item['model_edge'] = model_edge(item)
        rows.append(item)
    return pd.DataFrame(rows)


def summarize_locked_picks(frame: pd.DataFrame | list[dict[str, Any]]) -> dict[str, Any]:
    enriched = update_profit_columns(frame)
    if enriched.empty:
        return {
            'locked_picks': 0, 'resolved_picks': 0, 'wins': 0, 'losses': 0,
            'pushes': 0, 'hit_rate': None, 'total_staked_units': 0.0,
            'profit_units': 0.0, 'roi': None, 'avg_decimal_price': None,
            'avg_model_probability': None, 'avg_edge': None, 'valid_before_start': 0,
        }
    status = enriched['result_status'].astype(str).str.lower() if 'result_status' in enriched else pd.Series(dtype=str)
    resolved_mask = status.isin(['win', 'loss'])
    wins = int(status.eq('win').sum())
    losses = int(status.eq('loss').sum())
    pushes = int(status.isin(['void', 'push']).sum())
    resolved = wins + losses
    stake = pd.to_numeric(enriched.get('stake_units', pd.Series(dtype=float)), errors='coerce').fillna(1.0)
    staked_resolved = float(stake[resolved_mask].sum()) if len(stake) == len(enriched) else 0.0
    profit = pd.to_numeric(enriched.get('profit_units', pd.Series(dtype=float)), errors='coerce').fillna(0.0)
    profit_total = float(profit.sum())
    prices = pd.to_numeric(enriched.get('decimal_price', pd.Series(dtype=float)), errors='coerce').dropna()
    probs = pd.to_numeric(enriched.get('model_probability', pd.Series(dtype=float)), errors='coerce').dropna()
    probs = probs.where(probs <= 1.0, probs / 100.0)
    edges = pd.to_numeric(enriched.get('model_edge', pd.Series(dtype=float)), errors='coerce').dropna()
    proof_status = enriched.get('proof_status', pd.Series(dtype=str)).astype(str)
    return {
        'locked_picks': int(len(enriched)),
        'resolved_picks': resolved,
        'wins': wins,
        'losses': losses,
        'pushes': pushes,
        'hit_rate': None if resolved == 0 else round(wins / resolved, 6),
        'total_staked_units': round(staked_resolved, 4),
        'profit_units': round(profit_total, 4),
        'roi': None if staked_resolved <= 0 else round(profit_total / staked_resolved, 6),
        'avg_decimal_price': None if prices.empty else round(float(prices.mean()), 4),
        'avg_model_probability': None if probs.empty else round(float(probs.mean()), 6),
        'avg_edge': None if edges.empty else round(float(edges.mean()), 6),
        'valid_before_start': int(proof_status.eq('locked_before_start').sum()),
    }


def performance_by_group(frame: pd.DataFrame | list[dict[str, Any]], group_col: str = 'sport') -> pd.DataFrame:
    enriched = update_profit_columns(frame)
    if enriched.empty or group_col not in enriched.columns:
        return pd.DataFrame()
    rows = []
    for value, group in enriched.groupby(group_col, dropna=False):
        summary = summarize_locked_picks(group)
        summary[group_col] = value
        rows.append(summary)
    out = pd.DataFrame(rows)
    ordered = [group_col, 'locked_picks', 'resolved_picks', 'wins', 'losses', 'hit_rate', 'profit_units', 'roi', 'avg_decimal_price', 'avg_edge']
    return out[[col for col in ordered if col in out.columns]]


def public_confidence(row: Mapping[str, Any]) -> str:
    decision = safe_text(row.get('agent_decision') or row.get('decision')).lower()
    edge = model_edge(row)
    score = _safe_float(row.get('agent_score')) or 0.0
    if decision == 'play_strong' and edge is not None and edge >= 0.075 and score >= 75:
        return 'Premium'
    if decision in {'play_strong', 'play_small'} and edge is not None and edge >= 0.035:
        return 'Qualified'
    return 'Watch'


def public_reason(row: Mapping[str, Any]) -> str:
    parts: list[str] = []
    edge = model_edge(row)
    if edge is not None:
        parts.append(f'model edge {edge * 100:.1f}%')
    book = bookmaker_or_source(row)
    if book:
        parts.append(f'price/source: {book}')
    decision = safe_text(row.get('agent_decision') or row.get('decision'))
    if decision:
        parts.append(decision.replace('_', ' '))
    blockers = safe_text(row.get('lock_blockers'))
    if blockers:
        parts.append(f'blocked: {blockers}')
    return '; '.join(parts) or 'qualified by model review'


def client_view(frame: pd.DataFrame | list[dict[str, Any]], *, public_only: bool = True) -> pd.DataFrame:
    raw = update_profit_columns(frame)
    if raw.empty:
        return pd.DataFrame()
    columns = PUBLIC_COLUMNS if public_only else PRIVATE_COLUMNS
    for column in columns:
        if column not in raw.columns:
            raw[column] = ''
    return raw[columns]


def daily_report(frame: pd.DataFrame | list[dict[str, Any]], *, language: str = 'English', public_only: bool = True, max_picks: int = 8) -> str:
    view = client_view(frame, public_only=public_only)
    if view.empty:
        return 'No qualified locked picks are available.' if language != 'Español' else 'No hay picks bloqueados calificados disponibles.'
    view = view.head(max_picks)
    summary = summarize_locked_picks(frame)
    spanish = language == 'Español'
    lines = []
    if spanish:
        lines.append('Reporte de Picks Bloqueados')
        lines.append(f"Picks bloqueados: {summary['locked_picks']} | Resueltos: {summary['resolved_picks']} | Récord: {summary['wins']}-{summary['losses']}")
        roi = summary['roi']
        lines.append(f"ROI: {'pendiente' if roi is None else f'{roi * 100:.1f}%'} | Unidades: {summary['profit_units']}")
        lines.append('')
        for _, row in view.iterrows():
            lines.append(f"• {safe_text(row.get('event'))} — {safe_text(row.get('prediction'))} @ {safe_text(row.get('decimal_price'))} ({safe_text(row.get('public_confidence'))})")
            reason = safe_text(row.get('public_reason'))
            if reason:
                lines.append(f"  Razón: {reason}")
            proof = safe_text(row.get('proof_id'))
            if proof:
                lines.append(f"  Proof ID: {proof}")
    else:
        lines.append('Locked Picks Report')
        lines.append(f"Locked picks: {summary['locked_picks']} | Resolved: {summary['resolved_picks']} | Record: {summary['wins']}-{summary['losses']}")
        roi = summary['roi']
        lines.append(f"ROI: {'pending' if roi is None else f'{roi * 100:.1f}%'} | Units: {summary['profit_units']}")
        lines.append('')
        for _, row in view.iterrows():
            lines.append(f"• {safe_text(row.get('event'))} — {safe_text(row.get('prediction'))} @ {safe_text(row.get('decimal_price'))} ({safe_text(row.get('public_confidence'))})")
            reason = safe_text(row.get('public_reason'))
            if reason:
                lines.append(f"  Reason: {reason}")
            proof = safe_text(row.get('proof_id'))
            if proof:
                lines.append(f"  Proof ID: {proof}")
    return '\n'.join(lines)
