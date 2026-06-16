from __future__ import annotations

import re
import unicodedata
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title='Simulation Lab', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='simulation_lab_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'Simulation Lab',
        'caption': 'Monte Carlo stress testing, game-by-game scout risk, automatic what-if selection, optimizer, drawdown, ROI, and proof handoff.',
        'source': 'Prediction source', 'session': 'Use latest prediction session', 'survivor_source': 'Use last simulation survivor list', 'upload': 'Upload prediction CSV', 'upload_label': 'Upload CSV',
        'run': 'Run simulations + optimizer', 'no_rows': 'No usable simulation rows found. The file loaded, but the simulator could not find usable probability + odds columns.',
        'settings': 'Simulation settings', 'iterations': 'Iterations', 'stake': 'Flat stake units', 'max_rows': 'Max rows per strategy', 'min_rows': 'Minimum optimizer rows',
        'change_settings': 'Game Scout Auto-Select', 'preset': 'Fallback stress preset', 'swarm': 'Use Game Scout Swarm', 'auto_select': 'Auto-select each game\'s weather/news/altitude/travel/market risk',
        'swarm_help': 'Runs per-game scout agents for weather, injury/news, altitude, travel, market movement, data quality, memory, and price risk.',
        'auto_help': 'When ON, the simulator uses each game\'s own columns and scout flags first. The sliders become fallback values only when the CSV has no data for that risk.',
        'stress_scale': 'Use presets first. 0.00 = ignore, 0.25 = mild, 0.50 = serious, 0.75+ = extreme. In Auto mode these are fallback values, not forced onto every game.',
        'rain': 'Bad weather fallback', 'rain_help': 'Fallback for rain, wind, heat, cold, or wet-field risk when a game has no weather columns.',
        'injury': 'Bad news fallback', 'injury_help': 'Fallback if the side/player we picked has no injury/news columns but you want to test a bad-news shock.',
        'opp_injury': 'Good news fallback', 'opp_injury_help': 'Fallback if the opponent may lose a key player. This helps our pick slightly.',
        'altitude': 'Altitude fallback', 'altitude_help': 'Fallback for low-altitude away teams/players playing at high-altitude venues.',
        'travel': 'Travel/fatigue fallback', 'travel_help': 'Fallback for long travel, time-zone changes, short rest, back-to-back games, or fatigue.',
        'chaos': 'Market/news uncertainty fallback', 'chaos_help': 'Fallback when conditions are unclear; pulls simulation toward market probability.',
        'summary': 'Simulation summary', 'details': 'Selected rows', 'optimizer': 'Simulation optimizer', 'survivor': 'Simulation survivor handoff', 'risk_report': 'What-if risk report', 'scout_report': 'Game Scout Swarm report', 'diagnostics': 'Input diagnostics', 'download': 'Download simulation report',
        'note': 'Best use: run Auto-Select so the simulator chooses risk settings game by game from the data. Manual sliders should be fallback stress tests, not guesses for every game.',
        'saved': 'Simulation survivor rows saved for Odds Lock Pro handoff.', 'recommendation': 'Recommendation', 'meters': 'Fallback stress meters',
    },
    'es': {
        'title': 'Laboratorio de Simulación',
        'caption': 'Prueba Monte Carlo, riesgo por juego, selección automática de escenarios, optimizador, drawdown, ROI y traspaso a proof.',
        'source': 'Fuente de predicciones', 'session': 'Usar última sesión de predicciones', 'survivor_source': 'Usar última lista sobreviviente de simulación', 'upload': 'Subir CSV de predicciones', 'upload_label': 'Subir CSV',
        'run': 'Ejecutar simulaciones + optimizador', 'no_rows': 'No se encontraron filas útiles. El archivo cargó, pero el simulador no pudo encontrar probabilidad + cuotas utilizables.',
        'settings': 'Configuración de simulación', 'iterations': 'Iteraciones', 'stake': 'Unidades fijas por pick', 'max_rows': 'Máx filas por estrategia', 'min_rows': 'Mínimo de filas del optimizador',
        'change_settings': 'Auto-Selección Scout por Juego', 'preset': 'Preset de estrés de respaldo', 'swarm': 'Usar enjambre scout por juego', 'auto_select': 'Auto-seleccionar clima/noticias/altitud/viaje/mercado por juego',
        'swarm_help': 'Ejecuta scouts por juego para clima, lesión/noticias, altitud, viaje, movimiento de mercado, calidad de datos, memoria y riesgo de precio.',
        'auto_help': 'Activado: usa primero los datos y señales de cada juego. Los sliders solo son valores de respaldo si el CSV no trae ese riesgo.',
        'stress_scale': 'Usa presets primero. 0.00 = ignorar, 0.25 = leve, 0.50 = serio, 0.75+ = extremo. En modo Auto son respaldos, no se fuerzan en cada juego.',
        'rain': 'Respaldo mal clima', 'rain_help': 'Respaldo para lluvia, viento, calor, frío o cancha mojada cuando el juego no trae columnas de clima.',
        'injury': 'Respaldo mala noticia', 'injury_help': 'Respaldo si nuestro lado/jugador no trae columnas de lesión/noticia pero quieres probar un golpe negativo.',
        'opp_injury': 'Respaldo buena noticia', 'opp_injury_help': 'Respaldo si el rival puede perder una pieza clave. Ayuda un poco a nuestro pick.',
        'altitude': 'Respaldo altitud', 'altitude_help': 'Respaldo para visitantes de baja altitud jugando en sede de alta altitud.',
        'travel': 'Respaldo viaje/fatiga', 'travel_help': 'Respaldo para viaje largo, cambio horario, poco descanso, back-to-back o fatiga.',
        'chaos': 'Respaldo incertidumbre', 'chaos_help': 'Respaldo cuando las condiciones no están claras; acerca la simulación al mercado.',
        'summary': 'Resumen de simulación', 'details': 'Filas seleccionadas', 'optimizer': 'Optimizador de simulación', 'survivor': 'Traspaso sobreviviente', 'risk_report': 'Reporte de riesgo qué pasaría si', 'scout_report': 'Reporte de enjambre scout', 'diagnostics': 'Diagnóstico de entrada', 'download': 'Descargar reporte',
        'note': 'Uso ideal: ejecuta Auto-Selección para que el simulador elija riesgos juego por juego desde los datos. Los sliders deben ser respaldos, no adivinanzas para todos los juegos.',
        'saved': 'Filas sobrevivientes guardadas para Odds Lock Pro.', 'recommendation': 'Recomendación', 'meters': 'Medidores de respaldo',
    },
}

