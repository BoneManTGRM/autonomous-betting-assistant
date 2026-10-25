"""Intentional contract change: intake is review-only, never live training."""
from __future__ import annotations

from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import ast
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from autonomous_betting_agent import auto_learning_cycle as cycle
from autonomous_betting_agent.learning_evidence_admission import admission_reasons, load_evidence_json, review_learning_records
from autonomous_betting_agent.learning_memory_tools import compact_row, extract_probability, extract_result, read_compact_csv_bytes
from autonomous_betting_agent.learning import ProbabilityCalibrator


def claim(index=0, **changes):
    decision = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=index)
    stamp = lambda hours: (decision + timedelta(hours=hours)).isoformat()
    row = {'event_id': f'synthetic-{index}', 'market_id': 'moneyline-full-game', 'selection_id': 'home',
           'sport': 'synthetic', 'market_type': 'moneyline_2way', 'event': f'Synthetic game {index}',
           'decision_time': stamp(0), 'prediction_recorded_at': stamp(0), 'event_start': stamp(1),
           'result_available_at': stamp(5), 'verified_at': stamp(6), 'outcome_verified': True,
           'raw_model_probability': 0.7, 'baseline_probability': 0.7,
           'raw_probability_available_at': stamp(0), 'baseline_probability_available_at': stamp(0),
           'raw_model_version': 'synthetic-raw-v1', 'baseline_model_version': 'synthetic-base-v1',
           'result_status': 'win' if index % 2 else 'loss', 'features': {},
           'event_source': 'synthetic event claim', 'prediction_source': 'synthetic prediction claim',
           'result_source': 'https://example.invalid/forged-but-well-formed-claim'}
    row.update(changes)
    return row


def csv_bytes(rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: json.dumps(value) if isinstance(value, (dict, list, bool)) else value for key, value in row.items()})
    return out.getvalue().encode()


