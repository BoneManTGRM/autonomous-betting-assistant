from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import requests
import streamlit as st

from autonomous_betting_agent.learning import (
    GradedPrediction,
    ProbabilityCalibrator,
    fit_probability_calibrator,
    parse_graded_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
LEARNED_STATE_PATH = REPO_ROOT / "learned_state.json"
DEFAULT_GITHUB_REPOSITORY = "BoneManTGRM/autonomous-betting-agent"
DEFAULT_GITHUB_BRANCH = "main"

st.set_page_config(page_title="Learning Memory", layout="wide")


def get_secret(*names: str) -> str:
    for name in names:
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


def dedupe_rows(rows: list[GradedPrediction]) -> list[GradedPrediction]:
    seen: set[tuple[str, str, str, int]] = set()
    unique: list[GradedPrediction] = []
    for row in rows:
        key = (
            row.event_name.strip().lower(),
            row.predicted_side.strip().lower(),
            row.actual_side.strip().lower(),
            row.outcome,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def calibrator_json(calibrator: ProbabilityCalibrator) -> str:
    return json.dumps(calibrator.to_dict(), indent=2, sort_keys=True) + "\n"


def save_local_learned_state(calibrator: ProbabilityCalibrator) -> None:
    LEARNED_STATE_PATH.write_text(calibrator_json(calibrator), encoding="utf-8")


def github_put_text_file(*, path: str, content: str, message: str) -> dict[str, Any]:
    token = get_secret("GITHUB_TOKEN", "GH_TOKEN")
    if not token:
        raise RuntimeError("Missing GITHUB_TOKEN in Streamlit secrets.")

    repository = get_secret("GITHUB_REPOSITORY") or DEFAULT_GITHUB_REPOSITORY
    branch = get_secret("GITHUB_BRANCH") or DEFAULT_GITHUB_BRANCH
    url = f"https://api.github.com/repos/{repository}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    sha = None
    read_response = requests.get(url, headers=headers, params={"ref": branch}, timeout=20)
    if read_response.status_code == 200:
        sha = read_response.json().get("sha")
    elif read_response.status_code != 404:
        raise RuntimeError(f"GitHub read failed: {read_response.status_code} {read_response.text[:500]}")

    payload: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
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


st.title("Learning Memory")
st.caption(
    "Upload a finished/graded prediction CSV. The app trains learned_state.json, "
    "and the live predictor uses that calibration automatically on future scans."
)

current = current_learned_state()
if current is not None:
    cols = st.columns(4)
    cols[0].metric("Events trained", current.events_trained)
    cols[1].metric("Accuracy before", "" if current.accuracy_before is None else f"{current.accuracy_before * 100:.1f}%")
    cols[2].metric("Accuracy after", "" if current.accuracy_after is None else f"{current.accuracy_after * 100:.1f}%")
    cols[3].metric("Brier after", "" if current.brier_after is None else f"{current.brier_after:.4f}")
    with st.expander("Current learned_state.json", expanded=False):
        st.json(current.to_dict())
else:
    st.info("No learned_state.json is currently loaded.")

st.subheader("Train from finished games")
st.write(
    "Use a CSV that already has final results marked as win/loss. Accepted result columns include "
    "result, outcome, win_loss, graded_result, or status. Accepted probability columns include "
    "probability, predicted_probability, pick_probability, favorite_probability, model_probability, "
    "market_probability, no_vig_probability, or confidence_probability."
)

graded_upload = st.file_uploader(
    "Upload graded results CSV",
    type=["csv"],
    accept_multiple_files=False,
    key="graded_results_for_learning_memory",
)

settings = st.columns(4)
min_events = settings[0].number_input("Minimum graded events", min_value=5, max_value=500, value=5, step=1)
epochs = settings[1].number_input("Training epochs", min_value=100, max_value=10000, value=2500, step=100)
learning_rate = settings[2].number_input("Learning rate", min_value=0.001, max_value=0.5, value=0.05, step=0.001, format="%.3f")
l2 = settings[3].number_input("Regularization", min_value=0.0, max_value=1.0, value=0.01, step=0.001, format="%.3f")

save_to_github = st.toggle(
    "Save learned_state.json back to GitHub so the app remembers after restart",
    value=bool(get_secret("GITHUB_TOKEN", "GH_TOKEN")),
)

if save_to_github and not get_secret("GITHUB_TOKEN", "GH_TOKEN"):
    st.warning("GitHub saving is enabled, but GITHUB_TOKEN is missing from Streamlit secrets. Local learning will still work for this running session.")

if st.button("Train and remember", type="primary", use_container_width=True):
    if graded_upload is None:
        st.warning("Upload a graded results CSV first.")
        st.stop()

    csv_bytes = graded_upload.getvalue()
    with NamedTemporaryFile(delete=False, suffix=".csv") as handle:
        handle.write(csv_bytes)
        temp_path = Path(handle.name)

    try:
        parsed_rows = parse_graded_csv(temp_path)
        rows = dedupe_rows(parsed_rows)
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass

    if len(rows) < int(min_events):
        st.error(f"Found {len(rows)} usable unique graded rows. Need at least {int(min_events)}.")
        st.stop()

    calibrator = fit_probability_calibrator(
        rows,
        epochs=int(epochs),
        learning_rate=float(learning_rate),
        l2=float(l2),
        min_events=int(min_events),
        source=getattr(graded_upload, "name", "uploaded_graded_results.csv"),
    )
    calibrator.notes.append(f"Parsed {len(parsed_rows)} usable graded rows; trained on {len(rows)} unique rows.")
    save_local_learned_state(calibrator)

    st.success("Learning memory updated locally for this running app session.")
    if save_to_github:
        try:
            github_put_text_file(
                path="learned_state.json",
                content=calibrator_json(calibrator),
                message=f"Update learned calibration from graded results {datetime.now(timezone.utc).date().isoformat()}",
            )
            st.success("learned_state.json was also saved to GitHub. Streamlit should redeploy or reload from the updated repo.")
        except Exception as exc:
            st.error(f"Could not save learned_state.json to GitHub: {exc}")

    st.subheader("New learned state")
    st.json(calibrator.to_dict())