SCENARIOS = [
    'model', 'market_blend', 'memory_penalty', 'overconfident_5pct', 'overconfident_10pct',
    'conservative_blend', 'rain_weather_stress', 'injury_to_pick_stress', 'altitude_travel_stress',
    'market_reversal_stress', 'unknown_data_shock', 'combined_variable_change',
]
CHANGE_SCENARIOS = {'rain_weather_stress', 'injury_to_pick_stress', 'altitude_travel_stress', 'market_reversal_stress', 'unknown_data_shock', 'combined_variable_change'}
UPSTREAM_SESSION_KEYS = ('pro_predictor_latest_rows', 'ultra80_profit_mode_rows', 'ultra80_max_volume_rows', 'ara_latest_predictions', 'pro_predictor_all_rows')
STRESS_PRESETS = {
    'Balanced default': {'rain': 0.25, 'injury': 0.10, 'opponent_injury': 0.00, 'altitude': 0.20, 'travel': 0.15, 'chaos': 0.10},
    'Bad weather test': {'rain': 0.65, 'injury': 0.10, 'opponent_injury': 0.00, 'altitude': 0.20, 'travel': 0.15, 'chaos': 0.15},
    'Injury scare test': {'rain': 0.25, 'injury': 0.55, 'opponent_injury': 0.00, 'altitude': 0.20, 'travel': 0.15, 'chaos': 0.20},
    'Altitude/travel test': {'rain': 0.25, 'injury': 0.10, 'opponent_injury': 0.00, 'altitude': 0.65, 'travel': 0.55, 'chaos': 0.20},
    'Market chaos test': {'rain': 0.30, 'injury': 0.20, 'opponent_injury': 0.00, 'altitude': 0.25, 'travel': 0.25, 'chaos': 0.45},
    'Worst-case combo': {'rain': 0.60, 'injury': 0.45, 'opponent_injury': 0.00, 'altitude': 0.55, 'travel': 0.45, 'chaos': 0.50},
}
RISK_COLS = ['weather_risk', 'injury_risk', 'news_risk', 'altitude_risk', 'travel_risk', 'line_movement_risk', 'data_quality_risk', 'negative_memory_risk', 'price_risk']

