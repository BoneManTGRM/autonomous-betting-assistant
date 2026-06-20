from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from .row_normalizer import dedupe_frame, normalize_frame, safe_text

UNSUPPORTED_TENNIS_TERMS = {
    'tennis',
    'atp',
    'wta',
    'halle',
    'queen',
    "queen's",
    'german open',
    'nottingham',
    'berlin',
    'bad homburg',
    'eastbourne',
    'mallorca',
    'wimbledon',
    'roland garros',
    'us open tennis',
    'australian open',
}

SUPPORTED_PROOF_SPORT_HINTS = {
    'afl',
    'aussie rules',
    'baseball',
    'basketball',
    'cricket',
    'fifa',
    'football',
    'kbo',
    'mlb',
    'nfl',
    'nhl',
    'npb',
    'nrl',
    'rugby',
    'soccer',
    'wnba',
}

PROOF_STORE_KEYS = [
    'odds_lock_pro_locked_rows',
    'public_proof_dashboard_refresh_rows',
    'ara_latest_predictions',
]


def row_text(row: Mapping[str, Any]) -> str:
    fields = [
        row.get('sport'),
        row.get('sport_key'),
        row.get('league'),
        row.get('competition'),
        row.get('event'),
        row.get('market_type'),
        row.get('source_file'),
        row.get('odds_source'),
    ]
    return ' '.join(safe_text(value).lower() for value in fields if safe_text(value))


def unsupported_market_reason(row: Mapping[str, Any]) -> str:
    text = row_text(row)
    if not text:
        return 'missing_market_context'
    for term in sorted(UNSUPPORTED_TENNIS_TERMS, key=len, reverse=True):
        if term in text:
            return 'unsupported_tennis_market_no_odds_api'
    return ''


def is_supported_proof_market(row: Mapping[str, Any]) -> bool:
    return unsupported_market_reason(row) == ''


def mark_market_support(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    normalized = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if normalized.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for row in normalized.to_dict(orient='records'):
        item = dict(row)
        reason = unsupported_market_reason(item)
        item['market_supported_for_proof'] = not bool(reason)
        item['unsupported_market_reason'] = reason
        if reason:
            item['proof_tier'] = 'REJECT_UNSUPPORTED_MARKET'
            item['official_lock_ready'] = False
            existing = safe_text(item.get('lock_blockers'))
            blockers = [part.strip() for part in existing.split(';') if part.strip()]
            blockers.append(reason)
            item['lock_blockers'] = '; '.join(sorted(set(blockers)))
            item['public_confidence'] = 'Rejected'
            item['public_reason'] = 'Unsupported market for official proof: tennis odds API unavailable.'
        rows.append(item)
    return dedupe_frame(pd.DataFrame(rows))


def supported_only(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    marked = mark_market_support(frame)
    if marked.empty:
        return pd.DataFrame()
    return marked[marked['market_supported_for_proof'].fillna(False)].copy()


def unsupported_only(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    marked = mark_market_support(frame)
    if marked.empty:
        return pd.DataFrame()
    return marked[~marked['market_supported_for_proof'].fillna(False)].copy()


def proof_lane(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    marked = mark_market_support(frame)
    if marked.empty:
        return pd.DataFrame()
    official = marked[marked['market_supported_for_proof'].fillna(False)].copy()
    if 'proof_tier' not in official.columns:
        official['proof_tier'] = 'A_TEST'
    return official


def market_support_summary(frame: pd.DataFrame | list[dict[str, Any]]) -> dict[str, int]:
    marked = mark_market_support(frame)
    if marked.empty:
        return {'rows': 0, 'supported': 0, 'unsupported': 0, 'unsupported_tennis': 0}
    supported = int(marked['market_supported_for_proof'].fillna(False).sum())
    unsupported = int(len(marked) - supported)
    tennis = int(marked['unsupported_market_reason'].astype(str).eq('unsupported_tennis_market_no_odds_api').sum())
    return {'rows': int(len(marked)), 'supported': supported, 'unsupported': unsupported, 'unsupported_tennis': tennis}
