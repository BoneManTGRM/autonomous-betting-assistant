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
        "English": "Upload ARA prediction CSVs, mark final results, and let the tracker learn which confidence ranges, sports, and reads actually perform best. First version: manual results. Automatic final scores need a results API later.",
        "Español": "Sube CSVs de predicciones de ARA, marca resultados finales y deja que el rastreador aprenda qué rangos de confianza, deportes y lecturas funcionan mejor. Primera versión: resultados manuales. Para marcadores automáticos se necesita una API de resultados después.",
    },
    "upload_predictions": {"English": "Upload prediction CSV", "Español": "Subir CSV de predicciones"},
    "upload_memory": {"English": "Upload previous learning CSV", "Español": "Subir CSV de aprendizaje anterior"},
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
    "records": {"English": "Learning records", "Español": "Registros de aprendizaje"},
    "resolved": {"English": "Resolved picks", "Español": "Selecciones resueltas"},
    "hit_rate": {"English": "Hit rate", "Español": "Tasa de acierto"},
    "avg_prob": {"English": "Avg predicted", "Español": "Promedio predicho"},
    "edge_gap": {"English": "Actual minus predicted", "Español": "Real menos predicho"},
    "brier": {"English": "Brier score", "Español": "Brier score"},
    "learned": {"English": "What ARA learned", "Español": "Lo que ARA aprendió"},
    "buckets": {"English": "Probability buckets", "Español": "Rangos de probabilidad"},
    "sports": {"English": "By sport", "Español": "Por deporte"},
    "reads": {"English": "By read/classification", "Español": "Por lectura/clasificación"},
    "download_tracker": {"English": "Download updated tracker CSV", "Español": "Descargar tracker actualizado"},
    "download_memory": {"English": "Download learning memory CSV", "Español": "Descargar memoria de aprendizaje"},
    "clear": {"English": "Clear session memory", "Español": "Borrar memoria de sesión"},
    "empty": {"English": "Upload prediction CSVs or add records manually. Then mark won/lost results to feed the model.", "Español": "Sube CSVs de predicciones o agrega registros manualmente. Luego marca ganadas/perdidas para alimentar el modelo."},
    "not_auto": {"English": "This does not automatically know final scores yet. To do that, add a results/scores API later.", "Español": "Esto todavía no sabe marcadores finales automáticamente. Para eso se agregaría una API de resultados/marcadores después."},
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
    return float(match.group(0)) if match else 0.0


def find_col(df: pd.DataFrame, names: list[str]):
    lookup = {str(col).strip().lower(): col for col in df.columns}
    for name in names:
        if name.lower() in lookup:
            return lookup[name.lower()]
    for col in df.columns:
        clean = str(col).strip().lower()
        if any(name.lower() in clean for name in names):
            return col
    return None


