import csv
import io
import re
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Self Learning Engine", layout="wide")

language = st.selectbox("Translate page", ["English", "Español"], index=0)
IS_ES = language == "Español"

TEXT = {
    "title": {"English": "Self Learning Engine", "Español": "Motor de Aprendizaje"},
    "caption": {
        "English": "Upload ARA prediction CSVs, mark final results, and learn which probabilities, sports, and reads actually perform best. This is the first self-feeding layer: manual results now, automatic scores later with a results API.",
        "Español": "Sube CSVs de predicciones de ARA, marca resultados finales y aprende qué probabilidades, deportes y lecturas funcionan mejor. Esta es la primera capa de autoalimentación: resultados manuales ahora, marcadores automáticos después con una API de resultados.",
    },
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
    "won": {"English": "won", "Español": "ganó"},
    "lost": {"English": "lost", "Español": "perdió"},
    "unknown": {"English": "unknown", "Español": "pendiente"},
    "add": {"English": "Add record", "Español": "Agregar registro"},
    "resolved": {"English": "Resolved picks", "Español": "Selecciones resueltas"},
    "hit_rate": {"English": "Hit rate", "Español": "Tasa de acierto"},
    "avg_prob": {"English": "Avg predicted", "Español": "Promedio predicho"},
    "edge_gap": {"English": "Actual minus predicted", "Español": "Real menos predicho"},
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
    "empty": {"English": "Upload prediction CSVs or add records manually. Then mark won/lost results to feed the model.", "Español": "Sube CSVs de predicciones o agrega registros manualmente. Luego marca ganadas/perdidas para alimentar el modelo."},
    "not_auto": {"English": "This does not automatically know final scores yet. Add a results API later for automatic grading.", "Español": "Esto todavía no sabe marcadores finales automáticamente. Después se puede agregar una API de resultados para calificación automática."},
    "loaded": {"English": "Loaded", "Español": "Cargados"},
    "could_not_load": {"English": "Could not load", "Español": "No se pudo cargar"},
    "mark_results": {"English": "Mark some results as won or lost to make ARA learn.", "Español": "Marca algunos resultados como ganados o perdidos para que ARA aprenda."},
}

EXPECTED_COLUMNS = ["event", "sport", "pick", "probability", "predictor_score", "read", "result", "source", "created_at"]
RESULT_MAP = {
    "won": "won", "win": "won", "w": "won", "ganó": "won", "gano": "won", "ganada": "won", "acierto": "won",
    "lost": "lost", "loss": "lost", "l": "lost", "perdió": "lost", "perdio": "lost", "perdida": "lost", "fallo": "lost",
    "unknown": "unknown", "pending": "unknown", "pendiente": "unknown", "": "unknown", "nan": "unknown",
}


def t(key: str) -> str:
    return TEXT.get(key, {}).get(language) or TEXT.get(key, {}).get("English") or key


def parse_probability(value) -> float:
    if value is None or pd.isna(value):
        return 0.0
    text = str(value).strip().replace("%", "")
    try:
        number = float(text)
    except ValueError:
        return 0.0
    if number > 1:
        number = number / 100.0
    return max(0.0, min(1.0, number))


def parse_score(value) -> float:
    if value is None or pd.isna(value):
        return 0.0
    match = re.search(r"\d+(?:\.\d+)?", str(value))
    return max(0.0, min(100.0, float(match.group(0)))) if match else 0.0


