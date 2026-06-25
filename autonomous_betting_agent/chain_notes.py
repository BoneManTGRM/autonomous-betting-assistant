from __future__ import annotations

from typing import Any, Mapping, Sequence

RESEARCH = 'Research only'
DO_NOT_COMBINE = 'Do not combine'
STRAIGHT_ONLY = 'Straight only'
ANCHOR = 'Possible anchor leg'
SMALL_COMBO = 'Small combo only'
STRAIGHT_PREFERRED = 'Straight preferred'
PASS = 'Pass'

ES = {
    RESEARCH: 'Investigación',
    DO_NOT_COMBINE: 'No combinar',
    STRAIGHT_ONLY: 'Solo directa',
    ANCHOR: 'Posible ancla',
    SMALL_COMBO: 'Combinada pequeña',
    STRAIGHT_PREFERRED: 'Directa preferida',
    PASS: 'Pasar',
}

RESEARCH_TERMS = ('RESEARCH', 'NOT OFFICIAL', 'NEEDS GRADING', 'UNVERIFIED', 'MISSING ODDS', 'DATA BLOCKED', 'NO VERIFIED')
PASS_TERMS = ('PASS', 'NO PLAY', 'AVOID', 'SKIP')
VOLATILE_MARKET_TERMS = ('PROP', 'PLAYER PROP', 'TEAM TOTAL', 'ALT', 'ALTERNATE', 'LIVE', 'FIRST HALF', '1H')


