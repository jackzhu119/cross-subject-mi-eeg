"""Bind ONE future CPU source acceptance to the actual isolated GPU runtime.

Imports actual trainer dependencies but never creates a model/CUDA tensor,
reads target EEG, registers a job, authorizes training or changes accounting.
The previously completed diagnostic acceptance is not re-run by this wrapper.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.metadata as metadata
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
import sysconfig

sys.path.insert(0, str(Path(__file__).resolve().parent))
import isolated_training_runtime as runtime

ROOT = Path(__file__).resolve().parents[3]


def exact_imports(receipt):
    if platform.python_version() != runtime.FROZEN_PAPER1_PYTHON:
        raise ValueError('paper1_original_python_version_required')
    env = Path(receipt['environment']).resolve()
    if Path(sys.prefix).resolve() != env or sys.prefix == sys.base_prefix:
        raise ValueError('acceptance_not_running_in_prepared_isolated_runtime')
    expected_site = env / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'
    sys_sites = [Path(p).resolve() for p in sys.path if p.endswith('site-packages')]
    if sys_sites != [expected_site.resolve()] or not sys.dont_write_bytecode:
        raise ValueError('acceptance_requires_no_inheritance_no_user_site_no_bytecode')
    standard = Path(sysconfig.get_path('stdlib')).resolve()
    allowed_paths = {str(Path(__file__).resolve().parent), str(expected_site.resolve()),
        str(standard), str(standard / 'lib-dynload'),
        str(standard.parent / f'python{sys.version_info.major}{sys.version_info.minor}.zip')}
    if any(str(Path(p).resolve()) not in allowed_paths for p in sys.path):
        raise ValueError('acceptance_foreign_sys_path_not_allowed')
    cache = env / 'readonly-acceptance-cache'
    # Imports can create font/cache configuration. Keep those writes in the
    # isolated child, never in paper2 or a shared home directory.
    for key, suffix in (('MPLCONFIGDIR', 'matplotlib'), ('XDG_CACHE_HOME', 'xdg'),
                        ('TORCH_HOME', 'torch'), ('HF_HOME', 'huggingface'),
                        ('NUMBA_CACHE_DIR', 'numba')):
        os.environ[key] = str(cache / suffix)
    linked = receipt['linked_gpu_components']
    for name, original in linked.items():
        path = expected_site / name
        if not path.is_symlink() or path.resolve() != Path(original).resolve():
            raise ValueError('prepared_gpu_component_binding_changed')
    if runtime.sha(runtime.REQ) != receipt['requirements_sha256']:
        raise ValueError('requirements_changed_after_runtime_preparation')
    package_names = {'scikit-learn': 'sklearn', 'pytest': 'pytest'}
    imports = {}
    for line in runtime.REQ.read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        name, version = line.split('==')
        if metadata.version(name) != version:
            raise ValueError('pinned_training_dependency_version_changed:' + name)
        module = importlib.import_module(package_names.get(name, name.replace('-', '_')))
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(expected_site.resolve()):
            raise ValueError('lightweight_dependency_resolved_outside_child:' + name)
        imports[name] = {'version': version, 'file': str(path), 'sha256': runtime.sha(path)}
    for name in ('torch', 'torchaudio'):
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        if module.__version__ != '2.8.0+cu128' or not path.is_relative_to(Path(linked[name]).resolve()):
            raise ValueError('donated_gpu_pair_import_not_exact:' + name)
        imports[name] = {'version': module.__version__, 'file': str(path), 'sha256': runtime.sha(path)}
    import torch
    if torch.version.cuda != '12.8':
        raise ValueError('donated_torch_cuda_version_not_exact')
    return imports


def run(args):
    runtime.fixed_checkout(args.code_revision)
    wrapper_rel = str(Path(__file__).relative_to(ROOT))
    if Path(__file__).read_bytes() != subprocess.check_output(['git', '-C', str(ROOT), 'show', args.code_revision + ':' + wrapper_rel]):
        raise ValueError('uncommitted_runtime_acceptance_wrapper')
    if args.runtime_receipt.is_symlink():
        raise ValueError('runtime_receipt_symlink')
    receipt = json.loads(args.runtime_receipt.read_text())
    if receipt.get('status') != 'ISOLATED_RUNTIME_PREPARED_IMPORT_AND_SOURCE_ACCEPTANCE_PENDING' or receipt.get('code_revision') != args.code_revision:
        raise ValueError('prepared_runtime_receipt_required_same_revision')
    if args.runtime_receipt.resolve() != Path(receipt['environment']).resolve() / 'runtime_preparation.json':
        raise ValueError('runtime_receipt_not_in_prepared_child')
    observed = runtime.donor_observation(Path(receipt['donor_metadata']['donor_python']))
    if runtime.identity(observed) != runtime.identity(receipt['donor_post_metadata']):
        raise ValueError('gpu_donor_changed_since_runtime_preparation')
    imports = exact_imports(receipt)
    from importlib.util import spec_from_file_location, module_from_spec
    path = ROOT / 'research_runs/REDESIGN_HANDOFF_20261014/formal_numerical_execution/accept_source_numerics.py'
    spec = spec_from_file_location('actual_runtime_source_acceptance', path)
    acceptance = module_from_spec(spec); spec.loader.exec_module(acceptance)
    args.runtime_role = 'training'
    # The existing implementation calls training.load_source19 on CPU and
    # separately audits the exact full diagnostic private package, never target.
    code = acceptance.run(args)
    final = runtime.donor_observation(Path(receipt['donor_metadata']['donor_python']))
    if runtime.identity(final) != runtime.identity(observed):
        raise ValueError('gpu_donor_changed_during_source_acceptance')
    report_path = args.output_dir / 'formal_source_acceptance.json'
    report = json.loads(report_path.read_text())
    if code != 0 or report.get('training_authorization') is not False:
        raise ValueError('training_runtime_source_or_private_package_gate_pending')
    bound = {'status': 'ACTUAL_TRAINING_RUNTIME_SOURCE_MATCH_REVIEW_AND_RECOVERY_PENDING',
        'code_revision': args.code_revision, 'runtime_receipt_sha256': runtime.sha(args.runtime_receipt),
        'formal_source_acceptance_sha256': runtime.sha(report_path),
        'private_full_package_sha256': acceptance.FULL_PACKAGE_SHA,
        'imported_packages': imports, 'GPU_donor_metadata_unchanged': True,
        'runtime_GPU_computation_verified': False, 'no_CUDA_tensor_or_model_created': True,
        'target_EEG_read': False, 'new_fits': 0, 'training_authorization': False,
        'old_task_transition_authorized': False, 'budget_transition_authorized': False,
        'checkpoint_and_backup_transition_verified': False, 'target_restoration_verified': False}
    runtime.emit(args.output_dir / 'runtime_bound_acceptance.json', bound)
    print(json.dumps(bound, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--code-revision', required=True)
    p.add_argument('--runtime-receipt', type=Path, required=True)
    p.add_argument('--data-dir', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--diagnostic-package', type=Path, required=True)
    p.add_argument('--old-work-root', type=Path)
    run(p.parse_args())


if __name__ == '__main__':
    main()
