"""Control-plane failure tests: no network, GPU, model fitting or inference."""
import argparse
import hashlib
import importlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
supervisor = importlib.import_module('cloud_supervisor')
prepare_data = importlib.import_module('prepare_data')
trainer = importlib.import_module('train_exploratory')


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


@pytest.fixture
def job(tmp_path, monkeypatch):
    study = tmp_path / 'research_runs/REDESIGN_CLOUD_20261013'
    jobs = study / 'jobs'
    current = jobs / '20261014T010203Z-exploratory-fixture'
    current.mkdir(parents=True)
    monkeypatch.setattr(supervisor, 'ROOT', tmp_path)
    monkeypatch.setattr(supervisor, 'STUDY', study)
    monkeypatch.setattr(supervisor, 'JOBS', jobs)
    monkeypatch.setattr(supervisor, 'CLOUD_BASE', tmp_path / 'cloud-base')
    monkeypatch.setattr(supervisor, 'inside', lambda p: Path(p).resolve().relative_to(tmp_path).as_posix())
    put(study / 'config/experiment.json', {})
    monkeypatch.setattr(trainer, 'CONFIG', study / 'config/experiment.json')
    put(current / 'launch_record.json', {'code_revision': 'a' * 40, 'r2_enabled': False,
        'data_dir': str(tmp_path / 'data'), 'job_id': current.name})
    actual = {'gpu_uuid': 'gpu-original', 'machine_hostname': 'original-machine', 'python': '3.12.0',
              'runtime_cuda': '12.8', 'packages': {'braindecode': '1.5.1'}}
    put(current / 'runtime_lock.json', {**actual, 'status': 'FROZEN_BEFORE_SOURCE_FITS'})
    put(current / 'budget_authorization.json', {
        'status': 'PASS_BOUNDED_MACHINE_BUDGET', 'gpu_uuid': 'gpu-original', 'machine_hostname': 'original-machine',
        'config_sha256': hashlib.sha256((study / 'config/experiment.json').read_bytes()).hexdigest(),
        'maximum_neural_fits': 26, 'maximum_optimizer_updates': 34440, 'maximum_gpu_hours': 8,
        'maximum_total_usd': 10, 'approved_hourly_rate_usd': .5, 'non_gpu_reserved_usd': 2,
        'target_fits_authorized': False, 'optional_grouping_authorized': False,
        'authorized_at_utc': datetime.now(timezone.utc).isoformat(),
        'expires_at_utc': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()})
    put(current / 'code_identity.json', {'code_revision': 'a' * 40, 'files': {}})
    return current


def args(job, **changes):
    values = dict(resume=job.name, code_revision='a' * 40, hourly_rate=.5, r2=False,
                  reset_credentials=False, launch_started_at=datetime.now(timezone.utc).isoformat())
    values.update(changes)
    return argparse.Namespace(**values)


def prevent_side_effects(monkeypatch):
    def blocked(*unused, **kwargs):
        raise AssertionError('No external/worker side effect was expected')
    monkeypatch.setattr(supervisor, 'secure_credentials', blocked)
    monkeypatch.setattr(supervisor.subprocess, 'Popen', blocked)


