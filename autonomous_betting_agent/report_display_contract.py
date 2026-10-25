"""Read-only, locale-explicit presentation contract for magazine reports.

This module never enriches data, changes stored rows, or promotes verification.
Provider prose is displayed only with an explicit locale or a supplied translation.
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping

COPY = {
    'Source type: Saved row with provider/context fields': 'Tipo de fuente: fila guardada con contexto del proveedor',
    'Current provider match: Recheck required': 'Coincidencia actual del proveedor: se requiere una nueva verificación',
    'Verification status: Saved price only': 'Estado de verificación: solo cuota guardada',
    'Verification Checklist': 'Lista de verificación',
    'Eligibility Summary': 'Resumen de elegibilidad',
    'Required Checks': 'Controles pendientes',
    'Current provider verification is incomplete.': 'La verificación del proveedor actual está incompleta.',
    'Source verification is distinct from model accuracy.': 'La verificación de la fuente es distinta de la precisión del modelo.',
    'Stored source note; not a live availability confirmation.': 'Nota de fuente guardada; no confirma disponibilidad en vivo.',
    'Accounting review required before report publication.': 'Se requiere revisión contable antes de publicar el reporte.',
    'ACCOUNTING REVIEW': 'REVISIÓN CONTABLE',
    'Accounting review required': 'Revisión contable requerida',
    'Selection Review': 'Selección en revisión',
    'See full source notes.': 'Ver las notas completas.',
    'Full source note continues on the source-notes pages.': 'La nota completa continúa en las páginas de notas de fuentes.',
    'SOURCE NOTES': 'NOTAS DE FUENTES',
    'Daily Sports Analysis': 'Análisis deportivo diario',
    'Baseball': 'Béisbol', 'Baseball regular season': 'Béisbol — temporada regular',
    'Basketball': 'Baloncesto', 'MARKET REVIEW': 'REVISIÓN DE MERCADO',
    'Provider verification required': 'Se requiere verificación del proveedor',
    'Current provider row': 'Fila del proveedor actual', 'Current provider matched': 'Coincidencia actual del proveedor',
    'VERIFIED PRICE': 'CUOTA VERIFICADA', 'RESEARCH ONLY': 'SOLO INVESTIGACIÓN', 'Basketball regular season': 'Baloncesto — temporada regular',
    'WNBA regular season': 'WNBA — temporada regular',
    'MODEL P': 'P DEL MODELO', 'MODEL PROBABILITY': 'PROBABILIDAD DEL MODELO',
    'MODEL EV': 'VE DEL MODELO', 'STORED EV': 'VE GUARDADO', 'STORED PRICE': 'CUOTA GUARDADA',
    'STAKE (u)': 'APUESTA (u)', 'NO ACTION': 'SIN APUESTA',
    'MANUALLY VERIFIED INPUT / PLAYABLE VALUE': 'ENTRADA VERIFICADA MANUALMENTE / VALOR DISPONIBLE',
    'Operator-attested manual input': 'Entrada manual confirmada por el operador',
    'Manually verified': 'Verificada manualmente', 'BOOK / PRICE': 'CASA / CUOTA',
    'Not used for this price': 'No utilizada para esta cuota',
    'No verified current-provider picks': 'No hay selecciones verificadas del proveedor actual',
    'No verified buyer picks': 'No hay selecciones verificadas para clientes',
    'NO VERIFIED BUYER PICKS': 'SIN SELECCIONES VERIFICADAS PARA CLIENTES',
    'NO_VERIFIED_BUYER_PICKS': 'SIN SELECCIONES VERIFICADAS PARA CLIENTES',
    'Provider not matched': 'Sin coincidencia del proveedor',
    'DEMONSTRATION ONLY': 'SOLO DEMOSTRACIÓN', 'Demonstration fixture': 'Caso de demostración',
    'Demonstration only - not current betting advice': 'Solo demostración; no es consejo de apuesta actual',
    'DEMO PRICE - NOT LIVE API': 'MOMIO DE DEMOSTRACIÓN - NO ES API EN VIVO',
    'Not used for this validation fixture': 'No utilizada para este caso de validación',
    'DATA SCOPE': 'ALCANCE DE DATOS', 'ODDS STATUS': 'ESTADO DE CUOTA', 'LIVE API': 'API EN VIVO',
    'REPORT SOURCE': 'FUENTE DEL REPORTE', 'TRUTH': 'VERIFICACIÓN', 'Missing': 'Falta',
    'WATCHLIST / VERIFY PRICE': 'SEGUIMIENTO / VERIFICAR CUOTA',
    'VERIFIED CANDIDATE / PLAYABLE VALUE': 'SELECCIÓN VERIFICADA / VALOR DISPONIBLE',
    'NO BET / PRICE REJECTED': 'NO APOSTAR / CUOTA RECHAZADA',
    'AUDIT ONLY': 'SOLO AUDITORÍA',
    'VERIFY': 'VERIFICAR', 'VERIFY CURRENT PRICE': 'VERIFICAR CUOTA ACTUAL',
    'PRICE STATUS': 'ESTADO DE CUOTA', 'SAVED PRICE': 'CUOTA GUARDADA', 'TIMESTAMP': 'FECHA Y HORA',
    'MATCHED': 'COINCIDENCIA', 'MODEL SOURCE': 'FUENTE DEL MODELO',
    'NO LIVE FEEDS USED': 'NO SE USARON FUENTES EN VIVO',
    'Saved row + provider context': 'Fila guardada con contexto del proveedor',
    'Verify current price': 'Verificar la cuota actual',
    'Current provider recheck required': 'Se requiere verificar al proveedor actual',
    'Saved-source report. Verify current provider price before publishing.': 'Reporte de fuente guardada. Verificar la cuota actual del proveedor antes de publicar.',
    'No verified selection': 'No hay selección verificada',
    'NO VERIFIED SELECTION': 'SIN SELECCIÓN VERIFICADA',
    'No actionable stake; price verification is required.': 'Sin apuesta operativa; se requiere verificar la cuota.',
    'Model estimate; source not supplied.': 'Estimación del modelo; no se proporcionó su fuente.',
    'Stored model estimate; not a calibrated accuracy claim.': 'Estimación guardada del modelo; no representa precisión calibrada.',
    'Stored-price calculation; current value is unverified.': 'Cálculo con cuota guardada; el valor actual no está verificado.',
    'No live team snapshot returned.': 'No se recibió un resumen del equipo en vivo.',
    'No verified lineup/injury update returned.': 'No se recibió una actualización verificada de alineación o lesiones.',
    'Team data not matched to a live provider.': 'Los datos del equipo no están vinculados a un proveedor en vivo.',
    'Verify before entry.': 'Verificar antes de apostar.',
    'Verify lineup/news before entry.': 'Verificar alineación y noticias antes de apostar.',
    'No team-specific source supplied.': 'No se proporcionó una fuente específica del equipo.',
    'No team-specific injury source supplied.': 'No se proporcionó una fuente de lesiones específica del equipo.',
    'Content language was not supplied.': 'No se indicó el idioma del contenido.',
    'Requested-language content was not supplied.': 'No se proporcionó contenido en el idioma solicitado.',
    'No matched matchup source supplied.': 'No se proporcionó una fuente vinculada al partido.',
    'Weather is not a direct playing-condition factor for an indoor venue.': 'El clima exterior no afecta directamente las condiciones de juego de un recinto cubierto.',
    'Weather relevance is unverified; venue conditions were not supplied.': 'La relevancia del clima no está verificada; faltan las condiciones del recinto.',
    'No event-matched weather source supplied.': 'No se proporcionó una fuente meteorológica vinculada al evento.',
    'Missing exact market line': 'Falta la línea exacta del mercado',
    'Missing selection side': 'Falta el lado de la selección',
    'Conflicting market values': 'Hay valores de mercado contradictorios',
    'Unknown market selection': 'Selección de mercado desconocida',
    'Market Scan Summary': 'Resumen de mercados revisados',
    'Watchlist Legs': 'Selecciones en seguimiento', 'Blocked / Why': 'Bloqueos y motivos',
    'Data Needed to Unlock': 'Datos necesarios para verificar',
    'No verified parlay or chain bet qualifies.': 'No hay parlay ni apuesta combinada que cumpla la verificación.',
    'No current-provider selection is verified; this report is a watchlist only.': 'No hay una selección verificada con un proveedor actual; este reporte es solo de seguimiento.',
    'Verify the anchor before considering a straight bet or a parlay.': 'Verificar la selección principal antes de considerar una apuesta simple o un parlay.',
    'Line supplied, not provider-verified': 'Línea proporcionada, no verificada por el proveedor',
    'No actionable stake': 'Sin apuesta operativa',
    'Information only; not a verified recommendation.': 'Solo información; no es una recomendación verificada.',
    'Fallback/watchlist only.': 'Solo fuente de respaldo o seguimiento.',
    'Confirm current price before entry.': 'Confirmar la cuota actual antes de apostar.',
    'Watchlist only: current price and live context need verification.': 'Solo seguimiento: se deben verificar la cuota actual y el contexto en vivo.',
    'No line movement observations supplied.': 'No se proporcionaron observaciones de movimiento de línea.',
}
_COPY_CASEFOLD = {key.casefold(): value for key, value in COPY.items()}


def language(value: Any) -> str:
    return 'es' if str(value or '').lower().startswith('es') else 'en'


def text(value: Any) -> str:
    value = '' if value is None else str(value).strip()
    return '' if value.casefold() in {'', 'nan', 'none', 'null', 'n/a', 'na', '--'} else re.sub(r'\s+', ' ', value)


def tr(value: Any, lang: str) -> str:
    value = text(value)
    if language(lang) != 'es':
        return value
    translated = _COPY_CASEFOLD.get(value.casefold())
    if translated is not None:
        return translated.upper() if value.isupper() else translated
    market = re.fullmatch(r"(Game Total|Team Total|Spread|Run Line|Player Prop|Moneyline):\s*(.+)", value, flags=re.I)
    if market:
        labels = {'game total': 'Total del partido', 'team total': 'Total del equipo', 'spread': 'Hándicap', 'run line': 'Línea de carrera', 'player prop': 'Mercado de jugador', 'moneyline': 'Ganador'}
        kind, body = market.group(1).lower(), market.group(2)
        for english in ('Missing exact market line', 'Missing selection side', 'Conflicting market values', 'Missing selection'):
            spanish = _COPY_CASEFOLD.get(english.casefold(), 'Falta la selección')
            body = re.sub(re.escape(english) + r"$", spanish, body, flags=re.I)
        if kind in {'game total', 'team total', 'player prop'}:
            body = re.sub(r"\bOver(?=\s+(?:[+-]?\d|[-–]))", 'Más de', body, flags=re.I)
            body = re.sub(r"\bUnder(?=\s+(?:[+-]?\d|[-–]))", 'Menos de', body, flags=re.I)
        if kind == 'player prop':
            for source, localized_stat in (('player points', 'puntos del jugador'), ('player_points', 'puntos del jugador'), ('strikeouts', 'ponches'), ('rebounds', 'rebotes'), ('assists', 'asistencias'), ('shots', 'tiros'), ('points', 'puntos')):
                body = re.sub(r'(?<!\w)' + re.escape(source) + r'$', localized_stat, body, flags=re.I)
        localized = labels[kind] + ': ' + body
        return localized.upper() if value.isupper() else localized
    # Whole-message templates only. Never substitute fragments inside provider prose.
    patterns = (
        (r'Stored price: (.+?) from (.+)', r'Cuota guardada: \1 de \2'),
        (r'Stored price: (.+)', r'Cuota guardada: \1'),
        (r'Timestamp: (.+)', r'Fecha y hora: \1'),
        (r'Model projects (.+?) probability for (.+?)\.', r'El modelo estima una probabilidad de \1 para \2.'),
        (r'Market-implied probability checks at (.+?)\.', r'La probabilidad implícita del mercado es \1.'),
        (r'Measured edge: (.+?)\.', r'Ventaja calculada: \1.'),
        (r'Expected value: (.+?)\.', r'Valor esperado: \1.'),
        (r'Stored target: (.+?) u; not actionable\.', r'Objetivo guardado: \1 u; no es una apuesta operativa.'),
        (r'Model source: (.+)', r'Fuente del modelo: \1'),
        (r'Source: (.+)', r'Fuente: \1'),
        (r'Captured: (.+)', r'Registro: \1'),
    )
    for pattern, replacement in patterns:
        if re.fullmatch(pattern, value, flags=re.I):
            return re.sub(pattern, replacement, value, flags=re.I)
    return value


def number(value: Any) -> float | None:
    try:
        result = float(str(value).replace('%', '').replace(',', '').replace('−', '-').replace('–', '-').replace('—', '-'))
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) else None


def first(row: Mapping[str, Any], *keys: str) -> str:
    return next((text(row.get(key)) for key in keys if text(row.get(key))), '')


def localized_content(row: Mapping[str, Any], keys: tuple[str, ...], lang: str) -> tuple[str, str]:
    """Return explicit-locale prose or an actionable reason, never guessed language."""
    lang = language(lang)
    unknown = False
    other = False
    for key in keys:
        translated = first(row, f'{key}_{lang}')
        if translated:
            return translated, ''
        value = text(row.get(key))
        if not value:
            continue
        locale = first(row, f'{key}_language', f'{key}_locale', 'content_language', 'source_content_language')
        if not locale:
            unknown = True
        elif language(locale) == lang and locale.lower().split('-')[0] in {'en', 'es'}:
            return value, ''
        else:
            other = True
    reason = 'Requested-language content was not supplied.' if other else 'Content language was not supplied.' if unknown else ''
    return '', tr(reason, lang)


# Only documented bookmaker/selection aliases. Model projections are deliberately absent.
MARKET_FIELDS = ('selected_market', 'market_type', 'market', 'market_name', 'market_raw', 'raw_market', 'bet_type')
SELECTION_FIELDS = ('selected_pick', 'selection', 'public_pick', 'prediction', 'pick', 'side', 'outcome', 'exact_bet')
LINE_FIELDS = ('selected_line', 'locked_line', 'total_line', 'game_total_line', 'team_total_line', 'spread_line', 'run_line', 'runline', 'line_display', 'line', 'line_point', 'point', 'points', 'handicap', 'total', 'spread', 'threshold', 'market_line', 'bet_line', 'line_value', 'prop_line', 'provider_line', 'current_line', 'verified_line')


def _selection_tokens(value: Any) -> str:
    value = text(value).casefold().replace('−', '-').replace('–', '-').replace('—', '-')
    value = re.sub(r'(?<!\w)([ou])\s*(?=[+-]?\d)', lambda m: 'over ' if m.group(1) == 'o' else 'under ', value)
    value = re.sub(r'\b(over|under)\s*(?=[+-]?\d)', r'\1 ', value)
    for es, en in (('total del partido', 'game total'), ('total del juego', 'game total'), ('total del equipo', 'team total'), ('más de', 'over'), ('mas de', 'over'), ('menos de', 'under'), ('hándicap', 'spread'), ('ganador', 'moneyline'), ('línea de carrera', 'run line')):
        value = value.replace(es, en)
    return re.sub(r'\s+', ' ', value).strip()


def _market_family(value: Any) -> str:
    value = _selection_tokens(value).replace('_', ' ')
    if 'team total' in value: return 'team_total'
    if any(token in value for token in ('player', 'prop', 'strikeout', 'assist', 'rebound')): return 'player_prop'
    if re.search(r'\b(total|totals|over|under)\b', value): return 'total'
    if any(token in value for token in ('run line', 'runline', 'puck line')): return 'run_line'
    if any(token in value for token in ('spread', 'handicap')): return 'spread'
    if any(token in value for token in ('player', 'prop', 'strikeout', 'assist', 'rebound')): return 'player_prop'
    if value in {'ml', 'h2h', 'winner', 'moneyline', 'money line'}: return 'moneyline'
    return ''


def canonical_market_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve explicit aliases on a copy, recording contradictions before choosing.

    Conflicts are sticky through display wrappers. A child market must start with
    its own aliases, not clear a conflict by overwriting one parent's field.
    """
    out = dict(row)
    prior = row.get('report_field_conflicts')
    conflicts = list(prior) if isinstance(prior, (list, tuple)) else []
    market_values = [(key, text(row.get(key))) for key in MARKET_FIELDS if text(row.get(key))]
    families = {family for _, value in market_values if (family := _market_family(value))}
    if len(families) > 1:
        conflicts.append('market type')
    selected_market = first(row, *MARKET_FIELDS)
    selections = [(key, _selection_tokens(row.get(key))) for key in SELECTION_FIELDS if text(row.get(key))]
    selected = first(row, *SELECTION_FIELDS)
    sides, participants, lines = set(), set(), []
    explicit_line = False
    for key, value in selections:
        match = re.search(r'\b(over|under)\b', value)
        if match:
            sides.add(match.group(1))
        line_match = re.search(r'\b(?:over|under)\s+([+-]?\d+(?:\.\d+)?)\b', value)
        if line_match is None and families & {'spread', 'run_line'}:
            line_match = re.search(r'(?<![\w.])([+-]\d+(?:\.\d+)?)(?![\w.])', value)
        if line_match:
            lines.append((key, float(line_match.group(1))))
            explicit_line = True
        # Compare named participants only in markets where a participant is required.
        if families & {'moneyline', 'spread', 'run_line', 'team_total', 'player_prop'}:
            named = re.sub(r'\b(?:game total|team total|moneyline|money line|ml|spread|point spread|run line|puck line|player prop)\b[: ]*', '', value)
            named = re.sub(r'\b(?:over|under)\s*(?:[+-]?\d+(?:\.\d+)?)?', '', named)
            named = re.sub(r'(?<![\w.])[+-]\d+(?:\.\d+)?(?![\w.])', '', named).strip(' -:|/')
            if 'player_prop' in families:
                for key in ('prop_name', 'stat_type', *MARKET_FIELDS):
                    stat = _selection_tokens(row.get(key)).replace('_', ' ')
                    if stat:
                        named = re.sub(r'(?:\s|:)+' + re.escape(stat) + r'$', '', named).strip()
            if named in {'home', 'away'}:
                named = _selection_tokens(row.get(named + '_team'))
            if named and named not in {'selection', 'no pick', 'sin selección', 'sin seleccion'}:
                participants.add(named)
    if 'player_prop' in families:
        participants.update(_selection_tokens(row.get(key)) for key in ('player', 'player_name', 'participant') if text(row.get(key)))
    if len(sides) > 1 or len(participants) > 1:
        conflicts.append('selection side or participant')
    for key in LINE_FIELDS:
        value = number(row.get(key))
        if value is not None:
            lines.append((key, value))
    if lines and any(abs(value - lines[0][1]) > 1e-9 for _, value in lines[1:]):
        conflicts.append('market line')
    # These aliases refer to the same provider receipt, unlike odds_api/sportsdata IDs.
    fixture_ids = {text(row.get(key)) for key in ('provider_event_id', 'verified_provider_event_id', 'current_provider_event_id') if text(row.get(key))}
    provider = first(row, 'provider', 'odds_provider', 'api_provider', 'odds_source').casefold()
    provider_aliases = ('odds_api_event_id',) if 'odds api' in provider else ('sportsdataio_event_id', 'sdio_event_id') if 'sportsdataio' in provider else ('api_football_fixture_id',) if 'api-football' in provider else ()
    fixture_ids.update(text(row.get(key)) for key in provider_aliases if text(row.get(key)))
    if len(fixture_ids) > 1:
        conflicts.append('provider fixture')
    if selected_market:
        out['market_type'] = selected_market
    if selected:
        out['selection'] = selected
    if conflicts or text(row.get('report_market_issue')):
        out['report_market_issue'] = 'Conflicting market values'
        out['report_field_conflicts'] = sorted(set(conflicts))
    elif lines:
        out['line'] = lines[0][1]
        out['report_line_origin'] = 'explicit selection' if explicit_line else 'structured field'
    return out


