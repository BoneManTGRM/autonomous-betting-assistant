import pytest
from autonomous_betting_agent import dashboard_ui as ui
from autonomous_betting_agent.dashboard_data_service import build_dashboard_data


def test_empty_no_key_dashboard_is_not_connectivity_evidence():
    dashboard = build_dashboard_data([])
    assert ui.api_status_label(dashboard['api_usage']) == ui.API_OK
    display = ui.api_usage_indicator(dashboard['api_usage'])
    assert display['label'] == 'API usage'
    assert display['value'] == 'Not assessed'
    assert 'not checked' in display['help']
    assert 'connectivity' in display['help']
    assert 'credentials' in display['help']


@pytest.mark.parametrize('usage', [None, {}, {'call_limit': 0, 'usage_fraction': 0},
    {'call_limit': -1, 'usage_fraction': 0}, {'call_limit': 100, 'usage_fraction': float('nan')},
    {'call_limit': float('inf'), 'usage_fraction': 0}, {'call_limit': 100},
    {'call_limit': 100, 'usage_fraction': -1}])
def test_unassessed_usage_never_implies_api_health(usage):
    assert ui.api_usage_indicator(usage)['value'] == 'Not assessed'


@pytest.mark.parametrize('fraction,raw,text', [
    (0, ui.API_OK, 'Within usage thresholds'),
    (.74, ui.API_OK, 'Within usage thresholds'),
    (.75, ui.API_WARNING, 'Usage warning'),
    (.9, ui.API_HIGH_USAGE, 'High usage'),
    (1.2, ui.API_HIGH_USAGE, 'High usage'),
])
def test_known_usage_preserves_raw_contract_without_connectivity_claim(fraction, raw, text):
    usage = {'call_limit': 100, 'used_calls': fraction * 100, 'usage_fraction': fraction}
    before = dict(usage)
    display = ui.api_usage_indicator(usage)
    assert display['value'] == text
    assert ui.api_status_label(usage) == raw
    assert usage == before
    assert 'not checked' in display['help']


def test_spanish_labels_and_connectivity_disclaimer():
    empty = ui.api_usage_indicator(None, 'es')
    assert empty['label'] == 'Uso de API'
    assert empty['value'] == 'Sin evaluar'
    assert 'no se verifican' in empty['help']
    assert 'conectividad' in empty['help']
    known = ui.api_usage_indicator({'call_limit': 100, 'used_calls': 90, 'usage_fraction': .9}, 'es')
    assert known['value'] == 'Uso elevado'


@pytest.mark.parametrize('used', [None, -1, float('nan'), float('inf'), 'invalid'])
def test_missing_or_invalid_call_count_is_unassessed(used):
    usage = {'call_limit': 100, 'usage_fraction': 0, 'used_calls': used}
    assert ui.api_usage_indicator(usage)['value'] == 'Not assessed'


def test_missing_count_differs_from_known_zero_count():
    usage = {'call_limit': 100, 'usage_fraction': 0}
    assert ui.api_usage_indicator(usage)['value'] == 'Not assessed'
    assert ui.api_usage_indicator({**usage, 'used_calls': 0})['value'] == 'Within usage thresholds'
