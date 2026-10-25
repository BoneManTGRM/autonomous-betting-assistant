"""Pure, observation-only admission review for *new* learning intake.

This checks supplied evidence, not its authenticity. It neither certifies old
weights nor fits, persists, promotes, discovers records, or changes predictions.
Missing historical evidence is never reconstructed from a confidence label.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .accuracy_calibration import result_from_row
from .offline_learning_validation import MIN_TRAIN_EVENTS, SCHEMA_VERSION, validate_observation

ADMISSION_VERSION = "learning-evidence-admission-v1"
COMPACT_SCHEMA = "learning-evidence-compact-v1"
GRADE_ALIASES = {
    "result_status", "verified_grade", "result", "resultado", "outcome", "win_loss",
    "ganada_perdida", "graded_result", "status", "estado", "final_result", "w_l", "wl",
    "manual_grade", "verified_result", "verified_status", "verified_outcome",
    "verified_result_status", "grade", "final_grade", "proof_grade", "pick_grade",
    "row_grade", "result_grade",
}
_FINAL_STATES = {"settled", "final", "completed", "closed", "graded"}


def _key(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def strict_learning_grade(row: Mapping[str, Any]) -> str | None:
    """All supplied grade aliases must agree; no substring/winner inference."""
    grades = set()
    for key, value in row.items():
        column = _key(key)
        if column not in GRADE_ALIASES or value is None or value == "":
            continue
        if column in {"status", "estado"} and str(value).strip().lower() in _FINAL_STATES:
            continue
        grade = result_from_row({"result_status": value})
        if grade not in {"win", "loss"}:
            return None
        grades.add(grade)
    return next(iter(grades)) if len(grades) == 1 else None


def _time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("explicit timestamp required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("explicit timezone required")
    return parsed.astimezone(timezone.utc)


def load_evidence_json(text: str) -> Any:
    """Reject last-key-wins and non-JSON numeric literals before evidence review."""
    import json

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'duplicate JSON key: {key}')
            result[key] = value
        return result

    def invalid_number(value):
        raise ValueError(f'non-finite JSON literal: {value}')

    return json.loads(text, object_pairs_hook=unique, parse_constant=invalid_number)


def evidence_view(record: Mapping[str, Any]) -> dict[str, Any]:
    """Deserialize explicit CSV values only; retain the original separately."""
    raw = record.get("raw_evidence", record)
    if not isinstance(raw, Mapping):
        raise ValueError("raw_evidence must be an object")
    if "raw_evidence" in record and "raw_evidence" in raw:
        raise ValueError("nested compact evidence envelopes are not supported")
    row = deepcopy(dict(raw))
    if row.get("outcome_verified") in ("true", "false"):
        row["outcome_verified"] = row["outcome_verified"] == "true"
    for field in ("features", "market_snapshot"):
        if isinstance(row.get(field), str):
            if row[field] == "" and field == "features":
                continue  # Missing evidence stays missing, not an invented object.
            row[field] = load_evidence_json(row[field])
    return row


def admission_reasons(record: Any) -> tuple[list[str], Any]:
    """Return explicit reasons plus a validated observation, without mutation."""
    if not isinstance(record, Mapping):
        return ["record must be an object"], None
    try:
        row = evidence_view(record)
    except (TypeError, ValueError) as exc:
        return [str(exc)], None
    reasons: list[str] = []
    grade = strict_learning_grade(row)
    if grade is None:
        reasons.append("exact, unambiguous binary final grade required across all aliases")
    if "raw_evidence" in record and record.get("compact_schema") != COMPACT_SCHEMA:
        reasons.append("missing or unsupported compact evidence schema")
    for field in ("grading_match_status", "auto_result_status", "review_reason", "audit_status", "odds_audit_status"):
        value = str(row.get(field) or "").strip().lower()
        if (field == "review_reason" and value) or any(word in value for word in ("review", "unverified", "mismatch", "conflict", "pending", "no_match", "blocked", "rejected", "quarantine", "fail")):
            reasons.append(f"{field}: unresolved or rejected evidence")
    for supplied in (row, record):
        for field in ("probability_source", "model_probability_source", "raw_model_probability_source"):
            probability_source = str(supplied.get(field) or "").lower()
            if any(word in probability_source for word in ("fallback", "price_implied", "confidence")):
                reasons.append(f"{field}: original pre-event model probability required; inferred confidence/price is not evidence")
    event_id = row.get("event_id")
    for field in ("result_event_id", "matched_result_event_id", "matched_event_id", "verified_event_id"):
        if row.get(field) not in (None, "") and row[field] != event_id:
            reasons.append(f"{field}: event identity mismatch")
    for field in ("game_id", "fixture_id"):
        if row.get(field) not in (None, "") and row[field] != event_id:
            reasons.append(f"{field}: event identity/namespace not established")
    for field, original in (("matched_result_market_id", "market_id"), ("matched_result_selection_id", "selection_id")):
        if row.get(field) not in (None, "") and row[field] != row.get(original):
            reasons.append(f"{field}: selection/market identity mismatch")
    for field in ("matched_result_event", "matched_event"):
        if row.get(field):
            events = [str(row[key]).strip().casefold() for key in ("event", "event_name") if row.get(key)]
            if not events or any(str(row[field]).strip().casefold() != event for event in events):
                reasons.append(f"{field}: event identity not established")
    for field in ("event_start_utc", "matched_result_event_start_utc", "result_event_start"):
        if row.get(field) not in (None, ""):
            try:
                if _time(row[field]) != _time(row.get("event_start")):
                    reasons.append(f"{field}: event time mismatch")
            except (TypeError, ValueError):
                reasons.append(f"{field}: event time not established")
    try:
        # Canonicalizing an explicit agreed grade is not creating a result.
        view = {**row, "result_status": grade} if grade is not None else row
        observation = validate_observation(view)
    except (TypeError, ValueError) as exc:
        reasons.append(str(exc))
        observation = None
    if observation is not None and "raw_evidence" in record:
        # One canonical shape, not an ever-growing list of envelope aliases.
        # This pure renderer has no admission recursion, I/O, fitting or writes.
        from .learning_memory_tools import _compact_row_from_observation
        expected = _compact_row_from_observation(record['raw_evidence'], observation)
        if set(record) != set(expected):
            reasons.append("compact envelope has missing or unrecognized fields")
        for key, value in expected.items():
            if key in record and (record[key] != value or type(record[key]) is not type(value)):
                reasons.append(f"compact {key}: conflicts with retained original evidence")
    return list(dict.fromkeys(reasons)), observation


def review_learning_records(records: Sequence[Any], *, minimum_events: int = MIN_TRAIN_EVENTS) -> dict[str, Any]:
    """All-or-nothing readiness, with every original record and rejection visible.

    Duplicate rows never increase event evidence. A rejected/conflicting member
    quarantines its event. Passing this check never enables a fit or promotion.
    """
    entries = []
    grouped: dict[str, list[int]] = defaultdict(list)
    observations = {}
    for index, record in enumerate(records):
        reasons, observation = admission_reasons(record)
        entry = {"row_index": index, "record": deepcopy(record), "reasons": reasons}
        entries.append(entry)
        try:
            event = evidence_view(record).get("event_id") if isinstance(record, Mapping) else None
        except (TypeError, ValueError):
            event = None
        if isinstance(event, str) and event.strip():
            grouped[event.strip()].append(index)
        if observation is not None:
            observations[index] = observation
    for indices in grouped.values():
        valid = [observations[i] for i in indices if i in observations]
        by_key = defaultdict(list)
        for observation in valid:
            by_key[observation.key].append(observation)
        conflict = any(any(row != rows[0] for row in rows[1:]) for rows in by_key.values())
        conflict |= len({(row.event_start, row.sport) for row in valid}) > 1
        market_types = defaultdict(set)
        for observation in valid:
            market_types[observation.market_id].add(observation.market_type)
        conflict |= any(len(types) > 1 for types in market_types.values())
        if conflict or any(entries[i]["reasons"] for i in indices):
            for i in indices:
                entries[i]["reasons"].append("event quarantined: conflicting identity or another record failed admission")
    for entry in entries:
        entry["admitted"] = not entry["reasons"]
    admitted = [observations[e["row_index"]] for e in entries if e["admitted"]]
    events = {row.event_id for row in admitted}
    required = max(MIN_TRAIN_EVENTS, int(minimum_events))
    reasons = []
    if any(not entry["admitted"] for entry in entries):
        reasons.append("one or more records failed admission; no subset will be trained")
    if len(events) < required:
        reasons.append(f"need at least {required} unique admitted events; got {len(events)}")
    if {row.outcome for row in admitted} != {0, 1}:
        reasons.append("both explicitly supplied final wins and losses are required")
    return {"version": ADMISSION_VERSION, "evidence_schema": SCHEMA_VERSION,
            "status": "BLOCKED" if reasons else "READY_FOR_OBSERVATION_ONLY",
            "reason": "; ".join(reasons) if reasons else "admitted for offline observation only; no training or promotion",
            "observation_only": True, "live_mutation_allowed": False, "promotion_allowed": False,
            "evidence_authentication": "UNVERIFIED_SUPPLIED_CLAIMS", "independently_verified": False,
            "trained": False, "artifacts_written": False, "predictive_gain_proven": False,
            "input_rows": len(entries), "admitted_rows": len(admitted),
            "rejected_rows": len(entries) - len(admitted), "unique_admitted_events": len(events),
            "minimum_required_events": required, "batch_admitted": bool(entries) and all(e["admitted"] for e in entries),
            "records": entries,
            "limitations": ["Checks supplied evidence structure, not external source authenticity.",
                            "Existing saved weights are unchanged and their historical provenance remains uncertified.",
                            "No holdout experiment has run and no predictive improvement is established."]}
