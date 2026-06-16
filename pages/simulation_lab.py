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
        'caption': 'Monte Carlo stress test for hit rate, ROI, drawdown, profit risk, and changing conditions. This does not prove the model; it tests whether a strategy survives reasonable probability error.',
        'source': 'Prediction source', 'session': 'Use latest prediction session', 'survivor_source': 'Use last simulation survivor list', 'upload': 'Upload prediction CSV', 'upload_label': 'Upload CSV',
        'run': 'Run simulations + optimizer', 'no_rows': 'No rows available. Run Pro Predictor/Ultra 80 first or upload a CSV.',
        'settings': 'Simulation settings', 'iterations': 'Iterations', 'stake': 'Flat stake units', 'max_rows': 'Max rows per strategy', 'min_rows': 'Minimum optimizer rows',
        'change_settings': 'What-If Change Stress Test',
        'stress_scale': 'Slider guide: 0.00 = ignore that risk, 0.25 = mild stress, 0.50 = serious stress, 0.75+ = extreme stress. These are what-if shocks on top of any weather, injury, altitude, travel, CLV, or price-risk columns already in the CSV.',
        'rain': 'Weather trouble', 'rain_help': 'Tests rain, wind, heat, cold, or wet-field risk. Higher values hurt outdoor/weather-sensitive sports more than indoor sports.',
        'injury': 'Injury to our pick', 'injury_help': 'Tests what happens if the side/player we picked loses a key player or has an injury downgrade.',
        'opp_injury': 'Opponent injury advantage', 'opp_injury_help': 'Tests the opposite: the opponent loses a key player, which can slightly help our pick.',
        'altitude': 'High-altitude disadvantage', 'altitude_help': 'Tests an away team/player from lower altitude playing at a high-altitude venue.',
        'travel': 'Away travel / fatigue', 'travel_help': 'Tests long travel, time-zone changes, short rest, or fatigue for the away side.',
        'chaos': 'Market uncertainty / chaos', 'chaos_help': 'Moves the simulation away from the model and closer to the market when conditions are unstable or unknown.',
        'summary': 'Simulation summary', 'details': 'Selected rows', 'optimizer': 'Simulation optimizer', 'survivor': 'Simulation survivor handoff', 'risk_report': 'What-if risk report', 'download': 'Download simulation report',
        'note': 'Best use: compare strategies under model, market, memory, overconfidence, weather, injury, altitude, travel, market-reversal, and combined-change scenarios. A strategy that only works when conditions stay perfect is not robust enough.',
        'saved': 'Simulation survivor rows saved for Odds Lock Pro handoff.', 'recommendation': 'Recommendation',
    },
    'es': {
        'title': 'Laboratorio de Simulación',
        'caption': 'Prueba Monte Carlo para acierto, ROI, drawdown, riesgo de pérdida y condiciones cambiantes. No prueba el modelo; prueba si la estrategia sobrevive errores razonables de probabilidad.',
        'source': 'Fuente de predicciones', 'session': 'Usar última sesión de predicciones', 'survivor_source': 'Usar última lista sobreviviente de simulación', 'upload': 'Subir CSV de predicciones', 'upload_label': 'Subir CSV',
        'run': 'Ejecutar simulaciones + optimizador', 'no_rows': 'No hay filas. Ejecuta Predictor Pro/Ultra 80 primero o sube un CSV.',
        'settings': 'Configuración de simulación', 'iterations': 'Iteraciones', 'stake': 'Unidades fijas por pick', 'max_rows': 'Máx filas por estrategia', 'min_rows': 'Mínimo de filas del optimizador',
        'change_settings': 'Prueba Qué Pasaría Si Cambian las Condiciones',
        'stress_scale': 'Guía: 0.00 = ignorar ese riesgo, 0.25 = estrés leve, 0.50 = estrés serio, 0.75+ = estrés extremo. Estos son choques hipotéticos además de cualquier columna de clima, lesión, altitud, viaje, CLV o riesgo de precio que ya venga en el CSV.',
        'rain': 'Problemas de clima', 'rain_help': 'Prueba lluvia, viento, calor, frío o cancha mojada. Los valores altos afectan más a deportes al aire libre que a deportes bajo techo.',
        'injury': 'Lesión en nuestro pick', 'injury_help': 'Prueba qué pasa si el lado/jugador que elegimos pierde una pieza clave o tiene una lesión negativa.',
        'opp_injury': 'Ventaja por lesión del rival', 'opp_injury_help': 'Prueba lo contrario: el rival pierde una pieza clave, lo cual puede ayudar ligeramente a nuestro pick.',
        'altitude': 'Desventaja por altitud', 'altitude_help': 'Prueba un equipo/jugador visitante de baja altitud jugando en una sede de alta altitud.',
        'travel': 'Viaje / fatiga del visitante', 'travel_help': 'Prueba viaje largo, cambio de zona horaria, poco descanso o fatiga del visitante.',
        'chaos': 'Incertidumbre / caos del mercado', 'chaos_help': 'Mueve la simulación lejos del modelo y más cerca del mercado cuando las condiciones son inestables o desconocidas.',
        'summary': 'Resumen de simulación', 'details': 'Filas seleccionadas', 'optimizer': 'Optimizador de simulación', 'survivor': 'Traspaso sobreviviente de simulación', 'risk_report': 'Reporte de riesgo qué pasaría si', 'download': 'Descargar reporte de simulación',
        'note': 'Uso ideal: comparar estrategias con escenarios de modelo, mercado, memoria, sobreconfianza, clima, lesiones, altitud, viaje, reversa de mercado y cambio combinado. Una estrategia que solo funciona cuando las condiciones se mantienen perfectas no es suficientemente robusta.',
        'saved': 'Filas sobrevivientes de simulación guardadas para traspaso a Odds Lock Pro.', 'recommendation': 'Recomendación',
    },
}

