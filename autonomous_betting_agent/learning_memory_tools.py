from __future__ import annotations

import csv
import io
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

from .learning import GradedPrediction, ProbabilityCalibrator
from .learning_strength import learning_memory_health

PROBABILITY_COLUMNS = (
    'final_probability_value', 'valor_probabilidad_final', 'prob_final', 'probabilidad_final',
    'final_probability', 'calibrated_probability', 'probabilidad_calibrada', 'model_probability_clean',
    'model_probability', 'probabilidad_modelo', 'predicted_probability', 'probabilidad_pronosticada',
    'pick_probability', 'favorite_probability', 'market_probability_value', 'market_probability',
    'probabilidad_mercado', 'prob_mercado', 'market_implied_probability', 'implied_probability',
    'no_vig_probability', 'confidence_probability', 'probability', 'probabilidad', 'prob',
)
RESULT_COLUMNS = ('result_status', 'result', 'resultado', 'outcome', 'win_loss', 'ganada_perdida', 'graded_result', 'status', 'estado', 'final_result', 'w_l', 'wl')
PRICE_COLUMNS = ('best_price', 'mejor_cuota', 'decimal_price', 'sportsbook_odds', 'decimal_odds', 'average_price', 'avg_price', 'odds_at_pick', 'odds', 'cuotas', 'price', 'cuota')
CLOSING_PRICE_COLUMNS = ('closing_price', 'close_price', 'closing_decimal_price', 'closing_odds', 'close_odds', 'clv_close_price')
STAKE_COLUMNS = ('stake_units', 'recommended_stake_units', 'stake', 'units', 'unidad', 'unidades')
PROFIT_COLUMNS = ('profit_units', 'roi_profit_units', 'net_units', 'units_result', 'profit', 'ganancia_unidades')
PICK_COLUMNS = ('prediction', 'prediccion', 'pronostico', 'pick', 'predicted_side', 'predicted_winner', 'favorite', 'selection', 'seleccion', 'favorito')
WINNER_COLUMNS = ('winner', 'ganador', 'actual_winner', 'winning_side', 'final_winner')
EVENT_COLUMNS = ('event', 'evento', 'event_name', 'game', 'partido', 'match', 'fixture')
SPORT_COLUMNS = ('sport', 'deporte', 'sport_title', 'league', 'liga', 'competition', 'competicion')
START_COLUMNS = ('event_start_utc', 'start', 'inicio', 'known_start_utc', 'commence_time', 'event_date', 'date', 'fecha')
CONFIDENCE_COLUMNS = ('agent_decision', 'confidence', 'confianza', 'confidence_bucket', 'read', 'lectura', 'decision', 'confidence_tier')
MARKET_COLUMNS = ('market_type', 'tipo_mercado', 'market', 'mercado', 'prop_type')
BOOKMAKER_COLUMNS = ('bookmaker', 'sportsbook', 'book', 'best_bookmaker', 'casa', 'casa_de_apuestas')
MODEL_VERSION_COLUMNS = ('model_version', 'app_version', 'learning_memory_version', 'settings_hash', 'proof_model_version')


def clean_key(value: Any) -> str:
    text = '' if value is None else str(value)
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r'[^a-zA-Z0-9]+', '_', text.lower().strip())
    return re.sub(r'_+', '_', text).strip('_')


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace('%', '').replace(',', '')
    if not text or text.lower() in {'none', 'null', 'nan', 'unknown', 'n/a', 'na', 'pending'}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def parse_probability(value: Any) -> float | None:
    number = parse_float(value)
    if number is None:
        return None
    if 1.0 < number <= 100.0:
        number /= 100.0
    if 0.0 < number < 1.0:
        return max(0.000001, min(0.999999, number))
    return None


def parse_result(value: Any) -> int | None:
    text = clean_key(value)
    win_words = {'won', 'win', 'w', 'correct', 'hit', 'true', 'yes', '1', 'gano', 'ganada', 'acierto', 'acertado', 'victoria'}
    loss_words = {'lost', 'loss', 'l', 'incorrect', 'miss', 'false', 'no', '0', 'perdio', 'perdida', 'fallo', 'fallado', 'derrota'}
    push_words = {'push', 'void', 'cancelled', 'canceled', 'empate', 'anulada'}
    if text in push_words:
        return None
    if text in win_words:
        return 1
    if text in loss_words:
        return 0
    if any(token in text for token in ('win', 'won', 'correct', 'ganad', 'acert')):
        return 1
    if any(token in text for token in ('loss', 'lost', 'incorrect', 'perdid', 'fall')):
        return 0
    return None