def normalize_result(value) -> str:
    return RESULT_MAP.get(str(value or "unknown").strip().lower(), "unknown")


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
    rows = []
    if not event_col or not pick_col or not prob_col:
        return pd.DataFrame(columns=EXPECTED_COLUMNS)
    for _, row in df.iterrows():
        event = str(row.get(event_col, "")).strip()
        pick = str(row.get(pick_col, "")).strip()
        if not event or not pick:
            continue
        rows.append({
            "event": event,
            "sport": str(row.get(sport_col, "unknown")).strip() if sport_col else "unknown",
            "pick": pick,
            "probability": parse_probability(row.get(prob_col, 0)),
            "predictor_score": parse_score(row.get(score_col, 0)) if score_col else 0.0,
            "read": str(row.get(read_col, "unknown")).strip() if read_col else "unknown",
            "result": normalize_result(row.get(result_col, "unknown")) if result_col else "unknown",
            "source": "upload",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    return pd.DataFrame(rows, columns=EXPECTED_COLUMNS)


def tracker_df() -> pd.DataFrame:
    if "ara_learning_records" not in st.session_state:
        st.session_state.ara_learning_records = []
    df = pd.DataFrame(st.session_state.ara_learning_records)
    if df.empty:
        return pd.DataFrame(columns=EXPECTED_COLUMNS)
    return clean_tracker(df)


def clean_tracker(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = "unknown" if col not in ["probability", "predictor_score"] else 0.0
    df = df[EXPECTED_COLUMNS]
    df["event"] = df["event"].astype(str).str.strip()
    df["sport"] = df["sport"].astype(str).str.strip().replace({"": "unknown", "nan": "unknown"})
    df["pick"] = df["pick"].astype(str).str.strip()
    df["read"] = df["read"].astype(str).str.strip().replace({"": "unknown", "nan": "unknown"})
    df["result"] = df["result"].apply(normalize_result)
    df["probability"] = df["probability"].apply(parse_probability)
    df["predictor_score"] = df["predictor_score"].apply(parse_score)
    df["source"] = df["source"].astype(str).replace({"": "unknown", "nan": "unknown"})
    df["created_at"] = df["created_at"].astype(str).replace({"": datetime.now(timezone.utc).isoformat(), "nan": datetime.now(timezone.utc).isoformat()})
    return df[df["event"].ne("") & df["pick"].ne("")]


def set_tracker(df: pd.DataFrame) -> None:
    st.session_state.ara_learning_records = clean_tracker(df).to_dict("records")


def csv_text(df: pd.DataFrame) -> str:
    output = io.StringIO()
    clean_tracker(df).to_csv(output, index=False, quoting=csv.QUOTE_MINIMAL)
    return output.getvalue()


def summarize_group(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    rows = []
    grouped = df.copy()
    grouped[group_col] = grouped[group_col].astype(str).fillna("unknown")
    for key, group in grouped.groupby(group_col, dropna=False):
        if group.empty:
            continue
        actual = float(group["actual"].mean())
        predicted = float(group["probability"].mean())
        brier = float(((group["probability"] - group["actual"]) ** 2).mean())
        rows.append({
            group_col: str(key),
            "records": int(len(group)),
            "avg_predicted": round(predicted, 3),
            "actual_hit_rate": round(actual, 3),
            "actual_minus_predicted": round(actual - predicted, 3),
            "brier": round(brier, 3),
        })
    if not rows:
        return pd.DataFrame(columns=[group_col, "records", "avg_predicted", "actual_hit_rate", "actual_minus_predicted", "brier"])
    return pd.DataFrame(rows).sort_values(["records", "actual_minus_predicted"], ascending=[False, False])


def add_probability_bucket(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    bins = [0, 0.4, 0.5, 0.6, 0.7, 0.8, 1.01]
    labels = ["0-40%", "40-50%", "50-60%", "60-70%", "70-80%", "80-100%"]
    df["probability_bucket"] = pd.cut(df["probability"], bins=bins, labels=labels, include_lowest=True).astype(str)
    return df


def best_and_worst(summaries: list[pd.DataFrame]) -> tuple[str, str]:
    combined = pd.concat([df for df in summaries if not df.empty], ignore_index=True) if any(not df.empty for df in summaries) else pd.DataFrame()
    if combined.empty:
        return "Not enough data", "Not enough data"
    qualified = combined[combined["records"] >= 2]
    if qualified.empty:
        qualified = combined
    best = qualified.sort_values(["actual_minus_predicted", "records"], ascending=[False, False]).iloc[0]
    worst = qualified.sort_values(["actual_minus_predicted", "records"], ascending=[True, False]).iloc[0]
    best_label = f"{best.iloc[0]} | {int(best['records'])} records | {best['actual_hit_rate']:.1%} actual"
    worst_label = f"{worst.iloc[0]} | {int(worst['records'])} records | {worst['actual_hit_rate']:.1%} actual"
    return best_label, worst_label


st.title(t("title"))
st.caption(t("caption"))
st.info(t("not_auto"))

uploaded = st.file_uploader(t("upload_predictions"), type=["csv"], accept_multiple_files=True)
if uploaded:
    current = tracker_df()
    frames = [current] if not current.empty else []
    loaded_count = 0
    for file in uploaded:
        try:
            raw = pd.read_csv(file)
            normalized = normalize_upload(raw)
            if len(normalized):
                frames.append(normalized)
                loaded_count += len(normalized)
        except Exception as exc:
            st.warning(f"{t('could_not_load')} {file.name}: {exc}")
    if frames:
        combined = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["event", "pick", "probability"], keep="last")
        set_tracker(combined)
        st.success(f"{t('loaded')}: {loaded_count}")

memory_upload = st.file_uploader(t("upload_memory"), type=["csv"], key="memory_upload")
if memory_upload is not None:
    try:
        memory_df = pd.read_csv(memory_upload)
        normalized_memory = clean_tracker(memory_df) if {"event", "pick", "probability", "result"}.issubset(memory_df.columns) else normalize_upload(memory_df)
        current = tracker_df()
        combined = pd.concat([current, normalized_memory], ignore_index=True).drop_duplicates(subset=["event", "pick", "probability"], keep="last")
        set_tracker(combined)
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
    if st.button(t("add")):
        if event.strip() and pick.strip():
            current = tracker_df()
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
            set_tracker(pd.concat([current, new_row], ignore_index=True))
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

    bucket_summary = summarize_group(resolved, "probability_bucket")
    sport_summary = summarize_group(resolved, "sport")
    read_summary = summarize_group(resolved, "read")
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
    st.download_button(t("download_memory"), data=csv_text(learning_memory), file_name="ara_learning_memory.csv", mime="text/csv")

st.download_button(t("download_tracker"), data=csv_text(editable), file_name="ara_self_learning_tracker.csv", mime="text/csv")
if st.button(t("clear")):
    st.session_state.ara_learning_records = []
    st.rerun()
