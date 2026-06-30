from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

import pandas as pd

REQUIRED_REPORT_COLUMNS = [
    'event_id','event_key','duplicate_group_id','row_id','raw_input_hash','enrichment_input_hash','sport','league','event_date','start_time','home_team','away_team','normalized_home_team','normalized_away_team','selected_market','selected_pick','bookmaker','decimal_odds','american_odds','odds_source','odds_status','odds_last_refresh','odds_failure_reason','odds_market_sides_available','model_probability','model_probability_source','confidence_source','confidence_status','raw_implied_probability','no_vig_implied_probability','no_vig_status','edge','no_vig_edge','EV','ev_source','ev_status','fair_odds','target_odds','confidence_tier','recommendation_status','units','risk_label','risk_reasons','sportsdataio_event_id','sportsdataio_match_status','sportsdataio_failure_reason','api_football_fixture_id','api_football_match_status','api_football_failure_reason','weather_status','weather_summary','weather_failure_reason','news_status','news_summary','news_failure_reason','perplexity_status','perplexity_context','perplexity_failure_reason','context_source','context_status','context_failure_reason','injury_notes','team_snapshot_home','team_snapshot_away','matchup_notes','pro_bettor_evidence','reparodynamics_status','reparodynamics_notes','repair_flags','fallback_used','fallback_reason','cache_status','enrichment_status','data_freshness_status','last_api_refresh_time','report_run_id','report_source','field_provenance_json','source_trace_json','api_health_json'
]

API_KEY_NAMES = {
    'Odds API': ('ODDS_API_KEY','THE_ODDS_API_KEY'),
    'SportsDataIO': ('SPORTSDATAIO_API_KEY','SPORTS_DATA_IO_API_KEY','SPORTSDATA_API_KEY'),
    'API-Football': ('API_FOOTBALL_KEY','APIFOOTBALL_KEY'),
    'WeatherAPI': ('WEATHERAPI_KEY','WEATHER_API_KEY'),
    'NewsAPI': ('NEWSAPI_KEY','NEWS_API_KEY'),
    'Perplexity': ('PERPLEXITY_API_KEY','PPLX_API_KEY'),
}
PLACEHOLDER_PATTERNS = (
    'CONTEXT ' + 'UNAVAILABLE',
    'Simple news ' + 'aggregator',
    'Show ' + 'HN:',
    'No Live: ' + 'Odds',
    'uploaded/' + 'cached row',
)


def _txt(v: Any) -> str:
    if v is None:
        return ''
    try:
        if pd.isna(v):
            return ''
    except Exception:
        pass
    s = str(v).strip()
    return '' if s.lower() in {'','nan','none','null','n/a','na'} else s


def _num(v: Any) -> float | None:
    s = _txt(v).replace('%','').replace(',','')
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _first(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if _txt(row.get(key)):
            return row.get(key)
    return ''


def _norm(v: Any) -> str:
    s = _txt(v).lower()
    try:
        import unicodedata
        s = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode('ascii')
    except Exception:
        pass
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())


def _hash(v: Any) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, default=str).encode('utf-8')).hexdigest()


def _frame(v: Any) -> pd.DataFrame:
    if isinstance(v, pd.DataFrame):
        return v.copy()
    if v is None:
        return pd.DataFrame()
    try:
        return pd.DataFrame(v)
    except Exception:
        return pd.DataFrame()


def _secret(names: Iterable[str]) -> str:
    try:
        import streamlit as st  # type: ignore
        for name in names:
            try:
                val = str(st.secrets.get(name, '') or '').strip()
            except Exception:
                val = ''
            if val:
                return val
    except Exception:
        pass
    for name in names:
        val = os.getenv(name, '').strip()
        if val:
            return val
    return ''


def _mask(v: str) -> str:
    return '' if not v else (v[:4] + '...' + v[-4:] if len(v) > 8 else v[:2] + '...' + v[-2:])


def check_api_health(mask_secrets: bool = True) -> dict[str, Any]:
    out = {}
    for label, names in API_KEY_NAMES.items():
        val = _secret(names)
        out[label] = {'status': 'CONFIGURED' if val else 'API_KEY_MISSING', 'key_loaded': bool(val), 'key': _mask(val) if mask_secrets else val}
    return out


def _teams(row: Mapping[str, Any]) -> tuple[str, str]:
    away = _txt(_first(row,'away_team','team_a','team1'))
    home = _txt(_first(row,'home_team','team_b','team2'))
    event = _txt(_first(row,'event','game','event_name','matchup'))
    if not (away and home) and event:
        for sep in (' at ',' vs ',' VS ',' v ',' @ '):
            if sep in event:
                left, right = event.split(sep, 1)
                return left.strip(), right.strip()
    return away, home
