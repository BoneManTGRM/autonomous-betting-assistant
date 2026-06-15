from __future__ import annotations

import io
from typing import Any

import pandas as pd
import streamlit as st

TEXT = {
    "en": {
        "title": "Odds Breakdown Report Reader for Learning",
        "caption": "Upload a Pro Predictor odds breakdown/report CSV, and this reader converts graded rows into the clean format Learning Memory can train on.",
        "upload": "Upload graded odds breakdown/report CSV",
        "paste": "Or paste graded report CSV text",
        "needs_result": "This reader needs final results. Add a result/outcome column with won/lost, or an actual_winner/final_winner column that can be compared to prediction.",
        "input_rows": "Input rows",
        "usable_rows": "Learning-ready rows",
        "missing_probability": "Missing probability",
        "missing_result": "Missing result",
        "preview": "Learning-ready preview",
        "download": "Download learning-ready CSV",
        "how_to_use": "Download this CSV, then upload it below in Train from finished games.",
    },
    "es": {
        "title": "Lector de reportes de cuotas para aprendizaje",
        "caption": "Sube un CSV de desglose/reporte de Predictor Pro y este lector convierte filas calificadas al formato limpio que Memoria de Aprendizaje puede entrenar.",
        "upload": "Subir CSV calificado de desglose/reporte de cuotas",
        "paste": "O pegar texto CSV calificado",
        "needs_result": "Este lector necesita resultados finales. Agrega una columna result/outcome con won/lost, o una columna actual_winner/final_winner que se pueda comparar con prediction.",
        "input_rows": "Filas de entrada",
        "usable_rows": "Filas listas para aprender",
        "missing_probability": "Sin probabilidad",
        "missing_result": "Sin resultado",
        "preview": "Vista previa lista para aprendizaje",
        "download": "Descargar CSV listo para aprendizaje",
        "how_to_use": "Descarga este CSV y luego súbelo abajo en Entrenar con partidos terminados.",
    },
}

PROBABILITY_NAMES = (
    "model_probability",
    "probabilidad_modelo",
    "final_probability_value",
    "valor_probabilidad_final",
    "final_probability",
    "probabilidad_final",
    "calibrated_probability",
    "probabilidad_calibrada",
    "predicted_probability",
    "probabilidad_pronosticada",
    "probability",
    "probabilidad",
)
EVENT_NAMES = ("event", "evento", "event_name", "game", "partido", "match", "fixture")
PICK_NAMES = ("prediction", "pronostico", "pronóstico", "pick", "seleccion", "selección", "predicted_winner", "favorite", "favorito")
SPORT_NAMES = ("sport", "deporte", "sport_title", "league", "liga", "competition")
START_NAMES = ("start", "inicio", "event_date", "fecha_evento", "commence_time", "date")
RESULT_NAMES = ("result", "resultado", "outcome", "win_loss", "graded_result", "status")
WINNER_NAMES = ("actual_winner", "ganador_real", "winner", "ganador", "winning_side", "final_winner")
PRICE_NAMES = ("best_price", "mejor_cuota", "decimal_price", "decimal_odds", "average_price", "avg_price", "odds", "cuotas", "price", "cuota")
BOOKS_NAMES = ("books", "casas", "bookmakers", "bookmaker_count", "source_count")
CONFIDENCE_NAMES = ("confidence", "confianza", "decision", "read", "lectura", "classification")
API_NAMES = ("api_coverage_score", "puntaje_cobertura_api", "api_coverage")


def _lang() -> str:
    return "es" if str(st.session_state.get("global_language", "English")) == "Español" else "en"


def _t(key: str) -> str:
    return TEXT[_lang()].get(key, TEXT["en"].get(key, key))


