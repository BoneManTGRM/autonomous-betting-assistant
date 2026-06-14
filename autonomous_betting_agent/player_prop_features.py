from __future__ import annotations

import csv
import math
import re
from pathlib import Path
from typing import Any, Mapping

from .player_props import normalize_prop_type

PLAYER_KEY_COLUMNS = ("player_id", "sdio_player_id", "sdio_feature_player_id", "PlayerID", "PlayerId")
PLAYER_NAME_COLUMNS = ("player", "player_name", "athlete", "name", "display_name", "PlayerName")
PROP_TYPE_COLUMNS = ("prop_type", "market", "stat", "bet_type")
PROP_LINE_COLUMNS = ("line", "prop_line", "stat_line", "threshold", "total", "handicap")
PROP_SIDE_COLUMNS = ("side", "over_under", "selection_side", "direction")

FEATURE_OUTPUT_COLUMNS = [
    "feature_match_status",
    "feature_match_key",
    "feature_expected_value",
    "feature_season_rate",
    "feature_usage_rate",
    "feature_sample_size",
    "feature_data_quality",
    "feature_reason",
]

PROP_FEATURE_MAP = {
    "passing_yards": "passing_yards_per_game",
    "rush_yards": "rushing_yards_per_game",
    "receiving_yards": "receiving_yards_per_game",
    "reception": "receptions_per_game",
    "touchdown": "touchdowns_per_game",
    "home_run": "home_runs_per_game",
    "hit": "hits_per_game",
    "strikeout": "strikeouts_per_game",
    "goal": "goals_per_game",
    "assist": "assists_per_game",
    "shot_on_goal": "shots_on_goal_per_game",
}

USAGE_FEATURES = {
    "passing_yards": ("passing_attempts_per_game",),
    "rush_yards": ("rushing_attempts_per_game",),
    "receiving_yards": ("receiving_targets_per_game", "receptions_per_game"),
    "reception": ("receiving_targets_per_game", "receptions_per_game"),
    "touchdown": ("rushing_attempts_per_game", "receiving_targets_per_game"),
    "home_run": ("hits_per_game",),
    "hit": ("hits_per_game",),
    "strikeout": ("innings_pitched_per_game",),
    "goal": ("shots_on_goal_per_game", "shots_per_game"),
    "assist": ("assists_per_game",),
    "shot_on_goal": ("shots_on_goal_per_game", "shots_per_game"),
}

BINARY_PROP_TYPES = {"touchdown", "home_run", "goal", "assist", "hit"}
LINE_PROP_TYPES = {"passing_yards", "rush_yards", "receiving_yards", "reception", "strikeout", "shot_on_goal"}