EVENT_ALIASES = ['event', 'game', 'match', 'partido', 'fixture', 'fixture_name', 'game_name', 'event_name', 'evento']
PICK_ALIASES = ['prediction', 'pick', 'selection', 'prediccion', 'predicción', 'pronostico', 'pronóstico', 'predicted_winner', 'team_pick', 'side', 'seleccion']
PROB_ALIASES = ['model_probability_clean', 'model_probability', 'final_probability_value', 'final_probability', 'probability', 'probabilidad', 'prob_final', 'prob final', 'prob. final', 'confidence_probability', 'predicted_probability', 'win_probability', 'win_prob', 'projected_probability', 'prob_modelo', 'confianza']
MARKET_PROB_ALIASES = ['market_probability', 'market_implied_probability', 'implied_probability', 'no_vig_probability', 'prob_mercado', 'prob mercado', 'prob. mercado']
DECIMAL_ALIASES = ['decimal_price', 'decimal_odds', 'best_price', 'average_price', 'best_odds', 'market_odds', 'book_odds', 'odds', 'price', 'cuota', 'mejor_cuota', 'mejor cuota', 'cuota_decimal']
AMERICAN_ALIASES = ['american_odds', 'american_price', 'moneyline', 'ml', 'american']
EDGE_ALIASES = ['model_market_edge', 'model_edge', 'edge_probability', 'edge', 'edge_percent', 'model_minus_no_vig', 'ventaja']
EV_ALIASES = ['expected_value_per_unit', 'estimated_ev_decimal', 'computed_ev_decimal', 'estimated_ev', 'ev', 'expected_value', 'valor_esperado']
BOOK_ALIASES = ['bookmaker_count', 'books', 'source_count', 'bookmakers', 'casas', 'num_books', 'sportsbooks_count']
API_ALIASES = ['api_coverage_score', 'api_coverage', 'cobertura_api', 'cobertura api']


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def column_key(value: Any) -> str:
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode('ascii').lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')


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


def altitude_feet_series(frame: pd.DataFrame, ft_aliases: list[str], m_aliases: list[str]) -> pd.Series:
    return num_series(frame, ft_aliases).fillna(num_series(frame, m_aliases) * 3.28084)


def text_risk(frame: pd.DataFrame) -> pd.Series:
    note = text_series(frame, ['news_summary', 'latest_news', 'injury_news', 'team_news', 'weather_note', 'notes', 'motivo_revisar', 'reason', 'api_context_error']).str.lower()
    high = 'out|doubtful|suspended|late scratch|illness|storm|severe|postponed|lineup change|not starting|ruled out|descartado|suspendido|lesionado'
    medium = 'questionable|probable|limited|rest|rotation|rain|wind|heat|cold|altitude|travel|fatigue|line move|odds drift|market moved|uncertain|duda|lluvia|viento|viaje|fatiga|altitud'
    risk = pd.Series(0.0, index=frame.index)
    risk = risk.mask(note.str.contains(medium, regex=True, na=False), 0.35)
    risk = risk.mask(note.str.contains(high, regex=True, na=False), 0.75)
    return risk.fillna(0.0).clip(0.0, 1.0)


def normalize(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    out['event'] = text_series(frame, EVENT_ALIASES)
    out['sport'] = text_series(frame, ['sport', 'sport_key', 'league', 'competition', 'deporte'])
    out['market_type'] = text_series(frame, ['market_type', 'market', 'bet_type', 'prop_type', 'tipo_mercado', 'mercado']).str.lower()
    out['prediction'] = text_series(frame, PICK_ALIASES)
    out['home_team'] = text_series(frame, ['home_team', 'home', 'local', 'equipo_local'])
    out['away_team'] = text_series(frame, ['away_team', 'away', 'visitor', 'visitante', 'equipo_visitante'])
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
    temp_f = num_series(frame, ['temperature_f', 'temp_f']).fillna(num_series(frame, ['temperature_c', 'temp_c']) * 9 / 5 + 32)
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
    clv = num_series(frame, ['closing_value_percent', 'clv_percent', 'clv_pct', 'closing_line_value'], percent_like=True).fillna(out['decimal_price'] / closing - 1.0)
    out['closing_line_value'] = clv
    out['line_movement_risk'] = (-clv.fillna(0.0) * 5.0).clip(0.0, 1.0)
    out['data_quality_risk'] = np.maximum((1.0 - out['api_coverage']).clip(0.0, 1.0) * 0.35, (4.0 - out['books']).clip(lower=0.0) / 10.0).clip(0.0, 1.0)
    out['news_risk'] = text_risk(frame)
    out['weather_risk'] = np.maximum.reduce([out['rain_risk'].to_numpy(float), out['wind_risk'].to_numpy(float), out['heat_cold_risk'].to_numpy(float)]) * out['weather_sensitivity']
    out['negative_memory_risk'] = (-out['memory_signal']).clip(lower=0.0, upper=0.08) / 0.08
    out['variable_change_risk'] = np.maximum.reduce([out[col].to_numpy(float) for col in RISK_COLS])
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
        {'check': 'market probability fallback', 'value': 'found' if matched(MARKET_PROB_ALIASES) else 'missing', 'matched_column': matched(MARKET_PROB_ALIASES)},
        {'check': 'usable simulation rows', 'value': int(len(frame)), 'matched_column': 'needs model probability + decimal/american odds or market probability'},
    ])


