"""Prepare a NEW lightweight environment; never install or alter CUDA/torch.

Default: plan only. --prepare is a separate dot-operated storage operation,
NOT job registration, budget authorization, source acceptance or model execution.
The exact donor inventory must first be independently reviewed. All writes are
confined to a new environment/evidence directory. Donor sites are not inherited.
"""
from __future__ import annotations

import argparse
import importlib.util
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[3]
REQ = ROOT / 'research_runs/REDESIGN_CLOUD_20261013/requirements.txt'
MAX_NEW_BYTES = 3 * 1024**3
MIN_FREE_BYTES = 10 * 1024**3
MAX_WHEEL_BYTES = 512 * 1024**2
SETUPTOOLS_PTH_SHA = '2638ce9e2500e572a5e0de7faed6661eb569d1b696fcba07b0dd223da5f5d224'
FROZEN_PAPER1_PYTHON = '3.12.3'
PRIORITY_PATH = ROOT / 'research_runs/REDESIGN_HANDOFF_20261015/runtime/priority_gate.py'
ACTIVE_PRIORITY = None


class UnvalidatedPriority:
    """Poison a previous slot before a new receipt is checked."""
    def __getattr__(self, name):
        raise ValueError('fresh_dot_priority_slot_not_validated')


def arm_priority(path, operation):
    global ACTIVE_PRIORITY
    ACTIVE_PRIORITY = UnvalidatedPriority()
    if path is None:
        raise ValueError('fresh_dot_paper2_priority_slot_required')
    spec = importlib.util.spec_from_file_location('paper1_dot_priority_gate', PRIORITY_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    ACTIVE_PRIORITY = module.validate_receipt(path, expected_operation=operation)
    return ACTIVE_PRIORITY


def priority_checkpoint():
    if ACTIVE_PRIORITY is not None:
        ACTIVE_PRIORITY.assert_active()


def free_floor():
    return max(MIN_FREE_BYTES, ACTIVE_PRIORITY.min_free_bytes) + ACTIVE_PRIORITY.paper2_reserve_bytes if ACTIVE_PRIORITY else MIN_FREE_BYTES


def new_storage_cap():
    return min(MAX_NEW_BYTES, ACTIVE_PRIORITY.max_new_bytes) if ACTIVE_PRIORITY else MAX_NEW_BYTES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def norm(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def clean_env():
    env = os.environ.copy()
    for key in list(env):
        if (key.startswith(('PYTHON', 'PIP_', 'R2_', 'AWS_'))
                or key in ('GH_TOKEN', 'GITHUB_TOKEN', 'RUNPOD_API_KEY')
                or key.endswith(('_TOKEN', '_SECRET', '_PASSWORD', '_SECRET_ACCESS_KEY', '_ACCESS_KEY_ID'))):
            env.pop(key)
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1',
               PIP_CONFIG_FILE=os.devnull, PIP_DISABLE_PIP_VERSION_CHECK='1')
    return env


def emit(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write('\n')


def fixed_checkout(revision):
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('immutable_revision_required')
    head = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    if head != revision:
        raise ValueError('runtime_preparation_checkout_revision_mismatch')
    paths = [Path(__file__), Path(__file__).with_name('donor_gpu_inventory.py'), REQ, PRIORITY_PATH]
    identities = {}
    for path in paths:
        rel = str(path.relative_to(ROOT))
        committed = subprocess.check_output(['git', '-C', str(ROOT), 'show', revision + ':' + rel])
        if path.is_symlink() or path.read_bytes() != committed:
            raise ValueError('runtime_preparation_uncommitted_file:' + rel)
        identities[rel] = hashlib.sha256(committed).hexdigest()
    return identities


def identity(inventory):
    """Compare provenance, excluding changing clock/free-space observations."""
    return {key: inventory[key] for key in ('donor_python', 'prefix', 'base_prefix',
        'base_executable', 'python_version', 'SOABI', 'cache_tag', 'platform', 'site_packages',
        'distributions', 'components', 'critical_module_files', 'torch_gpu_dependency_pins',
        'numerical_donor_observation_not_reused', 'inventory_implementation_sha256',
        'isolated_venv_prerequisites')}


def donor_observation(python):
    raw = subprocess.check_output([str(python), '-I', '-B',
        str(Path(__file__).with_name('donor_gpu_inventory.py')), '--expected-python', str(python)], env=clean_env(), timeout=60)
    report = json.loads(raw)
    if report.get('status') != 'GPU_DONOR_METADATA_EXACT_NOT_IMPORT_VERIFIED':
        raise ValueError('donor_metadata_not_exact')
    if report.get('inventory_implementation_sha256') != sha(Path(__file__).with_name('donor_gpu_inventory.py')):
        raise ValueError('donor_inventory_helper_identity_not_verified')
    return report


def validate_plan(report, protected):
    """The only installation candidates must be bounded non-GPU wheels."""
    protected = {norm(x) for x in protected}
    items = report.get('install')
    if not isinstance(items, list) or not items:
        raise ValueError('missing_lightweight_wheel_plan')
    names = set()
    for item in items:
        meta = item['metadata']
        name = norm(meta['name'])
        if name in names or name in protected or name.startswith('nvidia-') or name in ('torch', 'torchaudio', 'triton'):
            raise ValueError('resolver_attempts_protected_or_duplicate_distribution:' + name)
        names.add(name)
        if not re.fullmatch(r'[A-Za-z0-9_.+!-]+', meta['version']):
            raise ValueError('unsafe_resolved_version')
        download = item['download_info']
        if not download['url'].split('?', 1)[0].endswith('.whl'):
            raise ValueError('binary_wheels_only_no_build_scripts')
        if not re.fullmatch('[0-9a-f]{64}', download['archive_info']['hashes']['sha256']):
            raise ValueError('wheel_sha_required')
    return items


def wheel_budget(folder, items, protected=()):
    files = list(Path(folder).glob('*.whl'))
    if len(files) != len(items) or len(list(Path(folder).iterdir())) != len(files):
        raise ValueError('wheel_plan_file_count_mismatch')
    expected = {x['download_info']['archive_info']['hashes']['sha256']: x for x in items}
    if len(expected) != len(items) or {sha(p) for p in files} != set(expected):
        raise ValueError('wheel_bytes_differ_from_resolved_plan')
    expanded = compressed = 0
    for path in files:
        size = path.stat().st_size
        if size > MAX_WHEEL_BYTES:
            raise ValueError('single_wheel_storage_cap')
        compressed += size
        with zipfile.ZipFile(path) as z:
            names = [m.filename for m in z.infolist()]
            if len(names) != len(set(names)):
                raise ValueError('duplicate_wheel_members')
            metadata_names = [n for n in names if len(Path(n).parts) == 2 and n.endswith('.dist-info/METADATA')]
            if len(metadata_names) != 1:
                raise ValueError('wheel_single_distribution_metadata_required')
            if z.getinfo(metadata_names[0]).file_size > 1024**2:
                raise ValueError('wheel_metadata_size_cap')
            meta = BytesParser().parsebytes(z.read(metadata_names[0]))
            item = expected[sha(path)]['metadata']
            if norm(meta.get('Name', '')) != norm(item['name']) or meta.get('Version') != item['version']:
                raise ValueError('wheel_distribution_identity_different_from_plan')
            for m in z.infolist():
                p = Path(m.filename)
                if p.is_absolute() or '..' in p.parts or '\\' in m.filename:
                    raise ValueError('unsafe_wheel_member')
                kind = stat.S_IFMT(m.external_attr >> 16)
                if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise ValueError('wheel_symlink_or_special_member')
                parts = p.parts
                if not parts:
                    raise ValueError('wheel_empty_member')
                top = parts[0]
                if top.endswith('.data'):
                    if len(parts) < 3:
                        if m.is_dir():
                            continue
                        raise ValueError('malformed_wheel_data_destination')
                    if parts[1] in ('purelib', 'platlib'):
                        top = parts[2]
                    elif parts[1] == 'scripts':
                        if parts[2].startswith(('python', 'pip')):
                            raise ValueError('wheel_cannot_replace_environment_interpreter')
                    else:
                        raise ValueError('wheel_data_or_headers_destination_requires_separate_review')
                if top in set(protected) or top in ('torch', 'torchgen', 'functorch', 'torchaudio', 'torio', 'triton', 'nvidia'):
                    raise ValueError('wheel_writes_into_protected_gpu_component')
                vetted_setuptools_hook = (parts == ('distutils-precedence.pth',)
                    and norm(item['name']) == 'setuptools' and m.file_size <= 1024
                    and hashlib.sha256(z.read(m)).hexdigest() == SETUPTOOLS_PTH_SHA)
                if (p.name.endswith('.pth') and not vetted_setuptools_hook) or p.name in ('sitecustomize.py', 'usercustomize.py'):
                    raise ValueError('wheel_may_inherit_or_execute_foreign_startup_code')
                expanded += m.file_size
    # Includes retained wheels, installed files, venv/pip and evidence overhead.
    peak = compressed + 2 * expanded + 256 * 1024**2
    if peak > new_storage_cap():
        raise ValueError('new_runtime_peak_exceeds_3GiB')
    return {'wheel_compressed_bytes': compressed, 'wheel_expanded_bytes': expanded,
            'estimated_peak_new_bytes': peak, 'maximum_new_bytes': MAX_NEW_BYTES}


def download_wheels(items, folder, environment):
    """Stream bounded byte-authenticated wheels, with no package build execution."""
    priority_checkpoint()
    started = time.monotonic()
    for item in items:
        priority_checkpoint()
        url = item['download_info']['url']
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'https' or parsed.hostname != 'files.pythonhosted.org' or parsed.username or parsed.password:
            raise ValueError('unreviewed_wheel_origin')
        name = urllib.parse.unquote(Path(parsed.path).name)
        if Path(name).name != name or not name.endswith('.whl'):
            raise ValueError('unsafe_wheel_filename')
        digest = hashlib.sha256(); written = 0
        with urllib.request.urlopen(url, timeout=30) as response:
            length = response.headers.get('Content-Length')
            if length is None or not length.isdigit() or int(length) > MAX_WHEEL_BYTES:
                raise ValueError('bounded_wheel_content_length_required')
            priority_checkpoint()
            if allocated(environment) + int(length) + 256 * 1024**2 > new_storage_cap():
                raise ValueError('wheel_download_would_exceed_3GiB_cap')
            if shutil.disk_usage(environment).free < free_floor() + int(length):
                raise ValueError('wheel_download_remaining_space_floor')
            with (folder / name).open('xb') as f:
                while True:
                    priority_checkpoint()
                    if time.monotonic() - started > 300:
                        raise ValueError('bounded_wheel_download_timeout')
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    written += len(block)
                    if written > min(int(length), MAX_WHEEL_BYTES):
                        raise ValueError('wheel_response_exceeds_declared_size')
                    if shutil.disk_usage(environment).free < free_floor() + len(block):
                        raise ValueError('concurrent_storage_change_aborts_wheel_stream')
                    digest.update(block); f.write(block)
        if written != int(length) or digest.hexdigest() != item['download_info']['archive_info']['hashes']['sha256']:
            raise ValueError('wheel_stream_size_or_hash_mismatch')


def link_components(inventory, site):
    donor_sites = {Path(p).resolve() for p in inventory['site_packages']}
    linked = {}
    for component in inventory['components']:
        name, raw = component['name'], component['path']
        path = Path(raw)
        if Path(name).name != name or name.startswith('.') or path.parent.resolve() not in donor_sites:
            raise ValueError('unsafe_donor_component')
        # No generic .pth, sitecustomize, NumPy/SciPy or other-site inheritance.
        if name.endswith('.pth') or name in ('numpy', 'scipy', 'sitecustomize.py', 'usercustomize.py'):
            raise ValueError('forbidden_donor_component')
        if path.is_symlink() or not path.exists() or path.resolve().parent not in donor_sites:
            raise ValueError('donor_component_not_regular_within_site')
        dest = site / name
        if dest.exists() or dest.is_symlink():
            raise ValueError('existing_child_component_do_not_replace')
        dest.symlink_to(path, target_is_directory=path.is_dir())
        linked[name] = str(path)
    return linked


def allocated(folder):
    # Symlink targets are not followed and never counted as newly allocated CUDA.
    return sum(p.lstat().st_blocks * 512 for p in Path(folder).rglob('*') if not p.is_symlink())


def validate_log(path, protected, dest):
    if path is None or path.exists() or path.is_symlink() or path.parent.resolve() != Path('/workspace'):
        raise ValueError('new_workspace_sibling_log_required')
    resolved = path.resolve()
    if resolved.is_relative_to(dest) or any(resolved.is_relative_to(Path(p).resolve()) for p in protected):
        raise ValueError('log_cannot_write_into_protected_root')


def stop_owned_child(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL); process.wait()
    except ProcessLookupError:
        pass


def run_command(command, log, folder):
    priority_checkpoint()
    env = clean_env()
    temp = Path(folder) / 'bounded-temp'
    if Path(folder).is_dir():
        temp.mkdir(exist_ok=True)
        env['TMPDIR'] = str(temp)
    started = time.monotonic()
    with log.open('a') as f:
        # Commands contain no credentials or credential-bearing URLs.
        f.write(json.dumps(command) + '\n'); f.flush()
        process = subprocess.Popen(command, stdout=f, stderr=subprocess.STDOUT,
                                   env=env, start_new_session=True)
        try:
            while process.poll() is None:
                priority_checkpoint()
                if time.monotonic() - started > 300:
                    raise ValueError('bounded_environment_command_timeout')
                if shutil.disk_usage(Path(folder).parent).free < free_floor():
                    raise ValueError('concurrent_storage_change_aborts_owned_installer')
                if Path(folder).exists() and allocated(folder) > new_storage_cap():
                    raise ValueError('new_runtime_allocation_exceeds_3GiB')
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
        except BaseException:
            stop_owned_child(process)
            raise
    if process.returncode:
        raise ValueError('lightweight_environment_command_failed_inspect_private_log')


def prepare(args):
    code = fixed_checkout(args.code_revision)
    permit = arm_priority(getattr(args, 'priority_receipt', None), 'runtime_preparation')
    old = json.loads(args.donor_report.read_text())
    now = donor_observation(args.donor_python)
    if old.get('status') != now['status'] or identity(old) != identity(now):
        raise ValueError('reviewed_donor_identity_changed')
    if now['python_version'] != FROZEN_PAPER1_PYTHON:
        raise ValueError('paper1_requires_original_python_3_12_3_no_cross_ABI_donor')
    prerequisites = now['isolated_venv_prerequisites']
    if prerequisites.get('venv_module_available') is not True or prerequisites.get('ensurepip_module_available') is not True:
        raise ValueError('existing_venv_and_ensurepip_required_no_global_install_fallback')
    dest = args.environment.resolve()
    if args.environment.exists() or args.environment.is_symlink():
        raise ValueError('new_environment_only_no_retry_overwrite')
    protected = (ROOT, Path(now['prefix']), *[Path(p) for p in now['site_packages']], Path('/workspace/paper1-readonly-probe/data'), Path('/workspace/mi-eeg-cloud'), Path('/workspace/.venvs/paper2-gpu'))
    for forbidden in protected:
        if dest.is_relative_to(forbidden.resolve()) or forbidden.resolve().is_relative_to(dest):
            raise ValueError('new_environment_overlaps_protected_work')
    if dest.parent != Path('/workspace') or not dest.parent.is_dir():
        raise ValueError('environment_must_be_new_direct_child_of_workspace')
    free = shutil.disk_usage(dest.parent).free
    if free < free_floor() + new_storage_cap():
        raise ValueError('require_runtime_cap_plus_free_floor_and_paper2_reservation')
    plan = {'status': 'ISOLATED_RUNTIME_PLAN_ONLY_REVIEW_REQUIRED',
        'code_revision': args.code_revision, 'execution_files': code,
        'donor_report_sha256': sha(args.donor_report), 'donor_metadata': now,
        'environment': str(dest), 'maximum_new_bytes': MAX_NEW_BYTES,
        'minimum_remaining_free_bytes': MIN_FREE_BYTES, 'observed_free_bytes': free,
        'paper2_priority_receipt_sha256': permit.receipt_sha256,
        'paper2_additional_reserved_bytes': permit.paper2_reserve_bytes,
        'actual_required_free_floor_bytes': free_floor(),
        'actual_maximum_new_bytes': new_storage_cap(),
        'cuda_packages_downloaded': False, 'donor_modified': False,
        'source_acceptance_run': False, 'new_fits': 0, 'target_EEG_read': False,
        'budget_updated': False, 'training_authorization': False}
    if not args.prepare:
        print(json.dumps(plan, indent=2)); return
    validate_log(args.log, protected, dest)
    # Environment installation is independent of scientific job/budget accounting.
    dest.mkdir(exist_ok=False)
    run_command([now['base_executable'], '-I', '-B', '-m', 'venv', str(dest)],
                args.log, dest)
    py = dest / 'bin/python'
    child = json.loads(subprocess.check_output([str(py), '-I', '-B', '-c',
        'import sys,sysconfig,json; print(json.dumps({"version":list(sys.version_info[:2]),"cache_tag":sys.implementation.cache_tag,"SOABI":sysconfig.get_config_var("SOABI"),"purelib":sysconfig.get_path("purelib"),"platlib":sysconfig.get_path("platlib")}))'], env=clean_env(), text=True))
    if (child['version'] != now['python_major_minor'] or child['cache_tag'] != now['cache_tag']
            or child['SOABI'] != now['SOABI'] or child['purelib'] != child['platlib']):
        raise ValueError('child_and_donor_python_ABI_mismatch')
    site = Path(child['purelib'])
    if not site.is_relative_to(dest) or 'include-system-site-packages = false' not in (dest / 'pyvenv.cfg').read_text().lower():
        raise ValueError('child_venv_isolation_not_verified')
    links = link_components(now, site)
    constraints = dest / 'gpu-donor-constraints.txt'
    constraints.write_text(''.join(f'{name}=={d["version"]}\n' for name, d in sorted(now['distributions'].items())))
    emit(dest / 'runtime_plan.json', plan)
    resolve = dest / 'wheel-resolution.json'
    run_command([str(py), '-I', '-B', '-m', 'pip', 'install', '--dry-run', '--report', str(resolve),
        '--no-cache-dir', '--only-binary=:all:', '--index-url', 'https://pypi.org/simple',
        '-c', str(constraints), '-r', str(REQ)], args.log, dest)
    items = validate_plan(json.loads(resolve.read_text()), now['distributions'])
    wheel_req = dest / 'resolved-lightweight-wheels.txt'
    wheel_req.write_text(''.join(f'{x["metadata"]["name"]}=={x["metadata"]["version"]} --hash=sha256:{x["download_info"]["archive_info"]["hashes"]["sha256"]}\n' for x in items))
    wheels = dest / 'reviewed-wheels'; wheels.mkdir()
    download_wheels(items, wheels, dest)
    disk = wheel_budget(wheels, items, links)
    if shutil.disk_usage(dest).free < free_floor() + 2 * disk['wheel_expanded_bytes'] + 256 * 1024**2:
        raise ValueError('free_storage_dropped_before_install_do_not_proceed')
    # No resolver runs during installation; no donated package can be uninstalled.
    run_command([str(py), '-I', '-B', '-m', 'pip', 'install', '--no-deps', '--no-index',
        *[str(p) for p in sorted(wheels.glob('*.whl'))]], args.log, dest)
    run_command([str(py), '-I', '-B', '-m', 'pip', 'check'], args.log, dest)
    after = donor_observation(args.donor_python)
    if identity(now) != identity(after):
        raise ValueError('donor_identity_changed_during_preparation')
    for name, path in links.items():
        if not (site / name).is_symlink() or (site / name).resolve() != Path(path).resolve():
            raise ValueError('gpu_component_link_changed')
    used = allocated(dest)
    priority_checkpoint()
    if used > new_storage_cap() or shutil.disk_usage(dest).free < free_floor():
        raise ValueError('runtime_storage_budget_exceeded')
    plan.update(status='ISOLATED_RUNTIME_PREPARED_IMPORT_AND_SOURCE_ACCEPTANCE_PENDING',
        donor_post_metadata=after, linked_gpu_components=links, disk_budget=disk,
        actual_new_allocated_bytes=used, donor_metadata_unchanged=True,
        wheel_resolution_sha256=sha(resolve), requirements_sha256=sha(REQ))
    emit(dest / 'runtime_preparation.json', plan)
    print(json.dumps({'status': plan['status'], 'runtime_receipt': str(dest / 'runtime_preparation.json'),
        'new_allocated_bytes': used, 'training_authorization': False, 'new_fits': 0}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--code-revision', required=True)
    p.add_argument('--donor-python', type=Path, required=True)
    p.add_argument('--donor-report', type=Path, required=True)
    p.add_argument('--environment', type=Path, required=True)
    p.add_argument('--prepare', action='store_true')
    p.add_argument('--log', type=Path)
    p.add_argument('--priority-receipt', type=Path, required=True)
    a = p.parse_args()
    if a.prepare and (a.log is None or a.log.exists() or a.log.is_symlink()):
        p.error('--prepare requires a NEW log path; existing failed logs/environments are retained')
    prepare(a)


if __name__ == '__main__':
    main()
