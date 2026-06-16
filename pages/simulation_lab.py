from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title='Simulation Lab', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='simulation_lab_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'Simulation Lab',
        'caption': 'Monte Carlo stress test for hit rate, ROI, drawdown, and profit risk. This does not prove the model; it tests whether a strategy survives reasonable probability error.',
        'source': 'Prediction source', 'session': 'Use latest session rows', 'upload': 'Upload prediction CSV', 'upload_label': 'Upload CSV',
        'run': 'Run simulations + optimizer', 'no_rows': 'No rows available. Run Pro Predictor/Ultra 80 first or upload a CSV.',
        'settings': 'Simulation settings', 'iterations': 'Iterations', 'stake': 'Flat stake units', 'max_rows': 'Max rows per strategy',
        'summary': 'Simulation summary', 'details': 'Selected rows', 'optimizer': 'Simulation optimizer', 'survivor': 'Simulation survivor handoff', 'download': 'Download simulation report',
        'note': 'Best use: compare strategies under model, blended-market, memory-penalty, and overconfidence scenarios. A strategy that only works when the model is perfectly calibrated is not robust enough.',
        'saved': 'Simulation survivor rows saved for Odds Lock Pro handoff.',
    },
    'es': {
        'title': 'Laboratorio de Simulación',
        'caption': 'Prueba Monte Carlo para acierto, ROI, drawdown y riesgo de pérdida. No prueba el modelo; prueba si la estrategia sobrevive errores razonables de probabilidad.',
        'source': 'Fuente de predicciones', 'session': 'Usar últimas filas de la sesión', 'upload': 'Subir CSV de predicciones', 'upload_label': 'Subir CSV',
        'run': 'Ejecutar simulaciones + optimizador', 'no_rows': 'No hay filas. Ejecuta Predictor Pro/Ultra 80 primero o sube un CSV.',
        'settings': 'Configuración de simulación', 'iterations': 'Iteraciones', 'stake': 'Unidades fijas por pick', 'max_rows': 'Máx filas por estrategia',
        'summary': 'Resumen de simulación', 'details': 'Filas seleccionadas', 'optimizer': 'Optimizador de simulación', 'survivor': 'Traspaso sobreviviente de simulación', 'download': 'Descargar reporte de simulación',
        'note': 'Uso ideal: comparar estrategias con escenarios de modelo, mezcla de mercado, penalización de memoria y sobreconfianza. Una estrategia que solo funciona cuando el modelo está perfectamente calibrado no es suficientemente robusta.',
        'saved': 'Filas sobrevivientes de simulación guardadas para traspaso a Odds Lock Pro.',
    },
}

SCENARIOS = ['model', 'market_blend', 'memory_penalty', 'overconfident_5pct', 'overconfident_10pct', 'conservative_blend']


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def session_frame() -> pd.DataFrame:
    for key in ('simulation_survivor_rows', 'ultra80_profit_mode_rows', 'ultra80_max_volume_rows', 'pro_predictor_latest_rows', 'ara_latest_predictions', 'pro_predictor_all_rows'):
        rows = st.session_state.get(key)
        if isinstance(rows, list) and rows:
            return pd.DataFrame(rows)
    return pd.DataFrame()


def first_col(frame: pd.DataFrame, aliases: list[str]) -> str | None:
    lookup = {str(col).strip().lower().replace(' ', '_').replace('-', '_'): col for col in frame.columns}
    for alias in aliases:
        key = alias.strip().lower().replace(' ', '_').replace('-', '_')
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
    values = pd.to_numeric(raw.str.replace('%', '', regex=False).str.replace(',', '', regex=False), errors='coerce')
    percent_mask = raw.str.contains('%', regex=False, na=False)
    values.loc[percent_mask] = values.loc[percent_mask] / 100.0
    if probability:
        values = values.where(values <= 1.0, values / 100.0)
    elif percent_like and any(token in str(col).lower() for token in ['percent', 'pct']):
        values = values.where(values.abs() <= 1.0, values / 100.0)
    return values


def american_to_decimal(values: pd.Series) -> pd.Series:
    out = pd.Series(float('nan'), index=values.index, dtype=float)
    positive = values > 0
    negative = values < 0
    out.loc[positive] = 1.0 + values.loc[positive] / 100.0
    out.loc[negative] = 1.0 + 100.0 / values.loc[negative].abs()
    return out


