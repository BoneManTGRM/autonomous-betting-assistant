from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger, normalize_workspace_id
from autonomous_betting_agent.event_list_dedupe import collapse_to_event_rows, event_duplicate_summary
from autonomous_betting_agent.explanations import build_client_safe_pick_summary
from autonomous_betting_agent.grading_rules import summarize_event_level, summarize_row_level
from autonomous_betting_agent.ledger_types import classify_ledger_type, is_future_locked, public_metric_allowed
from autonomous_betting_agent.local_access import require_streamlit_access
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.storage import LocalStorage
from autonomous_betting_agent.ui_i18n import localize_dataframe, localize_value

st.set_page_config(page_title="Proof Center", layout="wide")
LANG = render_app_sidebar("proof_center", language_key="proof_center_language")
require_streamlit_access(st, allow_roles={"admin", "client", "demo"})

TEXT = {
    "en": {
        "title": "Proof Center",
        "caption": "Unified proof review, proof ID verification, row-level/event-level records, and local proof rows.",
        "warning": "Proof Center is for analytics and proof tracking only. It does not guarantee outcomes or returns.",
        "workspace": "Workspace",
        "source_counts": "Rows loaded: {total} total, {local} local, {ledger} ledger.",
        "local_rows": "Rows",
        "row_record": "Row record",
        "events": "Events",
        "event_record": "Event record",
        "tabs": ["Summary", "Proof ID Verification", "Proof Audit", "Row vs Event Record", "Local Proof Rows"],
        "public_summary": "Public proof summary",
        "no_rows": "No local or ledger proof rows found yet.",
        "public_safe_rows": "Public-safe rows",
        "research_review_rows": "Research/review rows",
        "legacy_dashboard": "Open legacy Public Proof Dashboard",
        "legacy_control": "Open legacy Proof Control Center",
        "proof_id": "Proof ID",
        "enter_proof_id": "Enter a proof ID to verify a local row.",
        "no_proof_id": "No local row found for that proof ID.",
        "ledger_type": "Ledger type",
        "forward_locked": "Forward locked",
        "public_safe": "Public-safe",
        "grade": "Grade",
        "yes": "Yes",
        "no": "No",
        "proof_audit": "Proof audit",
        "no_audit_rows": "No rows available for audit.",
        "row_vs_event": "Row-level vs event-level record",
        "row_summary": "Row-level summary",
        "event_summary": "Event-level summary",
        "event_caption": "Use event-level counts when multiple rows belong to the same matchup/game.",
        "local_proof_rows": "Proof rows",
        "event_level_rows": "Event-level proof rows",
        "row_level_rows": "Row-level market rows",
        "show_row_level": "Show row-level market rows",
        "duplicate_events": "Events with multiple rows",
        "duplicate_event_rows": "Extra row-level market rows",
        "download_rows": "Download proof rows",
    },
    "es": {
        "title": "Centro de Prueba",
        "caption": "Revisión unificada de prueba, verificación de ID, récord por fila/evento y filas locales.",
        "warning": "El Centro de Prueba es solo para analítica y seguimiento de prueba. No garantiza resultados ni ganancias.",
        "workspace": "Workspace",
        "source_counts": "Filas cargadas: {total} total, {local} locales, {ledger} ledger.",
        "local_rows": "Filas",
        "row_record": "Récord por fila",
        "events": "Eventos",
        "event_record": "Récord por evento",
        "tabs": ["Resumen", "Verificación de ID", "Auditoría de prueba", "Fila vs evento", "Filas locales"],
        "public_summary": "Resumen de prueba pública",
        "no_rows": "Todavía no hay filas locales ni de ledger.",
        "public_safe_rows": "Filas seguras para público",
        "research_review_rows": "Filas investigación/revisión",
        "legacy_dashboard": "Abrir Panel Público de Prueba anterior",
        "legacy_control": "Abrir Centro de Control de Prueba anterior",
        "proof_id": "ID de prueba",
        "enter_proof_id": "Ingresa un ID de prueba para verificar una fila local.",
        "no_proof_id": "No se encontró una fila local con ese ID de prueba.",
        "ledger_type": "Tipo de ledger",
        "forward_locked": "Bloqueada antes del inicio",
        "public_safe": "Segura para público",
        "grade": "Calificación",
        "yes": "Sí",
        "no": "No",
        "proof_audit": "Auditoría de prueba",
        "no_audit_rows": "No hay filas disponibles para auditoría.",
        "row_vs_event": "Récord por fila vs evento",
        "row_summary": "Resumen por fila",
        "event_summary": "Resumen por evento",
        "event_caption": "Usa conteos por evento cuando varias filas pertenecen al mismo partido/juego.",
        "local_proof_rows": "Filas de prueba",
        "event_level_rows": "Filas de prueba por evento",
        "row_level_rows": "Filas por mercado",
        "show_row_level": "Mostrar filas individuales por mercado",
        "duplicate_events": "Eventos con varias filas",
        "duplicate_event_rows": "Filas extra por mercado",
        "download_rows": "Descargar filas de prueba",
    },
}


