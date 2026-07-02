from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd

from .final_enriched_report_pipeline import (
    PLACEHOLDER_PATTERNS,
    REQUIRED_REPORT_COLUMNS,
    _first,
    _frame,
    _hash,
    _norm,
    _num,
    _teams,
    _txt,
    check_api_health,
)

LINE_FIELDS = (
    'selected_line', 'locked_line', 'line', 'line_point', 'point', 'points', 'handicap',
    'spread', 'total', 'threshold', 'market_line', 'bet_line', 'line_display', 'prop_line'
)
PROVIDER_LINE_FIELDS = ('provider_line', 'live_line', 'sportsbook_line', 'odds_api_line', 'current_line')
TIMESTAMP_FIELDS = ('timestamp', 'price_timestamp', 'last_update', 'last_updated', 'updated_at', 'commence_time', 'locked_at_utc')
SOURCE_FIELDS = ('provider', 'bookmaker', 'sportsbook', 'odds_source', 'data_source')
ENDPOINT_FIELDS = ('provider_endpoint', 'endpoint_called', 'odds_endpoint')


def _decimal_odds(row: Mapping[str, Any]) -> float | None:
    value = _num(_first(row, 'decimal_odds', 'decimal_price', 'best_price', 'odds_decimal', 'odds'))
    if value and value > 1:
        return value
    american = _num(_first(row, 'american_odds', 'moneyline'))
    if american is None or american == 0:
        return None
    return round(1 + american / 100, 6) if american > 0 else round(1 + 100 / abs(american), 6)


def _american_from_decimal(decimal_odds: float | None) -> int | None:
    if decimal_odds is None or decimal_odds <= 1:
        return None
    return int(round((decimal_odds - 1) * 100)) if decimal_odds >= 2 else int(round(-100 / (decimal_odds - 1)))


def _model_probability(row: Mapping[str, Any]) -> float | None:
    value = _num(_first(row, 'model_probability', 'model_probability_clean', 'learned_model_probability', 'final_probability', 'probability'))
    if value is None:
        return None
    value = value / 100 if value > 1 else value
    return round(value, 6) if 0 < value < 1 else None


def _is_placeholder(value: Any) -> bool:
    text = _txt(value).lower()
    return any(pattern.lower() in text for pattern in PLACEHOLDER_PATTERNS)


def _clean(value: Any) -> str:
    text = _txt(value)
    return '' if _is_placeholder(text) else text


def _num_from_fields(row: Mapping[str, Any], fields: tuple[str, ...]) -> float | None:
    for field in fields:
        value = _num(_first(row, field))
        if value is not None:
            return value
    return None


def _live_status(row: Mapping[str, Any], flags: tuple[str, ...], fields: tuple[str, ...]) -> tuple[str, str]:
    flagged = any(_txt(row.get(key)).lower() in {'true', '1', 'yes', 'live', 'active'} for key in flags)
    has_payload = any(_txt(row.get(key)) and not _is_placeholder(row.get(key)) for key in fields)
    if flagged and has_payload:
        return 'LIVE', ''
    if flagged:
        return 'FAILED', 'Live flag was set but no usable provider payload reached final_enriched_picks_df.'
    return 'FAILED', 'No successful provider response reached final_enriched_picks_df.'


def _event_key(row: Mapping[str, Any], home: str, away: str, index: int) -> str:
    date = _txt(_first(row, 'event_date', 'event_start_utc', 'commence_time', 'start_time'))[:10]
    key = '|'.join([_norm(_first(row, 'sport', 'league')), date] + sorted([_norm(home), _norm(away)])).strip('|')
    return key or f'event_{index}'


def _recommendation(probability: float | None, ev: float | None, edge: float | None) -> str:
    if probability is None or ev is None or edge is None:
        return 'UNVERIFIED'
    if ev > 0 and edge > 0:
        return 'BET CANDIDATE'
    if probability >= 0.60 and ev <= 0:
        return 'WATCHLIST'
    return 'PASS' if ev <= 0 else 'NO PLAY'


def _market_text(row: Mapping[str, Any]) -> str:
    return ' '.join(_txt(_first(row, 'selected_market', 'market_type', 'market', 'market_name', 'bet_type', 'wager_type', 'prediction', 'pick', 'selection')).lower().replace('_', ' ').split())


