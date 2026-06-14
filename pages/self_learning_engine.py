import csv
import io
import re
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Self Learning Engine", layout="wide")

language = st.selectbox("Translate page", ["English", "Español"], index=0)

TEXT = {
    "title": {"English": "Self Learning Engine", "Español": "Motor de Aprendizaje"},
    "caption": {
        "English": "Upload ARA prediction CSVs, mark final results, and learn which probabilities, sports, and reads actually perform best. Level 1 can also import the latest Pro Predictor scan from this same app session.",
        "Español": "Sube CSVs de predicciones de ARA, marca resultados finales y aprende qué probabilidades, deportes y lecturas funcionan mejor. Nivel 1 también puede importar el último escaneo del Predictor Profesional en esta misma sesión.",
    },
    "import_latest": {"English": "Import latest predictor scan", "Español": "Importar último escaneo del predictor"},
    "no_latest": {"English": "No latest predictor scan found. Run Pro Predictor first in this same app session.", "Español": "No se encontró un escaneo reciente. Ejecuta primero el Predictor Profesional en esta misma sesión."},
    "imported_latest": {"English": "Imported latest predictor scan", "Español": "Último escaneo importado"},
    "latest_info": {"English": "Latest scan ready", "Español": "Último escaneo listo"},
    "upload_predictions": {"English": "Upload prediction CSV", "Español": "Subir CSV de predicciones"},
    "upload_memory": {"English": "Upload previous tracker CSV", "Español": "Subir tracker anterior"},
    "manual": {"English": "Manual record", "Español": "Registro manual"},
    "event": {"English": "Event", "Español": "Evento"},
    "sport": {"English": "Sport", "Español": "Deporte"},
    "pick": {"English": "Pick", "Español": "Selección"},
    "prob": {"English": "Predicted probability", "Español": "Probabilidad predicha"},
    "score": {"English": "Predictor score", "Español": "Puntaje del predictor"},
    "read": {"English": "Read", "Español": "Lectura"},
    "result": {"English": "Result", "Español": "Resultado"},
    "add": {"English": "Add record", "Español": "Agregar registro"},
    "resolved": {"English": "Resolved picks", "Español": "Selecciones resueltas"},
    "hit_rate": {"English": "Hit rate", "Español": "Tasa de acierto"},
    "avg_prob": {"English": "Avg predicted", "Español": "Promedio predicho"},
    "brier": {"English": "Brier score", "Español": "Brier score"},
    "learned": {"English": "What ARA learned", "Español": "Lo que ARA aprendió"},
    "best_area": {"English": "Best current area", "Español": "Mejor área actual"},
    "worst_area": {"English": "Weakest current area", "Español": "Área más débil actual"},
    "buckets": {"English": "Probability buckets", "Español": "Rangos de probabilidad"},
    "sports": {"English": "By sport", "Español": "Por deporte"},
    "reads": {"English": "By read/classification", "Español": "Por lectura/clasificación"},
    "download_tracker": {"English": "Download updated tracker CSV", "Español": "Descargar tracker actualizado"},
    "download_memory": {"English": "Download learning memory CSV", "Español": "Descargar memoria de aprendizaje"},
    "clear": {"English": "Clear session memory", "Español": "Borrar memoria de sesión"},
    "empty": {"English": "Upload prediction CSVs, import the latest predictor scan, or add records manually. Then mark won/lost results to feed the model.", "Español": "Sube CSVs, importa el último escaneo del predictor o agrega registros manualmente. Luego marca ganadas/perdidas para alimentar el modelo."},
    "not_auto": {"English": "Level 1 is automatic inside this app session. It still does not know final scores automatically; that needs a results API later.", "Español": "Nivel 1 es automático dentro de esta sesión. Todavía no sabe marcadores finales automáticamente; eso necesita una API de resultados después."},
    "loaded": {"English": "Loaded", "Español": "Cargados"},
    "could_not_load": {"English": "Could not load", "Español": "No se pudo cargar"},
    "mark_results": {"English": "Mark some results as won or lost to make ARA learn.", "Español": "Marca algunos resultados como ganados o perdidos para que ARA aprenda."},
}

EXPECTED_COLUMNS = ["event", "sport", "pick", "probability", "predictor_score", "read", "result", "source", "created_at"]
RESULT_MAP = {
    "won": "won", "win": "won", "w": "won", "ganó": "won", "gano": "won", "ganada": "won", "acierto": "won",
    "lost": "lost", "loss": "lost", "l": "lost", "perdió": "lost", "perdio": "lost", "perdida": "lost", "fallo": "lost",
    "unknown": "unknown", "pending": "unknown", "pendiente": "unknown", "": "unknown", "nan": "unknown", "none": "unknown",
}


