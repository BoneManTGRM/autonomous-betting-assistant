from __future__ import annotations

import re
import unicodedata
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Simulation Lab', layout='wide')
LANG = render_app_sidebar('simulation_lab', language_key='simulation_lab_language', selector='radio')

TEXT = {
    'en': {
        'title': 'Simulation Lab',
        'caption': 'Fast Monte Carlo stress test for Ultra 70 / Pro Predictor rows.',
        'source': 'Prediction source', 'session': 'Use latest prediction session', 'survivor_source': 'Use last simulation survivor list', 'upload': 'Upload prediction CSV', 'upload_label': 'Upload CSV',
        'run': 'Run fast simulation', 'no_rows': 'No usable simulation rows found. The simulator needs probability plus odds or market probability.',
        'settings': 'Simulation settings', 'iterations': 'Iterations', 'stake': 'Flat stake units', 'max_rows': 'Max rows to simulate', 'min_prob': 'Minimum probability', 'fast': 'Fast mode',
        'fast_help': 'Recommended. Skips the heavy optimizer grid and only simulates the strongest rows.',
        'risk': 'Risk/stress settings', 'swarm': 'Use Game Scout risk adjustments', 'auto_select': 'Auto-select per-game risk',
        'rain': 'Bad weather fallback', 'injury': 'Bad news fallback', 'opp_injury': 'Good opponent-news boost', 'altitude': 'Altitude fallback', 'travel': 'Travel/fatigue fallback', 'chaos': 'Market/news uncertainty fallback',
        'summary': 'Simulation summary', 'details': 'Selected rows', 'risk_report': 'Risk report', 'scout_report': 'Scout report', 'diagnostics': 'Input diagnostics', 'download': 'Download simulation report',
        'saved': 'Simulation survivor rows saved for Odds Lock Pro handoff.', 'recommendation': 'Recommendation', 'note': 'Best use: run this after Ultra 70, not on the full Pro Predictor board.',
    },
    'es': {
        'title': 'Laboratorio de Simulación',
        'caption': 'Simulación Monte Carlo rápida para filas Ultra 70 / Pro Predictor.',
        'source': 'Fuente de predicciones', 'session': 'Usar última sesión de predicciones', 'survivor_source': 'Usar última lista sobreviviente', 'upload': 'Subir CSV de predicciones', 'upload_label': 'Subir CSV',
        'run': 'Ejecutar simulación rápida', 'no_rows': 'No se encontraron filas útiles. El simulador necesita probabilidad y cuota o probabilidad de mercado.',
        'settings': 'Configuración de simulación', 'iterations': 'Iteraciones', 'stake': 'Unidades fijas por pick', 'max_rows': 'Máx filas para simular', 'min_prob': 'Probabilidad mínima', 'fast': 'Modo rápido',
        'fast_help': 'Recomendado. Salta el optimizador pesado y solo simula las filas más fuertes.',
        'risk': 'Configuración de riesgo/estrés', 'swarm': 'Usar ajustes de riesgo Scout', 'auto_select': 'Auto-seleccionar riesgo por juego',
        'rain': 'Respaldo mal clima', 'injury': 'Respaldo mala noticia', 'opp_injury': 'Impulso por buena noticia rival', 'altitude': 'Respaldo altitud', 'travel': 'Respaldo viaje/fatiga', 'chaos': 'Respaldo incertidumbre mercado/noticias',
        'summary': 'Resumen de simulación', 'details': 'Filas seleccionadas', 'risk_report': 'Reporte de riesgo', 'scout_report': 'Reporte scout', 'diagnostics': 'Diagnóstico de entrada', 'download': 'Descargar reporte',
        'saved': 'Filas sobrevivientes guardadas para Odds Lock Pro.', 'recommendation': 'Recomendación', 'note': 'Uso ideal: ejecútalo después de Ultra 70, no sobre todo el tablero de Pro Predictor.',
    },
}

SCENARIOS = [
    'model', 'market_blend', 'conservative_blend', 'overconfident_5pct',
    'weather_news_travel_stress', 'market_chaos_stress', 'combined_stress',
]
UPSTREAM_SESSION_KEYS = ('ultra80_max_volume_rows', 'ultra80_profit_mode_rows', 'ara_latest_predictions', 'pro_predictor_latest_rows', 'pro_predictor_all_rows')

