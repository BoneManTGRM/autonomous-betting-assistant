from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from autonomous_betting_agent.bankroll import suggest_stake
from autonomous_betting_agent.correlation import correlation_warnings
from autonomous_betting_agent.learning_memory_controls import reset_confirmation_matches, split_learning_safe_rows, version_placeholder_path
from autonomous_betting_agent.ledger_types import LEDGER_TYPES
from autonomous_betting_agent.license_status import load_license_records, make_license_record, upsert_license_record
from autonomous_betting_agent.local_access import require_streamlit_access
from autonomous_betting_agent.local_alerts import sqlite_fallback_alert
from autonomous_betting_agent.local_calibration import brier_score, calibration_buckets, odds_band_summary
from autonomous_betting_agent.local_storage_import import import_rows_to_local_storage, parse_uploaded_csv_bytes
from autonomous_betting_agent.sidebar_nav import render_app_sidebar, safe_csv_download
from autonomous_betting_agent.storage import LocalStorage
from autonomous_betting_agent.ui_i18n import localize_dataframe, localize_options, render_upload_css, tr, upload_helper

st.set_page_config(page_title="Local Control Center", layout="wide")
LANG = render_app_sidebar("local_control_center", language_key="local_control_center_language")
render_upload_css(st, LANG)
require_streamlit_access(st, allow_roles={"admin"})

st.title(tr(LANG, "Local Control Center", "Centro de Control Local"))
st.caption(tr(LANG, "Local storage, calibration, bankroll risk, license tracking, learning safety, and workflow guide.", "Almacenamiento local, calibracion, riesgo de bankroll, licencias, seguridad de aprendizaje y guia de flujo."))
st.warning(tr(LANG, "Analytics, proof tracking, reporting, and risk review only.", "Solo analitica, seguimiento de prueba, reportes y revision de riesgo."))

SAFETY_WARNING_EN = "Saving rows here only stores proof/research rows locally. It does not train the model, change live picks, or activate Reparodynamics repairs."
SAFETY_WARNING_ES = "Guardar filas aqui solo almacena filas de prueba/investigacion localmente. No entrena el modelo, no cambia picks en vivo ni activa reparaciones Reparodynamics."
PERSISTENCE_WARNING_EN = "Local storage may not persist across redeploys unless persistent storage is configured. Use exports for long-term proof backup."
PERSISTENCE_WARNING_ES = "El almacenamiento local puede no persistir entre redeploys si no hay almacenamiento persistente configurado. Usa exportaciones como respaldo de prueba a largo plazo."
LEDGER_OPTIONS = [ledger for ledger in ["research", "official", "quarantine", "learning_only", "client", "all_high_confidence"] if ledger in LEDGER_TYPES]

store = LocalStorage()
rows = store.load_rows()

if store.using_sqlite:
    st.success(tr(LANG, "Using local SQLite storage", "Usando almacenamiento SQLite local"))
else:
    st.warning(sqlite_fallback_alert(store.sqlite_error)["message"])

ledger_counts = {ledger: len(store.load_rows(ledger)) for ledger in sorted(LEDGER_TYPES)}

col1, col2, col3, col4 = st.columns(4)
col1.metric(tr(LANG, "Total local rows", "Filas locales totales"), len(rows))
col2.metric(tr(LANG, "Official rows", "Filas oficiales"), ledger_counts.get("official", 0))
col3.metric(tr(LANG, "Research rows", "Filas de investigacion"), ledger_counts.get("research", 0))
col4.metric(tr(LANG, "Quarantine rows", "Filas en cuarentena"), ledger_counts.get("quarantine", 0))

tabs = st.tabs([tr(LANG, "Storage/Admin", "Almacenamiento/Admin"), tr(LANG, "Calibration", "Calibracion"), tr(LANG, "Bankroll Risk", "Riesgo de bankroll"), tr(LANG, "License Tracking", "Licencias"), tr(LANG, "Learning Safety", "Seguridad de aprendizaje"), tr(LANG, "Workflow Guide", "Guia de flujo"), tr(LANG, "Alerts/Status", "Alertas/estado")])