def normalize(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    out['event'] = text_series(frame, ['event', 'game', 'match', 'partido'])
    out['sport'] = text_series(frame, ['sport', 'sport_key', 'league', 'competition', 'deporte'])
    out['market_type'] = text_series(frame, ['market_type', 'market', 'bet_type', 'prop_type', 'tipo_mercado']).str.lower()
    out['prediction'] = text_series(frame, ['prediction', 'pick', 'selection', 'prediccion', 'pronostico'])
    out['volume_tier'] = text_series(frame, ['volume_tier', 'tier', 'ultra80_tier'], 'unknown')
    out['model_probability'] = num_series(frame, ['model_probability_clean', 'model_probability', 'final_probability_value', 'final_probability', 'probability', 'probabilidad', 'prob_final'], probability=True)
    decimal = num_series(frame, ['decimal_price', 'best_price', 'average_price', 'odds', 'price', 'cuota', 'mejor_cuota'])
    american = num_series(frame, ['american_odds', 'american_price', 'moneyline'])
    out['decimal_price'] = decimal.fillna(american_to_decimal(american))
    out['edge'] = num_series(frame, ['model_market_edge', 'model_edge', 'edge_probability', 'edge', 'model_minus_no_vig'], percent_like=True)
    implied = 1.0 / out['decimal_price']
    out['edge'] = out['edge'].fillna(out['model_probability'] - implied)
    out['ev'] = num_series(frame, ['expected_value_per_unit', 'estimated_ev_decimal', 'computed_ev_decimal', 'estimated_ev', 'ev'], percent_like=True)
    out['ev'] = out['ev'].fillna(out['model_probability'] * out['decimal_price'] - 1.0)
    out['books'] = num_series(frame, ['bookmaker_count', 'books', 'source_count', 'bookmakers']).fillna(0.0)
    out['api_coverage'] = num_series(frame, ['api_coverage_score', 'api_coverage'], probability=True).fillna(0.0)
    out['agent_score'] = num_series(frame, ['agent_score', 'scanner_strength_score', 'target_70_quality_score']).fillna(0.0)
    out['memory_signal'] = num_series(frame, ['pattern_ara_memory_signal', 'ara_memory_signal', 'memory_signal'], percent_like=True).fillna(0.0)
    out['robust_ev'] = num_series(frame, ['_robust_expected_value', 'robust_expected_value'], percent_like=True).fillna(out['ev'])
    out['robust_profit80'] = num_series(frame, ['_robust_profit_at_80_percent', 'robust_profit_at_80_percent'], percent_like=True).fillna(0.80 * out['decimal_price'] - 1.0)
    out['price_risk'] = num_series(frame, ['_price_range_risk', 'price_range_risk', 'price_range']).fillna(0.0)
    return out.dropna(subset=['model_probability', 'decimal_price'])


def strategy_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    p = frame['model_probability']
    price = frame['decimal_price']
    return {
        'All valid rows': pd.Series(True, index=frame.index),
        'A strict proof': (p >= 0.80) & frame['ev'].ge(0.025) & frame['robust_ev'].ge(0.015) & frame['edge'].ge(0.075) & frame['books'].ge(6) & frame['api_coverage'].ge(0.66) & price.between(1.27, 1.75) & frame['memory_signal'].ge(-0.005) & frame['robust_profit80'].gt(0) & frame['price_risk'].le(0.25),
        'B max profitable': (p >= 0.76) & frame['ev'].ge(0.005) & frame['robust_ev'].ge(0.0) & frame['edge'].ge(0.04) & frame['books'].ge(4) & frame['api_coverage'].ge(0.50) & price.between(1.27, 1.75) & frame['memory_signal'].ge(-0.02) & frame['robust_profit80'].gt(0) & frame['price_risk'].le(0.35),
        'C reserve watch': (p >= 0.72) & frame['edge'].ge(0.02) & frame['books'].ge(3) & price.between(1.25, 2.20) & frame['memory_signal'].ge(-0.035) & frame['robust_profit80'].gt(0) & frame['price_risk'].le(0.50),
        'Profit focus': (p >= 0.65) & frame['ev'].ge(0.02) & frame['robust_ev'].ge(0.0) & frame['books'].ge(4) & frame['api_coverage'].ge(0.50) & price.between(1.27, 2.20),
        '70 target EV+': (p >= 0.69) & (p <= 0.82) & frame['ev'].gt(0) & frame['books'].ge(4) & frame['api_coverage'].ge(0.50),
    }


def scenario_probabilities(data: pd.DataFrame, scenario: str) -> np.ndarray:
    p = data['model_probability'].to_numpy(float)
    market = np.clip(1.0 / data['decimal_price'].to_numpy(float), 0.01, 0.99)
    memory = data['memory_signal'].fillna(0.0).to_numpy(float)
    if scenario == 'model':
        true = p
    elif scenario == 'market_blend':
        true = 0.5 * p + 0.5 * market
    elif scenario == 'memory_penalty':
        true = p + np.minimum(memory, 0.0)
    elif scenario == 'overconfident_5pct':
        true = p - 0.05
    elif scenario == 'overconfident_10pct':
        true = p - 0.10
    elif scenario == 'conservative_blend':
        true = 0.5 * p + 0.5 * market + np.minimum(memory, 0.0) - 0.02
    else:
        true = p
    return np.clip(true, 0.01, 0.99)


def expected_roi(data: pd.DataFrame, scenario: str) -> float | None:
    if data.empty:
        return None
    probs = scenario_probabilities(data, scenario)
    odds = data['decimal_price'].to_numpy(float)
    return float(np.mean(probs * odds - 1.0))


def max_drawdown(profit_paths: np.ndarray) -> np.ndarray:
    cumulative = profit_paths.cumsum(axis=1)
    peaks = np.maximum.accumulate(np.maximum(cumulative, 0.0), axis=1)
    drawdowns = peaks - cumulative
    return drawdowns.max(axis=1)


def simulate(data: pd.DataFrame, scenario: str, iterations: int, stake: float, seed: int) -> dict[str, Any]:
    if data.empty:
        return {'rows': 0}
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
        'rows': int(len(data)),
        'scenario': scenario,
        'avg_model_prob': round(float(data['model_probability'].mean()), 6),
        'avg_odds': round(float(data['decimal_price'].mean()), 4),
        'mean_units': round(float(profits.mean()), 4),
        'mean_roi': round(float(profits.mean() / staked), 6) if staked else None,
        'profit_probability': round(float((profits > 0).mean()), 6),
        'loss_probability': round(float((profits < 0).mean()), 6),
        'p05_units': round(float(np.quantile(profits, 0.05)), 4),
        'p95_units': round(float(np.quantile(profits, 0.95)), 4),
        'mean_hit_rate': round(float(hit_rates.mean()), 6),
        'prob_hit_80_plus': round(float((hit_rates >= 0.80).mean()), 6),
        'avg_max_drawdown_units': round(float(drawdowns.mean()), 4),
        'p95_max_drawdown_units': round(float(np.quantile(drawdowns, 0.95)), 4),
    }


