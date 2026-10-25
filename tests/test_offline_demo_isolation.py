"""Demo rows are fixtures, never live provider input or official proof."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from autonomous_betting_agent import magazine_live_api_enrichment as enrichment
from autonomous_betting_agent.ledger_types import classify_ledger_type, public_metric_allowed
from autonomous_betting_agent.report_exports import summarize_record


def fixture(**fields):
    return {'event': 'SYNTHETIC Alpha vs Beta', 'home_team': 'Beta', 'away_team': 'Alpha',
            'venue': 'Synthetic Field', 'proof_id': 'synthetic-only',
            'locked_at_utc': '2026-01-01T10:00:00Z', 'event_start_utc': '2026-01-01T12:00:00Z',
            'grade': 'win', 'ledger_type': 'official', **fields}


class OfflineDemoIsolationTests(unittest.TestCase):
    def test_legacy_demo_markers_never_count_as_public_proof(self):
        for marker in ('source_file', 'active_list_id', 'ledger_batch_id'):
            for ledger in ('official', 'all_high_confidence'):
                with self.subTest(marker=marker, ledger=ledger):
                    row = fixture(**{marker: 'demo_ledger', 'ledger_type': ledger})
                    self.assertFalse(public_metric_allowed(row))
                    self.assertEqual(classify_ledger_type(row), 'research')
                    self.assertEqual(summarize_record([row])['rows'], 0)

    def test_demonstration_flag_and_fixture_scope_are_not_official(self):
        for flags in ({'demonstration_mode': True}, {'demonstration_mode': 'true'},
                      {'report_data_scope': 'Demonstration only'},
                      {'source_mode': 'synthetic_test_fixture'}):
            with self.subTest(flags=flags):
                self.assertFalse(public_metric_allowed(fixture(**flags)))

    def test_ordinary_rows_remain_public_and_research_high_confidence_does_not(self):
        self.assertTrue(public_metric_allowed(fixture()))
        self.assertTrue(public_metric_allowed(fixture(ledger_type='all_high_confidence')))
        self.assertFalse(public_metric_allowed(fixture(ledger_type='all_high_confidence', research_only=True)))

    def test_demo_does_not_attempt_provider_calls_even_with_configured_keys(self):
        for flags in ({'demonstration_mode': True}, {'source_file': 'demo_ledger'},
                      {'report_title': 'Validation fixture'}, {'source_mode': 'synthetic_fixture'}):
            with self.subTest(flags=flags), patch.object(enrichment, '_secret', return_value='synthetic-not-a-real-key'), \
                    patch.object(enrichment, '_request_json', return_value={}) as request:
                original = fixture(**flags)
                result = enrichment.enrich_row_with_live_api_data(original)
                request.assert_not_called()
                self.assertEqual(result['live_api_enrichment_status'], 'DEMONSTRATION_ONLY')
                self.assertNotIn('live_api_enrichment_status', original)

    def test_demo_renderer_wrapper_does_not_attempt_provider_calls(self):
        module = SimpleNamespace(render_full_pick_magazine_page=lambda row: row, MAGAZINE_STYLE_VERSION='test')
        enrichment.install(module)
        with patch.object(enrichment, '_secret', return_value='synthetic-not-a-real-key'), \
                patch.object(enrichment, '_request_json', return_value={}) as request:
            result = module.render_full_pick_magazine_page(fixture(demonstration_mode=True))
            request.assert_not_called()
            self.assertTrue(result['demonstration_mode'])

    def test_no_keys_means_no_provider_requests(self):
        with patch.object(enrichment, '_secret', return_value=''), \
                patch.object(enrichment, '_request_json', return_value={}) as request:
            result = enrichment.enrich_row_with_live_api_data(fixture())
            request.assert_not_called()
            self.assertEqual(result['sportsdataio_status'], 'API_KEY_MISSING')

    def test_buyer_demo_page_does_not_write_production_session_slots(self):
        root = Path(__file__).resolve().parents[1]
        tree = ast.parse((root / 'pages/buyer_demo_mode.py').read_text())
        stores = {node.slice.value for node in ast.walk(tree)
                  if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store)
                  and isinstance(node.value, ast.Attribute) and node.value.attr == 'session_state'
                  and isinstance(node.slice, ast.Constant)}
        self.assertNotIn('odds_lock_pro_locked_rows', stores)
        self.assertNotIn('ara_latest_predictions', stores)
        self.assertIn('buyer_demo_mode_rows', stores)


if __name__ == '__main__':
    unittest.main()
