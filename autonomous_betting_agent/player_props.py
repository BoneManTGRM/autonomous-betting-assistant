from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import math

import pandas as pd

from .ara_filters import parse_float, parse_percent

PLAYER_PROP_OUTPUT_COLUMNS = [
    "prop_player_name",
    "prop_type_normalized",
    "prop_market_probability",
    "prop_no_vig_probability",
    "prop_model_probability",
    "prop_blended_probability",
    "prop_implied_edge",
    "prop_fair_decimal_price",
    "prop_status",
    "prop_stake_units",
    "prop_reasons",
    "prop_required_data",
]

PROP_ALIASES = {
    "td": "touchdown",
    "touchdown": "touchdown",
    "anytime touchdown": "touchdown",
    "anytime_td": "touchdown",
    "home run": "home_run",
    "hr": "home_run",
    "homerun": "home_run",
    "goal": "goal",
    "anytime goal": "goal",
    "shot on goal": "shot_on_goal",
    "sog": "shot_on_goal",
    "assist": "assist",
    "hit": "hit",
    "strikeout": "strikeout",
    "k": "strikeout",
    "reception": "reception",
    "rush yard": "rush_yards",
    "rush yards": "rush_yards",
    "receiving yard": "receiving_yards",
    "receiving yards": "receiving_yards",
    "passing yard": "passing_yards",
    "passing yards": "passing_yards",
}


@dataclass(frozen=True)
class PlayerPropPolicy:
    min_books: int = 4
    min_data_quality: float = 75.0
    min_model_edge: float = 0.03
    normal_model_edge: float = 0.05
    strong_model_edge: float = 0.08
    max_blend_market_weight: float = 0.65
    min_blend_market_weight: float = 0.35
    max_stake_units: float = 0.50


def _field(row: Mapping[str, Any], names: tuple[str, ...]) -> Any:
    lookup = {str(key).strip().lower().replace(" ", "_").replace("-", "_"): value for key, value in row.items()}
    for name in names:
        key = name.lower().replace(" ", "_").replace("-", "_")
        if key in lookup:
            value = lookup[key]
            try:
                if pd.isna(value):
                    return None
            except (TypeError, ValueError):
                pass
            return value
    return None


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalize_prop_type(value: Any) -> str:
    text = _text(value).lower().replace("-", "_").replace(" ", "_")
    compact = text.replace("_", " ")
    return PROP_ALIASES.get(text, PROP_ALIASES.get(compact, text or "unknown"))


def decimal_implied_probability(price: Any) -> float | None:
    price_float = parse_float(price)
    if price_float is None or price_float <= 1.0:
        return None
    return 1.0 / price_float


def no_vig_binary_probability(over_price: Any, under_price: Any) -> float | None:
    over_imp = decimal_implied_probability(over_price)
    under_imp = decimal_implied_probability(under_price)
    if over_imp is None or under_imp is None:
        return None
    total = over_imp + under_imp
    if total <= 0:
        return None
    return over_imp / total


def _player_name(row: Mapping[str, Any]) -> str:
    return _text(_field(row, ("player", "player_name", "athlete", "name")))


def _market_probability(row: Mapping[str, Any]) -> float | None:
    direct = parse_percent(_field(row, ("market_probability", "prop_market_probability", "book_probability", "implied_probability")))
    if direct is not None:
        return direct
    no_vig = no_vig_binary_probability(_field(row, ("over_price", "yes_price", "best_yes_price")), _field(row, ("under_price", "no_price", "best_no_price")))
    if no_vig is not None:
        return no_vig
    return decimal_implied_probability(_field(row, ("best_price", "price", "decimal_odds", "odds")))


def _model_probability(row: Mapping[str, Any]) -> tuple[float | None, list[str]]:
    reasons: list[str] = []
    direct = parse_percent(_field(row, ("model_probability", "prop_model_probability", "player_model_probability", "ara_model_probability")))
    if direct is not None:
        return direct, ["direct_model_probability"]

    rates = []
    for column, label in (
        ("recent_rate", "recent_rate"),
        ("season_rate", "season_rate"),
        ("player_season_rate", "player_season_rate"),
        ("opponent_allowed_rate", "opponent_allowed_rate"),
        ("usage_rate", "usage_rate"),
    ):
        value = parse_percent(_field(row, (column,)))
        if value is not None:
            rates.append(value)
            reasons.append(label)
    if not rates:
        return None, []

    recency = parse_percent(_field(row, ("recent_rate",)))
    season = parse_percent(_field(row, ("season_rate", "player_season_rate")))
    opponent = parse_percent(_field(row, ("opponent_allowed_rate",)))
    usage = parse_percent(_field(row, ("usage_rate",)))
    weighted = 0.0
    weight = 0.0
    for value, item_weight in ((recency, 0.35), (season, 0.30), (opponent, 0.20), (usage, 0.15)):
        if value is not None:
            weighted += value * item_weight
            weight += item_weight
    if weight > 0:
        return max(0.01, min(0.99, weighted / weight)), reasons
    return max(0.01, min(0.99, sum(rates) / len(rates))), reasons


def _data_quality(row: Mapping[str, Any]) -> float | None:
    value = parse_float(_field(row, ("data_quality", "prop_data_quality", "quality")))
    if value is None:
        return None
    return value * 100.0 if value <= 1.0 else value


def _books(row: Mapping[str, Any]) -> int | None:
    value = parse_float(_field(row, ("books", "book_count", "bookmaker_count", "prop_books")))
    return None if value is None else int(round(value))


