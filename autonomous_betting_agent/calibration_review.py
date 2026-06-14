from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .learning import clamp_probability

PROBABILITY_COLUMNS = (
    "probability",
    "predicted_probability",
    "pick_probability",
    "favorite_probability",
    "model_probability",
    "market_probability",
    "predictor_score",
    "predictor score",
)

RESULT_COLUMNS = ("result", "outcome", "win_loss", "graded_result", "status")
CLASSIFICATION_COLUMNS = ("classification", "pick_classification", "grade", "signal", "decision")
SPORT_COLUMNS = ("sport", "league", "sport_group")
PRICE_COLUMNS = ("best_price", "price", "odds", "decimal_odds")


@dataclass(frozen=True)
class CalibrationBucket:
    bucket: str
    records: int
    wins: int
    losses: int
    hit_rate: float | None
    avg_predicted_probability: float | None
    calibration_gap: float | None
    recommendation: str
    reason: str


def _clean_key(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _first(row: Mapping[str, Any], keys: Iterable[str]) -> Any:
    lookup = {_clean_key(str(key)): value for key, value in row.items()}
    for key in keys:
        value = lookup.get(_clean_key(key))
        if value not in (None, ""):
            return value
    return None


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text or text.lower() in {"nan", "none", "null", "unknown"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number


def parse_probability(value: Any) -> float | None:
    number = _parse_float(value)
    if number is None:
        return None
    if 1.0 < number <= 100.0:
        number /= 100.0
    if 0.0 < number < 1.0:
        return clamp_probability(number)
    return None


def parse_result(value: Any) -> int | None:
    text = str(value or "").strip().lower()
    if text in {"won", "win", "w", "correct", "hit", "true", "yes", "1"}:
        return 1
    if text in {"lost", "loss", "l", "incorrect", "miss", "false", "no", "0"}:
        return 0
    return None


def _probability_from_row(row: Mapping[str, Any]) -> float | None:
    for key in PROBABILITY_COLUMNS:
        probability = parse_probability(_first(row, (key,)))
        if probability is not None:
            return probability
    price = _parse_float(_first(row, PRICE_COLUMNS))
    if price is not None and price > 1.0:
        return clamp_probability(1.0 / price)
    return None


def _bucket_probability(probability: float | None) -> str:
    if probability is None:
        return "missing"
    lower = int(probability * 10) * 10
    upper = lower + 10
    if lower < 0:
        lower = 0
    if upper > 100:
        upper = 100
    return f"{lower:02d}_{upper:02d}"


def _safe_key(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _summarize_bucket(name: str, rows: list[tuple[float | None, int]], min_records: int, gap_threshold: float) -> CalibrationBucket:
    records = len(rows)
    wins = sum(outcome for _, outcome in rows)
    losses = records - wins
    hit_rate = wins / records if records else None
    probabilities = [probability for probability, _ in rows if probability is not None]
    avg_probability = sum(probabilities) / len(probabilities) if probabilities else None
    gap = None if hit_rate is None or avg_probability is None else hit_rate - avg_probability

    if records < min_records:
        recommendation = "INSUFFICIENT_SAMPLE"
        reason = f"Only {records} graded records; need at least {min_records}."
    elif gap is None:
        recommendation = "NEEDS_PROBABILITY_DATA"
        reason = "No usable predicted probability in this bucket."
    elif gap <= -gap_threshold:
        recommendation = "DOWNWEIGHT"
        reason = "Actual hit rate is meaningfully below predicted probability."
    elif gap >= gap_threshold:
        recommendation = "UPWEIGHT_CAUTION"
        reason = "Actual hit rate is meaningfully above predicted probability; verify no leakage before increasing trust."
    else:
        recommendation = "CALIBRATED_OK"
        reason = "Actual hit rate is close to predicted probability."

    return CalibrationBucket(
        bucket=name,
        records=records,
        wins=wins,
        losses=losses,
        hit_rate=None if hit_rate is None else round(hit_rate, 4),
        avg_predicted_probability=None if avg_probability is None else round(avg_probability, 4),
        calibration_gap=None if gap is None else round(gap, 4),
        recommendation=recommendation,
        reason=reason,
    )


def review_calibration_rows(rows: list[Mapping[str, Any]], *, min_records: int = 10, gap_threshold: float = 0.08) -> dict[str, Any]:
    usable: list[tuple[Mapping[str, Any], float | None, int]] = []
    for row in rows:
        result = parse_result(_first(row, RESULT_COLUMNS))
        if result is None:
            continue
        usable.append((row, _probability_from_row(row), result))

    overall_rows = [(probability, outcome) for _, probability, outcome in usable]
    overall = _summarize_bucket("overall", overall_rows, min_records, gap_threshold)

    by_classification: dict[str, list[tuple[float | None, int]]] = {}
    by_probability_bucket: dict[str, list[tuple[float | None, int]]] = {}
    by_sport: dict[str, list[tuple[float | None, int]]] = {}

    for row, probability, outcome in usable:
        by_classification.setdefault(_safe_key(_first(row, CLASSIFICATION_COLUMNS), "unclassified"), []).append((probability, outcome))
        by_probability_bucket.setdefault(_bucket_probability(probability), []).append((probability, outcome))
        by_sport.setdefault(_safe_key(_first(row, SPORT_COLUMNS), "unknown_sport"), []).append((probability, outcome))

    report = {
        "overall": asdict(overall),
        "by_classification": {key: asdict(_summarize_bucket(key, value, min_records, gap_threshold)) for key, value in sorted(by_classification.items())},
        "by_probability_bucket": {key: asdict(_summarize_bucket(key, value, min_records, gap_threshold)) for key, value in sorted(by_probability_bucket.items())},
        "by_sport": {key: asdict(_summarize_bucket(key, value, min_records, gap_threshold)) for key, value in sorted(by_sport.items())},
        "settings": {
            "min_records": min_records,
            "gap_threshold": gap_threshold,
            "usable_finished_rows": len(usable),
            "ignored_unfinished_or_unusable_rows": len(rows) - len(usable),
        },
    }
    return report


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def review_calibration_csv(path: str | Path, *, min_records: int = 10, gap_threshold: float = 0.08) -> dict[str, Any]:
    return review_calibration_rows(read_csv_rows(path), min_records=min_records, gap_threshold=gap_threshold)


def write_report(report: Mapping[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
