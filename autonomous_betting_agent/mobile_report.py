from __future__ import annotations

from typing import Any, Callable, Mapping

import pandas as pd

from .audit import audit_dashboard_metrics, clean_text, enrich_prediction_frame, parse_float, truthy

MOBILE_LABELS = {
    'event': 'Event',
    'sport': 'Sport',
    'start': 'Start',
    'prediction': 'Pick',
    'decision': 'Pick Status',
    'decision_reason': 'Why',
    'confidence_tier': 'Confidence Tier',
    'final_probability': 'Model Probability',
    'final_probability_value': 'Model Probability Raw',
    'best_price': 'Best Odds',
    'decimal_price': 'Decimal Odds',
    'american_odds': 'American Odds',
    'implied_probability': 'Break-even %',
    'estimated_ev_decimal': 'Estimated EV',
    'profit_units': 'Units',
    'roi_percent': 'ROI %',
    'clean_grading_status': 'Grade Status',
    'audit_inclusion': 'Audit Use',
}

PRIORITY_COLUMNS = (
    'event',
    'sport',
    'start',
    'prediction',
    'decision',
    'decision_reason',
    'confidence_tier',
    'final_probability',
    'best_price',
    'decimal_price',
    'american_odds',
    'implied_probability',
    'estimated_ev_decimal',
    'clean_grading_status',
    'audit_inclusion',
)

ACTIONABLE_TIERS = {'A+ High Confidence', 'A Strong', 'B Lean'}


def _has_column(frame: pd.DataFrame, name: str) -> bool:
    return name in frame.columns


def _series_text(frame: pd.DataFrame, name: str) -> pd.Series:
    if name not in frame.columns:
        return pd.Series([''] * len(frame), index=frame.index)
    return frame[name].fillna('').astype(str)


def _empty_like(value: Any) -> bool:
    text = clean_text(value)
    return text in {'', 'missing', 'none', 'null', 'nan', 'n/a', 'na', 'unknown'}


def _row_value(row: Mapping[str, Any], *names: str, default: str = '') -> Any:
    lowered = {str(key).lower().replace(' ', '_').replace('-', '_'): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.lower().replace(' ', '_').replace('-', '_'))
        if value not in (None, ''):
            return value
    return default


def compact_report_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    columns = [col for col in PRIORITY_COLUMNS if col in frame.columns]
    compact = frame[columns].copy()
    if 'decision' in compact.columns:
        compact['decision'] = compact['decision'].replace({'watch_only': 'Watch Only', 'skip': 'No Bet', 'candidate': 'Candidate', 'strong_candidate': 'Strong Candidate'})
    if 'decision_reason' in compact.columns:
        compact['decision_reason'] = compact['decision_reason'].replace({'Not strong enough for the shortlist.': 'No Bet: quality/odds did not clear the shortlist.'})
    for col in ('implied_probability',):
        if col in compact.columns:
            compact[col] = compact[col].map(lambda value: '' if _empty_like(value) else f'{float(value):.1%}' if parse_float(value) is not None and parse_float(value) <= 1 else value)
    return compact.rename(columns={col: MOBILE_LABELS.get(col, col.replace('_', ' ').title()) for col in compact.columns})


def rejection_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=['Issue', 'Count'])
    rows: list[dict[str, Any]] = []
    missing_decimal = ~_series_text(frame, 'decimal_price').map(lambda value: not _empty_like(value))
    missing_best = ~_series_text(frame, 'best_price').map(lambda value: not _empty_like(value))
    missing_odds = missing_decimal & missing_best
    if int(missing_odds.sum()):
        rows.append({'Issue': 'Missing odds / price', 'Count': int(missing_odds.sum())})
    probability_source = _series_text(frame, 'probability_source')
    missing_probability_source = probability_source.map(_empty_like)
    if int(missing_probability_source.sum()):
        rows.append({'Issue': 'Missing probability source', 'Count': int(missing_probability_source.sum())})
    decision = _series_text(frame, 'decision').map(clean_text)
    watch_only = decision.eq('watch only') | decision.eq('watch_only')
    if int(watch_only.sum()):
        rows.append({'Issue': 'Watch only / not actionable', 'Count': int(watch_only.sum())})
    quality = pd.to_numeric(frame.get('odds_quality_score', pd.Series([None] * len(frame))), errors='coerce')
    low_quality = quality.notna() & (quality < 70)
    if int(low_quality.sum()):
        rows.append({'Issue': 'Quality score below 70', 'Count': int(low_quality.sum())})
    ev = _series_text(frame, 'estimated_ev_decimal')
    missing_ev = ev.map(_empty_like)
    if int(missing_ev.sum()):
        rows.append({'Issue': 'EV unavailable', 'Count': int(missing_ev.sum())})
    review_needed = _series_text(frame, 'clean_grading_status').map(clean_text).eq('review needed') | _series_text(frame, 'clean_grading_status').map(clean_text).eq('review_needed')
    if int(review_needed.sum()):
        rows.append({'Issue': 'Needs manual review', 'Count': int(review_needed.sum())})
    return pd.DataFrame(rows or [{'Issue': 'No major rejection issue detected', 'Count': 0}])