def t(key: str):
    return TEXT.get(LANG, TEXT["en"]).get(key, TEXT["en"].get(key, key))


def to_records(value) -> list[dict]:
    frame = pd.DataFrame(value) if value is not None else pd.DataFrame()
    if frame.empty:
        return []
    return frame.fillna("").to_dict("records")


def merge_rows(*parts: list[dict]) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for part in parts:
        for row in part:
            proof_id = safe_text(row.get("proof_id"))
            event = safe_text(row.get("event") or row.get("event_name") or row.get("matchup"))
            pick = safe_text(row.get("prediction") or row.get("pick") or row.get("selection"))
            market = safe_text(row.get("market_type") or row.get("market"))
            line = safe_text(row.get("line_point") or row.get("line") or row.get("handicap") or row.get("total"))
            start = safe_text(row.get("event_start_utc") or row.get("event_start_time") or row.get("commence_time"))
            key = proof_id or "|".join([event.lower(), pick.lower(), market.lower(), line.lower(), start.lower()])
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            rows.append(dict(row))
    return rows


st.title(t("title"))
st.caption(t("caption"))
st.warning(t("warning"))

workspace_id = normalize_workspace_id(st.session_state.get("aba_test_window_id", "test_01"))
st.caption(f"{t('workspace')}: {workspace_id}")

store = LocalStorage()
local_rows = store.load_rows()
ledger_rows = to_records(load_persistent_ledger(workspace_id=workspace_id, active_only=False))
if not ledger_rows and workspace_id != "default":
    ledger_rows = to_records(load_persistent_ledger(active_only=False))
rows = merge_rows(local_rows, ledger_rows)
st.caption(t("source_counts").format(total=len(rows), local=len(local_rows), ledger=len(ledger_rows)))

row_summary = summarize_row_level(rows)
event_summary = summarize_event_level(rows)

col1, col2, col3, col4 = st.columns(4)
col1.metric(t("local_rows"), len(rows))
col2.metric(t("row_record"), f"{row_summary['wins']}-{row_summary['losses']}")
col3.metric(t("events"), event_summary.get("events", 0))
col4.metric(t("event_record"), f"{event_summary['wins']}-{event_summary['losses']}")

tabs = st.tabs(t("tabs"))

with tabs[0]:
    st.subheader(t("public_summary"))
    if not rows:
        st.info(t("no_rows"))
    else:
        public_rows = [row for row in rows if public_metric_allowed(row)]
        st.metric(t("public_safe_rows"), len(public_rows))
        st.metric(t("research_review_rows"), max(0, len(rows) - len(public_rows)))
        st.dataframe(localize_dataframe(pd.DataFrame([{"scope": "row_level", **row_summary}, {"scope": "event_level", **event_summary}]), LANG), use_container_width=True)
    st.page_link("pages/public_proof_dashboard.py", label=t("legacy_dashboard"))
    st.page_link("pages/proof_control_center.py", label=t("legacy_control"))

