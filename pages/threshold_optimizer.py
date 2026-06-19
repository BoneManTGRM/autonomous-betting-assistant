from __future__ import annotations

from io import StringIO
from itertools import product
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Threshold Optimizer', layout='wide')
LANG = render_app_sidebar('threshold_optimizer', language_key='threshold_optimizer_language', selector='radio')

TEXT = {
    'en': {
        'title': 'Threshold Optimizer + Score Accuracy Lab',
        'caption': 'Paste a graded CSV or upload one. The optimizer runs automatically. No run button is needed.',
        'paste_title': 'Mobile-safe CSV paste',
        'paste': 'Paste graded CSV text here',
        'paste_help': 'Paste the whole CSV including the header row. This avoids the mobile upload button completely.',
        'upload_optional': 'Optional desktop upload fallback',
        'upload': 'Upload graded CSV / proof ledger',
        'no_file': 'Paste or upload a CSV with finished results first.',
        'not_enough': 'Need at least 25 resolved rows for useful optimization.',
        'summary': 'Resolved data summary',
        'score_optimizer': 'Score / winner optimizer',
        'patterns': 'Loss-pattern report',
        'groups': 'Group performance',
        'download': 'Download optimizer report',
        'notice': 'Use only rows created before the event when making performance claims. Backfilled results can help tuning, but they are not proof.',
        'running': 'CSV loaded. Results are below.',
    },
    'es': {
        'title': 'Optimizador de Umbrales + Laboratorio de Acierto por Marcador',
        'caption': 'Pega un CSV calificado o sube uno. El optimizador corre automáticamente. No se necesita botón.',
        'paste_title': 'Pegar CSV seguro para móvil',
        'paste': 'Pega texto CSV calificado aquí',
        'paste_help': 'Pega todo el CSV incluyendo encabezados. Esto evita completamente el botón móvil de subir archivo.',
        'upload_optional': 'Subida opcional para escritorio',
        'upload': 'Subir CSV calificado / ledger de prueba',
        'no_file': 'Pega o sube un CSV con resultados terminados primero.',
        'not_enough': 'Se necesitan al menos 25 filas resueltas para una optimización útil.',
        'summary': 'Resumen de datos resueltos',
        'score_optimizer': 'Optimizador marcador / ganador',
        'patterns': 'Reporte de patrones de pérdida',
        'groups': 'Rendimiento por grupo',
        'download': 'Descargar reporte del optimizador',
        'notice': 'Usa solo filas creadas antes del evento para declarar rendimiento. Los resultados agregados después sirven para ajustar, pero no son prueba.',
        'running': 'CSV cargado. Los resultados están abajo.',
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


def num_col(frame: pd.DataFrame, aliases: list[str], *, probability: bool = False, percent_like: bool = False) -> pd.Series:
    col = first_col(frame, aliases)
    if col is None:
        return pd.Series(float('nan'), index=frame.index, dtype=float)
    raw = frame[col].astype(str).str.strip()
    out = pd.to_numeric(raw.str.replace('%', '', regex=False).str.replace(',', '', regex=False), errors='coerce')
    percent_mask = raw.str.contains('%', regex=False, na=False)
    out.loc[percent_mask] = out.loc[percent_mask] / 100.0
    if probability:
        out = out.where(out <= 1.0, out / 100.0)
    elif percent_like and ('percent' in clean_name(col) or 'pct' in clean_name(col)):
        out = out.where(out.abs() <= 1.0, out / 100.0)
    return out


def compact_text(series: pd.Series) -> pd.Series:
    return series.fillna('').astype(str).str.lower().str.replace(r'[^a-z0-9áéíóúüñ]+', '', regex=True)


def outcome_from_text(result: pd.Series, pick: pd.Series, winner: pd.Series) -> pd.Series:
    outcome = pd.Series(pd.NA, index=result.index, dtype='Int64')
    compact = compact_text(result)
    outcome[compact.isin({'win', 'won', 'w', 'correct', 'hit', 'true', 'yes', '1', '10', 'ganada', 'gano', 'victoria', 'acierto'})] = 1
    outcome[compact.isin({'loss', 'lost', 'l', 'incorrect', 'miss', 'false', 'no', '0', '00', 'perdida', 'perdio', 'derrota', 'fallo'})] = 0
    outcome[outcome.isna() & compact.str.contains(r'win|won|correct|hit|ganad|victor|aciert', regex=True, na=False)] = 1
    outcome[outcome.isna() & compact.str.contains(r'loss|lost|incorrect|miss|perdid|derrot|fall', regex=True, na=False)] = 0
    pick_clean = compact_text(pick)
    winner_clean = compact_text(winner)
    outcome[outcome.isna() & winner_clean.ne('') & pick_clean.ne('') & winner_clean.eq(pick_clean)] = 1
    outcome[outcome.isna() & winner_clean.ne('') & pick_clean.ne('') & ~winner_clean.eq(pick_clean)] = 0
    return outcome


def normalize(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    out['event'] = text_col(frame, ['event', 'event_name', 'game', 'match', 'partido'])
    out['sport'] = text_col(frame, ['sport', 'sport_key', 'league', 'competition', 'deporte'])
    out['market_type'] = text_col(frame, ['market_type', 'market', 'bet_type', 'prop_type', 'tipo_mercado'], 'score').str.lower()
    out['prediction'] = text_col(frame, ['prediction', 'pick', 'selection', 'prediccion', 'pronostico'])
    out['volume_tier'] = text_col(frame, ['confidence_bucket', 'volume_tier', 'tier', 'ultra80_tier'], 'unknown')
    out['model_probability'] = num_col(frame, ['model_probability_clean', 'model_probability', 'final_probability_value', 'probability', 'probabilidad', 'prob_final'], probability=True)
    out['edge'] = num_col(frame, ['model_market_edge', 'edge_probability', 'model_edge', 'edge', 'edge_percent', 'edge_pct'], percent_like=True)
    out['books'] = num_col(frame, ['bookmaker_count', 'books', 'source_count', 'bookmakers']).fillna(0.0)
    out['api_coverage'] = num_col(frame, ['api_coverage_score', 'api_coverage'], probability=True).fillna(0.0)
    out['agent_score'] = num_col(frame, ['agent_score']).fillna(0.0)
    out['scanner_strength'] = num_col(frame, ['scanner_strength_score', 'signal_strength_score']).fillna(0.0)
    result = text_col(frame, ['result_status', 'result', 'outcome', 'win_loss', 'graded_result', 'status', 'resultado'])
    winner = text_col(frame, ['winner', 'actual_winner', 'ganador'])
    out['outcome'] = outcome_from_text(result, out['prediction'], winner)
    return out


def metrics(frame: pd.DataFrame) -> dict[str, Any]:
    resolved = frame[frame['outcome'].notna()].copy()
    if resolved.empty:
        return {'rows': 0, 'wins': 0, 'losses': 0, 'hit_rate': None, 'avg_prob': None, 'avg_edge': None}
    wins = int(resolved['outcome'].sum())
    rows = int(len(resolved))
    return {
        'rows': rows,
        'wins': wins,
        'losses': rows - wins,
        'hit_rate': round(wins / rows, 6),
        'avg_prob': None if resolved['model_probability'].dropna().empty else round(float(resolved['model_probability'].mean()), 6),
        'avg_edge': None if resolved['edge'].dropna().empty else round(float(resolved['edge'].mean()), 6),
    }


def score_mask(frame: pd.DataFrame, p: float, signal: float, agent: float, books: int, api: float, edge: float) -> pd.Series:
    return frame['model_probability'].fillna(0.0).ge(p) & frame['scanner_strength'].fillna(0.0).ge(signal) & frame['agent_score'].fillna(0.0).ge(agent) & frame['books'].fillna(0.0).ge(books) & frame['api_coverage'].fillna(0.0).ge(api) & frame['edge'].fillna(-1.0).ge(edge)


def optimize_score(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for p, signal, agent, books, api, edge in product([0.56, 0.58, 0.60, 0.62, 0.64, 0.66], [30, 35, 38, 40, 45, 50], [0, 35, 40, 45, 50, 60], [0, 1, 2, 4], [0.0, 0.33, 0.50], [-0.08, -0.03, -0.01, 0.0, 0.02]):
        selected = frame[score_mask(frame, p, signal, agent, books, api, edge)]
        m = metrics(selected)
        if m['rows'] < 10:
            continue
        hit = m['hit_rate'] or 0
        score = hit * 100 + min(m['rows'], 250) / 10
        if hit < 0.65:
            score -= 20
        rows.append({**m, 'score': round(score, 4), 'min_probability': p, 'min_signal_strength': signal, 'min_agent_score': agent, 'min_books': books, 'min_api_coverage': api, 'min_edge': edge})
    return pd.DataFrame(rows).sort_values(['score', 'hit_rate', 'rows'], ascending=False).head(50).reset_index(drop=True) if rows else pd.DataFrame()


def group_report(frame: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    usable = frame[frame['outcome'].notna()].copy()
    rows = []
    for keys, group in usable.groupby(cols, dropna=False):
        item = metrics(group)
        if item['rows'] < 3:
            continue
        if not isinstance(keys, tuple):
            keys = (keys,)
        rows.append({**{col: value for col, value in zip(cols, keys)}, **item})
    return pd.DataFrame(rows).sort_values(['hit_rate', 'rows'], ascending=False).reset_index(drop=True) if rows else pd.DataFrame()


def false_positive_report(frame: pd.DataFrame) -> pd.DataFrame:
    losses = frame[(frame['outcome'] == 0)].copy()
    if losses.empty:
        return pd.DataFrame()
    tests = {
        'probability_under_60': losses['model_probability'].lt(0.60),
        'books_below_4': losses['books'].lt(4),
        'api_below_50pct': losses['api_coverage'].lt(0.50),
        'agent_below_60': losses['agent_score'].lt(60),
        'signal_below_45': losses['scanner_strength'].lt(45),
        'negative_edge': losses['edge'].lt(0.0),
    }
    rows = []
    for reason, mask in tests.items():
        subset = losses[mask.fillna(False)]
        if not subset.empty:
            rows.append({'loss_pattern': reason, 'loss_rows': int(len(subset)), 'share_of_losses': round(len(subset) / len(losses), 6)})
    return pd.DataFrame(rows).sort_values('loss_rows', ascending=False).reset_index(drop=True) if rows else pd.DataFrame()


def load_pasted_csv() -> pd.DataFrame:
    pasted = str(st.session_state.get('threshold_pasted_csv') or '').strip()
    if not pasted:
        return pd.DataFrame()
    try:
        return pd.read_csv(StringIO(pasted))
    except Exception as exc:
        st.warning(f'Pasted CSV could not be read: {exc}')
        return pd.DataFrame()


def load_optional_upload() -> pd.DataFrame:
    with st.expander(t('upload_optional'), expanded=False):
        upload = st.file_uploader(t('upload'), type=['csv'])
        if upload is not None:
            try:
                return pd.read_csv(upload)
            except Exception as exc:
                st.warning(f'CSV could not be read: {exc}')
    return pd.DataFrame()


st.title(t('title'))
st.caption(t('caption'))
st.warning(t('notice'))
st.subheader(t('paste_title'))
st.text_area(t('paste'), key='threshold_pasted_csv', height=180, help=t('paste_help'), placeholder='event,prediction,result_status,model_probability\nTeam A at Team B,Team A,win,0.61')
raw = load_pasted_csv()
if raw.empty:
    raw = load_optional_upload()
if raw.empty:
    st.info(t('no_file'))
    st.stop()

st.success(t('running'))
data = normalize(raw)
resolved = data[data['outcome'].notna()].copy()
if len(resolved) < 25:
    st.warning(f"{t('not_enough')} Resolved rows: {len(resolved)}")
summary = pd.DataFrame([metrics(resolved)])
score_opt = optimize_score(resolved)
patterns = false_positive_report(resolved)
groups = group_report(resolved, ['sport', 'market_type'])
tabs = st.tabs([t('summary'), t('score_optimizer'), t('patterns'), t('groups')])
with tabs[0]:
    st.dataframe(summary, use_container_width=True, hide_index=True)
with tabs[1]:
    st.dataframe(score_opt, use_container_width=True, hide_index=True)
with tabs[2]:
    st.dataframe(patterns, use_container_width=True, hide_index=True)
with tabs[3]:
    st.dataframe(groups, use_container_width=True, hide_index=True)
merged = []
for name, frame in {'summary': summary, 'score_optimizer': score_opt, 'patterns': patterns, 'groups': groups}.items():
    if frame.empty:
        continue
    temp = frame.copy()
    temp.insert(0, 'report_section', name)
    merged.append(temp)
download = pd.concat(merged, ignore_index=True, sort=False) if merged else pd.DataFrame()
st.download_button(t('download'), download.to_csv(index=False), file_name='threshold_optimizer_report.csv', mime='text/csv')
