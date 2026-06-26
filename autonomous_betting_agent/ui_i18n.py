from __future__ import annotations

import re
from typing import Any

import pandas as pd

from autonomous_betting_agent.report_product_layer import event_text, pick_text, sport_text, team_label, value_text


COLUMN_LABELS_ES = {
    "active_list_id": "id_lista_activa",
    "actual_win_rate": "acierto_real",
    "avg_predicted": "promedio_predicho",
    "beat_close": "superó_cierre",
    "bookmaker": "casa",
    "bucket": "rango",
    "client_report_ready": "listo_reporte_cliente",
    "closing_odds": "cuota_cierre",
    "confidence": "confianza",
    "consumer_action": "acción_cliente",
    "data_issue_reason": "motivo_problema_datos",
    "decimal_price": "cuota_decimal",
    "edge": "ventaja",
    "event": "evento",
    "event_level": "nivel_evento",
    "event_name": "evento",
    "event_pick_index": "índice_pick_evento",
    "event_start_time": "inicio_evento",
    "event_start_utc": "inicio_utc",
    "expected_value_per_unit": "valor_esperado_por_unidad",
    "expected_win_rate": "acierto_esperado",
    "final_score": "marcador_final",
    "grade": "calificación",
    "has_proof_hash": "tiene_hash_prueba",
    "ledger_batch_id": "id_lote_ledger",
    "ledger_type": "tipo_ledger",
    "learning_ready": "listo_aprendizaje",
    "learning_status": "estado_aprendizaje",
    "line_point": "línea",
    "locked_at_utc": "bloqueado_utc",
    "losses": "derrotas",
    "market": "mercado",
    "market_probability": "probabilidad_mercado",
    "market_type": "tipo_mercado",
    "model_market_edge": "ventaja_modelo_mercado",
    "model_probability": "probabilidad_modelo",
    "model_probability_source": "fuente_probabilidad_modelo",
    "odds": "cuota",
    "odds_audit_status": "estado_auditoría_cuotas",
    "odds_band": "rango_cuota",
    "odds_source": "fuente_cuotas",
    "odds_verified": "cuota_verificada",
    "official_publish_ready": "listo_publicación_oficial",
    "official_status_label": "estado_oficial",
    "page": "página",
    "pending": "pendientes",
    "pick_rows": "filas_pick",
    "prediction": "selección",
    "profit_units": "unidades_ganancia",
    "proof_hash": "hash_prueba",
    "proof_id": "id_prueba",
    "public_action": "acción_pública",
    "public_pick": "selección_pública",
    "public_safe": "segura_público",
    "publish_ready": "listo_publicar",
    "pushes": "pushes",
    "recommended_action": "acción_recomendada",
    "report_lane": "carril_reporte",
    "report_lane_v2": "carril_reporte_v2",
    "result": "resultado",
    "result_status": "estado_resultado",
    "roi": "ROI",
    "row_level": "nivel_fila",
    "rows": "filas",
    "sample_size": "tamaño_muestra",
    "scope": "alcance",
    "source": "fuente",
    "source_file": "archivo_fuente",
    "sport": "deporte",
    "status": "estado",
    "suggested_stake_units": "unidades_stake_sugeridas",
    "unique_event_id": "id_evento_único",
    "voids": "voids",
    "win_rate": "tasa_acierto",
    "winner": "ganador",
    "wins": "victorias",
    "workspace_id": "id_workspace",
}

VALUE_LABELS_ES = {
    "row_level": "nivel de fila",
    "event_level": "nivel de evento",
    "official": "oficial",
    "research": "investigación",
    "client": "cliente",
    "quarantine": "cuarentena",
    "learning_only": "solo aprendizaje",
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
    "public": "público",
    "persistent_proof_ledger": "ledger de prueba persistente",
    "none": "ninguna",
    "unknown": "desconocido",
    "strong_learning_memory": "memoria de aprendizaje fuerte",
    "medium_learning_memory": "memoria de aprendizaje media",
    "weak_learning_memory": "memoria de aprendizaje débil",
    "fallback_probability": "probabilidad fallback",
    "price_implied_probability": "probabilidad implícita por cuota",
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
    "ready_for_lock_or_learning": "listo para bloqueo o aprendizaje",
    "lock_first": "bloquear primero",
    "fifa_world_cup": "Copa Mundial FIFA",
    "super_league_china": "Superliga - China",
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
    return tr(language, "Upload control text may be controlled by Streamlit.", "El texto interno del botón de carga puede depender de Streamlit.")


def render_upload_css(st_module, language: str | None) -> None:
    """Best-effort Spanish styling for Streamlit's built-in file uploader.

    Streamlit owns the internal file-uploader button text. This CSS only runs in
    Spanish mode and visually replaces the default button label where Streamlit's
    current DOM supports it.
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
