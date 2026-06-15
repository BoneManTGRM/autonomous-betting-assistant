from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.agent_decision_engine import agent_decision_summary, build_agent_decisions, lock_ready_candidates, playable_candidates
from autonomous_betting_agent.api_snapshot_memory import build_api_snapshots, snapshot_memory_summary
from autonomous_betting_agent.clv_intelligence import build_clv_intelligence, clv_by_segment, clv_summary
from autonomous_betting_agent.four_tool_orchestrator import page_health, page_health_frame
from autonomous_betting_agent.mobile_report import compact_report_frame
from autonomous_betting_agent.odds_breakdown import build_odds_breakdown
from autonomous_betting_agent.performance_segments import build_segment_frame, top_segments
from autonomous_betting_agent.post_loss_autopsy import autopsy_summary, build_loss_autopsies, future_rules
from autonomous_betting_agent.row_normalizer import normalize_frame
from autonomous_betting_agent.scanner_strength import score_scanner_frame, scanner_strength_summary
from autonomous_betting_agent.sport_specific_models import build_sport_specific_decisions, sport_model_summary
from autonomous_betting_agent.walk_forward_lab import walk_forward_summary, walk_forward_validate

st.set_page_config(page_title='What Are the Odds', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='what_are_the_odds_pro_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'What Are the Odds',
        'caption': 'The pro market/value command board. It combines Scanner Pro strength, Pro Predictor probabilities, agent decisions, CLV, loss review, walk-forward validation, and sport routing.',
        'info': 'Use this as the single market/value finder. Best Board is the main operating board before Odds Lock.',
        'workflow': 'Clean path: Scanner Pro → Pro Predictor → What Are the Odds → Odds Lock → Learning Memory.',
        'upload': 'Upload CSV file(s)',
        'paste': 'Or paste CSV text',
        'use_session': 'Use latest Scanner Pro / Pro Predictor session rows',
        'waiting': 'Upload CSVs, paste CSV text, or use latest session rows.',
        'min_edge': 'Minimum model-vs-market edge',
        'strong_edge': 'Strong edge threshold',
        'min_strength': 'Minimum scanner strength',
        'min_train_rows': 'Walk-forward minimum training rows',
        'source': 'Source',
        'rows': 'Rows',
        'playable': 'Playable',
        'lock_ready': 'Lock ready',
        'watch': 'Watch only',
        'review': 'Review needed',
        'avg_strength': 'Avg scan strength',
        'premium': 'Premium scans',
        'clv_ready': 'CLV ready',
        'next': 'Next',
        'handoff': 'Four-tool handoff health',
        'best_board': 'Best Board',
        'all_decisions': 'All decisions',
        'lock_candidates': 'Lock-ready',
        'scanner_rank': 'Scanner rank',
        'odds_breakdown': 'Odds breakdown',
        'segments': 'Segments',
        'clv': 'CLV',
        'loss_autopsy': 'Loss autopsy',
        'walk_lab': 'Walk-forward',
        'sport_models': 'Sport models',
        'exports': 'Exports',
        'no_best': 'No playable candidates after filters.',
        'session_saved': 'Rows saved in session for Odds Lock, Learning Memory, and Max Agent Intelligence review.',
    },
    'es': {
        'title': 'What Are the Odds',
        'caption': 'Tablero pro de mercado/valor. Combina fuerza de Scanner Pro, probabilidades de Predictor Pro, decisiones del agente, CLV, revisión de pérdidas, validación walk-forward y rutas por deporte.',
        'info': 'Usa esta como la única página para buscar mercado/valor. Best Board es el tablero principal antes de Odds Lock.',
        'workflow': 'Ruta limpia: Scanner Pro → Predictor Pro → What Are the Odds → Odds Lock → Memoria de Aprendizaje.',
        'upload': 'Subir archivo(s) CSV',
        'paste': 'O pegar texto CSV',
        'use_session': 'Usar filas recientes de Scanner Pro / Predictor Pro',
        'waiting': 'Sube CSVs, pega texto CSV o usa las filas recientes de la sesión.',
        'min_edge': 'Ventaja mínima modelo-vs-mercado',
        'strong_edge': 'Umbral de ventaja fuerte',
        'min_strength': 'Fuerza mínima del escáner',
        'min_train_rows': 'Mínimo de filas de entrenamiento walk-forward',
        'source': 'Fuente',
        'rows': 'Filas',
        'playable': 'Jugables',
        'lock_ready': 'Listas para bloquear',
        'watch': 'Solo vigilar',
        'review': 'Revisar',
        'avg_strength': 'Fuerza promedio',
        'premium': 'Escaneos premium',
        'clv_ready': 'CLV listo',
        'next': 'Siguiente',
        'handoff': 'Salud del traspaso entre herramientas',
        'best_board': 'Best Board',
        'all_decisions': 'Todas las decisiones',
        'lock_candidates': 'Listas para bloquear',
        'scanner_rank': 'Ranking del escáner',
        'odds_breakdown': 'Desglose de cuotas',
        'segments': 'Segmentos',
        'clv': 'CLV',
        'loss_autopsy': 'Autopsia de pérdidas',
        'walk_lab': 'Walk-forward',
        'sport_models': 'Modelos por deporte',
        'exports': 'Exportaciones',
        'no_best': 'No hay candidatos jugables después de los filtros.',
        'session_saved': 'Las filas se guardaron en sesión para Odds Lock, Memoria de Aprendizaje y Max Agent Intelligence.',
    },
}

