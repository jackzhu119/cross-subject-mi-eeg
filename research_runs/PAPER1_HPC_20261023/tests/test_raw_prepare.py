import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np
from hpcmi import raw_prepare as r


class RawPreparationTests(unittest.TestCase):
    def test_new_profile_preserves_all_old_filter_coefficients_and_contract(self):
        identity = r._identity()
        old = json.loads((r.VENDOR / 'config/filter_bank18.json').read_text())
        new = json.loads(r.HPC_FILTER_BANK.read_text())
        changed = {'profile_id', 'numpy_version', 'scipy_version', 'parent_profile_sha256', 'runtime_amendment'}
        self.assertEqual({k: v for k, v in old.items() if k not in changed},
                         {k: v for k, v in new.items() if k not in changed})
        self.assertEqual(identity['numpy'], '2.2.6')
        self.assertEqual(identity['scipy'], '1.15.3')
        self.assertEqual(old['numpy_version'], '2.3.5')
        self.assertEqual(old['scipy_version'], '1.17.0')

    def test_synthetic_native_three_rates_forward_shape_scale_and_center(self):
        bank = r.p1_data.load_filter_bank(r.HPC_FILTER_BANK)
        rng = np.random.default_rng(1023)
        for rate in (250, 512, 1000):
            context = rng.normal(size=(18, 6 * rate))
            x, audit = r.p1_data.transform_native_context(context, rate, bank, return_audit=True)
            scaled = r.p1_data.transform_native_context(context * 2, rate, bank)
            self.assertEqual(x.shape, (3, 18, 320))
            self.assertEqual(x.dtype, np.float32)
            self.assertTrue(np.isfinite(x).all())
            self.assertFalse(audit['trial_normalization_uses_other_trials'])
            np.testing.assert_allclose(x.mean(axis=-1), 0, atol=1e-7)
            self.assertAlmostEqual(float(np.sqrt(np.mean(x[0] ** 2))), 1.0, places=6)
            np.testing.assert_array_equal(x, scaled)

    def test_person_receipts_skip_completed_preprocessing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            raw, cache, out = base/'raw', base/'cache', base/'data'
            for name in ('bnci', 'yang', 'dreyer'):
                (raw/name).mkdir(parents=True)
                (raw/name/'_download_manifest.json').write_text('{}')
            def build(dataset, person, source, path, **kwargs):
                self.assertEqual(kwargs['filter_bank_json'], r.HPC_FILTER_BANK)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'synthetic-published-cache')
            audit = {'X_sha256': 'test-array', 'numpy_version': '2.2.6', 'scipy_version': '1.15.3'}
            with mock.patch.object(r, 'quick_raw_ready', return_value=True), \
                 mock.patch.object(r.p1_data, 'roster', return_value=[1]), \
                 mock.patch.object(r, '_raw_stats', return_value={'file': {'bytes': 4, 'mtime_ns': 1}}), \
                 mock.patch.object(r.p1_data, 'verify_subject_npz', return_value=audit), \
                 mock.patch.object(r, 'prepare', return_value={'fingerprint': 'synthetic'}):
                with mock.patch.object(r.p1_data, 'build_subject_npz', side_effect=build) as run:
                    r.raw_prepare(raw, cache, out)
                    self.assertEqual(run.call_count, 3)
                with mock.patch.object(r.p1_data, 'build_subject_npz', side_effect=AssertionError('repeat')):
                    r.raw_prepare(raw, cache, out)
                self.assertEqual(len(list(cache.glob('*/*.hpc-preparation.json'))), 3)


if __name__ == '__main__':
    unittest.main()
