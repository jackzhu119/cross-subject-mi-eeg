"""Exploratory access gates/transport software tests; never download in tests."""
import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('exploratory_access', ROOT / 'scripts/acquire_exposure_unconfirmed.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def record():
    return {'status': 'AUTHOR_REPORTED_UNCERTAIN', 'dataset': 'Dreyer2023',
            'provider_dataset_id': 'nm000250', 'provider_manifest_sha256': MODULE.MANIFEST_SHA,
            'prior_proposed_decoder_results_inspected_or_used': None,
            'prior_dataset_scientific_analysis_performed': None,
            'used_in_other_manuscripts_or_projects': None, 'independent_confirmation_qualified': False,
            'author_name': 'Ziyuan Zhu', 'confirmation_record': '不确定，可以批准GPU预算',
            'reported_at_utc': datetime.now(timezone.utc).isoformat()}


class ExposureAccessTests(unittest.TestCase):
    def declaration(self, value):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / 'author.json'
        path.write_text(json.dumps(value, ensure_ascii=False))
        return path

    def test_fixed_manifest_plan_retains_174_files_87_persons_unknown_exposure(self):
        rows, plan = MODULE.verified_plan()
        self.assertEqual(len(rows), 174)
        self.assertEqual(sum(r['size'] for r in rows), 2515343396)
        self.assertEqual(len({r['path'].split('/')[1] for r in rows}), 87)
        self.assertEqual(plan['metadata_excluded_subjects_primary'], [17, 41])
        self.assertEqual(plan['canonical19_order'], MODULE.COMMON19)
        self.assertEqual(plan['evidence_class'], MODULE.CLASS)
        self.assertFalse(plan['independent_confirmation_qualified'])
        self.assertFalse(plan['model_training_enabled'])
        self.assertFalse(plan['model_inference_enabled'])

    def test_actual_unknown_record_stays_unknown_not_no_prior_use(self):
        receipt = MODULE.author_uncertainty_gate(self.declaration(record()))
        self.assertEqual(receipt['prior_use_fact'], 'unknown')
        self.assertFalse(receipt['independent_confirmation_qualified'])

    def test_prior_false_or_true_cannot_substitute_uncertainty(self):
        for wrong in [False, True, 0, '', 'unknown']:
            data = record()
            data['prior_proposed_decoder_results_inspected_or_used'] = wrong
            with self.assertRaisesRegex(ValueError, 'uncertainty_record_mismatch'):
                MODULE.author_uncertainty_gate(self.declaration(data))

    def test_missing_fact_not_accepted_as_null(self):
        data = record()
        del data['prior_dataset_scientific_analysis_performed']
        with self.assertRaisesRegex(ValueError, 'field_missing'):
            MODULE.author_uncertainty_gate(self.declaration(data))

    def test_false_status_or_prior_template_is_rejected(self):
        data = record()
        data['status'] = 'AUTHOR_CONFIRMED'
        with self.assertRaisesRegex(ValueError, 'status'):
            MODULE.author_uncertainty_gate(self.declaration(data))

    def test_qualification_boolean_cannot_be_zero(self):
        data = record()
        data['independent_confirmation_qualified'] = 0
        with self.assertRaisesRegex(ValueError, 'independent_confirmation'):
            MODULE.author_uncertainty_gate(self.declaration(data))

    def test_missing_literal_actual_reply_is_rejected(self):
        data = record()
        data['confirmation_record'] = 'Agent infers no prior exposure.'
        with self.assertRaisesRegex(ValueError, 'actual_uncertainty'):
            MODULE.author_uncertainty_gate(self.declaration(data))

    def test_timestamp_without_timezone_rejected(self):
        data = record()
        data['reported_at_utc'] = '2026-10-13T09:00:00'
        with self.assertRaisesRegex(ValueError, 'timestamp'):
            MODULE.author_uncertainty_gate(self.declaration(data))

    def test_missing_author_record_rejected(self):
        with self.assertRaisesRegex(ValueError, 'missing'):
            MODULE.author_uncertainty_gate(None)

    def test_registration_requires_full_sha_before_git_or_network(self):
        with mock.patch.object(MODULE.subprocess, 'run', side_effect=AssertionError('No git')):
            with self.assertRaisesRegex(ValueError, 'full_registration'):
                MODULE.registration_gate('abc')

    def test_registration_git_bytes_mismatch_blocks_before_public_get(self):
        result = mock.Mock(returncode=0, stdout=b'wrong bytes')
        with mock.patch.object(MODULE.subprocess, 'run', return_value=result), \
             mock.patch.object(MODULE, 'read_public', side_effect=AssertionError('No public get')):
            with self.assertRaisesRegex(ValueError, 'local_bytes_differ'):
                MODULE.registration_gate('a' * 40)

    def test_registration_missing_git_object_blocks(self):
        result = mock.Mock(returncode=128, stdout=b'')
        with mock.patch.object(MODULE.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(ValueError, 'local_bytes_differ'):
                MODULE.registration_gate('b' * 40)

    def test_registration_public_bytes_mismatch_blocks_before_raw_get(self):
        with mock.patch.object(MODULE.subprocess, 'run', return_value=mock.Mock(returncode=0, stdout=MODULE.PLAN_PATH.read_bytes())), \
             mock.patch.object(MODULE, 'read_public', return_value=b'changed'):
            with self.assertRaisesRegex(ValueError, 'public_bytes_differ'):
                MODULE.registration_gate('a' * 40)

    def test_registration_real_reads_all_fixed_paths_and_retains_nonconfirmatory(self):
        paths = [MODULE.PLAN_PATH, Path(MODULE.__file__).resolve(), self.declaration(record()), MODULE.MANIFEST_PATH] + [MODULE.PREVIOUS / p for p in MODULE.PINNED_HELPERS]
        # A temporary author file outside the repo is deliberately not accepted;
        # positive fixture uses another registered file to exercise exact bytes.
        paths[2] = MODULE.PLAN_PATH
        data = iter([p.read_bytes() for p in paths])
        public = iter([p.read_bytes() for p in paths])
        with mock.patch.object(MODULE, 'registration_files', return_value=paths), \
             mock.patch.object(MODULE.subprocess, 'run', side_effect=lambda *a, **k: mock.Mock(returncode=0, stdout=next(data))), \
             mock.patch.object(MODULE, 'read_public', side_effect=lambda *a, **k: next(public)):
            receipt = MODULE.registration_gate('c' * 40)
        self.assertEqual(len(receipt['files']), 6)
        self.assertFalse(receipt['independent_confirmation_qualified'])
        self.assertFalse(receipt['target_inference_authorized'])
        self.assertTrue(all(f['public_http_200_readback_identical'] for f in receipt['files']))

    def test_default_cli_no_network_no_raw_access(self):
        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch.object(MODULE, 'perform', side_effect=AssertionError('No raw access')), \
             mock.patch.object(MODULE, 'read_public', side_effect=AssertionError('No network')), \
             contextlib.redirect_stdout(io.StringIO()):
            path = Path(temporary) / 'dry.json'
            self.assertEqual(MODULE.main(['--receipt', str(path)]), 0)
            receipt = json.loads(path.read_text())
        self.assertEqual(receipt['raw_bytes_downloaded_now'], 0)
        self.assertEqual(receipt['files'], [])
        self.assertFalse(receipt['independent_confirmation_qualified'])
        self.assertFalse(receipt['paid_resources_started'])

    def test_explicit_download_without_valid_uncertainty_never_transports(self):
        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch.object(MODULE, 'perform', side_effect=AssertionError('No raw access')), \
             mock.patch.object(MODULE, 'read_public', side_effect=AssertionError('No network')), \
             contextlib.redirect_stdout(io.StringIO()):
            path = Path(temporary) / 'blocked.json'
            code = MODULE.main(['--download', '--author-uncertainty-record', str(Path(temporary) / 'missing.json'), '--receipt', str(path)])
            receipt = json.loads(path.read_text())
        self.assertEqual(code, 1)
        self.assertEqual(receipt['raw_bytes_downloaded_now'], 0)
        self.assertFalse(receipt['model_training_authorized'])

    def test_old_published_helpers_sha_changes_rejected(self):
        with mock.patch.object(MODULE, 'sha_file', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'published_helper'):
                MODULE.import_previous('scripts/check_dreyer_metadata.py', 'bad')

    def test_modified_plan_unknown_class_or_model_flag_rejected(self):
        for field, bad in [('evidence_class', 'CONFIRMATORY'), ('independent_confirmation_qualified', True),
                           ('model_training_enabled', True), ('model_inference_enabled', 0), ('maximum_download_workers', 4)]:
            plan = json.loads(MODULE.PLAN_PATH.read_text())
            plan[field] = bad
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / 'modified.json'
                path.write_text(json.dumps(plan))
                with self.assertRaises(ValueError):
                    MODULE.verified_plan(path)

    def test_corrupt_final_cache_not_overwritten_and_no_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / 'cache'
            pilot = Path(temporary) / 'pilot'
            row = {'path': 'test.edf', 'size': 3, 'checksum': hashlib.sha256(b'abc').hexdigest(), 'bytes_url': 'https://data.nemar.org/test'}
            cache.mkdir()
            path = cache / row['path']
            path.write_bytes(b'bad')
            with mock.patch.object(MODULE.urllib.request, 'urlopen', side_effect=AssertionError('No network')):
                with self.assertRaisesRegex(ValueError, 'sha256_mismatch'):
                    MODULE.ensure_raw(row, cache, pilot)
            self.assertEqual(path.read_bytes(), b'bad')

    def test_verified_cache_reused_no_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / 'cache'
            cache.mkdir()
            row = {'path': 'test.edf', 'size': 3, 'checksum': hashlib.sha256(b'abc').hexdigest()}
            (cache / row['path']).write_bytes(b'abc')
            with mock.patch.object(MODULE.urllib.request, 'urlopen', side_effect=AssertionError('No network')):
                transfer = MODULE.ensure_raw(row, cache, Path(temporary) / 'pilot')
            self.assertEqual(transfer['downloaded_now'], 0)
            self.assertEqual(transfer['status'], 'verified_full_cohort_cache_reused')

    def test_pilot_verified_copy_preserves_old_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / 'cache'
            pilot = Path(temporary) / 'pilot'
            pilot.mkdir()
            row = {'path': 'test.edf', 'size': 3, 'checksum': hashlib.sha256(b'abc').hexdigest()}
            source = pilot / row['path']
            source.write_bytes(b'abc')
            with mock.patch.object(MODULE.urllib.request, 'urlopen', side_effect=AssertionError('No network')):
                transfer = MODULE.ensure_raw(row, cache, pilot)
            self.assertEqual(transfer['downloaded_now'], 0)
            self.assertEqual(source.read_bytes(), b'abc')
            self.assertEqual(transfer['path'].read_bytes(), b'abc')

    def test_symlink_cache_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'cache.edf'
            source = Path(temporary) / 'source.edf'
            source.write_bytes(b'abc')
            path.symlink_to(source)
            row = {'path': 'test.edf', 'size': 3, 'checksum': hashlib.sha256(b'abc').hexdigest()}
            with self.assertRaisesRegex(ValueError, 'symlink'):
                MODULE.verified_file(row, path)

    def simulated_transfer(self, payload, expected=b'abc'):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        cache = Path(temporary.name) / 'cache'
        pilot = Path(temporary.name) / 'pilot'
        row = {'path': 'test.edf', 'size': len(expected),
               'checksum': hashlib.sha256(expected).hexdigest(),
               'bytes_url': 'https://data.nemar.org/pinned/test.edf'}
        stream = io.BytesIO(payload)
        stream.status = 200
        return cache, pilot, row, stream

    def test_successful_download_full_hash_verified_before_final_cache(self):
        cache, pilot, row, stream = self.simulated_transfer(b'abc')
        with mock.patch.object(MODULE.urllib.request, 'urlopen', return_value=stream):
            transfer = MODULE.ensure_raw(row, cache, pilot)
        self.assertEqual(transfer['downloaded_now'], 3)
        self.assertEqual(transfer['path'].read_bytes(), b'abc')
        self.assertEqual(list(cache.glob('*.failed')), [])

    def test_truncated_transfer_retains_failed_bytes_without_final_cache(self):
        cache, pilot, row, stream = self.simulated_transfer(b'ab')
        with mock.patch.object(MODULE.urllib.request, 'urlopen', return_value=stream):
            with self.assertRaisesRegex(ValueError, 'size_or_sha256_mismatch'):
                MODULE.ensure_raw(row, cache, pilot)
        self.assertFalse((cache / row['path']).exists())
        self.assertEqual([p.read_bytes() for p in cache.glob('*.failed')], [b'ab'])

    def test_wrong_sha_transfer_retains_failed_bytes_without_final_cache(self):
        cache, pilot, row, stream = self.simulated_transfer(b'bad')
        with mock.patch.object(MODULE.urllib.request, 'urlopen', return_value=stream):
            with self.assertRaisesRegex(ValueError, 'size_or_sha256_mismatch'):
                MODULE.ensure_raw(row, cache, pilot)
        self.assertFalse((cache / row['path']).exists())
        self.assertEqual([p.read_bytes() for p in cache.glob('*.failed')], [b'bad'])

    def test_oversized_transfer_rejected_before_final_cache_and_archived(self):
        cache, pilot, row, stream = self.simulated_transfer(b'abcdef')
        with mock.patch.object(MODULE.urllib.request, 'urlopen', return_value=stream):
            with self.assertRaisesRegex(ValueError, 'exceeds_fixed_manifest'):
                MODULE.ensure_raw(row, cache, pilot)
        self.assertFalse((cache / row['path']).exists())
        self.assertEqual(len(list(cache.glob('*.failed'))), 1)

    def test_existing_cache_lock_prevents_any_transport(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            lock = cache / '.exploratory_acquisition.lock'
            lock.write_text('Existing worker')
            args = mock.Mock(cache_dir=cache)
            with mock.patch.object(MODULE, 'perform_unlocked', side_effect=AssertionError('No transport')):
                with self.assertRaisesRegex(ValueError, 'lock_exists'):
                    MODULE.perform([], args, {})
            self.assertEqual(lock.read_text(), 'Existing worker')

    def test_acquisition_lock_cleared_after_transport_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            args = mock.Mock(cache_dir=cache)
            with mock.patch.object(MODULE, 'perform_unlocked', side_effect=ValueError('expected failure')):
                with self.assertRaisesRegex(ValueError, 'expected failure'):
                    MODULE.perform([], args, {})
            self.assertFalse((cache / '.exploratory_acquisition.lock').exists())

    def test_real_pilot_header_audit_is_not_full_signal_qc_or_confirmation(self):
        rows, _ = MODULE.verified_plan()
        row = rows[0]
        path = MODULE.DEFAULT_PILOT / row['path']
        if not path.is_file():
            self.skipTest('Raw pilot absent; do not download in tests')
        parser = MODULE.import_previous('scripts/check_dreyer_metadata.py', 'real_test_parser')
        receipt = MODULE.audit_one(row, path, parser)
        self.assertEqual(receipt['cue_counts'], {'769': 20, '770': 20})
        self.assertFalse(receipt['signal_only_qc_complete'])
        self.assertFalse(receipt['independent_confirmation_qualified'])
        self.assertFalse(receipt['original_gdf_equivalence_verified'])
        self.assertEqual(receipt['evidence_class'], MODULE.CLASS)


if __name__ == '__main__':
    unittest.main(verbosity=2)
