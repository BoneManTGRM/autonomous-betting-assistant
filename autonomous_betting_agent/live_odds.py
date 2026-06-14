from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from .learning import ProbabilityCalibrator

API_HOST = "https://api.the-odds-api.com"


@dataclass(frozen=True)
class SportInfo:
    key: str
    group: str
    title: str
    description: str
    active: bool
    has_outrights: bool


@dataclass(frozen=True)
class OutcomePrice:
    name: str
    average_price: float
    raw_probability: float
    normalized_probability: float
    source_count: int
    best_price: Optional[float] = None
    worst_price: Optional[float] = None
    price_range: Optional[float] = None
    best_bookmaker: Optional[str] = None


@dataclass(frozen=True)
class MarketLine:
    market: str
    name: str
    point: Optional[float]
    average_price: float
    source_count: int
    best_price: Optional[float] = None
    worst_price: Optional[float] = None
    price_range: Optional[float] = None
    best_bookmaker: Optional[str] = None


@dataclass(frozen=True)
class LiveEventSummary:
    event_id: str
    sport_key: str
    sport_title: str
    commence_time: str
    home_team: str
    away_team: str
    favorite: str
    favorite_probability: float
    outcomes: List[OutcomePrice]
    bookmaker_count: int
    cycle_notes: List[str]
    market_overround: float = 0.0
    spreads: List[MarketLine] = None
    totals: List[MarketLine] = None


MARKET_LABELS = {
    "spreads": "Point spread",
    "totals": "Game total",
}


def get_api_key(explicit_key: Optional[str] = None) -> str:
    key = explicit_key or os.getenv("THE_ODDS_API_KEY") or ""
    if not key:
        raise RuntimeError("Missing THE_ODDS_API_KEY. Add it to Streamlit secrets or environment variables.")
    return key


def _get_json(path: str, params: Dict[str, Any]) -> Any:
    response = requests.get(f"{API_HOST}{path}", params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def list_sports(api_key: str, include_all: bool = False) -> List[SportInfo]:
    payload = _get_json("/v4/sports/", {"apiKey": api_key, "all": str(include_all).lower()})
    sports = []
    for item in payload:
        sports.append(
            SportInfo(
                key=str(item.get("key", "")),
                group=str(item.get("group", "")),
                title=str(item.get("title", "")),
                description=str(item.get("description", "")),
                active=bool(item.get("active", False)),
                has_outrights=bool(item.get("has_outrights", False)),
            )
        )
    return sports


def fetch_odds(
    api_key: str,
    sport_key: str,
    regions: str = "us,eu,uk",
    markets: str = "h2h,spreads,totals",
    odds_format: str = "decimal",
) -> List[Dict[str, Any]]:
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": odds_format,
        "dateFormat": "iso",
    }
    return list(_get_json(f"/v4/sports/{sport_key}/odds/", params))


def _prices_by_outcome(bookmakers: Iterable[Dict[str, Any]]) -> Dict[str, List[Tuple[float, str]]]:
    prices: Dict[str, List[Tuple[float, str]]] = {}
    for bookmaker in bookmakers:
        book_name = str(bookmaker.get("title") or bookmaker.get("key") or "Unknown")
        for market in bookmaker.get("markets", []):
            if market.get("key") != "h2h":
                continue
            for outcome in market.get("outcomes", []):
                name = str(outcome.get("name", "")).strip()
                price = outcome.get("price")
                if not name or price is None:
                    continue
                try:
                    price_float = float(price)
                except (TypeError, ValueError):
                    continue
                if price_float <= 1.0:
                    continue
                prices.setdefault(name, []).append((price_float, book_name))
    return prices


def _market_lines(bookmakers: Iterable[Dict[str, Any]], market_key: str) -> List[MarketLine]:
    line_map: Dict[Tuple[str, Optional[float]], List[Tuple[float, str]]] = {}
    for bookmaker in bookmakers:
        book_name = str(bookmaker.get("title") or bookmaker.get("key") or "Unknown")
        for market in bookmaker.get("markets", []):
            if market.get("key") != market_key:
                continue
            for outcome in market.get("outcomes", []):
                name = str(outcome.get("name", "")).strip()
                price = outcome.get("price")
                raw_point = outcome.get("point")
                if not name or price is None:
                    continue
                try:
                    price_float = float(price)
                except (TypeError, ValueError):
                    continue
                if price_float <= 1.0:
                    continue
                try:
                    point = None if raw_point is None else float(raw_point)
                except (TypeError, ValueError):
                    point = None
                line_map.setdefault((name, point), []).append((price_float, book_name))

    rows: List[MarketLine] = []
    for (name, point), entries in line_map.items():
        avg_price = mean([price for price, _ in entries])
        best_price, best_bookmaker = max(entries, key=lambda pair: pair[0])
        worst_price = min(price for price, _ in entries)
        rows.append(
            MarketLine(
                market=market_key,
                name=name,
                point=point,
                average_price=avg_price,
                source_count=len(entries),
                best_price=best_price,
                worst_price=worst_price,
                price_range=best_price - worst_price,
                best_bookmaker=best_bookmaker,
            )
        )
    rows.sort(key=lambda item: (item.market, item.name, item.point if item.point is not None else 0.0))
    return rows


