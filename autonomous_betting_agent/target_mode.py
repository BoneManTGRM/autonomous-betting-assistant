from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TargetModePolicy:
    target_probability: float = 0.70
    tolerance: float = 0.01
    min_books: int = 4
    min_reliability: float = 90.0
    min_market_probability: float = 0.62
    min_ev: float = 0.0
    max_price_probability_gap: float = 0.12
    h2h_only: bool = True
    require_high_confidence: bool = True
    min_api_coverage_score: float = 1.0
    require_all_configured_apis: bool = False


@dataclass(frozen=True)
class TargetModeResult:
    passed: bool
    quality_score: int
    rejection_reason: str
    probability_band_low: float
    probability_band_high: float


def implied_probability(decimal_price: Any) -> float | None:
    try:
        price = float(decimal_price)
    except (TypeError, ValueError):
        return None
    if price <= 1.0:
        return None
    return 1.0 / price


def price_probability_gap(decimal_price: Any, market_probability: float) -> float | None:
    implied = implied_probability(decimal_price)
    if implied is None:
        return None
    return abs(implied - float(market_probability))


def estimated_ev(final_probability: float, decimal_price: Any) -> float | None:
    try:
        price = float(decimal_price)
    except (TypeError, ValueError):
        return None
    if price <= 1.0:
        return None
    return float(final_probability) * price - 1.0


def api_coverage_score(row: dict[str, Any]) -> float:
    configured = int(row.get('configured_api_sources_count', 0) or 0)
    used = int(row.get('api_sources_used_count', 0) or 0)
    if configured <= 0:
        return 0.0
    return round(max(0.0, min(1.0, used / configured)), 6)


def _truthy(value: Any) -> bool:
    return str(value or '').strip().lower() in {'true', '1', 'yes', 'y'}


def _confidence_is_high(value: Any) -> bool:
    return str(value or '').strip().lower() == 'high'


def target_quality_score(row: dict[str, Any], policy: TargetModePolicy) -> int:
    final_probability = float(row.get('final_probability_value', 0.0) or 0.0)
    reliability = float(row.get('reliability_score', 0.0) or 0.0)
    books = int(row.get('books', 0) or 0)
    ev_value = row.get('estimated_ev_value')
    gap = row.get('price_probability_gap_value')
    coverage = float(row.get('api_coverage_score', api_coverage_score(row)) or 0.0)

    distance = abs(final_probability - policy.target_probability)
    score = 100.0
    score -= min(35.0, (distance / max(policy.tolerance, 0.001)) * 12.0)
    score += min(8.0, max(0.0, float(ev_value or 0.0)) * 100.0)
    score += min(6.0, max(0, books - policy.min_books) * 1.5)
    score += min(8.0, max(0.0, reliability - policy.min_reliability) * 0.8)
    score += min(10.0, coverage * 10.0)
    if gap is not None:
        score -= min(15.0, float(gap) * 100.0)
    if row.get('duplicate_event_pick'):
        score -= 50.0
    if policy.require_high_confidence and not _confidence_is_high(row.get('confidence')):
        score -= 20.0
    if policy.require_all_configured_apis and not _truthy(row.get('all_configured_apis_used')):
        score -= 25.0
    return int(max(0, min(100, round(score))))


def evaluate_target_mode(row: dict[str, Any], policy: TargetModePolicy = TargetModePolicy()) -> TargetModeResult:
    reasons: list[str] = []
    low = policy.target_probability - policy.tolerance
    high = policy.target_probability + policy.tolerance

    final_probability = float(row.get('final_probability_value', 0.0) or 0.0)
    market_probability = float(row.get('market_probability_value', 0.0) or 0.0)
    reliability = float(row.get('reliability_score', 0.0) or 0.0)
    books = int(row.get('books', 0) or 0)
    gap = row.get('price_probability_gap_value')
    ev_value = row.get('estimated_ev_value')
    coverage = float(row.get('api_coverage_score', api_coverage_score(row)) or 0.0)

    if final_probability < low or final_probability > high:
        reasons.append(f'outside {low:.0%}-{high:.0%} band')
    if market_probability < policy.min_market_probability:
        reasons.append(f'market probability below floor ({market_probability:.1%} < {policy.min_market_probability:.1%})')
    if books < policy.min_books:
        reasons.append(f'not enough books ({books} < {policy.min_books})')
    if reliability < policy.min_reliability:
        reasons.append(f'reliability below target ({reliability:.1f} < {policy.min_reliability:.1f})')
    if gap is None or float(gap) > policy.max_price_probability_gap:
        reasons.append('price/probability mismatch')
    if ev_value is None or float(ev_value) < policy.min_ev:
        reasons.append('EV below target')
    if coverage < policy.min_api_coverage_score:
        reasons.append(f'API coverage below target ({coverage:.1%} < {policy.min_api_coverage_score:.1%})')
    if policy.require_all_configured_apis and not _truthy(row.get('all_configured_apis_used')):
        reasons.append('not all configured APIs used')
    if row.get('duplicate_event_pick'):
        reasons.append('duplicate event/pick')
    if policy.h2h_only and row.get('market_type') != 'h2h':
        reasons.append('not h2h')
    if policy.require_high_confidence and not _confidence_is_high(row.get('confidence')):
        reasons.append('not high confidence')

    return TargetModeResult(
        passed=not reasons,
        quality_score=target_quality_score(row, policy),
        rejection_reason='; '.join(reasons),
        probability_band_low=low,
        probability_band_high=high,
    )
