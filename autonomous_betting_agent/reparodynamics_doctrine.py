"""Reparodynamics operating doctrine for ABA Signal Pro.

This module is intentionally wording-focused and behavior-neutral. It defines the
Phase 3A doctrine used by reports and dashboards without activating repairs,
Shadow Mode, TGRM, RYE scoring, confidence changes, bet-tier changes, bankroll
changes, sportsbook recommendations, or live model mutation.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

DOCTRINE_SCHEMA_VERSION = "reparodynamics_phase_3a_v1"

REPARODYNAMICS_MOTIVE = (
    "Reparodynamics is the operating doctrine of measured self-repair. "
    "ABA observes first, diagnoses carefully, preserves data integrity, "
    "conserves repair energy, and repairs only after controlled evidence shows "
    "a targeted change improves measurable performance without increasing hidden risk."
)

REPAIR_PRINCIPLES = [
    "Observe first and repair later.",
    "Diagnose drift before proposing any repair.",
    "Prefer targeted repair over blind retraining.",
    "Conserve repair energy by changing only what evidence supports.",
    "Keep pattern candidates watchlist-only until controlled evidence supports promotion.",
    "Treat RYE readiness as readiness only, not activation.",
    "Treat Shadow Mode readiness as readiness only, not activation.",
]

SAFETY_PRINCIPLES = [
    "Phase 3A is observation-only.",
    "Learning means observation, diagnostics, watchlist candidates, readiness checks, and saved reports only.",
    "No repair activates during Phase 3A.",
    "No repair survives without proof.",
    "The system does not chase losses.",
    "The system does not panic after variance.",
    "The system does not blindly retrain.",
    "The system does not inflate confidence.",
]

FORBIDDEN_PHASE_3A_ACTIONS = [
    "live repairs",
    "Shadow Mode activation",
    "TGRM repair activation",
    "full RYE repair scoring",
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

PHASE_3A_DOCTRINE: dict[str, Any] = {
    "doctrine_version": DOCTRINE_SCHEMA_VERSION,
    "motive": REPARODYNAMICS_MOTIVE,
    "current_phase": "Phase 3A",
    "operating_mode": "Observation-only",
    "repair_philosophy": "Evidence-gated targeted repair",
    "repair_principles": REPAIR_PRINCIPLES,
    "safety_principles": SAFETY_PRINCIPLES,
    "forbidden_actions": FORBIDDEN_PHASE_3A_ACTIONS,
    "live_mutation": "Forbidden",
    "repair_activation": "OFF",
    "shadow_mode_activation": "OFF",
    "tgrm_activation": "OFF",
    "rye_activation": "OFF",
    "final_rule": "ABA should learn automatically, but repair cautiously.",
}


def get_reparodynamics_doctrine() -> dict[str, Any]:
    """Return a defensive copy of the Phase 3A Reparodynamics doctrine."""

    return deepcopy(PHASE_3A_DOCTRINE)
