from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_betting_agent.api_budget import APIBudgetManager
from autonomous_betting_agent.environment_intelligence import score_environment
from autonomous_betting_agent.injury_lineup import score_injury_lineup
from autonomous_betting_agent.rejection_learning import learn_from_rejections
from autonomous_betting_agent.sport_key_resolver import resolve_sport_key


class ProductionUpgradeTests(unittest.TestCase):
    def test_environment_scores_high_wind_as_risk(self) -> None:
        risk = score_environment({"sport": "soccer", "wind_mph": "25", "temp_f": "70", "precip_mm": "0"})
        self.assertEqual(risk.weather_flag, "WATCH")
        self.assertLess(risk.weather_risk_score, 80)
        self.assertIn("wind", risk.weather_reason)

    def test_indoor_weather_is_low_risk(self) -> None:
        risk = score_environment({"sport": "nba", "venue_type": "indoor arena", "wind_mph": "40"})
        self.assertEqual(risk.weather_flag, "LOW")
        self.assertGreaterEqual(risk.weather_risk_score, 90)

    def test_injury_lineup_flags_key_player_out(self) -> None:
        risk = score_injury_lineup({"injury_status": "Out", "player_role": "star starter", "lineup_status": "projected"})
        self.assertEqual(risk.key_player_out, "true")
        self.assertIn("key_player_out", risk.lineup_do_not_bet_reason)
        self.assertLess(risk.injury_risk_score, 60)

    def test_sport_key_resolver_matches_soccer_feed(self) -> None:
        feeds = [
            {"key": "americanfootball_nfl", "title": "NFL", "group": "Football", "active": True},
            {"key": "soccer_international", "title": "International Soccer", "group": "Soccer", "active": True},
        ]
        match = resolve_sport_key(feeds, sport_search="soccer", game="Mexico vs South Korea")
        self.assertEqual(match.matched_sport_key, "soccer_international")
        self.assertGreater(match.match_confidence, 0.7)

    def test_api_budget_uses_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            calls = {"count": 0}
            manager = APIBudgetManager(cache_dir=Path(temp_dir), max_api_calls_per_run=1, ttl_seconds=999)

            def fetcher():
                calls["count"] += 1
                return {"ok": True}

            first = manager.call(provider="test", endpoint="endpoint", params={"a": 1}, fetcher=fetcher)
            second = manager.call(provider="test", endpoint="endpoint", params={"a": 1}, fetcher=fetcher)
            self.assertEqual(first, second)
            self.assertEqual(calls["count"], 1)
            self.assertEqual(manager.cache_hits, 1)

    def test_rejection_learning_scores_helpfulness(self) -> None:
        rows = [
            {"bankroll_action": "REJECT", "do_not_bet_reason": "low_edge", "result": "loss", "best_price": "2.0"},
            {"bankroll_action": "REJECT", "do_not_bet_reason": "low_edge", "result": "loss", "best_price": "2.0"},
            {"bankroll_action": "REJECT", "do_not_bet_reason": "bad_weather", "result": "win", "best_price": "2.0"},
        ]
        stats = learn_from_rejections(rows)
        by_reason = {item.reason: item for item in stats}
        self.assertGreater(by_reason["low_edge"].filter_helpfulness_score, 0)
        self.assertLess(by_reason["bad_weather"].filter_helpfulness_score, 0)


if __name__ == "__main__":
    unittest.main()
