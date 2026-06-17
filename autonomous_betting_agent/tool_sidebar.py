from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from .commercial_platform_tools import load_persistent_ledger, proof_audit_summary

APP_NAME = 'ABA Signal Pro'
APP_TAGLINE = 'Powered by Reparodynamics'
PREDICTOR_TOOL_NAME = 'Pro Predictor'

WORKFLOW = [
    'Start Here',
    'Deployment Health',
    'Scanner Pro',
    PREDICTOR_TOOL_NAME,
    'Ultra 70 Profit Mode',
    'Simulation Lab',
    'What Are the Odds',
    'Odds Lock Pro',
    'Public Proof Dashboard',
    'Auto Result Grading',
    'Learning Memory',
    'Monthly License Readiness',
    'Buyer Demo Mode',
]

PAGE_GUIDES: dict[str, dict[str, dict[str, Any]]] = {
    'start_here': {
        'en': {'name': 'Start Here', 'purpose': 'Operating guide for the full system.', 'use_when': 'Open this first before testing, showing, or selling the app.', 'inputs': 'None.', 'outputs': 'Daily workflow, proof rules, settings, and common mistakes.', 'next': 'Deployment Health.', 'avoid': 'Do not skip proof rules when presenting the product.'},
        'es': {'name': 'Inicio', 'purpose': 'Guía de operación del sistema completo.', 'use_when': 'Ábrela primero antes de probar, mostrar o vender la app.', 'inputs': 'Ninguna.', 'outputs': 'Flujo diario, reglas de prueba, ajustes y errores comunes.', 'next': 'Deployment Health.', 'avoid': 'No ignores las reglas de prueba al presentar el producto.'},
    },
    'deployment_health': {
        'en': {'name': 'Deployment Health', 'purpose': 'Checks API keys, page files, ledger status, and proof quality.', 'use_when': 'Use before every serious run or client demo.', 'inputs': 'Streamlit secrets and current ledger.', 'outputs': 'Readiness score, action items, page status, API status.', 'next': 'Scanner Pro or Buyer Demo Mode.', 'avoid': 'Do not run live scans if the Odds API key is missing or placeholder.'},
        'es': {'name': 'Salud del Despliegue', 'purpose': 'Revisa APIs, páginas, ledger y calidad de prueba.', 'use_when': 'Úsala antes de cada corrida seria o demo.', 'inputs': 'Secretos de Streamlit y ledger actual.', 'outputs': 'Puntaje, acciones, estado de páginas y APIs.', 'next': 'Scanner Pro o Buyer Demo Mode.', 'avoid': 'No corras escaneos si falta la Odds API real.'},
    },
    'scanner_pro': {
        'en': {'name': 'Scanner Pro', 'purpose': 'Finds live markets and ranks market coverage/price quality.', 'use_when': 'Start here when you need fresh odds from APIs.', 'inputs': 'Odds API key, sport keys, markets, regions, max events.', 'outputs': 'Scanner-ranked live market rows saved to session.', 'next': 'Pro Predictor.', 'avoid': 'Do not treat scanner-only rows as official picks.'},
        'es': {'name': 'Scanner Pro', 'purpose': 'Encuentra mercados en vivo y califica cobertura/precio.', 'use_when': 'Empieza aquí cuando necesitas cuotas frescas de APIs.', 'inputs': 'Odds API, sport keys, mercados, regiones, eventos.', 'outputs': 'Filas de mercado guardadas en sesión.', 'next': 'Pro Predictor.', 'avoid': 'No trates filas de scanner como picks oficiales.'},
    },
    'pro_predictor': {
        'en': {'name': PREDICTOR_TOOL_NAME, 'purpose': 'Builds probabilities and highest-confidence prediction rows.', 'use_when': 'Use after scanning or when you want a filtered prediction board.', 'inputs': 'Live odds rows plus SportsDataIO/WeatherAPI context when available.', 'outputs': 'Full board and high-confidence handoff for Ultra 70 and Odds Lock Pro.', 'next': 'Ultra 70 Profit Mode, then Odds Lock Pro.', 'avoid': 'Do not send a huge unfiltered list directly to clients.'},
        'es': {'name': 'Pro Predictor', 'purpose': 'Crea probabilidades y filas de máxima confianza.', 'use_when': 'Úsalo después del scanner o para filtrar predicciones.', 'inputs': 'Cuotas en vivo y contexto SportsDataIO/WeatherAPI.', 'outputs': 'Tablero completo y handoff de máxima confianza para Ultra 70 y Odds Lock Pro.', 'next': 'Ultra 70 Profit Mode, luego Odds Lock Pro.', 'avoid': 'No envíes una lista enorme sin filtrar a clientes.'},
    },
    'ultra80_profit_mode': {
        'en': {'name': 'Ultra 70 Profit Mode', 'purpose': 'Builds adaptive 70%+ lock tiers while keeping strict 80% proof separate.', 'use_when': 'Use after Pro Predictor to separate B+ positive-value locks, B adaptive pattern locks, and C watch rows.', 'inputs': 'Latest Pro Predictor session rows or uploaded prediction CSV.', 'outputs': 'A strict 80 proof tier, B/B+ Ultra 70 adaptive lock tier, and C value-watch/review tier.', 'next': 'Simulation Lab for stress testing, then Odds Lock Pro.', 'avoid': 'Do not call Ultra 70 rows strict 80 proof; track the tiers separately.'},
        'es': {'name': 'Ultra 70 Profit Mode', 'purpose': 'Crea niveles adaptativos 70%+ y mantiene la prueba estricta 80% separada.', 'use_when': 'Úsalo después de Pro Predictor para separar B+ con valor, B adaptativo por patrón y C revisión.', 'inputs': 'Última sesión de Predictor o CSV de predicciones.', 'outputs': 'Nivel A prueba 80 estricta, nivel B/B+ Ultra 70 adaptativo y nivel C vigilancia/revisión.', 'next': 'Simulation Lab para estrés, luego Odds Lock Pro.', 'avoid': 'No llames filas Ultra 70 prueba estricta 80; rastrea los niveles separados.'},
    },
    'simulation_lab': {
        'en': {'name': 'Simulation Lab', 'purpose': 'Fast Monte Carlo stress test for Ultra 70 and Pro Predictor rows.', 'use_when': 'Use after Ultra 70 when you want to check downside, ROI stress, and confidence before locking.', 'inputs': 'Latest Ultra 70 / Pro Predictor session rows or uploaded prediction CSV.', 'outputs': 'Simulation summary, scout actions, risk report, diagnostics, and survivor rows saved for handoff.', 'next': 'Odds Lock Pro for future-only proof rows.', 'avoid': 'Do not use Simulation Lab as the only gate; treat it as a warning/stress-test tool.'},
        'es': {'name': 'Simulation Lab', 'purpose': 'Prueba rápida Monte Carlo para filas Ultra 70 y Pro Predictor.', 'use_when': 'Úsalo después de Ultra 70 para revisar downside, ROI bajo estrés y confianza antes de bloquear.', 'inputs': 'Filas de sesión Ultra 70 / Pro Predictor o CSV de predicciones.', 'outputs': 'Resumen de simulación, acciones scout, reporte de riesgo, diagnóstico y filas sobrevivientes guardadas.', 'next': 'Odds Lock Pro para prueba futura oficial.', 'avoid': 'No uses Simulation Lab como único filtro; úsalo como herramienta de advertencia/estrés.'},
    },
    'what_are_the_odds': {
        'en': {'name': 'What Are the Odds', 'purpose': 'Market/value command board with EV, odds quality, manual context, CLV, and decision scoring.', 'use_when': 'Use before locking to verify value and add missing expert context.', 'inputs': 'Predictor/scanner rows, optional manual context CSV.', 'outputs': 'Best Board, lock-ready rows, odds accuracy export.', 'next': 'Odds Lock Pro.', 'avoid': 'Do not apply manual probability changes without notes.'},
        'es': {'name': 'What Are the Odds', 'purpose': 'Tablero de valor con EV, calidad de cuotas, contexto manual, CLV y decisiones.', 'use_when': 'Úsalo antes de bloquear para verificar valor y contexto.', 'inputs': 'Filas del predictor/scanner y CSV manual opcional.', 'outputs': 'Best Board, filas listas para bloquear, export de cuotas.', 'next': 'Odds Lock Pro.', 'avoid': 'No hagas cambios manuales sin notas.'},
    },
    'odds_lock_pro': {
        'en': {'name': 'Odds Lock Pro', 'purpose': 'Creates official future-only proof rows.', 'use_when': 'Use only before events start.', 'inputs': 'Lock-ready rows with event, prediction, probability, odds, source, start time.', 'outputs': 'Proof ID, proof hash, locked timestamp, persistent proof ledger.', 'next': 'Public Proof Dashboard.', 'avoid': 'Do not use old result CSVs as official proof.'},
        'es': {'name': 'Odds Lock Pro', 'purpose': 'Crea prueba oficial solo para eventos futuros.', 'use_when': 'Úsalo solo antes de que empiecen los eventos.', 'inputs': 'Filas con evento, pick, probabilidad, cuota, fuente e inicio.', 'outputs': 'Proof ID, hash, timestamp y ledger persistente.', 'next': 'Dashboard Público.', 'avoid': 'No uses CSVs viejos como prueba oficial.'},
    },
    'public_proof_dashboard': {
        'en': {'name': 'Public Proof Dashboard', 'purpose': 'Client-safe proof, ROI, pending picks, audit, and report cards.', 'use_when': 'Use after locking or when reviewing proof quality.', 'inputs': 'Persistent proof ledger, locked session rows, result uploads.', 'outputs': 'Public table, metrics, proof audit, report card exports.', 'next': 'Auto Result Grading after games finish.', 'avoid': 'Do not mix historical tracker rows with official proof claims.'},
        'es': {'name': 'Dashboard Público', 'purpose': 'Prueba para clientes, ROI, pendientes, auditoría y reportes.', 'use_when': 'Úsalo después de bloquear o revisar calidad.', 'inputs': 'Ledger persistente, sesión bloqueada, resultados.', 'outputs': 'Tabla pública, métricas, auditoría y reportes.', 'next': 'Auto Result Grading después de juegos.', 'avoid': 'No mezcles tracker histórico con prueba oficial.'},
    },
    'auto_result_grading': {
        'en': {'name': 'Auto Result Grading', 'purpose': 'Updates locked proof rows after games finish.', 'use_when': 'Use only after final results are known.', 'inputs': 'Finished result CSV or explicit score fetch.', 'outputs': 'Updated ledger with win/loss/void and profit units.', 'next': 'Public Proof Dashboard, then Learning Memory.', 'avoid': 'Do not grade pending/live games as final.'},
        'es': {'name': 'Auto Result Grading', 'purpose': 'Actualiza filas bloqueadas cuando terminan juegos.', 'use_when': 'Úsalo solo con resultados finales.', 'inputs': 'CSV de resultados o fetch explícito.', 'outputs': 'Ledger con win/loss/void y unidades.', 'next': 'Dashboard Público, luego Learning Memory.', 'avoid': 'No califiques juegos pendientes/en vivo como finales.'},
    },
    'daily_workflow': {
        'en': {'name': 'Daily Workflow', 'purpose': 'One-click lock/report workflow for qualified rows.', 'use_when': 'Use after Ultra 70 or What Are the Odds when you want a guided daily process.', 'inputs': 'Current session rows or uploaded prediction CSV.', 'outputs': 'Locked rows, public proof table, daily report, report card.', 'next': 'Public Proof Dashboard.', 'avoid': 'Do not run this on result-only files.'},
        'es': {'name': 'Daily Workflow', 'purpose': 'Flujo de bloqueo/reporte de un clic.', 'use_when': 'Úsalo después de Ultra 70 o What Are the Odds para proceso guiado.', 'inputs': 'Filas de sesión o CSV de predicciones.', 'outputs': 'Filas bloqueadas, tabla pública, reporte y tarjeta.', 'next': 'Dashboard Público.', 'avoid': 'No lo corras con archivos solo de resultados.'},
    },
    'learning_memory': {
        'en': {'name': 'Learning Memory', 'purpose': 'Trains durable calibration and pattern memory from graded results.', 'use_when': 'Use only after results are graded.', 'inputs': 'Finished, graded rows with probability and result.', 'outputs': 'Calibration state, cumulative memory, ARA pattern memory.', 'next': 'Run future scans with the updated memory.', 'avoid': 'Do not train on ungraded pending rows.'},
        'es': {'name': 'Learning Memory', 'purpose': 'Entrena calibración y patrones duraderos.', 'use_when': 'Úsalo solo después de calificar resultados.', 'inputs': 'Filas finalizadas con probabilidad y resultado.', 'outputs': 'Calibración, memoria acumulada y patrones ARA.', 'next': 'Correr futuros escaneos con memoria actualizada.', 'avoid': 'No entrenes con filas pendientes.'},
    },
    'monthly_license_readiness': {
        'en': {'name': 'Monthly License Readiness', 'purpose': 'Scores readiness for beta, operator, and white-label licensing.', 'use_when': 'Use before pricing or pitching monthly clients.', 'inputs': 'Proof ledger or demo ledger.', 'outputs': 'Readiness checklist, pricing tiers, offer copy, next build queue.', 'next': 'Fix blockers, then pitch private beta.', 'avoid': 'Do not present demo rows as real proof.'},
        'es': {'name': 'Monthly License Readiness', 'purpose': 'Califica preparación para beta, operador y white-label.', 'use_when': 'Úsalo antes de cobrar o presentar clientes.', 'inputs': 'Ledger real o demo.', 'outputs': 'Checklist, precios, oferta y próximos pasos.', 'next': 'Corregir bloqueos y presentar beta.', 'avoid': 'No presentes demo como prueba real.'},
    },
    'buyer_demo_mode': {
        'en': {'name': 'Buyer Demo Mode', 'purpose': 'Shows a polished demo without API keys.', 'use_when': 'Use for walkthroughs only.', 'inputs': 'Built-in demo ledger.', 'outputs': 'Demo metrics, proof table, audit, report card.', 'next': 'Monthly License Readiness.', 'avoid': 'Do not claim demo rows are real performance.'},
        'es': {'name': 'Buyer Demo Mode', 'purpose': 'Muestra demo pulida sin APIs.', 'use_when': 'Úsalo solo para walkthroughs.', 'inputs': 'Ledger demo interno.', 'outputs': 'Métricas demo, tabla, auditoría y reporte.', 'next': 'Monthly License Readiness.', 'avoid': 'No digas que filas demo son rendimiento real.'},
    },
}


