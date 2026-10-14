"""Exact formal source input acceptance. Never trains or resumes a job.

This CPU-only acceptance records independent pending gates; a source match is
never a data_prepare PASS or an authorization to launch source/target fitting.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
EXPECTED_OLD_JOB = '20261014T071918Z-exploratory-89b0c07d'
FULL_PACKAGE_SHA = '2871f422755bf5d0b939d0db59fc41547b192d6c939db1a6a13b97a91ba49ae9'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def saved_records(work_root):
    """Observe only non-secret old accounting records; no identity assumption."""
    if work_root is None:
        return {'observed': False, 'reason': 'old_work_root_not_supplied'}, {}
    registration = work_root / 'execution_registration.json'
    if not registration.is_file() or registration.is_symlink():
        return {'observed': False, 'reason': 'old_registration_not_accessible'}, {}
    record = json.loads(registration.read_text())
    if record.get('job_id') != EXPECTED_OLD_JOB:
        raise ValueError('different_old_task_registration_do_not_touch')
    revision = record.get('code_revision', '')
    if len(revision) != 40 or any(x not in '0123456789abcdef' for x in revision):
        raise ValueError('invalid_old_revision')
    job = work_root / ('code-' + revision) / 'research_runs/REDESIGN_CLOUD_20261013/jobs' / EXPECTED_OLD_JOB
    paths = [registration, work_root / 'budget_origin.json']
    paths += [job / n for n in ('launch_record.json', 'runtime_lock.json', 'budget_authorization.json',
        'job_status.json', 'source/budget_ledger.json')]
    hashes = {}
    for path in paths:
        if path.is_symlink():
            raise ValueError('old_accounting_record_symlink')
        if path.is_file():
            hashes[str(path)] = sha(path)
    # Do not use this observation to assert that a new Pod is the old machine.
    return {'observed': True, 'job_id': EXPECTED_OLD_JOB, 'record_hashes': hashes,
            'identity_transition_authorized': False, 'budget_transition_authorized': False}, hashes


def check_checkout(revision):
    actual = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != revision:
        raise ValueError('acceptance_checkout_revision_mismatch')
    paths = ['research_runs/REDESIGN_CLOUD_20261013/' + n for n in (
        'config/experiment.json', 'config/numerical_execution_v1.json', 'scripts/formal_core_inputs.py',
        'scripts/prepare_data.py', 'scripts/train_exploratory.py', 'scripts/validate_source.py',
        'scripts/infer_exploratory.py', 'scripts/numerical_review_gate.py')]
    paths += [str(Path(__file__).relative_to(ROOT)),
        'research_runs/REDESIGN_HANDOFF_20261014/formal_numerical_execution/audit_full_diagnostic_bundle.py']
    identities = {}
    for name in paths:
        path = ROOT / name
        committed = subprocess.check_output(['git', '-C', str(ROOT), 'show', revision + ':' + name])
        if path.is_symlink() or path.read_bytes() != committed:
            raise ValueError('uncommitted_execution_file:' + name)
        identities[name] = hashlib.sha256(committed).hexdigest()
    return identities


def import_binding(path, name):
    tree = ast.parse(path.read_text())
    return any(isinstance(node, ast.ImportFrom) and node.module == 'formal_core_inputs'
        and any(alias.name == name for alias in node.names) for node in ast.walk(tree))


def run(args):
    files = check_checkout(args.code_revision)
    before, record_hashes = saved_records(args.old_work_root)
    if args.output_dir.exists() or args.output_dir.is_symlink():
        raise ValueError('acceptance_output_already_exists_no_overwrite')
    if args.output_dir.resolve().is_relative_to(ROOT) or args.output_dir.resolve().is_relative_to(args.data_dir.resolve()):
        raise ValueError('acceptance_output_must_be_outside_checkout_and_raw_data')
    args.output_dir.mkdir(parents=False, exist_ok=False)
    scripts = ROOT / 'research_runs/REDESIGN_CLOUD_20261013/scripts'
    sys.path.insert(0, str(scripts))
    import formal_core_inputs as formal
    bindings = {name: import_binding(scripts / name, 'load_source19')
                for name in ('train_exploratory.py', 'validate_source.py')}
    prepare_tree = ast.parse((scripts / 'prepare_data.py').read_text())
    bindings['prepare_data.py'] = any(isinstance(node, ast.Import)
        and any(a.name == 'formal_core_inputs' and a.asname == 'source' for a in node.names)
        for node in ast.walk(prepare_tree))
    if not all(bindings.values()):
        raise ValueError('actual_consumers_not_bound_to_formal_path')
    loader = formal.load_source19
    imports_verified = False
    if args.runtime_role == 'training':
        import torch
        import torchaudio
        import train_exploratory as training
        import validate_source as validation
        if (torch.__version__.split('+')[0], torchaudio.__version__.split('+')[0], torch.version.cuda) != ('2.8.0', '2.8.0', '12.8'):
            raise ValueError('actual_training_runtime_pair_not_verified')
        if training.load_source19 is not loader or validation.load_source19 is not loader:
            raise ValueError('actual_training_consumer_binding_mismatch')
        loader = training.load_source19
        imports_verified = True
    config = json.loads((scripts.parent / 'config/experiment.json').read_text())
    arrays, rows, audit = loader(args.data_dir / 'bnci', config)
    # The formal loader itself enforces the original complete strict gate.
    formal.verify_source_inputs(arrays, rows, audit)
    if audit['n_raw_files'] != 18 or audit['n_runs'] != 108 or len(rows) != 2592:
        raise ValueError('complete_source_acceptance_inventory_required')
    package_verified = False
    package_report = {'status': 'PRIVATE_FULL_PACKAGE_NOT_ACCESSIBLE_NOT_AUDITED'}
    if args.diagnostic_package:
        from audit_full_diagnostic_bundle import audit_bundle
        package_report = audit_bundle(args.diagnostic_package, ROOT)
        package_verified = package_report['status'] == 'FULL_DIAGNOSTIC_PRIVATE_BUNDLE_AUDIT_PASSED_TRAINING_BLOCKED'
    for path, value in record_hashes.items():
        if not Path(path).is_file() or sha(path) != value:
            raise ValueError('old_accounting_record_changed_during_acceptance')
    complete = imports_verified and package_verified
    report = {'status': 'SOURCE_NUMERICAL_ACCEPTANCE_MATCH_TRAINING_STILL_BLOCKED' if complete
              else 'SOURCE_NUMERICS_MATCH_PRIVATE_PACKAGE_OR_TRAINING_RUNTIME_PENDING',
        'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'code_revision': args.code_revision,
        'source_complete_exact_hash_gate_passed': True, 'source_array_hashes': audit['array_hashes'],
        'source_files': 18, 'source_runs': 108, 'source_trials': 2592,
        'numerical_execution': formal.numerical_identity(), 'consumer_static_bindings': bindings,
        'training_consumer_imports_verified': imports_verified,
        'private_full_package_independently_verified': package_verified,
        'private_full_package_sha256': FULL_PACKAGE_SHA if package_verified else None,
        'private_package_audit': package_report, 'old_accounting_observation': before,
        'old_accounting_records_unchanged': True, 'target_complete_restoration_verified': False,
        'target_frozen_input_mapping_verified': False, 'runtime_GPU_preflight_verified': False,
        'old_machine_identity_proven': False, 'budget_resume_authorized': False,
        'checkpoint_and_verified_backup_gates_passed': False,
        'execution_file_identities': files, 'training_authorization': False, 'new_fits': 0,
        'target_EEG_read': False, 'target_predictions_computed': False,
        'source_arrays_serialized_or_replaced': False,
        'historical_generation_BLAS_identity_established': False}
    (args.output_dir / 'formal_source_acceptance.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)
    return 0 if complete else 3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-revision', required=True)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--diagnostic-package', type=Path)
    parser.add_argument('--old-work-root', type=Path)
    parser.add_argument('--runtime-role', choices=['diagnostic', 'training'], default='diagnostic')
    args = parser.parse_args()
    raise SystemExit(run(args))


if __name__ == '__main__':
    main()
