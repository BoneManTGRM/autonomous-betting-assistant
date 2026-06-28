from __future__ import annotations

import re
from typing import Any

import pandas as pd

from autonomous_betting_agent.report_product_layer import event_text, pick_text, sport_text, team_label, value_text


COLUMN_LABELS_ES = {
    "active_list_id": "id_lista_activa",
    "actual_win_rate": "acierto_real",
    "agent_decision": "decision_agente",
    "agent_score": "puntaje_agente",
    "api_coverage_score": "cobertura_api",
    "avg_predicted": "promedio_predicho",
    "beat_close": "supero_cierre",
    "blocker": "bloqueador",
    "bookmaker": "casa",
    "bookmaker_count": "cantidad_casas",
    "bucket": "rango",
    "client_report_ready": "listo_reporte_cliente",
    "closing_odds": "cuota_cierre",
    "confidence": "confianza",
    "confidence_bucket": "rango_confianza",
    "confidence_risk_score": "riesgo_confianza",
    "consumer_action": "accion_cliente",
    "control": "control",
    "data_issue_reason": "motivo_problema_datos",
    "decimal_price": "cuota_decimal",
    "decision_reasons": "razones_decision",
    "edge": "ventaja",
    "edge_bucket": "rango_ventaja",
    "edge_status": "estado_ventaja",
    "event": "evento",
    "event_id": "id_evento",
    "event_level": "nivel_evento",
    "event_name": "evento",
    "event_pick_index": "indice_pick_evento",
    "event_start_time": "inicio_evento",
    "event_start_utc": "inicio_utc",
    "expected_value_per_unit": "valor_esperado_por_unidad",
    "expected_win_rate": "acierto_esperado",
    "final_score": "marcador_final",
    "grade": "calificacion",
    "has_proof_hash": "tiene_hash_prueba",
    "ignored_value_blockers": "bloqueos_valor_ignorados",
    "ledger_batch_id": "id_lote_ledger",
    "ledger_type": "tipo_ledger",
    "learning_ready": "listo_aprendizaje",
    "learning_status": "estado_aprendizaje",
    "limit_units": "limite_unidades",
    "line_point": "linea",
    "lock_blockers": "bloqueos",
    "lock_ready": "listo_bloqueo",
    "locked_at_utc": "bloqueado_utc",
    "losses": "derrotas",
    "market": "mercado",
    "market_probability": "probabilidad_mercado",
    "market_read": "lectura_mercado",
    "market_type": "tipo_mercado",
    "model_edge": "ventaja_modelo",
    "model_lean_label": "inclinacion_modelo",
    "model_market_edge": "ventaja_modelo_mercado",
    "model_probability": "probabilidad_modelo",
    "model_probability_bucket": "rango_probabilidad_modelo",
    "model_probability_clean": "probabilidad_modelo_limpia",
    "model_probability_source": "fuente_probabilidad_modelo",
    "next_action": "siguiente_accion",
    "odds": "cuota",
    "odds_audit_status": "estado_auditoria_cuotas",
    "odds_band": "rango_cuota",
    "odds_ready": "cuotas_listas",
    "odds_source": "fuente_cuotas",
    "odds_verified": "cuota_verificada",
    "official_lock_ready": "listo_bloqueo_oficial",
    "official_publish_ready": "listo_publicacion_oficial",
    "official_status_label": "estado_oficial",
    "page": "pagina",
    "pending": "pendientes",
    "pick_rows": "filas_pick",
    "prelock_status": "estado_prebloqueo",
    "prediction": "seleccion",
    "price_value_label": "valor_precio",
    "profit_units": "unidades_ganancia",
    "proof_hash": "hash_prueba",
    "proof_id": "id_prueba",
    "proof_status": "estado_prueba",
    "public_action": "accion_publica",
    "public_confidence": "confianza_publica",
    "public_pick": "seleccion_publica",
    "public_reason": "razon_publica",
    "public_safe": "segura_publico",
    "publish_ready": "listo_publicar",
    "pushes": "pushes",
    "recommended_action": "accion_recomendada",
    "report_lane": "carril_reporte",
    "report_lane_v2": "carril_reporte_v2",
    "research_lock_blockers": "bloqueos_investigacion",
    "research_lock_ready": "listo_bloqueo_investigacion",
    "result": "resultado",
    "result_status": "estado_resultado",
    "risk_preference": "preferencia_riesgo",
    "roi": "ROI",
    "row_level": "nivel_fila",
    "rows": "filas",
    "sample_size": "tamano_muestra",
    "scanner_strength_score": "puntaje_fuerza_scanner",
    "scope": "alcance",
    "source": "fuente",
    "source_file": "archivo_fuente",
    "sport": "deporte",
    "sport_key": "clave_deporte",
    "stake_blocked": "stake_bloqueado",
    "stake_reason": "razon_stake",
    "stake_units": "unidades_stake",
    "status": "estado",
    "suggested_stake_units": "unidades_stake_sugeridas",
    "suggestion": "sugerencia",
    "unique_event_id": "id_evento_unico",
    "visibility": "visibilidad",
    "voids": "voids",
    "why_it_matters": "por_que_importa",
    "win_rate": "tasa_acierto",
    "winner": "ganador",
    "wins": "victorias",
    "workspace_id": "id_workspace",
}

