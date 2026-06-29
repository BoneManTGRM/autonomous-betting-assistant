from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

import pandas as pd

RESULT_FIELDS = ("result", "grade", "outcome", "pick_result", "final_result", "official_result", "settled_status", "result_status")
PROB_FIELDS = ("model_probability", "model_probability_clean", "final_probability", "probability", "confidence_probability")
PICK_FIELDS = ("prediction", "selection", "pick", "team", "public_pick")
EVENT_FIELDS = ("event_id", "game_id", "match_id", "event", "event_name", "matchup", "game")


def records(rows: Sequence[Mapping[str, Any]] | pd.DataFrame | None) -> list[dict[str, Any]]:
    if rows is None:
        return []
    if isinstance(rows, pd.DataFrame):
        return rows.to_dict("records")
    return [deepcopy(dict(row)) for row in rows if isinstance(row, Mapping)]


def clean(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in {"none", "nan", "null", "nat"} else text


def present(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str | None:
    for field in fields:
        if any(clean(row.get(field)) for row in rows if field in row):
            return field
    return None
