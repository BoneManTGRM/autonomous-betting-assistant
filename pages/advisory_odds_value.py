from __future__ import annotations

import base64
import html
from typing import Any, Mapping

import pandas as pd
import streamlit as st

import autonomous_betting_agent.advisory_i18n_phase3e5  # noqa: F401
import autonomous_betting_agent.ui_i18n_phase3e  # noqa: F401
from autonomous_betting_agent.advisory_candidate_review import (
    apply_manual_candidate_selection,
    candidate_review_blocker_summary,
    candidate_review_report_section,
    candidate_review_rows,
    candidate_review_summary,
)
from autonomous_betting_agent.advisory_clv_tracking import (
    apply_manual_clv_fields,
    manual_clv_group_summary,
    manual_clv_report_section,
    manual_clv_summary,
)
from autonomous_betting_agent.advisory_explanation_engine import (
    advisory_explanation_reason_counts,
    advisory_explanation_report_section,
    advisory_explanation_summary,
    explain_advisory_rows,
)
from autonomous_betting_agent.advisory_odds_value_display import (
    ADVISORY_WARNING,
    SAFETY_CONFIRMATION,
    advisory_csv_frame,
    advisory_frame,
    advisory_real_file_diagnostics,
    advisory_report_text,
    advisory_summary_counts,
    blocked_reason_summary,
    duplicate_conflict_summary,
    fresh_slate_readiness_check,
    line_shopping_summary,
    market_completeness_summary,
    playable_table,
    prediction_only_table,
    sportsbook_hold_summary,
    sportsbook_source_summary,
    stale_line_summary,
    validate_advisory_rows,
    watchlist_table,
)
from autonomous_betting_agent.advisory_threshold_calibration import (
    PLAYABLE_PLUS_EV,
    PREDICTION_ONLY_NOT_PLUS_EV,
    WATCHLIST_VALUE,
    advisory_threshold_presets,
    apply_advisory_thresholds,
    calibrated_blocked_reason_summary,
    calibrated_status_table,
    normalize_threshold_config,
    threshold_calibration_summary,
    threshold_impact_summary,
    threshold_report_text,
)
from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.pick_hold_store import load_first_available
from autonomous_betting_agent.row_normalizer import normalize_frame
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe

st.set_page_config(page_title="Advisory Odds Value", layout="wide")
LANG = render_app_sidebar("advisory_odds_value", language_key="advisory_odds_value_language", selector="radio")

