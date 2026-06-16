from __future__ import annotations

import builtins
import csv
import json
import math
import os
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


def get_secret(*names: str) -> str:
    """Read a Streamlit secret or environment variable by one of several names."""
    try:
        import streamlit as st
    except Exception:
        st = None  # type: ignore[assignment]
    for name in names:
        if not name:
            continue
        if st is not None:
            try:
                value = str(st.secrets.get(name, "")).strip()
                if value:
                    return value
            except Exception:
                pass
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


builtins.get_secret = get_secret

EPSILON = 1e-6

PROBABILITY_COLUMNS = (
    "final_probability_value",
    "valor_probabilidad_final",
    "final_probability",
    "probabilidad_final",
    "prob_final",
    "calibrated_probability",
    "probabilidad_calibrada",
    "model_probability_clean",
    "model_probability",
    "probabilidad_modelo",
    "predicted_probability",
    "probabilidad_pronosticada",
    "pick_probability",
    "favorite_probability",
    "market_probability_value",
    "market_probability",
    "probabilidad_mercado",
    "prob_mercado",
    "no_vig_probability",
    "confidence_probability",
    "probability",
    "probabilidad",
    "prob",
)

PRICE_COLUMNS = (
    "best_price",
    "mejor_cuota",
    "decimal_price",
    "decimal_odds",
    "sportsbook_odds",
    "average_price",
    "avg_price",
    "odds",
    "cuotas",
    "price",
    "cuota",
)

RESULT_COLUMNS = (
    "result_status",
    "result",
    "resultado",
    "outcome",
    "win_loss",
    "ganada_perdida",
    "graded_result",
    "status",
    "estado",
    "final_result",
    "w_l",
    "wl",
)

PICK_COLUMNS = (
    "pick",
    "prediction",
    "prediccion",
    "pronostico",
    "predicted_side",
    "favored_side",
    "favorite",
    "favorito",
    "selection",
    "seleccion",
)

WINNER_COLUMNS = (
    "winner",
    "ganador",
    "actual_winner",
    "winning_side",
    "final_winner",
)

EVENT_COLUMNS = (
    "event",
    "evento",
    "event_name",
    "game",
    "partido",
    "match",
    "fixture",
)

DEFAULT_L2_CANDIDATES = (0.0025, 0.01, 0.03, 0.08, 0.15)


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

    The calibrator learns a small logistic probability mapping. It also stores
    validation metrics so the app can tell whether calibration improved the data
    or whether the identity mapping was safer.
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
    validation_brier_before: float | None = None
    validation_brier_after: float | None = None
    validation_log_loss_before: float | None = None
    validation_log_loss_after: float | None = None
    calibration_strength: float = 1.0
    training_strategy: str = "logistic_calibration"
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
            validation_brier_before=_optional_float(data.get("validation_brier_before")),
            validation_brier_after=_optional_float(data.get("validation_brier_after")),
            validation_log_loss_before=_optional_float(data.get("validation_log_loss_before")),
            validation_log_loss_after=_optional_float(data.get("validation_log_loss_after")),
            calibration_strength=float(data.get("calibration_strength", 1.0)),
            training_strategy=str(data.get("training_strategy", "logistic_calibration")),
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


def _evaluate_params(rows: Sequence[GradedPrediction], intercept: float, slope: float) -> dict[str, float]:
    calibrator = ProbabilityCalibrator(intercept=intercept, slope=slope, events_trained=len(rows))
    return evaluate(rows, calibrator)


