"""Prospective evidence workspace. Downloads only; no ledger reads or writes."""
from __future__ import annotations

import hashlib
import json

import streamlit as st

from autonomous_betting_agent.prospective_evidence import (
    prepare_packet, preparation_template, receipt_template, review_packet,
)
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Forward Test Tracker', layout='wide')
LANG = render_app_sidebar('forward_test_tracker', language_key='forward_test_language', selector='radio')
TEXT = {
    'en': {
        'title': 'Forward Test Tracker — Evidence Preparation',
        'limit': 'Preparation only. A download, local clock, source URL or hash does not prove that a prediction existed before the event or that a result is authentic. This page does not start an authenticated forward test.',
        'safe': 'No paid APIs, bets, training, model promotion, historical ledger loading or saved-weight changes. Inputs stay in this session; download your originals. This page does not establish server-side persistence.',
        'steps': '1. Declare the population, selection policy, exclusions and baseline before results. 2. Prepare and retain the original packet before events start. 3. Obtain a separately controlled pre-event timestamp and independently check result sources. 4. Review later receipts against that exact packet. Step 3 is not performed here.',
        'mode': 'Workflow', 'prepare': 'Prepare future predictions', 'review': 'Review packet and result receipts', 'legacy': 'Existing history',
        'schema': 'Use exact event/market/selection IDs from one event namespace, settlement rules, original raw and baseline probabilities, model versions, source availability times, and odds observed within five minutes. Never substitute confidence labels or implied odds for missing predictions. Fields and JSON keys remain in their machine-readable schema language.',
        'template': 'Download blank preparation JSON', 'input': 'Paste preparation JSON',
        'build': 'Prepare downloadable packet', 'need': 'Paste the requested JSON first.',
        'error': 'The supplied input could not be accepted. Check the exact schema, required evidence, identifiers and timestamp order. No records were changed.',
        'detail': 'Technical diagnostics (schema field names and machine messages)',
        'prepared': 'Packet prepared, not independently timestamped or authenticated. Retain the exact original file; changing input creates a different packet, not a correction to the original.',
        'download': 'Download original prepared packet', 'receipts_template': 'Download blank result-receipt JSON',
        'packet': 'Paste the complete original packet JSON', 'receipts': 'Paste result receipts JSON (use [] if no results are available)',
        'run': 'Review supplied evidence', 'reviewed': 'Structural review only. All rows remain unverified; no win rate, ROI or predictive improvement is certified.',
        'summary': 'Complete cohort coverage', 'cohort_rows': 'Prepared rows', 'unique_supplied_event_ids': 'Distinct supplied event IDs',
        'pending_rows': 'Without a result receipt', 'needs_review_rows': 'Rows needing reconciliation',
        'supplied_wins': 'Supplied wins', 'supplied_losses': 'Supplied losses', 'supplied_voids': 'Supplied voids',
        'unverified_rows': 'Unverified rows', 'authenticated_rows': 'Authenticated rows',
        'receipt_count': 'Supplied receipts', 'rejected_receipts': 'Rejected receipts',
        'duplicate_or_revised_receipts': 'Duplicate or revised receipts',
        'denominator': 'Pending, void and rejected rows stay in the original cohort. Multiple selections from one event are not independent evidence. Event IDs and source statements still require independent reconciliation.',
        'review_download': 'Download complete supplied-evidence review', 'raw': 'Original cohort and every receipt, including rejection reasons',
        'history': 'Historical records and existing weights are unchanged. The previous tracker reconstructed “official” labels from supplied timestamps; those labels are not authenticated forward proof and are no longer used for certification on this screen.',
        'history_link': 'Open Odds Lock to inspect existing history',
        'legacy_warning': 'Other legacy pages may still display older proof labels. This preparation workflow does not certify them. Do not repackage historical records as prospective evidence.',
    },
    'es': {
        'title': 'Seguimiento prospectivo — Preparación de evidencia',
        'limit': 'Solo preparación. Una descarga, reloj local, URL o huella digital no demuestra que una predicción existiera antes del evento ni que un resultado sea auténtico. Esta página no inicia una prueba prospectiva autenticada.',
        'safe': 'Sin APIs de pago, apuestas, entrenamiento, promoción de modelos, carga del historial ni cambios de pesos guardados. Los datos permanecen en esta sesión; descarga los originales. Esta página no comprueba la persistencia en el servidor.',
        'steps': '1. Declara la población, selección, exclusiones y referencia antes de los resultados. 2. Prepara y conserva el paquete original antes de los eventos. 3. Obtén una constancia de tiempo independiente previa al evento y comprueba las fuentes de resultados. 4. Revisa los comprobantes posteriores contra ese paquete exacto. Aquí no se realiza el paso 3.',
        'mode': 'Flujo de trabajo', 'prepare': 'Preparar predicciones futuras', 'review': 'Revisar paquete y comprobantes de resultados', 'legacy': 'Historial existente',
        'schema': 'Usa IDs exactos de evento, mercado y selección de un único sistema de identificación; reglas de liquidación; probabilidades originales y de referencia; versiones de modelo; fechas de disponibilidad de las fuentes y cuotas observadas en los últimos cinco minutos. Nunca sustituyas predicciones faltantes con etiquetas de confianza o probabilidades implícitas. Las claves JSON conservan el idioma técnico del esquema.',
        'template': 'Descargar JSON de preparación en blanco', 'input': 'Pegar JSON de preparación',
        'build': 'Preparar paquete descargable', 'need': 'Primero pega el JSON solicitado.',
        'error': 'No se aceptaron los datos proporcionados. Revisa el esquema exacto, la evidencia requerida, los identificadores y el orden de las fechas. No se cambió ningún registro.',
        'detail': 'Diagnóstico técnico (campos del esquema y mensajes del sistema)',
        'prepared': 'Paquete preparado, sin constancia de tiempo independiente ni autenticación. Conserva el archivo original exacto; cambiar los datos crea otro paquete, no una corrección del original.',
        'download': 'Descargar paquete original preparado', 'receipts_template': 'Descargar JSON de comprobantes en blanco',
        'packet': 'Pegar el JSON completo del paquete original', 'receipts': 'Pegar JSON de comprobantes (usa [] si aún no hay resultados)',
        'run': 'Revisar evidencia proporcionada', 'reviewed': 'Solo revisión estructural. Todas las filas siguen sin verificar; no se certifican la tasa de aciertos, el retorno ni mejoras predictivas.',
        'summary': 'Cobertura de la cohorte completa', 'cohort_rows': 'Filas preparadas', 'unique_supplied_event_ids': 'IDs de evento distintos proporcionados',
        'pending_rows': 'Sin comprobante de resultado', 'needs_review_rows': 'Filas por conciliar',
        'supplied_wins': 'Aciertos declarados', 'supplied_losses': 'Fallos declarados', 'supplied_voids': 'Anulaciones declaradas',
        'unverified_rows': 'Filas sin verificar', 'authenticated_rows': 'Filas autenticadas',
        'receipt_count': 'Comprobantes proporcionados', 'rejected_receipts': 'Comprobantes rechazados',
        'duplicate_or_revised_receipts': 'Comprobantes duplicados o revisados',
        'denominator': 'Las filas pendientes, anuladas o rechazadas permanecen en la cohorte original. Varias selecciones del mismo evento no son evidencia independiente. Los IDs y las afirmaciones de las fuentes aún requieren conciliación independiente.',
        'review_download': 'Descargar revisión completa de evidencia proporcionada', 'raw': 'Cohorte original y cada comprobante, incluidos motivos de rechazo',
        'history': 'El historial y los pesos existentes no cambiaron. El seguimiento anterior reconstruía etiquetas «oficiales» a partir de fechas proporcionadas; no son prueba prospectiva autenticada y esta pantalla ya no las usa para certificar resultados.',
        'history_link': 'Abrir Odds Lock para consultar el historial',
        'legacy_warning': 'Otras páginas anteriores aún pueden mostrar etiquetas antiguas de prueba. Este flujo de preparación no las certifica. No presentes registros históricos como evidencia prospectiva.',
    },
}
T = TEXT.get(LANG, TEXT['en'])
PREFIX = 'aba_prospective_v1'