def _clean_key(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_").replace("/", "_")


def _find_col(df: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    lookup = {_clean_key(col): col for col in df.columns}
    for name in names:
        key = _clean_key(name)
        if key in lookup:
            return lookup[key]
    for col in df.columns:
        col_key = _clean_key(col)
        if any(_clean_key(name) in col_key for name in names):
            return col
    return None


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text or text.lower() in {"nan", "none", "null", "unknown", "n/a", "pendiente", "desconocido"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _prob(value: Any) -> float | None:
    number = _num(value)
    if number is None:
        return None
    if 1.0 < number <= 100.0:
        number /= 100.0
    return max(0.000001, min(0.999999, number)) if 0.0 < number < 1.0 else None


def _result(value: Any) -> int | None:
    text = str(value or "").strip().lower()
    if text in {"won", "win", "w", "correct", "hit", "true", "yes", "1", "ganó", "gano", "ganada", "acierto"}:
        return 1
    if text in {"lost", "loss", "l", "incorrect", "miss", "false", "no", "0", "perdió", "perdio", "perdida", "fallo"}:
        return 0
    return None


def _first(row: pd.Series, col: str | None, default: str = "") -> str:
    if col is None:
        return default
    value = row.get(col, default)
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value).strip()


def normalize_learning_report(df: pd.DataFrame, source: str = "odds_breakdown_report") -> tuple[pd.DataFrame, dict[str, int]]:
    event_col = _find_col(df, EVENT_NAMES)
    pick_col = _find_col(df, PICK_NAMES)
    probability_col = _find_col(df, PROBABILITY_NAMES)
    result_col = _find_col(df, RESULT_NAMES)
    winner_col = _find_col(df, WINNER_NAMES)
    sport_col = _find_col(df, SPORT_NAMES)
    start_col = _find_col(df, START_NAMES)
    price_col = _find_col(df, PRICE_NAMES)
    books_col = _find_col(df, BOOKS_NAMES)
    confidence_col = _find_col(df, CONFIDENCE_NAMES)
    api_col = _find_col(df, API_NAMES)

    rows: list[dict[str, Any]] = []
    stats = {"input_rows": int(len(df)), "usable_rows": 0, "missing_probability": 0, "missing_result": 0}
    for idx, row in df.iterrows():
        probability = _prob(row.get(probability_col)) if probability_col else None
        result = _result(row.get(result_col)) if result_col else None
        event = _first(row, event_col, f"row {idx + 1}")
        pick = _first(row, pick_col)
        if result is None and winner_col and pick:
            winner = _first(row, winner_col).lower()
            if winner:
                result = 1 if pick.lower() == winner or pick.lower() in winner or winner in pick.lower() else 0
        if probability is None:
            stats["missing_probability"] += 1
        if result is None:
            stats["missing_result"] += 1
        if probability is None or result is None or not event or not pick:
            continue
        price = _num(row.get(price_col)) if price_col else None
        books = _num(row.get(books_col)) if books_col else None
        api = _num(row.get(api_col)) if api_col else None
        if api is not None and api > 1.0:
            api /= 100.0
        rows.append({
            "event": event[:140],
            "start": _first(row, start_col)[:40],
            "sport": _first(row, sport_col, "unknown")[:80],
            "prediction": pick[:100],
            "probability": round(float(probability), 6),
            "outcome": int(result),
            "best_price": "" if price is None else price,
            "books": "" if books is None else int(max(0, round(float(books)))),
            "api_coverage_score": "" if api is None else round(max(0.0, min(1.0, float(api))), 6),
            "confidence": _first(row, confidence_col, "unknown")[:60],
            "source": source[:120],
            "result": "won" if int(result) == 1 else "lost",
        })
    stats["usable_rows"] = len(rows)
    return pd.DataFrame(rows), stats


def _read_upload_or_paste() -> tuple[str, pd.DataFrame | None]:
    uploaded = st.file_uploader(_t("upload"), type=["csv"], key="learning_odds_report_reader_upload")
    pasted = st.text_area(_t("paste"), height=120, key="learning_odds_report_reader_paste")
    if uploaded is not None:
        return uploaded.name, pd.read_csv(uploaded)
    if pasted.strip():
        return "pasted_odds_report.csv", pd.read_csv(io.StringIO(pasted.strip()))
    return "", None


def render_learning_report_reader() -> None:
    with st.expander(_t("title"), expanded=False):
        st.caption(_t("caption"))
        source, raw = _read_upload_or_paste()
        if raw is None:
            return
        normalized, stats = normalize_learning_report(raw, source=source)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(_t("input_rows"), stats["input_rows"])
        c2.metric(_t("usable_rows"), stats["usable_rows"])
        c3.metric(_t("missing_probability"), stats["missing_probability"])
        c4.metric(_t("missing_result"), stats["missing_result"])
        if normalized.empty:
            st.warning(_t("needs_result"))
            return
        st.success(_t("how_to_use"))
        st.write(_t("preview"))
        st.dataframe(normalized.head(100), use_container_width=True, hide_index=True)
        st.download_button(
            _t("download"),
            data=normalized.to_csv(index=False),
            file_name="learning_ready_odds_report.csv",
            mime="text/csv",
            key="learning_ready_odds_report_download",
        )
