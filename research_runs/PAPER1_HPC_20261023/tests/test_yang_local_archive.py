"""Original-ZIP import using small synthetic bytes; no network or EEG fits."""
from contextlib import ExitStack, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile
import zlib

from hpcmi import acquire as a
from hpcmi import yang_transport as t


class LocalYangArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / 'raw'
        self.yang = self.raw / 'yang'
        self.yang.mkdir(parents=True)
        self.source = self.yang / a.YANG_LOCAL_ARCHIVE_NAME
        self.bodies = {'synthetic/data.bdf': bytes(range(256)) * 80,
                       'synthetic/evt.bdf': b'event bytes' * 30,
                       'synthetic/README.md': b'synthetic metadata'}
        with zipfile.ZipFile(self.source, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, body in self.bodies.items():
                archive.writestr(name, body)
        self.original = self.source.read_bytes()
        with zipfile.ZipFile(self.source) as archive:
            self.infos = archive.infolist()
            self.cd_offset = archive.start_dir
        cd_sha = hashlib.sha256(self.original[self.cd_offset:-22]).hexdigest()
        self.rows = [{**a.member_record(info), 'size': info.file_size,
                      **({'sha256': hashlib.sha256(self.bodies[info.filename]).hexdigest()}
                         if info.filename.endswith('.bdf') else {})} for info in self.infos]
        self.inventory = {'archive_url': t.frozen.YANG_URL, 'archive_bytes': len(self.original),
            'central_directory_offset': self.cd_offset,
            'central_directory_bytes': len(self.original)-22-self.cd_offset,
            'central_directory_sha256': cd_sha, 'member_count': len(self.rows),
            'eocd_offset': len(self.original)-22}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.output = self.stack.enter_context(redirect_stdout(io.StringIO()))
        self.stack.enter_context(mock.patch.object(t.frozen, 'YANG_BYTES', len(self.original)))
        self.stack.enter_context(mock.patch.object(t.frozen, 'YANG_CENTRAL_SHA256', cd_sha))
        self.stack.enter_context(mock.patch.object(a, 'yang_pins', return_value=(self.inventory, self.rows)))
        self.stack.enter_context(mock.patch.object(a, 'selected_yang_members',
                                      side_effect=lambda archive: archive.infolist()))
        self.stack.enter_context(mock.patch.object(a.shutil, 'disk_usage',
                                      return_value=SimpleNamespace(free=8*1024**3)))
        self.http = self.stack.enter_context(mock.patch.object(t, 'YangRangeReader',
                                      side_effect=AssertionError('Local source must never use HTTP')))

    def test_local_reader_is_readonly_and_has_zero_network_counters(self):
        with t.LocalReadonlyReader(self.source) as reader:
            self.assertEqual(reader.url, t.frozen.YANG_URL)
            self.assertEqual(reader.size, len(self.original))
            self.assertEqual(reader.read(4), self.original[:4])
            self.assertEqual(reader.seek(-4, os.SEEK_END), len(self.original)-4)
            self.assertEqual(reader.read(), self.original[-4:])
            self.assertEqual(reader.tell(), reader.size)
            self.assertEqual(reader.local_bytes_read, 8)
            self.assertEqual((reader.bytes_received, reader.request_count), (0, 0))
            with self.assertRaises((io.UnsupportedOperation, NotImplementedError)):
                reader.write(b'changed')
        self.assertTrue(reader.closed)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_local_archive_uses_same_directory_identity_without_full_md5(self):
        with mock.patch.object(t.hashlib, 'md5', side_effect=AssertionError('No whole ZIP scan')):
            reader, archive, attestation, directory = t.open_yang_archive(local_archive=self.source)
        try:
            self.assertEqual(attestation, self.inventory)
            self.assertEqual(directory, self.original[self.cd_offset:-22])
            self.assertEqual(len(archive.infolist()), len(self.rows))
            self.assertEqual(reader.bytes_received, 0)
            self.assertGreater(reader.local_bytes_read, 0)
        finally:
            archive.close()
            reader.close()
        self.http.assert_not_called()

    def test_wrong_size_or_directory_is_preserved_without_network_fallback(self):
        self.source.write_bytes(self.original + b'incomplete or wrong upload')
        before = self.source.read_bytes()
        with self.assertRaisesRegex(ValueError, 'length differs'):
            a._open_yang_source(self.yang)
        self.assertEqual(self.source.read_bytes(), before)
        changed = bytearray(self.original)
        changed[self.cd_offset+4] ^= 1
        self.source.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, 'central-directory SHA256'):
            a._open_yang_source(self.yang)
        self.assertEqual(self.source.read_bytes(), changed)
        self.http.assert_not_called()

    def test_partial_member_resumes_and_native_crc_sha_publish_stays_offline(self):
        first = self.rows[0]
        info = self.infos[0]
        target = self.yang / first['path']
        target.parent.mkdir(parents=True)
        start = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
        compressed = target.with_name(target.name+'.compressed.part')
        compressed.write_bytes(self.original[start:start+7])
        with mock.patch.object(a.zlib, 'decompressobj', side_effect=AssertionError('Transport must not decode')):
            a.acquire_yang_transport(self.yang)
        self.assertFalse(target.exists())
        self.assertEqual(compressed.stat().st_size, first['compressed_bytes'])
        receipt = json.loads(a._transport_receipt(self.yang, first).read_text())
        self.assertFalse(receipt['native_sha256_verified'])
        self.assertTrue(a._yang_payloads_cached(self.yang, self.inventory, self.rows))
        with mock.patch.object(a, '_open_yang_source', side_effect=AssertionError('Complete cache must not reopen ZIP')):
            a.acquire_yang_transport(self.yang)
            a.publish_yang_offline(self.yang)
        for name, data in self.bodies.items():
            self.assertEqual((self.yang/name).read_bytes(), data)
        with mock.patch.object(a, 'sha256_file', side_effect=AssertionError('Do not rehash completed bytes')), \
             mock.patch.object(a, '_open_yang_source', side_effect=AssertionError('Do not reopen cached ZIP')):
            a.acquire_yang_transport(self.yang)
            a.publish_yang_offline(self.yang)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.http.assert_not_called()

    def test_preflight_uses_local_directory_then_cached_receipts_without_rehash(self):
        with mock.patch.object(a, '_pinned_native_ready', return_value=True):
            result = a.check_download_route(self.raw)
        self.assertEqual(result['status'], 'DOWNLOAD_SOURCES_PREFLIGHT_VERIFIED')
        self.assertEqual(result['checked_sources'][1]['status'], 'YANG_LOCAL_ZIP_DIRECTORY_VERIFIED')
        self.assertFalse(result['full_all_dataset_sha256_verified'])
        self.assertEqual(result['model_fits'], 0)
        a.acquire_yang_transport(self.yang)
        with mock.patch.object(a, '_pinned_native_ready', return_value=True), \
             mock.patch.object(a, 'sha256_file', side_effect=AssertionError('No metadata preflight rehash')), \
             mock.patch.object(a, '_open_yang_source', side_effect=AssertionError('Cached payload needs no ZIP')):
            result = a.check_download_route(self.raw)
        self.assertEqual(result['checked_sources'][1]['status'], 'CACHED_YANG_PAYLOADS_VERIFIED')
        self.assertTrue(result['checked_sources'][1]['native_validation_may_be_pending'])
        self.http.assert_not_called()

    def test_native_sha_failure_never_publishes_or_changes_source(self):
        self.rows[0]['sha256'] = '0'*64
        a.acquire_yang_transport(self.yang)
        target = self.yang / self.rows[0]['path']
        compressed = target.with_name(target.name+'.compressed.part')
        with self.assertRaisesRegex(ValueError, 'size/CRC/SHA mismatch'):
            a.publish_yang_offline(self.yang)
        self.assertFalse(target.exists())
        self.assertTrue(target.with_name(target.name+'.part').exists())
        self.assertTrue(compressed.exists())
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_local_payload_corruption_keeps_crc_gate_and_original_failure_bytes(self):
        info = self.infos[0]
        offset = info.header_offset+30+len(info.filename.encode())+len(info.extra)
        changed = bytearray(self.original)
        changed[offset+info.compress_size//2] ^= 1
        self.source.write_bytes(changed)
        a.acquire_yang_transport(self.yang)
        target = self.yang / self.rows[0]['path']
        with self.assertRaises((ValueError, zlib.error)):
            a.publish_yang_offline(self.yang)
        self.assertFalse(target.exists())
        self.assertTrue(target.with_name(target.name+'.compressed.part').exists())
        self.assertEqual(self.source.read_bytes(), changed)

    def test_local_metadata_budget_is_bounded(self):
        with t.LocalReadonlyReader(self.source, max_total_bytes=4) as reader:
            self.assertEqual(reader.read(4), self.original[:4])
            with self.assertRaisesRegex(ValueError, 'metadata read limit'):
                reader.read(1)
            self.assertEqual(reader.local_bytes_read, 4)
            self.assertEqual(reader.bytes_received, 0)


if __name__ == '__main__':
    unittest.main()
