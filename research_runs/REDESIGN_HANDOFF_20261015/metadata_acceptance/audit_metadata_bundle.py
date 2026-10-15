"""Audit the supplied metadata-only archive; never execute its payloads.

Only a fixed public Git checkout and small local evidence archive are read.
This does not contact a Pod, import numerical/GPU packages or authorise runtime
construction, a scientific input acceptance or a model fit.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[3]
REVISION = '1efe9d1ba2ab8671ad1bf76c360e067fb63fd7ac'
ARCHIVE_BYTES = 8589
ARCHIVE_SHA = '7a652a96eded108155188a366d4cf4d930e6ea404566cf44e9773ba0ce6f69d0'
INVENTORY_SHA = '3a83a9cf93cca3e9813056645bc73f26a9429ee6f1f7bc06f2ae78a1c36471b1'
PREFIX = 'research_runs/REDESIGN_HANDOFF_20261015/'
HELPER = 'research_runs/REDESIGN_HANDOFF_20261014/runtime_transition/donor_gpu_inventory.py'
FIXED_FILES = {HELPER, PREFIX + 'runtime/priority_gate.py',
    PREFIX + 'runtime/compare_donor_transcript.py',
    PREFIX + 'runtime/donor_metadata_transcript.json',
    PREFIX + 'runtime/paper2_priority_slot.PLAN_ONLY.json'}
PAYLOADS = {'dispatch/' + n for n in ('completion.json', 'fixed-code-identity.json',
    'metadata-command.sh', 'metadata-dispatch.log', 'metadata-slot.json',
    'preflight.json', 'source-fetch.log')}
PAYLOADS |= {'metadata/' + n for n in ('SHA256SUMS.txt', 'exit-code.txt',
    'gpu_donor_inventory.json', 'metadata_slot_check.json', 'observed-end-utc.txt', 'worker.log')}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def parsed(raw):
    def unique(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('duplicate_metadata_key')
            value[key] = item
        return value
    value = json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_metadata')))
    if not isinstance(value, dict):
        raise ValueError('metadata_object_required')
    return value


def read_members(raw):
    """Bounded in-memory tar read, without extraction or executing shell/code."""
    result = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        total = 0
        for member in archive:
            p = PurePosixPath(member.name)
            if (not member.isfile() or p.is_absolute() or '..' in p.parts
                    or str(p) != member.name or member.name in result
                    or member.name not in PAYLOADS | {'manifest.json'}):
                raise ValueError('unsafe_duplicate_or_unexpected_archive_member')
            total += member.size
            if member.size > 128 * 1024 or total > 256 * 1024:
                raise ValueError('metadata_archive_expansion_limit')
            result[member.name] = archive.extractfile(member).read(member.size + 1)
            if len(result[member.name]) != member.size:
                raise ValueError('archive_member_size_mismatch')
    if set(result) != PAYLOADS | {'manifest.json'}:
        raise ValueError('metadata_archive_inventory_mismatch')
    return result


def git_bytes(path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', REVISION + ':' + path])


def trusted_module(path, name):
    local = ROOT / path
    if local.is_symlink() or local.read_bytes() != git_bytes(path):
        raise ValueError('audit_dependency_not_fixed:' + path)
    spec = importlib.util.spec_from_file_location(name, local)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def audit(path):
    path = Path(path).absolute()
    if (any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file()
            or path.stat().st_size != ARCHIVE_BYTES):
        raise ValueError('original_bounded_metadata_archive_required')
    raw = path.read_bytes()
    if digest(raw) != ARCHIVE_SHA:
        raise ValueError('original_metadata_archive_sha_mismatch')
    files = read_members(raw)
    manifest = parsed(files['manifest.json'])
    if manifest.get('fixed_commit') != REVISION or len(manifest.get('files', [])) != 13:
        raise ValueError('fixed_metadata_manifest_required')
    seen = set()
    for row in manifest['files']:
        name = row['path']
        if (name not in PAYLOADS or name in seen or type(row['bytes']) is not int
                or row['bytes'] != len(files[name]) or digest(files[name]) != row['sha256']):
            raise ValueError('metadata_manifest_payload_mismatch')
        seen.add(name)
    if seen != PAYLOADS:
        raise ValueError('metadata_manifest_incomplete')
    fixed = parsed(files['dispatch/fixed-code-identity.json'])
    if fixed.get('commit') != REVISION or set(fixed['reviewed_file_sha256']) != FIXED_FILES:
        raise ValueError('five_fixed_source_identities_required')
    for name, sha in fixed['reviewed_file_sha256'].items():
        if digest(git_bytes(name)) != sha:
            raise ValueError('fixed_public_source_sha_mismatch:' + name)
    canonical = git_bytes(PREFIX + 'DOT_NEXT.md').split(b'```bash\n')[1].split(b'```')[0]
    if files['dispatch/metadata-command.sh'] != canonical:
        raise ValueError('executed_metadata_command_not_canonical')
    checksum_names = set()
    for line in files['metadata/SHA256SUMS.txt'].decode().splitlines():
        sha, name = line.split('  ', 1)
        key = 'metadata/' + name
        if key in checksum_names or key not in PAYLOADS or digest(files[key]) != sha:
            raise ValueError('inner_metadata_checksum_mismatch')
        checksum_names.add(key)
    if checksum_names != {'metadata/' + n for n in ('exit-code.txt',
            'gpu_donor_inventory.json', 'metadata_slot_check.json', 'observed-end-utc.txt', 'worker.log')}:
        raise ValueError('inner_metadata_checksum_inventory_mismatch')
    inventory_raw = files['metadata/gpu_donor_inventory.json']
    if len(inventory_raw) != 22450 or digest(inventory_raw) != INVENTORY_SHA:
        raise ValueError('complete_inventory_bytes_mismatch')
    inventory = parsed(inventory_raw)
    comparator = trusted_module(PREFIX + 'runtime/compare_donor_transcript.py', 'audit_fixed_comparator')
    comparison = comparator.compare(inventory,
        parsed(git_bytes(PREFIX + 'runtime/donor_metadata_transcript.json')), digest(git_bytes(HELPER)))
    if (inventory['prefix'], inventory['base_prefix'], inventory['base_executable'], inventory['cache_tag']) != (
            '/usr', '/usr', '/usr/bin/python3', 'cpython-312'):
        raise ValueError('observed_cp312_interpreter_identity_mismatch')
    prerequisites = inventory['isolated_venv_prerequisites']
    if prerequisites != {'venv_module_available': True, 'ensurepip_module_available': True,
            'packages_installed_by_inventory': False}:
        raise ValueError('existing_runtime_tooling_metadata_mismatch')
    if len(inventory['components']) != 24 or len(inventory['critical_module_files']) != 5:
        raise ValueError('complete_component_inventory_required')
    done = parsed(files['dispatch/completion.json'])
    start, end = (datetime.fromisoformat(done[k]) for k in ('started_utc', 'ended_utc'))
    if (start.utcoffset().total_seconds() != 0 or end.utcoffset().total_seconds() != 0
            or not 0 < (end - start).total_seconds() <= 60
            or done.get('exit_code') != 0 or done.get('automatic_retry') is not False
            or done.get('GPU_fit_started') is not False or files['metadata/exit-code.txt'] != b'0\n'
            or files['metadata/worker.log'] != b''):
        raise ValueError('single_successful_metadata_execution_required')
    gate = trusted_module(PREFIX + 'runtime/priority_gate.py', 'audit_fixed_priority')
    slot_raw = files['dispatch/metadata-slot.json']
    slot = gate._validate(slot_raw, 'metadata', start)
    gate._validate(slot_raw, 'metadata', end)
    post = parsed(files['metadata/metadata_slot_check.json'])
    if post != {'slot_sha256': digest(slot_raw), 'postcheck_error': None,
            'continuous_mid_command_slot_monitor': False, 'training_authorization': False}:
        raise ValueError('same_slot_postcheck_record_mismatch')
    observed_end = datetime.fromisoformat(files['metadata/observed-end-utc.txt'].decode().strip())
    if not start <= observed_end <= end:
        raise ValueError('metadata_report_time_outside_dispatch')
    dispatch = files['dispatch/metadata-dispatch.log'].decode()
    if 'DOT_METADATA_COMPLETE_SAME_SLOT_VERIFIED_NO_GPU_NO_EEG_NO_INSTALL\n' not in dispatch:
        raise ValueError('metadata_dispatch_acknowledgement_missing')
    logged = parsed(dispatch.split('\n', 1)[1])
    if logged.get('inventory_file_sha256') != INVENTORY_SHA or any(logged.get(k) != v for k, v in comparison.items()):
        raise ValueError('logged_metadata_comparison_mismatch')
    return {'status': 'CP312_METADATA_ARCHIVE_INDEPENDENT_AUDIT_PASSED_RUNTIME_STILL_PENDING',
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'archive_bytes': len(raw), 'archive_sha256': digest(raw), 'payloads_verified': len(PAYLOADS),
        'manifest_sha256': digest(files['manifest.json']), 'payload_manifest': manifest['files'],
        'fixed_execution_revision': REVISION, 'five_public_source_hashes_verified': fixed['reviewed_file_sha256'],
        'canonical_command_exact_byte_match': True, 'inner_checksums_verified': True,
        'inventory_bytes': len(inventory_raw), 'inventory_sha256': INVENTORY_SHA,
        'comparison': comparison, 'observed_runtime_metadata': {k: inventory[k] for k in (
            'python_version', 'donor_python', 'prefix', 'base_prefix', 'base_executable', 'cache_tag',
            'SOABI', 'platform', 'site_packages', 'isolated_venv_prerequisites')},
        'observed_GPU_distribution_count': len(inventory['distributions']),
        'observed_component_count': len(inventory['components']),
        'observed_critical_entry_files': inventory['critical_module_files'],
        'numerical_donor_observation_NOT_reused': inventory['numerical_donor_observation_not_reused'],
        'recorded_metadata_free_bytes_on_donor_prefix_filesystem': inventory['free_bytes'],
        'recorded_workspace_preflight': parsed(files['dispatch/preflight.json']),
        'metadata_execution': done, 'recorded_slot_sha256': digest(slot_raw),
        'historical_slot_valid_at_start_and_end': True,
        'same_slot_check_reported_and_canonical_controller_verified': True,
        'continuous_mid_command_monitoring_claimed': False,
        'old_metadata_slot_reusable_for_next_operation': False,
        'current_Pod_state_independently_observed_here': False,
        'metadata_hashes_independently_recomputed_from_live_Pod_files': False,
        'all_GPU_payload_bytes_verified': False, 'actual_training_runtime_verified': False,
        'source_input_acceptance_verified_by_this_metadata': False,
        'historical_2390byte_JSON_reconstructed_or_verified': False,
        'runtime_installation_authorization': False, 'training_authorization': False,
        'archive_payloads_executed': False, 'Pod_operations': False, 'EEG_read': False,
        'new_model_fits': 0, 'next_operation': 'fixed1efe_plan_only_with_NEW_dot_runtime_preparation_slot'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(audit(args.archive), indent=2))


if __name__ == '__main__':
    main()
