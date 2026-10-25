from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from .report_product_layer import lang_code, safe_text

CONTEXT_UNAVAILABLE = {
    'en': 'Context unavailable.',
    'es': 'Contexto no disponible.',
}

API_MMA_KEY_MISSING = {
    'en': 'API-MMA key missing; structured MMA context skipped.',
    'es': 'Falta la clave de API-MMA; se omitió contexto estructurado de MMA.',
}
API_MMA_NO_MATCH = {
    'en': 'API-MMA did not return a matching fight/fighter.',
    'es': 'API-MMA no devolvió contexto del peleador.',
}
API_MMA_FAILED = {
    'en': 'API-MMA request failed; structured MMA context unavailable.',
    'es': 'Falló la solicitud de API-MMA; contexto estructurado de MMA no disponible.',
}
MMA_CONFIRM_NEWS = {
    'en': 'Confirm fight news, injuries, weight cut, and camp updates before betting.',
    'es': 'Confirma noticias, lesiones, corte de peso y campamento antes de apostar.',
}

SPORT_CONTEXT_FIELDS = {
    'baseball': ('pitching_matchup', 'bullpen_angle', 'recent_form', 'park_weather_angle', 'market_movement'),
    'basketball': ('pace_angle', 'rest_angle', 'injury_angle', 'matchup_style', 'recent_efficiency', 'market_movement'),
    'soccer': ('form_angle', 'home_away_angle', 'draw_risk', 'scoring_trend', 'total_goals_angle', 'market_pressure'),
    'mma': (
        'away_record', 'home_record', 'away_form', 'home_form', 'away_rank', 'home_rank',
        'away_fighter_profile', 'home_fighter_profile', 'away_recent_fights', 'home_recent_fights',
        'away_finish_rate', 'home_finish_rate', 'away_injuries', 'home_injuries',
        'away_player_notes', 'home_player_notes', 'matchup_style', 'matchup_notes',
    ),
    'boxing': (
        'away_record', 'home_record', 'away_form', 'home_form', 'away_fighter_profile', 'home_fighter_profile',
        'away_recent_fights', 'home_recent_fights', 'away_injuries', 'home_injuries',
        'away_player_notes', 'home_player_notes', 'matchup_style', 'matchup_notes',
    ),
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
    'fifa': 'soccer',
    'mma': 'mma',
    'ufc': 'mma',
    'combat': 'mma',
    'mixed martial arts': 'mma',
    'boxing': 'boxing',
}

_API_MMA_CACHE: dict[str, dict[str, Any]] = {}


def sport_family(value: Any) -> str:
    text = safe_text(value).lower()
    for token, family in ALIASES.items():
        if token in text:
            return family
    return text or 'other'


def _context_key(row: Mapping[str, Any]) -> str:
    event = safe_text(row.get('event') or row.get('event_name')).lower()
    sport = safe_text(row.get('sport')).lower()
    start = safe_text(row.get('commence_time') or row.get('event_date') or row.get('start_time')).lower()
    return '|'.join(part for part in (sport, event, start) if part)


def _secret(name: str) -> str:
    value = os.getenv(name)
    if value:
        return safe_text(value)
    try:
        import streamlit as st  # type: ignore
        value = st.secrets.get(name) if hasattr(st, 'secrets') else None
    except Exception:
        value = None
    return safe_text(value)


def _row_team(row: Mapping[str, Any], side: str) -> str:
    keys = (
        f'{side}_team', f'{side}_fighter', f'{side}_name', f'{side}_competitor',
        'away' if side == 'away' else 'home',
    )
    for key in keys:
        value = safe_text(row.get(key))
        if value:
            return value
    event = safe_text(row.get('event_name') or row.get('event') or row.get('game'))
    separators = (' vs ', ' v ', ' at ', ' @ ')
    for sep in separators:
        if sep in event.lower():
            parts = re_split_case_insensitive(event, sep)
            if len(parts) >= 2:
                return safe_text(parts[0] if side == 'away' else parts[1])
    return ''


def re_split_case_insensitive(text: str, sep: str) -> list[str]:
    lower = text.lower()
    marker = sep.lower()
    pos = lower.find(marker)
    if pos < 0:
        return [text]
    return [text[:pos].strip(), text[pos + len(sep):].strip()]