def normalize_upload(df: pd.DataFrame) -> pd.DataFrame:
    event_col = find_col(df, ["event", "evento", "game", "match"])
    sport_col = find_col(df, ["sport", "deporte", "league"])
    pick_col = find_col(df, ["prediction", "predicción", "pick", "selección", "market lean"])
    prob_col = find_col(df, ["market probability", "probabilidad", "probability", "no-vig probability", "probabilidad sin margen"])
    score_col = find_col(df, ["predictor score", "puntaje", "score"])
    read_col = find_col(df, ["classification", "clasificación", "read", "lectura"])
    result_col = find_col(df, ["result", "resultado"])
    rows = []
    if not event_col or not pick_col or not prob_col:
        return pd.DataFrame(columns=["event", "sport", "pick", "probability", "predictor_score", "read", "result", "source", "created_at"])
    for _, row in df.iterrows():
        rows.append({
            "event": str(row.get(event_col, "")),
            "sport": str(row.get(sport_col, "unknown")) if sport_col else "unknown",
            "pick": str(row.get(pick_col, "")),
            "probability": parse_probability(row.get(prob_col, 0)),
            "predictor_score": parse_score(row.get(score_col, 0)) if score_col else 0.0,
            "read": str(row.get(read_col, "unknown")) if read_col else "unknown",
            "result": str(row.get(result_col, "unknown")).lower() if result_col else "unknown",
            "source": "upload",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    return pd.DataFrame(rows)


def tracker_df() -> pd.DataFrame:
    if "ara_learning_records" not in st.session_state:
        st.session_state.ara_learning_records = []
    return pd.DataFrame(st.session_state.ara_learning_records)


def set_tracker(df: pd.DataFrame) -> None:
    expected = ["event", "sport", "pick", "probability", "predictor_score", "read", "result", "source", "created_at"]
    for col in expected:
        if col not in df.columns:
            df[col] = "unknown" if col not in ["probability", "predictor_score"] else 0.0
    st.session_state.ara_learning_records = df[expected].to_dict("records")


def csv_text(df: pd.DataFrame) -> str:
    output = io.StringIO()
    df.to_csv(output, index=False, quoting=csv.QUOTE_MINIMAL)
    return output.getvalue()


def summarize_group(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    rows = []
    for key, group in df.groupby(group_col):
        if len(group) < 1:
            continue
        actual = group["actual"].mean()
        predicted = group["probability"].mean()
        brier = ((group["probability"] - group["actual"]) ** 2).mean()
        rows.append({
            group_col: key,
            "records": len(group),
            "avg_predicted": round(predicted, 3),
            "actual_hit_rate": round(actual, 3),
            "actual_minus_predicted": round(actual - predicted, 3),
            "brier": round(brier, 3),
        })
    return pd.DataFrame(rows).sort_values(["records", "actual_minus_predicted"], ascending=[False, False]) if rows else pd.DataFrame()


def add_probability_bucket(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    bins = [0, 0.4, 0.5, 0.6, 0.7, 0.8, 1.01]
    labels = ["0-40%", "40-50%", "50-60%", "60-70%", "70-80%", "80-100%"]
    df["probability_bucket"] = pd.cut(df["probability"], bins=bins, labels=labels, include_lowest=True)
    return df


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
            st.warning(f"Could not load {file.name}: {exc}")
    if frames:
        combined = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["event", "pick", "probability"], keep="last")
        set_tracker(combined)
        st.success(f"Loaded {loaded_count} records." if not IS_ES else f"Se cargaron {loaded_count} registros.")

memory_upload = st.file_uploader(t("upload_memory"), type=["csv"], key="memory_upload")
if memory_upload is not None:
    memory_df = pd.read_csv(memory_upload)
    normalized_memory = normalize_upload(memory_df) if not {"event", "pick", "probability", "result"}.issubset(memory_df.columns) else memory_df
    current = tracker_df()
    combined = pd.concat([current, normalized_memory], ignore_index=True).drop_duplicates(subset=["event", "pick", "probability"], keep="last")
    set_tracker(combined)

with st.expander(t("manual"), expanded=False):
    event = st.text_input(t("event"))
    sport = st.text_input(t("sport"), "unknown")
    pick = st.text_input(t("pick"))
    probability = st.number_input(t("prob"), min_value=0.0, max_value=1.0, value=0.50, step=0.01)
    predictor_score = st.number_input(t("score"), min_value=0.0, max_value=100.0, value=50.0, step=1.0)
    read = st.text_input(t("read"), "manual")
    result = st.selectbox(t("result"), ["unknown", "won", "lost"])
    if st.button(t("add")):
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
)
set_tracker(editable)

resolved = editable[editable["result"].isin(["won", "lost"])].copy()
if resolved.empty:
    st.info("Mark some results as won or lost to make ARA learn." if not IS_ES else "Marca algunos resultados como ganados o perdidos para que ARA aprenda.")
else:
    resolved["actual"] = resolved["result"].map({"won": 1.0, "lost": 0.0})
    resolved = add_probability_bucket(resolved)
    hit_rate = resolved["actual"].mean()
    avg_prob = resolved["probability"].mean()
    brier = ((resolved["probability"] - resolved["actual"]) ** 2).mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("resolved"), len(resolved))
    c2.metric(t("hit_rate"), f"{hit_rate:.1%}")
    c3.metric(t("avg_prob"), f"{avg_prob:.1%}")
    c4.metric(t("brier"), f"{brier:.3f}")

    st.subheader(t("learned"))
    tabs = st.tabs([t("buckets"), t("sports"), t("reads")])
    with tabs[0]:
        st.dataframe(summarize_group(resolved, "probability_bucket"), use_container_width=True, hide_index=True)
    with tabs[1]:
        st.dataframe(summarize_group(resolved, "sport"), use_container_width=True, hide_index=True)
    with tabs[2]:
        st.dataframe(summarize_group(resolved, "read"), use_container_width=True, hide_index=True)

    learning_memory = pd.concat([
        summarize_group(resolved, "probability_bucket").assign(memory_type="probability_bucket"),
        summarize_group(resolved, "sport").assign(memory_type="sport"),
        summarize_group(resolved, "read").assign(memory_type="read"),
    ], ignore_index=True)
    st.download_button(t("download_memory"), data=csv_text(learning_memory), file_name="ara_learning_memory.csv", mime="text/csv")

st.download_button(t("download_tracker"), data=csv_text(editable), file_name="ara_self_learning_tracker.csv", mime="text/csv")
if st.button(t("clear")):
    st.session_state.ara_learning_records = []
    st.rerun()
