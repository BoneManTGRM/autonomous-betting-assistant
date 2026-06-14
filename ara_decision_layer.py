# ara_decision_layer.py
# Drop-in decision layer for ARA betting predictions.
# Usage in Streamlit:
#   from ara_decision_layer import apply_ara_decision_layer
#   df = apply_ara_decision_layer(df)
# Then display columns: ara_live_decision, ara_live_stake_units, ara_risk_flags, ara_decision_reason.

import math
import pandas as pd


def _parse_percent(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    has_percent = '%' in text
    text = text.replace('%', '').replace(',', '')
    try:
        number = float(text)
    except ValueError:
        return None
    if has_percent or number > 1:
        number /= 100.0
    return max(0.0, min(1.0, number))


def _parse_float(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().replace(',', '')
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_int(value):
    number = _parse_float(value)
    return None if number is None else int(round(number))


def _fmt_pct(value):
    return '' if value is None else f'{value * 100:.1f}%'


def _fmt_dec(value):
    return '' if value is None else f'{value:.3f}'


def _sport_group(sport):
    s = str(sport or '').lower()
    if any(x in s for x in ['mlb', 'milb', 'baseball']):
        return 'Baseball'
    if any(x in s for x in ['nba', 'wnba']):
        return 'Basketball'
    if any(x in s for x in ['mma', 'boxing', 'ufc']):
        return 'Combat'
    if any(x in s for x in ['ncaaf', 'nfl', 'ufl']):
        return 'American football'
    if any(x in s for x in ['wta', 'atp', 'tennis']):
        return 'Tennis'
    if any(x in s for x in ['afl', 'nrl', 'rugby']):
        return 'AFL/NRL/Rugby'
    if any(x in s for x in ['fifa', 'premier', 'primera', 'liga', 'league', 'veikkausliiga', 'serie', 'bundesliga', 'mls', 'soccer', 'football']):
        return 'Soccer'
    return 'Other'


def _record_key(row):
    return ' | '.join(str(row.get(k, '')).strip() for k in ('Event', 'Start', 'Prediction'))


def _risk_flags(row):
    flags = []
    classification = str(row.get('Classification', '') or '').strip().title()
    sg = _sport_group(row.get('Sport'))
    market_p = _parse_percent(row.get('Market probability'))
    draw_p = _parse_percent(row.get('Draw probability'))
    data_quality = _parse_float(row.get('Data quality'))
    risk_penalty = _parse_float(row.get('Risk penalty'))
    price = _parse_float(row.get('Best price'))
    books = _parse_int(row.get('Books'))
    implied = (1.0 / price) if price and price > 0 else None
    proxy_edge = (market_p - implied) if market_p is not None and implied is not None else None

    if classification == 'Avoid':
        flags.append('classification_avoid')
    elif classification == 'Watch':
        flags.append('watch_track_only')

    if data_quality is None:
        flags.append('missing_data_quality')
    elif data_quality < 80:
        flags.append('data_quality_under_80')

    if risk_penalty is not None and risk_penalty > 15:
        flags.append('risk_penalty_over_15')

    if books is None:
        flags.append('missing_book_count')
    elif books < 5:
        flags.append('low_book_coverage_under_5')
    elif books < 8:
        flags.append('limited_book_coverage_under_8')

    if sg == 'Soccer':
        if draw_p is None:
            flags.append('soccer_draw_probability_missing')
        elif draw_p >= 0.30:
            flags.append('soccer_draw_risk_extreme_30_plus')
        elif draw_p >= 0.25:
            flags.append('soccer_draw_risk_block_ml_25_plus')
        elif draw_p >= 0.18:
            flags.append('soccer_draw_risk_elevated_18_plus')

    if sg == 'Baseball' and classification == 'Watch' and market_p is not None and 0.50 <= market_p <= 0.56:
        flags.append('baseball_watch_low_edge_50_56')

    if price is None:
        flags.append('missing_best_price')
    elif price < 1.30:
        flags.append('heavy_favorite_price_under_1_30')
    elif price > 3.00:
        flags.append('longshot_price_over_3_00')

    if proxy_edge is None:
        flags.append('proxy_edge_missing')
    elif proxy_edge < 0.03:
        flags.append('proxy_edge_under_3pct')

    if _parse_percent(row.get('ARA model probability')) is None and _parse_percent(row.get('Model probability')) is None:
        flags.append('independent_ara_probability_missing')

    return flags


def _recommended_market(row, flags):
    if _sport_group(row.get('Sport')) == 'Soccer' and any(flag.startswith('soccer_draw_risk') for flag in flags):
        return 'No moneyline; consider draw-no-bet/double-chance only if independent edge confirms value'
    return 'Moneyline only if independent ARA edge confirms value'


def _model_probability(row):
    # Accept either column name so future APIs can feed the decision layer without refactoring.
    return _parse_percent(row.get('ARA model probability')) or _parse_percent(row.get('Model probability'))


def _live_decision(row):
    flags = _risk_flags(row)
    price = _parse_float(row.get('Best price'))
    implied = (1.0 / price) if price and price > 0 else None
    model_p = _model_probability(row)
    edge = (model_p - implied) if model_p is not None and implied is not None else None

    hard_blocks = {
        'classification_avoid', 'soccer_draw_risk_extreme_30_plus', 'soccer_draw_risk_block_ml_25_plus',
        'missing_best_price', 'missing_data_quality', 'data_quality_under_80', 'low_book_coverage_under_5',
        'heavy_favorite_price_under_1_30', 'longshot_price_over_3_00', 'baseball_watch_low_edge_50_56'
    }

    if 'classification_avoid' in flags:
        return 'AVOID', 0.0, None, 'Avoid classification blocks betting.', flags
    if any(flag in hard_blocks for flag in flags):
        blocked = ', '.join(flag for flag in flags if flag in hard_blocks)
        return 'WATCH', 0.0, edge, 'Blocked by hard risk controls: ' + blocked, flags
    if model_p is None or edge is None:
        return 'WATCH', 0.0, None, 'Independent ARA probability is missing; no live bet.', flags
    if edge < 0.03:
        return 'WATCH', 0.0, edge, 'Edge under 3%; no bet.', flags
    if 'watch_track_only' in flags and edge < 0.08:
        return 'WATCH', 0.0, edge, 'Watch classification requires 8%+ independent edge.', flags
    if edge >= 0.08:
        return 'BET_STRONG', 1.0, edge, 'Independent edge is 8%+ and hard filters passed.', flags
    if edge >= 0.05:
        return 'BET', 0.75, edge, 'Independent edge is 5%+ and hard filters passed.', flags
    return 'BET_SMALL', 0.25, edge, 'Independent edge is 3%+ and hard filters passed.', flags


def _proxy_filter_decision(row):
    flags = _risk_flags(row)
    classification = str(row.get('Classification', '') or '').strip().title()
    if classification == 'Avoid':
        return 'PROXY_AVOID', 'Avoid classification.'
    if 'soccer_draw_risk_extreme_30_plus' in flags or 'soccer_draw_risk_block_ml_25_plus' in flags:
        return 'PROXY_WATCH_NO_ML', 'Soccer draw risk blocks moneyline.'
    if 'baseball_watch_low_edge_50_56' in flags:
        return 'PROXY_WATCH', 'Baseball Watch pick in 50-56% probability band is too volatile.'
    if 'data_quality_under_80' in flags or 'low_book_coverage_under_5' in flags:
        return 'PROXY_WATCH', 'Insufficient data quality or book coverage.'
    return 'PROXY_CANDIDATE', 'Passes current leak-control filters; still needs independent edge before live betting.'


def apply_ara_decision_layer(df):
    out = df.copy()
    market_probs = []
    implied_probs = []
    proxy_edges = []
    risk_flags = []
    live_decisions = []
    live_stakes = []
    live_edges = []
    reasons = []
    recommended = []
    proxy_decisions = []
    proxy_reasons = []
    sport_groups = []
    record_keys = []

    for _, row in out.iterrows():
        row_dict = row.to_dict()
        price = _parse_float(row_dict.get('Best price'))
        market_p = _parse_percent(row_dict.get('Market probability'))
        implied = (1.0 / price) if price and price > 0 else None
        proxy_edge = (market_p - implied) if market_p is not None and implied is not None else None
        decision, stake, live_edge, reason, flags = _live_decision(row_dict)
        pdec, preason = _proxy_filter_decision(row_dict)

        record_keys.append(_record_key(row_dict))
        sport_groups.append(_sport_group(row_dict.get('Sport')))
        market_probs.append(_fmt_dec(market_p))
        implied_probs.append(_fmt_pct(implied))
        proxy_edges.append(_fmt_pct(proxy_edge))
        risk_flags.append('; '.join(flags))
        live_decisions.append(decision)
        live_stakes.append(f'{stake:.2f}')
        live_edges.append(_fmt_pct(live_edge))
        reasons.append(reason)
        recommended.append(_recommended_market(row_dict, flags))
        proxy_decisions.append(pdec)
        proxy_reasons.append(preason)

    out['ara_record_key'] = record_keys
    out['ara_sport_group'] = sport_groups
    out['ara_market_probability_decimal'] = market_probs
    out['ara_implied_probability_best_price'] = implied_probs
    out['ara_proxy_edge_vs_best_price'] = proxy_edges
    out['ara_risk_flags'] = risk_flags
    out['ara_live_decision'] = live_decisions
    out['ara_live_stake_units'] = live_stakes
    out['ara_live_edge'] = live_edges
    out['ara_decision_reason'] = reasons
    out['ara_recommended_market'] = recommended
    out['ara_proxy_filter_decision'] = proxy_decisions
    out['ara_proxy_filter_reason'] = proxy_reasons
    return out
