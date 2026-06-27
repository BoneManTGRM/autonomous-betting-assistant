from __future__ import annotations

import pandas as pd

from .value_math import assess_value_pick, all_red_diagnostic


EDGE_BUFFER = 0.0
EV_BUFFER = 0.0
MIN_CONFIDENCE = 0.50
TARGET_ODDS_MARGIN = 0.02


def _num(frame: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in frame.columns:
        return pd.Series(default, index=frame.index, dtype='float64')
    return pd.to_numeric(frame[col], errors='coerce').fillna(default)


def _flag(frame: pd.DataFrame, col: str, default: bool = False) -> pd.Series:
    if col not in frame.columns:
        return pd.Series(default, index=frame.index, dtype='bool')
    return frame[col].astype(bool)


def _assessment_rows(frame: pd.DataFrame) -> list:
    return [assess_value_pick(row.to_dict(), min_confidence=MIN_CONFIDENCE, edge_buffer=EDGE_BUFFER, ev_buffer=EV_BUFFER, safety_margin=TARGET_ODDS_MARGIN) for _, row in frame.iterrows()]


def add_profit_guard(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach strict positive-EV classification without inflating confidence.

    Green/playable status is based on real positive edge and EV after safety checks.
    High confidence with bad price becomes watchlist/yellow, not green.
    """
    out = frame.copy()
    if out.empty:
        return out

    assessments = _assessment_rows(out)
    diagnostic = all_red_diagnostic(assessments)

    out['model_probability_clean'] = [a.model_probability for a in assessments]
    out['model_probability'] = [a.model_probability for a in assessments]
    out['decimal_price'] = [a.decimal_odds for a in assessments]
    out['market_implied_probability'] = [a.raw_implied_probability for a in assessments]
    out['raw_implied_probability'] = [a.raw_implied_probability for a in assessments]
    out['no_vig_implied_probability'] = [a.no_vig_implied_probability for a in assessments]
    out['model_market_edge'] = [a.edge for a in assessments]
    out['no_vig_edge'] = [a.no_vig_edge for a in assessments]
    out['expected_value_per_unit'] = [a.expected_value for a in assessments]
    out['profit_expected_value'] = [a.expected_value for a in assessments]
    out['profit_edge_proxy'] = [a.edge for a in assessments]
    out['fair_odds'] = [a.fair_odds for a in assessments]
    out['target_odds'] = [a.target_odds for a in assessments]
    out['odds_verified'] = [a.odds_verified for a in assessments]
    out['market_freshness_status'] = ['fresh_or_recently_cached' if a.market_fresh else 'stale_odds' for a in assessments]
    out['value_color'] = [a.color for a in assessments]
    out['recommendation_color'] = [a.color for a in assessments]
    out['color_classification'] = [a.color for a in assessments]
    out['final_recommendation_gate'] = [a.recommendation for a in assessments]
    out['reason_for_color'] = [a.reason for a in assessments]
    out['reason_final_recommendation_is_or_is_not_green'] = [a.reason for a in assessments]
    out['better_price_needed'] = [
        'Current odds are too low. This pick becomes playable only at target odds or better.'
        if a.color in {'YELLOW', 'RED'} and a.target_odds is not None else ''
        for a in assessments
    ]
    out['confidence_edge_explanation'] = [
        'Model confidence can be high while edge is negative because the sportsbook price implies a higher probability than the model.'
        if a.color in {'YELLOW', 'RED'} else 'Confidence, edge, and EV agree after safety checks.'
        for a in assessments
    ]
    out['all_red_diagnostic'] = diagnostic

    status = pd.Series('research_only', index=out.index, dtype='object')
    status.loc[out['value_color'].eq('DATA WARNING')] = 'data_warning'
    status.loc[out['value_color'].eq('RED')] = 'negative_ev_avoid'
    status.loc[out['value_color'].eq('YELLOW')] = 'watchlist_price_too_low'
    status.loc[out['value_color'].eq('GREEN')] = 'value_ok'

    odds = _num(out, 'decimal_price', 0.0)
    price_safety = odds.between(1.05, 5.00, inclusive='both')
    status.loc[~price_safety & out['value_color'].ne('DATA WARNING')] = 'reject_price_safety'

    out['profit_guard_status'] = status
    out['profit_green_ok'] = out['value_color'].eq('GREEN') & price_safety
    out['profit_watchlist_ok'] = out['value_color'].isin({'GREEN', 'YELLOW'}) & price_safety
    out['profit_volume_safe'] = out['value_color'].isin({'GREEN', 'YELLOW'}) & price_safety & _flag(out, 'odds_verified', False)
    out['profit_balanced_ok'] = out['profit_watchlist_ok'] & _flag(out, 'odds_verified', False)
    out['profit_official_ok'] = out['profit_green_ok'] & _flag(out, 'odds_verified', False)
    out['profit_elite_ok'] = out['profit_green_ok'] & _num(out, 'model_market_edge', -1.0).ge(0.015) & _num(out, 'expected_value_per_unit', -1.0).ge(0.015)

    base = _num(out, 'pattern_points', 0.0).where(_num(out, 'pattern_points', 0.0).gt(0), _num(out, 'agent_score', 0.0))
    ev = _num(out, 'expected_value_per_unit', -1.0)
    edge = _num(out, 'model_market_edge', -1.0)
    prob = _num(out, 'model_probability_clean', 0.0)
    green_bonus = out['profit_green_ok'].astype(float) * 65.0
    yellow_bonus = out['value_color'].eq('YELLOW').astype(float) * 12.0
    red_penalty = out['value_color'].eq('RED').astype(float) * 45.0 + out['value_color'].eq('DATA WARNING').astype(float) * 70.0
    odds_score = odds.between(1.25, 2.75, inclusive='both').astype(float) * 6.0 - odds.lt(1.15).astype(float) * 18.0 - odds.gt(3.50).astype(float) * 12.0
    score = (base * 0.35 + green_bonus + yellow_bonus - red_penalty + prob * 10.0 + ev.clip(-0.25, 0.25) * 180.0 + edge.clip(-0.15, 0.15) * 120.0 + odds_score).clip(0, 100).round(3)
    out['profit_protection_score'] = score

    lane = pd.Series('research_volume', index=out.index, dtype='object')
    lane.loc[out['value_color'].eq('YELLOW')] = 'watchlist_price_check'
    lane.loc[out['profit_official_ok'].astype(bool)] = 'official_positive_ev'
    lane.loc[out['profit_elite_ok'].astype(bool)] = 'elite_positive_ev'
    lane.loc[out['value_color'].eq('RED')] = 'blocked_negative_ev'
    lane.loc[out['value_color'].eq('DATA WARNING')] = 'blocked_data_warning'
    out['profit_lane'] = lane

    stake = pd.Series(0.0, index=out.index, dtype='float64')
    stake.loc[out['value_color'].eq('YELLOW')] = 0.05
    stake.loc[out['profit_official_ok'].astype(bool)] = 0.10
    stake.loc[out['profit_elite_ok'].astype(bool)] = 0.15
    out['suggested_stake_units'] = stake

    event_key = out.get('event_id', out.get('event', pd.Series('', index=out.index))).astype(str)
    market_key = out.get('market_type', pd.Series('', index=out.index)).astype(str)
    portfolio_key = event_key + '|' + market_key
    tmp = pd.DataFrame({'key': portfolio_key, 'score': score, 'idx': range(len(out))}).sort_values(['key', 'score'], ascending=[True, False])
    tmp['rank'] = tmp.groupby('key').cumcount() + 1
    group_rank = tmp.sort_values('idx')['rank'].reset_index(drop=True).astype(int)
    out['portfolio_group_rank'] = group_rank.values
    penalty = (out['portfolio_group_rank'].clip(lower=1) - 1) * 6.0
    out['portfolio_priority_score'] = (score - penalty).clip(0, 100).round(3)

    existing = out['decision_signals'].astype(str) if 'decision_signals' in out.columns else pd.Series('', index=out.index, dtype='object')
    out['decision_signals'] = (existing + '; positive_ev_value_guard_v1').str.strip('; ')
    return out


def filter_profit_guard(frame: pd.DataFrame, mode: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    if 'profit_guard_status' not in frame.columns:
        frame = add_profit_guard(frame)
    text = str(mode or '').lower()
    if text.startswith('research'):
        return frame
    if text.startswith('volume'):
        return frame[frame.get('profit_volume_safe', pd.Series(True, index=frame.index)).astype(bool)]
    if text.startswith('balanced'):
        return frame[frame.get('profit_balanced_ok', pd.Series(True, index=frame.index)).astype(bool)]
    if text.startswith('official'):
        return frame[frame.get('profit_official_ok', pd.Series(False, index=frame.index)).astype(bool)]
    if text.startswith('elite'):
        return frame[frame.get('profit_elite_ok', pd.Series(False, index=frame.index)).astype(bool)]
    return frame
