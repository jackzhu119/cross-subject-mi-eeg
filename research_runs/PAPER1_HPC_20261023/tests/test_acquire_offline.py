"""Synthetic split-transfer tests: no real EEG, network, training or installation."""
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import errno
import socket
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from hpcmi import acquire as a


class SplitAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / 'raw'
        self.vendor = self.root / 'vendor'
        (self.vendor / 'config').mkdir(parents=True)
        self.raw.mkdir()
        self.output = io.StringIO()
        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(contextlib.redirect_stdout(self.output))
        self.patches.enter_context(mock.patch.object(a, 'VENDOR', self.vendor))
        self.bodies = {
            'dataset/sub-001/data.bdf': bytes(range(256)) * 100,
            'dataset/sub-001/evt.bdf': b'synthetic event bytes' * 20,
            'dataset/README.md': b'synthetic public metadata only',
        }
        source = io.BytesIO()
        with zipfile.ZipFile(source, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, body in self.bodies.items():
                archive.writestr(name, body)
        self.archive_bytes = source.getvalue()
        with zipfile.ZipFile(io.BytesIO(self.archive_bytes)) as archive:
            self.infos = archive.infolist()
            directory_offset = archive.start_dir
        self.rows = []
        for info in self.infos:
            row = {**a.member_record(info), 'size': info.file_size}
            if info.filename.endswith('.bdf'):
                row['sha256'] = hashlib.sha256(self.bodies[info.filename]).hexdigest()
            self.rows.append(row)
        self.inventory = {
            'archive_url': 'https://official.example/synthetic.zip',
            'archive_bytes': len(self.archive_bytes),
            'central_directory_offset': directory_offset,
            'central_directory_bytes': len(self.archive_bytes) - 22 - directory_offset,
            'central_directory_sha256': hashlib.sha256(self.archive_bytes[directory_offset:-22]).hexdigest(),
            'member_count': len(self.rows), 'eocd_offset': len(self.archive_bytes) - 22,
        }
        self.patches.enter_context(mock.patch.object(a, 'yang_pins', side_effect=lambda: (self.inventory, self.rows)))
        # Native BNCI/Dreyer fixtures already have actual verified bytes and receipts.
        for dataset, count in [('bnci', 18), ('dreyer', 174)]:
            folder = self.raw / dataset
            folder.mkdir()
            files = []
            for number in range(count):
                body = ('synthetic-' + dataset + '-' + str(number)).encode()
                row = {'path': 'file-%03d.raw' % number, 'size': len(body),
                       'sha256': hashlib.sha256(body).hexdigest(),
                       'url': 'https://official.example/' + dataset + '/' + str(number)}
                (folder / row['path']).write_bytes(body)
                a._record(folder, row, row['sha256'])
                files.append(row)
            manifest = {'files': files, 'dataset': dataset}
            (self.vendor / 'config' / (dataset + '_manifest.json')).write_text(json.dumps(manifest))
            (folder / '_download_manifest.json').write_text(json.dumps(manifest))

    def archive(self):
        return (io.BytesIO(self.archive_bytes), zipfile.ZipFile(io.BytesIO(self.archive_bytes)),
                dict(self.inventory), b'synthetic directory')

    def transport(self):
        with mock.patch.object(a, 'open_yang_archive', side_effect=self.archive), \
             mock.patch.object(a, 'selected_yang_members', side_effect=lambda archive: archive.infolist()), \
             mock.patch.object(a, '_open_no_redirect', side_effect=AssertionError('native network should be cached')), \
             mock.patch.object(a.zlib, 'decompressobj', side_effect=AssertionError('login must not decompress')):
            self.assertEqual(a.main(['--raw-dir', str(self.raw), '--transport-only']), 0)

    def test_failure_receipt_binds_attempt_and_redacts_secret_context(self):
        attempt = '0123456789abcdef0123456789abcdef'
        private = 'https://PRIVATE_USER:PRIVATE_PASSWORD@proxy.invalid/?signature=PRIVATE'
        dns = a.urllib.error.URLError(socket.gaierror(socket.EAI_NONAME, private))
        failure = RuntimeError(private)
        failure.__cause__ = dns
        path = a.record_transport_failure(failure, ['--raw-dir', str(self.raw), '--transport-only'],
                                          {'PAPER1_TRANSFER_ATTEMPT': attempt})
        self.assertEqual(path, self.raw / '.transport-failures' / (attempt + '.json'))
        data = path.read_bytes()
        report = json.loads(data)
        self.assertEqual(report['attempt_id'], attempt)
        self.assertEqual(report['category'], 'dns')
        self.assertEqual(report['errno'], socket.EAI_NONAME)
        self.assertNotIn('PRIVATE', data.decode())
        self.assertNotIn('proxy.invalid', data.decode())
        self.assertNotIn('https://', data.decode())
        self.assertEqual(a.record_transport_failure(ValueError('hash mismatch'),
            ['--raw-dir=' + str(self.raw)], {'PAPER1_TRANSFER_ATTEMPT': attempt}), path)
        self.assertEqual(path.read_bytes(), data)

    def test_actual_cli_exception_wrapper_saves_attempt_receipt_without_network(self):
        empty = self.root / 'empty-offline-raw'
        attempt = 'a' * 32
        env = {**os.environ, 'PAPER1_TRANSFER_ATTEMPT': attempt}
        result = subprocess.run([sys.executable, '-u', '-m', 'hpcmi.acquire',
            '--raw-dir', str(empty), '--offline-publish'],
            cwd=Path(a.__file__).resolve().parents[1], env=env,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        self.assertEqual(result.returncode, 1)
        report = json.loads((empty / '.transport-failures' / (attempt + '.json')).read_text())
        self.assertEqual(report['attempt_id'], attempt)
        self.assertEqual(report['error_class'], 'ValueError')
        self.assertEqual(report['category'], 'unknown')
        self.assertIn('Native dataset transport incomplete', result.stderr)

    def test_failure_receipt_invalid_attempt_is_ignored_and_disk_is_not_network(self):
        self.assertIsNone(a.record_transport_failure(OSError(errno.ENOSPC, 'PRIVATE path'),
            ['--raw-dir', str(self.raw)], {'PAPER1_TRANSFER_ATTEMPT': '../bad'}))
        self.assertFalse((self.raw / '.transport-failures').exists())
        path = a.record_transport_failure(OSError(errno.ENOSPC, 'PRIVATE path'),
            ['--raw-dir', str(self.raw)], {'PAPER1_TRANSFER_ATTEMPT': 'f' * 32})
        report = json.loads(path.read_text())
        self.assertEqual(report['category'], 'os_error')
        self.assertEqual(report['errno'], errno.ENOSPC)
        self.assertNotIn('PRIVATE', path.read_text())
        self.assertIsNone(a.record_transport_failure(ValueError('hash mismatch'),
            [], {'PAPER1_TRANSFER_ATTEMPT': 'e' * 32}))

    def test_transport_resumes_compressed_bytes_without_decompression_or_native_claim(self):
        first = self.rows[0]
        info = self.infos[0]
        target = self.raw / 'yang' / first['path']
        target.parent.mkdir(parents=True)
        data_offset = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
        compressed = target.with_name(target.name + '.compressed.part')
        compressed.write_bytes(self.archive_bytes[data_offset:data_offset + 8])
        self.transport()
        self.assertFalse(target.exists())
        self.assertFalse(a.quick_raw_ready(self.raw))
        with mock.patch.object(a, 'sha256_file', side_effect=AssertionError('readiness must not rehash')):
            self.assertTrue(a.network_payloads_ready(self.raw))
        receipt = json.loads(a._transport_receipt(self.raw / 'yang', first).read_text())
        self.assertEqual(receipt['compressed_stat'], a.stat_identity(compressed))
        self.assertFalse(receipt['native_sha256_verified'])
        self.assertEqual(receipt['pin']['sha256'], first['sha256'])
        status = json.loads((self.raw / 'network_payloads_ready.json').read_text())
        self.assertEqual(status['status'], 'NETWORK_PAYLOADS_COMPLETE_NATIVE_YANG_VALIDATION_PENDING')
        self.assertFalse(status['yang_decompressed_in_this_transport'])
        self.assertEqual(json.loads((self.raw / 'transport_status.json').read_text())['completed_objects'], 504)
        # A completed transport can resume without even opening the remote archive.
        with mock.patch.object(a, 'open_yang_archive', side_effect=AssertionError('no repeated network')):
            a.acquire_yang_transport(self.raw / 'yang')

    def test_offline_publish_never_opens_network_and_reuses_completed_native_files(self):
        self.transport()
        with mock.patch.object(a, 'open_yang_archive', side_effect=AssertionError('no remote ZIP')), \
             mock.patch.object(a, '_open_no_redirect', side_effect=AssertionError('no HTTP')), \
             mock.patch.object(a.urllib.request, 'urlopen', side_effect=AssertionError('no network')):
            self.assertEqual(a.main(['--raw-dir', str(self.raw), '--offline-publish']), 0)
        self.assertTrue(a.quick_raw_ready(self.raw))
        marker = json.loads((self.raw / 'network_payloads_ready.json').read_text())
        self.assertEqual(marker['status'], 'ALL_NATIVE_INPUTS_VERIFIED')
        self.assertFalse(marker['native_yang_validation_pending'])
        for name, expected in self.bodies.items():
            target = self.raw / 'yang' / name
            self.assertEqual(target.read_bytes(), expected)
            self.assertFalse(target.with_name(target.name + '.compressed.part').exists())
        with mock.patch.object(a, 'sha256_file', side_effect=AssertionError('no repeated full native hash')), \
             mock.patch.object(a, 'open_yang_archive', side_effect=AssertionError('no network')), \
             mock.patch.object(a.zlib, 'decompressobj', side_effect=AssertionError('no repeated decode')):
            self.assertEqual(a.main(['--raw-dir', str(self.raw), '--offline-publish']), 0)

    def test_changed_receipt_pin_is_rejected_before_decode_and_cache_is_retained(self):
        self.transport()
        row = self.rows[0]
        receipt_path = a._transport_receipt(self.raw / 'yang', row)
        receipt = json.loads(receipt_path.read_text())
        receipt['pin']['size'] += 1
        receipt_path.write_text(json.dumps(receipt))
        target = self.raw / 'yang' / row['path']
        compressed = target.with_name(target.name + '.compressed.part')
        before = compressed.read_bytes()
        with mock.patch.object(a.zlib, 'decompressobj', side_effect=AssertionError('do not decode changed pin')):
            with self.assertRaisesRegex(ValueError, 'frozen inventory'):
                a.publish_yang_offline(self.raw / 'yang')
        self.assertEqual(compressed.read_bytes(), before)
        self.assertFalse(target.exists())
        self.assertEqual(json.loads(receipt_path.read_text()), receipt)

    def test_changed_compressed_cache_is_rejected_and_native_sha_failure_never_publishes(self):
        self.transport()
        row = self.rows[0]
        target = self.raw / 'yang' / row['path']
        compressed = target.with_name(target.name + '.compressed.part')
        original = compressed.read_bytes()
        compressed.write_bytes(original + b'x')
        with self.assertRaisesRegex(ValueError, 'length changed'):
            a.publish_yang_offline(self.raw / 'yang')
        self.assertEqual(compressed.read_bytes(), original + b'x')
        self.assertFalse(target.exists())

    def test_frozen_native_sha_is_enforced_after_transport_before_publication(self):
        self.rows[0]['sha256'] = '0' * 64
        self.transport()  # Size-complete transport does not claim native SHA validation.
        target = self.raw / 'yang' / self.rows[0]['path']
        compressed = target.with_name(target.name + '.compressed.part')
        before = compressed.read_bytes()
        with mock.patch.object(a, 'open_yang_archive', side_effect=AssertionError('no network')):
            with self.assertRaisesRegex(ValueError, 'size/CRC/SHA mismatch'):
                a.publish_yang_offline(self.raw / 'yang')
        self.assertEqual(compressed.read_bytes(), before)
        self.assertTrue(target.with_name(target.name + '.part').exists())
        self.assertFalse(target.exists())
        self.assertFalse(a._receipt_path(self.raw / 'yang', self.rows[0]['path']).exists())

    def test_interrupted_offline_publication_keeps_first_completed_member_for_resume(self):
        self.transport()
        original = a._publish_yang_compressed
        calls = []
        def interrupted(row, root):
            calls.append(row['path'])
            if len(calls) == 2:
                raise OSError('synthetic interrupted publication')
            return original(row, root)
        with mock.patch.object(a, '_publish_yang_compressed', side_effect=interrupted):
            with self.assertRaisesRegex(OSError, 'interrupted'):
                a.publish_yang_offline(self.raw / 'yang')
        first = self.raw / 'yang' / self.rows[0]['path']
        first_stat = a.stat_identity(first)
        with mock.patch.object(a, 'open_yang_archive', side_effect=AssertionError('no network')):
            a.publish_yang_offline(self.raw / 'yang')
        self.assertEqual(a.stat_identity(first), first_stat)
        self.assertTrue(a.quick_raw_ready(self.raw))


if __name__ == '__main__':
    unittest.main()
