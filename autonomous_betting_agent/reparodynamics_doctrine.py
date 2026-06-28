"""Reparodynamics operating doctrine for ABA Signal Pro.

This module is intentionally wording-focused and behavior-safe. It defines the
Phase 3C doctrine used by reports and dashboards. Phase 3C turns Shadow Backtest
comparison on for counterfactual evaluation only. It still forbids live repairs,
confidence changes, bet-tier changes, bankroll changes, sportsbook changes, live
filters, proof-ledger mutation, stored-data mutation, and production model mutation.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

DOCTRINE_SCHEMA_VERSION = "reparodynamics_phase_3c_shadow_backtest_v1"

REPARODYNAMICS_MOTIVE = (
    "Reparodynamics is the operating doctrine of measured self-repair. "
    "ABA observes first, diagnoses carefully, preserves data integrity, "
    "conserves repair energy, and tests repairs in Shadow Backtest before any "
    "targeted change can be considered for manual approval."
)

REPAIR_PRINCIPLES = [
    "Observe first and repair later.",
    "Diagnose drift before proposing any repair.",
    "Separate data blockers from repair candidates.",
    "Prefer targeted repair over blind retraining.",
    "Conserve repair energy by changing only what evidence supports.",
    "Evaluate pattern candidates in Shadow Backtest before promotion.",
    "Treat RYE readiness as readiness only, not live activation.",
    "Treat Shadow Mode as counterfactual evaluation only.",
]

SAFETY_PRINCIPLES = [
    "Phase 3C enables Shadow Backtest comparison only.",
    "Learning means observation, diagnostics, shadow evaluation, readiness checks, and saved reports only.",
    "No live repair activates during Phase 3C.",
    "No repair survives without proof.",
    "The system does not chase losses.",
    "The system does not panic after variance.",
    "The system does not blindly retrain.",
    "The system does not inflate confidence.",
]

FORBIDDEN_PHASE_3C_ACTIONS = [
    "live repairs",
    "TGRM repair activation",
    "full RYE repair activation",
    "Hidden Value Score activation",
    "confidence calibration activation",
    "live pick filtering",
    "live model mutation",
    "Learning Page live model updates",
    "automatic confidence adjustment",
    "automatic bet-tier changes",
    "production repair candidates",
    "automatic bankroll changes",
    "automatic sportsbook recommendation changes",
    "stored proof data mutation",
    "automatic proof ledger mutation",
]

PHASE_3C_DOCTRINE: dict[str, Any] = {
    "doctrine_version": DOCTRINE_SCHEMA_VERSION,
    "motive": REPARODYNAMICS_MOTIVE,
    "current_phase": "Phase 3C Shadow Backtest",
    "operating_mode": "Shadow Backtest comparison",
    "repair_philosophy": "Evidence-gated targeted repair",
    "repair_principles": REPAIR_PRINCIPLES,
    "safety_principles": SAFETY_PRINCIPLES,
    "forbidden_actions": FORBIDDEN_PHASE_3C_ACTIONS,
    "live_mutation": "FORBIDDEN",
    "repair_activation": "OFF",
    "shadow_mode_activation": "ON",
    "tgrm_activation": "SHADOW ONLY",
    "rye_activation": "SHADOW ONLY",
    "model_training": "FORBIDDEN",
    "stored_data_mutation": "FORBIDDEN",
    "live_repairs_applied": 0,
    "repairs_applied_live": 0,
    "final_rule": "ABA may test repairs in Shadow Backtest, but live repair remains forbidden.",
}

# Backward-compatible aliases for code that imports older constant names.
PHASE_3B_DOCTRINE = PHASE_3C_DOCTRINE
PHASE_3A_DOCTRINE = PHASE_3C_DOCTRINE


def get_reparodynamics_doctrine() -> dict[str, Any]:
    """Return a defensive copy of the current Reparodynamics doctrine."""
    return deepcopy(PHASE_3C_DOCTRINE)
