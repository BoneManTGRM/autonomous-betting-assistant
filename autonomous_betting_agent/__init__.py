"""Autonomous Betting Agent.

A standalone, research-only sports analytics agent derived from the ARA/TGRM
architecture. It estimates probabilities, explains evidence, tracks uncertainty,
learns probability calibration from graded results, tracks edge/profit/CLV, and
supports backtesting.
"""

from __future__ import annotations

from typing import Any

from .learning import GradedPrediction, ProbabilityCalibrator, fit_probability_calibrator, parse_graded_csv
from .models import EventResearchInput, PredictionResult, TeamSnapshot
from .researcher import AutonomousBettingAgent
from .tgrm import TGRMLoop
from .tracking import PredictionLedgerRow, SelectionDecision, SelectionPolicy, TrackingReport, choose_decision, summarize_tracking


def _install_streamlit_helpers() -> None:
    """Install one global Streamlit language selector, clean tool menu, table translator, and CSV translator."""
    try:
        import io
        import pandas as pd
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return

    if getattr(st, "_aba_streamlit_helpers_installed", False):
        return
    st._aba_streamlit_helpers_installed = True

    tools: tuple[tuple[str, str, str], ...] = (
        ("Pro Predictor", "Predictor Pro", "pages/pro_predictor.py"),
        ("Scanner Pro", "Scanner Pro", "pages/scanner_pro.py"),
        ("What Are the Odds", "What Are the Odds", "pages/what_are_the_odds.py"),
        ("Learning Memory", "Memoria de Aprendizaje", "pages/learn_memory.py"),
    )
    notes_en = (
        "Clean workflow: Scanner Pro → Pro Predictor → What Are the Odds → Learning Memory.",
        "Use Scanner Pro for live market discovery.",
        "Use Pro Predictor for final all-sports prediction scoring.",
        "Use What Are the Odds for market/value review, CLV, loss autopsy, and lock-ready candidates.",
        "Use Learning Memory for durable training and saved model memory.",
    )
    notes_es = (
        "Flujo limpio: Scanner Pro → Predictor Pro → What Are the Odds → Memoria de Aprendizaje.",
        "Usa Scanner Pro para descubrir mercados en vivo.",
        "Usa Predictor Pro para la calificación final de predicciones en todos los deportes.",
        "Usa What Are the Odds para revisar mercado/valor, CLV, autopsia de pérdidas y candidatos listos para bloquear.",
        "Usa Memoria de Aprendizaje para entrenamiento duradero y memoria guardada del modelo.",
    )

    es_columns = {
        "event": "evento",
        "game": "partido",
        "match": "partido",
        "sport": "deporte",
        "league": "liga",
        "start": "inicio",
        "event_start_utc": "inicio_evento_utc",
        "prediction_timestamp": "hora_pronostico",
        "event_date": "fecha_evento",
        "market_type": "tipo_mercado",
        "market": "mercado",
        "prediction": "pronostico",
        "pick": "seleccion",
        "favorite": "favorito",
        "outcome": "resultado",
        "result": "resultado",
        "result_status": "estado_resultado",
        "probability": "probabilidad",
        "model_probability": "probabilidad_modelo",
        "model_probability_clean": "probabilidad_modelo_limpia",
        "market_probability": "probabilidad_mercado",
        "market_implied_probability": "probabilidad_implicita_mercado",
        "implied_probability": "probabilidad_implicita",
        "no_vig_implied_probability": "probabilidad_sin_margen",
        "market_hold": "margen_casa",
        "model_market_edge": "ventaja_modelo_mercado",
        "model_market_edge_percent": "ventaja_modelo_mercado_pct",
        "model_minus_implied": "modelo_menos_implicita",
        "model_minus_no_vig": "modelo_menos_sin_margen",
        "fair_decimal_price": "cuota_justa_decimal",
        "fair_american_price": "cuota_justa_americana",
        "computed_ev_decimal": "ev_calculado_decimal",
        "estimated_ev": "ev_estimado_original",
        "estimated_ev_decimal": "ev_estimado_decimal",
        "odds_quality_score": "puntaje_calidad_cuotas",
        "decision": "decision",
        "agent_decision": "decision_agente",
        "agent_score": "puntaje_agente",
        "decision_reason": "razon_decision",
        "decision_reasons": "razones_decision",
        "decision_signals": "senales_decision",
        "event_timing_status": "estado_tiempo_evento",
        "lock_ready": "listo_para_bloquear",
        "already_locked": "ya_bloqueado",
        "recommended_stake_units": "unidades_apuesta_recomendadas",
        "line_value_signal": "senal_valor_linea",
        "final_probability": "probabilidad_final",
        "final_probability_value": "valor_probabilidad_final",
        "confidence": "confianza",
        "confidence_tier": "nivel_confianza",
        "reliability_score": "puntaje_confiabilidad",
        "best_price": "mejor_cuota",
        "decimal_price": "cuota_decimal",
        "closing_decimal_price": "cuota_cierre_decimal",
        "bookmaker": "casa_apuestas",
        "books": "casas",
        "bookmaker_count": "numero_casas",
        "clv_signal": "senal_clv",
        "clv_percent": "clv_porcentaje",
        "beat_close": "supero_cierre",
        "estimated_score": "marcador_estimado",
        "score_source": "fuente_marcador",
        "score_note": "nota_marcador",
        "prop_type": "tipo_prop",
        "prop_estimate": "estimacion_prop",
        "source": "fuente",
        "source_file": "archivo_fuente",
        "odds_source": "fuente_cuotas",
        "note": "nota",
        "warning": "advertencia",
        "records": "registros",
        "actual_hit_rate": "tasa_acierto_real",
        "avg_predicted": "promedio_pronosticado",
        "smoothed_hit_rate": "tasa_suavizada",
        "smoothed_edge": "ventaja_suavizada",
        "resolved": "resueltos",
        "wins": "ganadas",
        "losses": "perdidas",
        "hit_rate": "tasa_acierto",
        "brier": "brier",
        "profit_units": "unidades_ganancia",
        "stake_units": "unidades_apostadas",
        "api_coverage_score": "puntaje_cobertura_api",
        "api_coverage_percent": "porcentaje_cobertura_api",
        "api_sources_used": "apis_usadas",
        "api_sources_missing": "apis_faltantes",
        "sportsdataio_status": "estado_sportsdataio",
        "weatherapi_status": "estado_weatherapi",
        "weather_location": "ubicacion_clima",
        "weather_reason": "razon_clima",
        "weather_flag": "alerta_clima",
        "weather_risk_score": "puntaje_riesgo_clima",
    }
    es_values = {
        "HIGH": "ALTA",
        "MEDIUM": "MEDIA",
        "LOW": "BAJA",
        "True": "Verdadero",
        "False": "Falso",
        "true": "verdadero",
        "false": "falso",
        "yes": "sí",
        "no": "no",
        "won": "ganó",
        "win": "ganó",
        "lost": "perdió",
        "loss": "perdió",
        "unknown": "pendiente",
        "pending": "pendiente",
        "used": "usado",
        "not_supported_sport": "deporte_no_compatible",
        "not_configured": "no_configurado",
        "not_available_from_feed": "no_disponible_en_feed",
        "model_estimate": "estimacion_modelo",
        "csv_market_or_field": "mercado_o_campo_csv",
        "csv_field": "campo_csv",
        "play_strong": "jugar_fuerte",
        "play_small": "jugar_pequeno",
        "watch_only": "solo_vigilar",
        "no_action": "sin_accion",
        "review_needed": "requiere_revision",
        "strong_candidate": "candidato_fuerte",
        "candidate": "candidato",
        "skip": "omitir",
        "positive": "positivo",
        "negative": "negativo",
        "neutral": "neutral",
        "missing": "faltante",
        "ready": "listo",
        "raise_trust": "subir_confianza",
        "lower_trust": "bajar_confianza",
        "watch": "vigilar",
    }
    es_phrases = {
        "outside": "fuera de",
        "band": "banda",
        "market probability below floor": "probabilidad de mercado debajo del piso",
        "not enough books": "no hay suficientes casas",
        "reliability below target": "confiabilidad debajo del objetivo",
        "price/probability mismatch": "desajuste precio/probabilidad",
        "EV below target": "EV debajo del objetivo",
        "API coverage below target": "cobertura API debajo del objetivo",
        "not all configured APIs used": "no se usaron todas las APIs configuradas",
        "duplicate event/pick": "evento/pronóstico duplicado",
        "not h2h": "no es h2h",
        "not high confidence": "no es confianza alta",
        "missing_model_probability": "falta_probabilidad_modelo",
        "missing_decimal_price": "falta_cuota_decimal",
        "missing_bookmaker": "falta_casa_apuestas",
        "missing_odds_source": "falta_fuente_cuotas",
        "historical_result_present": "resultado_historico_presente",
        "prediction_timestamp_not_before_start": "pronostico_no_fue_antes_del_inicio",
        "event_already_started": "evento_ya_inicio",
        "future_event_not_locked_yet": "evento_futuro_aun_no_bloqueado",
        "lock_ready": "listo_para_bloquear",
        "not_locked_yet": "aun_no_bloqueado",
        "positive_edge": "ventaja_positiva",
        "strong_edge": "ventaja_fuerte",
        "negative_edge": "ventaja_negativa",
        "edge_below_minimum": "ventaja_debajo_del_minimo",
        "low_field_coverage": "cobertura_de_datos_baja",
        "Estimated from probability, sport type, and any total/spread fields found.": "Estimado con probabilidad, tipo de deporte y cualquier total/spread encontrado.",
        "No official round prop found": "No se encontró prop oficial de round",
        "Home-run market/field was detected in the CSV.": "Se detectó mercado/campo de home run en el CSV.",
        "Detected from uploaded CSV column.": "Detectado desde una columna del CSV subido.",
        "Venue was not provided by the available API sources.": "La sede no fue proporcionada por las APIs disponibles.",
    }

    def query_language() -> str:
        try:
            value = st.query_params.get("lang", "")
            if isinstance(value, list):
                value = value[0] if value else ""
            if str(value).lower().startswith("es"):
                return "Español"
            if str(value).lower().startswith("en"):
                return "English"
        except Exception:
            pass
        return ""

    def language_value() -> str:
        if "global_language" not in st.session_state:
            st.session_state["global_language"] = query_language() or "English"
        return str(st.session_state.get("global_language", "English"))

    def save_language_query(value: str) -> None:
        try:
            st.query_params["lang"] = "es" if value == "Español" else "en"
        except Exception:
            pass

    def translate_value(value: Any) -> Any:
        if language_value() != "Español" or value is None:
            return value
        text = es_values.get(str(value), str(value))
        for source, target in es_phrases.items():
            text = text.replace(source, target)
        return text

    def translate_frame(data: Any) -> Any:
        if language_value() != "Español" or not isinstance(data, pd.DataFrame):
            return data
        frame = data.copy()
        for col in frame.columns:
            if frame[col].dtype == object:
                frame[col] = frame[col].map(translate_value)
        return frame.rename(columns={str(col): es_columns.get(str(col), str(col)) for col in frame.columns})

    def translate_csv_text(data: Any) -> Any:
        if language_value() != "Español":
            return data
        try:
            if isinstance(data, bytes):
                text = data.decode("utf-8")
                was_bytes = True
            elif isinstance(data, str):
                text = data
                was_bytes = False
            else:
                return data
            translated = translate_frame(pd.read_csv(io.StringIO(text))).to_csv(index=False)
            return translated.encode("utf-8") if was_bytes else translated
        except Exception:
            return data

    def render_nav(lang: str) -> None:
        with st.sidebar:
            st.markdown("---")
            st.markdown("### Herramientas" if lang == "Español" else "### Tools")
            for english, spanish, path in tools:
                label = spanish if lang == "Español" else english
                try:
                    st.page_link(path, label=label)
                except Exception:
                    st.caption(label)
            st.markdown("---")
            st.markdown("### Flujo" if lang == "Español" else "### Workflow")
            for note in (notes_es if lang == "Español" else notes_en):
                st.caption(note)

    real_set_page_config = st.set_page_config
    real_st_selectbox = st.selectbox
    real_dg_selectbox = DeltaGenerator.selectbox
    real_st_dataframe = st.dataframe
    real_dg_dataframe = DeltaGenerator.dataframe
    real_st_table = st.table
    real_dg_table = DeltaGenerator.table
    real_st_download_button = st.download_button
    real_dg_download_button = DeltaGenerator.download_button

    def patched_set_page_config(*args: Any, **kwargs: Any) -> Any:
        return real_set_page_config(*args, **kwargs)

    def language_selectbox(label: Any, options: Any, args: tuple[Any, ...], kwargs: dict[str, Any], original: Any, target: Any = None) -> Any:
        label_text = str(label or "").lower()
        is_language = "language" in label_text or "idioma" in label_text or "translate page" in label_text
        opts = list(options)
        if is_language and "English" in opts and "Español" in opts:
            kwargs = dict(kwargs)
            kwargs["key"] = "global_language"
            current = language_value()
            kwargs["index"] = opts.index(current) if current in opts else 0
            selector_label = "Idioma" if current == "Español" else "Language"
            if target is None:
                value = real_dg_selectbox(st.sidebar, selector_label, opts, *args, **kwargs)
            else:
                value = original(target, selector_label, opts, *args, **kwargs)
            save_language_query(str(value))
            render_nav(str(value))
            return value
        if target is None:
            return original(label, options, *args, **kwargs)
        return original(target, label, options, *args, **kwargs)

    def patched_st_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        return language_selectbox(label, options, args, kwargs, real_st_selectbox)

    def patched_dg_selectbox(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        return language_selectbox(label, options, args, kwargs, real_dg_selectbox, target=self)

    def patched_st_dataframe(data: Any = None, *args: Any, **kwargs: Any) -> Any:
        return real_st_dataframe(translate_frame(data), *args, **kwargs)

    def patched_dg_dataframe(self: Any, data: Any = None, *args: Any, **kwargs: Any) -> Any:
        return real_dg_dataframe(self, translate_frame(data), *args, **kwargs)

    def patched_st_table(data: Any = None, *args: Any, **kwargs: Any) -> Any:
        return real_st_table(translate_frame(data), *args, **kwargs)

    def patched_dg_table(self: Any, data: Any = None, *args: Any, **kwargs: Any) -> Any:
        return real_dg_table(self, translate_frame(data), *args, **kwargs)

    def _translate_download_payload(args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[tuple[Any, ...], dict[str, Any]]:
        kwargs = dict(kwargs)
        file_name = str(kwargs.get("file_name", ""))
        mime = str(kwargs.get("mime", ""))
        if language_value() != "Español" or not (file_name.endswith(".csv") or mime == "text/csv"):
            return args, kwargs
        if "data" in kwargs:
            kwargs["data"] = translate_csv_text(kwargs["data"])
            return args, kwargs
        if args:
            mutable = list(args)
            mutable[0] = translate_csv_text(mutable[0])
            return tuple(mutable), kwargs
        return args, kwargs

    def patched_st_download_button(label: Any, *args: Any, **kwargs: Any) -> Any:
        args, kwargs = _translate_download_payload(args, kwargs)
        return real_st_download_button(label, *args, **kwargs)

    def patched_dg_download_button(self: Any, label: Any, *args: Any, **kwargs: Any) -> Any:
        args, kwargs = _translate_download_payload(args, kwargs)
        return real_dg_download_button(self, label, *args, **kwargs)

    st.set_page_config = patched_set_page_config
    st.selectbox = patched_st_selectbox
    st.dataframe = patched_st_dataframe
    st.table = patched_st_table
    st.download_button = patched_st_download_button
    DeltaGenerator.selectbox = patched_dg_selectbox
    DeltaGenerator.dataframe = patched_dg_dataframe
    DeltaGenerator.table = patched_dg_table
    DeltaGenerator.download_button = patched_dg_download_button


_install_streamlit_helpers()

__all__ = [
    "AutonomousBettingAgent",
    "EventResearchInput",
    "GradedPrediction",
    "PredictionLedgerRow",
    "PredictionResult",
    "ProbabilityCalibrator",
    "SelectionDecision",
    "SelectionPolicy",
    "TeamSnapshot",
    "TGRMLoop",
    "TrackingReport",
    "choose_decision",
    "fit_probability_calibrator",
    "parse_graded_csv",
    "summarize_tracking",
]