def prepare_mobile_report(frame: pd.DataFrame) -> dict[str, Any]:
    enriched = enrich_prediction_frame(frame) if not frame.empty else pd.DataFrame()
    metrics = audit_dashboard_metrics(enriched)
    compact = compact_report_frame(enriched)
    rejection = rejection_summary(enriched)
    actionable = enriched[enriched.get('confidence_tier', pd.Series(dtype=str)).isin(ACTIONABLE_TIERS)] if not enriched.empty else pd.DataFrame()
    missing_odds_count = int((rejection.loc[rejection['Issue'] == 'Missing odds / price', 'Count'].sum())) if not rejection.empty else 0
    return {'enriched': enriched, 'compact': compact, 'rejection': rejection, 'metrics': metrics, 'actionable': actionable, 'missing_odds_count': missing_odds_count}


def _fmt_pct(value: Any) -> str:
    parsed = parse_float(value)
    if parsed is None:
        return ''
    return f'{parsed:.1%}' if parsed <= 1 else f'{parsed:.1f}%'


def _fmt_value(value: Any) -> str:
    if value is None or _empty_like(value):
        return 'Missing'
    return str(value)


def render_pick_cards(frame: pd.DataFrame, *, max_cards: int = 8) -> None:
    import streamlit as st

    if frame.empty:
        st.info('No actionable picks. Rows with missing odds, low quality, duplicates, or review flags stay out of the shortlist.')
        return
    for row in frame.head(max_cards).to_dict(orient='records'):
        event = _fmt_value(_row_value(row, 'event', 'game', 'match'))
        pick = _fmt_value(_row_value(row, 'prediction', 'pick'))
        tier = _fmt_value(_row_value(row, 'confidence_tier'))
        decision = _fmt_value(_row_value(row, 'decision'))
        reason = _fmt_value(_row_value(row, 'decision_reason', 'target_70_rejection_reason'))
        probability = _fmt_pct(_row_value(row, 'final_probability_value', 'final_probability'))
        odds = _fmt_value(_row_value(row, 'decimal_price', 'best_price'))
        ev = _fmt_value(_row_value(row, 'estimated_ev_decimal', 'estimated_ev_value'))
        st.markdown(f'**{event}**')
        st.caption(f'Pick: {pick} | Tier: {tier} | Status: {decision}')
        st.write(f'Model probability: {probability or "Missing"} | Odds: {odds} | EV: {ev}')
        st.caption(f'Why: {reason}')
        st.divider()


def render_mobile_predictor_report(frame: pd.DataFrame, *, table_renderer: Callable[..., Any] | None = None) -> Any:
    import streamlit as st

    prepared = prepare_mobile_report(frame)
    enriched = prepared['enriched']
    compact = prepared['compact']
    metrics = prepared['metrics']
    rejection = prepared['rejection']
    actionable = prepared['actionable']

    st.subheader('Mobile pick view')
    cols = st.columns(5)
    cols[0].metric('Rows', metrics['total_rows'])
    cols[1].metric('Actionable', len(actionable))
    cols[2].metric('Official graded', metrics['official_graded'])
    cols[3].metric('A+ picks', metrics['a_plus_count'])
    cols[4].metric('Missing odds', prepared['missing_odds_count'])

    if prepared['missing_odds_count']:
        st.warning('Odds are missing for part or all of this report. Profit, ROI, EV, and break-even rate cannot be trusted until best_price or decimal_price is filled.')

    st.caption('Best picks are shown as cards first. Watch-only and rejected rows stay in the compact/technical tables below.')
    render_pick_cards(actionable)

    with st.expander('Why rows were rejected or marked Watch Only', expanded=True):
        renderer = table_renderer or st.dataframe
        renderer(rejection, use_container_width=True, hide_index=True)

    with st.expander('Compact mobile table', expanded=True):
        renderer = table_renderer or st.dataframe
        renderer(compact, use_container_width=True, hide_index=True)

    with st.expander('Full technical table', expanded=False):
        renderer = table_renderer or st.dataframe
        return renderer(enriched, use_container_width=True, hide_index=True)
    return None
