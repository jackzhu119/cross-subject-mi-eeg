"""Offline audit of the exact completed plan-only evidence, never a rerun.

Reads two supplied archives and fixed public Git objects. No archived command
is executed, no Pod/network/EEG/package/runtime operation is available here.
"""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[3]
REVISION = '1efe9d1ba2ab8671ad1bf76c360e067fb63fd7ac'
PLAN_SHA = 'bca300252a44997e46f102e689c6d1a10f16c91d079f8ed4eb3752acf68ad526'
META_SHA = '7a652a96eded108155188a366d4cf4d930e6ea404566cf44e9773ba0ce6f69d0'
REPORT_SHA = '3a83a9cf93cca3e9813056645bc73f26a9429ee6f1f7bc06f2ae78a1c36471b1'
STDOUT_SHA = 'e4852d1e2517abc69464c22e69658c2618d8e3950184fa40eb4c8a2af6ce5a0c'
HELPER = 'research_runs/REDESIGN_HANDOFF_20261014/runtime_transition/isolated_training_runtime.py'
INVENTORY = 'research_runs/REDESIGN_HANDOFF_20261014/runtime_transition/donor_gpu_inventory.py'
REQ = 'research_runs/REDESIGN_CLOUD_20261013/requirements.txt'
GATE = 'research_runs/REDESIGN_HANDOFF_20261015/runtime/priority_gate.py'
PAYLOADS = {'runtime-plan-slot.json', 'preflight.json', 'command.json',
            'plan.stdout.json', 'plan.stderr.log', 'completion.json'}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_archive(path, expected_bytes, expected_sha):
    path = Path(path).absolute()
    if (any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file()
            or path.stat().st_size != expected_bytes):
        raise ValueError('exact_regular_archive_required')
    raw = path.read_bytes()
    if digest(raw) != expected_sha:
        raise ValueError('archive_sha256_mismatch')
    result, total = {}, 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        for member in archive:
            p = PurePosixPath(member.name)
            total += member.size
            if (not member.isfile() or p.is_absolute() or '..' in p.parts
                    or str(p) != member.name or member.name in result
                    or member.size > 128 * 1024 or total > 256 * 1024):
                raise ValueError('unsafe_or_unbounded_archive_member')
            result[member.name] = archive.extractfile(member).read(member.size + 1)
            if len(result[member.name]) != member.size:
                raise ValueError('truncated_archive_member')
    return result


