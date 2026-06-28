from __future__ import annotations

from pathlib import Path

import pandas as pd

from autonomous_betting_agent.sidebar_nav import _sidebar_language_label, _sidebar_language_option, normalize_language
from autonomous_betting_agent.ui_i18n import localize_dataframe, localize_options, localize_value


def test_spanish_core_values_translate() -> None:
    assert localize_value("A_top_candidate", "es") == "Nivel A - candidato fuerte"
    assert localize_value("B_high_confidence_test", "es") == "Nivel B - prueba de alta confianza"
    assert localize_value("learning_candidate", "es") == "candidata de aprendizaje"
    assert localize_value("research_play", "es") == "jugada de investigacion"
    assert localize_value("private", "es") == "privado"
    assert localize_value("public", "es") == "publico"
    assert localize_value("trial", "es") == "prueba"
    assert localize_value("data_blocker", "es") == "bloqueador de datos"
    assert localize_value("no_play", "es") == "no jugar"


def test_spanish_dataframe_display_translates_columns_and_cells() -> None:
    frame = pd.DataFrame([
        {
            "confidence_bucket": "A_top_candidate",
            "confidence_risk_score": 1,
            "sample_size": 50,
            "wins": 38,
            "losses": 12,
            "win_rate": 0.76,
            "market_type": "moneyline",
            "model_probability_bucket": "research_play",
            "report_lane_v2": "learning_candidate",
            "visibility": "private",
        }
    ])
    out = localize_dataframe(frame, "es")
    assert "Rango de confianza" in out.columns
    assert "Riesgo de confianza" in out.columns
    assert "Tamano de muestra" in out.columns
    assert "Victorias" in out.columns
    assert "Derrotas" in out.columns
    assert "Tasa de acierto" in out.columns
    assert "Tipo de mercado" in out.columns
    assert "Rango de probabilidad del modelo" in out.columns
    assert "Carril de reporte v2" in out.columns
    assert out.loc[0, "Rango de confianza"] == "Nivel A - candidato fuerte"
    assert out.loc[0, "Tipo de mercado"] == "ganador"
    assert out.loc[0, "Rango de probabilidad del modelo"] == "jugada de investigacion"
    assert out.loc[0, "Carril de reporte v2"] == "candidata de aprendizaje"
    assert out.loc[0, "Visibilidad"] == "privado"


def test_empty_spanish_dataframe_columns_localize() -> None:
    frame = pd.DataFrame(columns=["event", "event_id", "sport", "sport_key", "event_start_utc"])
    out = localize_dataframe(frame, "es")
    assert list(out.columns) == ["Evento", "ID de evento", "Deporte", "Clave de deporte", "Inicio UTC"]


def test_storage_keys_localize_for_diagnostics_tables() -> None:
    frame = pd.DataFrame([{"workspace_id": "test_01", "key": "pro_predictor_high_confidence_rows", "loaded_rows": 148, "disk_rows": 0, "github_rows": 148}])
    out = localize_dataframe(frame, "es")
    assert out.loc[0, "Clave"] == "Filas de alta confianza de Predictor Pro"
    assert "ID del espacio de trabajo" in out.columns
    assert "Filas cargadas" in out.columns


def test_english_mode_and_option_values_are_stable() -> None:
    frame = pd.DataFrame([{"confidence_bucket": "A_top_candidate", "visibility": "private"}])
    assert localize_value("A_top_candidate", "en") == "A_top_candidate"
    assert localize_dataframe(frame, "en").equals(frame)
    display, mapping = localize_options(["private", "public"], "es")
    assert display == ["privado", "publico"]
    assert mapping["privado"] == "private"
    assert mapping["publico"] == "public"


def test_sidebar_language_selector_behavior() -> None:
    source = Path("autonomous_betting_agent/sidebar_nav.py").read_text(encoding="utf-8")
    assert "_sidebar_language_label(language)" in source
    assert "SIDEBAR_RADIO_LEGACY_TEST_MARKER" not in source
    assert _sidebar_language_label("Español") == "Idioma"
    assert _sidebar_language_option("English", "es") == "Inglés"
    assert _sidebar_language_option("Español", "es") == "Español"
    assert normalize_language("Español") == "es"


def test_key_pages_use_spanish_display_helpers() -> None:
    assert "Fase 3C es solo Shadow Backtest" in Path("pages/reparodynamics.py").read_text(encoding="utf-8")
    assert "from autonomous_betting_agent.ui_i18n import localize_dataframe" in Path("pages/storage_diagnostics.py").read_text(encoding="utf-8")
    assert Path("autonomous_betting_agent/reparodynamics_shadow_backtest.py").exists()
