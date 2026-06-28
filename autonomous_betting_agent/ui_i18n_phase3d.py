from __future__ import annotations

from autonomous_betting_agent import ui_i18n

PHASE3D_COLUMN_LABELS_ES = {
    "repair_key": "Clave de reparacion",
    "first_seen_utc": "Visto por primera vez UTC",
    "last_seen_utc": "Visto por ultima vez UTC",
    "times_seen": "Veces detectado",
    "times_shadow_tested": "Veces probado en Shadow",
    "times_rejected": "Veces rechazado",
    "times_manual_review_eligible": "Veces elegible para revision manual",
    "times_data_blocked": "Veces bloqueado por datos",
    "times_watchlist": "Veces en lista de observacion",
    "total_sample_size": "Tamano de muestra total",
    "total_completed_rows_used": "Filas completadas totales",
    "avg_ROI_delta": "Cambio ROI promedio",
    "median_ROI_delta": "Cambio ROI mediano",
    "best_ROI_delta": "Mejor cambio ROI",
    "worst_ROI_delta": "Peor cambio ROI",
    "avg_profit_units_delta": "Cambio promedio en unidades de ganancia",
    "total_profit_units_delta": "Cambio total en unidades de ganancia",
    "avg_losses_delta": "Cambio promedio de derrotas",
    "total_avoided_losses": "Derrotas evitadas totales",
    "avg_CLV_delta": "Cambio CLV promedio",
    "CLV_sample_size_total": "Muestra CLV total",
    "overfit_risk_latest": "Riesgo de sobreajuste reciente",
    "confidence_level_latest": "Nivel de confianza reciente",
    "latest_decision": "Decision mas reciente",
    "latest_decision_reason": "Razon mas reciente",
    "memory_status": "Estado de memoria",
    "manual_status": "Estado manual",
    "manual_note": "Nota manual",
    "reviewer": "Revisor",
    "manual_updated_at_utc": "Revision manual actualizada UTC",
    "eligible_for_phase4_lockbox": "Elegible para lockbox Fase 4",
    "manual_review_enabled": "Revision manual activada",
    "phase4_lockbox_status": "Estado lockbox Fase 4",
    "automatic_live_promotion": "Promocion automatica en vivo",
    "event_type": "Tipo de evento",
    "created_at_utc": "Creado UTC",
    "rows_added": "Filas agregadas",
    "section": "Seccion",
    "observed_at_utc": "Observado UTC",
}

PHASE3D_VALUE_LABELS_ES = {
    "new": "nuevo",
    "keep_testing": "seguir probando",
    "promising": "prometedor",
    "rejected": "rechazado",
    "manual_approved_for_future": "aprobado manualmente para futuro",
    "phase4_lockbox_candidate": "candidato lockbox Fase 4",
    "data_blocked": "bloqueado por datos",
    "clear_manual_decision": "borrar decision manual",
    "manual_review_required": "requiere revision manual",
    "preparation_only": "solo preparacion",
    "automatic_live_promotion_forbidden": "promocion automatica en vivo prohibida",
    "phase3c_saved_to_memory": "Fase 3C guardada en memoria",
    "manual_review_decision": "decision de revision manual",
    "repair_memory_summary": "resumen de Repair Memory",
    "phase4_lockbox_candidate_detected": "candidato lockbox Fase 4 detectado",
    "phase_3d_repair_memory": "Fase 3D Repair Memory",
    "repair_memory_manual_review_gate": "Repair Memory + compuerta de revision manual",
    "enabled": "activado",
}

PHASE3D_VALUE_COLUMNS = {
    "memory_status",
    "manual_status",
    "latest_decision",
    "latest_decision_reason",
    "event_type",
    "automatic_live_promotion",
    "phase4_lockbox_status",
    "manual_review_enabled",
}


def apply_phase3d_i18n() -> None:
    ui_i18n.COLUMN_LABELS_ES.update(PHASE3D_COLUMN_LABELS_ES)
    ui_i18n.VALUE_LABELS_ES.update(PHASE3D_VALUE_LABELS_ES)
    ui_i18n.VALUE_COLUMNS.update(PHASE3D_VALUE_COLUMNS)


apply_phase3d_i18n()
