from __future__ import annotations

import re
from typing import Any

import pandas as pd

from autonomous_betting_agent.report_product_layer import event_text, pick_text, sport_text, team_label, value_text


COLUMN_LABELS_ES = {
    "active_list_id": "ID de lista activa",
    "actual_win_rate": "Acierto real",
    "agent_decision": "Decision del agente",
    "agent_score": "Puntaje del agente",
    "api_coverage_score": "Cobertura API",
    "avg_predicted": "Promedio predicho",
    "backup_rows": "Filas en respaldo",
    "beat_close": "Supero cierre",
    "blocker": "Bloqueador",
    "bookmaker": "Casa",
    "bookmaker_count": "Cantidad de casas",
    "bucket": "Rango",
    "checked_at_utc": "Revisado UTC",
    "client_report_ready": "Listo para reporte cliente",
    "closing_odds": "Cuota de cierre",
    "confidence": "Confianza",
    "confidence_bucket": "Rango de confianza",
    "confidence_risk_score": "Riesgo de confianza",
    "consumer_action": "Accion del cliente",
    "control": "Control",
    "data_issue_reason": "Motivo del problema de datos",
    "decimal_price": "Cuota decimal",
    "decision_reasons": "Razones de decision",
    "details": "Detalles",
    "disk_rows": "Filas en disco",
    "edge": "Ventaja",
    "edge_bucket": "Rango de ventaja",
    "edge_status": "Estado de ventaja",
    "event": "Evento",
    "event_id": "ID de evento",
    "event_level": "Nivel de evento",
    "event_name": "Evento",
    "event_pick_index": "Indice de pick del evento",
    "event_start_time": "Inicio del evento",
    "event_start_utc": "Inicio UTC",
    "expected_value_per_unit": "Valor esperado por unidad",
    "expected_win_rate": "Acierto esperado",
    "final_score": "Marcador final",
    "grade": "Calificacion",
    "github_rows": "Filas en GitHub",
    "has_proof_hash": "Tiene hash de prueba",
    "ignored_value_blockers": "Bloqueos de valor ignorados",
    "key": "Clave",
    "ledger_batch_id": "ID de lote ledger",
    "ledger_type": "Tipo de ledger",
    "learning_ready": "Listo para aprendizaje",
    "learning_status": "Estado de aprendizaje",
    "limit_units": "Limite de unidades",
    "line_point": "Linea",
    "loaded_rows": "Filas cargadas",
    "lock_blockers": "Bloqueos",
    "lock_ready": "Listo para bloqueo",
    "locked_at_utc": "Bloqueado UTC",
    "losses": "Derrotas",
    "market": "Mercado",
    "market_probability": "Probabilidad de mercado",
    "market_read": "Lectura de mercado",
    "market_type": "Tipo de mercado",
    "model_edge": "Ventaja del modelo",
    "model_lean_label": "Inclinacion del modelo",
    "model_market_edge": "Ventaja modelo vs mercado",
    "model_probability": "Probabilidad del modelo",
    "model_probability_bucket": "Rango de probabilidad del modelo",
    "model_probability_clean": "Probabilidad limpia del modelo",
    "model_probability_source": "Fuente de probabilidad del modelo",
    "next_action": "Siguiente accion",
    "odds": "Cuota",
    "odds_audit_status": "Estado de auditoria de cuotas",
    "odds_band": "Rango de cuota",
    "odds_ready": "Cuotas listas",
    "odds_source": "Fuente de cuotas",
    "odds_verified": "Cuota verificada",
    "official_lock_ready": "Listo para bloqueo oficial",
    "official_publish_ready": "Listo para publicacion oficial",
    "official_status_label": "Estado oficial",
    "page": "Pagina",
    "pending": "Pendientes",
    "pick_rows": "Filas de pick",
    "prelock_status": "Estado prebloqueo",
    "prediction": "Seleccion",
    "price_value_label": "Valor del precio",
    "profit_units": "Unidades de ganancia",
    "proof_hash": "Hash de prueba",
    "proof_id": "ID de prueba",
    "proof_status": "Estado de prueba",
    "public_action": "Accion publica",
    "public_confidence": "Confianza publica",
    "public_pick": "Seleccion publica",
    "public_reason": "Razon publica",
    "public_safe": "Seguro para publico",
    "publish_ready": "Listo para publicar",
    "pushes": "Pushes",
    "recommended_action": "Accion recomendada",
    "report_lane": "Carril de reporte",
    "report_lane_v2": "Carril de reporte v2",
    "research_lock_blockers": "Bloqueos de investigacion",
    "research_lock_ready": "Listo para bloqueo de investigacion",
    "result": "Resultado",
    "result_status": "Estado de resultado",
    "risk_preference": "Preferencia de riesgo",
    "roi": "ROI",
    "row_level": "Nivel de fila",
    "rows": "Filas",
    "sample_size": "Tamano de muestra",
    "scanner_strength_score": "Puntaje de fuerza del scanner",
    "scope": "Alcance",
    "source": "Fuente",
    "source_file": "Archivo fuente",
    "sport": "Deporte",
    "sport_key": "Clave de deporte",
    "stake_blocked": "Stake bloqueado",
    "stake_reason": "Razon de stake",
    "stake_units": "Unidades de stake",
    "status": "Estado",
    "suggested_stake_units": "Unidades de stake sugeridas",
    "suggestion": "Sugerencia",
    "unique_event_id": "ID de evento unico",
    "visibility": "Visibilidad",
    "voids": "Voids",
    "why_it_matters": "Por que importa",
    "win_rate": "Tasa de acierto",
    "winner": "Ganador",
    "wins": "Victorias",
    "workspace_id": "ID del espacio de trabajo",
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
    "ara_latest_predictions": "Predicciones recientes ARA",
    "odds_lock_pro_locked_rows": "Filas bloqueadas de Odds Lock Pro",
    "pro_predictor_high_confidence_rows": "Filas de alta confianza de Predictor Pro",
    "pro_predictor_latest_rows": "Filas recientes de Predictor Pro",
    "public_proof_dashboard_refresh_rows": "Filas para refrescar dashboard publico",
    "what_are_the_odds_latest_rows": "Filas recientes de revision de cuotas",
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
    "spreads": "hándicaps",
    "spread": "hándicap",
    "moneyline": "ganador",
    "team_total": "total del equipo",
    "game_total": "total del partido",
    "price_watch_research": "Seguimiento de precio / investigación",
    "research_track_for_learning": "Investigación / seguimiento para aprendizaje",
    "research_learning": "Investigación / aprendizaje",
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
    "live_repairs": "reparaciones en vivo",
    "tgrm_repair_activation": "activacion de reparacion TGRM",
    "full_rye_repair_activation": "activacion completa de reparacion RYE",
    "hidden_value_score_activation": "activacion de Hidden Value Score",
    "confidence_calibration_activation": "activacion de calibracion de confianza",
    "live_pick_filtering": "filtrado de picks en vivo",
    "live_model_mutation": "mutacion del modelo en vivo",
    "learning_page_live_model_updates": "actualizaciones en vivo del modelo desde Learning Page",
    "automatic_confidence_adjustment": "ajuste automatico de confianza",
    "automatic_bet_tier_changes": "cambios automaticos de nivel de apuesta",
    "production_repair_candidates": "candidatos de reparacion en produccion",
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
    "key",
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


def _column_label(column: Any) -> str:
    raw = str(column)
    if raw in COLUMN_LABELS_ES:
        return COLUMN_LABELS_ES[raw]
    return raw.replace("_", " ")


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
    if frame is None:
        return frame
    if not is_spanish(language):
        return frame
    out = frame.copy()
    if not out.empty:
        for column in out.columns:
            if out[column].dtype == object:
                out[column] = out[column].map(lambda item, col=column: localize_cell(item, language, str(col)))
    return out.rename(columns={column: _column_label(column) for column in out.columns})


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
