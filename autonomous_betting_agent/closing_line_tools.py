from __future__ import annotations

import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Mapping

import pandas as pd

from .commercial_platform_tools import filter_locked_proof_rows
from .live_odds import fetch_odds, summarize_event
from .row_normalizer import safe_text

PENDING_STATUSES = {'', 'pending', 'unknown', 'scheduled', 'live'}


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _clean(value: Any) -> str:
    return ' '.join(safe_text(value).lower().replace('-', ' ').replace('_', ' ').replace('@', ' at ').split())


def _similarity(left: Any, right: Any) -> float:
    a, b = _clean(left), _clean(right)
    if not a or not b:
        return 0.0
    if a == b or a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _date_prefix(value: Any) -> str:
    text = safe_text(value)
    return text[:10] if len(text) >= 10 else ''


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _numbers(value: Any) -> list[float]:
    return [float(match) for match in re.findall(r'[+-]?\d+(?:\.\d+)?', safe_text(value))]


def _event_name(summary: Any) -> str:
    away = safe_text(getattr(summary, 'away_team', ''))
    home = safe_text(getattr(summary, 'home_team', ''))
    return f'{away} at {home}' if away and home else safe_text(getattr(summary, 'event_id', ''))


def _market_alias(value: Any) -> str:
    text = _clean(value)
    if text in {'moneyline', 'ml', 'h2h', 'winner'}:
        return 'h2h'
    if 'spread' in text or 'handicap' in text or re.search(r'(^|\s)[+-]\d+(?:\.\d+)?(\s|$)', safe_text(value)):
        return 'spreads'
    if 'total' in text or 'over' in text or 'under' in text:
        return 'totals'
    return text


def _line_value(row: Mapping[str, Any]) -> float | None:
    for key in ('line_point', 'point', 'spread', 'total', 'closing_line_point'):
        parsed = _safe_float(row.get(key))
        if parsed is not None:
            return parsed
    numbers = _numbers(row.get('prediction'))
    return numbers[-1] if numbers else None


def _line_score(ledger_row: Mapping[str, Any], outcome: Any) -> float:
    ledger_line = _line_value(ledger_row)
    outcome_line = getattr(outcome, 'point', None)
    outcome_line = _safe_float(outcome_line)
    if ledger_line is None or outcome_line is None:
        return 0.0
    if abs(abs(ledger_line) - abs(outcome_line)) < 1e-9:
        return 1.0
    return 0.0


def _side_score(ledger_row: Mapping[str, Any], outcome: Any) -> float:
    prediction = _clean(ledger_row.get('prediction'))
    outcome_name = _clean(getattr(outcome, 'name', ''))
    if not prediction or not outcome_name:
        return 0.0
    if outcome_name in prediction or prediction in outcome_name:
        return 1.0
    if ('over' in prediction and 'over' in outcome_name) or ('under' in prediction and 'under' in outcome_name):
        return 1.0
    return _similarity(prediction, outcome_name)


def _pick_match_score(ledger_row: Mapping[str, Any], outcome: Any) -> float:
    market = _market_alias(ledger_row.get('market_type') or ledger_row.get('prediction'))
    outcome_market = _market_alias(getattr(outcome, 'market', ''))
    if market and outcome_market and market != outcome_market:
        return 0.0
    side_score = _side_score(ledger_row, outcome)
    line_score = _line_score(ledger_row, outcome)
    if market in {'spreads', 'totals'}:
        return side_score * 0.65 + line_score * 0.35
    return side_score


def _best_event_match(ledger_row: Mapping[str, Any], summaries: list[Any]) -> tuple[Any | None, float]:
    best = None
    best_score = 0.0
    ledger_date = _date_prefix(ledger_row.get('event_start_utc'))
    for summary in summaries:
        event_score = _similarity(ledger_row.get('event'), _event_name(summary))
        sport_score = max(_similarity(ledger_row.get('sport_key'), getattr(summary, 'sport_key', '')), _similarity(ledger_row.get('sport'), getattr(summary, 'sport_title', '')))
        date_score = 1.0 if ledger_date and ledger_date == _date_prefix(getattr(summary, 'commence_time', '')) else 0.0
        score = event_score * 0.70 + sport_score * 0.15 + date_score * 0.15
        if score > best_score:
            best_score = score
            best = summary
    return best, best_score


def _eligible_sport_keys(ledger: pd.DataFrame) -> list[str]:
    values: set[str] = set()
    for col in ('sport_key', 'sport'):
        if col in ledger.columns:
            for value in ledger[col].dropna().astype(str):
                text = safe_text(value)
                if text and '_' in text:
                    values.add(text)
    return sorted(values)


