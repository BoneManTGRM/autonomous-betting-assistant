from copy import deepcopy
import json
from pathlib import Path
import pytest
import requests
from streamlit.testing.v1 import AppTest
import streamlit as st

DOWNLOADS=[]
ORIGINAL_DOWNLOAD=st.download_button
def record_download(label,data,*args,**kwargs):
    if kwargs.get("key")=="aba_prediction_capture_download":DOWNLOADS.append(json.loads(data))
    return ORIGINAL_DOWNLOAD(label,data,*args,**kwargs)

ROOT=Path(__file__).resolve().parents[1]
ROWS=[{'event_id':'synthetic-event','event':'Synthetic A at B','prediction':'A',
       'event_start_utc':'2030-01-02T00:00:00Z','model_probability_clean':.7,
       'decimal_price':2.0,'prediction_timestamp':'','result_status':''}]

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def deny(*a,**kw):raise AssertionError('Capture must not call providers')
    monkeypatch.setattr(requests.sessions.Session,'request',deny)
    monkeypatch.setattr(st,'download_button',record_download)
    DOWNLOADS.clear()


def page(route,language,rows=None):
    app=AppTest.from_file(str(ROOT/'streamlit_app.py')).run(timeout=30)
    if rows is not None:app.session_state['pro_predictor_all_rows']=deepcopy(rows)
    app.switch_page(f'pages/{route}.py').run(timeout=30)
    if language=='es':app.radio(key='aba_radio_pro_predictor_language').set_value('Español').run(timeout=30)
    assert not app.exception
    return app


def downloaded(app):
    assert any('prediction_capture_download' in b.proto.id for b in app.get('download_button'))
    return DOWNLOADS[-1]


@pytest.mark.parametrize('route',['pro_predictor','pro_predictor_volume'])
@pytest.mark.parametrize('language',['en','es'])
def test_capture_existing_rows_without_scan_and_invalidate_on_change(route,language):
    app=page(route,language,ROWS)
    report=downloaded(app)
    assert report['row_count']==1 and report['packet_ready'] is False
    assert report['rows'][0]['captured_fields']['model_probability_clean']==.7
    assert app.session_state['pro_predictor_all_rows']==ROWS
    assert ('Descargar evidencia' if language=='es' else 'Download current prediction') in next(b.proto.label for b in app.get('download_button') if 'prediction_capture_download' in b.proto.id)
    first=report['capture_sha256'];app.run()
    assert downloaded(app)['capture_sha256']!=first
    app.session_state['pro_predictor_all_rows']=[{**ROWS[0],'event_id':'replacement'}]
    app.run()
    assert downloaded(app)['rows'][0]['captured_fields']['event_id']=='replacement'
    app.session_state['pro_predictor_all_rows']=[];app.run()
    assert not [b for b in app.get('download_button') if 'prediction_capture_download' in b.proto.id]
    assert ('No hay filas' if language=='es' else 'No current Pro Predictor') in '\n'.join(i.value for i in app.info)
    app.session_state['pro_predictor_all_rows']=[None];app.run()
    assert app.error and not app.exception
    assert not [b for b in app.get('download_button') if 'prediction_capture_download' in b.proto.id]


@pytest.mark.parametrize('route',['pro_predictor','pro_predictor_volume'])
@pytest.mark.parametrize('language',['en','es'])
def test_capture_does_not_fallback_to_held_history(route,language):
    app=page(route,language)
    app.session_state['ara_latest_predictions']=ROWS
    app.session_state['pro_predictor_latest_rows']=ROWS
    app.run()
    assert not [b for b in app.get('download_button') if 'prediction_capture_download' in b.proto.id]
    assert not app.exception
