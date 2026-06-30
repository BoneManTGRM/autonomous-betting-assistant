import unittest

import pandas as pd

from autonomous_betting_agent.api_result_update_tools import (
    apply_clv_columns,
    auto_full_update_rows,
    grade_moneyline_row,
    report_quality_checks,
)


class ApiResultUpdateToolsTests(unittest.TestCase):
    def test_clv_columns_do_not_change_locked_price(self):
        frame = pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'decimal_price': 2.0, 'closing_decimal_price': 1.8}
        ])
        out = apply_clv_columns(frame)
        self.assertEqual(float(out.iloc[0]['decimal_price']), 2.0)
        self.assertAlmostEqual(float(out.iloc[0]['clv_percent']), 0.111111, places=6)
        self.assertTrue(bool(out.iloc[0]['beat_close']))

    def test_moneyline_grading_protects_unsupported_markets(self):
        row = {'event': 'A at B', 'market_type': 'total', 'prediction': 'over', 'decimal_price': 1.9}
        out = grade_moneyline_row(row, winner='B')
        self.assertEqual(out['api_grade_status'], 'manual_review_market_not_supported')
        self.assertNotEqual(out.get('result_status'), 'loss')

    def test_auto_update_preserves_proof_and_pick_fields(self):
        frame = pd.DataFrame([
            {
                'proof_id': 'OLP-TEST',
                'proof_hash': 'abc',
                'locked_at_utc': '2026-06-01T00:00:00Z',
                'event': 'A at B',
                'market_type': 'h2h',
                'prediction': 'B',
                'decimal_price': 2.0,
                'model_probability': 0.6,
                'api_winner': 'B',
                'api_final_score': 'A 1 - 2 B',
                'result_status': 'pending',
            }
        ])
        out, report = auto_full_update_rows(frame, odds_api_key='test')
        self.assertTrue(report['protected_fields_ok'])
        self.assertFalse(report['selection_thresholds_changed'])
        self.assertEqual(out.iloc[0]['result_status'], 'win')
        self.assertEqual(out.iloc[0]['proof_id'], 'OLP-TEST')
        self.assertEqual(float(out.iloc[0]['model_probability']), 0.6)

    def test_report_quality_counts_unique_events_vs_pick_rows(self):
        frame = pd.DataFrame([
            {'event': 'A at B', 'event_start_utc': '2026-06-01T00:00:00Z', 'prediction': 'A', 'result_status': 'win'},
            {'event': 'A at B', 'event_start_utc': '2026-06-01T00:00:00Z', 'prediction': 'B', 'result_status': 'loss'},
            {'event': 'C at D', 'event_start_utc': '2026-06-02T00:00:00Z', 'prediction': 'C', 'result_status': 'pending'},
        ])
        checks = report_quality_checks(frame)
        self.assertEqual(checks['pick_rows'], 3)
        self.assertEqual(checks['unique_events'], 2)
        self.assertEqual(checks['duplicate_pick_rows'], 1)
        self.assertEqual(checks['resolved_pick_rows'], 2)


if __name__ == '__main__':
    unittest.main()
