from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

EPSILON = 1e-6

PROBABILITY_COLUMNS = (
    "probability",
    "predicted_probability",
    "pick_probability",
    "favorite_probability",
    "model_probability",
    "market_probability",
    "no_vig_probability",
    "confidence_probability",
)

PRICE_COLUMNS = (
    "price",
    "best_price",
    "average_price",
    "avg_price",
    "odds",
    "decimal_odds",
)

RESULT_COLUMNS = (
    "result",
    "outcome",
    "win_loss",
    "graded_result",
    "status",
)

PICK_COLUMNS = (
    "pick",
    "prediction",
    "predicted_side",
    "favored_side",
    "favorite",
)

WINNER_COLUMNS = (
    "winner",
    "actual_winner",
    "winning_side",
    "final_winner",
)


@dataclass(frozen=True)
class GradedPrediction:
    event_name: str
    probability: float
    outcome: int
    predicted_side: str = ""
    actual_side: str = ""


@dataclass
class ProbabilityCalibrator:
    """Learns how much to trust raw model or market probabilities.

    The calibrator learns a logistic mapping from an original probability to an
    adjusted probability using graded historical predictions. It is intentionally
    small and auditable: prediction -> final result -> fit calibration -> save
    state -> apply to future predictions.
    """

    intercept: float = 0.0
    slope: float = 1.0
    events_trained: int = 0
    brier_before: float | None = None
    brier_after: float | None = None
    log_loss_before: float | None = None
    log_loss_after: float | None = None
    accuracy_before: float | None = None
    accuracy_after: float | None = None
    trained_at_utc: str = ""
    source: str = ""
    notes: list[str] = field(default_factory=list)

    def apply(self, probability: float) -> float:
        probability = clamp_probability(probability)
        return sigmoid(self.intercept + self.slope * logit(probability))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProbabilityCalibrator":
        return cls(
            intercept=float(data.get("intercept", 0.0)),
            slope=float(data.get("slope", 1.0)),
            events_trained=int(data.get("events_trained", 0)),
            brier_before=_optional_float(data.get("brier_before")),
            brier_after=_optional_float(data.get("brier_after")),
            log_loss_before=_optional_float(data.get("log_loss_before")),
            log_loss_after=_optional_float(data.get("log_loss_after")),
            accuracy_before=_optional_float(data.get("accuracy_before")),
            accuracy_after=_optional_float(data.get("accuracy_after")),
            trained_at_utc=str(data.get("trained_at_utc", "")),
            source=str(data.get("source", "")),
            notes=[str(item) for item in data.get("notes", [])],
        )

    @classmethod
    def load(cls, path: str | Path) -> "ProbabilityCalibrator":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def clamp_probability(value: float) -> float:
    return max(EPSILON, min(1.0 - EPSILON, float(value)))


def logit(probability: float) -> float:
    probability = clamp_probability(probability)
    return math.log(probability / (1.0 - probability))


def sigmoid(value: float) -> float:
    if value >= 0.0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def brier_score(probability: float, outcome: int) -> float:
    return (clamp_probability(probability) - float(outcome)) ** 2


def log_loss(probability: float, outcome: int) -> float:
    probability = clamp_probability(probability)
    if outcome:
        return -math.log(probability)
    return -math.log(1.0 - probability)


def evaluate(rows: Sequence[GradedPrediction], calibrator: ProbabilityCalibrator | None = None) -> dict[str, float]:
    if not rows:
        raise ValueError("Evaluation requires at least one graded prediction")
    probabilities = [calibrator.apply(row.probability) if calibrator else clamp_probability(row.probability) for row in rows]
    outcomes = [row.outcome for row in rows]
    return {
        "events": float(len(rows)),
        "brier": sum(brier_score(probability, outcome) for probability, outcome in zip(probabilities, outcomes)) / len(rows),
        "log_loss": sum(log_loss(probability, outcome) for probability, outcome in zip(probabilities, outcomes)) / len(rows),
        "accuracy": sum(1.0 if (probability >= 0.5) == bool(outcome) else 0.0 for probability, outcome in zip(probabilities, outcomes)) / len(rows),
    }


