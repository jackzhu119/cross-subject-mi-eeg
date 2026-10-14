"""Next dot step: metadata/package binding only; no new runtime or EEG reads."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import isolated_training_runtime as runtime
import transition_target_gate as transition


def preflight(args):
    files = runtime.fixed_checkout(args.code_revision)
    parent = Path(__file__).resolve().parent
    for path in (Path(__file__), Path(transition.__file__),
            parent / 'transition_plan.template.json', parent / 'transition_plan.schema.json',
            parent.parent / 'formal_numerical_execution/audit_full_diagnostic_bundle.py'):
        rel = str(path.relative_to(runtime.ROOT))
        committed = subprocess.check_output(['git', '-C', str(runtime.ROOT), 'show', args.code_revision + ':' + rel])
        if path.is_symlink() or path.read_bytes() != committed:
            raise ValueError('uncommitted_preflight_file')
        files[rel] = runtime.sha(path)
    out = args.output_dir
    if out.exists() or out.is_symlink() or out.parent.resolve() != Path('/workspace'):
        raise ValueError('new_direct_workspace_evidence_directory_required')
    forbidden = (runtime.ROOT, Path('/workspace/.venvs/paper2-gpu'), Path('/workspace/paper1-readonly-probe/data'), Path('/workspace/mi-eeg-cloud'))
    if any(out.resolve().is_relative_to(p.resolve()) or p.resolve().is_relative_to(out.resolve()) for p in forbidden):
        raise ValueError('preflight_output_overlaps_protected_work')
    # All stdout/errors below are evidence for this operation, never an
    # automatic retry. The donor script is stdlib-only and never imports torch.
    donor = runtime.donor_observation(args.donor_python)
    if donor['python_version'] != runtime.FROZEN_PAPER1_PYTHON:
        raise ValueError('candidate_is_not_original_paper1_python_do_not_create_environment')
    if out.resolve().is_relative_to(Path(donor['prefix']).resolve()):
        raise ValueError('preflight_output_inside_actual_donor')
    out.mkdir(exist_ok=False)
    runtime.emit(out / 'gpu_donor_inventory.json', donor)
    mapping = runtime.ROOT / 'research_runs/REDESIGN_HANDOFF_20261014/source_r2_mapping.json'
    plan = runtime.ROOT / 'research_runs/REDESIGN_HANDOFF_20261014/runtime_transition/transition_plan.template.json'
    pending = transition.review(runtime.ROOT, old_root=args.old_work_root,
        mapping=mapping, mapping_sha='7d5ec2e9ddec16d2be5cb3778037c96dabb6559b8c208ad4cca9923c67407663', plan=plan)
    runtime.emit(out / 'transition_target_metadata.json', pending)
    private = {'status': 'AUDITED_PACKAGE_LOCAL_PATH_NOT_SUPPLIED',
               'required_sha256': transition.FULL_PACKAGE_SHA}
    if args.diagnostic_package:
        path = runtime.ROOT / 'research_runs/REDESIGN_HANDOFF_20261014/formal_numerical_execution/audit_full_diagnostic_bundle.py'
        spec = importlib.util.spec_from_file_location('private_package_readonly_auditor', path)
        auditor = importlib.util.module_from_spec(spec); spec.loader.exec_module(auditor)
        private = auditor.audit_bundle(args.diagnostic_package, runtime.ROOT)
    runtime.emit(out / 'private_full_package_binding.json', private)
    result = {'status': 'RUNTIME_PREFLIGHT_RECORDED_NO_SOURCE_ACCEPTANCE_OR_TRAINING',
        'code_revision': args.code_revision, 'execution_files': files,
        'donor_inventory_sha256': runtime.sha(out / 'gpu_donor_inventory.json'),
        'private_package_binding_sha256': runtime.sha(out / 'private_full_package_binding.json'),
        'transition_target_metadata_sha256': runtime.sha(out / 'transition_target_metadata.json'),
        'donor_gpu_import_verified': False, 'isolated_environment_created': False,
        'CPU_source_acceptance_run': False, 'target_EEG_read': False, 'new_fits': 0,
        'training_authorization': False, 'original_budget_changed': False,
        'Pod_queried_or_stopped': False, 'output_dir': str(out)}
    runtime.emit(out / 'preflight_receipt.json', result)
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-revision', required=True)
    parser.add_argument('--donor-python', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--old-work-root', type=Path)
    parser.add_argument('--diagnostic-package', type=Path)
    preflight(parser.parse_args())


if __name__ == '__main__':
    main()
