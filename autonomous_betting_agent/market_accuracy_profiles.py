from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .profit_goal import parse_price, parse_result, unit_profit_loss

SPORT_COLUMNS = ("sport", "league", "competition")
MARKET_COLUMNS = ("market", "market_key", "prop_type", "bet_type")
PRICE_COLUMNS = ("best_price", "entry_odds", "price", "odds", "decimal_odds")
QUALITY_COLUMNS = ("data_quality", "prop_data_quality", "feature_data_quality")
CLV_COLUMNS = ("closing_line_value", "clv")
RESULT_COLUMNS = ("result", "outcome", "win_loss", "graded_result", "status")


@dataclass(frozen=True)
class MarketProfile:
    profile_key: str
    samples: int
    wins: int
    losses: int
    pushes: int
    win_rate: float | None
    roi: float | None
    average_odds: float | None
    average_clv: float | None
    accuracy_score: float
    trust_level: str


@dataclass(frozen=True)
class MarketProfileReport:
    raw_rows: int
    profile_count: int
    enriched_rows: int
    high_trust_rows: int
    medium_trust_rows: int
    low_trust_rows: int
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


def _odds_bucket(price: float | None) -> str:
    if price is None:
        return "odds_unknown"
    if price < 1.43:
        return "odds_below_1_43"
    if price < 1.75:
        return "odds_1_43_to_1_75"
    if price < 2.25:
        return "odds_1_75_to_2_25"
    return "odds_above_2_25"


def _quality_tier(value: float | None) -> str:
    if value is None:
        return "quality_unknown"
    if value >= 80:
        return "quality_high"
    if value >= 60:
        return "quality_medium"
    return "quality_low"


def _favorite_tier(price: float | None) -> str:
    if price is None:
        return "side_unknown"
    if price < 1.75:
        return "favorite"
    if price <= 2.25:
        return "near_even"
    return "underdog"


def _clv(row: Mapping[str, Any]) -> float | None:
    value = _float(_first(row, CLV_COLUMNS))
    if value is None:
        return None
    return value / 100.0 if abs(value) > 1 else value


def profile_key(row: Mapping[str, Any], *, depth: str = "full") -> str:
    sport = str(_first(row, SPORT_COLUMNS)).strip().lower() or "sport_unknown"
    market = str(_first(row, MARKET_COLUMNS)).strip().lower() or "market_unknown"
    price = parse_price(_first(row, PRICE_COLUMNS))
    quality = _float(_first(row, QUALITY_COLUMNS))
    if depth == "sport_market":
        return f"{sport}|{market}"
    if depth == "sport_market_odds":
        return f"{sport}|{market}|{_odds_bucket(price)}"
    return f"{sport}|{market}|{_odds_bucket(price)}|{_favorite_tier(price)}|{_quality_tier(quality)}"


def _score_profile(win_rate: float | None, roi: float | None, avg_clv: float | None, samples: int) -> float:
    score = 50.0
    if win_rate is not None:
        score += (win_rate - 0.50) * 70.0
    if roi is not None:
        score += roi * 35.0
    if avg_clv is not None:
        score += avg_clv * 200.0
    score += min(10.0, samples / 20.0)
    return round(max(0.0, min(100.0, score)), 2)


def _trust(score: float, samples: int) -> str:
    if samples >= 100 and score >= 70:
        return "HIGH"
    if samples >= 30 and score >= 55:
        return "MEDIUM"
    return "LOW"


