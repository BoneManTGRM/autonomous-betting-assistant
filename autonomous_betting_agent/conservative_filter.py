from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from .row_normalizer import safe_text

REPO_ROOT = Path(__file__).resolve().parents[1]
ARA_MEMORY_PATH = REPO_ROOT / 'data' / 'ara_learning_memory.csv'

SPORT_SOCCER_TERMS = ('soccer', 'football', 'fifa', 'world cup', 'uefa', 'liga', 'epl', 'mls')
SPORT_TENNIS_TERMS = ('tennis', 'atp', 'wta', 'halle', 'queen', 'stuttgart', 'berlin', 'wimbledon')
SPORT_BASEBALL_TERMS = ('mlb', 'baseball', 'ncaa baseball')
SPORT_BASKETBALL_TERMS = ('nba', 'wnba', 'basketball', 'ncaab')
GRASS_TERMS = ('grass', 'halle', "queen", 'stuttgart', 'wimbledon', 'mallorca', 'eastbourne')


def _num(value: Any) -> float | None:
    try:
        parsed = float(str(value).replace('%', '').replace(',', '').strip())
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _prob(value: Any) -> float | None:
    parsed = _num(value)
    if parsed is None:
        return None
    if 1.0 < parsed <= 100.0:
        parsed /= 100.0
    return parsed if 0.0 < parsed < 1.0 else None


def _text(row: dict[str, Any], *keys: str) -> str:
    return ' '.join(safe_text(row.get(key)) for key in keys if safe_text(row.get(key))).lower()


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def sport_family(row: dict[str, Any]) -> str:
    text = _text(row, 'sport', 'league', 'sport_title', 'event', 'competition', 'tournament')
    if _contains(text, SPORT_SOCCER_TERMS):
        return 'soccer'
    if _contains(text, SPORT_TENNIS_TERMS):
        return 'tennis'
    if _contains(text, SPORT_BASEBALL_TERMS):
        return 'baseball'
    if _contains(text, SPORT_BASKETBALL_TERMS):
        return 'basketball'
    return 'other'


