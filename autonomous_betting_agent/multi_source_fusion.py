from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

PRICE_COLUMNS = ("best_price", "entry_odds", "price", "odds", "decimal_odds")
MODEL_PROB_COLUMNS = ("model_probability", "probability", "confidence_probability", "prop_blended_probability", "prop_model_probability")
STATS_PROB_COLUMNS = ("stats_probability", "team_probability", "form_probability", "ara_stats_probability")
DIRECT_STATS_COLUMNS = ("stats_adjustment", "team_strength_adjustment", "form_adjustment", "schedule_adjustment", "matchup_adjustment")
DIRECT_INJURY_COLUMNS = ("injury_adjustment", "lineup_adjustment")
DIRECT_WEATHER_COLUMNS = ("weather_adjustment", "context_adjustment")
DIRECT_MEMORY_COLUMNS = ("ara_memory_adjustment", "memory_adjustment", "learning_adjustment")


@dataclass(frozen=True)
class FusionPolicy:
    market_weight: float = 1.0
    stats_weight: float = 0.35
    injury_weight: float = 1.0
    weather_weight: float = 1.0
    memory_weight: float = 0.75
    max_stats_adjustment: float = 0.06
    max_injury_adjustment: float = 0.06
    max_weather_adjustment: float = 0.035
    max_memory_adjustment: float = 0.04
    min_probability: float = 0.01
    max_probability: float = 0.99


@dataclass(frozen=True)
class FusionResult:
    market_probability: float | None
    stats_adjustment: float
    injury_adjustment: float
    weather_adjustment: float
    ara_memory_adjustment: float
    final_probability: float | None
    reliability_score: float
    confidence: str
    fusion_reason: str
    fusion_warning: str


def _first(row: Mapping[str, Any], names: tuple[str, ...]) -> Any:
    lowered = {str(key).lower().replace(" ", "_").replace("-", "_"): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.lower().replace(" ", "_").replace("-", "_"))
        if value not in (None, ""):
            return value
    return ""