TEXT = {
    "en": {
        "title": "Advisory Odds Value",
        "caption": "Phase 3E.6.1 proof-safe advisory odds readiness, explanations, local candidate review, and manual CLV tracking.",
        "input": "Input",
        "test_window": "Test Window ID",
        "use_session": "Use latest saved/session rows",
        "upload": "Upload prediction CSV",
        "source": "Input source",
        "none": "none",
        "no_rows": "No rows found. Upload a CSV or run Pro Predictor/Odds Lock Pro first.",
        "safety": "Advisory safety banner",
        "readiness": "Fresh Slate Readiness",
        "readiness_details": "Fresh slate readiness details",
        "source_summary": "Sportsbook Source Summary",
        "market_summary": "Market Completeness Summary",
        "thresholds": "Advisory Threshold Calibration",
        "threshold_summary": "Threshold Calibration Summary",
        "calibrated_playable": "Calibrated playable +EV rows",
        "calibrated_watchlist": "Calibrated watchlist rows",
        "calibrated_prediction_only": "Calibrated prediction-only rows",
        "calibrated_blocked": "Calibrated blocked / failed-threshold rows",
        "explanations": "Advisory Explanation Engine",
        "explanation_summary": "Explanation Summary",
        "reason_counts": "Reason Code Counts",
        "row_explanations": "Row-Level Explanations",
        "candidate_review": "Manual Advisory Candidate Review Gate",
        "candidate_summary": "Candidate Review Summary",
        "candidate_blockers": "Candidate Review Blockers",
        "eligible_candidates": "Eligible Local Review Candidates",
        "selected_candidates": "Selected Manual Candidates",
        "blocked_candidates": "Blocked Candidate Rows",
        "watchlist_candidates": "Watchlist-Only Rows",
        "prediction_only_candidates": "Prediction-Only Rows",
        "clv_tracking": "Manual CLV Tracking",
        "clv_summary": "Manual CLV Summary",
        "clv_by_book": "CLV by Sportsbook",
        "clv_by_market": "CLV by Market",
        "clv_by_explanation": "CLV by Explanation Status",
        "clv_rows": "Row-Level Manual CLV",
        "diagnostics": "Why no playable +EV rows?",
        "summary": "Advisory summary",
        "playable": "Original playable +EV advisory picks",
        "watchlist": "Original watchlist value picks",
        "prediction_only": "Original prediction-only rows",
        "prediction_only_note": "These may be good predictions, but the current price does not show playable positive EV.",
        "blocked": "Original blocked rows by reason",
        "hold": "Sportsbook hold table",
        "line_shopping": "Best-price line-shopping table",
        "stale": "Stale-line warnings",
        "conflicts": "Duplicate/conflict warnings",
        "validation": "Real-file validation",
        "download": "Download advisory CSV",
        "report": "Copy/paste advisory report",
    },
    "es": {
        "title": "Valor de Odds Asesoría",
        "caption": "Fase 3E.6.1 preparación, explicaciones, revisión local de candidatos y CLV manual sin tocar prueba.",
        "input": "Entrada",
        "test_window": "ID de ventana de prueba",
        "use_session": "Usar ultimas filas guardadas/sesion",
        "upload": "Subir CSV de predicciones",
        "source": "Fuente de entrada",
        "none": "ninguna",
        "no_rows": "No hay filas. Sube un CSV o ejecuta Predictor Pro/Odds Lock Pro primero.",
        "safety": "Banner de seguridad asesoría",
        "readiness": "Preparacion de slate fresco",
        "readiness_details": "Detalles de preparacion de slate fresco",
        "source_summary": "Resumen de fuente sportsbook",
        "market_summary": "Resumen de mercado completo",
        "thresholds": "Calibracion de umbrales asesoría",
        "threshold_summary": "Resumen de calibracion de umbrales",
        "calibrated_playable": "Filas +EV jugables calibradas",
        "calibrated_watchlist": "Filas watchlist calibradas",
        "calibrated_prediction_only": "Filas solo prediccion calibradas",
        "calibrated_blocked": "Filas bloqueadas / umbral fallado calibradas",
        "explanations": "Motor de explicacion asesoría",
        "explanation_summary": "Resumen de explicaciones",
        "reason_counts": "Conteo de codigos de razon",
        "row_explanations": "Explicaciones por fila",
        "candidate_review": "Puerta de revisión manual de candidatos",
        "candidate_summary": "Resumen de revisión de candidatos",
        "candidate_blockers": "Bloqueadores de candidatos",
        "eligible_candidates": "Candidatos locales elegibles",
        "selected_candidates": "Candidatos manuales seleccionados",
        "blocked_candidates": "Filas candidatas bloqueadas",
        "watchlist_candidates": "Filas solo watchlist",
        "prediction_only_candidates": "Filas solo prediccion",
        "clv_tracking": "Seguimiento CLV manual",
        "clv_summary": "Resumen CLV manual",
        "clv_by_book": "CLV por sportsbook",
        "clv_by_market": "CLV por mercado",
        "clv_by_explanation": "CLV por estado de explicación",
        "clv_rows": "CLV manual por fila",
        "diagnostics": "Por que no hay filas +EV jugables?",
        "summary": "Resumen asesoría",
        "playable": "Picks asesoría +EV originales",
        "watchlist": "Picks watchlist originales",
        "prediction_only": "Filas solo prediccion originales",
        "prediction_only_note": "Pueden ser buenas predicciones, pero el precio actual no muestra EV positivo jugable.",
        "blocked": "Filas bloqueadas originales por razon",
        "hold": "Tabla hold de sportsbook",
        "line_shopping": "Tabla mejor precio line-shopping",
        "stale": "Alertas de linea vieja",
        "conflicts": "Alertas duplicado/conflicto",
        "validation": "Validacion de archivo real",
        "download": "Descargar CSV asesoría",
        "report": "Reporte asesoría para copiar/pegar",
    },
}

