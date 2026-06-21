import unittest

import pandas as pd

from autonomous_betting_agent.odds_lock_tools import lock_rows, summarize_locked_picks
from autonomous_betting_agent.row_normalizer import normalize_frame, result_status


class VoidOutcomeTests(unittest.TestCase):
    def test_push_and_cancellation_labels_normalize_to_void(self):
        labels = [
            'push',
            'pushed',
            'draw_no_bet_push',
            'cancelled',
            'canceled',
            'cancelation',
            'cancellation',
            'postponed',
            'abandoned',
            'no_action',
        ]
        for label in labels:
            with self.subTest(label=label):
                self.assertEqual(result_status({'result_status': label}), 'void')

    def test_voids_do_not_affect_record_hit_rate_or_units(self):
        frame = lock_rows(pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'model_probability': 0.64, 'decimal_price': 2.0, 'agent_decision': 'play_small', 'result_status': 'win'},
            {'event': 'C at D', 'prediction': 'D', 'model_probability': 0.58, 'decimal_price': 1.8, 'agent_decision': 'play_small', 'result_status': 'loss'},
            {'event': 'E at F', 'prediction': 'F -1', 'model_probability': 0.60, 'decimal_price': 1.9, 'agent_decision': 'play_small', 'result_status': 'push'},
            {'event': 'G at H', 'prediction': 'H', 'model_probability': 0.60, 'decimal_price': 1.9, 'agent_decision': 'play_small', 'result_status': 'cancellation'},
        ]), analyst='Test Brand')
        summary = summarize_locked_picks(frame)
        self.assertEqual(summary['wins'], 1)
        self.assertEqual(summary['losses'], 1)
        self.assertEqual(summary['pushes'], 2)
        self.assertEqual(summary['resolved_picks'], 2)
        self.assertEqual(summary['hit_rate'], 0.5)
        self.assertEqual(float(frame.loc[2, 'profit_units']), 0.0)
        self.assertEqual(float(frame.loc[3, 'profit_units']), 0.0)

    def test_legacy_loss_is_repaired_when_void_label_exists_elsewhere(self):
        frame = normalize_frame(pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'result_status': 'loss', 'outcome': 'push'},
            {'event': 'C at D', 'prediction': 'D', 'result_status': 'loss', 'result_note': 'cancelled before start'},
        ]))
        self.assertEqual(frame.loc[0, 'result_status'], 'void')
        self.assertEqual(frame.loc[1, 'result_status'], 'void')


if __name__ == '__main__':
    unittest.main()
