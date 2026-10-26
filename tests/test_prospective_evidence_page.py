from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest
import requests
from streamlit.testing.v1 import AppTest

from autonomous_betting_agent import prospective_evidence as pe, proof_ledger

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'aba_prospective_v1'


def blank_filled(now):
    data = pe.preparation_template()
    data['protocol'] = {key: f'Synthetic {key}' for key in pe.PROTOCOL_FIELDS}
    row = data['predictions'][0]
    for key in pe.PREDICTION_TEXT_FIELDS:
        row[key] = f'Synthetic {key}'
    for key in pe.PREDICTION_TIME_FIELDS:
        row[key] = (now + timedelta(hours=1) if key == 'event_start' else now - timedelta(seconds=1)).isoformat()
    row.update(raw_model_probability=.7, baseline_probability=.6, decimal_odds=1.9)
    return json.dumps(data)


@pytest.fixture(autouse=True)
def no_external_or_historical_calls(monkeypatch):
    def prohibited(*args, **kwargs): raise AssertionError('No provider or legacy ledger access')
    monkeypatch.setattr(requests.sessions.Session, 'request', prohibited)
    monkeypatch.setattr(proof_ledger, 'load_ledger', prohibited)


def page(language):
    app = AppTest.from_file(str(ROOT / 'streamlit_app.py')).run(timeout=30)
    app.switch_page('pages/forward_test_tracker.py').run(timeout=30)
    if language == 'es':
        app.radio(key='aba_radio_forward_test_language').set_value('Español').run(timeout=30)
    assert not app.exception
    return app


@pytest.mark.parametrize('language', ['en', 'es'])
def test_prepare_download_and_changed_input_invalidation(language):
    app = page(language)
    app.button(key=f'{PREFIX}_prepare_button').click().run()
    assert app.warning and not app.exception
    data = blank_filled(datetime.now(timezone.utc))
    app.text_area(key=f'{PREFIX}_source').set_value(data)
    app.button(key=f'{PREFIX}_prepare_button').click().run()
    assert not app.exception and not app.error
    packet = app.session_state[f'{PREFIX}_packet']
    assert packet['original_input'] == data
    assert packet['independently_verified'] is False
    assert len(app.get('download_button')) == 3
    assert ('Paquete preparado' if language == 'es' else 'Packet prepared') in '\n'.join(x.value for x in app.info)
    app.text_area(key=f'{PREFIX}_source').set_value(data + ' ').run()
    assert f'{PREFIX}_packet' not in app.session_state
    assert len(app.get('download_button')) == 1
    app.text_area(key=f'{PREFIX}_source').set_value('{}')
    app.button(key=f'{PREFIX}_prepare_button').click().run()
    assert app.error and not app.exception
    assert f'{PREFIX}_packet' not in app.session_state


@pytest.mark.parametrize('language', ['en', 'es'])
def test_review_preserves_pending_and_changed_receipt_clears_result(language):
    past = datetime.now(timezone.utc) - timedelta(days=1)
    packet = pe.prepare_packet(blank_filled(past), now=past)
    app = page(language)
    app.radio(key=f'{PREFIX}_mode').set_value('review').run()
    app.text_area(key=f'{PREFIX}_review_packet').set_value(json.dumps(packet))
    app.button(key=f'{PREFIX}_review_button').click().run()
    assert not app.exception and not app.error
    report = app.session_state[f'{PREFIX}_review']
    assert report['pending_rows'] == report['cohort_rows'] == 1
    assert report['authenticated_rows'] == 0
    assert len(app.metric) == 12
    values = '\n'.join(x.label for x in app.metric)
    assert ('Filas sin verificar' if language == 'es' else 'Unverified rows') in values
    app.text_area(key=f'{PREFIX}_review_receipts').set_value('[{}]').run()
    assert f'{PREFIX}_review' not in app.session_state
    assert not app.metric
    app.button(key=f'{PREFIX}_review_button').click().run()
    assert not app.exception
    assert app.session_state[f'{PREFIX}_review']['rejected_receipts'] == 1


@pytest.mark.parametrize('language', ['en', 'es'])
def test_legacy_view_never_reconstructs_official_statistics(language):
    app = page(language)
    app.radio(key=f'{PREFIX}_mode').set_value('legacy').run()
    assert not app.exception and not app.metric
    assert ('historial' if language == 'es' else 'Historical') in '\n'.join(x.value for x in app.info)
    assert any('odds_lock_pro' in link.proto.page for link in app.main.get('page_link'))
    assert not app.get('dataframe')