def _fit_params(rows: Sequence[GradedPrediction], *, epochs: int, learning_rate: float, l2: float) -> tuple[float, float]:
    intercept = 0.0
    slope = 1.0
    xs = [max(-6.0, min(6.0, logit(row.probability))) for row in rows]
    ys = [float(row.outcome) for row in rows]
    n = float(len(rows))
    for _ in range(max(1, epochs)):
        grad_intercept = 0.0
        grad_slope = 0.0
        for x, y in zip(xs, ys):
            prediction = sigmoid(intercept + slope * x)
            error = prediction - y
            grad_intercept += error
            grad_slope += error * x
        grad_intercept /= n
        grad_slope = grad_slope / n + l2 * (slope - 1.0)
        intercept -= learning_rate * grad_intercept
        slope -= learning_rate * grad_slope
        slope = max(0.05, min(5.0, slope))
        intercept = max(-5.0, min(5.0, intercept))
    return intercept, slope


def _validation_score(rows: Sequence[GradedPrediction], *, l2: float, epochs: int, learning_rate: float, folds: int) -> dict[str, float]:
    fold_count = max(2, min(folds, len(rows)))
    held_out: list[GradedPrediction] = []
    calibrated_probabilities: list[float] = []
    outcomes: list[int] = []
    for fold in range(fold_count):
        train = [row for index, row in enumerate(rows) if index % fold_count != fold]
        validation = [row for index, row in enumerate(rows) if index % fold_count == fold]
        if not train or not validation:
            continue
        intercept, slope = _fit_params(train, epochs=epochs, learning_rate=learning_rate, l2=l2)
        for row in validation:
            held_out.append(row)
            calibrated_probabilities.append(sigmoid(intercept + slope * logit(row.probability)))
            outcomes.append(row.outcome)
    if not held_out:
        before = evaluate(rows)
        return {"brier_before": before["brier"], "brier_after": before["brier"], "log_loss_before": before["log_loss"], "log_loss_after": before["log_loss"]}
    before_probabilities = [clamp_probability(row.probability) for row in held_out]
    return {
        "brier_before": sum(brier_score(probability, outcome) for probability, outcome in zip(before_probabilities, outcomes)) / len(outcomes),
        "brier_after": sum(brier_score(probability, outcome) for probability, outcome in zip(calibrated_probabilities, outcomes)) / len(outcomes),
        "log_loss_before": sum(log_loss(probability, outcome) for probability, outcome in zip(before_probabilities, outcomes)) / len(outcomes),
        "log_loss_after": sum(log_loss(probability, outcome) for probability, outcome in zip(calibrated_probabilities, outcomes)) / len(outcomes),
    }