def t(key: str) -> str:
    return TEXT.get(key, {}).get(language) or TEXT.get(key, {}).get("English") or key


def clean_text(value, default: str = "unknown") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null", "<na>"}:
        return default
    return text


def parse_probability(value) -> float:
    if value is None:
        return 0.0
    try:
        if pd.isna(value):
            return 0.0
    except Exception:
        pass
    text = str(value).strip().replace("%", "")
    try:
        number = float(text)
    except ValueError:
        return 0.0
    if number > 1:
        number = number / 100.0
    return max(0.0, min(1.0, number))


def parse_score(value) -> float:
    if value is None:
        return 0.0
    try:
        if pd.isna(value):
            return 0.0
    except Exception:
        pass
    match = re.search(r"\d+(?:\.\d+)?", str(value))
    return max(0.0, min(100.0, float(match.group(0)))) if match else 0.0


def normalize_result(value) -> str:
    return RESULT_MAP.get(clean_text(value, "unknown").lower(), "unknown")


def find_col(df: pd.DataFrame, names: list[str]):
    lookup = {str(col).strip().lower(): col for col in df.columns}
    for name in names:
        if name.lower() in lookup:
            return lookup[name.lower()]
    for col in df.columns:
        clean_col = str(col).strip().lower()
        if any(name.lower() in clean_col for name in names):
            return col
    return None