HANDOFF_KEYS = [
    "pro_predictor_latest_rows",
    "pro_predictor_high_confidence_rows",
    "ara_latest_predictions",
    "what_are_the_odds_latest_rows",
    "odds_lock_pro_locked_rows",
    "public_proof_dashboard_refresh_rows",
]


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, TEXT["en"].get(key, key))


def display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return localize_dataframe(frame, LANG)


def csv_link(label: str, frame: pd.DataFrame, filename: str) -> None:
    data = base64.b64encode(frame.to_csv(index=False).encode("utf-8")).decode("ascii")
    st.markdown(
        f'<a href="data:text/csv;base64,{data}" download="{html.escape(filename)}" '
        f'style="display:block;text-align:center;background:#ef5350;color:white;'
        f'padding:.75rem 1rem;border-radius:.45rem;text-decoration:none;font-weight:700;">'
        f'{html.escape(label)}</a>',
        unsafe_allow_html=True,
    )


def rows_from_sources(workspace_id: str) -> tuple[str, list[dict[str, Any]]]:
    for key in HANDOFF_KEYS:
        rows = st.session_state.get(key) or []
        if rows:
            return key, [dict(row) for row in rows if isinstance(row, dict)]
    key, rows = load_first_available(HANDOFF_KEYS, workspace_id)
    if rows:
        st.session_state[key] = rows
        return f"local:{key}", rows
    return "", []


def read_inputs(workspace_id: str) -> tuple[str, pd.DataFrame]:
    label, rows = rows_from_sources(workspace_id)
    use_session = st.checkbox(t("use_session"), value=bool(rows))
    frames: list[pd.DataFrame] = []
    names: list[str] = []
    if use_session and rows:
        frames.append(pd.DataFrame(rows))
        names.append(label or "saved_rows")
    uploads = st.file_uploader(t("upload"), type=["csv"], accept_multiple_files=True)
    if uploads:
        for upload in uploads:
            try:
                frame = pd.read_csv(upload)
                frame["source_file"] = upload.name
                frames.append(frame)
                names.append(upload.name)
            except Exception as exc:
                st.warning(f"{upload.name}: {exc}")
    if not frames:
        return "", pd.DataFrame()
    return ", ".join(names), pd.concat(frames, ignore_index=True, sort=False)


def show_table(title: str, frame: pd.DataFrame, *, note: str | None = None) -> None:
    st.subheader(title)
    if note:
        st.caption(note)
    if frame.empty:
        st.info("No rows.")
    else:
        st.dataframe(display_frame(frame), use_container_width=True, hide_index=True)


def candidate_label(row: Mapping[str, Any]) -> str:
    event = str(row.get("event") or row.get("event_name") or "event")
    prediction = str(row.get("prediction") or row.get("selection") or "selection")
    book = str(row.get("sportsbook") or row.get("bookmaker") or "book")
    row_id = str(row.get("advisory_candidate_review_row_id") or "")
    return f"{event} | {prediction} | {book} | {row_id}"


