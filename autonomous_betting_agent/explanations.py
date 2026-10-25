"""Client-safe pick explanation helpers.

The functions in this module convert scoring/audit fields into plain-English
reasons without promising wins, ROI, or certainty.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from .ledger_types import classify_ledger_type


def _float(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if value is None or value == "":
            continue
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(number):
            return number
    return None


def _int(row: Mapping[str, Any], *keys: str) -> int | None:
    value = _float(row, *keys)
    return None if value is None else int(value)


def _text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def build_odds_audit_explanation(row: Mapping[str, Any]) -> str:
    status = _text(row, "odds_audit_status", "audit_status").lower()
    reason = _text(row, "odds_audit_reason", "audit_reason")
    average_price = _float(row, "average_price")
    best_price = _float(row, "best_price")

    if status in {"pass", "passed", "clean"}:
        base = "The odds audit did not flag a major price-quality issue."
    elif status in {"quarantine", "review", "fail", "failed", "blocked"}:
        base = "The odds audit marked this row for review before it should be trusted as official proof."
    else:
        base = "The odds audit status is incomplete, so this row should be reviewed before being promoted."

    if average_price and best_price and best_price > average_price * 1.35:
        base += " The best price is far above the market average, which may indicate an outlier or mapping issue."
    if reason:
        base += f" Audit note: {reason}."
    return base


def build_pattern_points_explanation(row: Mapping[str, Any]) -> str:
    points = _float(row, "pattern_points")
    tier = _text(row, "pattern_confidence_tier")
    pattern_count = _int(row, "learning_pattern_count")
    adjustment = _float(row, "learning_adjustment_score")

    if points is None:
        return "Pattern Points were not available for this row."
    if points >= 85:
        base = "Pattern Points are very strong for this row."
    elif points >= 75:
        base = "Pattern Points are strong for this row."
    elif points >= 65:
        base = "Pattern Points show a useful learned-pattern signal."
    elif points >= 55:
        base = "Pattern Points show a research-level signal that needs more proof."
    else:
        base = "Pattern Points are weak or incomplete for this row."

    base += f" Score: {points:.1f}/100."
    if tier:
        base += f" Tier: {tier}."
    if pattern_count is not None and pattern_count > 0:
        base += f" It matched {pattern_count} learned pattern(s)."
    if adjustment is not None and adjustment > 0:
        base += " Learning adjustment was positive."
    elif adjustment is not None and adjustment < 0:
        base += " Learning adjustment was negative, so this needs extra caution."
    return base


def build_risk_summary(row: Mapping[str, Any]) -> str:
    warnings: list[str] = []
    ledger_type = classify_ledger_type(row)
    audit_status = _text(row, "odds_audit_status", "audit_status").lower()
    book_count = _int(row, "books", "bookmaker_count", "book_count")
    probability = _float(row, "learned_model_probability", "model_probability", "probability")
    decimal_price = _float(row, "decimal_price", "odds_at_pick")

    if ledger_type not in {"official", "client"}:
        warnings.append(f"This row is classified as {ledger_type}, not official public proof.")
    if audit_status in {"quarantine", "review", "fail", "failed", "blocked"}:
        warnings.append("The odds audit requires review before this row should be used in official reporting.")
    if book_count is not None and book_count < 2:
        warnings.append("Book coverage is thin, so the market price may be less reliable.")
    if probability is None:
        warnings.append("Model probability is missing.")
    if decimal_price is None:
        warnings.append("Proof-safe decimal price is missing.")
    if not warnings:
        return "No major local risk flag was detected from the available fields. This is still analytics/research only, not a guaranteed outcome."
    return " ".join(warnings) + " This is analytics/research only, not a guaranteed outcome."


def build_pick_explanation(row: Mapping[str, Any]) -> str:
    parts: list[str] = []
    probability = _float(row, "learned_model_probability", "model_probability", "probability")
    edge = _float(row, "model_market_edge", "edge", "ev")
    book_count = _int(row, "books", "bookmaker_count", "book_count")
    ledger_type = classify_ledger_type(row)

    parts.append(f"Ledger classification: {ledger_type}.")
    if probability is not None:
        parts.append(f"Model probability is {probability:.1%}.")
    if edge is not None:
        if edge > 0:
            parts.append("The row shows positive model-market edge from the available fields.")
        elif edge < 0:
            parts.append("The row shows negative model-market edge and should be reviewed carefully.")
        else:
            parts.append("The row shows neutral model-market edge.")
    if book_count is not None:
        if book_count >= 4:
            parts.append("Book coverage is broad enough for cleaner price review.")
        elif book_count >= 2:
            parts.append("Book coverage is moderate.")
        else:
            parts.append("Book coverage is thin.")

    parts.append(build_pattern_points_explanation(row))
    parts.append(build_odds_audit_explanation(row))
    parts.append(build_risk_summary(row))
    return " ".join(part for part in parts if part).strip()


def build_client_safe_pick_summary(row: Mapping[str, Any]) -> str:
    event = _text(row, "event", "event_name", "matchup", "game") or "Event"
    pick = _text(row, "prediction", "pick", "selection") or "Selection not specified"
    market = _text(row, "market", "market_type") or "market not specified"
    proof_id = _text(row, "proof_id")
    explanation = build_pick_explanation(row)
    proof_text = f" Proof ID: {proof_id}." if proof_id else ""
    return f"{event} — {pick} ({market}).{proof_text} {explanation}"
