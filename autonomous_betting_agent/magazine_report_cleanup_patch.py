from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

_PATCH_VERSION = 'magazine_cleanup_pregame_truth_v2'

BAD_TOKENS = (
    'api-mma', 'api mma', 'matching fight', 'fighter data', 'weight cut', 'camp updates',
    'no provider event id', 'sdio checked', 'no sdio event id', 'no fixture match',
    'no match returned', 'simple news aggregator', 'show hn', 'uploaded/cached row',
    'not returned for this event', 'data not returned', 'player data not returned',
)
POSTGAME_TOKENS = (
    ' ended ', ' defeated ', ' beat ', ' won ', ' lost ', ' victory ', ' final score',
    ' confirmed ', ' confirming ', ' goals from ', ' goal from ', ' match was won',
)
MOJIBAKE = {
    'Ã¡': 'á', 'Ã©': 'é', 'Ã­': 'í', 'Ã³': 'ó', 'Ãº': 'ú', 'Ã±': 'ñ', 'Ã¼': 'ü',
    'Ã': '', 'Â': '', 'â€™': "'", 'â€œ': '"', 'â€�': '"', 'â€“': '-', 'â€”': '-',
    'â€¦': '…', '�': '',
}


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, 'to_dict'):
        data = value.to_dict()
        return dict(data) if isinstance(data, Mapping) else {}
    return dict(getattr(value, '__dict__', {}) or {})


def _text(value: Any) -> str:
    if value is None:
        return ''
    text = str(value)
    for old, new in MOJIBAKE.items():
        text = text.replace(old, new)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def _sport(row: Mapping[str, Any]) -> str:
    text = ' '.join(str(row.get(k, '')) for k in ('sport', 'league', 'event', 'event_name', 'matchup')).lower()
    if any(token in text for token in ('mma', 'ufc', 'boxing', 'fighter')):
        return 'combat'
    if any(token in text for token in ('soccer', 'fifa', 'football', 'world cup', 'uefa', 'liga')):
        return 'soccer'
    return 'generic'


def _bad(value: Any, row: Mapping[str, Any]) -> bool:
    text = f" {_text(value).lower()} "
    if not text.strip():
        return True
    if any(token in text for token in POSTGAME_TOKENS):
        return True
    if _sport(row) != 'combat' and any(token in text for token in ('api-mma', 'api mma', 'matching fight', 'fighter data', 'weight cut', 'camp updates')):
        return True
    return any(token in text for token in BAD_TOKENS)


def _split(value: Any) -> list[str]:
    text = _text(value)
    if not text:
        return []
    return [_text(part).strip(' .•-') for part in re.split(r'(?:\n|•|;|\s+-\s+|(?<=[.!?])\s+)', text) if _text(part).strip(' .•-')]


def _short(text: str, max_chars: int = 82) -> str:
    text = _text(text)
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars - 1].rsplit(' ', 1)[0].strip()
    return (cut or text[: max_chars - 1]).rstrip('.,;:') + '…'


