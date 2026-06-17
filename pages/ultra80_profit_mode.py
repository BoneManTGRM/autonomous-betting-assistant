from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.agent_decision_engine import build_agent_decisions
from autonomous_betting_agent.four_tool_orchestrator import page_health, page_health_frame

st.set_page_config(page_title='Ultra 70 Profit Mode', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='ultra80_profit_mode_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'Ultra 70 Lock + Profit Mode',
        'caption': 'Locks 70%+ positive-value rows for Odds Lock Pro, while keeping strict 80% proof and watch rows separate.',
        'source': 'Prediction source', 'session': 'Use latest Pro Predictor session', 'upload': 'Upload Pro Predictor CSV', 'upload_label': 'Upload CSV',
        'run': 'Build Ultra 70 value-lock list', 'no_rows': 'No rows available. Run Pro Predictor first or upload a CSV.',
        'no_pass': 'No rows passed the selected tier. That is normal when the filters are strict.',
        'all_rows': 'All reviewed rows', 'strict_rows': 'A — Strict 80 proof', 'max_rows_tab': 'B+ — Ultra 70 positive-value locks', 'reserve_rows': 'C — Value watch / review', 'selected_rows': 'Selected handoff',
        'download': 'Download selected CSV', 'download_strict': 'Download strict 80 proof CSV', 'download_all': 'Download reviewed CSV',
        'reviewed': 'Rows reviewed', 'strict': 'Strict 80 proof', 'max_profit': 'B+ value locks', 'reserve': 'Watch/review', 'handoff': 'Handoff rows', 'avg_prob': 'Avg model probability', 'avg_ev': 'Avg EV/unit', 'avg_profit70': 'Avg profit at 70%', 'next': 'Next action',
        'rules': 'Tier rules',
        'rule_text': 'A = strict 80% proof tier. B+ = Ultra 70 lock tier: 70%+ model probability AND positive value checks. C = 70% weak-value favorites plus 60–70% positive-value watch rows. Only A+B+ should be sent to Odds Lock Pro by default.',
        'proof': 'Lock before start time. Track A, B+, and C separately. B+ is the practical Ultra 70 value-lock list; A remains the only strict 80% proof tier.',
        'handoff_mode': 'Handoff mode', 'strict_only': 'A only — strict 80 proof', 'max_volume': 'A+B+ — Ultra 70 value locks', 'research_volume': 'A+B+C — value locks plus watch',
        'one_per_event': 'Keep only the best pick per event', 'max_a': 'Max A rows', 'max_b': 'Max B+ rows', 'max_c': 'Max C rows',
        'saved': 'Selected rows saved as the active handoff list for Odds Lock Pro.', 'blockers': 'Top rejection/blocker reasons', 'quality_note': 'Conflict guard active: when multiple picks come from the same event, the system keeps the strongest row by tier quality score.',
        'robust_note': 'Ultra 70 now requires value for the lock tier: probability 70%+ is not enough by itself. Negative-EV or negative-edge favorites are moved to watch/review instead of Odds Lock Pro.',
    },
    'es': {
        'title': 'Modo Ultra 70 Bloqueo + Rentabilidad',
        'caption': 'Bloquea filas de 70%+ con valor positivo para Odds Lock Pro y mantiene la prueba estricta 80% y filas de revisión separadas.',
        'source': 'Fuente de predicciones', 'session': 'Usar última sesión de Predictor Pro', 'upload': 'Subir CSV de Predictor Pro', 'upload_label': 'Subir CSV',
        'run': 'Crear lista Ultra 70 con valor', 'no_rows': 'No hay filas disponibles. Ejecuta Predictor Pro primero o sube un CSV.',
        'no_pass': 'Ninguna fila pasó el nivel seleccionado. Eso es normal con filtros estrictos.',
        'all_rows': 'Todas las filas revisadas', 'strict_rows': 'A — Prueba estricta 80', 'max_rows_tab': 'B+ — Bloqueos Ultra 70 con valor', 'reserve_rows': 'C — Valor vigilancia / revisión', 'selected_rows': 'Traspaso seleccionado',
        'download': 'Descargar CSV seleccionado', 'download_strict': 'Descargar CSV prueba estricta 80', 'download_all': 'Descargar CSV revisado',
        'reviewed': 'Filas revisadas', 'strict': 'Prueba estricta 80', 'max_profit': 'B+ bloqueos con valor', 'reserve': 'Vigilar/revisar', 'handoff': 'Filas traspaso', 'avg_prob': 'Probabilidad promedio', 'avg_ev': 'EV promedio/unidad', 'avg_profit70': 'Ganancia promedio al 70%', 'next': 'Siguiente acción',
        'rules': 'Reglas por nivel',
        'rule_text': 'A = prueba estricta 80%. B+ = nivel Ultra 70 bloqueable: 70%+ probabilidad del modelo Y controles de valor positivo. C = favoritos 70% con valor débil más filas 60–70% con valor positivo para vigilar. Por defecto solo A+B+ debe ir a Odds Lock Pro.',
        'proof': 'Bloquear antes del inicio. Rastrear A, B+ y C por separado. B+ es la lista práctica Ultra 70 con valor; A sigue siendo el único nivel de prueba estricta 80%.',
        'handoff_mode': 'Modo de traspaso', 'strict_only': 'Solo A — prueba estricta 80', 'max_volume': 'A+B+ — Bloqueos Ultra 70 con valor', 'research_volume': 'A+B+C — bloqueos con valor más vigilancia',
        'one_per_event': 'Mantener solo el mejor pick por evento', 'max_a': 'Máx filas A', 'max_b': 'Máx filas B+', 'max_c': 'Máx filas C',
        'saved': 'Filas seleccionadas guardadas como lista activa para Odds Lock Pro.', 'blockers': 'Principales razones de rechazo/bloqueo', 'quality_note': 'Protección de conflicto activa: cuando salen varios picks del mismo evento, el sistema conserva la fila más fuerte según el puntaje de calidad del nivel.',
        'robust_note': 'Ultra 70 ahora requiere valor para bloquear: 70%+ de probabilidad no basta por sí solo. Favoritos con EV negativo o ventaja negativa pasan a vigilar/revisar en vez de Odds Lock Pro.',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def pct(value: Any) -> str:
    number = pd.to_numeric(pd.Series([value]), errors='coerce').iloc[0]
    if pd.isna(number):
        return 'N/A'
    return f'{float(number) * 100:.1f}%'


def load_session_frame() -> pd.DataFrame:
    for key in ('pro_predictor_all_rows', 'pro_predictor_high_confidence_rows', 'pro_predictor_latest_rows', 'ara_latest_predictions'):
        rows = st.session_state.get(key)
        if isinstance(rows, list) and rows:
            return pd.DataFrame(rows)
    return pd.DataFrame()


def clean_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame is None or frame.empty or column not in frame.columns:
        return pd.Series(index=frame.index if frame is not None else None, dtype=float)
    values = pd.to_numeric(frame[column], errors='coerce')
    percent_like = {
        'ultra80_profit_at_80_percent', 'profit_at_80_percent', 'expected_value_per_unit',
        'model_market_edge', 'pattern_ara_memory_signal', '_robust_expected_value',
        '_robust_profit_at_80_percent', '_robust_profit_at_70_percent', '_price_range_risk',
        'computed_ev_decimal', 'estimated_ev_decimal', 'model_edge',
    }
    if 'prob' in column.lower() or column in percent_like:
        values = values.where(values <= 1.0, values / 100.0)
    return values


def text_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame is None or frame.empty or column not in frame.columns:
        return pd.Series('', index=frame.index if frame is not None else None, dtype=str)
    return frame[column].fillna('').astype(str).str.lower().str.strip()


def bool_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame is None or frame.empty or column not in frame.columns:
        return pd.Series(False, index=frame.index if frame is not None else None, dtype=bool)
    return text_series(frame, column).isin(['true', '1', 'yes', 'y', 'pass'])


def source_frame() -> tuple[pd.DataFrame, str]:
    choice = st.radio(t('source'), [t('session'), t('upload')], horizontal=True)
    if choice == t('upload'):
        upload = st.file_uploader(t('upload_label'), type=['csv'], key='ultra80_upload_csv')
        if upload is None:
            return pd.DataFrame(), 'upload'
        try:
            return pd.read_csv(upload), getattr(upload, 'name', 'uploaded_csv')
        except Exception as exc:
            st.error(str(exc))
            return pd.DataFrame(), 'upload_error'
    return load_session_frame(), 'session'


def non_hard_blocked(frame: pd.DataFrame) -> pd.Series:
    reasons = text_series(frame, 'ultra80_reasons') + ' | ' + text_series(frame, 'decision_reasons')
    hard_tokens = (
        'historical_result_present', 'bad_timing', 'prediction_timestamp_not_before_start',
        'event_already_started_without_prediction_timestamp', 'missing_event', 'missing_prediction',
        'missing_model_probability', 'missing_decimal_price', 'blocks_draws', 'negative_line_movement',
    )
    blocked = pd.Series(False, index=frame.index)
    for token in hard_tokens:
        blocked = blocked | reasons.str.contains(token, regex=False)
    return ~blocked


def conservative_price(frame: pd.DataFrame) -> pd.Series:
    worst = clean_numeric(frame, 'worst_price')
    average = clean_numeric(frame, 'average_price')
    decimal = clean_numeric(frame, 'decimal_price').fillna(clean_numeric(frame, 'best_price'))
    return worst.fillna(average).fillna(decimal)


def price_range_risk(frame: pd.DataFrame) -> pd.Series:
    explicit = clean_numeric(frame, 'price_range')
    best = clean_numeric(frame, 'decimal_price').fillna(clean_numeric(frame, 'best_price'))
    conservative = conservative_price(frame)
    return explicit.fillna((best - conservative).abs()).fillna(0.0)


def add_robust_profit_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    probability = clean_numeric(out, 'model_probability_clean').fillna(clean_numeric(out, 'model_probability'))
    robust_price = conservative_price(out)
    out['_robust_decimal_price'] = robust_price
    out['_robust_expected_value'] = probability * robust_price - 1.0
    out['_robust_profit_at_80_percent'] = 0.80 * robust_price - 1.0
    out['_robust_profit_at_70_percent'] = 0.70 * robust_price - 1.0
    out['_price_range_risk'] = price_range_risk(out)
    return out


def value_series(frame: pd.DataFrame) -> pd.Series:
    raw_ev = clean_numeric(frame, 'expected_value_per_unit')
    raw_ev = raw_ev.fillna(clean_numeric(frame, 'computed_ev_decimal'))
    raw_ev = raw_ev.fillna(clean_numeric(frame, 'estimated_ev_decimal'))
    raw_ev = raw_ev.fillna(clean_numeric(frame, '_robust_expected_value'))
    return raw_ev


def edge_series(frame: pd.DataFrame) -> pd.Series:
    return clean_numeric(frame, 'model_market_edge').fillna(clean_numeric(frame, 'model_edge'))


def quality_score(frame: pd.DataFrame) -> pd.Series:
    probability = clean_numeric(frame, 'model_probability_clean').fillna(clean_numeric(frame, 'model_probability')).fillna(0.0)
    ev = value_series(frame).fillna(0.0)
    profit70 = clean_numeric(frame, '_robust_profit_at_70_percent').fillna(0.0)
    profit80 = clean_numeric(frame, 'ultra80_profit_at_80_percent').fillna(clean_numeric(frame, '_robust_profit_at_80_percent')).fillna(0.0)
    robust_ev = clean_numeric(frame, '_robust_expected_value').fillna(ev).fillna(0.0)
    price_risk = clean_numeric(frame, '_price_range_risk').fillna(0.0)
    edge = edge_series(frame).fillna(0.0)
    agent_score = clean_numeric(frame, 'agent_score').fillna(0.0) / 100.0
    scanner = clean_numeric(frame, 'scanner_strength_score').fillna(0.0) / 100.0
    pattern = clean_numeric(frame, 'pattern_ara_memory_signal').fillna(clean_numeric(frame, 'ara_memory_signal')).fillna(0.0)
    return (probability * 50.0) + (edge.clip(-0.10, 0.20) * 80.0) + (ev.clip(-0.10, 0.25) * 35.0) + (profit70.clip(-0.10, 0.25) * 25.0) + (profit80.clip(-0.10, 0.25) * 10.0) + (robust_ev.clip(-0.10, 0.25) * 35.0) + (agent_score * 15.0) + (scanner * 8.0) + (pattern.clip(-0.05, 0.05) * 70.0) - (price_risk.clip(0.0, 0.50) * 20.0)


def event_key_frame(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=str)
    event = text_series(frame, 'event')
    start = text_series(frame, 'event_start_utc').str.slice(0, 10)
    sport = text_series(frame, 'sport')
    fallback = text_series(frame, 'home_team') + '|' + text_series(frame, 'away_team')
    key = sport + '|' + event.where(event.ne(''), fallback) + '|' + start
    return key.str.replace(r'\s+', ' ', regex=True).str.strip('|')


def limit_and_resolve_conflicts(frame: pd.DataFrame, *, tier: str, max_rows: int, one_per_event: bool) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    out = frame.copy().drop(columns=['volume_tier', '_tier_quality_score', '_event_key'], errors='ignore')
    out.insert(0, 'volume_tier', tier)
    out['_tier_quality_score'] = quality_score(out)
    out['_event_key'] = event_key_frame(out)
    out = out.sort_values(['_tier_quality_score', 'agent_score', 'model_probability_clean'], ascending=False, na_position='last')
    if one_per_event and '_event_key' in out.columns:
        out = out.drop_duplicates(subset=['_event_key'], keep='first')
    if int(max_rows) > 0:
        out = out.head(int(max_rows))
    return out.drop(columns=['_event_key'], errors='ignore').reset_index(drop=True)


def build_tiers(reviewed: pd.DataFrame, *, max_a: int, max_b: int, max_c: int, one_per_event: bool) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if reviewed.empty:
        empty = pd.DataFrame()
        return empty, empty, empty
    reviewed = add_robust_profit_columns(reviewed)
    strict_base = bool_series(reviewed, 'ultra80_candidate')
    probability = clean_numeric(reviewed, 'model_probability_clean').fillna(clean_numeric(reviewed, 'model_probability'))
    ev = value_series(reviewed).fillna(0.0)
    edge = edge_series(reviewed).fillna(0.0)
    books = clean_numeric(reviewed, 'bookmaker_count').fillna(clean_numeric(reviewed, 'books'))
    agent_score = clean_numeric(reviewed, 'agent_score')
    pattern_signal = clean_numeric(reviewed, 'pattern_ara_memory_signal').fillna(clean_numeric(reviewed, 'ara_memory_signal')).fillna(0.0)
    robust_ev = clean_numeric(reviewed, '_robust_expected_value').fillna(ev)
    robust_profit80 = clean_numeric(reviewed, '_robust_profit_at_80_percent')
    price_risk = clean_numeric(reviewed, '_price_range_risk').fillna(0.0)
    draw = bool_series(reviewed, 'is_draw_prediction')
    safe_timing = non_hard_blocked(reviewed)
    value_ok = ev.ge(0.0).fillna(False) & edge.ge(0.0).fillna(False) & robust_ev.ge(-0.005).fillna(False)

    strict_mask = (
        strict_base
        & probability.ge(0.80).fillna(False)
        & robust_ev.ge(0.015).fillna(False)
        & robust_profit80.gt(0.0).fillna(False)
        & edge.ge(0.0).fillna(False)
        & price_risk.le(0.25).fillna(True)
    )

    lock70_mask = (
        ~strict_mask
        & safe_timing
        & ~draw
        & probability.ge(0.70).fillna(False)
        & value_ok
        & books.ge(1).fillna(False)
        & agent_score.ge(0).fillna(True)
        & pattern_signal.ge(-0.10).fillna(True)
        & price_risk.le(0.90).fillna(True)
    )

    weak_70_watch = probability.ge(0.70).fillna(False) & ~(value_ok)
    value_60_70_watch = probability.ge(0.60).fillna(False) & probability.lt(0.70).fillna(False) & ev.ge(0.0).fillna(False) & edge.ge(0.0).fillna(False)
    reserve_mask = (
        ~strict_mask
        & ~lock70_mask
        & safe_timing
        & ~draw
        & books.ge(1).fillna(False)
        & pattern_signal.ge(-0.10).fillna(True)
        & price_risk.le(1.00).fillna(True)
        & (weak_70_watch | value_60_70_watch | (probability.ge(0.65).fillna(False) & edge.ge(-0.020).fillna(True)))
    )

    strict = limit_and_resolve_conflicts(reviewed[strict_mask], tier='A_strict_80_proof', max_rows=max_a, one_per_event=one_per_event)
    used_keys = set(event_key_frame(strict)) if one_per_event and not strict.empty else set()

    lock70_source = reviewed[lock70_mask].copy()
    if one_per_event and used_keys and not lock70_source.empty:
        lock70_source = lock70_source[~event_key_frame(lock70_source).isin(used_keys)]
    lock70 = limit_and_resolve_conflicts(lock70_source, tier='B_plus_ultra70_positive_value_lock', max_rows=max_b, one_per_event=one_per_event)
    used_keys |= set(event_key_frame(lock70)) if one_per_event and not lock70.empty else set()

    reserve_source = reviewed[reserve_mask].copy()
    if one_per_event and used_keys and not reserve_source.empty:
        reserve_source = reserve_source[~event_key_frame(reserve_source).isin(used_keys)]
    reserve = limit_and_resolve_conflicts(reserve_source, tier='C_value_watch_review', max_rows=max_c, one_per_event=one_per_event)
    return strict, lock70, reserve


def selected_handoff(strict: pd.DataFrame, lock70: pd.DataFrame, reserve: pd.DataFrame, mode: str) -> pd.DataFrame:
    if mode == t('strict_only'):
        return strict.copy()
    if mode == t('max_volume'):
        return pd.concat([strict, lock70], ignore_index=True)
    return pd.concat([strict, lock70, reserve], ignore_index=True)


def display_columns(frame: pd.DataFrame) -> list[str]:
    return [
        col for col in [
            'volume_tier', 'event', 'sport', 'market_type', 'prediction', 'model_probability_clean', 'decimal_price',
            '_robust_decimal_price', 'market_implied_probability', 'model_market_edge', 'expected_value_per_unit',
            '_robust_expected_value', 'ultra80_profit_at_80_percent', '_robust_profit_at_80_percent', '_robust_profit_at_70_percent', '_price_range_risk',
            'bookmaker_count', 'api_coverage_score', 'pattern_ara_memory_signal', 'line_value_signal', 'agent_score',
            '_tier_quality_score', 'recommended_stake_units', 'ultra80_signals', 'ultra80_reasons', 'decision_reasons'
        ] if col in frame.columns
    ]


def show_table(frame: pd.DataFrame, label: str, filename: str) -> None:
    if frame.empty:
        st.info(t('no_pass'))
        return
    cols = display_columns(frame)
    st.dataframe(frame[cols] if cols else frame, use_container_width=True, hide_index=True)
    st.download_button(label, frame.to_csv(index=False), file_name=filename, mime='text/csv')


def blocker_breakdown(reviewed: pd.DataFrame) -> pd.DataFrame:
    if reviewed.empty:
        return pd.DataFrame()
    reviewed = add_robust_profit_columns(reviewed)
    reasons = (text_series(reviewed, 'ultra80_reasons') + ' | ' + text_series(reviewed, 'decision_reasons')).str.split('|')
    counts: dict[str, int] = {}
    for items in reasons:
        for item in items:
            reason = str(item).strip()
            if not reason:
                continue
            counts[reason] = counts.get(reason, 0) + 1
    probability = clean_numeric(reviewed, 'model_probability_clean').fillna(clean_numeric(reviewed, 'model_probability'))
    ev = value_series(reviewed).fillna(0.0)
    edge = edge_series(reviewed).fillna(0.0)
    robust_ev = clean_numeric(reviewed, '_robust_expected_value').fillna(ev)
    robust_profit80 = clean_numeric(reviewed, '_robust_profit_at_80_percent')
    robust_profit70 = clean_numeric(reviewed, '_robust_profit_at_70_percent')
    price_risk = clean_numeric(reviewed, '_price_range_risk')
    counts['prob70_but_ev_below_0'] = int((probability.ge(0.70).fillna(False) & ev.lt(0.0).fillna(False)).sum())
    counts['prob70_but_edge_below_0'] = int((probability.ge(0.70).fillna(False) & edge.lt(0.0).fillna(False)).sum())
    counts['robust_ev_below_0'] = int(robust_ev.lt(0).fillna(False).sum())
    counts['robust_profit80_below_0'] = int(robust_profit80.le(0).fillna(False).sum())
    counts['robust_profit70_below_0'] = int(robust_profit70.le(0).fillna(False).sum())
    counts['price_range_risk_over_0_90'] = int(price_risk.gt(0.90).fillna(False).sum())
    counts = {key: value for key, value in counts.items() if value > 0}
    if not counts:
        return pd.DataFrame()
    return pd.DataFrame([{'reason': key, 'rows': value} for key, value in counts.items()]).sort_values('rows', ascending=False).reset_index(drop=True)


st.title(t('title'))
st.caption(t('caption'))
with st.expander(t('rules'), expanded=True):
    st.write(t('rule_text'))
    st.warning(t('proof'))
    st.caption(t('quality_note'))
    st.caption(t('robust_note'))

frame, source = source_frame()
settings = st.columns(4)
one_per_event = settings[0].checkbox(t('one_per_event'), value=True)
max_a = settings[1].number_input(t('max_a'), min_value=1, max_value=500, value=200, step=25)
max_b = settings[2].number_input(t('max_b'), min_value=1, max_value=1000, value=500, step=50)
max_c = settings[3].number_input(t('max_c'), min_value=1, max_value=2000, value=1000, step=100)
handoff_mode = st.selectbox(t('handoff_mode'), [t('max_volume'), t('strict_only'), t('research_volume')], index=0)

if st.button(t('run'), type='primary', use_container_width=True):
    if frame.empty:
        st.info(t('no_rows'))
        st.stop()

    reviewed = build_agent_decisions(frame)
    strict, lock70, reserve = build_tiers(reviewed, max_a=int(max_a), max_b=int(max_b), max_c=int(max_c), one_per_event=bool(one_per_event))
    handoff = selected_handoff(strict, lock70, reserve, handoff_mode)

    if not handoff.empty:
        st.session_state['ultra80_profit_mode_rows'] = strict.to_dict('records')
        st.session_state['ultra80_max_volume_rows'] = lock70.to_dict('records')
        st.session_state['ultra80_reserve_rows'] = reserve.to_dict('records')
        st.session_state['pro_predictor_latest_rows'] = handoff.to_dict('records')
        st.session_state['ara_latest_predictions'] = handoff.to_dict('records')
        st.session_state['ara_latest_predictions_source'] = f'Ultra 70 Value Lock Mode — {handoff_mode}'
        st.success(t('saved'))
    else:
        st.warning(t('no_pass'))

    metrics = st.columns(8)
    metrics[0].metric(t('reviewed'), len(reviewed))
    metrics[1].metric(t('strict'), len(strict))
    metrics[2].metric(t('max_profit'), len(lock70))
    metrics[3].metric(t('reserve'), len(reserve))
    metrics[4].metric(t('handoff'), len(handoff))
    metrics[5].metric(t('avg_prob'), pct(clean_numeric(handoff, 'model_probability_clean').mean()) if not handoff.empty else 'N/A')
    metrics[6].metric(t('avg_ev'), pct(value_series(handoff).mean()) if not handoff.empty else 'N/A')
    metrics[7].metric(t('avg_profit70'), pct(clean_numeric(handoff, '_robust_profit_at_70_percent').mean()) if not handoff.empty else 'N/A')

    health = page_health(handoff if not handoff.empty else reviewed, page='ultra80_profit_mode')
    st.metric(t('next'), health.get('next_action', 'review'))

    blockers = blocker_breakdown(reviewed)
    if not blockers.empty:
        with st.expander(t('blockers'), expanded=True):
            st.dataframe(blockers.head(25), use_container_width=True, hide_index=True)

    tabs = st.tabs([t('selected_rows'), t('strict_rows'), t('max_rows_tab'), t('reserve_rows'), t('all_rows')])
    with tabs[0]:
        show_table(handoff, t('download'), 'ultra70_selected_handoff.csv')
        if not handoff.empty:
            st.subheader('Handoff health')
            st.dataframe(page_health_frame(handoff, page='ultra80_profit_mode'), use_container_width=True, hide_index=True)
    with tabs[1]:
        show_table(strict, t('download_strict'), 'strict80_proof.csv')
    with tabs[2]:
        show_table(lock70, 'Download Ultra 70 positive-value lock CSV' if LANG == 'en' else 'Descargar CSV Ultra 70 con valor positivo', 'ultra70_positive_value_locks.csv')
    with tabs[3]:
        show_table(reserve, 'Download value-watch CSV' if LANG == 'en' else 'Descargar CSV de vigilancia de valor', 'ultra70_value_watch_review.csv')
    with tabs[4]:
        show_table(add_robust_profit_columns(reviewed), t('download_all'), 'ultra70_reviewed_all_rows.csv')