def _sample_strength(events: int) -> float:
    if events <= 10:
        return 0.20
    return max(0.25, min(1.0, math.log(events + 1) / math.log(500)))


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

    The training now uses sample-size shrinkage and, when enough rows exist,
    cross-validated guardrails. If calibration does not improve held-out Brier or
    log loss, the system falls back toward the identity mapping instead of
    learning a misleading overfit curve.
    """

    data = list(rows)
    if len(data) < min_events:
        raise ValueError(f"Need at least {min_events} graded predictions to train; got {len(data)}")

    before = evaluate(data)
    l2_values = sorted({float(l2), *DEFAULT_L2_CANDIDATES})
    validation: dict[str, float] | None = None
    best_l2 = float(l2)
    strategy = "sample_shrunk_logistic_calibration"

    if len(data) >= max(20, min_events * 3):
        cv_epochs = max(350, min(1200, epochs // 2))
        folds = min(5, max(2, len(data) // 12))
        scored_candidates: list[tuple[float, float, dict[str, float]]] = []
        for candidate_l2 in l2_values:
            metrics = _validation_score(data, l2=candidate_l2, epochs=cv_epochs, learning_rate=learning_rate, folds=folds)
            ranking_score = metrics["brier_after"] + 0.025 * metrics["log_loss_after"]
            scored_candidates.append((ranking_score, candidate_l2, metrics))
        _rank, best_l2, validation = sorted(scored_candidates, key=lambda item: item[0])[0]
        strategy = f"cross_validated_logistic_calibration_l2={best_l2:g}"

    intercept, slope = _fit_params(data, epochs=epochs, learning_rate=learning_rate, l2=best_l2)
    strength = _sample_strength(len(data))

    if validation is not None:
        brier_worse = validation["brier_after"] > validation["brier_before"] + 0.001
        logloss_worse = validation["log_loss_after"] > validation["log_loss_before"] + 0.003
        if brier_worse and logloss_worse:
            intercept, slope = 0.0, 1.0
            strength = 0.0
            strategy += "_identity_fallback"
        elif brier_worse or logloss_worse:
            strength *= 0.50
            strategy += "_extra_shrink"

    intercept *= strength
    slope = 1.0 + (slope - 1.0) * strength
    slope = max(0.05, min(5.0, slope))
    intercept = max(-5.0, min(5.0, intercept))

    calibrator = ProbabilityCalibrator(
        intercept=intercept,
        slope=slope,
        events_trained=len(data),
        calibration_strength=round(strength, 6),
        training_strategy=strategy,
        trained_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        source=source,
        notes=[
            "Learns probability calibration from graded historical predictions.",
            "Uses sample-size shrinkage to reduce overfitting on small datasets.",
            "Uses held-out validation when enough rows exist and falls back toward identity if calibration hurts validation.",
            "This does not prove betting profitability; use untouched forward tests before making performance claims.",
        ],
    )
    after = evaluate(data, calibrator)
    calibrator.brier_before = before["brier"]
    calibrator.brier_after = after["brier"]
    calibrator.log_loss_before = before["log_loss"]
    calibrator.log_loss_after = after["log_loss"]
    calibrator.accuracy_before = before["accuracy"]
    calibrator.accuracy_after = after["accuracy"]
    if validation is not None:
        calibrator.validation_brier_before = validation["brier_before"]
        calibrator.validation_brier_after = validation["brier_after"]
        calibrator.validation_log_loss_before = validation["log_loss_before"]
        calibrator.validation_log_loss_after = validation["log_loss_after"]
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
                    event_name=_first_text(row, EVENT_COLUMNS) or f"row {line_number}",
                    probability=probability,
                    outcome=outcome,
                    predicted_side=_first_text(row, PICK_COLUMNS),
                    actual_side=_first_text(row, WINNER_COLUMNS),
                )
            )
    return rows


def _clean_key(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower().strip())
    return re.sub(r"_+", "_", text).strip("_")


def _first_text(row: Mapping[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = row.get(_clean_key(key))
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("%", "").replace(",", "")
    if not text or text.lower() in {"none", "null", "nan", "unknown", "n/a", "na", "pending"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _extract_probability(row: Mapping[str, Any]) -> float | None:
    for key in PROBABILITY_COLUMNS:
        number = _parse_float(row.get(_clean_key(key)))
        if number is None:
            continue
        if 1.0 < number <= 100.0:
            number /= 100.0
        if 0.0 < number < 1.0:
            return clamp_probability(number)
    for key in PRICE_COLUMNS:
        number = _parse_float(row.get(_clean_key(key)))
        if number is None or number <= 1.0:
            continue
        return clamp_probability(1.0 / number)
    return None


def _extract_outcome(row: Mapping[str, Any]) -> int | None:
    win_words = {"won", "win", "w", "correct", "hit", "true", "yes", "1", "gano", "ganada", "acierto", "acertado", "victoria"}
    loss_words = {"lost", "loss", "l", "incorrect", "miss", "false", "no", "0", "perdio", "perdida", "fallo", "fallado", "derrota"}
    for key in RESULT_COLUMNS:
        value = _clean_key(row.get(_clean_key(key)))
        if value in win_words:
            return 1
        if value in loss_words:
            return 0
        if any(token in value for token in ("win", "won", "correct", "ganad", "acert")):
            return 1
        if any(token in value for token in ("loss", "lost", "incorrect", "perdid", "fall")):
            return 0
    pick = _clean_key(_first_text(row, PICK_COLUMNS))
    winner = _clean_key(_first_text(row, WINNER_COLUMNS))
    if pick and winner:
        return 1 if pick == winner else 0
    return None
