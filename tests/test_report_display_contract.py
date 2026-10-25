from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from autonomous_betting_agent.report_display_contract import canonical_market_row, context_items, localized_content, team_items
from autonomous_betting_agent.report_public_quality import build_full_market_label, has_exact_market_line
from autonomous_betting_agent import magazine_second_page_patch as page2


def saved_row(**changes):
    row = {
        'event': 'North Lake vs East Harbor', 'away_team': 'North Lake', 'home_team': 'East Harbor',
        'sport': 'Basketball', 'league': 'WNBA', 'venue_type': 'indoor',
        'selected_market': 'game total', 'selected_pick': 'Over 171.5', 'selected_line': 171.5,
        'decimal_odds': 1.73, 'model_probability': .59,
        'model_market_edge': .59 - 1/1.73, 'expected_value_per_unit': .59*1.73 - 1,
        'source_mode': 'saved-handoff', 'odds_status': 'UPLOADED_ROW', 'odds_source': 'saved_row',
        'price_timestamp': '2020-01-02T03:04:05Z', 'target_stake_units': .2,
        'sports_context_summary': 'The game total is 171.5. This is not an injury report.',
        'perplexity_context': 'Never recycle this paragraph as team or injury evidence.',
        'weather_summary': 'Weather: Rain outdoors.', 'report_title': 'Daily Sports Analysis',
    }
    row.update(changes)
    return row


def test_canonical_selection_and_line_are_consistent_and_read_only():
    raw = saved_row()
    before = deepcopy(raw)
    resolved = canonical_market_row(raw)
    assert build_full_market_label(resolved) == 'Game Total: Over 171.5'
    assert has_exact_market_line(resolved)
    assert raw == before
    assert not has_exact_market_line(saved_row(selected_line=170.5))
    assert 'Conflicting market values' in build_full_market_label(saved_row(provider_line=170.5))


def test_narrative_does_not_supply_missing_market_side_or_line():
    row = saved_row(selected_pick='', selected_line='', sports_context_summary='Over 171.5 looks attractive.')
    assert not has_exact_market_line(row)
    assert 'Missing exact market line' in build_full_market_label(row)
    assert build_full_market_label(saved_row(selected_pick='', selected_line=171.5)) == 'Game Total: Missing selection side'


def test_side_specific_content_requires_explicit_locale_not_word_guessing():
    row = saved_row(team_snapshot_home='Local form is improving.', team_snapshot_home_language='en')
    assert team_items(row, 'home', 'en') == ['Local form is improving.']
    assert 'Local form' not in ' '.join(team_items(row, 'away', 'en'))
    assert 'idioma solicitado' in ' '.join(team_items(row, 'home', 'es'))
    row['team_snapshot_home_es'] = 'El equipo local mejora su forma.'
    assert team_items(row, 'home', 'es') == ['El equipo local mejora su forma.']
    assert 'Never recycle' not in ' '.join(team_items(row, 'home', 'en', injury=True))
    assert localized_content({'note': 'texto'}, ('note',), 'es')[1] == 'No se indicó el idioma del contenido.'


def test_indoor_weather_is_not_presented_as_predictive_evidence():
    items = context_items(saved_row(), 'es')
    assert any('recinto cubierto' in item for item in items)
    assert not any('Rain' in item or 'Weather:' in item for item in items)


def test_zero_eligible_saved_selection_is_not_a_straight_bet_anchor():
    row = canonical_market_row(saved_row())
    candidates, diagnostics = page2.generate_parlay_candidates(row)
    assert diagnostics['eligible_legs'] == 0
    assert not any(p.status == page2.PARLAY_PLAYABLE for p in candidates)
    assert page2._final_status(row, 'en', parlays=candidates, diagnostics=diagnostics)[0] == 'NO VERIFIED SELECTION'
    text = '\n'.join(item for _, items, _ in page2._page_two_sections(row, 'es', parlays=candidates, diagnostics=diagnostics) for item in items)
    assert 'Elegibles: 0; necesarias: 2.' in text
    assert 'STRAIGHT ANCHOR ONLY' not in text
    assert 'SOLO ANCLA DIRECTA' not in text


