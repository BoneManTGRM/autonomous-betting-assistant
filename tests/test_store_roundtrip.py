from autonomous_betting_agent import pick_hold_store as s


def test_local_store_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "DATA_DIR", tmp_path)
    data = [{"row_id": "one"}]
    assert s.save_held_rows("ara_latest_predictions", data, "test_01") == 1
    assert s.load_held_rows("ara_latest_predictions", "test_01") == data


def test_local_store_verify(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "DATA_DIR", tmp_path)
    result = s.verify_held_rows("ara_latest_predictions", [{"row_id": "two"}], "test_01")
    assert result["ok"] is True
    assert result["expected_rows"] == 1
    assert result["reloaded_rows"] == 1
