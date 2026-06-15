from __future__ import annotations

from io import StringIO
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.agent_decision_engine import (
    agent_decision_summary,
    build_agent_decisions,
    lock_ready_candidates,
    playable_candidates,
)
from autonomous_betting_agent.api_snapshot_memory import build_api_snapshots, snapshot_memory_summary
from autonomous_betting_agent.clv_intelligence import build_clv_intelligence, clv_by_segment, clv_summary
from autonomous_betting_agent.mobile_report import compact_report_frame
from autonomous_betting_agent.odds_breakdown import build_odds_breakdown
from autonomous_betting_agent.performance_segments import build_segment_frame, top_segments
from autonomous_betting_agent.post_loss_autopsy import autopsy_summary, build_loss_autopsies, future_rules
from autonomous_betting_agent.row_normalizer import normalize_frame
from autonomous_betting_agent.sport_specific_models import build_sport_specific_decisions, sport_model_summary
from autonomous_betting_agent.walk_forward_lab import walk_forward_summary, walk_forward_validate

st.set_page_config(page_title='What Are the Odds', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='what_are_the_odds_pro_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'What Are the Odds',
        'caption': 'The pro market finder. It reads Scanner Pro, Pro Predictor, odds exports, props, results, CLV, segments, losses, and walk-forward validation in one place.',
        'info': 'Use this as the single market/value finder page. It replaces old market finder pages and keeps the stronger name.',
        'workflow': 'Clean path: Scanner Pro → Pro Predictor → What Are the Odds → Odds Lock → Learning Memory → Max Agent Intelligence.',
        'upload': 'Upload CSV file(s)',
        'paste': 'Or paste CSV text',
        'use_session': 'Use latest Scanner Pro / Pro Predictor session rows',
        'waiting': 'Upload CSVs, paste CSV text, or use latest Scanner Pro / Pro Predictor session rows.',
        'min_edge': 'Minimum model-vs-market edge',
        'strong_edge': 'Strong edge threshold',
        'min_train_rows': 'Walk-forward minimum training rows',
        'source': 'Source',
        'rows': 'Rows',
        'playable': 'Playable',
        'lock_ready': 'Lock ready',
        'watch': 'Watch only',
        'review': 'Review needed',
        'snapshots': 'Snapshots',
        'losses': 'Losses reviewed',
        'clv_ready': 'CLV ready',
        'beat_close': 'Beat-close rate',
        'walk_forward': 'Walk-forward rows',
        'all_decisions': 'All decisions',
        'best_board': 'Best board',
        'lock_candidates': 'Lock-ready',
        'odds_breakdown': 'Odds breakdown',
        'segments': 'Segments',
        'clv': 'CLV',
        'loss_autopsy': 'Loss autopsy',
        'walk_lab': 'Walk-forward',
        'sport_models': 'Sport models',
        'exports': 'Exports',
        'top_segments': 'Top segments',
        'all_segments': 'All segments',
        'props_scores': 'Props / Scores',
        'clv_by_sport': 'CLV by sport',
        'future_rules': 'Future rules',
        'download_decisions': 'Download all decisions',
        'download_best': 'Download best board',
        'download_lock_ready': 'Download lock-ready candidates',
        'download_breakdown': 'Download odds breakdown',
        'download_segments': 'Download segments',
        'download_clv': 'Download CLV intelligence',
        'download_losses': 'Download loss autopsies',
        'download_walk': 'Download walk-forward validation',
        'download_sports': 'Download sport-specific decisions',
        'download_snapshots': 'Download API snapshots',
        'no_best': 'No playable candidates after filters.',
        'session_saved': 'Rows saved in session for Odds Lock, Learning Memory, and Max Agent Intelligence review.',
    },
    'es': {
        'title': 'What Are the Odds',
        'caption': 'Buscador pro de mercados. Lee Scanner Pro, Pro Predictor, exportaciones de cuotas, props, resultados, CLV, segmentos, pérdidas y validación walk-forward en una sola página.',
        'info': 'Usa esta como la única página para buscar mercado/valor. Reemplaza las páginas antiguas de búsqueda de mercados y conserva el nombre más fuerte.',
        'workflow': 'Ruta limpia: Scanner Pro → Pro Predictor → What Are the Odds → Odds Lock → Memoria de Aprendizaje → Max Agent Intelligence.',
        'upload': 'Subir archivo(s) CSV',
        'paste': 'O pegar texto CSV',
        'use_session': 'Usar filas recientes de Scanner Pro / Pro Predictor',
        'waiting': 'Sube CSVs, pega texto CSV o usa las filas recientes de Scanner Pro / Pro Predictor.',
        'min_edge': 'Ventaja mínima modelo-vs-mercado',
        'strong_edge': 'Umbral de ventaja fuerte',
        'min_train_rows': 'Mínimo de filas de entrenamiento walk-forward',
        'source': 'Fuente',
        'rows': 'Filas',
        'playable': 'Jugables',
        'lock_ready': 'Listas para bloquear',
        'watch': 'Solo vigilar',
        'review': 'Revisar',
        'snapshots': 'Snapshots',
        'losses': 'Pérdidas revisadas',
        'clv_ready': 'CLV listo',
        'beat_close': 'Tasa de superar el cierre',
        'walk_forward': 'Filas walk-forward',
        'all_decisions': 'Todas las decisiones',
        'best_board': 'Mejor tablero',
        'lock_candidates': 'Listas para bloquear',
        'odds_breakdown': 'Desglose de cuotas',
        'segments': 'Segmentos',
        'clv': 'CLV',
        'loss_autopsy': 'Autopsia de pérdidas',
        'walk_lab': 'Walk-forward',
        'sport_models': 'Modelos por deporte',
        'exports': 'Exportaciones',
        'top_segments': 'Mejores segmentos',
        'all_segments': 'Todos los segmentos',
        'props_scores': 'Props / Marcadores',
        'clv_by_sport': 'CLV por deporte',
        'future_rules': 'Reglas futuras',
        'download_decisions': 'Descargar todas las decisiones',
        'download_best': 'Descargar mejor tablero',
        'download_lock_ready': 'Descargar candidatos listos para bloquear',
        'download_breakdown': 'Descargar desglose de cuotas',
        'download_segments': 'Descargar segmentos',
        'download_clv': 'Descargar inteligencia CLV',
        'download_losses': 'Descargar autopsias de pérdidas',
        'download_walk': 'Descargar validación walk-forward',
        'download_sports': 'Descargar decisiones por deporte',
        'download_snapshots': 'Descargar snapshots API',
        'no_best': 'No hay candidatos jugables después de los filtros.',
        'session_saved': 'Las filas se guardaron en la sesión para revisión en Odds Lock, Memoria de Aprendizaje y Max Agent Intelligence.',
    },
}