def parsed(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('duplicate_json_key')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_json')))


def git_bytes(path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', REVISION + ':' + path])


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit(plan_archive, metadata_archive):
    files = read_archive(plan_archive, 6463, PLAN_SHA)
    require(set(files) == PAYLOADS | {'MANIFEST.json'}, 'actual_uppercase_manifest_and_six_payloads_required')
    manifest = parsed(files['MANIFEST.json'])
    require(manifest.get('schema') == 'paper1-plan-only-evidence-v1'
            and len(manifest.get('payloads', [])) == 6, 'actual_manifest_schema_required')
    seen = set()
    for row in manifest['payloads']:
        name = row['path']
        require(name in PAYLOADS and name not in seen
                and type(row['bytes']) is int and row['bytes'] == len(files[name])
                and row['sha256'] == digest(files[name]), 'payload_manifest_mismatch')
        seen.add(name)
    require(seen == PAYLOADS, 'complete_six_payload_manifest_required')
    require(len(files['plan.stdout.json']) == 25128 and digest(files['plan.stdout.json']) == STDOUT_SHA,
            'exact_completed_plan_stdout_required')
    value = parsed(files['plan.stdout.json'])
    require(value.get('status') == 'ISOLATED_RUNTIME_PLAN_ONLY_REVIEW_REQUIRED'
            and value.get('code_revision') == REVISION, 'fixed_plan_status_required')
    require(set(value['execution_files']) == {HELPER, INVENTORY, REQ, GATE}, 'four_execution_files_required')
    for path, sha in value['execution_files'].items():
        require(digest(git_bytes(path)) == sha, 'fixed_git_file_sha_mismatch:' + path)
    require(value['donor_report_sha256'] == REPORT_SHA, 'audited_metadata_report_binding_required')
    previous = read_archive(metadata_archive, 8589, META_SHA)
    old_raw = previous['metadata/gpu_donor_inventory.json']
    require(len(old_raw) == 22450 and digest(old_raw) == REPORT_SHA, 'previous_complete_inventory_required')
    old, new = parsed(old_raw), value['donor_metadata']
    identity_keys = ('donor_python', 'prefix', 'base_prefix', 'base_executable', 'python_version',
        'SOABI', 'cache_tag', 'platform', 'site_packages', 'distributions', 'components',
        'critical_module_files', 'torch_gpu_dependency_pins', 'numerical_donor_observation_not_reused',
        'inventory_implementation_sha256', 'isolated_venv_prerequisites')
    require(all(old[k] == new[k] for k in identity_keys), 'fresh_donor_identity_changed')
    require(new['python_version'] == '3.12.3' and new['SOABI'] == 'cpython-312-x86_64-linux-gnu',
            'same_cp312_identity_required')
    for flag in ('cuda_packages_downloaded', 'donor_modified', 'source_acceptance_run',
                 'target_EEG_read', 'budget_updated', 'training_authorization'):
        require(value.get(flag) is False, 'plan_scope_changed:' + flag)
    require(type(value.get('new_fits')) is int and value['new_fits'] == 0, 'no_new_fit_required')
    for flag in ('CUDA_operation_performed', 'torch_imported_by_inventory', 'target_EEG_read',
                 'training_authorization', 'training_consumer_imports_verified', 'gpu_payload_exhaustively_hashed'):
        require(new.get(flag) is False, 'donor_metadata_scope_changed:' + flag)
    require(type(new.get('new_fits')) is int and new['new_fits'] == 0, 'no_new_donor_fit_required')
    environment = '/workspace/paper1-training-runtime-cp312-run01'
    require(value['environment'] == environment, 'exact_new_destination_required')
    command = parsed(files['command.json'])
    require(command == ['/usr/bin/python3', '-I', '-B',
        '/workspace/paper1-metadata-code-1efe9d1/' + HELPER,
        '--code-revision', REVISION, '--donor-python', '/usr/bin/python3',
        '--donor-report', '/workspace/paper1-cp312-metadata-20261015-run01/gpu_donor_inventory.json',
        '--environment', environment, '--priority-receipt',
        '/workspace/paper1-runtime-plan-20261015-run01/runtime-plan-slot.json'],
        'exact_plan_only_command_required')
    done, pre = parsed(files['completion.json']), parsed(files['preflight.json'])
    start, end = (datetime.fromisoformat(done[k]) for k in ('started_utc', 'ended_utc'))
    require(done.get('exit_code') == 0 and done.get('automatic_retry') is False
            and done.get('environment_created') is False and files['plan.stderr.log'] == b''
            and 0 < (end - start).total_seconds() <= 60, 'completed_no_install_execution_required')
    local_gate = ROOT / GATE
    require(not local_gate.is_symlink() and local_gate.read_bytes() == git_bytes(GATE), 'trusted_fixed_gate_required')
    spec = importlib.util.spec_from_file_location('offline_plan_fixed_gate', local_gate)
    gate = importlib.util.module_from_spec(spec); sys.modules[spec.name] = gate
    spec.loader.exec_module(gate)
    slot_raw = files['runtime-plan-slot.json']
    gate._validate(slot_raw, 'runtime_preparation', start)
    gate._validate(slot_raw, 'runtime_preparation', end)
    slot = parsed(slot_raw)
    require(digest(slot_raw) == value['paper2_priority_receipt_sha256'], 'exact_fresh_slot_binding_required')
    require(slot['max_new_bytes'] == value['actual_maximum_new_bytes'] == value['maximum_new_bytes'] == 3 * 1024**3
            and slot['min_free_bytes'] == value['minimum_remaining_free_bytes'] == 10 * 1024**3
            and slot['paper2_reserve_bytes'] == value['paper2_additional_reserved_bytes'] == 5 * 1024**3
            and value['actual_required_free_floor_bytes'] == 15 * 1024**3,
            'unchanged_storage_cap_and_actual_reserve_required')
    required = value['actual_maximum_new_bytes'] + value['actual_required_free_floor_bytes']
    require(pre['required_free_bytes'] == required == 18 * 1024**3
            and pre['destination_absent'] is True
            and pre['helper_sha256'] == value['execution_files'][HELPER]
            and pre['free_bytes'] >= required and value['observed_free_bytes'] >= required,
            'recorded_new_destination_and_disk_gate_required')
    return {
        'schema_version': 1,
        'status': 'COMPLETED_PLAN_ONLY_ARCHIVE_INDEPENDENT_REVIEW_PASSED_NO_REPEAT_REQUIRED',
        'archive_bytes': 6463, 'archive_sha256': PLAN_SHA, 'manifest_name': 'MANIFEST.json',
        'manifest_schema': manifest['schema'], 'verified_payloads': 6,
        'all_payload_sizes_sha256_verified': True, 'archive_commands_executed': False,
        'payload_manifest': manifest['payloads'], 'plan_stdout_bytes': 25128,
        'plan_stdout_sha256': STDOUT_SHA, 'fixed_execution_revision': REVISION,
        'four_execution_source_sha256_verified_against_git': value['execution_files'],
        'accepted_complete_donor_report_sha256': REPORT_SHA,
        'fresh_donor_identity_matches_previous_audited_report': True,
        'donor_distributions': len(new['distributions']), 'donor_components': len(new['components']),
        'donor_critical_file_identities': len(new['critical_module_files']),
        'recorded_command_without_prepare': command,
        'recorded_started_utc': done['started_utc'], 'recorded_ended_utc': done['ended_utc'],
        'recorded_elapsed_seconds': (end-start).total_seconds(), 'recorded_exit_code': 0,
        'slot_sha256': digest(slot_raw), 'slot_valid_at_recorded_start_and_end': True,
        'continuous_slot_monitoring_verified': False, 'same_permit_postcheck_receipt_present': False,
        'slot_current_or_reusable': False, 'recorded_destination': environment,
        'destination_absent_reported_by_preflight_and_completion': True,
        'destination_presence_independently_observed_live_here': False,
        'recorded_free_bytes_at_helper_check': value['observed_free_bytes'],
        'required_initial_bytes_cap_plus_floor_plus_reserve': required,
        'actual_required_remaining_free_bytes': value['actual_required_free_floor_bytes'],
        'new_environment_byte_cap': value['actual_maximum_new_bytes'],
        'evidence_limits': [
            'This is the completed direct fixed-helper plan; no later outer controller is retroactively claimed to have run.',
            'Slot time validity is independently checked against archived start/end, not live/continuous control or a separate postcheck receipt.',
            'Donor metadata/RECORD/entry hash identities match prior evidence; exhaustive CUDA payload bytes and actual child imports remain unverified.',
            'Destination absence, Paper2 complete_exported/idle state and disk availability are recorded dot/helper observations, not current Pod queries.',
            'The parent initial manifest-name/schema parsing error is outside this original archive; no synthetic error payload is added.',
            'No venv, installation, exact numerical package runtime, GPU arithmetic or source-input acceptance is proved by a plan.',
            'Old accounting/cumulative GPU hours/checkpoints/backup/target-mapping gates remain unresolved by this evidence.',
        ],
        'new_fits': 0, 'runtime_installation_performed_by_review': False,
        'actual_training_runtime_accepted': False, 'source_hash_acceptance_passed': False,
        'training_authorization': False, 'next_step': 'No repeated plan; separately reviewed preparation controller and NEW dot slot only.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan-archive', type=Path, required=True)
    parser.add_argument('--metadata-archive', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.plan_archive, args.metadata_archive), indent=2))


if __name__ == '__main__':
    main()
