import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_reviewed_copy import build, SOURCE_DATA_SHA
from yang_clock_policy import validate_yang_clock, SIGNAL_SHA256, EVENT_SHA256

SOURCE = Path(__file__).resolve().parents[1] / 'SOURCE_EXPANSION_20261017'


class RecoveryTests(unittest.TestCase):
    def test_equal_clocks_preserve_previous_policy(self):
        self.assertEqual(validate_yang_clock('same', 'same', 'x', 'y')['event_shift_seconds'], 0)

    def test_verified_pair_keeps_TAL_position(self):
        audit = validate_yang_clock('22.03.1915.03.13', '22.03.1915.03.12', SIGNAL_SHA256, EVENT_SHA256)
        self.assertEqual(audit['event_shift_seconds'], 0)
        self.assertEqual(round((166.634 + audit['event_shift_seconds']) * 1000), 166634)
        self.assertEqual(round((2151.278 + audit['event_shift_seconds']) * 1000), 2151278)

    def test_unreviewed_pair_or_different_clock_rejected(self):
        expected = ['22.03.1915.03.13', '22.03.1915.03.12', SIGNAL_SHA256, EVENT_SHA256]
        for i in range(4):
            args = expected.copy()
            args[i] = 'unreviewed'
            with self.subTest(field=i), self.assertRaisesRegex(ValueError, 'unreviewed'):
                validate_yang_clock(*args)

    def test_other_one_second_difference_rejected(self):
        with self.assertRaises(ValueError):
            validate_yang_clock('23.03.1915.03.13', '23.03.1915.03.12', SIGNAL_SHA256, EVENT_SHA256)

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
            self.assertIn('data/processed18_clockfix_20261018', runner)
            self.assertIn('default="expansion18_clockfix_20261018"', runner)
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