PRIORITY_COLUMNS = [
    'event', 'sport', 'market_type', 'prediction', 'model_probability_clean', 'market_implied_probability',
    'model_market_edge', 'model_market_edge_percent', 'decimal_price', 'best_price', 'bookmaker',
    'agent_decision', 'agent_score', 'scanner_strength_score', 'scanner_strength_tier', 'scanner_recommendation',
    'recommended_stake_units', 'event_timing_status', 'lock_ready', 'line_value_signal', 'decision_reasons',
]


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def session_rows() -> tuple[str, list[dict]]:
    sources = [
        ('pro_predictor_latest_rows', 'Pro Predictor'),
        ('scanner_pro_latest_rows', 'Scanner Pro'),
        ('what_are_the_odds_latest_rows', 'What Are the Odds'),
        ('ara_latest_predictions', 'Latest session'),
    ]
    for key, label in sources:
        rows = st.session_state.get(key) or []
        if rows:
            return label, rows
    return '', []


def read_inputs() -> tuple[str, pd.DataFrame]:
    label, rows = session_rows()
    use_session = st.checkbox(t('use_session'), value=bool(rows))
    frames: list[pd.DataFrame] = []
    names: list[str] = []
    if use_session and rows:
        frames.append(pd.DataFrame(rows))
        names.append(label or 'session_rows')
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


def max_board(decisions: pd.DataFrame, min_strength: float) -> pd.DataFrame:
    if decisions.empty or 'agent_decision' not in decisions.columns:
        return pd.DataFrame()
    out = decisions[decisions['agent_decision'].astype(str).isin(['play_strong', 'play_small'])].copy()
    if 'scanner_strength_score' in out.columns:
        out = out[pd.to_numeric(out['scanner_strength_score'], errors='coerce').fillna(0) >= float(min_strength)]
    if out.empty:
        return out
    for col in ['lock_ready', 'agent_score', 'scanner_strength_score', 'model_market_edge', 'model_probability_clean']:
        if col not in out.columns:
            continue
        if col == 'lock_ready':
            out[col] = out[col].astype(bool)
        else:
            out[col] = pd.to_numeric(out[col], errors='coerce').fillna(0)
    sort_cols = [col for col in ['lock_ready', 'agent_score', 'scanner_strength_score', 'model_market_edge', 'model_probability_clean'] if col in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols, ascending=False)
    return compact_columns(out).head(75)


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
min_strength = st.slider(t('min_strength'), min_value=0.0, max_value=100.0, value=35.0, step=1.0)
min_train_rows = st.number_input(t('min_train_rows'), min_value=1, max_value=500, value=10, step=1)

normalized = normalize_frame(raw)
scored_input = score_scanner_frame(normalized)
decisions = build_agent_decisions(scored_input, min_edge=float(min_edge), strong_edge=float(strong_edge))
decisions = score_scanner_frame(decisions)
plays = playable_candidates(decisions, min_edge=float(min_edge), strong_edge=float(strong_edge))
lock_ready = lock_ready_candidates(decisions, min_edge=float(min_edge), strong_edge=float(strong_edge))
summary = agent_decision_summary(decisions, min_edge=float(min_edge), strong_edge=float(strong_edge))
strength = scanner_strength_summary(decisions)
health = page_health(decisions, page='what_are_the_odds')
best = max_board(decisions, min_strength=float(min_strength))
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
cols = st.columns(10)
cols[0].metric(t('rows'), len(normalized))
cols[1].metric(t('playable'), summary['play_strong'] + summary['play_small'])
cols[2].metric(t('lock_ready'), health['lock_ready_rows'])
cols[3].metric(t('watch'), summary['watch_only'])
cols[4].metric(t('review'), summary['review_needed'])
cols[5].metric(t('avg_strength'), 'N/A' if strength['avg_score'] is None else strength['avg_score'])
cols[6].metric(t('premium'), strength['premium_scan'])
cols[7].metric(t('clv_ready'), clv_stats['ready'])
cols[8].metric('WF rows', walk_stats['tested_rows'])
cols[9].metric(t('next'), health['next_action'])