PRIORITY_COLUMNS = [
    'event', 'sport', 'market_type', 'prediction', 'model_probability_clean', 'market_implied_probability',
    'model_market_edge', 'model_market_edge_percent', 'decimal_price', 'best_price', 'bookmaker',
    'agent_decision', 'agent_score', 'recommended_stake_units', 'event_timing_status', 'lock_ready',
    'already_locked', 'line_value_signal', 'decision_reasons', 'decision_signals',
]


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def read_inputs() -> tuple[str, pd.DataFrame]:
    use_session = st.checkbox(t('use_session'), value=bool(st.session_state.get('scanner_pro_latest_rows') or st.session_state.get('ara_latest_predictions')))
    frames: list[pd.DataFrame] = []
    names: list[str] = []
    if use_session:
        session_rows = st.session_state.get('scanner_pro_latest_rows') or st.session_state.get('ara_latest_predictions') or []
        if session_rows:
            frames.append(pd.DataFrame(session_rows))
            names.append('session_rows')
    uploads = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=True)
    pasted = st.text_area(t('paste'), height=120)
    if uploads:
        for upload in uploads:
            try:
                frame = pd.read_csv(upload)
                frame['source_file'] = upload.name
                frames.append(frame)
                names.append(upload.name)
            except Exception as exc:
                st.warning(f'Could not read {upload.name}: {exc}')
    if pasted.strip():
        try:
            frame = pd.read_csv(StringIO(pasted.strip()))
            frame['source_file'] = 'pasted_csv'
            frames.append(frame)
            names.append('pasted_csv')
        except Exception as exc:
            st.warning(f'Could not read pasted CSV: {exc}')
    if not frames:
        return '', pd.DataFrame()
    return ', '.join(names), pd.concat(frames, ignore_index=True, sort=False)


