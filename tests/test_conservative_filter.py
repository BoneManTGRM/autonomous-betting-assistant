from __future__ import annotations

import unittest

import pandas as pd

from autonomous_betting_agent.conservative_filter import enrich_conservative_frame, memory_adjustment


class ConservativeFilterTests(unittest.TestCase):
    def test_soccer_moneyline_draw_risk_downgrades_close_projection(self) -> None:
        frame = pd.DataFrame([
            {
                'event': 'Mexico at Germany',
                'sport': 'FIFA World Cup',
                'market_type': 'h2h',
                'prediction': 'Germany',
                'model_probability': 0.61,
                'decimal_price': 1.85,
                'estimated_score': '2-1',
            }
        ])
        out = enrich_conservative_frame(frame)
        row = out.iloc[0]
        self.assertEqual(row['draw_risk'], 'high')
        self.assertIn(row['bettable_yes_no'], {'track_only', 'no'})
        self.assertIn('soccer', row['reason_for_downgrade'])

    def test_strong_soccer_without_draw_info_still_requires_big_edge(self) -> None:
        frame = pd.DataFrame([
            {
                'event': 'Home FC at Away FC',
                'sport': 'soccer_epl',
                'market_type': 'h2h',
                'prediction': 'Away FC',
                'model_probability': 0.63,
                'decimal_price': 1.72,
            }
        ])
        out = enrich_conservative_frame(frame)
        row = out.iloc[0]
        self.assertIn(row['bettable_yes_no'], {'track_only', 'no'})
        self.assertIn('draw_probability_missing', row['reason_for_downgrade'])

    def test_grass_tennis_requires_stronger_probability_and_edge(self) -> None:
        frame = pd.DataFrame([
            {
                'event': 'Player A vs Player B Halle',
                'sport': 'ATP Halle Open',
                'market_type': 'h2h',
                'prediction': 'Player A',
                'model_probability': 0.64,
                'decimal_price': 1.75,
                'estimated_score': '2-1',
            }
        ])
        out = enrich_conservative_frame(frame)
        row = out.iloc[0]
        self.assertEqual(row['surface_risk'], 'high')
        self.assertIn(row['bettable_yes_no'], {'track_only', 'no'})
        self.assertIn('grass_tennis', row['reason_for_downgrade'])

    def test_memory_small_sample_is_visible_without_adjustment(self) -> None:
        memory = pd.DataFrame([
            {
                'area_type': 'sport',
                'group_value': 'FIFA World Cup',
                'records': 3,
                'smoothed_edge': -0.18,
                'reliability': 0.25,
            }
        ])
        result = memory_adjustment({'sport': 'FIFA World Cup', 'market_type': 'h2h', 'model_probability': 0.67}, memory=memory)
        self.assertEqual(result['memory_influence_strength'], 'visible_only_small_sample')
        self.assertEqual(result['memory_adjustment'], 0.0)
        self.assertIn('lower_trust', result['memory_reason'])


if __name__ == '__main__':
    unittest.main()
