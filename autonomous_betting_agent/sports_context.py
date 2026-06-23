from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from .report_product_layer import lang_code, safe_text

CONTEXT_UNAVAILABLE = {
    'en': 'Context unavailable.',
    'es': 'Contexto no disponible.',
}

SPORT_CONTEXT_FIELDS = {
    'baseball': ('pitching_matchup', 'bullpen_angle', 'recent_form', 'park_weather_angle', 'market_movement'),
    'basketball': ('pace_angle', 'rest_angle', 'injury_angle', 'matchup_style', 'recent_efficiency', 'market_movement'),
    'soccer': ('form_angle', 'home_away_angle', 'draw_risk', 'scoring_trend', 'total_goals_angle', 'market_pressure'),
}

ALIASES = {
    'mlb': 'baseball',
    'baseball': 'baseball',
    'nba': 'basketball',
    'ncaab': 'basketball',
    'basketball': 'basketball',
    'soccer': 'soccer',
    'football': 'soccer',
    'epl': 'soccer',
    'liga': 'soccer',
}


def sport_family(value: Any) -> str:
    text = safe_text(value).lower()
    for token, family in ALIASES.items():
        if token in text:
            return family
    return text or 'other'


def _context_key(row: Mapping[str, Any]) -> str:
    event = safe_text(row.get('event')).lower()
    sport = safe_text(row.get('sport')).lower()
    start = safe_text(row.get('commence_time') or row.get('event_date') or row.get('start_time')).lower()
    return '|'.join(part for part in (sport, event, start) if part)


@dataclass
class ContextProvider:
    language: str = 'en'

    def lookup(self, row: Mapping[str, Any]) -> dict[str, str]:
        return {}


@dataclass
class ColumnContextProvider(ContextProvider):
    def lookup(self, row: Mapping[str, Any]) -> dict[str, str]:
        family = sport_family(row.get('sport'))
        fields = SPORT_CONTEXT_FIELDS.get(family, ())
        return {field: safe_text(row.get(field)) for field in fields if safe_text(row.get(field))}


@dataclass
class JsonContextProvider(ContextProvider):
    path: str | None = None

    def _payload(self) -> dict[str, Any]:
        configured = self.path or os.getenv('ABA_SPORTS_CONTEXT_JSON')
        if not configured:
            return {}
        try:
            data = json.loads(Path(configured).read_text(encoding='utf-8'))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def lookup(self, row: Mapping[str, Any]) -> dict[str, str]:
        payload = self._payload()
        if not payload:
            return {}
        keys = [_context_key(row), safe_text(row.get('event')).lower(), safe_text(row.get('event_id')).lower()]
        for key in keys:
            if key and isinstance(payload.get(key), dict):
                return {str(k): safe_text(v) for k, v in payload[key].items() if safe_text(v)}
        return {}


def build_context(row: Mapping[str, Any], *, language: str = 'en', providers: list[ContextProvider] | None = None) -> dict[str, str]:
    providers = providers or [ColumnContextProvider(language=language), JsonContextProvider(language=language)]
    merged: dict[str, str] = {}
    for provider in providers:
        merged.update(provider.lookup(row))
    return merged


def context_summary(row: Mapping[str, Any], *, language: str = 'en') -> str:
    code = lang_code(language)
    family = sport_family(row.get('sport'))
    context = build_context(row, language=language)
    fields = SPORT_CONTEXT_FIELDS.get(family, ())
    labels = {
        'en': {
            'pitching_matchup': 'Pitching', 'bullpen_angle': 'Bullpen', 'recent_form': 'Recent form', 'park_weather_angle': 'Park/weather',
            'market_movement': 'Market movement', 'pace_angle': 'Pace', 'rest_angle': 'Rest', 'injury_angle': 'Injuries',
            'matchup_style': 'Matchup style', 'recent_efficiency': 'Recent efficiency', 'form_angle': 'Form', 'home_away_angle': 'Home/away',
            'draw_risk': 'Draw risk', 'scoring_trend': 'Scoring trend', 'total_goals_angle': 'Total goals', 'market_pressure': 'Market pressure',
        },
        'es': {
            'pitching_matchup': 'Abridores', 'bullpen_angle': 'Bullpen', 'recent_form': 'Forma reciente', 'park_weather_angle': 'Parque/clima',
            'market_movement': 'Movimiento del mercado', 'pace_angle': 'Ritmo', 'rest_angle': 'Descanso', 'injury_angle': 'Lesiones',
            'matchup_style': 'Estilo del duelo', 'recent_efficiency': 'Eficiencia reciente', 'form_angle': 'Forma', 'home_away_angle': 'Local/visita',
            'draw_risk': 'Riesgo de empate', 'scoring_trend': 'Tendencia de goles', 'total_goals_angle': 'Total de goles', 'market_pressure': 'Presión del mercado',
        },
    }
    parts = []
    for field in fields:
        value = context.get(field)
        if value:
            parts.append(f"{labels[code].get(field, field)}: {value}")
    return ' · '.join(parts[:4]) if parts else CONTEXT_UNAVAILABLE[code]


def enrich_sports_context(frame: pd.DataFrame, *, language: str = 'en') -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame
    out = frame.copy()
    out['sports_context_summary'] = [context_summary(row, language=language) for row in out.to_dict('records')]
    out['sports_context_available'] = out['sports_context_summary'].ne(CONTEXT_UNAVAILABLE[lang_code(language)])
    return out