def _build_profile(key: str, rows: list[Mapping[str, Any]]) -> MarketProfile:
    wins = losses = pushes = 0
    prices: list[float] = []
    clvs: list[float] = []
    profit = 0.0
    for row in rows:
        result = parse_result(_first(row, RESULT_COLUMNS))
        price = parse_price(_first(row, PRICE_COLUMNS))
        if price is not None:
            prices.append(price)
        clv = _clv(row)
        if clv is not None:
            clvs.append(clv)
        if result == "win":
            wins += 1
        elif result == "loss":
            losses += 1
        elif result == "push":
            pushes += 1
        if result in {"win", "loss", "push"}:
            profit += unit_profit_loss(result, price)
    decisions = wins + losses
    win_rate = wins / decisions if decisions else None
    roi = profit / decisions if decisions else None
    avg_odds = sum(prices) / len(prices) if prices else None
    avg_clv = sum(clvs) / len(clvs) if clvs else None
    score = _score_profile(win_rate, roi, avg_clv, decisions)
    return MarketProfile(
        profile_key=key,
        samples=decisions,
        wins=wins,
        losses=losses,
        pushes=pushes,
        win_rate=None if win_rate is None else round(win_rate, 6),
        roi=None if roi is None else round(roi, 6),
        average_odds=None if avg_odds is None else round(avg_odds, 6),
        average_clv=None if avg_clv is None else round(avg_clv, 6),
        accuracy_score=score,
        trust_level=_trust(score, decisions),
    )


def build_market_profiles(rows: list[Mapping[str, Any]], *, min_samples: int = 10) -> dict[str, MarketProfile]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        if parse_result(_first(row, RESULT_COLUMNS)) not in {"win", "loss", "push"}:
            continue
        for depth in ("full", "sport_market_odds", "sport_market"):
            grouped.setdefault(profile_key(row, depth=depth), []).append(row)
    profiles: dict[str, MarketProfile] = {}
    for key, group in grouped.items():
        profile = _build_profile(key, group)
        if profile.samples >= min_samples:
            profiles[key] = profile
    return profiles


def _best_profile_for_row(row: Mapping[str, Any], profiles: Mapping[str, MarketProfile]) -> MarketProfile | None:
    for depth in ("full", "sport_market_odds", "sport_market"):
        candidate = profiles.get(profile_key(row, depth=depth))
        if candidate is not None:
            return candidate
    return None


def enrich_with_market_profiles(rows: list[Mapping[str, Any]], history_rows: list[Mapping[str, Any]], *, min_samples: int = 10) -> list[dict[str, Any]]:
    profiles = build_market_profiles(history_rows, min_samples=min_samples)
    enriched: list[dict[str, Any]] = []
    for row in rows:
        out = dict(row)
        profile = _best_profile_for_row(row, profiles)
        out["profile_key"] = "" if profile is None else profile.profile_key
        out["profile_sample_size"] = "" if profile is None else str(profile.samples)
        out["profile_win_rate"] = "" if profile is None or profile.win_rate is None else str(profile.win_rate)
        out["profile_roi"] = "" if profile is None or profile.roi is None else str(profile.roi)
        out["profile_clv"] = "" if profile is None or profile.average_clv is None else str(profile.average_clv)
        out["profile_accuracy_score"] = "" if profile is None else str(profile.accuracy_score)
        out["profile_trust_level"] = "LOW" if profile is None else profile.trust_level
        enriched.append(out)
    return enriched


def summarize_profiles(rows: list[Mapping[str, Any]], history_rows: list[Mapping[str, Any]], *, output_csv: str | None = None) -> MarketProfileReport:
    profiles = build_market_profiles(history_rows)
    return MarketProfileReport(
        raw_rows=len(history_rows),
        profile_count=len(profiles),
        enriched_rows=len(rows),
        high_trust_rows=sum(1 for row in rows if row.get("profile_trust_level") == "HIGH"),
        medium_trust_rows=sum(1 for row in rows if row.get("profile_trust_level") == "MEDIUM"),
        low_trust_rows=sum(1 for row in rows if row.get("profile_trust_level") == "LOW"),
        output_csv=output_csv,
        notes=[
            "Market profiles learn reliability by sport, market, odds range, favorite/underdog status and data-quality tier.",
            "Rows fall back from specific profiles to broader sport/market profiles when sample size is limited.",
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


def write_report(report: MarketProfileReport, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