VALUE_LABELS_ES = {
    "a_top_candidate": "Nivel A - candidato fuerte",
    "b_high_confidence_test": "Nivel B - prueba de alta confianza",
    "c_research_volume": "Nivel C - volumen de investigacion",
    "row_level": "nivel de fila",
    "event_level": "nivel de evento",
    "official": "oficial",
    "research": "investigacion",
    "research_play": "jugada de investigacion",
    "research_test": "investigacion/prueba",
    "research_test_future_only": "investigacion/prueba futuro",
    "client": "cliente",
    "quarantine": "cuarentena",
    "learning_only": "solo aprendizaje",
    "learning_candidate": "candidata de aprendizaje",
    "all_high_confidence": "alta confianza",
    "win": "ganada",
    "won": "ganada",
    "loss": "perdida",
    "lost": "perdida",
    "pending": "pendiente",
    "void": "void",
    "push": "push",
    "cancel": "cancelada",
    "private": "privado",
    "public": "publico",
    "default": "predeterminado",
    "trial": "prueba",
    "active": "activo",
    "inactive": "inactivo",
    "expired": "vencido",
    "persistent_proof_ledger": "ledger de prueba persistente",
    "persistent_ledger": "ledger persistente",
    "pro_predictor_high_confidence": "Predictor Pro alta confianza",
    "pro_predictor_latest": "Predicciones recientes de Predictor Pro",
    "none": "ninguna",
    "unknown": "desconocido",
    "ok": "correcto",
    "over_limit": "sobre el limite",
    "daily_total": "total diario",
    "true": "si",
    "false": "no",
    "strong_learning_memory": "memoria de aprendizaje fuerte",
    "medium_learning_memory": "memoria de aprendizaje media",
    "weak_learning_memory": "memoria de aprendizaje debil",
    "fallback_probability": "probabilidad fallback",
    "price_implied_probability": "probabilidad implicita por cuota",
    "direct_probability": "probabilidad directa",
    "totals": "totales",
    "total": "total",
    "spreads": "handicaps",
    "spread": "handicap",
    "moneyline": "ganador",
    "team_total": "total del equipo",
    "game_total": "total del partido",
    "price_watch_research": "Seguimiento de precio / investigacion",
    "research_track_for_learning": "Investigacion / seguimiento para aprendizaje",
    "research_learning": "Investigacion / aprendizaje",
    "official_ev": "oficial +EV",
    "official_plus_ev": "oficial +EV",
    "official_plus_ev_future_only": "oficial +EV futuro",
    "ready_for_lock_or_learning": "listo para bloqueo o aprendizaje",
    "lock_first": "bloquear primero",
    "fifa_world_cup": "Copa Mundial FIFA",
    "super_league_china": "Superliga - China",
    "research_test_lock": "bloqueo investigacion/prueba",
    "accuracy_test_lock_value_blockers_ignored_not_an_official_ev_pick": "Bloqueo de prueba de precision; bloqueos de valor ignorados. No es una jugada oficial +EV.",
    "consumer_magazine": "Revista de consumidor",
    "tipster_report": "Reporte tipster",
    "client_safe_summary": "Resumen seguro para cliente",
    "analyst_proof_report": "Reporte de prueba para analista",
    "daily_sports_analysis": "Analisis deportivo diario",
    "balanced": "balanceado",
    "conservative": "conservador",
    "aggressive": "agresivo",
    "flat": "stake fijo",
    "conservative_kelly": "Kelly conservador",
    "live_mutation": "mutacion en vivo",
    "repair_activation": "activacion de reparacion",
    "shadow_mode_activation": "activacion Shadow Mode",
    "tgrm_activation": "activacion TGRM",
    "rye_activation": "activacion RYE",
    "on": "encendido",
    "off": "apagado",
    "forbidden": "prohibido",
    "watch_only": "solo observar",
    "research_watch": "seguimiento de investigacion",
    "play_small": "jugar pequeno",
    "play_strong": "jugar fuerte",
    "locked_before_start": "bloqueado antes del inicio",
    "computed_from_model_probability_vs_odds_api_price": "calculado con probabilidad del modelo vs cuota Odds API",
    "odds_unavailable_no_edge": "cuotas no disponibles sin ventaja",
}

