from __future__ import annotations

from autonomous_betting_agent.ui_i18n import COLUMN_LABELS_ES, VALUE_COLUMNS, VALUE_LABELS_ES

ADVISORY_COLUMN_LABELS_ES = {
    "advisory_raw_implied_probability": "Probabilidad implicita cruda asesoría",
    "advisory_no_vig_implied_probability": "Probabilidad implicita sin vig asesoría",
    "advisory_market_hold": "Hold de mercado asesoría",
    "advisory_market_hold_pct": "Hold de mercado % asesoría",
    "advisory_raw_edge": "Ventaja cruda asesoría",
    "advisory_no_vig_edge": "Ventaja sin vig asesoría",
    "advisory_raw_EV": "EV crudo asesoría",
    "advisory_best_price_EV": "EV mejor precio asesoría",
    "advisory_no_vig_value_ratio": "Ratio valor sin vig asesoría",
    "advisory_fair_odds": "Cuota justa asesoría",
    "advisory_target_odds": "Cuota objetivo asesoría",
    "advisory_current_decimal_odds": "Cuota decimal actual asesoría",
    "advisory_best_available_decimal_odds": "Mejor cuota disponible asesoría",
    "advisory_best_available_sportsbook": "Mejor sportsbook asesoría",
    "advisory_line_shopping_gain": "Ganancia line-shopping asesoría",
    "advisory_line_shopping_gain_pct": "Ganancia line-shopping % asesoría",
    "advisory_best_price_no_vig_edge": "Ventaja sin vig al mejor precio asesoría",
    "advisory_stale_line_status": "Estado linea asesoría",
    "advisory_stale_line_reason": "Razon linea asesoría",
    "advisory_market_completeness_status": "Estado mercado completo asesoría",
    "advisory_duplicate_event_status": "Estado duplicado evento asesoría",
    "advisory_duplicate_event_reason": "Razon duplicado evento asesoría",
    "advisory_conflict_status": "Estado conflicto asesoría",
    "advisory_conflict_reason": "Razon conflicto asesoría",
    "advisory_playable_status": "Estado jugable asesoría",
    "advisory_playable_reason": "Razon jugable asesoría",
    "advisory_prediction_only_reason": "Razon solo prediccion asesoría",
    "advisory_odds_value_tier": "Nivel valor odds asesoría",
    "advisory_odds_math_mode": "Modo matematica odds asesoría",
}

ADVISORY_VALUE_LABELS_ES = {
    "PLAYABLE_PLUS_EV": "JUGABLE +EV",
    "WATCHLIST_VALUE": "VALOR EN WATCHLIST",
    "PREDICTION_ONLY_NOT_PLUS_EV": "SOLO PREDICCION NO +EV",
    "BLOCKED_NEGATIVE_EV": "BLOQUEADO EV NEGATIVO",
    "BLOCKED_STALE_LINE": "BLOQUEADO LINEA VIEJA",
    "BLOCKED_DUPLICATE_CONFLICT": "BLOQUEADO CONFLICTO DUPLICADO",
    "BLOCKED_INCOMPLETE_MARKET": "BLOQUEADO MERCADO INCOMPLETO",
    "BLOCKED_MISSING_ODDS": "BLOQUEADO SIN CUOTAS",
    "BLOCKED_LOW_MODEL_CONFIDENCE": "BLOQUEADO BAJA CONFIANZA MODELO",
    "BLOCKED_WEAK_SHADOW_SAMPLE": "BLOQUEADO MUESTRA SHADOW DEBIL",
    "BLOCKED_INVALID_PROBABILITY": "BLOQUEADO PROBABILIDAD INVALIDA",
    "COMPLETE_MARKET": "MERCADO COMPLETO",
    "INCOMPLETE_MARKET": "MERCADO INCOMPLETO",
    "FRESH": "FRESCA",
    "STALE": "VIEJA",
    "UNKNOWN": "DESCONOCIDO",
    "EVENT_STARTED": "EVENTO INICIADO",
    "HISTORICAL_ROW": "FILA HISTORICA",
    "UNIQUE_EVENT": "EVENTO UNICO",
    "MULTIPLE_ROWS_SAME_EVENT": "MULTIPLES FILAS MISMO EVENTO",
    "EXACT_DUPLICATE": "DUPLICADO EXACTO",
    "NO_CONFLICT": "SIN CONFLICTO",
    "CONFLICTING_MARKET_SIDES": "LADOS DE MERCADO EN CONFLICTO",
    "ADVISORY_ONLY": "SOLO ASESORIA",
    "PLAYABLE": "JUGABLE",
    "WATCHLIST": "WATCHLIST",
    "PREDICTION_ONLY": "SOLO PREDICCION",
    "BLOCKED": "BLOQUEADO",
}


def register_advisory_i18n() -> None:
    COLUMN_LABELS_ES.update(ADVISORY_COLUMN_LABELS_ES)
    VALUE_LABELS_ES.update(ADVISORY_VALUE_LABELS_ES)
    VALUE_COLUMNS.update({
        "advisory_odds_math_mode",
        "advisory_playable_status",
        "advisory_playable_reason",
        "advisory_prediction_only_reason",
        "advisory_odds_value_tier",
        "advisory_stale_line_status",
        "advisory_stale_line_reason",
        "advisory_market_completeness_status",
        "advisory_duplicate_event_status",
        "advisory_duplicate_event_reason",
        "advisory_conflict_status",
        "advisory_conflict_reason",
    })


def install_upload_source_patch() -> None:
    try:
        from autonomous_betting_agent.proof_upload_source_patch import install
    except Exception:
        return
    install()


register_advisory_i18n()
install_upload_source_patch()
