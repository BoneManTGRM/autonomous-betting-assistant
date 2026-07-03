from __future__ import annotations

from typing import Any

import pandas as pd


FILTER_DIAGNOSTIC_TIER = "RESEARCH ONLY / FILTER DIAGNOSTIC"
FILTER_DIAGNOSTIC_SOURCE = "pro_predictor_filter_diagnostic"


def _numeric(frame: pd.DataFrame, column: str, *, default: float) -> pd.Series:
    if column not in frame.columns:
        return pd.Series([default] * len(frame), index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").fillna(default)


def _summary(series: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return {"min": None, "median": None, "max": None}
    return {
        "min": round(float(clean.min()), 6),
        "median": round(float(clean.median()), 6),
        "max": round(float(clean.max()), 6),
    }


def apply_filter_audit(
    frame: pd.DataFrame,
    *,
    min_prob: float,
    min_edge: float,
    min_signal: float,
    min_agent: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply Pro Predictor gates and return both filtered rows and gate diagnostics.

    This keeps the scan truthful: rows must still pass the configured gates to be
    returned as normal decisions, but the caller can show the audit table when
    no rows survive instead of emitting a blind no-rows message.
    """
    current = frame.copy()
    rows: list[dict[str, Any]] = []
    gates = [
        ("Minimum model probability", "model_probability_clean", float(min_prob), 0.0),
        ("Minimum edge", "model_market_edge", float(min_edge), -999.0),
        ("Minimum signal strength", "scanner_strength_score", float(min_signal), 0.0),
        ("Large-list min learned score", "agent_score", float(min_agent), 0.0),
    ]
    for gate_name, column, threshold, default in gates:
        before = len(current)
        values = _numeric(current, column, default=default) if before else pd.Series(dtype="float64")
        passed_mask = values >= threshold if before else pd.Series(dtype=bool)
        passed = int(passed_mask.sum()) if before else 0
        stats = _summary(values)
        rows.append(
            {
                "gate": gate_name,
                "column": column,
                "threshold": threshold,
                "before_rows": before,
                "passed_rows": passed,
                "failed_rows": before - passed,
                "after_rows": passed,
                "value_min": stats["min"],
                "value_median": stats["median"],
                "value_max": stats["max"],
            }
        )
        current = current[passed_mask].copy() if before else current
    return current, pd.DataFrame(rows)


def first_blocking_gate(audit: pd.DataFrame) -> str:
    if audit.empty:
        return "no filter audit available"
    blocked = audit[pd.to_numeric(audit.get("after_rows"), errors="coerce").fillna(0).eq(0)]
    if blocked.empty:
        return "all configured gates passed"
    first = blocked.iloc[0]
    return f"{first.get('gate', 'filter gate')} blocked all rows at threshold {first.get('threshold')}"


def diagnostic_mode_allowed(*, min_signal: float, min_agent: float) -> bool:
    """Only unlock diagnostic fallback when the user has intentionally loosened the two late-stage gates."""
    return float(min_signal) <= 1.0 and float(min_agent) <= 1.0


def make_research_diagnostic_candidates(
    frame: pd.DataFrame,
    audit: pd.DataFrame,
    *,
    max_rows: int,
) -> pd.DataFrame:
    """Return non-official research rows when strict filters removed every normal decision.

    These rows are real provider/scored rows, not fake picks. They are explicitly
    labeled research-only and are prevented from becoming official publish rows.
    """
    if frame.empty:
        return pd.DataFrame()
    out = frame.copy()
    blocker = first_blocking_gate(audit)
    out["filter_diagnostic_mode"] = True
    out["filter_blocker_reason"] = blocker
    out["recommendation_tier"] = FILTER_DIAGNOSTIC_TIER
    out["recommendation_gate_passed"] = False
    out["official_gate_passed"] = False
    out["client_report_ready"] = False
    out["official_publish_ready"] = False
    out["proof_source_type"] = FILTER_DIAGNOSTIC_SOURCE
    out["agent_decision"] = "research_diagnostic"
    out["recommended_stake_units"] = 0.0
    if "decision_reasons" in out.columns:
        out["decision_reasons"] = out["decision_reasons"].astype(str).str.strip()
        out["decision_reasons"] = (out["decision_reasons"] + "; " + blocker).str.strip("; ")
    else:
        out["decision_reasons"] = blocker
    if "decision_signals" in out.columns:
        out["decision_signals"] = out["decision_signals"].astype(str) + "; research_filter_diagnostic"
    else:
        out["decision_signals"] = "research_filter_diagnostic"
    sort_cols = [
        col
        for col in [
            "learned_agent_score",
            "agent_score",
            "learning_adjustment_score",
            "scanner_strength_score",
            "model_probability_clean",
            "model_market_edge",
        ]
        if col in out.columns
    ]
    if sort_cols:
        out = out.sort_values(sort_cols, ascending=False, na_position="last")
    return out.head(int(max_rows)).reset_index(drop=True)
