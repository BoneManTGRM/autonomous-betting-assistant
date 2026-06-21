from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class OddsAudit:
    decimal_price: float | None
    robust_decimal_price: float | None
    odds_at_pick: float | None
    status: str
    reason: str
    price_range_risk: float
    best_to_average_ratio: float | None
    implied_probability: float | None
    quarantine: bool


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def audit_prices(
    *,
    best_price: Any = None,
    average_price: Any = None,
    worst_price: Any = None,
    normalized_probability: Any = None,
    market: Any = 'h2h',
) -> OddsAudit:
    """Choose a safe price for proof rows and quarantine likely side/market flips.

    The proof price intentionally uses the market average, not the single best book.
    A single book can be stale, mapped to the wrong side, or attached to the wrong market.
    The best price is retained for diagnostics only.
    """
    best = _safe_float(best_price)
    avg = _safe_float(average_price)
    worst = _safe_float(worst_price)
    prob = _safe_float(normalized_probability)
    market_text = str(market or '').strip().lower()

    candidates = [value for value in [avg, worst, best] if value is not None and value > 1.0]
    if not candidates:
        return OddsAudit(None, None, None, 'fail', 'missing_valid_decimal_price', 0.0, None, None, True)

    selected = avg if avg is not None and avg > 1.0 else candidates[0]
    robust = worst if worst is not None and worst > 1.0 else selected
    ratio = (best / selected) if best is not None and selected and selected > 1.0 else None
    price_range = max(0.0, (best or selected) - (worst or selected))
    implied = round(1.0 / selected, 6) if selected and selected > 1.0 else None

    reasons: list[str] = []
    quarantine = False

    if selected <= 1.01:
        reasons.append('decimal_price_too_low')
        quarantine = True
    if selected >= 3.0:
        reasons.append('average_price_above_high_confidence_cap')
        quarantine = True
    if ratio is not None and ratio >= 1.65:
        reasons.append('best_price_outlier_vs_average')
        quarantine = True
    if best is not None and selected < 1.75 and best >= 3.0:
        reasons.append('favorite_price_flip_suspected')
        quarantine = True
    if price_range >= 0.75:
        reasons.append('wide_book_price_range')
        quarantine = True
    if prob is not None and 0.0 < prob < 1.0 and market_text == 'h2h':
        if selected < 1.50 and prob < 0.50:
            reasons.append('favorite_price_with_underdog_probability')
            quarantine = True
        if selected > 2.50 and prob > 0.60:
            reasons.append('underdog_price_with_favorite_probability')
            quarantine = True

    status = 'quarantine' if quarantine else 'pass'
    reason = '; '.join(reasons) if reasons else 'verified_average_price_used'
    return OddsAudit(
        decimal_price=round(float(selected), 6),
        robust_decimal_price=round(float(robust), 6),
        odds_at_pick=round(float(selected), 6),
        status=status,
        reason=reason,
        price_range_risk=round(float(price_range), 6),
        best_to_average_ratio=None if ratio is None else round(float(ratio), 6),
        implied_probability=implied,
        quarantine=quarantine,
    )
