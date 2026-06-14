from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from .ara_filters import parse_float, parse_percent

PLAYER_PROP_OUTPUT_COLUMNS = [
    "prop_player_name",
    "prop_type_normalized",
    "prop_market_source",
    "prop_market_probability",
    "prop_no_vig_probability",
    "prop_model_probability",
    "prop_blended_probability",
    "prop_implied_edge",
    "prop_fair_decimal_price",
    "prop_data_quality",
    "prop_confidence_score",
    "prop_status",
    "prop_stake_units",
    "prop_reasons",
    "prop_required_data",
]

PROP_ALIASES = {
    "td": "touchdown",
    "anytime td": "touchdown",
    "anytime_td": "touchdown",
    "touchdown": "touchdown",
    "anytime touchdown": "touchdown",
    "anytime_touchdown": "touchdown",
    "home run": "home_run",
    "home_run": "home_run",
    "hr": "home_run",
    "homerun": "home_run",
    "goal": "goal",
    "anytime goal": "goal",
    "anytime_goal": "goal",
    "shot on goal": "shot_on_goal",
    "shot_on_goal": "shot_on_goal",
    "sog": "shot_on_goal",
    "assist": "assist",
    "hit": "hit",
    "strikeout": "strikeout",
    "strikeouts": "strikeout",
    "k": "strikeout",
    "ks": "strikeout",
    "reception": "reception",
    "receptions": "reception",
    "rush yard": "rush_yards",
    "rush_yard": "rush_yards",
    "rush yards": "rush_yards",
    "rush_yards": "rush_yards",
    "rushing yards": "rush_yards",
    "rushing_yards": "rush_yards",
    "receiving yard": "receiving_yards",
    "receiving_yard": "receiving_yards",
    "receiving yards": "receiving_yards",
    "receiving_yards": "receiving_yards",
    "passing yard": "passing_yards",
    "passing_yard": "passing_yards",
    "passing yards": "passing_yards",
    "passing_yards": "passing_yards",
}

CRITICAL_WATCH_REASONS = {
    "extreme_market_probability",
    "extreme_model_probability",
    "model_market_disagreement_extreme",
}


@dataclass(frozen=True)
class PlayerPropPolicy:
    min_books: int = 4
    strong_books: int = 8
    min_data_quality: float = 75.0
    strong_data_quality: float = 85.0
    min_sample_size: int = 10
    min_model_edge: float = 0.03
    normal_model_edge: float = 0.05
    strong_model_edge: float = 0.08
    max_blend_market_weight: float = 0.65
    min_blend_market_weight: float = 0.35
    max_stake_units: float = 0.50
    extreme_probability_low: float = 0.03
    extreme_probability_high: float = 0.97


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


def _fmt_prob(value: float | None) -> str | float:
    return "" if value is None else round(value, 4)


def normalize_prop_type(value: Any) -> str:
    raw = _text(value).lower()
    spaced = raw.replace("-", " ").replace("_", " ")
    spaced = " ".join(spaced.split())
    underscored = spaced.replace(" ", "_")
    return PROP_ALIASES.get(underscored, PROP_ALIASES.get(spaced, underscored or "unknown"))


def implied_probability_from_price(price: Any) -> float | None:
    """Convert decimal or American odds to implied probability.

    Decimal odds use values like 1.80 or 2.25. American odds use values like +150 or -120.
    Values between 1.01 and 99.99 are treated as decimal prices; values >=100 or <=-100 are treated as American odds.
    """
    price_float = parse_float(price)
    if price_float is None:
        return None
    if price_float >= 100:
        return 100.0 / (price_float + 100.0)
    if price_float <= -100:
        return abs(price_float) / (abs(price_float) + 100.0)
    if price_float > 1.0:
        return 1.0 / price_float
    return None


def no_vig_binary_probability(over_price: Any, under_price: Any) -> float | None:
    over_imp = implied_probability_from_price(over_price)
    under_imp = implied_probability_from_price(under_price)
    if over_imp is None or under_imp is None:
        return None
    total = over_imp + under_imp
    if total <= 0:
        return None
    return over_imp / total


def _player_name(row: Mapping[str, Any]) -> str:
    return _text(_field(row, ("player", "player_name", "athlete", "name")))


