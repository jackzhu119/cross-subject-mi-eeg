"""Read-only metadata preparation; never authorizes or launches scientific work.

Only named JSON manifests/records are read. No raw EEG, tensors, checkpoints,
credentials, R2 calls, Torch imports, subprocesses or runtime modifications.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

OLD_JOB = '20261014T071918Z-exploratory-89b0c07d'
OLD_REVISION = '05e683e91e2bb39b977970d04402221761e575d2'
OLD_STARTED = '2026-10-14T07:07:45.290107+00:00'
OLD_DEADLINE = '2026-10-14T15:07:45.290107+00:00'
FULL_PACKAGE_SHA = '2871f422755bf5d0b939d0db59fc41547b192d6c939db1a6a13b97a91ba49ae9'
SOURCE_RECEIPT_SHA = '66c5aa472809cf29fe68b7b56401c4f0aa4b4f577156425a1f4e1fc20d45d8dd'
SOURCE_TRIAL_SHA = 'e142e927228d9c46afb872fa649335cc6e9ec286b1d291b94ac0e43a6d59e4cf'
SOURCE_PATH = 'research_runs/Q8-E001/results/source_files.json'
SOURCE_SHA = '0ccef780ed5bfbc2d430b8caf0c108641fb230a2dc27e4189e7e771c999f64a6'
TARGET_PATH = 'research_runs/REDESIGN_SOURCE_SELECTION_20261012/evidence/dataset_sources/dreyer_nemar_acquisition_edf_manifest.json'
TARGET_SHA = '2cfdf35aa7990df880826d1b84d1230e0bda3c9393c17d3ec6e27b7b311d2bf2'
ROSTER_PATH = 'research_runs/REDESIGN_EXPLORATORY_20261013/results/raw-qc-543feb2f/raw_only_roster.json'
ROSTER_SHA = 'f578c8d0ee4a2500532f473c06f561390f698072f353c479accef639707df4a1'
MAX_JSON = 10 * 1024**2
GIB = 1024**3


def hash_bytes(blob):
    return hashlib.sha256(blob).hexdigest()


def reject_symlinks(path):
    path = Path(path).absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('symlink_rejected')
    return path


def read_json(path, expected_sha=None):
    path = reject_symlinks(path)
    if not path.is_file() or path.stat().st_size > MAX_JSON:
        raise ValueError('bounded_regular_json_required')
    # Read, hash, and parse one byte snapshot; duplicate keys/NaN are rejected.
    blob = path.read_bytes()
    if len(blob) > MAX_JSON or (expected_sha and hash_bytes(blob) != expected_sha):
        raise ValueError('json_sha256_mismatch')
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError('duplicate_json_key')
            obj[key] = value
        return obj
    def invalid(_):
        raise ValueError('nonfinite_json_rejected')
    return json.loads(blob, object_pairs_hook=unique, parse_constant=invalid), hash_bytes(blob)


def relative(value):
    if (not isinstance(value, str) or not value or '\\' in value
            or any(ord(c) < 32 for c in value)):
        raise ValueError('unsafe_relative_path')
    if PurePosixPath(value).is_absolute() or any(x in ('', '.', '..') for x in value.split('/')):
        raise ValueError('unsafe_relative_path')
    return value


def identity(repo):
    """Inspect byte-bound frozen metadata only; never opens its raw-data paths."""
    repo = reject_symlinks(repo)
    source, source_sha = read_json(repo / SOURCE_PATH, SOURCE_SHA)
    target, _ = read_json(repo / TARGET_PATH, TARGET_SHA)
    roster, _ = read_json(repo / ROSTER_PATH, ROSTER_SHA)
    read_json(repo / 'research_runs/REDESIGN_EXPLORATORY_20261013/evidence/source_exact_input_fingerprints_receipt.json', SOURCE_RECEIPT_SHA)
    fingerprints = reject_symlinks(repo / 'research_runs/REDESIGN_EXPLORATORY_20261013/evidence/source_exact_input_fingerprints.csv')
    if not fingerprints.is_file() or fingerprints.stat().st_size > MAX_JSON or hash_bytes(fingerprints.read_bytes()) != SOURCE_TRIAL_SHA:
        raise ValueError('frozen_source_trial_fingerprints_changed')
    entries = [{'path': 'bnci/' + Path(r['path']).name, 'bytes': r['bytes'], 'sha256': r['sha256']} for r in source]
    entries += [{'path': 'dreyer_acquisition/' + r['path'], 'bytes': r['size'], 'sha256': r['checksum']} for r in target['files']]
    if (len(source) != 18 or len(target['files']) != 174 or len({r['path'] for r in entries}) != 192
            or sum(r['bytes'] for r in entries[:18]) != 779873919
            or sum(r['bytes'] for r in entries[18:]) != 2515343396):
        raise ValueError('frozen_raw_manifest_identity_changed')
    events = roster['events']
    counts = Counter(r['subject_id'] for r in events)
    if (len(roster['participants']) != 85 or len(set(roster['participants'])) != 85
            or len(events) != 6800 or len({r['event_id'] for r in events}) != 6800
            or set(counts) != set(roster['participants']) or set(counts.values()) != {80}
            or roster['technical_exclusions'] != ['A17', 'A41']
            or roster['prior_use'] != 'unknown' or roster['independent_confirmation_qualified'] is not False
            or roster['target_fits'] != 0 or roster['target_predictions_computed'] is not False):
        raise ValueError('frozen_target_roster_identity_changed')
    if {r['source_file'] for r in events} - {r['path'] for r in target['files']}:
        raise ValueError('target_events_outside_frozen_acquisition_manifest')
    return entries, {
        'source_files': 18, 'source_raw_bytes': 779873919,
        'source_files_manifest_sha256': source_sha,
        'source_exact_input_receipt_sha256': SOURCE_RECEIPT_SHA,
        'source_exact_trial_fingerprints_sha256': SOURCE_TRIAL_SHA,
        'target_files': 174, 'target_raw_bytes': 2515343396,
        'target_manifest_sha256': TARGET_SHA, 'target_roster_sha256': ROSTER_SHA,
        'target_retained_participants': 85, 'target_retained_events': 6800,
        'provider_exclusions': ['A17', 'A41'], 'prior_exposure': 'unknown',
        'independent_confirmation_qualified': False,
    }


def mapping_review(mapping, expected):
    """Coverage review mirrors r2_only.validate_mapping without network access.

    Partial mappings are reported as incomplete, never passed to the importer.
    Existing keys must be authentic; no prefix/name guess is generated here.
    """
    if mapping.get('schema_version') != 1 or not isinstance(mapping.get('files'), list):
        raise ValueError('r2_mapping_schema')
    expected = {r['path']: r for r in expected}
    observed, keys = {}, set()
    for row in mapping['files']:
        if not isinstance(row, dict):
            raise ValueError('r2_mapping_row_schema')
        name, key = relative(row.get('path')), relative(row.get('object_key'))
        if name in observed or key in keys:
            raise ValueError('duplicate_mapping')
        if name not in expected:
            raise ValueError('r2_mapping_extra_path')
        if type(row.get('bytes')) is not int or any(row.get(k) != expected[name][k] for k in ('bytes', 'sha256')):
            raise ValueError('r2_mapping_not_frozen_identity')
        observed[name] = row
        keys.add(key)
    missing = set(expected) - set(observed)
    return {
        'status': 'COMPLETE_LOCAL_MAPPING_METADATA_ONLY' if not missing else 'INCOMPLETE_MAPPING_TRAINING_BLOCKED',
        'covered_files': len(observed), 'missing_source_files': sum(p.startswith('bnci/') for p in missing),
        'missing_target_files': sum(p.startswith('dreyer_acquisition/') for p in missing),
        'missing_raw_bytes': sum(expected[p]['bytes'] for p in missing),
        'all_192_file_identities_mapped': not missing,
        'objects_accessible': None, 'remote_raw_hashes_verified': None,
        'object_keys_generated_or_guessed': False,
        'minimum_import_free_bytes_if_all_raw_absent': sum(r['bytes'] for r in expected.values()) + 6 * GIB,
        'additional_runtime_training_space_included': False,
    }


def observed_json(path):
    path = reject_symlinks(path)
    if not path.exists():
        return None, {'state': 'NOT_OBSERVED', 'sha256': None}
    value, sha = read_json(path)
    return value, {'state': 'OBSERVED_LOCAL_METADATA_NOT_REMOTE_VERIFIED', 'sha256': sha}


def old_record_review(root, current=None):
    """Read only known, non-secret accounting JSON in the historical layout."""
    current = current or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError('timezone_required')
    report = {
        'old_job_id': OLD_JOB, 'old_code_revision': OLD_REVISION,
        'original_authorized_at_utc': OLD_STARTED, 'original_expires_at_utc': OLD_DEADLINE,
        'original_budget_clock_state': 'EXPIRED' if current >= datetime.fromisoformat(OLD_DEADLINE) else 'NOT_EXPIRED_AT_REVIEW_TIME',
        'same_machine_identity_proven': None, 'budget_migration_authorized': False,
        'budget_clock_rebased': False, 'old_registration_modified': False,
        'counters': None, 'zero_fit_checkpoint_absence_verified': None,
        'private_checkpoint_backup_verified': None, 'records': {},
    }
    if root is None:
        report['state'] = 'OLD_WORK_ROOT_NOT_SUPPLIED_NOT_OBSERVED'
        return report
    root = reject_symlinks(root)
    if not root.is_dir():
        report['state'] = 'OLD_WORK_ROOT_NOT_ACCESSIBLE_NOT_OBSERVED'
        return report
    job = root / ('code-' + OLD_REVISION) / 'research_runs/REDESIGN_CLOUD_20261013/jobs' / OLD_JOB
    names = {
        'registration': root / 'execution_registration.json',
        'budget_origin': root / 'budget_origin.json',
        'launch_record': job / 'launch_record.json',
        'code_identity': job / 'code_identity.json',
        'runtime_lock': job / 'runtime_lock.json',
        'budget_authorization': job / 'budget_authorization.json',
        'job_status': job / 'job_status.json',
        'source_budget_ledger': job / 'source/budget_ledger.json',
    }
    values = {}
    for name, path in names.items():
        values[name], report['records'][name] = observed_json(path)
    for name in ('registration', 'launch_record', 'job_status'):
        value = values[name]
        if value is not None and value.get('job_id') != OLD_JOB:
            raise ValueError('old_job_identity_mismatch:' + name)
    for name in ('registration', 'launch_record', 'code_identity'):
        value = values[name]
        if value is not None and value.get('code_revision') != OLD_REVISION:
            raise ValueError('old_revision_identity_mismatch:' + name)
    budget = values['budget_authorization']
    origin = values['budget_origin']
    if origin is not None and origin.get('started_at_utc') != OLD_STARTED:
        raise ValueError('original_budget_origin_changed')
    if budget is not None:
        if (budget.get('authorized_at_utc') != OLD_STARTED or budget.get('expires_at_utc') != OLD_DEADLINE
                or budget.get('maximum_gpu_hours') != 8 or budget.get('maximum_neural_fits') != 26
                or budget.get('maximum_optimizer_updates') != 34440
                or budget.get('maximum_total_usd') != 10 or budget.get('non_gpu_reserved_usd') != 2
                or budget.get('config_sha256') != '8ba78d4ead0e41fc5a5fc6f9890b750f0bdfdaba74a57efab5422b43d57feff0'
                or budget.get('target_fits_authorized') is not False):
            raise ValueError('original_budget_identity_changed')
        lock = values['runtime_lock']
        if lock is not None and any(budget.get(k) != lock.get(k) for k in ('machine_hostname', 'gpu_uuid')):
            raise ValueError('old_budget_runtime_identity_mismatch')
    ledgers = [v for v in (values['job_status'], values['source_budget_ledger']) if v is not None]
    counters = []
    for value in ledgers:
        fields = ('actual_neural_fits_started', 'actual_neural_fits_completed', 'optimizer_updates')
        if any(type(value.get(k)) is not int or value[k] < 0 for k in fields):
            raise ValueError('old_counters_missing_or_invalid')
        if value.get('target_fits') != 0 or value.get('target_predictions_computed') is not False:
            raise ValueError('old_target_boundary_changed')
        counters.append({k: value[k] for k in fields})
    if counters and any(v != counters[0] for v in counters):
        raise ValueError('old_status_ledger_counters_disagree')
    report['counters'] = counters[0] if counters else None
    report['state'] = ('OLD_RECORD_METADATA_OBSERVED_IDENTITY_AND_BACKUP_REVIEW_REQUIRED'
                       if any(v is not None for v in values.values())
                       else 'OLD_WORK_ROOT_ACCESSIBLE_ACCOUNTING_NOT_OBSERVED')
    # Absence of a ledger/checkpoint does not establish zero fits or backup.
    return report


def plan_review(plan):
    """A plan is deliberately unable to carry PASS/authorization statements."""
    allowed = {'schema_version', 'record_kind', 'old_job_id', 'old_code_revision',
               'original_authorized_at_utc', 'original_expires_at_utc',
               'private_full_diagnostic_package_sha256', 'source_exact_input_receipt_sha256',
               'source_exact_trial_fingerprints_sha256', 'training_authorization',
               'new_budget_authorization', 'pending_gates', 'scope'}
    if (not isinstance(plan, dict) or set(plan) != allowed
            or plan.get('schema_version') != 1 or plan.get('record_kind') != 'PLAN_ONLY_NOT_AUTHORIZATION'
            or plan.get('old_job_id') != OLD_JOB or plan.get('old_code_revision') != OLD_REVISION
            or plan.get('original_authorized_at_utc') != OLD_STARTED
            or plan.get('original_expires_at_utc') != OLD_DEADLINE
            or plan.get('private_full_diagnostic_package_sha256') != FULL_PACKAGE_SHA
            or plan.get('source_exact_input_receipt_sha256') != SOURCE_RECEIPT_SHA
            or plan.get('source_exact_trial_fingerprints_sha256') != SOURCE_TRIAL_SHA
            or plan.get('training_authorization') is not False
            or plan.get('new_budget_authorization') is not None):
        raise ValueError('transition_plan_cannot_replace_original_budget_or_authorize_training')
    gates = plan.get('pending_gates')
    required = {'actual_training_runtime_source_acceptance', 'old_identity_and_counters',
                'checkpoint_and_remote_backup', 'explicit_machine_budget_amendment',
                'dreyer_actual_r2_mapping', 'dreyer_full_raw_and_tensor_identity', 'reviewed_execution_transition'}
    if not isinstance(gates, dict) or set(gates) != required:
        raise ValueError('transition_plan_required_gates_changed')
    for g in gates.values():
        if (not isinstance(g, dict) or set(g) != {'state', 'evidence_path', 'evidence_sha256', 'reviewer'}
                or g.get('state') not in {'UNKNOWN', 'EVIDENCE_PRESENT_REVIEW_REQUIRED', 'BLOCKED'}
                or any(g[k] is not None and not isinstance(g[k], str) for k in ('evidence_path', 'reviewer'))
                or (g['evidence_sha256'] is not None
                    and (not isinstance(g['evidence_sha256'], str)
                         or not re.fullmatch('[0-9a-f]{64}', g['evidence_sha256'])))):
            raise ValueError('transition_plan_must_not_clear_unknown_gates')
    return {'state': 'PLAN_INSPECTED_NOT_AN_EXECUTION_AUTHORIZATION', 'pending_gates': sorted(gates)}


def review(repo, *, old_root=None, mapping=None, mapping_sha=None, plan=None):
    expected, frozen = identity(repo)
    result = {
        'schema_version': 1, 'status': 'TRANSITION_AND_TARGET_GATES_PENDING_TRAINING_BLOCKED',
        'reviewed_at_utc': datetime.now(timezone.utc).isoformat(), 'frozen_metadata': frozen,
        'observation_scope': 'THIS_PROCESS_LOCAL_FILESYSTEM_ONLY_NOT_REMOTE_POD_OBSERVATION',
        'private_full_diagnostic_package_required_sha256': FULL_PACKAGE_SHA,
        'old_task': old_record_review(old_root),
        'target_mapping': {'status': 'NOT_SUPPLIED', 'objects_accessible': None, 'remote_raw_hashes_verified': None},
        'training_authorization': False, 'target_EEG_read': False, 'GPU_fits_started': 0,
        'R2_network_requests': 0, 'credentials_read': False, 'files_modified': False,
        'same_machine_resume_authorized': False, 'cross_machine_resume_authorized': False,
        'budget_deadline_extended': False, 'pod_stop_requested': False,
    }
    if mapping is not None:
        if not mapping_sha or not re.fullmatch('[0-9a-f]{64}', mapping_sha):
            raise ValueError('mapping_sha256_required')
        data, actual_sha = read_json(mapping, mapping_sha)
        result['target_mapping'] = {**mapping_review(data, expected), 'mapping_sha256': actual_sha}
    if plan is not None:
        data, actual_sha = read_json(plan)
        result['transition_plan'] = {**plan_review(data), 'sha256': actual_sha}
    result['next_gates'] = [
        'Independently review actual training-runtime source acceptance with audited full package binding.',
        'Recover or explicitly mark unobserved old accounting/checkpoint records; do not treat absence as zero.',
        'Verify immutable checkpoint/ledger/log backup and unresolved update intents before a reviewed transition.',
        'Record a separate explicit machine/budget amendment; preserve original deadline and counters.',
        'Supply authentic complete 192-file R2 mapping; verify remote/local raw bytes and frozen target trial identities later.',
        'Keep Dreyer exploratory with unknown prior exposure; target fitting, BN updates and selection remain prohibited.',
    ]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--old-work-root', type=Path)
    parser.add_argument('--r2-mapping', type=Path)
    parser.add_argument('--r2-mapping-sha256')
    parser.add_argument('--plan', type=Path)
    args = parser.parse_args()
    try:
        result = review(args.repo, old_root=args.old_work_root, mapping=args.r2_mapping,
                        mapping_sha=args.r2_mapping_sha256, plan=args.plan)
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError):
        print(json.dumps({'status': 'METADATA_REVIEW_BLOCKED', 'training_authorization': False,
                          'next_step': 'Review missing, unsafe or changed metadata; no raw EEG or network was read.'}))
        raise SystemExit(2) from None
    print(json.dumps(result, sort_keys=True, indent=2))
    raise SystemExit(3)  # Deliberate pending gates, never a training-ready exit.


if __name__ == '__main__':
    main()