def threshold_controls() -> dict[str, Any]:
    presets = advisory_threshold_presets()
    st.subheader(t("thresholds"))
    st.warning("This calibration panel changes advisory classifications only. It does not change official locks, proof history, bankroll, staking, ledgers, or live betting.")
    preset_name = st.selectbox("Preset", ["Balanced", "Conservative", "Aggressive", "Custom"], index=0)
    base = normalize_threshold_config(presets.get(preset_name, presets["Balanced"]))
    if preset_name == "Custom":
        base["advisory_threshold_preset"] = "Custom"
    cols = st.columns(2)
    with cols[0]:
        base["advisory_threshold_min_raw_ev"] = st.number_input("Minimum raw EV", value=float(base["advisory_threshold_min_raw_ev"]), step=0.005, format="%.3f")
        base["advisory_threshold_min_best_price_ev"] = st.number_input("Minimum best-price EV", value=float(base["advisory_threshold_min_best_price_ev"]), step=0.005, format="%.3f")
        base["advisory_threshold_min_no_vig_edge"] = st.number_input("Minimum no-vig edge", value=float(base["advisory_threshold_min_no_vig_edge"]), step=0.005, format="%.3f")
        base["advisory_threshold_max_market_hold"] = st.number_input("Maximum sportsbook hold", value=float(base["advisory_threshold_max_market_hold"]), step=0.005, format="%.3f")
        base["advisory_threshold_min_model_probability"] = st.number_input("Minimum model probability", value=float(base["advisory_threshold_min_model_probability"]), step=0.005, format="%.3f")
    with cols[1]:
        base["advisory_threshold_min_line_shopping_gain"] = st.number_input("Minimum line-shopping gain", value=float(base["advisory_threshold_min_line_shopping_gain"]), step=0.005, format="%.3f")
        base["advisory_threshold_max_odds_age_minutes"] = st.number_input("Maximum odds age minutes", value=float(base["advisory_threshold_max_odds_age_minutes"]), step=5.0, format="%.0f")
        base["advisory_threshold_watchlist_min_raw_ev"] = st.number_input("Watchlist minimum raw EV", value=float(base["advisory_threshold_watchlist_min_raw_ev"]), step=0.005, format="%.3f")
        base["advisory_threshold_watchlist_min_no_vig_edge"] = st.number_input("Watchlist minimum no-vig edge", value=float(base["advisory_threshold_watchlist_min_no_vig_edge"]), step=0.005, format="%.3f")
        base["advisory_threshold_max_risk_flags"] = st.number_input("Maximum risk flags", value=int(base["advisory_threshold_max_risk_flags"]), step=1, min_value=0, max_value=25)
    return normalize_threshold_config(base)


st.title(t("title"))
st.caption(t("caption"))

with st.expander(t("input"), expanded=True):
    workspace_input = st.text_input(t("test_window"), value=st.session_state.get("aba_test_window_id", "test_01"))
    workspace_id = normalize_workspace_id(workspace_input)
    st.session_state["aba_test_window_id"] = workspace_id
    source_name, raw = read_inputs(workspace_id)

if raw.empty:
    st.caption(f"{t('source')}: {t('none')}")
    st.warning(t("no_rows"))
    st.stop()

