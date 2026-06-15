from __future__ import annotations

import base64
import builtins
import csv
import io
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import pandas as pd
import requests
import streamlit as st

from autonomous_betting_agent.learning import GradedPrediction, ProbabilityCalibrator, fit_probability_calibrator


def get_secret(*names: str) -> str:
    """Read Streamlit secrets or environment variables safely on every runtime."""
    for name in names:
        if not name:
            continue
        try:
            value = str(st.secrets.get(name, "")).strip()
            if value:
                return value
        except Exception:
            pass
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


builtins.get_secret = get_secret

REPO_ROOT = Path(__file__).resolve().parents[1]
LEARNED_STATE_PATH = REPO_ROOT / "learned_state.json"
MEMORY_BANK_PATH = REPO_ROOT / "data" / "learning_memory_bank.json"
ARA_MEMORY_PATH = REPO_ROOT / "data" / "ara_learning_memory.csv"
DEFAULT_GITHUB_REPOSITORY = "BoneManTGRM/autonomous-betting-agent"
DEFAULT_GITHUB_BRANCH = "main"

PROBABILITY_COLUMNS = (
    "final_probability_value",
    "calibrated_probability",
    "model_probability",
    "predicted_probability",
    "pick_probability",
    "favorite_probability",
    "market_probability_value",
    "market_probability",
    "no_vig_probability",
    "confidence_probability",
    "probability",
)
RESULT_COLUMNS = ("result", "outcome", "win_loss", "graded_result", "status")
PRICE_COLUMNS = ("best_price", "sportsbook_odds", "decimal_odds", "average_price", "avg_price", "odds", "price")
PICK_COLUMNS = ("prediction", "pick", "predicted_side", "predicted_winner", "favorite")
WINNER_COLUMNS = ("winner", "actual_winner", "winning_side", "final_winner")
EVENT_COLUMNS = ("event", "event_name", "game", "match", "fixture")
SPORT_COLUMNS = ("sport", "sport_title", "league", "competition")
START_COLUMNS = ("start", "commence_time", "event_date", "date")

