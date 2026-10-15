"""ONE future CPU import/source acceptance of the separately repaired runtime.

Never installs, restores raw files, invokes a diagnostic, constructs a model,
performs CUDA work, registers/resumes a job, or grants training authority.
The in-memory import-binding view is NOT a preparation-success receipt.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata as metadata
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile

HERE = Path(__file__).absolute().parent
BASE_REVISION = '1efe9d1ba2ab8671ad1bf76c360e067fb63fd7ac'
ENVIRONMENT = Path('/workspace/paper1-training-runtime-cp312-run01')
REPAIR_SHA = '7ebd6080181ec3bb5d2c9faf74d754af68c0ea4eea48978467df713e8465f8a1'
REPAIR_BYTES = 442155
RECEIPT_SHA = '0e487c7c8dcc83006681c8bdb066254da4184d49ab9f6ce96a07ad53d7cf092b'
DONOR_SHA = '3a83a9cf93cca3e9813056645bc73f26a9429ee6f1f7bc06f2ae78a1c36471b1'
JOURNAL_SHA = 'db82e716e22ce7bcf48e6d7908f279b4b8a5ae9ececbd67714ec083d6aa89b0d'
FULL_SHA = '2871f422755bf5d0b939d0db59fc41547b192d6c939db1a6a13b97a91ba49ae9'
FORMAL_SHA = 'a4c6c3f7beadf6ce0c927c6e4b9d20b6d37ff3bc2c033ad4b4fd836ca38a6b0d'
MANIFEST_SHA = 'e553d65cd86e5309e077ccfea21a9bee6020c5d9d5040de12089c2b859770b86'
REQ_SHA = '7322d4f85f25064ef8c29efa502c67417fc9b8a0d3297692263c1e618804769a'
BASE_OWNED = 869490688
HISTORICAL_ENV_DU = 869425152
GIB = 1024 ** 3
TRANSITION = 'research_runs/REDESIGN_HANDOFF_20261014/runtime_transition/'
FORMAL = 'research_runs/REDESIGN_HANDOFF_20261014/formal_numerical_execution/'
MANIFEST_REL = 'research_runs/REDESIGN_HANDOFF_20261014/official_source_diagnostic/source_official_manifest.json'
EXECUTION_FILES = [TRANSITION + n for n in ('isolated_training_runtime.py', 'donor_gpu_inventory.py', 'accept_training_runtime_source.py')]
EXECUTION_FILES += [FORMAL + n for n in ('accept_source_numerics.py', 'audit_full_diagnostic_bundle.py')]
EXECUTION_FILES += ['research_runs/REDESIGN_HANDOFF_20261015/runtime/priority_gate.py', MANIFEST_REL,
    'research_runs/REDESIGN_CLOUD_20261013/requirements.txt']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def no_symlink(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('acceptance_input_or_output_symlink')
    return path


def regular_bytes(path, maximum, *, size=None, expected=None):
    path = no_symlink(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
        raise ValueError('bounded_regular_acceptance_input_required')
    data = path.read_bytes()
    if len(data) > maximum or (size is not None and len(data) != size) or (expected is not None and digest(data) != expected):
        raise ValueError('acceptance_input_bytes_or_sha_changed')
    return data


def parse(data):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate_json_key')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_json')))


def archive_members(data):
    members, expanded = {}, 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for item in archive:
            name = item.name
            if (not item.isfile() or name.startswith('/') or '\\' in name
                    or any(p in ('', '.', '..') for p in name.split('/'))
                    or str(PurePosixPath(name)) != name or name in members
                    or item.size > 2 * 1024**2 or len(members) >= 40):
                raise ValueError('unsafe_or_unexpected_repair_archive_member')
            expanded += item.size
            if expanded > 4 * 1024**2:
                raise ValueError('repair_archive_expansion_limit')
            body = archive.extractfile(item).read(2 * 1024**2 + 1)
            if len(body) != item.size:
                raise ValueError('repair_archive_member_size')
            members[name] = body
    manifest = parse(members['MANIFEST.json'])
    records = manifest['payloads']
    if len(records) != 30 or len(members) != 31:
        raise ValueError('complete_repair_archive_inventory_required')
    found = set()
    for row in records:
        if (set(row) != {'path', 'bytes', 'sha256'} or row['path'] in found
                or row['path'] == 'MANIFEST.json' or row['path'] not in members):
            raise ValueError('repair_manifest_coverage')
        body = members[row['path']]
        if type(row['bytes']) is not int or len(body) != row['bytes'] or digest(body) != row['sha256']:
            raise ValueError('repair_manifest_member_bytes_or_sha')
        found.add(row['path'])
    if found != set(members) - {'MANIFEST.json'}:
        raise ValueError('repair_manifest_complete_coverage_required')
    return members


def original_preparation_absent():
    old = ENVIRONMENT / 'runtime_preparation.json'
    if old.exists() or old.is_symlink():
        raise ValueError('original_preparation_receipt_must_remain_absent')


def repair_binding(args):
    members = archive_members(regular_bytes(args.repair_archive, REPAIR_BYTES, size=REPAIR_BYTES, expected=REPAIR_SHA))
    if no_symlink(args.runtime_receipt) != ENVIRONMENT / 'runtime_repair_run01.json':
        raise ValueError('exact_independent_repair_receipt_path_required')
    receipt_data = regular_bytes(args.runtime_receipt, 6554, size=6554, expected=RECEIPT_SHA)
    if receipt_data != members['environment/runtime_repair_run01.json']:
        raise ValueError('actual_repair_receipt_not_archived_receipt')
    journal = regular_bytes(ENVIRONMENT / 'repair_run01.journal.jsonl', 22896, size=22896, expected=JOURNAL_SHA)
    if journal != members['environment/repair_run01.journal.jsonl']:
        raise ValueError('actual_repair_journal_changed')
    receipt, donor = parse(receipt_data), parse(members['inputs/gpu_donor_inventory.json'])
    if digest(members['inputs/gpu_donor_inventory.json']) != DONOR_SHA:
        raise ValueError('archived_donor_identity_changed')
    if (receipt.get('status') != 'REPAIRED_PREPARED_IMPORT_SOURCE_REVIEW_PENDING'
            or receipt.get('original_base_revision') != BASE_REVISION
            or receipt.get('environment') != str(ENVIRONMENT)
            or receipt.get('donor_report_sha256') != DONOR_SHA):
        raise ValueError('separate_successful_repair_identity_required')
    for key in ('runtime_import_acceptance_passed', 'source_acceptance_passed',
                'old_accounting_reconciled', 'old_cost_known', 'target_EEG_read',
                'budget_reset', 'budget_expanded', 'training_authorization'):
        if receipt.get(key) is not False:
            raise ValueError('repair_scope_or_pending_gate_changed:' + key)
    if type(receipt.get('new_fits')) is not int or receipt['new_fits'] != 0:
        raise ValueError('repair_new_fits_must_be_zero')
    original_preparation_absent()
    for name in ('pyvenv.cfg', 'gpu-donor-constraints.txt', 'runtime_plan.json',
                 'wheel-resolution.json', 'resolved-lightweight-wheels.txt'):
        body = regular_bytes(ENVIRONMENT / name, 2 * 1024**2)
        if body != members['environment/' + name]:
            raise ValueError('repaired_environment_binding_changed:' + name)
    for name in ('ttx.1', 'isympy.1'):
        body = regular_bytes(ENVIRONMENT / 'share/man/man1' / name, 8192)
        if body != members['installed-manpages/' + name]:
            raise ValueError('installed_approved_manpage_changed:' + name)
    return receipt, donor, members


def verify_checkout(root):
    root = no_symlink(root)
    git = ['git', '--no-replace-objects', '-c', 'credential.helper=', '-c', 'core.hooksPath=/dev/null', '-C', str(root)]
    if subprocess.check_output(git + ['rev-parse', 'HEAD'], text=True).strip() != BASE_REVISION:
        raise ValueError('original_exact_clean_checkout_required')
    if subprocess.check_output(git + ['status', '--porcelain', '--untracked-files=all'], text=True).strip():
        raise ValueError('original_checkout_must_remain_clean')
    checked = {}
    for rel in EXECUTION_FILES:
        committed = subprocess.check_output(git + ['show', BASE_REVISION + ':' + rel])
        if regular_bytes(root / rel, 2 * 1024**2) != committed:
            raise ValueError('fixed_original_execution_file_changed:' + rel)
        checked[rel] = digest(committed)
    return checked


def module_from(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def import_binding_view_from_repair(receipt, donor):
    """Transient old import-check arguments only; never write an old receipt."""
    return {'environment': receipt['environment'],
        'linked_gpu_components': {row['name']: row['path'] for row in donor['components']},
        'requirements_sha256': REQ_SHA}


def verify_source_files(data_dir, code_dir):
    """Read only the18 named source originals; no array transform or target I/O."""
    manifest = parse(regular_bytes(code_dir / MANIFEST_REL, 16384, expected=MANIFEST_SHA))
    rows = manifest['files']
    expected = {f'A{i:02d}{s}.mat' for i in range(1, 10) for s in ('T', 'E')}
    if len(rows) != 18 or {r['filename'] for r in rows} != expected or sum(r['bytes'] for r in rows) != 779873919:
        raise ValueError('frozen_source_inventory_changed')
    directory = no_symlink(data_dir / 'bnci')
    # Check complete presence before reading even the first MAT byte.
    paths = []
    for row in rows:
        path = no_symlink(directory / row['filename'])
        if not path.is_file() or path.stat().st_size != row['bytes']:
            raise ValueError('source_originals_not_restored_exact18_required')
        paths.append((path, row))
    identities = []
    for path, row in paths:
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024**2), b''):
                h.update(block)
        if h.hexdigest() != row['sha256']:
            raise ValueError('source_original_sha256_mismatch')
        identities.append({'filename': row['filename'], 'bytes': row['bytes'], 'sha256': row['sha256']})
    return identities



def source_restore_binding(path, data_dir, source_files, gate):
    path = no_symlink(path)
    if path != no_symlink(data_dir) / 'source_restore_run01.json':
        raise ValueError('independent_source_restore_receipt_must_bind_actual_source_root')
    raw = regular_bytes(path, 128 * 1024)
    receipt = parse(raw)
    if gate.review.get('source_restore_receipt_sha256') != digest(raw):
        raise ValueError('actual_source_restore_receipt_not_bound_to_parent_review')
    if (receipt.get('status') != 'SOURCE18_EXACT_BYTES_RESTORED_NUMERICAL_ACCEPTANCE_PENDING'
            or receipt.get('source_expected_files') != 18
            or receipt.get('source_expected_bytes') != 779873919
            or receipt.get('official_manifest_sha256') != MANIFEST_SHA
            or receipt.get('source_root') != str(no_symlink(data_dir))):
        raise ValueError('completed_new_container_source_restore_receipt_required')
    for key in ('diagnostic_rerun', 'runtime_imported', 'target_EEG_accessed',
                'training_authorization', 'budget_reset'):
        if receipt.get(key) is not False:
            raise ValueError('source_restore_scope_must_remain_raw_only:' + key)
    if type(receipt.get('new_fits')) is not int or receipt['new_fits'] != 0:
        raise ValueError('source_restore_fits_must_be_zero')
    rows = receipt.get('files')
    if not isinstance(rows, list) or len(rows) != 18:
        raise ValueError('source_restore_complete18_receipt_rows_required')
    observed = []
    for row in rows:
        if (not isinstance(row, dict) or row.get('status') not in
                ('RESTORED_OFFICIAL_EXACT_BYTES', 'REUSED_VERIFIED_CACHE')
                or set(row) - {'filename', 'status', 'bytes', 'sha256', 'response_route'}):
            raise ValueError('source_restore_exact_official_or_verified_cache_row_required')
        observed.append({key: row[key] for key in ('filename', 'bytes', 'sha256')})
    if sorted(observed, key=lambda row: row['filename']) != sorted(source_files, key=lambda row: row['filename']):
        raise ValueError('source_restore_receipt_does_not_match_actual_strict_source_bytes')
    finished = datetime.fromisoformat(receipt['finished_at_utc'].replace('Z', '+00:00'))
    reviewed = datetime.fromisoformat(gate.review['reviewed_at_utc'].replace('Z', '+00:00'))
    if (finished.tzinfo is None or finished.utcoffset().total_seconds() != 0
            or reviewed < finished):
        raise ValueError('new_actual_acceptance_review_must_follow_source_restore_completion')
    return digest(raw)


def installed_versions(receipt, donor):
    site = ENVIRONMENT / 'lib/python3.12/site-packages'
    expected = receipt['installed_versions_metadata_only']
    observed = {}
    for dist in metadata.distributions(path=[str(site)]):
        name = re.sub(r'[-_.]+', '-', dist.metadata['Name']).lower()
        if name in observed:
            raise ValueError('duplicate_runtime_distribution_metadata')
        observed[name] = dist.version
    if len(observed) != 97 or observed != expected:
        raise ValueError('actual_complete97_runtime_metadata_changed')
    if (observed.get('numpy'), observed.get('scipy'), observed.get('torch'), observed.get('torchaudio'), observed.get('triton')) != (
            '2.3.5', '1.17.0', '2.8.0+cu128', '2.8.0+cu128', '3.4.0'):
        raise ValueError('exact_repaired_scientific_versions_required')
    for component in donor['components']:
        p = site / component['name']
        if not p.is_symlink() or p.resolve() != Path(component['path']).resolve():
            raise ValueError('repaired_gpu_donor_component_link_changed')
    return observed


def allocated(path):
    path = Path(path)
    if not path.exists() or path.is_symlink():
        return 0
    if path.is_file():
        return path.stat().st_blocks * 512
    return sum(p.lstat().st_blocks * 512 for p in (path, *path.rglob('*')) if not p.is_symlink())


def resources(gate, args, attempt):
    gate.check()
    # Carry the successful repair's original total, including outside-child
    # evidence allocation. This is not a fresh3GiB installation allowance.
    used = max(BASE_OWNED, allocated(ENVIRONMENT) + BASE_OWNED - HISTORICAL_ENV_DU)
    # Include the source bridge's journal/log/receipt as well as its MAT cache;
    # the receipt is already inside this root, so do not count it twice.
    for path in (args.data_dir, args.output_dir, args.log_file, attempt,
                 args.repair_archive, args.diagnostic_package, args.formal_acceptance_package):
        used += allocated(path)
    if used + 64 * 1024 > min(3 * GIB, gate.max_new_bytes):
        raise ValueError('original_total3gib_ownership_cap_exceeded')
    free = shutil.disk_usage(ENVIRONMENT.parent).free
    if free < max(10 * GIB, gate.min_free_bytes) + max(5 * GIB, gate.reserve_bytes):
        raise ValueError('runtime_source_acceptance_paper2_disk_floor')
    return {'observed_total_owned_bytes': used, 'free_bytes': free,
        'original_total_cap_bytes': 3 * GIB, 'budget_reset': False}


def fresh_output(args):
    out = no_symlink(args.output_dir)
    if out.parent != ENVIRONMENT.parent or out.exists():
        raise ValueError('brand_new_direct_workspace_acceptance_output_required')
    attempt = no_symlink(out.with_name(out.name + '.attempt.json'))
    if attempt.exists():
        raise ValueError('acceptance_attempt_already_consumed_no_automatic_retry')
    log = no_symlink(args.log_file)
    if (log.parent != ENVIRONMENT.parent or log == attempt or log == out
            or (log.exists() and (not log.is_file() or log.stat().st_size != 0))):
        raise ValueError('separate_direct_workspace_acceptance_log_required')
    inputs = [args.code_dir, ENVIRONMENT, args.data_dir, args.repair_archive,
              args.diagnostic_package, args.formal_acceptance_package, args.review_record, args.priority_receipt, args.source_restore_receipt]
    if any(log == Path(p).absolute() for p in inputs):
        raise ValueError('acceptance_log_overlaps_protected_input')
    if any(out == Path(p).absolute() or Path(p).absolute().is_relative_to(out) or out.is_relative_to(Path(p).absolute()) for p in inputs):
        raise ValueError('acceptance_output_overlaps_protected_inputs')
    return attempt


def require_bounded_cpu_window(gate):
    # The delivered outer command is fixed to timeout300s. A tighter review
    # must not silently retain that longer external watchdog.
    if (gate.max_wall_seconds != 300 or
            (gate.end - datetime.now(timezone.utc)).total_seconds() < 310):
        raise ValueError('reviewed300second_CPU_watchdog_with310second_slot_headroom_required')


def run(args):
    if not re.fullmatch('[0-9a-f]{40}', args.acceptance_revision):
        raise ValueError('immutable_adapter_revision_required')
    script_sha = digest(Path(__file__).read_bytes())
    gate_module = module_from(HERE / 'acceptance_gate.py', 'paper1_repaired_acceptance_gate')
    gate = gate_module.Gate(args.review_record, args.priority_receipt,
        'source_cpu_acceptance', args.acceptance_revision, script_sha)
    gate.check()
    files = verify_checkout(args.code_dir)
    receipt, donor, members = repair_binding(args)
    regular_bytes(args.diagnostic_package, 134436, size=134436, expected=FULL_SHA)
    regular_bytes(args.formal_acceptance_package, 12299, size=12299, expected=FORMAL_SHA)
    attempt = fresh_output(args)
    source_files = verify_source_files(args.data_dir, args.code_dir)
    source_restore_sha = source_restore_binding(args.source_restore_receipt, args.data_dir, source_files, gate)
    before_resources = resources(gate, args, attempt)
    versions = installed_versions(receipt, donor)
    runtime = module_from(args.code_dir / (TRANSITION + 'isolated_training_runtime.py'), 'isolated_training_runtime')
    runtime.fixed_checkout(BASE_REVISION)
    before = runtime.donor_observation(Path(donor['donor_python']))
    if runtime.identity(before) != runtime.identity(donor):
        raise ValueError('gpu_donor_changed_after_repair')
    require_bounded_cpu_window(gate)
    claim = {'status': 'ONE_ACTUAL_REPAIRED_RUNTIME_ACCEPTANCE_ATTEMPT_CONSUMED',
        'adapter_sha256': digest(Path(__file__).read_bytes()), 'acceptance_revision': args.acceptance_revision,
        'original_base_revision': BASE_REVISION, 'repair_archive_sha256': REPAIR_SHA,
        'repair_receipt_sha256': RECEIPT_SHA, 'review_sha256': gate.review_sha256,
        'slot_sha256': gate.slot_sha256, 'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'new_fits': 0, 'training_authorization': False, 'automatic_retry': False}
    with attempt.open('x') as stream:
        json.dump(claim, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    if digest(Path(__file__).read_bytes()) != script_sha or verify_checkout(args.code_dir) != files:
        raise ValueError('adapter_or_fixed_execution_code_changed_before_imports')
    gate.check()
    wrapper = module_from(args.code_dir / (TRANSITION + 'accept_training_runtime_source.py'), 'paper1_original_import_checker_only')
    binding_view = import_binding_view_from_repair(receipt, donor)
    # Calls ONLY the original import checker, not its old-preparation run().
    imports = wrapper.exact_imports(binding_view)
    import torch
    if torch.cuda.is_initialized():
        raise ValueError('acceptance_cuda_must_not_be_initialized')
    resources(gate, args, attempt)
    if digest(Path(__file__).read_bytes()) != script_sha or verify_checkout(args.code_dir) != files:
        raise ValueError('adapter_or_fixed_execution_code_changed_before_source_dispatch')
    # The original acceptor imports this sibling by name; bind its authenticated
    # source explicitly without adding the new delivery directory to sys.path.
    module_from(args.code_dir / (FORMAL + 'audit_full_diagnostic_bundle.py'), 'audit_full_diagnostic_bundle')
    acceptance = module_from(args.code_dir / (FORMAL + 'accept_source_numerics.py'), 'paper1_actual_repaired_source_acceptor')
    formal_args = argparse.Namespace(code_revision=BASE_REVISION, data_dir=args.data_dir,
        output_dir=args.output_dir, diagnostic_package=args.diagnostic_package,
        old_work_root=args.old_work_root, runtime_role='training')
    result = acceptance.run(formal_args)  # One actual consumer load, no old diagnostic.
    if result != 0:
        raise ValueError('actual_runtime_source_or_private_package_acceptance_not_complete')
    if torch.cuda.is_initialized():
        raise ValueError('source_acceptance_unexpected_CUDA_initialization')
    final_resources = resources(gate, args, attempt)
    after = runtime.donor_observation(Path(donor['donor_python']))
    if runtime.identity(before) != runtime.identity(after):
        raise ValueError('gpu_donor_changed_during_actual_acceptance')
    if digest(Path(__file__).read_bytes()) != script_sha or verify_checkout(args.code_dir) != files:
        raise ValueError('adapter_or_fixed_execution_code_changed_during_acceptance')
    original_preparation_absent()
    repair_binding(args)  # Exact independent receipt/journal/config/manpage preservation.
    if digest(regular_bytes(args.source_restore_receipt, 128 * 1024)) != source_restore_sha:
        raise ValueError('new_source_restore_receipt_changed_during_acceptance')
    report_path = args.output_dir / 'formal_source_acceptance.json'
    report_data = regular_bytes(report_path, 2 * 1024**2)
    report = parse(report_data)
    if (report.get('status') != 'SOURCE_NUMERICAL_ACCEPTANCE_MATCH_TRAINING_STILL_BLOCKED'
            or report.get('training_consumer_imports_verified') is not True
            or report.get('private_full_package_independently_verified') is not True
            or report.get('training_authorization') is not False
            or report.get('target_EEG_read') is not False or report.get('new_fits') != 0):
        raise ValueError('independent_actual_acceptance_report_required')
    bound = {'status': 'REPAIRED_ACTUAL_TRAINING_RUNTIME_SOURCE_MATCH_OTHER_GATES_PENDING',
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'acceptance_revision': args.acceptance_revision, 'original_base_revision': BASE_REVISION,
        'adapter_sha256': digest(Path(__file__).read_bytes()),
        'repair_archive_sha256': REPAIR_SHA, 'independent_repair_receipt_sha256': RECEIPT_SHA,
        'repair_journal_sha256': JOURNAL_SHA, 'donor_report_sha256': DONOR_SHA,
        'new_container_source_restore_receipt_sha256': source_restore_sha,
        'historical_full_diagnostic_package_sha256': FULL_SHA,
        'historical_formal_diagnostic_archive_sha256': FORMAL_SHA,
        'historical_diagnostic_executed': False, 'original_preparation_receipt_created': False,
        'formal_source_acceptance_sha256': digest(report_data),
        'source_originals_verified': source_files, 'strict_trial_and_aggregate_hash_gate_passed': True,
        'actual_imported_packages': imports, 'actual_metadata_versions': versions,
        'execution_file_sha256': files, 'donor_metadata_unchanged': True,
        'review_sha256': gate.review_sha256, 'slot_sha256': gate.slot_sha256,
        'pre_resources': before_resources, 'post_resources': final_resources,
        'actual_training_runtime_imports_verified': True, 'CUDA_initialized': False,
        'GPU_computation_verified': False, 'source_arrays_serialized': False,
        'new_fits': 0, 'target_EEG_read': False, 'target_fits': 0,
        'old_accounting_reconciled': False, 'old_cost_known': False,
        'budget_reset': False, 'budget_expanded': False, 'budget_transition_authorized': False,
        'checkpoint_and_backup_transition_verified': False, 'target_mapping_and_restore_accepted': False,
        'training_authorization': False,
        'observation_boundary': 'Gate and resources checked before/after imports and synchronous source load; outer timeout enforces wall bound; no claim of continuous mid-filter monitoring.'}
    gate.check()
    runtime.emit(args.output_dir / 'repaired_runtime_bound_acceptance.json', bound)
    print(json.dumps(bound, indent=2), flush=True)
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--acceptance-revision', required=True)
    for name in ('code-dir', 'repair-archive', 'runtime-receipt', 'diagnostic-package',
                 'formal-acceptance-package', 'source-restore-receipt', 'data-dir', 'output-dir', 'review-record',
                 'priority-receipt', 'log-file'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--old-work-root', type=Path)
    return run(p.parse_args())


if __name__ == '__main__':
    raise SystemExit(main())