def _lang_key(language: str) -> str:
    return 'es' if str(language).lower().startswith('es') else 'en'


def _count_session_rows(key: str) -> int:
    rows = st.session_state.get(key) or []
    try:
        return int(len(rows))
    except TypeError:
        return 0


def session_state_summary() -> pd.DataFrame:
    rows = [
        {'stage': 'Scanner rows', 'session_key': 'scanner_pro_latest_rows', 'rows': _count_session_rows('scanner_pro_latest_rows')},
        {'stage': 'Pro Predictor handoff', 'session_key': 'pro_predictor_latest_rows', 'rows': _count_session_rows('pro_predictor_latest_rows')},
        {'stage': 'High-confidence rows', 'session_key': 'pro_predictor_high_confidence_rows', 'rows': _count_session_rows('pro_predictor_high_confidence_rows')},
        {'stage': 'Ultra 70 rows', 'session_key': 'ultra80_max_volume_rows', 'rows': _count_session_rows('ultra80_max_volume_rows')},
        {'stage': 'Simulation survivors', 'session_key': 'simulation_survivor_rows', 'rows': _count_session_rows('simulation_survivor_rows')},
        {'stage': 'Odds/value rows', 'session_key': 'what_are_the_odds_latest_rows', 'rows': _count_session_rows('what_are_the_odds_latest_rows')},
        {'stage': 'Locked proof rows', 'session_key': 'odds_lock_pro_locked_rows', 'rows': _count_session_rows('odds_lock_pro_locked_rows')},
    ]
    return pd.DataFrame(rows)