with tabs[1]:
    st.subheader(t("proof_id"))
    proof_id = st.text_input(t("proof_id"), "").strip()
    if not proof_id:
        st.info(t("enter_proof_id"))
    else:
        matches = [row for row in rows if str(row.get("proof_id") or "").strip() == proof_id]
        if not matches:
            st.error(t("no_proof_id"))
        else:
            row = matches[0]
            ledger_type = localize_value(classify_ledger_type(row), LANG)
            future_locked = is_future_locked(row)
            public_safe = public_metric_allowed(row)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(t("ledger_type"), ledger_type)
            c2.metric(t("forward_locked"), t("yes") if future_locked else t("no"))
            c3.metric(t("public_safe"), t("yes") if public_safe else t("no"))
            c4.metric(t("grade"), localize_value(str(row.get("grade") or row.get("result") or "pending"), LANG))
            st.write({
                t("proof_id"): row.get("proof_id"),
                "hash_prueba" if LANG == "es" else "proof_hash": row.get("proof_hash"),
                "bloqueado_utc" if LANG == "es" else "locked_at_utc": row.get("locked_at_utc"),
                "inicio_evento" if LANG == "es" else "event_start_time": row.get("event_start_time") or row.get("commence_time"),
                "evento" if LANG == "es" else "event_name": row.get("event_name") or row.get("event") or row.get("matchup"),
                "selección" if LANG == "es" else "prediction": row.get("prediction") or row.get("pick") or row.get("selection"),
                "mercado" if LANG == "es" else "market": row.get("market") or row.get("market_type"),
                "estado_auditoría_cuotas" if LANG == "es" else "odds_audit_status": row.get("odds_audit_status") or row.get("audit_status"),
            })
            st.info(build_client_safe_pick_summary(row))

with tabs[2]:
    st.subheader(t("proof_audit"))
    if not rows:
        st.info(t("no_audit_rows"))
    else:
        audit_rows = []
        for row in rows:
            audit_rows.append({
                "proof_id": row.get("proof_id", ""),
                "ledger_type": classify_ledger_type(row),
                "forward_locked": is_future_locked(row),
                "public_safe": public_metric_allowed(row),
                "has_proof_hash": bool(row.get("proof_hash")),
                "grade": row.get("grade") or row.get("result") or "pending",
                "event": row.get("event_name") or row.get("event") or row.get("matchup"),
            })
        st.dataframe(localize_dataframe(pd.DataFrame(audit_rows), LANG), use_container_width=True)

with tabs[3]:
    st.subheader(t("row_vs_event"))
    left, right = st.columns(2)
    with left:
        st.markdown(f"**{t('row_summary')}**")
        st.dataframe(localize_dataframe(pd.DataFrame([row_summary]), LANG), use_container_width=True)
    with right:
        st.markdown(f"**{t('event_summary')}**")
        st.dataframe(localize_dataframe(pd.DataFrame([event_summary]), LANG), use_container_width=True)
    st.caption(t("event_caption"))

with tabs[4]:
    st.subheader(t("local_proof_rows"))
    if rows:
        duplicate_summary = event_duplicate_summary(rows)
        c1, c2, c3 = st.columns(3)
        c1.metric(t("events"), duplicate_summary["unique_events"])
        c2.metric(t("duplicate_events"), duplicate_summary["duplicate_events"])
        c3.metric(t("duplicate_event_rows"), duplicate_summary["duplicate_event_rows"])
        show_row_level = st.checkbox(t("show_row_level"), value=False)
        display_rows = rows if show_row_level else collapse_to_event_rows(rows)
        label = t("row_level_rows") if show_row_level else t("event_level_rows")
        st.markdown(f"**{label}**")
        df = pd.DataFrame(display_rows)
        st.dataframe(localize_dataframe(df, LANG), use_container_width=True)
        st.download_button(t("download_rows"), df.to_csv(index=False).encode("utf-8"), file_name="local_proof_rows.csv", mime="text/csv")
    else:
        st.info(t("no_rows"))
