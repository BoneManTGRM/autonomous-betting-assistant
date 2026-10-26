from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from autonomous_betting_agent import prospective_evidence as pe

NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


def stamp(minutes=0):
    return (NOW + timedelta(minutes=minutes)).isoformat()


def prediction(**changes):
    row = {
        'event_namespace': 'synthetic-provider-v1', 'event_id': 'synthetic-1',
        'market_id': 'full-game-moneyline', 'selection_id': 'home', 'sport': 'synthetic',
        'market_type': 'moneyline_2way', 'event_label': 'Synthetic A v B',
        'selection_label': 'Synthetic A', 'settlement_rule': 'Full game, overtime included; abandoned = void',
        'raw_model_version': 'synthetic-raw-v1', 'baseline_model_version': 'synthetic-baseline-v1',
        'event_source': 'https://example.invalid/fixture', 'prediction_source': 'synthetic-artifact-sha256-reference',
        'odds_source': 'synthetic-book', 'event_start': stamp(60),
        'raw_probability_available_at': stamp(-1), 'baseline_probability_available_at': stamp(-1),
        'odds_observed_at': stamp(-1), 'raw_model_probability': .70000012345,
        'baseline_probability': .62, 'decimal_odds': 1.9,
    }
    row.update(changes)
    return row


def input_text(rows=None, **protocol):
    values = {'test_id': 'synthetic-test', 'population': 'All predeclared synthetic events',
              'selection_policy': 'One fixed rule, no outcome-based selection',
              'exclusions': 'No exclusions', 'baseline_definition': 'Frozen synthetic baseline'}
    values.update(protocol)
    return json.dumps({'protocol': values, 'predictions': rows if rows is not None else [prediction()]})


def receipt(packet, index=0, **changes):
    r = pe.receipt_template(packet, now=NOW)[index]
    r.update({'result_status': 'win', 'result_available_at': stamp(180),
              'source_observed_at': stamp(181), 'verified_at': stamp(182),
              'source_url': 'https://example.invalid/synthetic-final', 'source_sha256': 'a' * 64,
              'source_final_status': 'final', 'verifier_reference': 'synthetic-reviewer',
              'settlement_explanation': 'Synthetic final score supports the supplied selection and settlement rule'})
    r.update(changes)
    return r


def review(packet, receipts):
    return pe.review_packet(json.dumps(packet), json.dumps(receipts), now=NOW + timedelta(hours=4))


