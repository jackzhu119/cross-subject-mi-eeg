"""Bounded standalone diagnosis with mock HTTP; no EEG, network or task use."""
import importlib.util
import io
import json
from pathlib import Path
import ssl
import unittest
from unittest import mock
import urllib.error

from hpcmi import yang_transport as transport

SPEC = importlib.util.spec_from_file_location('yang_route_diagnostic',
    Path(__file__).resolve().parents[1] / 'DIAGNOSE_YANG_ON_SCHOOL.py')
diagnostic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostic)
PRIVATE = 'PRIVATE-QUERY-AND-BODY'
STORAGE = 'https://' + transport.STORAGE_HOST + transport.STORAGE_PATH + '?Signature=' + PRIVATE + '&Expires=0'


class Response(io.BytesIO):
    def __init__(self, body=b'P', url=STORAGE, status=206, headers=None):
        super().__init__(body)
        self.url, self.status = url, status
        self.headers = {'Content-Range': 'bytes 0-0/65630556299', 'Content-Length': '1',
                        'Content-Type': 'application/octet-stream', **(headers or {})}
        self.read_calls = []

    def geturl(self):
        return self.url

    def read(self, size=-1):
        self.read_calls.append(size)
        return super().read(size)


class FakeOpener:
    def __init__(self, outcomes):
        self.outcomes, self.requests, self.handler = list(outcomes), [], None

    def factory(self, handler):
        self.handler = handler
        return self

    def open(self, request, **kwargs):
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, tuple):
            location, = outcome
            following = self.handler.redirect_request(request, None, 302, 'Found',
                {'Location': location, 'Content-Type': 'text/html'}, location)
            return self.open(following, **kwargs)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def http_error(url, body, status=403, headers=None):
    return urllib.error.HTTPError(url, status, PRIVATE,
        {'Content-Type': 'application/xml', **(headers or {})}, io.BytesIO(body))


