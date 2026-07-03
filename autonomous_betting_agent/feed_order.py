from __future__ import annotations

from typing import Any

ORDER = {
    "baseball_mlb": 0,
    "basketball_wnba": 1,
    "basketball_nba": 2,
    "americanfootball_nfl": 3,
    "icehockey_nhl": 4,
    "soccer_epl": 5,
}


def sort_feeds(items: list[Any]) -> list[Any]:
    return sorted(items, key=lambda item: (ORDER.get(str(getattr(item, "key", "") or ""), 999), str(getattr(item, "key", "") or "")))
