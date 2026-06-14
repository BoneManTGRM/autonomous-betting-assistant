from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import math

import pandas as pd


@dataclass(frozen=True)
class AraFilterPolicy:
    min_data_quality: float = 80.0
    min_books: int = 5
    limited_books: int = 8
    max_risk_penalty: float = 15.0
    max_overround: float = 0.15
    price_range_watch: float = 0.18
    soccer_draw_watch: float = 0.18
    soccer_draw_block: float = 0.25
    soccer_draw_extreme: float = 0.30
    min_price: float = 1.30
    max_price: float = 3.00
    min_edge: float = 0.03
    normal_edge: float = 0.05
    strong_edge: float = 0.08
    watch_edge: float = 0.08
    weather_watch_edge: float = 0.06
    baseball_low: float = 0.50
    baseball_high: float = 0.56
    prior_strength: float = 8.0
    wind_watch_mph: float = 15.0
    wind_block_mph: float = 25.0
    precip_watch_mm: float = 2.0
    precip_block_mm: float = 8.0


OUTPUT_COLUMNS = [
    "ara_record_key", "ara_sport_group", "ara_probability_bucket",
    "ara_market_probability_decimal", "ara_implied_probability_best_price",
    "ara_proxy_edge_vs_best_price", "ara_calibrated_probability_smoothed",
    "ara_calibrated_edge_vs_best_price", "ara_draw_probability_decimal",
    "ara_weather_flags", "ara_risk_flags", "ara_live_decision",
    "ara_live_stake_units", "ara_live_edge", "ara_decision_reason",
    "ara_recommended_market", "ara_proxy_filter_decision",
    "ara_proxy_filter_reason", "ara_requires_independent_probability", "ara_notes",
]