def test_stale_provider_timestamp_cannot_become_an_eligible_parlay_leg():
    row = canonical_market_row(saved_row(source_mode='current-run', odds_source='Odds API', provider='Odds API',
                                         provider_event_id='fixture-event', sportsbook='Fixture Book', odds_status='LIVE', provider_verified=True))
    candidates, diagnostics = page2.generate_parlay_candidates(row)
    assert diagnostics['eligible_legs'] == 0
    assert not any(p.status == page2.PARLAY_PLAYABLE for p in candidates)
    assert 'stale' in page2._final_status(row, 'en')[1]


def test_report_preparation_preserves_receipts_and_observation_time(monkeypatch):
    from autonomous_betting_agent import magazine_pipeline_runtime as runtime
    monkeypatch.setattr(runtime, 'check_api_health', lambda **kw: {})
    row = saved_row(field_provenance_json='{"model":"original"}', source_trace_json='{"receipt":"original"}',
                    model_probability_source='fixture-model-v1', last_api_refresh_time='2020-01-02T03:04:05Z',
                    odds_api_live=True, odds_api_summary='Old saved live flag and payload')
    before = deepcopy(row)
    prepared = runtime.build_final_enriched_picks_df([row]).iloc[0].to_dict()
    assert row == before
    assert prepared['source_trace_json'] == row['source_trace_json']
    assert prepared['field_provenance_json'] == row['field_provenance_json']
    assert prepared['model_probability_source'] == 'fixture-model-v1'
    assert prepared['price_timestamp'] == prepared['source_observed_at'] == row['price_timestamp']
    assert prepared['last_api_refresh_time'] == row['last_api_refresh_time']
    assert prepared['data_freshness_status'] == 'STORED_UNVERIFIED'
    assert prepared['odds_status'] != 'LIVE'
    assert prepared['report_generated_at'] != row['price_timestamp']


