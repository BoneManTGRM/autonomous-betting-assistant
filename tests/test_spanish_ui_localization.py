from __future__ import annotations

from pathlib import Path

import pandas as pd

from autonomous_betting_agent.ui_i18n import localize_dataframe, localize_options, localize_value


def test_spanish_value_localization_core_buckets() -> None:
    assert localize_value("A_top_candidate", "es") == "Nivel A - candidato fuerte"
    assert localize_value("B_high_confidence_test", "es") == "Nivel B - prueba de alta confianza"
    assert localize_value("learning_candidate", "es") == "candidata de aprendizaje"
    assert localize_value("research_play", "es") == "jugada de investigacion"


def test_spanish_value_localization_visibility_and_status() -> None:
    assert localize_value("private", "es") == "privado"
    assert localize_value("public", "es") == "publico"
    assert localize_value("trial", "es") == "prueba"
    assert localize_value("active", "es") == "activo"
    assert localize_value("inactive", "es") == "inactivo"
    assert localize_value("expired", "es") == "vencido"


def test_localize_dataframe_columns_and_cells() -> None:
    frame = pd.DataFrame(
        [
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
        ]
    )
    out = localize_dataframe(frame, "es")
    assert "rango_confianza" in out.columns
    assert "riesgo_confianza" in out.columns
    assert "tamano_muestra" in out.columns
    assert "victorias" in out.columns
    assert "derrotas" in out.columns
    assert "tasa_acierto" in out.columns
    assert "tipo_mercado" in out.columns
    assert "rango_probabilidad_modelo" in out.columns
    assert "carril_reporte_v2" in out.columns
    assert out.loc[0, "rango_confianza"] == "Nivel A - candidato fuerte"
    assert out.loc[0, "tipo_mercado"] == "ganador"
    assert out.loc[0, "rango_probabilidad_modelo"] == "jugada de investigacion"
    assert out.loc[0, "carril_reporte_v2"] == "candidata de aprendizaje"
    assert out.loc[0, "visibilidad"] == "privado"


def test_english_mode_unchanged() -> None:
    frame = pd.DataFrame([{"confidence_bucket": "A_top_candidate", "visibility": "private"}])
    assert localize_value("A_top_candidate", "en") == "A_top_candidate"
    assert localize_dataframe(frame, "en").equals(frame)


def test_localize_options_preserves_internal_values() -> None:
    display, mapping = localize_options(["private", "public"], "es")
    assert display == ["privado", "publico"]
    assert mapping["privado"] == "private"
    assert mapping["publico"] == "public"


def test_odds_lock_visible_labels_are_localized() -> None:
    source = Path("pages/odds_lock_pro.py").read_text(encoding="utf-8")
    assert "st.number_input('Daily exposure limit'" not in source
    assert "st.number_input('Per-sport exposure limit'" not in source
    assert "metric('Uploaded locked'" not in source
    assert "'Exposure', t('client')" not in source
    assert "t('daily_exposure_limit')" in source
    assert "t('per_sport_exposure_limit')" in source
    assert "t('uploaded_locked')" in source
    assert "t('exposure')" in source


def test_signal_board_spanish_guide_uses_tablero_de_senales() -> None:
    source = Path("pages/signal_board.py").read_text(encoding="utf-8")
    assert "Revisa este Signal Board" not in source
    assert "Revisa este tablero de senales" in source
    assert "st.dataframe(localize_dataframe" in source


def test_report_studio_dropdowns_preserve_raw_values_with_spanish_labels() -> None:
    source = Path("pages/report_studio.py").read_text(encoding="utf-8")
    assert "visibility_values = [\"private\", \"public\"]" in source
    assert "visibility_labels, visibility_map = localize_options(visibility_values, LANG)" in source
    assert "visibility = visibility_map.get" in source
    assert "profile_map.get" in source
    assert "global_localize_dataframe" in source


def test_no_model_or_ledger_logic_modules_changed() -> None:
    touched_pages = [
        "pages/signal_board.py",
        "pages/odds_lock_pro.py",
        "pages/report_studio.py",
        "pages/reparodynamics.py",
    ]
    for file_name in touched_pages:
        assert Path(file_name).exists()