SCENARIOS = [
    'model', 'market_blend', 'memory_penalty', 'overconfident_5pct', 'overconfident_10pct',
    'conservative_blend', 'rain_weather_stress', 'injury_to_pick_stress',
    'altitude_travel_stress', 'market_reversal_stress', 'unknown_data_shock', 'combined_variable_change',
]
CHANGE_SCENARIOS = {'rain_weather_stress', 'injury_to_pick_stress', 'altitude_travel_stress', 'market_reversal_stress', 'unknown_data_shock', 'combined_variable_change'}
UPSTREAM_SESSION_KEYS = ('pro_predictor_latest_rows', 'ultra80_profit_mode_rows', 'ultra80_max_volume_rows', 'ara_latest_predictions', 'pro_predictor_all_rows')


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


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


def altitude_feet_series(frame: pd.DataFrame, ft_aliases: list[str], m_aliases: list[str]) -> pd.Series:
    feet = num_series(frame, ft_aliases)
    meters = num_series(frame, m_aliases)
    return feet.fillna(meters * 3.28084)


def normalize(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    out['event'] = text_series(frame, ['event', 'game', 'match', 'partido'])
    out['sport'] = text_series(frame, ['sport', 'sport_key', 'league', 'competition', 'deporte'])
    out['market_type'] = text_series(frame, ['market_type', 'market', 'bet_type', 'prop_type', 'tipo_mercado']).str.lower()
    out['prediction'] = text_series(frame, ['prediction', 'pick', 'selection', 'prediccion', 'pronostico'])
    out['home_team'] = text_series(frame, ['home_team', 'home', 'local'])
    out['away_team'] = text_series(frame, ['away_team', 'away', 'visitor', 'visitante'])
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
    out['price_risk'] = num_series(frame, ['_price_range_risk', 'price_range_risk', 'price_range']).fillna(0.0).clip(0.0, 1.0)

    prediction = out['prediction'].str.lower()
    away = out['away_team'].str.lower()
    home = out['home_team'].str.lower()
    out['is_away_pick'] = away.ne('') & prediction.ne('') & prediction.eq(away)
    out['is_home_pick'] = home.ne('') & prediction.ne('') & prediction.eq(home)

    sport = out['sport'].str.lower()
    market = out['market_type'].str.lower()
    out['weather_sensitivity'] = np.select(
        [sport.str.contains('tennis|baseball|mlb|soccer|football|nfl|rugby|cricket', regex=True, na=False), market.str.contains('total|spread|prop', regex=True, na=False)],
        [1.00, 0.75],
        default=0.35,
    )
    out['injury_risk'] = num_series(frame, ['injury_risk', 'picked_side_injury_risk', 'key_injury_risk', 'injury_impact'], probability=True).fillna(0.0).clip(0.0, 1.0)
    out['opponent_injury_risk'] = num_series(frame, ['opponent_injury_risk', 'opponent_key_injury_risk'], probability=True).fillna(0.0).clip(0.0, 1.0)
    out['rain_risk'] = num_series(frame, ['rain_probability', 'precipitation_probability', 'precip_probability', 'rain_risk'], probability=True).fillna(0.0).clip(0.0, 1.0)
    wind = num_series(frame, ['wind_speed_mph', 'wind_mph', 'wind_speed'])
    out['wind_risk'] = (wind.fillna(0.0) / 25.0).clip(0.0, 1.0)
    temp_f = num_series(frame, ['temperature_f', 'temp_f'])
    temp_c = num_series(frame, ['temperature_c', 'temp_c'])
    temp_f = temp_f.fillna(temp_c * 9 / 5 + 32)
    out['heat_cold_risk'] = np.maximum(((temp_f.fillna(70) - 86).clip(lower=0) / 25.0), ((40 - temp_f.fillna(70)).clip(lower=0) / 25.0)).clip(0.0, 1.0)
    stadium_alt = altitude_feet_series(frame, ['stadium_altitude_ft', 'venue_altitude_ft', 'altitude_ft'], ['stadium_altitude_m', 'venue_altitude_m', 'altitude_m'])
    away_base_alt = altitude_feet_series(frame, ['away_base_altitude_ft', 'away_home_altitude_ft', 'away_team_altitude_ft'], ['away_base_altitude_m', 'away_home_altitude_m', 'away_team_altitude_m'])
    altitude_gap = (stadium_alt - away_base_alt).fillna(0.0)
    out['altitude_gap_ft'] = altitude_gap
    out['altitude_risk'] = ((altitude_gap - 2500).clip(lower=0) / 5000.0).clip(0.0, 1.0) * out['is_away_pick'].astype(float)
    travel_km = num_series(frame, ['travel_km', 'away_travel_km', 'travel_distance_km']).fillna(num_series(frame, ['travel_miles', 'away_travel_miles']) * 1.60934)
    tz = num_series(frame, ['timezone_change', 'timezone_shift', 'time_zone_change']).abs().fillna(0.0)
    rest = num_series(frame, ['rest_days', 'away_rest_days']).fillna(7.0)
    travel_component = ((travel_km.fillna(0.0) - 1200).clip(lower=0) / 5000.0).clip(0.0, 1.0)
    tz_component = (tz / 4.0).clip(0.0, 1.0)
    rest_component = ((3.0 - rest).clip(lower=0) / 3.0).clip(0.0, 1.0)
    out['travel_risk'] = np.maximum.reduce([travel_component.to_numpy(float), tz_component.to_numpy(float), rest_component.to_numpy(float)]) * out['is_away_pick'].astype(float)

    closing = num_series(frame, ['closing_decimal_price', 'closing_price', 'close_decimal', 'closing_odds'])
    clv = num_series(frame, ['closing_value_percent', 'clv_percent', 'clv_pct', 'closing_line_value'], percent_like=True)
    inferred_clv = out['decimal_price'] / closing - 1.0
    clv = clv.fillna(inferred_clv)
    out['closing_line_value'] = clv
    out['line_movement_risk'] = (-clv.fillna(0.0) * 5.0).clip(0.0, 1.0)
    out['data_quality_risk'] = np.maximum((1.0 - out['api_coverage']).clip(0.0, 1.0) * 0.35, (4.0 - out['books']).clip(lower=0.0) / 10.0).clip(0.0, 1.0)
    out['weather_risk'] = np.maximum.reduce([out['rain_risk'].to_numpy(float), out['wind_risk'].to_numpy(float), out['heat_cold_risk'].to_numpy(float)]) * out['weather_sensitivity']
    out['variable_change_risk'] = np.maximum.reduce([
        out['weather_risk'].to_numpy(float), out['injury_risk'].to_numpy(float), out['altitude_risk'].to_numpy(float),
        out['travel_risk'].to_numpy(float), out['line_movement_risk'].to_numpy(float), out['price_risk'].to_numpy(float),
        out['data_quality_risk'].to_numpy(float),
    ])
    return out.dropna(subset=['model_probability', 'decimal_price'])


def strategy_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    p = frame['model_probability']
    price = frame['decimal_price']
    return {
        'All valid rows': pd.Series(True, index=frame.index),
        'A strict proof': (p >= 0.80) & frame['ev'].ge(0.025) & frame['robust_ev'].ge(0.015) & frame['edge'].ge(0.075) & frame['books'].ge(6) & frame['api_coverage'].ge(0.66) & price.between(1.27, 1.75) & frame['memory_signal'].ge(-0.005) & frame['robust_profit80'].gt(0) & frame['price_risk'].le(0.25) & frame['variable_change_risk'].le(0.60),
        'B max profitable': (p >= 0.76) & frame['ev'].ge(0.005) & frame['robust_ev'].ge(0.0) & frame['edge'].ge(0.04) & frame['books'].ge(4) & frame['api_coverage'].ge(0.50) & price.between(1.27, 1.75) & frame['memory_signal'].ge(-0.02) & frame['robust_profit80'].gt(0) & frame['price_risk'].le(0.35) & frame['variable_change_risk'].le(0.75),
        'C reserve watch': (p >= 0.72) & frame['edge'].ge(0.02) & frame['books'].ge(3) & price.between(1.25, 2.20) & frame['memory_signal'].ge(-0.035) & frame['robust_profit80'].gt(0) & frame['price_risk'].le(0.50),
        'Profit focus': (p >= 0.65) & frame['ev'].ge(0.02) & frame['robust_ev'].ge(0.0) & frame['books'].ge(4) & frame['api_coverage'].ge(0.50) & price.between(1.27, 2.20) & frame['variable_change_risk'].le(0.80),
        '70 target EV+': (p >= 0.69) & (p <= 0.82) & frame['ev'].gt(0) & frame['books'].ge(4) & frame['api_coverage'].ge(0.50) & frame['variable_change_risk'].le(0.85),
    }


def scenario_probabilities(data: pd.DataFrame, scenario: str, stress: dict[str, float]) -> np.ndarray:
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
    elif scenario == 'rain_weather_stress':
        weather = np.maximum(data['weather_risk'].to_numpy(float), np.full(len(data), stress['rain']) * data['weather_sensitivity'].to_numpy(float))
        true = p - weather * 0.08
    elif scenario == 'injury_to_pick_stress':
        injury = np.maximum(data['injury_risk'].to_numpy(float), np.full(len(data), stress['injury']))
        opponent = np.maximum(data['opponent_injury_risk'].to_numpy(float), np.full(len(data), stress['opponent_injury']))
        true = p - injury * 0.12 + opponent * 0.05
    elif scenario == 'altitude_travel_stress':
        altitude = np.maximum(data['altitude_risk'].to_numpy(float), np.full(len(data), stress['altitude']) * data['is_away_pick'].astype(float).to_numpy())
        travel = np.maximum(data['travel_risk'].to_numpy(float), np.full(len(data), stress['travel']) * data['is_away_pick'].astype(float).to_numpy())
        true = p - altitude * 0.08 - travel * 0.05
    elif scenario == 'market_reversal_stress':
        true = p - data['line_movement_risk'].to_numpy(float) * 0.08 - data['price_risk'].to_numpy(float) * 0.04
        true = true * 0.75 + market * 0.25
    elif scenario == 'unknown_data_shock':
        true = p - data['data_quality_risk'].to_numpy(float) * 0.06 - np.maximum(data['price_risk'].to_numpy(float), data['line_movement_risk'].to_numpy(float)) * 0.03
    elif scenario == 'combined_variable_change':
        weather = np.maximum(data['weather_risk'].to_numpy(float), np.full(len(data), stress['rain']) * data['weather_sensitivity'].to_numpy(float))
        injury = np.maximum(data['injury_risk'].to_numpy(float), np.full(len(data), stress['injury']))
        opponent = np.maximum(data['opponent_injury_risk'].to_numpy(float), np.full(len(data), stress['opponent_injury']))
        altitude = np.maximum(data['altitude_risk'].to_numpy(float), np.full(len(data), stress['altitude']) * data['is_away_pick'].astype(float).to_numpy())
        travel = np.maximum(data['travel_risk'].to_numpy(float), np.full(len(data), stress['travel']) * data['is_away_pick'].astype(float).to_numpy())
        penalty = weather * 0.05 + injury * 0.10 + altitude * 0.06 + travel * 0.04 + data['line_movement_risk'].to_numpy(float) * 0.06 + data['data_quality_risk'].to_numpy(float) * 0.03 - opponent * 0.03
        true = p - penalty
        shrink = np.clip(stress['chaos'], 0.0, 0.75)
        true = true * (1.0 - shrink) + market * shrink
    else:
        true = p
    return np.clip(true, 0.01, 0.99)


def expected_roi(data: pd.DataFrame, scenario: str, stress: dict[str, float]) -> float | None:
    if data.empty:
        return None
    probs = scenario_probabilities(data, scenario, stress)
    odds = data['decimal_price'].to_numpy(float)
    return float(np.mean(probs * odds - 1.0))


def max_drawdown(profit_paths: np.ndarray) -> np.ndarray:
    cumulative = profit_paths.cumsum(axis=1)
    peaks = np.maximum.accumulate(np.maximum(cumulative, 0.0), axis=1)
    drawdowns = peaks - cumulative
    return drawdowns.max(axis=1)


def simulate(data: pd.DataFrame, scenario: str, iterations: int, stake: float, seed: int, stress: dict[str, float]) -> dict[str, Any]:
    if data.empty:
        return {'rows': 0}
    probs = scenario_probabilities(data, scenario, stress)
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
        'avg_change_risk': round(float(data['variable_change_risk'].mean()), 6),
        'scenario_avg_prob': round(float(probs.mean()), 6),
        'scenario_prob_delta': round(float(probs.mean() - data['model_probability'].mean()), 6),
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
        & frame['variable_change_risk'].le(params['max_variable_change_risk']).fillna(True)
        & frame['line_movement_risk'].le(params['max_line_movement_risk']).fillna(True)
    )


