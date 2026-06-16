from __future__ import annotations

from itertools import product
from typing import Any

import pandas as pd
import streamlit as st

st.set_page_config(page_title='Threshold Optimizer', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='threshold_optimizer_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'Threshold Optimizer + False Positive Report',
        'caption': 'Uses finished, graded picks to learn which thresholds are actually working. This is for improving accuracy/profit without guessing.',
        'upload': 'Upload graded CSV / proof ledger', 'run': 'Run optimizer', 'no_file': 'Upload a CSV with finished results first.', 'not_enough': 'Need at least 25 resolved rows for useful optimization.',
        'summary': 'Resolved data summary', 'optimizer': 'Best threshold candidates', 'false_positive': 'False positive report', 'sport_market': 'Sport/market performance', 'tier_perf': 'Tier performance', 'download': 'Download optimizer report',
        'proof_warning': 'Use only picks locked before the game when making performance claims. Backfilled results can help tuning, but they are not proof.',
    },
    'es': {
        'title': 'Optimizador de Umbrales + Reporte de Falsos Positivos',
        'caption': 'Usa picks terminados y calificados para aprender qué umbrales realmente funcionan. Sirve para mejorar precisión/ganancia sin adivinar.',
        'upload': 'Subir CSV calificado / ledger de prueba', 'run': 'Ejecutar optimizador', 'no_file': 'Primero sube un CSV con resultados terminados.', 'not_enough': 'Se necesitan al menos 25 filas resueltas para una optimización útil.',
        'summary': 'Resumen de datos resueltos', 'optimizer': 'Mejores candidatos de umbrales', 'false_positive': 'Reporte de falsos positivos', 'sport_market': 'Rendimiento por deporte/mercado', 'tier_perf': 'Rendimiento por nivel', 'download': 'Descargar reporte del optimizador',
        'proof_warning': 'Usa solo picks bloqueados antes del juego para declarar rendimiento. Los resultados agregados después sirven para ajustar, pero no son prueba.',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def clean_name(value: Any) -> str:
    return str(value or '').strip().lower().replace(' ', '_').replace('-', '_')


def first_col(frame: pd.DataFrame, aliases: list[str]) -> str | None:
    lookup = {clean_name(col): col for col in frame.columns}
    for alias in aliases:
        if clean_name(alias) in lookup:
            return lookup[clean_name(alias)]
    return None


def text_col(frame: pd.DataFrame, aliases: list[str], default: str = '') -> pd.Series:
    col = first_col(frame, aliases)
    if col is None:
        return pd.Series(default, index=frame.index, dtype=str)
    return frame[col].fillna(default).astype(str).str.strip()


def num_col(frame: pd.DataFrame, aliases: list[str]) -> pd.Series:
    col = first_col(frame, aliases)
    if col is None:
        return pd.Series(float('nan'), index=frame.index, dtype=float)
    out = pd.to_numeric(frame[col].astype(str).str.replace('%', '', regex=False).str.replace(',', '', regex=False), errors='coerce')
    if any('prob' in clean_name(alias) for alias in aliases):
        out = out.where(out <= 1.0, out / 100.0)
    return out


def normalize(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    out['event'] = text_col(frame, ['event', 'event_name', 'game', 'match', 'partido'])
    out['sport'] = text_col(frame, ['sport', 'sport_key', 'league', 'competition', 'deporte'])
    out['market_type'] = text_col(frame, ['market_type', 'market', 'bet_type', 'prop_type', 'tipo_mercado']).str.lower()
    out['prediction'] = text_col(frame, ['prediction', 'pick', 'selection', 'prediccion', 'pronostico'])
    out['volume_tier'] = text_col(frame, ['volume_tier', 'tier', 'ultra80_tier'], 'unknown')
    out['model_probability'] = num_col(frame, ['model_probability_clean', 'model_probability', 'final_probability_value', 'probability', 'probabilidad', 'prob_final'])
    out['decimal_price'] = num_col(frame, ['decimal_price', 'best_price', 'average_price', 'odds', 'price', 'cuota', 'mejor_cuota'])
    out['edge'] = num_col(frame, ['model_market_edge', 'edge_probability', 'model_edge', 'edge'])
    out['ev'] = num_col(frame, ['expected_value_per_unit', 'computed_ev_decimal', 'estimated_ev_decimal', 'estimated_ev', 'ev'])
    out['books'] = num_col(frame, ['bookmaker_count', 'books', 'source_count', 'bookmakers'])
    out['api_coverage'] = num_col(frame, ['api_coverage_score', 'api_coverage'])
    out['agent_score'] = num_col(frame, ['agent_score'])
    out['scanner_strength'] = num_col(frame, ['scanner_strength_score'])
    out['memory_signal'] = num_col(frame, ['pattern_ara_memory_signal', 'ara_memory_signal', 'memory_signal'])
    out['profit80'] = num_col(frame, ['ultra80_profit_at_80_percent', 'profit_at_80_percent'])
    result = text_col(frame, ['result_status', 'result', 'outcome', 'win_loss', 'graded_result', 'status', 'resultado']).str.lower()
    winner = text_col(frame, ['winner', 'actual_winner', 'ganador']).str.lower()
    pick = out['prediction'].str.lower()
    outcome = pd.Series(pd.NA, index=frame.index, dtype='Int64')
    win_words = {'win', 'won', 'w', 'correct', 'hit', 'true', 'yes', '1', '1.0', 'ganada', 'gano', 'victoria', 'acierto'}
    loss_words = {'loss', 'lost', 'l', 'incorrect', 'miss', 'false', 'no', '0', '0.0', 'perdida', 'perdio', 'derrota', 'fallo'}
    outcome[result.isin(win_words)] = 1
    outcome[result.isin(loss_words)] = 0
    outcome[outcome.isna() & winner.ne('') & pick.ne('') & winner.eq(pick)] = 1
    outcome[outcome.isna() & winner.ne('') & pick.ne('') & ~winner.eq(pick)] = 0
    out['outcome'] = outcome
    if out['ev'].isna().all():
        out['ev'] = out['model_probability'] * out['decimal_price'] - 1.0
    if out['edge'].isna().all():
        implied = 1.0 / out['decimal_price']
        out['edge'] = out['model_probability'] - implied
    if out['profit80'].isna().all():
        out['profit80'] = 0.80 * out['decimal_price'] - 1.0
    return out


def profit_units(prob_frame: pd.DataFrame, stake: float = 1.0) -> pd.Series:
    return prob_frame['outcome'].astype(float).where(prob_frame['outcome'].astype(float).eq(0), prob_frame['decimal_price'].astype(float) - 1.0) * stake


def metrics(frame: pd.DataFrame) -> dict[str, Any]:
    resolved = frame[frame['outcome'].notna()].copy()
    if resolved.empty:
        return {'rows': 0, 'wins': 0, 'losses': 0, 'hit_rate': None, 'profit_units': 0.0, 'roi': None, 'avg_odds': None, 'avg_prob': None}
    wins = int(resolved['outcome'].sum())
    rows = int(len(resolved))
    profits = profit_units(resolved)
    return {
        'rows': rows,
        'wins': wins,
        'losses': rows - wins,
        'hit_rate': round(wins / rows, 6),
        'profit_units': round(float(profits.sum()), 4),
        'roi': round(float(profits.sum()) / rows, 6),
        'avg_odds': round(float(resolved['decimal_price'].mean()), 4),
        'avg_prob': round(float(resolved['model_probability'].mean()), 6),
    }


def candidate_mask(frame: pd.DataFrame, p: float, edge: float, ev: float, books: int, api: float, agent: float, memory: float) -> pd.Series:
    return (
        frame['model_probability'].ge(p).fillna(False)
        & frame['edge'].ge(edge).fillna(False)
        & frame['ev'].ge(ev).fillna(False)
        & frame['books'].ge(books).fillna(False)
        & frame['api_coverage'].ge(api).fillna(False)
        & frame['agent_score'].ge(agent).fillna(False)
        & frame['memory_signal'].ge(memory).fillna(False)
    )


def optimize(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    p_grid = [0.70, 0.72, 0.74, 0.76, 0.78, 0.80, 0.82]
    edge_grid = [0.00, 0.02, 0.035, 0.05, 0.075]
    ev_grid = [-0.01, 0.00, 0.005, 0.015, 0.025]
    books_grid = [2, 3, 4, 5, 6, 8]
    api_grid = [0.0, 0.33, 0.50, 0.66, 1.0]
    agent_grid = [0, 50, 60, 70]
    memory_grid = [-0.05, -0.035, -0.02, -0.005, 0.0]
    for p, edge, ev, books, api, agent, memory in product(p_grid, edge_grid, ev_grid, books_grid, api_grid, agent_grid, memory_grid):
        selected = frame[candidate_mask(frame, p, edge, ev, books, api, agent, memory)]
        m = metrics(selected)
        if m['rows'] < 10:
            continue
        score = (m['hit_rate'] or 0) * 100 + (m['roi'] or -1) * 35 + min(m['rows'], 250) / 20
        if (m['roi'] or -1) <= 0:
            score -= 20
        if (m['hit_rate'] or 0) < 0.70:
            score -= 25
        rows.append({**m, 'score': round(score, 4), 'min_probability': p, 'min_edge': edge, 'min_ev': ev, 'min_books': books, 'min_api_coverage': api, 'min_agent_score': agent, 'min_memory_signal': memory})
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    return out.sort_values(['score', 'hit_rate', 'roi', 'rows'], ascending=False).head(50).reset_index(drop=True)


def group_report(frame: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    usable = frame[frame['outcome'].notna()].copy()
    if usable.empty:
        return pd.DataFrame()
    rows = []
    for keys, group in usable.groupby(cols, dropna=False):
        item = metrics(group)
        if item['rows'] < 3:
            continue
        if not isinstance(keys, tuple):
            keys = (keys,)
        rows.append({**{col: value for col, value in zip(cols, keys)}, **item})
    return pd.DataFrame(rows).sort_values(['hit_rate', 'roi', 'rows'], ascending=False).reset_index(drop=True) if rows else pd.DataFrame()


def false_positive_report(frame: pd.DataFrame) -> pd.DataFrame:
    losses = frame[(frame['outcome'] == 0)].copy()
    if losses.empty:
        return pd.DataFrame()
    tests = {
        'probability_80_plus': losses['model_probability'].ge(0.80),
        'probability_72_to_80': losses['model_probability'].between(0.72, 0.799999),
        'edge_below_3_5pct': losses['edge'].lt(0.035),
        'ev_below_0': losses['ev'].lt(0.0),
        'books_below_4': losses['books'].lt(4),
        'api_below_50pct': losses['api_coverage'].lt(0.50),
        'agent_below_60': losses['agent_score'].lt(60),
        'negative_memory': losses['memory_signal'].lt(0),
        'short_odds_under_1_27': losses['decimal_price'].lt(1.27),
        'longer_odds_over_1_75': losses['decimal_price'].gt(1.75),
    }
    rows = []
    for reason, mask in tests.items():
        subset = losses[mask.fillna(False)]
        if subset.empty:
            continue
        rows.append({'loss_pattern': reason, 'loss_rows': int(len(subset)), 'share_of_losses': round(len(subset) / len(losses), 6), 'avg_probability': round(float(subset['model_probability'].mean()), 6), 'avg_edge': round(float(subset['edge'].mean()), 6), 'avg_ev': round(float(subset['ev'].mean()), 6)})
    return pd.DataFrame(rows).sort_values('loss_rows', ascending=False).reset_index(drop=True)


st.title(t('title'))
st.caption(t('caption'))
st.warning(t('proof_warning'))
upload = st.file_uploader(t('upload'), type=['csv'])
if st.button(t('run'), type='primary', use_container_width=True):
    if upload is None:
        st.info(t('no_file'))
        st.stop()
    raw = pd.read_csv(upload)
    data = normalize(raw)
    resolved = data[data['outcome'].notna()].copy()
    if len(resolved) < 25:
        st.warning(f"{t('not_enough')} Resolved rows: {len(resolved)}")
    summary = pd.DataFrame([metrics(resolved)])
    opt = optimize(resolved)
    false_pos = false_positive_report(resolved)
    sport_market = group_report(resolved, ['sport', 'market_type'])
    tier_perf = group_report(resolved, ['volume_tier'])
    tabs = st.tabs([t('summary'), t('optimizer'), t('false_positive'), t('sport_market'), t('tier_perf')])
    with tabs[0]:
        st.dataframe(summary, use_container_width=True, hide_index=True)
    with tabs[1]:
        st.dataframe(opt, use_container_width=True, hide_index=True)
    with tabs[2]:
        st.dataframe(false_pos, use_container_width=True, hide_index=True)
    with tabs[3]:
        st.dataframe(sport_market, use_container_width=True, hide_index=True)
    with tabs[4]:
        st.dataframe(tier_perf, use_container_width=True, hide_index=True)
    report = {
        'summary': summary,
        'optimizer': opt,
        'false_positive': false_pos,
        'sport_market': sport_market,
        'tier_perf': tier_perf,
    }
    merged = []
    for name, frame in report.items():
        if frame.empty:
            continue
        temp = frame.copy()
        temp.insert(0, 'report_section', name)
        merged.append(temp)
    download = pd.concat(merged, ignore_index=True, sort=False) if merged else pd.DataFrame()
    st.download_button(t('download'), download.to_csv(index=False), file_name='threshold_optimizer_report.csv', mime='text/csv')