def normalize_upload(df: pd.DataFrame) -> pd.DataFrame:
    event_col = find_col(df, ["event", "evento", "game", "match"])
    sport_col = find_col(df, ["sport", "deporte", "league", "liga"])
    pick_col = find_col(df, ["prediction", "predicción", "prediccion", "pick", "selección", "seleccion", "market lean"])
    prob_col = find_col(df, ["market probability", "probabilidad", "probability", "no-vig probability", "probabilidad sin margen", "team win %", "favorite %"])
    score_col = find_col(df, ["predictor score", "puntaje", "score"])
    read_col = find_col(df, ["classification", "clasificación", "clasificacion", "read", "lectura"])
    result_col = find_col(df, ["result", "resultado"])
    if not event_col or not pick_col or not prob_col:
        return pd.DataFrame(columns=EXPECTED_COLUMNS)
    rows = []
    for _, row in df.iterrows():
        event = clean_text(row.get(event_col, ""), "")
        pick = clean_text(row.get(pick_col, ""), "")
        if not event or not pick:
            continue
        rows.append({
            "event": event,
            "sport": clean_text(row.get(sport_col, "unknown") if sport_col else "unknown"),
            "pick": pick,
            "probability": parse_probability(row.get(prob_col, 0)),
            "predictor_score": parse_score(row.get(score_col, 0)) if score_col else 0.0,
            "read": clean_text(row.get(read_col, "unknown") if read_col else "unknown"),
            "result": normalize_result(row.get(result_col, "unknown") if result_col else "unknown"),
            "source": "upload",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    return pd.DataFrame(rows, columns=EXPECTED_COLUMNS)


def clean_tracker(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0 if col in ["probability", "predictor_score"] else "unknown"
    df = df[EXPECTED_COLUMNS]
    df["event"] = df["event"].apply(lambda x: clean_text(x, ""))
    df["sport"] = df["sport"].apply(clean_text)
    df["pick"] = df["pick"].apply(lambda x: clean_text(x, ""))
    df["probability"] = df["probability"].apply(parse_probability)
    df["predictor_score"] = df["predictor_score"].apply(parse_score)
    df["read"] = df["read"].apply(clean_text)
    df["result"] = df["result"].apply(normalize_result)
    df["source"] = df["source"].apply(clean_text)
    df["created_at"] = df["created_at"].apply(lambda x: clean_text(x, datetime.now(timezone.utc).isoformat()))
    return df[df["event"].ne("") & df["pick"].ne("")]


def tracker_df() -> pd.DataFrame:
    if "ara_learning_records" not in st.session_state:
        st.session_state.ara_learning_records = []
    df = pd.DataFrame(st.session_state.ara_learning_records)
    if df.empty:
        return pd.DataFrame(columns=EXPECTED_COLUMNS)
    return clean_tracker(df)


def set_tracker(df: pd.DataFrame) -> None:
    st.session_state.ara_learning_records = clean_tracker(df).to_dict("records")


def merge_into_tracker(new_df: pd.DataFrame) -> int:
    current = tracker_df()
    before = len(current)
    combined = pd.concat([current, clean_tracker(new_df)], ignore_index=True)
    combined = combined.drop_duplicates(subset=["event", "pick", "probability"], keep="last")
    set_tracker(combined)
    return max(0, len(tracker_df()) - before)


def tracker_csv_text(df: pd.DataFrame) -> str:
    output = io.StringIO()
    clean_tracker(df).to_csv(output, index=False, quoting=csv.QUOTE_MINIMAL)
    return output.getvalue()


def raw_csv_text(df: pd.DataFrame) -> str:
    output = io.StringIO()
    df.to_csv(output, index=False, quoting=csv.QUOTE_MINIMAL)
    return output.getvalue()


def summarize_group(df: pd.DataFrame, group_col: str, area_type: str) -> pd.DataFrame:
    rows = []
    grouped = df.copy()
    grouped[group_col] = grouped[group_col].apply(clean_text)
    for key, group in grouped.groupby(group_col, dropna=False):
        key = clean_text(key)
        actual = float(group["actual"].mean())
        predicted = float(group["probability"].mean())
        brier = float(((group["probability"] - group["actual"]) ** 2).mean())
        rows.append({
            "area": f"{area_type}: {key}",
            "area_type": area_type,
            "group_value": key,
            "records": int(len(group)),
            "avg_predicted": round(predicted, 3),
            "actual_hit_rate": round(actual, 3),
            "actual_minus_predicted": round(actual - predicted, 3),
            "brier": round(brier, 3),
        })
    if not rows:
        return pd.DataFrame(columns=["area", "area_type", "group_value", "records", "avg_predicted", "actual_hit_rate", "actual_minus_predicted", "brier"])
    return pd.DataFrame(rows).sort_values(["records", "actual_minus_predicted"], ascending=[False, False])


def add_probability_bucket(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    bins = [0, 0.4, 0.5, 0.6, 0.7, 0.8, 1.01]
    labels = ["0-40%", "40-50%", "50-60%", "60-70%", "70-80%", "80-100%"]
    df["probability_bucket"] = pd.cut(df["probability"], bins=bins, labels=labels, include_lowest=True).astype(str)
    df["probability_bucket"] = df["probability_bucket"].apply(clean_text)
    return df


def best_and_worst(summaries: list[pd.DataFrame]) -> tuple[str, str]:
    valid = [df for df in summaries if not df.empty and "area" in df.columns]
    if not valid:
        return "Not enough data", "Not enough data"
    combined = pd.concat(valid, ignore_index=True)
    combined["area"] = combined["area"].apply(clean_text)
    qualified = combined[combined["records"] >= 2]
    if qualified.empty:
        qualified = combined
    best = qualified.sort_values(["actual_minus_predicted", "records"], ascending=[False, False]).iloc[0]
    worst = qualified.sort_values(["actual_minus_predicted", "records"], ascending=[True, False]).iloc[0]
    return (
        f"{best['area']} | {int(best['records'])} records | {best['actual_hit_rate']:.1%} actual",
        f"{worst['area']} | {int(worst['records'])} records | {worst['actual_hit_rate']:.1%} actual",
    )


st.title(t("title"))
st.caption(t("caption"))
st.info(t("not_auto"))

latest_predictions = st.session_state.get("ara_latest_predictions", [])
latest_source = st.session_state.get("ara_latest_predictions_source", "Predictor")
latest_saved_at = st.session_state.get("ara_latest_predictions_saved_at", "")
if latest_predictions:
    st.success(f"{t('latest_info')}: {len(latest_predictions)} from {latest_source} {latest_saved_at}")
    if st.button(t("import_latest"), type="primary"):
        added = merge_into_tracker(pd.DataFrame(latest_predictions))
        st.success(f"{t('imported_latest')}: {added}")
        st.rerun()
else:
    st.caption(t("no_latest"))

uploaded = st.file_uploader(t("upload_predictions"), type=["csv"], accept_multiple_files=True)
if uploaded:
    loaded_count = 0
    for file in uploaded:
        try:
            raw = pd.read_csv(file)
            normalized = normalize_upload(raw)
            if len(normalized):
                merge_into_tracker(normalized)
                loaded_count += len(normalized)
        except Exception as exc:
            st.warning(f"{t('could_not_load')} {file.name}: {exc}")
    if loaded_count:
        st.success(f"{t('loaded')}: {loaded_count}")

memory_upload = st.file_uploader(t("upload_memory"), type=["csv"], key="memory_upload")
if memory_upload is not None:
    try:
        memory_df = pd.read_csv(memory_upload)
        if {"event", "pick", "probability", "result"}.issubset(memory_df.columns):
            normalized_memory = clean_tracker(memory_df)
            merge_into_tracker(normalized_memory)
        else:
            st.info("Learning-memory summary files are for review only. Upload the updated tracker CSV here if you want to restore editable picks." if language == "English" else "Los archivos de memoria son solo para revisión. Sube aquí el tracker actualizado si quieres restaurar selecciones editables.")
    except Exception as exc:
        st.warning(f"{t('could_not_load')} {memory_upload.name}: {exc}")

with st.expander(t("manual"), expanded=False):
    event = st.text_input(t("event"))
    sport = st.text_input(t("sport"), "unknown")
    pick = st.text_input(t("pick"))
    probability = st.number_input(t("prob"), min_value=0.0, max_value=1.0, value=0.50, step=0.01)
    predictor_score = st.number_input(t("score"), min_value=0.0, max_value=100.0, value=50.0, step=1.0)
    read = st.text_input(t("read"), "manual")
    result = st.selectbox(t("result"), ["unknown", "won", "lost"])
    if st.button(t("add")) and event.strip() and pick.strip():
        new_row = pd.DataFrame([{
            "event": event,
            "sport": sport,
            "pick": pick,
            "probability": probability,
            "predictor_score": predictor_score,
            "read": read,
            "result": result,
            "source": "manual",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }])
        merge_into_tracker(new_row)
        st.rerun()

current = tracker_df()
if current.empty:
    st.info(t("empty"))
    st.stop()

editable = st.data_editor(
    current,
    use_container_width=True,
    hide_index=True,
    column_config={
        "result": st.column_config.SelectboxColumn(t("result"), options=["unknown", "won", "lost"]),
        "probability": st.column_config.NumberColumn(t("prob"), min_value=0.0, max_value=1.0, step=0.01),
        "predictor_score": st.column_config.NumberColumn(t("score"), min_value=0.0, max_value=100.0, step=1.0),
    },
    key="self_learning_editor",
)
set_tracker(editable)
editable = tracker_df()

resolved = editable[editable["result"].isin(["won", "lost"])].copy()
if resolved.empty:
    st.info(t("mark_results"))
else:
    resolved["actual"] = resolved["result"].map({"won": 1.0, "lost": 0.0})
    resolved = add_probability_bucket(resolved)
    hit_rate = float(resolved["actual"].mean())
    avg_prob = float(resolved["probability"].mean())
    brier = float(((resolved["probability"] - resolved["actual"]) ** 2).mean())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("resolved"), len(resolved))
    c2.metric(t("hit_rate"), f"{hit_rate:.1%}")
    c3.metric(t("avg_prob"), f"{avg_prob:.1%}")
    c4.metric(t("brier"), f"{brier:.3f}")

    bucket_summary = summarize_group(resolved, "probability_bucket", "Probability bucket")
    sport_summary = summarize_group(resolved, "sport", "Sport")
    read_summary = summarize_group(resolved, "read", "Read")
    best, worst = best_and_worst([bucket_summary, sport_summary, read_summary])

    c5, c6 = st.columns(2)
    c5.success(f"{t('best_area')}: {best}")
    c6.warning(f"{t('worst_area')}: {worst}")

    st.subheader(t("learned"))
    tabs = st.tabs([t("buckets"), t("sports"), t("reads")])
    with tabs[0]:
        st.dataframe(bucket_summary, use_container_width=True, hide_index=True)
    with tabs[1]:
        st.dataframe(sport_summary, use_container_width=True, hide_index=True)
    with tabs[2]:
        st.dataframe(read_summary, use_container_width=True, hide_index=True)

    learning_memory = pd.concat([
        bucket_summary.assign(memory_type="probability_bucket"),
        sport_summary.assign(memory_type="sport"),
        read_summary.assign(memory_type="read"),
    ], ignore_index=True)
    st.download_button(t("download_memory"), data=raw_csv_text(learning_memory), file_name="ara_learning_memory.csv", mime="text/csv")

st.download_button(t("download_tracker"), data=tracker_csv_text(editable), file_name="ara_self_learning_tracker.csv", mime="text/csv")
if st.button(t("clear")):
    st.session_state.ara_learning_records = []
    st.rerun()
