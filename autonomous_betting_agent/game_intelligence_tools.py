from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .odds_lock_tools import parse_datetime_utc
from .proof_safety_tools import enrich_safety_columns
from .row_normalizer import normalize_frame, probability_value, safe_text

BOOK_COLUMNS = {
    'DraftKings': ['draftkings_decimal_price', 'draftkings_odds', 'dk_decimal_price'],
    'FanDuel': ['fanduel_decimal_price', 'fanduel_odds', 'fd_decimal_price'],
    'Bet365': ['bet365_decimal_price', 'bet365_odds'],
    'Pinnacle': ['pinnacle_decimal_price', 'pinnacle_odds'],
    'Local/Other': ['local_decimal_price', 'local_odds', 'other_decimal_price', 'other_odds'],
}

DISPLAY_COLUMNS = [
    'event', 'sport', 'market_type', 'prediction', 'model_probability', 'decimal_price',
    'best_available_price', 'best_available_book', 'fair_decimal_price', 'minimum_playable_decimal',
    'great_value_decimal', 'edge_percent', 'expected_value_percent', 'information_confidence_score',
    'market_disagreement_flag', 'market_disagreement_percent', 'data_quality_wall_pass',
    'data_quality_blockers', 'data_quality_warnings', 'shadow_proof_ready', 'game_intelligence_grade',
    'agent_decision', 'recommended_action', 'what_would_change_my_mind', 'game_intelligence_card',
]


def _num(value: Any) -> float | None:
    try:
        parsed = float(str(value).replace('%', '').replace(',', '').strip())
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _price(value: Any) -> float | None:
    parsed = _num(value)
    if parsed is None:
        return None
    if parsed >= 100:
        return 1.0 + parsed / 100.0
    if parsed <= -100:
        return 1.0 + 100.0 / abs(parsed)
    if parsed > 1.0:
        return parsed
    return None


def _prob(row: dict[str, Any]) -> float | None:
    return probability_value(row, 'model_probability') or probability_value(row, 'model_probability_clean')


def _future(row: dict[str, Any]) -> bool:
    parsed = parse_datetime_utc(row.get('event_start_utc'))
    return bool(parsed and parsed > datetime.now(timezone.utc))


def playable_odds_targets(model_probability: float | None, min_edge: float = 0.03, great_edge: float = 0.075) -> dict[str, Any]:
    if model_probability is None or not (0.0 < model_probability < 1.0):
        return {'fair_decimal_price': None, 'minimum_playable_decimal': None, 'great_value_decimal': None}
    return {
        'fair_decimal_price': round(1.0 / model_probability, 4),
        'minimum_playable_decimal': round(1.0 / max(0.01, model_probability - min_edge), 4),
        'great_value_decimal': round(1.0 / max(0.01, model_probability - great_edge), 4),
    }


