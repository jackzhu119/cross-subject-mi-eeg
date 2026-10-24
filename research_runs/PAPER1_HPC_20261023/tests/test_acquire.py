import hashlib
import contextlib
import errno
import http.client
import io
import json
from pathlib import Path
import tempfile
import socket
import ssl
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

    def test_storage_503_is_retryable_but_storage_403_is_not(self):
        from hpcmi import login_pipeline
        row = self.pin()
        location = 'https://' + a.STORAGE_HOST + '/nm000250/objects/SHA256E-s10--' + row['sha256'] + '.edf?signature=PRIVATE'
        for status, retryable in ((503, True), (403, False)):
            redirect = a.urllib.error.HTTPError(row['url'], 302, 'Found', {'Location': location}, None)
            failure = a.urllib.error.HTTPError(location, status, 'PRIVATE', {}, None)
            with self.subTest(status=status), mock.patch.object(a, '_open_no_redirect', side_effect=[redirect, failure]):
                with self.assertRaises(ValueError) as caught:
                    with a.open_object(row, nemar=True):
                        self.fail('HTTP failure yielded an object')
            detail = a.safe_error_details(caught.exception)
            self.assertEqual(detail['http_status'], status)
            self.assertTrue(a._independent_network_failure(caught.exception, detail))
            self.assertEqual(login_pipeline._network_retryable({'attempt_id': 'unit', **detail}, 'unit'), retryable)
            self.assertNotIn('PRIVATE', json.dumps(detail))

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

    def error_rows(self, text):
        return [json.loads(line) for line in text.splitlines() if line.startswith('{')]

    def test_dns_and_certificate_diagnostics_recover_context_without_messages(self):
        secret = 'https://proxy-user:PRIVATE_PASSWORD@proxy.invalid/?signature=PRIVATE_SIGNATURE'
        dns = a.urllib.error.URLError(socket.gaierror(socket.EAI_NONAME, secret))
        certificate = ssl.SSLCertVerificationError(1, secret)
        certificate.verify_code = 20
        certificate.verify_message = secret
        for cause, category in ((dns, 'dns'), (a.urllib.error.URLError(certificate), 'tls_certificate')):
            output = io.StringIO()
            with mock.patch.object(a, '_open_no_redirect', side_effect=cause), contextlib.redirect_stdout(output):
                with self.assertRaises(RuntimeError):
                    a.transfer_object(self.root, self.pin(), attempts=1)
            rows = self.error_rows(output.getvalue())
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['stage'], 'canonical_open')
            self.assertEqual(rows[0]['category'], category)
            self.assertFalse(rows[0]['will_retry'])
            self.assertNotIn('PRIVATE', output.getvalue())
            self.assertNotIn('proxy.invalid', output.getvalue())
            if category == 'tls_certificate':
                self.assertEqual(rows[0]['ssl_verify_code'], 20)
            else:
                self.assertIn(socket.EAI_NONAME, [r.get('errno') for r in rows[0]['causes']])

    def test_local_disk_error_identifies_fsync_and_retains_partial(self):
        row = self.pin()
        output = io.StringIO()
        with mock.patch.object(a, '_open_no_redirect', return_value=Response(b'abcdefghij', row['url'])), \
             mock.patch.object(a.os, 'fsync', side_effect=OSError(errno.ENOSPC, 'PRIVATE disk path')), \
             contextlib.redirect_stdout(output):
            with self.assertRaises(RuntimeError):
                a.transfer_object(self.root, row, attempts=1)
        report = self.error_rows(output.getvalue())[0]
        self.assertEqual(report['stage'], 'fsync_partial')
        self.assertEqual(report['category'], 'os_error')
        self.assertEqual(report['causes'][0]['errno'], errno.ENOSPC)
        self.assertNotIn('PRIVATE', output.getvalue())
        self.assertEqual((self.root / (row['path'] + '.part')).read_bytes(), b'abcdefghij')
        self.assertFalse((self.root / row['path']).exists())

    def test_mirror_http_status_and_incomplete_body_never_emit_url_or_payload(self):
        row = self.pin()
        location = 'https://' + a.STORAGE_HOST + '/nm000250/objects/SHA256E-s10--' + row['sha256'] + '.edf?signature=PRIVATE_SIGNATURE'
        redirect = a.urllib.error.HTTPError(row['url'], 302, 'Found', {'Location': location}, None)
        denial = a.urllib.error.HTTPError(location, 403, 'PRIVATE_MESSAGE', {'Location': location}, None)
        output = io.StringIO()
        with mock.patch.object(a, '_open_no_redirect', side_effect=[redirect, denial]) as opener, contextlib.redirect_stdout(output):
            with self.assertRaises(ValueError):
                a.transfer_object(self.root, row, nemar=True)
        self.assertEqual(opener.call_count, 2)
        report = self.error_rows(output.getvalue())[0]
        self.assertEqual((report['stage'], report['http_status']), ('official_mirror_open', 403))
        self.assertNotIn('PRIVATE', output.getvalue())
        self.assertNotIn('https://', output.getvalue())
        response = Response(b'abcdefghij', row['url'])
        output = io.StringIO()
        with mock.patch.object(a, '_open_no_redirect', return_value=response), \
             mock.patch.object(response, 'read', side_effect=http.client.IncompleteRead(b'PRIVATE_BODY', 9)), \
             contextlib.redirect_stdout(output):
            with self.assertRaises(RuntimeError):
                a.transfer_object(self.root, row, attempts=1)
        report = self.error_rows(output.getvalue())[0]
        self.assertEqual((report['stage'], report['category']), ('read_body', 'incomplete_read'))
        self.assertEqual(report['causes'][0]['partial_bytes'], len(b'PRIVATE_BODY'))
        self.assertNotIn('PRIVATE', output.getvalue())

    def test_safe_diagnostics_bound_exception_cycles_and_preserve_retry_count(self):
        secret = 'https://user:PRIVATE@host/?signature=PRIVATE'
        failure = a.urllib.error.URLError(secret)
        failure.__context__ = failure
        self.assertEqual(len(a.safe_error_details(failure)['causes']), 1)
        output = io.StringIO()
        with mock.patch.object(a, '_open_no_redirect', side_effect=failure) as opener, \
             mock.patch.object(a.time, 'sleep') as wait, contextlib.redirect_stdout(output):
            with self.assertRaises(RuntimeError):
                a.transfer_object(self.root, self.pin(), attempts=2)
        self.assertEqual(opener.call_count, 2)
        self.assertEqual(wait.call_count, 1)
        self.assertEqual([r['will_retry'] for r in self.error_rows(output.getvalue())], [True, False])
        self.assertNotIn('PRIVATE', output.getvalue())

    def test_bnci_typed_canonical_connection_failure_uses_exact_official_alias(self):
        data = b'abcdefghij'
        for number, reason in enumerate((socket.gaierror(socket.EAI_NONAME, 'PRIVATE DNS message'),
                                         TimeoutError('PRIVATE timeout'),
                                         ConnectionRefusedError(errno.ECONNREFUSED, 'PRIVATE refused'),
                                         ssl.SSLCertVerificationError(1, 'PRIVATE certificate')), 1):
            basename = 'A0%dE.mat' % number
            canonical = 'https://bnci-horizon-2020.eu/database/data-sets/001-2014/' + basename
            alias = 'https://lampx.tugraz.at/~bci/database/001-2014/' + basename
            row = {**self.pin(data), 'path': basename, 'url': canonical}
            output = io.StringIO()
            with mock.patch.object(a, '_open_no_redirect', side_effect=[a.urllib.error.URLError(reason),
                    Response(data, alias)]) as opener, contextlib.redirect_stdout(output):
                self.assertEqual(a.transfer_object(self.root, row), row['sha256'])
            self.assertEqual(opener.call_args_list, [mock.call(canonical, 0), mock.call(alias, 0)])
            report = self.error_rows(output.getvalue())[0]
            self.assertEqual(report['event'], 'official_alias_attempt')
            self.assertFalse(report['school_failure_cause_established'])
            self.assertNotIn('PRIVATE', output.getvalue())
            self.assertEqual((self.root / basename).read_bytes(), data)

    def test_bnci_http_and_string_reason_denials_never_try_alias(self):
        canonical = 'https://bnci-horizon-2020.eu/database/data-sets/001-2014/A01E.mat'
        row = {**self.pin(), 'path': 'A01E.mat', 'url': canonical}
        failure = a.urllib.error.HTTPError(canonical, 403, 'PRIVATE denial', {}, None)
        for cause, expected in ((failure, ValueError),
                (a.urllib.error.URLError('Tunnel denied HTTP403 PRIVATE'), RuntimeError),
                (a.urllib.error.URLError(failure), RuntimeError),
                (a.urllib.error.URLError(OSError(errno.EACCES, 'PRIVATE local denial')), RuntimeError),
                (a.urllib.error.URLError(OSError(errno.ENOSPC, 'PRIVATE disk failure')), RuntimeError)):
            output = io.StringIO()
            with mock.patch.object(a, '_open_no_redirect', side_effect=cause) as opener, contextlib.redirect_stdout(output):
                with self.assertRaises(expected):
                    a.transfer_object(self.root, row, attempts=1)
            opener.assert_called_once_with(canonical, 0)
            self.assertNotIn('official_alias_attempt', output.getvalue())
            self.assertNotIn('PRIVATE', output.getvalue())

    def test_bnci_exact_route_errors_use_official_alias_and_remain_network_failures(self):
        data = b'abcdefghij'
        for index, code in enumerate((errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ENETDOWN), 1):
            with self.subTest(errno=code):
                basename = 'A0%dE.mat' % index
                canonical = 'https://bnci-horizon-2020.eu/database/data-sets/001-2014/' + basename
                alias = 'https://lampx.tugraz.at/~bci/database/001-2014/' + basename
                row = {**self.pin(data), 'path': basename, 'url': canonical}
                failure = a.urllib.error.URLError(OSError(code, 'PRIVATE network route'))
                output = io.StringIO()
                with mock.patch.object(a, '_open_no_redirect', side_effect=[failure, Response(data, alias)]) as opener, \
                     contextlib.redirect_stdout(output):
                    self.assertEqual(a.transfer_object(self.root, row), row['sha256'])
                self.assertEqual(opener.call_args_list, [mock.call(canonical, 0), mock.call(alias, 0)])
                report = self.error_rows(output.getvalue())[0]
                self.assertEqual(report['event'], 'official_alias_attempt')
                self.assertEqual((report['category'], report['errno']), ('connection', code))
                self.assertNotIn('PRIVATE', output.getvalue())
                self.assertEqual((self.root / basename).read_bytes(), data)
                self.assertEqual(a.safe_error_details(failure)['category'], 'connection')

    def test_errno101_canonical_and_alias_failure_preserves_bound_and_retry_evidence(self):
        canonical = 'https://bnci-horizon-2020.eu/database/data-sets/001-2014/A01E.mat'
        alias = 'https://lampx.tugraz.at/~bci/database/001-2014/A01E.mat'
        row = {**self.pin(), 'path': 'A01E.mat', 'url': canonical}
        failure = a.urllib.error.URLError(OSError(errno.ENETUNREACH, 'PRIVATE network route'))
        output = io.StringIO()
        with mock.patch.object(a, '_open_no_redirect', side_effect=failure) as opener, \
             contextlib.redirect_stdout(output):
            with self.assertRaises(RuntimeError) as raised:
                a.transfer_object(self.root, row, attempts=1)
        self.assertEqual(opener.call_args_list, [mock.call(canonical, 0), mock.call(alias, 0)])
        report = self.error_rows(output.getvalue())[-1]
        self.assertEqual((report['stage'], report['category'], report['errno']),
                         ('official_mirror_open', 'connection', errno.ENETUNREACH))
        self.assertFalse(report['will_retry'])
        self.assertEqual(a.safe_error_details(raised.exception)['category'], 'connection')
        self.assertNotIn('PRIVATE', output.getvalue())
        self.assertFalse((self.root / 'A01E.mat').exists())


class RouteHeadTests(unittest.TestCase):
    def test_head_checks_frozen_length_without_body_read(self):
        row = json.loads((a.VENDOR / 'config/bnci_manifest.json').read_text())['files'][0]
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.headers = {'Content-Length': str(row['size'])}
        with mock.patch.object(a.urllib.request, 'build_opener') as factory:
            factory.return_value.open.return_value = response
            a.check_download_route()
        request = factory.return_value.open.call_args.args[0]
        self.assertEqual(request.get_method(), 'HEAD')
        self.assertTrue(request.full_url.startswith('https://lampx.tugraz.at/~bci/database/001-2014/'))
        response.read.assert_not_called()

    def test_changed_head_length_stops_without_body_read(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.headers = {'Content-Length': '1'}
        with mock.patch.object(a.urllib.request, 'build_opener') as factory:
            factory.return_value.open.return_value = response
            with self.assertRaises(ValueError):
                a.check_download_route()
        response.read.assert_not_called()


if __name__ == '__main__':
    unittest.main()