def team_items(row: Mapping[str, Any], side: str, lang: str, *, injury: bool = False) -> list[str]:
    keys = ((f'{side}_injuries', f'{side}_injury_report', f'{side}_lineup_status', f'{side}_player_notes') if injury else
            (f'team_snapshot_{side}', f'{side}_team_form', f'{side}_team_record', f'{side}_recent_results', f'{side}_sportsdataio_team_summary'))
    value, reason = localized_content(row, keys, lang)
    if value:
        return [value]
    missing = 'No verified lineup/injury update returned.' if injury else 'No live team snapshot returned.'
    detail = reason or tr('No team-specific injury source supplied.' if injury else 'No team-specific source supplied.', lang)
    return [reason or tr(missing, lang)]


def context_items(row: Mapping[str, Any], lang: str) -> list[str]:
    items = []
    venue = first(row, 'venue_type', 'venue_environment', 'roof_type').casefold()
    indoor = venue in {'indoor', 'indoors', 'closed', 'covered', 'retractable_closed'} or row.get('is_indoor') is True
    sport = first(row, 'sport', 'league').casefold()
    # Basketball is played indoors unless a particular outdoor event is explicit.
    indoor = indoor or (not venue and any(k in sport for k in ('basketball', 'wnba', 'nba')))
    if indoor:
        items.append(tr('Weather is not a direct playing-condition factor for an indoor venue.', lang))
    elif venue not in {'outdoor', 'outdoors', 'open', 'retractable_open'}:
        items.append(tr('Weather relevance is unverified; venue conditions were not supplied.', lang))
    else:
        weather, reason = localized_content(row, ('weather_summary_short', 'weather_summary', 'venue_weather'), lang)
        items.append(weather or reason or tr('No event-matched weather source supplied.', lang))
    matchup, reason = localized_content(row, ('expanded_matchup_context', 'sports_context_summary', 'preview_summary', 'game_summary', 'matchup_note'), lang)
    items.append(matchup or reason or tr('No matched matchup source supplied.', lang))
    return items