def proof_sidebar_snapshot() -> dict[str, Any]:
    ledger = load_persistent_ledger()
    audit = proof_audit_summary(ledger)
    resolved = 0
    wins = 0
    losses = 0
    if not ledger.empty and 'result_status' in ledger.columns:
        status = ledger['result_status'].fillna('').astype(str).str.lower()
        wins = int(status.eq('win').sum())
        losses = int(status.eq('loss').sum())
        resolved = wins + losses
    return {
        'locked_rows': int(len(ledger)),
        'resolved_rows': resolved,
        'record': f'{wins}-{losses}',
        'proof_quality': audit.get('proof_quality_score', 0),
        'needs_review': audit.get('needs_review', 0),
    }


def render_tool_sidebar(page_key: str, language: str = 'English') -> None:
    lang = _lang_key(language)
    guide = PAGE_GUIDES.get(page_key, PAGE_GUIDES['start_here']).get(lang, PAGE_GUIDES.get(page_key, PAGE_GUIDES['start_here'])['en'])
    labels = {
        'en': {
            'guide': 'Tool guide', 'workflow': 'Workflow position', 'purpose': 'Purpose', 'use_when': 'Use when',
            'inputs': 'Inputs', 'outputs': 'Outputs', 'next': 'Next step', 'avoid': 'Avoid', 'session': 'Session handoff',
            'proof': 'Proof snapshot', 'proof_rules': 'Proof rules',
            'official': 'Official proof requires future event, timestamp, odds, probability, source, proof ID, and proof hash.',
            'analytics': 'Analytics only. No guaranteed wins or returns.',
        },
        'es': {
            'guide': 'Guía de herramienta', 'workflow': 'Posición del flujo', 'purpose': 'Propósito', 'use_when': 'Úsala cuando',
            'inputs': 'Entradas', 'outputs': 'Salidas', 'next': 'Siguiente paso', 'avoid': 'Evitar', 'session': 'Handoff de sesión',
            'proof': 'Resumen de prueba', 'proof_rules': 'Reglas de prueba',
            'official': 'La prueba oficial requiere evento futuro, timestamp, cuota, probabilidad, fuente, proof ID y hash.',
            'analytics': 'Solo analítica. No garantiza wins ni retornos.',
        },
    }[lang]

    st.sidebar.markdown('### :green[ABA] Signal :red[Pro]')
    st.sidebar.caption(APP_TAGLINE)
    st.sidebar.divider()
    st.sidebar.subheader(labels['guide'])
    st.sidebar.markdown(f"**{guide['name']}**")
    st.sidebar.caption(f"{labels['purpose']}: {guide['purpose']}")
    with st.sidebar.expander(labels['workflow'], expanded=False):
        current = guide['name']
        for index, item in enumerate(WORKFLOW, start=1):
            marker = '➡️' if item == current or item.lower().replace(' ', '_') == page_key else '•'
            st.write(f'{marker} {index}. {item}')
    with st.sidebar.expander(labels['use_when'], expanded=False):
        st.write(guide['use_when'])
        st.write(f"**{labels['inputs']}:** {guide['inputs']}")
        st.write(f"**{labels['outputs']}:** {guide['outputs']}")
        st.write(f"**{labels['next']}:** {guide['next']}")
    with st.sidebar.expander(labels['avoid'], expanded=False):
        st.warning(guide['avoid'])
    with st.sidebar.expander(labels['session'], expanded=False):
        st.dataframe(session_state_summary(), use_container_width=True, hide_index=True)
    with st.sidebar.expander(labels['proof'], expanded=False):
        st.json(proof_sidebar_snapshot())
    with st.sidebar.expander(labels['proof_rules'], expanded=False):
        st.write(labels['official'])
        st.caption(labels['analytics'])
