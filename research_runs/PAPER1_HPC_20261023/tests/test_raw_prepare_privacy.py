"""Offline orchestration with tiny byte stubs; no EEG processing or model fits."""
from contextlib import ExitStack, contextmanager, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from hpcmi import raw_prepare as r


class RawPreparationPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.raw, self.cache, self.out = self.base/'raw', self.base/'cache', self.base/'data'
        self.base_identity = {'code': {'frozen': 'unchanged'}, 'numpy': '2.2.6', 'scipy': '1.15.3'}
        self.descriptor = r.yang_privacy.current_identity()
        self.semantic_descriptor = {k: v for k, v in self.descriptor.items() if k != 'adapter_sha256'}
        self.context_active = False
        self.context_calls, self.build_calls, self.verify_calls = [], [], []
        self.fail_event = False
        self.audit_by_payload = {}
        for dataset in ('bnci', 'yang', 'dreyer'):
            folder = self.raw/dataset
            folder.mkdir(parents=True)
            if dataset == 'bnci':
                names = ['A01T.mat', 'A01E.mat']
            elif dataset == 'yang':
                names = [f'WBCIC_SHU Motor Imagery dataset/sourcedata/2C dataset/sub-001/ses-{s:02d}/eeg/{name}'
                         for s in range(1, 4) for name in ('data.bdf', 'evt.bdf')]
            else:
                names = ['sourcedata/sub-01/eeg/run-1.edf', 'sourcedata/sub-01/eeg/run-2.edf']
            rows = []
            for name in names:
                path = folder/name
                path.parent.mkdir(parents=True, exist_ok=True)
                body = ('stub-'+dataset).encode()
                path.write_bytes(body)
                rows.append({'path': name, 'size': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
            (folder/'_download_manifest.json').write_text(json.dumps({'files': rows}))
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(redirect_stdout(io.StringIO()))
        self.identity = self.stack.enter_context(mock.patch.object(r, '_identity', return_value=self.base_identity))
        self.ready = self.stack.enter_context(mock.patch.object(r, 'quick_raw_ready', return_value=True))
        self.stack.enter_context(mock.patch.object(r.p1_data, 'roster', return_value=[1]))
        self.profile_identity = self.stack.enter_context(mock.patch.object(r.yang_privacy, 'current_identity', return_value=self.descriptor))
        self.policy = self.stack.enter_context(mock.patch.object(r.yang_privacy, 'policy_context', side_effect=self.context))
        self.builder = self.stack.enter_context(mock.patch.object(r.p1_data, 'build_subject_npz', side_effect=self.build))
        self.verifier = self.stack.enter_context(mock.patch.object(r.p1_data, 'verify_subject_npz', side_effect=self.verify))
        self.preparer = self.stack.enter_context(mock.patch.object(r, 'prepare', side_effect=lambda *args: {'fingerprint': 'stub-fingerprint'}))

    @contextmanager
    def context(self, module):
        self.assertIs(module, r.p1_data)
        self.assertFalse(self.context_active)
        self.context_active = True
        self.context_calls.append('enter')
        try:
            yield self.descriptor
        finally:
            self.context_active = False
            self.context_calls.append('exit')

    def activate(self):
        (self.raw/'yang/.source-profile.json').write_text(json.dumps({'profile': r.yang_privacy.PROFILE}))
        path = self.raw/'yang/_download_manifest.json'
        obj = json.loads(path.read_text())
        obj['input_source_profile'] = r.yang_privacy.PROFILE
        path.write_text(json.dumps(obj))

    def build(self, dataset, person, source, path, **kwargs):
        self.build_calls.append((dataset, path))
        self.assertEqual(kwargs['filter_bank_json'], r.HPC_FILTER_BANK)
        if dataset == 'yang':
            active = (self.raw/'yang/.source-profile.json').exists()
            self.assertEqual(self.context_active, active)
            if self.fail_event:
                raise ValueError('Native event sequence changed')
        else:
            self.assertFalse(self.context_active)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = (dataset+'-'+str(len(self.build_calls))).encode()
        path.write_bytes(payload)
        self.audit_by_payload[payload] = {
            'X_sha256': 'stub-array-'+dataset, 'numpy_version': r.np.__version__,
            'scipy_version': r.scipy.__version__,
            'downloader_manifest_sha256': r._file_sha(source/'_download_manifest.json')}

    def verify(self, path, **kwargs):
        self.verify_calls.append(path)
        is_new_yang = path.parent.name == 'yang-nemar-privacy-v1'
        self.assertEqual(self.context_active, is_new_yang)
        return self.audit_by_payload[path.read_bytes()].copy()

    def run_prepare(self):
        return r.raw_prepare(self.raw, self.cache, self.out)

    def test_default_source_keeps_original_paths_identity_and_zero_new_policy_calls(self):
        result = self.run_prepare()
        self.assertNotIn('input_source_profiles', result)
        self.assertEqual([p.parent.name for _, p in self.build_calls], ['bnci', 'yang', 'dreyer'])
        self.policy.assert_not_called()
        self.profile_identity.assert_not_called()
        self.assertTrue((self.cache/'input_sources.json').is_file())
        for name in ('bnci', 'yang', 'dreyer'):
            receipt = json.loads((self.cache/name/'sub-001.hpc-preparation.json').read_text())
            self.assertEqual(receipt['identity'], self.base_identity)
        self.builder.reset_mock()
        self.run_prepare()
        self.builder.assert_not_called()

    def test_active_profile_only_builds_new_yang_and_reuses_bnci_dreyer_byte_for_byte(self):
        self.run_prepare()
        old_files = {path: path.read_bytes() for name in ('bnci', 'yang', 'dreyer') for path in (self.cache/name).iterdir()}
        old_sources = (self.cache/'input_sources.json').read_bytes()
        self.activate()
        self.build_calls.clear()
        result = self.run_prepare()
        self.assertEqual([d for d, _ in self.build_calls], ['yang'])
        self.assertEqual(self.context_calls, ['enter', 'exit'])
        self.assertEqual(result['input_source_profiles'], {'yang': self.semantic_descriptor})
        self.assertEqual((self.cache/'input_sources.json').read_bytes(), old_sources)
        for path, before in old_files.items():
            self.assertEqual(path.read_bytes(), before)
        new_receipt = json.loads((self.cache/'yang-nemar-privacy-v1/sub-001.hpc-preparation.json').read_text())
        self.assertEqual(new_receipt['identity'], {**self.base_identity, 'input_source_profile': self.semantic_descriptor})
        sources = json.loads((self.cache/'input_sources-nemar-privacy-v1.json').read_text())
        self.assertEqual(sources['input_source_profiles'], {'yang': self.semantic_descriptor})
        groups = {row['dataset']: row for row in sources['datasets']}
        self.assertEqual(groups['yang']['directory'], str(self.cache/'yang-nemar-privacy-v1'))
        self.assertEqual((groups['yang']['expected_subjects'], groups['yang']['expected_trials']), (51, 30591))
        self.assertEqual(groups['bnci']['directory'], str(self.cache/'bnci'))
        self.assertEqual(groups['dreyer']['directory'], str(self.cache/'dreyer'))
        self.assertEqual(json.loads((self.out/'manifest.json').read_text())['input_source_profiles'], {'yang': self.semantic_descriptor})
        self.builder.reset_mock()
        self.run_prepare()
        self.builder.assert_not_called()

    def test_adapter_implementation_change_preserves_semantic_identity_and_cached_inputs(self):
        self.activate()
        first = self.run_prepare()
        sources = self.cache/'input_sources-nemar-privacy-v1.json'
        source_bytes = sources.read_bytes()
        self.assertNotIn('adapter_sha256', json.loads(source_bytes)['input_source_profiles']['yang'])
        receipt_path = self.cache/'yang-nemar-privacy-v1/sub-001.hpc-preparation.json'
        receipt = json.loads(receipt_path.read_text())
        # A receipt written by the earlier adapter is accepted semantically and
        # retained verbatim; its recorded implementation identity is evidence.
        receipt['identity']['input_source_profile']['adapter_sha256'] = self.descriptor['adapter_sha256']
        receipt_path.write_text(json.dumps(receipt))
        retained = receipt_path.read_bytes()
        next_adapter_sha = 'e' * 64
        self.profile_identity.return_value = {**self.descriptor, 'adapter_sha256': next_adapter_sha}
        self.builder.reset_mock()
        result = self.run_prepare()
        self.builder.assert_not_called()
        self.assertEqual(receipt_path.read_bytes(), retained)
        self.assertEqual(sources.read_bytes(), source_bytes)
        self.assertEqual(result['fingerprint'], first['fingerprint'])
        self.assertEqual(result['input_source_profiles'], first['input_source_profiles'])
        self.assertEqual(result['execution_evidence']['yang_privacy_adapter_sha256'], next_adapter_sha)
        # Excluding an implementation digest never excludes scientific identity.
        self.profile_identity.return_value = {**self.descriptor, 'contract_sha256': 'f' * 64}
        with self.assertRaisesRegex(ValueError, 'input/runtime/output changed'):
            self.run_prepare()

    def test_old_yang_receipt_cannot_be_used_as_new_version(self):
        self.run_prepare()
        self.activate()
        folder = self.cache/'yang-nemar-privacy-v1'
        folder.mkdir()
        for suffix in ('.npz', '.hpc-preparation.json'):
            shutil.copy2(self.cache/'yang'/('sub-001'+suffix), folder/('sub-001'+suffix))
        retained = {path: path.read_bytes() for path in folder.iterdir()}
        with self.assertRaisesRegex(ValueError, 'input/runtime/output changed'):
            self.run_prepare()
        for path, before in retained.items():
            self.assertEqual(path.read_bytes(), before)
        self.assertFalse(self.context_active)

    def test_unreceipted_old_yang_array_is_rejected_by_real_source_manifest_identity(self):
        self.run_prepare()
        self.activate()
        folder = self.cache/'yang-nemar-privacy-v1'
        folder.mkdir()
        target = folder/'sub-001.npz'
        shutil.copy2(self.cache/'yang/sub-001.npz', target)
        before = target.read_bytes()
        with self.assertRaisesRegex(ValueError, 'different inputs/runtime'):
            self.run_prepare()
        self.assertEqual(target.read_bytes(), before)
        self.assertFalse(target.with_suffix('.hpc-preparation.json').exists())
        self.assertFalse(self.context_active)

    def test_native_event_error_propagates_and_restores_policy_without_publishing_receipt(self):
        self.activate()
        self.fail_event = True
        with self.assertRaisesRegex(ValueError, 'Native event sequence changed'):
            self.run_prepare()
        self.assertFalse(self.context_active)
        self.assertEqual(self.context_calls, ['enter', 'exit'])
        self.assertFalse((self.cache/'yang-nemar-privacy-v1/sub-001.hpc-preparation.json').exists())
        self.preparer.assert_not_called()


if __name__ == '__main__':
    unittest.main()
