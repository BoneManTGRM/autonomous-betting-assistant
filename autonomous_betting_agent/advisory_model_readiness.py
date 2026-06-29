from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd

from autonomous_betting_agent.model_status_constants import *
from autonomous_betting_agent.model_status_results import brier_score, outcome_value
from autonomous_betting_agent.model_status_utils import EVENT_FIELDS, PICK_FIELDS, PROB_FIELDS, clean, present, records, result_column

PREFIX = "advisory_shadow_"


def k(name: str) -> str:
    return PREFIX + name


def _event_identity(row: Mapping[str, Any]) -> str:
    for field in EVENT_FIELDS:
        value = clean(row.get(field))
        if value:
            return value.lower().replace(" ", "_")
    return ""


def model_readiness_diagnostics(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    rows = records(rows_or_frame)
    result_field = result_column(rows)
    prob_present = bool(present(rows, PROB_FIELDS))
    pick_present = bool(present(rows, PICK_FIELDS))
    event_ids = [_event_identity(row) for row in rows]
    event_present = any(event_ids)
    unique_events = {event for event in event_ids if event}
    results = [outcome_value(row.get(result_field)) for row in rows] if result_field else []
    wins = results.count("win")
    losses = results.count("loss")
    pushes = results.count("push")
    cancels = results.count("cancel")
    usable = wins + losses
    completed_events = len({event for event, result in zip(event_ids, results) if event and result in {"win", "loss"}})
    duplicates = max(0, len(rows) - len(unique_events)) if rows else 0
    duplicate_rate = duplicates / len(rows) if rows else 0.0
    cal_ok, brier = brier_score(rows, result_field)
    if not result_field:
        status = NEEDS_RESULT_FIELD
    elif not prob_present:
        status = NEEDS_PROBABILITY_FIELD
    elif not pick_present:
        status = NEEDS_SELECTION_FIELD
    elif not event_present:
        status = NEEDS_EVENT_IDENTITY
    elif usable == 0:
        status = NEEDS_GRADED_ROWS
    elif duplicate_rate > 0.25:
        status = DUPLICATE_HEAVY_SAMPLE
    elif completed_events < 50:
        status = NEEDS_MORE_COMPLETED_EVENTS
    elif not wins or not losses:
        status = NEEDS_OUTCOME_DIVERSITY
    elif completed_events >= 100:
        status = SHADOW_READY
    else:
        status = READY_FOR_OBSERVATION_ONLY
    score = min(100, (15 if result_field else 0) + (15 if prob_present else 0) + (10 if pick_present else 0) + (10 if event_present else 0) + (15 if completed_events >= 50 else 0) + (10 if completed_events >= 100 else 0) + (10 if wins and losses else 0) + (10 if duplicate_rate <= 0.25 else 0) + (10 if cal_ok else 0) + 5)
    return {k("readiness_status"): status, k("readiness_score"): int(score), k("readiness_reason"): status.lower(), k("training_guidance"): status.lower(), k("minimum_required_completed_events"): 50, k("completed_event_count"): completed_events, k("completed_row_count"): usable, k("unique_event_count"): len(unique_events), k("duplicate_row_count"): duplicates, k("duplicate_rate"): round(duplicate_rate, 6), k("win_count"): wins, k("loss_count"): losses, k("push_count"): pushes, k("cancel_count"): cancels, k("graded_usable_count"): usable, k("outcome_diversity_status"): "HAS_WINS_AND_LOSSES" if wins and losses else "MISSING_WIN_OR_LOSS_DIVERSITY", k("probability_field_present"): prob_present, k("selection_field_present"): pick_present, k("result_field_present"): bool(result_field), k("event_identity_present"): event_present, k("calibration_available"): cal_ok, k("brier_score"): brier, k("probability_bucket_summary"): "[]", k("drift_signal"): "insufficient_data", k("observation_only"): True, k("live_mutation_allowed"): False}


def apply_model_readiness_fields(rows_or_frame, config=None):
    rows = records(rows_or_frame)
    data = model_readiness_diagnostics(rows, config=config)
    out = []
    for row in rows:
        item = dict(row)
        item.update(data)
        out.append(item)
    return out


def model_readiness_summary(rows_or_frame, config=None):
    return pd.DataFrame([model_readiness_diagnostics(rows_or_frame, config=config)])
