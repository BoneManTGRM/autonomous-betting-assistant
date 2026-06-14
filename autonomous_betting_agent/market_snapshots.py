from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .live_odds import LiveEventSummary

SNAPSHOT_COLUMNS = [
    "snapshot_time_utc",
    "event_id",
    "sport_key",
    "sport_title",
    "commence_time",
    "home_team",
    "away_team",
    "outcome",
    "is_favorite",
    "normalized_probability",
    "raw_probability",
    "average_price",
    "best_price",
    "worst_price",
    "price_range",
    "best_bookmaker",
    "source_count",
    "bookmaker_count",
    "market_overround",
]

MOVEMENT_COLUMNS = [
    "opening_probability",
    "current_probability",
    "probability_move",
    "probability_move_abs",
    "opening_best_price",
    "current_best_price",
    "best_price_move",
    "best_price_move_abs",
    "movement_signal",
    "movement_strength",
    "market_confidence_score",
    "opening_snapshot_time_utc",
    "latest_snapshot_time_utc",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def event_snapshot_rows(summary: LiveEventSummary, snapshot_time_utc: str | None = None) -> list[dict[str, Any]]:
    taken_at = snapshot_time_utc or utc_now_iso()
    rows: list[dict[str, Any]] = []
    for outcome in summary.outcomes:
        rows.append({
            "snapshot_time_utc": taken_at,
            "event_id": summary.event_id,
            "sport_key": summary.sport_key,
            "sport_title": summary.sport_title,
            "commence_time": summary.commence_time,
            "home_team": summary.home_team,
            "away_team": summary.away_team,
            "outcome": outcome.name,
            "is_favorite": outcome.name == summary.favorite,
            "normalized_probability": outcome.normalized_probability,
            "raw_probability": outcome.raw_probability,
            "average_price": outcome.average_price,
            "best_price": outcome.best_price,
            "worst_price": outcome.worst_price,
            "price_range": outcome.price_range,
            "best_bookmaker": outcome.best_bookmaker,
            "source_count": outcome.source_count,
            "bookmaker_count": summary.bookmaker_count,
            "market_overround": summary.market_overround,
        })
    return rows


def summaries_to_snapshot_frame(summaries: Iterable[LiveEventSummary], snapshot_time_utc: str | None = None) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    taken_at = snapshot_time_utc or utc_now_iso()
    for summary in summaries:
        rows.extend(event_snapshot_rows(summary, taken_at))
    return pd.DataFrame(rows, columns=SNAPSHOT_COLUMNS)


def append_snapshot_csv(rows: pd.DataFrame, path: str | Path) -> pd.DataFrame:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        existing = pd.read_csv(output_path)
        combined = pd.concat([existing, rows], ignore_index=True)
    else:
        combined = rows.copy()
    combined = combined.drop_duplicates(subset=["snapshot_time_utc", "event_id", "outcome"], keep="last")
    combined.to_csv(output_path, index=False)
    return combined


def _movement_signal(probability_move: float | None) -> tuple[str, str]:
    if probability_move is None or pd.isna(probability_move):
        return "NO_DATA", "none"
    move = float(probability_move)
    abs_move = abs(move)
    if abs_move >= 0.05:
        strength = "strong"
    elif abs_move >= 0.02:
        strength = "moderate"
    elif abs_move >= 0.01:
        strength = "small"
    else:
        return "STABLE", "none"
    return ("STEAM" if move > 0 else "DRIFT", strength)


def _confidence_score(row: pd.Series) -> int:
    score = 50
    books = row.get("bookmaker_count")
    overround = row.get("market_overround")
    price_range = row.get("price_range")
    movement = row.get("probability_move_abs")
    try:
        if pd.notna(books):
            score += min(20, max(0, int(books) * 2))
    except (TypeError, ValueError):
        pass
    try:
        if pd.notna(overround):
            score -= int(max(0.0, float(overround)) * 100)
    except (TypeError, ValueError):
        pass
    try:
        if pd.notna(price_range):
            score -= min(20, int(abs(float(price_range)) * 50))
    except (TypeError, ValueError):
        pass
    try:
        if pd.notna(movement) and float(movement) >= 0.02:
            score += min(15, int(float(movement) * 200))
    except (TypeError, ValueError):
        pass
    return max(0, min(100, score))


def add_line_movement(snapshot_frame: pd.DataFrame) -> pd.DataFrame:
    if snapshot_frame.empty:
        out = snapshot_frame.copy()
        for column in MOVEMENT_COLUMNS:
            out[column] = pd.Series(dtype="object")
        return out

    work = snapshot_frame.copy()
    work["_snapshot_dt"] = pd.to_datetime(work["snapshot_time_utc"], errors="coerce", utc=True)
    work["_snapshot_sort"] = work["_snapshot_dt"].fillna(pd.Timestamp.min.tz_localize("UTC"))
    sort_cols = ["event_id", "outcome", "_snapshot_sort"]
    work = work.sort_values(sort_cols).reset_index(drop=True)
    group_cols = ["event_id", "outcome"]
    first = work.groupby(group_cols, dropna=False).first().reset_index()
    last = work.groupby(group_cols, dropna=False).last().reset_index()
    movement = first[group_cols + ["normalized_probability", "best_price", "snapshot_time_utc"]].merge(
        last[group_cols + ["normalized_probability", "best_price", "snapshot_time_utc"]],
        on=group_cols,
        suffixes=("_opening", "_current"),
    )
    movement["opening_probability"] = movement["normalized_probability_opening"]
    movement["current_probability"] = movement["normalized_probability_current"]
    movement["probability_move"] = movement["current_probability"] - movement["opening_probability"]
    movement["probability_move_abs"] = movement["probability_move"].abs()
    movement["opening_best_price"] = movement["best_price_opening"]
    movement["current_best_price"] = movement["best_price_current"]
    movement["best_price_move"] = movement["current_best_price"] - movement["opening_best_price"]
    movement["best_price_move_abs"] = movement["best_price_move"].abs()
    movement["movement_signal"] = movement["probability_move"].apply(lambda value: _movement_signal(value)[0])
    movement["movement_strength"] = movement["probability_move"].apply(lambda value: _movement_signal(value)[1])
    movement["opening_snapshot_time_utc"] = movement["snapshot_time_utc_opening"]
    movement["latest_snapshot_time_utc"] = movement["snapshot_time_utc_current"]
    keep = group_cols + [column for column in MOVEMENT_COLUMNS if column != "market_confidence_score"]
    enriched = work.merge(movement[keep], on=group_cols, how="left").drop(columns=["_snapshot_dt", "_snapshot_sort"])
    enriched["market_confidence_score"] = enriched.apply(_confidence_score, axis=1)
    return enriched


def latest_snapshot_with_movement(snapshot_frame: pd.DataFrame) -> pd.DataFrame:
    moved = add_line_movement(snapshot_frame)
    if moved.empty:
        return moved
    moved["_snapshot_dt"] = pd.to_datetime(moved["snapshot_time_utc"], errors="coerce", utc=True)
    moved = moved.sort_values(["event_id", "outcome", "_snapshot_dt"])
    latest = moved.groupby(["event_id", "outcome"], dropna=False).tail(1).reset_index(drop=True)
    return latest.drop(columns=["_snapshot_dt"])


def top_market_movers(snapshot_frame: pd.DataFrame, limit: int = 25) -> pd.DataFrame:
    latest = latest_snapshot_with_movement(snapshot_frame)
    if latest.empty or "probability_move_abs" not in latest.columns:
        return latest
    return latest.sort_values(["probability_move_abs", "market_confidence_score"], ascending=[False, False]).head(limit).reset_index(drop=True)
