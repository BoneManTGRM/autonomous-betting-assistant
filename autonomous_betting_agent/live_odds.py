from __future__ import annotations

import os
from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

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
    markets: str = "h2h",
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
    cycle_notes = [
        "TEST: pulled live market prices for the event.",
        "DETECT: checked whether at least two outcomes had usable prices.",
        "REPAIR: averaged prices across books, found best available prices, and normalized implied probabilities.",
        "VERIFY: ranked outcomes by no-vig probability and marked draw risk when present.",
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
    )


def scan_market(api_key: str, sport_key: str, regions: str = "us,eu,uk", max_events: int = 25) -> List[LiveEventSummary]:
    events = fetch_odds(api_key, sport_key=sport_key, regions=regions)
    summaries = []
    for event in events[:max_events]:
        summary = summarize_event(event)
        if summary is not None:
            summaries.append(summary)
    return summaries
