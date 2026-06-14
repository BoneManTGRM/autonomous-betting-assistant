from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Mapping


@dataclass(frozen=True)
class SportKeyMatch:
    matched_sport_key: str
    matched_event_id: str
    match_confidence: float
    match_reason: str


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").replace("-", " ").split())


def _ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _score_feed(feed: Mapping[str, Any], query: str, game: str) -> tuple[float, str]:
    key = _norm(feed.get("key") or feed.get("sport_key"))
    title = _norm(feed.get("title") or feed.get("sport_title"))
    group = _norm(feed.get("group") or "")
    haystack = " ".join([key, title, group])
    query_norm = _norm(query)
    game_norm = _norm(game)
    score = max(_ratio(query_norm, key), _ratio(query_norm, title), _ratio(query_norm, group))
    reason = "fuzzy_match"
    if query_norm and query_norm in haystack:
        score = max(score, 0.95)
        reason = "query_contained_in_feed"
    for token in game_norm.split():
        if len(token) >= 4 and token in haystack:
            score = max(score, 0.70)
            reason = "game_token_feed_match"
    if feed.get("active") is False:
        score *= 0.5
        reason += "; inactive_feed_penalty"
    return round(score, 4), reason


def resolve_sport_key(sports: list[Mapping[str, Any]], *, sport_search: str, game: str = "") -> SportKeyMatch:
    best: tuple[float, str, Mapping[str, Any]] | None = None
    for feed in sports:
        score, reason = _score_feed(feed, sport_search, game)
        if best is None or score > best[0]:
            best = (score, reason, feed)
    if best is None:
        return SportKeyMatch("", "", 0.0, "no_sports_supplied")
    feed = best[2]
    return SportKeyMatch(
        matched_sport_key=str(feed.get("key") or feed.get("sport_key") or ""),
        matched_event_id=str(feed.get("id") or feed.get("event_id") or ""),
        match_confidence=best[0],
        match_reason=best[1],
    )


def attach_sport_key_match(row: Mapping[str, Any], sports: list[Mapping[str, Any]]) -> dict[str, Any]:
    match = resolve_sport_key(sports, sport_search=str(row.get("sport_search") or row.get("sport") or ""), game=str(row.get("game") or row.get("event") or ""))
    out = dict(row)
    out["matched_sport_key"] = match.matched_sport_key
    out["matched_event_id"] = match.matched_event_id
    out["match_confidence"] = str(match.match_confidence)
    out["match_reason"] = match.match_reason
    return out