class DiagnosticTests(unittest.TestCase):
    def run_probe(self, opener):
        return diagnostic.probe_route(transport, *transport.ROUTES[0], opener_factory=opener.factory)

    def assert_private_absent(self, result):
        text = json.dumps(result)
        self.assertNotIn(PRIVATE, text)
        self.assertNotIn('Signature=', text)
        self.assertNotIn('Expires=', text)

    def test_success_is_one_get_byte_not_head_and_records_only_public_hops(self):
        response = Response()
        opener = FakeOpener([(STORAGE,), response])
        result = self.run_probe(opener)
        self.assertTrue(result['range_probe_verified'])
        self.assertEqual(result['body_bytes_read'], 1)
        self.assertEqual(response.read_calls, [2])
        self.assertEqual([row['http_status'] for row in result['hops']], [302, 206])
        self.assertEqual(len(opener.requests), 2)
        self.assertTrue(all(req.get_method() == 'GET' and req.get_header('Range') == 'bytes=0-0'
                            for req in opener.requests))
        self.assertTrue(result['hops'][-1]['signature_expired'])
        self.assert_private_absent(result)

    def test_entry_403_reads_no_body_and_does_not_retry(self):
        failure = http_error(transport.ROUTES[0][1], PRIVATE.encode())
        body = failure.fp
        opener = FakeOpener([failure])
        result = self.run_probe(opener)
        self.assertFalse(result['range_probe_verified'])
        self.assertEqual(result['body_bytes_read'], 0)
        self.assertEqual(result['hops'][-1]['stage'], 'entry')
        self.assertNotIn('storage_error_code', result['hops'][-1])
        self.assertEqual(len(opener.requests), 1)
        self.assertTrue(body.closed)
        self.assert_private_absent(result)

    def test_unavailable_error_body_still_reports_host_and_status_without_secret_traceback(self):
        failure = http_error(STORAGE, b'')
        failure.read = mock.Mock(side_effect=TimeoutError(PRIVATE))
        result = self.run_probe(FakeOpener([(STORAGE,), failure]))
        self.assertFalse(result['range_probe_verified'])
        self.assertEqual(result['hops'][-1]['http_status'], 403)
        self.assertEqual(result['hops'][-1]['stage'], 'storage')
        self.assertEqual(result['failure_category'], 'error_body_unavailable')
        self.assert_private_absent(result)

    def test_storage_403_reads_bounded_xml_and_whitelists_error_code(self):
        for code in ('AccessDenied', 'SignatureDoesNotMatch', PRIVATE):
            with self.subTest(code=code):
                failure = http_error(STORAGE, ('<Error><Code>' + code + '</Code><Message>' + PRIVATE + '</Message></Error>').encode())
                opener = FakeOpener([(STORAGE,), failure])
                result = self.run_probe(opener)
                self.assertEqual(result['hops'][-1]['stage'], 'storage')
                self.assertEqual(result['hops'][-1]['storage_error_code'],
                    code if code in diagnostic.ERROR_CODES else 'unrecognized')
                self.assertFalse(result['hops'][-1]['known_expiry_error'])
                self.assertLessEqual(result['body_bytes_read'], 8192)
                self.assertEqual(len(opener.requests), 2)
                self.assert_private_absent(result)

    def test_known_expiry_supports_bare_and_namespaced_xml_without_message_output(self):
        for body in (b'<Error><Code>ExpiredToken</Code></Error>',
                     b'<Error><Code>AccessDenied</Code><Message>Request has expired</Message></Error>',
                     b'<Error xmlns="https://s3.amazonaws.com/doc/2006-03-01/"><Code>RequestExpired</Code></Error>'):
            result = self.run_probe(FakeOpener([(STORAGE,), http_error(STORAGE, body)]))
            self.assertTrue(result['hops'][-1]['known_expiry_error'])
            self.assertNotIn('Request has expired', json.dumps(result))
            self.assert_private_absent(result)

    def test_unknown_redirect_never_followed_or_logged_and_tls_not_bypassed(self):
        unknown = 'https://unknown.example/' + PRIVATE + '?signature=' + PRIVATE
        opener = FakeOpener([(unknown,)])
        result = self.run_probe(opener)
        self.assertEqual(len(opener.requests), 1)
        self.assertEqual(result['failure_category'], 'integrity_or_redirect_rejected')
        self.assertFalse(result['hops'][-1]['redirect_allowed'])
        self.assert_private_absent(result)
        opener = FakeOpener([urllib.error.URLError(ssl.SSLCertVerificationError(PRIVATE))])
        result = self.run_probe(opener)
        self.assertEqual(len(opener.requests), 1)
        self.assertEqual(result['failure_category'], 'tls')
        self.assert_private_absent(result)

    def test_wrong_range_or_full_response_never_reads_body(self):
        for response in (Response(status=200), Response(headers={'Content-Length': '2'}),
                         Response(headers={'Content-Range': 'bytes 0-0/99'})):
            result = self.run_probe(FakeOpener([response]))
            self.assertFalse(result['range_probe_verified'])
            self.assertEqual(result['failure_category'], 'integrity_or_redirect_rejected')
            self.assertEqual(response.read_calls, [])
            self.assert_private_absent(result)

    def test_error_body_limit_and_redirect_hop_limit_are_enforced(self):
        result = self.run_probe(FakeOpener([(STORAGE,), http_error(STORAGE, PRIVATE.encode() * 1000)]))
        self.assertEqual(result['body_bytes_read'], 8192)
        self.assert_private_absent(result)
        origin = transport.ROUTES[0][1]
        opener = FakeOpener([(origin,), (origin,), (origin,)])
        result = self.run_probe(opener)
        self.assertEqual(len(opener.requests), 3)
        self.assertFalse(result['range_probe_verified'])
        self.assertEqual(result['failure_category'], 'integrity_or_redirect_rejected')


if __name__ == '__main__':
    unittest.main()