def _all_strings(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(item, (Mapping, list, tuple)):
                out.extend(_all_strings(item))
            else:
                txt = safe_text(item)
                if txt:
                    out.append(txt)
    elif isinstance(value, (list, tuple)):
        for item in value:
            out.extend(_all_strings(item))
    else:
        txt = safe_text(value)
        if txt:
            out.append(txt)
    return out


def _flatten_dicts(value: Any) -> list[Mapping[str, Any]]:
    out: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        out.append(value)
        for item in value.values():
            out.extend(_flatten_dicts(item))
    elif isinstance(value, list):
        for item in value:
            out.extend(_flatten_dicts(item))
    return out


def _api_response(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        if isinstance(payload.get('response'), (list, dict)):
            return payload['response']
        if isinstance(payload.get('data'), (list, dict)):
            return payload['data']
        if isinstance(payload.get('results'), (list, dict)):
            return payload['results']
    return payload


def _name_match(item: Any, *names: str) -> bool:
    haystack = ' '.join(_all_strings(item)).lower()
    return all(name and name.lower() in haystack for name in names)


def _pick_match(payload: Any, away: str, home: str) -> Mapping[str, Any] | None:
    response = _api_response(payload)
    candidates = response if isinstance(response, list) else [response]
    for item in candidates:
        if isinstance(item, Mapping) and _name_match(item, away, home):
            return item
    for item in _flatten_dicts(response):
        if _name_match(item, away, home):
            return item
    return None


def _find_fighter(payload: Any, name: str) -> Mapping[str, Any] | None:
    for item in _flatten_dicts(_api_response(payload)):
        item_name = safe_text(item.get('name') or item.get('fighter') or item.get('full_name') or item.get('fullname'))
        if name and item_name and name.lower() in item_name.lower():
            return item
        if name and _name_match(item, name):
            return item
    return None


def _record_from(obj: Mapping[str, Any]) -> str:
    for key in ('record', 'pro_record', 'mma_record', 'stats_record'):
        value = safe_text(obj.get(key))
        if value:
            return value
    wins = safe_text(obj.get('wins') or obj.get('win'))
    losses = safe_text(obj.get('losses') or obj.get('loss'))
    draws = safe_text(obj.get('draws') or obj.get('draw'))
    if wins or losses:
        return '-'.join(part for part in (wins or '0', losses or '0', draws) if part != '')
    return ''


def _rank_from(obj: Mapping[str, Any]) -> str:
    for key in ('rank', 'ranking', 'position', 'standing'):
        value = safe_text(obj.get(key))
        if value:
            return value
    return ''


def _profile_from(obj: Mapping[str, Any]) -> str:
    bits: list[str] = []
    for label, keys in (
        ('Stance', ('stance',)), ('Height', ('height',)), ('Reach', ('reach',)),
        ('Weight', ('weight', 'weight_class')), ('Age', ('age',)), ('Country', ('country', 'nationality')),
    ):
        for key in keys:
            value = safe_text(obj.get(key))
            if value:
                bits.append(f'{label}: {value}')
                break
    return ' · '.join(bits[:4])


def _finish_rate_from(obj: Mapping[str, Any]) -> str:
    for key in ('finish_rate', 'ko_rate', 'submission_rate', 'finishes'):
        value = safe_text(obj.get(key))
        if value:
            return value
    return ''


def _form_from(obj: Mapping[str, Any]) -> str:
    for key in ('form', 'recent_form', 'last_fights', 'recent_fights', 'last_5'):
        value = safe_text(obj.get(key))
        if value:
            return value
    return ''


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
class ApiMmaContextProvider(ContextProvider):
    base_url: str | None = None
    timeout_seconds: float = 8.0

    def _api_key(self) -> str:
        for key in ('API_MMA_KEY', 'APISPORTS_API_KEY', 'API_SPORTS_KEY', 'API_FOOTBALL_KEY'):
            value = _secret(key)
            if value:
                return value
        return ''

    def _base_url(self) -> str:
        configured = self.base_url or _secret('API_MMA_BASE_URL')
        return configured.rstrip('/') if configured else 'https://v1.mma.api-sports.io'

    def _api_get(self, path: str, params: Mapping[str, str]) -> dict[str, Any]:
        base = self._base_url()
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v})
        url = f'{base}{path}' + (f'?{query}' if query else '')
        cache_key = url
        if cache_key in _API_MMA_CACHE:
            return _API_MMA_CACHE[cache_key]
        request = urllib.request.Request(url, headers={'x-apisports-key': self._api_key(), 'Accept': 'application/json'})
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:  # nosec - URL is controlled by config/default API host.
            payload = json.loads(response.read().decode('utf-8'))
        if isinstance(payload, dict):
            _API_MMA_CACHE[cache_key] = payload
            return payload
        return {}

    def _unavailable(self, reason: str, *, configured: bool, called: bool, matched: bool = False) -> dict[str, str]:
        return {
            'api_mma_configured': str(configured).lower(),
            'api_mma_called': str(called).lower(),
            'api_mma_match_found': str(matched).lower(),
            'api_mma_unavailable_reason': reason,
            'matchup_notes': reason,
            'away_player_notes': MMA_CONFIRM_NEWS[lang_code(self.language)],
            'home_player_notes': MMA_CONFIRM_NEWS[lang_code(self.language)],
        }

    def lookup(self, row: Mapping[str, Any]) -> dict[str, str]:
        if sport_family(row.get('sport') or row.get('league')) != 'mma':
            return {}
        code = lang_code(self.language)
        api_key = self._api_key()
        if not api_key:
            return self._unavailable(API_MMA_KEY_MISSING[code], configured=False, called=False)
        away = _row_team(row, 'away')
        home = _row_team(row, 'home')
        event = safe_text(row.get('event_name') or row.get('event') or row.get('game'))
        date = safe_text(row.get('commence_time') or row.get('event_date') or row.get('start_time'))[:10]
        try:
            fight_payloads = []
            for params in ({'search': event}, {'date': date} if date else {}, {'fighter': away}, {'fighter': home}):
                if any(params.values()):
                    fight_payloads.append(self._api_get('/fights', params))
            match = None
            for payload in fight_payloads:
                match = _pick_match(payload, away, home)
                if match:
                    break
            away_payload = self._api_get('/fighters', {'search': away}) if away else {}
            home_payload = self._api_get('/fighters', {'search': home}) if home else {}
        except Exception:
            return self._unavailable(API_MMA_FAILED[code], configured=True, called=True)

        away_fighter = _find_fighter(away_payload, away) or (_find_fighter(match or {}, away) if match else None)
        home_fighter = _find_fighter(home_payload, home) or (_find_fighter(match or {}, home) if match else None)
        if not match and not away_fighter and not home_fighter:
            return self._unavailable(API_MMA_NO_MATCH[code], configured=True, called=True)

        out: dict[str, str] = {
            'api_mma_configured': 'true',
            'api_mma_called': 'true',
            'api_mma_match_found': str(bool(match or away_fighter or home_fighter)).lower(),
        }
        for prefix, fighter in (('away', away_fighter), ('home', home_fighter)):
            if not fighter:
                continue
            record = _record_from(fighter)
            rank = _rank_from(fighter)
            profile = _profile_from(fighter)
            form = _form_from(fighter)
            finish_rate = _finish_rate_from(fighter)
            if record:
                out[f'{prefix}_record'] = record
            if rank:
                out[f'{prefix}_rank'] = rank
            if profile:
                out[f'{prefix}_fighter_profile'] = profile
                out[f'{prefix}_player_notes'] = profile
            if form:
                out[f'{prefix}_form'] = form
                out[f'{prefix}_recent_fights'] = form
            if finish_rate:
                out[f'{prefix}_finish_rate'] = finish_rate
        if match:
            venue = safe_text(match.get('venue') or match.get('arena') or match.get('location'))
            status = safe_text(match.get('status') or match.get('stage'))
            promotion = safe_text(match.get('league') or match.get('promotion') or match.get('organization'))
            notes = [x for x in (promotion, venue, status) if x]
            if notes:
                out['matchup_notes'] = ' · '.join(notes[:3])
            out['matchup_style'] = safe_text(match.get('matchup_style') or match.get('category') or match.get('weight_class'))
        if 'matchup_notes' not in out:
            out['matchup_notes'] = MMA_CONFIRM_NEWS[code]
        summary_bits = []
        for key in ('away_record', 'home_record', 'away_form', 'home_form', 'matchup_style', 'matchup_notes'):
            if out.get(key):
                summary_bits.append(out[key])
        if summary_bits:
            out['sports_context_summary'] = ' · '.join(summary_bits[:4])
            out['game_preview'] = out['sports_context_summary']
        return out


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


