from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

PROBABILITY_COLUMNS = ("calibrated_probability", "model_probability", "probability", "prop_blended_probability", "prop_model_probability")
EDGE_COLUMNS = ("edge", "expected_value", "ev", "prop_implied_edge")
DATA_QUALITY_COLUMNS = ("data_quality", "prop_data_quality", "feature_data_quality")
BOOKMAKER_COLUMNS = ("bookmaker_count", "book_count", "books")
CLV_COLUMNS = ("closing_line_value", "clv", "clv_history_score")
MARKET_SUPPORT_COLUMNS = ("market_support_score", "line_movement_strength", "profile_accuracy_score")
NEGATIVE_FLAG_COLUMNS = ("injury_flag", "weather_flag", "lineup_flag", "duplicate_check", "market_disagreement_flag")


@dataclass(frozen=True)
class EnsemblePolicy:
    min_probability: float = 0.56
    min_edge: float = 0.02
    min_data_quality: float = 70.0
    min_bookmaker_count: int = 3
    accept_score: float = 70.0
    watch_score: float = 50.0
    min_accept_agreements: int = 4
    max_accept_conflicts: int = 1


@dataclass(frozen=True)
class EnsembleReport:
    raw_rows: int
    accept_rows: int
    watch_rows: int
    reject_rows: int
    average_ensemble_score: float | None
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
        return float(text)
    except ValueError:
        return None


def _probability(value: Any) -> float | None:
    number = _float(value)
    if number is None:
        return None
    if number > 1.0:
        number /= 100.0
    if number < 0 or number > 1:
        return None
    return number


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "high", "bad", "fail", "duplicate", "missing", "conflict"}


def _edge(row: Mapping[str, Any]) -> float | None:
    value = _float(_first(row, EDGE_COLUMNS))
    if value is None:
        return None
    return value / 100.0 if abs(value) > 1.0 else value


def _quality(row: Mapping[str, Any]) -> float | None:
    return _float(_first(row, DATA_QUALITY_COLUMNS))


def _books(row: Mapping[str, Any]) -> int | None:
    value = _float(_first(row, BOOKMAKER_COLUMNS))
    return None if value is None else int(value)


def score_ensemble_row(row: Mapping[str, Any], policy: EnsemblePolicy = EnsemblePolicy()) -> dict[str, Any]:
    out = dict(row)
    agreements: list[str] = []
    conflicts: list[str] = []
    score = 0.0

    probability = _probability(_first(row, PROBABILITY_COLUMNS))
    if probability is not None and probability >= policy.min_probability:
        agreements.append("probability")
        score += min(30.0, max(0.0, (probability - 0.50) * 150.0))
    elif probability is None:
        conflicts.append("missing_probability")
    else:
        conflicts.append("low_probability")

    edge = _edge(row)
    if edge is not None and edge >= policy.min_edge:
        agreements.append("edge")
        score += min(20.0, edge * 250.0)
    elif edge is None:
        conflicts.append("missing_edge")
    else:
        conflicts.append("low_edge")

    quality = _quality(row)
    if quality is not None and quality >= policy.min_data_quality:
        agreements.append("data_quality")
        score += min(20.0, max(0.0, (quality - 50.0) / 2.5))
    elif quality is None:
        conflicts.append("missing_data_quality")
    else:
        conflicts.append("low_data_quality")

    books = _books(row)
    if books is not None and books >= policy.min_bookmaker_count:
        agreements.append("bookmaker_count")
        score += min(10.0, books * 1.25)
    elif books is None:
        conflicts.append("missing_bookmaker_count")
    else:
        conflicts.append("low_bookmaker_count")

    clv = _float(_first(row, CLV_COLUMNS))
    if clv is not None and clv > 0:
        agreements.append("positive_clv_or_history")
        score += min(10.0, clv * 200.0 if abs(clv) <= 1 else clv / 5.0)
    elif clv is not None and clv < 0:
        conflicts.append("negative_clv_or_history")
        score -= 8.0

    market_support = _float(_first(row, MARKET_SUPPORT_COLUMNS))
    if market_support is not None and market_support >= 60:
        agreements.append("market_support")
        score += min(10.0, (market_support - 50.0) / 5.0)
    elif market_support is not None and market_support < 40:
        conflicts.append("weak_market_support")
        score -= 6.0

    lookup = _lookup(row)
    for flag in NEGATIVE_FLAG_COLUMNS:
        if _truthy(lookup.get(_clean_key(flag))):
            conflicts.append(flag)
            score -= 10.0

    score = round(max(0.0, min(100.0, score)), 2)
    if score >= policy.accept_score and len(agreements) >= policy.min_accept_agreements and len(conflicts) <= policy.max_accept_conflicts:
        status = "ACCEPT"
    elif score >= policy.watch_score:
        status = "WATCH"
    else:
        status = "REJECT"

    out["ensemble_score"] = str(score)
    out["signal_agreement_count"] = str(len(agreements))
    out["signal_conflict_count"] = str(len(conflicts))
    out["signal_agreements"] = "; ".join(agreements)
    out["signal_conflicts"] = "; ".join(conflicts)
    out["ensemble_status"] = status
    out["acceptance_reason"] = "; ".join(agreements) if status == "ACCEPT" else ""
    out["rejection_reason"] = "; ".join(conflicts) if status != "ACCEPT" else ""
    return out


def apply_ensemble_scoring(rows: list[Mapping[str, Any]], policy: EnsemblePolicy = EnsemblePolicy()) -> list[dict[str, Any]]:
    return [score_ensemble_row(row, policy=policy) for row in rows]


def summarize_ensemble(rows: list[Mapping[str, Any]], *, output_csv: str | None = None) -> EnsembleReport:
    scores = [_float(row.get("ensemble_score")) for row in rows]
    scores = [score for score in scores if score is not None]
    return EnsembleReport(
        raw_rows=len(rows),
        accept_rows=sum(1 for row in rows if row.get("ensemble_status") == "ACCEPT"),
        watch_rows=sum(1 for row in rows if row.get("ensemble_status") == "WATCH"),
        reject_rows=sum(1 for row in rows if row.get("ensemble_status") == "REJECT"),
        average_ensemble_score=None if not scores else round(sum(scores) / len(scores), 4),
        output_csv=output_csv,
        notes=[
            "Ensemble score rewards independent agreement across probability, edge, data quality, books, CLV and market support.",
            "Rows with signal conflicts are downgraded even when model probability is high.",
        ],
    )


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


def write_report(report: EnsembleReport, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
