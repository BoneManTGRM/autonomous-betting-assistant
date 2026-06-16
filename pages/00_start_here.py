from __future__ import annotations

import streamlit as st

st.set_page_config(page_title='Start Here', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='start_here_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'Start Here — Operating Guide',
        'caption': 'Use this page before running the system. It explains the correct workflow, what each page does, and what counts as official proof.',
        'warning': 'This is analytics and research software. It does not guarantee wins or returns and it does not execute transactions. Official proof only starts when a pick is locked before event start in Odds Lock Pro.',
        'workflow_title': 'Correct daily workflow',
        'settings_title': 'Recommended starting settings',
        'proof_title': 'What counts as official proof',
        'tracker_title': 'What old tracker CSVs are for',
        'client_title': 'Monthly-license workflow',
        'mistakes_title': 'Common mistakes to avoid',
    },
    'es': {
        'title': 'Inicio — Guía de Operación',
        'caption': 'Usa esta página antes de ejecutar el sistema. Explica el flujo correcto, qué hace cada página y qué cuenta como prueba oficial.',
        'warning': 'Esto es software de analítica e investigación. No garantiza wins ni retornos y no ejecuta transacciones. La prueba oficial solo empieza cuando un pick se bloquea antes del inicio en Odds Lock Pro.',
        'workflow_title': 'Flujo diario correcto',
        'settings_title': 'Configuración inicial recomendada',
        'proof_title': 'Qué cuenta como prueba oficial',
        'tracker_title': 'Para qué sirven los CSVs viejos de tracker',
        'client_title': 'Flujo para licencia mensual',
        'mistakes_title': 'Errores comunes que debes evitar',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


st.title(t('title'))
st.caption(t('caption'))
st.warning(t('warning'))

if LANG == 'en':
    workflow = [
        ['1', 'Deployment Health', 'Confirm API keys, page files, ledger status, and proof quality are usable before scanning.'],
        ['2', 'Scanner Pro', 'Optional first pass for market coverage and scanner strength.'],
        ['3', 'Pro Predictor', 'Run the model. Use the Highest-confidence output section so only the strongest rows are handed to Odds Lock Pro.'],
        ['4', 'What Are the Odds', 'Review value, line movement, scanner strength, CLV, segments, and add manual context if APIs are missing important information.'],
        ['5', 'Odds Lock Pro', 'Create official future-only proof rows before event start. Do not lock old or already-started rows.'],
        ['6', 'Public Proof Dashboard', 'Show locked record, ROI, pending picks, proof audit, report cards, and client-safe exports.'],
        ['7', 'Auto Result Grading', 'After games finish, update the proof ledger from result CSVs or explicit score fetch.'],
        ['8', 'Learning Memory', 'Train memory only after rows are graded with real results.'],
        ['9', 'Monthly License Readiness', 'Check whether the system is ready for private beta, operator licensing, or white-label use.'],
    ]
    settings = [
        ['Minimum model probability', '0.58 to 0.62 for high-confidence output'],
        ['Minimum edge', '0.04 to 0.06 starting range'],
        ['Strong edge threshold', '0.075 to 0.10'],
        ['Minimum scanner strength', '60+ for serious shortlists'],
        ['Minimum books', '3+ preferred when market coverage exists'],
        ['Max high-confidence rows', '10 to 25 per run'],
        ['Manual context adjustment', 'Keep inside -3 to +3 percentage points unless evidence is strong'],
    ]
    proof_rules = [
        ['Required', 'event, prediction, model_probability, decimal_price, bookmaker or odds_source, event_start_utc'],
        ['Created by', 'Odds Lock Pro'],
        ['Proof fields', 'proof_id, proof_hash, locked_at_utc'],
        ['Timing rule', 'locked_at_utc must be before event_start_utc'],
        ['After game', 'result_status, final_score, winner, closing_decimal_price if available'],
        ['Dashboard quality', 'Proof quality should be near 90/100+ before client pitches'],
    ]
    tracker_rules = [
        ['Historical tracker CSV', 'Useful for record review and learning, but not official proof'],
        ['Why not proof', 'Usually missing proof_id, locked_at_utc, odds, bookmaker, or model probability'],
        ['Where to use', 'Public Proof Dashboard historical tracker mode or Learning Memory after careful review'],
        ['Where not to use', 'Do not sell historical tracker rows as future-locked proof'],
    ]
    client_rules = [
        ['Private beta', '$500-$1,000/mo only after the workflow is clean and proof is honest'],
        ['Analyst license', '$1,000-$2,500/mo after 100+ future-locked rows with transparent ROI'],
        ['Operator license', '$2,500-$5,000/mo after stronger proof, clean exports, and support workflow'],
        ['White-label', 'Only after operator-ready proof and private deployment process exist'],
    ]
    mistakes = [
        'Do not upload an old results CSV to Odds Lock Pro and expect it to become official proof.',
        'Do not pitch hit rate without showing sample size, odds, ROI, and proof quality.',
        'Do not lock rows after events have started.',
        'Do not use large prediction lists directly for clients; use high-confidence shortlists.',
        'Do not apply manual probability boosts without writing the reason in manual notes.',
    ]
else:
    workflow = [
        ['1', 'Deployment Health', 'Confirma claves API, páginas, ledger y calidad de prueba antes de escanear.'],
        ['2', 'Scanner Pro', 'Primer paso opcional para cobertura del mercado y fuerza del escáner.'],
        ['3', 'Predictor Pro', 'Ejecuta el modelo. Usa Máxima Confianza para enviar solo las filas fuertes a Odds Lock Pro.'],
        ['4', 'What Are the Odds', 'Revisa valor, movimiento de línea, fuerza, CLV, segmentos y agrega contexto manual si faltan datos.'],
        ['5', 'Odds Lock Pro', 'Crea prueba oficial solo de eventos futuros antes del inicio. No bloquees filas viejas.'],
        ['6', 'Dashboard Público', 'Muestra récord bloqueado, ROI, pendientes, auditoría, tarjetas y exports para clientes.'],
        ['7', 'Auto Result Grading', 'Después de los juegos, actualiza el ledger con CSVs de resultados o fetch explícito.'],
        ['8', 'Learning Memory', 'Entrena memoria solo después de calificar resultados reales.'],
        ['9', 'Monthly License Readiness', 'Revisa si está listo para beta privada, operador o white-label.'],
    ]
    settings = [
        ['Probabilidad mínima', '0.58 a 0.62 para máxima confianza'],
        ['Ventaja mínima', '0.04 a 0.06 como inicio'],
        ['Ventaja fuerte', '0.075 a 0.10'],
        ['Fuerza mínima del escáner', '60+ para listas serias'],
        ['Mínimo de casas', '3+ preferido si existe cobertura'],
        ['Máximo de filas alta confianza', '10 a 25 por corrida'],
        ['Ajuste manual', 'Mantener entre -3 y +3 puntos salvo evidencia fuerte'],
    ]
    proof_rules = [
        ['Requerido', 'event, prediction, model_probability, decimal_price, bookmaker/odds_source, event_start_utc'],
        ['Creado por', 'Odds Lock Pro'],
        ['Campos de prueba', 'proof_id, proof_hash, locked_at_utc'],
        ['Regla de tiempo', 'locked_at_utc debe ser antes de event_start_utc'],
        ['Después del juego', 'result_status, final_score, winner, closing_decimal_price si está disponible'],
        ['Calidad', 'Proof quality cerca de 90/100+ antes de presentar clientes'],
    ]
    tracker_rules = [
        ['CSV histórico', 'Sirve para revisar récord y aprendizaje, pero no es prueba oficial'],
        ['Por qué no', 'Suele faltar proof_id, locked_at_utc, odds, bookmaker o probabilidad'],
        ['Dónde usarlo', 'Modo tracker histórico o Learning Memory con revisión'],
        ['Dónde no', 'No vender filas históricas como prueba futura bloqueada'],
    ]
    client_rules = [
        ['Beta privada', '$500-$1,000/mes con flujo limpio y prueba honesta'],
        ['Licencia analista', '$1,000-$2,500/mes después de 100+ filas futuras con ROI claro'],
        ['Licencia operador', '$2,500-$5,000/mes con más prueba, exports y soporte'],
        ['White-label', 'Solo con prueba de nivel operador y proceso de despliegue privado'],
    ]
    mistakes = [
        'No subas un CSV viejo de resultados a Odds Lock Pro esperando prueba oficial.',
        'No presentes hit rate sin tamaño de muestra, odds, ROI y proof quality.',
        'No bloquees filas después de que empiece el evento.',
        'No uses listas enormes para clientes; usa máxima confianza.',
        'No subas probabilidades manualmente sin escribir la razón en notas.',
    ]

st.subheader(t('workflow_title'))
st.dataframe(
    [{'step': row[0], 'page': row[1], 'what_to_do': row[2]} for row in workflow],
    use_container_width=True,
    hide_index=True,
)

st.subheader(t('settings_title'))
st.dataframe(
    [{'setting': row[0], 'recommended_start': row[1]} for row in settings],
    use_container_width=True,
    hide_index=True,
)

col1, col2 = st.columns(2)
with col1:
    st.subheader(t('proof_title'))
    st.dataframe(
        [{'item': row[0], 'rule': row[1]} for row in proof_rules],
        use_container_width=True,
        hide_index=True,
    )
with col2:
    st.subheader(t('tracker_title'))
    st.dataframe(
        [{'item': row[0], 'rule': row[1]} for row in tracker_rules],
        use_container_width=True,
        hide_index=True,
    )

st.subheader(t('client_title'))
st.dataframe(
    [{'tier': row[0], 'rule': row[1]} for row in client_rules],
    use_container_width=True,
    hide_index=True,
)

st.subheader(t('mistakes_title'))
for item in mistakes:
    st.write(f'- {item}')