def _float(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "").replace("%", "")
    if not text or text.lower() in {"none", "null", "nan", "unknown"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def parse_probability(value: Any) -> float | None:
    number = _float(value)
    if number is None:
        return None
    if number > 1.0:
        number /= 100.0
    if number < 0 or number > 1:
        return None
    return number


def parse_price(value: Any) -> float | None:
    price = _float(value)
    if price is None:
        return None
    if price >= 100:
        return 1.0 + price / 100.0
    if price <= -100:
        return 1.0 + 100.0 / abs(price)
    if price > 1.0:
        return price
    return None


def market_probability_from_row(row: Mapping[str, Any]) -> float | None:
    direct = parse_probability(_first(row, ("market_probability", "implied_probability", "book_probability")))
    if direct is not None:
        return direct
    price = parse_price(_first(row, PRICE_COLUMNS))
    if price is None or price <= 1.0:
        return None
    return _clamp(1.0 / price, 0.01, 0.99)


def _direct_adjustment(row: Mapping[str, Any], columns: tuple[str, ...], cap: float) -> float | None:
    values: list[float] = []
    for column in columns:
        value = _float(_first(row, (column,)))
        if value is None:
            continue
        if abs(value) > 1.0:
            value /= 100.0
        values.append(_clamp(value, -cap, cap))
    if not values:
        return None
    return _clamp(sum(values), -cap, cap)


def _stats_adjustment(row: Mapping[str, Any], market_probability: float | None, policy: FusionPolicy) -> tuple[float, str]:
    direct = _direct_adjustment(row, DIRECT_STATS_COLUMNS, policy.max_stats_adjustment)
    if direct is not None:
        return round(direct * policy.stats_weight, 6), "direct stats adjustment"
    stats_probability = parse_probability(_first(row, STATS_PROB_COLUMNS))
    model_probability = parse_probability(_first(row, MODEL_PROB_COLUMNS))
    comparison_probability = stats_probability if stats_probability is not None else model_probability
    if market_probability is None or comparison_probability is None:
        return 0.0, "missing stats probability"
    raw = (comparison_probability - market_probability) * policy.stats_weight
    return round(_clamp(raw, -policy.max_stats_adjustment, policy.max_stats_adjustment), 6), "stats probability vs market"


def _injury_adjustment(row: Mapping[str, Any], policy: FusionPolicy) -> tuple[float, str]:
    direct = _direct_adjustment(row, DIRECT_INJURY_COLUMNS, policy.max_injury_adjustment)
    if direct is not None:
        return round(direct * policy.injury_weight, 6), "direct injury/lineup adjustment"
    risk = _float(_first(row, ("injury_risk_score", "lineup_risk_score")))
    key_out = str(_first(row, ("key_player_out",))).lower() in {"true", "1", "yes"}
    confirmed = str(_first(row, ("lineup_confirmed",))).lower()
    adjustment = 0.0
    reason: list[str] = []
    if risk is not None:
        adjustment += ((risk - 100.0) / 100.0) * policy.max_injury_adjustment
        reason.append("injury risk score")
    if key_out:
        adjustment -= policy.max_injury_adjustment
        reason.append("key player out")
    if confirmed in {"false", "unknown"}:
        adjustment -= 0.015
        reason.append("lineup not confirmed")
    return round(_clamp(adjustment * policy.injury_weight, -policy.max_injury_adjustment, policy.max_injury_adjustment), 6), "; ".join(reason) or "no injury signal"


def _weather_adjustment(row: Mapping[str, Any], policy: FusionPolicy) -> tuple[float, str]:
    direct = _direct_adjustment(row, DIRECT_WEATHER_COLUMNS, policy.max_weather_adjustment)
    if direct is not None:
        return round(direct * policy.weather_weight, 6), "direct weather/context adjustment"
    risk = _float(_first(row, ("weather_risk_score", "weather_score")))
    flag = str(_first(row, ("weather_flag",))).upper()
    if risk is None and not flag:
        return 0.0, "missing weather signal"
    adjustment = 0.0
    if risk is not None:
        adjustment += ((risk - 100.0) / 100.0) * policy.max_weather_adjustment
    if flag in {"HIGH", "REJECT_OR_WAIT"}:
        adjustment -= policy.max_weather_adjustment
    elif flag in {"WATCH", "REDUCE_CONFIDENCE"}:
        adjustment -= 0.01
    return round(_clamp(adjustment * policy.weather_weight, -policy.max_weather_adjustment, policy.max_weather_adjustment), 6), "weather risk score"


def _memory_adjustment(row: Mapping[str, Any], policy: FusionPolicy) -> tuple[float, str]:
    direct = _direct_adjustment(row, DIRECT_MEMORY_COLUMNS, policy.max_memory_adjustment)
    if direct is not None:
        return round(direct * policy.memory_weight, 6), "direct ARA memory adjustment"
    bucket_roi = _float(_first(row, ("bucket_roi", "profile_roi", "market_profile_roi", "historical_roi")))
    bucket_win_rate = parse_probability(_first(row, ("bucket_win_rate", "profile_win_rate", "historical_win_rate")))
    adjustment = 0.0
    reasons: list[str] = []
    if bucket_roi is not None:
        if abs(bucket_roi) > 1.0:
            bucket_roi /= 100.0
        adjustment += _clamp(bucket_roi * 0.10, -policy.max_memory_adjustment, policy.max_memory_adjustment)
        reasons.append("historical ROI")
    if bucket_win_rate is not None:
        adjustment += _clamp((bucket_win_rate - 0.5) * 0.10, -policy.max_memory_adjustment, policy.max_memory_adjustment)
        reasons.append("historical win rate")
    return round(_clamp(adjustment * policy.memory_weight, -policy.max_memory_adjustment, policy.max_memory_adjustment), 6), "; ".join(reasons) or "missing ARA memory signal"


def fuse_row(row: Mapping[str, Any], policy: FusionPolicy = FusionPolicy()) -> FusionResult:
    market = market_probability_from_row(row)
    model = parse_probability(_first(row, MODEL_PROB_COLUMNS))
    base = market if market is not None else model
    warnings: list[str] = []
    if market is None:
        warnings.append("missing market probability; using model probability as fallback")
    stats_adj, stats_reason = _stats_adjustment(row, market, policy)
    injury_adj, injury_reason = _injury_adjustment(row, policy)
    weather_adj, weather_reason = _weather_adjustment(row, policy)
    memory_adj, memory_reason = _memory_adjustment(row, policy)
    if base is None:
        return FusionResult(None, stats_adj, injury_adj, weather_adj, memory_adj, None, 0.0, "LOW", "missing base probability", "; ".join(warnings))
    final_probability = _clamp(base + stats_adj + injury_adj + weather_adj + memory_adj, policy.min_probability, policy.max_probability)
    delta = abs(final_probability - base)
    reliability = 70.0
    if market is not None:
        reliability += 12.0
    if stats_reason != "missing stats probability":
        reliability += 6.0
    if injury_reason != "no injury signal":
        reliability += 4.0
    if weather_reason != "missing weather signal":
        reliability += 3.0
    if memory_reason != "missing ARA memory signal":
        reliability += 5.0
    if delta > 0.10:
        reliability -= 15.0
        warnings.append("large probability move from market")
    elif delta > 0.06:
        reliability -= 7.0
        warnings.append("moderate probability move from market")
    reliability = round(_clamp(reliability, 0.0, 100.0), 2)
    confidence = "HIGH" if reliability >= 78 and final_probability >= 0.58 else "MEDIUM" if reliability >= 60 else "LOW"
    reason = f"market base; {stats_reason}; {injury_reason}; {weather_reason}; {memory_reason}"
    return FusionResult(
        None if market is None else round(market, 6),
        stats_adj,
        injury_adj,
        weather_adj,
        memory_adj,
        round(final_probability, 6),
        reliability,
        confidence,
        reason,
        "; ".join(warnings),
    )


def fuse_rows(rows: list[Mapping[str, Any]], policy: FusionPolicy = FusionPolicy(), *, override_model_probability: bool = True) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        result = fuse_row(row, policy)
        enriched = dict(row)
        original_probability = _first(row, MODEL_PROB_COLUMNS)
        enriched.setdefault("raw_model_probability", original_probability)
        enriched["market_probability"] = "" if result.market_probability is None else str(result.market_probability)
        enriched["stats_adjustment"] = str(result.stats_adjustment)
        enriched["injury_adjustment"] = str(result.injury_adjustment)
        enriched["weather_adjustment"] = str(result.weather_adjustment)
        enriched["ara_memory_adjustment"] = str(result.ara_memory_adjustment)
        enriched["final_probability"] = "" if result.final_probability is None else str(result.final_probability)
        enriched["final_adjusted_probability"] = enriched["final_probability"]
        enriched["reliability_score"] = str(result.reliability_score)
        enriched["confidence"] = result.confidence
        enriched["fusion_reason"] = result.fusion_reason
        enriched["fusion_warning"] = result.fusion_warning
        if override_model_probability and result.final_probability is not None:
            enriched["model_probability"] = str(result.final_probability)
        output.append(enriched)
    return output
