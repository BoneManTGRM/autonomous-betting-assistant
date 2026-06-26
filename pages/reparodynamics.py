from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.reparodynamics_doctrine import get_reparodynamics_doctrine
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Reparodynamics", layout="wide")
LANG = render_app_sidebar("reparodynamics", language_key="reparodynamics_language", selector="radio")

TEXT = {
    "en": {
        "title": "Reparodynamics",
        "caption": "ABA Signal Pro operating doctrine for measured self-repair.",
        "phase": "Current phase",
        "mode": "Operating mode",
        "repair": "Repair activation",
        "shadow": "Shadow Mode",
        "tgrm": "TGRM",
        "rye": "RYE",
        "motive": "Doctrine motive",
        "principles": "Repair principles",
        "safety": "Safety principles",
        "forbidden": "Forbidden in Phase 3A",
        "status": "Activation status",
        "final": "Final rule",
        "warning": "This page is documentation/status only. It does not activate live repairs, Shadow Mode, TGRM, RYE scoring, confidence changes, bet-tier changes, bankroll changes, sportsbook changes, or model mutation.",
    },
    "es": {
        "title": "Reparodynamics",
        "caption": "Doctrina operativa de ABA Signal Pro para autorreparación medida.",
        "phase": "Fase actual",
        "mode": "Modo operativo",
        "repair": "Activación de reparación",
        "shadow": "Shadow Mode",
        "tgrm": "TGRM",
        "rye": "RYE",
        "motive": "Motivo de la doctrina",
        "principles": "Principios de reparación",
        "safety": "Principios de seguridad",
        "forbidden": "Prohibido en Fase 3A",
        "status": "Estado de activación",
        "final": "Regla final",
        "warning": "Esta página es solo documentación/estado. No activa reparaciones en vivo, Shadow Mode, TGRM, puntuación RYE, cambios de confianza, cambios de nivel de apuesta, cambios de bankroll, cambios de sportsbook ni mutación del modelo.",
    },
}

ES_VALUE_MAP = {
    "Phase 3A": "Fase 3A",
    "Observation-only": "Solo observación",
    "Evidence-gated targeted repair": "Reparación dirigida con control de evidencia",
    "Forbidden": "Prohibido",
    "OFF": "APAGADO",
    "ABA should learn automatically, but repair cautiously.": "ABA debe aprender automáticamente, pero reparar con cautela.",
}

ES_LIST_MAP = {
    "Observe first and repair later.": "Observar primero y reparar después.",
    "Diagnose drift before proposing any repair.": "Diagnosticar deriva antes de proponer cualquier reparación.",
    "Prefer targeted repair over blind retraining.": "Preferir reparación dirigida en vez de reentrenamiento ciego.",
    "Conserve repair energy by changing only what evidence supports.": "Conservar energía de reparación cambiando solo lo que la evidencia respalda.",
    "Keep pattern candidates watchlist-only until controlled evidence supports promotion.": "Mantener candidatos de patrón solo en watchlist hasta que evidencia controlada respalde su promoción.",
    "Treat RYE readiness as readiness only, not activation.": "Tratar la preparación RYE solo como preparación, no como activación.",
    "Treat Shadow Mode readiness as readiness only, not activation.": "Tratar la preparación de Shadow Mode solo como preparación, no como activación.",
    "Phase 3A is observation-only.": "La Fase 3A es solo observación.",
    "Learning means observation, diagnostics, watchlist candidates, readiness checks, and saved reports only.": "Aprendizaje significa solo observación, diagnósticos, candidatos en watchlist, revisiones de preparación y reportes guardados.",
    "No repair activates during Phase 3A.": "Ninguna reparación se activa durante la Fase 3A.",
    "No repair survives without proof.": "Ninguna reparación sobrevive sin prueba.",
    "The system does not chase losses.": "El sistema no persigue pérdidas.",
    "The system does not panic after variance.": "El sistema no entra en pánico después de la varianza.",
    "The system does not blindly retrain.": "El sistema no se reentrena a ciegas.",
    "The system does not inflate confidence.": "El sistema no infla la confianza.",
    "live repairs": "reparaciones en vivo",
    "Shadow Mode activation": "activación de Shadow Mode",
    "TGRM repair activation": "activación de reparación TGRM",
    "full RYE repair scoring": "puntuación completa de reparación RYE",
    "Hidden Value Score activation": "activación de Hidden Value Score",
    "confidence calibration activation": "activación de calibración de confianza",
    "live pick filtering": "filtrado de picks en vivo",
    "live model mutation": "mutación del modelo en vivo",
    "Learning Page live model updates": "actualizaciones del modelo en vivo desde Learning Page",
    "automatic confidence adjustment": "ajuste automático de confianza",
    "automatic bet-tier changes": "cambios automáticos de nivel de apuesta",
    "production repair candidates": "candidatos de reparación de producción",
    "automatic bankroll changes": "cambios automáticos de bankroll",
    "automatic sportsbook recommendation changes": "cambios automáticos de recomendación de sportsbook",
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, TEXT["en"].get(key, key))