def _pick_text(row: Mapping[str, Any]) -> str:
    return _txt(_first(row, 'selected_pick', 'prediction', 'pick', 'selection', 'exact_bet', 'public_pick'))


def _market_family(row: Mapping[str, Any]) -> str:
    text = (_market_text(row) + ' ' + _pick_text(row).lower()).replace('_', ' ')
    if any(token in text for token in ('total', 'over ', 'under ', 'over/', 'over under')):
        return 'total'
    if any(token in text for token in ('spread', 'handicap', 'run line', 'puck line', 'point spread')):
        return 'spread'
    if any(token in text for token in ('moneyline', 'h2h', 'winner', 'match winner', 'head to head')):
        return 'moneyline'
    return 'unknown'


def _selected_line(row: Mapping[str, Any]) -> float | None:
    direct = _num_from_fields(row, LINE_FIELDS)
    if direct is not None:
        return direct
    text = _pick_text(row).lower()
    match = re.search(r'(?<!\d)([+-]?\d+(?:\.\d+)?)(?!\d)', text)
    if match:
        return float(match.group(1))
    return None


def _provider_line(row: Mapping[str, Any]) -> float | None:
    return _num_from_fields(row, PROVIDER_LINE_FIELDS)


def _line_label(value: float | None) -> str:
    if value is None:
        return ''
    return f'+{value:g}' if value > 0 else f'{value:g}'


def _total_side(row: Mapping[str, Any]) -> str:
    text = (_pick_text(row) + ' ' + _market_text(row)).lower()
    if 'under' in text:
        return 'Under'
    if 'over' in text:
        return 'Over'
    return ''


def _selection_name(row: Mapping[str, Any], home: str = '', away: str = '') -> str:
    pick = _pick_text(row)
    cleaned = re.sub(r'\b(moneyline|spread|point spread|run line|puck line|game total|total|over|under)\b', ' ', pick, flags=re.I)
    cleaned = re.sub(r'[+-]?\d+(?:\.\d+)?', ' ', cleaned)
    cleaned = re.sub(r'[:·\-]+', ' ', cleaned)
    cleaned = ' '.join(cleaned.split())
    if cleaned:
        return cleaned
    return home or away or pick or 'Selection'


def _line_guard(row: Mapping[str, Any], context: str = '') -> dict[str, Any]:
    family = _market_family(row)
    selected = _selected_line(row)
    provider = _provider_line(row)
    issue = ''
    risk = ''
    action = ''
    if family == 'total' and selected is None:
        issue, risk, action = 'missing total line', 'TOTAL LINE MISSING', 'BLOCKED'
    elif family == 'spread' and selected is None:
        issue, risk, action = 'missing spread/run-line handicap', 'HANDICAP MISSING', 'BLOCKED'
    elif selected is not None and provider is not None and abs(float(selected) - float(provider)) > 0.001:
        issue, risk, action = f'line mismatch: selected {_line_label(selected)} vs provider {_line_label(provider)}', 'LINE MISMATCH', 'BLOCKED'
    elif selected is not None and context:
        # Loose narrative is not allowed to overwrite the pick; it can only warn.
        narrative = [float(x) for x in re.findall(r'favou?red by\s*([+-]?\d+(?:\.\d+)?)|spread\s*([+-]?\d+(?:\.\d+)?)', context, flags=re.I) for x in x if x]
        if narrative and all(abs(selected - value) > 0.001 for value in narrative[:2]):
            risk, action = 'VERIFY LINE', 'WATCHLIST'
    return {'market_family': family, 'selected_line': selected, 'provider_line': provider, 'data_issue_reason': issue, 'risk_override': risk, 'action_override': action}


