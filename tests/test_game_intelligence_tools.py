from __future__ import annotations

import unittest

import pandas as pd

from autonomous_betting_agent.game_intelligence_tools import (
    agent_answer,
    best_line,
    enrich_game_intelligence,
    line_shop_table,
    playable_odds_targets,
    shadow_proof_frame,
)


class GameIntelligenceToolsTest(unittest.TestCase):
    def test_playable_odds_targets(self):
        targets = playable_odds_targets(0.62)
        self.assertAlmostEqual(targets['fair_decimal_price'], 1.6129, places=4)
        self.assertGreater(targets['minimum_playable_decimal'], targets['fair_decimal_price'])
        self.assertGreater(targets['great_value_decimal'], targets['minimum_playable_decimal'])

    def test_line_shop_picks_best_price(self):
        row = {
            'event': 'Away at Home',
            'prediction': 'Home',
            'model_probability': 0.62,
            'decimal_price': 1.80,
            'draftkings_decimal_price': 1.91,
            'fanduel_decimal_price': 1.88,
        }
        table = line_shop_table(row)
        self.assertFalse(table.empty)
        self.assertEqual(table.iloc[0]['bookmaker'], 'DraftKings')
        self.assertEqual(best_line(row)['best_available_book'], 'DraftKings')

    def test_enrich_game_intelligence_uses_best_line_for_ev(self):
        frame = pd.DataFrame([{
            'event': 'Away at Home',
            'prediction': 'Home',
            'sport': 'MLB',
            'market_type': 'h2h',
            'model_probability': 0.62,
            'decimal_price': 1.80,
            'draftkings_decimal_price': 1.91,
            'bookmaker': 'TestBook',
            'bookmaker_count': 4,
            'event_start_utc': '2099-01-01T00:00:00Z',
            'manual_context_notes': 'starter confirmed',
        }])
        enriched = enrich_game_intelligence(frame)
        self.assertAlmostEqual(float(enriched.loc[0, 'decimal_price']), 1.91, places=2)
        self.assertEqual(enriched.loc[0, 'best_available_book'], 'DraftKings')
        self.assertGreater(float(enriched.loc[0, 'expected_value_per_unit']), 0)
        self.assertIn(enriched.loc[0, 'minimum_line_value_status'], {'playable_value_price', 'great_value_price'})

    def test_enrich_game_intelligence_adds_required_columns(self):
        frame = pd.DataFrame([{
            'event': 'Away at Home',
            'prediction': 'Home',
            'sport': 'MLB',
            'market_type': 'h2h',
            'model_probability': 0.62,
            'decimal_price': 1.91,
            'bookmaker': 'TestBook',
            'bookmaker_count': 4,
            'event_start_utc': '2099-01-01T00:00:00Z',
            'manual_context_notes': 'starter confirmed',
        }])
        enriched = enrich_game_intelligence(frame)
        self.assertFalse(enriched.empty)
        self.assertIn('minimum_playable_decimal', enriched.columns)
        self.assertIn('what_would_change_my_mind', enriched.columns)
        self.assertIn('game_intelligence_card', enriched.columns)
        self.assertIn('operator_next_step', enriched.columns)

    def test_shadow_proof_frame(self):
        frame = pd.DataFrame([{
            'event': 'Away at Home',
            'prediction': 'Home',
            'sport': 'MLB',
            'market_type': 'h2h',
            'model_probability': 0.62,
            'decimal_price': 1.91,
            'bookmaker': 'TestBook',
            'bookmaker_count': 4,
            'event_start_utc': '2099-01-01T00:00:00Z',
        }])
        shadow = shadow_proof_frame(frame)
        self.assertFalse(shadow.empty)
        self.assertEqual(shadow.iloc[0]['proof_mode'], 'internal_shadow_not_public')

    def test_agent_answer_odds(self):
        enriched = enrich_game_intelligence(pd.DataFrame([{
            'event': 'Away at Home',
            'prediction': 'Home',
            'model_probability': 0.62,
            'decimal_price': 1.91,
            'bookmaker': 'TestBook',
            'event_start_utc': '2099-01-01T00:00:00Z',
        }]))
        answer = agent_answer(enriched.iloc[0].to_dict(), 'What odds do I need?')
        self.assertIn('Minimum playable', answer)


if __name__ == '__main__':
    unittest.main()
