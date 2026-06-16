from __future__ import annotations

import unittest

import pandas as pd

from autonomous_betting_agent.odds_accuracy_tools import enrich_odds_accuracy, odds_accuracy_summary


class OddsAccuracyToolsTest(unittest.TestCase):
    def test_best_available_line_updates_active_price_and_ev(self):
        frame = pd.DataFrame([{
            'event': 'Away at Home',
            'prediction': 'Home',
            'market_type': 'h2h',
            'model_probability': 0.62,
            'decimal_price': 1.80,
            'draftkings_decimal_price': 1.91,
            'fanduel_decimal_price': 1.88,
            'bookmaker': 'BaseBook',
            'bookmaker_count': 3,
            'event_start_utc': '2099-01-01T00:00:00Z',
        }])
        out = enrich_odds_accuracy(frame)
        self.assertAlmostEqual(float(out.loc[0, 'decimal_price']), 1.91, places=2)
        self.assertEqual(out.loc[0, 'best_available_book'], 'DraftKings')
        self.assertGreater(float(out.loc[0, 'expected_value_per_unit']), 0)
        self.assertIn('robust_expected_value_per_unit', out.columns)

    def test_no_vig_hold_from_grouped_market(self):
        frame = pd.DataFrame([
            {
                'event': 'Away at Home',
                'prediction': 'Away',
                'market_type': 'h2h',
                'model_probability': 0.48,
                'decimal_price': 2.00,
                'bookmaker': 'BookA',
                'bookmaker_count': 4,
                'event_start_utc': '2099-01-01T00:00:00Z',
            },
            {
                'event': 'Away at Home',
                'prediction': 'Home',
                'market_type': 'h2h',
                'model_probability': 0.57,
                'decimal_price': 1.80,
                'bookmaker': 'BookA',
                'bookmaker_count': 4,
                'event_start_utc': '2099-01-01T00:00:00Z',
            },
        ])
        out = enrich_odds_accuracy(frame)
        self.assertTrue(out['market_hold'].notna().any())
        self.assertTrue(out['no_vig_implied_probability'].notna().any())
        self.assertIn(out.iloc[0]['market_hold_status'], {'normal_hold', 'elevated_hold', 'high_hold', 'efficient_low_hold'})

    def test_summary_counts_robust_positive_ev(self):
        frame = pd.DataFrame([{
            'event': 'Away at Home',
            'prediction': 'Home',
            'market_type': 'h2h',
            'model_probability': 0.62,
            'decimal_price': 1.91,
            'bookmaker': 'BookA',
            'bookmaker_count': 4,
            'event_start_utc': '2099-01-01T00:00:00Z',
        }])
        summary = odds_accuracy_summary(frame)
        self.assertIn('robust_positive_ev_rows', summary)
        self.assertGreaterEqual(summary['positive_ev_rows'], 1)


if __name__ == '__main__':
    unittest.main()