def beginner_explanation(row: Mapping[str, Any], home: str = '', away: str = '') -> str:
    family = _market_family(row)
    line = _selected_line(row)
    pick = _pick_text(row)
    selection = _selection_name(row, home, away)
    sport = _txt(_first(row, 'sport', 'league')).lower()
    if family == 'moneyline':
        return f'Moneyline means {selection} must win the game. The final margin does not matter.'
    if family == 'total':
        side = _total_side(row)
        if line is None:
            return 'Game total is missing its number, so this is not bettable until the total line is known.'
        needed = int(line) + 1 if side.lower() == 'over' and float(line).is_integer() is False else None
        if side.lower() == 'over':
            threshold = int(line + 0.5) if line % 1 == 0.5 else line
            return f'Over {_line_label(line).lstrip("+")} means the two teams must combine for {threshold} or more points.'
        if side.lower() == 'under':
            threshold = int(line - 0.5) if line % 1 == 0.5 else line
            return f'Under {_line_label(line).lstrip("+")} means the two teams must combine for {threshold} or fewer points.'
        return f'Total {_line_label(line)} needs an Over or Under side before it is bettable.'
    if family == 'spread':
        if line is None:
            return 'Spread handicap is missing, so this is not bettable until the handicap is known.'
        margin = abs(float(line))
        integer_margin = int(margin + 0.5) if margin % 1 == 0.5 else margin
        score_unit = 'runs' if 'baseball' in sport or 'mlb' in sport else ('goals' if 'hockey' in sport or 'nhl' in sport else 'points')
        if line < 0:
            return f'{selection} {_line_label(line)} means {selection} must win by {integer_margin} or more {score_unit}.'
        return f'{selection} +{margin:g} means {selection} can win outright or lose by {int(margin - 0.5) if margin % 1 == 0.5 else margin} or fewer {score_unit}.'
    if 'parlay' in pick.lower():
        return 'A parlay needs every leg to win. One losing leg loses the whole parlay.'
    return 'Read the market type, line, price, source, edge, and EV before using this pick.'


def _shadow_math(row: Mapping[str, Any], decimal_odds: float | None, model_probability: float | None, raw_implied: float | None, edge: float | None, ev: float | None, no_vig: float | None, odds_status: str, line_info: Mapping[str, Any]) -> dict[str, Any]:
    current_price = _decimal_odds(row)
    best_price = _decimal_odds({'decimal_odds': _first(row, 'best_sportsbook_price', 'best_price', 'best_decimal_odds')}) or current_price
    opening_price = _decimal_odds({'decimal_odds': _first(row, 'opening_price', 'opening_decimal_odds')})
    closing_price = _decimal_odds({'decimal_odds': _first(row, 'closing_price', 'closing_decimal_odds')})
    no_vig_edge = round(model_probability - no_vig, 6) if model_probability is not None and no_vig is not None else None
    best_ev = round(model_probability * best_price - 1, 6) if model_probability is not None and best_price else None
    shadow_ev_delta = round(best_ev - ev, 6) if best_ev is not None and ev is not None else None
    stale = odds_status != 'LIVE'
    mismatch = bool(line_info.get('data_issue_reason') and 'line mismatch' in _txt(line_info.get('data_issue_reason')).lower())
    if mismatch:
        rec = 'BLOCK LINE MISMATCH'
        reject = line_info.get('data_issue_reason')
    elif stale:
        rec = 'BLOCK STALE PRICE'
        reject = 'odds source is not live verified'
    elif best_price and decimal_odds and best_price > decimal_odds:
        rec = 'BETTER PRICE AVAILABLE'
        reject = ''
    elif ev is not None and ev <= 0:
        rec = 'WAIT FOR TARGET PRICE'
        reject = 'current EV is not positive'
    else:
        rec = 'KEEP ORIGINAL'
        reject = ''
    return {
        'shadow_mode': 'OBSERVING_ONLY',
        'shadow_status_label': 'Shadow Mode: observing only',
        'shadow_recommendation': rec,
        'shadow_original_recommendation': _txt(_first(row, 'final_decision', 'recommendation', 'recommended_action', 'consumer_action')),
        'shadow_disagrees_with_current_pick': str(rec not in {'KEEP ORIGINAL', ''}),
        'shadow_raw_implied_probability': raw_implied,
        'shadow_no_vig_implied_probability': no_vig,
        'shadow_no_vig_edge_delta': no_vig_edge,
        'shadow_ev_delta': shadow_ev_delta,
        'shadow_edge_delta': edge,
        'shadow_price_quality': 'STALE_OR_UNVERIFIED' if stale else ('BETTER_PRICE_AVAILABLE' if rec == 'BETTER PRICE AVAILABLE' else 'CURRENT_PRICE_OK'),
        'shadow_clv_estimate': round((closing_price or 0) - (decimal_odds or 0), 6) if closing_price and decimal_odds else None,
        'shadow_reject_reason': reject,
        'shadow_promote_reason': '',
        'shadow_confidence_adjustment': 'none_shadow_mode',
        'shadow_market_quality_score': 0 if stale or mismatch else (1 if ev and ev > 0 else 0.5),
        'shadow_line_quality_score': 0 if mismatch else (0.5 if line_info.get('risk_override') == 'VERIFY LINE' else 1),
        'shadow_source_quality_score': 1 if odds_status == 'LIVE' else 0,
        'shadow_stale_price_detected': str(stale),
        'shadow_line_mismatch_detected': str(mismatch),
        'shadow_current_decimal_odds': current_price,
        'shadow_opening_price': opening_price,
        'shadow_current_price': current_price,
        'shadow_best_sportsbook_price': best_price,
        'shadow_sportsbook_count': _txt(_first(row, 'sportsbook_count', 'book_count')) or '0',
        'shadow_sportsbook_disagreement_range': _txt(_first(row, 'sportsbook_disagreement_range', 'book_price_range')),
        'shadow_price_movement_direction': _txt(_first(row, 'price_movement_direction', 'line_movement_direction')),
        'shadow_line_movement_flag': str(bool(_txt(_first(row, 'line_movement', 'price_movement')))),
    }