def compact_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    columns = [column for column in PRIORITY_COLUMNS if column in frame.columns]
    return frame[columns] if columns else frame


def best_board(decisions: pd.DataFrame) -> pd.DataFrame:
    if decisions.empty or 'agent_decision' not in decisions.columns:
        return pd.DataFrame()
    out = decisions[decisions['agent_decision'].astype(str).isin(['play_strong', 'play_small'])].copy()
    if out.empty:
        return out
    sort_cols = [col for col in ['lock_ready', 'agent_score', 'model_market_edge'] if col in out.columns]
    ascending = [False if col == 'lock_ready' else False for col in sort_cols]
    if sort_cols:
        out = out.sort_values(sort_cols, ascending=ascending)
    return compact_columns(out).head(50)


st.title(t('title'))
st.caption(t('caption'))
st.info(t('info'))
st.caption(t('workflow'))
source, raw = read_inputs()
if raw.empty:
    st.warning(t('waiting'))
    st.stop()

min_edge = st.slider(t('min_edge'), min_value=0.0, max_value=0.20, value=0.035, step=0.005)
strong_edge = st.slider(t('strong_edge'), min_value=0.0, max_value=0.30, value=0.075, step=0.005)
min_train_rows = st.number_input(t('min_train_rows'), min_value=1, max_value=500, value=10, step=1)

normalized = normalize_frame(raw)
decisions = build_agent_decisions(normalized, min_edge=float(min_edge), strong_edge=float(strong_edge))
plays = playable_candidates(normalized, min_edge=float(min_edge), strong_edge=float(strong_edge))
lock_ready = lock_ready_candidates(normalized, min_edge=float(min_edge), strong_edge=float(strong_edge))
summary = agent_decision_summary(normalized, min_edge=float(min_edge), strong_edge=float(strong_edge))
best = best_board(decisions)
segments = build_segment_frame(normalized)
top = top_segments(normalized, min_resolved=1, limit=30)
clv = build_clv_intelligence(normalized)
clv_stats = clv_summary(normalized)
clv_sport = clv_by_segment(normalized, 'sport')
losses = build_loss_autopsies(normalized)
loss_stats = autopsy_summary(normalized)
rules = future_rules(normalized)
walk = walk_forward_validate(normalized, min_train_rows=int(min_train_rows))
walk_stats = walk_forward_summary(normalized, min_train_rows=int(min_train_rows))
sport_decisions = build_sport_specific_decisions(normalized)
sport_stats = sport_model_summary(normalized)
snapshots = build_api_snapshots(normalized)
snapshot_stats = snapshot_memory_summary(normalized)
try:
    odds_main, odds_props, odds_diag = build_odds_breakdown(raw)
except Exception:
    odds_main, odds_props, odds_diag = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

st.session_state['what_are_the_odds_latest_rows'] = decisions.to_dict('records')
st.session_state['ara_latest_predictions'] = decisions.to_dict('records')
st.session_state['ara_latest_predictions_source'] = 'What Are the Odds'
st.session_state['ara_latest_predictions_saved_at'] = pd.Timestamp.utcnow().isoformat()

st.success(t('session_saved'))
st.caption(f"{t('source')}: {source}")
cols = st.columns(9)
cols[0].metric(t('rows'), len(normalized))
cols[1].metric(t('playable'), summary['play_strong'] + summary['play_small'])
cols[2].metric(t('lock_ready'), len(lock_ready))
cols[3].metric(t('watch'), summary['watch_only'])
cols[4].metric(t('review'), summary['review_needed'])
cols[5].metric(t('snapshots'), snapshot_stats['rows'])
cols[6].metric(t('losses'), loss_stats['losses_reviewed'])
cols[7].metric(t('clv_ready'), clv_stats['ready'])
cols[8].metric(t('walk_forward'), walk_stats['tested_rows'])

