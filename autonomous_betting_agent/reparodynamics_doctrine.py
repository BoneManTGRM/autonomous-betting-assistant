"""Reparodynamics operating doctrine for ABA Signal Pro.

This module is intentionally wording-focused and behavior-safe. It defines the
Phase 3B doctrine used by reports and dashboards. Phase 3B turns Shadow Mode on
for counterfactual evaluation only. It still forbids live repairs, TGRM repair
activation, confidence changes, bet-tier changes, bankroll changes, sportsbook
recommendation changes, live filters, and production model mutation.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

DOCTRINE_SCHEMA_VERSION = "reparodynamics_phase_3b_shadow_v1"

REPARODYNAMICS_MOTIVE = (
    "Reparodynamics is the operating doctrine of measured self-repair. "
    "ABA observes first, diagnoses carefully, preserves data integrity, "
    "conserves repair energy, and tests repairs in Shadow Mode before any "
    "targeted change can be considered for manual approval."
)

REPAIR_PRINCIPLES = [
    "Observe first and repair later.",
    "Diagnose drift before proposing any repair.",
    "Prefer targeted repair over blind retraining.",
    "Conserve repair energy by changing only what evidence supports.",
    "Evaluate pattern candidates in Shadow Mode before promotion.",
    "Treat RYE readiness as readiness only, not live activation.",
    "Treat Shadow Mode as counterfactual evaluation only.",
]

SAFETY_PRINCIPLES = [
    "Phase 3B enables Shadow Mode evaluation only.",
    "Learning means observation, diagnostics, shadow evaluation, readiness checks, and saved reports only.",
    "No live repair activates during Phase 3B.",
    "No repair survives without proof.",
    "The system does not chase losses.",
    "The system does not panic after variance.",
    "The system does not blindly retrain.",
    "The system does not inflate confidence.",
]

FORBIDDEN_PHASE_3B_ACTIONS = [
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
]

PHASE_3B_DOCTRINE: dict[str, Any] = {
    "doctrine_version": DOCTRINE_SCHEMA_VERSION,
    "motive": REPARODYNAMICS_MOTIVE,
    "current_phase": "Phase 3B",
    "operating_mode": "Shadow Mode evaluation",
    "repair_philosophy": "Evidence-gated targeted repair",
    "repair_principles": REPAIR_PRINCIPLES,
    "safety_principles": SAFETY_PRINCIPLES,
    "forbidden_actions": FORBIDDEN_PHASE_3B_ACTIONS,
    "live_mutation": "Forbidden",
    "repair_activation": "OFF",
    "shadow_mode_activation": "ON",
    "tgrm_activation": "OFF",
    "rye_activation": "OFF",
    "final_rule": "ABA may test repairs in Shadow Mode, but live repair remains forbidden.",
}


# Backward-compatible alias for code that imports the old constant name.
PHASE_3A_DOCTRINE = PHASE_3B_DOCTRINE


def get_reparodynamics_doctrine() -> dict[str, Any]:
    """Return a defensive copy of the current Reparodynamics doctrine."""

    return deepcopy(PHASE_3B_DOCTRINE)
