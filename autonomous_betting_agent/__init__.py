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


def _install_bilingual_sidebar() -> None:
    """Install one global Streamlit language, sidebar, table, and CSV translator."""
    try:
        import io
        import pandas as pd
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return

    if getattr(st, "_aba_bilingual_sidebar_installed", False):
        return
    st._aba_bilingual_sidebar_installed = True

    tools: tuple[tuple[str, str, str], ...] = (
        ("Pro Predictor", "Predictor Pro", "pages/pro_predictor.py"),
        ("What Are the Odds", "Qué dicen las cuotas", "pages/what_are_the_odds.py"),
        ("Learning Memory", "Memoria de Aprendizaje", "pages/learn_memory.py"),
        ("Pro Intelligence Scanner", "Escáner Pro de Inteligencia", "pages/pro_intelligence_scanner.py"),
        ("Weather Intelligence", "Inteligencia de Clima", "pages/weather_intelligence.py"),
        ("Accuracy Tracker", "Rastreador de Precisión", "pages/accuracy_tracker.py"),
        ("Live Market Scanner", "Escáner de Mercado en Vivo", "pages/live_scanner.py"),
        ("US Pro Team Market Finder", "Buscador de Equipos Pro USA", "pages/us_pro_team_market_finder.py"),
        ("Mexico Team Market Finder", "Buscador de Equipos Mexicanos", "pages/mexico_team_market_finder.py"),
        ("College Team Market Finder", "Buscador de Equipos Universitarios", "pages/college_team_market_finder.py"),
        ("Combat Sports Fighter Finder", "Buscador de Peleadores", "pages/combat_sports_fighter_finder.py"),
        ("NBA Playoffs Predictor", "Predictor de Playoffs NBA", "pages/nba_playoffs_predictor.py"),
        ("Self Learning Engine", "Motor de Aprendizaje", "pages/self_learning_engine.py"),
    )
    notes_en = (
        "Primary tools: Pro Predictor, What Are the Odds, Learning Memory, Pro Intelligence Scanner, Weather Intelligence.",
        "Likely overlap: Live Market Scanner is a simpler version of Pro Intelligence Scanner.",
        "Likely overlap: Self Learning Engine is older than Learning Memory.",
        "Specialized tools: US, Mexico, College, Combat, and NBA pages are focused finders, not full replacements for Pro Predictor.",
    )
    notes_es = (
        "Herramientas principales: Predictor Pro, Qué dicen las cuotas, Memoria de Aprendizaje, Escáner Pro de Inteligencia, Inteligencia de Clima.",
        "Posible duplicado: Escáner de Mercado en Vivo es una versión más simple del Escáner Pro de Inteligencia.",
        "Posible duplicado: Motor de Aprendizaje es anterior a Memoria de Aprendizaje.",
        "Herramientas especializadas: las páginas USA, México, Universitario, Combate y NBA son buscadores enfocados, no reemplazos completos del Predictor Pro.",
    )

    es_columns = {
        "event": "evento",
        "game": "partido",
        "match": "partido",
        "sport": "deporte",
        "league": "liga",
        "start": "inicio",
        "event_date": "fecha_evento",
        "latest_event_date_filter": "filtro_fecha_maxima",
        "market_type": "tipo_mercado",
        "market": "mercado",
        "prediction": "pronostico",
        "pick": "seleccion",
        "favorite": "favorito",
        "outcome": "resultado",
        "result": "resultado",
        "winner": "ganador",
        "actual_winner": "ganador_real",
        "probability": "probabilidad",
        "model_probability": "probabilidad_modelo",
        "implied_probability": "probabilidad_implicita",
        "market_probability": "probabilidad_mercado",
        "market_probability_value": "valor_probabilidad_mercado",
        "final_probability": "probabilidad_final",
        "final_probability_value": "valor_probabilidad_final",
        "calibrated_probability": "probabilidad_calibrada",
        "predicted_probability": "probabilidad_pronosticada",
        "avg_predicted": "promedio_pronosticado",
        "actual_hit_rate": "tasa_acierto_real",
        "actual_win_rate": "tasa_victoria_real",
        "hit_rate": "tasa_acierto",
        "brier_score": "puntaje_brier",
        "best_price": "mejor_cuota",
        "avg_price": "cuota_promedio",
        "average_price": "cuota_promedio",
        "odds": "cuotas",
        "price": "cuota",
        "books": "casas",
        "bookmakers": "casas",
        "best_book": "mejor_casa",
        "best_bookmaker": "mejor_casa",
        "estimated_ev": "ev_estimado",
        "estimated_ev_value": "valor_ev_estimado",
        "estimated_ev_decimal": "ev_estimado_decimal",
        "estimated_score": "marcador_estimado",
        "score_source": "fuente_marcador",
        "score_note": "nota_marcador",
        "prop_type": "tipo_prop",
        "prop_estimate": "estimacion_prop",
        "source": "fuente",
        "note": "nota",
        "confidence": "confianza",
        "read": "lectura",
        "classification": "clasificacion",
        "quality": "calidad",
        "reliability": "confiabilidad",
        "reliability_score": "puntaje_confiabilidad",
        "target_70_mode": "modo_objetivo_70",
        "target_70_quality_score": "puntaje_calidad_objetivo_70",
        "target_70_rejection_reason": "razon_rechazo_objetivo_70",
        "target_probability_band_low": "banda_objetivo_baja",
        "target_probability_band_high": "banda_objetivo_alta",
        "api_coverage_score": "puntaje_cobertura_api",
        "api_coverage_percent": "porcentaje_cobertura_api",
        "api_sources_used": "apis_usadas",
        "api_sources_missing": "apis_faltantes",
        "configured_api_sources": "apis_configuradas",
        "all_configured_apis_used": "todas_las_apis_configuradas_usadas",
        "sportsdataio_status": "estado_sportsdataio",
        "weatherapi_status": "estado_weatherapi",
        "weather_location": "ubicacion_clima",
        "weather_reason": "razon_clima",
        "weather_flag": "alerta_clima",
        "weather_risk_score": "puntaje_riesgo_clima",
        "venue_name": "nombre_sede",
        "venue_name_fifa": "nombre_sede_fifa",
        "venue_city": "ciudad_sede",
        "venue_state": "estado_sede",
        "venue_country": "pais_sede",
        "venue_source": "fuente_sede",
        "venue_note": "nota_sede",
        "sede_fifa": "sede_fifa",
        "estadio_real": "estadio_real",
        "ciudad_area": "ciudad_area",
        "pais_sede": "pais_sede",
        "fuente_sede": "fuente_sede",
        "area_type": "tipo_area",
        "group_value": "valor_grupo",
        "records": "registros",
        "actual_minus_predicted": "real_menos_pronosticado",
        "smoothed_hit_rate": "tasa_suavizada",
        "smoothed_edge": "ventaja_suavizada",
        "memory_type": "tipo_memoria",
        "importance": "importancia",
        "action": "accion",
    }
    es_values = {
        "HIGH": "ALTA",
        "MEDIUM": "MEDIA",
        "LOW": "BAJA",
        "High": "Alta",
        "Medium": "Media",
        "Low": "Baja",
        "True": "Verdadero",
        "False": "Falso",
        "true": "verdadero",
        "false": "falso",
        "yes": "sí",
        "no": "no",
        "won": "ganó",
        "lost": "perdió",
        "unknown": "pendiente",
        "pending": "pendiente",
        "used": "usado",
        "not_supported_sport": "deporte_no_compatible",
        "not_configured": "no_configurado",
        "not_available_from_feed": "no_disponible_en_feed",
        "no_location": "sin_ubicacion",
        "model_estimate": "estimacion_modelo",
        "csv_market_or_field": "mercado_o_campo_csv",
        "csv_field": "campo_csv",
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
        "Official sportsbook props are used when the CSV contains those markets.": "Los props oficiales de casa de apuesta se usan cuando el CSV contiene esos mercados.",
        "Estimated from probability, sport type, and any total/spread fields found.": "Estimado con probabilidad, tipo de deporte y cualquier total/spread encontrado.",
        "No official round prop found": "No se encontró prop oficial de round",
        "Home-run market/field was detected in the CSV.": "Se detectó mercado/campo de home run en el CSV.",
        "Detected from uploaded CSV column.": "Detectado desde una columna del CSV subido.",
        "Venue was not provided by the available API sources.": "La sede no fue proporcionada por las APIs disponibles.",
        "Neutral-site FIFA venue override matched by event teams and start time.": "Sede neutral FIFA identificada por equipos y hora de inicio.",
        "Venue inferred from SportsDataIO home-team metadata; neutral-site events may differ.": "Sede inferida desde metadatos del equipo local en SportsDataIO; eventos en sede neutral pueden diferir.",
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
        text = str(value)
        text = es_values.get(text, text)
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
            st.markdown("### Limpieza de herramientas" if lang == "Español" else "### Tool cleanup")
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


_install_bilingual_sidebar()

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
