from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

PROBABILITY_COLUMNS = (
    "calibrated_probability",
    "model_probability",
    "probability",
    "confidence_probability",
    "prop_blended_probability",
    "prop_model_probability",
)
RAW_PROBABILITY_COLUMNS = (
    "raw_model_probability",
    "model_probability",
    "probability",
    "confidence_probability",
    "prop_blended_probability",
    "prop_model_probability",
)
CALIBRATED_PROBABILITY_COLUMNS = ("calibrated_probability",)
RESULT_COLUMNS = ("result", "outcome", "win_loss", "graded_result", "status")
SPORT_COLUMNS = ("sport", "league", "competition")
MARKET_COLUMNS = ("market", "market_key", "prop_type", "bet_type")


@dataclass(frozen=True)
class CalibrationBucket:
    bucket_floor: float
    bucket_ceiling: float
    samples: int
    wins: int
    losses: int
    observed_win_rate: float | None
    calibrated_probability: float


@dataclass(frozen=True)
class CalibrationModel:
    global_samples: int
    global_wins: int
    global_losses: int
    global_win_rate: float
    shrinkage_strength: float
    bucket_size: float
    min_bucket_samples: int
    buckets: dict[str, CalibrationBucket]


@dataclass(frozen=True)
class CalibrationReport:
    raw_rows: int
    usable_rows: int
    calibrated_rows: int
    global_win_rate: float
    average_raw_probability: float | None
    average_calibrated_probability: float | None
    bucket_count: int
    raw_brier_score: float | None
    calibrated_brier_score: float | None
    brier_improvement: float | None
    raw_expected_calibration_error: float | None
    calibrated_expected_calibration_error: float | None
    expected_calibration_error_improvement: float | None
    output_csv: str | None
    notes: list[str]