normalized = normalize_frame(raw)
advisory = advisory_frame(normalized)
threshold_config = threshold_controls()
calibrated_rows = apply_advisory_thresholds(advisory, threshold_config)
calibrated_frame = pd.DataFrame(calibrated_rows)
explained_rows = explain_advisory_rows(calibrated_rows)
explained_frame = pd.DataFrame(explained_rows)
candidate_base_rows = candidate_review_rows(explained_rows)
candidate_base_frame = pd.DataFrame(candidate_base_rows)
clv_base_rows = apply_manual_clv_fields(candidate_base_rows)
impact = threshold_impact_summary(advisory, calibrated_rows)
validation = validate_advisory_rows(normalized)
counts = advisory_summary_counts(advisory)
readiness = fresh_slate_readiness_check(advisory)
explanation_summary_frame = advisory_explanation_summary(explained_rows)
top_explanation = explanation_summary_frame.iloc[0].to_dict() if not explanation_summary_frame.empty else {}
candidate_summary_base = candidate_review_summary(candidate_base_rows)
top_candidate = candidate_summary_base.iloc[0].to_dict() if not candidate_summary_base.empty else {}
clv_base_summary = manual_clv_summary(clv_base_rows)
top_clv = clv_base_summary.iloc[0].to_dict() if not clv_base_summary.empty else {}
readiness.update({
    "threshold_preset_used": threshold_config.get("advisory_threshold_preset"),
    "calibrated_playable_count": impact.get("calibrated_PLAYABLE_PLUS_EV", 0),
    "calibrated_watchlist_count": impact.get("calibrated_WATCHLIST_VALUE", 0),
    "calibrated_prediction_only_count": impact.get("calibrated_prediction_only_rows", 0),
    "threshold_calibration_note": "Threshold calibration is informational and does not make Fresh Slate Readiness stricter.",
    "explanation_engine_available": True,
    "explained_row_count": len(explained_rows),
    "top_explanation_status": top_explanation.get("explanation_status"),
    "top_explanation_blocker": top_explanation.get("most_common_primary_reason"),
    "manual_candidate_review_available": True,
    "manual_candidate_review_row_count": len(candidate_base_rows),
    "top_manual_candidate_review_status": top_candidate.get("advisory_manual_review_status"),
    "manual_clv_tracking_available": True,
    "manual_clv_row_count": len(clv_base_rows),
    "top_manual_clv_status": top_clv.get("advisory_clv_status"),
    "manual_clv_note": "Manual CLV fields are informational and do not make Fresh Slate Readiness stricter.",
})
diagnostics = advisory_real_file_diagnostics(advisory)

st.caption(f"{t('source')}: {source_name or t('none')}")
st.subheader(t("safety"))
st.warning(ADVISORY_WARNING)
st.info(SAFETY_CONFIRMATION)
st.json({
    "advisory_only": True,
    "proof_preserving": True,
    "threshold_calibration_only": True,
    "explanation_only": True,
    "manual_candidate_review_only": True,
    "manual_clv_tracking_only": True,
    "odds_polling": "OFF",
    "live_application": "OFF",
    "applied_live_count": 0,
    "does_not_feed_official_locks": True,
})

st.subheader(t("readiness"))
score_col, status_col = st.columns(2)
score_col.metric("Readiness score", f"{readiness['readiness_score']}/100")
status_col.metric("Readiness status", readiness["readiness_status"])
st.info(readiness.get("recommended_next_action", "Review advisory tables."))
with st.expander(t("readiness_details"), expanded=True):
    st.json(readiness)

show_table(t("source_summary"), sportsbook_source_summary(advisory))
show_table(t("market_summary"), market_completeness_summary(advisory))

st.subheader("Threshold impact summary")
impact_cols = st.columns(6)
impact_cols[0].metric("Original playable", impact["original_PLAYABLE_PLUS_EV"])
impact_cols[1].metric("Calibrated playable", impact["calibrated_PLAYABLE_PLUS_EV"])
impact_cols[2].metric("Original watchlist", impact["original_WATCHLIST_VALUE"])
impact_cols[3].metric("Calibrated watchlist", impact["calibrated_WATCHLIST_VALUE"])
impact_cols[4].metric("Downgraded", impact["downgraded_by_thresholds"])
impact_cols[5].metric("Upgraded", impact["upgraded_by_thresholds"])
st.json(impact)
show_table(t("threshold_summary"), threshold_calibration_summary(advisory, threshold_config))
show_table(t("calibrated_playable"), calibrated_status_table(calibrated_rows, PLAYABLE_PLUS_EV, threshold_config))
show_table(t("calibrated_watchlist"), calibrated_status_table(calibrated_rows, WATCHLIST_VALUE, threshold_config))
show_table(t("calibrated_prediction_only"), calibrated_status_table(calibrated_rows, PREDICTION_ONLY_NOT_PLUS_EV, threshold_config))
show_table(t("calibrated_blocked"), calibrated_blocked_reason_summary(calibrated_rows, threshold_config))

