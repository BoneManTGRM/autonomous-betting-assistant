from __future__ import annotations

import math
from dataclasses import asdict
from typing import Dict, List, Tuple

from .cycle_log import CycleLog
from .learning import ProbabilityCalibrator
from .market_math import normalize_two_way_market, unit_edge
from .models import EventResearchInput, PredictionResult, TeamSnapshot


class AutonomousBettingAgent:
    DEFAULT_WEIGHTS: Dict[str, float] = {
        "rating": 1.00,
        "recent_form": 0.32,
        "injury_impact": 0.40,
        "rest_advantage": 0.18,
        "matchup_edge": 0.30,
        "weather_fit": 0.10,
        "home_advantage": 0.18,
    }

    def __init__(self, weights: Dict[str, float] | None = None, calibrator: ProbabilityCalibrator | None = None) -> None:
        self.weights = dict(self.DEFAULT_WEIGHTS)
        if weights:
            unknown = set(weights) - set(self.DEFAULT_WEIGHTS)
            if unknown:
                raise ValueError(f"Unknown weights: {sorted(unknown)}")
            self.weights.update({key: float(value) for key, value in weights.items()})
        self.calibrator = calibrator

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    @staticmethod
    def _sigmoid(value: float) -> float:
        if value >= 0.0:
            z = math.exp(-value)
            return 1.0 / (1.0 + z)
        z = math.exp(value)
        return z / (1.0 + z)

    def _validate_team(self, team: TeamSnapshot) -> List[str]:
        warnings: List[str] = []
        bounded_fields = {
            "recent_form": (-1.0, 1.0),
            "injury_impact": (0.0, 1.0),
            "rest_advantage": (-1.0, 1.0),
            "matchup_edge": (-1.0, 1.0),
            "weather_fit": (-1.0, 1.0),
            "data_completeness": (0.0, 1.0),
        }
        raw = asdict(team)
        for field_name, (low, high) in bounded_fields.items():
            value = float(raw[field_name])
            if value < low or value > high:
                warnings.append(f"{team.name}: {field_name} is outside the expected range and was clamped.")
        return warnings

    def _signal_difference(self, home: TeamSnapshot, away: TeamSnapshot, neutral_site: bool) -> Tuple[float, Dict[str, float]]:
        rating_diff = self._clamp((home.rating - away.rating) / 400.0, -3.0, 3.0)
        recent_form = self._clamp(home.recent_form, -1.0, 1.0) - self._clamp(away.recent_form, -1.0, 1.0)
        injury = self._clamp(away.injury_impact, 0.0, 1.0) - self._clamp(home.injury_impact, 0.0, 1.0)
        rest = self._clamp(home.rest_advantage, -1.0, 1.0) - self._clamp(away.rest_advantage, -1.0, 1.0)
        matchup = self._clamp(home.matchup_edge, -1.0, 1.0) - self._clamp(away.matchup_edge, -1.0, 1.0)
        weather = self._clamp(home.weather_fit, -1.0, 1.0) - self._clamp(away.weather_fit, -1.0, 1.0)
        home_advantage = 0.0 if neutral_site else 1.0
        contributions = {
            "rating": self.weights["rating"] * rating_diff,
            "recent_form": self.weights["recent_form"] * recent_form,
            "injury_impact": self.weights["injury_impact"] * injury,
            "rest_advantage": self.weights["rest_advantage"] * rest,
            "matchup_edge": self.weights["matchup_edge"] * matchup,
            "weather_fit": self.weights["weather_fit"] * weather,
            "home_advantage": self.weights["home_advantage"] * home_advantage,
        }
        return sum(contributions.values()), contributions

    @staticmethod
    def _evidence(contributions: Dict[str, float], home_name: str, away_name: str) -> List[str]:
        evidence: List[str] = []
        labels = {
            "rating": "baseline rating",
            "recent_form": "recent form",
            "injury_impact": "injury availability",
            "rest_advantage": "rest and schedule",
            "matchup_edge": "matchup profile",
            "weather_fit": "weather or conditions",
            "home_advantage": "home advantage",
        }
        for key, value in sorted(contributions.items(), key=lambda item: abs(item[1]), reverse=True):
            if abs(value) < 0.01:
                continue
            side = home_name if value > 0 else away_name
            evidence.append(f"{labels[key].capitalize()} favors {side}.")
        return evidence or ["No material edge was produced by the supplied signals."]

    def analyze(self, event: EventResearchInput) -> PredictionResult:
        log = CycleLog()
        log.add("TEST", [f"Loaded event: {event.event_name}", f"Sport: {event.sport}"])
        warnings = self._validate_team(event.home) + self._validate_team(event.away)
        log.add("DETECT", warnings or ["No input-range issues detected."])
        score, contributions = self._signal_difference(event.home, event.away, event.neutral_site)
        uncalibrated_home_probability = self._sigmoid(score)
        if self.calibrator is not None:
            home_probability = self.calibrator.apply(uncalibrated_home_probability)
            calibration_note = f"Applied learned probability calibration from {self.calibrator.events_trained} graded events."
        else:
            home_probability = uncalibrated_home_probability
            calibration_note = "No learned calibration state was supplied."
        away_probability = 1.0 - home_probability
        completeness = (self._clamp(event.home.data_completeness, 0.0, 1.0) + self._clamp(event.away.data_completeness, 0.0, 1.0)) / 2.0
        source_strength = min(max(event.home.source_count, 0) + max(event.away.source_count, 0), 20) / 20.0
        separation = abs(home_probability - away_probability)
        if completeness < 0.7:
            warnings.append("Input completeness is below 70%; the probability is provisional.")
        if source_strength < 0.3:
            warnings.append("Few independent sources were supplied; evidence diversity is weak.")
        if separation < 0.08:
            warnings.append("The event is close to a coin flip under the current inputs.")
        if self.calibrator is not None:
            warnings.append(calibration_note)
        log.add("REPAIR", ["Converted normalized research factors into an auditable probability score.", "Separated model probability from market probability.", calibration_note])
        confidence = self._clamp(0.55 * completeness + 0.25 * source_strength + 0.20 * separation, 0.0, 1.0)
        market_home, market_away, overround = normalize_two_way_market(event.home_market_price, event.away_market_price)
        home_edge = None if market_home is None else home_probability - market_home
        away_edge = None if market_away is None else away_probability - market_away
        favored_side = event.home.name if home_probability >= away_probability else event.away.name
        log.add("VERIFY", ["Computed confidence and market comparison."], {"confidence": confidence, "separation": separation})
        warnings.append("Research output only: probabilities are estimates and require backtesting before real-world use.")
        return PredictionResult(
            event_name=event.event_name,
            sport=event.sport,
            home_team=event.home.name,
            away_team=event.away.name,
            home_probability=home_probability,
            away_probability=away_probability,
            confidence=confidence,
            favored_side=favored_side,
            evidence=self._evidence(contributions, event.home.name, event.away.name),
            warnings=warnings,
            market={
                "home_no_vig_probability": market_home,
                "away_no_vig_probability": market_away,
                "overround": overround,
                "home_model_edge": home_edge,
                "away_model_edge": away_edge,
                "home_unit_edge": unit_edge(home_probability, event.home_market_price),
                "away_unit_edge": unit_edge(away_probability, event.away_market_price),
            },
            diagnostics={
                "raw_score": score,
                **contributions,
                "data_completeness": completeness,
                "source_strength": source_strength,
                "uncalibrated_home_probability": uncalibrated_home_probability,
                "calibration_intercept": self.calibrator.intercept if self.calibrator is not None else 0.0,
                "calibration_slope": self.calibrator.slope if self.calibrator is not None else 1.0,
            },
            tgrm=log.to_dict(),
        )