EVENT_ALIASES = ['event', 'game', 'match', 'partido', 'fixture', 'fixture_name', 'game_name', 'event_name', 'evento']
PICK_ALIASES = ['prediction', 'pick', 'selection', 'prediccion', 'predicción', 'pronostico', 'pronóstico', 'predicted_winner', 'team_pick', 'side', 'seleccion']
PROB_ALIASES = ['model_probability_clean', 'model_probability', 'final_probability_value', 'final_probability', 'probability', 'probabilidad', 'prob_final', 'confidence_probability', 'predicted_probability', 'win_probability', 'win_prob', 'projected_probability', 'prob_modelo', 'confianza']
MARKET_PROB_ALIASES = ['market_probability', 'market_implied_probability', 'implied_probability', 'no_vig_probability', 'prob_mercado']
DECIMAL_ALIASES = ['decimal_price', 'decimal_odds', 'best_price', 'average_price', 'best_odds', 'market_odds', 'book_odds', 'odds', 'price', 'cuota', 'mejor_cuota', 'cuota_decimal']
AMERICAN_ALIASES = ['american_odds', 'american_price', 'moneyline', 'ml', 'american']
EDGE_ALIASES = ['model_market_edge', 'model_edge', 'edge_probability', 'edge', 'edge_percent', 'model_minus_no_vig', 'ventaja']
EV_ALIASES = ['expected_value_per_unit', 'estimated_ev_decimal', 'computed_ev_decimal', 'estimated_ev', 'ev', 'expected_value', 'valor_esperado']
BOOK_ALIASES = ['bookmaker_count', 'books', 'source_count', 'bookmakers', 'casas', 'num_books', 'sportsbooks_count']
API_ALIASES = ['api_coverage_score', 'api_coverage', 'cobertura_api']


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def column_key(value: Any) -> str:
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode('ascii').lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')


def first_col(frame: pd.DataFrame, aliases: list[str]) -> str | None:
    lookup = {column_key(col): col for col in frame.columns}
    for alias in aliases:
        key = column_key(alias)
        if key in lookup:
            return lookup[key]
    return None


def text_series(frame: pd.DataFrame, aliases: list[str], default: str = '') -> pd.Series:
    col = first_col(frame, aliases)
    if col is None:
        return pd.Series(default, index=frame.index, dtype=str)
    return frame[col].fillna(default).astype(str).str.strip()


def num_series(frame: pd.DataFrame, aliases: list[str], *, probability: bool = False, percent_like: bool = False) -> pd.Series:
    col = first_col(frame, aliases)
    if col is None:
        return pd.Series(float('nan'), index=frame.index, dtype=float)
    raw = frame[col].astype(str).str.strip()
    cleaned = raw.str.replace('%', '', regex=False).str.replace(',', '', regex=False).str.replace('−', '-', regex=False)
    values = pd.to_numeric(cleaned, errors='coerce')
    missing = values.isna()
    if missing.any():
        extracted = raw[missing].str.extract(r'([+-]?\d+(?:\.\d+)?)')[0]
        values.loc[missing] = pd.to_numeric(extracted, errors='coerce')
    percent_mask = raw.str.contains('%', regex=False, na=False)
    values.loc[percent_mask] = values.loc[percent_mask] / 100.0
    if probability:
        values = values.where(values <= 1.0, values / 100.0)
    elif percent_like and (percent_mask.any() or any(token in column_key(col) for token in ['percent', 'pct'])):
        values = values.where(values.abs() <= 1.0, values / 100.0)
    return values


def american_to_decimal(values: pd.Series) -> pd.Series:
    out = pd.Series(float('nan'), index=values.index, dtype=float)
    out.loc[values > 0] = 1.0 + values.loc[values > 0] / 100.0
    out.loc[values < 0] = 1.0 + 100.0 / values.loc[values < 0].abs()
    return out


def session_frame() -> pd.DataFrame:
    for key in UPSTREAM_SESSION_KEYS:
        rows = st.session_state.get(key)
        if isinstance(rows, list) and rows:
            return pd.DataFrame(rows)
    return pd.DataFrame()


def survivor_frame() -> pd.DataFrame:
    rows = st.session_state.get('simulation_survivor_rows')
    if isinstance(rows, list) and rows:
        return pd.DataFrame(rows)
    return pd.DataFrame()


def load_input() -> pd.DataFrame:
    choice = st.radio(t('source'), [t('session'), t('survivor_source'), t('upload')], horizontal=True)
    if choice == t('upload'):
        upload = st.file_uploader(t('upload_label'), type=['csv'])
        if upload is None:
            return pd.DataFrame()
        try:
            return pd.read_csv(upload)
        except Exception as exc:
            st.error(str(exc))
            return pd.DataFrame()
    if choice == t('survivor_source'):
        return survivor_frame()
    return session_frame()


