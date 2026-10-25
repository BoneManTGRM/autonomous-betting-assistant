"""Strict, offline-only learning experiment. No persistence or live callers.

This intentionally does not use learning.py, compact learning memory, the legacy
walk-forward runner, or ensemble selection. Those are not temporal proof inputs.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import random
from typing import Any, Mapping, Sequence

from .accuracy_calibration import result_from_row

SCHEMA_VERSION = "offline-learning-v1"
# Context is audited for future experiments, NOT used by the v1 calibrator.
FEATURE_MAX_AGE_SECONDS = {
    "rest_days": 86400, "travel_distance_km": 86400,
    "injury_count": 21600, "lineup_confirmed": 21600,
    "recent_form": 604800, "opponent_strength": 604800,
    "source_disagreement": 3600, "starter_rating": 86400,
    "bullpen_workload": 86400, "pace": 604800,
    "expected_minutes": 21600, "surface_rating": 604800,
    "weight_class": 604800, "short_notice_days": 86400,
    "weather_wind_kph": 3600,
}
MIN_TRAIN_EVENTS = 50
MIN_HOLDOUT_EVENTS = 100
MIN_HOLDOUT_DAYS = 20
MIN_SUBGROUP_EVENTS = 50


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}: nonempty string required")
    return value.strip()


def _time(value: Any, field: str) -> datetime:
    value = _text(value, field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field}: invalid ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field}: explicit timezone required")
    return parsed.astimezone(timezone.utc)


def _probability(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field}: probability must be numeric, not boolean")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field}: numeric probability required") from exc
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise ValueError(f"{field}: finite probability in [0, 1] required")
    return number


def devig_market(snapshot: Mapping[str, Any], *, event_id: str, market_id: str,
                 selection_id: str, decision_time: datetime) -> float:
    """Proportional de-vig of one complete, same-book decision-time snapshot.

    This is an explicit benchmark convention, not a true-probability claim.
    Arbitrary/incomplete/unsupported markets never get an inferred complement.
    """
    expected = {
        "moneyline_2way": {"home", "away"},
        "moneyline_3way": {"home", "draw", "away"},
        "total_2way": {"over", "under"},
    }.get(snapshot.get("market_type"))
    if expected is None:
        raise ValueError("unsupported market type")
    book = _text(snapshot.get("bookmaker"), "bookmaker")
    snapshot_id = _text(snapshot.get("snapshot_id"), "snapshot_id")
    available = _time(snapshot.get("available_at"), "market available_at")
    if available > decision_time or (decision_time - available).total_seconds() > 300:
        raise ValueError("market snapshot is future or stale")
    if snapshot.get("event_id") != event_id or snapshot.get("market_id") != market_id:
        raise ValueError("market snapshot identity mismatch")
    quotes = snapshot.get("outcomes")
    if not isinstance(quotes, list) or len(quotes) != len(expected):
        raise ValueError("complete market required")
    implied: dict[str, float] = {}
    for quote in quotes:
        if not isinstance(quote, Mapping):
            raise ValueError("invalid outcome quote")
        identity = (quote.get("event_id"), quote.get("market_id"), quote.get("bookmaker"), quote.get("snapshot_id"))
        if identity != (event_id, market_id, book, snapshot_id):
            raise ValueError("mixed book, market, event or snapshot")
        if _time(quote.get("available_at"), "quote available_at") != available:
            raise ValueError("mixed quote times")
        side = quote.get("selection_id")
        if side not in expected or side in implied:
            raise ValueError("duplicate or unexpected market outcome")
        price = quote.get("decimal_odds")
        if isinstance(price, bool):
            raise ValueError("invalid decimal odds")
        try:
            price = float(price)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("invalid decimal odds") from exc
        if not math.isfinite(price) or price <= 1:
            raise ValueError("invalid decimal odds")
        implied[side] = 1 / price
    if set(implied) != expected or selection_id not in implied:
        raise ValueError("complete selected market required")
    return implied[selection_id] / sum(implied.values())


@dataclass(frozen=True)
class Observation:
    event_id: str
    selection_id: str
    market_id: str
    sport: str
    market_type: str
    decision_time: datetime
    event_start: datetime
    label_available: datetime
    raw_probability: float
    baseline_probability: float
    raw_model_version: str
    baseline_model_version: str
    outcome: int
    features: tuple[tuple[str, Any, datetime, str], ...]
    provenance: tuple[str, str, str]
    market_probability: float | None
    market_baseline_reason: str

    @property
    def key(self) -> tuple[str, str, str]:
        return self.event_id, self.market_id, self.selection_id


def validate_observation(row: Mapping[str, Any]) -> Observation:
    event = _text(row.get("event_id"), "event_id")
    selection = _text(row.get("selection_id"), "selection_id")
    market = _text(row.get("market_id"), "market_id")
    decision = _time(row.get("decision_time"), "decision_time")
    recorded = _time(row.get("prediction_recorded_at"), "prediction_recorded_at")
    start = _time(row.get("event_start"), "event_start")
    available = _time(row.get("result_available_at"), "result_available_at")
    verified = _time(row.get("verified_at"), "verified_at")
    if not recorded <= decision < start <= available <= verified:
        raise ValueError("recorded/decision/start/result/verification chronology invalid")
    if row.get("outcome_verified") is not True:
        raise ValueError("outcome_verified must be true with source evidence")
    grade = result_from_row(row)
    if grade not in {"win", "loss"}:
        raise ValueError("exact, unambiguous verified binary final grade required")
    for key in ("raw_probability_available_at", "baseline_probability_available_at"):
        if _time(row.get(key), key) > decision:
            raise ValueError(f"{key}: probability unavailable at decision time")
    features = row.get("features", {})
    if not isinstance(features, Mapping):
        raise ValueError("features must be an availability-stamped object")
    checked = []
    for name, feature in sorted(features.items()):
        if name not in FEATURE_MAX_AGE_SECONDS or not isinstance(feature, Mapping):
            raise ValueError(f"feature not allowlisted: {name}")
        when = _time(feature.get("available_at"), f"{name}.available_at")
        age = (decision - when).total_seconds()
        if age < 0 or age > FEATURE_MAX_AGE_SECONDS[name]:
            raise ValueError(f"feature future or stale: {name}")
        value = feature.get("value")
        if not isinstance(value, (str, int, float, bool)) or (isinstance(value, float) and not math.isfinite(value)):
            raise ValueError(f"feature value missing or invalid: {name}")
        checked.append((name, value, when, _text(feature.get("source"), f"{name}.source")))
    market_probability = None
    market_reason = "not supplied"
    if isinstance(row.get("market_snapshot"), Mapping):
        try:
            if row["market_snapshot"].get("market_type") != row.get("market_type"):
                raise ValueError("market type mismatch")
            market_probability = devig_market(row["market_snapshot"], event_id=event, market_id=market,
                                             selection_id=selection, decision_time=decision)
            market_reason = "complete same-book proportional de-vig"
        except ValueError as exc:
            market_reason = str(exc)
    elif row.get("market_snapshot") is not None:
        market_reason = "market snapshot must be an object"
    return Observation(
        event, selection, market, _text(row.get("sport"), "sport"),
        _text(row.get("market_type"), "market_type"), decision, start, verified,
        _probability(row.get("raw_model_probability"), "raw_model_probability"),
        _probability(row.get("baseline_probability"), "baseline_probability"),
        _text(row.get("raw_model_version"), "raw_model_version"),
        _text(row.get("baseline_model_version"), "baseline_model_version"), int(grade == "win"),
        tuple(checked), tuple(_text(row.get(name), name) for name in ("event_source", "prediction_source", "result_source")),
        market_probability, market_reason,
    )


def decision_features(row: Observation) -> dict[str, Any]:
    """A label-free, allowlisted decision view; never copy the uploaded record."""
    return {"raw_model_probability": row.raw_probability,
            "context": {name: value for name, value, _when, _source in row.features}}


def _clip(p: float) -> float:
    return max(1e-12, min(1 - 1e-12, p))


def _predict(p: float, intercept: float) -> float:
    p = _clip(p)
    z = math.log(p / (1 - p)) + intercept
    return 1 / (1 + math.exp(-z))


def _fit_intercept(rows: Sequence[Observation]) -> float:
    """Fixed regularized intercept-only logistic calibration; event-balanced.

    No model search, feature fitting, development tuning, or holdout feedback.
    """
    counts = Counter(row.event_id for row in rows)
    intercept = 0.0
    for _ in range(80):
        gradient = intercept  # fixed L2 strength 1.0
        curvature = 1.0
        for row in rows:
            p = _predict(row.raw_probability, intercept)
            weight = 1 / counts[row.event_id]
            gradient += weight * (p - row.outcome)
            curvature += weight * p * (1 - p)
        new = max(-2.0, min(2.0, intercept - gradient / curvature))
        if abs(new - intercept) < 1e-10:
            return new
        intercept = new
    return intercept


def _metrics(rows: Sequence[Observation], probabilities: Sequence[float]) -> dict[str, Any] | None:
    if not rows:
        return None
    counts = Counter(row.event_id for row in rows)
    event_count = len(counts)
    brier = logloss = bias = 0.0
    bins: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for row, p in zip(rows, probabilities):
        w = 1 / counts[row.event_id]
        brier += w * (p - row.outcome) ** 2
        q = _clip(p)
        logloss += w * (-math.log(q) if row.outcome else -math.log1p(-q))
        bias += w * (p - row.outcome)
        bucket = bins[min(9, int(p * 10))]
        bucket[0] += w
        bucket[1] += w * p
        bucket[2] += w * row.outcome
    ece = sum(abs(predicted - actual) for weight, predicted, actual in bins.values()) / event_count
    return {"rows": len(rows), "unique_events": event_count, "brier": brier / event_count,
            "log_loss": logloss / event_count, "ece_10_bins": ece,
            "calibration_bias": bias / event_count,
            "reliability_bins": [{"lower": index / 10, "event_weight": values[0],
                                  "mean_probability": values[1] / values[0], "observed_rate": values[2] / values[0]}
                                 for index, values in sorted(bins.items())]}


def _paired_uncertainty(rows: Sequence[Observation], candidate: Sequence[float], baseline: Sequence[float]) -> dict[str, Any]:
    # First aggregate picks by event, then resample UTC decision-day blocks.
    events: dict[str, list[tuple[float, float, str]]] = defaultdict(list)
    for row, p, b in zip(rows, candidate, baseline):
        y = row.outcome
        loss = lambda q: -math.log(_clip(q)) if y else -math.log1p(-_clip(q))
        events[row.event_id].append(((p - y) ** 2 - (b - y) ** 2, loss(p) - loss(b), row.decision_time.date().isoformat()))
    blocks: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for values in events.values():
        blocks[min(value[2] for value in values)].append((sum(value[0] for value in values) / len(values), sum(value[1] for value in values) / len(values)))
    groups = list(blocks.values())
    if not groups:
        return {"method": "UTC decision-day block bootstrap", "blocks": 0, "brier_delta_ci95": None, "log_loss_delta_ci95": None}
    rng = random.Random(1729)
    samples = [[], []]
    for _ in range(500):
        drawn = [value for _ in groups for value in rng.choice(groups)]
        for metric in range(2):
            samples[metric].append(sum(value[metric] for value in drawn) / len(drawn))
    intervals = []
    for values in samples:
        values.sort()
        intervals.append([values[12], values[487]])
    return {"method": "UTC decision-day block bootstrap; 500 replicates; seed 1729",
            "blocks": len(groups), "brier_delta_ci95": intervals[0], "log_loss_delta_ci95": intervals[1],
            "limitation": "Same-day clustering is preserved; longer temporal or team dependence is not fully modeled."}


def _comparison(rows: Sequence[Observation], intercept: float) -> dict[str, Any]:
    candidate = [_predict(row.raw_probability, intercept) for row in rows]
    baseline = [row.baseline_probability for row in rows]
    before = _metrics(rows, baseline)
    after = _metrics(rows, candidate)
    market_rows = [row for row in rows if row.market_probability is not None]
    market_metrics = _metrics(market_rows, [row.market_probability for row in market_rows])
    return {"baseline": before, "candidate": after,
            "delta": None if not before else {key: after[key] - before[key] for key in ("brier", "log_loss", "ece_10_bins")},
            "uncertainty": _paired_uncertainty(rows, candidate, baseline),
            "market_baseline": {"coverage_rows": len(market_rows), "total_rows": len(rows), "metrics": market_metrics,
                                "candidate_on_same_rows": _metrics(market_rows, [_predict(row.raw_probability, intercept) for row in market_rows]),
                                "missing_reasons": dict(Counter(row.market_baseline_reason for row in rows if row.market_probability is None))},
            "predictions": [{"event_id": row.event_id, "market_id": row.market_id, "selection_id": row.selection_id,
                             "probability": p, "baseline_probability": b} for row, p, b in zip(rows, candidate, baseline)]}


def _digest(rows: Sequence[Observation]) -> str:
    payload = json.dumps([asdict(row) for row in rows], sort_keys=True, separators=(",", ":"),
                         default=lambda value: value.isoformat(), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_offline_validation(rows: Sequence[Mapping[str, Any]], *, train_before: str,
                           holdout_from: str, evaluation_as_of: str) -> dict[str, Any]:
    """One frozen experiment. Final holdout is never used to fit or tune.

    The caller must reserve this holdout before looking at outcomes. This pure
    function cannot certify external provenance or prevent repeated reuse.
    """
    train_cutoff = _time(train_before, "train_before")
    holdout_cutoff = _time(holdout_from, "holdout_from")
    as_of = _time(evaluation_as_of, "evaluation_as_of")
    if not train_cutoff < holdout_cutoff < as_of:
        raise ValueError("require train_before < holdout_from < evaluation_as_of")
    rejected: list[dict[str, Any]] = []
    invalid_events: set[str] = set()
    grouped: dict[str, list[tuple[int, Observation]]] = defaultdict(list)
    for index, source in enumerate(rows):
        try:
            if not isinstance(source, Mapping):
                raise ValueError("record must be an object")
            row = validate_observation(source)
            if row.decision_time >= as_of or row.label_available > as_of:
                raise ValueError("decision or verified result unavailable at evaluation cutoff")
            grouped[row.event_id].append((index, row))
        except (ValueError, TypeError) as exc:
            rejected.append({"row": index, "reason": str(exc)})
            if isinstance(source, Mapping) and isinstance(source.get("event_id"), str):
                invalid_events.add(source["event_id"].strip())
    partitions: dict[str, list[Observation]] = {"train": [], "development": [], "holdout": []}
    duplicate_count = 0
    for event, indexed in sorted(grouped.items()):
        unique: dict[tuple[str, str, str], Observation] = {}
        conflict = False
        group_duplicates = 0
        for _index, row in indexed:
            if row.key in unique:
                if row != unique[row.key]:
                    conflict = True
                else:
                    group_duplicates += 1
            unique[row.key] = row
        destinations = {"train" if row.decision_time < train_cutoff else "development" if row.decision_time < holdout_cutoff else "holdout" for row in unique.values()}
        market_types: dict[str, set[str]] = defaultdict(set)
        for row in unique.values():
            market_types[row.market_id].add(row.market_type)
        if event in invalid_events:
            reason = "another record for this event failed admission; quarantine entire event"
        elif conflict or len(destinations) != 1 or len({(row.event_start, row.sport) for row in unique.values()}) != 1 or any(len(types) != 1 for types in market_types.values()):
            reason = "conflicting duplicate/event identity or event crosses split boundary"
        elif destinations == {"train"} and any(row.label_available >= train_cutoff for row in unique.values()):
            reason = "training label not verified before training cutoff"
        else:
            reason = ""
        if reason:
            rejected.extend({"row": index, "event_id": event, "reason": reason} for index, _row in indexed)
        else:
            partitions[next(iter(destinations))].extend(unique.values())
            duplicate_count += group_duplicates
    for partition in partitions.values():
        partition.sort(key=lambda row: (row.decision_time, row.key))
    train, development, holdout = (partitions[key] for key in ("train", "development", "holdout"))
    admitted = train + development + holdout
    actions: list[str] = []
    if len({row.event_id for row in train}) < MIN_TRAIN_EVENTS or {row.outcome for row in train} != {0, 1}:
        actions.append("Need at least 50 verified training events with both outcomes.")
    if len({row.raw_model_version for row in admitted}) > 1 or len({row.baseline_model_version for row in admitted}) > 1:
        actions.append("Freeze one raw model version and one incumbent baseline version per experiment.")
    # Never fit on insufficient or mixed-version data; report identity instead.
    fitted = not actions
    intercept = _fit_intercept(train) if fitted else 0.0
    comparison = _comparison(holdout, intercept)
    if len({row.event_id for row in holdout}) < MIN_HOLDOUT_EVENTS or {row.outcome for row in holdout} != {0, 1}:
        actions.append("Need at least 100 untouched holdout events with both outcomes.")
    if comparison["uncertainty"]["blocks"] < MIN_HOLDOUT_DAYS:
        actions.append("Need at least 20 holdout decision-day blocks for uncertainty review.")
    if rejected:
        actions.append("Resolve rejected records and selection bias before review; original records remain untouched.")
    delta = comparison["delta"]
    intervals = comparison["uncertainty"]
    if not delta or any(intervals[key] is None or intervals[key][1] >= 0 for key in ("brier_delta_ci95", "log_loss_delta_ci95")):
        actions.append("Both paired Brier and log-loss improvements must have upper 95% block-bootstrap bounds below zero.")
    if delta and delta["ece_10_bins"] > 0.005:
        actions.append("Holdout calibration error deteriorated by more than 0.005.")
    subgroups: dict[str, Any] = {}
    for key in sorted({(row.sport, row.market_type) for row in holdout}):
        subset = [row for row in holdout if (row.sport, row.market_type) == key]
        detail = _comparison(subset, intercept)
        enough = len({row.event_id for row in subset}) >= MIN_SUBGROUP_EVENTS and {row.outcome for row in subset} == {0, 1}
        acceptable = enough and all(detail["delta"][metric] <= 0 for metric in ("brier", "log_loss"))
        subgroups["|".join(key)] = {"unique_events": len({row.event_id for row in subset}), "delta": detail["delta"],
                                    "status": "NO_DETECTED_REGRESSION" if acceptable else "INSUFFICIENT_OR_REGRESSED"}
        if not acceptable:
            actions.append(f"Subgroup {key[0]} / {key[1]} needs 50 diverse events and non-worsening Brier/log loss.")
    return {
        "schema_version": SCHEMA_VERSION, "mode": "OFFLINE_OBSERVATION_ONLY",
        "status": "INSUFFICIENT_EVIDENCE" if actions else "REVIEW_CANDIDATE",
        "live_mutation_allowed": False, "promotion_allowed": False, "predictive_gain_proven": False,
        "cutoffs": {"train_before": train_before, "holdout_from": holdout_from, "evaluation_as_of": evaluation_as_of},
        "partition_sha256": {key: _digest(value) for key, value in partitions.items()},
        "candidate": {"type": "fixed event-balanced L2 intercept-only logistic calibration", "fitted": fitted,
                      "intercept": intercept, "context_features_used_for_fitting": []},
        "coverage": {"input_rows": len(rows), "admitted_unique_rows": len(admitted), "duplicate_rows_removed": duplicate_count,
                     "rejected_rows": len(rejected), "eligibility_fraction": len(admitted) / (len(rows) - duplicate_count) if len(rows) > duplicate_count else 0.0,
                     "meaning": "Data eligibility only; not betting selection or wager coverage."},
        "partitions": {key: {"rows": len(value), "unique_events": len({row.event_id for row in value})} for key, value in partitions.items()},
        "rejected": rejected, "development": _comparison(development, intercept), "holdout": comparison,
        "subgroups": subgroups, "required_actions": actions,
        "limitations": ["Synthetic success proves implementation correctness, not predictive gain.",
                        "Provenance references and an untouched holdout require independent verification; assertions are not proof.",
                        "Do not reuse this holdout for model selection; register all attempted variants and reserve a fresh final test.",
                        "Legacy learning.py and compact learning-memory rows are not accepted temporal-validation pipelines.",
                        "Context features are availability-audited only; the v1 calibrator does not learn sport-specific effects.",
                        "Existing Phase 3 observation-only and readiness gates remain unchanged."]}