def summarize_event(event: Dict[str, Any]) -> Optional[LiveEventSummary]:
    price_map = _prices_by_outcome(event.get("bookmakers", []))
    if len(price_map) < 2:
        return None

    average_prices = {name: mean([price for price, _ in entries]) for name, entries in price_map.items() if entries}
    raw_probs = {name: 1.0 / avg_price for name, avg_price in average_prices.items() if avg_price > 1.0}
    total = sum(raw_probs.values())
    if total <= 0:
        return None

    outcomes: List[OutcomePrice] = []
    for name in raw_probs:
        entries = price_map[name]
        best_price, best_bookmaker = max(entries, key=lambda pair: pair[0])
        worst_price = min(price for price, _ in entries)
        outcomes.append(
            OutcomePrice(
                name=name,
                average_price=average_prices[name],
                raw_probability=raw_probs[name],
                normalized_probability=raw_probs[name] / total,
                source_count=len(entries),
                best_price=best_price,
                worst_price=worst_price,
                price_range=best_price - worst_price,
                best_bookmaker=best_bookmaker,
            )
        )

    outcomes.sort(key=lambda item: item.normalized_probability, reverse=True)
    favorite = outcomes[0]
    market_overround = total - 1.0
    spreads = _market_lines(event.get("bookmakers", []), "spreads")
    totals = _market_lines(event.get("bookmakers", []), "totals")
    cycle_notes = [
        "TEST: pulled live moneyline, spread, and total market prices for the event when available.",
        "DETECT: checked whether at least two moneyline outcomes had usable prices.",
        "REPAIR: averaged prices across books, found best available prices, and normalized implied probabilities.",
        "VERIFY: ranked outcomes by no-vig probability and attached spreads/totals when providers returned them.",
    ]
    return LiveEventSummary(
        event_id=str(event.get("id", "")),
        sport_key=str(event.get("sport_key", "")),
        sport_title=str(event.get("sport_title", event.get("sport_key", ""))),
        commence_time=str(event.get("commence_time", "")),
        home_team=str(event.get("home_team", "")),
        away_team=str(event.get("away_team", "")),
        favorite=favorite.name,
        favorite_probability=favorite.normalized_probability,
        outcomes=outcomes,
        bookmaker_count=len(event.get("bookmakers", [])),
        cycle_notes=cycle_notes,
        market_overround=market_overround,
        spreads=spreads,
        totals=totals,
    )


def _load_calibrator(path: str | Path | None) -> ProbabilityCalibrator | None:
    if path is None:
        return None
    try:
        candidate = Path(path)
        if not candidate.exists():
            return None
        return ProbabilityCalibrator.load(candidate)
    except (OSError, ValueError, json.JSONDecodeError, TypeError):
        return None


def _apply_calibration(summary: LiveEventSummary, calibrator: ProbabilityCalibrator) -> LiveEventSummary:
    adjusted = [calibrator.apply(outcome.normalized_probability) for outcome in summary.outcomes]
    total = sum(adjusted)
    if total <= 0.0:
        return summary

    calibrated_outcomes: List[OutcomePrice] = []
    for outcome, adjusted_probability in zip(summary.outcomes, adjusted):
        calibrated_outcomes.append(
            OutcomePrice(
                name=outcome.name,
                average_price=outcome.average_price,
                raw_probability=outcome.raw_probability,
                normalized_probability=adjusted_probability / total,
                source_count=outcome.source_count,
                best_price=outcome.best_price,
                worst_price=outcome.worst_price,
                price_range=outcome.price_range,
                best_bookmaker=outcome.best_bookmaker,
            )
        )
    calibrated_outcomes.sort(key=lambda item: item.normalized_probability, reverse=True)
    favorite = calibrated_outcomes[0]
    return LiveEventSummary(
        event_id=summary.event_id,
        sport_key=summary.sport_key,
        sport_title=summary.sport_title,
        commence_time=summary.commence_time,
        home_team=summary.home_team,
        away_team=summary.away_team,
        favorite=favorite.name,
        favorite_probability=favorite.normalized_probability,
        outcomes=calibrated_outcomes,
        bookmaker_count=summary.bookmaker_count,
        cycle_notes=summary.cycle_notes + [f"VERIFY: applied learned probability calibration from {calibrator.events_trained} graded events."],
        market_overround=summary.market_overround,
        spreads=summary.spreads,
        totals=summary.totals,
    )


def scan_market(
    api_key: str,
    sport_key: str,
    regions: str = "us,eu,uk",
    max_events: int = 25,
    markets: str = "h2h,spreads,totals",
    learned_state_path: str | Path | None = "learned_state.json",
) -> List[LiveEventSummary]:
    events = fetch_odds(api_key, sport_key=sport_key, regions=regions, markets=markets)
    calibrator = _load_calibrator(learned_state_path)
    summaries = []
    for event in events[:max_events]:
        summary = summarize_event(event)
        if summary is not None:
            if calibrator is not None and calibrator.events_trained > 0:
                summary = _apply_calibration(summary, calibrator)
            summaries.append(summary)
    return summaries
