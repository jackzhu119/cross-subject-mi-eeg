"""Frozen Yang byte-range transport; no external network or EEG is used."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import socket
import ssl
import unittest
from unittest import mock
import urllib.error
import urllib.request
import zipfile

from hpcmi import yang_transport as t

PRIVATE = 'PRIVATE-SIGNED-QUERY-NOT-FOR-LOGS'
STORAGE = 'https://' + t.STORAGE_HOST + t.STORAGE_PATH + '?signature=' + PRIVATE


class Response(io.BytesIO):
    def __init__(self, data=b'P', *, status=206, start=0, count=None, total=None, url=STORAGE, headers=None):
        super().__init__(data)
        count = len(data) if count is None else count
        self.status = status
        self.headers = {'Content-Range': 'bytes %d-%d/%d' % (start, start + count - 1, t.frozen.YANG_BYTES if total is None else total),
                        'Content-Length': str(count)}
        self.headers.update(headers or {})
        self.url = url
        self.read_calls = []

    def read(self, count=-1):
        self.read_calls.append(count)
        return super().read(count)

    def geturl(self):
        return self.url


class Opener:
    def __init__(self, outcomes):
        self.outcomes, self.calls = list(outcomes), []

    def open(self, request, **kwargs):
        self.calls.append((request, kwargs))
        if not self.outcomes:
            raise AssertionError('Unexpected request')
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def denial(url=STORAGE, code=403, body=b'<Error><Code>AccessDenied</Code><Message>Forbidden</Message></Error>'):
    return urllib.error.HTTPError(url, code, 'PRIVATE SERVER MESSAGE', {}, io.BytesIO(body))


class YangTransportTests(unittest.TestCase):
    def test_get_probe_and_exact_range_never_issue_head(self):
        first, data = Response(), Response(b'abcd', count=4)
        opener = Opener([first, data])
        reader = t.YangRangeReader(opener=opener)
        self.assertEqual(reader.read(4), b'abcd')
        self.assertEqual(reader.url, t.frozen.YANG_URL)
        self.assertEqual(reader.bytes_received, 5)
        self.assertEqual(reader.request_count, 2)
        self.assertTrue(all(req.get_method() == 'GET' for req, _ in opener.calls))
        self.assertEqual([req.get_header('Range') for req, _ in opener.calls], ['bytes=0-0', 'bytes=0-3'])
        self.assertEqual(first.read_calls, [2])
        self.assertEqual(data.read_calls, [5])

    def test_full_200_or_wrong_range_never_reads_body_or_rotates(self):
        for response in (Response(status=200), Response(headers={'Content-Range': 'bytes 1-1/9'}),
                         Response(headers={'Content-Encoding': 'gzip'})):
            with self.subTest(response=response.headers):
                opener = Opener([response])
                with self.assertRaises(ValueError):
                    t.YangRangeReader(opener=opener)
                self.assertEqual(response.read_calls, [])
                self.assertEqual(len(opener.calls), 1)

    def test_verified_official_alternate_after_typed_connection_failure(self):
        opener = Opener([urllib.error.URLError(socket.gaierror(-2, 'PRIVATE DNS')), Response()])
        with contextlib.redirect_stdout(io.StringIO()) as output:
            reader = t.YangRangeReader(opener=opener)
        self.assertEqual(reader._route_index, 1)
        self.assertEqual(reader.url, t.frozen.YANG_URL)
        self.assertEqual(opener.calls[1][0].full_url, t.ROUTES[1][1])
        self.assertNotIn(PRIVATE, output.getvalue())

    def test_explicit_fresh_denial_does_not_try_another_route(self):
        opener = Opener([denial(t.frozen.YANG_URL)])
        with self.assertRaises(t.YangTransportError) as result:
            t.YangRangeReader(opener=opener)
        self.assertEqual(result.exception.http_status, 403)
        self.assertEqual(len(opener.calls), 1)
        self.assertNotIn(PRIVATE, str(result.exception))

    def test_unknown_redirect_or_storage_path_is_rejected(self):
        for url in ('https://example.org/51001884/file.zip', STORAGE.replace('/51001884/', '/999/'),
                    STORAGE.replace('https:', 'http:'), STORAGE + '#fragment',
                    STORAGE.replace(t.STORAGE_HOST, 'user:pass@' + t.STORAGE_HOST)):
            with self.subTest(url=url.split('?')[0]), self.assertRaises(ValueError):
                t._validate_download_url(url)
        handler = t._OfficialRedirect()
        request = urllib.request.Request(t.frozen.YANG_URL, headers={'Range': 'bytes=0-0'})
        with self.assertRaises(ValueError):
            handler.redirect_request(request, None, 302, 'Found', {}, 'https://unknown.example/file')
        redirected = handler.redirect_request(request, None, 302, 'Found', {}, STORAGE)
        self.assertEqual(redirected.get_method(), 'GET')
        self.assertEqual(redirected.get_header('Range'), 'bytes=0-0')

    def test_expired_storage_link_refreshes_once_with_public_get(self):
        expired = denial(body=b'<Error><Code>AccessDenied</Code><Message>Request has expired</Message></Error>')
        opener = Opener([Response(), expired, Response(), Response(b'ab', count=2)])
        with mock.patch.object(t.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()) as output:
            reader = t.YangRangeReader(opener=opener)
            self.assertEqual(reader.read(2), b'ab')
        self.assertEqual(len(opener.calls), 4)
        self.assertEqual(opener.calls[2][0].full_url, t.frozen.YANG_URL)
        self.assertNotIn(PRIVATE, output.getvalue())

    def test_repeated_expired_storage_link_stops_after_one_refresh(self):
        def expired():
            return denial(body=b'<Error><Code>ExpiredToken</Code></Error>')
        opener = Opener([Response(), expired(), Response(), expired()])
        with mock.patch.object(t.time, 'sleep'):
            reader = t.YangRangeReader(opener=opener)
            with self.assertRaises(t.YangTransportError) as result:
                reader.read(2)
        self.assertEqual(result.exception.http_status, 403)
        self.assertEqual(len(opener.calls), 4)

    def test_all_routes_network_failure_retains_safe_typed_retry_reason(self):
        opener = Opener([urllib.error.URLError(socket.gaierror(-2, 'PRIVATE first DNS')),
                         urllib.error.URLError(OSError(101, 'PRIVATE route failed'))])
        with self.assertRaises(t.YangTransportError) as raised:
            t.YangRangeReader(opener=opener)
        from hpcmi.acquire import safe_error_details
        details = safe_error_details(raised.exception)
        self.assertEqual(details['category'], 'connection')
        self.assertEqual(details['errno'], 101)
        self.assertNotIn('PRIVATE', str(raised.exception))
        self.assertEqual(len(opener.calls), 2)

    def test_official_route_server_503_rotates_once(self):
        opener = Opener([denial(t.frozen.YANG_URL, 503), Response()])
        reader = t.YangRangeReader(opener=opener)
        self.assertEqual(reader._route_index, 1)
        self.assertEqual(len(opener.calls), 2)

    def test_truncated_range_retries_same_offset_without_caching_partial(self):
        opener = Opener([Response(), Response(b'a', count=2), Response(), Response(b'ab', count=2)])
        with mock.patch.object(t.time, 'sleep'):
            reader = t.YangRangeReader(opener=opener)
            self.assertEqual(reader.read(2), b'ab')
        self.assertEqual([req.get_header('Range') for req, _ in opener.calls],
                         ['bytes=0-0', 'bytes=0-1', 'bytes=0-0', 'bytes=0-1'])
        self.assertEqual(reader.bytes_received, 5)

    def test_tls_failure_is_not_retried_through_another_host(self):
        opener = Opener([urllib.error.URLError(ssl.SSLCertVerificationError('PRIVATE TLS'))])
        with self.assertRaises(t.YangTransportError) as raised:
            t.YangRangeReader(opener=opener)
        self.assertIsInstance(raised.exception.reason, ssl.SSLError)
        self.assertEqual(len(opener.calls), 1)

    def test_error_body_obeys_explicit_network_budget_too(self):
        error = denial(body=b'<Error><Code>ExpiredToken</Code></Error>')
        body = error.fp
        with mock.patch.object(body, 'read', wraps=body.read) as read:
            with self.assertRaises(t.YangTransportError):
                t.YangRangeReader(opener=Opener([error]), max_total_bytes=1)
            self.assertEqual(read.call_args.args[0], 1)

    def test_network_budget_includes_probe_and_prevents_extra_body(self):
        opener = Opener([Response()])
        reader = t.YangRangeReader(opener=opener, max_total_bytes=1)
        self.assertEqual(reader.read(1), b'P')  # Cached one-byte probe.
        with self.assertRaises(ValueError):
            reader.read(1)
        self.assertEqual(len(opener.calls), 1)

    def test_metadata_checks_exact_version_file_size_md5_and_license(self):
        record = {'doi': '10.25452/figshare.plus.22671172.v5', 'license': {'name': 'CC BY 4.0'},
                  'files': [{'id': t.FILE_ID, 'size': t.frozen.YANG_BYTES,
                             'supplied_md5': t.frozen.YANG_ARCHIVE_MD5,
                             'computed_md5': t.frozen.YANG_ARCHIVE_MD5,
                             'download_url': t.frozen.YANG_URL}]}
        response = Response(json.dumps(record).encode(), status=200, url=t.ARTICLE_METADATA_URL)
        result = t.verify_official_file_metadata(Opener([response]))
        self.assertFalse(result['whole_archive_md5_verified'])
        self.assertEqual(result['file_id'], t.FILE_ID)
        record['files'][0]['size'] += 1
        with self.assertRaises(ValueError):
            t.verify_official_file_metadata(Opener([Response(json.dumps(record).encode(), status=200)]))

    def test_original_zip_parser_and_central_hash_are_reused(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('synthetic.txt', b'not EEG')
        blob = stream.getvalue()
        directory = blob[blob.index(b'PK\x01\x02'):blob.index(b'PK\x05\x06')]
        class LocalRanges:
            def __init__(self): self.calls = []
            def open(self, request, **kwargs):
                self.calls.append(request)
                start, end = map(int, request.get_header('Range')[6:].split('-'))
                return Response(blob[start:end + 1], start=start, count=end - start + 1, total=len(blob))
        opener = LocalRanges()
        with mock.patch.object(t.frozen, 'YANG_BYTES', len(blob)), \
             mock.patch.object(t.frozen, 'YANG_CENTRAL_SHA256', hashlib.sha256(directory).hexdigest()):
            reader, archive, attestation, actual = t.open_yang_archive(opener=opener)
            self.assertEqual(actual, directory)
            self.assertEqual(attestation['archive_url'], t.frozen.YANG_URL)
            self.assertEqual(archive.read('synthetic.txt'), b'not EEG')
            archive.close(); reader.close()
        with mock.patch.object(t.frozen, 'YANG_BYTES', len(blob)), \
             mock.patch.object(t.frozen, 'YANG_CENTRAL_SHA256', '0' * 64), self.assertRaises(ValueError):
            t.open_yang_archive(opener=LocalRanges())


if __name__ == '__main__':
    unittest.main()
