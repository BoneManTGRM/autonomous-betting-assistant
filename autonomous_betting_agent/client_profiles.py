"""Client profile and personalization helpers for ABA Signal Pro."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

_RISK_MODES = {"conservative", "balanced", "aggressive"}


def _list(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        return tuple(part.strip().lower() for part in value.replace(";", ",").split(",") if part.strip())
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return tuple(str(part).strip().lower() for part in value if str(part).strip())
    return (str(value).strip().lower(),)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool(value: Any, default: bool = False) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "allow", "allowed"}


@dataclass(frozen=True)
class ClientProfile:
    client_id: str = "default"
    name: str = "Default Client"
    bankroll: float = 0.0
    risk_profile: str = "balanced"
    preferred_sports: tuple[str, ...] = field(default_factory=tuple)
    preferred_books: tuple[str, ...] = field(default_factory=tuple)
    preferred_markets: tuple[str, ...] = field(default_factory=tuple)
    unit_size: float = 1.0
    max_daily_exposure: float = 3.0
    max_single_exposure: float = 1.0
    max_chain_legs: int = 2
    allow_chains: bool = True
    allow_player_markets: bool = True
    allow_hr_markets: bool = False
    conservative_mode: bool = False
    aggressive_mode: bool = False
    avoid_list: tuple[str, ...] = field(default_factory=tuple)
    goal: str = ""
    notes: str = ""


def normalize_client_profile(data: Mapping[str, Any] | ClientProfile | None = None) -> ClientProfile:
    if isinstance(data, ClientProfile):
        return data
    row: Mapping[str, Any] = data or {}
    risk = str(row.get("risk_profile") or row.get("risk") or row.get("mode") or "balanced").strip().lower()
    if risk not in _RISK_MODES:
        risk = "balanced"
    max_chain_default = 2 if risk == "conservative" else 3 if risk == "balanced" else 4
    return ClientProfile(
        client_id=str(row.get("client_id") or row.get("subscriber_id") or row.get("id") or "default"),
        name=str(row.get("name") or row.get("client_name") or row.get("subscriber_name") or "Default Client"),
        bankroll=_float(row.get("bankroll"), 0.0),
        risk_profile=risk,
        preferred_sports=_list(row.get("preferred_sports") or row.get("sports")),
        preferred_books=_list(row.get("preferred_books") or row.get("preferred_sportsbooks") or row.get("sportsbooks")),
        preferred_markets=_list(row.get("preferred_markets") or row.get("preferred_bet_types") or row.get("bet_types")),
        unit_size=max(0.0, _float(row.get("unit_size"), 1.0)),
        max_daily_exposure=max(0.0, _float(row.get("max_daily_exposure") or row.get("max_daily_risk"), 3.0)),
        max_single_exposure=max(0.0, _float(row.get("max_single_exposure") or row.get("max_single_bet_stake"), 1.0)),
        max_chain_legs=int(_float(row.get("max_chain_legs"), max_chain_default)),
        allow_chains=_bool(row.get("allow_chains") if "allow_chains" in row else row.get("allow_chain_bets"), default=True),
        allow_player_markets=_bool(row.get("allow_player_markets") if "allow_player_markets" in row else row.get("allow_player_props"), default=(risk != "conservative")),
        allow_hr_markets=_bool(row.get("allow_hr_markets") if "allow_hr_markets" in row else row.get("allow_home_run_props"), default=(risk == "aggressive")),
        conservative_mode=_bool(row.get("conservative_mode"), default=(risk == "conservative")),
        aggressive_mode=_bool(row.get("aggressive_mode"), default=(risk == "aggressive")),
        avoid_list=_list(row.get("avoid_list") or row.get("avoid")),
        goal=str(row.get("goal") or row.get("profit_goal") or ""),
        notes=str(row.get("notes") or ""),
    )


def _row_text(row: Mapping[str, Any], *keys: str) -> str:
    return " ".join(str(row.get(key, "")).strip().lower() for key in keys if row.get(key) not in (None, ""))


def _contains_any(text: str, values: tuple[str, ...]) -> bool:
    return any(value in text for value in values)


def client_allows_pick(row: Mapping[str, Any], profile_data: Mapping[str, Any] | ClientProfile | None = None) -> bool:
    profile = normalize_client_profile(profile_data)
    haystack = _row_text(row, "game", "event", "event_name", "matchup", "bet_type", "market", "exact_bet", "pick", "selection", "sportsbook", "bookmaker", "sport", "league")
    if profile.avoid_list and _contains_any(haystack, profile.avoid_list):
        return False
    sport = _row_text(row, "sport", "league", "sport_league")
    if profile.preferred_sports and not _contains_any(sport, profile.preferred_sports):
        return False
    book = _row_text(row, "sportsbook_casino", "sportsbook", "bookmaker", "best_bookmaker")
    if profile.preferred_books and book and not _contains_any(book, profile.preferred_books):
        return False
    market = _row_text(row, "bet_type", "market", "market_type", "exact_bet", "pick", "selection")
    if profile.preferred_markets and not _contains_any(market, profile.preferred_markets):
        return False
    is_chain = bool(row.get("legs")) or any(word in market for word in ("chain", "parlay", "sgp"))
    is_hr = any(word in market for word in ("home run", "homer", " hr"))
    is_player = is_hr or any(word in market for word in ("player", "prop", "hits", "total bases", "rbi", "strikeouts", "outs"))
    if is_chain and not profile.allow_chains:
        return False
    if is_player and not profile.allow_player_markets:
        return False
    if is_hr and not profile.allow_hr_markets:
        return False
    legs = row.get("legs")
    if isinstance(legs, Sequence) and not isinstance(legs, (str, bytes)) and len(legs) > profile.max_chain_legs:
        return False
    return True


def client_risk_limit(profile_data: Mapping[str, Any] | ClientProfile | None = None) -> float:
    profile = normalize_client_profile(profile_data)
    if profile.risk_profile == "conservative":
        return 5.0
    if profile.risk_profile == "aggressive":
        return 8.5
    return 7.0


def recommended_exposure(row: Mapping[str, Any], profile_data: Mapping[str, Any] | ClientProfile | None = None, risk_score: float | None = None) -> float:
    profile = normalize_client_profile(profile_data)
    unit = profile.unit_size or 1.0
    cap = profile.max_single_exposure or unit
    if risk_score is None:
        risk_score = _float(row.get("risk_score") or row.get("blended_risk_score"), 6.0)
    if risk_score <= 3:
        amount = unit
    elif risk_score <= 6:
        amount = unit * 0.5
    elif risk_score <= 8:
        amount = unit * 0.25
    else:
        amount = 0.0 if profile.risk_profile != "aggressive" else unit * 0.1
    return round(min(amount, cap), 4)