st.subheader(t("explanations"))
st.warning("Explanations are advisory-only. They do not create official locks, change proof history, change bankroll/staking, or place bets.")
show_table(t("explanation_summary"), explanation_summary_frame)
show_table(t("reason_counts"), advisory_explanation_reason_counts(explained_rows))
explanation_cols = [
    "event", "prediction", "market_type", "sportsbook", "bookmaker", "advisory_playable_status",
    "advisory_calibrated_playable_status", "advisory_explanation_status", "advisory_explanation_summary",
    "advisory_explanation_primary_reason", "advisory_explanation_reason_codes", "advisory_explanation_blockers",
    "advisory_explanation_warnings", "advisory_explanation_next_action",
]
show_table(t("row_explanations"), explained_frame[[col for col in explanation_cols if col in explained_frame.columns]].copy() if not explained_frame.empty else pd.DataFrame(columns=explanation_cols))

st.subheader(t("candidate_review"))
st.warning("Manual candidate review creates local review candidates only. It does not create official locks, does not publish proof, does not change bankroll/staking, and does not place bets.")
eligible_frame = candidate_base_frame[candidate_base_frame.get("advisory_manual_review_status", pd.Series(dtype=str)).fillna("").astype(str) == "REVIEW_ELIGIBLE"].copy() if not candidate_base_frame.empty else pd.DataFrame()
option_labels = {str(row.get("advisory_candidate_review_row_id")): candidate_label(row) for row in eligible_frame.to_dict("records")}
selected_ids = st.multiselect(
    "Select eligible rows as local review candidates",
    options=list(option_labels.keys()),
    format_func=lambda value: option_labels.get(str(value), str(value)),
)
candidate_rows = apply_manual_candidate_selection(explained_rows, selected_ids)
candidate_frame = pd.DataFrame(candidate_rows)
show_table(t("candidate_summary"), candidate_review_summary(candidate_rows))
show_table(t("candidate_blockers"), candidate_review_blocker_summary(candidate_rows))
candidate_cols = [
    "event", "prediction", "market_type", "sportsbook", "bookmaker", "advisory_playable_status",
    "advisory_calibrated_playable_status", "advisory_explanation_status", "advisory_manual_review_status",
    "advisory_manual_review_eligible", "advisory_manual_review_blockers", "advisory_manual_review_warnings",
    "advisory_candidate_review_status", "advisory_candidate_review_row_id", "advisory_manual_review_next_action",
]
if candidate_frame.empty:
    empty_candidate = pd.DataFrame(columns=candidate_cols)
    selected_candidate_frame = empty_candidate
    blocked_candidate_frame = empty_candidate
    watchlist_candidate_frame = empty_candidate
    prediction_candidate_frame = empty_candidate
else:
    selected_candidate_frame = candidate_frame[candidate_frame["advisory_candidate_review_status"].fillna("").astype(str) == "MANUAL_CANDIDATE_ONLY"].copy()
    blocked_candidate_frame = candidate_frame[candidate_frame["advisory_manual_review_status"].fillna("").astype(str) == "REVIEW_BLOCKED"].copy()
    watchlist_candidate_frame = candidate_frame[candidate_frame["advisory_manual_review_status"].fillna("").astype(str) == "REVIEW_WATCHLIST_ONLY"].copy()
    prediction_candidate_frame = candidate_frame[candidate_frame["advisory_manual_review_status"].fillna("").astype(str) == "REVIEW_PREDICTION_ONLY"].copy()
show_table(t("eligible_candidates"), eligible_frame[[col for col in candidate_cols if col in eligible_frame.columns]].copy() if not eligible_frame.empty else pd.DataFrame(columns=candidate_cols))
show_table(t("selected_candidates"), selected_candidate_frame[[col for col in candidate_cols if col in selected_candidate_frame.columns]].copy() if not selected_candidate_frame.empty else pd.DataFrame(columns=candidate_cols))
show_table(t("blocked_candidates"), blocked_candidate_frame[[col for col in candidate_cols if col in blocked_candidate_frame.columns]].copy() if not blocked_candidate_frame.empty else pd.DataFrame(columns=candidate_cols))
show_table(t("watchlist_candidates"), watchlist_candidate_frame[[col for col in candidate_cols if col in watchlist_candidate_frame.columns]].copy() if not watchlist_candidate_frame.empty else pd.DataFrame(columns=candidate_cols))
show_table(t("prediction_only_candidates"), prediction_candidate_frame[[col for col in candidate_cols if col in prediction_candidate_frame.columns]].copy() if not prediction_candidate_frame.empty else pd.DataFrame(columns=candidate_cols))