def value_text(value: str) -> str:
    return ES_VALUE_MAP.get(value, value) if LANG == "es" else value


def list_text(values: list[str]) -> list[str]:
    if LANG != "es":
        return values
    return [ES_LIST_MAP.get(value, value) for value in values]


doctrine = get_reparodynamics_doctrine()

st.title(t("title"))
st.caption(t("caption"))
st.warning(t("warning"))

status_cols = st.columns(5)
status_cols[0].metric(t("phase"), value_text(str(doctrine.get("current_phase", ""))))
status_cols[1].metric(t("mode"), value_text(str(doctrine.get("operating_mode", ""))))
status_cols[2].metric(t("repair"), value_text(str(doctrine.get("repair_activation", ""))))
status_cols[3].metric(t("shadow"), value_text(str(doctrine.get("shadow_mode_activation", ""))))
status_cols[4].metric(t("tgrm"), value_text(str(doctrine.get("tgrm_activation", ""))))

st.subheader(t("motive"))
if LANG == "es":
    st.write("Reparodynamics es la doctrina operativa de autorreparación medida. ABA observa primero, diagnostica con cuidado, preserva la integridad de los datos, conserva energía de reparación y repara solo después de que evidencia controlada demuestre que un cambio dirigido mejora el rendimiento medible sin aumentar riesgo oculto.")
else:
    st.write(doctrine.get("motive", ""))

left, right = st.columns(2)
with left:
    st.subheader(t("principles"))
    for item in list_text(list(doctrine.get("repair_principles", []))):
        st.markdown(f"- {item}")
with right:
    st.subheader(t("safety"))
    for item in list_text(list(doctrine.get("safety_principles", []))):
        st.markdown(f"- {item}")

st.subheader(t("forbidden"))
st.dataframe(
    pd.DataFrame({t("forbidden"): list_text(list(doctrine.get("forbidden_actions", [])))}),
    use_container_width=True,
    hide_index=True,
)

st.subheader(t("status"))
st.dataframe(
    pd.DataFrame(
        [
            {"control": "live_mutation", "status": value_text(str(doctrine.get("live_mutation", "")))},
            {"control": "repair_activation", "status": value_text(str(doctrine.get("repair_activation", "")))},
            {"control": "shadow_mode_activation", "status": value_text(str(doctrine.get("shadow_mode_activation", "")))},
            {"control": "tgrm_activation", "status": value_text(str(doctrine.get("tgrm_activation", "")))},
            {"control": "rye_activation", "status": value_text(str(doctrine.get("rye_activation", "")))},
        ]
    ),
    use_container_width=True,
    hide_index=True,
)

st.success(value_text(str(doctrine.get("final_rule", ""))))