def parse_percent(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    text = str(value).strip()
    if not text:
        return None
    pct = "%" in text
    try:
        num = float(text.replace("%", "").replace(",", ""))
    except ValueError:
        return None
    if pct or num > 1:
        num /= 100.0
    return max(0.0, min(1.0, num))


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    value = parse_float(value)
    return None if value is None else int(round(value))


def fmt_pct(value: float | None) -> str:
    return "" if value is None else f"{value * 100:.1f}%"


def fmt_dec(value: float | None) -> str:
    return "" if value is None else f"{value:.3f}"


def _field(row: Mapping[str, Any], names: tuple[str, ...]) -> Any:
    lookup = {str(k).strip().lower().replace(" ", "_").replace("-", "_"): v for k, v in row.items()}
    for name in names:
        key = name.lower().replace(" ", "_").replace("-", "_")
        if key in lookup:
            return lookup[key]
    return None


def sport_group(value: Any) -> str:
    text = str(value or "").lower().replace("_", " ")
    if any(x in text for x in ("mlb", "milb", "baseball")):
        return "Baseball"
    if any(x in text for x in ("nba", "wnba", "basketball")):
        return "Basketball"
    if any(x in text for x in ("mma", "boxing", "ufc")):
        return "Combat"
    if any(x in text for x in ("nfl", "ncaaf", "american football", "americanfootball", "ufl")):
        return "American football"
    if any(x in text for x in ("nhl", "hockey")):
        return "Hockey"
    if any(x in text for x in ("atp", "wta", "tennis")):
        return "Tennis"
    if any(x in text for x in ("afl", "nrl", "rugby")):
        return "AFL/NRL/Rugby"
    if any(x in text for x in ("fifa", "soccer", "football", "liga", "league", "mls", "premier", "serie", "bundesliga")):
        return "Soccer"
    return "Other"


def record_key(row: Mapping[str, Any]) -> str:
    return " | ".join(str(_field(row, names) or "").strip() for names in (("Event", "event", "game", "match"), ("Start", "start", "commence_time"), ("Prediction", "prediction", "pick")))


def bucket(prob: float | None) -> str:
    if prob is None:
        return "Missing"
    low = math.floor(prob * 10) / 10
    high = min(1.0, low + 0.1)
    return f"{int(low * 100)}-{int(high * 100)}%"


def market_probability(row: Mapping[str, Any]) -> float | None:
    return parse_percent(_field(row, ("Market probability", "market_probability", "favorite_probability", "probability")))


def model_probability(row: Mapping[str, Any]) -> float | None:
    return parse_percent(_field(row, ("ARA model probability", "Model probability", "model_probability", "ara_probability", "weather_adjusted_probability")))


def best_price(row: Mapping[str, Any]) -> float | None:
    return parse_float(_field(row, ("Best price", "best_price", "sportsbook_odds", "decimal_odds", "odds", "price")))


def draw_probability(row: Mapping[str, Any]) -> float | None:
    return parse_percent(_field(row, ("Draw probability", "draw_probability", "draw_prob")))


def classification(row: Mapping[str, Any]) -> str:
    return str(_field(row, ("Classification", "classification", "decision")) or "").strip().title()


def implied_probability(row: Mapping[str, Any]) -> float | None:
    price = best_price(row)
    return 1.0 / price if price and price > 1.0 else None


def weather_flags_for(row: Mapping[str, Any], policy: AraFilterPolicy = AraFilterPolicy()) -> tuple[str, ...]:
    flags: list[str] = []
    group = sport_group(_field(row, ("Sport", "sport", "league", "competition")))
    outdoor_raw = _field(row, ("is_outdoor", "outdoor", "venue_outdoor"))
    outdoor_default = group in {"Baseball", "American football", "Soccer", "Tennis", "AFL/NRL/Rugby"}
    is_outdoor = outdoor_default if outdoor_raw is None else str(outdoor_raw).strip().lower() in {"1", "true", "yes", "y", "outdoor"}
    if not is_outdoor:
        return tuple(flags)

    wind_mph = parse_float(_field(row, ("wind_mph", "weather_wind_mph", "wind")))
    wind_kph = parse_float(_field(row, ("wind_kph", "weather_wind_kph")))
    if wind_mph is None and wind_kph is not None:
        wind_mph = wind_kph * 0.621371
    precip_mm = parse_float(_field(row, ("precip_mm", "weather_precip_mm", "precipitation_mm", "rain_mm")))
    condition = str(_field(row, ("weather_condition", "condition")) or "").lower()
    condition_tokens = {token.strip(".,;:!?()[]") for token in condition.replace("/", " ").replace("-", " ").split()}

    if wind_mph is not None:
        if wind_mph >= policy.wind_block_mph:
            flags.append("weather_wind_block")
        elif wind_mph >= policy.wind_watch_mph:
            flags.append("weather_wind_watch")
    if precip_mm is not None:
        if precip_mm >= policy.precip_block_mm:
            flags.append("weather_precip_block")
        elif precip_mm >= policy.precip_watch_mm:
            flags.append("weather_precip_watch")
    if condition_tokens & {"storm", "storms", "thunder", "thunderstorm", "snow", "ice", "icy", "sleet"}:
        flags.append("weather_condition_severe")
    return tuple(flags)


def risk_flags_for(row: Mapping[str, Any], policy: AraFilterPolicy = AraFilterPolicy()) -> tuple[str, ...]:
    flags: list[str] = []
    cls = classification(row)
    group = sport_group(_field(row, ("Sport", "sport", "league", "competition")))
    mprob = market_probability(row)
    dprob = draw_probability(row)
    implied = implied_probability(row)
    proxy_edge = mprob - implied if mprob is not None and implied is not None else None
    data_quality = parse_float(_field(row, ("Data quality", "data_quality", "quality")))
    risk_penalty = parse_float(_field(row, ("Risk penalty", "risk_penalty", "market_overround")))
    if risk_penalty is not None and risk_penalty <= 1.0:
        risk_penalty *= 100.0
    books = parse_int(_field(row, ("Books", "bookmaker_count", "bookmakers", "source_count")))
    price_range = parse_float(_field(row, ("Price range", "price_range", "market_price_range")))

    if cls == "Avoid":
        flags.append("classification_avoid")
    elif cls == "Watch":
        flags.append("watch_track_only")
    if data_quality is None:
        flags.append("missing_data_quality")
    elif data_quality < policy.min_data_quality:
        flags.append("data_quality_under_80")
    if risk_penalty is not None:
        if risk_penalty > policy.max_risk_penalty:
            flags.append("risk_penalty_over_15")
        if risk_penalty / 100.0 > policy.max_overround:
            flags.append("market_overround_high")
    if price_range is not None and price_range >= policy.price_range_watch:
        flags.append("price_range_disagreement")
    if books is None:
        flags.append("missing_book_count")
    elif books < policy.min_books:
        flags.append("low_book_coverage_under_5")
    elif books < policy.limited_books:
        flags.append("limited_book_coverage_under_8")

    if group == "Soccer":
        if dprob is None:
            flags.append("soccer_draw_probability_missing")
        elif dprob >= policy.soccer_draw_extreme:
            flags.append("soccer_draw_risk_extreme_30_plus")
        elif dprob >= policy.soccer_draw_block:
            flags.append("soccer_draw_risk_block_ml_25_plus")
        elif dprob >= policy.soccer_draw_watch:
            flags.append("soccer_draw_risk_elevated_18_plus")
    if group == "Baseball" and cls == "Watch" and mprob is not None and policy.baseball_low <= mprob <= policy.baseball_high:
        flags.append("baseball_watch_low_edge_50_56")
    price = best_price(row)
    if price is None:
        flags.append("missing_best_price")
    elif price < policy.min_price:
        flags.append("heavy_favorite_price_under_1_30")
    elif price > policy.max_price:
        flags.append("longshot_price_over_3_00")
    if proxy_edge is None:
        flags.append("proxy_edge_missing")
    elif proxy_edge < policy.min_edge:
        flags.append("proxy_edge_under_3pct")
    if model_probability(row) is None:
        flags.append("independent_ara_probability_missing")
    return tuple(flags)


def proxy_filter_decision(row: Mapping[str, Any], policy: AraFilterPolicy = AraFilterPolicy()) -> tuple[str, str]:
    flags = risk_flags_for(row, policy)
    weather = weather_flags_for(row, policy)
    if "classification_avoid" in flags:
        return "PROXY_AVOID", "Avoid classification."
    if "soccer_draw_risk_extreme_30_plus" in flags or "soccer_draw_risk_block_ml_25_plus" in flags:
        return "PROXY_WATCH_NO_ML", "Soccer draw risk blocks moneyline."
    if "baseball_watch_low_edge_50_56" in flags:
        return "PROXY_WATCH", "Baseball Watch pick in 50-56% probability band is too volatile."
    if "data_quality_under_80" in flags or "low_book_coverage_under_5" in flags:
        return "PROXY_WATCH", "Insufficient data quality or book coverage."
    if "market_overround_high" in flags or "price_range_disagreement" in flags:
        return "PROXY_WATCH", "Market is too noisy or books disagree too much."
    if "weather_wind_block" in weather or "weather_precip_block" in weather or "weather_condition_severe" in weather:
        return "PROXY_WATCH", "Severe weather requires weather-adjusted model probability."
    return "PROXY_CANDIDATE", "Passes current leak-control filters; still needs independent edge."


def live_decision(row: Mapping[str, Any], policy: AraFilterPolicy = AraFilterPolicy()) -> tuple[str, float, float | None, str, tuple[str, ...], tuple[str, ...]]:
    flags = risk_flags_for(row, policy)
    weather = weather_flags_for(row, policy)
    implied = implied_probability(row)
    model = model_probability(row)
    edge = model - implied if model is not None and implied is not None else None
    hard = {"classification_avoid", "soccer_draw_risk_extreme_30_plus", "soccer_draw_risk_block_ml_25_plus", "missing_best_price", "missing_data_quality", "data_quality_under_80", "low_book_coverage_under_5", "heavy_favorite_price_under_1_30", "longshot_price_over_3_00", "baseball_watch_low_edge_50_56"}
    noisy = {"market_overround_high", "price_range_disagreement"}
    weather_hard = {"weather_wind_block", "weather_precip_block", "weather_condition_severe"}
    if "classification_avoid" in flags:
        return "AVOID", 0.0, edge, "Avoid classification blocks live action.", flags, weather
    if any(flag in hard for flag in flags):
        return "WATCH", 0.0, edge, "Blocked by hard risk controls: " + ", ".join(flag for flag in flags if flag in hard), flags, weather
    if any(flag in noisy for flag in flags) and (edge is None or edge < policy.strong_edge):
        return "WATCH", 0.0, edge, "Market noise requires 8%+ independent edge: " + ", ".join(flag for flag in flags if flag in noisy), flags, weather
    if any(flag in weather_hard for flag in weather) and model is None:
        return "WATCH", 0.0, edge, "Blocked by weather controls until weather-adjusted probability exists: " + ", ".join(flag for flag in weather if flag in weather_hard), flags, weather
    if model is None or edge is None:
        return "WATCH", 0.0, edge, "Independent ARA probability is missing; no live action.", flags, weather
    required_edge = policy.min_edge
    if weather and any(flag.endswith("watch") for flag in weather):
        required_edge = max(required_edge, policy.weather_watch_edge)
    if edge < required_edge:
        return "WATCH", 0.0, edge, f"Independent edge under required threshold ({required_edge:.0%}).", flags, weather
    if "watch_track_only" in flags and edge < policy.watch_edge:
        return "WATCH", 0.0, edge, "Watch classification requires 8%+ independent edge.", flags, weather
    if edge >= policy.strong_edge:
        return "BET_STRONG", 1.0, edge, "Independent edge is 8%+ and hard filters passed.", flags, weather
    if edge >= policy.normal_edge:
        return "BET", 0.75, edge, "Independent edge is 5%+ and hard filters passed.", flags, weather
    return "BET_SMALL", 0.25, edge, "Independent edge is 3%+ and hard filters passed.", flags, weather


def _smooth_maps(df: pd.DataFrame, policy: AraFilterPolicy) -> tuple[float | None, dict[str, float], dict[str, float], dict[str, float]]:
    if df.empty or "result" not in df.columns:
        return None, {}, {}, {}
    work = df.copy()
    work["_result"] = work["result"].astype(str).str.lower().str.strip()
    done = work[work["_result"].isin(["won", "lost"])].copy()
    if done.empty:
        return None, {}, {}, {}
    done["_win"] = (done["_result"] == "won").astype(float)
    done["_bucket"] = done.apply(lambda row: bucket(market_probability(row.to_dict())), axis=1)
    done["_class"] = done.apply(lambda row: classification(row.to_dict()) or "Missing", axis=1)
    done["_sport"] = done.apply(lambda row: sport_group(_field(row.to_dict(), ("Sport", "sport", "league", "competition"))), axis=1)
    base = float(done["_win"].mean())

    def make(column: str) -> dict[str, float]:
        out: dict[str, float] = {}
        for key, group in done.groupby(column):
            wins = float(group["_win"].sum())
            count = float(len(group))
            out[str(key)] = (wins + policy.prior_strength * base) / (count + policy.prior_strength)
        return out

    return base, make("_bucket"), make("_class"), make("_sport")


def _calibrated(row: Mapping[str, Any], base: float | None, by_bucket: dict[str, float], by_class: dict[str, float], by_sport: dict[str, float]) -> float | None:
    mprob = market_probability(row)
    if mprob is None:
        return None
    if base is None:
        return mprob
    if mprob < 0.50:
        return max(0.01, min(0.49, 0.85 * mprob + 0.15 * base))
    vals = [by_bucket.get(bucket(mprob)), by_class.get(classification(row) or "Missing"), by_sport.get(sport_group(_field(row, ("Sport", "sport", "league", "competition"))))]
    vals = [value for value in vals if value is not None]
    if not vals:
        return mprob
    empirical = sum(vals) / len(vals)
    return max(0.01, min(0.99, 0.65 * empirical + 0.35 * mprob))


def apply_ara_decision_layer(df: pd.DataFrame, policy: AraFilterPolicy = AraFilterPolicy()) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        for column in OUTPUT_COLUMNS:
            out[column] = pd.Series(dtype="object")
        return out
    base, by_bucket, by_class, by_sport = _smooth_maps(out, policy)
    rows = []
    for _, series in out.iterrows():
        row = series.to_dict()
        implied = implied_probability(row)
        mprob = market_probability(row)
        dprob = draw_probability(row)
        proxy_edge = mprob - implied if mprob is not None and implied is not None else None
        cal = _calibrated(row, base, by_bucket, by_class, by_sport)
        cal_edge = cal - implied if cal is not None and implied is not None else None
        decision, units, edge, reason, flags, weather = live_decision(row, policy)
        pdec, preason = proxy_filter_decision(row, policy)
        group = sport_group(_field(row, ("Sport", "sport", "league", "competition")))
        market = "Moneyline only if independent ARA edge confirms value"
        if group == "Soccer" and any(flag.startswith("soccer_draw_risk") for flag in flags):
            market = "No moneyline; consider draw-no-bet/double-chance only if independent edge confirms value"
        if weather:
            market = "Use weather-adjusted model probability before live action"
        rows.append({
            "ara_record_key": record_key(row),
            "ara_sport_group": group,
            "ara_probability_bucket": bucket(mprob),
            "ara_market_probability_decimal": fmt_dec(mprob),
            "ara_implied_probability_best_price": fmt_pct(implied),
            "ara_proxy_edge_vs_best_price": fmt_pct(proxy_edge),
            "ara_calibrated_probability_smoothed": fmt_pct(cal),
            "ara_calibrated_edge_vs_best_price": fmt_pct(cal_edge),
            "ara_draw_probability_decimal": fmt_dec(dprob),
            "ara_weather_flags": "; ".join(weather),
            "ara_risk_flags": "; ".join(flags),
            "ara_live_decision": decision,
            "ara_live_stake_units": f"{units:.2f}",
            "ara_live_edge": fmt_pct(edge),
            "ara_decision_reason": reason,
            "ara_recommended_market": market,
            "ara_proxy_filter_decision": pdec,
            "ara_proxy_filter_reason": preason,
            "ara_requires_independent_probability": "NO" if model_probability(row) is not None else "YES",
            "ara_notes": "Odds-derived probability is not independent model edge. Add weather-adjusted model probability before live action.",
        })
    add = pd.DataFrame(rows, index=out.index)
    for column in OUTPUT_COLUMNS:
        out[column] = add[column]
    return out


def dedupe_ara_records(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    keys = df.apply(lambda row: record_key(row.to_dict()), axis=1)
    return df.loc[~keys.duplicated()].copy()
