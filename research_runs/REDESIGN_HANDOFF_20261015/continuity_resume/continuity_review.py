"""Read fixed acceptance JSON and old-task metadata only; never launch/resume fits.

No imports from experiment code, network, subprocess, Torch, raw EEG or checkpoint
contents. Local backup metadata does not prove remote freshness or blob readback.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys

OLD_JOB = '20261014T071918Z-exploratory-89b0c07d'
OLD_REVISION = '05e683e91e2bb39b977970d04402221761e575d2'
CONFIG_SHA = '8ba78d4ead0e41fc5a5fc6f9890b750f0bdfdaba74a57efab5422b43d57feff0'
SOURCE_ARCHIVE_SHA = '2c943a5f70608d10cb1f0720be5874ce53c01e3bed6d5bf2cbcafbc636ff312d'
MAX_JSON = 2 * 1024**2
PRIORITY_SHA = 'eb88b6c75381a714bd91d9b0bb0acb4fd82edf295b73a25abed4f0236c054fff'
BINDINGS = {
    'restore': ('source_restore_repair_run01.json', 14931, 'acdaa915e5f5c0dd66e1b0178fa8602791a70146f46734fd023e2c455acb196c'),
    'completion': ('source_restore_repair_run01.completion.json', 676, '60023885557693cdd10f96a746eceebc3f66b3788701cb9a74bbd609675ded77'),
    'outer': ('source_restore_repair_run01.compat_outer_exit.json', 833, '1566370c2d6b0b0b30c828290f3d443e59e694016cbd1ecff8d10ed266fee52e'),
    'formal': ('formal_source_acceptance.json', 10433, '9f6980404ccd2ceb8f96aa300d497919caa185b02bbff0cc441451ae0a8a59e9'),
    'runtime': ('repaired_runtime_bound_acceptance.json', 13157, '8e5ae3890240b130c875180a18e455dcd3158eab53926dcabb95c2f40768a39b'),
}
ARRAY_HASHES = {
    'broad': '420cd1635c3748e4706c3635e795384f7f859961736bbe7400eae9eb4db7dcd0',
    'mu': '704635466155eb4965a732d389ffcb71a1a7a862ffc41e0d615dc3c68b7d17dc',
    'beta': '8e2a88db18e4db719a4b1e396a7871bc102123f99358751f332e0dbd678c6462',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, maximum=None):
    require(type(value) is int and value >= 0 and (maximum is None or value <= maximum), 'invalid_integer_counter')
    return value


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink_rejected')
    return path


def load(path, expected_sha=None, expected_size=None):
    path = safe_path(path)
    require(path.suffix == '.json', 'only_explicit_json_contents_allowed')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_JSON, 'bounded_regular_json_required')
        data = stream.read(MAX_JSON + 1)
        after = os.fstat(stream.fileno())
    require((before.st_size, before.st_mtime_ns, before.st_ino) == (after.st_size, after.st_mtime_ns, after.st_ino)
            and len(data) == before.st_size, 'json_changed_during_read')
    require((expected_size is None or len(data) == expected_size)
            and (expected_sha is None or digest(data) == expected_sha), 'json_identity_mismatch:' + path.name)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    def invalid(_):
        raise ValueError('nonfinite_json_rejected')
    result = json.loads(data, object_pairs_hook=unique, parse_constant=invalid)
    require(isinstance(result, dict), 'json_object_required')
    return result, digest(data)


def source_review(restore_root, acceptance_root):
    records = {}
    for key, (name, size, sha) in BINDINGS.items():
        records[key], _ = load(Path(restore_root if key in ('restore', 'completion', 'outer') else acceptance_root) / name, sha, size)
    restore, completion, outer, formal, runtime = (records[k] for k in ('restore', 'completion', 'outer', 'formal', 'runtime'))
    require(restore['old_task'] == OLD_JOB and restore['status'] == 'SOURCE18_EXACT_BYTES_RESTORED_NUMERICAL_ACCEPTANCE_PENDING', 'source_restore_identity')
    rows = restore['files']
    require(len(rows) == 18 and {r['filename'] for r in rows} == {f'A{i:02}{s}.mat' for i in range(1, 10) for s in 'ET'}, 'source18_inventory')
    require(sum(integer(r['bytes']) for r in rows) == 779873919
            and all(re.fullmatch('[0-9a-f]{64}', r['sha256']) for r in rows), 'source18_size_or_sha')
    require(completion['receipt_sha256'] == BINDINGS['restore'][2]
            and integer(completion['worker_exit_code_observed']) == 0
            and integer(outer['exit_code']) == 0
            and outer['controller_completion_sha256'] == BINDINGS['completion'][2]
            and outer['receipt_sha256'] == BINDINGS['restore'][2], 'source_process_completion_not_verified')
    require(formal['status'] == 'SOURCE_NUMERICAL_ACCEPTANCE_MATCH_TRAINING_STILL_BLOCKED'
            and formal['source_complete_exact_hash_gate_passed'] is True
            and formal['training_consumer_imports_verified'] is True
            and formal['source_array_hashes'] == ARRAY_HASHES
            and [integer(formal[k]) for k in ('source_files', 'source_runs', 'source_trials')] == [18, 108, 2592], 'formal_source_gate')
    require(runtime['status'] == 'REPAIRED_ACTUAL_TRAINING_RUNTIME_SOURCE_MATCH_OTHER_GATES_PENDING'
            and runtime['actual_training_runtime_imports_verified'] is True
            and runtime['strict_trial_and_aggregate_hash_gate_passed'] is True
            and runtime['formal_source_acceptance_sha256'] == BINDINGS['formal'][2]
            and runtime['new_container_source_restore_receipt_sha256'] == BINDINGS['restore'][2], 'runtime_source_binding')
    for report in (restore, completion, outer, formal, runtime):
        require(report['training_authorization'] is False, 'acceptance_cannot_authorize_training')
    require(integer(runtime['new_fits']) == 0 and runtime['CUDA_initialized'] is False
            and runtime['target_EEG_read'] is False, 'cpu_acceptance_boundary')
    return {'status': 'FIXED_ACTUAL_SOURCE18_RUNTIME_CPU_ACCEPTANCE_REUSED_NOT_RERUN',
            'evidence_archive_sha256': SOURCE_ARCHIVE_SHA,
            'metadata_sha256': {k: v[2] for k, v in BINDINGS.items()},
            'source_files': 18, 'source_bytes': 779873919, 'source_runs': 108, 'source_trials': 2592,
            'actual_runtime_imports_verified_in_bound_evidence': True,
            'strict_hashes_verified_in_bound_evidence': True,
            'CPU_exit_zero_independently_audited_in_bound_archive': True,
            'new_acceptance_performed': False, 'runtime_or_raw_files_currently_inspected': False,
            'historical_effective_cgroup': {'observed_at_utc': '2026-10-15T07:17:18.866707+00:00',
                'effective_CPUs': 10.2, 'memory_limit_bytes': 61999996928, 'live_or_continuous_observation': False}}


def old_review(root):
    result = {'old_job_id': OLD_JOB, 'old_code_revision': OLD_REVISION, 'counters': None, 'observed_counters_by_record': {},
              'records': {}, 'fit_receipts': [], 'checkpoint_stat_inventory': {}, 'unresolved_update_intents': [],
              'checkpoint_contents_verified': False, 'missing': [], 'issues': []}
    if root is None or not safe_path(root).is_dir():
        result['state'] = 'OLD_WORK_ROOT_NOT_OBSERVED'
        result['missing'] = ['original_registration', 'latest_fit_update_ledger', 'fit_checkpoint_inventory', 'verified_backup_continuity']
        return result
    root = safe_path(root)
    job = root / ('code-' + OLD_REVISION) / 'research_runs/REDESIGN_CLOUD_20261013/jobs' / OLD_JOB
    names = {'registration': root / 'execution_registration.json', 'budget_origin': root / 'budget_origin.json',
             **{n: job / (n + '.json') for n in ('launch_record', 'code_identity', 'runtime_lock', 'job_status')},
             'source_ledger': job / 'source/budget_ledger.json'}
    values = {}
    for name, path in names.items():
        if not safe_path(path).exists():
            result['records'][name] = {'state': 'NOT_OBSERVED', 'sha256': None}
            result['missing'].append(name)
            continue
        values[name], sha = load(path)
        result['records'][name] = {'state': 'LOCAL_JSON_OBSERVED_NOT_LATEST_REMOTE_PROOF', 'sha256': sha}
    for name in ('registration', 'launch_record', 'job_status'):
        if name in values:
            require(values[name].get('job_id') == OLD_JOB, 'old_job_identity_mismatch:' + name)
    for name in ('registration', 'launch_record', 'code_identity'):
        if name in values:
            require(values[name].get('code_revision') == OLD_REVISION, 'old_code_identity_mismatch:' + name)
    counters = []
    for name in ('source_ledger', 'job_status'):
        if name not in values:
            continue
        obj = values[name]
        row = {k: integer(obj.get(k), cap) for k, cap in [('actual_neural_fits_started', 26), ('actual_neural_fits_completed', 26), ('optimizer_updates', 34440)]}
        require(row['actual_neural_fits_completed'] <= row['actual_neural_fits_started'], 'completed_exceeds_started')
        require(type(obj.get('target_fits')) is int and obj['target_fits'] == 0
                and obj.get('target_predictions_computed') is False, 'old_target_boundary')
        counters.append(row)
        result['observed_counters_by_record'][name] = row
    if counters:
        # A status-only snapshot, including a published historical zero, cannot
        # establish the latest durable source ledger after a lost container.
        result['counters'] = result['observed_counters_by_record'].get('source_ledger')
        if any(v != counters[0] for v in counters):
            result['issues'].append('old_status_ledger_counters_disagree')
    source = job / 'source'
    if safe_path(source).is_dir():
        seen = 0
        def inaccessible(error):
            raise error
        for base, dirs, files in os.walk(source, followlinks=False, onerror=inaccessible):
            for name in dirs + files:
                safe_path(Path(base) / name)
            seen += len(dirs) + len(files)
            require(seen <= 10000, 'source_metadata_inventory_limit')
            for name in files:
                path = Path(base) / name
                rel = path.relative_to(job).as_posix()
                if name in ('checkpoint.pt', 'resume_state.pt', 'partition.json', 'source_curve.json'):
                    info = path.lstat()
                    require(stat.S_ISREG(info.st_mode), 'checkpoint_inventory_regular_file_required')
                    result['checkpoint_stat_inventory'][rel] = {'bytes': info.st_size, 'contents_read': False}
                elif name == 'fit_receipt.json':
                    receipt, sha = load(path)
                    require(receipt.get('status') in ('started', 'completed'), 'fit_status_invalid')
                    integer(receipt.get('fit_ordinal'), 26)
                    require(receipt['fit_ordinal'] > 0 and receipt.get('configuration_sha256') == CONFIG_SHA
                            and receipt.get('target_fit') is False, 'fit_identity_or_target_boundary')
                    result['fit_receipts'].append({'path': rel, 'sha256': sha, 'receipt': receipt})
                elif name == 'update_intent.json':
                    _, sha = load(path)
                    result['unresolved_update_intents'].append({'path': rel, 'sha256': sha})
    receipts = result['fit_receipts']
    require(len({r['receipt']['fit_ordinal'] for r in receipts}) == len(receipts), 'duplicate_fit_ordinal')
    if receipts:
        require(sorted(r['receipt']['fit_ordinal'] for r in receipts) == list(range(1, len(receipts) + 1)), 'noncontiguous_fit_ordinals')
    require(sum(r['receipt']['status'] == 'started' for r in receipts) <= 1, 'multiple_active_fits')
    if result['counters'] is not None:
        c = result['counters']
        if len(receipts) != c['actual_neural_fits_started'] or sum(r['receipt']['status'] == 'completed' for r in receipts) != c['actual_neural_fits_completed']:
            result['issues'].append('fit_receipts_and_counters_disagree')
    if result['unresolved_update_intents']:
        result['issues'].append('unresolved_update_intent_blocks_automatic_resume')
    result['state'] = 'OLD_LOCAL_METADATA_OBSERVED_CONTINUITY_NOT_PROVEN'
    return result


def backup_review(head_path, head_sha, manifest_path, manifest_sha, old):
    result = {'state': 'NOT_OBSERVED', 'remote_latest_proven': False, 'blob_readback_verified': False,
              'checkpoint_contents_verified': False, 'issues': []}
    if all(x is None for x in (head_path, head_sha, manifest_path, manifest_sha)):
        return result
    require(head_path is not None and re.fullmatch('[0-9a-f]{64}', head_sha or ''), 'backup_HEAD_and_SHA_required')
    head, _ = load(head_path, head_sha)
    require(head.get('job_id') == OLD_JOB, 'backup_wrong_job')
    result.update(state='LOCAL_HEAD_METADATA_ONLY', head_sha256=head_sha, head_state=head.get('state'))
    if head.get('state') != 'COMMITTED':
        result['issues'].append('backup_HEAD_not_COMMITTED_no_replay')
        return result
    require(manifest_path is not None and re.fullmatch('[0-9a-f]{64}', manifest_sha or '')
            and head.get('manifest_sha256') == manifest_sha, 'HEAD_manifest_binding_required')
    prefix = 'redesign-private-recovery/' + OLD_JOB
    require(isinstance(head.get('manifest'), str) and head['manifest'].startswith(prefix + '/manifests/')
            and '..' not in PurePosixPath(head['manifest']).parts, 'unsafe_manifest_key')
    manifest, _ = load(manifest_path, manifest_sha)
    require(manifest.get('schema_version') == 1 and manifest.get('job_id') == OLD_JOB
            and isinstance(manifest.get('files'), dict) and 0 < len(manifest['files']) <= 10000, 'manifest_identity')
    files = manifest['files']
    for name, row in files.items():
        require(isinstance(name, str) and not PurePosixPath(name).is_absolute()
                and not any(p in ('', '.', '..') for p in name.split('/')) and '\\' not in name, 'unsafe_manifest_path')
        require(isinstance(row, dict) and re.fullmatch('[0-9a-f]{64}', row.get('sha256', ''))
                and integer(row.get('bytes'), 256 * 1024**2) >= 0
                and row.get('key') == prefix + '/blobs/' + row['sha256'], 'manifest_object_identity')
    required = ('launch_record.json', 'runtime_lock.json', 'budget_authorization.json', 'code_identity.json', 'data_prepare_receipt.json', 'public_freeze.json')
    if not set(required).issubset(files):
        result['issues'].append('backup_static_manifest_incomplete')
    for item in old['fit_receipts']:
        rel, receipt = item['path'], item['receipt']
        if rel not in files or files[rel]['sha256'] != item['sha256']:
            result['issues'].append('backup_fit_receipt_unbound:' + rel)
        parent = str(PurePosixPath(rel).parent)
        names = {'checkpoint.pt': 'checkpoint_sha256', 'source_curve.json': 'curve_sha256', 'partition.json': 'partition_sha256'}
        for name, key in names.items() if receipt['status'] == 'completed' else [('resume_state.pt', None)]:
            full = parent + '/' + name
            if full not in files or (key is not None and files[full]['sha256'] != receipt.get(key)):
                result['issues'].append('backup_checkpoint_declaration_unbound:' + full)
            if full not in old['checkpoint_stat_inventory']:
                result['issues'].append('local_checkpoint_not_observed:' + full)
            elif full in files and files[full]['bytes'] != old['checkpoint_stat_inventory'][full]['bytes']:
                result['issues'].append('checkpoint_stat_size_disagrees:' + full)
    if any(name.endswith('update_intent.json') for name in files):
        result['issues'].append('backup_unresolved_update_intent')
    result.update(manifest_sha256=manifest_sha, state='LOCAL_COMMITTED_METADATA_NOT_REMOTE_OR_BLOB_VERIFICATION')
    return result


def review(restore_root, acceptance_root, old_root=None, head=None, head_sha=None, manifest=None, manifest_sha=None):
    source = source_review(restore_root, acceptance_root)
    old = old_review(old_root)
    backup = backup_review(head, head_sha, manifest, manifest_sha, old)
    missing = list(old['missing']) + list(old['issues']) + list(backup['issues'])
    if backup['state'] == 'NOT_OBSERVED':
        missing.append('authentic_latest_backup_HEAD_manifest_and_blob_readback')
    missing += ['independent_checkpoint_contents_and_remote_backup_verification', 'explicit_new_machine_transition_preserving_old_identity',
                'target174_same_byte_restore_and_frozen_numerical_input_acceptance', 'production_route_and_data_prepare_public_freeze',
                'Paper2_priority_new_exclusive_GPU_slot_and_actual_GPU_preflight']
    return {'schema_version': 1, 'status': 'SOURCE_RUNTIME_ACCEPTED_ORIGINAL_TASK_CONTINUITY_AND_TARGET_GATES_PENDING',
            'old_job_id': OLD_JOB, 'old_code_revision': OLD_REVISION, 'source_runtime': source, 'old_task': old,
            'backup_metadata': backup, 'financial_preconditions': 'superseded-by-user',
            'historical_unknown_costs_or_counters_reset': False, 'GPU_deadline_utc': '2026-10-16T09:54:00Z',
            'Paper2_remaining_GPU_queue_priority': True, 'Paper2_remaining_items_reported_by_user': 36,
            'actionable_missing': sorted(set(missing)), 'training_authorization': False, 'GPU_fit_started': False,
            'target_EEG_read': False, 'checkpoint_bytes_read': False, 'provider_Pod_control_performed': False,
            'diagnostic_or_acceptance_rerun': False, 'old_registration_modified': False}


def priority_permit(gate_path, receipt_path):
    gate_path = safe_path(gate_path)
    require(gate_path.is_file() and gate_path.stat().st_size <= 32768
            and digest(gate_path.read_bytes()) == PRIORITY_SHA, 'fixed_priority_gate_identity_required')
    spec = importlib.util.spec_from_file_location('_paper1_fixed_priority_metadata_gate', gate_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.validate_receipt(receipt_path, expected_operation='metadata')


def resource_gate(permit, directory):
    permit.assert_active()
    current = datetime.now(timezone.utc)
    require(datetime(2026, 10, 15, 5, 7, 25, tzinfo=timezone.utc) <= current
            < datetime(2026, 10, 17, 5, 7, 25, tzinfo=timezone.utc), 'CPU_recovery_authorization_window_closed')
    require(permit.paper2_reserve_bytes >= 5 * 1024**3 and 0 < permit.max_new_bytes <= MAX_JSON,
            'metadata_2MiB_cap_and_Paper2_5GiB_reserve_required')
    require(shutil.disk_usage(directory).free >= permit.required_free_bytes + MAX_JSON,
            'disk_floor_plus_Paper2_reserve_required')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-restore-root', type=Path, required=True)
    parser.add_argument('--source-acceptance-root', type=Path, required=True)
    parser.add_argument('--old-work-root', type=Path)
    parser.add_argument('--backup-head', type=Path)
    parser.add_argument('--backup-head-sha256')
    parser.add_argument('--backup-manifest', type=Path)
    parser.add_argument('--backup-manifest-sha256')
    parser.add_argument('--priority-gate', type=Path, required=True)
    parser.add_argument('--priority-receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = safe_path(args.output)
    require(output.suffix == '.json' and not output.exists(), 'new_exclusive_JSON_output_required')
    permit = priority_permit(args.priority_gate, args.priority_receipt)
    resource_gate(permit, output.parent)
    result = review(args.source_restore_root, args.source_acceptance_root, args.old_work_root,
                    args.backup_head, args.backup_head_sha256, args.backup_manifest, args.backup_manifest_sha256)
    resource_gate(permit, output.parent)
    result['metadata_slot_sha256'] = permit.receipt_sha256
    data = (json.dumps(result, indent=2, allow_nan=False) + '\n').encode()
    require(len(data) <= min(MAX_JSON, permit.max_new_bytes), 'report_too_large')
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(data)
    resource_gate(permit, output.parent)
    print(json.dumps({'status': result['status'], 'output': str(output), 'sha256': digest(data), 'training_authorization': False}))


if __name__ == '__main__':
    main()