def auto_game_profile(frame: pd.DataFrame, fallback: dict[str, float], *, auto_select: bool = True) -> pd.DataFrame:
    out = frame.copy()
    if not auto_select:
        out['auto_weather_stress'] = float(fallback['rain']) * out['weather_sensitivity']
        out['auto_injury_stress'] = float(fallback['injury'])
        out['auto_opponent_boost'] = float(fallback['opponent_injury'])
        out['auto_altitude_stress'] = float(fallback['altitude']) * out['is_away_pick'].astype(float)
        out['auto_travel_stress'] = float(fallback['travel']) * out['is_away_pick'].astype(float)
        out['auto_chaos_stress'] = float(fallback['chaos'])
    else:
        out['auto_weather_stress'] = np.maximum(out['weather_risk'], out['rain_risk'] * out['weather_sensitivity']).fillna(0.0)
        out['auto_injury_stress'] = np.maximum.reduce([out['injury_risk'].to_numpy(float), out['news_risk'].to_numpy(float)])
        out['auto_opponent_boost'] = out['opponent_injury_risk'].fillna(0.0)
        out['auto_altitude_stress'] = out['altitude_risk'].fillna(0.0)
        out['auto_travel_stress'] = out['travel_risk'].fillna(0.0)
        out['auto_chaos_stress'] = np.maximum.reduce([out['data_quality_risk'].to_numpy(float), out['line_movement_risk'].to_numpy(float), out['price_risk'].to_numpy(float), out['negative_memory_risk'].to_numpy(float) * 0.50])
        for col, fallback_key in [('auto_weather_stress', 'rain'), ('auto_injury_stress', 'injury'), ('auto_altitude_stress', 'altitude'), ('auto_travel_stress', 'travel'), ('auto_chaos_stress', 'chaos')]:
            values = pd.to_numeric(out[col], errors='coerce').fillna(0.0)
            no_signal = values.le(0.0)
            fallback_values: Any = float(fallback[fallback_key])
            if fallback_key == 'rain':
                fallback_values = fallback_values * out['weather_sensitivity']
            if fallback_key in {'altitude', 'travel'}:
                fallback_values = fallback_values * out['is_away_pick'].astype(float)
            out[col] = values.where(~no_signal, fallback_values)
        out['auto_opponent_boost'] = out['auto_opponent_boost'].where(out['auto_opponent_boost'].gt(0), float(fallback['opponent_injury']))
    auto_cols = ['auto_weather_stress', 'auto_injury_stress', 'auto_altitude_stress', 'auto_travel_stress', 'auto_chaos_stress', 'auto_opponent_boost']
    for col in auto_cols:
        out[col] = pd.to_numeric(out[col], errors='coerce').fillna(0.0).clip(0.0, 1.0)
    out['auto_total_stress'] = np.maximum.reduce([out[col].to_numpy(float) for col in auto_cols if col != 'auto_opponent_boost'])
    out['auto_mode'] = 'auto_per_game' if auto_select else 'manual_global_fallback'
    return out