def line_shop_table(row: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    base_book = safe_text(row.get('bookmaker') or row.get('odds_source')) or 'Entered price'
    base_price = _price(row.get('decimal_price') or row.get('best_price') or row.get('odds'))
    if base_price is not None:
        rows.append({'bookmaker': base_book, 'decimal_price': round(base_price, 6), 'source_column': 'decimal_price'})
    for bookmaker, columns in BOOK_COLUMNS.items():
        for column in columns:
            price = _price(row.get(column))
            if price is not None:
                rows.append({'bookmaker': bookmaker, 'decimal_price': round(price, 6), 'source_column': column})
                break
    if not rows:
        return pd.DataFrame(columns=['bookmaker', 'decimal_price', 'implied_probability', 'edge_percent', 'expected_value_percent'])
    out = pd.DataFrame(rows).drop_duplicates(subset=['bookmaker', 'decimal_price'])
    out['implied_probability'] = (1.0 / pd.to_numeric(out['decimal_price'], errors='coerce')).round(6)
    probability = _prob(row)
    if probability is None:
        out['edge_percent'] = None
        out['expected_value_percent'] = None
    else:
        out['edge_percent'] = ((probability - out['implied_probability']) * 100.0).round(3)
        out['expected_value_percent'] = ((probability * pd.to_numeric(out['decimal_price'], errors='coerce') - 1.0) * 100.0).round(3)
    return out.sort_values('decimal_price', ascending=False).reset_index(drop=True)


def best_line(row: dict[str, Any]) -> dict[str, Any]:
    table = line_shop_table(row)
    if table.empty:
        return {'best_available_price': None, 'best_available_book': '', 'line_shop_count': 0, 'price_gap_percent': None}
    best = table.iloc[0].to_dict()
    worst = table.iloc[-1].to_dict()
    best_price = _price(best.get('decimal_price'))
    worst_price = _price(worst.get('decimal_price'))
    gap = round(((best_price / worst_price) - 1.0) * 100.0, 3) if best_price and worst_price else None
    return {'best_available_price': best_price, 'best_available_book': safe_text(best.get('bookmaker')), 'line_shop_count': int(len(table)), 'price_gap_percent': gap}


def information_confidence(row: dict[str, Any]) -> dict[str, Any]:
    quality = _num(row.get('odds_accuracy_score')) or 0.0
    books = _num(row.get('book_count_normalized') or row.get('bookmaker_count') or row.get('books')) or 0.0
    notes = safe_text(row.get('manual_context_notes'))
    context = 90.0 if any(word in notes.lower() for word in ['confirmed', 'official', 'lineup', 'starter']) else 75.0 if notes else 35.0
    score = round(quality * 0.35 + min(100.0, books * 20.0) * 0.20 + context * 0.15 + (100.0 if _future(row) else 20.0) * 0.10 + (100.0 if _price(row.get('decimal_price')) else 0.0) * 0.10 + (100.0 if _prob(row) else 0.0) * 0.10, 2)
    return {'information_confidence_score': score, 'context_info_score': context, 'market_depth_score': round(min(100.0, books * 20.0), 2)}


def market_disagreement(row: dict[str, Any]) -> dict[str, Any]:
    probability = _prob(row)
    market = _num(row.get('market_implied_probability'))
    if probability is None or market is None:
        return {'market_disagreement_flag': 'insufficient_data', 'market_disagreement_percent': None}
    diff = round((probability - market) * 100.0, 3)
    abs_diff = abs(diff)
    if abs_diff >= 18.0:
        flag = 'extreme_review_required'
    elif abs_diff >= 12.0:
        flag = 'large_disagreement_review'
    elif abs_diff >= 7.0:
        flag = 'meaningful_edge_or_missing_info'
    else:
        flag = 'normal_range'
    return {'market_disagreement_flag': flag, 'market_disagreement_percent': diff}


def change_mind_rules(row: dict[str, Any]) -> str:
    targets = playable_odds_targets(_prob(row))
    sport = safe_text(row.get('sport')).lower()
    market = safe_text(row.get('market_type')).lower()
    items: list[str] = []
    if targets.get('minimum_playable_decimal'):
        items.append(f'available odds drop below {targets["minimum_playable_decimal"]}')
    if 'baseball' in sport or 'mlb' in sport:
        items.append('starting pitcher or lineup changes')
    if any(term in sport for term in ['nba', 'wnba', 'basketball']):
        items.append('key player ruled out, rest news, or minutes restriction')
    if any(term in sport for term in ['soccer', 'football']):
        items.append('major lineup rotation or keeper change')
    if market in {'totals', 'spreads'}:
        items.append('line moves materially against the pick')
    items.append('new injury, weather, travel, or market news contradicts current notes')
    return '; '.join(items)


def data_quality_wall(row: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    for field in ['event', 'prediction']:
        if not safe_text(row.get(field)):
            blockers.append(f'missing_{field}')
    if _prob(row) is None:
        blockers.append('missing_model_probability')
    if _price(row.get('decimal_price')) is None:
        blockers.append('missing_decimal_price')
    if not safe_text(row.get('bookmaker')) and not safe_text(row.get('odds_source')):
        blockers.append('missing_bookmaker_or_source')
    if not _future(row):
        warnings.append('not_future_event')
    ev = _num(row.get('expected_value_per_unit'))
    if ev is not None and ev <= 0:
        warnings.append('non_positive_ev')
    quality = _num(row.get('odds_accuracy_score'))
    if quality is not None and quality < 65:
        warnings.append('odds_quality_below_65')
    manual = abs(_num(row.get('manual_probability_adjustment')) or 0.0)
    if manual > 1.0:
        manual /= 100.0
    if manual >= 0.03 and not safe_text(row.get('manual_context_notes')):
        blockers.append('manual_adjustment_needs_notes')
    return {'data_quality_wall_pass': not blockers and not warnings, 'data_quality_blockers': '; '.join(blockers), 'data_quality_warnings': '; '.join(warnings)}


def intelligence_grade(row: dict[str, Any]) -> str:
    info = _num(row.get('information_confidence_score')) or 0.0
    ev = _num(row.get('expected_value_per_unit')) or 0.0
    disagreement = safe_text(row.get('market_disagreement_flag'))
    if row.get('data_quality_wall_pass') and info >= 82 and ev >= 0.08 and disagreement != 'extreme_review_required':
        return 'operator_grade_A+'
    if info >= 72 and ev > 0 and disagreement != 'extreme_review_required':
        return 'operator_grade_A'
    if info >= 60 and ev > -0.02:
        return 'operator_grade_B_review'
    if disagreement == 'extreme_review_required':
        return 'operator_grade_C_extreme_review'
    return 'operator_grade_D_skip'


def card_markdown(row: dict[str, Any]) -> str:
    event = safe_text(row.get('event')) or 'Unknown event'
    pick = safe_text(row.get('prediction')) or 'Unknown pick'
    lines = [f'### {event}', f'**Pick:** {pick}']
    probability = _prob(row)
    if probability is not None:
        lines.append(f'**Model probability:** {probability * 100:.1f}%')
    for label, key, suffix in [('Current odds', 'decimal_price', ''), ('Best odds', 'best_available_price', ''), ('EV', 'expected_value_percent', '%'), ('Edge', 'edge_percent', ' pts'), ('Info confidence', 'information_confidence_score', '/100')]:
        value = _num(row.get(key))
        if value is not None:
            lines.append(f'**{label}:** {value:.2f}{suffix}')
    lines.append(f'**Minimum playable odds:** {row.get("minimum_playable_decimal") or "N/A"}')
    lines.append(f'**Great value odds:** {row.get("great_value_decimal") or "N/A"}')
    lines.append(f'**Market disagreement:** {safe_text(row.get("market_disagreement_flag")) or "N/A"}')
    lines.append(f'**Data quality wall:** {"PASS" if row.get("data_quality_wall_pass") else "REVIEW"}')
    lines.append(f'**Recommended action:** {safe_text(row.get("recommended_action")) or safe_text(row.get("agent_decision")) or "review"}')
    change = safe_text(row.get('what_would_change_my_mind'))
    if change:
        lines.append(f'**What would change my mind:** {change}')
    return '\n\n'.join(lines)


def agent_answer(row: dict[str, Any], question: str) -> str:
    q = safe_text(question).lower()
    if 'lock' in q or 'ready' in q:
        if row.get('shadow_proof_ready'):
            return 'This row is ready for internal shadow proof review, assuming the displayed price is still available.'
        return f"Needs review. Blockers: {safe_text(row.get('data_quality_blockers')) or 'none'}. Warnings: {safe_text(row.get('data_quality_warnings')) or 'none'}."
    if 'missing' in q or 'need' in q:
        return safe_text(row.get('needed_info')) or safe_text(row.get('data_quality_blockers')) or 'No critical missing fields detected.'
    if 'odds' in q or 'price' in q:
        return f"Fair odds: {row.get('fair_decimal_price') or 'N/A'}. Minimum playable: {row.get('minimum_playable_decimal') or 'N/A'}. Great value: {row.get('great_value_decimal') or 'N/A'}. Best available: {row.get('best_available_price') or 'N/A'} at {safe_text(row.get('best_available_book')) or 'N/A'}."
    if 'change' in q or 'mind' in q:
        return safe_text(row.get('what_would_change_my_mind')) or 'No change-my-mind rules generated.'
    if 'ev' in q or 'value' in q:
        return f"EV: {row.get('expected_value_percent') or 'N/A'}%. Edge: {row.get('edge_percent') or 'N/A'} percentage points. Rating: {safe_text(row.get('value_rating')) or 'N/A'}."
    return safe_text(row.get('game_intelligence_card')) or 'No game card available.'


def enrich_game_intelligence(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    normalized = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if normalized.empty:
        return pd.DataFrame()
    safety = enrich_safety_columns(normalized)
    rows: list[dict[str, Any]] = []
    for row in safety.to_dict(orient='records'):
        item = dict(row)
        item.update(best_line(item))
        best = _price(item.get('best_available_price'))
        current = _price(item.get('decimal_price'))
        if best and (current is None or best > current):
            item['original_entered_decimal_price'] = item.get('decimal_price')
            item['decimal_price'] = round(best, 6)
            item['bookmaker'] = item.get('best_available_book') or item.get('bookmaker')
        item.update(playable_odds_targets(_prob(item)))
        item.update(information_confidence(item))
        item.update(market_disagreement(item))
        item['what_would_change_my_mind'] = change_mind_rules(item)
        item.update(data_quality_wall(item))
        item['shadow_proof_ready'] = bool(_future(item) and not item.get('data_quality_blockers') and _prob(item) is not None and _price(item.get('decimal_price')) is not None)
        item['shadow_proof_label'] = 'internal_shadow_only' if item['shadow_proof_ready'] else ''
        item['game_intelligence_grade'] = intelligence_grade(item)
        item['game_intelligence_card'] = card_markdown(item)
        rows.append(item)
    return pd.DataFrame(rows)


def display_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in DISPLAY_COLUMNS if column in frame.columns]


def shadow_proof_frame(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    enriched = enrich_game_intelligence(frame)
    if enriched.empty or 'shadow_proof_ready' not in enriched.columns:
        return pd.DataFrame()
    out = enriched[enriched['shadow_proof_ready'].astype(bool)].copy()
    if out.empty:
        return out
    out['shadow_checked_at_utc'] = datetime.now(timezone.utc).isoformat()
    out['proof_mode'] = 'internal_shadow_not_public'
    return out


def operator_daily_report(frame: pd.DataFrame | list[dict[str, Any]]) -> str:
    enriched = enrich_game_intelligence(frame)
    if enriched.empty:
        return 'No rows available for the operator report.'
    candidates = int(enriched.get('shadow_proof_ready', pd.Series(dtype=bool)).fillna(False).astype(bool).sum())
    review = int(enriched.get('data_quality_wall_pass', pd.Series(dtype=bool)).fillna(False).astype(bool).eq(False).sum())
    lines = ['# Daily Operator Report', '', f'Total rows reviewed: {len(enriched)}', f'Internal shadow candidates: {candidates}', f'Rows needing review: {review}', '', '## Top board']
    for index, row in enumerate(enriched.head(10).to_dict(orient='records'), start=1):
        lines.append(f"{index}. {safe_text(row.get('prediction')) or 'Pick'} — {safe_text(row.get('event')) or 'Event'} | Grade: {safe_text(row.get('game_intelligence_grade')) or 'N/A'} | Action: {safe_text(row.get('recommended_action')) or safe_text(row.get('agent_decision')) or 'review'}")
    lines.extend(['', '## Reminder', 'This is internal analytics output. Public proof still requires official lock rows created before event start.'])
    return '\n'.join(lines)
