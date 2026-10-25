"""Fake scheduler/processes only; migration never starts fits or reads EEG."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from hpcmi.common import atomic_json, read_json
from hpcmi import login_pipeline as login
from hpcmi import yang_privacy as privacy
from hpcmi import yang_privacy_activation as activation


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'paper1-risk-v1'
        self.raw = self.project / 'raw'
        for name in ('bnci', 'yang', 'dreyer'):
            (self.raw / name).mkdir(parents=True)
        self.partial = self.raw / 'dreyer/native.edf.part'
        self.partial.write_bytes(b'prior partial')
        self.failure = self.raw / 'yang/old-failure.json'
        self.failure.write_bytes(b'old source failure')
        self.paths = {'project': str(self.project), 'raw_dir': str(self.raw),
                      'data_dir': str(self.project / 'data/prepared'),
                      'cache_dir': str(self.project / 'data/eligible_npz'),
                      'training_python': sys.executable, 'repository': 'owner/research'}
        atomic_json(self.project / 'config/paths.json', self.paths)
        atomic_json(self.project / 'config/data_path.json', {'data_dir': self.paths['data_dir']})
        self.ledger = self.project / 'state/single_job_submissions.json'
        atomic_json(self.ledger, {'schema_version': 1, 'submissions': [
            {'job_id': '771084', 'job_name': 'p1-single-old', 'status': 'FAILED'}]})
        self.old_ledger = self.ledger.read_bytes()
        self.queue = mock.Mock(return_value=subprocess.CompletedProcess([], 0, '', ''))

    def test_explicit_migration_reuses_native_and_partial_files_and_retains_old_paths(self):
        current = activation.activate(self.project, self.paths, runner=self.queue)
        self.assertEqual(self.queue.call_count, 1)
        self.assertEqual(self.queue.call_args.args[0][0], 'squeue')
        new = self.project / 'raw-nemar-privacy-v1'
        self.assertEqual(current['raw_dir'], str(new))
        self.assertEqual(current['cache_dir'], self.paths['cache_dir'])
        self.assertEqual(current['data_dir'], str(self.project / 'data/prepared-nemar-privacy-v1'))
        self.assertTrue((new / 'bnci').is_symlink())
        self.assertEqual((new / 'dreyer/native.edf.part').read_bytes(), b'prior partial')
        self.assertEqual(self.failure.read_bytes(), b'old source failure')
        marker = read_json(new / 'yang/.source-profile.json')
        self.assertEqual(marker['approval_mode'], 'explicit_operator_cli_selection')
        self.assertTrue(privacy.is_active(new / 'yang'))
        history = self.project / 'state/source-profile-history' / privacy.PROFILE
        self.assertEqual(read_json(history / 'paths.before.json'), self.paths)
        self.assertEqual(self.ledger.read_bytes(), self.old_ledger)

    def test_repeated_profile_resume_preserves_current_checkpoint_and_avoids_rescans(self):
        current = activation.activate(self.project, self.paths, runner=self.queue)
        checkpoint = self.project / 'outputs/runs/new-fit/checkpoints/latest.pt'
        checkpoint.parent.mkdir(parents=True)
        checkpoint.write_bytes(b'current-version checkpoint')
        self.queue.reset_mock()
        self.assertEqual(activation.activate(self.project, current, runner=self.queue), current)
        self.queue.assert_not_called()
        self.assertEqual(checkpoint.read_bytes(), b'current-version checkpoint')
        self.assertEqual(activation.effective_raw_dir(self.project, str(self.raw)), current['raw_dir'])
        with self.assertRaises(ValueError):
            activation.effective_raw_dir(self.project, str(self.raw), 'original')

    def test_prior_scientific_outputs_block_first_migration_without_path_changes(self):
        for relative in ('state/data_prepared.json', 'outputs/runs/old-fit/complete.json',
                         'outputs/runs/old-fit/checkpoints/latest.pt'):
            with self.subTest(relative=relative):
                path = self.project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'old evidence')
                before = (self.project / 'config/paths.json').read_bytes()
                with self.assertRaises(RuntimeError):
                    activation.activate(self.project, self.paths, runner=self.queue)
                self.assertEqual((self.project / 'config/paths.json').read_bytes(), before)
                self.assertFalse((self.project / 'raw-nemar-privacy-v1').exists())
                self.assertEqual(path.read_bytes(), b'old evidence')
                path.unlink()
        self.queue.assert_not_called()

    def test_same_contract_runtime_revision_does_not_reinitialize_current_checkpoint(self):
        current = activation.activate(self.project, self.paths, runner=self.queue)
        checkpoint = self.project / 'outputs/runs/new-fit/checkpoints/latest.pt'
        checkpoint.parent.mkdir(parents=True)
        checkpoint.write_bytes(b'current checkpoint remains')
        new_identity = {**privacy.current_identity(), 'adapter_sha256': 'f' * 64}
        self.queue.reset_mock()
        with mock.patch.object(privacy, 'current_identity', return_value=new_identity):
            self.assertEqual(activation.activate(self.project, current, runner=self.queue), current)
        self.queue.assert_not_called()
        self.assertEqual(checkpoint.read_bytes(), b'current checkpoint remains')
        self.assertNotEqual(current['yang_source_identity']['adapter_sha256'], new_identity['adapter_sha256'])

    def test_project_job_is_not_cancelled_and_other_paper_does_not_block(self):
        self.queue.return_value = subprocess.CompletedProcess([], 0,
            '8900|p1-single-old|zhuziyuan|PENDING|hpc_gpu|' + str(self.project) + '|Resources\n', '')
        with self.assertRaisesRegex(RuntimeError, 'scheduler job retained'):
            activation.activate(self.project, self.paths, runner=self.queue)
        self.assertFalse((self.project / 'raw-nemar-privacy-v1').exists())
        self.assertEqual(self.ledger.read_bytes(), self.old_ledger)
        self.queue.return_value = subprocess.CompletedProcess([], 0,
            '8901|paper2-training|zhuziyuan|RUNNING|hpc_gpu|/some/other/project|None\n', '')
        activation.activate(self.project, self.paths, runner=self.queue)
        self.assertTrue(all(call.args[0][0] == 'squeue' for call in self.queue.call_args_list))

    def test_existing_unknown_destinations_and_wrong_marker_are_retained(self):
        new = self.project / 'raw-nemar-privacy-v1'
        (new / 'yang').mkdir(parents=True)
        (new / 'yang/unknown.part').write_bytes(b'owned elsewhere')
        with self.assertRaises(ValueError):
            activation.activate(self.project, self.paths, runner=self.queue)
        self.assertEqual((new / 'yang/unknown.part').read_bytes(), b'owned elsewhere')

    def test_login_optin_checks_new_route_after_owned_transfer_exit_and_migration(self):
        args = SimpleNamespace(project=str(self.project), python=sys.executable, raw_dir=str(self.raw),
            repository='owner/research', reauthorize=False, restart_transfer=False,
            yang_source='nemar-privacy-v1', gpus=2, memory='128G', replace_job=None, wheelhouse=None)
        observed = {'pid': 123, 'stage': 'login_transport_only'}
        current = {**self.paths, 'raw_dir': str(self.project / 'raw-nemar-privacy-v1')}
        events = []
        with mock.patch.dict(login.os.environ, {}, clear=True), \
             mock.patch.object(login.cli, 'setup', return_value=self.paths), \
             mock.patch.object(login.github_sync, 'confirm_credentials', return_value=self.project / 'token'), \
             mock.patch.object(login, '_live_driver', side_effect=[observed,
                 {'pid': 456, 'stage': 'login_transport_only'}, {'pid': 456, 'stage': 'login_transport_only'}]), \
             mock.patch.object(login, '_restart_transfer_driver', side_effect=lambda *a: events.append('old_transfer_exit')), \
             mock.patch.object(activation, 'activate', side_effect=lambda *a: events.append('activate') or current), \
             mock.patch.object(login, '_check_download_route', side_effect=lambda p: events.append(('route', p['raw_dir']))), \
             mock.patch.object(login, 'start_sync'), \
             mock.patch.object(login.cli, '_daemon', return_value=456), redirect_stdout(io.StringIO()):
            self.assertEqual(login.start(args), 0)
        self.assertEqual(events, ['old_transfer_exit', 'activate', ('route', current['raw_dir'])])

    def test_cli_accepts_source_selection_only_as_explicit_choice(self):
        with mock.patch.object(login, 'start', return_value=0) as start:
            self.assertEqual(login.main(['start', '--yang-source', 'nemar-privacy-v1']), 0)
        self.assertEqual(start.call_args.args[0].yang_source, 'nemar-privacy-v1')


if __name__ == '__main__':
    unittest.main()
