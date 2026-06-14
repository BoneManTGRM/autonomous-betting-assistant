from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Mapping

RESULT_OUTPUT_COLUMNS = [
    "sdio_result_match_status",
    "sdio_result_game_id",
    "sdio_result_home_team",
    "sdio_result_away_team",
    "sdio_result_home_score",
    "sdio_result_away_score",
    "sdio_result_winner",
    "sdio_result_status",
    "sdio_result_source",
    "sdio_result_note",
    "result",
    "actual_winner",
]

PREDICTION_EVENT_COLUMNS = ("event", "event_name", "game", "match", "fixture")
PREDICTION_PICK_COLUMNS = ("prediction", "pick", "predicted_side", "selection", "team")
PREDICTION_GAME_ID_COLUMNS = ("sdio_game_id", "sportsdataio_game_id", "game_id")
PREDICTION_HOME_COLUMNS = ("home_team", "event_home", "home")
PREDICTION_AWAY_COLUMNS = ("away_team", "event_away", "away")
GAME_ID_COLUMNS = ("sdio_game_id", "game_id", "GameID", "GameId")


def _clean_key(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def _lookup(row: Mapping[str, Any]) -> dict[str, Any]:
    return {_clean_key(key): value for key, value in row.items()}


def _first(row: Mapping[str, Any], names: tuple[str, ...]) -> str:
    lookup = _lookup(row)
    for name in names:
        value = lookup.get(_clean_key(name))
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _norm(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _contains_team_pair(event_text: str, home_team: str, away_team: str) -> bool:
    event = f" {_norm(event_text)} "
    home = f" {_norm(home_team)} "
    away = f" {_norm(away_team)} "
    if not home.strip() or not away.strip():
        return False
    return home in event and away in event


def _teams_match(pred_home: str, pred_away: str, game: Mapping[str, Any]) -> bool:
    if not pred_home or not pred_away:
        return False
    return _norm(pred_home) == _norm(game.get("home_team")) and _norm(pred_away) == _norm(game.get("away_team"))


def _game_id(row: Mapping[str, Any], names: tuple[str, ...]) -> str:
    value = _first(row, names)
    if value.endswith(".0"):
        value = value[:-2]
    return value


def _is_final_game(game: Mapping[str, Any]) -> bool:
    is_final = str(game.get("is_final", "")).strip().lower()
    status = str(game.get("status", "")).strip().lower()
    return is_final == "true" or status in {"final", "f", "closed", "completed", "complete", "final/ot", "final ot"}


def _winner(game: Mapping[str, Any]) -> str:
    return str(game.get("winner", "")).strip()


def _pick_result(pick: str, winner: str) -> str:
    if not pick or not winner:
        return "unknown"
    pick_norm = _norm(pick)
    winner_norm = _norm(winner)
    if winner_norm == "push":
        return "push"
    return "won" if pick_norm == winner_norm else "lost"


def match_game(prediction: Mapping[str, Any], games: list[Mapping[str, Any]]) -> tuple[str, Mapping[str, Any] | None, str]:
    prediction_game_id = _game_id(prediction, PREDICTION_GAME_ID_COLUMNS)
    if prediction_game_id:
        matches = [game for game in games if _game_id(game, GAME_ID_COLUMNS) == prediction_game_id]
        if len(matches) == 1:
            return "matched", matches[0], "matched_by_game_id"
        if len(matches) > 1:
            return "ambiguous", None, "multiple_games_with_same_id"

    pred_home = _first(prediction, PREDICTION_HOME_COLUMNS)
    pred_away = _first(prediction, PREDICTION_AWAY_COLUMNS)
    if pred_home and pred_away:
        matches = [game for game in games if _teams_match(pred_home, pred_away, game)]
        if len(matches) == 1:
            return "matched", matches[0], "matched_by_home_away"
        if len(matches) > 1:
            return "ambiguous", None, "multiple_games_with_same_home_away"

    event_text = _first(prediction, PREDICTION_EVENT_COLUMNS)
    if event_text:
        matches = [game for game in games if _contains_team_pair(event_text, str(game.get("home_team", "")), str(game.get("away_team", "")))]
        if len(matches) == 1:
            return "matched", matches[0], "matched_by_event_text"
        if len(matches) > 1:
            return "ambiguous", None, "multiple_event_text_matches"

    return "unmatched", None, "no_sportsdataio_game_match"


def enrich_prediction_with_result(prediction: Mapping[str, Any], games: list[Mapping[str, Any]]) -> dict[str, Any]:
    out = dict(prediction)
    status, game, note = match_game(prediction, games)
    for column in RESULT_OUTPUT_COLUMNS:
        out.setdefault(column, "")
    out["sdio_result_match_status"] = status
    out["sdio_result_note"] = note
    out["sdio_result_source"] = "SportsDataIO"

    if not game:
        return out

    out["sdio_result_game_id"] = _game_id(game, GAME_ID_COLUMNS)
    out["sdio_result_home_team"] = str(game.get("home_team", ""))
    out["sdio_result_away_team"] = str(game.get("away_team", ""))
    out["sdio_result_home_score"] = str(game.get("home_score", ""))
    out["sdio_result_away_score"] = str(game.get("away_score", ""))
    out["sdio_result_winner"] = _winner(game)
    out["sdio_result_status"] = str(game.get("status", ""))

    if not _is_final_game(game):
        out["sdio_result_match_status"] = "not_final"
        out["sdio_result_note"] = "matched_but_game_not_final"
        return out

    winner = _winner(game)
    pick = _first(prediction, PREDICTION_PICK_COLUMNS)
    result = _pick_result(pick, winner)
    out["actual_winner"] = winner
    out["result"] = result
    return out


def enrich_predictions_with_results(predictions: list[Mapping[str, Any]], games: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_prediction_with_result(prediction, games) for prediction in predictions]


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
