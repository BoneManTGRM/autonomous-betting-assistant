"""Near double-money finder for ABA Signal Pro.

Finds +100 / 2.00 decimal proximity without forcing bad-value plays.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .client_profiles import client_allows_pick
from .odds_value import near_double_money_score, normalize_decimal_odds, row_edge, row_ev, row_model_probability

BAD_DOUBLE_MONEY_WARNING = "BAD VALUE — DO NOT FORCE DOUBLE-MONEY BET"


def double_money_distance(decimal_odds: float | int | str | None) -> float | None:
    return near_double_money_score(decimal_odds)


def is_near_double_but_bad_value(row: Mapping[str, Any]) -> bool:
    decimal = normalize_decimal_odds(row)
    distance = double_money_distance(decimal)
    ev = row_ev(row)
    probability = row_model_probability(row)
    edge = row_edge(row)
    return bool(distance is not None and distance <= 0.25 and (probability is None or ev is None or ev <= 0 or edge is None or edge <= 0))


def _chain_as_row(option: Any) -> Mapping[str, Any]:
    if hasattr(option, "as_row"):
        return option.as_row()
    if isinstance(option, Mapping):
        return option
    return {}


def _rank_key(option: Any, subscriber: Mapping[str, Any] | None = None) -> tuple[int, float, float, float, int, float]:
    row = _chain_as_row(option)
    decimal = normalize_decimal_odds(row)
    distance = double_money_distance(decimal)
    ev = row_ev(row)
    probability = row_model_probability(row)
    edge = row_edge(row)
    fit = client_allows_pick(row, subscriber)
    return (
        0 if ev is not None and ev > 0 else 1,
        -(ev if ev is not None else -99),
        -(probability if probability is not None else 0),
        -(edge if edge is not None else -99),
        0 if fit else 1,
        distance if distance is not None else 99,
    )


def rank_near_double_options(options: Iterable[Any], subscriber: Mapping[str, Any] | None = None) -> list[Any]:
    return sorted(options, key=lambda option: _rank_key(option, subscriber))


def find_best_near_double_single(picks: Iterable[Mapping[str, Any]], subscriber: Mapping[str, Any] | None = None) -> Mapping[str, Any] | None:
    qualified: list[Mapping[str, Any]] = []
    for pick in picks:
        decimal = normalize_decimal_odds(pick)
        distance = double_money_distance(decimal)
        ev = row_ev(pick)
        edge = row_edge(pick)
        if distance is None or distance > 0.35:
            continue
        if ev is not None and ev > 0 and edge is not None and edge > 0 and client_allows_pick(pick, subscriber):
            qualified.append(pick)
    ranked = rank_near_double_options(qualified, subscriber)
    return ranked[0] if ranked else None


def find_best_near_double_chain(chains: Iterable[Any], subscriber: Mapping[str, Any] | None = None) -> Any | None:
    qualified = []
    for chain in chains:
        row = _chain_as_row(chain)
        decimal = normalize_decimal_odds(row)
        distance = double_money_distance(decimal)
        ev = row_ev(row)
        if distance is None or distance > 0.75:
            continue
        if ev is not None and ev > 0:
            qualified.append(chain)
    ranked = rank_near_double_options(qualified, subscriber)
    return ranked[0] if ranked else None


def near_double_report(picks: Iterable[Mapping[str, Any]], chains: Sequence[Any] | None = None, subscriber: Mapping[str, Any] | None = None) -> dict[str, Any]:
    pick_list = list(picks)
    chain_list = list(chains or [])
    best_single = find_best_near_double_single(pick_list, subscriber)
    best_chain = find_best_near_double_chain(chain_list, subscriber)
    ranked = rank_near_double_options([item for item in [best_single, best_chain] if item], subscriber)
    return {
        "best_near_double_single": best_single,
        "best_near_double_chain": best_chain,
        "safest_near_double_option": ranked[0] if ranked else None,
        "highest_upside_near_double_option": ranked[0] if ranked else None,
        "warning": "" if ranked else BAD_DOUBLE_MONEY_WARNING,
    }
