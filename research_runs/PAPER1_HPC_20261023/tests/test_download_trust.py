"""Process-local CA selection; no external requests, EEG, or package changes."""
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
import io
import json
import os
import ssl
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from hpcmi import acquire as a
SYSTEM_CA_CANDIDATES = a._SYSTEM_CA_BUNDLES


class DownloadTrustTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bundle = self.root / 'ca-bundle.crt'
        self.bundle.write_text('PRIVATE CERTIFICATE CONTENT MUST NOT BE LOGGED\n')
        self.other = self.root / 'second-bundle.pem'
        self.other.write_text('OTHER CERTIFICATE CONTENT\n')
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.dict(os.environ, {}, clear=True))
        self.context = mock.Mock()
        self.context.verify_mode = ssl.CERT_REQUIRED
        self.context.check_hostname = True
        self.context.cert_store_stats.return_value = {'x509_ca': 3}
        self.create = self.stack.enter_context(mock.patch.object(a.ssl, 'create_default_context', return_value=self.context))
        self.stack.enter_context(mock.patch.object(a, '_SYSTEM_CA_BUNDLES', (str(self.bundle), str(self.other))))
        self.output = io.StringIO()
        self.stack.enter_context(redirect_stdout(self.output))

    def test_selects_first_existing_el7_style_bundle_and_binds_process_only(self):
        report = a.configure_download_trust()
        self.create.assert_called_once_with(cafile=str(self.bundle), capath=None)
        self.assertEqual(os.environ['SSL_CERT_FILE'], str(self.bundle))
        self.assertEqual(report['source'], 'system_ca_bundle')
        self.assertEqual(report['trusted_ca_certificates'], 3)
        self.assertTrue(report['certificate_verification_required'])
        self.assertTrue(report['hostname_verification_required'])
        self.assertNotIn('PRIVATE CERTIFICATE CONTENT', self.output.getvalue())
        self.assertEqual(self.bundle.read_text(), 'PRIVATE CERTIFICATE CONTENT MUST NOT BE LOGGED\n')

    def test_valid_explicit_file_is_preserved_and_custom_path_not_logged(self):
        os.environ['SSL_CERT_FILE'] = str(self.other)
        report = a.configure_download_trust()
        self.create.assert_called_once_with(cafile=str(self.other), capath=None)
        self.assertEqual(os.environ['SSL_CERT_FILE'], str(self.other))
        self.assertEqual(report['source'], 'SSL_CERT_FILE')
        self.assertIsNone(report['system_bundle'])
        self.assertNotIn(str(self.other), self.output.getvalue())

    def test_explicit_paper_bundle_is_validated_and_selected_without_writing_files(self):
        os.environ['PAPER1_CA_BUNDLE'] = str(self.other)
        before = self.other.read_bytes()
        report = a.configure_download_trust()
        self.assertEqual(report['source'], 'PAPER1_CA_BUNDLE')
        self.assertEqual(os.environ['SSL_CERT_FILE'], str(self.other))
        self.assertEqual(self.other.read_bytes(), before)
        self.assertNotIn(str(self.other), self.output.getvalue())

    def test_invalid_explicit_file_or_directory_is_not_silently_replaced(self):
        for key in ('SSL_CERT_FILE', 'SSL_CERT_DIR', 'PAPER1_CA_BUNDLE'):
            for value in ('', str(self.root / 'missing')):
                with self.subTest(key=key, value=value), mock.patch.dict(os.environ, {key: value}, clear=True):
                    with self.assertRaisesRegex(ValueError, 'Invalid explicit download CA path: ' + key):
                        a.configure_download_trust()
                    self.assertEqual(os.environ[key], value)
                    self.create.assert_not_called()

    def test_explicit_hashed_directory_is_accepted_with_lazy_ca_loading(self):
        directory = self.root / 'certs'
        directory.mkdir()
        (directory / '0123abcd.0').write_text('SYNTHETIC HASHED CA')
        os.environ['SSL_CERT_DIR'] = str(directory)
        self.context.cert_store_stats.return_value = {'x509_ca': 0}
        report = a.configure_download_trust()
        self.create.assert_called_once_with(cafile=None, capath=str(directory))
        self.assertEqual(report['source'], 'SSL_CERT_DIR')
        self.assertTrue(report['hashed_ca_directory_available'])
        self.assertNotIn('SSL_CERT_FILE', os.environ)
        self.assertEqual(os.environ['SSL_CERT_DIR'], str(directory))

    def test_no_system_bundle_uses_valid_python_default_store(self):
        with mock.patch.object(a, '_SYSTEM_CA_BUNDLES', ()), \
             mock.patch.object(a.ssl, 'get_default_verify_paths', return_value=SimpleNamespace(capath=None)):
            report = a.configure_download_trust()
        self.create.assert_called_once_with(cafile=None, capath=None)
        self.assertEqual(report['source'], 'python_default')
        self.assertNotIn('SSL_CERT_FILE', os.environ)

    def test_unparseable_or_empty_store_never_disables_verification(self):
        self.create.side_effect = ssl.SSLError('PRIVATE CA CONTENT')
        with self.assertRaisesRegex(ValueError, 'CA store could not be loaded'):
            a.configure_download_trust()
        self.assertNotIn('SSL_CERT_FILE', os.environ)
        self.create.side_effect = None
        self.context.cert_store_stats.return_value = {'x509_ca': 0}
        with self.assertRaisesRegex(ValueError, 'No trusted roots'):
            a.configure_download_trust()
        self.assertNotIn('SSL_CERT_FILE', os.environ)
        self.assertNotIn('PRIVATE', self.output.getvalue())

    def test_context_requires_certificate_and_hostname_verification(self):
        for field, value in (('verify_mode', ssl.CERT_NONE), ('check_hostname', False)):
            with self.subTest(field=field), mock.patch.object(self.context, field, value):
                with self.assertRaisesRegex(ValueError, 'verify certificates and hostnames'):
                    a.configure_download_trust()
                self.assertNotIn('SSL_CERT_FILE', os.environ)

    def test_offline_publish_never_configures_trust_or_opens_network(self):
        raw = self.root / 'raw'
        with mock.patch.object(a, 'configure_download_trust', side_effect=AssertionError('Offline path must not touch trust')), \
             mock.patch.object(a, 'publish_offline', return_value=True), \
             mock.patch.object(a, 'network_payloads_ready', return_value=True), \
             mock.patch.object(a.urllib.request, 'build_opener', side_effect=AssertionError('No network')):
            self.assertEqual(a.main(['--raw-dir', str(raw), '--offline-publish']), 0)
        self.assertNotIn('SSL_CERT_FILE', os.environ)

    def test_canonical_probe_timeout_is_shorter_without_changing_alias_range(self):
        with mock.patch.object(a.urllib.request, 'build_opener') as build:
            a._open_no_redirect('https://bnci-horizon-2020.eu/database/data-sets/001-2014/A01E.mat')
            self.assertEqual(build.return_value.open.call_args.kwargs['timeout'], 8)
            a._open_no_redirect('https://lampx.tugraz.at/~bci/database/001-2014/A01E.mat', 5)
            self.assertEqual(build.return_value.open.call_args.kwargs['timeout'], 60)
            request = build.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header('Range'), 'bytes=5-')

    def test_real_child_ca_binding_does_not_mutate_parent_environment(self):
        env = dict(os.environ)
        code = ('import json,os; from hpcmi.acquire import configure_download_trust; '
                'd=configure_download_trust(); '
                'print(json.dumps({"file":os.environ.get("SSL_CERT_FILE"),"source":d["source"]}))')
        result = subprocess.run([sys.executable, '-c', code], cwd=Path(a.__file__).resolve().parents[1],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(report['source'], 'system_ca_bundle')
        self.assertIn(report['file'], SYSTEM_CA_CANDIDATES)
        self.assertNotIn('SSL_CERT_FILE', os.environ)


if __name__ == '__main__':
    unittest.main()
