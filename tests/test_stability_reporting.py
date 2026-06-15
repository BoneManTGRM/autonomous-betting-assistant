import unittest

import pandas as pd

from autonomous_betting_agent.daily_report import build_daily_report
from autonomous_betting_agent.performance_segments import build_segment_frame
from autonomous_betting_agent.prediction_snapshot import build_prediction_snapshots
from autonomous_betting_agent.readiness_scorecard import build_readiness_scorecard
from autonomous_betting_agent.review_packet import build_review_packet, packet_markdown
from autonomous_betting_agent.row_normalizer import normalize_row


class StabilityReportingTests(unittest.TestCase):
    def test_event_start_does_not_become_prediction_timestamp(self):
        row = {
            'event': 'Team A at Team B',
            'prediction': 'Team B',
            'model_probability': 0.62,
            'decimal_price': 1.95,
            'known_start_utc': '2026-06-15T22:00:00Z',
        }
        normalized = normalize_row(row)
        self.assertEqual(normalized['event_start_utc'], '2026-06-15T22:00:00Z')
        self.assertEqual(normalized['prediction_timestamp'], '')

        snapshots = build_prediction_snapshots(pd.DataFrame([row]), allow_auto_lock=False)
        self.assertEqual(snapshots.loc[0, 'event_start_utc'], '2026-06-15T22:00:00Z')
        self.assertEqual(snapshots.loc[0, 'locked_at_utc'], '')
        self.assertEqual(snapshots.loc[0, 'lock_status'], 'not_official')

    def test_auto_lock_explicitly_creates_lock(self):
        row = {
            'event': 'Team A at Team B',
            'prediction': 'Team B',
            'model_probability': 0.62,
            'decimal_price': 1.95,
            'known_start_utc': '2026-06-15T22:00:00Z',
        }
        snapshots = build_prediction_snapshots(pd.DataFrame([row]), allow_auto_lock=True)
        self.assertEqual(snapshots.loc[0, 'lock_status'], 'official_locked')
        self.assertEqual(snapshots.loc[0, 'lock_origin'], 'new_lock_created_now')

    def test_reporting_modules_return_basic_outputs(self):
        frame = pd.DataFrame([
            {
                'event': 'Team A at Team B',
                'sport': 'Demo',
                'market_type': 'moneyline',
                'prediction': 'Team B',
                'winner': 'Team B',
                'model_probability': 0.62,
                'decimal_price': 1.95,
                'prediction_timestamp': '2026-06-15T18:00:00Z',
                'known_start_utc': '2026-06-15T22:00:00Z',
                'stake_units': 1,
                'profit_units': 0.95,
                'closing_decimal_price': 1.80,
                'graded_at_utc': '2026-06-16T02:00:00Z',
            }
        ])
        self.assertFalse(build_segment_frame(frame).empty)
        daily = build_daily_report(frame, report_date='2026-06-16')
        self.assertEqual(daily['statistics']['wins'], 1)
        scorecard = build_readiness_scorecard(frame)
        self.assertGreaterEqual(scorecard['readiness_score'], 0)
        packet = build_review_packet(frame)
        self.assertIn('statistics', packet)
        self.assertIn('Review Packet', packet_markdown(packet))


if __name__ == '__main__':
    unittest.main()
