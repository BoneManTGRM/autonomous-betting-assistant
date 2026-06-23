from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from .report_product_layer import MagazineBrand, grouped_report, safe_text

REPO_ROOT = Path(__file__).resolve().parents[1]
FEED_ROOT = REPO_ROOT / 'data' / 'report_feeds'

CONSUMER_FIELDS = (
    'event', 'sport', 'public_sport', 'public_pick', 'recommended_action', 'confidence_tier', 'risk_tier',
    'market_read', 'why_it_matters', 'game_preview', 'sports_context_summary', 'report_lane', 'publish_ready'
)
ANALYST_FIELDS = CONSUMER_FIELDS + (
    'decimal_price', 'model_probability', 'market_probability', 'model_market_edge', 'expected_value_per_unit',
    'odds_verified', 'proof_id', 'locked_at_utc', 'odds_source', 'bookmaker', 'model_probability_source', 'tennis_blocked'
)


def normalize_id(value: Any) -> str:
    text = safe_text(value).lower() or 'default'
    return ''.join(ch if ch.isalnum() or ch in {'_', '-'} else '_' for ch in text)[:80]


def _brand_dict(brand: MagazineBrand | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(brand, Mapping):
        return dict(brand)
    if is_dataclass(brand):
        return asdict(brand)
    return {}


def _public_feed_id(workspace_id: str, mode: str, generated_at: str, public: bool) -> str:
    base = f'{workspace_id}|{mode}|{generated_at}'
    if not public:
        base += '|private'
    return hashlib.sha256(base.encode('utf-8')).hexdigest()[:20]


def _records(frame: pd.DataFrame, *, include_technical: bool) -> list[dict[str, Any]]:
    fields = ANALYST_FIELDS if include_technical else CONSUMER_FIELDS
    cols = [col for col in fields if col in frame.columns]
    if not cols:
        return []
    return frame[cols].fillna('').to_dict('records')


def build_app_feed(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any], *, mode: str = 'consumer', public: bool = False) -> dict[str, Any]:
    brand_data = _brand_dict(brand)
    workspace_id = normalize_id(brand_data.get('workspace_id'))
    generated_at = datetime.now(timezone.utc).isoformat()
    include_technical = mode in {'analyst', 'proof'} or safe_text(mode).lower().startswith('analyst')
    groups = grouped_report(cards)
    feed_id = _public_feed_id(workspace_id, mode, generated_at, public)
    return {
        'schema_version': 'aba-report-feed-v1',
        'feed_id': feed_id,
        'workspace_id': workspace_id,
        'visibility': 'public' if public else 'private',
        'mode': mode,
        'generated_at': generated_at,
        'brand': brand_data,
        'counts': {
            'best_plays': int(len(groups['best_plays'])),
            'watchlist': int(len(groups['watchlist'])),
            'no_play': int(len(groups['no_play'])),
            'publish_ready': int(cards.get('publish_ready', pd.Series(dtype=bool)).astype(bool).sum()) if cards is not None and not cards.empty else 0,
        },
        'groups': {
            'best_plays': _records(groups['best_plays'], include_technical=include_technical),
            'watchlist': _records(groups['watchlist'], include_technical=include_technical),
            'no_play': _records(groups['no_play'], include_technical=include_technical),
        },
        'notes': 'Consumer feeds omit technical pricing fields unless analyst/proof mode is selected.',
    }


def save_app_feed(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any], *, mode: str = 'consumer', public: bool = False) -> dict[str, Any]:
    feed = build_app_feed(cards, brand, mode=mode, public=public)
    workspace = normalize_id(feed['workspace_id'])
    folder = FEED_ROOT / workspace
    folder.mkdir(parents=True, exist_ok=True)
    latest = folder / 'latest.json'
    specific = folder / f"{feed['feed_id']}.json"
    text = json.dumps(feed, ensure_ascii=False, indent=2)
    latest.write_text(text, encoding='utf-8')
    specific.write_text(text, encoding='utf-8')
    feed['saved_paths'] = {'latest': str(latest), 'feed': str(specific)}
    return feed


def load_latest_feed(workspace_id: str) -> dict[str, Any]:
    path = FEED_ROOT / normalize_id(workspace_id) / 'latest.json'
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