def install_source_note_pages(module: Any) -> None:
    """Attach deterministic source-note overflow at the public export boundary."""
    current = module.render_full_magazine_book_pages
    if getattr(current, '_ABA_SOURCE_NOTE_PAGES', False):
        return

    def pages(picks, *args, **kwargs):
        from PIL import ImageDraw
        rows = list(picks)
        rendered = list(current(rows, *args, **kwargs))
        if any(page.info.get("_aba_source_notes") for page in rendered):
            return rendered
        explicit_lang = kwargs.get('language') or (args[8] if len(args) > 8 else None)
        report_name = kwargs.get('report_name') or (args[1] if len(args) > 1 else None)
        references = []
        for page_index, page in enumerate(rendered):
            page.info['report_row_index'] = page_index // 2
        for row_index, raw in enumerate(rows):
            row = dict(raw) if isinstance(raw, Mapping) else raw.to_dict()
            lang = language(explicit_lang or row.get('report_language'))
            notes = []
            for page_index in (row_index * 2, row_index * 2 + 1):
                if page_index < len(rendered):
                    notes.extend(rendered[page_index].info.get("_aba_overflow_notes", []))
            notes = list(dict.fromkeys(notes))
            if not notes:
                continue
            first_page = len(rendered) + 1
            title = first(row, 'event', 'event_name', 'matchup')
            page = None
            draw = None
            y = 0
            font = module._font(20)
            heading_font = module._font(24, True)
            step = max(25, module._line_height(font) + 4)
            for heading, body in notes:
                # Pixel-measured wrapping has no line-count limit or ellipsis.
                blocks = [(heading, heading_font)] + [(paragraph, font) for paragraph in body.splitlines() if paragraph.strip()]
                for block_text, block_font in blocks:
                    lines = module._wrap_text_to_box(ImageDraw.Draw(module._paper(17)), block_text, block_font, 950, max(1, len(block_text) + 1))
                    for line in lines:
                        if page is None or y + step > 1510:
                            if page is not None:
                                rendered.append(page.convert('RGB'))
                            page = module._paper(17 + len(rendered)).convert('RGBA')
                            page.info['_aba_source_notes'] = True
                            page.info['report_row_index'] = row_index
                            draw = ImageDraw.Draw(page, 'RGBA')
                            draw.rectangle((18, 18, 1062, 82), fill=module.BLACK)
                            brand = text(report_name or row.get('report_brand_name') or 'ABA SIGNAL PRO').upper()
                            draw.text((40, 30), brand, font=module._fit(brand, 510, 32, 16, True), fill=module.CREAM)
                            draw.text((42, 104), tr('SOURCE NOTES', lang), font=module._font(30, True), fill=module.BLUE)
                            title_lines = module._wrap_text_to_box(draw, title, heading_font, 960, max(1, len(title) + 1))
                            ty = 148
                            for title_line in title_lines:
                                draw.text((42, ty), title_line, font=heading_font, fill=module.RED)
                                ty += 30
                            y = ty + 24
                            draw.rectangle((20, 1542, 1060, 1581), fill=module.BLACK)
                            footer = module._tr(module.SAFETY_FOOTER, lang)
                            draw.text((42, 1551), footer, font=module._fit(footer, 970, 16, 12, False), fill=module.CREAM)
                        draw.text((54, y), line, font=block_font, fill=module.TEXT)
                        y += step
                    y += 14
            if page is not None:
                rendered.append(page.convert('RGB'))
            references.append((row_index * 2, first_page, len(rendered), lang))
        if references:
            total = len(rendered)
            for index, page in enumerate(rendered):
                lang = language(explicit_lang or (rows[min(index // 2, len(rows)-1)].get('report_language') if rows else 'en'))
                draw = ImageDraw.Draw(page)
                draw.rounded_rectangle((840, 24, 1050, 74), radius=5, fill=module.CREAM, outline=module.BLACK)
                page_text = module._page_label(index + 1, total, lang)
                draw.text((862, 32), page_text, font=module._fit(page_text, 174, 28, 15, True), fill=module.BLACK)
            for main_index, start, end, lang in references:
                if main_index >= len(rendered):
                    continue
                draw = ImageDraw.Draw(rendered[main_index])
                label = f'Notas completas: páginas {start}–{end}' if lang == 'es' else f'Full source notes: pages {start}–{end}'
                draw.rectangle((620, 420, 1050, 454), fill=module.BLUE)
                draw.text((632, 427), label, font=module._fit(label, 404, 19, 13, True), fill=module.CREAM)
        if references:
            from .magazine_export_state_guard import remember_display_pages
            remember_display_pages(rows, rendered, report_name=report_name, language=explicit_lang)
        return rendered

    pages._ABA_SOURCE_NOTE_PAGES = True
    module.render_full_magazine_book_pages = pages
    def single_png(pick, background_image=None, report_name=None, page_number=1, total_pages=1, logo_image=None, background_mode='hero_right', logo_mode='header', background_opacity=.9, logo_opacity=1., use_team_logo=True, language=None):
        from PIL import Image
        rendered = module.render_full_magazine_book_pages([pick], background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
        book = Image.new('RGB', (module.PAGE_WIDTH, sum(page.height for page in rendered)), module.PAPER)
        y = 0
        for page in rendered:
            book.paste(page, (0, y))
            y += page.height
        return module._png(book)
    module.render_full_pick_magazine_page_png = single_png


def accounting_quarantined(row: Mapping[str, Any]) -> bool:
    return str(row.get('report_accounting_quarantined', '')).strip().lower() in {'true', '1', 'yes'}


def display_decision(row: Mapping[str, Any]) -> dict[str, Any]:
    """One fail-closed presentation decision; never promotes the source gate."""
    from .report_public_quality import has_exact_market_line
    from .report_verification_gate import classify_report_row, VERIFIED_BUYER_PICK
    data = canonical_market_row(row)
    result = classify_report_row(data)
    actionable = result.get('report_verification_class') == VERIFIED_BUYER_PICK
    action = result.get('final_decision') or 'RESEARCH ONLY'
    if accounting_quarantined(data):
        actionable, action = False, 'ACCOUNTING REVIEW'
    elif data.get('report_market_issue'):
        actionable, action = False, 'MARKET REVIEW'
    elif not has_exact_market_line(data):
        actionable, action = False, 'RESEARCH ONLY'
    result['report_display_actionable'] = actionable
    result['report_display_status'] = action
    return result