TEXT = {
    "en": {
        "language": "Language / Idioma",
        "title": "Learning Memory",
        "caption": "Cumulative zero-cost learning. Upload graded results, merge with prior memory, prune low-value history, rebuild calibration, and save back to GitHub.",
        "saved_calibration": "Saved calibration summary",
        "cumulative_summary": "Cumulative memory summary",
        "metrics_note": "Saved calibration is the trained calibrator file. Cumulative memory is the raw stored graded rows. If both show the same row count but different win rate, one file is stale or came from a different upload.",
        "events_trained": "Events trained",
        "raw_accuracy": "Raw accuracy",
        "calibrated_accuracy": "Calibrated accuracy",
        "brier_after": "Brier after",
        "existing_rows": "Existing cumulative memory rows",
        "resolved_picks": "Resolved picks",
        "hit_rate": "Hit rate",
        "avg_predicted": "Avg predicted",
        "brier_score": "Brier score",
        "wins": "Wins",
        "losses": "Losses",
        "metric_check": "Metric check",
        "metric_mismatch": "Saved calibration and cumulative memory do not match. Re-train once with the latest graded CSV and save to GitHub so both sections use the same rows.",
        "metric_match": "Saved calibration and cumulative memory are aligned.",
        "saved_implies": "Saved calibration implies",
        "memory_shows": "cumulative memory shows",
        "best_area": "Best reliable area",
        "weakest_area": "Weakest reliable area",
        "records": "records",
        "actual": "actual",
        "smoothed": "smoothed",
        "what_learned": "What ARA learned",
        "train_from_finished": "Train from finished games",
        "upload_graded": "Upload graded results CSV",
        "min_events": "Minimum graded events",
        "max_rows": "Max stored memory rows",
        "min_pattern_rows": "Min rows per pattern",
        "max_patterns": "Max stored patterns",
        "save_github": "Save learning files back to GitHub so the app remembers after restart",
        "missing_token": "GitHub saving is enabled, but GITHUB_TOKEN is missing from Streamlit secrets.",
        "button": "Train and remember",
        "upload_first": "Upload a graded results CSV first.",
        "too_few": "Found {rows} usable unique graded rows after pruning. Need at least {needed}.",
        "updated_local": "Learning memory updated locally for this running app session.",
        "saved_github": "Saved learned_state.json, cumulative memory, and ARA memory patterns to GitHub.",
        "save_error": "Could not save all learning files to GitHub: {error}",
        "training_summary": "Training summary",
        "calibration_details": "Calibration details",
        "top_patterns": "Top learned patterns",
        "download_ara": "Download ARA memory CSV",
        "no_state": "No learned_state.json is currently loaded.",
    },
    "es": {
        "language": "Idioma / Language",
        "title": "Memoria de Aprendizaje",
        "caption": "Aprendizaje acumulativo sin costo extra. Sube resultados ya calificados, combínalos con la memoria anterior, elimina historial de bajo valor, reconstruye la calibración y guárdalo en GitHub.",
        "saved_calibration": "Resumen de calibración guardado",
        "cumulative_summary": "Resumen de memoria acumulativa",
        "metrics_note": "La calibración guardada es el archivo entrenado. La memoria acumulativa son las filas calificadas crudas. Si ambas muestran el mismo número de filas pero distinta tasa de acierto, un archivo está desactualizado o vino de otra carga.",
        "events_trained": "Eventos entrenados",
        "raw_accuracy": "Precisión bruta",
        "calibrated_accuracy": "Precisión calibrada",
        "brier_after": "Brier después",
        "existing_rows": "Filas acumuladas en memoria",
        "resolved_picks": "Pronósticos resueltos",
        "hit_rate": "Tasa de acierto",
        "avg_predicted": "Promedio pronosticado",
        "brier_score": "Puntaje Brier",
        "wins": "Ganadas",
        "losses": "Perdidas",
        "metric_check": "Revisión de métricas",
        "metric_mismatch": "La calibración guardada y la memoria acumulativa no coinciden. Entrena una vez con el CSV calificado más reciente y guarda en GitHub para que ambas secciones usen las mismas filas.",
        "metric_match": "La calibración guardada y la memoria acumulativa están alineadas.",
        "saved_implies": "La calibración guardada implica",
        "memory_shows": "la memoria acumulativa muestra",
        "best_area": "Mejor área confiable",
        "weakest_area": "Área confiable más débil",
        "records": "registros",
        "actual": "real",
        "smoothed": "suavizado",
        "what_learned": "Lo que ARA aprendió",
        "train_from_finished": "Entrenar con partidos terminados",
        "upload_graded": "Subir CSV de resultados calificados",
        "min_events": "Mínimo de eventos calificados",
        "max_rows": "Máximo de filas guardadas",
        "min_pattern_rows": "Mínimo de filas por patrón",
        "max_patterns": "Máximo de patrones guardados",
        "save_github": "Guardar archivos de aprendizaje en GitHub para que la app recuerde después de reiniciar",
        "missing_token": "Guardar en GitHub está activado, pero falta GITHUB_TOKEN en los secretos de Streamlit.",
        "button": "Entrenar y recordar",
        "upload_first": "Primero sube un CSV de resultados calificados.",
        "too_few": "Se encontraron {rows} filas únicas utilizables después de podar. Se necesitan al menos {needed}.",
        "updated_local": "Memoria de aprendizaje actualizada localmente en esta sesión de la app.",
        "saved_github": "Se guardaron learned_state.json, la memoria acumulativa y los patrones ARA en GitHub.",
        "save_error": "No se pudieron guardar todos los archivos de aprendizaje en GitHub: {error}",
        "training_summary": "Resumen del entrenamiento",
        "calibration_details": "Detalles de calibración",
        "top_patterns": "Principales patrones aprendidos",
        "download_ara": "Descargar CSV de memoria ARA",
        "no_state": "Actualmente no hay learned_state.json cargado.",
    },
}