with tabs[0]:
    st.subheader(tr(LANG, "Local storage/admin", "Almacenamiento/Admin local"))
    st.warning(tr(LANG, SAFETY_WARNING_EN, SAFETY_WARNING_ES))
    st.info(tr(LANG, PERSISTENCE_WARNING_EN, PERSISTENCE_WARNING_ES))

    st.subheader(tr(LANG, "Import rows into local storage", "Importar filas al almacenamiento local"))
    upload = st.file_uploader(tr(LANG, "Upload graded CSV to local storage", "Subir CSV calificado al almacenamiento local"), type=["csv"], key="local_storage_import_upload")
    ledger_type = st.selectbox(tr(LANG, "Ledger type", "Tipo de ledger"), LEDGER_OPTIONS, index=LEDGER_OPTIONS.index("research") if "research" in LEDGER_OPTIONS else 0)
    preview_only = st.checkbox(tr(LANG, "Preview only", "Solo vista previa"), value=True, key="local_storage_import_preview_only")
    confirmed = st.checkbox(tr(LANG, "I understand this saves rows locally only and does not train or mutate the model", "Entiendo que esto solo guarda filas localmente y no entrena ni muta el modelo"), value=False, key="local_storage_import_confirmed")
    dedupe = st.checkbox(tr(LANG, "Skip duplicate rows", "Omitir filas duplicadas"), value=True, key="local_storage_import_dedupe")

    parsed_rows = []
    preview_result = None
    if upload is not None:
        try:
            uploaded_bytes = upload.getvalue()
            parsed_rows = parse_uploaded_csv_bytes(uploaded_bytes)
            preview_result = import_rows_to_local_storage(
                parsed_rows,
                ledger_type=ledger_type,
                filename=upload.name,
                source="local_control_center_upload",
                preview_only=True,
                confirmed=False,
                dedupe=dedupe,
                storage=store,
            )
            c1, c2, c3 = st.columns(3)
            c1.metric(tr(LANG, "Rows seen", "Filas vistas"), preview_result["rows_seen"])
            c2.metric(tr(LANG, "Selected ledger", "Ledger seleccionado"), preview_result["ledger_type"])
            c3.metric(tr(LANG, "Possible duplicates", "Posibles duplicados"), preview_result["rows_skipped_duplicate"])
            if parsed_rows:
                st.dataframe(localize_dataframe(pd.DataFrame(parsed_rows).head(100), LANG), use_container_width=True)
        except Exception as exc:
            st.warning(f"{tr(LANG, 'Could not parse CSV', 'No se pudo leer el CSV')}: {exc}")
            parsed_rows = []

    if st.button(tr(LANG, "Import uploaded rows", "Importar filas subidas"), type="primary"):
        if upload is None:
            st.info(tr(LANG, "No file uploaded. Nothing was saved.", "No se subio archivo. No se guardo nada."))
        elif not preview_only and not confirmed:
            st.warning(tr(LANG, "Confirmation is required before saving rows locally.", "Se requiere confirmacion antes de guardar filas localmente."))
        else:
            result = import_rows_to_local_storage(
                parsed_rows,
                ledger_type=ledger_type,
                filename=upload.name,
                source="local_control_center_upload",
                preview_only=preview_only,
                confirmed=confirmed,
                dedupe=dedupe,
                storage=store,
            )
            if result["rows_imported"]:
                st.success(result["message"])
                st.rerun()
            else:
                st.info(result["message"])

    st.subheader(tr(LANG, "Local rows by ledger", "Filas locales por ledger"))
    st.dataframe(localize_dataframe(pd.DataFrame([{"ledger_type": key, "rows": value} for key, value in ledger_counts.items()]), LANG), use_container_width=True)
    if rows:
        visible = pd.DataFrame(rows)
        st.dataframe(localize_dataframe(visible, LANG), use_container_width=True)
        st.download_button(tr(LANG, "Download all local rows", "Descargar todas las filas locales"), visible.to_csv(index=False).encode("utf-8"), file_name="local_control_rows.csv", mime="text/csv")
    else:
        st.info(tr(LANG, "No local rows found yet.", "Todavia no hay filas locales."))

    audit = store.load_audit_log(limit=250)
    st.subheader(tr(LANG, "Proof backup", "Respaldo de prueba"))
    if rows:
        st.markdown(safe_csv_download(tr(LANG, "Backup all local rows", "Respaldar todas las filas locales"), pd.DataFrame(rows).to_csv(index=False), "local_control_rows_backup.csv"), unsafe_allow_html=True)
    if audit:
        st.markdown(safe_csv_download(tr(LANG, "Backup audit events", "Respaldar eventos de auditoria"), pd.DataFrame(audit).to_csv(index=False), "local_audit_events_backup.csv"), unsafe_allow_html=True)
    st.caption(tr(LANG, "Use backups before redeploys if persistent storage is not configured.", "Usa respaldos antes de redeploys si no hay almacenamiento persistente configurado."))

    st.subheader(tr(LANG, "Audit log", "Registro de auditoria"))
    if audit:
        st.dataframe(localize_dataframe(pd.DataFrame(audit), LANG), use_container_width=True)
    else:
        st.info(tr(LANG, "No local audit events found yet.", "Todavia no hay eventos locales de auditoria."))

