"""Local calibration helpers for graded proof rows."""

from __future__ import annotations

from collections import defaultdict
import math
from typing import Any, Iterable, Mapping

from .grading_rules import grade_from_row

def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _result_value(row: Mapping[str, Any]) -> float | None:
    grade = grade_from_row(row)
    if grade in {"win", "won", "w"}:
        return 1.0
    if grade in {"loss", "lost", "l"}:
        return 0.0
    return None


def row_probability(row: Mapping[str, Any]) -> float | None:
    for key in ("learned_model_probability", "model_probability", "probability"):
        probability = _float(row.get(key))
        if probability is not None:
            return probability
    return None


def normalize_probability(value: float | None) -> float | None:
    if value is None:
        return None
    probability = value / 100.0 if value > 1 else value
    if 0 <= probability <= 1:
        return probability
    return None


def brier_score(rows: Iterable[Mapping[str, Any]]) -> float | None:
    errors: list[float] = []
    for row in rows:
        probability = normalize_probability(row_probability(row))
        result = _result_value(row)
        if probability is None or result is None:
            continue
        errors.append((probability - result) ** 2)
    return sum(errors) / len(errors) if errors else None


def _bucket_index(probability: float, bucket_size: float) -> int:
    bucket_count = max(1, round(1.0 / bucket_size))
    index = int((probability * 100.0) // (bucket_size * 100.0))
    return max(0, min(bucket_count - 1, index))


def calibration_buckets(rows: Iterable[Mapping[str, Any]], bucket_size: float = 0.10) -> list[dict[str, Any]]:
    if not math.isfinite(bucket_size) or not 0 < bucket_size <= 1:
        raise ValueError("bucket_size must be finite and greater than zero, up to one")
    buckets: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for row in rows:
        probability = normalize_probability(row_probability(row))
        result = _result_value(row)
        if probability is None or result is None:
            continue
        bucket = _bucket_index(probability, bucket_size)
        buckets[bucket].append((probability, result))

    output: list[dict[str, Any]] = []
    for bucket, values in sorted(buckets.items()):
        expected = sum(item[0] for item in values) / len(values)
        actual = sum(item[1] for item in values) / len(values)
        output.append(
            {
                "bucket": f"{bucket * bucket_size:.0%}-{(bucket + 1) * bucket_size:.0%}",
                "sample_size": len(values),
                "expected_win_rate": expected,
                "actual_win_rate": actual,
                "gap": actual - expected,
            }
        )
    return output


def odds_band_summary(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    bands = {
        "<1.30": [],
        "1.30-1.59": [],
        "1.60-1.89": [],
        "1.90-2.24": [],
        "2.25-2.99": [],
        "3.00+": [],
    }
    for row in rows:
        price = _float(row.get("decimal_price") or row.get("odds_at_pick"))
        result = _result_value(row)
        if price is None or price <= 1 or result is None:
            continue
        if price < 1.30:
            key = "<1.30"
        elif price < 1.60:
            key = "1.30-1.59"
        elif price < 1.90:
            key = "1.60-1.89"
        elif price < 2.25:
            key = "1.90-2.24"
        elif price < 3.00:
            key = "2.25-2.99"
        else:
            key = "3.00+"
        bands[key].append(result)
    output = []
    for key, values in bands.items():
        output.append({"odds_band": key, "sample_size": len(values), "win_rate": (sum(values) / len(values) if values else None)})
    return output
