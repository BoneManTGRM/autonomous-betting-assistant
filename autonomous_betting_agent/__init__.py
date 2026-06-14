"""Autonomous Betting Agent.

A standalone, research-only sports analytics agent derived from the ARA/TGRM
architecture. It estimates probabilities, explains evidence, tracks uncertainty,
learns probability calibration from graded results, tracks edge/profit/CLV, and
supports backtesting.
"""

from .learning import GradedPrediction, ProbabilityCalibrator, fit_probability_calibrator, parse_graded_csv
from .models import EventResearchInput, PredictionResult, TeamSnapshot
from .researcher import AutonomousBettingAgent
from .tgrm import TGRMLoop
from .tracking import PredictionLedgerRow, SelectionDecision, SelectionPolicy, TrackingReport, choose_decision, summarize_tracking

__all__ = [
    "AutonomousBettingAgent",
    "EventResearchInput",
    "GradedPrediction",
    "PredictionLedgerRow",
    "PredictionResult",
    "ProbabilityCalibrator",
    "SelectionDecision",
    "SelectionPolicy",
    "TeamSnapshot",
    "TGRMLoop",
    "TrackingReport",
    "choose_decision",
    "fit_probability_calibrator",
    "parse_graded_csv",
    "summarize_tracking",
]