def _row(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    data = getattr(value, '__dict__', None)
    return data if isinstance(data, Mapping) else {}


def clean(value: Any) -> str:
    return str(value or '').replace('_', ' ').strip()


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(',', '')
    if not text or text.lower() in {'nan', 'none', 'null', 'n/a', 'na'}:
        return None
    try:
        return float(text.replace('%', ''))
    except Exception:
        return None


def normalize_probability(value: Any) -> float | None:
    parsed = safe_float(value)
    if parsed is None:
        return None
    if parsed > 1.0:
        parsed /= 100.0
    if parsed < 0:
        return None
    return min(parsed, 1.0)


def _signed_decimal(value: Any) -> float | None:
    parsed = safe_float(value)
    if parsed is None:
        return None
    if abs(parsed) > 1.0:
        parsed /= 100.0
    return parsed


def normalize_edge(value: Any) -> float | None:
    return _signed_decimal(value)


def normalize_ev(value: Any) -> float | None:
    return _signed_decimal(value)


def _first(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ''):
            return value
    return None


def _any(text: str, terms: Sequence[str]) -> bool:
    return any(term in text for term in terms)


def _status(row: Mapping[str, Any]) -> str:
    keys = ('risk', 'risk_level', 'risk_label', 'profit_guard_status', 'official_status_label', 'result_status', 'learning_status', 'price_value_label', 'consumer_action', 'recommended_action', 'final_decision', 'recommendation')
    return ' '.join(clean(row.get(key)).upper() for key in keys if clean(row.get(key)))


def _confidence_low(row: Mapping[str, Any]) -> bool:
    confidence = clean(_first(row, 'confidence', 'confidence_tier', 'tier')).upper()
    if 'LOW' in confidence or 'WEAK' in confidence:
        return True
    probability = normalize_probability(_first(row, 'learned_model_probability', 'model_probability_clean', 'model_probability', 'final_probability'))
    return probability is not None and probability < 0.52


def _data_poor(row: Mapping[str, Any]) -> bool:
    completeness = normalize_probability(_first(row, 'data_completeness', 'sports_context_available', 'context_completeness'))
    if completeness is not None and completeness < 0.5:
        return True
    source = clean(_first(row, 'odds_source', 'bookmaker', 'source')).upper()
    return source in {'', 'N/A', 'NONE', 'NO VERIFIED SOURCE'} or 'MISSING' in source or 'UNVERIFIED' in source


def _market_volatile(row: Mapping[str, Any]) -> bool:
    market = clean(_first(row, 'market_type', 'market', 'bet_type')).upper()
    return _any(market, VOLATILE_MARKET_TERMS)


def _explicit_notes(row: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ('chain_notes', 'combo_notes', 'add_on_legs'):
        text = clean(row.get(key))
        if text:
            out.extend(part.strip(' -•') for part in text.replace('•', '\n').replace(';', '\n').replace('|', '\n').splitlines() if part.strip(' -•'))
    return out[:3]


def chain_score(row_like: Any) -> dict[str, Any]:
    row = _row(row_like)
    status = _status(row)
    edge = normalize_edge(_first(row, 'model_market_edge', 'edge'))
    ev = normalize_ev(_first(row, 'expected_value', 'expected_value_per_unit', 'profit_expected_value', 'ev'))
    probability = normalize_probability(_first(row, 'learned_model_probability', 'model_probability', 'model_probability_clean', 'final_probability'))
    corr = detect_correlation_warning(row, existing_legs=None, language='en')
    score = 0.0
    if probability is not None:
        score += max(0.0, probability - 0.5) * 100.0
    if edge is not None:
        score += edge * 100.0
    if ev is not None:
        score += ev * 50.0
    if _any(status, RESEARCH_TERMS):
        score -= 50.0
    if _confidence_low(row):
        score -= 12.0
    if _data_poor(row):
        score -= 12.0
    if corr:
        score -= 8.0
    return {'score': round(score, 3), 'probability': probability, 'edge': edge, 'ev': ev, 'status': status, 'confidence_low': _confidence_low(row), 'data_poor': _data_poor(row), 'market_volatile': _market_volatile(row), 'correlation_warning': corr}


def _classification_en(row_like: Any) -> str:
    row = _row(row_like)
    status = _status(row)
    score = chain_score(row)
    edge = score['edge']
    ev = score['ev']
    probability = score['probability']
    negative_value = (edge is not None and edge <= 0) or (ev is not None and ev <= 0)
    if _any(status, PASS_TERMS):
        return PASS
    if _any(status, RESEARCH_TERMS):
        return RESEARCH
    if negative_value or 'HIGH' in status or score['confidence_low'] or score['data_poor']:
        return DO_NOT_COMBINE
    if 'THIN EDGE' in status or 'WATCHLIST' in status or score['market_volatile']:
        return STRAIGHT_ONLY
    if probability is not None and probability >= 0.58 and (edge is None or edge > 0) and (ev is None or ev > 0) and not score['correlation_warning']:
        return ANCHOR
    if probability is not None and probability >= 0.54 and (edge is not None and edge > 0) and (ev is None or ev > 0):
        return SMALL_COMBO
    return STRAIGHT_PREFERRED


def classify(row: Any, language: str = 'en') -> str:
    classification = _classification_en(row)
    if str(language or 'en').lower().startswith('es'):
        return ES.get(classification, classification)
    return classification


def leg_quality(row: Any, language: str = 'en') -> str:
    return classify(row, language)


def notes(row_like: Any, language: str = 'en') -> list[str]:
    row = _row(row_like)
    explicit = _explicit_notes(row)
    if explicit:
        return explicit
    lang = 'es' if str(language or 'en').lower().startswith('es') else 'en'
    classification = _classification_en(row)
    corr = detect_correlation_warning(row, existing_legs=None, language=lang)
    if lang == 'es':
        if classification == RESEARCH:
            return ['Solo directa: investigación', 'No combinar sin verificación oficial', 'Esperar mejor contexto, momio o selección verificada']
        if classification in {DO_NOT_COMBINE, PASS}:
            return ['No agregar a una combinada', 'La ventaja/VE no justifica otra selección', 'Esperar mejor momio o señal más fuerte']
        if classification == STRAIGHT_ONLY:
            return ['Mejor como directa pequeña', 'Ventaja delgada: el movimiento del momio puede borrar valor', 'No sumar selecciones débiles']
        if classification == ANCHOR:
            bullets = ['Puede ser ancla pequeña', 'Usar solo 2–3 selecciones verificadas e independientes', 'Evitar selecciones correlacionadas']
            return [corr] + bullets[:2] if corr else bullets
        if classification == SMALL_COMBO:
            return ['Combinada pequeña solamente', 'Combinar solo con valor independiente más fuerte', 'Reducir exposición']
        return ['Directa preferida', 'Solo combinar con otra ventaja verificada', 'No perseguir pago con selecciones débiles']
    if classification == RESEARCH:
        return ['Straight only: research', 'Do not combine without official verification', 'Wait for better context or price']
    if classification in {DO_NOT_COMBINE, PASS}:
        return ['Do not add to a combination', 'Current edge/EV does not support another leg', 'Wait for a better price or stronger signal']
    if classification == STRAIGHT_ONLY:
        return ['Better as a small straight read', 'Thin edge: line movement can erase value', 'Do not add weak legs']
    if classification == ANCHOR:
        bullets = ['Possible small anchor leg', 'Use only 2–3 independent verified legs', 'Avoid correlated legs']
        return [corr] + bullets[:2] if corr else bullets
    if classification == SMALL_COMBO:
        return ['Small combo only', 'Pair only with stronger independent value', 'Reduce exposure']
    return ['Straight read preferred', 'Only combine with another verified edge', 'Do not chase payout with weak legs']


def _norm(value: Any) -> str:
    return clean(value).lower()


def detect_correlation_warning(row_like: Any, existing_legs: Sequence[Any] | None = None, language: str = 'en') -> str:
    row = _row(row_like)
    lang = 'es' if str(language or 'en').lower().startswith('es') else 'en'
    flag_text = ' '.join(clean(row.get(key)).upper() for key in ('correlation_warning', 'same_game_correlation', 'injury_dependency', 'weather_dependency', 'lineup_dependency', 'market_dependency') if clean(row.get(key)))
    if 'WEATHER' in flag_text or 'CLIMA' in flag_text:
        return 'No apilar mercados dependientes del clima sin revisión.' if lang == 'es' else 'Weather-dependent markets should not be stacked blindly.'
    if 'INJURY' in flag_text or 'LINEUP' in flag_text or 'LESION' in flag_text or 'ALINE' in flag_text:
        return 'Las selecciones dependientes de alineación necesitan confirmación.' if lang == 'es' else 'Lineup-dependent legs need confirmation before entry.'
    if 'CORREL' in flag_text or 'SAME' in flag_text:
        return 'Advertencia de correlación: selecciones del mismo partido pueden no ser independientes.' if lang == 'es' else 'Correlation warning: same-game legs may not be independent.'
    if not existing_legs:
        return ''
    event = _norm(_first(row, 'event_name', 'event', 'matchup'))
    teams = {_norm(_first(row, 'away_team', 'away')), _norm(_first(row, 'home_team', 'home'))} - {''}
    market = _norm(_first(row, 'market_type', 'market', 'bet_type'))
    for other_like in existing_legs:
        other = _row(other_like)
        other_event = _norm(_first(other, 'event_name', 'event', 'matchup'))
        other_teams = {_norm(_first(other, 'away_team', 'away')), _norm(_first(other, 'home_team', 'home'))} - {''}
        other_market = _norm(_first(other, 'market_type', 'market', 'bet_type'))
        if event and other_event and event == other_event:
            return 'Advertencia de correlación: selecciones del mismo partido pueden no ser independientes.' if lang == 'es' else 'Correlation warning: same-game legs may not be independent.'
        if teams and other_teams and teams.intersection(other_teams) and market and other_market and market == other_market:
            return 'Advertencia de correlación: selecciones del mismo equipo/mercado pueden no ser independientes.' if lang == 'es' else 'Correlation warning: same-team/same-market legs may not be independent.'
    return ''


def install() -> None:
    try:
        from . import cn_patch
    except Exception:
        return
    cn_patch.install()


normalize_chain_classification = classify
chain_betting_bullets = notes
chain_betting_score = chain_score
parlay_leg_quality = leg_quality