@pytest.mark.parametrize('runtime_on', [False, True])
def test_full_export_path_both_locales_and_lossless_overflow(tmp_path, runtime_on):
    root = Path(__file__).resolve().parents[1]
    script = Path(__file__).with_name('report_display_render_probe.py')
    env = dict(os.environ, PYTHONPATH=str(root), GITHUB_ACTIONS='true', ABA_REPORT_PROBE_RUNTIME='1' if runtime_on else '0')
    result = subprocess.run([sys.executable, str(script), str(tmp_path)], cwd=root, env=env, text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads((tmp_path/'render_evidence.json').read_text())
    assert payload['network_attempts'] == 0
    assert payload['unchanged_inputs'] is True
    assert payload['actual_cards_cache_path'] is True
    assert len(payload['edge_results']) == 24
    for lang in ('en', 'es'):
        assert payload[lang]['short_pages'] == 2
        assert payload[lang]['long_pages'] > 2
        assert payload[lang]['pdf_pages'] == payload[lang]['long_pages']
        assert payload[lang]['all_long_text_present']
        assert not payload[lang]['overflow_outside_page']
        assert payload[lang]['stale_status'] == ('SIN SELECCIÓN VERIFICADA' if lang == 'es' else 'NO VERIFIED SELECTION')
        assert payload[lang]['missing_line']
    spanish = payload['es']['visible_text']
    for old_bug in ('Model projects', 'PRICE STATUS', 'Saved row with', 'Recheck required', 'SOURCE NOTES', 'STRAIGHT ANCHOR ONLY', 'modelorobability', 'Weather:', 'GAME TOTAL:', 'MISSING EXACT', 'ONLY'):
        assert old_bug not in spanish
    assert 'ANÁLISIS DEPORTIVO DIARIO' in spanish
    assert 'SIN APUESTA' in spanish


def test_accounting_quarantine_cannot_be_repainted_as_verified():
    from autonomous_betting_agent.active_magazine_export_guard import normalize_row
    from autonomous_betting_agent.magazine_sale_ready_patch import _force_truthful_gate
    row = saved_row(report_accounting_quarantined=True, report_accounting_status='conflict',
                    provider_verified=True, source_mode='current-run', provider='Odds API',
                    sportsbook='Fixture Book', provider_event_id='fixture-event', price_timestamp='now')
    before = deepcopy(row)
    assert normalize_row(row)['final_decision'] == 'RESEARCH ONLY'
    assert _force_truthful_gate(row)['risk'] == 'ACCOUNTING REVIEW'
    candidates, diagnostics = page2.generate_parlay_candidates(canonical_market_row(row))
    assert not any(p.status == page2.PARLAY_PLAYABLE for p in candidates)
    assert page2._final_status(row, 'es')[0] == 'REVISIÓN CONTABLE'
    assert page2._final_status(row, 'es')[1] == 'Se requiere revisión contable antes de publicar el reporte.'
    assert row == before


def current_row(**changes):
    return saved_row(source_mode='current-run', odds_status='CURRENT', odds_source='Odds API', provider='Odds API',
        sportsbook='Fixture Book', provider_event_id='fixture-one', provider_verified=True,
        price_timestamp=datetime.now(timezone.utc).isoformat(), **changes)


@pytest.mark.parametrize('changes', [
    {'selection': 'Under 170.5'}, {'total': 170.5}, {'market': 'moneyline'},
    {'verified_provider_event_id': 'other-fixture'}, {'current_line': 170.5},
    {'prediction': 'Under 171.5'}, {'selected_line': 170.5}, {'odds_api_event_id': 'different-same-provider-id'},
])
def test_conflicting_structured_aliases_fail_closed_everywhere(changes):
    from autonomous_betting_agent.report_display_contract import display_decision
    row = current_row()
    row.update(changes)
    original = deepcopy(row)
    canonical = canonical_market_row(row)
    assert not has_exact_market_line(row)
    assert canonical['report_field_conflicts']
    assert canonical_market_row(canonical)['report_field_conflicts'] == canonical['report_field_conflicts']
    assert 'Conflicting market values' in build_full_market_label(row)
    assert not display_decision(row)['report_display_actionable']
    assert not page2._leg_is_eligible(page2._anchor_market(row))[0]
    assert page2._final_status(row, 'en')[0] == 'NO VERIFIED SELECTION'
    assert row == original


def test_equivalent_localized_aliases_and_distinct_model_projections_do_not_conflict():
    row = current_row()
    row.update(selection='Over', public_pick='Total del partido: Más de 171.5', market='totals',
        model_total=178.5, projected_total=179.5, odds_api_event_id='fixture-one', sportsdataio_event_id='sdio-namespace')
    assert has_exact_market_line(row)
    assert build_full_market_label(row) == 'Game Total: Over 171.5'
    assert page2._leg_is_eligible(page2._anchor_market(row))[0]
    assert build_full_market_label(dict(selected_market='Total del partido', selected_pick='Más de 171.5', selected_line=171.5)) == 'Game Total: Over 171.5'
    assert build_full_market_label(dict(market='moneyline', selection='Philadelphia 76ers')) == 'Moneyline: Philadelphia 76ers'


def test_child_market_owns_aliases_but_cannot_clear_parent_quarantine():
    parent = current_row()
    child = dict(market='team total', selection='North Lake Under 80.5', line=80.5, decimal_odds=2.0, model_probability=.6)
    candidate = page2._candidate(child, parent, 'basketball')
    assert candidate.full_label == 'Team Total: North Lake Under 80.5'
    assert page2._leg_is_eligible(candidate)[0]
    parent['report_accounting_quarantined'] = True
    child['report_accounting_quarantined'] = False
    candidate = page2._candidate(child, parent, 'basketball')
    assert not page2._leg_is_eligible(candidate)[0]
    assert candidate.rejection_reason == 'Accounting review required before report publication.'


def test_fresh_receipt_is_not_replaced_by_generic_timestamp_or_generation_time(monkeypatch):
    from autonomous_betting_agent import magazine_pipeline_runtime as runtime
    monkeypatch.setattr(runtime, 'check_api_health', lambda **kw: {})
    row = current_row(odds_api_live=True, odds_api_summary='Supplied observation', timestamp='2020-01-01T00:00:00Z')
    prepared = runtime.build_final_enriched_picks_df([row]).iloc[0].to_dict()
    assert prepared['price_timestamp'] == prepared['source_observed_at'] == row['price_timestamp']
    assert prepared['odds_last_refresh'] == row['price_timestamp']
    assert prepared['odds_last_refresh'] != prepared['report_generated_at']
    row['source_observed_at'] = '2020-01-01T00:00:00Z'
    old = runtime.build_final_enriched_picks_df([row]).iloc[0].to_dict()
    assert old['odds_status'] != 'LIVE'
    assert old['price_timestamp'] == row['source_observed_at']


def cache_roundtrip_functions():
    # Load only the actual pure cache serialization functions, not Streamlit UI side effects.
    import ast
    path = Path(__file__).resolve().parents[1] / 'pages/report_studio.py'
    module = ast.parse(path.read_text())
    selected = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name in {'serializable_row', 'deserialize_row'}]
    scope = {'json': json}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), scope)
    return scope['serializable_row'], scope['deserialize_row']