def test_expired_deadline_blocks_before_child_spawn(job, monkeypatch):
    put(job / 'budget_authorization.json', {
        'expires_at_utc': (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()})
    prevent_side_effects(monkeypatch)
    with pytest.raises(RuntimeError, match='budget_exhausted'):
        supervisor.run_step(job, 'prepare_data.py', [], object())


@pytest.mark.parametrize('field,change', [('gpu_uuid', 'other-GPU'), ('machine_hostname', 'other-machine')])
def test_resume_machine_change_blocks_before_credential_access(job, monkeypatch, field, change):
    actual = json.loads((job / 'runtime_lock.json').read_text())
    actual[field] = change
    monkeypatch.setattr(supervisor, 'runtime', lambda: actual)
    monkeypatch.setattr(supervisor, 'checked_code_revision', lambda unused: {})
    prevent_side_effects(monkeypatch)
    with pytest.raises(ValueError, match='Runtime lock mismatch: ' + field):
        supervisor.launch(args(job))


def test_resume_expired_budget_is_not_reauthorized(job, monkeypatch):
    authorization = json.loads((job / 'budget_authorization.json').read_text())
    authorization['expires_at_utc'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    put(job / 'budget_authorization.json', authorization)
    original = (job / 'budget_authorization.json').read_bytes()
    monkeypatch.setattr(supervisor, 'runtime', lambda: json.loads((job / 'runtime_lock.json').read_text()))
    monkeypatch.setattr(supervisor, 'checked_code_revision', lambda unused: {})
    prevent_side_effects(monkeypatch)
    with pytest.raises((RuntimeError, ValueError), match='budget_exhausted|budget has expired'):
        supervisor.launch(args(job, hourly_rate=.1))
    assert (job / 'budget_authorization.json').read_bytes() == original


def test_global_registration_prevents_fresh_duplicate_budget(job, monkeypatch, capsys):
    put(supervisor.CLOUD_BASE / 'execution_registration.json', {
        'job_id': job.name, 'code_revision': 'a' * 40, 'approved_total_budget_usd': 10})
    prevent_side_effects(monkeypatch)
    monkeypatch.setattr(supervisor, 'runtime', lambda: pytest.fail('Existing budget must prevent new GPU preflight'))
    before = set(supervisor.JOBS.iterdir())
    supervisor.launch(args(job, resume=None))
    assert set(supervisor.JOBS.iterdir()) == before
    assert 'EXISTING_BUDGETED_JOB_DO_NOT_START_DUPLICATE' in capsys.readouterr().out


def test_registered_resume_other_job_or_revision_is_blocked(job, monkeypatch):
    put(supervisor.CLOUD_BASE / 'execution_registration.json', {
        'job_id': job.name, 'code_revision': 'a' * 40, 'approved_total_budget_usd': 10})
    prevent_side_effects(monkeypatch)
    with pytest.raises(ValueError, match='registered_job_or_revision_mismatch'):
        supervisor.launch(args(job, code_revision='b' * 40))


def test_resume_rechecks_code_bytes_before_runtime_or_credentials(job, monkeypatch):
    def changed(unused): raise ValueError('code_differs_from_immutable_revision')
    monkeypatch.setattr(supervisor, 'checked_code_revision', changed)
    monkeypatch.setattr(supervisor, 'runtime', lambda: pytest.fail('Mutated code must fail before runtime'))
    prevent_side_effects(monkeypatch)
    with pytest.raises(ValueError, match='code_differs'):
        supervisor.launch(args(job))


def test_wall_deadline_terminates_child_process_group(job, monkeypatch):
    killed = []
    class Process:
        pid = 87654
        returncode = None
        def poll(self): return None
        def wait(self, timeout=None): self.returncode = -15
    calls = iter([60])
    def deadline(unused):
        try: return next(calls)
        except StopIteration: raise RuntimeError('budget_expired')
    monkeypatch.setattr(supervisor, 'remaining', deadline)
    monkeypatch.setattr(supervisor.subprocess, 'Popen', lambda *a, **k: Process())
    monkeypatch.setattr(supervisor.os, 'killpg', lambda pid, sig: killed.append((pid, sig)))
    with pytest.raises(RuntimeError, match='budget_expired'):
        supervisor.run_step(job, 'train_exploratory.py', [], object())
    assert len(killed) == 1 and killed[0][0] == Process.pid


def test_completed_only_artifacts_omit_inflight_checkpoint_and_resume_state(job):
    complete = job / 'source/final/complete'
    active = job / 'source/final/active'
    put(complete / 'fit_receipt.json', {'status': 'completed'})
    put(active / 'fit_receipt.json', {'status': 'started'})
    for folder in (complete, active):
        (folder / 'checkpoint.pt').write_bytes(b'checkpoint fixture')
        (folder / 'resume_state.pt').write_bytes(b'batch fixture')
        put(folder / 'update_intent.json', {})
    names = supervisor.select_artifacts(job, completed_only=True)
    assert 'source/final/complete/checkpoint.pt' in names
    assert 'source/final/active/checkpoint.pt' not in names
    assert not any('resume_state' in n or 'update_intent' in n for n in names)


def test_raw_tensor_cache_never_selected_for_github(job):
    for n in ('target/raw_logits.npz', 'target/cells/broad-fixed.npz', 'target/raw_tensor.npz', 'source/inputs.npz'):
        p = job / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'non EEG fixture')
    names = supervisor.select_artifacts(job)
    assert 'target/raw_logits.npz' in names and 'target/cells/broad-fixed.npz' in names
    assert 'target/raw_tensor.npz' not in names and 'source/inputs.npz' not in names


def test_freeze_excludes_mutable_progress_but_binds_actual_job_paths(job, monkeypatch):
    put(job / 'target/raw_only_roster.json', {'participants': ['fixture-only']})
    put(job / 'job_status.json', {'stage': 'mutable'})
    put(job / 'source/source_status.json', {})
    put(job / 'last_publication_receipt.json', {})
    put(job / 'failure.json', {})
    captures = []
    def publish(current, publisher, message, paths=None, immutable=False):
        captures.append((paths, immutable))
        return {'commit': 'b' * 40, 'branch': 'redesign/run-' + job.name,
                'artifact_prefix': 'research_runs/REDESIGN_CLOUD_20261013/jobs/' + job.name}
    monkeypatch.setattr(supervisor, 'publish', publish)
    monkeypatch.setattr(supervisor, 'fetch_snapshot', lambda r: None)
    freeze = supervisor.issue_freeze(job, object(), 'preinference_freeze.json', True)
    assert captures[0][1] is True
    assert not set(captures[0][0]) & {'job_status.json', 'source/source_status.json', 'last_publication_receipt.json', 'failure.json'}
    for name, binding in freeze['artifact_bindings'].items():
        assert supervisor.ROOT / binding['public_path'] == job / name
        assert freeze['files'][binding['public_path']] == hashlib.sha256((job / name).read_bytes()).hexdigest()
    assert freeze['independent_confirmation_qualified'] is False and freeze['target_fits'] == 0


def test_publish_requires_verified_public_readback(job):
    class Publisher:
        def publish_snapshot(self, **kwargs):
            return {'github_public_readback_verified': False}
    with pytest.raises(ValueError, match='not_verified'):
        supervisor.publish(job, Publisher(), 'fixture', ['launch_record.json'])
    assert not (job / 'last_publication_receipt.json').exists()


def test_status_never_claims_worker_exit_stops_billing(job):
    supervisor.status(job, 'COMPLETED_EXPLORATORY_VALIDATED_GITHUB_BACKED_UP_MANUAL_STOP_REQUIRED')
    state = json.loads((job / 'job_status.json').read_text())
    assert state['provider_billing_stop_verified'] is False
    assert state['automatic_pod_stop_requested'] is False
    assert state['target_fits'] == 0 and state['independent_confirmation_qualified'] is False


def test_verified_source_cache_rejects_changed_bytes_without_download(tmp_path, monkeypatch):
    p = tmp_path / 'A01T.mat'
    p.write_bytes(b'ABC')
    row = {'path': '/historical/location/A01T.mat', 'bytes': 3,
           'sha256': hashlib.sha256(b'ABC').hexdigest()}
    monkeypatch.setattr(prepare_data.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('Cached source must not silently download replacement'))
    assert prepare_data.source_one(row, tmp_path)['bytes'] == 3
    p.write_bytes(b'ABD')
    with pytest.raises(ValueError, match='cached_hash_mismatch'):
        prepare_data.source_one(row, tmp_path)
    assert p.read_bytes() == b'ABD'


def test_source_transfer_overrun_leaves_no_partial(tmp_path, monkeypatch):
    class Reply:
        status = 200
        def __init__(self): self.sent = False
        def __enter__(self): return self
        def __exit__(self, *a): return None
        def read(self, size):
            if self.sent: return b''
            self.sent = True
            return b'oversize'
    row = {'path': 'A01T.mat', 'bytes': 3, 'sha256': hashlib.sha256(b'ABC').hexdigest()}
    monkeypatch.setattr(prepare_data.urllib.request, 'urlopen', lambda *a, **k: Reply())
    with pytest.raises(ValueError, match='oversize'):
        prepare_data.source_one(row, tmp_path)
    assert not (tmp_path / 'A01T.mat').exists() and not list(tmp_path.glob('*.transfer'))


def test_frozen_tensor_cache_changed_values_fail_closed(tmp_path):
    path = tmp_path / 'A01.npz'
    arrays = {'broad': np.zeros((2, 19, 320), dtype=np.float32),
              'mu': np.zeros((2, 19, 320), dtype=np.float32),
              'beta': np.zeros((2, 19, 320), dtype=np.float32)}
    ids = ['fake-event-1', 'fake-event-2']
    initial = prepare_data.verified_tensor(path, arrays, ids)
    assert prepare_data.verified_tensor(path, arrays, ids) == initial
    changed = {k: v.copy() for k, v in arrays.items()}
    changed['mu'][0, 0, 0] = 1
    with pytest.raises(ValueError, match='tensor_cache_bytes_changed'):
        prepare_data.verified_tensor(path, changed, ids)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == initial


def test_frozen_tensor_event_order_changed_fails(tmp_path):
    path = tmp_path / 'A01.npz'
    arrays = {'broad': np.zeros((2, 19, 320), dtype=np.float32)}
    prepare_data.verified_tensor(path, arrays, ['fake-1', 'fake-2'])
    with pytest.raises(ValueError, match='tensor_cache_bytes_changed'):
        prepare_data.verified_tensor(path, arrays, ['fake-2', 'fake-1'])


def test_frozen_tensor_symlink_rejected(tmp_path):
    actual = tmp_path / 'actual.npz'
    actual.write_bytes(b'fixture')
    alias = tmp_path / 'A01.npz'
    alias.symlink_to(actual)
    with pytest.raises(ValueError, match='symlink'):
        prepare_data.verified_tensor(alias, {}, [])


def simulated_work(job, monkeypatch, failure=None):
    """Fixture-only subprocess records for the orchestration ordering contract."""
    calls = []
    monkeypatch.setattr(supervisor, 'secure_credentials', lambda **kw: {'GH_TOKEN': 'fixture-sensitive-token'})
    monkeypatch.setattr(supervisor, 'GitHubPublisher', lambda *a, **kw: object())
    def freeze(current, publisher, name, preinference=False):
        calls.append(name)
        assert (current / 'data_prepare_receipt.json').exists()
        if preinference:
            assert json.loads((current / 'source/source_validation.json').read_text())['status'] == 'PASS_SOURCE_ARTIFACT_VALIDATION_EXPLORATORY'
        put(current / name, {'commit_sha': 'c' * 40})
    monkeypatch.setattr(supervisor, 'issue_freeze', freeze)
    def step(current, script, arguments, publisher, periodic=False):
        calls.append(script)
        if script == failure:
            raise RuntimeError('fixture_step_failed_no_scientific_execution')
        if script == 'prepare_data.py':
            put(current / 'data_prepare_receipt.json', {'status': 'PASS_DATA_PREPARATION_EXPLORATORY',
                'source_dir': 'synthetic-source-location', 'tensor_cache': 'synthetic-target-location'})
            for name in ['raw_only_roster.json', 'raw_only_event_roster.csv', 'full_raw_qc_report.json', 'tensor_cache_receipt.json']:
                p = current / 'qc' / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('fixture-only')
        elif script == 'train_exploratory.py':
            assert (current / 'public_freeze.json').exists()
            assert not (current / 'preinference_freeze.json').exists()
            put(current / 'source/budget_ledger.json', {'actual_neural_fits_started': 26,
                'actual_neural_fits_completed': 26, 'optimizer_updates': 123})
        elif script == 'validate_source.py':
            put(current / 'source/source_validation.json', {'status': 'PASS_SOURCE_ARTIFACT_VALIDATION_EXPLORATORY'})
        elif script == 'infer_exploratory.py':
            assert (current / 'preinference_freeze.json').exists()
            assert (current / 'source/source_validation.json').exists()
            put(current / 'target/prediction_completion_receipt.json', {'fixture_only': True})
            (current / 'target/predictions.csv').write_text('fixture_only\nno_actual_predictions\n')
        elif script == 'validate_predictions.py':
            assert (current / 'target/prediction_completion_receipt.json').exists()
        elif script == 'analyze_exploratory.py':
            assert calls.index('validate_predictions.py') < calls.index(script)
            put(current / 'target/analysis.json', {'fixture_only': True, 'independent_confirmation_qualified': False})
        elif script == 'validate_analysis.py':
            assert calls.index('analyze_exploratory.py') < calls.index(script)
            put(current / 'target/statistical_validation.json', {
                'status': 'PASS_SEPARATE_STATISTICAL_NUMERICAL_RECONSTRUCTION_EXPLORATORY',
                'analysis_sha256': hashlib.sha256((current / 'target/analysis.json').read_bytes()).hexdigest(),
                'predictions_sha256': hashlib.sha256((current / 'target/predictions.csv').read_bytes()).hexdigest(),
                'target_fits': 0, 'independent_confirmation_qualified': False, 'fixture_only': True})
    monkeypatch.setattr(supervisor, 'run_step', step)
    def publication(current, publisher, message, paths=None, immutable=False):
        calls.append('backup:' + message)
        return {'commit': 'd' * 40, 'github_public_readback_verified': True, 'checkpoint_backup_verified': True}
    monkeypatch.setattr(supervisor, 'publish', publication)
    monkeypatch.setattr(supervisor, 'fetch_snapshot', lambda r: None)
    return calls


def test_workflow_freezes_before_fits_and_validates_before_target_then_backups(job, monkeypatch):
    calls = simulated_work(job, monkeypatch)
    supervisor.work(job)
    expected = ['prepare_data.py', 'public_freeze.json', 'train_exploratory.py', 'validate_source.py',
                'preinference_freeze.json', 'infer_exploratory.py', 'validate_predictions.py', 'analyze_exploratory.py',
                'validate_analysis.py']
    assert calls[:9] == expected
    assert calls[9].startswith('backup:Complete exploratory') and calls[10].startswith('backup:Verified completion')
    result = json.loads((job / 'job_status.json').read_text())
    assert result['stage'] == 'COMPLETED_EXPLORATORY_VALIDATED_GITHUB_BACKED_UP_MANUAL_STOP_REQUIRED'
    assert result['actual_neural_fits_completed'] == 26 and result['target_fits'] == 0
    assert result['provider_billing_stop_verified'] is False and result['independent_confirmation_qualified'] is False


@pytest.mark.parametrize('failure', ['prepare_data.py', 'train_exploratory.py', 'validate_source.py',
                                    'infer_exploratory.py', 'validate_predictions.py', 'analyze_exploratory.py',
                                    'validate_analysis.py'])
def test_failed_stage_never_falls_through_to_later_science_or_completion(job, monkeypatch, failure):
    calls = simulated_work(job, monkeypatch, failure)
    with pytest.raises(SystemExit) as caught:
        supervisor.work(job)
    assert caught.value.code == 1
    result = json.loads((job / 'job_status.json').read_text())
    assert result['stage'] == 'FAILED_OR_BLOCKED_MANUAL_REVIEW_REQUIRED'
    assert not (job / 'completed_backup_receipt.json').exists()
    assert not any(c.startswith('backup:Complete exploratory') for c in calls)
    if failure in {'prepare_data.py', 'train_exploratory.py', 'validate_source.py'}:
        assert 'infer_exploratory.py' not in calls and not (job / 'preinference_freeze.json').exists()
    if failure == 'validate_predictions.py':
        assert 'analyze_exploratory.py' not in calls


@pytest.mark.parametrize('invalid', ['missing', 'wrong_status', 'changed_analysis', 'changed_predictions', 'independence_promoted'])
def test_statistics_receipt_missing_or_unbound_never_claims_completion(job, monkeypatch, invalid):
    calls = simulated_work(job, monkeypatch)
    expected_step = supervisor.run_step
    def altered_step(current, script, arguments, publisher, periodic=False):
        expected_step(current, script, arguments, publisher, periodic)
        if script != 'validate_analysis.py': return
        p = current / 'target/statistical_validation.json'
        if invalid == 'missing':
            p.unlink()
        else:
            value = json.loads(p.read_text())
            if invalid == 'wrong_status': value['status'] = 'INCOMPLETE'
            if invalid == 'changed_analysis': value['analysis_sha256'] = '0' * 64
            if invalid == 'changed_predictions': value['predictions_sha256'] = '0' * 64
            if invalid == 'independence_promoted': value['independent_confirmation_qualified'] = True
            put(p, value)
    monkeypatch.setattr(supervisor, 'run_step', altered_step)
    with pytest.raises(SystemExit):
        supervisor.work(job)
    assert json.loads((job / 'job_status.json').read_text())['stage'] == 'FAILED_OR_BLOCKED_MANUAL_REVIEW_REQUIRED'
    assert not any(c.startswith('backup:Complete exploratory') for c in calls)
    assert not (job / 'completed_backup_receipt.json').exists()


def test_completion_backup_error_records_failure_and_redacts_secret(job, monkeypatch):
    simulated_work(job, monkeypatch)
    def broken_publication(current, publisher, message, paths=None, immutable=False):
        raise RuntimeError('fixture-sensitive-token backup_failure')
    monkeypatch.setattr(supervisor, 'publish', broken_publication)
    with pytest.raises(SystemExit):
        supervisor.work(job)
    text = (job / 'job_status.json').read_text()
    assert 'fixture-sensitive-token' not in text and '[redacted]' in text
    assert json.loads(text)['stage'] == 'FAILED_OR_BLOCKED_MANUAL_REVIEW_REQUIRED'
    assert not (job / 'completed_backup_receipt.json').exists()


def test_github_metadata_readback_without_checkpoints_cannot_claim_completion(job, monkeypatch):
    calls = simulated_work(job, monkeypatch)
    original = supervisor.publish
    def metadata_only(current, publisher, message, paths=None, immutable=False):
        result = original(current, publisher, message, paths, immutable)
        result['checkpoint_backup_verified'] = False
        return result
    monkeypatch.setattr(supervisor, 'publish', metadata_only)
    with pytest.raises(SystemExit):
        supervisor.work(job)
    result = json.loads((job / 'job_status.json').read_text())
    assert result['stage'] == 'FAILED_OR_BLOCKED_MANUAL_REVIEW_REQUIRED'
    assert not (job / 'completed_backup_receipt.json').exists()
    assert not any(c.startswith('backup:Verified completion') for c in calls)


def test_supervisor_lock_blocks_second_worker_before_credentials(job, monkeypatch):
    def locked(*unused): raise BlockingIOError('fixture-lock-owned')
    monkeypatch.setattr(supervisor.fcntl, 'flock', locked)
    prevent_side_effects(monkeypatch)
    with pytest.raises(supervisor.LockBusy, match='local_process_lock_busy:supervisor'):
        supervisor.work(job)
