from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .profit_goal import parse_result, unit_profit_loss

OPENING_COLUMNS = ("opening_odds", "open_odds", "open_price")
ENTRY_COLUMNS = ("entry_odds", "best_price", "price", "odds", "decimal_odds")
CLOSING_COLUMNS = ("closing_odds", "closing_price", "close_odds", "close_price")
SPORT_COLUMNS = ("sport", "league", "competition")
MARKET_COLUMNS = ("market", "market_key", "prop_type", "bet_type")
RESULT_COLUMNS = ("result", "outcome", "win_loss", "graded_result", "status")


@dataclass(frozen=True)
class MovementProfile:
    profile_key: str
    samples: int
    wins: int
    losses: int
    win_rate: float | None
    roi: float | None
    average_clv: float | None
    market_support_score: float


@dataclass(frozen=True)
class LineMovementReport:
    raw_rows: int
    enriched_rows: int
    profile_count: int
    with_opening_rows: int
    with_entry_rows: int
    with_closing_rows: int
    positive_clv_rows: int
    negative_clv_rows: int
    output_csv: str | None
    notes: list[str]


def _clean_key(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _lookup(row: Mapping[str, Any]) -> dict[str, Any]:
    return {_clean_key(str(key)): value for key, value in row.items()}


def _first(row: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    lookup = _lookup(row)
    for key in keys:
        value = lookup.get(_clean_key(key))
        if value not in (None, ""):
            return value
    return ""


def _float(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "").replace("%", "")
    if not text or text.lower() in {"none", "null", "nan", "unknown"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_price(value: Any) -> float | None:
    price = _float(value)
    if price is None:
        return None
    if price >= 100:
        return 1.0 + price / 100.0
    if price <= -100:
        return 1.0 + 100.0 / abs(price)
    if price > 1.0:
        return price
    return None


def _scope(row: Mapping[str, Any]) -> str:
    sport = str(_first(row, SPORT_COLUMNS)).strip().lower()
    market = str(_first(row, MARKET_COLUMNS)).strip().lower()
    return f"{sport}|{market}"


def movement_direction(entry_odds: float | None, closing_odds: float | None) -> str:
    if entry_odds is None or closing_odds is None:
        return "unknown"
    delta = entry_odds - closing_odds
    if abs(delta) < 0.000001:
        return "flat"
    return "toward_pick" if delta > 0 else "against_pick"


def movement_strength(entry_odds: float | None, closing_odds: float | None) -> float | None:
    if entry_odds is None or closing_odds is None or entry_odds <= 0:
        return None
    return round((entry_odds - closing_odds) / entry_odds, 6)


def opening_to_entry_movement(opening_odds: float | None, entry_odds: float | None) -> float | None:
    if opening_odds is None or entry_odds is None or opening_odds <= 0:
        return None
    return round((entry_odds - opening_odds) / opening_odds, 6)


def _profile_key(row: Mapping[str, Any]) -> str:
    entry = parse_price(_first(row, ENTRY_COLUMNS))
    close = parse_price(_first(row, CLOSING_COLUMNS))
    return f"{_scope(row)}|{movement_direction(entry, close)}"


def build_line_movement_profiles(rows: list[Mapping[str, Any]], *, min_samples: int = 10) -> dict[str, MovementProfile]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        key = _profile_key(row)
        if key.endswith("|unknown"):
            continue
        grouped.setdefault(key, []).append(row)

    profiles: dict[str, MovementProfile] = {}
    for key, group in grouped.items():
        wins = losses = 0
        profits: list[float] = []
        clvs: list[float] = []
        for row in group:
            result = parse_result(_first(row, RESULT_COLUMNS))
            entry = parse_price(_first(row, ENTRY_COLUMNS))
            close = parse_price(_first(row, CLOSING_COLUMNS))
            if result == "win":
                wins += 1
            elif result == "loss":
                losses += 1
            if result in {"win", "loss", "push"}:
                profits.append(unit_profit_loss(result, entry))
            clv = movement_strength(entry, close)
            if clv is not None:
                clvs.append(clv)
        decisions = wins + losses
        if decisions < min_samples:
            continue
        win_rate = wins / decisions if decisions else None
        roi = sum(profits) / decisions if decisions and profits else None
        avg_clv = sum(clvs) / len(clvs) if clvs else None
        score = 50.0
        if win_rate is not None:
            score += (win_rate - 0.50) * 80.0
        if roi is not None:
            score += roi * 30.0
        if avg_clv is not None:
            score += avg_clv * 200.0
        profiles[key] = MovementProfile(
            profile_key=key,
            samples=decisions,
            wins=wins,
            losses=losses,
            win_rate=None if win_rate is None else round(win_rate, 6),
            roi=None if roi is None else round(roi, 6),
            average_clv=None if avg_clv is None else round(avg_clv, 6),
            market_support_score=round(max(0.0, min(100.0, score)), 2),
        )
    return profiles


def enrich_line_movement_rows(rows: list[Mapping[str, Any]], history_rows: list[Mapping[str, Any]] | None = None, *, min_profile_samples: int = 10) -> list[dict[str, Any]]:
    profiles = build_line_movement_profiles(history_rows or [], min_samples=min_profile_samples)
    enriched: list[dict[str, Any]] = []
    for row in rows:
        out = dict(row)
        opening = parse_price(_first(row, OPENING_COLUMNS))
        entry = parse_price(_first(row, ENTRY_COLUMNS))
        close = parse_price(_first(row, CLOSING_COLUMNS))
        direction = movement_direction(entry, close)
        strength = movement_strength(entry, close)
        open_entry = opening_to_entry_movement(opening, entry)
        profile_key = f"{_scope(row)}|{direction}"
        profile = profiles.get(profile_key)
        out["opening_odds"] = "" if opening is None else str(round(opening, 6))
        out["entry_odds"] = "" if entry is None else str(round(entry, 6))
        out["closing_odds"] = "" if close is None else str(round(close, 6))
        out["line_movement_direction"] = direction
        out["line_movement_strength"] = "" if strength is None else str(strength)
        out["opening_to_entry_movement"] = "" if open_entry is None else str(open_entry)
        out["line_movement_profile_key"] = profile_key
        out["line_movement_profile_samples"] = "" if profile is None else str(profile.samples)
        out["market_support_score"] = "" if profile is None else str(profile.market_support_score)
        out["clv_history_score"] = "" if profile is None else str(profile.market_support_score)
        enriched.append(out)
    return enriched


def summarize_line_movement(rows: list[Mapping[str, Any]], history_rows: list[Mapping[str, Any]] | None = None, *, output_csv: str | None = None) -> LineMovementReport:
    profiles = build_line_movement_profiles(history_rows or [])
    strengths = [_float(row.get("line_movement_strength")) for row in rows]
    strengths = [item for item in strengths if item is not None]
    return LineMovementReport(
        raw_rows=len(rows),
        enriched_rows=len(rows),
        profile_count=len(profiles),
        with_opening_rows=sum(1 for row in rows if row.get("opening_odds") not in (None, "")),
        with_entry_rows=sum(1 for row in rows if row.get("entry_odds") not in (None, "")),
        with_closing_rows=sum(1 for row in rows if row.get("closing_odds") not in (None, "")),
        positive_clv_rows=sum(1 for item in strengths if item > 0),
        negative_clv_rows=sum(1 for item in strengths if item < 0),
        output_csv=output_csv,
        notes=[
            "Line movement toward the pick means entry odds were better than closing odds for that selection.",
            "Historical movement profiles estimate whether similar market movement has produced wins, ROI and CLV.",
        ],
    )


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


def write_report(report: LineMovementReport, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
