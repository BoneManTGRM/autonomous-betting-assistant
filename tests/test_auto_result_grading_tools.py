from __future__ import annotations

import unittest

import pandas as pd

from autonomous_betting_agent.auto_result_grading_tools import fuzzy_match_results, normalize_result_feed, result_match_summary


class AutoResultGradingToolsTest(unittest.TestCase):
    def test_normalize_result_feed_adds_winner_from_scores(self):
        frame = pd.DataFrame([{
            'home_team': 'Home',
            'away_team': 'Away',
            'home_score': 4,
            'away_score': 2,
        }])
        normalized = normalize_result_feed(frame)
        self.assertEqual(normalized.loc[0, 'winner'], 'Home')
        self.assertEqual(normalized.loc[0, 'event'], 'Away at Home')

    def test_fuzzy_match_results_matches_event(self):
        ledger = pd.DataFrame([{
            'proof_id': 'OLP-TEST123',
            'locked_at_utc': '2026-01-01T00:00:00Z',
            'event': 'Away at Home',
            'prediction': 'Home',
            'sport': 'Baseball',
            'event_start_utc': '2026-01-01T20:00:00Z',
        }])
        results = pd.DataFrame([{
            'event': 'Away at Home',
            'winner': 'Home',
            'sport': 'Baseball',
            'event_start_utc': '2026-01-01T20:00:00Z',
            'final_score': 'Home 4 - Away 2',
        }])
        matches = fuzzy_match_results(ledger, results)
        self.assertFalse(matches.empty)
        self.assertEqual(matches.loc[0, 'match_status'], 'matched')
        summary = result_match_summary(matches)
        self.assertEqual(summary['matched'], 1)


if __name__ == '__main__':
    unittest.main()
