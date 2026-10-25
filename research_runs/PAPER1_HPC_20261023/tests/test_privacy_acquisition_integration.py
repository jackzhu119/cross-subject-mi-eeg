"""Source-selection/acquisition integration using small synthetic native bytes."""
from contextlib import ExitStack, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zlib

from hpcmi import acquire as a, yang_nemar_download as n, yang_privacy as p


class PrivacyAcquisitionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / 'raw-versioned'
        self.yang = self.raw / 'yang'
        self.yang.mkdir(parents=True)
        (self.yang / '.source-profile.json').write_text(json.dumps(
            {'profile': p.PROFILE, 'contract_sha256': p.CONTRACT_SHA256}))
        self.vendor = self.root / 'vendor'
        (self.vendor / 'config').mkdir(parents=True)
        for dataset in ('bnci', 'dreyer'):
            old = self.root / 'raw-original' / dataset
            old.mkdir(parents=True)
            (self.raw / dataset).symlink_to(old, target_is_directory=True)
            body = ('synthetic-' + dataset).encode()
            row = {'path': 'existing.raw', 'size': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
            (old / row['path']).write_bytes(body)
            a._record(old, row, row['sha256'])
            manifest = {'dataset': dataset, 'files': [row]}
            (old / '_download_manifest.json').write_text(json.dumps(manifest))
            (self.vendor / 'config' / (dataset + '_manifest.json')).write_text(json.dumps(manifest))
        self.rows = []
        for name, body in [('data.bdf', b'synthetic signal'), ('evt.bdf', b'synthetic event'), ('README.md', b'synthetic metadata')]:
            row = {'path': 'synthetic/' + name, 'size': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
                   'original_sha256': hashlib.sha256(b'old-'+body).hexdigest() if name.endswith('.bdf') else None,
                   'original_zip_crc32': 'deadbeef'}
            if name.endswith('.md'):
                row['crc32'] = '%08x' % (zlib.crc32(body) & 0xffffffff)
            target = self.yang / row['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            a._record(self.yang, row, row['sha256'])
            self.rows.append(row)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(redirect_stdout(io.StringIO()))
        self.stack.enter_context(mock.patch.object(a, 'VENDOR', self.vendor))
        self.stack.enter_context(mock.patch.object(p, 'pins', return_value=self.rows))
        self.stack.enter_context(mock.patch.object(p, 'load_contract', return_value={
            'provider_dataset': 'nm000348', 'provider_version': 'v1.0.5'}))
        self.identity = {'profile': p.PROFILE, 'contract_sha256': p.CONTRACT_SHA256,
                         'adapter_sha256': 'a'*64}
        self.stack.enter_context(mock.patch.object(p, 'current_identity', side_effect=lambda: dict(self.identity)))

    def test_native_cached_download_and_offline_publication_reuse_linked_datasets(self):
        original = (self.raw / 'bnci' / 'existing.raw').stat()
        with mock.patch.object(n, '_source_url'), \
             mock.patch.object(a, '_open_no_redirect', side_effect=AssertionError('no network for completed inputs')), \
             mock.patch.object(a, 'sha256_file', side_effect=AssertionError('no repeated native SHA scan')):
            a.acquire_yang_transport(self.yang)
            self.assertTrue(a.network_payloads_ready(self.raw))
            self.assertTrue(a.quick_raw_ready(self.raw))
            self.assertTrue(a.publish_offline(self.raw))
        manifest = json.loads((self.yang / '_download_manifest.json').read_text())
        self.assertEqual(manifest['source_profile'], p.PROFILE)
        self.assertFalse(manifest['original_zip_crc_for_corrected_bdf_verified'])
        self.assertEqual(manifest['files'][0]['sha256'], self.rows[0]['sha256'])
        self.assertNotEqual(manifest['files'][0]['sha256'], self.rows[0]['original_sha256'])
        self.assertNotIn('crc32', manifest['files'][0])
        self.assertEqual((self.raw / 'bnci' / 'existing.raw').stat(), original)

    def test_runtime_adapter_only_update_keeps_native_manifest_identity(self):
        completed = {row['path']: row['sha256'] for row in self.rows}
        a._privacy_yang_manifest(self.yang, self.rows, completed)
        before = (self.yang / '_download_manifest.json').read_bytes()
        self.identity['adapter_sha256'] = 'b'*64
        a._privacy_yang_manifest(self.yang, self.rows, completed)
        self.assertEqual((self.yang / '_download_manifest.json').read_bytes(), before)

    def test_offline_publication_checks_small_metadata_crc_after_stat_receipt(self):
        self.rows[-1]['crc32'] = '00000000'
        with self.assertRaisesRegex(ValueError, 'metadata original CRC differs'):
            a._publish_privacy_yang_offline(self.yang)
        self.assertFalse((self.yang / '_download_manifest.json').exists())

    def test_old_ancestor_hash_or_profile_cannot_satisfy_selected_source(self):
        completed = {row['path']: row['sha256'] for row in self.rows}
        a._privacy_yang_manifest(self.yang, self.rows, completed)
        path = self.yang / '_download_manifest.json'
        manifest = json.loads(path.read_text())
        manifest['files'][0]['sha256'] = self.rows[0]['original_sha256']
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'Raw manifest pin changed'):
            a.quick_raw_ready(self.raw)
        manifest['files'][0]['sha256'] = self.rows[0]['sha256']
        manifest['source_profile'] = 'figshare_v5_original'
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'selected privacy source'):
            a.quick_raw_ready(self.raw)

    def test_progress_exposes_only_known_profile_and_typed_integrity_stage(self):
        from hpcmi.github_sync import _safe_stats
        self.assertEqual(_safe_stats({'yang_source_profile': p.PROFILE,
                                     'native_yang_validation_pending': False}),
                         {'yang_source_profile': p.PROFILE, 'native_yang_validation_pending': False})
        self.assertEqual(_safe_stats({'yang_source_profile': 'https://private.invalid/?signature=secret',
                                     'native_yang_validation_pending': 'false'}), {})


if __name__ == '__main__':
    unittest.main()
