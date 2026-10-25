from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Mapping

import pandas as pd

from .commercial_platform_tools import filter_locked_proof_rows, load_persistent_ledger, save_persistent_ledger
from .row_normalizer import ALIASES, first_text, result_status, safe_text

RESOLVED = {'win', 'loss', 'void'}
PENDING = {'', 'pending', 'unknown', 'scheduled', 'live', 'needs_review'}
AUTO_LOSS_MIN_SCORE = 0.97
AUTO_LOSS_MIN_EVENT = 0.95
AUTO_LOSS_MIN_DATE = 0.65

TEAM_ALIASES = {
    'new york yankees': {'yankees', 'ny yankees', 'nyy'},
    'cincinnati reds': {'reds', 'cin reds', 'cin'},
    'detroit tigers': {'tigers', 'det'},
    'chicago white sox': {'white sox', 'chisox', 'cws', 'chi white sox'},
    'miami marlins': {'marlins', 'mia'},
    'san francisco giants': {'giants', 'sf giants', 'sfg'},
    'houston astros': {'astros', 'hou'},
    'cleveland guardians': {'guardians', 'cle'},
    'tampa bay rays': {'rays', 'tb rays', 'tbr'},
    'washington nationals': {'nationals', 'nats', 'was'},
    'st. louis cardinals': {'cardinals', 'st louis cardinals', 'stl'},
    'kansas city royals': {'royals', 'kc royals', 'kcr'},
    'texas rangers': {'rangers', 'tex'},
    'san diego padres': {'padres', 'sd padres', 'sd'},
    'pittsburgh pirates': {'pirates', 'pit'},
    'colorado rockies': {'rockies', 'col'},
    'boston red sox': {'red sox', 'bos'},
    'toronto blue jays': {'blue jays', 'jays', 'tor'},
    'baltimore orioles': {'orioles', 'bal'},
    'philadelphia phillies': {'phillies', 'phi'},
    'atlanta braves': {'braves', 'atl'},
    'new york mets': {'mets', 'nym'},
    'los angeles dodgers': {'dodgers', 'la dodgers', 'lad'},
    'los angeles angels': {'angels', 'la angels', 'laa'},
    'arizona diamondbacks': {'diamondbacks', 'dbacks', 'ari'},
    'milwaukee brewers': {'brewers', 'mil'},
    'chicago cubs': {'cubs', 'chc'},
    'minnesota twins': {'twins', 'min'},
    'seattle mariners': {'mariners', 'sea'},
    'oakland athletics': {'athletics', 'a s', 'oak'},
    'sacramento athletics': {'athletics', 'a s', 'ath'},
}

ALIAS_TO_CANONICAL: dict[str, str] = {}
for canonical, aliases in TEAM_ALIASES.items():
    ALIAS_TO_CANONICAL[canonical] = canonical
    for alias in aliases:
        ALIAS_TO_CANONICAL[alias] = canonical

STOP_TOKENS = {'at', 'vs', 'v', 'the', 'fc', 'cf', 'club', 'team', 'ml', 'moneyline', 'winner', 'pick'}


def clean(value: Any) -> str:
    text = safe_text(value).lower().replace('&', ' and ').replace('@', ' at ')
    text = re.sub(r'[^a-z0-9.+\- ]+', ' ', text.replace('_', ' ').replace('-', ' '))
    return ' '.join(text.split())


def tokens(value: Any) -> set[str]:
    return {tok for tok in clean(value).split() if tok and tok not in STOP_TOKENS and len(tok) > 1}


def token_overlap(a: Any, b: Any) -> float:
    left, right = tokens(a), tokens(b)
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, min(len(left), len(right)))


def sim(a: Any, b: Any) -> float:
    left, right = clean(a), clean(b)
    if not left or not right:
        return 0.0
    if left == right or left in right or right in left:
        return 1.0
    return max(SequenceMatcher(None, left, right).ratio(), token_overlap(left, right))


def canonical_team(value: Any) -> str:
    text = clean(value)
    if not text:
        return ''
    if text in ALIAS_TO_CANONICAL:
        return ALIAS_TO_CANONICAL[text]
    best = ''
    best_len = 0
    for alias, canonical in ALIAS_TO_CANONICAL.items():
        if alias and (alias == text or re.search(rf'(^|\s){re.escape(alias)}($|\s)', text) or text in alias) and len(alias) > best_len:
            best = canonical
            best_len = len(alias)
    return best or text