with tabs[1]:
    st.subheader(tr(LANG, "Calibration", "Calibracion"))
    resolved = [row for row in rows if str(row.get("grade") or row.get("result") or "").strip().lower() in {"win", "won", "w", "loss", "lost", "l"}]
    score = brier_score(resolved)
    c1, c2, c3 = st.columns(3)
    c1.metric(tr(LANG, "Rows", "Filas"), len(rows))
    c2.metric(tr(LANG, "Resolved win/loss rows", "Filas resueltas ganadas/perdidas"), len(resolved))
    c3.metric(tr(LANG, "Brier score", "Puntaje Brier"), "N/A" if score is None else f"{score:.4f}")
    buckets = calibration_buckets(resolved)
    if buckets:
        bucket_df = pd.DataFrame(buckets)
        st.dataframe(localize_dataframe(bucket_df, LANG), use_container_width=True)
        st.bar_chart(bucket_df.set_index("bucket")[["expected_win_rate", "actual_win_rate"]])
    else:
        st.info(tr(LANG, "No graded rows with usable probabilities were found.", "No se encontraron filas calificadas con probabilidades utiles."))
    st.dataframe(localize_dataframe(pd.DataFrame(odds_band_summary(resolved)), LANG), use_container_width=True)

with tabs[2]:
    st.subheader(tr(LANG, "Bankroll risk", "Riesgo de bankroll"))
    bankroll = st.number_input(tr(LANG, "Bankroll units", "Unidades de bankroll"), min_value=1.0, value=100.0, step=10.0)
    mode_options, mode_map = localize_options(["flat", "conservative_kelly"], LANG)
    mode_label = st.selectbox(tr(LANG, "Stake mode", "Modo de stake"), mode_options)
    mode = mode_map.get(mode_label, mode_label)
    flat_units = st.number_input(tr(LANG, "Flat stake units", "Unidades de stake fijo"), min_value=0.1, value=1.0, step=0.1)
    max_daily = st.number_input(tr(LANG, "Max daily exposure %", "Exposicion diaria maxima %"), min_value=0.1, max_value=100.0, value=5.0, step=0.5) / 100.0
    max_sport = st.number_input(tr(LANG, "Max sport exposure %", "Exposicion maxima por deporte %"), min_value=0.1, max_value=100.0, value=5.0, step=0.5) / 100.0
    max_event = st.number_input(tr(LANG, "Max event exposure %", "Exposicion maxima por evento %"), min_value=0.1, max_value=100.0, value=2.0, step=0.5) / 100.0
    for warning in correlation_warnings(rows):
        st.warning(warning)
    review_rows = []
    for row in rows:
        suggestion = suggest_stake(row, bankroll=float(bankroll), mode=mode, flat_units=float(flat_units), max_daily_exposure_pct=float(max_daily), max_sport_exposure_pct=float(max_sport), max_event_exposure_pct=float(max_event))
        output = dict(row)
        output["suggested_stake_units"] = suggestion.stake
        output["stake_blocked"] = suggestion.blocked
        output["stake_reason"] = suggestion.reason
        review_rows.append(output)
    if review_rows:
        st.dataframe(localize_dataframe(pd.DataFrame(review_rows), LANG), use_container_width=True)
    else:
        st.info(tr(LANG, "No rows available for bankroll review.", "No hay filas disponibles para revisar bankroll."))
    st.caption(tr(LANG, "Cooldown and drawdown automation remain safe placeholders.", "Cooldown y drawdown siguen como marcadores seguros."))

with tabs[3]:
    st.subheader(tr(LANG, "Manual license tracking", "Seguimiento manual de licencias"))
    with st.form("local_control_license_form"):
        client_name = st.text_input(tr(LANG, "Client name", "Nombre del cliente"))
        status_options, status_map = localize_options(["trial", "active", "inactive", "expired"], LANG)
        client_status_label = st.selectbox(tr(LANG, "Client status", "Estado del cliente"), status_options)
        client_status = status_map.get(client_status_label, client_status_label)
        subscription_tier = st.text_input(tr(LANG, "Subscription tier", "Nivel de suscripcion"), "private_beta")
        manual_payment_status = st.text_input(tr(LANG, "Manual payment status", "Estado de pago manual"), "manual")
        renewal_date = st.text_input(tr(LANG, "Renewal date", "Fecha de renovacion"), "")
        notes = st.text_area(tr(LANG, "Notes", "Notas"), "")
        future_stripe_ready = st.checkbox(tr(LANG, "Future payment placeholder", "Marcador futuro de pago"), value=False)
        submitted = st.form_submit_button(tr(LANG, "Save local license record", "Guardar licencia local"))
    if submitted:
        if not client_name.strip():
            st.error(tr(LANG, "Client name is required.", "El nombre del cliente es obligatorio."))
        else:
            upsert_license_record(make_license_record(client_name, client_status, subscription_tier, manual_payment_status, renewal_date, notes, future_stripe_ready))
            st.success(tr(LANG, "Manual local license record saved.", "Licencia local guardada."))
    records = load_license_records()
    if records:
        df = pd.DataFrame([asdict(record) for record in records])
        st.dataframe(localize_dataframe(df, LANG), use_container_width=True)
        st.download_button(tr(LANG, "Download local license CSV", "Descargar CSV local de licencias"), df.to_csv(index=False).encode("utf-8"), file_name="local_license_status.csv", mime="text/csv")
    else:
        st.info(tr(LANG, "No local license records found yet.", "Todavia no hay licencias locales."))
    st.caption(tr(LANG, "Manual license tracking only. No payment processing.", "Solo seguimiento manual de licencias. No procesa pagos."))

