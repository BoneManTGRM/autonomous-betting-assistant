"""Autonomous Betting Agent package."""

from __future__ import annotations

import math
from dataclasses import dataclass

APP_NAME = 'ABA Signal Pro'
APP_TAGLINE = 'Powered by Reparodynamics'
PREDICTOR_TOOL_NAME = 'Pro Predictor'


@dataclass(frozen=True)
class TeamSnapshot:
    name: str = ''
    rating: float = 1500.0
    recent_form: float = 0.0
    injury_impact: float = 0.0
    rest_advantage: float = 0.0
    matchup_edge: float = 0.0
    data_completeness: float = 1.0
    source_count: int = 0


@dataclass(frozen=True)
class EventResearchInput:
    sport: str
    event_name: str
    home: TeamSnapshot
    away: TeamSnapshot
    neutral_site: bool = False


@dataclass(frozen=True)
class AgentAnalysisResult:
    home_probability: float
    away_probability: float
    favored_side: str


class AutonomousBettingAgent:
    def analyze(self, event: EventResearchInput) -> AgentAnalysisResult:
        home_score = self._team_score(event.home)
        away_score = self._team_score(event.away)
        if not event.neutral_site:
            home_score += 0.03
        diff = home_score - away_score
        if abs(diff) < 1e-12:
            home_probability = 0.5
        else:
            home_probability = 1.0 / (1.0 + math.exp(-diff))
        home_probability = min(0.99, max(0.01, home_probability))
        away_probability = 1.0 - home_probability
        favored_side = event.home.name if home_probability >= away_probability else event.away.name
        return AgentAnalysisResult(
            home_probability=round(home_probability, 6),
            away_probability=round(away_probability, 6),
            favored_side=favored_side,
        )

    @staticmethod
    def _team_score(team: TeamSnapshot) -> float:
        return (
            (float(team.rating) - 1500.0) / 400.0
            + float(team.recent_form)
            - float(team.injury_impact)
            + float(team.rest_advantage)
            + float(team.matchup_edge)
            + min(max(float(team.data_completeness), 0.0), 1.0) * 0.02
            + min(max(int(team.source_count), 0), 10) * 0.003
        )


def _install_price_normalizer() -> None:
    try:
        from dataclasses import replace
        from . import live_odds
    except Exception:
        return
    if getattr(live_odds, '_aba_price_normalizer_v1', False):
        return
    original = live_odds.summarize_event

    def normalized_summary(event):
        summary = original(event)
        if summary is None:
            return None
        rows = []
        for outcome in summary.outcomes:
            try:
                avg = float(outcome.average_price)
            except (TypeError, ValueError):
                avg = None
            if avg is not None and avg > 1.0:
                rows.append(replace(outcome, best_price=avg, best_bookmaker='consensus_average'))
            else:
                rows.append(outcome)
        return replace(summary, outcomes=rows)

    live_odds.summarize_event = normalized_summary
    live_odds._aba_price_normalizer_v1 = True


def _install_adaptive_learning_area_key_normalizer() -> None:
    try:
        from . import adaptive_learning
    except Exception:
        return
    if getattr(adaptive_learning, '_aba_area_key_normalizer_v1', False):
        return

    def normalized_feature_key(area_type: str, value: str) -> str:
        area = str(area_type or '').strip().lower().replace('-', '_').replace(' ', '_')
        return f'{area}:{value}'.lower()

    adaptive_learning._feature_key = normalized_feature_key
    adaptive_learning._aba_area_key_normalizer_v1 = True


def _install_magazine_renderer_patches() -> None:
    try:
        from .magazine_book_export_patches import install
    except Exception:
        return
    install()


def _install_mexico_spanish_terms() -> None:
    try:
        from . import report_product_layer as rpl
    except Exception:
        return
    if getattr(rpl, '_aba_mexico_spanish_terms_v2', False):
        return
    try:
        rpl.COUNTRY_ES.update({
            'qatar': 'Qatar',
            'bosnia & herzegovina': 'Bosnia y Herzegovina',
            'bosnia and herzegovina': 'Bosnia y Herzegovina',
            'bosnia-herzegovina': 'Bosnia y Herzegovina',
            'netherlands': 'Países Bajos',
            'ivory coast': 'Costa de Marfil',
            'iraq': 'Irak',
            'france': 'Francia',
            'germany': 'Alemania',
            'tunisia': 'Túnez',
        })
        rpl.SPORT_ES.update({
            'boxing': 'Boxeo',
            'mma': 'MMA',
            'soccer': 'Fútbol',
            'fifa world cup': 'Copa Mundial FIFA',
            'baseball': 'Béisbol',
            'basketball': 'Baloncesto',
            'football': 'Fútbol americano',
            'tennis': 'Tenis',
        })
        rpl.VALUE_ES.update({
            'Odds': 'Momio',
            'ODDS': 'MOMIO',
            'Price Watch': 'Seguimiento de momio',
            'Price Watch / Research': 'Seguimiento de momio / investigación',
            'Negative at listed odds': 'Negativo con el momio actual',
            'Missing or unverified odds': 'Momios faltantes o no verificados',
            'Thin edge favorite': 'Ventaja delgada',
            'THIN EDGE FAVORITE': 'VENTAJA DELGADA',
            'Research Only': 'Investigación',
            'RESEARCH ONLY': 'INVESTIGACIÓN',
            'Watchlist Only': 'Seguimiento',
            'WATCHLIST ONLY': 'SEGUIMIENTO',
            'Low': 'Bajo',
            'Medium': 'Medio',
            'High': 'Alto',
            'LOW': 'BAJO',
            'MEDIUM': 'MEDIO',
            'HIGH': 'ALTO',
            'Review': 'Revisar',
            'REVIEW': 'REVISAR',
        })
        original_value_text = rpl.value_text

        def mexico_value_text(value, language='en'):
            text = original_value_text(value, language)
            if rpl.lang_code(language) != 'es' or not text:
                return text
            return (
                text.replace('Seguimiento de precio', 'Seguimiento de momio')
                .replace('cuota actual', 'momio actual')
                .replace('Cuotas', 'Momios')
                .replace('cuotas', 'momios')
                .replace('Cuota', 'Momio')
                .replace('cuota', 'momio')
            )

        rpl.value_text = mexico_value_text
        original_market_read = rpl.market_read

        def mexico_market_read(odds_ok, model_prob, market_prob, edge, language='en'):
            text = original_market_read(odds_ok, model_prob, market_prob, edge, language)
            if rpl.lang_code(language) != 'es':
                return text
            return text.replace('Cuotas', 'Momios').replace('cuotas', 'momios').replace('cuota', 'momio')

        rpl.market_read = mexico_market_read
        rpl._aba_mexico_spanish_terms_v2 = True
    except Exception:
        return


def _install_chain_notes() -> None:
    try:
        from . import chain_notes
    except Exception:
        return
    try:
        chain_notes.install()
    except Exception:
        return


def _install_magazine_value_safety() -> None:
    try:
        from .magazine_value_safety_patch import install
    except Exception:
        return
    try:
        install()
    except Exception:
        return


_install_price_normalizer()
_install_adaptive_learning_area_key_normalizer()
_install_magazine_renderer_patches()
_install_mexico_spanish_terms()
_install_chain_notes()
_install_magazine_value_safety()
