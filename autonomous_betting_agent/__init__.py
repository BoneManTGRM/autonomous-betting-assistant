"""Autonomous Betting Agent.

A standalone, research-only sports analytics agent derived from the ARA/TGRM
architecture. It estimates probabilities, explains evidence, tracks uncertainty,
and supports backtesting. It does not place wagers.
"""

from .models import EventResearchInput, PredictionResult, TeamSnapshot
from .researcher import AutonomousBettingAgent
from .tgrm import TGRMLoop

__all__ = [
    "AutonomousBettingAgent",
    "EventResearchInput",
    "PredictionResult",
    "TeamSnapshot",
    "TGRMLoop",
]