def _market_probability_with_source(row: Mapping[str, Any]) -> tuple[float | None, float | None, str]:
    direct = parse_percent(_field(row, ("market_probability", "prop_market_probability", "book_probability", "implied_probability")))
    if direct is not None:
        return direct, None, "direct_market_probability"
    no_vig = no_vig_binary_probability(_field(row, ("over_price", "yes_price", "best_yes_price")), _field(row, ("under_price", "no_price", "best_no_price")))
    if no_vig is not None:
        return no_vig, no_vig, "binary_no_vig"
    implied = implied_probability_from_price(_field(row, ("best_price", "price", "decimal_odds", "odds", "american_odds")))
    if implied is not None:
        return implied, None, "single_price_implied"
    return None, None, "missing_market_probability"


def _model_probability(row: Mapping[str, Any]) -> tuple[float | None, list[str]]:
    reasons: list[str] = []
    direct = parse_percent(_field(row, ("model_probability", "prop_model_probability", "player_model_probability", "ara_model_probability")))
    if direct is not None:
        return direct, ["direct_model_probability"]

    inputs: list[tuple[float | None, float, str]] = [
        (parse_percent(_field(row, ("recent_rate",))), 0.35, "recent_rate"),
        (parse_percent(_field(row, ("season_rate", "player_season_rate"))), 0.30, "season_rate"),
        (parse_percent(_field(row, ("opponent_allowed_rate",))), 0.20, "opponent_allowed_rate"),
        (parse_percent(_field(row, ("usage_rate",))), 0.15, "usage_rate"),
    ]
    weighted = 0.0
    weight = 0.0
    for value, item_weight, reason in inputs:
        if value is not None:
            weighted += value * item_weight
            weight += item_weight
            reasons.append(reason)
    if weight <= 0:
        return None, []
    return max(0.01, min(0.99, weighted / weight)), reasons


def _data_quality(row: Mapping[str, Any]) -> float | None:
    value = parse_float(_field(row, ("data_quality", "prop_data_quality", "quality")))
    if value is None:
        return None
    return value * 100.0 if value <= 1.0 else value


def _books(row: Mapping[str, Any]) -> int | None:
    value = parse_float(_field(row, ("books", "book_count", "bookmaker_count", "prop_books")))
    return None if value is None else int(round(value))


def _sample_size(row: Mapping[str, Any]) -> int | None:
    values = []
    for name in ("sample_size", "recent_games", "season_games", "games_played", "player_games", "opponent_sample_size"):
        value = parse_float(_field(row, (name,)))
        if value is not None:
            values.append(int(round(value)))
    return min(values) if values else None


def _market_weight(row: Mapping[str, Any], policy: PlayerPropPolicy) -> float:
    books = _books(row) or 0
    quality = _data_quality(row) or 0.0
    if books >= policy.strong_books and quality >= policy.strong_data_quality:
        return policy.max_blend_market_weight
    if books >= policy.min_books and quality >= policy.min_data_quality:
        return 0.50
    return policy.min_blend_market_weight


def _confidence_score(row: Mapping[str, Any], market: float | None, model: float | None, edge: float | None, policy: PlayerPropPolicy) -> float:
    score = 40.0
    books = _books(row)
    quality = _data_quality(row)
    sample = _sample_size(row)
    if market is not None:
        score += 10
    if model is not None:
        score += 15
    if books is not None:
        score += min(12.0, books * 1.5)
    if quality is not None:
        score += max(-10.0, min(12.0, (quality - policy.min_data_quality) * 0.4))
    if sample is not None:
        score += min(8.0, sample * 0.4)
    if edge is not None and edge >= policy.strong_model_edge:
        score += 6
    elif edge is not None and edge < 0:
        score -= 10
    return round(max(0.0, min(100.0, score)), 1)


def _fair_price(probability: float | None) -> float | None:
    if probability is None or probability <= 0:
        return None
    return round(1.0 / probability, 4)


def _has_critical_watch(watch_reasons: list[str]) -> bool:
    return any(reason in CRITICAL_WATCH_REASONS for reason in watch_reasons)