def _clean_key(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _lookup(row: Mapping[str, Any]) -> dict[str, Any]:
    return {_clean_key(str(key)): value for key, value in row.items()}


def _first(row: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    lookup = _lookup(row)
    for key in keys:
        value = lookup.get(_clean_key(key))
        if value not in (None, ""):
            return value
    return ""


def _float(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "").replace("%", "")
    if not text or text.lower() in {"none", "null", "nan", "unknown"}:
        return None
    try:
        value_float = float(text)
    except ValueError:
        return None
    if not math.isfinite(value_float):
        return None
    return value_float


def parse_probability(value: Any) -> float | None:
    number = _float(value)
    if number is None:
        return None
    if number > 1.0:
        number = number / 100.0
    if number < 0 or number > 1:
        return None
    return number


def parse_result(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"won", "win", "w", "1", "true", "correct"}:
        return "win"
    if text in {"lost", "loss", "l", "0", "false", "incorrect"}:
        return "loss"
    if text in {"push", "void", "tie", "draw", "cancelled", "canceled"}:
        return "push"
    return None


def raw_probability(row: Mapping[str, Any]) -> float | None:
    return parse_probability(_first(row, PROBABILITY_COLUMNS))


def probability_from_columns(row: Mapping[str, Any], columns: tuple[str, ...]) -> float | None:
    return parse_probability(_first(row, columns))


def _binary_result(row: Mapping[str, Any]) -> int | None:
    result = parse_result(_first(row, RESULT_COLUMNS))
    if result == "win":
        return 1
    if result == "loss":
        return 0
    return None


def brier_score(rows: list[Mapping[str, Any]], probability_columns: tuple[str, ...] = PROBABILITY_COLUMNS) -> float | None:
    errors: list[float] = []
    for row in rows:
        result = _binary_result(row)
        probability = probability_from_columns(row, probability_columns)
        if result is None or probability is None:
            continue
        errors.append((probability - result) ** 2)
    if not errors:
        return None
    return round(sum(errors) / len(errors), 6)


def expected_calibration_error(rows: list[Mapping[str, Any]], probability_columns: tuple[str, ...] = PROBABILITY_COLUMNS, *, bucket_size: float = 0.05) -> float | None:
    buckets: dict[str, dict[str, float]] = {}
    total = 0
    for row in rows:
        result = _binary_result(row)
        probability = probability_from_columns(row, probability_columns)
        if result is None or probability is None:
            continue
        key = _bucket_key(probability, bucket_size)
        stats = buckets.setdefault(key, {"count": 0.0, "probability_sum": 0.0, "win_sum": 0.0})
        stats["count"] += 1.0
        stats["probability_sum"] += probability
        stats["win_sum"] += float(result)
        total += 1
    if total == 0:
        return None
    error = 0.0
    for stats in buckets.values():
        confidence = stats["probability_sum"] / stats["count"]
        accuracy = stats["win_sum"] / stats["count"]
        error += (stats["count"] / total) * abs(confidence - accuracy)
    return round(error, 6)


def _improvement(before: float | None, after: float | None) -> float | None:
    if before is None or after is None:
        return None
    return round(before - after, 6)


def _bucket_key(probability: float, bucket_size: float) -> str:
    # Add a tiny epsilon so exact-looking values such as 0.70 do not fall into
    # the lower bucket because of binary floating point representation.
    bucket_count = max(1, int(round(1.0 / bucket_size)))
    index = int(math.floor((probability + 1e-12) / bucket_size))
    index = max(0, min(bucket_count - 1, index))
    floor = round(index * bucket_size, 10)
    ceiling = round(min(1.0, floor + bucket_size), 10)
    return f"{floor:.2f}-{ceiling:.2f}"


def _bucket_bounds(key: str) -> tuple[float, float]:
    left, right = key.split("-")
    return float(left), float(right)


def fit_calibration_model(
    rows: list[Mapping[str, Any]],
    *,
    bucket_size: float = 0.05,
    min_bucket_samples: int = 20,
    shrinkage_strength: float = 25.0,
) -> CalibrationModel:
    if bucket_size <= 0 or bucket_size > 0.5:
        raise ValueError("bucket_size must be > 0 and <= 0.5")
    bucket_stats: dict[str, dict[str, int]] = {}
    global_wins = 0
    global_losses = 0
    for row in rows:
        probability = raw_probability(row)
        result = parse_result(_first(row, RESULT_COLUMNS))
        if probability is None or result not in {"win", "loss"}:
            continue
        key = _bucket_key(probability, bucket_size)
        stats = bucket_stats.setdefault(key, {"wins": 0, "losses": 0})
        if result == "win":
            stats["wins"] += 1
            global_wins += 1
        else:
            stats["losses"] += 1
            global_losses += 1

    global_samples = global_wins + global_losses
    global_rate = global_wins / global_samples if global_samples else 0.5
    buckets: dict[str, CalibrationBucket] = {}
    for key, stats in bucket_stats.items():
        wins = stats["wins"]
        losses = stats["losses"]
        samples = wins + losses
        observed = wins / samples if samples else None
        if samples >= min_bucket_samples and observed is not None:
            calibrated = ((observed * samples) + (global_rate * shrinkage_strength)) / (samples + shrinkage_strength)
        else:
            raw_midpoint = sum(_bucket_bounds(key)) / 2.0
            calibrated = ((raw_midpoint * samples) + (global_rate * shrinkage_strength)) / (samples + shrinkage_strength)
        floor, ceiling = _bucket_bounds(key)
        buckets[key] = CalibrationBucket(
            bucket_floor=floor,
            bucket_ceiling=ceiling,
            samples=samples,
            wins=wins,
            losses=losses,
            observed_win_rate=None if observed is None else round(observed, 6),
            calibrated_probability=round(max(0.01, min(0.99, calibrated)), 6),
        )

    return CalibrationModel(
        global_samples=global_samples,
        global_wins=global_wins,
        global_losses=global_losses,
        global_win_rate=round(global_rate, 6),
        shrinkage_strength=shrinkage_strength,
        bucket_size=bucket_size,
        min_bucket_samples=min_bucket_samples,
        buckets=buckets,
    )


def _scope_key(row: Mapping[str, Any]) -> str:
    sport = str(_first(row, SPORT_COLUMNS)).strip().lower()
    market = str(_first(row, MARKET_COLUMNS)).strip().lower()
    return f"{sport}|{market}"


def fit_scoped_calibration_models(
    rows: list[Mapping[str, Any]],
    *,
    bucket_size: float = 0.05,
    min_bucket_samples: int = 20,
    shrinkage_strength: float = 25.0,
    min_scope_samples: int = 50,
) -> dict[str, CalibrationModel]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_scope_key(row), []).append(row)
    models = {"__global__": fit_calibration_model(rows, bucket_size=bucket_size, min_bucket_samples=min_bucket_samples, shrinkage_strength=shrinkage_strength)}
    for key, group_rows in grouped.items():
        usable = [row for row in group_rows if raw_probability(row) is not None and parse_result(_first(row, RESULT_COLUMNS)) in {"win", "loss"}]
        if len(usable) >= min_scope_samples:
            models[key] = fit_calibration_model(group_rows, bucket_size=bucket_size, min_bucket_samples=min_bucket_samples, shrinkage_strength=shrinkage_strength)
    return models


def calibrate_probability(probability: float | None, model: CalibrationModel) -> tuple[float | None, str, str]:
    if probability is None:
        return None, "missing_probability", ""
    key = _bucket_key(probability, model.bucket_size)
    bucket = model.buckets.get(key)
    if bucket is None:
        return round(((probability * model.global_samples) + (model.global_win_rate * model.shrinkage_strength)) / max(1.0, model.global_samples + model.shrinkage_strength), 6), "global_fallback", key
    if bucket.samples < model.min_bucket_samples:
        return bucket.calibrated_probability, "low_sample_bucket_shrunk", key
    return bucket.calibrated_probability, "bucket_observed_shrunk", key


def apply_calibration(rows: list[Mapping[str, Any]], history_rows: list[Mapping[str, Any]], *, bucket_size: float = 0.05, min_bucket_samples: int = 20, shrinkage_strength: float = 25.0, min_scope_samples: int = 50) -> tuple[list[dict[str, Any]], CalibrationReport]:
    models = fit_scoped_calibration_models(history_rows, bucket_size=bucket_size, min_bucket_samples=min_bucket_samples, shrinkage_strength=shrinkage_strength, min_scope_samples=min_scope_samples)
    global_model = models["__global__"]
    output: list[dict[str, Any]] = []
    raw_values: list[float] = []
    calibrated_values: list[float] = []
    for row in rows:
        out = dict(row)
        probability = raw_probability(row)
        if probability is not None:
            raw_values.append(probability)
        model = models.get(_scope_key(row), global_model)
        calibrated, reason, bucket = calibrate_probability(probability, model)
        out["raw_model_probability"] = "" if probability is None else str(round(probability, 6))
        out["calibrated_probability"] = "" if calibrated is None else str(calibrated)
        out["calibration_reason"] = reason
        out["calibration_bucket"] = bucket
        out["calibration_scope"] = _scope_key(row) if _scope_key(row) in models else "__global__"
        out["calibration_samples"] = str(model.global_samples)
        if calibrated is not None:
            calibrated_values.append(calibrated)
        output.append(out)

    raw_brier = brier_score(output, RAW_PROBABILITY_COLUMNS)
    calibrated_brier = brier_score(output, CALIBRATED_PROBABILITY_COLUMNS)
    raw_ece = expected_calibration_error(output, RAW_PROBABILITY_COLUMNS, bucket_size=bucket_size)
    calibrated_ece = expected_calibration_error(output, CALIBRATED_PROBABILITY_COLUMNS, bucket_size=bucket_size)
    report = CalibrationReport(
        raw_rows=len(rows),
        usable_rows=sum(1 for row in history_rows if raw_probability(row) is not None and parse_result(_first(row, RESULT_COLUMNS)) in {"win", "loss"}),
        calibrated_rows=sum(1 for row in output if row.get("calibrated_probability") not in (None, "")),
        global_win_rate=global_model.global_win_rate,
        average_raw_probability=None if not raw_values else round(sum(raw_values) / len(raw_values), 6),
        average_calibrated_probability=None if not calibrated_values else round(sum(calibrated_values) / len(calibrated_values), 6),
        bucket_count=len(global_model.buckets),
        raw_brier_score=raw_brier,
        calibrated_brier_score=calibrated_brier,
        brier_improvement=_improvement(raw_brier, calibrated_brier),
        raw_expected_calibration_error=raw_ece,
        calibrated_expected_calibration_error=calibrated_ece,
        expected_calibration_error_improvement=_improvement(raw_ece, calibrated_ece),
        output_csv=None,
        notes=[
            "Calibration uses historical win/loss outcomes and shrinks bucket rates toward the global win rate.",
            "Scoped sport/market calibration is used only when enough historical samples exist; otherwise global calibration is used.",
            "Brier score and expected calibration error are reported when rows being calibrated already contain graded results.",
        ],
    )
    return output, report


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(rows: list[Mapping[str, Any]], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_report(report: CalibrationReport, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