bcols = st.columns(2)
bcols[0].metric(t('beat_close'), 'N/A' if clv_stats['beat_close_rate'] is None else f"{clv_stats['beat_close_rate']:.1%}")
bcols[1].metric('Brier WF', 'N/A' if walk_stats['avg_brier_walk_forward'] is None else walk_stats['avg_brier_walk_forward'])

tabs = st.tabs([
    t('best_board'),
    t('all_decisions'),
    t('lock_candidates'),
    t('odds_breakdown'),
    t('segments'),
    t('clv'),
    t('loss_autopsy'),
    t('walk_lab'),
    t('sport_models'),
    t('exports'),
])
with tabs[0]:
    if best.empty:
        st.info(t('no_best'))
    else:
        st.dataframe(best, use_container_width=True, hide_index=True)
with tabs[1]:
    st.dataframe(compact_columns(decisions).head(500), use_container_width=True, hide_index=True)
with tabs[2]:
    st.dataframe(compact_columns(lock_ready).head(300), use_container_width=True, hide_index=True)
with tabs[3]:
    st.dataframe(compact_report_frame(odds_main).head(500) if not odds_main.empty else odds_main, use_container_width=True, hide_index=True)
    if not odds_props.empty:
        st.subheader(t('props_scores'))
        st.dataframe(odds_props.head(300), use_container_width=True, hide_index=True)
with tabs[4]:
    st.subheader(t('top_segments'))
    st.dataframe(top, use_container_width=True, hide_index=True)
    st.subheader(t('all_segments'))
    st.dataframe(segments, use_container_width=True, hide_index=True)
with tabs[5]:
    st.json(clv_stats)
    st.dataframe(clv.head(500), use_container_width=True, hide_index=True)
    st.subheader(t('clv_by_sport'))
    st.dataframe(clv_sport, use_container_width=True, hide_index=True)
with tabs[6]:
    st.json(loss_stats)
    st.dataframe(losses.head(300), use_container_width=True, hide_index=True)
    st.subheader(t('future_rules'))
    st.dataframe(rules, use_container_width=True, hide_index=True)
with tabs[7]:
    st.json(walk_stats)
    st.dataframe(walk.head(500), use_container_width=True, hide_index=True)
with tabs[8]:
    st.dataframe(sport_stats, use_container_width=True, hide_index=True)
    st.dataframe(sport_decisions.head(500), use_container_width=True, hide_index=True)
with tabs[9]:
    st.download_button(t('download_decisions'), decisions.to_csv(index=False), file_name='what_are_the_odds_decisions.csv', mime='text/csv')
    st.download_button(t('download_best'), best.to_csv(index=False), file_name='what_are_the_odds_best_board.csv', mime='text/csv')
    st.download_button(t('download_lock_ready'), lock_ready.to_csv(index=False), file_name='what_are_the_odds_lock_ready.csv', mime='text/csv')
    st.download_button(t('download_breakdown'), odds_main.to_csv(index=False), file_name='what_are_the_odds_breakdown.csv', mime='text/csv')
    st.download_button(t('download_segments'), segments.to_csv(index=False), file_name='what_are_the_odds_segments.csv', mime='text/csv')
    st.download_button(t('download_clv'), clv.to_csv(index=False), file_name='what_are_the_odds_clv.csv', mime='text/csv')
    st.download_button(t('download_losses'), losses.to_csv(index=False), file_name='what_are_the_odds_loss_autopsy.csv', mime='text/csv')
    st.download_button(t('download_walk'), walk.to_csv(index=False), file_name='what_are_the_odds_walk_forward.csv', mime='text/csv')
    st.download_button(t('download_sports'), sport_decisions.to_csv(index=False), file_name='what_are_the_odds_sport_decisions.csv', mime='text/csv')
    st.download_button(t('download_snapshots'), snapshots.to_csv(index=False), file_name='what_are_the_odds_api_snapshots.csv', mime='text/csv')
