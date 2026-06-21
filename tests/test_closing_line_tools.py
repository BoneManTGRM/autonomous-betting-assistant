from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pandas as pd

from autonomous_betting_agent.closing_line_tools import collect_closing_lines, collect_closing_lines_for_all_sports
from autonomous_betting_agent.odds_lock_tools import lock_rows


class ClosingLineToolsTests(unittest.TestCase):
    def _locked_frame(self):
        return lock_rows(pd.DataFrame([
            {
                'event': 'Away Team at Home Team',
                'sport': 'Basketball',
                'sport_key': 'basketball_nba',
                'market_type': 'h2h',
                'prediction': 'Home Team',
                'model_probability': 0.64,
                'decimal_price': 1.80,
                'bookmaker': 'OpenBook',
                'agent_decision': 'play_small',
                'event_start_utc': '2099-01-01T00:00:00Z',
            }
        ]), analyst='Test Brand')

    def _summary(self, outcomes=None):
        return SimpleNamespace(
            sport_key='basketball_nba',
            sport_title='Basketball',
            commence_time='2099-01-01T00:00:00Z',
            away_team='Away Team',
            home_team='Home Team',
            event_id='event-1',
            outcomes=outcomes or [
                SimpleNamespace(name='Home Team', average_price=1.70, market='h2h', point=None, source_count=6),
                SimpleNamespace(name='Away Team', average_price=2.20, market='h2h', point=None, source_count=6),
            ],
        )

    def test_collects_closing_price_for_matching_moneyline(self):
        with patch('autonomous_betting_agent.closing_line_tools.fetch_odds', return_value=[{'id': 'event-1'}]), \
             patch('autonomous_betting_agent.closing_line_tools.summarize_event', return_value=self._summary()):
            updated, stats = collect_closing_lines(self._locked_frame(), api_key='real_key_1234567890', sport_key='basketball_nba')
        self.assertEqual(stats['updated_rows'], 1)
        self.assertEqual(float(updated.iloc[0]['closing_decimal_price']), 1.70)
        self.assertEqual(updated.iloc[0]['closing_source'], 'the_odds_api_current_odds')
        self.assertEqual(updated.iloc[0]['closing_collection_status'], 'collected')
        self.assertEqual(stats['closing_rows'], 1)

    def test_does_not_overwrite_existing_closing_price_by_default(self):
        frame = self._locked_frame()
        frame.loc[0, 'closing_decimal_price'] = 1.66
        with patch('autonomous_betting_agent.closing_line_tools.fetch_odds', return_value=[{'id': 'event-1'}]), \
             patch('autonomous_betting_agent.closing_line_tools.summarize_event', return_value=self._summary()):
            updated, stats = collect_closing_lines(frame, api_key='real_key_1234567890', sport_key='basketball_nba')
        self.assertEqual(stats['updated_rows'], 0)
        self.assertEqual(float(updated.iloc[0]['closing_decimal_price']), 1.66)
        self.assertEqual(updated.iloc[0]['closing_collection_status'], 'already_collected')

    def test_collects_spread_line_with_point_match(self):
        frame = self._locked_frame()
        frame.loc[0, 'market_type'] = 'spread'
        frame.loc[0, 'prediction'] = 'Home Team -3.5'
        summary = self._summary([
            SimpleNamespace(name='Point spread: Home Team -3.5', average_price=1.91, market='spreads', point=-3.5, source_count=5)
        ])
        with patch('autonomous_betting_agent.closing_line_tools.fetch_odds', return_value=[{'id': 'event-1'}]), \
             patch('autonomous_betting_agent.closing_line_tools.summarize_event', return_value=summary):
            updated, stats = collect_closing_lines(frame, api_key='real_key_1234567890', sport_key='basketball_nba')
        self.assertEqual(stats['updated_rows'], 1)
        self.assertEqual(float(updated.iloc[0]['closing_decimal_price']), 1.91)
        self.assertEqual(updated.iloc[0]['closing_market_type'], 'spreads')

    def test_collects_all_sports_from_ledger(self):
        with patch('autonomous_betting_agent.closing_line_tools.fetch_odds', return_value=[{'id': 'event-1'}]) as fetch_mock, \
             patch('autonomous_betting_agent.closing_line_tools.summarize_event', return_value=self._summary()):
            updated, stats = collect_closing_lines_for_all_sports(self._locked_frame(), api_key='real_key_1234567890')
        self.assertEqual(stats['updated_rows'], 1)
        self.assertEqual(stats['sport_keys'], ['basketball_nba'])
        self.assertEqual(float(updated.iloc[0]['closing_decimal_price']), 1.70)
        fetch_mock.assert_called_once()

    def test_pending_only_skips_resolved_rows(self):
        frame = self._locked_frame()
        frame.loc[0, 'result_status'] = 'win'
        with patch('autonomous_betting_agent.closing_line_tools.fetch_odds', return_value=[{'id': 'event-1'}]), \
             patch('autonomous_betting_agent.closing_line_tools.summarize_event', return_value=self._summary()):
            updated, stats = collect_closing_lines(frame, api_key='real_key_1234567890', sport_key='basketball_nba')
        self.assertEqual(stats['updated_rows'], 0)
        self.assertEqual(stats['skipped_resolved'], 1)
        self.assertEqual(updated.iloc[0]['closing_collection_status'], 'skipped_resolved')


if __name__ == '__main__':
    unittest.main()
