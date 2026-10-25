from contextlib import contextmanager
import base64
import json
from unittest.mock import Mock

import pytest
from autonomous_betting_agent import pick_hold_store as store


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(store, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(store, '_memory_store', lambda: {})
    monkeypatch.setattr(store, '_github_token', lambda: 'synthetic-placeholder')
    monkeypatch.setattr(store, '_github_repo', lambda: 'synthetic/repo')
    monkeypatch.setattr(store, '_github_branch', lambda: 'main')
    return monkeypatch


def response(payload=None, status=200):
    obj = Mock(status_code=status)
    obj.json.return_value = {'content': base64.b64encode(json.dumps(payload or {}).encode()).decode(), 'sha': 'synthetic'}
    return obj


def test_timeout_stops_amplification_and_marks_unavailable(isolated):
    get = Mock(side_effect=store.requests.Timeout('synthetic'))
    isolated.setattr(store.requests, 'get', get)
    with store.remote_read_budget() as state:
        assert store.load_first_available(tuple(sorted(store.HELD_KEYS)), 'synthetic') == ('', [])
        assert state.unavailable
    assert get.call_count == 1
    assert max(get.call_args.kwargs['timeout']) <= 2.5


def test_missing_is_not_failure_and_memoized_only_this_render(isolated):
    get = Mock(return_value=response(status=404))
    isolated.setattr(store.requests, 'get', get)
    with store.remote_read_budget() as state:
        store.load_held_rows('odds_lock_pro_locked_rows', 'synthetic')
        store.load_held_rows('odds_lock_pro_locked_rows', 'synthetic')
        assert not state.unavailable
    assert get.call_count == 2
    with store.remote_read_budget():
        store.load_held_rows('odds_lock_pro_locked_rows', 'synthetic')
    assert get.call_count == 4


def test_budget_expiry_skips_next_request(isolated):
    now = [0.0]
    isolated.setattr(store.time, 'monotonic', lambda: now[0])
    def get(*a, **kw):
        now[0] += 5.0
        return response(status=404)
    mock = Mock(side_effect=get)
    isolated.setattr(store.requests, 'get', mock)
    with store.remote_read_budget() as state:
        store.load_held_rows('odds_lock_pro_locked_rows', 'synthetic')
        assert state.unavailable
    assert mock.call_count == 1


def test_no_key_is_offline_not_unavailable(isolated):
    isolated.setattr(store, '_github_token', lambda: '')
    get = Mock(side_effect=AssertionError('no HTTP'))
    isolated.setattr(store.requests, 'get', get)
    with store.remote_read_budget() as state:
        assert store.load_held_rows('odds_lock_pro_locked_rows') == []
        assert not state.unavailable
    get.assert_not_called()


def test_local_rows_survive_remote_failure(isolated):
    rows = [{'proof_id': 'synthetic', 'result_status': 'win'}]
    store._write_payload(store._path_for('odds_lock_pro_locked_rows'), {'rows': rows})
    get = Mock(side_effect=store.requests.Timeout('synthetic'))
    isolated.setattr(store.requests, 'get', get)
    with store.remote_read_budget() as state:
        store._github_get_json('synthetic-path')
        assert store.load_held_rows('odds_lock_pro_locked_rows') == rows
        assert state.unavailable
    assert get.call_count == 1


def test_chunk_failure_never_returns_partial_remote_ledger(isolated):
    get = Mock(side_effect=[response({'format': 'chunked', 'parts': 2}), response({'rows': [{'proof_id': 'synthetic'}]}), store.requests.Timeout('synthetic')])
    isolated.setattr(store.requests, 'get', get)
    with store.remote_read_budget() as state:
        assert store.load_held_rows('odds_lock_pro_locked_rows') == []
        assert state.unavailable


def test_context_reset_and_retry_after_exception(isolated):
    get = Mock(side_effect=store.requests.Timeout('synthetic'))
    isolated.setattr(store.requests, 'get', get)
    with pytest.raises(ValueError):
        with store.remote_read_budget():
            store._github_get_json('one')
            raise ValueError('synthetic')
    with store.remote_read_budget():
        store._github_get_json('one')
    assert get.call_count == 2
    store._github_get_json('one')
    assert get.call_args.kwargs['timeout'] == 20


def test_remote_success_and_local_success(isolated):
    rows = [{'proof_id': 'synthetic'}]
    get = Mock(side_effect=[response(status=404), response({'rows': rows})])
    isolated.setattr(store.requests, 'get', get)
    with store.remote_read_budget() as state:
        assert store.load_held_rows('odds_lock_pro_locked_rows') == rows
        assert not state.unavailable
    store._write_payload(store._path_for('odds_lock_pro_locked_rows'), {'rows': rows})
    get.reset_mock()
    with store.remote_read_budget() as state:
        assert store.load_held_rows('odds_lock_pro_locked_rows') == rows
        assert not state.unavailable
    get.assert_not_called()


def test_empty_success_and_missing_chunk(isolated):
    get = Mock(side_effect=[response({'format': 'chunked', 'parts': 1}), response({'rows': []})])
    isolated.setattr(store.requests, 'get', get)
    with store.remote_read_budget() as state:
        assert store.load_held_rows('odds_lock_pro_locked_rows') == []
        assert not state.unavailable
    get.side_effect = [response({'format': 'chunked', 'parts': 1}), response(status=404)]
    with store.remote_read_budget() as state:
        assert store.load_held_rows('odds_lock_pro_locked_rows') == []
        assert state.unavailable


def test_nested_and_thread_contexts_do_not_leak(isolated):
    from concurrent.futures import ThreadPoolExecutor
    get = Mock(return_value=response(status=404))
    isolated.setattr(store.requests, 'get', get)
    with store.remote_read_budget() as outer:
        store._github_get_json('one')
        with store.remote_read_budget() as inner:
            store._github_get_json('one')
            assert inner is not outer
            inner.unavailable = True
        assert not outer.unavailable
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(store._REMOTE_READ_BUDGET.get).result() is None
        store._github_get_json('one')
    assert get.call_count == 2
    assert store._REMOTE_READ_BUDGET.get() is None


def test_write_preflight_bypasses_unavailable_read_context(isolated):
    get = Mock(return_value=response({'rows': []}))
    put = Mock(return_value=response())
    isolated.setattr(store.requests, 'get', get)
    isolated.setattr(store.requests, 'put', put)
    with store.remote_read_budget() as state:
        state.unavailable = True
        assert store._github_put_json('synthetic-path', {'rows': []}, 'synthetic')
    assert get.call_args.kwargs['timeout'] == 20
    assert put.call_args.kwargs['json']['sha'] == 'synthetic'
    assert put.call_args.kwargs['timeout'] == 30


def test_complete_save_stale_part_cleanup_bypasses_read_budget(isolated):
    get = Mock(return_value=response({'format': 'chunked', 'parts': 3}))
    put = Mock(return_value=response())
    isolated.setattr(store.requests, 'get', get)
    isolated.setattr(store.requests, 'put', put)
    with store.remote_read_budget() as state:
        state.unavailable = True
        assert store._github_save_payload('odds_lock_pro_locked_rows', [{'proof_id': 'synthetic'}])
    assert get.call_count == 5  # old index plus each PUT preflight
    assert put.call_count == 4  # new part, two stale parts, index
    assert all(call.kwargs['timeout'] == 20 for call in get.call_args_list)
    messages = [call.kwargs['json']['message'] for call in put.call_args_list]
    assert sum('Clear stale' in message for message in messages) == 2


@pytest.mark.parametrize('parts', [-1, 0, 'bad', True, 65])
def test_invalid_chunk_count_is_unavailable(isolated, parts):
    get = Mock(return_value=response({'format': 'chunked', 'parts': parts}))
    isolated.setattr(store.requests, 'get', get)
    with store.remote_read_budget() as state:
        assert store.load_held_rows('odds_lock_pro_locked_rows') == []
        assert state.unavailable
    assert get.call_count == 1


@pytest.mark.parametrize('bad_part', [{'unexpected': 'wrong schema'}, {'rows': [1]}, {'rows': None}])
def test_malformed_chunk_never_returns_partial_rows(isolated, bad_part):
    get = Mock(side_effect=[response({'format': 'chunked', 'parts': 2}), response({'rows': [{'proof_id': 'synthetic'}]}), response(bad_part)])
    isolated.setattr(store.requests, 'get', get)
    with store.remote_read_budget() as state:
        assert store.load_held_rows('odds_lock_pro_locked_rows') == []
        assert state.unavailable


def test_non_object_payload_and_malformed_legacy_unavailable(isolated):
    bad = response()
    bad.json.return_value['content'] = base64.b64encode(b'[]').decode()
    get = Mock(return_value=bad)
    isolated.setattr(store.requests, 'get', get)
    with store.remote_read_budget() as state:
        assert store.load_held_rows('odds_lock_pro_locked_rows') == []
        assert state.unavailable
    get.side_effect = [response(status=404), response({'wrong': 'schema'})]
    with store.remote_read_budget() as state:
        assert store.load_held_rows('odds_lock_pro_locked_rows') == []
        assert state.unavailable