def strategy_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    p = frame['model_probability']
    price = frame['decimal_price']
    return {
        'All valid rows': pd.Series(True, index=frame.index),
        'A strict proof': (p >= 0.80) & frame['ev'].ge(0.025) & frame['robust_ev'].ge(0.015) & frame['edge'].ge(0.075) & frame['books'].ge(6) & frame['api_coverage'].ge(0.66) & price.between(1.27, 1.75) & frame['memory_signal'].ge(-0.005) & frame['robust_profit80'].gt(0) & frame['price_risk'].le(0.25) & frame['auto_total_stress'].le(0.60),
        'B max profitable': (p >= 0.76) & frame['ev'].ge(0.005) & frame['robust_ev'].ge(0.0) & frame['edge'].ge(0.04) & frame['books'].ge(4) & frame['api_coverage'].ge(0.50) & price.between(1.27, 1.75) & frame['memory_signal'].ge(-0.02) & frame['robust_profit80'].gt(0) & frame['price_risk'].le(0.35) & frame['auto_total_stress'].le(0.75),
        'C reserve watch': (p >= 0.72) & frame['edge'].ge(0.02) & frame['books'].ge(3) & price.between(1.25, 2.20) & frame['memory_signal'].ge(-0.035) & frame['robust_profit80'].gt(0) & frame['price_risk'].le(0.50),
        'Profit focus': (p >= 0.65) & frame['ev'].ge(0.02) & frame['robust_ev'].ge(0.0) & frame['books'].ge(4) & frame['api_coverage'].ge(0.50) & price.between(1.27, 2.20) & frame['auto_total_stress'].le(0.80),
        '70 target EV+': (p >= 0.69) & (p <= 0.82) & frame['ev'].gt(0) & frame['books'].ge(4) & frame['api_coverage'].ge(0.50) & frame['auto_total_stress'].le(0.85),
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
    elif scenario == 'rain_weather_stress':
        true = p - data['auto_weather_stress'].to_numpy(float) * 0.08
    elif scenario == 'injury_to_pick_stress':
        true = p - data['auto_injury_stress'].to_numpy(float) * 0.12 + data['auto_opponent_boost'].to_numpy(float) * 0.05
    elif scenario == 'altitude_travel_stress':
        true = p - data['auto_altitude_stress'].to_numpy(float) * 0.08 - data['auto_travel_stress'].to_numpy(float) * 0.05
    elif scenario == 'market_reversal_stress':
        true = p - data['line_movement_risk'].to_numpy(float) * 0.08 - data['price_risk'].to_numpy(float) * 0.04
        true = true * 0.75 + market * 0.25
    elif scenario == 'unknown_data_shock':
        true = p - data['data_quality_risk'].to_numpy(float) * 0.06 - np.maximum.reduce([data['price_risk'].to_numpy(float), data['line_movement_risk'].to_numpy(float), data['news_risk'].to_numpy(float)]) * 0.03
    elif scenario == 'combined_variable_change':
        penalty = data['auto_weather_stress'].to_numpy(float) * 0.05 + data['auto_injury_stress'].to_numpy(float) * 0.10 + data['auto_altitude_stress'].to_numpy(float) * 0.06 + data['auto_travel_stress'].to_numpy(float) * 0.04 + data['line_movement_risk'].to_numpy(float) * 0.06 + data['data_quality_risk'].to_numpy(float) * 0.03 + data['negative_memory_risk'].to_numpy(float) * 0.02 - data['auto_opponent_boost'].to_numpy(float) * 0.03
        true = p - penalty
        shrink = np.clip(data['auto_chaos_stress'].to_numpy(float), 0.0, 0.75)
        true = true * (1.0 - shrink) + market * shrink
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
    return (peaks - cumulative).max(axis=1)


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
        'rows': int(len(data)), 'scenario': scenario,
        'avg_model_prob': round(float(data['model_probability'].mean()), 6),
        'avg_odds': round(float(data['decimal_price'].mean()), 4),
        'avg_auto_stress': round(float(data['auto_total_stress'].mean()), 6),
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
        & frame['auto_total_stress'].le(params['max_auto_stress']).fillna(True)
        & frame['line_movement_risk'].le(params['max_line_movement_risk']).fillna(True)
    )