def team_sim(a: Any, b: Any) -> float:
    ca, cb = canonical_team(a), canonical_team(b)
    if ca and cb and ca == cb:
        return 1.0
    return max(sim(ca or a, cb or b), token_overlap(a, b))


def split_event_teams(value: Any) -> tuple[str, str]:
    cleaned = clean(value)
    if not cleaned:
        return '', ''
    parts = re.split(r'\s+(?:at|vs|v)\s+', cleaned, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return '', ''


def event_team_score(ledger_row: Mapping[str, Any], result_row: Mapping[str, Any]) -> float:
    ledger_away, ledger_home = split_event_teams(ledger_row.get('event'))
    result_away = safe_text(result_row.get('away_team')) or split_event_teams(result_row.get('event'))[0]
    result_home = safe_text(result_row.get('home_team')) or split_event_teams(result_row.get('event'))[1]
    if ledger_away and ledger_home and result_away and result_home:
        direct = (team_sim(ledger_away, result_away) + team_sim(ledger_home, result_home)) / 2.0
        swapped = (team_sim(ledger_away, result_home) + team_sim(ledger_home, result_away)) / 2.0
        return max(direct, swapped)
    return max(sim(ledger_row.get('event'), result_row.get('event')), token_overlap(ledger_row.get('event'), result_row.get('event')))


def day(value: Any) -> str:
    text = safe_text(value)
    return text[:10] if len(text) >= 10 else ''


def date_score(left: Any, right: Any) -> float:
    lday, rday = day(left), day(right)
    if not lday or not rday:
        return 0.0
    if lday == rday:
        return 1.0
    try:
        ldt = pd.to_datetime(lday, utc=True).date()
        rdt = pd.to_datetime(rday, utc=True).date()
        return 0.65 if abs((ldt - rdt).days) <= 1 else 0.0
    except Exception:
        return 0.0


def score_value(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == '':
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def line_value(row: Mapping[str, Any]) -> float | None:
    for key in ('line_point', 'point', 'spread', 'total'):
        parsed = number(row.get(key))
        if parsed is not None:
            return parsed
    found = re.findall(r'[+-]?\d+(?:\.\d+)?', safe_text(row.get('prediction')))
    return float(found[-1]) if found else None


def market_kind(row: Mapping[str, Any]) -> str:
    text = clean(row.get('market_type') or row.get('market') or row.get('prediction'))
    pick = clean(row.get('prediction'))
    if 'over' in pick or 'under' in pick or 'total' in text:
        return 'total'
    if 'spread' in text or 'handicap' in text or re.search(r'(^|\s)[+-]\d+(?:\.\d+)?(\s|$)', safe_text(row.get('prediction'))):
        return 'spread'
    return 'h2h'


def normalize_results(results: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    raw = pd.DataFrame(results) if isinstance(results, list) else results
    if raw is None or raw.empty:
        return pd.DataFrame()
    rows = []
    for row in raw.to_dict(orient='records'):
        item = dict(row)
        home = safe_text(item.get('home_team'))
        away = safe_text(item.get('away_team'))
        home_score = score_value(item.get('home_score'))
        away_score = score_value(item.get('away_score'))
        winner = safe_text(item.get('winner') or item.get('actual_winner') or item.get('final_winner'))
        if not winner and home and away and home_score is not None and away_score is not None:
            if home_score > away_score:
                winner = home
            elif away_score > home_score:
                winner = away
            else:
                item['result_status'] = 'void'
        if winner:
            item['winner'] = winner
        if home and away and not safe_text(item.get('event')):
            item['event'] = f'{away} at {home}'
        if home_score is not None:
            item['home_score'] = home_score
        if away_score is not None:
            item['away_score'] = away_score
        if home_score is not None and away_score is not None and not safe_text(item.get('final_score')):
            item['final_score'] = f'{away} {away_score} - {home_score} {home}'
        rows.append(item)
    return pd.DataFrame(rows)


def odds_scores_to_result_frame_v2(payload: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for event in payload or []:
        if not bool(event.get('completed', False)):
            continue
        score_map = {}
        for score in event.get('scores') or []:
            name = safe_text(score.get('name'))
            value = score_value(score.get('score'))
            if name and value is not None:
                score_map[name] = value
        home = safe_text(event.get('home_team'))
        away = safe_text(event.get('away_team'))
        home_score = score_map.get(home)
        away_score = score_map.get(away)
        winner = ''
        status = 'pending'
        if home_score is not None and away_score is not None:
            if home_score > away_score:
                winner = home
                status = 'final'
            elif away_score > home_score:
                winner = away
                status = 'final'
            else:
                status = 'void'
        rows.append({
            'event': f'{away} at {home}' if away and home else safe_text(event.get('id')),
            'sport_key': safe_text(event.get('sport_key')),
            'sport': safe_text(event.get('sport_title') or event.get('sport_key')),
            'event_start_utc': safe_text(event.get('commence_time')),
            'home_team': home,
            'away_team': away,
            'home_score': home_score,
            'away_score': away_score,
            'winner': winner,
            'result_status': status,
            'final_score': '' if home_score is None or away_score is None else f'{away} {away_score} - {home_score} {home}',
        })
    return pd.DataFrame(rows)


def match_components(ledger_row: Mapping[str, Any], result_row: Mapping[str, Any]) -> dict[str, float]:
    event_score = max(sim(ledger_row.get('event'), result_row.get('event')), event_team_score(ledger_row, result_row))
    sport_score = max(sim(ledger_row.get('sport'), result_row.get('sport')), sim(ledger_row.get('sport_key'), result_row.get('sport_key')))
    left_day = _utc_identity_day(ledger_row.get('event_start_utc'))
    right_day = _utc_identity_day(result_row.get('event_start_utc'))
    dscore = 1.0 if left_day and left_day == right_day else 0.0
    pick_score = max(
        team_sim(ledger_row.get('prediction'), result_row.get('winner')),
        team_sim(ledger_row.get('prediction'), result_row.get('home_team')),
        team_sim(ledger_row.get('prediction'), result_row.get('away_team')),
    )
    return {'event': event_score, 'sport': sport_score, 'date': dscore, 'pick': pick_score}


def match_score(ledger_row: Mapping[str, Any], result_row: Mapping[str, Any]) -> float:
    comp = match_components(ledger_row, result_row)
    strict = comp['event'] * 0.50 + comp['sport'] * 0.12 + comp['date'] * 0.13 + comp['pick'] * 0.25
    if comp['event'] >= 0.88 and comp['pick'] >= 0.70:
        return max(strict, 0.91)
    if comp['event'] >= 0.75 and comp['pick'] >= 0.90 and comp['sport'] >= 0.50:
        return max(strict, 0.86)
    return strict


def side_scores(ledger_row: Mapping[str, Any], result_row: Mapping[str, Any]) -> tuple[float, float] | None:
    home = safe_text(result_row.get('home_team'))
    away = safe_text(result_row.get('away_team'))
    hs = score_value(result_row.get('home_score'))
    aw = score_value(result_row.get('away_score'))
    if not home or not away or hs is None or aw is None:
        return None
    pick = ledger_row.get('prediction')
    if _selected_team_identity(ledger_row) and _selected_team_identity(ledger_row) == _identity_team(home):
        return float(hs), float(aw)
    if _selected_team_identity(ledger_row) and _selected_team_identity(ledger_row) == _identity_team(away):
        return float(aw), float(hs)
    return None


def grade_pick(ledger_row: Mapping[str, Any], result_row: Mapping[str, Any]) -> str:
    status = result_status(result_row)
    kind = market_kind(ledger_row)
    if kind in {'h2h', 'spread'}:
        pair = _identity_pair(result_row)
        if not pair or _selected_team_identity(ledger_row) not in pair:
            return 'pending'
    if status == 'void':
        return 'void'
    hs = score_value(result_row.get('home_score'))
    aw = score_value(result_row.get('away_score'))
    if kind == 'total':
        line = line_value(ledger_row)
        pick = clean(ledger_row.get('prediction'))
        if hs is None or aw is None or line is None:
            return 'pending'
        total = hs + aw
        if abs(total - line) < 1e-9:
            return 'void'
        if 'over' in pick:
            return 'win' if total > line else 'loss'
        if 'under' in pick:
            return 'win' if total < line else 'loss'
        return 'pending'
    if kind == 'spread':
        line = line_value(ledger_row)
        scores = side_scores(ledger_row, result_row)
        if line is None or scores is None:
            return 'pending'
        selected, opponent = scores
        adjusted = selected + line - opponent
        if abs(adjusted) < 1e-9:
            return 'void'
        return 'win' if adjusted > 0 else 'loss'
    winner = safe_text(result_row.get('winner') or result_row.get('actual_winner') or result_row.get('final_winner'))
    if winner:
        pick_id, winner_id = _selected_team_identity(ledger_row), _identity_team(winner)
        pair = _identity_pair(result_row)
        if not pair or not pick_id or not winner_id or pick_id not in pair or winner_id not in pair:
            return 'pending'
        return 'win' if pick_id == winner_id else 'loss'
    if hs is not None and aw is not None and hs == aw:
        return 'void'
    return 'pending'


# Receipt fields must travel with the accepted outcome, including field absence.
RESULT_RECEIPT_FIELDS = {
    name for key in ('result_status', 'winner', 'final_score', 'profit_units')
    for name in ALIASES[key]
} | {'graded_at_utc', 'home_score', 'away_score', 'protected_auto_downgrade', 'grade_confidence', 'graded_by', 'resolved_at_utc'}
RESULT_RECEIPT_PREFIXES = ('matched_result_', 'grading_match_', 'best_result_', 'best_match_', 'review_', 'result_source', 'graded_', 'resolved_')


def restore_result_receipt(proposed: Mapping[str, Any], original: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(proposed)
    fields = RESULT_RECEIPT_FIELDS | {
        key for key in set(proposed) | set(original)
        if key.startswith(RESULT_RECEIPT_PREFIXES)
    }
    for field in fields:
        if field in original:
            item[field] = original[field]
        else:
            item.pop(field, None)
    return item


def result_receipts_survive_normalization(frame: pd.DataFrame) -> bool:
    """Pure preflight for the downstream normalizer; never writes or updates sessions."""
    originals = frame.to_dict(orient='records')
    marker = '__aba_receipt_preflight_index'
    while marker in frame.columns:
        marker += '_'
    probe = frame.copy()
    probe[marker] = range(len(probe))
    try:
        normalized = filter_locked_proof_rows(probe).to_dict(orient='records')
        if len(normalized) != len(originals):
            return False
        seen = set()
        for row in normalized:
            index = int(row.pop(marker))
            if index in seen or not 0 <= index < len(originals):
                return False
            seen.add(index)
            restored = restore_result_receipt(row, originals[index])
            if set(restored) != set(row) or any(safe_text(restored[key]) != safe_text(row[key]) for key in row):
                return False
        return True
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def _identity_team(value: Any) -> str:
    # Exact names or explicitly enumerated aliases only: no substring/fuzzy match.
    name = clean(value)
    matches = {
        clean(canonical) for canonical, aliases in TEAM_ALIASES.items()
        if name in {clean(canonical), *(clean(alias) for alias in aliases)}
    }
    return next(iter(matches)) if len(matches) == 1 else ('' if matches else name)


def _selected_team_identity(row: Mapping[str, Any]) -> str:
    prediction = safe_text(row.get('prediction'))
    if market_kind(row) == 'spread':
        suffix = re.search(r'\s+([+-]\d+(?:\.\d+)?)\s*$', prediction)
        if suffix:
            if line_value(row) != float(suffix.group(1)):
                return ''
            prediction = prediction[:suffix.start()]
    return _identity_team(prediction)


def _identity_pair(row: Mapping[str, Any]) -> tuple[str, str] | None:
    event = safe_text(row.get('event'))
    parsed = split_event_teams(event)
    explicit = (safe_text(row.get('away_team')), safe_text(row.get('home_team')))
    pairs = []
    if event:
        if not all(parsed):
            return None
        pairs.append(tuple(sorted(_identity_team(team) for team in parsed)))
    if any(explicit):
        if not all(explicit):
            return None
        pairs.append(tuple(sorted(_identity_team(team) for team in explicit)))
    if not pairs or any(not all(pair) or pair[0] == pair[1] for pair in pairs):
        return None
    return pairs[0] if all(pair == pairs[0] for pair in pairs) else None


def _utc_identity_day(value: Any) -> str:
    # Date-only and timezone-naive values cannot establish a UTC event day.
    text = safe_text(value)
    if not re.match(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}', text):
        return ''
    try:
        stamp = pd.Timestamp(text)
        if pd.isna(stamp) or stamp.tzinfo is None:
            return ''
        return stamp.tz_convert('UTC').date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return ''


def _sport_identity(row: Mapping[str, Any]) -> str:
    aliases = {'mlb': 'baseball', 'nba': 'basketball', 'wnba': 'basketball',
               'nfl': 'americanfootball', 'nhl': 'icehockey',
               'american football': 'americanfootball', 'ice hockey': 'icehockey'}
    families = {'baseball', 'basketball', 'soccer', 'americanfootball', 'icehockey',
                'tennis', 'mma', 'cricket', 'rugby', 'golf', 'volleyball'}
    identities = set()
    for field in ('sport', 'sport_key', 'sport_title', 'league', 'competition', 'deporte'):
        value = safe_text(row.get(field)).lower().strip()
        if not value:
            continue
        value = aliases.get(value, value)
        family = value.split('_', 1)[0]
        if family not in families:
            return ''
        identities.add(family)
    return next(iter(identities)) if len(identities) == 1 else ''


def _sport_competitions(row: Mapping[str, Any]) -> set[str]:
    known = {'mlb': 'baseball_mlb', 'nba': 'basketball_nba', 'wnba': 'basketball_wnba',
             'nfl': 'americanfootball_nfl', 'nhl': 'icehockey_nhl'}
    competitions = set()
    for field in ('sport', 'sport_key', 'sport_title', 'league', 'competition', 'deporte'):
        value = safe_text(row.get(field)).lower().strip()
        if value in known:
            competitions.add(known[value])
        elif '_' in value:
            competitions.add(value)
    return competitions


def automatic_identity_issue(ledger_row: Mapping[str, Any], result_row: Mapping[str, Any]) -> str:
    """Outcome-neutral prerequisite; ambiguous evidence is not an automatic loss."""
    left_sport, right_sport = _sport_identity(ledger_row), _sport_identity(result_row)
    if not left_sport or not right_sport or left_sport != right_sport:
        return 'event_sport_unverified'
    left_comp, right_comp = _sport_competitions(ledger_row), _sport_competitions(result_row)
    if len(left_comp) > 1 or len(right_comp) > 1 or (left_comp and right_comp and left_comp != right_comp):
        return 'event_competition_unverified'
    # IDs are opaque and provider scoped. Compare aliases without guessing a namespace.
    ids = []
    for row in (ledger_row, result_row):
        ids.append([(safe_text(row.get(field + '_namespace') or row.get('id_namespace')), safe_text(row.get(field)))
                    for field in ('event_id', 'game_id', 'fixture_id') if safe_text(row.get(field))])
    for left_ns, left_value in ids[0]:
        for right_ns, right_value in ids[1]:
            if left_value != right_value:
                return 'event_id_mismatch' if left_ns and left_ns == right_ns else 'event_id_namespace_unverified'
    left, right = _identity_pair(ledger_row), _identity_pair(result_row)
    if left is None or right is None or left != right:
        return 'event_identity_mismatch'
    left_day = _utc_identity_day(ledger_row.get('event_start_utc'))
    right_day = _utc_identity_day(result_row.get('event_start_utc'))
    if not left_day or not right_day:
        return 'event_utc_date_unverified'
    return '' if left_day == right_day else 'event_utc_date_mismatch'


def _result_evidence(row: Mapping[str, Any]) -> tuple[Any, ...]:
    scores = tuple(sorted((_identity_team(row.get(team)), safe_text(row.get(score)))
                          for team, score in (('home_team', 'home_score'), ('away_team', 'away_score'))))
    return (_identity_team(row.get('winner') or row.get('actual_winner') or row.get('final_winner')),
            result_status(row) == 'void', scores)


def _has_manual_result(row: Mapping[str, Any]) -> bool:
    fields = ('manual_grade', 'verified_grade', 'verified_result', 'verified_status',
              'verified_outcome', 'verified_result_status')
    return any(safe_text(row.get(field)) and result_status({field: row[field]}) in RESOLVED for field in fields)


def safe_auto_loss(ledger_row: Mapping[str, Any], result_row: Mapping[str, Any], best_score: float, components: Mapping[str, float]) -> bool:
    """Losses need a higher standard than wins/voids.

    Auto losses are the dangerous case for public proof because one bad fuzzy match hurts the record.
    Only accept an automatic loss when the event, date, and pick-side evidence are all strong.
    Otherwise route it to needs_review so it is excluded from dashboard win/loss math.
    """
    if safe_text(result_row.get('proof_id')) and safe_text(result_row.get('proof_id')) == safe_text(ledger_row.get('proof_id')):
        return True
    kind = market_kind(ledger_row)
    event_ok = float(components.get('event', 0.0)) >= AUTO_LOSS_MIN_EVENT
    date_ok = float(components.get('date', 0.0)) >= AUTO_LOSS_MIN_DATE
    score_ok = best_score >= AUTO_LOSS_MIN_SCORE
    if not (event_ok and date_ok and score_ok):
        return False
    if kind == 'spread':
        return side_scores(ledger_row, result_row) is not None and line_value(ledger_row) is not None
    if kind == 'total':
        return line_value(ledger_row) is not None and score_value(result_row.get('home_score')) is not None and score_value(result_row.get('away_score')) is not None
    return max(team_sim(ledger_row.get('prediction'), result_row.get('home_team')), team_sim(ledger_row.get('prediction'), result_row.get('away_team'))) >= 0.90


def _best_match(item: Mapping[str, Any], result_rows: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float, dict[str, float]]:
    best = None
    best_score = 0.0
    best_comp: dict[str, float] = {}
    proof_id = safe_text(item.get('proof_id'))
    if proof_id:
        for rrow in result_rows:
            if safe_text(rrow.get('proof_id')) == proof_id:
                return rrow, 1.0, {'proof_id': 1.0, 'event': 1.0, 'sport': 1.0, 'date': 1.0, 'pick': 1.0}
    for rrow in result_rows:
        score = match_score(item, rrow)
        if score > best_score:
            best_score = score
            best = rrow
            best_comp = match_components(item, rrow)
    return best, best_score, best_comp


def _ambiguous_raw_identities(rows: list[dict[str, Any]]) -> bool:
    seen = set()
    for row in rows:
        proof_id = safe_text(row.get('proof_id'))
        key = ('proof', proof_id) if proof_id else ('fallback',) + tuple(
            first_text(row, field).lower() for field in
            ('event', 'prediction', 'event_start_utc', 'market_type')) + (safe_text(row.get('line_point')),)
        if key in seen:
            return True
        seen.add(key)
    return False


def apply_fuzzy_updates(ledger: pd.DataFrame | list[dict[str, Any]], results: pd.DataFrame | list[dict[str, Any]], *, threshold: float = 0.82, regrade_resolved: bool = False) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = pd.DataFrame(ledger) if isinstance(ledger, list) else (ledger.copy() if ledger is not None else None)
    if raw is None or raw.empty:
        return pd.DataFrame(), {'updated_rows': 0, 'matched_rows': 0, 'unmatched_pending_rows': 0, 'reason': 'empty_ledger'}
    originals = raw.to_dict(orient='records')
    if _ambiguous_raw_identities(originals):
        return raw, {'updated_rows': 0, 'matched_rows': 0, 'unmatched_pending_rows': 0,
                     'reason': 'ambiguous_original_identity_needs_review'}
    marker = '__aba_result_receipt_index'
    while marker in raw.columns:
        marker += '_'
    raw[marker] = range(len(raw))
    locked = filter_locked_proof_rows(raw)
    result_frame = normalize_results(results)
    if locked.empty:
        return pd.DataFrame(), {'updated_rows': 0, 'matched_rows': 0, 'unmatched_pending_rows': 0, 'reason': 'empty_ledger'}
    result_rows = result_frame.to_dict(orient='records')
    rows = []
    retained: dict[int, tuple[dict[str, Any], str]] = {}
    accepted: dict[int, tuple[dict[str, Any], str]] = {}
    updated = matched = unmatched = skipped_resolved = pending_match = identity_reviews = 0
    best_scores: list[float] = []
    preview: list[dict[str, Any]] = []
    for lrow in locked.to_dict(orient='records'):
        item = dict(lrow)
        original = originals[int(item.pop(marker))]
        current = result_status(original)
        index = len(rows)
        if _has_manual_result(original) or (current in RESOLVED and not regrade_resolved):
            retained[index] = (original, '')
            skipped_resolved += 1
            rows.append(item)
            continue
        best, best_score, best_comp = _best_match(item, result_rows)
        best_scores.append(best_score)
        if len(preview) < 30:
            preview.append({'ledger_event': safe_text(item.get('event')),
                            'ledger_prediction': safe_text(item.get('prediction')),
                            'current_status': current,
                            'best_result_event': safe_text((best or {}).get('event')),
                            'best_winner': safe_text((best or {}).get('winner')),
                            'best_score': round(best_score, 4),
                            'components': {key: round(value, 4) for key, value in best_comp.items()}})
        eligible = [r for r in result_rows if not automatic_identity_issue(item, r)
                    and match_score(item, r) >= threshold]
        issue = ''
        if not eligible:
            issue = automatic_identity_issue(item, best) if best is not None else 'no_match'
            issue = issue or 'no_match'
        elif len({_result_evidence(r) for r in eligible}) > 1:
            issue = 'conflicting_result_evidence'
        else:
            best, best_score, best_comp = _best_match(item, eligible)
        if issue:
            retained[index] = (original, issue if current not in RESOLVED else '')
            identity_reviews += int(issue != 'no_match')
            unmatched += int(issue == 'no_match')
            rows.append(item)
            continue
        grade = grade_pick(item, best)
        if grade not in RESOLVED:
            retained[index] = (original, 'selected_side_or_result_unverified' if current not in RESOLVED else '')
            pending_match += 1
            rows.append(item)
            continue
        matched += 1
        accepted[index] = (original, grade)
        item['grading_match_confidence'] = round(best_score, 4)
        item['matched_result_event'] = safe_text(best.get('event'))
        item['matched_result_source'] = safe_text(best.get('result_source'))
        item['best_match_components'] = str(best_comp)
        item['grading_match_status'] = 'matched'
        item['result_status'] = grade
        item['winner'] = safe_text(best.get('winner') or item.get('winner'))
        item['final_score'] = safe_text(best.get('final_score') or item.get('final_score'))
        item['graded_at_utc'] = pd.Timestamp.utcnow().isoformat()
        updated += 1
        rows.append(item)
    out_rows = filter_locked_proof_rows(pd.DataFrame(rows)).to_dict(orient='records')
    for index, (original, proposed_grade) in accepted.items():
        if result_status(out_rows[index]) != proposed_grade:
            retained[index] = (original, '')
            updated -= 1
    for index, (original, issue) in retained.items():
        out_rows[index] = restore_result_receipt(out_rows[index], original)
        if issue:
            out_rows[index]['grading_match_status'] = 'identity_needs_review' if issue != 'no_match' else 'no_match'
            out_rows[index]['review_reason'] = issue
    out = pd.DataFrame(out_rows)
    return out, {
        'updated_rows': updated, 'matched_rows': matched, 'skipped_resolved': skipped_resolved,
        'unmatched_pending_rows': unmatched, 'pending_matched_needs_review': pending_match,
        'auto_losses_sent_to_review': 0, 'identity_matches_sent_to_review': identity_reviews,
        'result_rows': int(len(result_frame)), 'threshold': threshold,
        'auto_loss_min_score': AUTO_LOSS_MIN_SCORE,
        'avg_best_match_score': round(float(sum(best_scores) / len(best_scores)), 4) if best_scores else None,
        'max_best_match_score': round(float(max(best_scores)), 4) if best_scores else None,
        'match_preview': preview,
        **({'reason': 'empty_results'} if result_frame.empty else {}),
    }


def grade_persistent_with_fuzzy(results: pd.DataFrame | list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, Any]]:
    ledger = load_persistent_ledger()
    updated, stats = apply_fuzzy_updates(ledger, results)
    if not updated.empty:
        if not result_receipts_survive_normalization(updated):
            return ledger, {**stats, 'proposed_updated_rows': stats.get('updated_rows', 0),
                            'updated_rows': 0, 'persisted': False,
                            'reason': 'retained_receipt_normalization_needs_review'}
        save_persistent_ledger(updated)
    return updated, stats
