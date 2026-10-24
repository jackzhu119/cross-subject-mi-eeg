"""Frozen source preflight: metadata mocks only, no network or EEG files."""
from contextlib import ExitStack, redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import urllib.error

from hpcmi import acquire as a


class Archive:
    def __init__(self, rows):
        self.items = {row['path']: SimpleNamespace(
            filename=row['path'], file_size=row['bytes'], compress_size=row['compressed_bytes'],
            CRC=int(row['crc32'], 16), header_offset=row['header_offset'],
            compress_type=row['compression']) for row in rows}
        self.closed = False

    def namelist(self):
        return list(self.items)

    def getinfo(self, name):
        return self.items[name]

    def close(self):
        self.closed = True


class DownloadPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raw = Path(self.temp.name) / 'raw'
        self.raw.mkdir()
        self.marker = self.raw / 'preserved.partial'
        self.marker.write_bytes(b'original partial evidence')
        self.inventory, self.rows = a.yang_pins()  # Actual frozen metadata only.
        self.archive = Archive(self.rows)
        self.reader = mock.Mock()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.output = self.stack.enter_context(redirect_stdout(io.StringIO()))
        self.native_ready = self.stack.enter_context(mock.patch.object(a, '_pinned_native_ready', return_value=True))
        self.bnci_head = self.stack.enter_context(mock.patch.object(a, '_check_bnci_download_head',
                         side_effect=AssertionError('Cached BNCI must not be requested')))
        self.open_yang = self.stack.enter_context(mock.patch.object(a, 'open_yang_archive',
                         return_value=(self.reader, self.archive, copy.deepcopy(self.inventory), b'bounded directory')))
        self.native_open = self.stack.enter_context(mock.patch.object(a, 'open_object',
                           side_effect=AssertionError('Cached native sources must not be requested')))

    def report(self):
        return json.loads((self.raw / 'download_route_status.json').read_text())

    def response(self, body=b'x'):
        value = mock.MagicMock()
        value.__enter__.return_value = value
        value.read.return_value = body
        return value

    def test_cached_native_inputs_skip_get_yang_uses_exact_frozen_directory_and_members(self):
        result = a.check_download_route(self.raw)
        self.assertEqual(result['status'], 'DOWNLOAD_SOURCES_PREFLIGHT_VERIFIED')
        self.bnci_head.assert_not_called()
        self.native_open.assert_not_called()
        self.open_yang.assert_called_once_with(max_total_bytes=1024 * 1024)
        self.assertEqual([r['dataset'] for r in result['checked_sources']], ['bnci', 'yang', 'dreyer'])
        yang = result['checked_sources'][1]
        self.assertEqual(yang['selected_members'], 312)
        self.assertEqual(yang['central_directory_sha256'], self.inventory['central_directory_sha256'])
        self.assertEqual(yang['archive_bytes'], 65630556299)
        self.assertFalse(yang['eeg_payload_read'])
        self.assertFalse(result['full_all_dataset_sha256_verified'])
        self.assertEqual(result['model_fits'], 0)
        self.assertTrue(self.archive.closed)
        self.reader.close.assert_called_once()
        self.assertEqual(self.report(), result)
        self.assertEqual(self.marker.read_bytes(), b'original partial evidence')

    def test_yang_503_does_not_prevent_bounded_dreyer_probe_or_claim_all_verified(self):
        self.native_ready.side_effect = lambda root, dataset: dataset == 'bnci'
        self.open_yang.side_effect = urllib.error.HTTPError(
            'https://PRIVATE.invalid/?signature=PRIVATE', 503, 'PRIVATE', {}, None)
        response = self.response()
        self.native_open.side_effect = None
        self.native_open.return_value = response
        result = a.check_download_route(self.raw)
        row = json.loads((a.VENDOR / 'config/dreyer_manifest.json').read_text())['files'][0]
        self.native_open.assert_called_once_with(row, row['size'] - 1, nemar=True)
        response.read.assert_called_once_with(2)
        self.assertEqual(result['status'], 'DOWNLOAD_SOURCES_RETRY_PENDING')
        self.assertEqual([r['dataset'] for r in result['checked_sources']], ['bnci', 'dreyer'])
        self.assertEqual(result['checked_sources'][-1]['range_probe_bytes'], 1)
        self.assertFalse(result['checked_sources'][-1]['full_file_sha256_verified'])
        self.assertEqual(result['unavailable_sources'][0]['dataset'], 'yang')
        self.assertEqual(result['unavailable_sources'][0]['http_status'], 503)
        self.assertFalse(result['full_all_dataset_sha256_verified'])
        self.assertNotIn('PRIVATE', self.output.getvalue())
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertEqual(self.report(), result)

    def test_wrong_frozen_directory_is_fatal_before_dreyer_and_never_writes_verified_status(self):
        bad = copy.deepcopy(self.inventory)
        bad['central_directory_sha256'] = '0' * 64
        self.open_yang.return_value = (self.reader, self.archive, bad, b'changed directory')
        with self.assertRaisesRegex(ValueError, 'frozen ZIP identity'):
            a.check_download_route(self.raw)
        self.native_open.assert_not_called()
        self.assertFalse((self.raw / 'download_route_status.json').exists())
        self.assertTrue(self.archive.closed)
        self.reader.close.assert_called_once()
        self.assertEqual(self.marker.read_bytes(), b'original partial evidence')

    def test_changed_member_pin_is_fatal_before_dreyer(self):
        self.archive.items[self.rows[0]['path']].compress_size += 1
        with self.assertRaisesRegex(ValueError, 'frozen pin'):
            a.check_download_route(self.raw)
        self.native_open.assert_not_called()
        self.assertFalse((self.raw / 'download_route_status.json').exists())
        self.assertTrue(self.archive.closed)
        self.reader.close.assert_called_once()

    def test_dreyer_probe_reads_at_most_two_bytes_and_rejects_non_one_byte_reply(self):
        self.native_ready.side_effect = lambda root, dataset: dataset == 'bnci'
        response = self.response(b'xx')
        self.native_open.side_effect = None
        self.native_open.return_value = response
        with self.assertRaisesRegex(ValueError, 'bounded range probe length'):
            a.check_download_route(self.raw)
        response.read.assert_called_once_with(2)
        self.assertFalse((self.raw / 'download_route_status.json').exists())
        self.assertEqual(self.marker.read_bytes(), b'original partial evidence')


if __name__ == '__main__':
    unittest.main()