class ProspectiveEvidenceTests(unittest.TestCase):
    def test_preparation_preserves_original_exact_values_and_has_no_proof(self):
        raw = input_text() + '\n'
        packet = pe.prepare_packet(raw, now=NOW)
        self.assertEqual(packet['original_input'], raw)
        self.assertEqual(packet['input_sha256'], hashlib.sha256(raw.encode()).hexdigest())
        self.assertEqual(packet['predictions'][0]['prediction'], json.loads(raw)['predictions'][0])
        self.assertEqual(pe.validate_packet(packet, now=NOW), packet)
        for key, value in pe.TRUST.items():
            self.assertEqual(packet[key], value)
        self.assertFalse(packet['authenticated_pre_event_commitment'])
        self.assertEqual(pe.receipt_template(packet, now=NOW)[0]['result_status'], '')

    def test_past_event_future_availability_and_stale_odds_block(self):
        for changes in ({'event_start': stamp(0)}, {'event_start': stamp(-1)},
                        {'event_start': '2026-01-01T15:00:00'},
                        {'odds_observed_at': stamp(-6)}, {'odds_observed_at': stamp(1)},
                        {'raw_probability_available_at': stamp(1)},
                        {'baseline_probability_available_at': stamp(1)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                pe.prepare_packet(input_text([prediction(**changes)]), now=NOW)

    def test_missing_unknown_result_and_backdating_fields_block(self):
        for field in pe.PREDICTION_FIELDS:
            row = prediction(); del row[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                pe.prepare_packet(input_text([row]), now=NOW)
        for field in ('result_status', 'winner', 'score', 'outcome_verified', 'prepared_at', 'prediction_recorded_at', 'closing_odds', 'confidence'):
            with self.subTest(extra=field), self.assertRaises(ValueError):
                pe.prepare_packet(input_text([prediction(**{field: 'forged'})]), now=NOW)
        with self.assertRaises(ValueError):
            pe.prepare_packet(input_text(population=''), now=NOW)

    def test_numeric_bool_nonfinite_and_out_of_range_block(self):
        for field in ('raw_model_probability', 'baseline_probability', 'decimal_odds'):
            for value in (True, '0.7', None, float('nan'), float('inf'), 10**400):
                with self.subTest(field=field, value=str(value)[:20]), self.assertRaises(ValueError):
                    pe.prepare_packet(input_text([prediction(**{field: value})]), now=NOW)
        for value in (-.1, 1.1):
            with self.assertRaises(ValueError):
                pe.prepare_packet(input_text([prediction(raw_model_probability=value)]), now=NOW)
        for value in (-1, 0, 1):
            with self.assertRaises(ValueError):
                pe.prepare_packet(input_text([prediction(decimal_odds=value)]), now=NOW)
        for value in (0, 1):
            self.assertIsInstance(pe.prepare_packet(input_text([prediction(raw_model_probability=value)]), now=NOW), dict)

    def test_duplicate_conflicting_events_and_cross_namespace_fail_closed(self):
        for other in (prediction(), prediction(raw_model_probability=.8),
                      prediction(selection_id='away', event_start=stamp(80)),
                      prediction(selection_id='away', sport='different'),
                      prediction(selection_id='away', settlement_rule='different'),
                      prediction(event_namespace='another-provider'),
                      prediction(event_id='another-event', raw_model_version='changed-raw'),
                      prediction(event_id='another-event', baseline_model_version='changed-base')):
            with self.subTest(other=other), self.assertRaises(ValueError):
                pe.prepare_packet(input_text([prediction(), other]), now=NOW)
        packet = pe.prepare_packet(input_text([prediction(), prediction(selection_id='away', selection_label='Synthetic B')]), now=NOW)
        report = review(packet, [])
        self.assertEqual(report['cohort_rows'], 2)
        self.assertEqual(report['unique_supplied_event_ids'], 1)

    def test_packet_modified_hash_schema_type_and_future_clock_fail_closed(self):
        packet = pe.prepare_packet(input_text(), now=NOW)
        for modify in (lambda p: p.update(packet_sha256='b'*64),
                       lambda p: p.update(independently_verified=True),
                       lambda p: p.update(independently_verified=0),
                       lambda p: p.update(extra='unexpected'),
                       lambda p: p['predictions'][0]['prediction'].update(raw_model_probability=.8),
                       lambda p: p.update(original_input=p['original_input']+' ')):
            changed = deepcopy(packet); modify(changed)
            with self.assertRaises(ValueError): pe.validate_packet(changed, now=NOW)
        with self.assertRaises(ValueError): pe.validate_packet(packet, now=NOW-timedelta(seconds=1))

    def test_fully_rehashed_forgery_remains_unverified(self):
        # A locally valid fabricated claim cannot be distinguished by hashes.
        forged = pe.prepare_packet(input_text(), now=NOW)
        report = review(forged, [receipt(forged)])
        self.assertEqual(report['supplied_wins'], 1)
        self.assertEqual(report['authenticated_rows'], 0)
        self.assertEqual(report['unverified_rows'], 1)
        for key in ('independently_verified', 'authenticated_pre_event_commitment', 'training_allowed', 'promotion_allowed', 'live_mutation_allowed', 'predictive_gain_proven'):
            self.assertIs(report[key], False)
        self.assertNotIn('win_rate', report); self.assertNotIn('roi', report)

    def test_cohort_preserved_pending_void_win_loss_and_no_mutation(self):
        rows = [prediction(event_id=f'synthetic-{i}') for i in range(4)]
        packet = pe.prepare_packet(input_text(rows), now=NOW)
        receipts = [receipt(packet, i, result_status=grade) for i, grade in enumerate(('win', 'loss', 'void'))]
        original = deepcopy((packet, receipts))
        report = review(packet, receipts)
        self.assertEqual((packet, receipts), original)
        self.assertEqual(report['cohort_rows'], 4)
        for key in ('pending_rows', 'supplied_voids', 'supplied_wins', 'supplied_losses'):
            self.assertEqual(report[key], 1)
        self.assertEqual(report['unverified_rows'], 4)

    def test_mismatched_or_bad_receipt_retained_not_counted(self):
        packet = pe.prepare_packet(input_text(), now=NOW)
        changes = [{'packet_sha256': 'b'*64}, {'event_id': 'wrong'}, {'market_id':'wrong'},
                   {'selection_id':'wrong'}, {'event_namespace':'wrong'}, {'result_status':'pending win review'},
                   {'source_url':'http://example.invalid/'}, {'source_url':'https://user:pass@example.invalid/'},
                   {'source_sha256':'not-a-hash'}, {'source_final_status':'pending'},
                   {'result_available_at':stamp(0)}, {'source_observed_at':stamp(179)},
                   {'verified_at':stamp(300)}, {'result_available_at':stamp(60)},
                   {'outcome_verified':True}]
        for change in changes:
            raw = receipt(packet, **change)
            with self.subTest(change=change):
                report = review(packet, [raw])
                self.assertEqual(report['rejected_receipts'], 1)
                self.assertEqual(report['supplied_wins'], 0)
                self.assertEqual(report['receipts'][0]['receipt'], raw)
                self.assertEqual(report['needs_review_rows'], 1)

    def test_duplicate_and_revised_receipts_do_not_last_write_win(self):
        packet = pe.prepare_packet(input_text(), now=NOW)
        for second in (receipt(packet), receipt(packet, result_status='loss')):
            report = review(packet, [receipt(packet), second])
            self.assertEqual(report['rejected_receipts'], 2)
            self.assertEqual(report['duplicate_or_revised_receipts'], 2)
            self.assertEqual(report['supplied_wins'], 0)
            self.assertEqual(report['supplied_losses'], 0)
            self.assertEqual(report['needs_review_rows'], 1)

    def test_unknown_and_nonobject_receipts_never_disappear(self):
        packet = pe.prepare_packet(input_text(), now=NOW)
        raw = [receipt(packet, prediction_id='unknown'), None, 'not a receipt', {'prediction_id': []}]
        report = review(packet, raw)
        self.assertEqual(report['receipt_count'], 4)
        self.assertEqual(report['rejected_receipts'], 4)
        self.assertEqual(report['pending_rows'], 1)
        self.assertEqual([entry['receipt'] for entry in report['receipts']], raw)

    def test_strict_json_duplicate_keys_and_invalid_counts(self):
        with self.assertRaises(ValueError): pe.prepare_packet('{"protocol": {}, "protocol": {}}', now=NOW)
        with self.assertRaises(ValueError): pe.prepare_packet(input_text([]), now=NOW)
        with self.assertRaises(ValueError): pe.prepare_packet('x'*(pe.MAX_INPUT_BYTES+1), now=NOW)
        packet = pe.prepare_packet(input_text(), now=NOW)
        with self.assertRaises(ValueError): pe.review_packet(json.dumps(packet), '{}', now=NOW)
        with self.assertRaises(ValueError): pe.review_packet(json.dumps(packet), '[NaN]', now=NOW)
        with self.assertRaises(ValueError): pe.prepare_packet(input_text(), now=datetime(2026,1,1))

    def test_pure_workflow_cannot_write_network_or_train(self):
        with patch('builtins.open', side_effect=AssertionError('no file I/O')), \
             patch.object(Path, 'write_text', side_effect=AssertionError('no writes')), \
             patch.object(socket, 'socket', side_effect=AssertionError('no network')):
            packet = pe.prepare_packet(input_text(), now=NOW)
            report = review(packet, [receipt(packet)])
            self.assertEqual(report['authenticated_rows'], 0)
        source = Path(pe.__file__).read_text()
        for token in ('fit_calibrator(', 'save_', 'load_ledger(', 'urlopen(', 'requests.'):
            self.assertNotIn(token, source)


if __name__ == '__main__': unittest.main()
