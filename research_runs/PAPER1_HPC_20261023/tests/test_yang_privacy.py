"""Versioned identities and original policy behavior; metadata only, no fits."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from hpcmi import yang_privacy as p

if str(p.VENDOR) not in sys.path:
    sys.path.insert(0, str(p.VENDOR))
original_events = importlib.import_module('eligibility_policy')
original_clock = importlib.import_module('yang_clock_policy')


class PrivacyPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / 'config'
        self.config.mkdir()
        for filename in ('yang_nemar_privacy_v1.json', 'yang_clock_registry_nemar_privacy_v1.json',
                         'eligibility_manifest_nemar_privacy_v1.json'):
            shutil.copyfile(p.CONFIG / filename, self.config / filename)
        self.config_patch = mock.patch.object(p, 'CONFIG', self.config)
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        self.hash_patch = mock.patch.object(p, 'CONTRACT_SHA256', p.CONTRACT_SHA256)
        self.hash_patch.start()
        self.addCleanup(self.hash_patch.stop)
        self.data = SimpleNamespace(population=original_events.population,
                                    qualified_events=original_events.qualified_events)

    def read(self, filename):
        return json.loads((self.config / filename).read_text())

    def mutate(self, filename, callback):
        obj = self.read(filename)
        callback(obj)
        path = self.config / filename
        path.write_text(json.dumps(obj, indent=2) + '\n')
        if filename != 'yang_nemar_privacy_v1.json':
            field = ('clock_registry_sha256' if filename.startswith('yang_clock') else
                     'eligibility_manifest_sha256')
            contract = self.read('yang_nemar_privacy_v1.json')
            contract[field] = hashlib.sha256(path.read_bytes()).hexdigest()
            (self.config / 'yang_nemar_privacy_v1.json').write_text(json.dumps(contract, indent=2) + '\n')
        p.CONTRACT_SHA256 = hashlib.sha256((self.config / 'yang_nemar_privacy_v1.json').read_bytes()).hexdigest()

    def test_default_inactive_marker_is_explicit_and_pins_keep_actual_new_identities(self):
        self.assertFalse(p.is_active(self.root / 'yang'))
        with self.assertRaisesRegex(ValueError, 'not active'):
            p.pins(self.root / 'yang')
        marker = self.root / 'yang/.source-profile.json'
        marker.parent.mkdir()
        marker.write_text(json.dumps({'profile': p.PROFILE}))
        self.assertTrue(p.is_active(marker.parent))
        rows = p.pins(marker.parent)
        self.assertEqual(len(rows), 312)
        native = [r for r in rows if r['original_sha256']]
        self.assertEqual(len(native), 306)
        self.assertTrue(all(r['sha256'] != r['original_sha256'] and 'crc32' not in r for r in native))
        self.assertTrue(all(r['crc32'] == r['original_zip_crc32'] for r in rows if not r['original_sha256']))
        self.assertTrue(all(r['url'] == r['provider_url'] for r in rows))
        marker.write_text(json.dumps({'profile': 'unreviewed'}))
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            p.is_active(marker.parent)

    def test_contract_hash_tampering_is_rejected(self):
        path = self.config / 'yang_nemar_privacy_v1.json'
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            p.load_contract()

    def test_scientific_clock_or_eligibility_change_rejected_even_after_resigning_identity(self):
        self.mutate('yang_clock_registry_nemar_privacy_v1.json',
                    lambda obj: obj['pairs'][0]['signal'].__setitem__('start_date_time', '20.03.1913.53.11'))
        with self.assertRaisesRegex(ValueError, 'non-identity fields'):
            p.load_contract()
        # Restore this file before checking an independent eligibility mutation.
        shutil.copyfile(p.ROOT / 'config/yang_clock_registry_nemar_privacy_v1.json',
                        self.config / 'yang_clock_registry_nemar_privacy_v1.json')
        self.mutate('yang_clock_registry_nemar_privacy_v1.json', lambda obj: None)
        self.mutate('eligibility_manifest_nemar_privacy_v1.json',
                    lambda obj: obj['sessions'][0]['all_marker_counts'].__setitem__('1', 99))
        with self.assertRaisesRegex(ValueError, 'eligibility policy changed'):
            p.load_contract()

    @staticmethod
    def events_for(fixed):
        if 'all_events' in fixed:
            return copy.deepcopy(fixed['all_events'])
        codes = ['7'] * fixed['all_marker_counts'].get('7', 0)
        codes.extend(['255'] * fixed['all_marker_counts'].get('255', 0))
        for block in range(5):
            codes.extend(['1'] * 20 + ['2'] * 20)
            if block != 4:
                codes.append('9')
        codes.extend(['8'] * fixed['all_marker_counts'].get('8', 0))
        return [{'description': code, 'onset': float(i), 'duration': 0.0} for i, code in enumerate(codes)]

    def test_all_153_session_cues_labels_and_onsets_unchanged_with_real_new_identity(self):
        old = original_events.sessions()
        new = {(r['subject'], r['session']): r for r in self.read('eligibility_manifest_nemar_privacy_v1.json')['sessions']}
        with p.policy_context(self.data) as identity:
            self.assertEqual(identity['profile'], p.PROFILE)
            for person in range(1, 52):
                self.assertEqual(self.data.population('yang', person), original_events.population('yang', person))
            for key, fixed in old.items():
                events = self.events_for(fixed)
                before = {k: fixed[j] for k, j in [('path', 'path'), ('size', 'bytes'), ('sha256', 'sha256')]}
                after = {**before, 'sha256': new[key]['sha256']}
                expected_cues, expected_audit = original_events.qualified_events(*key, events, before)
                actual_cues, actual_audit = self.data.qualified_events(*key, events, after)
                self.assertEqual(actual_cues, expected_cues)
                self.assertEqual({k: v for k, v in actual_audit.items() if k != 'eligibility_manifest_sha256'},
                                 {k: v for k, v in expected_audit.items() if k != 'eligibility_manifest_sha256'})
                self.assertNotEqual(actual_audit['eligibility_manifest_sha256'], expected_audit['eligibility_manifest_sha256'])
                with self.assertRaisesRegex(ValueError, 'fixed eligibility identity'):
                    self.data.qualified_events(*key, events, before)

    def test_new_clock_rejects_wrong_hash_header_time_and_old_identity(self):
        pair = self.read('yang_clock_registry_nemar_privacy_v1.json')['pairs'][0]
        def arguments():
            return [pair['subject'], pair['session'], pair['signal']['start_date_time'], pair['event']['start_date_time'],
                {k: pair['signal'][v] for k, v in [('path', 'path'), ('size', 'bytes'), ('sha256', 'sha256')]},
                {k: pair['event'][v] for k, v in [('path', 'path'), ('size', 'bytes'), ('sha256', 'sha256')]},
                pair['signal']['header_sha256'], pair['event']['header_sha256']]
        with p.policy_context(self.data):
            result = original_clock.validate_yang_clock(*arguments())
            self.assertEqual(result['event_shift_seconds'], 0.0)
            self.assertEqual(result['input_profile'], p.PROFILE)
            for index, replacement in ((2, '20.03.1913.53.11'), (6, '0' * 64)):
                args = arguments();args[index] = replacement
                with self.assertRaises(ValueError):
                    original_clock.validate_yang_clock(*args)
            args = arguments();args[4]['sha256'] = '0' * 64
            with self.assertRaises(ValueError):
                original_clock.validate_yang_clock(*args)

    def test_changed_event_sequence_rejected_and_context_restores_after_error(self):
        original_q, original_p = self.data.qualified_events, self.data.population
        original_c = original_clock.validate_yang_clock
        fixed = self.read('eligibility_manifest_nemar_privacy_v1.json')['sessions'][0]
        record = {'path': fixed['path'], 'size': fixed['bytes'], 'sha256': fixed['sha256']}
        with self.assertRaisesRegex(RuntimeError, 'deliberate'):
            with p.policy_context(self.data):
                events = self.events_for(fixed)
                events[1]['description'] = '255'
                with self.assertRaisesRegex(ValueError, 'event sequence/count'):
                    self.data.qualified_events(fixed['subject'], fixed['session'], events, record)
                raise RuntimeError('deliberate')
        self.assertIs(self.data.qualified_events, original_q)
        self.assertIs(self.data.population, original_p)
        self.assertIs(original_clock.validate_yang_clock, original_c)


if __name__ == '__main__':
    unittest.main()