EVENT_COLUMNS = {"event", "event_name", "matchup", "public_event", "game"}
TEAM_COLUMNS = {"team", "team_name", "home_team", "away_team", "winner", "opponent"}
SPORT_COLUMNS = {"sport", "league", "competition", "public_sport"}
PICK_COLUMNS = {"prediction", "pick", "selection", "public_pick"}
VALUE_COLUMNS = {
    "consumer_action",
    "recommended_action",
    "public_action",
    "market",
    "market_type",
    "model_lean_label",
    "price_value_label",
    "official_status_label",
    "result_status",
    "learning_status",
    "data_issue_reason",
    "suggestion",
    "sports_context_summary",
    "market_read",
    "why_it_matters",
    "report_lane",
    "report_lane_v2",
    "ledger_type",
    "status",
    "next_action",
    "page",
    "confidence_bucket",
    "public_confidence",
    "public_reason",
    "scope",
    "proof_status",
    "agent_decision",
    "decision_reasons",
    "lock_blockers",
    "research_lock_blockers",
    "ignored_value_blockers",
}


def is_spanish(language: str | None) -> bool:
    return str(language or "").strip().lower().startswith("es")


def tr(language: str | None, english: str, spanish: str) -> str:
    return spanish if is_spanish(language) else english


def _value_key(value: Any) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9+]+", "_", str(value).strip().lower())).strip("_")


def localize_value(value: Any, language: str | None) -> Any:
    if not is_spanish(language):
        return value
    if value is None:
        return value
    text = str(value).strip()
    if not text:
        return value
    key = _value_key(text)
    if key in VALUE_LABELS_ES:
        return VALUE_LABELS_ES[key]
    translated = value_text(text, "es")
    return translated if translated != text else value


def localize_cell(value: Any, language: str | None, column: str | None = None) -> Any:
    if not is_spanish(language):
        return value
    if value is None:
        return value
    text = str(value).strip()
    if not text:
        return value
    col = str(column or "").strip().lower()
    if col in EVENT_COLUMNS:
        return event_text(text, "es")
    if col in TEAM_COLUMNS:
        return team_label(text, "es")
    if col in SPORT_COLUMNS:
        return sport_text(text, "es")
    if col in PICK_COLUMNS:
        return pick_text(text, "es")
    if col in VALUE_COLUMNS:
        return localize_value(text, language)
    if re.search(r"\s+(?:at|vs|v|@)\s+", text, flags=re.I):
        return event_text(text, "es")
    return localize_value(text, language)


def localize_dataframe(frame: pd.DataFrame, language: str | None) -> pd.DataFrame:
    if not is_spanish(language) or frame is None or frame.empty:
        return frame
    out = frame.copy()
    for column in out.columns:
        if out[column].dtype == object:
            out[column] = out[column].map(lambda item, col=column: localize_cell(item, language, str(col)))
    return out.rename(columns={column: COLUMN_LABELS_ES.get(str(column), str(column)) for column in out.columns})


def localize_options(options: list[str], language: str | None) -> tuple[list[str], dict[str, str]]:
    if not is_spanish(language):
        return options, {option: option for option in options}
    display = [str(localize_cell(option, language)) for option in options]
    return display, dict(zip(display, options))


def upload_helper(language: str | None) -> str:
    return tr(language, "Upload control text may be controlled by Streamlit.", "El texto interno del boton de carga puede depender de Streamlit.")


def render_upload_css(st_module, language: str | None) -> None:
    """Best-effort Spanish styling for Streamlit's built-in file uploader.

    Streamlit owns the internal file-uploader button text. This CSS only runs in
    Spanish mode and visually replaces the default button label where Streamlit's
    current DOM supports it. Native browser/toolbar text may remain English.
    """
    if not is_spanish(language):
        return
    st_module.markdown(
        """
<style>
div[data-testid="stFileUploader"] button div p,
div[data-testid="stFileUploader"] button p,
div[data-testid="stFileUploader"] button span {
  font-size: 0 !important;
  line-height: 0 !important;
}
div[data-testid="stFileUploader"] button div p::after,
div[data-testid="stFileUploader"] button p::after,
div[data-testid="stFileUploader"] button span::after {
  content: "Subir";
  font-size: 1rem !important;
  line-height: 1.2 !important;
}
div[data-testid="stFileUploader"] small {
  font-size: 0 !important;
}
div[data-testid="stFileUploader"] small::after {
  content: "CSV u otro archivo compatible";
  font-size: .9rem !important;
}
</style>
""",
        unsafe_allow_html=True,
    )