def _market_weight(row: Mapping[str, Any], policy: PlayerPropPolicy) -> float:
    books = _books(row) or 0
    quality = _data_quality(row) or 0.0
    if books >= 8 and quality >= 85:
        return policy.max_blend_market_weight
    if books >= policy.min_books and quality >= policy.min_data_quality:
        return 0.50
    return policy.min_blend_market_weight


def _fair_price(probability: float | None) -> float | None:
    if probability is None or probability <= 0:
        return None
    return round(1.0 / probability, 4)


def _grade_status(edge: float | None, required: list[str], hard_reasons: list[str], policy: PlayerPropPolicy) -> tuple[str, float]:
    if hard_reasons:
        return "REJECT", 0.0
    if required:
        return "TRACK_ONLY_NEEDS_PLAYER_MODEL_DATA", 0.0
    if edge is None or edge < policy.min_model_edge:
        return "WATCH", 0.0
    if edge >= policy.strong_model_edge:
        return "QUALIFIED_STRONG", min(policy.max_stake_units, 0.50)
    if edge >= policy.normal_model_edge:
        return "QUALIFIED", min(policy.max_stake_units, 0.35)
    return "QUALIFIED_SMALL", min(policy.max_stake_units, 0.20)


def score_player_prop(row: Mapping[str, Any], policy: PlayerPropPolicy = PlayerPropPolicy()) -> dict[str, Any]:
    market = _market_probability(row)
    model, model_reasons = _model_probability(row)
    data_quality = _data_quality(row)
    books = _books(row)
    prop_type = normalize_prop_type(_field(row, ("prop_type", "market", "stat", "bet_type")))
    required: list[str] = []
    hard: list[str] = []
    reasons: list[str] = []

    if not _player_name(row):
        required.append("player_name")
    if prop_type == "unknown":
        required.append("prop_type")
    if market is None:
        required.append("market_probability_or_decimal_price")
    if model is None:
        required.append("player_model_probability_or_player_rates")
    if books is not None and books < policy.min_books:
        hard.append("low_book_coverage")
    if data_quality is not None and data_quality < policy.min_data_quality:
        hard.append("low_data_quality")
    injury_status = _text(_field(row, ("injury_status", "status", "player_status"))).lower()
    if injury_status in {"out", "doubtful", "inactive", "injured reserve", "ir"}:
        hard.append("bad_player_status")

    blend = None
    edge = None
    if market is not None and model is not None:
        weight = _market_weight(row, policy)
        blend = max(0.01, min(0.99, weight * market + (1.0 - weight) * model))
        edge = model - market
        reasons.append(f"market_weight_{weight:.2f}")
        reasons.extend(model_reasons)
    elif model_reasons:
        reasons.extend(model_reasons)

    status, stake = _grade_status(edge, required, hard, policy)
    reasons.extend(hard)
    if edge is not None:
        if edge >= policy.strong_model_edge:
            reasons.append("edge_8pct_plus")
        elif edge >= policy.normal_model_edge:
            reasons.append("edge_5pct_plus")
        elif edge >= policy.min_model_edge:
            reasons.append("edge_3pct_plus")
        else:
            reasons.append("edge_under_3pct")

    return {
        "prop_player_name": _player_name(row),
        "prop_type_normalized": prop_type,
        "prop_market_probability": "" if market is None else round(market, 4),
        "prop_no_vig_probability": "" if market is None else round(market, 4),
        "prop_model_probability": "" if model is None else round(model, 4),
        "prop_blended_probability": "" if blend is None else round(blend, 4),
        "prop_implied_edge": "" if edge is None else round(edge, 4),
        "prop_fair_decimal_price": "" if blend is None else _fair_price(blend),
        "prop_status": status,
        "prop_stake_units": f"{stake:.2f}",
        "prop_reasons": "; ".join(dict.fromkeys(reasons)),
        "prop_required_data": "; ".join(dict.fromkeys(required)),
    }


def apply_player_prop_layer(df: pd.DataFrame, policy: PlayerPropPolicy = PlayerPropPolicy()) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        for column in PLAYER_PROP_OUTPUT_COLUMNS:
            out[column] = pd.Series(dtype="object")
        return out
    scored = pd.DataFrame([score_player_prop(row.to_dict(), policy) for _, row in out.iterrows()], index=out.index)
    for column in PLAYER_PROP_OUTPUT_COLUMNS:
        out[column] = scored[column]
    return out


def rank_player_props(df: pd.DataFrame, *, include_watch: bool = False, top_n: int = 50, policy: PlayerPropPolicy = PlayerPropPolicy()) -> pd.DataFrame:
    scored = apply_player_prop_layer(df, policy)
    status_order = {
        "QUALIFIED_STRONG": 0,
        "QUALIFIED": 1,
        "QUALIFIED_SMALL": 2,
        "WATCH": 3,
        "TRACK_ONLY_NEEDS_PLAYER_MODEL_DATA": 4,
        "REJECT": 5,
    }
    scored["_status_order"] = scored["prop_status"].map(status_order).fillna(9)
    edge_numeric = pd.to_numeric(scored["prop_implied_edge"], errors="coerce").fillna(-999)
    scored["_edge_sort"] = edge_numeric
    if not include_watch:
        scored = scored[scored["prop_status"].isin({"QUALIFIED_STRONG", "QUALIFIED", "QUALIFIED_SMALL"})]
    scored = scored.sort_values(["_status_order", "_edge_sort"], ascending=[True, False]).head(top_n)
    return scored.drop(columns=["_status_order", "_edge_sort"], errors="ignore")