st.subheader(t('handoff'))
st.dataframe(page_health_frame(decisions, page='what_are_the_odds'), use_container_width=True, hide_index=True)

tabs = st.tabs([t('best_board'), t('all_decisions'), t('lock_candidates'), t('scanner_rank'), t('odds_breakdown'), t('segments'), t('clv'), t('loss_autopsy'), t('walk_lab'), t('sport_models'), t('exports')])
with tabs[0]:
    if best.empty:
        st.info(t('no_best'))
    else:
        st.dataframe(best, use_container_width=True, hide_index=True)
with tabs[1]:
    st.dataframe(compact_columns(decisions).head(800), use_container_width=True, hide_index=True)
with tabs[2]:
    st.dataframe(compact_columns(lock_ready).head(400), use_container_width=True, hide_index=True)
with tabs[3]:
    scanner_cols = [col for col in ['event', 'sport', 'market_type', 'prediction', 'decimal_price', 'bookmaker', 'bookmaker_count', 'scanner_strength_score', 'scanner_strength_tier', 'scanner_recommendation', 'scanner_reasons'] if col in decisions.columns]
    st.dataframe(decisions[scanner_cols].head(400) if scanner_cols else decisions.head(400), use_container_width=True, hide_index=True)
with tabs[4]:
    st.dataframe(compact_report_frame(odds_main).head(500) if not odds_main.empty else odds_main, use_container_width=True, hide_index=True)
    if not odds_props.empty:
        st.subheader('Props / Scores' if LANG == 'en' else 'Props / Marcadores')
        st.dataframe(odds_props.head(300), use_container_width=True, hide_index=True)
with tabs[5]:
    st.subheader('Top segments' if LANG == 'en' else 'Mejores segmentos')
    st.dataframe(top, use_container_width=True, hide_index=True)
    st.subheader('All segments' if LANG == 'en' else 'Todos los segmentos')
    st.dataframe(segments, use_container_width=True, hide_index=True)
with tabs[6]:
    st.json(clv_stats)
    st.dataframe(clv.head(500), use_container_width=True, hide_index=True)
    st.subheader('CLV by sport' if LANG == 'en' else 'CLV por deporte')
    st.dataframe(clv_sport, use_container_width=True, hide_index=True)
with tabs[7]:
    st.json(loss_stats)
    st.dataframe(losses.head(300), use_container_width=True, hide_index=True)
    st.subheader('Future rules' if LANG == 'en' else 'Reglas futuras')
    st.dataframe(rules, use_container_width=True, hide_index=True)
with tabs[8]:
    st.json(walk_stats)
    st.dataframe(walk.head(500), use_container_width=True, hide_index=True)
with tabs[9]:
    st.dataframe(sport_stats, use_container_width=True, hide_index=True)
    st.dataframe(sport_decisions.head(500), use_container_width=True, hide_index=True)
with tabs[10]:
    st.download_button('Download all decisions' if LANG == 'en' else 'Descargar todas las decisiones', decisions.to_csv(index=False), file_name='what_are_the_odds_decisions.csv', mime='text/csv')
    st.download_button('Download best board' if LANG == 'en' else 'Descargar Best Board', best.to_csv(index=False), file_name='what_are_the_odds_best_board.csv', mime='text/csv')
    st.download_button('Download lock-ready' if LANG == 'en' else 'Descargar listas para bloquear', lock_ready.to_csv(index=False), file_name='what_are_the_odds_lock_ready.csv', mime='text/csv')
    st.download_button('Download scanner rank' if LANG == 'en' else 'Descargar ranking del escáner', decisions.to_csv(index=False), file_name='what_are_the_odds_scanner_rank.csv', mime='text/csv')
    st.download_button('Download CLV' if LANG == 'en' else 'Descargar CLV', clv.to_csv(index=False), file_name='what_are_the_odds_clv.csv', mime='text/csv')
    st.download_button('Download loss autopsy' if LANG == 'en' else 'Descargar autopsia de pérdidas', losses.to_csv(index=False), file_name='what_are_the_odds_loss_autopsy.csv', mime='text/csv')
    st.download_button('Download walk-forward' if LANG == 'en' else 'Descargar walk-forward', walk.to_csv(index=False), file_name='what_are_the_odds_walk_forward.csv', mime='text/csv')
    st.download_button('Download API snapshots' if LANG == 'en' else 'Descargar snapshots API', snapshots.to_csv(index=False), file_name='what_are_the_odds_api_snapshots.csv', mime='text/csv')