def _truth_timestamp(row: Mapping[str, Any]) -> str:
    return _txt(_first(row, *TIMESTAMP_FIELDS))


def _truth_provider(row: Mapping[str, Any]) -> str:
    return _txt(_first(row, *SOURCE_FIELDS))


def _truth_endpoint(row: Mapping[str, Any]) -> str:
    return _txt(_first(row, *ENDPOINT_FIELDS))


def build_final_enriched_picks_df(raw_picks_df: Any, force_refresh: bool = False) -> pd.DataFrame:
    raw = _frame(raw_picks_df)
    records = raw.to_dict('records') if not raw.empty else []
    now = datetime.now(timezone.utc).isoformat()
    report_run_id = 'report_' + uuid.uuid4().hex[:12]
    raw_hash = _hash(records)
    api_health = check_api_health(mask_secrets=True)
    rows: list[dict[str, Any]] = []

    for index, source_row in enumerate(records):
        row = dict(source_row)
        away_team, home_team = _teams(row)
        event_key = _event_key(row, home_team, away_team, index)
        decimal_odds = _decimal_odds(row)
        model_probability = _model_probability(row)
        raw_implied = round(1 / decimal_odds, 6) if decimal_odds else None
        edge = round(model_probability - raw_implied, 6) if model_probability is not None and raw_implied is not None else None
        ev = round(model_probability * decimal_odds - 1, 6) if model_probability is not None and decimal_odds else None
        full_sides = _txt(_first(row, 'odds_market_sides_available', 'market_sides_available')).lower() in {'true', '1', 'yes', 'full', 'complete'}
        no_vig = _num(_first(row, 'no_vig_implied_probability', 'novig_implied_probability')) if full_sides else None

        odds_live, odds_reason = _live_status(row, ('odds_api_live', 'the_odds_api_live'), ('odds_api_summary', 'live_odds_summary', 'odds_api_context'))
        if odds_live == 'LIVE':
            odds_status, odds_source, odds_failure = 'LIVE', 'LIVE_API', ''
        elif decimal_odds:
            odds_status, odds_source, odds_failure = 'UPLOADED_ROW', 'UPLOADED_ROW', odds_reason
        else:
            odds_status, odds_source, odds_failure = 'MISSING', 'EMPTY_WITH_REASON', odds_reason

        news_status, news_failure = _live_status(row, ('newsapi_live', 'newsapi_enabled'), ('news_summary', 'newsapi_summary', 'breaking_news_summary'))
        perplexity_status, perplexity_failure = _live_status(row, ('perplexity_live', 'perplexity_enabled'), ('perplexity_context', 'perplexity_summary', 'perplexity_news_context'))
        weather_status, weather_failure = _live_status(row, ('weatherapi_live', 'weather_live'), ('weather_summary', 'venue_weather', 'weather_risk'))
        news_summary = _clean(_first(row, 'news_summary', 'newsapi_summary', 'breaking_news_summary'))
        perplexity_context = _clean(_first(row, 'perplexity_context', 'perplexity_summary', 'perplexity_news_context'))
        uploaded_context = _clean(_first(row, 'context', 'sports_context_summary', 'game_summary', 'preview_summary', 'analysis_summary'))

        if perplexity_context:
            context, context_source, context_status, context_reason = perplexity_context, 'Perplexity', perplexity_status, '' if perplexity_status == 'LIVE' else perplexity_failure
        elif news_summary:
            context, context_source, context_status, context_reason = news_summary, 'NewsAPI', news_status, '' if news_status == 'LIVE' else news_failure
        elif uploaded_context:
            context, context_source, context_status, context_reason = uploaded_context, 'UPLOADED_ROW', 'FALLBACK_USED', 'Context came from the uploaded/generated row.'
        else:
            context, context_source, context_status, context_reason = '', 'EMPTY_WITH_REASON', 'FAILED', 'No real context source reached final_enriched_picks_df.'

        line_info = _line_guard(row, context)
        beginner = beginner_explanation(row, home_team, away_team)
        line_blocked = bool(line_info.get('data_issue_reason'))
        loose_verify_line = line_info.get('risk_override') == 'VERIFY LINE'
        ev_status = 'LIVE_RECALCULATED' if odds_status == 'LIVE' and ev is not None else ('UNVERIFIED_MODEL_ONLY' if decimal_odds and ev is not None else 'UNVERIFIED')
        ev_source = 'calculated_from_live_odds_and_model_probability' if ev_status == 'LIVE_RECALCULATED' else ('model_edge_pending_price_verification' if ev_status == 'UNVERIFIED_MODEL_ONLY' else 'EMPTY_WITH_REASON')
        fallback_used = odds_status != 'LIVE' or context_source != 'Perplexity' or news_status != 'LIVE' or perplexity_status != 'LIVE'
        fallback_reason = '; '.join(part for part in [odds_failure if odds_status != 'LIVE' else '', context_reason, news_failure if news_status != 'LIVE' else '', perplexity_failure if perplexity_status != 'LIVE' else ''] if part)
        recommendation = _recommendation(model_probability, ev, edge)
        if line_blocked:
            recommendation = 'BLOCKED'
        elif fallback_used or loose_verify_line:
            recommendation = 'WATCHLIST'
        shadow = _shadow_math(row, decimal_odds, model_probability, raw_implied, edge, ev, no_vig, odds_status, line_info)
        provenance = {'decimal_odds': odds_source, 'EV': ev_source, 'context': context_source, 'news_summary': 'NewsAPI' if news_status == 'LIVE' and news_summary else 'EMPTY_WITH_REASON', 'perplexity_context': 'Perplexity' if perplexity_status == 'LIVE' and perplexity_context else 'EMPTY_WITH_REASON'}
        risk_reasons = _txt(_first(row, 'risk_reasons', 'risk_reason', 'risk_notes'))
        if line_blocked:
            risk_reasons = f"{line_info.get('risk_override')}: {line_info.get('data_issue_reason')}"
        elif loose_verify_line:
            risk_reasons = 'Loose matchup/context text may reference a different line. Verify sportsbook line before using.'
        elif fallback_used:
            risk_reasons = 'Saved row / price verification required. Current sportsbook price not matched.'
        selected_line = line_info.get('selected_line')
        provider_line = line_info.get('provider_line')

        output = dict(row)
        output.update({
            'event_id': _txt(_first(row, 'event_id', 'game_id', 'fixture_id')) or event_key,
            'event_key': event_key,
            'duplicate_group_id': 'dup_' + hashlib.sha1(event_key.encode()).hexdigest()[:10],
            'row_id': hashlib.sha1(json.dumps(row, sort_keys=True, default=str).encode()).hexdigest()[:12],
            'raw_input_hash': raw_hash,
            'enrichment_input_hash': '',
            'sport': _txt(_first(row, 'sport', 'league')),
            'league': _txt(_first(row, 'league', 'competition')),
            'event_date': _txt(_first(row, 'event_date', 'event_start_utc', 'commence_time'))[:10],
            'start_time': _txt(_first(row, 'start_time', 'event_start_utc', 'commence_time')),
            'home_team': home_team,
            'away_team': away_team,
            'normalized_home_team': _norm(home_team),
            'normalized_away_team': _norm(away_team),
            'selected_market': _txt(_first(row, 'selected_market', 'market_type', 'market')),
            'selected_pick': _txt(_first(row, 'selected_pick', 'prediction', 'pick', 'selection')),
            'selected_line': selected_line,
            'provider_line': provider_line,
            'bookmaker': _txt(_first(row, 'bookmaker', 'sportsbook')),
            'sportsbook': _txt(_first(row, 'sportsbook', 'bookmaker')),
            'provider': _truth_provider(row) or odds_source,
            'provider_endpoint': _truth_endpoint(row),
            'price_timestamp': _truth_timestamp(row) if odds_status == 'LIVE' else '',
            'decimal_odds': decimal_odds,
            'decimal_price': decimal_odds,
            'american_odds': _num(_first(row, 'american_odds', 'moneyline')) or _american_from_decimal(decimal_odds),
            'odds_source': odds_source,
            'odds_status': odds_status,
            'odds_last_refresh': now if odds_status == 'LIVE' else '',
            'odds_failure_reason': odds_failure,
            'odds_market_sides_available': 'FULL' if full_sides else 'INCOMPLETE',
            'model_probability': model_probability,
            'model_probability_source': 'model_probability' if model_probability is not None else 'EMPTY_WITH_REASON',
            'confidence_source': 'model_probability' if model_probability is not None else 'EMPTY_WITH_REASON',
            'confidence_status': 'AVAILABLE' if model_probability is not None else 'MISSING',
            'raw_implied_probability': raw_implied,
            'no_vig_implied_probability': no_vig,
            'no_vig_status': 'CALCULATED' if no_vig is not None else 'UNAVAILABLE_MARKET_INCOMPLETE',
            'edge': edge,
            'model_market_edge': edge,
            'no_vig_edge': round(model_probability - no_vig, 6) if model_probability is not None and no_vig is not None else None,
            'EV': ev,
            'expected_value_per_unit': ev,
            'ev_source': ev_source,
            'ev_status': ev_status,
            'ev_display_label': 'Verified EV' if ev_status == 'LIVE_RECALCULATED' else 'Unverified EV',
            'edge_display_label': 'Verified edge' if ev_status == 'LIVE_RECALCULATED' else 'Model edge pending price verification',
            'fair_odds': round(1 / model_probability, 6) if model_probability else None,
            'target_odds': round((1 / model_probability) * 1.02, 6) if model_probability else None,
            'confidence_tier': _txt(_first(row, 'confidence_tier', 'confidence_bucket', 'public_confidence')),
            'recommendation_status': recommendation,
            'final_decision': recommendation,
            'consumer_action': recommendation,
            'recommended_action': recommendation,
            'units': _txt(_first(row, 'units', 'recommended_stake_units', 'suggested_stake_units')) or ('0.5' if recommendation == 'BET CANDIDATE' and ev_status == 'LIVE_RECALCULATED' else '0.0'),
            'live_verified_stake_units': _txt(_first(row, 'live_verified_stake_units')) if odds_status == 'LIVE' and not line_blocked else '0.0',
            'risk_label': line_info.get('risk_override') or ('VERIFY PRICE' if fallback_used else (_txt(_first(row, 'risk_label', 'risk', 'risk_level')) or 'STANDARD')),
            'risk_reasons': risk_reasons,
            'data_issue_reason': line_info.get('data_issue_reason') or _txt(_first(row, 'data_issue_reason')),
            'beginner_explanation': beginner,
            'what_this_means': beginner,
            'glossary_note': 'Moneyline: team must win. Spread: cover the listed margin. Over/Under: combined score versus the total. Parlay: every leg must win.',
            'sportsdataio_event_id': _txt(_first(row, 'sportsdataio_event_id', 'sportsdataio_game_id', 'sdio_event_id')),
            'sportsdataio_match_status': 'MATCHED' if _txt(_first(row, 'sportsdataio_event_id', 'sportsdataio_game_id', 'sdio_event_id')) else 'NO_MATCH_TEAM_NAME',
            'sportsdataio_failure_reason': '' if _txt(_first(row, 'sportsdataio_event_id', 'sportsdataio_game_id', 'sdio_event_id')) else 'No SportsDataIO event id reached final_enriched_picks_df.',
            'api_football_fixture_id': _txt(_first(row, 'api_football_fixture_id', 'api_football_match_id', 'fixture_id')),
            'api_football_match_status': 'MATCHED' if _txt(_first(row, 'api_football_fixture_id', 'api_football_match_id', 'fixture_id')) else 'NO_MATCH_TEAM_NAME',
            'api_football_failure_reason': '' if _txt(_first(row, 'api_football_fixture_id', 'api_football_match_id', 'fixture_id')) else 'No API-Football fixture id reached final_enriched_picks_df.',
            'weather_status': weather_status,
            'weather_summary': _clean(_first(row, 'weather_summary', 'venue_weather', 'weather_risk')),
            'weather_failure_reason': weather_failure if weather_status != 'LIVE' else '',
            'news_status': news_status,
            'news_summary': news_summary,
            'news_failure_reason': news_failure if news_status != 'LIVE' else '',
            'perplexity_status': perplexity_status,
            'perplexity_context': perplexity_context,
            'perplexity_failure_reason': perplexity_failure if perplexity_status != 'LIVE' else '',
            'context': context,
            'sports_context_summary': context or ('Context unavailable because: ' + context_reason),
            'context_source': context_source,
            'context_status': context_status,
            'context_failure_reason': context_reason,
            'fallback_used': bool(fallback_used),
            'fallback_reason': fallback_reason,
            'cache_status': 'CACHE_CLEARED' if force_refresh else 'LIVE_REFRESH',
            'enrichment_status': 'FALLBACK_USED' if fallback_used else 'LIVE_ENRICHED',
            'data_freshness_status': 'CURRENT_RUN',
            'last_api_refresh_time': now,
            'report_run_id': report_run_id,
            'report_source': 'final_enriched_picks_df',
            'report_source_mode': 'current-run' if odds_status == 'LIVE' else 'saved-handoff',
            'report_source_label': 'Official +EV locked rows are being used.' if odds_status == 'LIVE' else 'Saved handoff rows are being used. Confirm this is the newest run before publishing.',
            'report_data_scope': 'Current API-refreshed slate' if odds_status == 'LIVE' else 'Price verification required',
            'report_truth_severity': 'LIVE VERIFIED' if odds_status == 'LIVE' and not line_blocked else 'VERIFY PRICE',
            'verification_status': 'LIVE VERIFIED' if odds_status == 'LIVE' and not line_blocked else 'VERIFY PRICE',
            'field_provenance_json': json.dumps(provenance, sort_keys=True),
            'source_trace_json': json.dumps({'raw_row_index': index, 'event_key': event_key}, sort_keys=True),
            'api_health_json': json.dumps(api_health, sort_keys=True),
            **shadow,
        })
        output.setdefault('injury_notes', '')
        output.setdefault('team_snapshot_home', '')
        output.setdefault('team_snapshot_away', '')
        output['matchup_notes'] = '\n'.join([f'What This Means: {beginner}', context or '', risk_reasons or ''])
        output['why_lose'] = '\n'.join([risk_reasons or 'Recheck price before entry.', 'Unverified model edge — price must be rechecked.' if odds_status != 'LIVE' else 'Live price matched.'])
        output['chain_notes'] = '\n'.join([
            'Parlay recommendations require at least two verified legs.',
            'Because this row is not live-source verified, ABA can only show watchlist ideas, not a bettable parlay.' if odds_status != 'LIVE' else 'Only use verified source-returned markets.',
            output.get('shadow_status_label', 'Shadow Mode: observing only'),
        ])
        output.setdefault('pro_bettor_evidence', '')
        output.setdefault('reparodynamics_status', 'OBSERVATION_ONLY')
        output.setdefault('reparodynamics_notes', 'No Reparodynamics annotation reached this row.')
        output.setdefault('repair_flags', '')
        output['enrichment_input_hash'] = _hash({key: output.get(key) for key in REQUIRED_REPORT_COLUMNS if key not in {'enrichment_input_hash', 'report_run_id', 'last_api_refresh_time'}})
        rows.append(output)

    final_enriched_picks_df = pd.DataFrame(rows)
    for column in REQUIRED_REPORT_COLUMNS:
        if column not in final_enriched_picks_df.columns:
            final_enriched_picks_df[column] = ''
    return final_enriched_picks_df