def probability_bucket(probability: float | None) -> str:
    if probability is None:
        return 'unknown'
    percent = probability * 100.0
    low = int(percent // 10 * 10)
    high = low + 10
    if low < 50:
        return '<50%'
    if low >= 80:
        return '80%+'
    return f'{low}-{high}%'


def projected_margin(row: dict[str, Any]) -> float | None:
    for key in ['projected_score', 'estimated_score', 'predicted_score', 'score_projection', 'projected_final_score']:
        text = safe_text(row.get(key))
        if not text:
            continue
        numbers = [float(value) for value in re.findall(r'\d+(?:\.\d+)?', text)]
        if len(numbers) >= 2:
            return abs(numbers[0] - numbers[1])
    for pair in [('projected_home_score', 'projected_away_score'), ('home_projected_score', 'away_projected_score'), ('predicted_home_score', 'predicted_away_score')]:
        left = _num(row.get(pair[0]))
        right = _num(row.get(pair[1]))
        if left is not None and right is not None:
            return abs(left - right)
    return None


def set_projection_risk(row: dict[str, Any]) -> str:
    text = _text(row, 'projected_score', 'estimated_score', 'predicted_score', 'score_projection')
    if re.search(r'\b2\s*[-:]\s*1\b', text) or re.search(r'\b1\s*[-:]\s*2\b', text):
        return 'projected_2_1_close_match'
    if re.search(r'\b5\s*[-:]\s*4\b', text) or re.search(r'\b4\s*[-:]\s*5\b', text):
        return 'projected_5_4_one_run_game'
    if re.search(r'\b7\s*[-:]\s*6\b', text) or re.search(r'\b6\s*[-:]\s*7\b', text):
        return 'projected_tiebreak_margin'
    return ''


def market_type(row: dict[str, Any]) -> str:
    return safe_text(row.get('market_type') or row.get('market') or row.get('bet_type')).lower()


def edge_value(row: dict[str, Any]) -> float | None:
    edge = _num(row.get('edge_probability'))
    if edge is not None:
        return edge / 100.0 if abs(edge) > 1 else edge
    edge_percent = _num(row.get('edge_percent') or row.get('model_market_edge_percent'))
    if edge_percent is not None:
        return edge_percent / 100.0
    model = _prob(row.get('model_probability') or row.get('model_probability_clean') or row.get('memory_adjusted_probability'))
    implied = _prob(row.get('market_implied_probability'))
    if implied is None:
        price = _num(row.get('decimal_price'))
        if price and price > 1.0:
            implied = 1.0 / price
    if model is not None and implied is not None:
        return model - implied
    return None


def load_memory(path: Path = ARA_MEMORY_PATH) -> pd.DataFrame:
    try:
        if path.exists():
            return pd.read_csv(path)
    except Exception:
        pass
    return pd.DataFrame()


def _memory_rows_for(row: dict[str, Any], memory: pd.DataFrame, probability: float | None) -> pd.DataFrame:
    if memory.empty:
        return pd.DataFrame()
    sport = safe_text(row.get('sport') or row.get('sport_title') or row.get('league'))
    market = safe_text(row.get('market_type') or row.get('market'))
    bucket = probability_bucket(probability)
    candidates: list[pd.DataFrame] = []
    if sport:
        candidates.append(memory[(memory.get('area_type', '').astype(str) == 'sport') & (memory.get('group_value', '').astype(str).str.lower() == sport.lower())])
        candidates.append(memory[(memory.get('area_type', '').astype(str) == 'sport_probability_bucket') & (memory.get('group_value', '').astype(str).str.lower() == f'{sport}|{bucket}'.lower())])
    if market:
        candidates.append(memory[(memory.get('area_type', '').astype(str) == 'market_type') & (memory.get('group_value', '').astype(str).str.lower() == market.lower())])
    if sport and market:
        candidates.append(memory[(memory.get('area_type', '').astype(str) == 'sport_market') & (memory.get('group_value', '').astype(str).str.lower() == f'{sport}|{market}'.lower())])
    candidates.append(memory[(memory.get('area_type', '').astype(str) == 'probability_bucket') & (memory.get('group_value', '').astype(str).str.lower() == bucket.lower())])
    out = pd.concat([c for c in candidates if c is not None and not c.empty], ignore_index=True) if any(c is not None and not c.empty for c in candidates) else pd.DataFrame()
    return out.drop_duplicates() if not out.empty else out


def memory_adjustment(row: dict[str, Any], probability: float | None = None, memory: pd.DataFrame | None = None) -> dict[str, Any]:
    base = probability if probability is not None else _prob(row.get('model_probability') or row.get('model_probability_clean'))
    if base is None:
        return {'raw_model_probability': None, 'memory_adjustment': 0.0, 'memory_adjusted_probability': None, 'memory_influence_strength': 'none', 'memory_reason': 'missing_probability'}
    memory_frame = load_memory() if memory is None else memory
    matched = _memory_rows_for(row, memory_frame, base)
    if matched.empty:
        return {'raw_model_probability': round(base, 6), 'memory_adjustment': 0.0, 'memory_adjusted_probability': round(base, 6), 'memory_influence_strength': 'none', 'memory_reason': 'no_similar_memory'}
    records = pd.to_numeric(matched.get('records', pd.Series(dtype=float)), errors='coerce').fillna(0)
    edge = pd.to_numeric(matched.get('smoothed_edge', matched.get('actual_minus_predicted', pd.Series(dtype=float))), errors='coerce').fillna(0)
    reliability = pd.to_numeric(matched.get('reliability', pd.Series(dtype=float)), errors='coerce').fillna(0.25)
    weights = (records.clip(lower=1) ** 0.5) * reliability.clip(lower=0.1, upper=1.0)
    raw_adjustment = 0.0 if float(weights.sum()) == 0.0 else float((edge * weights).sum() / weights.sum())
    similar = int(records.max()) if not records.empty else 0
    if similar < 10:
        cap = 0.0
        strength = 'visible_only_small_sample'
    elif similar < 25:
        cap = 0.015
        strength = 'weak'
    elif similar < 100:
        cap = 0.03
        strength = 'medium'
    else:
        cap = 0.05
        strength = 'strong'
    adjustment = max(-cap, min(cap, raw_adjustment))
    adjusted = max(0.01, min(0.99, base + adjustment))
    direction = 'lower_trust' if raw_adjustment < -0.005 else 'raise_trust' if raw_adjustment > 0.005 else 'neutral'
    reason = f'{len(matched)} matched memory patterns; max_records={similar}; raw_adjustment={raw_adjustment:.3f}; cap={cap:.3f}; direction={direction}'
    return {'raw_model_probability': round(base, 6), 'memory_adjustment': round(adjustment, 6), 'memory_adjusted_probability': round(adjusted, 6), 'memory_influence_strength': strength, 'memory_direction': direction, 'memory_similar_patterns': int(len(matched)), 'memory_max_records': similar, 'memory_reason': reason}


def conservative_filter(row: dict[str, Any]) -> dict[str, Any]:
    family = sport_family(row)
    model = _prob(row.get('memory_adjusted_probability') or row.get('model_probability_clean') or row.get('model_probability'))
    edge = edge_value(row)
    margin = projected_margin(row)
    projection_risk = set_projection_risk(row)
    market = market_type(row)
    draw_prob = _prob(row.get('draw_probability') or row.get('model_draw_probability') or row.get('draw_prob'))
    text = _text(row, 'sport', 'event', 'tournament', 'surface', 'manual_context_notes')
    reasons: list[str] = []
    volatility = 0.0

    if edge is None:
        reasons.append('missing_edge_over_market')
        volatility += 15
    elif edge < 0.06:
        reasons.append('edge_below_6_percent')
        volatility += 18
    if model is not None and model < 0.58:
        reasons.append('model_probability_below_58_percent')
        volatility += 15

    if projection_risk:
        reasons.append(projection_risk)
        volatility += 15
    if margin is not None:
        if family == 'soccer' and margin <= 1.0:
            reasons.append('soccer_one_goal_margin_draw_risk')
            volatility += 20
        elif family == 'baseball' and margin <= 1.0:
            reasons.append('baseball_one_run_margin')
            volatility += 15
        elif family == 'basketball' and margin <= 5.0:
            reasons.append('basketball_one_score_or_close_margin')
            volatility += 10
        elif family == 'tennis' and margin <= 1.0:
            reasons.append('tennis_close_sets_or_tiebreak_risk')
            volatility += 15

    if family == 'soccer' and ('h2h' in market or 'moneyline' in market or market in {'winner', '1x2', ''}):
        if model is not None and model < 0.60:
            reasons.append('soccer_moneyline_probability_below_60_percent')
        if draw_prob is not None and draw_prob >= 0.25:
            reasons.append('soccer_draw_probability_above_25_percent')
        elif draw_prob is None and margin is not None and margin <= 1.0:
            reasons.append('soccer_draw_probability_missing_with_close_projection')
        volatility += 12

    if family == 'tennis':
        if _contains(text, GRASS_TERMS):
            reasons.append('grass_tennis_surface_volatility')
            volatility += 18
        if projection_risk == 'projected_2_1_close_match':
            reasons.append('tennis_projected_three_sets')
            volatility += 12

    if safe_text(row.get('line_value_signal')).lower() == 'negative' or 'negative_line_movement' in safe_text(row.get('decision_reasons')).lower():
        reasons.append('line_moved_against_pick')
        volatility += 12
    if safe_text(row.get('needed_info')) or safe_text(row.get('data_quality_blockers')):
        reasons.append('missing_required_context_or_data')
        volatility += 15
    if safe_text(row.get('injury_news_risk')).lower() in {'high', 'unclear', 'unknown'}:
        reasons.append('injury_news_unclear')
        volatility += 10

    volatility = max(0.0, min(100.0, volatility))
    if not reasons and edge is not None and model is not None and edge >= 0.08 and model >= 0.64 and volatility <= 15:
        tier = 'A+'
        bettable = 'yes'
        final_action = 'play_strong'
    elif not reasons and edge is not None and model is not None and edge >= 0.06 and model >= 0.60 and volatility <= 25:
        tier = 'A'
        bettable = 'yes_small'
        final_action = 'play_small'
    elif volatility <= 45 and edge is not None and edge >= 0.035:
        tier = 'B'
        bettable = 'track_only'
        final_action = 'watch_only'
    else:
        tier = 'C'
        bettable = 'no'
        final_action = 'no_action'

    return {
        'volatility_score': round(volatility, 3),
        'draw_risk': 'high' if any('draw' in reason for reason in reasons) else 'low',
        'surface_risk': 'high' if any('grass_tennis' in reason for reason in reasons) else 'low',
        'close_margin_risk': 'high' if any(term in '|'.join(reasons) for term in ['margin', '2_1', '5_4', 'tiebreak']) else 'low',
        'conservative_confidence_tier': tier,
        'bettable_yes_no': bettable,
        'conservative_action': final_action,
        'reason_for_downgrade': ' | '.join(dict.fromkeys(reasons)),
    }


def apply_conservative_filter(row: dict[str, Any]) -> dict[str, Any]:
    memory = memory_adjustment(row)
    combined = dict(row)
    combined.update(memory)
    filt = conservative_filter(combined)
    combined.update(filt)
    return {**memory, **filt}


def enrich_conservative_frame(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    data = pd.DataFrame(frame) if isinstance(frame, list) else frame
    if data is None or data.empty:
        return pd.DataFrame()
    rows = []
    for row in data.to_dict(orient='records'):
        item = dict(row)
        item.update(apply_conservative_filter(item))
        rows.append(item)
    return pd.DataFrame(rows)