def _clean_key(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _lookup(row: Mapping[str, Any]) -> dict[str, Any]:
    return {_clean_key(key): value for key, value in row.items()}


def _first(row: Mapping[str, Any], names: tuple[str, ...]) -> Any:
    lookup = _lookup(row)
    for name in names:
        value = lookup.get(_clean_key(name))
        if value not in (None, ""):
            return value
    return ""


def _norm_name(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _float(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "").replace("%", "")
    if not text or text.lower() in {"none", "null", "nan", "unknown"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if not math.isfinite(number):
        return None
    return number


def _fmt(value: float | None) -> str:
    return "" if value is None else str(round(value, 6))


def _clamp_probability(value: float) -> float:
    return max(0.01, min(0.99, value))


def _player_id(row: Mapping[str, Any]) -> str:
    value = str(_first(row, PLAYER_KEY_COLUMNS)).strip()
    if value.endswith(".0"):
        value = value[:-2]
    return value


def _player_name(row: Mapping[str, Any]) -> str:
    return str(_first(row, PLAYER_NAME_COLUMNS)).strip()


def _prop_side(row: Mapping[str, Any]) -> str:
    side = str(_first(row, PROP_SIDE_COLUMNS)).strip().lower()
    selection = str(_first(row, ("selection", "pick", "prediction"))).strip().lower()
    text = " ".join([side, selection])
    if "under" in text or text in {"no", "n"} or " no " in f" {text} ":
        return "under"
    if "over" in text or text in {"yes", "y"} or " yes " in f" {text} ":
        return "over"
    return "over"


def _feature_rate(feature_row: Mapping[str, Any], prop_type: str) -> tuple[float | None, str]:
    column = PROP_FEATURE_MAP.get(prop_type)
    if not column:
        return None, "unsupported_prop_type"
    value = _float(feature_row.get(column))
    return value, column


def _line_probability(rate: float | None, line: float | None) -> float | None:
    if rate is None or line is None or line <= 0:
        return None
    return _clamp_probability(0.5 + (rate - line) / (2.0 * line))


def _binary_probability(rate: float | None) -> float | None:
    if rate is None:
        return None
    if rate < 0:
        return None
    return _clamp_probability(1.0 - math.exp(-rate))


def _usage_rate(feature_row: Mapping[str, Any], prop_type: str) -> float | None:
    values = []
    for column in USAGE_FEATURES.get(prop_type, ()): 
        value = _float(feature_row.get(column))
        if value is not None and value >= 0:
            values.append(value)
    if not values:
        return None
    # Convert usage volume into a bounded support signal. This is not a true probability;
    # it simply gives the player-prop model a conservative usage input.
    return _clamp_probability(sum(values) / len(values) / 10.0)


def _feature_data_quality(feature_row: Mapping[str, Any]) -> float:
    flags = str(feature_row.get("feature_quality_flags", "")).strip()
    ready = str(feature_row.get("feature_ready", "")).strip().lower() == "true"
    if ready and not flags:
        return 90.0
    if flags:
        penalty = min(45.0, 12.0 * len([flag for flag in flags.split(";") if flag.strip()]))
        return max(40.0, 85.0 - penalty)
    return 75.0


def _sample_size(feature_row: Mapping[str, Any]) -> str:
    games = _float(feature_row.get("games"))
    return "" if games is None else str(int(round(games)))


def build_feature_index(features: list[Mapping[str, Any]]) -> tuple[dict[str, Mapping[str, Any]], dict[str, list[Mapping[str, Any]]]]:
    by_id: dict[str, Mapping[str, Any]] = {}
    by_name: dict[str, list[Mapping[str, Any]]] = {}
    for feature in features:
        player_id = _player_id(feature)
        if player_id:
            by_id[player_id] = feature
        name = _norm_name(_player_name(feature))
        if name:
            by_name.setdefault(name, []).append(feature)
    return by_id, by_name


def match_feature_row(prop_row: Mapping[str, Any], by_id: Mapping[str, Mapping[str, Any]], by_name: Mapping[str, list[Mapping[str, Any]]]) -> tuple[str, str, Mapping[str, Any] | None]:
    player_id = _player_id(prop_row)
    if player_id and player_id in by_id:
        return "matched", f"id:{player_id}", by_id[player_id]
    name = _norm_name(_player_name(prop_row))
    if name and name in by_name:
        rows = by_name[name]
        if len(rows) == 1:
            return "matched", f"name:{name}", rows[0]
        return "ambiguous", f"name:{name}", None
    return "unmatched", "", None


def enrich_prop_with_player_feature(prop_row: Mapping[str, Any], by_id: Mapping[str, Mapping[str, Any]], by_name: Mapping[str, list[Mapping[str, Any]]]) -> dict[str, Any]:
    out = dict(prop_row)
    for column in FEATURE_OUTPUT_COLUMNS:
        out.setdefault(column, "")
    status, key, feature = match_feature_row(prop_row, by_id, by_name)
    out["feature_match_status"] = status
    out["feature_match_key"] = key
    if feature is None:
        out["feature_reason"] = "no_unique_player_feature_match"
        return out

    prop_type = normalize_prop_type(_first(prop_row, PROP_TYPE_COLUMNS))
    rate, source_column = _feature_rate(feature, prop_type)
    line = _float(_first(prop_row, PROP_LINE_COLUMNS))
    side = _prop_side(prop_row)

    if prop_type in LINE_PROP_TYPES:
        season_rate = _line_probability(rate, line)
        reason = f"line_model_from_{source_column}"
    elif prop_type in BINARY_PROP_TYPES:
        season_rate = _binary_probability(rate)
        reason = f"binary_poisson_model_from_{source_column}"
    else:
        season_rate = None
        reason = "unsupported_prop_type"

    if season_rate is not None and side == "under":
        season_rate = _clamp_probability(1.0 - season_rate)
        reason += "_inverted_for_under"

    out["feature_expected_value"] = _fmt(rate)
    out["feature_season_rate"] = _fmt(season_rate)
    out["feature_usage_rate"] = _fmt(_usage_rate(feature, prop_type))
    out["feature_sample_size"] = _sample_size(feature)
    out["feature_data_quality"] = _fmt(_feature_data_quality(feature))
    out["feature_reason"] = reason

    # Fill the columns consumed by the existing player-prop scorer only when the
    # prediction row does not already provide stronger direct model inputs.
    out.setdefault("season_rate", out["feature_season_rate"])
    if not out.get("season_rate"):
        out["season_rate"] = out["feature_season_rate"]
    out.setdefault("usage_rate", out["feature_usage_rate"])
    if not out.get("usage_rate"):
        out["usage_rate"] = out["feature_usage_rate"]
    out.setdefault("sample_size", out["feature_sample_size"])
    if not out.get("sample_size"):
        out["sample_size"] = out["feature_sample_size"]
    out.setdefault("data_quality", out["feature_data_quality"])
    if not out.get("data_quality"):
        out["data_quality"] = out["feature_data_quality"]
    return out


def enrich_props_with_player_features(props: list[Mapping[str, Any]], features: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_id, by_name = build_feature_index(features)
    return [enrich_prop_with_player_feature(prop, by_id, by_name) for prop in props]


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(rows: list[Mapping[str, Any]], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