def _items(row: Mapping[str, Any], values: Iterable[Any], limit: int, max_chars: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        for sentence in _split(value):
            if _bad(sentence, row):
                continue
            item = _short(sentence, max_chars)
            key = item.lower()
            if key not in seen:
                out.append(item)
                seen.add(key)
            if len(out) >= limit:
                return out
    return out


def _live_odds(row: Mapping[str, Any]) -> bool:
    status = _text(row.get('odds_status')).lower()
    source = _text(row.get('odds_source') or row.get('data_source')).lower()
    if any(token in source for token in ('uploaded', 'fallback', 'cached', 'missing')):
        return False
    if source in {'live_api', 'odds api', 'the odds api', 'live_source'}:
        return True
    return status in {'live', 'live_api'} and not source


def _matchup_items(row_like: Any) -> list[str]:
    row = _row(row_like)
    values = [row.get(k) for k in (
        'perplexity_context', 'perplexity_summary', 'newsapi_summary', 'news_summary',
        'weather_summary', 'sports_context_summary', 'preview_summary', 'game_summary',
        'short_reason', 'matchup_note', 'matchup_notes'
    )]
    items = _items(row, values, 3, 82)
    if not _live_odds(row) and not any('odds' in item.lower() or 'price' in item.lower() for item in items):
        items.insert(0, 'Odds are not live; verify current price before entry.')
    return (items or ['Pregame context was not returned; verify odds and news before entry.'])[:3]


def _team_items(row_like: Any, side: str = '') -> list[str]:
    row = _row(row_like)
    values = [row.get(k) for k in (
        f'{side}_team_form', f'{side}_team_record', f'{side}_recent_results',
        f'{side}_sportsdataio_team_summary', f'{side}_api_football_team_summary',
        'team_stats_summary', 'recent_results', 'news_summary', 'newsapi_summary', 'perplexity_context'
    )]
    return _items(row, values, 3, 62) or ['Team data not matched to a live provider.', 'Verify lineup/news before entry.']


def _injury_items(row_like: Any, prefix: str) -> list[str]:
    row = _row(row_like)
    values = [row.get(k) for k in (
        f'{prefix}_injuries', f'{prefix}_injury_report', f'{prefix}_lineup_status',
        f'{prefix}_player_notes', 'injury_report', 'injuries', 'lineup_status',
        'sportsdataio_injury_summary', 'api_football_lineup_summary', 'news_injury_summary', 'perplexity_context'
    )]
    return _items(row, values, 2, 66) or ['No verified lineup/injury note returned.', 'Verify before entry.']


def sanitize_row(row_like: Any) -> dict[str, Any]:
    row = _row(row_like)
    if row.get("report_provider_calls_allowed") is False:
        # Snapshot diagnostics are not evidence; do not invent generic matchup
        # prose or replace the saved observation's provider fields.
        return row
    for key, value in list(row.items()):
        if isinstance(value, str):
            row[key] = _text(value)
            if _bad(row[key], row) and key in {'perplexity_context', 'perplexity_summary', 'newsapi_summary', 'news_summary', 'sports_context_summary', 'preview_summary', 'game_summary', 'short_reason', 'matchup_note', 'matchup_notes'}:
                row[key] = ''
    row['matchup_notes'] = '\n'.join(_matchup_items(row))
    if not _live_odds(row):
        row['odds_status'] = 'UPLOADED_ROW' if (row.get('decimal_odds') or row.get('american_odds') or row.get('odds')) else 'MISSING'
        row['odds_source'] = 'UPLOADED_ROW' if row['odds_status'] == 'UPLOADED_ROW' else 'MISSING'
        row['risk'] = 'FALLBACK MODE'
        row['risk_level'] = 'FALLBACK MODE'
        row['risk_label'] = 'FALLBACK MODE'
        row['final_decision'] = 'WATCHLIST'
        row['why_lose'] = 'Fallback data used.\nVerify live odds before entry.\nDo not use until the price is confirmed.'
        row['risk_notes'] = row['why_lose']
    return row


def install_live_cleanup() -> None:
    try:
        from autonomous_betting_agent import magazine_live_api_enrichment as live
    except Exception:
        return
    if getattr(live, '_ABA_REPORT_CLEANUP_VERSION', '') == _PATCH_VERSION:
        return
    original_one = live.enrich_row_with_live_api_data
    original_many = live.enrich_rows_with_live_api_data

    def enrich_one(row_like: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return sanitize_row(original_one(row_like, *args, **kwargs))

    def enrich_many(rows: list[Any] | tuple[Any, ...], **kwargs: Any) -> list[dict[str, Any]]:
        return [sanitize_row(row) for row in original_many(rows, **kwargs)]

    live.enrich_row_with_live_api_data = enrich_one
    live.enrich_rows_with_live_api_data = enrich_many
    live._bad_context = _bad
    live._is_live_odds = _live_odds
    live._ABA_REPORT_CLEANUP_VERSION = _PATCH_VERSION
    try:
        live.ENRICHMENT_VERSION = str(live.ENRICHMENT_VERSION) + '_cleanup_v2'
    except Exception:
        pass


def install_renderer_cleanup(module: Any | None = None) -> Any | None:
    if module is None:
        try:
            from autonomous_betting_agent import magazine_book_export as module
        except Exception:
            return None
    if getattr(module, '_ABA_REPORT_CLEANUP_VERSION', '') == _PATCH_VERSION:
        return module
    module._matchup_items = _matchup_items
    module._team_items = _team_items
    module._injury_items = _injury_items
    original_metric_cells = getattr(module, 'magazine_metric_cells', None)
    if callable(original_metric_cells):
        def metric_cells(odds: str, conf: str, edge: str, ev: str, units: str, risk: str):
            cells = list(original_metric_cells(odds, conf, edge, ev, units, risk))
            fixed = []
            danger = getattr(module, 'DANGER', (225, 67, 62))
            green = getattr(module, 'GREEN', (61, 205, 84))
            cream = getattr(module, 'CREAM', (255, 248, 230))
            risk_text = str(risk or '').upper()
            for label, value, color, x, width in cells:
                if str(label).upper() == 'RISK':
                    if any(token in risk_text for token in ('FALLBACK', 'NEG', 'MISSING', 'WATCH', 'NO')):
                        color = danger
                    elif any(token in risk_text for token in ('LIVE', 'VOLUME OK', 'SAFE')):
                        color = green
                    else:
                        color = cream
                fixed.append((label, value, color, x, width))
            return fixed
        module.magazine_metric_cells = metric_cells
    original_render = getattr(module, 'render_full_pick_magazine_page', None)
    if callable(original_render):
        def render(row_like: Any, *args: Any, **kwargs: Any):
            return original_render(sanitize_row(row_like), *args, **kwargs)
        module.render_full_pick_magazine_page = render
    module._ABA_REPORT_CLEANUP_VERSION = _PATCH_VERSION
    return module


def install() -> None:
    install_live_cleanup()
    install_renderer_cleanup()


install()