def dump(value):
    return json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)


def error(exc):
    st.error(T['error'])
    with st.expander(T['detail']):
        st.json({'diagnostic': str(exc)})


def fingerprint(*values):
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode('utf-8')).hexdigest()


st.title(T['title'])
st.warning(T['limit'])
st.info(T['safe'])
st.write(T['steps'])
mode = st.radio(T['mode'], ['prepare', 'review', 'legacy'], format_func=lambda key: T[key], key=f'{PREFIX}_mode', horizontal=True)

if mode == 'prepare':
    st.caption(T['schema'])
    st.download_button(T['template'], dump(preparation_template()), 'prospective_preparation_blank.json', 'application/json')
    source = st.text_area(T['input'], height=300, key=f'{PREFIX}_source')
    current = fingerprint(source)
    if st.session_state.get(f'{PREFIX}_packet_input') != current:
        st.session_state.pop(f'{PREFIX}_packet', None)
    if st.button(T['build'], type='primary', key=f'{PREFIX}_prepare_button'):
        st.session_state.pop(f'{PREFIX}_packet', None)
        if not source.strip():
            st.warning(T['need'])
        else:
            try:
                packet = prepare_packet(source)
                st.session_state[f'{PREFIX}_packet'] = packet
                st.session_state[f'{PREFIX}_packet_input'] = current
            except (ValueError, TypeError, OverflowError, RecursionError) as exc:
                error(exc)
    packet = st.session_state.get(f'{PREFIX}_packet')
    if packet is not None:
        st.info(T['prepared'])
        st.caption(f"{packet['prepared_at']} · SHA256 {packet['packet_sha256']}")
        st.download_button(T['download'], dump(packet), f"prospective_{packet['packet_sha256'][:16]}.json", 'application/json')
        st.download_button(T['receipts_template'], dump(receipt_template(packet)), f"receipts_{packet['packet_sha256'][:16]}.json", 'application/json')
