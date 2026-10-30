from copy import deepcopy
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json

import numpy as np
import pytest

from autonomous_betting_agent import prediction_stage_evidence as stage

NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)


def capture(rows, **kwargs):
    return stage.capture_stage_evidence(rows, origin_route='pro_predictor', now=NOW, **kwargs)


def test_detached_exact_stage_values_and_unknowns():
    rows = [{'event_id': 'same', 'model_probability': .61, 'market_probability': .6,
             'prediction_timestamp': '', 'api_key': 'SECRET', 'result_status': 'win'},
            {'event_id': 'same', 'model_probability': 0.0}]
    before = deepcopy(rows)
    output = capture(rows)
    assert rows == before and output == capture(rows)
    result = json.loads(output)
    assert result['row_count'] == 2
    assert result['rows'][0]['fields']['stage_model_probability'] == .61
    assert result['rows'][1]['fields']['stage_model_probability'] == 0
    assert result['stage_captured_at'] == NOW.isoformat()
    assert 'SECRET' not in output and 'api_key' not in output and 'result_status' not in output
    for key in ['packet_ready', 'training_allowed', 'promotion_allowed', 'predictive_gain_proven',
                'capture_time_is_prediction_time', 'complete_scanned_population', 'independently_verified']:
        assert result[key] is False
    assert 'raw_model_probability' not in output and 'baseline_probability' not in output
    digest = result.pop('content_sha256')
    canonical = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    assert digest == hashlib.sha256(canonical.encode()).hexdigest()
    rows[0]['model_probability'] = .99
    result['rows'][0]['fields']['stage_model_probability'] = .1
    assert json.loads(output)['rows'][0]['fields']['stage_model_probability'] == .61
    assert rows[0]['model_probability'] == .99


@pytest.mark.parametrize('value,tag', [(float('nan'), 'NaN'), (float('inf'), '+Infinity'), (-float('inf'), '-Infinity')])
def test_nonfinite_explicit(value, tag):
    result = json.loads(capture([{'model_probability': value}]))
    assert result['rows'][0]['fields']['stage_model_probability'] == {'nonfinite_number': tag}


@pytest.mark.parametrize('rows', [[], None, {}, [None], [{}] * 1001, [{1: 'bad'}],
    [{'event': 'x' * 10001}], [{'model_probability': Fraction(1, 3)}],
    [{'model_probability': np.longdouble('1e4000')}], [{'event': {'nested': 'bad'}}]])
def test_fail_whole_capture(rows):
    with pytest.raises(ValueError):
        capture(rows)


def test_limits_and_no_custom_repr(monkeypatch):
    class Unsafe:
        def __repr__(self):
            raise AssertionError('No repr allowed')
        __str__ = __repr__
    with pytest.raises(ValueError):
        capture([{}, {'event': Unsafe()}])
    monkeypatch.setattr(stage, 'MAX_BYTES', 100)
    with pytest.raises(ValueError):
        capture([{}])


def test_clock_origin_and_missing_not_backfilled():
    with pytest.raises(ValueError):
        stage.capture_stage_evidence([{}], origin_route='pro_predictor', now=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError):
        stage.capture_stage_evidence([{}], origin_route='history', now=NOW)
    result = json.loads(capture([{}]))
    assert result['rows'][0]['fields'] == {}
    assert set(result['rows'][0]['missing_stage_fields']) == set(stage.FIELDS.values())


def test_no_io_and_numeric_support(monkeypatch):
    import builtins
    import socket
    def deny(*args, **kwargs):
        raise AssertionError('No I/O')
    monkeypatch.setattr(builtins, 'open', deny)
    monkeypatch.setattr(socket.socket, 'connect', deny)
    for value in [np.float32(.5), np.float64(.5), np.int64(0)]:
        assert json.loads(capture([{'model_probability': value}]))['rows'][0]['fields']['stage_model_probability'] == value


def test_custom_scalar_and_container_hooks_never_run():
    class CustomInt(int):
        def __int__(self):
            raise AssertionError('Custom conversion ran')
    class CustomText(str):
        def __len__(self):
            raise AssertionError('Custom length ran')
    class CustomList(list):
        def __len__(self):
            raise AssertionError('Custom container ran')
    class CustomDict(dict):
        def __iter__(self):
            raise AssertionError('Custom iteration ran')
    for rows in [[{'bookmaker_count': CustomInt(1)}], [{'event': CustomText('x')}],
                 CustomList([{}]), [CustomDict(event='x')]]:
        with pytest.raises(ValueError):
            capture(rows)