SPANISH_COLUMNS = {
    "area": "area",
    "area_type": "tipo_area",
    "group_value": "valor_grupo",
    "records": "registros",
    "avg_predicted": "promedio_pronosticado",
    "actual_hit_rate": "tasa_acierto_real",
    "actual_minus_predicted": "real_menos_pronosticado",
    "smoothed_hit_rate": "tasa_suavizada",
    "smoothed_edge": "ventaja_suavizada",
    "reliability": "confiabilidad",
    "brier": "brier",
    "memory_type": "tipo_memoria",
    "importance": "importancia",
    "action": "accion",
}

SPANISH_VALUES = {
    "lower_trust": "bajar_confianza",
    "raise_trust": "subir_confianza",
    "watch": "vigilar",
    "probability_bucket": "bloque_probabilidad",
    "sport_probability_bucket": "deporte_bloque_probabilidad",
    "books_bucket": "bloque_casas",
    "api_coverage_bucket": "bloque_cobertura_api",
    "confidence": "confianza",
    "sport": "deporte",
    "unknown": "desconocido",
}

st.set_page_config(page_title="Learning Memory", layout="wide")
language_choice = st.sidebar.selectbox("Language / Idioma", ["English", "Español"], key="learning_memory_language")
LANG = "es" if language_choice == "Español" else "en"


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT["en"].get(key, key))


def pct(value: float | None) -> str:
    return "" if value is None else f"{value * 100:.1f}%"


def report_frame(rows: list[dict[str, Any]] | pd.DataFrame, *, lang: str) -> pd.DataFrame:
    frame = rows.copy() if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if frame.empty or lang != "es":
        return frame
    for col in frame.columns:
        if frame[col].dtype == object:
            frame[col] = frame[col].map(lambda value: SPANISH_VALUES.get(str(value), value))
    return frame.rename(columns={col: SPANISH_COLUMNS.get(str(col), str(col)) for col in frame.columns})


def summary_for_display(summary: dict[str, Any]) -> dict[str, Any]:
    if LANG != "es":
        return summary
    names = {
        "existing_rows_before_upload": "filas_existentes_antes_de_subir",
        "uploaded_usable_rows": "filas_subidas_utilizables",
        "duplicates_removed": "duplicados_eliminados",
        "rows_after_pruning": "filas_despues_de_poda",
        "patterns_saved": "patrones_guardados",
    }
    return {names.get(key, key): value for key, value in summary.items()}


