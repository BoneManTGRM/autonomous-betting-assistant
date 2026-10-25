"""Standalone, network-prohibited integration probe (not a production entry point)."""
from copy import deepcopy
from io import BytesIO
import importlib
import json
import os
from pathlib import Path
import re
import socket
import sys

out = Path(sys.argv[1])
network_attempts = []
def no_network(*args, **kwargs):
    network_attempts.append(True)
    raise RuntimeError('Network is prohibited in the report display probe')
socket.socket.connect = no_network
socket.create_connection = no_network
if os.environ['ABA_REPORT_PROBE_RUNTIME'] == '1':
    os.environ.pop('GITHUB_ACTIONS', None)
    import sitecustomize, usercustomize
    importlib.reload(sitecustomize)
    importlib.reload(usercustomize)
import autonomous_betting_agent.magazine_book_export as book
from autonomous_betting_agent.magazine_live_api_enrichment import install as install_live
from autonomous_betting_agent.magazine_report_polish_patch import install as install_polish
from autonomous_betting_agent.magazine_sale_ready_patch import apply_magazine_sale_ready_patch
import autonomous_betting_agent.report_studio_spanish_ui
book = apply_magazine_sale_ready_patch(install_live(importlib.reload(book)))
install_polish()
from autonomous_betting_agent.report_display_contract import canonical_market_row
from autonomous_betting_agent import magazine_second_page_patch as p2
from PIL import ImageDraw
base = {
    'event': 'North Lake vs East Harbor', 'away_team': 'North Lake', 'home_team': 'East Harbor',
    'sport': 'Basketball', 'league': 'WNBA', 'venue_type': 'indoor',
    'selected_market': 'game total', 'selected_pick': 'Over 171.5', 'selected_line': 171.5,
    'decimal_odds': 1.73, 'model_probability': .59, 'model_probability_source': 'receipt-model-v9', 'model_market_edge': .59 - 1/1.73, 'expected_value_per_unit': .59*1.73 - 1,
    'source_mode': 'saved-handoff', 'odds_status': 'UPLOADED_ROW', 'odds_source': 'saved_row',
    'price_timestamp': '2020-01-02T03:04:05Z', 'target_stake_units': .2,
    'sports_context_summary': 'The game total is 171.5.', 'perplexity_context': 'General context is not an injury report.',
    'weather_summary': 'Weather: Rain outdoors.', 'report_title': 'Daily Sports Analysis',
}
before = deepcopy(base)
result = {}
original = ImageDraw.ImageDraw.text
for lang in ('en', 'es'):
    row = dict(base, report_language=lang)
    draws = []
    def capture(self, xy, text, *args, **kwargs):
        draws.append((xy, str(text), kwargs.get('font')))
        return original(self, xy, text, *args, **kwargs)
    ImageDraw.ImageDraw.text = capture
    short = book.render_full_magazine_book_pages([row], language=lang, report_name='ABA FIXTURE')
    visible = '\n'.join(t for xy,t,font in draws)
    for i,page in enumerate(short): page.save(out/f'{lang}_short_{i+1}.png')
    # Unknown raw prose is never translated by guessed word substitution.
    long_text = ('Observación detallada del equipo local: el registro incluye evidencia específica y conserva toda la nota. ' if lang == 'es' else 'Detailed home-team observation: the record contains specific evidence and preserves the complete source note. ') * 35
    long_text += ' MARCADOR_FINAL_7391' if lang == 'es' else ' END_MARKER_7391'
    longrow = dict(row, **{f'team_snapshot_home_{lang}':long_text})
    draws.clear()
    long_pages = book.render_full_magazine_book_pages([longrow], language=lang, report_name='ABA FIXTURE')
    joined = ' '.join(t for xy,t,font in draws)
    all_present = ('MARCADOR_FINAL_7391' if lang == 'es' else 'END_MARKER_7391') in joined
    # Each overflow page starts at SOURCE NOTES; only those draws must be complete and inside its content rectangle.
    overflow_outside = False
    in_overflow = False
    for xy,t,font in draws:
        if t in {'SOURCE NOTES','NOTAS DE FUENTES'}:
            in_overflow = True
        if in_overflow and font is not None:
            box = font.getbbox(t)
            if xy[0] < 0 or xy[1] < 0 or xy[0]+box[2] > 1080 or xy[1]+box[3] > 1620:
                overflow_outside = True
    for i,page in enumerate(long_pages): page.save(out/f'{lang}_long_{i+1}.png')
    ImageDraw.ImageDraw.text = original
    # Exercise the actual public PDF export too; it must include the same continuation count.
    pdf = book.render_full_magazine_book_pdf([longrow], language=lang, report_name='ABA FIXTURE')
    assert pdf.startswith(b'%PDF')
    (out/f'{lang}_long.pdf').write_bytes(pdf)
    missing = canonical_market_row(dict(row, selected_pick='', selected_line='', sports_context_summary='Over 171.5'))
    result[lang] = {'short_pages':len(short), 'long_pages':len(long_pages), 'pdf_pages':len(re.findall(rb'/Type\s*/Page\b',pdf)),
        'all_long_text_present':all_present, 'overflow_outside_page':overflow_outside, 'visible_text':visible,
        'stale_status':p2._final_status(canonical_market_row(row),lang)[0],
        'missing_line': 'Missing exact market line' in p2.build_full_market_label(missing)}
