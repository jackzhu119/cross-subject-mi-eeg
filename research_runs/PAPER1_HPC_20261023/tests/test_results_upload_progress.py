"""Actual progress counters for synthetic result export/publication only."""
import contextlib
import io
import unittest
from unittest import mock

import test_results_publication as fixtures

b = fixtures.b
FakeGitHub = fixtures.FakeGitHub


class ProgressTests(unittest.TestCase):
    setUp = fixtures.BundleTests.setUp
    write = fixtures.BundleTests.write
    read = fixtures.BundleTests.read

    def test_bundle_progress_reports_real_counts_and_preserves_archive_bytes(self):
        events = []
        bundle = b.build_bundle(self.project, self.out,
                                progress=lambda stage, **values: events.append((stage, values)))
        repeated = b.build_bundle(self.project, self.out)
        self.assertEqual(bundle['sha256'], repeated['sha256'])
        phases = [stage for stage, values in events]
        for stage in ('checking_saved_results', 'hashing_result_files', 'packing_result_files',
                      'result_evidence_exported'):
            self.assertIn(stage, phases)
        checking = [values for stage, values in events if stage == 'checking_saved_results']
        self.assertEqual(checking[0]['completed_tasks'], 0)
        self.assertEqual(checking[-1]['completed_tasks'], 90)
        self.assertEqual(checking[-1]['selected_evaluation_summaries'], 105)
        self.assertEqual(checking[-1]['prediction_shards'], 105)
        for stage in ('hashing_result_files', 'packing_result_files'):
            values = [row for phase, row in events if phase == stage]
            self.assertEqual(values[0]['completed_files'], 0)
            self.assertEqual(values[-1]['completed_files'], bundle['manifest']['selected_file_count'])
            self.assertEqual(values[-1]['processed_bytes'],
                             sum(row['bytes'] for row in bundle['manifest']['selected_files']))
        self.assertEqual(events[-1][1]['sha256'], bundle['sha256'])

    def test_publication_progress_covers_blob_commit_and_verified_readback(self):
        bundle = b.build_bundle(self.project, self.out)
        events = []
        FakeGitHub.calls = []
        FakeGitHub.corrupt_readback = False
        with mock.patch.object(b, 'GitHubPublisher', FakeGitHub), contextlib.redirect_stdout(io.StringIO()):
            receipt = b.publish_bundle(self.project, bundle, 'FAKE_TOKEN',
                                      progress=lambda stage, **values: events.append((stage, values)))
        self.assertEqual([stage for stage, values in events], [
            'verifying_local_result_bundle', 'preparing_result_branch', 'uploading_result_bundle',
            'committing_result_evidence', 'reading_back_result_bundle', 'result_bundle_readback_verified'])
        self.assertTrue(receipt['full_archive_readback_verified'])
        self.assertTrue(all(values['archive_bytes'] == bundle['bytes'] for stage, values in events))

    def test_failed_export_never_reports_packed_or_verified_completion(self):
        (self.project / 'outputs/runs' / self.tasks[0]['id'] / 'complete.json').unlink()
        events = []
        with self.assertRaises(ValueError):
            b.build_bundle(self.project, self.out,
                           progress=lambda stage, **values: events.append((stage, values)))
        self.assertTrue(events)
        self.assertFalse(any(stage in {'result_evidence_exported', 'result_bundle_readback_verified'}
                             for stage, values in events))


if __name__ == '__main__':
    unittest.main()
