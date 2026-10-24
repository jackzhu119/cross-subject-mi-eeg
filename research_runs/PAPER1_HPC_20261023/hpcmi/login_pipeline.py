"""Login-side transfer and reporting; one offline multi-GPU Slurm job follows.

No EEG decompression, preprocessing or fitting runs in this module. Downloads
use the existing frozen source manifests; model inputs are published on compute.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback
import uuid

from . import cli, github_sync
from .common import atomic_json, exclusive_lock, read_json, utc_now


def emit(project, stage, **details):
    state = {"stage": stage, "updated_at_utc": utc_now(), "pid": os.getpid(),
             "scientific_fits_started_by_login_process": 0, **details}
    atomic_json(Path(project) / "state/login_pipeline_status.json", state)
    print(json.dumps(state, allow_nan=False), flush=True)
    return state


def _live_driver(project):
    try:
        state = read_json(project / "state/login_pipeline_status.json")
        pid = state["pid"]
        if type(pid) is not int or pid < 2:
            return None
        root = Path('/proc') / str(pid)
        if root.stat().st_uid != os.getuid():
            return None
        args = [value.decode() for value in (root / 'cmdline').read_bytes().split(b'\0') if value]
        if '-m' not in args or args[args.index('-m') + 1] != 'hpcmi.login_pipeline':
            return None
        if 'run' not in args or '--project' not in args or Path(args[args.index('--project') + 1]).resolve() != project:
            return None
        return state
    except (OSError, ValueError, KeyError, IndexError, UnicodeError):
        return None


def start_sync(project, paths, token_path):
    branch = 'hpc/' + project.name
    return cli._daemon(project, 'hpcmi.github_sync', [
        '--project', str(project), '--repository', paths['repository'], '--branch', branch,
        '--path', 'hpc_status/' + project.name + '/status.json', '--token-file', str(token_path),
        '--interval', '180'], 'github-sync-login.log')


def _network_retryable(failure, attempt_id):
    if not isinstance(failure, dict) or failure.get('attempt_id') != attempt_id:
        return False
    rows = failure.get('causes', [])
    if not isinstance(rows, list) or failure.get('category') in {'tls', 'tls_certificate'}:
        return False
    causes = [failure] + [row for row in rows if isinstance(row, dict)]
    if any(row.get('errno') in {1, 2, 5, 13, 28, 30, 122} or 'ssl_verify_code' in row
           or row.get('error_class') in {'SSLError', 'SSLCertVerificationError'} for row in causes):
        return False
    status = failure.get('http_status')
    if status is not None:
        return type(status) is int and status in {408, 429, 500, 502, 503, 504}
    return failure.get('category') in {'dns', 'timeout', 'connection', 'incomplete_read'}


def _wait_network_backoff(seconds, is_stopped):
    for _ in range(seconds):
        if is_stopped():
            return False
        time.sleep(1)
    return not is_stopped()


def _arguments(args):
    result = ['--project', str(Path(args.project).expanduser().resolve()), '--gpus', str(args.gpus),
              '--memory', args.memory]
    if args.replace_job:
        result += ['--replace-job', args.replace_job]
    if args.wheelhouse:
        result += ['--wheelhouse', str(args.wheelhouse)]
    return result


def start(args):
    if os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Start the login transfer pipeline outside a Slurm allocation')
    project = Path(args.project).expanduser().resolve()
    # The official API's IPv4 curl route has been observed on this school login
    # host. Credentials remain on stdin inside that transport, never in argv.
    os.environ.setdefault('PAPER1_GITHUB_TRANSPORT', 'curl')
    paths = cli.setup(project, args.python, raw_dir=args.raw_dir, repository=args.repository)
    # Fresh credentials are interactive here, before the detached child starts.
    token = github_sync.confirm_credentials(paths['repository'], project.name,
                                           force=args.reauthorize, require_verified=True)
    atomic_json(project / 'config/sync.json', {'repository': paths['repository'],
                'project_id': project.name, 'token_file': str(token)})
    with exclusive_lock(project / 'state/login-pipeline-start.lock'):
        observed = _live_driver(project)
        if observed:
            print(json.dumps({'status': 'EXISTING_LOGIN_PIPELINE_REUSED',
                              'stage': observed['stage'], 'pid': observed['pid']}), flush=True)
            return 0
        emit(project, 'github_verified_waiting_for_login_transfer',
             requested_gpus=args.gpus, requested_memory=args.memory)
        start_sync(project, paths, token)
        pid = cli._daemon(project, 'hpcmi.login_pipeline', ['run'] + _arguments(args), 'login-pipeline.log')
        # Observe a real child heartbeat, not merely Popen success. No data audit
        # is repeated here and no Slurm allocation is requested while waiting.
        for _ in range(40):
            observed = _live_driver(project)
            if observed is None:
                try:
                    saved = read_json(project / 'state/login_pipeline_status.json')
                    observed = saved if saved.get('pid') == pid else None
                except (OSError, ValueError):
                    observed = None
            if observed and observed.get('pid') == pid:
                stage = observed.get('stage')
                if stage in {'failed_existing_data_and_jobs_retained',
                             'transfer_failed_no_gpu_job_submitted', 'cancelled_no_gpu_job_submitted'}:
                    raise RuntimeError('Login child stopped at ' + stage +
                                       '; inspect logs/login-pipeline.log; existing data and jobs retained')
                job_id = observed.get('slurm_job_id')
                if stage == 'offline_gpu_job_submitted' and str(job_id).isdigit():
                    print(json.dumps({'status': 'LOGIN_PIPELINE_FINISHED_GPU_JOB_SUBMITTED', 'pid': pid,
                          'stage': stage, 'slurm_job_submitted': True, 'job_id': str(job_id),
                          'github_write_and_readback_verified': True,
                          'training_started_verified': False,
                          'log': str(project / 'logs/login-pipeline.log')}), flush=True)
                    return 0
                if stage in {'replacement_held_old_job_active', 'existing_job_preserved_no_new_gpu_job'}:
                    print(json.dumps({'status': 'LOGIN_PIPELINE_FINISHED_EXISTING_JOB_PRESERVED', 'pid': pid,
                          'stage': stage, 'submission_status': observed.get('submission_status'),
                          'slurm_job_submitted': False, 'job_id': job_id,
                          'training_started_verified': False, 'manual_action_required': True,
                          'log': str(project / 'logs/login-pipeline.log')}), flush=True)
                    return 0
            # A saved nonterminal status cannot prove that a child is still
            # alive. Recheck actual process identity for the startup response.
            live = _live_driver(project)
            if live and live['pid'] == pid:
                print(json.dumps({'status': 'LOGIN_TRANSFER_PIPELINE_STARTED', 'pid': pid,
                      'stage': live['stage'], 'slurm_job_submitted': False,
                      'github_write_and_readback_verified': True,
                      'log': str(project / 'logs/login-pipeline.log'),
                      'status_file': str(project / 'state/login_pipeline_status.json')}), flush=True)
                return 0
            time.sleep(.25)
        raise RuntimeError('Login child startup not observed; inspect logs/login-pipeline.log; no automatic retry')


def run(args):
    from .acquire import network_payloads_ready, quick_raw_ready
    from .submit_single import submit
    project = Path(args.project).expanduser().resolve()
    paths = read_json(project / 'config/paths.json')
    sync_config = read_json(project / 'config/sync.json')
    child = None
    stopped = False
    def stop(number, frame):
        nonlocal stopped
        stopped = True
        if child is not None and child.poll() is None:
            try:
                child.send_signal(signal.SIGTERM)
            except ProcessLookupError:
                pass
    old_handlers = {n: signal.signal(n, stop) for n in (signal.SIGTERM, signal.SIGINT)}
    try:
        with exclusive_lock(project / 'state/login-pipeline-run.lock'):
            emit(project, 'login_transport_only', requested_gpus=args.gpus, requested_memory=args.memory)
            if not quick_raw_ready(paths['raw_dir']) and not network_payloads_ready(paths['raw_dir']):
                retries = 0
                while True:
                    attempt_id = uuid.uuid4().hex
                    env = {**os.environ, 'PYTHONUNBUFFERED': '1', 'PYTHONNOUSERSITE': '1',
                           'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
                           'PAPER1_TRANSFER_ATTEMPT': attempt_id}
                    child = subprocess.Popen([paths['training_python'], '-u', '-m', 'hpcmi.acquire',
                            '--raw-dir', paths['raw_dir'], '--transport-only'], cwd=cli.ROOT,
                            env=env, stdin=subprocess.DEVNULL)
                    if stopped and child.poll() is None:
                        try:
                            child.send_signal(signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                    while child.poll() is None:
                        if stopped:
                            break
                        details = {}
                        progress_path = Path(paths['raw_dir']) / 'transport_status.json'
                        if progress_path.exists():
                            progress = read_json(progress_path)
                            details = {k: progress[k] for k in ('completed_objects', 'total_objects')
                                       if type(progress.get(k)) is int}
                        emit(project, 'login_transport_only', transfer_attempt=attempt_id, **details)
                        # Keep cancellation responsive without emitting noisy logs.
                        for _ in range(30):
                            if child.poll() is not None or stopped:
                                break
                            time.sleep(1)
                    code = child.wait()
                    child = None
                    if stopped:
                        emit(project, 'cancelled_no_gpu_job_submitted')
                        return 143
                    if not code:
                        break
                    failure_path = Path(paths['raw_dir']) / '.transport-failures' / (attempt_id + '.json')
                    try:
                        failure = read_json(failure_path)
                    except (OSError, ValueError):
                        failure = None
                    if not _network_retryable(failure, attempt_id):
                        emit(project, 'transfer_failed_no_gpu_job_submitted', transfer_exit_code=code)
                        return code
                    delay = min(900, 60 * 2 ** min(retries, 4))
                    retries += 1
                    emit(project, 'network_retry_wait', transfer_attempt=attempt_id,
                         transfer_exit_code=code, retry_after_seconds=delay,
                         network_retry_count=retries, error_category=failure.get('category'))
                    if not _wait_network_backoff(delay, lambda: stopped):
                        emit(project, 'cancelled_no_gpu_job_submitted')
                        return 143
            if stopped:
                emit(project, 'cancelled_no_gpu_job_submitted')
                return 143
            if not quick_raw_ready(paths['raw_dir']) and not network_payloads_ready(paths['raw_dir']):
                raise RuntimeError('Frozen network payload inventory is not complete; no GPU job submitted')
            emit(project, 'network_payloads_ready_submitting_offline_gpu_job')
            result = submit(project, paths['training_python'], raw_dir=paths['raw_dir'],
                            wheelhouse=args.wheelhouse, repository=paths['repository'], memory=args.memory,
                            gpus=args.gpus, require_github=True, offline_inputs=True,
                            login_sync=True, replace_job=args.replace_job)
            # The existing submitter may stop an old same-project sync process.
            # Restart the login reporter after it finishes; its lock deduplicates.
            start_sync(project, paths, sync_config['token_file'])
            accepted = result['status'] in {'SINGLE_JOB_SUBMITTED', 'EXISTING_SINGLE_JOB_REUSED'}
            stage = ('offline_gpu_job_submitted' if accepted else
                     'replacement_held_old_job_active' if result['status'].startswith('REPLACEMENT_HELD_')
                     else 'existing_job_preserved_no_new_gpu_job')
            emit(project, stage, submission_status=result['status'],
                 slurm_job_id=result.get('job_id'), requested_gpus=args.gpus,
                 requested_memory=args.memory, gpu_execution_verified=False)
            print(json.dumps(result), flush=True)
            return 0
    except BlockingIOError:
        print(json.dumps({'status': 'LOGIN_PIPELINE_ALREADY_RUNNING'}), flush=True)
        return 0
    except Exception as error:
        traceback.print_exc()
        emit(project, 'failed_existing_data_and_jobs_retained', error_class=type(error).__name__)
        return 1
    finally:
        try:
            if child is not None:
                if child.poll() is None:
                    try:
                        child.send_signal(signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                child.wait()
        finally:
            for number, handler in old_handlers.items():
                signal.signal(number, handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['start', 'run'])
    parser.add_argument('--project', default=cli.DEFAULT_PROJECT)
    parser.add_argument('--python', default=os.environ.get('PAPER1_PYTHON', cli.DEFAULT_PYTHON))
    parser.add_argument('--raw-dir')
    parser.add_argument('--wheelhouse', type=Path)
    parser.add_argument('--repository', default=cli.REPOSITORY)
    parser.add_argument('--gpus', type=int, choices=[2, 3], default=2)
    parser.add_argument('--memory', default='128G')
    parser.add_argument('--replace-job')
    parser.add_argument('--reauthorize', action='store_true')
    args = parser.parse_args(argv)
    return start(args) if args.mode == 'start' else run(args)


if __name__ == '__main__':
    raise SystemExit(main())
