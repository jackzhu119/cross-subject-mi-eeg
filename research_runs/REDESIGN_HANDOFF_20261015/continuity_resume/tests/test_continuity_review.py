"""Synthetic metadata tests only; no scientific imports or checkpoint reads."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

SPEC = importlib.util.spec_from_file_location('continuity_review', Path(__file__).parents[1] / 'continuity_review.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(obj) + '\n').encode()
    path.write_bytes(data)
    return M.digest(data), len(data)


def old_tree(tmp_path, started=0, completed=0, updates=0):
    root = tmp_path / 'old'
    job = root / ('code-' + M.OLD_REVISION) / 'research_runs/REDESIGN_CLOUD_20261013/jobs' / M.OLD_JOB
    ledger = {'actual_neural_fits_started': started, 'actual_neural_fits_completed': completed,
              'optimizer_updates': updates, 'target_fits': 0, 'target_predictions_computed': False}
    write(job / 'source/budget_ledger.json', ledger)
    write(job / 'job_status.json', dict(ledger, job_id=M.OLD_JOB))
    return root, job, ledger


def test_five_bound_source_records_and_tamper_rejected(tmp_path, monkeypatch):
    restore, accept = tmp_path / 'restore', tmp_path / 'accept'
    rows = [{'filename': f'A{i:02}{s}.mat', 'bytes': 1, 'sha256': 'a' * 64} for i in range(1, 10) for s in 'ET']
    rows[-1]['bytes'] = 779873919 - 17
    records = {
        'restore': {'old_task': M.OLD_JOB, 'status': 'SOURCE18_EXACT_BYTES_RESTORED_NUMERICAL_ACCEPTANCE_PENDING',
                    'files': rows, 'training_authorization': False},
        'completion': {'worker_exit_code_observed': 0, 'training_authorization': False},
        'outer': {'exit_code': 0, 'training_authorization': False},
        'formal': {'status': 'SOURCE_NUMERICAL_ACCEPTANCE_MATCH_TRAINING_STILL_BLOCKED',
                   'source_complete_exact_hash_gate_passed': True, 'training_consumer_imports_verified': True,
                   'source_array_hashes': M.ARRAY_HASHES, 'source_files': 18, 'source_runs': 108,
                   'source_trials': 2592, 'training_authorization': False},
        'runtime': {'status': 'REPAIRED_ACTUAL_TRAINING_RUNTIME_SOURCE_MATCH_OTHER_GATES_PENDING',
                    'actual_training_runtime_imports_verified': True, 'strict_trial_and_aggregate_hash_gate_passed': True,
                    'new_fits': 0, 'CUDA_initialized': False, 'target_EEG_read': False, 'training_authorization': False},
    }
    bindings = {}
    for key in ('restore', 'completion', 'outer', 'formal', 'runtime'):
        obj = records[key]
        if key in ('completion', 'outer'):
            obj['receipt_sha256'] = bindings['restore'][2]
        if key == 'outer':
            obj['controller_completion_sha256'] = bindings['completion'][2]
        if key == 'runtime':
            obj.update(formal_source_acceptance_sha256=bindings['formal'][2],
                       new_container_source_restore_receipt_sha256=bindings['restore'][2])
        filename = M.BINDINGS[key][0]
        sha, size = write((restore if key in ('restore', 'completion', 'outer') else accept) / filename, obj)
        bindings[key] = filename, size, sha
    monkeypatch.setattr(M, 'BINDINGS', bindings)
    result = M.source_review(restore, accept)
    assert result['strict_hashes_verified_in_bound_evidence'] is True
    assert result['new_acceptance_performed'] is False
    (accept / bindings['runtime'][0]).write_text('{}')
    with pytest.raises(ValueError, match='json_identity_mismatch'):
        M.source_review(restore, accept)


def test_absent_old_task_is_unknown_not_zero_and_never_training(tmp_path, monkeypatch):
    monkeypatch.setattr(M, 'source_review', lambda *_: {'status': 'BOUND_SOURCE_EVIDENCE'})
    result = M.review(tmp_path, tmp_path, tmp_path / 'nonexistent')
    assert result['old_task']['counters'] is None
    assert result['old_task']['state'] == 'OLD_WORK_ROOT_NOT_OBSERVED'
    assert result['financial_preconditions'] == 'superseded-by-user'
    assert result['training_authorization'] is False
    assert 'latest_fit_update_ledger' in result['actionable_missing']


def test_counts_intents_and_bool_rejection(tmp_path):
    root, job, ledger = old_tree(tmp_path, started=1)
    receipt = {'status': 'started', 'fit_ordinal': 1, 'configuration_sha256': M.CONFIG_SHA, 'target_fit': False}
    write(job / 'source/inner/cell/fit_receipt.json', receipt)
    write(job / 'source/inner/cell/update_intent.json', {'next_global_update': 1})
    result = M.old_review(root)
    assert result['counters']['actual_neural_fits_started'] == 1
    assert 'unresolved_update_intent_blocks_automatic_resume' in result['issues']
    ledger['actual_neural_fits_started'] = True
    write(job / 'source/budget_ledger.json', ledger)
    with pytest.raises(ValueError, match='invalid_integer_counter'):
        M.old_review(root)


def test_status_only_historical_zero_does_not_fill_latest_ledger(tmp_path):
    root, job, _ = old_tree(tmp_path)
    (job / 'source/budget_ledger.json').unlink()
    result = M.old_review(root)
    assert result['counters'] is None
    assert result['observed_counters_by_record']['job_status']['actual_neural_fits_started'] == 0
    assert 'source_ledger' in result['missing']


def test_committed_metadata_is_not_blob_or_checkpoint_verification(tmp_path, monkeypatch):
    root, job, _ = old_tree(tmp_path, 1, 1, 17)
    prefix = 'redesign-private-recovery/' + M.OLD_JOB
    cell = job / 'source/inner/cell'
    receipt = {'status': 'completed', 'fit_ordinal': 1, 'configuration_sha256': M.CONFIG_SHA,
               'target_fit': False, 'checkpoint_sha256': 'b' * 64, 'curve_sha256': 'c' * 64, 'partition_sha256': 'd' * 64}
    receipt_sha, size = write(cell / 'fit_receipt.json', receipt)
    (cell / 'checkpoint.pt').write_bytes(b'NOT_A_TORCH_FILE_AND_MUST_NOT_BE_READ')
    write(cell / 'source_curve.json', {})
    write(cell / 'partition.json', {})
    original = M.load
    def no_checkpoint_contents(path, *args):
        assert Path(path).name not in ('checkpoint.pt', 'resume_state.pt', 'partition.json', 'source_curve.json')
        return original(path, *args)
    monkeypatch.setattr(M, 'load', no_checkpoint_contents)
    old = M.old_review(root)
    files = {}
    for name in ('launch_record.json', 'runtime_lock.json', 'budget_authorization.json', 'code_identity.json', 'data_prepare_receipt.json', 'public_freeze.json'):
        files[name] = {'bytes': 1, 'sha256': 'a' * 64, 'key': prefix + '/blobs/' + 'a' * 64}
    files['source/inner/cell/fit_receipt.json'] = {'bytes': size, 'sha256': receipt_sha, 'key': prefix + '/blobs/' + receipt_sha}
    for filename, sha in [('checkpoint.pt', 'b' * 64), ('source_curve.json', 'c' * 64), ('partition.json', 'd' * 64)]:
        name = 'source/inner/cell/' + filename
        files[name] = {'bytes': old['checkpoint_stat_inventory'][name]['bytes'], 'sha256': sha, 'key': prefix + '/blobs/' + sha}
    manifest_path = tmp_path / 'manifest.json'
    manifest_sha, _ = write(manifest_path, {'schema_version': 1, 'job_id': M.OLD_JOB, 'files': files})
    head_path = tmp_path / 'HEAD.json'
    head_sha, _ = write(head_path, {'state': 'COMMITTED', 'job_id': M.OLD_JOB, 'manifest': prefix + '/manifests/one.json', 'manifest_sha256': manifest_sha})
    result = M.backup_review(head_path, head_sha, manifest_path, manifest_sha, old)
    assert result['issues'] == []
    assert result['blob_readback_verified'] is False
    assert result['checkpoint_contents_verified'] is False
    head_sha, _ = write(head_path, {'state': 'PENDING', 'job_id': M.OLD_JOB})
    assert 'backup_HEAD_not_COMMITTED_no_replay' in M.backup_review(head_path, head_sha, None, None, old)['issues']


def test_rejected_or_expired_slot_produces_no_report(tmp_path, monkeypatch):
    output = tmp_path / 'report.json'
    monkeypatch.setattr(sys, 'argv', ['continuity_review.py', '--source-restore-root', str(tmp_path),
        '--source-acceptance-root', str(tmp_path), '--priority-gate', str(tmp_path / 'gate.py'),
        '--priority-receipt', str(tmp_path / 'slot.json'), '--output', str(output)])
    def rejected(*_):
        raise ValueError('priority_slot_not_active_or_expired')
    monkeypatch.setattr(M, 'priority_permit', rejected)
    monkeypatch.setattr(M, 'source_review', lambda *_: pytest.fail('source metadata must not be read after failed slot'))
    with pytest.raises(ValueError, match='expired'):
        M.main()
    assert not output.exists()