def fit_probability_calibrator(
    rows: Sequence[GradedPrediction],
    *,
    epochs: int = 2500,
    learning_rate: float = 0.05,
    l2: float = 0.01,
    min_events: int = 5,
    source: str = "",
) -> ProbabilityCalibrator:
    """Fit a probability calibrator from graded historical predictions.

    This is real online-useful learning, but it is deliberately limited: it learns
    calibration, not team skill. It should be retrained as more results are graded.
    """

    data = list(rows)
    if len(data) < min_events:
        raise ValueError(f"Need at least {min_events} graded predictions to train; got {len(data)}")

    intercept = 0.0
    slope = 1.0
    xs = [max(-6.0, min(6.0, logit(row.probability))) for row in data]
    ys = [float(row.outcome) for row in data]

    for _ in range(max(1, epochs)):
        grad_intercept = 0.0
        grad_slope = 0.0
        for x, y in zip(xs, ys):
            prediction = sigmoid(intercept + slope * x)
            error = prediction - y
            grad_intercept += error
            grad_slope += error * x
        n = float(len(data))
        grad_intercept /= n
        grad_slope = grad_slope / n + l2 * (slope - 1.0)
        intercept -= learning_rate * grad_intercept
        slope -= learning_rate * grad_slope
        slope = max(0.05, min(5.0, slope))
        intercept = max(-5.0, min(5.0, intercept))

    calibrator = ProbabilityCalibrator(
        intercept=intercept,
        slope=slope,
        events_trained=len(data),
        trained_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        source=source,
        notes=[
            "Learns probability calibration from graded historical predictions.",
            "This does not prove betting profitability; use untouched forward tests before making performance claims.",
        ],
    )
    before = evaluate(data)
    after = evaluate(data, calibrator)
    calibrator.brier_before = before["brier"]
    calibrator.brier_after = after["brier"]
    calibrator.log_loss_before = before["log_loss"]
    calibrator.log_loss_after = after["log_loss"]
    calibrator.accuracy_before = before["accuracy"]
    calibrator.accuracy_after = after["accuracy"]
    return calibrator


def parse_graded_csv(path: str | Path) -> list[GradedPrediction]:
    rows: list[GradedPrediction] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for line_number, raw_row in enumerate(reader, start=2):
            row = {_clean_key(key): value for key, value in raw_row.items() if key is not None}
            probability = _extract_probability(row)
            outcome = _extract_outcome(row)
            if probability is None or outcome is None:
                continue
            rows.append(
                GradedPrediction(
                    event_name=_first_text(row, ("event", "event_name", "game", "match", "fixture")) or f"row {line_number}",
                    probability=probability,
                    outcome=outcome,
                    predicted_side=_first_text(row, PICK_COLUMNS),
                    actual_side=_first_text(row, WINNER_COLUMNS),
                )
            )
    return rows


def _clean_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _first_text(row: Mapping[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = row.get(_clean_key(key))
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("%", "")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number


def _extract_probability(row: Mapping[str, Any]) -> float | None:
    for key in PROBABILITY_COLUMNS:
        number = _parse_float(row.get(key))
        if number is None:
            continue
        if 1.0 < number <= 100.0:
            number /= 100.0
        if 0.0 < number < 1.0:
            return clamp_probability(number)
    for key in PRICE_COLUMNS:
        number = _parse_float(row.get(key))
        if number is None or number <= 1.0:
            continue
        return clamp_probability(1.0 / number)
    return None


def _extract_outcome(row: Mapping[str, Any]) -> int | None:
    for key in RESULT_COLUMNS:
        value = str(row.get(key, "")).strip().lower()
        if value in {"won", "win", "w", "correct", "hit", "true", "yes", "1"}:
            return 1
        if value in {"lost", "loss", "l", "incorrect", "miss", "false", "no", "0"}:
            return 0
    pick = _first_text(row, PICK_COLUMNS).strip().lower()
    winner = _first_text(row, WINNER_COLUMNS).strip().lower()
    if pick and winner:
        return 1 if pick == winner else 0
    return None