with tabs[4]:
    st.subheader(tr(LANG, "Learning safety", "Seguridad de aprendizaje"))
    safe_rows, blocked_rows = split_learning_safe_rows(rows)
    c1, c2, c3 = st.columns(3)
    c1.metric(tr(LANG, "Total local rows", "Filas locales totales"), len(rows))
    c2.metric(tr(LANG, "Learning-safe rows", "Filas seguras para aprendizaje"), len(safe_rows))
    c3.metric(tr(LANG, "Blocked/review rows", "Filas bloqueadas/revision"), len(blocked_rows))
    if safe_rows:
        df = pd.DataFrame(safe_rows)
        st.dataframe(localize_dataframe(df, LANG), use_container_width=True)
        st.download_button(tr(LANG, "Download learning-safe CSV", "Descargar CSV seguro para aprendizaje"), df.to_csv(index=False).encode("utf-8"), file_name="learning_safe_rows.csv", mime="text/csv")
    st.caption(upload_helper(LANG))
    upload = st.file_uploader(tr(LANG, "Preview learning-safe CSV", "Vista previa de CSV seguro para aprendizaje"), type=["csv"])
    if upload is not None:
        try:
            st.dataframe(localize_dataframe(pd.read_csv(upload).head(100), LANG), use_container_width=True)
            st.caption(tr(LANG, "Preview only. This does not train or overwrite memory.", "Solo vista previa. Esto no entrena ni sobrescribe memoria."))
        except Exception as exc:
            st.warning(f"{tr(LANG, 'Could not preview CSV', 'No se pudo previsualizar el CSV')}: {exc}")
    version_label = st.text_input(tr(LANG, "Version label placeholder", "Marcador de version"), "manual")
    st.code(str(version_placeholder_path(version_label)))
    confirmation = st.text_input(tr(LANG, "Reset confirmation placeholder", "Marcador de confirmacion de reinicio"), "")
    if reset_confirmation_matches(confirmation):
        st.error(tr(LANG, "Reset confirmation entered. This page still does not delete memory automatically.", "Confirmacion ingresada. Esta pagina todavia no elimina memoria automaticamente."))
    if blocked_rows:
        with st.expander(tr(LANG, "Blocked/review rows", "Filas bloqueadas/revision")):
            st.dataframe(localize_dataframe(pd.DataFrame(blocked_rows), LANG), use_container_width=True)

with tabs[5]:
    st.subheader(tr(LANG, "Workflow guide", "Guia de flujo"))
    st.markdown(tr(LANG, """1. Run Pro Predictor Volume or upload rows.
2. Use Odds Lock Pro to create research or official locks.
3. Verify saved rows in Local Control Center.
4. Check individual proof IDs in Proof Center.
5. Export reports in Report Studio.
6. Review bankroll risk and correlation before client use.
7. Review calibration after grading.
8. Export learning-safe rows only after grading and price/probability checks.""", """1. Ejecuta Pro Predictor Volume o sube filas.
2. Usa Odds Lock Pro para crear bloqueos de investigacion u oficiales.
3. Verifica filas guardadas en Centro de Control Local.
4. Revisa IDs de prueba en Centro de Prueba.
5. Exporta reportes en Report Studio.
6. Revisa bankroll y correlacion antes de uso con clientes.
7. Revisa calibracion despues de calificar.
8. Exporta solo filas seguras para aprendizaje despues de revisar calificacion, precio y probabilidad."""))

with tabs[6]:
    st.subheader(tr(LANG, "Local alerts/status", "Alertas/estado local"))
    st.write({
        tr(LANG, "storage_mode", "modo_almacenamiento"): "sqlite" if store.using_sqlite else "csv_fallback",
        tr(LANG, "sqlite_error", "error_sqlite"): store.sqlite_error,
        tr(LANG, "local_rows", "filas_locales"): len(rows),
        tr(LANG, "audit_events", "eventos_auditoria"): len(store.load_audit_log(limit=250)),
        tr(LANG, "correlation_warnings", "alertas_correlacion"): len(correlation_warnings(rows)),
    })
