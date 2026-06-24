"""Conservative bankroll and exposure helpers.

This is risk-management support only. It does not provide financial advice and
never guarantees a betting outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class StakeSuggestion:
    stake: float
    reason: str
    blocked: bool = False


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def conservative_kelly_fraction(probability: float, decimal_price: float, fraction: float = 0.25) -> float:
    if probability <= 0 or decimal_price <= 1:
        return 0.0
    b = decimal_price - 1.0
    edge_fraction = ((b * probability) - (1.0 - probability)) / b
    return max(0.0, edge_fraction * fraction)


def suggest_stake(
    row: Mapping[str, Any],
    bankroll: float,
    mode: str = "flat",
    flat_units: float = 1.0,
    max_daily_exposure_pct: float = 0.05,
    max_sport_exposure_pct: float | None = None,
    max_event_exposure_pct: float = 0.02,
    current_daily_exposure: float = 0.0,
    current_sport_exposure: float = 0.0,
    current_event_exposure: float = 0.0,
) -> StakeSuggestion:
    probability = _float(row.get("learned_model_probability") or row.get("model_probability") or row.get("probability"))
    decimal_price = _float(row.get("decimal_price") or row.get("odds_at_pick"))
    audit_status = str(row.get("odds_audit_status") or row.get("audit_status") or "").lower()

    if bankroll <= 0:
        return StakeSuggestion(0.0, "No stake suggested because bankroll is not positive.", True)
    if audit_status in {"fail", "failed", "quarantine", "review", "blocked"}:
        return StakeSuggestion(0.0, "No stake suggested because the odds audit requires review.", True)
    if probability is None or decimal_price is None:
        return StakeSuggestion(0.0, "No stake suggested because probability or proof-safe price is missing.", True)
    if probability <= 0 or probability >= 1 or decimal_price <= 1:
        return StakeSuggestion(0.0, "No stake suggested because probability or odds are outside a usable range.", True)

    daily_cap = bankroll * max_daily_exposure_pct
    sport_cap = bankroll * (max_sport_exposure_pct if max_sport_exposure_pct is not None else max_daily_exposure_pct)
    event_cap = bankroll * max_event_exposure_pct
    remaining_daily = max(0.0, daily_cap - current_daily_exposure)
    remaining_sport = max(0.0, sport_cap - current_sport_exposure)
    remaining_event = max(0.0, event_cap - current_event_exposure)
    exposure_cap = min(remaining_daily, remaining_sport, remaining_event)
    if exposure_cap <= 0:
        return StakeSuggestion(0.0, "No stake suggested because exposure caps are already reached.", True)

    if mode.lower() in {"kelly", "conservative_kelly"}:
        stake = bankroll * conservative_kelly_fraction(probability, decimal_price, fraction=0.25)
        reason = "Conservative Kelly fraction capped by daily, sport, and event exposure limits."
    else:
        stake = flat_units
        reason = "Flat stake capped by daily, sport, and event exposure limits."
    stake = max(0.0, min(stake, exposure_cap))
    if stake <= 0:
        return StakeSuggestion(0.0, "No stake suggested after conservative exposure limits.", True)
    return StakeSuggestion(round(stake, 4), reason + " Analytics/risk-management only; no guaranteed outcome.")