def test_preview_cache_roundtrip_preserves_nested_market_quote_and_evidence_types():
    serialize, deserialize = cache_roundtrip_functions()
    row = current_row()
    row['available_markets'] = [dict(market='game total', selection='Under 8.5', line=8.5, decimal_odds=2.0,
        model_probability=.6, edge=.1, ev=.2, event='West Bay vs South Park', provider_event_id='fixture-two')]
    row['report_accounting_quarantined'] = False
    row['source_receipt'] = {'origin': 'fixture', 'fields': ['line', 'odds'], 'count': 2}
    roundtrip = deserialize(serialize(row))
    assert roundtrip == row
    assert page2.generate_parlay_candidates(roundtrip)[1]['eligible_legs'] == page2.generate_parlay_candidates(row)[1]['eligible_legs'] == 2
    assert serialize(dict(row, report_language='es')) != serialize(dict(row, report_language='en'))
    assert deserialize((('untrusted', "__import__('os').remove('never-execute')"),))['untrusted'].startswith('__import__')


@pytest.mark.parametrize('sport', ['Soccer', 'Basketball', 'Baseball', 'MMA', 'Boxing', 'Football', 'Hockey'])
def test_actual_cards_and_snapshot_enrichment_are_offline_even_with_configured_keys(monkeypatch, sport):
    from autonomous_betting_agent import magazine_live_api_enrichment as enrichment
    from autonomous_betting_agent import sports_context
    from autonomous_betting_agent.report_studio_service import build_report_studio_cards, ReportStudioFilters
    calls = []
    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError('Report snapshot must never call providers')
    monkeypatch.setattr(enrichment, '_secret', lambda names: 'synthetic-configured-key')
    monkeypatch.setattr(sports_context, '_secret', lambda name: 'synthetic-configured-key')
    monkeypatch.setattr(enrichment, '_request_json', forbidden)
    monkeypatch.setattr(sports_context.ApiMmaContextProvider, '_api_get', forbidden)
    row = saved_row(sport=sport, venue='Fixture venue', model_probability_source='receipt-model-v9',
        source_trace_json='{"receipt":"original"}', sports_context_summary='Original context.', sports_context_summary_language='en')
    original = deepcopy(row)
    for lang in ('en', 'es'):
        cards = build_report_studio_cards([row], ReportStudioFilters(language=lang), source_note='saved:current handoff')[-1]
        assert len(cards) == 1
        card = cards.iloc[0].to_dict()
        assert card['model_probability_source'] == 'receipt-model-v9'
        assert card['sports_context_summary'] == 'Original context.'
        assert card['sports_context_summary_language'] == 'en'
        assert card['source_trace_json'] == row['source_trace_json']
        prepared = enrichment.prepare_report_snapshot_row(card)
        assert prepared['report_provider_calls_allowed'] is False
        assert prepared['sports_context_summary'] == 'Original context.'
    assert not calls
    assert row == original


@pytest.mark.parametrize('pick,other', [('O171.5','Under171.5'), ('O 171.5','Under 171.5'), ('U171.5','Over171.5'), ('U 171.5','Over 171.5')])
def test_existing_total_shorthand_cannot_bypass_alias_conflict(pick, other):
    row = current_row()
    row.update(selected_pick=pick, selection=other)
    assert not has_exact_market_line(row)
    assert not page2._leg_is_eligible(page2._anchor_market(row))[0]


