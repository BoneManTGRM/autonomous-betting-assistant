from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Mapping

IDENTITY_COLUMNS = {
    "player_id": ("sdio_player_id", "PlayerID", "PlayerId", "playerid", "player_id", "Id"),
    "global_player_id": ("sdio_global_player_id", "GlobalPlayerID", "GlobalPlayerId", "globalplayerid"),
    "display_name": ("display_name", "Name", "FullName", "DisplayName", "PlayerName", "player", "player_name"),
    "first_name": ("first_name", "FirstName", "First", "GivenName"),
    "last_name": ("last_name", "LastName", "Last", "Surname"),
    "team": ("team", "Team", "TeamKey", "CurrentTeam", "PlayerTeam"),
    "position": ("position", "Position", "FantasyPosition"),
    "season": ("season", "Season", "SeasonYear"),
    "week": ("week", "Week", "Round"),
}

STAT_ALIASES = {
    "games": ("Games", "GamesPlayed", "Played", "GP"),
    "started": ("Started", "GamesStarted", "Starts"),
    "minutes": ("Minutes", "MinutesPlayed", "Min"),
    "fantasy_points": ("FantasyPoints", "FantasyPointsFanDuel", "FantasyPointsDraftKings"),
    "passing_yards": ("PassingYards", "PassYards"),
    "passing_touchdowns": ("PassingTouchdowns", "PassingTD", "PassTouchdowns"),
    "passing_attempts": ("PassingAttempts", "PassAttempts"),
    "passing_completions": ("PassingCompletions", "Completions"),
    "interceptions": ("Interceptions", "PassingInterceptions"),
    "rushing_yards": ("RushingYards", "RushYards"),
    "rushing_attempts": ("RushingAttempts", "RushAttempts", "Carries"),
    "rushing_touchdowns": ("RushingTouchdowns", "RushTouchdowns", "RushTD"),
    "receiving_yards": ("ReceivingYards", "RecYards"),
    "receptions": ("Receptions", "ReceivingReceptions", "Catches"),
    "receiving_targets": ("Targets", "ReceivingTargets"),
    "receiving_touchdowns": ("ReceivingTouchdowns", "RecTouchdowns", "RecTD"),
    "touchdowns": ("Touchdowns", "TotalTouchdowns", "TD"),
    "home_runs": ("HomeRuns", "HR"),
    "hits": ("Hits", "H"),
    "rbis": ("RunsBattedIn", "RBI", "RBIs"),
    "runs": ("Runs", "R"),
    "stolen_bases": ("StolenBases", "SB"),
    "strikeouts": ("Strikeouts", "K", "PitchingStrikeouts"),
    "innings_pitched": ("InningsPitched", "IP"),
    "goals": ("Goals", "Goal"),
    "assists": ("Assists", "Ast"),
    "shots": ("Shots", "ShotAttempts"),
    "shots_on_goal": ("ShotsOnGoal", "SOG"),
    "saves": ("Saves",),
    "blocks": ("Blocks", "BlockedShots"),
    "steals": ("Steals",),
    "rebounds": ("Rebounds", "TotalRebounds"),
    "points": ("Points",),
}

OUTPUT_ID_COLUMNS = [
    "sdio_feature_player_id",
    "sdio_feature_global_player_id",
    "sport",
    "season",
    "week",
    "display_name",
    "team",
    "position",
]

QUALITY_COLUMNS = [
    "feature_ready",
    "feature_quality_flags",
    "feature_source",
]

CORE_FEATURES = [
    "games",
    "started",
    "minutes",
    "fantasy_points",
    "passing_yards",
    "passing_touchdowns",
    "passing_attempts",
    "passing_completions",
    "interceptions",
    "rushing_yards",
    "rushing_attempts",
    "rushing_touchdowns",
    "receiving_yards",
    "receptions",
    "receiving_targets",
    "receiving_touchdowns",
    "touchdowns",
    "home_runs",
    "hits",
    "rbis",
    "runs",
    "stolen_bases",
    "strikeouts",
    "innings_pitched",
    "goals",
    "assists",
    "shots",
    "shots_on_goal",
    "saves",
    "blocks",
    "steals",
    "rebounds",
    "points",
]

RATE_DENOMINATORS = ("games", "minutes")


def _clean_key(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "").replace("_", "").replace("-", "")


