"""Exercise optional curl transport with no network, token, or GitHub writes."""
import json
import os
from pathlib import Path
import stat
import subprocess
import unittest
from unittest import mock

from hpcmi import github_sync as sync


class CurlTransportTests(unittest.TestCase):
    def setUp(self):
        self.environment = mock.patch.dict(os.environ, {"PAPER1_GITHUB_TRANSPORT": "curl"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.token = "unit_test_not_a_real_token"
        self.endpoint = "/repos/example/research/contents/report.json"
        self.seen_headers = []

    def response(self, status=200, body=b'{"ok":true}', headers=b'', returncode=0):
        def run(arguments, **kwargs):
            self.assertEqual(arguments[:3], ["curl", "-q", "-4"])
            self.assertIn("--config", arguments)
            self.assertEqual(arguments[arguments.index("--config") + 1], "-")
            self.assertEqual(arguments[-1], sync.API_ROOT + self.endpoint)
            self.assertEqual(arguments[arguments.index("--connect-timeout") + 1], "8")
            self.assertEqual(arguments[arguments.index("--max-time") + 1], "20")
            self.assertEqual(kwargs["timeout"], 25)
            for forbidden in (self.token, "--location", "--location-trusted", "-L", "--insecure", "-k", "--retry"):
                self.assertNotIn(forbidden, arguments)
            self.assertNotIn("env", kwargs)
            configuration = kwargs["input"].decode()
            self.assertIn("Authorization: Bearer " + self.token, configuration)
            path = Path(arguments[arguments.index("--dump-header") + 1])
            self.seen_headers.append(path)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertNotIn(self.token.encode(), path.read_bytes())
            path.write_bytes(b'HTTP/2 ' + str(status).encode() + b' Response\r\n' + headers + b'\r\n')
            return subprocess.CompletedProcess(arguments, returncode,
                    body + b'\n' + str(status).encode(), ("network detail " + self.token).encode())
        return run

    def test_credentials_only_stdin_and_default_no_redirect_tls_or_retry_override(self):
        with mock.patch.object(sync.subprocess, "run", side_effect=self.response()) as run, \
             mock.patch.object(sync.urllib.request, "build_opener") as urllib:
            self.assertEqual(sync._api("GET", self.endpoint, self.token), {"ok": True})
        run.assert_called_once()
        urllib.assert_not_called()
        self.assertTrue(self.seen_headers)
        self.assertTrue(all(not path.exists() for path in self.seen_headers))

    def test_json_payload_config_roundtrip_keeps_quotes_newlines_and_unicode(self):
        payload = {"message": 'one "quote"\nsecond line', "non_ascii": "数据", "content": "a\\b"}
        with mock.patch.object(sync.subprocess, "run", side_effect=self.response(201)) as run:
            sync._api("PUT", self.endpoint, self.token, payload)
        configuration = run.call_args.kwargs["input"].decode().splitlines()
        data = next(line[len("data = "):] for line in configuration if line.startswith("data = "))
        self.assertEqual(json.loads(json.loads(data)), payload)
        self.assertEqual(run.call_args.args[0][run.call_args.args[0].index("--request") + 1], "PUT")
        run.assert_called_once()

    def test_http_denial_redirect_and_conflict_have_controlled_semantics(self):
        for status, permanent, code in ((401, True, "github_http_401"),
                                        (403, True, "github_http_403"),
                                        (302, True, "github_http_302"),
                                        (409, False, "github_conflict_retry_next_cycle")):
            with self.subTest(status=status), \
                 mock.patch.object(sync.subprocess, "run", side_effect=self.response(status, self.token.encode(),
                     b'Location: https://untrusted.example/private-signature\r\n')) as run:
                with self.assertRaises(sync.GitHubError) as raised:
                    sync._api("PUT", self.endpoint, self.token, {"example": 1})
                self.assertEqual(raised.exception.code, code)
                self.assertEqual(raised.exception.status, status)
                self.assertEqual(raised.exception.permanent, permanent)
                self.assertNotIn(self.token, str(raised.exception))
                self.assertNotIn("signature", str(raised.exception))
                run.assert_called_once()

    def test_rate_limit_and_proxy_header_block_are_parsed_without_leaking(self):
        for status in (403, 429):
            with self.subTest(status=status), mock.patch.object(sync.subprocess, "run", side_effect=self.response(
                    status, b'{}', b'X-RateLimit-Remaining: 0\r\nRetry-After: 11\r\n')):
                with self.assertRaises(sync.GitHubError) as raised:
                    sync._api("GET", self.endpoint, self.token)
                self.assertEqual(raised.exception.code, "github_rate_limited")
                self.assertEqual(raised.exception.retry_after, 11)
                self.assertFalse(raised.exception.permanent)

    def test_curl_error_text_is_never_rendered_and_no_write_retry_occurs(self):
        for code, expected in ((28, "github_network_unavailable"),
                               (60, "github_network_unavailable"),
                               (63, "github_response_too_large")):
            with self.subTest(code=code), mock.patch.object(sync.subprocess, "run", side_effect=self.response(
                    returncode=code)) as run:
                with self.assertRaises(sync.GitHubError) as raised:
                    sync._api("POST", self.endpoint, self.token, {"ref": "example"})
                self.assertEqual(raised.exception.code, expected)
                self.assertNotIn(self.token, str(raised.exception))
                run.assert_called_once()
        with mock.patch.object(sync.subprocess, "run", side_effect=subprocess.TimeoutExpired("curl", 25)):
            with self.assertRaisesRegex(sync.GitHubError, "github_network_unavailable"):
                sync._api("GET", self.endpoint, self.token)

    def test_malformed_and_oversized_responses_are_rejected(self):
        for body, expected in ((b'not-json', "github_invalid_json_response"),
                               (b'\xff', "github_invalid_json_response"),
                               (b'x' * 2_000_001, "github_response_too_large")):
            with self.subTest(expected=expected), mock.patch.object(sync.subprocess, "run", side_effect=self.response(body=body)):
                with self.assertRaisesRegex(sync.GitHubError, expected):
                    sync._api("GET", self.endpoint, self.token)
        with mock.patch.object(sync.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b'{}\n000', b'')):
            with self.assertRaisesRegex(sync.GitHubError, "github_invalid_http_response"):
                sync._api("GET", self.endpoint, self.token)

    def test_foreign_endpoint_never_calls_curl(self):
        with mock.patch.object(sync.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                sync._api("GET", "https://untrusted.example/repos/example/research", self.token)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