def first_text(row: dict[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = row.get(clean_key(name))
        if value not in (None, ''):
            return str(value).strip()
    return ''


def first_float(row: dict[str, Any], names: tuple[str, ...]) -> float | None:
    for name in names:
        value = parse_float(row.get(clean_key(name)))
        if value is not None:
            return value
    return None


def fallback_probability(row: dict[str, Any], source: str = '') -> tuple[float | None, str]:
    text = ' '.join([source, first_text(row, CONFIDENCE_COLUMNS), first_text(row, ('source', 'note', 'result_note', 'decision_reasons', 'decision_signals'))]).lower()
    if any(token in text for token in ('play_strong', 'jugar_fuerte', 'a+ high', 'high confidence', 'strong_candidate', 'strong candidate')):
        return 0.70, 'fallback_high_confidence'
    if any(token in text for token in ('play_small', 'high', 'alta', 'a strong')):
        return 0.67, 'fallback_high_confidence'
    if any(token in text for token in ('medium', 'media', 'lean', 'b lean', 'watch_only', 'solo_vigilar')):
        return 0.60, 'fallback_medium_confidence'
    if any(token in text for token in ('low', 'baja', 'no_action', 'sin_accion')):
        return 0.52, 'fallback_low_confidence'
    return None, 'missing'


def extract_probability(row: dict[str, Any], source: str = '') -> tuple[float | None, str]:
    for name in PROBABILITY_COLUMNS:
        value = parse_probability(row.get(clean_key(name)))
        if value is not None:
            return value, clean_key(name)
    price = first_float(row, PRICE_COLUMNS)
    if price is not None and price > 1.0:
        return max(0.000001, min(0.999999, 1.0 / price)), 'price_implied'
    return fallback_probability(row, source)


def extract_result(row: dict[str, Any]) -> int | None:
    for name in RESULT_COLUMNS:
        value = parse_result(row.get(clean_key(name)))
        if value is not None:
            return value
    pick = first_text(row, PICK_COLUMNS)
    winner = first_text(row, WINNER_COLUMNS)
    if pick and winner:
        return 1 if clean_key(pick) == clean_key(winner) else 0
    return None


def inferred_profit_units(*, outcome: int, price: float | None, stake: float | None, explicit_profit: float | None) -> float | None:
    if explicit_profit is not None:
        return round(float(explicit_profit), 6)
    stake_value = 1.0 if stake is None or stake <= 0 else float(stake)
    if price is None or price <= 1.0:
        return round(stake_value if outcome == 1 else -stake_value, 6)
    return round((float(price) - 1.0) * stake_value if outcome == 1 else -stake_value, 6)


def clv_metrics(price: float | None, close_price: float | None) -> dict[str, Any]:
    if price is None or close_price is None or price <= 1.0 or close_price <= 1.0:
        return {'closing_price': None, 'clv_decimal_delta': None, 'clv_percent': None, 'beat_close': None}
    return {
        'closing_price': round(float(close_price), 4),
        'clv_decimal_delta': round(float(price) - float(close_price), 6),
        'clv_percent': round((float(price) / float(close_price)) - 1.0, 6),
        'beat_close': bool(float(price) > float(close_price)),
    }


def compact_row(row: dict[str, Any], row_number: int, source: str) -> dict[str, Any] | None:
    probability, probability_source = extract_probability(row, source)
    result = extract_result(row)
    if probability is None or result is None:
        return None
    event = first_text(row, EVENT_COLUMNS) or f'row {row_number}'
    prediction = first_text(row, PICK_COLUMNS)
    start = first_text(row, START_COLUMNS)
    sport = first_text(row, SPORT_COLUMNS)
    market_type = first_text(row, MARKET_COLUMNS)
    bookmaker = first_text(row, BOOKMAKER_COLUMNS)
    price = first_float(row, PRICE_COLUMNS)
    close_price = first_float(row, CLOSING_PRICE_COLUMNS)
    stake = first_float(row, STAKE_COLUMNS)
    explicit_profit = first_float(row, PROFIT_COLUMNS)
    stake_value = 1.0 if stake is None or stake <= 0 else round(float(stake), 6)
    profit_units = inferred_profit_units(outcome=int(result), price=price, stake=stake_value, explicit_profit=explicit_profit)
    books = first_float(row, ('books', 'bookmaker_count', 'source_count', 'bookmakers', 'casas'))
    api_coverage = first_float(row, ('api_coverage_score', 'api_coverage', 'cobertura_api'))
    if api_coverage is not None and api_coverage > 1.0:
        api_coverage /= 100.0
    clv = clv_metrics(price, close_price)
    item = {
        'event': event[:140],
        'start': start[:40],
        'sport': sport[:80],
        'market_type': market_type[:80],
        'bookmaker': bookmaker[:80],
        'prediction': prediction[:100],
        'probability': round(probability, 6),
        'probability_source': probability_source,
        'outcome': int(result),
        'best_price': None if price is None else round(float(price), 4),
        'stake_units': stake_value,
        'profit_units': profit_units,
        'roi': None if profit_units is None or stake_value <= 0 else round(float(profit_units) / stake_value, 6),
        'books': None if books is None else int(max(0, round(float(books)))),
        'api_coverage_score': None if api_coverage is None else round(max(0.0, min(1.0, float(api_coverage))), 6),
        'confidence': first_text(row, CONFIDENCE_COLUMNS)[:60],
        'model_version': first_text(row, MODEL_VERSION_COLUMNS)[:100],
        'source': source[:120],
        'last_seen_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }
    item.update(clv)
    item['error_abs'] = round(abs(item['probability'] - item['outcome']), 6)
    item['dedupe_key'] = '|'.join(part for part in (clean_key(event), clean_key(start[:10]), clean_key(market_type), clean_key(prediction)) if part)
    return item


def read_compact_csv_bytes(data: bytes, source: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    stats = {'input_rows': 0, 'usable_rows': 0, 'missing_probability': 0, 'missing_result': 0, 'fallback_probability_rows': 0, 'price_implied_probability_rows': 0, 'direct_probability_rows': 0, 'wins': 0, 'losses': 0}
    text = data.decode('utf-8-sig', errors='replace')
    rows: list[dict[str, Any]] = []
    for row_number, raw in enumerate(csv.DictReader(io.StringIO(text)), start=2):
        stats['input_rows'] += 1
        row = {clean_key(k): v for k, v in raw.items() if k is not None}
        probability, probability_source = extract_probability(row, source)
        result = extract_result(row)
        if probability is None:
            stats['missing_probability'] += 1
        if result is None:
            stats['missing_result'] += 1
            continue
        if probability is None:
            continue
        item = compact_row(row, row_number, source)
        if item is None:
            continue
        if str(probability_source).startswith('fallback_'):
            stats['fallback_probability_rows'] += 1
        elif probability_source == 'price_implied':
            stats['price_implied_probability_rows'] += 1
        else:
            stats['direct_probability_rows'] += 1
        stats['usable_rows'] += 1
        stats['wins'] += int(item['outcome'] == 1)
        stats['losses'] += int(item['outcome'] == 0)
        rows.append(item)
    return rows, stats


def dedupe_key_for_row(row: dict[str, Any]) -> str:
    return '|'.join(part for part in (clean_key(row.get('event')), clean_key(str(row.get('start') or '')[:10]), clean_key(row.get('market_type')), clean_key(row.get('prediction'))) if part)


def valid_bank_row(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    probability = parse_probability(row.get('probability'))
    result = parse_result(row.get('outcome'))
    if probability is None or result is None:
        return None
    clean = dict(row)
    clean['probability'] = round(probability, 6)
    clean['outcome'] = int(result)
    clean['error_abs'] = round(abs(clean['probability'] - clean['outcome']), 6)
    clean['dedupe_key'] = str(clean.get('dedupe_key') or dedupe_key_for_row(clean)).lower()
    if clean['dedupe_key'].endswith('|0') or clean['dedupe_key'].endswith('|1'):
        clean['dedupe_key'] = dedupe_key_for_row(clean).lower() or clean['dedupe_key']
    stake = parse_float(clean.get('stake_units'))
    clean['stake_units'] = 1.0 if stake is None or stake <= 0 else round(float(stake), 6)
    price = parse_float(clean.get('best_price'))
    profit = parse_float(clean.get('profit_units'))
    if profit is None:
        profit = inferred_profit_units(outcome=int(result), price=price, stake=float(clean['stake_units']), explicit_profit=None)
    clean['profit_units'] = profit
    clean['roi'] = None if profit is None or float(clean['stake_units']) <= 0 else round(float(profit) / float(clean['stake_units']), 6)
    return clean


def row_quality(row: dict[str, Any]) -> int:
    useful_keys = ('event', 'start', 'sport', 'market_type', 'bookmaker', 'prediction', 'probability', 'outcome', 'best_price', 'closing_price', 'profit_units', 'books', 'api_coverage_score', 'confidence', 'model_version')
    return sum(row.get(key) not in (None, '') for key in useful_keys)


def merge_dedupe_rows(existing: list[dict[str, Any]], uploaded: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for raw in existing:
        row = valid_bank_row(raw)
        if row is not None:
            seen[row['dedupe_key']] = row
    for raw in uploaded:
        row = valid_bank_row(raw)
        if row is None:
            continue
        key = row['dedupe_key']
        old = seen.get(key)
        if old is not None:
            duplicates += 1
            if int(old['outcome']) != int(row['outcome']) or row_quality(row) >= row_quality(old):
                seen[key] = row
        else:
            seen[key] = row
    return list(seen.values()), duplicates


def prune_rows(rows: list[dict[str, Any]], max_rows: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(rows) <= max_rows:
        return rows, {'strategy': 'no_pruning_needed', 'rows_before': len(rows), 'rows_after': len(rows), 'rows_pruned': 0}
    ordered = sorted(rows, key=lambda row: (str(row.get('start') or ''), str(row.get('last_seen_utc') or '')), reverse=True)
    pruned = ordered[:max_rows]
    return pruned, {'strategy': 'most_recent_rows', 'rows_before': len(rows), 'rows_after': len(pruned), 'rows_pruned': len(rows) - len(pruned)}


def probability_bucket(probability: float) -> str:
    if probability < 0.40:
        return '0-40%'
    if probability < 0.50:
        return '40-50%'
    if probability < 0.60:
        return '50-60%'
    if probability < 0.70:
        return '60-70%'
    if probability < 0.80:
        return '70-80%'
    if probability < 0.90:
        return '80-90%'
    return '90-100%'


def price_bucket(value: Any) -> str:
    number = parse_float(value)
    if number is None:
        return 'unknown'
    if number < 1.30:
        return '<1.30'
    if number < 1.60:
        return '1.30-1.59'
    if number < 1.90:
        return '1.60-1.89'
    if number < 2.25:
        return '1.90-2.24'
    if number < 3.00:
        return '2.25-2.99'
    return '3.00+'


def books_bucket(value: Any) -> str:
    number = parse_float(value)
    if number is None:
        return 'unknown'
    if number <= 1:
        return '0-1'
    if number <= 3:
        return '2-3'
    if number <= 6:
        return '4-6'
    if number <= 10:
        return '7-10'
    return '11+'


def api_bucket(value: Any) -> str:
    number = parse_float(value)
    if number is None:
        return 'unknown'
    number = max(0.0, min(1.0, number))
    if number >= 0.999:
        return '100%'
    if number >= 0.66:
        return '66-99%'
    if number >= 0.33:
        return '33-65%'
    if number > 0:
        return '1-32%'
    return '0%'


def segment_keys(row: dict[str, Any]) -> list[tuple[str, str, str]]:
    keys: list[tuple[str, str, str]] = []
    sport = str(row.get('sport') or '').strip()
    market_type = str(row.get('market_type') or '').strip()
    bookmaker = str(row.get('bookmaker') or '').strip()
    confidence = str(row.get('confidence') or '').strip()
    probability = float(row['probability'])
    bucket = probability_bucket(probability)
    keys.append(('probability_bucket', bucket, f'Probability bucket: {bucket}'))
    probability_source = str(row.get('probability_source') or '').strip()
    if probability_source:
        keys.append(('probability_source', probability_source, f'Probability source: {probability_source}'))
    if sport:
        keys.append(('sport', sport, f'Sport: {sport}'))
        keys.append(('sport_probability_bucket', f'{sport}|{bucket}', f'{sport} / {bucket}'))
    if market_type:
        keys.append(('market_type', market_type, f'Market: {market_type}'))
        if sport:
            keys.append(('sport_market', f'{sport}|{market_type}', f'{sport} / {market_type}'))
    if bookmaker:
        keys.append(('bookmaker', bookmaker, f'Bookmaker: {bookmaker}'))
    if confidence:
        keys.append(('confidence', confidence, f'Confidence/read: {confidence}'))
    if row.get('best_price') is not None:
        keys.append(('odds_bucket', price_bucket(row.get('best_price')), f'Odds: {price_bucket(row.get("best_price"))}'))
    if row.get('books') is not None:
        bucket_books = books_bucket(row.get('books'))
        keys.append(('books_bucket', bucket_books, f'Books: {bucket_books}'))
    if row.get('api_coverage_score') is not None:
        bucket_api = api_bucket(row.get('api_coverage_score'))
        keys.append(('api_coverage_bucket', bucket_api, f'API coverage: {bucket_api}'))
    return keys


def build_segments(rows: list[dict[str, Any]], min_records: int, max_segments: int) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        for area_type, group_value, label in segment_keys(row):
            key = f'{area_type}:{group_value}'.lower()
            grouped.setdefault(key, {'area_type': area_type, 'group_value': group_value, 'area': label, 'rows': []})['rows'].append(row)
    segments: list[dict[str, Any]] = []
    for item in grouped.values():
        group = item.pop('rows')
        records = len(group)
        if records < min_records:
            continue
        probabilities = [float(row['probability']) for row in group]
        outcomes = [int(row['outcome']) for row in group]
        stakes = [float(row.get('stake_units') or 1.0) for row in group]
        profits = [float(row.get('profit_units') or 0.0) for row in group]
        prices = [parse_float(row.get('best_price')) for row in group]
        prices_clean = [p for p in prices if p is not None]
        clvs = [parse_float(row.get('clv_percent')) for row in group]
        clvs_clean = [c for c in clvs if c is not None]
        beat_close_values = [row.get('beat_close') for row in group if row.get('beat_close') is not None]
        avg_predicted = sum(probabilities) / records
        actual_hit_rate = sum(outcomes) / records
        profit_units = sum(profits)
        stake_units = sum(stakes) or records
        roi = profit_units / stake_units if stake_units else 0.0
        smoothed_hit_rate = (sum(outcomes) + avg_predicted * 8) / (records + 8)
        smoothed_edge = smoothed_hit_rate - avg_predicted
        brier = sum((p - y) ** 2 for p, y in zip(probabilities, outcomes)) / records
        sample_weight = min(1.0, math.log(records + 1) / math.log(51))
        reliability = max(0.05, min(1.0, 0.55 * sample_weight + 0.25 * (1.0 - min(0.40, brier) / 0.40) + 0.20 * min(1.0, abs(roi) / 0.12)))
        importance = (abs(smoothed_edge) + min(0.20, abs(roi))) * sample_weight * (1.0 + min(1.0, records / 30.0))
        if roi <= -0.08 and records >= max(20, min_records):
            action = 'block_or_review'
        elif smoothed_edge < -0.035 or roi < -0.03:
            action = 'lower_trust'
        elif smoothed_edge > 0.035 or roi > 0.04:
            action = 'raise_trust'
        else:
            action = 'watch'
        segments.append({
            **item,
            'records': records,
            'avg_predicted': round(avg_predicted, 6),
            'actual_hit_rate': round(actual_hit_rate, 6),
            'actual_minus_predicted': round(actual_hit_rate - avg_predicted, 6),
            'smoothed_hit_rate': round(smoothed_hit_rate, 6),
            'smoothed_edge': round(smoothed_edge, 6),
            'stake_units': round(stake_units, 6),
            'profit_units': round(profit_units, 6),
            'roi': round(roi, 6),
            'avg_price': None if not prices_clean else round(sum(prices_clean) / len(prices_clean), 6),
            'avg_clv_percent': None if not clvs_clean else round(sum(clvs_clean) / len(clvs_clean), 6),
            'beat_close_rate': None if not beat_close_values else round(sum(bool(v) for v in beat_close_values) / len(beat_close_values), 6),
            'reliability': round(reliability, 6),
            'brier': round(brier, 6),
            'memory_type': item['area_type'],
            'importance': round(importance, 6),
            'action': action,
        })
    segments.sort(key=lambda row: (float(row['importance']), int(row['records'])), reverse=True)
    return segments[:max_segments]


def make_ara_memory_csv(segments: list[dict[str, Any]]) -> str:
    fields = ['area', 'area_type', 'group_value', 'records', 'avg_predicted', 'actual_hit_rate', 'actual_minus_predicted', 'smoothed_hit_rate', 'smoothed_edge', 'stake_units', 'profit_units', 'roi', 'avg_price', 'avg_clv_percent', 'beat_close_rate', 'reliability', 'brier', 'memory_type', 'importance', 'action']
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for segment in segments:
        writer.writerow({field: segment.get(field, '') for field in fields})
    return buffer.getvalue()


def rows_to_graded(rows: list[dict[str, Any]]) -> list[GradedPrediction]:
    return [GradedPrediction(event_name=str(row.get('event') or ''), probability=float(row['probability']), outcome=int(row['outcome']), predicted_side=str(row.get('prediction') or '')) for row in rows]


def calibrator_json(calibrator: ProbabilityCalibrator) -> str:
    return json.dumps(calibrator.to_dict(), indent=2, sort_keys=True) + '\n'


def memory_metrics(rows: list[dict[str, Any]]) -> dict[str, float | int | None]:
    if not rows:
        return {'resolved': 0, 'hit_rate': None, 'avg_predicted': None, 'brier': None, 'wins': 0, 'losses': 0, 'profit_units': 0.0, 'roi': None, 'avg_price': None}
    probabilities = [float(row['probability']) for row in rows]
    outcomes = [int(row['outcome']) for row in rows]
    wins = sum(outcomes)
    stakes = [float(row.get('stake_units') or 1.0) for row in rows]
    profits = [float(row.get('profit_units') or 0.0) for row in rows]
    prices = [parse_float(row.get('best_price')) for row in rows]
    prices_clean = [price for price in prices if price is not None]
    stake_total = sum(stakes) or len(rows)
    profit_total = sum(profits)
    return {
        'resolved': len(rows),
        'hit_rate': wins / len(rows),
        'avg_predicted': sum(probabilities) / len(rows),
        'brier': sum((p - y) ** 2 for p, y in zip(probabilities, outcomes)) / len(rows),
        'wins': wins,
        'losses': len(rows) - wins,
        'profit_units': profit_total,
        'roi': profit_total / stake_total if stake_total else None,
        'avg_price': None if not prices_clean else sum(prices_clean) / len(prices_clean),
    }


def pattern_leaderboards(segments: list[dict[str, Any]], limit: int = 20) -> dict[str, list[dict[str, Any]]]:
    def has_records(row: dict[str, Any]) -> bool:
        return int(row.get('records') or 0) >= 3
    candidates = [row for row in segments if has_records(row)]
    best_roi = sorted(candidates, key=lambda row: (float(row.get('roi') or 0), int(row.get('records') or 0)), reverse=True)[:limit]
    worst_roi = sorted(candidates, key=lambda row: (float(row.get('roi') or 0), -int(row.get('records') or 0)))[:limit]
    best_hit = sorted(candidates, key=lambda row: (float(row.get('actual_hit_rate') or 0), int(row.get('records') or 0)), reverse=True)[:limit]
    reliable = sorted(candidates, key=lambda row: (float(row.get('reliability') or 0), int(row.get('records') or 0)), reverse=True)[:limit]
    return {'best_roi': best_roi, 'worst_roi': worst_roi, 'best_hit_rate': best_hit, 'most_reliable': reliable}


def build_memory_bank(*, compact_rows: list[dict[str, Any]], calibrator: ProbabilityCalibrator, segments: list[dict[str, Any]], parse_stats: dict[str, Any], prune_report: dict[str, Any], mode: str, existing_count: int, uploaded_count: int, duplicates_removed: int) -> dict[str, Any]:
    health = learning_memory_health(compact_rows)
    metrics = memory_metrics(compact_rows)
    return {
        'version': 'learning-memory-bank-v6-roi-clv-adaptive',
        'trained_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'training_mode': mode,
        'dedupe_policy': 'event_start_market_prediction_replaces_corrected_result',
        'summary': {
            'existing_rows_before_upload': existing_count,
            'uploaded_usable_rows': uploaded_count,
            'duplicates_removed': duplicates_removed,
            'rows_after_pruning': len(compact_rows),
            'patterns_saved': len(segments),
            'fallback_probability_rows': int(parse_stats.get('fallback_probability_rows', 0)),
            'price_implied_probability_rows': int(parse_stats.get('price_implied_probability_rows', 0)),
            'direct_probability_rows': int(parse_stats.get('direct_probability_rows', 0)),
            'learning_health_score': health['learning_health_score'],
            'learning_health_tier': health['learning_health_tier'],
            'recommended_learning_action': health['recommended_learning_action'],
            'profit_units': round(float(metrics.get('profit_units') or 0.0), 6),
            'roi': None if metrics.get('roi') is None else round(float(metrics['roi']), 6),
            'avg_price': None if metrics.get('avg_price') is None else round(float(metrics['avg_price']), 6),
        },
        'learning_health': health,
        'parse_stats': parse_stats,
        'prune_report': prune_report,
        'global_calibrator': calibrator.to_dict(),
        'pattern_leaderboards': pattern_leaderboards(segments),
        'patterns': segments,
        'compact_rows': compact_rows,
    }
