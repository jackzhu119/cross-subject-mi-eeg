import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from hpcmi import acquire as a


class Response(io.BytesIO):
    def __init__(self, body, url, status=200, headers=None):
        super().__init__(body)
        self.url = url
        self.status = status
        self.headers = {'Content-Length': str(len(body)), **(headers or {})}
    def geturl(self):
        return self.url


class AcquireTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()
    def pin(self, data=b'abcdefghij'):
        return {'path': 'sub/file.edf', 'url': 'https://data.nemar.org/nm000250/v1.0.5/sub/file.edf',
                'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

    def test_file_range_resume_and_completed_receipt_skips_network_hash(self):
        data = b'abcdefghij'
        row = self.pin(data)
        path = self.root / row['path']
        path.parent.mkdir()
        path.with_name(path.name + '.part').write_bytes(data[:4])
        response = Response(data[4:], row['url'], 206, {'Content-Range': 'bytes 4-9/10'})
        with mock.patch.object(a, '_open_no_redirect', return_value=response) as opener:
            self.assertEqual(a.transfer_object(self.root, row), row['sha256'])
            opener.assert_called_once_with(row['url'], 4)
        self.assertEqual(path.read_bytes(), data)
        with mock.patch.object(a, '_open_no_redirect', side_effect=AssertionError('network')), mock.patch.object(a, 'sha256_file', side_effect=AssertionError('rehash')):
            self.assertEqual(a.transfer_object(self.root, row), row['sha256'])

    def test_wrong_hash_and_unknown_redirect_are_preserved_rejected(self):
        row = self.pin()
        with mock.patch.object(a, '_open_no_redirect', return_value=Response(b'xxxxxxxxxx', row['url'])):
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                a.transfer_object(self.root, row)
        self.assertFalse((self.root / row['path']).exists())
        self.assertTrue((self.root / (row['path'] + '.part')).exists())
        location = 'https://' + a.STORAGE_HOST + '/nm000250/objects/SHA256E-s10--' + row['sha256'] + '.edf?signature=private'
        self.assertEqual(a.validate_nemar_location(row, location), location)
        for bad in (location.replace(a.STORAGE_HOST, 'unknown.example'), location.replace('s10--', 's11--'), location.replace('https:', 'http:'), location + '#fragment'):
            with self.assertRaises(ValueError):
                a.validate_nemar_location(row, bad)

    def test_nemar_single_exact_redirect_retains_range_and_denial_not_retried(self):
        row = self.pin()
        location = 'https://' + a.STORAGE_HOST + '/nm000250/objects/SHA256E-s10--' + row['sha256'] + '.edf?opaque=value'
        failure = a.urllib.error.HTTPError(row['url'], 302, 'Found', {'Location': location}, None)
        with mock.patch.object(a, '_open_no_redirect', side_effect=[failure, Response(b'abcdefghij', location)]) as opener:
            self.assertEqual(a.transfer_object(self.root, row, nemar=True), row['sha256'])
            self.assertEqual(opener.call_count, 2)
        other = {**row, 'path': 'other/file.edf'}
        denial = a.urllib.error.HTTPError(row['url'], 403, 'Denied', {}, None)
        with mock.patch.object(a, '_open_no_redirect', side_effect=denial) as opener:
            with self.assertRaisesRegex(ValueError, '403'):
                a.transfer_object(self.root, other, nemar=True)
            self.assertEqual(opener.call_count, 1)

    def test_yang_compressed_resume_crc_full_sha_and_receipt(self):
        data = bytes(range(255)) * 500
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('dataset/sub-001/data.bdf', data)
        payload = archive.getvalue()
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            info = z.infolist()[0]
        row = {**a.member_record(info), 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        target = self.root / row['path']
        target.parent.mkdir(parents=True)
        start = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
        compressed = target.with_name(target.name + '.compressed.part')
        compressed.write_bytes(payload[start:start + 20])
        self.assertEqual(a._yang_member(io.BytesIO(payload), info, row, self.root), row['sha256'])
        self.assertEqual(target.read_bytes(), data)
        self.assertFalse(compressed.exists())
        with mock.patch.object(a, 'sha256_file', side_effect=AssertionError('rehash')):
            self.assertEqual(a._yang_member(io.BytesIO(b''), info, row, self.root), row['sha256'])

    def test_bnci_exact_official_mirror_and_duplicate_lock(self):
        row = {**self.pin(), 'url': 'https://bnci-horizon-2020.eu/database/data-sets/001-2014/A01T.mat'}
        location = 'https://lampx.tugraz.at/~bci/database/001-2014/A01T.mat'
        self.assertEqual(a.validate_bnci_location(row, location), location)
        for bad in (location + '?key=x', location.replace('A01T', 'A02T'), location.replace('https:', 'http:')):
            with self.assertRaises(ValueError):
                a.validate_bnci_location(row, bad)
        failure = a.urllib.error.HTTPError(row['url'], 302, 'Found', {'Location': location}, None)
        with mock.patch.object(a, '_open_no_redirect', side_effect=[failure, Response(b'abcdefghij', location)]):
            self.assertEqual(a.transfer_object(self.root, row), row['sha256'])
        with a.acquisition_lock(self.root):
            with self.assertRaisesRegex(RuntimeError, 'already running'):
                with a.acquisition_lock(self.root):
                    self.fail('duplicate lock granted')
        self.assertTrue((self.root / '.acquisition.lock').is_file())

    def test_static_frozen_manifest_counts_and_vendor_identity(self):
        provenance = json.loads((a.VENDOR / 'VENDORED.json').read_text())
        for row in provenance['files']:
            self.assertEqual(hashlib.sha256((a.VENDOR / row['path']).read_bytes()).hexdigest(), row['sha256'])
        _, rows = a.yang_pins()
        self.assertEqual(len(rows), 312)
        self.assertEqual(sum('sha256' in r for r in rows), 306)
        self.assertEqual(sum(r['size'] for r in rows), 68044344823)
        for dataset, count in [('bnci', 18), ('dreyer', 174)]:
            manifest = json.loads((a.VENDOR / 'config' / (dataset + '_manifest.json')).read_text())
            self.assertEqual(len(manifest['files']), count)
        self.assertFalse(a.quick_raw_ready(self.root))


if __name__ == '__main__':
    unittest.main()