result['network_attempts'] = len(network_attempts)
result['unchanged_inputs'] = base == before
(out/'render_evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))

# Exercise the actual cards -> branding -> cache serialization -> selected PNG path.
import ast
from datetime import datetime, timezone
from PIL import Image
from autonomous_betting_agent.report_studio_service import build_report_studio_cards, ReportStudioFilters
from autonomous_betting_agent import magazine_live_api_enrichment as enrichment
from autonomous_betting_agent import sports_context
for provider in (enrichment, sports_context):
    provider._secret = lambda *args: 'synthetic-configured-key'
enrichment._request_json = no_network
sports_context.ApiMmaContextProvider._api_get = no_network
source = Path(__file__).resolve().parents[1] / 'pages/report_studio.py'
names = {'with_report_language', 'with_report_branding', 'serializable_row', 'deserialize_row', 'cached_render_full_pick_magazine_page_png'}
functions = [n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name in names]
for node in functions:
    node.decorator_list = []
scope = {'json':json, 'magazine_book_export':book, 'prepare_report_snapshot_rows':enrichment.prepare_report_snapshot_rows}
exec(compile(ast.Module(body=functions,type_ignores=[]), str(source), 'exec'),scope)
edge_results = {}
for sport in ('Soccer', 'Basketball', 'Baseball', 'MMA', 'Boxing', 'Football', 'Hockey'):
    for locale in ('en', 'es'):
        synthetic = dict(base, sport=sport, venue='Fixture venue')
        prepared_cards = build_report_studio_cards([synthetic], ReportStudioFilters(language=locale), source_note='saved:fixture')[-1]
        snapshots = enrichment.prepare_report_snapshot_rows(prepared_cards.to_dict('records'))
        assert snapshots and all(row['report_provider_calls_allowed'] is False for row in snapshots)
assert not network_attempts
for lang in ('en', 'es'):
    # Source observations remain immutable throughout the actual upstream cards path.
    upstream = dict(base, model_probability_source='receipt-model-v9', source_trace_json='{"receipt":"original"}',
        sports_context_summary='Original source context.', sports_context_summary_language='en')
    cards = build_report_studio_cards([upstream], ReportStudioFilters(language=lang), source_note='saved:current handoff')[-1]
    card = cards.iloc[0].to_dict()
    assert card['model_probability_source'] == 'receipt-model-v9'
    assert card['sports_context_summary'] == upstream['sports_context_summary']
    assert card['sports_context_summary_language'] == 'en'
    row = scope['with_report_branding'](card, 'ABA FIXTURE', 'Daily Sports Analysis', lang)
    preview = scope['cached_render_full_pick_magazine_page_png'](scope['serializable_row'](row), None, 'ABA FIXTURE', 1, 1, lang, 'test', 'test', 'test', 'test')
    direct = book.render_full_magazine_book_pages([row],language=lang,report_name='ABA FIXTURE')
    assert Image.open(BytesIO(preview)).height == sum(page.height for page in direct)
    (out/f'{lang}_cards_cached.png').write_bytes(preview)
    pdf = book.render_full_magazine_book_pdf([row], language=lang, report_name='ABA FIXTURE')
    assert len(re.findall(rb'/Type\s*/Page\b', pdf)) == len(direct)
    (out/f'{lang}_cards.pdf').write_bytes(pdf)
    current = dict(base, source_mode='current-run', odds_status='CURRENT', odds_source='Odds API', provider='Odds API',
        sportsbook='Fixture Book', provider_event_id='fixture-one', provider_verified=True, price_timestamp=datetime.now(timezone.utc).isoformat())
    fixtures = {
        'stale_current':dict(current,price_timestamp='2020-01-01T00:00:00Z'),
        'quarantine_current':dict(current,report_accounting_quarantined=True),
        'missing_line':dict(current,selected_pick='Over',selected_line=''),
        'conflict_side':dict(current,selection='Under 170.5'),
        'conflict_total':dict(current,total=170.5),
        'unverified_current':dict(current,provider_event_id='',provider_verified=False,provider='',odds_source='unknown'),
    }
    reason = ('El registro del partido incluye información importante para comprender el resultado esperado y las condiciones particulares de este encuentro. ' if lang == 'es' else 'The matchup record contains important information to understand the expected outcome and the particular playing conditions for this event. ')
    fixtures['rejected_child'] = dict(current, available_markets=[dict(market='player points', selection='Over21.5', line=21.5, decimal_odds=2.0, event='West Bay vs South Park', provider_event_id='fixture-two', player='Unique Player')])
    fixtures['long_names'] = dict(base, away_team='University of California Golden Bears', home_team='North Carolina Agricultural and Technical State Aggies', event='University of California Golden Bears vs North Carolina Agricultural and Technical State Aggies')
    fixtures['rationale_short'] = dict(base, **{f'why_pick_{lang}':reason*2+' FINAL_REASON_7391'})
    fixtures['injury_short'] = dict(base, **{f'home_injuries_{lang}':reason+' FINAL_INJURY_7391'})
    fixtures['context_short'] = dict(base, **{f'sports_context_summary_{lang}':reason+' FINAL_CONTEXT_7391'})
    fixtures['weather_long'] = dict(base,sport='Baseball',venue_type='outdoor', **{f'weather_summary_{lang}':reason*20+' FINAL_WEATHER_7391'})
    for name, fixture in fixtures.items():
        draws=[]
        ImageDraw.ImageDraw.text=capture
        pages=book.render_full_magazine_book_pages([fixture],language=lang,report_name='ABA FIXTURE')
        ImageDraw.ImageDraw.text=original
        texts=' '.join(t for xy,t,font in draws)
        marker={'rationale_short':'FINAL_REASON_7391','injury_short':'FINAL_INJURY_7391','context_short':'FINAL_CONTEXT_7391','weather_long':'FINAL_WEATHER_7391'}.get(name)
        if name == 'rejected_child':
            assert 'Unique Player' in texts
            if lang == 'es':
                assert 'Proveedor: Odds API.' in texts
                assert 'Proveedor: cuota API.' not in texts
            assert ('market-specific model probability' if lang == 'en' else 'probabilidad del modelo específica') in texts
        elif marker:
            assert marker in texts, (lang,name,'source text dropped')
        else:
            assert pages[0].info['report_display_actionable'] is False, (lang,name)
            assert pages[0].info['report_display_status'] not in {'PLAY','JUGAR','VERIFIED CANDIDATE / PLAYABLE VALUE'}
        if name == 'long_names':
            headline_text = ''.join(''.join(t.split()) for xy,t,font in draws if xy[1] < 330)
            assert ''.join(fixture['away_team'].upper().split()) in headline_text
            assert ''.join(fixture['home_team'].upper().split()) in headline_text
        for i,page in enumerate(pages):page.save(out/f'{lang}_{name}_{i+1}.png')
        edge_results[f'{lang}_{name}']={'pages':len(pages),'status':pages[0].info['report_display_status'],'actionable':pages[0].info['report_display_actionable'],'marker_present':bool(marker and marker in texts)}
assert not network_attempts
result['edge_results']=edge_results
result['actual_cards_cache_path']=True
(out/'render_evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