class LearningEvidenceAdmissionTests(unittest.TestCase):
    def test_complete_supplied_claim_is_not_authenticated_or_permission(self):
        original = [claim(index) for index in range(60)]
        before = deepcopy(original)
        report = review_learning_records(original)
        self.assertEqual(report['status'], 'READY_FOR_OBSERVATION_ONLY')
        self.assertEqual(original, before)
        self.assertEqual([entry['record'] for entry in report['records']], original)
        for key in ('independently_verified', 'trained', 'artifacts_written', 'live_mutation_allowed', 'promotion_allowed', 'predictive_gain_proven'):
            self.assertIs(report[key], False)
        self.assertEqual(report['evidence_authentication'], 'UNVERIFIED_SUPPLIED_CLAIMS')

    def test_legacy_unverified_conditional_conflicting_and_wrong_event_are_rejected(self):
        variants = [claim(outcome_verified=False), claim(result_status='pending win review'),
                    claim(result_status='win', result='loss'), claim(verified_grade='win', result_status='loss'),
                    claim(manual_grade='win', result_status='loss'), claim(matched_result_event_id='different'),
                    claim(grading_match_status='identity_needs_review'), claim(result_source='')]
        for row in variants:
            with self.subTest(row=row):
                self.assertTrue(admission_reasons(row)[0])
                self.assertIsNone(compact_row(row, 2, 'synthetic'))
        self.assertIsNone(extract_result({'prediction': 'A', 'winner': 'A'}))

    def test_missing_true_probability_never_falls_back_to_confidence_price_or_final(self):
        row = claim(confidence='high', decimal_price=1.8, final_probability=.99)
        del row['raw_model_probability']
        self.assertEqual(extract_probability(row), (None, 'missing_original_probability'))
        self.assertIsNone(compact_row(row, 2, 'High confidence.csv'))

    def test_missing_chronology_versions_and_provenance_are_not_reconstructed(self):
        for field in ('prediction_recorded_at', 'event_start', 'verified_at', 'raw_probability_available_at',
                      'raw_model_version', 'baseline_model_version', 'event_source', 'prediction_source', 'result_source'):
            row = claim()
            del row[field]
            before = deepcopy(row)
            self.assertTrue(admission_reasons(row)[0], field)
            self.assertEqual(row, before)
        row = claim(raw_probability_available_at=claim()['verified_at'])
        self.assertTrue(admission_reasons(row)[0])

    def test_compact_retains_every_original_field_without_rounding_probability(self):
        row = claim(raw_model_probability=.701234567890123, custom_receipt={'opaque': ['unchanged', 3]})
        before = deepcopy(row)
        compact = compact_row(row, 2, 'synthetic')
        self.assertEqual(compact['raw_evidence'], before)
        self.assertEqual(compact['probability'], before['raw_model_probability'])
        self.assertEqual(row, before)
        self.assertFalse(admission_reasons(compact)[0])
        compact['raw_evidence']['custom_receipt']['opaque'].append('local copy')
        self.assertEqual(row, before)

    def test_compact_envelope_cannot_hide_conflicts(self):
        for changes in ({'result_status': 'win'}, {'outcome_verified': False},
                        {'grading_match_status': 'needs_review'}, {'probability': .99},
                        {'event_id': 'different'}, {'result_source': 'different'},
                        {'probability_source': 'fallback_high_confidence'}):
            row = compact_row(claim(result_status='loss'), 2, 'synthetic')
            row.update(changes)
            self.assertTrue(admission_reasons(row)[0], changes)

    def test_every_emitted_compact_field_has_a_canonical_value_and_shape(self):
        original = compact_row(claim(result_status='loss'), 2, 'not-proof.csv')
        for key, value in original.items():
            with self.subTest(field=key):
                changed = deepcopy(original)
                if key == 'raw_evidence':
                    changed[key]['result_status'] = 'win'
                elif isinstance(value, bool):
                    changed[key] = not value
                elif isinstance(value, (int, float)):
                    changed[key] = value + 1
                else:
                    changed[key] = str(value) + '-tampered'
                self.assertTrue(admission_reasons(changed)[0])
                missing = deepcopy(original)
                del missing[key]
                self.assertTrue(admission_reasons(missing)[0])
        for key in ('future_probability_assertion', 'review_approved', 'verified_grade', 'unknown_receipt'):
            changed = {**original, key: 'claim'}
            self.assertTrue(admission_reasons(changed)[0])
        wrong_type = {**original, 'live_mutation_allowed': 0}
        self.assertTrue(admission_reasons(wrong_type)[0])
        unversioned = {'raw_evidence': claim()}
        self.assertTrue(admission_reasons(unversioned)[0])
        nested = {**original, 'raw_evidence': original}
        self.assertTrue(admission_reasons(nested)[0])

    def test_all_probability_source_and_legacy_identity_aliases_are_checked(self):
        for changes in ({'probability_source': 'raw_model_probability', 'model_probability_source': 'fallback_high_confidence'},
                        {'matched_event': 'wrong fixture'}, {'matched_event_id': 'wrong-id'}):
            self.assertTrue(admission_reasons(claim(**changes))[0])

    def test_duplicate_json_keys_and_invalid_utf8_fail_instead_of_last_wins(self):
        with self.assertRaises(ValueError):
            load_evidence_json('{"result_status":"loss","result_status":"win"}')
        with self.assertRaises(ValueError):
            load_evidence_json('{"raw_model_probability":NaN}')
        row = claim(features='{"rest_days":{},"rest_days":{}}')
        self.assertTrue(admission_reasons(row)[0])
        with self.assertRaises(UnicodeDecodeError):
            read_compact_csv_bytes(b'event,result\n\xff,win\n', 'synthetic.csv')

    def test_batch_does_not_silently_drop_rejected_or_duplicate_records(self):
        good = claim(1)
        bad = claim(2, outcome_verified=False)
        rows = [good, deepcopy(good), bad]
        report = review_learning_records(rows, minimum_events=1)
        self.assertEqual(report['input_rows'], 3)
        self.assertEqual([entry['record'] for entry in report['records']], rows)
        self.assertEqual(report['unique_admitted_events'], 1)
        self.assertEqual(report['minimum_required_events'], 50)
        self.assertFalse(report['batch_admitted'])
        compact, stats = read_compact_csv_bytes(csv_bytes(rows), 'synthetic.csv')
        self.assertEqual(compact, [])
        self.assertEqual(len(stats['admission_report']['records']), 3)

    def test_event_conflict_quarantines_both_outcomes(self):
        left, right = claim(3), claim(3, result_status='loss')
        report = review_learning_records([left, right])
        self.assertEqual(report['rejected_rows'], 2)
        self.assertEqual(report['admitted_rows'], 0)
        self.assertEqual([entry['record'] for entry in report['records']], [left, right])

    def test_csv_duplicate_headers_and_bad_width_fail_without_normalizing_evidence(self):
        for data in (b'result,result\nwin,loss\n', b'event,result\na,win,extra\n', b'event,result\na\n'):
            with self.assertRaises(ValueError):
                read_compact_csv_bytes(data, 'synthetic.csv')

    def test_existing_weight_readers_are_unchanged_by_auto_review(self):
        from autonomous_betting_agent.adaptive_learning import load_memory_payload
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            state = root / 'learned_state.json'
            bank = root / 'data' / 'learning_memory_bank.json'
            state.write_text(json.dumps({'intercept': .25, 'slope': .9, 'events_trained': 12, 'source': 'synthetic legacy'}))
            payload = {'compact_rows': [{'probability': .7, 'outcome': 1}], 'patterns': [{'old': 'unchanged'}]}
            bank.write_text(json.dumps(payload))
            before = {path: path.read_bytes() for path in (state, bank)}
            loaded_before = ProbabilityCalibrator.load(state).to_dict()
            with patch.object(cycle, 'REPO_ROOT', root), patch.object(cycle, 'MEMORY_BANK_PATH', bank):
                report = cycle.run_auto_learning_cycle(min_new_rows=1, min_total_rows=5, save_to_github=True)
            self.assertEqual(report['status'], 'BLOCKED')
            self.assertEqual(load_memory_payload(bank), payload)
            self.assertEqual(ProbabilityCalibrator.load(state).to_dict(), loaded_before)
            self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_public_auto_entrypoint_has_zero_training_writes_or_network_even_for_forged_complete_claims(self):
        import socket
        from autonomous_betting_agent import learning
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / 'data'
            data.mkdir()
            source = data / 'held_picks_test_01_odds_lock_pro_locked_rows.json'
            originals = [claim(index) for index in range(60)]
            source.write_text(json.dumps({'rows': originals}))
            before = source.read_bytes()
            with ExitStack() as stack:
                stack.enter_context(patch.object(cycle, 'REPO_ROOT', root))
                stack.enter_context(patch.object(cycle, 'MEMORY_BANK_PATH', data / 'learning_memory_bank.json'))
                fit = stack.enter_context(patch.object(learning, 'fit_probability_calibrator', side_effect=AssertionError('fit forbidden')))
                save = stack.enter_context(patch.object(ProbabilityCalibrator, 'save', side_effect=AssertionError('save forbidden')))
                stack.enter_context(patch.object(Path, 'write_text', side_effect=AssertionError('write forbidden')))
                stack.enter_context(patch.object(Path, 'write_bytes', side_effect=AssertionError('write forbidden')))
                stack.enter_context(patch.object(socket, 'create_connection', side_effect=AssertionError('network forbidden')))
                report = cycle.run_auto_learning_cycle(min_new_rows=1, min_total_rows=5, save_to_github=True)
            self.assertEqual(report['status'], 'READY_FOR_OBSERVATION_ONLY')
            self.assertFalse(report['trained'])
            self.assertFalse(report['github_saved'])
            self.assertEqual([entry['record'] for entry in report['records']], originals)
            fit.assert_not_called()
            save.assert_not_called()
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(list(data.iterdir()), [source])

    def test_source_parse_failure_is_explicit_and_no_coverage_is_invented(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            bad = root / 'data' / 'held_picks_test_01_odds_lock_pro_locked_rows.json'
            bad.write_text('{bad JSON')
            with patch.object(cycle, 'REPO_ROOT', root), patch.object(cycle, 'MEMORY_BANK_PATH', root / 'absent'):
                report = cycle.run_auto_learning_cycle()
            self.assertEqual(report['status'], 'BLOCKED')
            self.assertTrue(report['source_errors'])
            self.assertIn('Remote-only', report['coverage_note'])
            self.assertEqual(bad.read_text(), '{bad JSON')

    def test_cli_explicitly_reports_no_output_even_with_complete_claims(self):
        import learn_from_results
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'synthetic.csv'
            target = Path(directory) / 'learned_state.json'
            source.write_bytes(csv_bytes([claim(index) for index in range(60)]))
            target.write_bytes(b'unchanged synthetic state')
            stdout = io.StringIO()
            with patch.object(Path, 'write_text', side_effect=AssertionError('write forbidden')), redirect_stdout(stdout):
                code = learn_from_results.main([str(source), '--output', str(target), '--min-events', '5'])
            report = json.loads(stdout.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(report['command_outcome'], 'REVIEW_ONLY_NOT_TRAINED')
            self.assertFalse(report['output_written'])
            self.assertFalse(report['independently_verified'])
            self.assertEqual(target.read_bytes(), b'unchanged synthetic state')

    def test_manual_ui_contains_no_fit_or_artifact_write_path(self):
        root = Path(__file__).resolve().parents[1]
        for file in ('pages/learn_memory_safe.py', 'pages/auto_learning_cycle.py'):
            source = (root / file).read_text()
            tree = ast.parse(source)
            calls = {node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
                     for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))}
            self.assertFalse(calls & {'fit_probability_calibrator', 'save_github', 'write_text', 'write_bytes', 'save', 'prune_rows'})
            self.assertIn("'es'", source)
            self.assertIn('solo', source.lower())
            self.assertNotIn("== 'trained'", source)


if __name__ == '__main__':
    unittest.main()
