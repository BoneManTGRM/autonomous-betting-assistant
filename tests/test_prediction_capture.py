from copy import deepcopy
from datetime import datetime, timezone
import json
import pytest
from autonomous_betting_agent.prediction_capture import capture_predictions
NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)

def test_existing_predictor_fields_are_retained_not_relabelled_as_raw():
    rows=[{'event_id':'e','event':'A at B','prediction':'A','model_probability_clean':.7,'decimal_price':2.1,'prediction_timestamp':'','event_start_utc':'2030-01-02T00:00:00Z'}]
    before=deepcopy(rows);r=capture_predictions(rows,now=NOW)
    assert rows==before
    assert r['row_count']==1 and not r['packet_ready'] and not r['training_allowed']
    assert r['rows'][0]['captured_fields']['model_probability_clean']==.7
    assert 'raw_model_probability' in r['rows'][0]['missing_fields']
    assert 'raw_probability_available_at' in r['rows'][0]['missing_fields']
    assert r['rows'][0]['captured_fields']['prediction_timestamp']==''
    assert r['capture_time_is_prediction_time'] is False

def test_preserves_every_row_and_flags_unsafe_values():
    r=capture_predictions([{'event_id':'a','model_probability_clean':float('nan'),'api_key':'SECRET'}, {'event_id':'a','model_probability_clean':float('inf')}, {'event_id':'b','model_probability_clean':0.0}],now=NOW)
    assert r['row_count']==3
    assert r['rows'][0]['captured_fields']['model_probability_clean']=={'nonfinite_number':'NaN'}
    assert r['rows'][1]['captured_fields']['model_probability_clean']=={'nonfinite_number':'+Infinity'}
    assert r['rows'][2]['captured_fields']['model_probability_clean']==0.0
    assert 'SECRET' not in json.dumps(r,allow_nan=False)
    assert 'api_key' in r['rows'][0]['omitted_field_names']

@pytest.mark.parametrize('rows',[None,[],{},'bad',[None],[{}]*1001])
def test_invalid_sources_fail_closed(rows):
    with pytest.raises(ValueError):capture_predictions(rows,now=NOW)


def test_numeric_capture_never_rounds_unrecognized_real_values():
    from fractions import Fraction
    import numpy as np
    for value in [Fraction(1,3), np.longdouble('1e4000')]:
        with pytest.raises(ValueError):capture_predictions([{'model_probability_clean':value}],now=NOW)
    for value in [np.float16(.7),np.float32(.7),np.float64(.7),np.int64(4)]:
        result=capture_predictions([{'model_probability_clean':value}],now=NOW)
        assert result['rows'][0]['captured_fields']['model_probability_clean']==value