def _grade_status(edge: float | None, required: list[str], hard_reasons: list[str], watch_reasons: list[str], confidence: float, policy: PlayerPropPolicy) -> tuple[str, float]:
    if hard_reasons:
        return "REJECT", 0.0
    if required:
        return "TRACK_ONLY_NEEDS_PLAYER_MODEL_DATA", 0.0
    if edge is None or edge < policy.min_model_edge:
        return "WATCH", 0.0
    if _has_critical_watch(watch_reasons):
        return "WATCH", 0.0
    if watch_reasons and edge < policy.strong_model_edge:
        return "WATCH", 0.0
    if confidence < 60 and edge < policy.strong_model_edge:
        return "WATCH", 0.0
    if edge >= policy.strong_model_edge and confidence >= 65:
        return "QUALIFIED_STRONG", min(policy.max_stake_units, 0.50)
    if edge >= policy.normal_model_edge and confidence >= 60:
        return "QUALIFIED", min(policy.max_stake_units, 0.35)
    return "QUALIFIED_SMALL", min(policy.max_stake_units, 0.20)


def score_player_prop(row: Mapping[str, Any], policy: PlayerPropPolicy = PlayerPropPolicy()) -> dict[str, Any]:
    market, no_vig, market_source = _market_probability_with_source(row)
    model, model_reasons = _model_probability(row)
    data_quality = _data_quality(row)
    books = _books(row)
    sample_size = _sample_size(row)
    prop_type = normalize_prop_type(_field(row, ("prop_type", "market", "stat", "bet_type")))
    required: list[str] = []
    hard: list[str] = []
    watch: list[str] = []
    reasons: list[str] = [market_source] if market_source != "missing_market_probability" else []

    if not _player_name(row):
        required.append("player_name")
    if prop_type == "unknown":
        required.append("prop_type")
    if market is None:
        required.append("market_probability_or_price")
    elif market <= policy.extreme_probability_low or market >= policy.extreme_probability_high:
        watch.append("extreme_market_probability")
    if model is None:
        required.append("player_model_probability_or_player_rates")
    elif model <= policy.extreme_probability_low or model >= policy.extreme_probability_high:
        watch.append("extreme_model_probability")
    if market is not None and model is not None and abs(model - market) >= 0.25:
        watch.append("model_market_disagreement_extreme")
    if books is None:
        watch.append("missing_book_coverage")
    elif books < policy.min_books:
        hard.append("low_book_coverage")
    if data_quality is None:
        watch.append("missing_data_quality")
    elif data_quality < policy.min_data_quality:
        hard.append("low_data_quality")
    if sample_size is None:
        watch.append("missing_sample_size")
    elif sample_size < policy.min_sample_size:
        watch.append("small_sample_size")
    injury_status = _text(_field(row, ("injury_status", "status", "player_status"))).lower()
    if injury_status in {"out", "doubtful", "inactive", "injured reserve", "ir"}:
        hard.append("bad_player_status")
    elif injury_status in {"questionable", "probable", "limited"}:
        watch.append("player_status_watch")

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

    confidence = _confidence_score(row, market, model, edge, policy)
    status, stake = _grade_status(edge, required, hard, watch, confidence, policy)
    reasons.extend(hard)
    reasons.extend(watch)
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
        "prop_market_source": market_source,
        "prop_market_probability": _fmt_prob(market),
        "prop_no_vig_probability": _fmt_prob(no_vig),
        "prop_model_probability": _fmt_prob(model),
        "prop_blended_probability": _fmt_prob(blend),
        "prop_implied_edge": _fmt_prob(edge),
        "prop_fair_decimal_price": "" if blend is None else _fair_price(blend),
        "prop_data_quality": "" if data_quality is None else round(data_quality, 1),
        "prop_confidence_score": confidence,
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
    confidence_numeric = pd.to_numeric(scored["prop_confidence_score"], errors="coerce").fillna(0)
    scored["_edge_sort"] = edge_numeric
    scored["_confidence_sort"] = confidence_numeric
    if not include_watch:
        scored = scored[scored["prop_status"].isin({"QUALIFIED_STRONG", "QUALIFIED", "QUALIFIED_SMALL"})]
    scored = scored.sort_values(["_status_order", "_edge_sort", "_confidence_sort"], ascending=[True, False, False]).head(top_n)
    return scored.drop(columns=["_status_order", "_edge_sort", "_confidence_sort"], errors="ignore")
