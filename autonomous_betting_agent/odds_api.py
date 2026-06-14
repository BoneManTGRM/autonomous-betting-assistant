from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping


def odds_api_payload_to_rows(payload: Any, *, source: str = "odds_api") -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for event in payload:
        if not isinstance(event, Mapping):
            continue
        event_id = str(event.get("id") or event.get("game_id") or "")
        sport_key = str(event.get("sport_key") or "")
        sport_title = str(event.get("sport_title") or "")
        home_team = str(event.get("home_team") or "")
        away_team = str(event.get("away_team") or "")
        start_time = str(event.get("commence_time") or event.get("start_time") or "")
        event_name = f"{away_team} at {home_team}".strip() if home_team or away_team else event_id
        for book in event.get("bookmakers") or []:
            if not isinstance(book, Mapping):
                continue
            book_key = str(book.get("key") or book.get("title") or "")
            book_title = str(book.get("title") or book_key)
            book_time = str(book.get("last_update") or "")
            for market in book.get("markets") or []:
                if not isinstance(market, Mapping):
                    continue
                market_key = str(market.get("key") or "")
                market_time = str(market.get("last_update") or book_time)
                for outcome in market.get("outcomes") or []:
                    if not isinstance(outcome, Mapping):
                        continue
                    selection = str(outcome.get("name") or "")
                    rows.append({
                        "source": source,
                        "game_id": event_id,
                        "event_id": event_id,
                        "event": event_name,
                        "home_team": home_team,
                        "away_team": away_team,
                        "start_time": start_time,
                        "sport": sport_key or sport_title,
                        "league": sport_title or sport_key,
                        "market": market_key,
                        "market_key": market_key,
                        "selection": selection,
                        "outcome": selection,
                        "price": outcome.get("price", ""),
                        "point": outcome.get("point", ""),
                        "bookmaker": book_key,
                        "sportsbook": book_title,
                        "timestamp": market_time,
                        "last_update": market_time,
                        "is_closing": "false",
                    })
    return rows


def write_json_payload(payload: Any, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_odds_rows(rows: list[Mapping[str, Any]], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else ["empty"]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
