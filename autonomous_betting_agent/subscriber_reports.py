"""Subscriber personalization helpers for ABA Signal Pro reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .bet_catalog import build_catalog_pick, render_betting_magazine
from .chain_bets import build_small_chain_candidates


@dataclass(frozen=True)
class SubscriberProfile:
    subscriber_id: str
    name: str = ""
    bankroll: float = 0.0
    risk_profile: str = "balanced"
    preferred_sports: tuple[str, ...] = field(default_factory=tuple)
    preferred_sportsbooks: tuple[str, ...] = field(default_factory=tuple)
    preferred_bet_types: tuple[str, ...] = field(default_factory=tuple)
    unit_size: float = 1.0
    daily_risk_limit: float = 0.0
    maximum_exposure: float = 0.0
    single_bet_preference: bool = True
    chain_bet_preference: bool = False
    aggressive_mode: bool = False
    conservative_mode: bool = False
    avoid_list: tuple[str, ...] = field(default_factory=tuple)
    profit_goals: str = ""

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "SubscriberProfile":
        return cls(
            subscriber_id=str(data.get("subscriber_id") or data.get("id") or data.get("name") or "subscriber"),
            name=str(data.get("name") or ""),
            bankroll=float(data.get("bankroll") or 0.0),
            risk_profile=str(data.get("risk_profile") or data.get("risk") or "balanced").lower(),
            preferred_sports=tuple(str(v).lower() for v in _seq(data.get("preferred_sports"))),
            preferred_sportsbooks=tuple(str(v).lower() for v in _seq(data.get("preferred_sportsbooks") or data.get("sportsbooks"))),
            preferred_bet_types=tuple(str(v).lower() for v in _seq(data.get("preferred_bet_types") or data.get("bet_types"))),
            unit_size=float(data.get("unit_size") or data.get("unit") or 1.0),
            daily_risk_limit=float(data.get("daily_risk_limit") or 0.0),
            maximum_exposure=float(data.get("maximum_exposure") or data.get("max_exposure") or 0.0),
            single_bet_preference=bool(data.get("single_bet_preference", True)),
            chain_bet_preference=bool(data.get("chain_bet_preference", False)),
            aggressive_mode=bool(data.get("aggressive_mode", False)),
            conservative_mode=bool(data.get("conservative_mode", False)),
            avoid_list=tuple(str(v).lower() for v in _seq(data.get("avoid_list"))),
            profit_goals=str(data.get("profit_goals") or data.get("profit_goal") or ""),
        )


def _seq(value: Any) -> Sequence[Any]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(v.strip() for v in value.split(",") if v.strip())
    if isinstance(value, Sequence):
        return value
    return (value,)


def _text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip().lower()
    return ""


def _contains_avoided(row: Mapping[str, Any], subscriber: SubscriberProfile) -> bool:
    haystack = " ".join(
        _text(row, key) for key in ("game", "event", "event_name", "matchup", "exact_bet", "pick", "selection", "bet_type", "market")
    )
    return any(term and term in haystack for term in subscriber.avoid_list)


def subscriber_allows_pick(row: Mapping[str, Any], subscriber: SubscriberProfile) -> bool:
    if _contains_avoided(row, subscriber):
        return False
    sport = _text(row, "sport", "league", "sport_league")
    if subscriber.preferred_sports and sport and not any(pref in sport for pref in subscriber.preferred_sports):
        return False
    sportsbook = _text(row, "sportsbook", "sportsbook_casino", "bookmaker", "best_bookmaker")
    if subscriber.preferred_sportsbooks and sportsbook and not any(pref in sportsbook for pref in subscriber.preferred_sportsbooks):
        return False
    bet_type = _text(row, "bet_type", "market", "market_type")
    if subscriber.preferred_bet_types and bet_type and not any(pref in bet_type for pref in subscriber.preferred_bet_types):
        return False
    pick = build_catalog_pick(row)
    if subscriber.conservative_mode or subscriber.risk_profile == "conservative":
        if pick.risk_score is not None and pick.risk_score > 6:
            return False
        if pick.final_decision in {"AGGRESSIVE ONLY", "WATCH ONLY", "NO BET", "BAD VALUE"}:
            return False
    if not subscriber.aggressive_mode and subscriber.risk_profile != "aggressive":
        if pick.risk_score is not None and pick.risk_score > 8:
            return False
        if pick.final_decision == "AGGRESSIVE ONLY":
            return False
    return True


def personalize_rows(rows: Iterable[Mapping[str, Any]], subscriber: SubscriberProfile | Mapping[str, Any]) -> list[dict[str, Any]]:
    profile = subscriber if isinstance(subscriber, SubscriberProfile) else SubscriberProfile.from_mapping(subscriber)
    allowed = [dict(row) for row in rows if subscriber_allows_pick(row, profile)]
    if profile.chain_bet_preference:
        max_legs = 2 if profile.conservative_mode or profile.risk_profile == "conservative" else 3 if profile.risk_profile == "balanced" else 4
        chains = build_small_chain_candidates(allowed, max_legs=max_legs, limit=8)
        allowed.extend(chains)
    return allowed


def render_subscriber_betting_magazine(
    rows: Iterable[Mapping[str, Any]],
    subscriber: SubscriberProfile | Mapping[str, Any],
    *,
    title: str = "ABA Signal Pro Betting Magazine",
) -> str:
    profile = subscriber if isinstance(subscriber, SubscriberProfile) else SubscriberProfile.from_mapping(subscriber)
    personalized = personalize_rows(rows, profile)
    name = profile.name or profile.subscriber_id
    header = (
        f"Subscriber Risk Profile: {profile.risk_profile}\n"
        f"Subscriber Bankroll: {profile.bankroll:.2f}\n"
        f"Unit Size: {profile.unit_size:.2f}\n"
        f"Chain Preference: {'enabled' if profile.chain_bet_preference else 'disabled'}\n"
    )
    magazine = render_betting_magazine(personalized, title=title, subscriber_name=name)
    return magazine.replace("\n\n**Analytics notice:**", f"\n\n{header}\n**Analytics notice:**", 1)
