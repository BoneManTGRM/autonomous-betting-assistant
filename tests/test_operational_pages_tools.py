import tempfile
import unittest
from pathlib import Path

import pandas as pd

from autonomous_betting_agent.auto_result_grading_tools import (
    grading_summary,
    normalize_result_feed,
    odds_scores_to_result_frame,
)
from autonomous_betting_agent.commercial_platform_tools import demo_ledger
from autonomous_betting_agent.daily_workflow_tools import daily_workflow_preview, run_daily_workflow, workflow_stage_frame
from autonomous_betting_agent.deployment_health_tools import deployment_summary, file_status_frame, secret_status


class OperationalToolsTests(unittest.TestCase):
    def test_secret_status(self):
        self.assertEqual(secret_status(''), 'missing')
        self.assertEqual(secret_status('abcd1234abcd1234abcd1234'), 'configured')

    def test_file_status_and_deployment_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'pages').mkdir()
            for path in ['scanner_pro.py', 'pro_predictor.py', 'what_are_the_odds.py', 'odds_lock_pro.py', 'public_proof_dashboard.py', 'learn_memory.py']:
                (root / 'pages' / path).write_text('# test\n', encoding='utf-8')
            frame = file_status_frame(root)
            summary = deployment_summary(lambda name: 'abcd1234abcd1234abcd1234' if name == 'THE_ODDS_API_KEY' else '', root=root, ledger_path=root / 'ledger.csv')
        self.assertTrue(frame[frame['core'] == True]['status'].eq('present').all())
        self.assertGreaterEqual(summary['deployment_score'], 75)

    def test_normalize_result_feed_infers_winner(self):
        results = normalize_result_feed(pd.DataFrame([{'home_team': 'Home', 'away_team': 'Away', 'home_score': 3, 'away_score': 1}]))
        self.assertEqual(results.iloc[0]['winner'], 'Home')
        self.assertEqual(results.iloc[0]['final_score'], '3-1')

    def test_odds_scores_to_result_frame(self):
        payload = [{
            'id': '1',
            'sport_key': 'soccer_demo',
            'sport_title': 'Demo Soccer',
            'commence_time': '2099-01-01T00:00:00Z',
            'home_team': 'Home',
            'away_team': 'Away',
            'completed': True,
            'scores': [{'name': 'Home', 'score': '2'}, {'name': 'Away', 'score': '1'}],
        }]
        frame = odds_scores_to_result_frame(payload)
        self.assertEqual(frame.iloc[0]['winner'], 'Home')
        self.assertEqual(frame.iloc[0]['result_status'], 'win_or_loss_by_pick')

    def test_daily_workflow_preview_and_run(self):
        raw = pd.DataFrame([
            {'event': 'A at B', 'sport': 'Soccer', 'prediction': 'B', 'model_probability': 0.64, 'decimal_price': 2.0, 'bookmaker': 'Book', 'agent_decision': 'play_small', 'lock_ready': True, 'event_start_utc': '2099-01-01T00:00:00Z'}
        ])
        preview = daily_workflow_preview(raw)
        result = run_daily_workflow(raw, save_to_persistent=False)
        stages = workflow_stage_frame(result)
        self.assertEqual(preview['candidate_rows'], 1)
        self.assertEqual(result['locked_rows'], 1)
        self.assertFalse(stages.empty)

    def test_demo_ledger_grading_summary(self):
        summary = grading_summary(demo_ledger())
        self.assertGreaterEqual(summary['locked_rows'], 3)
        self.assertGreaterEqual(summary['resolved_rows'], 2)


if __name__ == '__main__':
    unittest.main()