def _lookup(row: Mapping[str, Any]) -> dict[str, Any]:
    return {_clean_key(key): value for key, value in row.items()}


def _first(row: Mapping[str, Any], names: tuple[str, ...]) -> Any:
    lookup = _lookup(row)
    for name in names:
        value = lookup.get(_clean_key(name))
        if value not in (None, ""):
            return value
    return ""


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _float(value: Any) -> float | None:
    text = _text(value).replace(",", "").replace("%", "")
    if not text or text.lower() in {"none", "null", "nan", "unknown"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if not math.isfinite(number):
        return None
    return number


def _number_text(value: Any) -> str:
    number = _float(value)
    if number is None:
        return ""
    return str(int(number)) if number.is_integer() else str(round(number, 6))


def _display_name(row: Mapping[str, Any]) -> str:
    direct = _text(_first(row, IDENTITY_COLUMNS["display_name"]))
    if direct:
        return direct
    first = _text(_first(row, IDENTITY_COLUMNS["first_name"]))
    last = _text(_first(row, IDENTITY_COLUMNS["last_name"]))
    return " ".join(part for part in (first, last) if part)


def _quality_flags(feature: Mapping[str, Any], stat_values: Mapping[str, float | None]) -> str:
    flags: list[str] = []
    if not feature.get("sdio_feature_player_id") and not feature.get("display_name"):
        flags.append("missing_player_identity")
    if not feature.get("team"):
        flags.append("missing_team")
    games = stat_values.get("games")
    if games is None:
        flags.append("missing_games")
    elif games <= 0:
        flags.append("zero_games")
    if not any(value not in (None, 0.0) for key, value in stat_values.items() if key not in {"games", "started", "minutes"}):
        flags.append("no_core_stats")
    return "; ".join(flags)


def _safe_rate(numerator: float | None, denominator: float | None) -> str:
    if numerator is None or denominator is None or denominator <= 0:
        return ""
    return str(round(numerator / denominator, 6))


def build_player_feature(row: Mapping[str, Any], *, sport: str = "", source: str = "SportsDataIO") -> dict[str, Any]:
    stat_values = {feature: _float(_first(row, aliases)) for feature, aliases in STAT_ALIASES.items()}
    out: dict[str, Any] = {
        "sdio_feature_player_id": _number_text(_first(row, IDENTITY_COLUMNS["player_id"])),
        "sdio_feature_global_player_id": _number_text(_first(row, IDENTITY_COLUMNS["global_player_id"])),
        "sport": sport,
        "season": _number_text(_first(row, IDENTITY_COLUMNS["season"])),
        "week": _number_text(_first(row, IDENTITY_COLUMNS["week"])),
        "display_name": _display_name(row),
        "team": _text(_first(row, IDENTITY_COLUMNS["team"])),
        "position": _text(_first(row, IDENTITY_COLUMNS["position"])),
    }

    for feature in CORE_FEATURES:
        out[feature] = _number_text(stat_values.get(feature))

    games = stat_values.get("games")
    minutes = stat_values.get("minutes")
    for feature in CORE_FEATURES:
        if feature in RATE_DENOMINATORS:
            continue
        value = stat_values.get(feature)
        out[f"{feature}_per_game"] = _safe_rate(value, games)
        out[f"{feature}_per_minute"] = _safe_rate(value, minutes)

    flags = _quality_flags(out, stat_values)
    out["feature_ready"] = str(flags == "").lower()
    out["feature_quality_flags"] = flags
    out["feature_source"] = source
    return out


def build_player_features(rows: list[Mapping[str, Any]], *, sport: str = "", source: str = "SportsDataIO") -> list[dict[str, Any]]:
    return [build_player_feature(row, sport=sport, source=source) for row in rows]


def feature_fieldnames(records: list[Mapping[str, Any]]) -> list[str]:
    rate_columns = []
    for feature in CORE_FEATURES:
        if feature in RATE_DENOMINATORS:
            continue
        rate_columns.extend([f"{feature}_per_game", f"{feature}_per_minute"])
    ordered = OUTPUT_ID_COLUMNS + CORE_FEATURES + rate_columns + QUALITY_COLUMNS
    extra = sorted({key for record in records for key in record.keys()} - set(ordered))
    return ordered + extra


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_player_features(features: list[Mapping[str, Any]], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = feature_fieldnames(features)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for feature in features:
            writer.writerow({key: feature.get(key, "") for key in fieldnames})