st.subheader(t("clv_tracking"))
st.warning("Manual CLV tracking uses uploaded/manual closing odds only. It does not poll odds, create official locks, publish proof, change result grading, change bankroll/staking, or place bets.")
clv_rows = apply_manual_clv_fields(candidate_rows)
clv_frame = pd.DataFrame(clv_rows)
show_table(t("clv_summary"), manual_clv_summary(clv_rows))
show_table(t("clv_by_book"), manual_clv_group_summary(clv_rows, "bookmaker"))
show_table(t("clv_by_market"), manual_clv_group_summary(clv_rows, "market_type"))
show_table(t("clv_by_explanation"), manual_clv_group_summary(clv_rows, "advisory_explanation_status"))
clv_cols = [
    "event", "prediction", "market_type", "sportsbook", "bookmaker", "advisory_candidate_review_status",
    "advisory_opening_decimal_odds", "advisory_closing_decimal_odds", "advisory_clv_decimal_delta",
    "advisory_clv_percent_delta", "advisory_clv_status", "advisory_clv_missing_reason", "advisory_clv_notes",
]
show_table(t("clv_rows"), clv_frame[[col for col in clv_cols if col in clv_frame.columns]].copy() if not clv_frame.empty else pd.DataFrame(columns=clv_cols))

st.subheader(t("diagnostics"))
if diagnostics.get("show_no_playable_warning"):
    st.warning(diagnostics.get("explanation", "No playable advisory rows were found."))
st.info(diagnostics.get("recommended_next_action", "Review advisory tables before manual promotion in a later phase."))
st.json(diagnostics)

st.subheader(t("summary"))
metric_cols = st.columns(9)
metric_cols[0].metric("Rows", counts["total_advisory_rows"])
metric_cols[1].metric("Playable +EV", counts["PLAYABLE_PLUS_EV"])
metric_cols[2].metric("Watchlist", counts["WATCHLIST_VALUE"])
metric_cols[3].metric("Prediction-only", counts["PREDICTION_ONLY_NOT_PLUS_EV"])
metric_cols[4].metric("Blocked", counts["blocked_rows"])
metric_cols[5].metric("Stale", counts["stale_rows"])
metric_cols[6].metric("Unknown", counts["unknown_freshness_rows"])
metric_cols[7].metric("Complete", counts["complete_markets"])
metric_cols[8].metric("Conflicts", counts["duplicate_conflict_rows"])

show_table(t("playable"), playable_table(advisory))
show_table(t("watchlist"), watchlist_table(advisory))
show_table(t("prediction_only"), prediction_only_table(advisory), note=t("prediction_only_note"))
show_table(t("blocked"), blocked_reason_summary(advisory))
show_table(t("hold"), sportsbook_hold_summary(advisory))
show_table(t("line_shopping"), line_shopping_summary(advisory))
show_table(t("stale"), stale_line_summary(advisory))
show_table(t("conflicts"), duplicate_conflict_summary(advisory))

st.subheader(t("validation"))
st.json(validation)

csv_link(t("download"), advisory_csv_frame(clv_frame), f"advisory_odds_value_{workspace_id}.csv")
st.subheader(t("report"))
combined_report = (
    advisory_report_text(advisory)
    + "\n\n"
    + threshold_report_text(calibrated_rows, threshold_config)
    + "\n\n"
    + advisory_explanation_report_section(explained_rows)
    + "\n\n"
    + candidate_review_report_section(candidate_rows)
    + "\n\n"
    + manual_clv_report_section(clv_rows)
)
st.text_area(t("report"), value=combined_report, height=580)
