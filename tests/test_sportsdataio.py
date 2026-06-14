from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_betting_agent.sportsdataio import (
    SportsDataIOClient,
    SportsDataIOConfig,
    SportsDataIOError,
    payload_row_count,
    payload_to_records,
    write_csv_records,
)


class FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params or {}, "headers": headers or {}, "timeout": timeout})
        return self.response


class SportsDataIOTests(unittest.TestCase):
    def test_builds_scores_endpoint_with_header_auth(self) -> None:
        session = FakeSession(FakeResponse(200, [{"GameID": 1}]))
        client = SportsDataIOClient(SportsDataIOConfig(api_key="abc", sport="nfl", subfeed="scores"), session=session)
        payload = client.scores_by_date("2026-JAN-15")
        self.assertEqual(payload, [{"GameID": 1}])
        call = session.calls[0]
        self.assertEqual(call["url"], "https://api.sportsdata.io/v3/nfl/scores/json/ScoresByDate/2026-JAN-15")
        self.assertEqual(call["headers"], {"Ocp-Apim-Subscription-Key": "abc"})
        self.assertEqual(call["params"], {})

    def test_query_auth_adds_key_parameter(self) -> None:
        session = FakeSession(FakeResponse(200, []))
        client = SportsDataIOClient(SportsDataIOConfig(api_key="abc", auth_mode="query"), session=session)
        client.raw_endpoint("Teams")
        self.assertEqual(session.calls[0]["params"]["key"], "abc")
        self.assertEqual(session.calls[0]["headers"], {})

    def test_http_error_raises(self) -> None:
        session = FakeSession(FakeResponse(403, {"error": "denied"}, "denied"))
        client = SportsDataIOClient(SportsDataIOConfig(api_key="abc"), session=session)
        with self.assertRaises(SportsDataIOError):
            client.raw_endpoint("Teams")

    def test_payload_row_count(self) -> None:
        self.assertEqual(payload_row_count([{"a": 1}, {"a": 2}]), 2)
        self.assertEqual(payload_row_count({"items": [{"a": 1}]}), 1)
        self.assertEqual(payload_row_count({"single": "value"}), 1)

    def test_payload_to_records_flattens_nested_payload(self) -> None:
        payload = {
            "Games": [
                {"GameID": 1, "HomeTeam": "DAL", "Score": {"Home": 24, "Away": 17}, "Officials": [{"Name": "A"}]},
                {"GameID": 2, "HomeTeam": "NYG", "Score": {"Home": 10, "Away": 20}},
            ]
        }
        records = payload_to_records(payload, record_key="Games")
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["Score_Home"], 24)
        self.assertIn("Officials", records[0])

    def test_write_csv_records_creates_flat_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "out.csv"
            write_csv_records([{"b": 2, "a": 1}], path)
            text = path.read_text(encoding="utf-8")
            self.assertIn("a,b", text.splitlines()[0])
            self.assertIn("1,2", text)


if __name__ == "__main__":
    unittest.main()