def simulation_optimizer(frame: pd.DataFrame, stress: dict[str, float], *, min_rows: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    p_grid = [0.62, 0.65, 0.67, 0.69, 0.70, 0.72, 0.74, 0.76, 0.78, 0.80]
    ev_grid = [0.0, 0.005, 0.01, 0.02, 0.03, 0.04, 0.05]
    edge_grid = [-0.005, 0.0, 0.01, 0.02, 0.03, 0.04]
    books_grid = [0, 4, 10, 20, 50, 60]
    odds_grid = [(1.20, 2.20), (1.25, 2.20), (1.27, 1.75), (1.30, 2.00), (1.35, 2.20), (1.40, 2.50)]
    change_grid = [1.00, 0.85, 0.70, 0.55, 0.40]
    line_grid = [1.00, 0.50, 0.30, 0.15]
    for pmin in p_grid:
        for pmax in [1.00, 0.82, 0.78]:
            if pmin > pmax:
                continue
            for evmin in ev_grid:
                for edgemin in edge_grid:
                    for booksmin in books_grid:
                        for oddsmin, oddsmax in odds_grid:
                            for max_change in change_grid:
                                for max_line in line_grid:
                                    params = {
                                        'min_probability': pmin, 'max_probability': pmax, 'min_ev': evmin,
                                        'min_robust_ev': max(-0.005, evmin - 0.015), 'min_edge': edgemin,
                                        'min_books': booksmin, 'min_api_coverage': 0.50, 'min_odds': oddsmin,
                                        'max_odds': oddsmax, 'min_memory_signal': -0.02, 'max_price_risk': 0.35,
                                        'max_variable_change_risk': max_change, 'max_line_movement_risk': max_line,
                                    }
                                    selected = frame[optimizer_mask(frame, params)]
                                    if len(selected) < int(min_rows):
                                        continue
                                    rois = {scenario: expected_roi(selected, scenario, stress) for scenario in SCENARIOS}
                                    worst_roi = min(value for value in rois.values() if value is not None)
                                    stress_worst = min(rois.get('overconfident_5pct', 0), rois.get('rain_weather_stress', 0), rois.get('injury_to_pick_stress', 0), rois.get('altitude_travel_stress', 0), rois.get('market_reversal_stress', 0), rois.get('unknown_data_shock', 0), rois.get('combined_variable_change', 0))
                                    avg_change = float(selected['variable_change_risk'].mean()) if 'variable_change_risk' in selected else 0.0
                                    score = (rois['conservative_blend'] or -1) * 65 + (rois['market_blend'] or -1) * 25 + stress_worst * 55 + min(len(selected), 50) / 20 - avg_change * 5
                                    if stress_worst < 0:
                                        score -= 12
                                    if (rois['combined_variable_change'] or -1) < -0.03:
                                        score -= 12
                                    rows.append({**params, 'rows': int(len(selected)), 'score': round(float(score), 6), 'worst_roi': round(float(worst_roi), 6), 'worst_change_roi': round(float(stress_worst), 6), 'avg_variable_change_risk': round(avg_change, 6), **{f'expected_roi_{k}': round(float(v), 6) for k, v in rois.items() if v is not None}})
    if not rows:
        return pd.DataFrame(), pd.DataFrame()
    table = pd.DataFrame(rows).sort_values(['score', 'expected_roi_combined_variable_change', 'expected_roi_conservative_blend', 'rows'], ascending=False).head(50).reset_index(drop=True)
    best = table.iloc[0].to_dict()
    survivor = frame[optimizer_mask(frame, best)].sort_values(['variable_change_risk', 'robust_ev', 'ev', 'model_probability', 'edge'], ascending=[True, False, False, False, False]).reset_index(drop=True)
    survivor.insert(0, 'strategy', 'Simulation optimized')
    return table, survivor


def survival_grade(row: pd.Series) -> str:
    scenario = str(row.get('scenario', ''))
    if scenario not in {'market_blend', 'memory_penalty', 'overconfident_5pct', 'conservative_blend'} | CHANGE_SCENARIOS:
        return 'reference'
    roi = float(row.get('mean_roi') or 0.0)
    profit_probability = float(row.get('profit_probability') or 0.0)
    hit80 = float(row.get('prob_hit_80_plus') or 0.0)
    if roi > 0.02 and profit_probability >= 0.60:
        return 'survives'
    if roi >= 0.0 and profit_probability >= 0.52:
        return 'borderline_survives'
    if hit80 >= 0.40 and roi >= -0.02:
        return 'accuracy_only_not_profit_safe'
    return 'fragile'


def risk_report(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    risk_cols = ['variable_change_risk', 'weather_risk', 'injury_risk', 'altitude_risk', 'travel_risk', 'line_movement_risk', 'data_quality_risk', 'price_risk']
    rows = []
    for col in risk_cols:
        if col not in frame.columns:
            continue
        values = pd.to_numeric(frame[col], errors='coerce').fillna(0.0)
        rows.append({'risk_type': col, 'avg_risk': round(float(values.mean()), 6), 'max_risk': round(float(values.max()), 6), 'rows_over_0_50': int(values.gt(0.50).sum()), 'rows_over_0_75': int(values.gt(0.75).sum())})
    return pd.DataFrame(rows).sort_values(['avg_risk', 'max_risk'], ascending=False).reset_index(drop=True)


def recommendation_table(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty or 'strategy' not in summary.columns:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for strategy, group in summary.groupby('strategy'):
        real = group[group['scenario'].isin(['market_blend', 'memory_penalty', 'overconfident_5pct', 'conservative_blend']) | group['scenario'].isin(CHANGE_SCENARIOS)].copy()
        if real.empty:
            continue
        roi_values = pd.to_numeric(real['mean_roi'], errors='coerce').dropna()
        change = real[real['scenario'].isin(CHANGE_SCENARIOS)]
        change_roi = pd.to_numeric(change['mean_roi'], errors='coerce').dropna()
        profit_probs = pd.to_numeric(real['profit_probability'], errors='coerce').dropna()
        hit80 = pd.to_numeric(real['prob_hit_80_plus'], errors='coerce').dropna()
        fragile = int(real['survival_grade'].eq('fragile').sum()) if 'survival_grade' in real.columns else 0
        rows.append({
            'strategy': strategy,
            'rows': int(pd.to_numeric(real['rows'], errors='coerce').max() or 0),
            'worst_mean_roi': None if roi_values.empty else round(float(roi_values.min()), 6),
            'worst_change_roi': None if change_roi.empty else round(float(change_roi.min()), 6),
            'avg_mean_roi': None if roi_values.empty else round(float(roi_values.mean()), 6),
            'worst_profit_probability': None if profit_probs.empty else round(float(profit_probs.min()), 6),
            'best_prob_hit_80_plus': None if hit80.empty else round(float(hit80.max()), 6),
            'fragile_scenarios': fragile,
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out['recommendation'] = np.where(
        (out['fragile_scenarios'].eq(0)) & (out['worst_mean_roi'].fillna(-1).ge(0.0)) & (out['worst_change_roi'].fillna(-1).ge(-0.01)),
        'lock_candidate_after_human_review',
        np.where(out['avg_mean_roi'].fillna(-1).ge(0.0), 'watch_or_reduce_stake', 'do_not_lock')
    )
    return out.sort_values(['recommendation', 'worst_change_roi', 'worst_mean_roi', 'avg_mean_roi', 'rows'], ascending=[True, False, False, False, False]).reset_index(drop=True)


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


st.title(t('title'))
st.caption(t('caption'))
st.info(t('note'))
raw = load_input()
with st.expander(t('settings'), expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    iterations = c1.number_input(t('iterations'), min_value=1000, max_value=100000, value=20000, step=1000)
    stake = c2.number_input(t('stake'), min_value=0.05, max_value=5.0, value=1.0, step=0.05)
    max_rows = c3.number_input(t('max_rows'), min_value=1, max_value=5000, value=500, step=25)
    min_optimizer_rows = c4.number_input(t('min_rows'), min_value=1, max_value=100, value=5, step=1)
with st.expander(t('change_settings'), expanded=False):
    st.caption(t('stress_scale'))
    s1, s2, s3 = st.columns(3)
    rain = s1.slider(t('rain'), min_value=0.0, max_value=1.0, value=0.35, step=0.05, help=t('rain_help'), format='%.2f')
    injury = s2.slider(t('injury'), min_value=0.0, max_value=1.0, value=0.15, step=0.05, help=t('injury_help'), format='%.2f')
    opponent_injury = s3.slider(t('opp_injury'), min_value=0.0, max_value=1.0, value=0.00, step=0.05, help=t('opp_injury_help'), format='%.2f')
    s4, s5, s6 = st.columns(3)
    altitude = s4.slider(t('altitude'), min_value=0.0, max_value=1.0, value=0.25, step=0.05, help=t('altitude_help'), format='%.2f')
    travel = s5.slider(t('travel'), min_value=0.0, max_value=1.0, value=0.20, step=0.05, help=t('travel_help'), format='%.2f')
    chaos = s6.slider(t('chaos'), min_value=0.0, max_value=0.75, value=0.15, step=0.05, help=t('chaos_help'), format='%.2f')
stress_profile = {'rain': float(rain), 'injury': float(injury), 'opponent_injury': float(opponent_injury), 'altitude': float(altitude), 'travel': float(travel), 'chaos': float(chaos)}

if st.button(t('run'), type='primary', use_container_width=True):
    if raw.empty:
        st.warning(t('no_rows'))
        st.stop()
    frame = normalize(raw)
    if frame.empty:
        st.warning(t('no_rows'))
        st.stop()
    optimizer_table, survivor = simulation_optimizer(frame, stress_profile, min_rows=int(min_optimizer_rows))
    masks = strategy_masks(frame)
    scenarios = SCENARIOS
    rows: list[dict[str, Any]] = []
    selected_frames: list[pd.DataFrame] = []
    for strategy, mask in masks.items():
        selected = frame[mask.fillna(False)].copy()
        if selected.empty:
            rows.append({'strategy': strategy, 'scenario': 'all', 'rows': 0})
            continue
        selected = selected.sort_values(['variable_change_risk', 'robust_ev', 'ev', 'model_probability', 'edge'], ascending=[True, False, False, False, False]).head(int(max_rows))
        temp = selected.copy()
        temp.insert(0, 'strategy', strategy)
        selected_frames.append(temp)
        for scenario in scenarios:
            rows.append({'strategy': strategy, **simulate(selected, scenario, int(iterations), float(stake), seed=20260616 + len(rows), stress=stress_profile)})
    if not survivor.empty:
        st.session_state['simulation_survivor_rows'] = survivor.drop(columns=['strategy'], errors='ignore').to_dict('records')
        st.session_state['ara_latest_predictions'] = survivor.drop(columns=['strategy'], errors='ignore').to_dict('records')
        st.session_state['ara_latest_predictions_source'] = 'Simulation Lab survivor'
        selected_frames.append(survivor)
        for scenario in scenarios:
            rows.append({'strategy': 'Simulation optimized', **simulate(survivor, scenario, int(iterations), float(stake), seed=20260616 + len(rows), stress=stress_profile)})
        st.success(t('saved'))
    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary['survival_grade'] = summary.apply(survival_grade, axis=1)
    recommendations = recommendation_table(summary)
    selected_all = pd.concat(selected_frames, ignore_index=True, sort=False) if selected_frames else pd.DataFrame()
    risks = risk_report(selected_all)
    st.subheader(t('recommendation'))
    st.dataframe(recommendations, use_container_width=True, hide_index=True)
    st.subheader(t('summary'))
    st.dataframe(summary, use_container_width=True, hide_index=True)
    st.subheader(t('optimizer'))
    st.dataframe(optimizer_table, use_container_width=True, hide_index=True)
    st.subheader(t('risk_report'))
    st.dataframe(risks, use_container_width=True, hide_index=True)
    st.subheader(t('details'))
    if not selected_all.empty:
        cols = [col for col in ['strategy', 'event', 'sport', 'market_type', 'prediction', 'model_probability', 'decimal_price', 'edge', 'ev', 'robust_ev', 'robust_profit80', 'variable_change_risk', 'weather_risk', 'injury_risk', 'altitude_risk', 'travel_risk', 'line_movement_risk', 'data_quality_risk', 'books', 'api_coverage', 'memory_signal'] if col in selected_all.columns]
        st.dataframe(selected_all[cols], use_container_width=True, hide_index=True)
    report_parts = [summary]
    if not recommendations.empty:
        rec = recommendations.copy()
        rec.insert(0, 'report_section', 'recommendations')
        report_parts.append(rec)
    if not optimizer_table.empty:
        opt = optimizer_table.copy()
        opt.insert(0, 'report_section', 'optimizer_thresholds')
        report_parts.append(opt)
    if not risks.empty:
        risk_export = risks.copy()
        risk_export.insert(0, 'report_section', 'change_risk_report')
        report_parts.append(risk_export)
    report = pd.concat(report_parts, ignore_index=True, sort=False)
    st.download_button(t('download'), report.to_csv(index=False), file_name='simulation_lab_report.csv', mime='text/csv')