def default_providers(language: str = 'en') -> list[ContextProvider]:
    return [ColumnContextProvider(language=language), ApiMmaContextProvider(language=language), JsonContextProvider(language=language)]


def build_context(row: Mapping[str, Any], *, language: str = 'en', providers: list[ContextProvider] | None = None) -> dict[str, str]:
    providers = providers or default_providers(language)
    merged: dict[str, str] = {}
    for provider in providers:
        for key, value in provider.lookup(row).items():
            if safe_text(value) and not safe_text(merged.get(key)):
                merged[key] = safe_text(value)
    return merged


def context_summary(row: Mapping[str, Any], *, language: str = 'en', providers: list[ContextProvider] | None = None) -> str:
    code = lang_code(language)
    family = sport_family(row.get('sport'))
    context = build_context(row, language=language, providers=providers)
    if context.get('sports_context_summary'):
        return context['sports_context_summary']
    fields = SPORT_CONTEXT_FIELDS.get(family, ())
    labels = {
        'en': {
            'pitching_matchup': 'Pitching', 'bullpen_angle': 'Bullpen', 'recent_form': 'Recent form', 'park_weather_angle': 'Park/weather',
            'market_movement': 'Market movement', 'pace_angle': 'Pace', 'rest_angle': 'Rest', 'injury_angle': 'Injuries',
            'matchup_style': 'Matchup style', 'recent_efficiency': 'Recent efficiency', 'form_angle': 'Form', 'home_away_angle': 'Home/away',
            'draw_risk': 'Draw risk', 'scoring_trend': 'Scoring trend', 'total_goals_angle': 'Total goals', 'market_pressure': 'Market pressure',
            'away_record': 'Away record', 'home_record': 'Home record', 'away_form': 'Away form', 'home_form': 'Home form',
            'away_rank': 'Away rank', 'home_rank': 'Home rank', 'away_fighter_profile': 'Away profile', 'home_fighter_profile': 'Home profile',
            'away_recent_fights': 'Away recent fights', 'home_recent_fights': 'Home recent fights', 'away_finish_rate': 'Away finish rate',
            'home_finish_rate': 'Home finish rate', 'away_injuries': 'Away injuries', 'home_injuries': 'Home injuries',
            'away_player_notes': 'Away notes', 'home_player_notes': 'Home notes', 'matchup_notes': 'Matchup notes',
        },
        'es': {
            'pitching_matchup': 'Abridores', 'bullpen_angle': 'Bullpen', 'recent_form': 'Forma reciente', 'park_weather_angle': 'Parque/clima',
            'market_movement': 'Movimiento del mercado', 'pace_angle': 'Ritmo', 'rest_angle': 'Descanso', 'injury_angle': 'Lesiones',
            'matchup_style': 'Estilo del duelo', 'recent_efficiency': 'Eficiencia reciente', 'form_angle': 'Forma', 'home_away_angle': 'Local/visita',
            'draw_risk': 'Riesgo de empate', 'scoring_trend': 'Tendencia de goles', 'total_goals_angle': 'Total de goles', 'market_pressure': 'Presión del mercado',
            'away_record': 'Récord visitante', 'home_record': 'Récord local', 'away_form': 'Forma visitante', 'home_form': 'Forma local',
            'away_rank': 'Ranking visitante', 'home_rank': 'Ranking local', 'away_fighter_profile': 'Perfil visitante', 'home_fighter_profile': 'Perfil local',
            'away_recent_fights': 'Peleas recientes visitante', 'home_recent_fights': 'Peleas recientes local', 'away_finish_rate': 'Finalizaciones visitante',
            'home_finish_rate': 'Finalizaciones local', 'away_injuries': 'Lesiones visitante', 'home_injuries': 'Lesiones local',
            'away_player_notes': 'Notas visitante', 'home_player_notes': 'Notas local', 'matchup_notes': 'Notas del duelo',
        },
    }
    parts = []
    for field in fields:
        value = context.get(field)
        if value:
            parts.append(f"{labels[code].get(field, field)}: {value}")
    return ' · '.join(parts[:4]) if parts else CONTEXT_UNAVAILABLE[code]