elif mode == 'review':
    packet_text = st.text_area(T['packet'], height=250, key=f'{PREFIX}_review_packet')
    receipts_text = st.text_area(T['receipts'], value='[]', height=250, key=f'{PREFIX}_review_receipts')
    current = fingerprint(packet_text, receipts_text)
    if st.session_state.get(f'{PREFIX}_review_input') != current:
        st.session_state.pop(f'{PREFIX}_review', None)
    if st.button(T['run'], type='primary', key=f'{PREFIX}_review_button'):
        st.session_state.pop(f'{PREFIX}_review', None)
        try:
            report = review_packet(packet_text, receipts_text)
            st.session_state[f'{PREFIX}_review'] = report
            st.session_state[f'{PREFIX}_review_input'] = current
        except (ValueError, TypeError, OverflowError, RecursionError) as exc:
            error(exc)
    report = st.session_state.get(f'{PREFIX}_review')
    if report is not None:
        st.warning(T['reviewed'])
        st.subheader(T['summary'])
        fields = ['cohort_rows', 'unique_supplied_event_ids', 'pending_rows', 'needs_review_rows', 'supplied_wins', 'supplied_losses', 'supplied_voids', 'unverified_rows', 'authenticated_rows', 'receipt_count', 'rejected_receipts', 'duplicate_or_revised_receipts']
        for start in range(0, len(fields), 3):
            for col, field in zip(st.columns(3), fields[start:start + 3]):
                col.metric(T[field], report[field])
        st.caption(T['denominator'])
        with st.expander(T['raw']):
            st.json(report)
        st.download_button(T['review_download'], dump(report), f"prospective_review_{report['packet_sha256'][:16]}.json", 'application/json')
else:
    st.info(T['history'])
    st.warning(T['legacy_warning'])
    st.page_link('pages/odds_lock_pro.py', label=T['history_link'])
