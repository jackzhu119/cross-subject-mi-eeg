"""Independent source failures, using synthetic callbacks and no EEG/network."""
from contextlib import ExitStack, redirect_stdout
import errno
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import urllib.error

from hpcmi import acquire as a
from hpcmi import login_pipeline


class TransferIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raw = Path(self.temp.name) / 'raw'
        self.raw.mkdir()
        self.partial = self.raw / 'yang/preserved.compressed.part'
        self.partial.parent.mkdir()
        self.partial.write_bytes(b'previous compressed bytes')
        self.attempt = 'a' * 32
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.output = self.stack.enter_context(redirect_stdout(io.StringIO()))
        self.stack.enter_context(mock.patch.dict(os.environ, {'PAPER1_TRANSFER_ATTEMPT': self.attempt}))
        self.trust = self.stack.enter_context(mock.patch.object(a, 'configure_download_trust'))
        self.complete, self.actions, self.calls = set(), {'bnci': 0, 'dreyer': 0}, []
        self.stack.enter_context(mock.patch.object(a, '_pinned_native_ready',
             side_effect=lambda root, dataset: dataset in self.complete))
        def native(dataset, root, progress=None):
            self.calls.append(dataset)
            if dataset not in self.complete:
                self.actions[dataset] += 1
                self.complete.add(dataset)
            if progress:
                progress(18 if dataset == 'bnci' else 174, 18 if dataset == 'bnci' else 174)
        self.native = self.stack.enter_context(mock.patch.object(a, 'acquire_pinned', side_effect=native))
        self.yang = self.stack.enter_context(mock.patch.object(a, 'acquire_yang_transport'))
        self.quick = self.stack.enter_context(mock.patch.object(a, 'quick_raw_ready', return_value=False))
        self.ready = self.stack.enter_context(mock.patch.object(a, 'network_payloads_ready', return_value=False))

    def main(self, dataset='all'):
        return a.main(['--raw-dir', str(self.raw), '--transport-only', '--dataset', dataset])

    def http_error(self, status):
        return urllib.error.HTTPError('https://PRIVATE.invalid/object?signature=PRIVATE', status,
                                      'PRIVATE response', {}, None)

    def status(self):
        return json.loads((self.raw / 'transport_status.json').read_text())

    def test_yang_503_does_not_block_dreyer_or_invent_yang_completion(self):
        def unavailable(root, progress=None):
            self.calls.append('yang')
            progress(0, 312)
            raise self.http_error(503)
        self.yang.side_effect = unavailable
        with self.assertRaises(a.DatasetTransportFailure) as caught:
            self.main()
        self.assertEqual(self.calls, ['bnci', 'yang', 'dreyer'])
        self.assertEqual(self.status()['completed_objects'], 192)
        self.assertEqual(self.status()['total_objects'], 504)
        self.assertEqual(self.status()['completed_by_dataset'], {'bnci': 18, 'yang': 0, 'dreyer': 174})
        failure = self.raw / '.dataset-transfer-failures' / (self.attempt + '-yang.json')
        data = failure.read_bytes()
        self.assertEqual(json.loads(data)['http_status'], 503)
        self.assertNotIn(b'PRIVATE', data)
        self.assertNotIn('PRIVATE', self.output.getvalue())
        top = a.record_transport_failure(caught.exception, ['--raw-dir', str(self.raw)],
                                        {'PAPER1_TRANSFER_ATTEMPT': self.attempt})
        report = json.loads(top.read_text())
        self.assertTrue(login_pipeline._network_retryable(report, self.attempt))
        self.assertEqual(report['failed_datasets'], ['yang'])
        self.assertFalse((self.raw / 'network_payloads_ready.json').exists())
        self.ready.assert_not_called()
        self.assertEqual(self.partial.read_bytes(), b'previous compressed bytes')

    def test_hash_or_disk_failure_is_immediate_even_with_network_cause(self):
        for failure in (ValueError('native SHA mismatch'), OSError(errno.ENOSPC, 'disk full')):
            with self.subTest(error=type(failure).__name__):
                self.calls.clear()
                failure.__cause__ = self.http_error(503)
                def fatal(root, progress=None):
                    self.calls.append('yang')
                    progress(2, 312)
                    raise failure
                self.yang.side_effect = fatal
                with self.assertRaises(type(failure)):
                    self.main()
                self.assertEqual(self.calls, ['bnci', 'yang'])
                self.assertLess(self.status()['completed_objects'], 504)
                self.assertFalse((self.raw / '.dataset-transfer-failures').exists())
                self.assertFalse((self.raw / 'network_payloads_ready.json').exists())
                self.assertEqual(self.partial.read_bytes(), b'previous compressed bytes')

    def test_retry_reuses_completed_native_sources_and_keeps_first_failure(self):
        self.yang.side_effect = TimeoutError('synthetic transient')
        with self.assertRaises(a.DatasetTransportFailure):
            self.main()
        old_path = self.raw / '.dataset-transfer-failures' / (self.attempt + '-yang.json')
        old_bytes = old_path.read_bytes()
        self.assertEqual(self.actions, {'bnci': 1, 'dreyer': 1})
        def resume(root, progress=None):
            progress(2, 312)
            progress(312, 312)
            self.complete.add('yang')
        self.yang.side_effect = resume
        self.ready.side_effect = lambda root: self.complete == {'bnci', 'yang', 'dreyer'}
        with mock.patch.dict(os.environ, {'PAPER1_TRANSFER_ATTEMPT': 'b' * 32}):
            self.assertEqual(self.main(), 0)
        self.assertEqual(self.actions, {'bnci': 1, 'dreyer': 1})
        self.assertEqual(self.status()['completed_objects'], 504)
        self.assertEqual(old_path.read_bytes(), old_bytes)
        self.assertEqual(self.partial.read_bytes(), b'previous compressed bytes')
        self.assertTrue(json.loads((self.raw / 'network_payloads_ready.json').read_text())['native_yang_validation_pending'])

    def test_permanent_403_wins_over_transient_503_without_retry_loop(self):
        self.yang.side_effect = self.http_error(503)
        original = self.native.side_effect
        def unavailable(dataset, root, progress=None):
            if dataset == 'dreyer':
                self.calls.append(dataset)
                raise self.http_error(403)
            return original(dataset, root, progress)
        self.native.side_effect = unavailable
        with self.assertRaises(a.DatasetTransportFailure) as caught:
            self.main()
        details = a.safe_error_details(caught.exception)
        self.assertEqual(details['http_status'], 403)
        self.assertEqual(details['failed_datasets'], ['yang', 'dreyer'])
        self.assertFalse(login_pipeline._network_retryable({'attempt_id': self.attempt, **details}, self.attempt))
        self.assertEqual(self.status()['completed_objects'], 18)
        self.assertEqual(len(list((self.raw / '.dataset-transfer-failures').glob('*.json'))), 2)

    def test_single_dataset_selection_never_starts_other_sources(self):
        self.yang.side_effect = self.http_error(403)
        with self.assertRaises(a.DatasetTransportFailure):
            self.main('yang')
        self.native.assert_not_called()
        self.assertEqual(self.status()['completed_objects'], 0)
        self.assertEqual(self.status()['total_objects'], 312)
        self.assertEqual(self.status()['unavailable_datasets'], ['yang'])

    def test_tls_failure_keeps_verification_and_allows_independent_source(self):
        self.yang.side_effect = a.ssl.SSLCertVerificationError(1, 'PRIVATE trust failure')
        with self.assertRaises(a.DatasetTransportFailure) as caught:
            self.main()
        details = a.safe_error_details(caught.exception)
        self.assertEqual(details['category'], 'tls_certificate')
        self.assertEqual(self.status()['completed_objects'], 192)
        self.assertFalse(login_pipeline._network_retryable({'attempt_id': self.attempt, **details}, self.attempt))
        self.trust.assert_called_once()
        self.assertNotIn('PRIVATE', self.output.getvalue())


if __name__ == '__main__':
    unittest.main()