def _closing_coverage(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {'rows': 0, 'closing_rows': 0, 'closing_coverage': 0.0}
    closing = frame.get('closing_decimal_price', pd.Series(dtype=str)).map(safe_text).ne('')
    return {
        'rows': int(len(frame)),
        'closing_rows': int(closing.sum()),
        'closing_coverage': round(float(closing.mean()), 6),
    }


def collect_closing_lines(
    ledger: pd.DataFrame | list[dict[str, Any]],
    *,
    api_key: str,
    sport_key: str,
    regions: str = 'us,eu,uk',
    markets: str = 'h2h,spreads,totals',
    event_threshold: float = 0.82,
    pick_threshold: float = 0.70,
    overwrite_existing: bool = False,
    pending_only: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    locked = filter_locked_proof_rows(ledger)
    if locked.empty:
        return pd.DataFrame(), {'updated_rows': 0, 'checked_rows': 0, 'matched_events': 0, 'matched_picks': 0, 'reason': 'empty_ledger'}

    odds_payload = fetch_odds(api_key, sport_key=sport_key, regions=regions, markets=markets)
    summaries = [summary for event in odds_payload for summary in [summarize_event(event)] if summary is not None]
    if not summaries:
        out = locked.copy()
        out['closing_collection_status'] = out.get('closing_collection_status', 'no_current_odds')
        return out, {'updated_rows': 0, 'checked_rows': int(len(locked)), 'matched_events': 0, 'matched_picks': 0, 'reason': 'no_current_odds', **_closing_coverage(out)}

    rows: list[dict[str, Any]] = []
    updated = 0
    matched_events = 0
    matched_picks = 0
    skipped_existing = 0
    skipped_resolved = 0
    skipped_sport = 0
    collected_at = _now_utc()
    wanted_sport = _clean(sport_key)

    for row in locked.to_dict(orient='records'):
        item = dict(row)
        status = safe_text(item.get('result_status')).lower()
        if pending_only and status not in PENDING_STATUSES:
            item['closing_collection_status'] = 'skipped_resolved'
            skipped_resolved += 1
            rows.append(item)
            continue
        if safe_text(item.get('closing_decimal_price')) and not overwrite_existing:
            item['closing_collection_status'] = 'already_collected'
            skipped_existing += 1
            rows.append(item)
            continue
        row_sport = _clean(item.get('sport_key') or item.get('sport'))
        if wanted_sport and row_sport and wanted_sport not in row_sport and row_sport not in wanted_sport:
            item['closing_collection_status'] = 'skipped_other_sport'
            skipped_sport += 1
            rows.append(item)
            continue
        summary, event_score = _best_event_match(item, summaries)
        if summary is None or event_score < event_threshold:
            item['closing_collection_status'] = 'no_event_match'
            item['closing_event_match_confidence'] = round(event_score, 4)
            rows.append(item)
            continue
        matched_events += 1
        best_outcome = None
        best_pick_score = 0.0
        for outcome in getattr(summary, 'outcomes', []) or []:
            score = _pick_match_score(item, outcome)
            if score > best_pick_score:
                best_pick_score = score
                best_outcome = outcome
        if best_outcome is None or best_pick_score < pick_threshold:
            item['closing_collection_status'] = 'no_pick_match'
            item['closing_event_match_confidence'] = round(event_score, 4)
            item['closing_pick_match_confidence'] = round(best_pick_score, 4)
            rows.append(item)
            continue
        matched_picks += 1
        item['closing_decimal_price'] = round(float(best_outcome.average_price), 6)
        item['closing_collected_at_utc'] = collected_at
        item['closing_source'] = 'the_odds_api_current_odds'
        item['closing_collection_status'] = 'collected'
        item['closing_event_match_confidence'] = round(event_score, 4)
        item['closing_pick_match_confidence'] = round(best_pick_score, 4)
        item['closing_match_confidence'] = round(event_score * 0.65 + best_pick_score * 0.35, 4)
        item['closing_market_type'] = safe_text(getattr(best_outcome, 'market', ''))
        item['closing_line_point'] = '' if getattr(best_outcome, 'point', None) is None else getattr(best_outcome, 'point')
        item['closing_bookmaker_count'] = int(getattr(best_outcome, 'source_count', 0) or 0)
        updated += 1
        rows.append(item)

    out = pd.DataFrame(rows)
    return out, {
        'updated_rows': updated,
        'checked_rows': int(len(locked)),
        'matched_events': matched_events,
        'matched_picks': matched_picks,
        'skipped_existing': skipped_existing,
        'skipped_resolved': skipped_resolved,
        'skipped_other_sport': skipped_sport,
        'sport_key': sport_key,
        'collected_at_utc': collected_at,
        **_closing_coverage(out),
        'note': 'Current odds were saved as closing_decimal_price. For best CLV, run this close to event start before the market disappears.',
    }


def collect_closing_lines_for_all_sports(
    ledger: pd.DataFrame | list[dict[str, Any]],
    *,
    api_key: str,
    regions: str = 'us,eu,uk',
    markets: str = 'h2h,spreads,totals',
    overwrite_existing: bool = False,
    pending_only: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    locked = filter_locked_proof_rows(ledger)
    if locked.empty:
        return pd.DataFrame(), {'updated_rows': 0, 'sport_runs': [], 'reason': 'empty_ledger'}
    sport_keys = _eligible_sport_keys(locked)
    if not sport_keys:
        return locked, {'updated_rows': 0, 'sport_runs': [], 'reason': 'no_sport_keys', **_closing_coverage(locked)}
    current = locked.copy()
    runs: list[dict[str, Any]] = []
    total_updated = 0
    for sport_key in sport_keys:
        current, stats = collect_closing_lines(
            current,
            api_key=api_key,
            sport_key=sport_key,
            regions=regions,
            markets=markets,
            overwrite_existing=overwrite_existing,
            pending_only=pending_only,
        )
        runs.append(stats)
        total_updated += int(stats.get('updated_rows', 0) or 0)
    return current, {'updated_rows': total_updated, 'sport_keys': sport_keys, 'sport_runs': runs, **_closing_coverage(current)}
