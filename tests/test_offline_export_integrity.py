"""Synthetic offline regressions for local grading and report integrity."""
import unittest

from autonomous_betting_agent.explanations import build_pick_explanation
from autonomous_betting_agent.grading_rules import grade_from_row, summarize_row_level
from autonomous_betting_agent.report_exports import (
    render_html_report, render_markdown_report, render_messenger_report, summarize_record,
)


def official(**fields):
    return {
        'event': 'SYNTHETIC Alpha vs Beta',
        'proof_id': 'synthetic-test-proof',
        'ledger_type': 'official',
        'locked_at_utc': '2026-01-01T10:00:00Z',
        'event_start_utc': '2026-01-01T12:00:00Z',
        **fields,
    }


class OfflineExportIntegrityTests(unittest.TestCase):
    def test_nonfinite_profit_does_not_resolve_rows(self):
        for value in ('NaN', 'nan', 'Infinity', '-Infinity', float('nan'), float('inf')):
            with self.subTest(value=value):
                self.assertEqual(grade_from_row({'profit_units': value}), 'pending')

    def test_nonfinite_profit_can_fall_through_to_valid_profit(self):
        self.assertEqual(grade_from_row({'actual_profit_units': 'NaN', 'profit_units': 2}), 'win')

    def test_finite_profit_and_explicit_grade_are_preserved(self):
        for value, grade in ((2, 'win'), (-2, 'loss'), (0, 'push')):
            self.assertEqual(grade_from_row({'profit_units': value}), grade)
        self.assertEqual(grade_from_row({'result_status': 'win', 'profit_units': 'NaN'}), 'win')
        self.assertEqual(grade_from_row({'result_status': 'pending', 'profit_units': 2}), 'pending')

    def test_export_recognizes_canonical_result_status(self):
        summary = summarize_record([official(result_status='win', decimal_price=2, stake=2)])
        self.assertEqual(summary['wins'], 1)
        self.assertEqual(summary['pending'], 0)
        self.assertEqual(summary['profit_units'], 2)

    def test_export_counts_match_shared_grading(self):
        rows = [official(**fields) for fields in (
            {'result_status': 'win'}, {'graded_result': 'loss'}, {'grade': 'void'},
            {'result': 'cancelled'}, {'grade': 'ungraded'}, {'grade': 'unrecognized'},
            {'grade': 'pending', 'result_status': 'win'},
        )]
        expected = summarize_row_level(rows)
        actual = summarize_record(rows)
        for key in ('rows', 'wins', 'losses', 'pushes', 'cancels', 'pending'):
            self.assertEqual(actual[key], expected[key], key)
        self.assertEqual(sum(actual[k] for k in ('wins', 'losses', 'pushes', 'cancels', 'pending')), len(rows))

    def test_zero_stake_never_becomes_one_unit(self):
        for fields in ({'stake': 0}, {'stake': '0'}, {'units': 0}, {'stake_units': 0}, {'stake': 0, 'units': 5}):
            with self.subTest(fields=fields):
                summary = summarize_record([official(grade='loss', **fields)])
                self.assertIsNone(summary['profit_units'])
                self.assertIsNone(summary['roi'])

    def test_native_locked_stake_units_are_used(self):
        summary = summarize_record([official(result_status='win', stake_units=.5, decimal_price=3)])
        self.assertEqual(summary['profit_units'], 1)
        self.assertEqual(summary['roi'], 2)

    def test_invalid_stakes_do_not_invent_profit(self):
        for value in ('bad', -2, 'NaN', 'Infinity', '-Infinity', 10 ** 400):
            for grade in ('win', 'loss'):
                with self.subTest(value=value, grade=grade):
                    summary = summarize_record([official(grade=grade, stake=value, decimal_price=2)])
                    self.assertIsNone(summary['profit_units'])
                    self.assertIsNone(summary['roi'])

    def test_missing_stake_retains_one_unit_default(self):
        summary = summarize_record([official(grade='win', decimal_price=3), official(grade='loss')])
        self.assertEqual(summary['profit_units'], 1)
        self.assertEqual(summary['roi'], 0.5)

    def test_invalid_winning_prices_do_not_invent_profit(self):
        for value in (0, 1, -2, 'bad', 'NaN', 'Infinity', '-Infinity'):
            with self.subTest(value=value):
                summary = summarize_record([official(grade='win', stake=2, decimal_price=value)])
                self.assertIsNone(summary['profit_units'])
                self.assertIsNone(summary['roi'])

    def test_numeric_aliases_keep_explicit_values(self):
        summary = summarize_record([official(grade='win', stake='', units=2, decimal_price='', odds_at_pick=3)])
        self.assertEqual(summary['profit_units'], 4)
        summary = summarize_record([official(grade='win', stake=2, decimal_price=0, odds_at_pick=3)])
        self.assertIsNone(summary['profit_units'])

    def test_nonfinite_optional_numbers_do_not_crash_export(self):
        for value in (float('nan'), float('inf'), float('-inf'), 'NaN', 'Infinity', 10 ** 400):
            with self.subTest(value=value):
                row = official(books=value, pattern_points=80, learning_pattern_count=value,
                               probability=value, edge=value)
                for render in (render_markdown_report, render_html_report):
                    report = render([row])
                    self.assertIn('SYNTHETIC Alpha vs Beta', report)
                    self.assertNotIn('nan%', report.lower())
                    self.assertNotIn('inf%', report.lower())

    def test_financial_arithmetic_overflow_is_not_reported_as_profit(self):
        cases = [
            [official(grade='win', stake=1e308, decimal_price=3)],
            [official(grade='win', stake=1e308, decimal_price=2)] * 2,
            [official(grade='loss', stake=1e308)] * 2,
            [official(grade='win', stake=1e308, decimal_price=1.5)] * 2,
        ]
        for rows in cases:
            with self.subTest(rows=rows):
                summary = summarize_record(rows)
                self.assertIsNone(summary['profit_units'])
                self.assertIsNone(summary['roi'])

    def test_numeric_explanation_alias_fallback(self):
        text = build_pick_explanation(official(books='NaN', bookmaker_count=4, probability=0.6))
        self.assertIn('Book coverage is broad', text)
        self.assertIn('60.0%', text)

    def test_export_formats_and_public_filter_are_preserved(self):
        rows = [official(result_status='win'), official(result_status='loss', ledger_type='research')]
        self.assertIn('- Wins: 1', render_markdown_report(rows))
        self.assertIn('- Losses: 0', render_html_report(rows))
        self.assertIn('Record: 1-0', render_messenger_report(iter(rows)))
        self.assertEqual(summarize_record(rows)['rows'], 1)
        self.assertEqual(summarize_record(rows, official_only=False)['rows'], 2)


if __name__ == '__main__':
    unittest.main()
