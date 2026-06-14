from __future__ import annotations

import unittest

from autonomous_betting_agent.odds_api import odds_api_payload_to_rows


class ProviderPayloadTests(unittest.TestCase):
    def test_flattens_event_payload(self) -> None:
        payload = [{
            "id": "game-1",
            "sport_key": "americanfootball_nfl",
            "sport_title": "NFL",
            "home_team": "DAL",
            "away_team": "NYG",
            "commence_time": "2026-09-10T20:20:00Z",
            "bookmakers": [{
                "key": "provider1",
                "title": "Provider 1",
                "last_update": "2026-09-10T12:00:00Z",
                "markets": [{
                    "key": "h2h",
                    "outcomes": [
                        {"name": "DAL", "price": 1.8},
                        {"name": "NYG", "price": 2.1},
                    ],
                }],
            }],
        }]
        rows = odds_api_payload_to_rows(payload)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["game_id"], "game-1")
        self.assertEqual(rows[0]["market"], "h2h")
        self.assertEqual(rows[0]["bookmaker"], "provider1")


if __name__ == "__main__":
    unittest.main()
