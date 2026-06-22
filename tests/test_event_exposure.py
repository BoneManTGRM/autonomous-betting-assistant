import unittest

import pandas as pd

from autonomous_betting_agent.event_exposure import add_event_exposure_columns, exposure_metrics


class EventExposureTests(unittest.TestCase):
    def test_same_event_multiple_markets_count_as_one_event(self):
        rows = pd.DataFrame([
            {
                'event_id': 'c1ec9a65f4b4cf74477b368a7d6282de',
                'event': 'Egypt at New Zealand',
                'market_type': 'spreads',
                'line_point': 0.25,
                'prediction': 'Point spread: New Zealand +0.25',
                'result_status': 'loss',
            },
            {
                'event_id': 'c1ec9a65f4b4cf74477b368a7d6282de',
                'event': 'Egypt at New Zealand',
                'market_type': 'spreads',
                'line_point': -2,
                'prediction': 'Point spread: Egypt -2',
                'result_status': 'push',
            },
            {
                'event_id': 'c1ec9a65f4b4cf74477b368a7d6282de',
                'event': 'Egypt at New Zealand',
                'market_type': 'totals',
                'line_point': 4.5,
                'prediction': 'Game total: Under 4.5',
                'result_status': 'win',
            },
        ])

        exposed = add_event_exposure_columns(rows)
        metrics = exposure_metrics(rows)

        self.assertEqual(exposed['unique_event_id'].nunique(), 1)
        self.assertTrue(exposed['same_event_pick_count'].eq(3).all())
        self.assertEqual(metrics['unique_events'], 1)
        self.assertEqual(metrics['completed_events'], 1)
        self.assertEqual(metrics['pick_rows'], 3)
        self.assertEqual(metrics['wins'], 1)
        self.assertEqual(metrics['losses'], 1)
        self.assertEqual(metrics['voids'], 1)
        self.assertEqual(metrics['extra_same_event_pick_rows'], 2)
        self.assertEqual(metrics['pick_hit_rate_excluding_voids'], 0.5)

    def test_exact_duplicate_pick_rows_are_not_double_counted(self):
        rows = pd.DataFrame([
            {
                'event_id': 'abc',
                'event': 'A at B',
                'market_type': 'h2h',
                'prediction': 'B',
                'result_status': 'win',
            },
            {
                'event_id': 'abc',
                'event': 'A at B',
                'market_type': 'h2h',
                'prediction': 'B',
                'result_status': 'win',
            },
        ])

        metrics = exposure_metrics(rows)

        self.assertEqual(metrics['unique_events'], 1)
        self.assertEqual(metrics['pick_rows'], 1)
        self.assertEqual(metrics['wins'], 1)
        self.assertEqual(metrics['extra_same_event_pick_rows'], 0)


if __name__ == '__main__':
    unittest.main()
