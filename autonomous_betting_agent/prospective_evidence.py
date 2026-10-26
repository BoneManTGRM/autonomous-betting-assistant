"""Pure preparation/review of supplied prospective evidence, never certification.

No files, network, fitting, ledger discovery or promotion. A local clock and hash
cannot establish independent pre-event existence or authenticate a result source.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

from .learning_evidence_admission import load_evidence_json

SCHEMA = "aba-prospective-preparation-v1"
REVIEW_SCHEMA = "aba-prospective-review-v1"
MAX_ROWS = 1000
MAX_INPUT_BYTES = 2_000_000
MAX_PACKET_BYTES = 8_000_000
PROTOCOL_FIELDS = {"test_id", "population", "selection_policy", "exclusions", "baseline_definition"}
PREDICTION_TEXT_FIELDS = {
    "event_namespace", "event_id", "market_id", "selection_id", "sport", "market_type",
    "event_label", "selection_label", "settlement_rule", "raw_model_version",
    "baseline_model_version", "event_source", "prediction_source", "odds_source",
}
PREDICTION_TIME_FIELDS = {"event_start", "raw_probability_available_at", "baseline_probability_available_at", "odds_observed_at"}
PREDICTION_FIELDS = PREDICTION_TEXT_FIELDS | PREDICTION_TIME_FIELDS | {"raw_model_probability", "baseline_probability", "decimal_odds"}
RECEIPT_FIELDS = {
    "packet_sha256", "prediction_id", "event_namespace", "event_id", "market_id", "selection_id",
    "result_status", "result_available_at", "source_observed_at", "verified_at", "source_url",
    "source_sha256", "source_final_status", "verifier_reference", "settlement_explanation",
}
TRUST = {
    "evidence_authentication": "UNVERIFIED_SUPPLIED_CLAIMS",
    "independently_verified": False, "authenticated_pre_event_commitment": False,
    "training_allowed": False, "promotion_allowed": False, "live_mutation_allowed": False,
    "predictive_gain_proven": False,
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{field}: nonempty text without surrounding whitespace required")
    if len(value) > 10_000 or any(ord(char) < 32 for char in value):
        raise ValueError(f"{field}: oversized text or control character")
    return value


def _shape(value: Any, fields: set[str], field: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{field}: exact schema required; missing or unknown fields")


def _time(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(_text(value, field).replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("timezone required")
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{field}: valid ISO timestamp with explicit timezone required") from exc


def _now(now: datetime | None) -> datetime:
    value = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aware clock required")
    return value.astimezone(timezone.utc)


def _number(value: Any, field: str, *, probability: bool = False) -> float:
    # JSON numbers only. Do not infer a probability from a label, percent or odds.
    if type(value) not in (int, float):
        raise ValueError(f"{field}: JSON number required")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{field}: finite number required") from exc
    if not math.isfinite(number) or (not 0 <= number <= 1 if probability else number <= 1):
        raise ValueError(f"{field}: number outside valid range")
    return number


def _digest(value: Any, field: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise ValueError(f"{field}: lowercase SHA256 required")


def _parse(text: str, *, max_bytes: int = MAX_INPUT_BYTES) -> Any:
    if not isinstance(text, str) or len(text.encode("utf-8")) > max_bytes:
        raise ValueError(f"UTF-8 JSON input exceeds the {max_bytes} byte limit")
    try:
        return load_evidence_json(text)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError(f"invalid evidence JSON: {exc}") from exc


def _check_prediction(row: Any, prepared_at: datetime) -> None:
    _shape(row, PREDICTION_FIELDS, "prediction")
    for field in PREDICTION_TEXT_FIELDS:
        _text(row[field], field)
    for field in ("raw_model_probability", "baseline_probability"):
        _number(row[field], field, probability=True)
    _number(row["decimal_odds"], "decimal_odds")
    if _time(row["event_start"], "event_start") <= prepared_at:
        raise ValueError("event_start: event must still be in the future at preparation")
    for field in ("raw_probability_available_at", "baseline_probability_available_at", "odds_observed_at"):
        available = _time(row[field], field)
        if available > prepared_at:
            raise ValueError(f"{field}: future availability cannot support this preparation")
        if field == "odds_observed_at" and (prepared_at - available).total_seconds() > 300:
            raise ValueError("odds_observed_at: supplied odds are older than five minutes")


def prepare_packet(input_text: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Prepare an outcome-free, exact-schema cohort using the current local clock.

    This is preparation, NOT a forward lock or a trusted timestamp. The input
    text is retained verbatim; no historical row or original probability is
    normalized, backfilled, deduplicated, fitted or overwritten.
    """
    prepared_at = _now(now)
    source = _parse(input_text)
    _shape(source, {"protocol", "predictions"}, "input")
    _shape(source["protocol"], PROTOCOL_FIELDS, "protocol")
    for field in PROTOCOL_FIELDS:
        _text(source["protocol"][field], f"protocol.{field}")
    rows = source["predictions"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise ValueError(f"predictions: supply 1–{MAX_ROWS} rows")
    identities = set()
    events = {}
    markets = {}
    namespaces = set()
    versions = set()
    for index, row in enumerate(rows):
        try:
            _check_prediction(row, prepared_at)
            identity = (row["event_namespace"], row["event_id"], row["market_id"], row["selection_id"])
            if identity in identities:
                raise ValueError("duplicate or conflicting event/market/selection identity")
            identities.add(identity)
            namespaces.add(row["event_namespace"])
            versions.add((row["raw_model_version"], row["baseline_model_version"]))
            event_key = identity[:2]
            event = (_time(row["event_start"], "event_start"), row["sport"], row["event_label"])
            if event_key in events and events[event_key] != event:
                raise ValueError("conflicting event time, sport or label")
            events[event_key] = event
            market_key = identity[:3]
            market = (row["market_type"], row["settlement_rule"])
            if market_key in markets and markets[market_key] != market:
                raise ValueError("conflicting market type or settlement rule")
            markets[market_key] = market
        except ValueError as exc:
            raise ValueError(f"prediction[{index}]: {exc}") from exc
    if len(namespaces) != 1:
        raise ValueError("one event namespace per cohort required; cross-provider identities are not reconciled")
    if len(versions) != 1:
        raise ValueError("one raw model version and one frozen baseline version per cohort required")
    stamp = prepared_at.isoformat()
    protocol_hash = _hash(source["protocol"])
    packet = {
        "schema": SCHEMA, "prepared_at": stamp,
        "input_sha256": hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
        "original_input": input_text, "protocol": deepcopy(source["protocol"]),
        "protocol_sha256": protocol_hash,
        "predictions": [{"prediction_id": _hash({"prepared_at": stamp, "protocol_sha256": protocol_hash, "prediction": row}),
                         "prediction": deepcopy(row)} for row in rows],
        **TRUST,
    }
    return {**packet, "packet_sha256": _hash(packet)}


def validate_packet(packet: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Check internal consistency only, including original input and exact shape."""
    if not isinstance(packet, dict):
        raise ValueError("packet: object required")
    prepared = _time(packet.get("prepared_at"), "prepared_at")
    if prepared > _now(now):
        raise ValueError("prepared_at: future preparation time")
    expected = prepare_packet(packet.get("original_input"), now=prepared)
    # Canonical bytes preserve JSON types (True must not equal numeric 1).
    try:
        if _canonical(packet) != _canonical(expected):
            raise ValueError("packet: modified content, unsupported schema or mismatched digest")
    except (TypeError, OverflowError, RecursionError) as exc:
        raise ValueError("packet: invalid JSON value") from exc
    return deepcopy(expected)


def _check_receipt(receipt: Any, packet: Mapping[str, Any], prediction: Mapping[str, Any], now: datetime) -> None:
    _shape(receipt, RECEIPT_FIELDS, "receipt")
    for key in RECEIPT_FIELDS:
        _text(receipt[key], key)
    if receipt["packet_sha256"] != packet["packet_sha256"]:
        raise ValueError("receipt: packet identity mismatch")
    row = prediction["prediction"]
    for key in ("event_namespace", "event_id", "market_id", "selection_id"):
        if receipt[key] != row[key]:
            raise ValueError(f"receipt: {key} identity mismatch")
    if receipt["result_status"] not in {"win", "loss", "void"}:
        raise ValueError("receipt: exact win/loss/void required")
    if receipt["source_final_status"] != "final":
        raise ValueError("receipt: explicit final source status required; it remains a supplied claim")
    _digest(receipt["source_sha256"], "source_sha256")
    url = urlsplit(receipt["source_url"])
    if url.scheme != "https" or not url.hostname or url.username or url.password or any(char.isspace() for char in receipt["source_url"]):
        raise ValueError("receipt: HTTPS result source URL without embedded credentials required")
    start = _time(row["event_start"], "event_start")
    available = _time(receipt["result_available_at"], "result_available_at")
    observed = _time(receipt["source_observed_at"], "source_observed_at")
    verified = _time(receipt["verified_at"], "verified_at")
    if not start < available <= observed <= verified <= now:
        raise ValueError("receipt: start/result/source-observation/review chronology invalid")


def review_packet(packet_text: str, receipts_text: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Retain the entire cohort and every receipt, including conflicts/errors.

    Passing structural checks never authenticates a URL, supplied source hash,
    reviewer claim or timestamp. No observed win rate or ROI is certified here.
    """
    clock = _now(now)
    packet = validate_packet(_parse(packet_text, max_bytes=MAX_PACKET_BYTES), now=clock)
    receipts = _parse(receipts_text)
    if not isinstance(receipts, list) or len(receipts) > MAX_ROWS * 3:
        raise ValueError(f"receipts: list with at most {MAX_ROWS * 3} entries required")
    predictions = {row["prediction_id"]: row for row in packet["predictions"]}
    entries = []
    grouped = defaultdict(list)
    for index, receipt in enumerate(receipts):
        errors = []
        identity = receipt.get("prediction_id") if isinstance(receipt, dict) else None
        if not isinstance(identity, str) or identity not in predictions:
            errors.append("receipt: unknown prediction identity")
        else:
            grouped[identity].append(index)
            try:
                _check_receipt(receipt, packet, predictions[identity], clock)
            except (ValueError, TypeError) as exc:
                errors.append(str(exc))
        entries.append({"receipt_index": index, "receipt": deepcopy(receipt), "reasons": errors})
    for indices in grouped.values():
        if len(indices) > 1:
            for index in indices:
                entries[index]["reasons"].append("duplicate or revised receipts require independent reconciliation; none selected")
    cohort = []
    for identity, prediction in predictions.items():
        indices = grouped[identity]
        if not indices:
            status = "pending"
        elif any(entries[index]["reasons"] for index in indices):
            status = "needs_review"
        else:
            status = "supplied_" + entries[indices[0]]["receipt"]["result_status"]
        cohort.append({**deepcopy(prediction), "receipt_indices": indices, "status": status})
    counts = Counter(row["status"] for row in cohort)
    rejected = sum(bool(entry["reasons"]) for entry in entries)
    return {
        "schema": REVIEW_SCHEMA, "reviewed_at": clock.isoformat(),
        "packet_sha256": packet["packet_sha256"], "original_packet_text": packet_text,
        "original_receipts_text": receipts_text, "protocol": deepcopy(packet["protocol"]),
        "status": "NEEDS_REVIEW" if rejected else "UNVERIFIED_SUPPLIED_CLAIMS",
        "cohort_rows": len(cohort),
        "unique_supplied_event_ids": len({(r["prediction"]["event_namespace"], r["prediction"]["event_id"]) for r in cohort}),
        "pending_rows": counts["pending"], "needs_review_rows": counts["needs_review"],
        "supplied_wins": counts["supplied_win"], "supplied_losses": counts["supplied_loss"], "supplied_voids": counts["supplied_void"],
        "unverified_rows": len(cohort), "authenticated_rows": 0,
        "receipt_count": len(entries), "rejected_receipts": rejected,
        "duplicate_or_revised_receipts": sum(len(indices) for indices in grouped.values() if len(indices) > 1),
        "cohort": cohort, "receipts": entries, **TRUST,
    }


def preparation_template() -> dict[str, Any]:
    """Blank schema, not a fabricated prediction or a reusable demo record."""
    return {"protocol": {key: "" for key in sorted(PROTOCOL_FIELDS)},
            "predictions": [{key: None if key in {"raw_model_probability", "baseline_probability", "decimal_odds"} else ""
                             for key in sorted(PREDICTION_FIELDS)}]}


def receipt_template(packet: Mapping[str, Any], *, now: datetime | None = None) -> list[dict[str, Any]]:
    checked = validate_packet(packet, now=now)
    rows = []
    for entry in checked["predictions"]:
        receipt = {key: "" for key in sorted(RECEIPT_FIELDS)}
        receipt.update({"packet_sha256": checked["packet_sha256"], "prediction_id": entry["prediction_id"]})
        receipt.update({key: entry["prediction"][key] for key in ("event_namespace", "event_id", "market_id", "selection_id")})
        rows.append(receipt)
    return rows