def simulation_optimizer(frame: pd.DataFrame, *, min_rows: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    p_grid = [0.62, 0.65, 0.67, 0.69, 0.70, 0.72, 0.74, 0.76, 0.78, 0.80]
    ev_grid = [0.0, 0.005, 0.01, 0.02, 0.03, 0.04, 0.05]
    edge_grid = [-0.005, 0.0, 0.01, 0.02, 0.03, 0.04]
    books_grid = [0, 4, 10, 20, 50, 60]
    odds_grid = [(1.20, 2.20), (1.25, 2.20), (1.27, 1.75), (1.30, 2.00), (1.35, 2.20), (1.40, 2.50)]
    stress_grid = [1.00, 0.85, 0.70, 0.55, 0.40]
    line_grid = [1.00, 0.50, 0.30, 0.15]
    for pmin in p_grid:
        for pmax in [1.00, 0.82, 0.78]:
            if pmin > pmax:
                continue
            for evmin in ev_grid:
                for edgemin in edge_grid:
                    for booksmin in books_grid:
                        for oddsmin, oddsmax in odds_grid:
                            for max_stress in stress_grid:
                                for max_line in line_grid:
                                    params = {'min_probability': pmin, 'max_probability': pmax, 'min_ev': evmin, 'min_robust_ev': max(-0.005, evmin - 0.015), 'min_edge': edgemin, 'min_books': booksmin, 'min_api_coverage': 0.50, 'min_odds': oddsmin, 'max_odds': oddsmax, 'min_memory_signal': -0.02, 'max_price_risk': 0.35, 'max_auto_stress': max_stress, 'max_line_movement_risk': max_line}
                                    selected = frame[optimizer_mask(frame, params)]
                                    if len(selected) < int(min_rows):
                                        continue
                                    rois = {scenario: expected_roi(selected, scenario) for scenario in SCENARIOS}
                                    stress_worst = min(rois.get(s, 0) for s in ['overconfident_5pct', 'rain_weather_stress', 'injury_to_pick_stress', 'altitude_travel_stress', 'market_reversal_stress', 'unknown_data_shock', 'combined_variable_change'])
                                    avg_stress = float(selected['auto_total_stress'].mean()) if 'auto_total_stress' in selected else 0.0
                                    score = (rois['conservative_blend'] or -1) * 65 + (rois['market_blend'] or -1) * 25 + stress_worst * 55 + min(len(selected), 50) / 20 - avg_stress * 5
                                    if stress_worst < 0:
                                        score -= 12
                                    if (rois['combined_variable_change'] or -1) < -0.03:
                                        score -= 12
                                    rows.append({**params, 'rows': int(len(selected)), 'score': round(float(score), 6), 'worst_roi': round(float(min(value for value in rois.values() if value is not None)), 6), 'worst_change_roi': round(float(stress_worst), 6), 'avg_auto_stress': round(avg_stress, 6), **{f'expected_roi_{k}': round(float(v), 6) for k, v in rois.items() if v is not None}})
    if not rows:
        return pd.DataFrame(), pd.DataFrame()
    table = pd.DataFrame(rows).sort_values(['score', 'expected_roi_combined_variable_change', 'expected_roi_conservative_blend', 'rows'], ascending=False).head(50).reset_index(drop=True)
    survivor = frame[optimizer_mask(frame, table.iloc[0].to_dict())].sort_values(['auto_total_stress', 'robust_ev', 'ev', 'model_probability', 'edge'], ascending=[True, False, False, False, False]).reset_index(drop=True)
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
    risk_cols = ['auto_total_stress', 'auto_weather_stress', 'auto_injury_stress', 'auto_altitude_stress', 'auto_travel_stress', 'auto_chaos_stress', 'weather_risk', 'injury_risk', 'news_risk', 'line_movement_risk', 'data_quality_risk', 'negative_memory_risk', 'price_risk']
    rows = []
    for col in risk_cols:
        if col not in frame.columns:
            continue
        values = pd.to_numeric(frame[col], errors='coerce').fillna(0.0)
        rows.append({'risk_type': col, 'avg_risk': round(float(values.mean()), 6), 'max_risk': round(float(values.max()), 6), 'rows_over_0_50': int(values.gt(0.50).sum()), 'rows_over_0_75': int(values.gt(0.75).sum())})
    return pd.DataFrame(rows).sort_values(['avg_risk', 'max_risk'], ascending=False).reset_index(drop=True)


def game_scout_report(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    risk_cols = ['auto_weather_stress', 'auto_injury_stress', 'auto_altitude_stress', 'auto_travel_stress', 'auto_chaos_stress', 'line_movement_risk', 'data_quality_risk', 'negative_memory_risk', 'price_risk']
    for _, row in frame.iterrows():
        risks = {col: float(pd.to_numeric(pd.Series([row.get(col, 0.0)]), errors='coerce').fillna(0.0).iloc[0]) for col in risk_cols}
        top = sorted([(col.replace('auto_', '').replace('_stress', '').replace('_risk', '').replace('_', ' '), val) for col, val in risks.items() if val >= 0.20], key=lambda item: item[1], reverse=True)[:4]
        risk_text = '; '.join(f'{name}: {value:.2f}' for name, value in top) or 'no major risk detected'
        stress = float(row.get('auto_total_stress') or 0.0)
        ev = float(row.get('robust_ev') if pd.notna(row.get('robust_ev')) else row.get('ev') or 0.0)
        p = float(row.get('model_probability') or 0.0)
        if stress <= 0.35 and ev > 0 and p >= 0.70:
            action = 'lock_candidate_after_price_check'
        elif stress <= 0.65 and ev >= 0:
            action = 'watch_or_reduce_stake'
        else:
            action = 'do_not_lock_until_rescanned'
        rows.append({'event': row.get('event', ''), 'sport': row.get('sport', ''), 'market_type': row.get('market_type', ''), 'prediction': row.get('prediction', ''), 'model_probability': round(p, 6), 'decimal_price': row.get('decimal_price', ''), 'robust_ev': round(ev, 6), 'auto_mode': row.get('auto_mode', ''), 'auto_stress_score': round(stress, 6), 'top_scout_flags': risk_text, 'scout_action': action})
    return pd.DataFrame(rows).sort_values(['scout_action', 'auto_stress_score', 'robust_ev'], ascending=[True, True, False]).reset_index(drop=True)


def recommendation_table(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty or 'strategy' not in summary.columns:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for strategy, group in summary.groupby('strategy'):
        real = group[group['scenario'].isin(['market_blend', 'memory_penalty', 'overconfident_5pct', 'conservative_blend']) | group['scenario'].isin(CHANGE_SCENARIOS)].copy()
        if real.empty:
            continue
        roi_values = pd.to_numeric(real['mean_roi'], errors='coerce').dropna()
        change_roi = pd.to_numeric(real[real['scenario'].isin(CHANGE_SCENARIOS)]['mean_roi'], errors='coerce').dropna()
        profit_probs = pd.to_numeric(real['profit_probability'], errors='coerce').dropna()
        hit80 = pd.to_numeric(real['prob_hit_80_plus'], errors='coerce').dropna()
        fragile = int(real['survival_grade'].eq('fragile').sum()) if 'survival_grade' in real.columns else 0
        rows.append({'strategy': strategy, 'rows': int(pd.to_numeric(real['rows'], errors='coerce').max() or 0), 'worst_mean_roi': None if roi_values.empty else round(float(roi_values.min()), 6), 'worst_change_roi': None if change_roi.empty else round(float(change_roi.min()), 6), 'avg_mean_roi': None if roi_values.empty else round(float(roi_values.mean()), 6), 'worst_profit_probability': None if profit_probs.empty else round(float(profit_probs.min()), 6), 'best_prob_hit_80_plus': None if hit80.empty else round(float(hit80.max()), 6), 'fragile_scenarios': fragile})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out['recommendation'] = np.where((out['fragile_scenarios'].eq(0)) & (out['worst_mean_roi'].fillna(-1).ge(0.0)) & (out['worst_change_roi'].fillna(-1).ge(-0.01)), 'lock_candidate_after_human_review', np.where(out['avg_mean_roi'].fillna(-1).ge(0.0), 'watch_or_reduce_stake', 'do_not_lock'))
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


def render_meter(label: str, value: float, help_text: str = '', *, good_when_high: bool = False) -> None:
    value = float(np.clip(value, 0.0, 1.0))
    level = 'Low' if value < 0.25 else 'Mild' if value < 0.50 else 'Serious' if value < 0.75 else 'Extreme'
    if good_when_high:
        level = {'Low': 'Small boost', 'Mild': 'Useful boost', 'Serious': 'Strong boost', 'Extreme': 'Major boost'}[level]
    st.caption(f'{label}: {value:.2f} · {level}' + (f' — {help_text}' if help_text else ''))
    st.progress(value)


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
    preset_name = st.selectbox(t('preset'), list(STRESS_PRESETS.keys()), index=0)
    preset = STRESS_PRESETS[preset_name]
    use_swarm = st.checkbox(t('swarm'), value=True, help=t('swarm_help'))
    auto_select = st.checkbox(t('auto_select'), value=True, help=t('auto_help'))
    st.caption(t('stress_scale'))
    s1, s2, s3 = st.columns(3)
    rain = s1.slider(t('rain'), min_value=0.0, max_value=1.0, value=float(preset['rain']), step=0.05, help=t('rain_help'), format='%.2f')
    injury = s2.slider(t('injury'), min_value=0.0, max_value=1.0, value=float(preset['injury']), step=0.05, help=t('injury_help'), format='%.2f')
    opponent_injury = s3.slider(t('opp_injury'), min_value=0.0, max_value=1.0, value=float(preset['opponent_injury']), step=0.05, help=t('opp_injury_help'), format='%.2f')
    s4, s5, s6 = st.columns(3)
    altitude = s4.slider(t('altitude'), min_value=0.0, max_value=1.0, value=float(preset['altitude']), step=0.05, help=t('altitude_help'), format='%.2f')
    travel = s5.slider(t('travel'), min_value=0.0, max_value=1.0, value=float(preset['travel']), step=0.05, help=t('travel_help'), format='%.2f')
    chaos = s6.slider(t('chaos'), min_value=0.0, max_value=0.75, value=float(preset['chaos']), step=0.05, help=t('chaos_help'), format='%.2f')
    st.markdown(f'#### {t("meters")}')
    m1, m2 = st.columns(2)
    with m1:
        render_meter(t('rain'), rain, t('rain_help'))
        render_meter(t('injury'), injury, t('injury_help'))
        render_meter(t('altitude'), altitude, t('altitude_help'))
    with m2:
        render_meter(t('opp_injury'), opponent_injury, t('opp_injury_help'), good_when_high=True)
        render_meter(t('travel'), travel, t('travel_help'))
        render_meter(t('chaos'), chaos, t('chaos_help'))
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
    frame = auto_game_profile(frame, stress_profile, auto_select=bool(auto_select and use_swarm))
    optimizer_table, survivor = simulation_optimizer(frame, min_rows=int(min_optimizer_rows))
    masks = strategy_masks(frame)
    rows: list[dict[str, Any]] = []
    selected_frames: list[pd.DataFrame] = []
    for strategy, mask in masks.items():
        selected = frame[mask.fillna(False)].copy()
        if selected.empty:
            rows.append({'strategy': strategy, 'scenario': 'all', 'rows': 0})
            continue
        selected = selected.sort_values(['auto_total_stress', 'robust_ev', 'ev', 'model_probability', 'edge'], ascending=[True, False, False, False, False]).head(int(max_rows))
        temp = selected.copy()
        temp.insert(0, 'strategy', strategy)
        selected_frames.append(temp)
        for scenario in SCENARIOS:
            rows.append({'strategy': strategy, **simulate(selected, scenario, int(iterations), float(stake), seed=20260616 + len(rows))})
    if not survivor.empty:
        st.session_state['simulation_survivor_rows'] = survivor.drop(columns=['strategy'], errors='ignore').to_dict('records')
        st.session_state['ara_latest_predictions'] = survivor.drop(columns=['strategy'], errors='ignore').to_dict('records')
        st.session_state['ara_latest_predictions_source'] = 'Simulation Lab survivor'
        selected_frames.append(survivor)
        for scenario in SCENARIOS:
            rows.append({'strategy': 'Simulation optimized', **simulate(survivor, scenario, int(iterations), float(stake), seed=20260616 + len(rows))})
        st.success(t('saved'))
    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary['survival_grade'] = summary.apply(survival_grade, axis=1)
    recommendations = recommendation_table(summary)
    selected_all = pd.concat(selected_frames, ignore_index=True, sort=False) if selected_frames else pd.DataFrame()
    risks = risk_report(selected_all)
    scouts = game_scout_report(frame if use_swarm else selected_all)
    st.subheader(t('recommendation'))
    st.dataframe(recommendations, use_container_width=True, hide_index=True)
    st.subheader(t('scout_report'))
    st.dataframe(scouts, use_container_width=True, hide_index=True)
    st.subheader(t('summary'))
    st.dataframe(summary, use_container_width=True, hide_index=True)
    st.subheader(t('optimizer'))
    st.dataframe(optimizer_table, use_container_width=True, hide_index=True)
    st.subheader(t('risk_report'))
    st.dataframe(risks, use_container_width=True, hide_index=True)
    st.subheader(t('diagnostics'))
    st.dataframe(input_diagnostics(raw, frame), use_container_width=True, hide_index=True)
    st.subheader(t('details'))
    if not selected_all.empty:
        cols = [col for col in ['strategy', 'event', 'sport', 'market_type', 'prediction', 'model_probability', 'market_probability', 'decimal_price', 'edge', 'ev', 'robust_ev', 'robust_profit80', 'auto_total_stress', 'auto_weather_stress', 'auto_injury_stress', 'auto_altitude_stress', 'auto_travel_stress', 'auto_chaos_stress', 'line_movement_risk', 'data_quality_risk', 'negative_memory_risk', 'books', 'api_coverage', 'memory_signal'] if col in selected_all.columns]
        st.dataframe(selected_all[cols], use_container_width=True, hide_index=True)
    report_parts = [summary]
    if not recommendations.empty:
        rec = recommendations.copy(); rec.insert(0, 'report_section', 'recommendations'); report_parts.append(rec)
    if not scouts.empty:
        scout_export = scouts.copy(); scout_export.insert(0, 'report_section', 'game_scout_swarm'); report_parts.append(scout_export)
    if not optimizer_table.empty:
        opt = optimizer_table.copy(); opt.insert(0, 'report_section', 'optimizer_thresholds'); report_parts.append(opt)
    if not risks.empty:
        risk_export = risks.copy(); risk_export.insert(0, 'report_section', 'change_risk_report'); report_parts.append(risk_export)
    diagnostics = input_diagnostics(raw, frame)
    if not diagnostics.empty:
        diag = diagnostics.copy(); diag.insert(0, 'report_section', 'input_diagnostics'); report_parts.append(diag)
    report = pd.concat(report_parts, ignore_index=True, sort=False)
    st.download_button(t('download'), report.to_csv(index=False), file_name='simulation_lab_report.csv', mime='text/csv')