def enrich_sports_context(frame: pd.DataFrame, *, language: str = 'en', allow_provider_refresh: bool = False) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame
    out = frame.copy()
    summaries: list[str] = []
    contexts = []
    for row in out.to_dict('records'):
        providers = None if allow_provider_refresh else [ColumnContextProvider(language=language), JsonContextProvider(language=language)]
        context = build_context(row, language=language, providers=providers)
        contexts.append(context)
        enriched_row = {**row, **context}
        summaries.append(context_summary(enriched_row, language=language, providers=providers))
    for context in contexts:
        for key, value in context.items():
            if key not in out.columns:
                out[key] = ''
            mask = out[key].map(lambda x: not safe_text(x))
            out.loc[mask, key] = value
    out['report_sports_context_summary'] = summaries
    out['report_sports_context_summary_language'] = lang_code(language)
    if 'sports_context_summary' not in out.columns:
        out['sports_context_summary'] = ''
    if 'sports_context_summary_language' not in out.columns:
        out['sports_context_summary_language'] = ''
    missing = out['sports_context_summary'].map(lambda value: not safe_text(value))
    out.loc[missing, 'sports_context_summary'] = pd.Series(summaries, index=out.index)[missing]
    out.loc[missing, 'sports_context_summary_language'] = lang_code(language)
    out['sports_context_available'] = out['sports_context_summary'].ne(CONTEXT_UNAVAILABLE[lang_code(language)])
    return out
