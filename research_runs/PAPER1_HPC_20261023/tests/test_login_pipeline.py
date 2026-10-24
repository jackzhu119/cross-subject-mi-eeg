"""Login transfer orchestration only; no real network, child, Slurm, or EEG."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from hpcmi.common import atomic_json, read_json
from hpcmi import login_pipeline as p

REAL_LIVE_DRIVER = p._live_driver


class Child:
    def __init__(self, code=0, ticks=1, on_poll=None):
        self.code, self.ticks, self.on_poll = code, ticks, on_poll
        self.signals = []
        self.wait_count = 0

    def poll(self):
        callback, self.on_poll = self.on_poll, None
        if callback:
            callback()
        if self.ticks:
            self.ticks -= 1
            return None
        return self.code

    def wait(self):
        self.wait_count += 1
        return self.code

    def send_signal(self, number):
        self.signals.append(number)
        self.code, self.ticks = 143, 0


class LoginPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'paper1-risk-v1'
        self.paths = {'training_python': sys.executable, 'repository': 'owner/research',
                      'raw_dir': str(self.project / 'raw')}
        atomic_json(self.project / 'config/paths.json', self.paths)
        atomic_json(self.project / 'config/sync.json', {'token_file': str(self.project / 'private-token')})
        self.ledger = self.project / 'state/single_job_submissions.json'
        atomic_json(self.ledger, {'submissions': [{'job_id': '771084', 'status': 'FAILED'}]})
        self.old_ledger = self.ledger.read_bytes()
        self.args = SimpleNamespace(project=str(self.project), python=sys.executable, raw_dir=None,
                      repository='owner/research', wheelhouse=self.project / 'wheels',
                      gpus=2, memory='128G', replace_job='771084', reauthorize=True,
                      restart_transfer=False)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.output = io.StringIO()
        self.stack.enter_context(redirect_stdout(self.output))
        self.stack.enter_context(mock.patch.dict(p.os.environ, {}, clear=True))
        self.stack.enter_context(mock.patch.object(p.time, 'sleep'))
        self.handlers = {}
        def install(number, handler):
            if callable(handler):
                self.handlers[number] = handler
            return signal.SIG_DFL
        self.stack.enter_context(mock.patch.object(p.signal, 'signal', side_effect=install))
        self.quick = self.stack.enter_context(mock.patch('hpcmi.acquire.quick_raw_ready', return_value=True))
        self.ready = self.stack.enter_context(mock.patch('hpcmi.acquire.network_payloads_ready', create=True,
                                                   side_effect=AssertionError('Already-ready inputs need no transport query')))
        self.submit = self.stack.enter_context(mock.patch('hpcmi.submit_single.submit', return_value={
                                  'status': 'SINGLE_JOB_SUBMITTED', 'job_id': '880003'}))
        self.sync = self.stack.enter_context(mock.patch.object(p, 'start_sync', return_value=909))
        self.popen = self.stack.enter_context(mock.patch.object(p.subprocess, 'Popen'))
        self.auth = self.stack.enter_context(mock.patch.object(p.github_sync, 'confirm_credentials',
                                                 return_value=self.project / 'private-token'))
        self.setup = self.stack.enter_context(mock.patch.object(p.cli, 'setup', return_value=self.paths))
        self.route_check = self.stack.enter_context(mock.patch.object(p, '_check_download_route'))
        self.daemon = self.stack.enter_context(mock.patch.object(p.cli, '_daemon', return_value=4321))
        self.live = self.stack.enter_context(mock.patch.object(p, '_live_driver', return_value=None))

    def state(self):
        return read_json(self.project / 'state/login_pipeline_status.json')

    def test_failed_targeted_tls_check_never_stops_old_transfer_or_starts_new(self):
        self.args.restart_transfer = True
        self.route_check.side_effect = RuntimeError('Targeted TLS HEAD failed')
        with mock.patch.object(p, '_restart_transfer_driver') as restart, self.assertRaises(RuntimeError):
            p.start(self.args)
        self.route_check.assert_called_once_with(self.paths)
        restart.assert_not_called()
        self.daemon.assert_not_called()
        self.assertEqual(self.ledger.read_bytes(), self.old_ledger)

    def test_ready_inputs_skip_transfer_and_submit_one_offline_two_gpu_job(self):
        self.assertEqual(p.run(self.args), 0)
        self.popen.assert_not_called()
        self.ready.assert_not_called()
        self.submit.assert_called_once_with(self.project, sys.executable,
             raw_dir=self.paths['raw_dir'], wheelhouse=self.args.wheelhouse,
             repository='owner/research', memory='128G', gpus=2, require_github=True,
             offline_inputs=True, login_sync=True, replace_job='771084')
        self.sync.assert_called_once()
        self.assertEqual(self.state()['stage'], 'offline_gpu_job_submitted')
        self.assertEqual(self.state()['slurm_job_id'], '880003')
        self.assertEqual(self.ledger.read_bytes(), self.old_ledger)

    def test_incomplete_network_inputs_use_transport_only_then_submit(self):
        self.quick.return_value = False
        self.ready.side_effect = [False, True]
        self.popen.return_value = Child(code=0)
        self.assertEqual(p.run(self.args), 0)
        command = self.popen.call_args.args[0]
        self.assertIn('--transport-only', command)
        self.assertNotIn('--offline-publish', command)
        self.assertEqual(command[:4], [sys.executable, '-u', '-m', 'hpcmi.acquire'])
        self.assertEqual(self.popen.call_args.kwargs['stdin'], p.subprocess.DEVNULL)
        self.submit.assert_called_once()
        self.assertEqual(self.ledger.read_bytes(), self.old_ledger)

    def test_transient_transport_retry_gets_new_attempt_and_submits_after_resume(self):
        self.quick.return_value = False
        self.ready.side_effect = [False, True]
        failures = []
        def attempt(command, **kwargs):
            attempt_id = kwargs['env']['PAPER1_TRANSFER_ATTEMPT']
            if len(failures) < 2:
                failure = Path(self.paths['raw_dir']) / '.transport-failures' / (attempt_id + '.json')
                detail = ({'category': 'dns', 'errno': -2, 'error_class': 'OSError'} if not failures
                          else {'category': 'http', 'http_status': 503, 'error_class': 'HTTPError'})
                atomic_json(failure, {'attempt_id': attempt_id, 'causes': [], **detail})
                failures.append(failure)
                return Child(code=1, ticks=0)
            return Child(code=0, ticks=0)
        self.popen.side_effect = attempt
        with mock.patch.object(p, '_wait_network_backoff', return_value=True) as backoff:
            self.assertEqual(p.run(self.args), 0)
        self.assertEqual(self.popen.call_count, 3)
        ids = [call.kwargs['env']['PAPER1_TRANSFER_ATTEMPT'] for call in self.popen.call_args_list]
        self.assertEqual(len(set(ids)), 3)
        for attempt_id in ids:
            self.assertRegex(attempt_id, r'^[0-9a-f]{32}$')
        for call in self.popen.call_args_list:
            self.assertIn('--transport-only', call.args[0])
            self.assertNotIn('--offline-publish', call.args[0])
        self.assertTrue(all(failure.exists() for failure in failures))
        self.assertEqual([call.args[0] for call in backoff.call_args_list], [60, 120])
        self.submit.assert_called_once()
        self.assertEqual(self.ledger.read_bytes(), self.old_ledger)

    def test_hash_disk_auth_tls_and_stale_failure_never_retry(self):
        self.quick.return_value = False
        self.ready.side_effect = None
        self.ready.return_value = False
        cases = [{'category': 'unknown', 'error_class': 'ValueError'},
                 {'category': 'os_error', 'error_class': 'OSError', 'errno': 28},
                 {'category': 'http', 'http_status': 403},
                 {'category': 'tls_certificate', 'ssl_verify_code': 20},
                 {'category': 'dns', 'attempt_id': 'stale-attempt'}]
        for detail in cases:
            with self.subTest(detail=detail):
                def failed(command, **kwargs):
                    attempt_id = kwargs['env']['PAPER1_TRANSFER_ATTEMPT']
                    atomic_json(Path(self.paths['raw_dir']) / '.transport-failures' / (attempt_id + '.json'),
                                {'attempt_id': attempt_id, 'causes': [], **detail})
                    return Child(code=1, ticks=0)
                self.popen.reset_mock()
                self.popen.side_effect = failed
                with mock.patch.object(p, '_wait_network_backoff', side_effect=AssertionError('Fatal input retried')):
                    self.assertEqual(p.run(self.args), 1)
                self.assertEqual(self.popen.call_count, 1)
                self.assertEqual(self.state()['stage'], 'transfer_failed_no_gpu_job_submitted')
                self.assertEqual(self.ledger.read_bytes(), self.old_ledger)
        self.submit.assert_not_called()

    def test_cancel_during_network_backoff_stops_without_another_transfer(self):
        self.quick.return_value = False
        self.ready.side_effect = None
        self.ready.return_value = False
        def timeout(command, **kwargs):
            attempt_id = kwargs['env']['PAPER1_TRANSFER_ATTEMPT']
            atomic_json(Path(self.paths['raw_dir']) / '.transport-failures' / (attempt_id + '.json'),
                        {'attempt_id': attempt_id, 'category': 'timeout', 'causes': []})
            return Child(code=1, ticks=0)
        self.popen.side_effect = timeout
        p.time.sleep.side_effect = lambda seconds: self.handlers[signal.SIGTERM](signal.SIGTERM, None)
        self.assertEqual(p.run(self.args), 143)
        self.assertEqual(self.popen.call_count, 1)
        self.submit.assert_not_called()
        self.assertEqual(self.state()['stage'], 'cancelled_no_gpu_job_submitted')
        self.assertEqual(self.ledger.read_bytes(), self.old_ledger)

    def test_transfer_failure_preserves_old_job_and_never_submits(self):
        self.quick.return_value = False
        self.ready.side_effect = None
        self.ready.return_value = False
        self.popen.return_value = Child(code=28)
        self.assertEqual(p.run(self.args), 28)
        self.submit.assert_not_called()
        self.sync.assert_not_called()
        self.assertEqual(self.state()['stage'], 'transfer_failed_no_gpu_job_submitted')
        self.assertEqual(self.state()['transfer_exit_code'], 28)
        self.assertEqual(self.ledger.read_bytes(), self.old_ledger)

    def test_held_replacement_is_never_reported_as_a_released_gpu_job(self):
        self.submit.return_value = {'status': 'REPLACEMENT_HELD_OLD_JOB_ACTIVE', 'job_id': '880003',
                                    'old_job_id': '771084', 'released': False}
        self.assertEqual(p.run(self.args), 0)
        self.assertEqual(self.state()['stage'], 'replacement_held_old_job_active')
        self.assertFalse(self.state()['gpu_execution_verified'])
        self.assertEqual(self.ledger.read_bytes(), self.old_ledger)

    def test_cancel_forwards_term_and_never_submits_or_requeues(self):
        self.quick.return_value = False
        self.ready.side_effect = None
        self.ready.return_value = False
        child = Child(on_poll=lambda: self.handlers[signal.SIGTERM](signal.SIGTERM, None))
        self.popen.return_value = child
        self.assertEqual(p.run(self.args), 143)
        self.assertEqual(child.signals, [signal.SIGTERM])
        self.submit.assert_not_called()
        self.sync.assert_not_called()
        self.daemon.assert_not_called()
        self.assertEqual(self.state()['stage'], 'cancelled_no_gpu_job_submitted')
        self.assertEqual(self.ledger.read_bytes(), self.old_ledger)

    def test_unexpected_progress_error_terminates_and_reaps_only_owned_transfer(self):
        self.quick.return_value = False
        self.ready.side_effect = None
        self.ready.return_value = False
        child = Child(ticks=100)
        self.popen.return_value = child
        progress = Path(self.paths['raw_dir']) / 'transport_status.json'
        progress.parent.mkdir(parents=True)
        progress.write_text('{invalid json')
        with redirect_stderr(io.StringIO()):
            self.assertEqual(p.run(self.args), 1)
        self.assertEqual(child.signals, [signal.SIGTERM])
        self.assertEqual(child.wait_count, 1)
        self.submit.assert_not_called()
        self.sync.assert_not_called()
        self.assertEqual(self.state()['stage'], 'failed_existing_data_and_jobs_retained')
        self.assertEqual(self.state()['error_class'], 'JSONDecodeError')
        self.assertEqual(self.ledger.read_bytes(), self.old_ledger)

    def test_cancel_exit_race_is_still_a_cancel_without_submission(self):
        self.quick.return_value = False
        self.ready.side_effect = None
        self.ready.return_value = False
        child = Child(ticks=100, on_poll=lambda: self.handlers[signal.SIGTERM](signal.SIGTERM, None))
        def exited_before_signal(number):
            child.code, child.ticks = 0, 0
            raise ProcessLookupError()
        child.send_signal = mock.Mock(side_effect=exited_before_signal)
        self.popen.return_value = child
        self.assertEqual(p.run(self.args), 143)
        child.send_signal.assert_called_once_with(signal.SIGTERM)
        self.assertEqual(child.wait_count, 1)
        self.submit.assert_not_called()
        self.assertEqual(self.state()['stage'], 'cancelled_no_gpu_job_submitted')

    def test_cli_defaults_use_two_gpus_and_128g_total_memory(self):
        with mock.patch.object(p, 'start', return_value=0) as start:
            self.assertEqual(p.main(['start']), 0)
        parsed = start.call_args.args[0]
        self.assertEqual(parsed.gpus, 2)
        self.assertEqual(parsed.memory, '128G')

    def test_foreground_reauthorization_failure_starts_no_background_process(self):
        self.auth.side_effect = p.github_sync.CredentialError('test rejected')
        with self.assertRaises(p.github_sync.CredentialError):
            p.start(self.args)
        self.auth.assert_called_once_with('owner/research', self.project.name,
                                         force=True, require_verified=True)
        self.daemon.assert_not_called()
        self.sync.assert_not_called()
        self.popen.assert_not_called()
        self.submit.assert_not_called()
        self.assertEqual(self.ledger.read_bytes(), self.old_ledger)

    def test_live_driver_is_reused_after_fresh_authorization_without_duplicate(self):
        self.live.return_value = {'pid': 4321, 'stage': 'login_transport_only'}
        self.assertEqual(p.start(self.args), 0)
        self.auth.assert_called_once_with('owner/research', self.project.name,
                                         force=True, require_verified=True)
        self.daemon.assert_not_called()
        self.sync.assert_not_called()
        self.submit.assert_not_called()
        self.assertIn('EXISTING_LOGIN_PIPELINE_REUSED', self.output.getvalue())

    def test_restart_transfer_waits_for_owned_old_driver_and_preserves_files(self):
        self.args.restart_transfer = True
        old = {'pid': 4310, 'stage': 'login_transport_only', 'completed_objects': 2}
        new = {'pid': 4321, 'stage': 'login_transport_only'}
        self.live.side_effect = [old, dict(old), None, new, new]
        partial = self.project / 'raw/bnci/A01E.mat.part'
        partial.parent.mkdir(parents=True)
        partial.write_bytes(b'Already downloaded native bytes retained')
        log = self.project / 'logs/login-pipeline.log'
        log.parent.mkdir()
        log.write_bytes(b'Original transfer failure log\n')
        with mock.patch.object(p.os, 'kill') as kill:
            self.assertEqual(p.start(self.args), 0)
        kill.assert_called_once_with(4310, signal.SIGTERM)
        self.auth.assert_called_once_with('owner/research', self.project.name,
                                         force=True, require_verified=True)
        self.daemon.assert_called_once()
        self.assertNotIn('--restart-transfer', self.daemon.call_args.args[2])
        snapshots = list((self.project / 'state/login-transfer-restarts').glob('*.json'))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(read_json(snapshots[0])['previous_status'], old)
        self.assertEqual(partial.read_bytes(), b'Already downloaded native bytes retained')
        self.assertEqual(log.read_bytes(), b'Original transfer failure log\n')
        self.assertEqual(self.ledger.read_bytes(), self.old_ledger)
        self.submit.assert_not_called()

    def test_restart_transfer_never_signals_a_changed_pid(self):
        self.args.restart_transfer = True
        old = {'pid': 4310, 'stage': 'login_transport_only'}
        current = {'pid': 4400, 'stage': 'network_retry_wait'}
        self.live.side_effect = [old, current]
        with mock.patch.object(p.os, 'kill') as kill:
            self.assertEqual(p.start(self.args), 0)
        kill.assert_not_called()
        self.daemon.assert_not_called()
        self.sync.assert_not_called()
        self.assertEqual(self.ledger.read_bytes(), self.old_ledger)

    def test_restart_transfer_checks_actual_uid_and_never_signals_foreign_owner(self):
        state = {'pid': p.os.getpid(), 'stage': 'login_transport_only'}
        atomic_json(self.project / 'state/login_pipeline_status.json', state)
        current_uid = p.os.getuid()
        with mock.patch.object(p, '_live_driver', REAL_LIVE_DRIVER), \
             mock.patch.object(p.os, 'getuid', return_value=current_uid + 1), \
             mock.patch.object(p.os, 'kill') as kill:
            self.assertIsNone(p._restart_transfer_driver(self.project, state))
        kill.assert_not_called()
        self.assertFalse((self.project / 'state/login-transfer-restarts').exists())
        self.assertEqual(self.ledger.read_bytes(), self.old_ledger)

    def test_restart_transfer_preserves_submission_and_gpu_stages(self):
        self.args.restart_transfer = True
        for stage in ('network_payloads_ready_submitting_offline_gpu_job',
                      'offline_gpu_job_submitted', 'replacement_held_old_job_active'):
            with self.subTest(stage=stage):
                self.live.return_value = {'pid': 4310, 'stage': stage}
                with mock.patch.object(p.os, 'kill') as kill:
                    self.assertEqual(p.start(self.args), 0)
                kill.assert_not_called()
        self.daemon.assert_not_called()
        self.sync.assert_not_called()
        self.submit.assert_not_called()
        self.assertEqual(self.ledger.read_bytes(), self.old_ledger)

    def test_restart_transfer_timeout_never_starts_another_driver(self):
        self.args.restart_transfer = True
        self.live.return_value = {'pid': 4310, 'stage': 'network_retry_wait'}
        with mock.patch.object(p.os, 'kill') as kill, \
             mock.patch.object(p.time, 'monotonic', side_effect=[0, 16]):
            with self.assertRaisesRegex(RuntimeError, 'Previous login transfer has not exited'):
                p.start(self.args)
        kill.assert_called_once_with(4310, signal.SIGTERM)
        self.daemon.assert_not_called()
        self.sync.assert_not_called()
        self.submit.assert_not_called()
        self.assertEqual(self.ledger.read_bytes(), self.old_ledger)

    def test_live_new_driver_startup_receives_exact_request(self):
        self.live.side_effect = [None, {'pid': 4321, 'stage': 'login_transport_only'},
                                 {'pid': 4321, 'stage': 'login_transport_only'}]
        self.assertEqual(p.start(self.args), 0)
        self.sync.assert_called_once()
        self.daemon.assert_called_once_with(self.project, 'hpcmi.login_pipeline', [
             'run', '--project', str(self.project), '--gpus', '2', '--memory', '128G',
             '--replace-job', '771084', '--wheelhouse', str(self.args.wheelhouse)], 'login-pipeline.log')
        self.assertIn('LOGIN_TRANSFER_PIPELINE_STARTED', self.output.getvalue())
        self.assertIn('"slurm_job_submitted": false', self.output.getvalue())

    def test_fast_child_exit_is_accepted_only_as_saved_submission_not_training(self):
        def fast_child(*args, **kwargs):
            atomic_json(self.project / 'state/login_pipeline_status.json', {'pid': 4321,
                      'stage': 'offline_gpu_job_submitted', 'slurm_job_id': '880003'})
            return 4321
        self.daemon.side_effect = fast_child
        self.assertEqual(p.start(self.args), 0)
        self.assertIn('LOGIN_PIPELINE_FINISHED_GPU_JOB_SUBMITTED', self.output.getvalue())
        self.assertIn('"training_started_verified": false', self.output.getvalue())
        self.assertNotIn('LOGIN_TRANSFER_PIPELINE_STARTED', self.output.getvalue())

    def test_fast_child_failure_is_reported_before_startup_timeout(self):
        def failed_child(*args, **kwargs):
            atomic_json(self.project / 'state/login_pipeline_status.json', {'pid': 4321,
                      'stage': 'transfer_failed_no_gpu_job_submitted', 'transfer_exit_code': 28})
            return 4321
        self.daemon.side_effect = failed_child
        with self.assertRaisesRegex(RuntimeError, 'transfer_failed_no_gpu_job_submitted'):
            p.start(self.args)
        self.submit.assert_not_called()
        self.assertNotIn('LOGIN_TRANSFER_PIPELINE_STARTED', self.output.getvalue())

    def test_fast_child_held_result_preserves_old_job_without_startup_timeout(self):
        def held_child(*args, **kwargs):
            atomic_json(self.project / 'state/login_pipeline_status.json', {'pid': 4321,
                      'stage': 'replacement_held_old_job_active', 'slurm_job_id': '880003',
                      'submission_status': 'REPLACEMENT_HELD_OLD_JOB_ACTIVE'})
            return 4321
        self.daemon.side_effect = held_child
        self.assertEqual(p.start(self.args), 0)
        self.assertIn('LOGIN_PIPELINE_FINISHED_EXISTING_JOB_PRESERVED', self.output.getvalue())
        self.assertIn('"slurm_job_submitted": false', self.output.getvalue())
        self.assertIn('"manual_action_required": true', self.output.getvalue())


if __name__ == '__main__':
    unittest.main()