@pytest.mark.parametrize('minus', ['−', '–', '—', '-'])
def test_mobile_minus_and_spread_line_aliases_are_compared(minus):
    row = dict(selected_market='spread', selected_pick=f'Phoenix {minus}1.5', provider_line=1.5)
    assert not has_exact_market_line(row)
    assert 'Conflicting market values' in build_full_market_label(row)
    assert build_full_market_label(dict(selected_market='spread', selected_pick=f'Phoenix {minus}1.5', line=f'{minus}1.5')) == 'Spread: Phoenix -1.5'


@pytest.mark.parametrize('row,prefix', [
    (dict(market_type='player points', selected_pick='Jordan Smith Over21.5', selection='Jordan Smith Over21.5', player='Jordan Smith', prop_name='points', line=21.5), 'Player Prop: Jordan Smith Over 21.5 points'),
    (dict(market_type='team total', selected_pick='France Over2.5', selection='France Over2.5', line=2.5), 'Team Total: France Over 2.5'),
])
def test_distinct_market_families_survive_repeated_display_normalization(row, prefix):
    from autonomous_betting_agent.active_magazine_export_guard import normalize_row
    from autonomous_betting_agent.magazine_sale_ready_patch import _force_truthful_gate
    original = deepcopy(row)
    for _ in range(3):
        row = _force_truthful_gate(normalize_row(row))
        assert not row.get('report_market_issue')
        assert build_full_market_label(row) == prefix
        assert has_exact_market_line(row)
    assert 'report_market_issue' not in original


def test_rejected_child_identity_and_all_missing_fields_remain_visible():
    row = current_row()
    row['available_markets'] = [dict(market='player points', selection='Over21.5', line=21.5, decimal_odds=2.0,
        event='West Bay vs South Park', provider_event_id='fixture-two', player='Unique Player')]
    for lang in ('en', 'es'):
        rendered = '\n'.join(item for title, items, color in page2._page_two_sections(row, lang) for item in items)
        assert 'Unique Player' in rendered
        assert 'West Bay vs South Park' in rendered
        assert ('market-specific model probability' if lang == 'en' else 'probabilidad del modelo específica') in rendered
        summary, details = page2._market_scan_report(row, lang)
        assert ('Lines:' if lang == 'en' else 'Líneas:') in summary
        assert ('Rejection reasons:' if lang == 'en' else 'Motivos de rechazo:') in '\n'.join(details)


def test_headline_fit_preserves_every_character_before_accepting_layout():
    from PIL import Image, ImageDraw
    from autonomous_betting_agent import magazine_book_export as renderer
    draw = ImageDraw.Draw(Image.new('RGB', (1080, 1620)))
    for name in ('University of California Golden Bears', 'North Carolina Agricultural and Technical State Aggies', 'A_SINGLE_SUPERLONGUNBROKENFOOTBALLCLUBNAME'):
        font, lines = renderer._fit_lines_to_box(draw, name, renderer.AWAY_HEADLINE_BOX, 60, 6, 2, True)
        assert ''.join(''.join(lines).split()) == ''.join(name.upper().split())
        assert len(lines) <= 2
        assert all(renderer._text_width(draw, line, font) <= renderer._rect_w(renderer.AWAY_HEADLINE_BOX) for line in lines)


def test_identical_market_labels_in_distinct_events_keep_distinct_eligible_identity():
    row = current_row()
    row['available_markets'] = [dict(market='game total', selection='Over 171.5', line=171.5, decimal_odds=1.73, model_probability=.59, event='West Bay vs South Park', provider_event_id='fixture-two')]
    parlays, diagnostics = page2.generate_parlay_candidates(row)
    assert diagnostics['eligible_legs'] == 2
    assert any(len(candidate.legs) == 2 for candidate in parlays)
    assert 'eligible: 2' in page2._market_scan_report(row, 'en')[0]


def test_zero_playable_counts_do_not_get_success_bullets():
    assert page2._status_bullet_color('Candidates: 0 · playable: 0 · watchlist: 0.', page2.BLUE) == page2.BLUE
    assert page2._status_bullet_color('Candidatos: 0 · jugables: 0 · seguimiento: 0.', page2.BLUE) == page2.BLUE
    assert page2._status_bullet_color('NOT PLAYABLE', page2.BLUE) == page2.RED