def validate_report_pipeline(df: Any) -> list[str]:
    frame = _frame(df)
    if frame.empty:
        return ['final_enriched_picks_df is empty']
    errors: list[str] = []
    for column in REQUIRED_REPORT_COLUMNS:
        if column not in frame.columns:
            errors.append('Missing required column: ' + column)
    for column in ('report_run_id', 'last_api_refresh_time', 'raw_input_hash', 'enrichment_input_hash'):
        if column not in frame or frame[column].map(_txt).eq('').any():
            errors.append(column + ' missing')
    if 'report_source' in frame and not frame['report_source'].astype(str).eq('final_enriched_picks_df').all():
        errors.append('report_source must be final_enriched_picks_df')
    if 'no_vig_status' in frame and 'odds_market_sides_available' in frame:
        bad = frame['no_vig_status'].astype(str).eq('CALCULATED') & ~frame['odds_market_sides_available'].astype(str).eq('FULL')
        if bool(bad.any()):
            errors.append('no-vig calculated with incomplete market sides')
    if 'shadow_mode' in frame and not frame['shadow_mode'].astype(str).eq('OBSERVING_ONLY').all():
        errors.append('Shadow Math must remain observing-only in this runtime.')
    return errors


def prepare_report_rows(rows: Any, force_refresh: bool = False) -> list[dict[str, Any]]:
    frame = _frame(rows)
    if force_refresh or frame.empty or 'report_source' not in frame.columns or not frame['report_source'].astype(str).eq('final_enriched_picks_df').all():
        frame = build_final_enriched_picks_df(frame, force_refresh=force_refresh)
    errors = validate_report_pipeline(frame)
    if errors:
        raise ValueError('Report pipeline validation failed: ' + '; '.join(errors))
    return frame.to_dict('records')