def normalize(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    out['event'] = text_series(frame, EVENT_ALIASES)
    out['sport'] = text_series(frame, ['sport', 'sport_key', 'league', 'competition', 'deporte'])
    out['market_type'] = text_series(frame, ['market_type', 'market', 'bet_type', 'prop_type', 'tipo_mercado', 'mercado']).str.lower()
    out['prediction'] = text_series(frame, PICK_ALIASES)
    out['volume_tier'] = text_series(frame, ['volume_tier', 'tier', 'ultra80_tier'], 'unknown')
    out['model_probability'] = num_series(frame, PROB_ALIASES, probability=True)
    out['market_probability'] = num_series(frame, MARKET_PROB_ALIASES, probability=True)
    decimal = num_series(frame, DECIMAL_ALIASES)
    american = num_series(frame, AMERICAN_ALIASES)
    implied_decimal = (1.0 / out['market_probability']).replace([np.inf, -np.inf], np.nan)
    out['decimal_price'] = decimal.fillna(american_to_decimal(american)).fillna(implied_decimal)
    implied = 1.0 / out['decimal_price']
    out['edge'] = num_series(frame, EDGE_ALIASES, percent_like=True).fillna(out['model_probability'] - implied)
    out['ev'] = num_series(frame, EV_ALIASES, percent_like=True).fillna(out['model_probability'] * out['decimal_price'] - 1.0)
    out['books'] = num_series(frame, BOOK_ALIASES).fillna(0.0)
    out['api_coverage'] = num_series(frame, API_ALIASES, probability=True).fillna(0.0)
    out['agent_score'] = num_series(frame, ['agent_score', 'scanner_strength_score', 'target_70_quality_score', 'score']).fillna(0.0)
    out['memory_signal'] = num_series(frame, ['pattern_ara_memory_signal', 'ara_memory_signal', 'memory_signal'], percent_like=True).fillna(0.0)
    out['robust_ev'] = num_series(frame, ['_robust_expected_value', 'robust_expected_value'], percent_like=True).fillna(out['ev'])
    out['price_risk'] = num_series(frame, ['_price_range_risk', 'price_range_risk', 'price_range']).fillna(0.0).clip(0.0, 1.0)
    out['line_movement_risk'] = num_series(frame, ['line_movement_risk', 'closing_line_risk']).fillna(0.0).clip(0.0, 1.0)
    out['news_risk'] = num_series(frame, ['news_risk', 'injury_risk', 'weather_risk']).fillna(0.0).clip(0.0, 1.0)
    return out.dropna(subset=['model_probability', 'decimal_price'])


def input_diagnostics(raw: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    def matched(aliases: list[str]) -> str:
        return first_col(raw, aliases) or ''
    return pd.DataFrame([
        {'check': 'raw rows loaded', 'value': int(len(raw)), 'matched_column': ''},
        {'check': 'raw columns loaded', 'value': int(len(raw.columns)), 'matched_column': ', '.join(map(str, raw.columns[:20]))},
        {'check': 'event column', 'value': 'found' if matched(EVENT_ALIASES) else 'missing', 'matched_column': matched(EVENT_ALIASES)},
        {'check': 'pick/prediction column', 'value': 'found' if matched(PICK_ALIASES) else 'missing', 'matched_column': matched(PICK_ALIASES)},
        {'check': 'model probability column', 'value': 'found' if matched(PROB_ALIASES) else 'missing', 'matched_column': matched(PROB_ALIASES)},
        {'check': 'decimal odds column', 'value': 'found' if matched(DECIMAL_ALIASES) else 'missing', 'matched_column': matched(DECIMAL_ALIASES)},
        {'check': 'american odds column', 'value': 'found' if matched(AMERICAN_ALIASES) else 'missing', 'matched_column': matched(AMERICAN_ALIASES)},
        {'check': 'usable simulation rows', 'value': int(len(frame)), 'matched_column': 'needs model probability + decimal/american odds or market probability'},
    ])


def apply_risk_profile(frame: pd.DataFrame, fallback: dict[str, float], *, auto_select: bool = True, use_swarm: bool = True) -> pd.DataFrame:
    out = frame.copy()
    if not use_swarm:
        out['auto_total_stress'] = 0.0
        out['auto_mode'] = 'risk_disabled'
        return out
    fallback_stress = max(float(fallback['rain']), float(fallback['injury']), float(fallback['altitude']), float(fallback['travel']), float(fallback['chaos']))
    if auto_select:
        detected = np.maximum.reduce([
            out['price_risk'].to_numpy(float), out['line_movement_risk'].to_numpy(float), out['news_risk'].to_numpy(float),
            (-out['memory_signal']).clip(lower=0.0, upper=0.08).to_numpy(float) / 0.08,
        ])
        out['auto_total_stress'] = np.maximum(detected, fallback_stress * 0.25).clip(0.0, 1.0)
        out['auto_mode'] = 'fast_auto_per_game'
    else:
        out['auto_total_stress'] = fallback_stress
        out['auto_mode'] = 'manual_fallback'
    return out


def scenario_probabilities(data: pd.DataFrame, scenario: str) -> np.ndarray:
    p = data['model_probability'].to_numpy(float)
    market = np.clip(1.0 / data['decimal_price'].to_numpy(float), 0.01, 0.99)
    memory = data['memory_signal'].fillna(0.0).to_numpy(float)
    stress = data['auto_total_stress'].fillna(0.0).to_numpy(float)
    if scenario == 'model':
        true = p
    elif scenario == 'market_blend':
        true = 0.65 * p + 0.35 * market
    elif scenario == 'conservative_blend':
        true = 0.50 * p + 0.50 * market + np.minimum(memory, 0.0) - 0.02
    elif scenario == 'overconfident_5pct':
        true = p - 0.05
    elif scenario == 'weather_news_travel_stress':
        true = p - stress * 0.08
    elif scenario == 'market_chaos_stress':
        true = (p - stress * 0.05) * 0.75 + market * 0.25
    elif scenario == 'combined_stress':
        true = (p - stress * 0.12 + np.minimum(memory, 0.0)) * 0.70 + market * 0.30
    else:
        true = p
    return np.clip(true, 0.01, 0.99)


def max_drawdown(profit_paths: np.ndarray) -> np.ndarray:
    cumulative = profit_paths.cumsum(axis=1)
    peaks = np.maximum.accumulate(np.maximum(cumulative, 0.0), axis=1)
    return (peaks - cumulative).max(axis=1)


def simulate(data: pd.DataFrame, scenario: str, iterations: int, stake: float, seed: int) -> dict[str, Any]:
    if data.empty:
        return {'rows': 0}
    iterations = int(min(max(iterations, 100), 5000))
    probs = scenario_probabilities(data, scenario)
    odds = data['decimal_price'].to_numpy(float)
    rng = np.random.default_rng(seed)
    wins = rng.random((iterations, len(data))) < probs
    profit_paths = np.where(wins, (odds - 1.0) * stake, -stake)
    profits = profit_paths.sum(axis=1)
    hit_rates = wins.mean(axis=1)
    drawdowns = max_drawdown(profit_paths)
    staked = len(data) * stake
    return {
        'rows': int(len(data)), 'scenario': scenario,
        'avg_model_prob': round(float(data['model_probability'].mean()), 6),
        'avg_odds': round(float(data['decimal_price'].mean()), 4),
        'avg_auto_stress': round(float(data['auto_total_stress'].mean()), 6),
        'scenario_avg_prob': round(float(probs.mean()), 6),
        'mean_units': round(float(profits.mean()), 4),
        'mean_roi': round(float(profits.mean() / staked), 6) if staked else None,
        'profit_probability': round(float((profits > 0).mean()), 6),
        'loss_probability': round(float((profits < 0).mean()), 6),
        'p05_units': round(float(np.quantile(profits, 0.05)), 4),
        'p95_units': round(float(np.quantile(profits, 0.95)), 4),
        'mean_hit_rate': round(float(hit_rates.mean()), 6),
        'prob_hit_70_plus': round(float((hit_rates >= 0.70).mean()), 6),
        'prob_hit_80_plus': round(float((hit_rates >= 0.80).mean()), 6),
        'avg_max_drawdown_units': round(float(drawdowns.mean()), 4),
        'p95_max_drawdown_units': round(float(np.quantile(drawdowns, 0.95)), 4),
    }


def select_rows(frame: pd.DataFrame, max_rows: int, min_prob: float) -> pd.DataFrame:
    selected = frame[frame['model_probability'].ge(float(min_prob)).fillna(False)].copy()
    if selected.empty:
        selected = frame.copy()
    selected['_sim_quality'] = (
        selected['model_probability'].fillna(0.0) * 100
        + selected['robust_ev'].fillna(selected['ev']).clip(-0.10, 0.25) * 50
        + selected['edge'].fillna(0.0).clip(-0.10, 0.25) * 40
        - selected['auto_total_stress'].fillna(0.0) * 20
        + selected['agent_score'].fillna(0.0) / 10
    )
    return selected.sort_values('_sim_quality', ascending=False).head(int(max_rows)).reset_index(drop=True)


def recommendation_table(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    real = summary[~summary['scenario'].eq('model')].copy()
    if real.empty:
        real = summary.copy()
    worst_roi = float(pd.to_numeric(real['mean_roi'], errors='coerce').min())
    avg_roi = float(pd.to_numeric(real['mean_roi'], errors='coerce').mean())
    worst_profit_probability = float(pd.to_numeric(real['profit_probability'], errors='coerce').min())
    if worst_roi >= 0.0 and worst_profit_probability >= 0.52:
        recommendation = 'lock_candidate_after_human_review'
    elif avg_roi >= 0.0:
        recommendation = 'watch_or_reduce_stake'
    else:
        recommendation = 'do_not_lock'
    return pd.DataFrame([{
        'strategy': 'Fast simulation shortlist',
        'rows': int(pd.to_numeric(summary['rows'], errors='coerce').max() or 0),
        'worst_mean_roi': round(worst_roi, 6),
        'avg_mean_roi': round(avg_roi, 6),
        'worst_profit_probability': round(worst_profit_probability, 6),
        'recommendation': recommendation,
    }])


def risk_report(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    rows = []
    for col in ['auto_total_stress', 'price_risk', 'line_movement_risk', 'news_risk']:
        if col not in frame.columns:
            continue
        values = pd.to_numeric(frame[col], errors='coerce').fillna(0.0)
        rows.append({'risk_type': col, 'avg_risk': round(float(values.mean()), 6), 'max_risk': round(float(values.max()), 6), 'rows_over_0_50': int(values.gt(0.50).sum())})
    return pd.DataFrame(rows).sort_values(['avg_risk', 'max_risk'], ascending=False).reset_index(drop=True)


def scout_report(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    rows = []
    for _, row in frame.iterrows():
        stress = float(row.get('auto_total_stress') or 0.0)
        ev = float(row.get('robust_ev') if pd.notna(row.get('robust_ev')) else row.get('ev') or 0.0)
        p = float(row.get('model_probability') or 0.0)
        if stress <= 0.35 and ev >= 0 and p >= 0.70:
            action = 'lock_candidate_after_price_check'
        elif stress <= 0.65 and p >= 0.65:
            action = 'watch_or_reduce_stake'
        else:
            action = 'do_not_lock_until_rescanned'
        rows.append({'event': row.get('event', ''), 'sport': row.get('sport', ''), 'prediction': row.get('prediction', ''), 'model_probability': round(p, 6), 'decimal_price': row.get('decimal_price', ''), 'robust_ev': round(ev, 6), 'auto_stress_score': round(stress, 6), 'scout_action': action})
    return pd.DataFrame(rows).sort_values(['scout_action', 'auto_stress_score', 'robust_ev'], ascending=[True, True, False]).reset_index(drop=True)


st.title(t('title'))
st.caption(t('caption'))
st.info(t('note'))
raw = load_input()
with st.expander(t('settings'), expanded=True):
    c1, c2, c3, c4, c5 = st.columns(5)
    iterations = c1.number_input(t('iterations'), min_value=100, max_value=5000, value=1000, step=500)
    stake = c2.number_input(t('stake'), min_value=0.05, max_value=5.0, value=1.0, step=0.05)
    max_rows = c3.number_input(t('max_rows'), min_value=1, max_value=250, value=50, step=25)
    min_prob = c4.number_input(t('min_prob'), min_value=0.0, max_value=1.0, value=0.65, step=0.01)
    fast_mode = c5.checkbox(t('fast'), value=True, help=t('fast_help'))
with st.expander(t('risk'), expanded=False):
    use_swarm = st.checkbox(t('swarm'), value=True)
    auto_select = st.checkbox(t('auto_select'), value=True)
    s1, s2, s3 = st.columns(3)
    rain = s1.slider(t('rain'), min_value=0.0, max_value=1.0, value=0.15 if fast_mode else 0.25, step=0.05)
    injury = s2.slider(t('injury'), min_value=0.0, max_value=1.0, value=0.05 if fast_mode else 0.10, step=0.05)
    opponent_injury = s3.slider(t('opp_injury'), min_value=0.0, max_value=1.0, value=0.0, step=0.05)
    s4, s5, s6 = st.columns(3)
    altitude = s4.slider(t('altitude'), min_value=0.0, max_value=1.0, value=0.10 if fast_mode else 0.20, step=0.05)
    travel = s5.slider(t('travel'), min_value=0.0, max_value=1.0, value=0.10 if fast_mode else 0.15, step=0.05)
    chaos = s6.slider(t('chaos'), min_value=0.0, max_value=0.75, value=0.05 if fast_mode else 0.10, step=0.05)
stress_profile = {'rain': float(rain), 'injury': float(injury), 'opponent_injury': float(opponent_injury), 'altitude': float(altitude), 'travel': float(travel), 'chaos': float(chaos)}

if st.button(t('run'), type='primary', use_container_width=True):
    if raw.empty:
        st.warning(t('no_rows'))
        st.stop()
    frame = normalize(raw)
    if frame.empty:
        st.warning(t('no_rows'))
        st.subheader(t('diagnostics'))
        st.dataframe(input_diagnostics(raw, frame), use_container_width=True, hide_index=True)
        st.stop()
    frame = apply_risk_profile(frame, stress_profile, auto_select=bool(auto_select), use_swarm=bool(use_swarm))
    selected = select_rows(frame, int(max_rows), float(min_prob))
    st.session_state['simulation_survivor_rows'] = selected.drop(columns=['_sim_quality'], errors='ignore').to_dict('records')
    st.session_state['ara_latest_predictions'] = selected.drop(columns=['_sim_quality'], errors='ignore').to_dict('records')
    st.session_state['ara_latest_predictions_source'] = 'Simulation Lab fast survivor'
    st.success(t('saved'))

    rows = []
    with st.spinner('Running fast simulations...' if LANG == 'en' else 'Ejecutando simulaciones rápidas...'):
        for index, scenario in enumerate(SCENARIOS):
            rows.append({'strategy': 'Fast simulation shortlist', **simulate(selected, scenario, int(iterations), float(stake), seed=20260616 + index)})
    summary = pd.DataFrame(rows)
    recommendations = recommendation_table(summary)
    risks = risk_report(selected)
    scouts = scout_report(selected)

    st.subheader(t('recommendation'))
    st.dataframe(recommendations, use_container_width=True, hide_index=True)
    st.subheader(t('scout_report'))
    st.dataframe(scouts, use_container_width=True, hide_index=True)
    st.subheader(t('summary'))
    st.dataframe(summary, use_container_width=True, hide_index=True)
    st.subheader(t('risk_report'))
    st.dataframe(risks, use_container_width=True, hide_index=True)
    st.subheader(t('diagnostics'))
    st.dataframe(input_diagnostics(raw, frame), use_container_width=True, hide_index=True)
    st.subheader(t('details'))
    cols = [col for col in ['event', 'sport', 'market_type', 'prediction', 'volume_tier', 'model_probability', 'market_probability', 'decimal_price', 'edge', 'ev', 'robust_ev', 'auto_total_stress', 'price_risk', 'line_movement_risk', 'news_risk', 'books', 'api_coverage', 'memory_signal', '_sim_quality'] if col in selected.columns]
    st.dataframe(selected[cols], use_container_width=True, hide_index=True)

    report_parts = [summary]
    if not recommendations.empty:
        rec = recommendations.copy(); rec.insert(0, 'report_section', 'recommendations'); report_parts.append(rec)
    if not scouts.empty:
        scout_export = scouts.copy(); scout_export.insert(0, 'report_section', 'scout_report'); report_parts.append(scout_export)
    if not risks.empty:
        risk_export = risks.copy(); risk_export.insert(0, 'report_section', 'risk_report'); report_parts.append(risk_export)
    details = selected.copy(); details.insert(0, 'report_section', 'selected_rows'); report_parts.append(details)
    diagnostics = input_diagnostics(raw, frame)
    if not diagnostics.empty:
        diag = diagnostics.copy(); diag.insert(0, 'report_section', 'input_diagnostics'); report_parts.append(diag)
    report = pd.concat(report_parts, ignore_index=True, sort=False)
    st.download_button(t('download'), report.to_csv(index=False), file_name='simulation_lab_report.csv', mime='text/csv')
