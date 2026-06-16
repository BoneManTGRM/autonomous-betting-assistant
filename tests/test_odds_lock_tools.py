import unittest

import pandas as pd

from autonomous_betting_agent.odds_lock_tools import (
    client_view,
    daily_report,
    lock_blockers,
    lock_rows,
    prepare_lock_candidates,
    summarize_locked_picks,
)


class OddsLockToolsTests(unittest.TestCase):
    def test_lock_rows_creates_proof_fields(self):
        frame = pd.DataFrame([
            {
                'event': 'A at B',
                'sport': 'Soccer',
                'market_type': 'h2h',
                'prediction': 'B',
                'model_probability': 0.64,
                'decimal_price': 2.05,
                'bookmaker': 'Book',
                'agent_decision': 'play_small',
                'agent_score': 78,
                'scanner_strength_score': 82,
                'lock_ready': True,
                'event_start_utc': '2099-01-01T00:00:00Z',
            }
        ])
        locked = lock_rows(frame, analyst='Test Brand')
        self.assertEqual(len(locked), 1)
        self.assertIn('proof_id', locked.columns)
        self.assertIn('proof_hash', locked.columns)
        self.assertEqual(locked.iloc[0]['proof_status'], 'locked_before_start')
        self.assertGreater(float(locked.iloc[0]['stake_units']), 0)

    def test_candidates_exclude_watch_by_default(self):
        frame = pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'model_probability': 0.55, 'decimal_price': 1.9, 'agent_decision': 'watch_only'},
            {'event': 'C at D', 'prediction': 'D', 'model_probability': 0.62, 'decimal_price': 2.0, 'agent_decision': 'play_small'},
        ])
        candidates = prepare_lock_candidates(frame)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates.iloc[0]['event'], 'C at D')

    def test_strict_future_lock_blocks_started_or_incomplete_rows(self):
        frame = pd.DataFrame([
            {'event': 'Started at Team', 'prediction': 'Team', 'model_probability': 0.64, 'decimal_price': 2.0, 'bookmaker': 'Book', 'agent_decision': 'play_small', 'event_start_utc': '2000-01-01T00:00:00Z'},
            {'event': 'Future at Team', 'prediction': 'Team', 'model_probability': 0.64, 'decimal_price': 2.0, 'agent_decision': 'play_small', 'event_start_utc': '2099-01-01T00:00:00Z'},
        ])
        strict = lock_rows(frame, strict=True, require_future=True)
        self.assertTrue(strict.empty)
        blockers = lock_blockers(frame.iloc[0].to_dict(), require_future=True)
        self.assertIn('invalid_after_start', blockers)
        blockers_missing_book = lock_blockers(frame.iloc[1].to_dict(), require_future=True)
        self.assertTrue({'missing_bookmaker', 'missing_bookmaker_or_odds_source'} & set(blockers_missing_book))

    def test_strict_future_lock_accepts_complete_future_row(self):
        frame = pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'model_probability': 0.64, 'decimal_price': 2.0, 'bookmaker': 'Book', 'agent_decision': 'play_small', 'event_start_utc': '2099-01-01T00:00:00Z'}
        ])
        strict = lock_rows(frame, strict=True, require_future=True)
        self.assertEqual(len(strict), 1)
        self.assertTrue(bool(strict.iloc[0]['official_lock_ready']))
        self.assertEqual(strict.iloc[0]['lock_blockers'], '')

    def test_summary_counts_units_and_roi(self):
        frame = lock_rows(pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'model_probability': 0.64, 'decimal_price': 2.0, 'agent_decision': 'play_small', 'result_status': 'win'},
            {'event': 'C at D', 'prediction': 'D', 'model_probability': 0.58, 'decimal_price': 1.8, 'agent_decision': 'play_small', 'result_status': 'loss'},
        ]), analyst='Test Brand')
        summary = summarize_locked_picks(frame)
        self.assertEqual(summary['resolved_picks'], 2)
        self.assertEqual(summary['wins'], 1)
        self.assertEqual(summary['losses'], 1)
        self.assertIsNotNone(summary['roi'])

    def test_client_view_hides_private_fields(self):
        locked = lock_rows(pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'model_probability': 0.64, 'decimal_price': 2.05, 'agent_decision': 'play_small'}
        ]))
        public = client_view(locked, public_only=True)
        self.assertIn('proof_id', public.columns)
        self.assertNotIn('model_probability', public.columns)
        self.assertNotIn('proof_hash', public.columns)

    def test_daily_report_contains_proof_id(self):
        locked = lock_rows(pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'model_probability': 0.64, 'decimal_price': 2.05, 'agent_decision': 'play_small'}
        ]))
        report = daily_report(locked)
        self.assertIn('Locked Picks Report', report)
        self.assertIn('Proof ID:', report)


if __name__ == '__main__':
    unittest.main()