def clean_key(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("%", "").replace(",", "")
    if not text or text.lower() in {"none", "null", "nan", "unknown", "n/a"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_probability(value: Any) -> float | None:
    number = parse_float(value)
    if number is None:
        return None
    if 1.0 < number <= 100.0:
        number /= 100.0
    if 0.0 < number < 1.0:
        return max(0.000001, min(0.999999, number))
    return None


def parse_result(value: Any) -> int | None:
    text = "" if value is None else str(value).strip().lower()
    if text in {"won", "win", "w", "correct", "hit", "true", "yes", "1"}:
        return 1
    if text in {"lost", "loss", "l", "incorrect", "miss", "false", "no", "0"}:
        return 0
    return None


def first_text(row: dict[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = row.get(clean_key(name))
        if value not in (None, ""):
            return str(value).strip()
    return ""


def first_float(row: dict[str, Any], names: tuple[str, ...]) -> float | None:
    for name in names:
        value = parse_float(row.get(clean_key(name)))
        if value is not None:
            return value
    return None


def extract_probability(row: dict[str, Any]) -> float | None:
    for name in PROBABILITY_COLUMNS:
        value = parse_probability(row.get(clean_key(name)))
        if value is not None:
            return value
    price = first_float(row, PRICE_COLUMNS)
    if price is not None and price > 1.0:
        return max(0.000001, min(0.999999, 1.0 / price))
    return None


def extract_result(row: dict[str, Any]) -> int | None:
    for name in RESULT_COLUMNS:
        value = parse_result(row.get(clean_key(name)))
        if value is not None:
            return value
    pick = first_text(row, PICK_COLUMNS).lower()
    winner = first_text(row, WINNER_COLUMNS).lower()
    if pick and winner:
        return 1 if pick == winner else 0
    return None


def compact_row(row: dict[str, Any], row_number: int, source: str) -> dict[str, Any] | None:
    probability = extract_probability(row)
    result = extract_result(row)
    if probability is None or result is None:
        return None
    event = first_text(row, EVENT_COLUMNS) or f"row {row_number}"
    prediction = first_text(row, PICK_COLUMNS)
    start = first_text(row, START_COLUMNS)
    sport = first_text(row, SPORT_COLUMNS)
    price = first_float(row, PRICE_COLUMNS)
    books = first_float(row, ("books", "bookmaker_count", "source_count", "bookmakers"))
    api_coverage = first_float(row, ("api_coverage_score", "api_coverage"))
    if api_coverage is not None and api_coverage > 1.0:
        api_coverage /= 100.0
    item = {
        "event": event[:140],
        "start": start[:40],
        "sport": sport[:80],
        "prediction": prediction[:100],
        "probability": round(probability, 6),
        "outcome": int(result),
        "best_price": None if price is None else round(float(price), 4),
        "books": None if books is None else int(max(0, round(float(books)))),
        "api_coverage_score": None if api_coverage is None else round(max(0.0, min(1.0, float(api_coverage))), 6),
        "confidence": first_text(row, ("confidence", "confidence_bucket", "read", "decision"))[:60],
        "source": source[:120],
    }
    item["error_abs"] = round(abs(item["probability"] - item["outcome"]), 6)
    item["dedupe_key"] = "|".join(part for part in (event.lower().strip(), start[:10].lower().strip(), prediction.lower().strip(), str(result)) if part)
    return item


def read_compact_csv(path: Path, source: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    stats = {"input_rows": 0, "usable_rows": 0, "missing_probability": 0, "missing_result": 0}
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row_number, raw in enumerate(csv.DictReader(handle), start=2):
            stats["input_rows"] += 1
            row = {clean_key(k): v for k, v in raw.items() if k is not None}
            item = compact_row(row, row_number, source)
            if item is None:
                if extract_probability(row) is None:
                    stats["missing_probability"] += 1
                if extract_result(row) is None:
                    stats["missing_result"] += 1
                continue
            rows.append(item)
            stats["usable_rows"] += 1
    return rows, stats


def load_memory_bank() -> dict[str, Any]:
    try:
        if MEMORY_BANK_PATH.exists():
            return json.loads(MEMORY_BANK_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"version": "learning-memory-bank-v1", "compact_rows": []}


def valid_bank_row(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    probability = parse_probability(row.get("probability"))
    result = parse_result(row.get("outcome"))
    if probability is None or result is None:
        return None
    row = dict(row)
    row["probability"] = round(probability, 6)
    row["outcome"] = int(result)
    row["error_abs"] = round(abs(row["probability"] - row["outcome"]), 6)
    row["dedupe_key"] = str(row.get("dedupe_key") or f"{row.get('event','')}|{row.get('start','')}|{row.get('prediction','')}|{row.get('outcome','')}").lower()
    return row


def merge_dedupe_rows(existing: list[dict[str, Any]], uploaded: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for raw in [*existing, *uploaded]:
        row = valid_bank_row(raw)
        if row is None:
            continue
        key = row["dedupe_key"]
        if key in seen:
            duplicates += 1
            if sum(value not in (None, "") for value in row.values()) > sum(value not in (None, "") for value in seen[key].values()):
                seen[key] = row
        else:
            seen[key] = row
    return list(seen.values()), duplicates


def prune_rows(rows: list[dict[str, Any]], max_rows: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(rows) <= max_rows:
        return rows, {"strategy": "no_pruning_needed", "rows_before": len(rows), "rows_after": len(rows), "rows_pruned": 0}
    ordered = sorted(rows, key=lambda row: (str(row.get("start") or ""), float(row.get("error_abs") or 0.0)), reverse=True)
    recent_keep = int(max_rows * 0.75)
    recent = ordered[:recent_keep]
    recent_keys = {row["dedupe_key"] for row in recent}
    high_error = sorted([row for row in ordered if row["dedupe_key"] not in recent_keys], key=lambda row: float(row.get("error_abs") or 0.0), reverse=True)
    kept = {row["dedupe_key"]: row for row in [*recent, *high_error[: max_rows - len(recent)]]}
    return list(kept.values()), {"strategy": "kept_recent_plus_high_error", "rows_before": len(rows), "rows_after": len(kept), "rows_pruned": len(rows) - len(kept)}


def probability_bucket(probability: float) -> str:
    if probability < 0.40:
        return "0-40%"
    if probability < 0.50:
        return "40-50%"
    if probability < 0.60:
        return "50-60%"
    if probability < 0.70:
        return "60-70%"
    if probability < 0.80:
        return "70-80%"
    if probability < 0.90:
        return "80-90%"
    return "90-100%"


def books_bucket(value: Any) -> str:
    number = parse_float(value)
    if number is None:
        return "unknown"
    if number <= 1:
        return "0-1"
    if number <= 3:
        return "2-3"
    if number <= 6:
        return "4-6"
    if number <= 10:
        return "7-10"
    return "11+"


def api_bucket(value: Any) -> str:
    number = parse_float(value)
    if number is None:
        return "unknown"
    number = max(0.0, min(1.0, number))
    if number >= 0.999:
        return "100%"
    if number >= 0.66:
        return "66-99%"
    if number >= 0.33:
        return "33-65%"
    if number > 0:
        return "1-32%"
    return "0%"


def segment_keys(row: dict[str, Any]) -> list[tuple[str, str, str]]:
    keys: list[tuple[str, str, str]] = []
    sport = str(row.get("sport") or "").strip()
    confidence = str(row.get("confidence") or "").strip()
    probability = float(row["probability"])
    bucket = probability_bucket(probability)
    keys.append(("probability_bucket", bucket, f"Probability bucket: {bucket}"))
    if sport:
        keys.append(("sport", sport, f"Sport: {sport}"))
        keys.append(("sport_probability_bucket", f"{sport}|{bucket}", f"{sport} / {bucket}"))
    if confidence:
        keys.append(("confidence", confidence, f"Confidence/read: {confidence}"))
    if row.get("books") is not None:
        bucket_books = books_bucket(row.get("books"))
        keys.append(("books_bucket", bucket_books, f"Books: {bucket_books}"))
    if row.get("api_coverage_score") is not None:
        bucket_api = api_bucket(row.get("api_coverage_score"))
        keys.append(("api_coverage_bucket", bucket_api, f"API coverage: {bucket_api}"))
    return keys


def build_segments(rows: list[dict[str, Any]], min_records: int, max_segments: int) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        for area_type, group_value, label in segment_keys(row):
            key = f"{area_type}:{group_value}".lower()
            grouped.setdefault(key, {"area_type": area_type, "group_value": group_value, "area": label, "rows": []})["rows"].append(row)
    segments: list[dict[str, Any]] = []
    for item in grouped.values():
        group = item.pop("rows")
        records = len(group)
        if records < min_records:
            continue
        probabilities = [float(row["probability"]) for row in group]
        outcomes = [int(row["outcome"]) for row in group]
        avg_predicted = sum(probabilities) / records
        actual_hit_rate = sum(outcomes) / records
        smoothed_hit_rate = (sum(outcomes) + avg_predicted * 8) / (records + 8)
        smoothed_edge = smoothed_hit_rate - avg_predicted
        brier = sum((p - y) ** 2 for p, y in zip(probabilities, outcomes)) / records
        sample_weight = min(1.0, math.log(records + 1) / math.log(51))
        reliability = max(0.05, min(1.0, 0.65 * sample_weight + 0.35 * (1.0 - min(0.40, brier) / 0.40)))
        importance = abs(smoothed_edge) * sample_weight * (1.0 + min(1.0, records / 30.0))
        segments.append({
            **item,
            "records": records,
            "avg_predicted": round(avg_predicted, 6),
            "actual_hit_rate": round(actual_hit_rate, 6),
            "actual_minus_predicted": round(actual_hit_rate - avg_predicted, 6),
            "smoothed_hit_rate": round(smoothed_hit_rate, 6),
            "smoothed_edge": round(smoothed_edge, 6),
            "reliability": round(reliability, 6),
            "brier": round(brier, 6),
            "memory_type": item["area_type"],
            "importance": round(importance, 6),
            "action": "lower_trust" if smoothed_edge < -0.035 else "raise_trust" if smoothed_edge > 0.035 else "watch",
        })
    segments.sort(key=lambda row: (float(row["importance"]), int(row["records"])), reverse=True)
    return segments[:max_segments]


def make_ara_memory_csv(segments: list[dict[str, Any]]) -> str:
    fields = ["area", "area_type", "group_value", "records", "avg_predicted", "actual_hit_rate", "actual_minus_predicted", "smoothed_hit_rate", "smoothed_edge", "reliability", "brier", "memory_type", "importance", "action"]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for segment in segments:
        writer.writerow({field: segment.get(field, "") for field in fields})
    return buffer.getvalue()


def rows_to_graded(rows: list[dict[str, Any]]) -> list[GradedPrediction]:
    return [GradedPrediction(event_name=str(row.get("event") or ""), probability=float(row["probability"]), outcome=int(row["outcome"]), predicted_side=str(row.get("prediction") or "")) for row in rows]


def calibrator_json(calibrator: ProbabilityCalibrator) -> str:
    return json.dumps(calibrator.to_dict(), indent=2, sort_keys=True) + "\n"


def github_put_text_file(*, path: str, content: str, message: str) -> dict[str, Any]:
    token = get_secret("GITHUB_TOKEN", "GH_TOKEN")
    if not token:
        raise RuntimeError("Missing GITHUB_TOKEN in Streamlit secrets.")
    repository = get_secret("GITHUB_REPOSITORY") or DEFAULT_GITHUB_REPOSITORY
    branch = get_secret("GITHUB_BRANCH") or DEFAULT_GITHUB_BRANCH
    url = f"https://api.github.com/repos/{repository}/contents/{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    sha = None
    read_response = requests.get(url, headers=headers, params={"ref": branch}, timeout=20)
    if read_response.status_code == 200:
        sha = read_response.json().get("sha")
    elif read_response.status_code != 404:
        raise RuntimeError(f"GitHub read failed: {read_response.status_code} {read_response.text[:500]}")
    payload: dict[str, Any] = {"message": message, "content": base64.b64encode(content.encode("utf-8")).decode("ascii"), "branch": branch}
    if sha:
        payload["sha"] = sha
    write_response = requests.put(url, headers=headers, json=payload, timeout=20)
    if write_response.status_code not in (200, 201):
        raise RuntimeError(f"GitHub write failed: {write_response.status_code} {write_response.text[:500]}")
    return write_response.json()


def current_learned_state() -> ProbabilityCalibrator | None:
    try:
        if LEARNED_STATE_PATH.exists():
            return ProbabilityCalibrator.load(LEARNED_STATE_PATH)
    except Exception:
        return None
    return None


def memory_metrics(rows: list[dict[str, Any]]) -> dict[str, float | int | None]:
    if not rows:
        return {"resolved": 0, "hit_rate": None, "avg_predicted": None, "brier": None, "wins": 0, "losses": 0}
    probabilities = [float(row["probability"]) for row in rows]
    outcomes = [int(row["outcome"]) for row in rows]
    wins = sum(outcomes)
    losses = len(outcomes) - wins
    return {
        "resolved": len(rows),
        "hit_rate": wins / len(rows),
        "avg_predicted": sum(probabilities) / len(rows),
        "brier": sum((p - y) ** 2 for p, y in zip(probabilities, outcomes)) / len(rows),
        "wins": wins,
        "losses": losses,
    }


def area_line(label: str, segment: dict[str, Any]) -> str:
    return f"{label}: {segment.get('area')} | {segment.get('records')} {t('records')} | {float(segment.get('actual_hit_rate', 0)):.1%} {t('actual')} | {float(segment.get('smoothed_hit_rate', 0)):.1%} {t('smoothed')}"


st.title(t("title"))
st.caption(t("caption"))

current = current_learned_state()
bank = load_memory_bank()
existing_rows = [row for row in (valid_bank_row(row) for row in bank.get("compact_rows", [])) if row is not None]
existing_metrics = memory_metrics(existing_rows)
existing_segments = build_segments(existing_rows, 3, 160) if existing_rows else []

st.subheader(t("saved_calibration"))
saved_raw_wins = None
if current is not None:
    cols = st.columns(4)
    cols[0].metric(t("events_trained"), current.events_trained)
    cols[1].metric(t("raw_accuracy"), "" if current.accuracy_before is None else pct(current.accuracy_before))
    cols[2].metric(t("calibrated_accuracy"), "" if current.accuracy_after is None else pct(current.accuracy_after))
    cols[3].metric(t("brier_after"), "" if current.brier_after is None else f"{current.brier_after:.4f}")
    if current.accuracy_before is not None:
        saved_raw_wins = int(round(float(current.accuracy_before) * int(current.events_trained)))
else:
    st.info(t("no_state"))

st.subheader(t("cumulative_summary"))
st.caption(t("metrics_note"))
cols = st.columns(4)
cols[0].metric(t("resolved_picks"), existing_metrics["resolved"])
cols[1].metric(t("hit_rate"), pct(existing_metrics["hit_rate"]) if existing_metrics["hit_rate"] is not None else "")
cols[2].metric(t("avg_predicted"), pct(existing_metrics["avg_predicted"]) if existing_metrics["avg_predicted"] is not None else "")
cols[3].metric(t("brier_score"), "" if existing_metrics["brier"] is None else f"{float(existing_metrics['brier']):.4f}")
win_cols = st.columns(3)
win_cols[0].metric(t("existing_rows"), len(existing_rows))
win_cols[1].metric(t("wins"), existing_metrics["wins"])
win_cols[2].metric(t("losses"), existing_metrics["losses"])

if current is not None and saved_raw_wins is not None and int(current.events_trained) == int(existing_metrics["resolved"]):
    memory_wins = int(existing_metrics["wins"] or 0)
    if saved_raw_wins != memory_wins:
        st.warning(f"{t('metric_mismatch')} {t('saved_implies')} {saved_raw_wins} {t('wins').lower()}; {t('memory_shows')} {memory_wins} {t('wins').lower()}.")
    else:
        st.success(t("metric_match"))

if existing_segments:
    best = max(existing_segments, key=lambda row: (float(row.get("reliability", 0)), float(row.get("smoothed_edge", 0))))
    weakest = min(existing_segments, key=lambda row: (float(row.get("reliability", 0)), float(row.get("smoothed_edge", 0))))
    st.success(area_line(t("best_area"), best))
    st.warning(area_line(t("weakest_area"), weakest))
    with st.expander(t("what_learned"), expanded=False):
        st.dataframe(report_frame(existing_segments[:40], lang=LANG), use_container_width=True, hide_index=True)

st.subheader(t("train_from_finished"))
graded_upload = st.file_uploader(t("upload_graded"), type=["csv"], accept_multiple_files=False, key="graded_results_for_learning_memory")
settings = st.columns(4)
min_events = settings[0].number_input(t("min_events"), min_value=5, max_value=500, value=5, step=1)
max_rows = settings[1].number_input(t("max_rows"), min_value=100, max_value=10000, value=2500, step=100)
min_segment_records = settings[2].number_input(t("min_pattern_rows"), min_value=2, max_value=50, value=3, step=1)
max_segments = settings[3].number_input(t("max_patterns"), min_value=20, max_value=1000, value=160, step=20)
save_to_github = st.toggle(t("save_github"), value=False)

if save_to_github and not get_secret("GITHUB_TOKEN", "GH_TOKEN"):
    st.warning(t("missing_token"))

if st.button(t("button"), type="primary", use_container_width=True):
    if graded_upload is None:
        st.warning(t("upload_first"))
        st.stop()
    with NamedTemporaryFile(delete=False, suffix=".csv") as handle:
        handle.write(graded_upload.getvalue())
        temp_path = Path(handle.name)
    try:
        uploaded_rows, parse_stats = read_compact_csv(temp_path, getattr(graded_upload, "name", "uploaded_graded_results.csv"))
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass
    merged_rows, duplicates_removed = merge_dedupe_rows(existing_rows, uploaded_rows)
    pruned_rows, prune_report = prune_rows(merged_rows, int(max_rows))
    if len(pruned_rows) < int(min_events):
        st.error(t("too_few").format(rows=len(pruned_rows), needed=int(min_events)))
        st.stop()
    graded_rows = rows_to_graded(pruned_rows)
    calibrator = fit_probability_calibrator(graded_rows, min_events=int(min_events), source=getattr(graded_upload, "name", "uploaded_graded_results.csv"))
    calibrator.notes.append(f"Merged {len(existing_rows)} existing rows with {len(uploaded_rows)} uploaded rows; removed {duplicates_removed} duplicates; trained on {len(pruned_rows)} rows.")
    segments = build_segments(pruned_rows, int(min_segment_records), int(max_segments))
    ara_csv = make_ara_memory_csv(segments)
    memory_bank = {
        "version": "learning-memory-bank-v2",
        "trained_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": {
            "existing_rows_before_upload": len(existing_rows),
            "uploaded_usable_rows": len(uploaded_rows),
            "duplicates_removed": duplicates_removed,
            "rows_after_pruning": len(pruned_rows),
            "patterns_saved": len(segments),
        },
        "parse_stats": parse_stats,
        "prune_report": prune_report,
        "global_calibrator": calibrator.to_dict(),
        "patterns": segments,
        "compact_rows": pruned_rows,
    }
    MEMORY_BANK_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_BANK_PATH.write_text(json.dumps(memory_bank, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LEARNED_STATE_PATH.write_text(calibrator_json(calibrator), encoding="utf-8")
    ARA_MEMORY_PATH.write_text(ara_csv, encoding="utf-8")
    st.success(t("updated_local"))
    if save_to_github:
        try:
            today = datetime.now(timezone.utc).date().isoformat()
            github_put_text_file(path="learned_state.json", content=calibrator_json(calibrator), message=f"Update learned calibration {today}")
            github_put_text_file(path="data/learning_memory_bank.json", content=json.dumps(memory_bank, indent=2, sort_keys=True) + "\n", message=f"Update cumulative learning memory {today}")
            github_put_text_file(path="data/ara_learning_memory.csv", content=ara_csv, message=f"Update ARA memory patterns {today}")
            st.success(t("saved_github"))
        except Exception as exc:
            st.error(t("save_error").format(error=exc))
    st.subheader(t("training_summary"))
    st.json(summary_for_display(memory_bank["summary"]))
    with st.expander(t("calibration_details"), expanded=False):
        st.json(calibrator.to_dict())
    st.subheader(t("top_patterns"))
    display_segments = report_frame(segments[:40], lang=LANG)
    st.dataframe(display_segments, use_container_width=True, hide_index=True)
    download_csv = display_segments.to_csv(index=False) if LANG == "es" else ara_csv
    download_name = "memoria_ara.csv" if LANG == "es" else "ara_learning_memory.csv"
    st.download_button(t("download_ara"), download_csv, file_name=download_name, mime="text/csv")