def install() -> None:
    try:
        from . import magazine_book_export as module
    except Exception:
        return
    if getattr(module, '_aba_final_enriched_pipeline_guard', False):
        return
    original_pages = module.render_full_magazine_book_pages
    original_page = module.render_full_pick_magazine_page
    original_pairs = module._pairs

    def guarded_pages(picks, *args, **kwargs):
        force_refresh = bool(kwargs.pop('force_refresh', False))
        return original_pages(prepare_report_rows(picks, force_refresh=force_refresh), *args, **kwargs)

    def guarded_page(pick, *args, **kwargs):
        force_refresh = bool(kwargs.pop('force_refresh', False))
        row = prepare_report_rows([pick], force_refresh=force_refresh)[0]
        return original_page(row, *args, **kwargs)

    def guarded_odds(row):
        data = row if isinstance(row, Mapping) else getattr(row, 'to_dict', lambda: {})()
        status = _txt(data.get('odds_status'))
        if status == 'LIVE':
            return 'LIVE_API Odds API'
        if status == 'UPLOADED_ROW':
            return 'UPLOADED_ROW odds'
        return status or 'EMPTY_WITH_REASON'

    def guarded_context(row):
        data = row if isinstance(row, Mapping) else getattr(row, 'to_dict', lambda: {})()
        context = _txt(data.get('context') or data.get('sports_context_summary'))
        reason = _txt(data.get('context_failure_reason'))
        beginner = _txt(data.get('beginner_explanation') or data.get('what_this_means'))
        lines = []
        if beginner:
            lines.append('What This Means: ' + beginner)
        if context and not _is_placeholder(context):
            lines.append(context)
        if not lines:
            lines.append('Context unavailable because: ' + (reason or 'no context reached final_enriched_picks_df'))
        return lines[:3]

    def guarded_pairs(row, lang):
        data = row if isinstance(row, Mapping) else getattr(row, 'to_dict', lambda: {})()
        diagnostics = [
            ('SOURCE', _txt(data.get('report_source')) or 'final_enriched_picks_df'),
            ('RUN', _txt(data.get('report_run_id'))[:18]),
            ('SHADOW', _txt(data.get('shadow_status_label')) or 'Shadow Mode: observing only'),
        ]
        return (diagnostics + original_pairs(row, lang))[:5]

    module.render_full_magazine_book_pages = guarded_pages
    module.render_full_pick_magazine_page = guarded_page
    module._odds_row_label = guarded_odds
    module._headline_context_lines = guarded_context
    module._pairs = guarded_pairs
    module._aba_final_enriched_pipeline_guard = True
