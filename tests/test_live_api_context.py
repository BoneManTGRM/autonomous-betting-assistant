from __future__ import annotations

import unittest
from types import SimpleNamespace

from autonomous_betting_agent.live_api_context import LiveAPIContextBuilder, sportsdataio_sport_from_odds


class FakeSportsDataIOClient:
    def teams(self, *, sport=None):
        return [
            {"Name": "Tigers", "FullName": "Boston Tigers", "City": "Boston", "Wins": 7, "Losses": 3, "Key": "BOS"},
            {"Name": "Bears", "FullName": "Chicago Bears", "City": "Chicago", "Wins": 3, "Losses": 7, "Key": "CHI"},
        ]

    def raw_endpoint(self, endpoint, *, sport=None, subfeed=None):
        if endpoint == "Injuries":
            return [{"Team": "BOS", "Status": "Out"}, {"Team": "BOS", "Status": "Questionable"}]
        return []


class FakeWeatherAPIClient:
    def forecast(self, *, location, days=1, aqi="no", alerts="yes"):
        return {
            "forecast": {
                "forecastday": [
                    {
                        "date": "2026-06-20",
                        "hour": [
                            {
                                "time": "2026-06-20 18:00",
                                "temp_f": 70,
                                "wind_mph": 8,
                                "gust_mph": 12,
                                "precip_mm": 0,
                                "humidity": 55,
                                "condition": {"text": "Clear"},
                            }
                        ],
                    }
                ]
            }
        }


class LiveAPIContextTests(unittest.TestCase):
    def test_sportsdataio_sport_mapping(self) -> None:
        self.assertEqual(sportsdataio_sport_from_odds("americanfootball_nfl", "NFL"), "nfl")
        self.assertEqual(sportsdataio_sport_from_odds("basketball_nba", "NBA"), "nba")
        self.assertEqual(sportsdataio_sport_from_odds("baseball_mlb", "MLB"), "mlb")

    def test_context_uses_sportsdataio_and_weatherapi_when_available(self) -> None:
        event = SimpleNamespace(
            sport_key="americanfootball_nfl",
            sport_title="NFL",
            home_team="Boston Tigers",
            away_team="Chicago Bears",
            commence_time="2026-06-20T18:00:00Z",
        )
        builder = LiveAPIContextBuilder(
            sportsdataio_key="test-sdio",
            weatherapi_key="test-weather",
            sportsdataio_client_factory=lambda sport: FakeSportsDataIOClient(),
            weather_client=FakeWeatherAPIClient(),
        )
        context = builder.context_for_event(event, pick_name="Boston Tigers")
        self.assertEqual(context["odds_api_source_used"], "yes")
        self.assertEqual(context["sportsdataio_source_used"], "yes")
        self.assertEqual(context["stats_source_used"], "yes")
        self.assertEqual(context["injury_source_used"], "yes")
        self.assertEqual(context["weather_source_used"], "yes")
        self.assertIn("stats_probability", context)
        self.assertIn("injury_risk_score", context)
        self.assertIn("weather_risk_score", context)
        self.assertEqual(context["weather_location"], "Boston")

    def test_context_marks_sources_not_used_without_keys(self) -> None:
        event = SimpleNamespace(
            sport_key="basketball_euroleague",
            sport_title="Euroleague",
            home_team="Home",
            away_team="Away",
            commence_time="2026-06-20T18:00:00Z",
        )
        context = LiveAPIContextBuilder().context_for_event(event, pick_name="Home")
        self.assertEqual(context["odds_api_source_used"], "yes")
        self.assertEqual(context["sportsdataio_source_used"], "no")
        self.assertEqual(context["weather_source_used"], "no")
        self.assertEqual(context["stats_source_used"], "no")
        self.assertEqual(context["injury_source_used"], "no")


if __name__ == "__main__":
    unittest.main()