def optimizer_mask(frame: pd.DataFrame, params: dict[str, Any]) -> pd.Series:
    return (
        frame['model_probability'].between(params['min_probability'], params['max_probability'], inclusive='both')
        & frame['ev'].ge(params['min_ev']).fillna(False)
        & frame['robust_ev'].ge(params['min_robust_ev']).fillna(False)
        & frame['edge'].ge(params['min_edge']).fillna(False)
        & frame['books'].ge(params['min_books']).fillna(False)
        & frame['api_coverage'].ge(params['min_api_coverage']).fillna(False)
        & frame['decimal_price'].between(params['min_odds'], params['max_odds'], inclusive='both')
        & frame['memory_signal'].ge(params['min_memory_signal']).fillna(False)
        & frame['robust_profit80'].gt(0).fillna(False)
        & frame['price_risk'].le(params['max_price_risk']).fillna(True)
    )


def simulation_optimizer(frame: pd.DataFrame, *, min_rows: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    p_grid = [0.62, 0.65, 0.67, 0.69, 0.70, 0.72, 0.74, 0.76, 0.78, 0.80]
    ev_grid = [0.0, 0.005, 0.01, 0.02, 0.03, 0.04, 0.05]
    edge_grid = [-0.005, 0.0, 0.01, 0.02, 0.03, 0.04]
    books_grid = [0, 4, 10, 20, 50, 60]
    odds_grid = [(1.20, 2.20), (1.25, 2.20), (1.27, 1.75), (1.30, 2.00), (1.35, 2.20), (1.40, 2.50)]
    for pmin in p_grid:
        for pmax in [1.00, 0.82, 0.78]:
            if pmin > pmax:
                continue
            for evmin in ev_grid:
                for edgemin in edge_grid:
                    for booksmin in books_grid:
                        for oddsmin, oddsmax in odds_grid:
                            params = {
                                'min_probability': pmin, 'max_probability': pmax, 'min_ev': evmin,
                                'min_robust_ev': max(-0.005, evmin - 0.015), 'min_edge': edgemin,
                                'min_books': booksmin, 'min_api_coverage': 0.50, 'min_odds': oddsmin,
                                'max_odds': oddsmax, 'min_memory_signal': -0.02, 'max_price_risk': 0.35,
                            }
                            selected = frame[optimizer_mask(frame, params)]
                            if len(selected) < int(min_rows):
                                continue
                            rois = {scenario: expected_roi(selected, scenario) for scenario in SCENARIOS}
                            worst_roi = min(value for value in rois.values() if value is not None)
                            score = (rois['conservative_blend'] or -1) * 90 + (rois['market_blend'] or -1) * 35 + (rois['overconfident_5pct'] or -1) * 20 + min(len(selected), 50) / 20
                            if (rois['overconfident_5pct'] or -1) < 0:
                                score -= 10
                            if (rois['conservative_blend'] or -1) < -0.03:
                                score -= 10
                            rows.append({**params, 'rows': int(len(selected)), 'score': round(float(score), 6), 'worst_roi': round(float(worst_roi), 6), **{f'expected_roi_{k}': round(float(v), 6) for k, v in rois.items() if v is not None}})
    if not rows:
        return pd.DataFrame(), pd.DataFrame()
    table = pd.DataFrame(rows).sort_values(['score', 'expected_roi_conservative_blend', 'expected_roi_market_blend', 'rows'], ascending=False).head(50).reset_index(drop=True)
    best = table.iloc[0].to_dict()
    survivor = frame[optimizer_mask(frame, best)].sort_values(['robust_ev', 'ev', 'model_probability', 'edge'], ascending=False).reset_index(drop=True)
    survivor.insert(0, 'strategy', 'Simulation optimized')
    return table, survivor


def load_input() -> pd.DataFrame:
    choice = st.radio(t('source'), [t('session'), t('upload')], horizontal=True)
    if choice == t('upload'):
        upload = st.file_uploader(t('upload_label'), type=['csv'])
        if upload is None:
            return pd.DataFrame()
        try:
            return pd.read_csv(upload)
        except Exception as exc:
            st.error(str(exc))
            return pd.DataFrame()
    return session_frame()


st.title(t('title'))
st.caption(t('caption'))
st.info(t('note'))
raw = load_input()
with st.expander(t('settings'), expanded=True):
    c1, c2, c3 = st.columns(3)
    iterations = c1.number_input(t('iterations'), min_value=1000, max_value=100000, value=20000, step=1000)
    stake = c2.number_input(t('stake'), min_value=0.05, max_value=5.0, value=1.0, step=0.05)
    max_rows = c3.number_input(t('max_rows'), min_value=1, max_value=5000, value=500, step=25)

if st.button(t('run'), type='primary', use_container_width=True):
    if raw.empty:
        st.warning(t('no_rows'))
        st.stop()
    frame = normalize(raw)
    if frame.empty:
        st.warning(t('no_rows'))
        st.stop()
    optimizer_table, survivor = simulation_optimizer(frame)
    masks = strategy_masks(frame)
    scenarios = SCENARIOS
    rows: list[dict[str, Any]] = []
    selected_frames: list[pd.DataFrame] = []
    for strategy, mask in masks.items():
        selected = frame[mask.fillna(False)].copy()
        if selected.empty:
            rows.append({'strategy': strategy, 'scenario': 'all', 'rows': 0})
            continue
        selected = selected.sort_values(['robust_ev', 'ev', 'model_probability', 'edge'], ascending=False).head(int(max_rows))
        temp = selected.copy()
        temp.insert(0, 'strategy', strategy)
        selected_frames.append(temp)
        for scenario in scenarios:
            rows.append({'strategy': strategy, **simulate(selected, scenario, int(iterations), float(stake), seed=20260616 + len(rows))})
    if not survivor.empty:
        st.session_state['simulation_survivor_rows'] = survivor.drop(columns=['strategy'], errors='ignore').to_dict('records')
        st.session_state['ara_latest_predictions'] = survivor.drop(columns=['strategy'], errors='ignore').to_dict('records')
        st.session_state['ara_latest_predictions_source'] = 'Simulation Lab survivor'
        selected_frames.append(survivor)
        for scenario in scenarios:
            rows.append({'strategy': 'Simulation optimized', **simulate(survivor, scenario, int(iterations), float(stake), seed=20260616 + len(rows))})
        st.success(t('saved'))
    summary = pd.DataFrame(rows)
    st.subheader(t('summary'))
    st.dataframe(summary, use_container_width=True, hide_index=True)
    st.subheader(t('optimizer'))
    st.dataframe(optimizer_table, use_container_width=True, hide_index=True)
    selected_all = pd.concat(selected_frames, ignore_index=True, sort=False) if selected_frames else pd.DataFrame()
    st.subheader(t('details'))
    if not selected_all.empty:
        cols = [col for col in ['strategy', 'event', 'sport', 'market_type', 'prediction', 'model_probability', 'decimal_price', 'edge', 'ev', 'robust_ev', 'robust_profit80', 'books', 'api_coverage', 'memory_signal'] if col in selected_all.columns]
        st.dataframe(selected_all[cols], use_container_width=True, hide_index=True)
    report_parts = [summary]
    if not optimizer_table.empty:
        opt = optimizer_table.copy()
        opt.insert(0, 'strategy', 'Simulation optimizer thresholds')
        report_parts.append(opt)
    report = pd.concat(report_parts, ignore_index=True, sort=False)
    st.download_button(t('download'), report.to_csv(index=False), file_name='simulation_lab_report.csv', mime='text/csv')
