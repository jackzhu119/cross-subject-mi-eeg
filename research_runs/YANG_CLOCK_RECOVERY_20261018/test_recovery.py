import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_reviewed_copy import build, SOURCE_DATA_SHA
from yang_clock_policy import validate_yang_clock, registry

SOURCE = Path(__file__).resolve().parents[1] / 'SOURCE_EXPANSION_20261017'


class RecoveryTests(unittest.TestCase):
    def arguments(self, row):
        return [row['subject'], row['session'], row['signal']['start_date_time'], row['event']['start_date_time'],
                *[{'path':row[r]['path'], 'size':row[r]['bytes'], 'sha256':row[r]['sha256']} for r in ('signal','event')],
                row['signal']['header_sha256'], row['event']['header_sha256']]

    def test_all_153_real_pairs_no_event_shift(self):
        from collections import Counter
        counts = Counter()
        for row in registry().pairs.values():
            audit = validate_yang_clock(*self.arguments(row))
            self.assertEqual(audit['event_shift_seconds'], 0)
            counts[audit['header_clock_difference_seconds_signal_minus_event']] += 1
        self.assertEqual(counts, {0:91, 1:61, 2:1})

    def test_actual_first_and_last_cues_unchanged(self):
        audit = validate_yang_clock(*self.arguments(registry().pairs[(1,2)]))
        self.assertEqual(round((166.634 + audit['event_shift_seconds']) * 1000), 166634)
        self.assertEqual(round((2151.278 + audit['event_shift_seconds']) * 1000), 2151278)

    def test_changed_clock_header_and_whole_file_rejected(self):
        import copy
        for index in [2,3,4,5,6,7]:
            args = copy.deepcopy(self.arguments(registry().pairs[(1,1)]))
            if index in (4,5):
                args[index]['sha256'] = '0'*64
            else:
                args[index] = 'changed'
            with self.subTest(field=index), self.assertRaises(ValueError):
                validate_yang_clock(*args)

    def test_wrong_pair_and_unknown_identity_rejected(self):
        args=self.arguments(registry().pairs[(1,2)])
        for subject,session in [(1,1),(2,2),(52,1)]:
            with self.subTest(subject=subject,session=session), self.assertRaises(ValueError):
                validate_yang_clock(subject,session,*args[2:])

    def test_incomplete_registry_invalid_date_and_duplicate_rejected(self):
        from yang_clock_registry import ClockRegistry
        import copy
        original = json.loads(Path(__file__).with_name('yang_clock_registry_v5.json').read_text())
        inventory=json.loads((SOURCE/'evidence/yang_v5_selected_inventory.json').read_text())
        changes=[lambda x:x['pairs'].pop(),lambda x:x['pairs'].append(x['pairs'][0]),
                 lambda x:x['pairs'][0]['event'].update(start_date_time='21.03.1913.53.10')]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'registry.json'
            for mutate in changes:
                obj=copy.deepcopy(original);mutate(obj);raw=json.dumps(obj).encode();path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    ClockRegistry(path,hashlib.sha256(raw).hexdigest(),inventory)
            with self.assertRaisesRegex(ValueError,'SHA256'):
                ClockRegistry(path,'0'*64,inventory)

    def test_build_isolated_copy_and_preserve_source(self):
        before = hashlib.sha256((SOURCE / 'p1_data.py').read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / 'code'
            manifest = build(SOURCE, dest)
            self.assertEqual(before, SOURCE_DATA_SHA)
            self.assertEqual(hashlib.sha256((SOURCE / 'p1_data.py').read_bytes()).hexdigest(), before)
            for row in manifest['files']:
                self.assertEqual(hashlib.sha256((dest / row['path']).read_bytes()).hexdigest(), row['sha256'])
            data = (dest / 'p1_data.py').read_text()
            self.assertIn('event_audit["clock_policy"] = validate_yang_clock', data)
            self.assertIn('event_sample = _grid(cue["onset"] * 1000', data)
            runner = (dest / 'p1_runner.py').read_text()
            self.assertIn('data/processed18_clockfix_v2_20261018', runner)
            self.assertIn('default="expansion18_clockfix_v2_20261018"', runner)
            self.assertEqual((dest / 'config/filter_bank18.json').read_bytes(), (SOURCE / 'config/filter_bank18.json').read_bytes())
            self.assertEqual((dest / 'config/study.json').read_bytes(), (SOURCE / 'config/study.json').read_bytes())
            compile(data, str(dest / 'p1_data.py'), 'exec')
            compile(runner, str(dest / 'p1_runner.py'), 'exec')
            with self.assertRaisesRegex(ValueError, 'must be new'):
                build(SOURCE, dest)

    def test_recovery_has_no_archive_or_credentials_operations(self):
        source = Path(__file__).with_name('build_reviewed_copy.py').read_text()
        self.assertNotIn('_archive/', source)
        self.assertNotIn('credentials.json', source)
        self.assertNotIn('subprocess.', source)


if __name__ == '__main__':
    unittest.main()
