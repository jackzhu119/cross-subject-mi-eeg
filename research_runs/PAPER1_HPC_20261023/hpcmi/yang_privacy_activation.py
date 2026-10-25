"""One explicit operational input-version migration; no scheduling or model work."""
from pathlib import Path
import subprocess

from .common import atomic_json, read_json, utc_now
from . import yang_privacy


def is_selected(paths):
    profile = paths.get('yang_source_profile')
    if not profile:
        return False
    if profile != yang_privacy.PROFILE or not yang_privacy.is_active(Path(paths['raw_dir']) / 'yang'):
        raise ValueError('Saved Yang source profile does not match its explicit marker')
    identity = paths.get('yang_source_identity')
    if not isinstance(identity, dict) or identity.get('contract_sha256') != yang_privacy.CONTRACT_SHA256:
        raise ValueError('Saved Yang source identity does not match its contract')
    return True


def effective_raw_dir(project, requested_raw, source=None):
    """An installer default must not silently undo an already selected version."""
    path = Path(project) / 'config/paths.json'
    if not path.exists():
        return requested_raw
    saved = read_json(path)
    if not is_selected(saved):
        return requested_raw
    if source == 'original':
        raise ValueError('Existing privacy input version retained; no automatic downgrade to old inputs')
    if requested_raw is None:
        return saved['raw_dir']
    requested = Path(requested_raw).expanduser().resolve()
    previous = Path(saved['original_raw_dir']).resolve()
    if requested in {previous, Path(saved['raw_dir']).resolve()}:
        return saved['raw_dir']
    return requested_raw  # setup reports an explicit unrelated path mismatch.


def _immutable_json(path, value):
    if path.exists():
        if read_json(path) != value:
            raise ValueError('Prior source migration evidence differs; retained: ' + path.name)
    else:
        atomic_json(path, value)


def _no_old_science(project):
    if (project / 'state/data_prepared.json').exists():
        raise RuntimeError('Existing prepared input receipt retained; use a separate experiment version')
    runs = project / 'outputs/runs'
    if not runs.exists():
        return
    if any(runs.glob('*/complete.json')) or any(
            p.is_file() and (p.suffix in {'.pt', '.pth', '.safetensors'} or p.name == 'checkpoint_status.json')
            for p in runs.glob('*/checkpoints/*')):
        raise RuntimeError('Existing model checkpoint/completion retained; input identity was not changed')
    for path in runs.glob('*/status.json'):
        status = read_json(path)
        if any(type(status.get(key)) is int and status[key] > 0
               for key in ('optimizer_updates', 'actual_neural_fits_started', 'actual_neural_fits_completed')):
            raise RuntimeError('Existing model progress retained; input identity was not changed')


def _no_project_job(project, runner):
    from .submit_single import OWNER, _queue
    known_names, known_ids = set(), set()
    ledger = project / 'state/single_job_submissions.json'
    if ledger.exists():
        for row in read_json(ledger).get('submissions', []):
            if row.get('job_name'):
                known_names.add(row['job_name'])
            if row.get('job_id'):
                known_ids.add(str(row['job_id']))
    for row in _queue(runner):
        if row['owner'] != OWNER:
            continue
        same_directory = bool(row.get('directory')) and Path(row['directory']).resolve() == project
        if same_directory or row['name'] in known_names or row['id'] in known_ids:
            raise RuntimeError('Existing same-project scheduler job retained; source migration deferred')


def _link_dataset(destination, source):
    if destination.is_symlink() or destination.exists():
        if not destination.is_symlink() or destination.resolve() != source.resolve():
            raise ValueError('Existing migration dataset destination differs; retained: ' + destination.name)
        return
    source.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(source.resolve(), target_is_directory=True)


def activate(project, paths, runner=None):
    """Called under the existing login start lock after its old transfer exits."""
    project = Path(project).expanduser().resolve()
    identity = yang_privacy.current_identity()
    expected_raw = project / 'raw-nemar-privacy-v1'
    expected_data = project / 'data/prepared-nemar-privacy-v1'
    if is_selected(paths):
        previous_identity = paths['yang_source_identity']
        same_contract = all(previous_identity.get(key) == value for key, value in identity.items()
                            if key != 'adapter_sha256')
        if Path(paths['raw_dir']).resolve() != expected_raw or not same_contract:
            raise ValueError('Existing privacy input version differs; retained without reinitialization')
        # Complete the second atomic path write if a previous invocation ended
        # between config writes. Current-version checkpoints are never scanned.
        data_path = project / 'config/data_path.json'
        expected = {'data_dir': paths['data_dir']}
        before = project / 'state/source-profile-history' / yang_privacy.PROFILE / 'data_path.before.json'
        if data_path.exists() and read_json(data_path) != expected and (
                not before.exists() or read_json(data_path) != read_json(before)):
            raise ValueError('Current data path has an unrelated identity; retained')
        if not data_path.exists() or read_json(data_path) != expected:
            atomic_json(data_path, expected)
        return paths
    _no_old_science(project)
    _no_project_job(project, runner or subprocess.run)
    old_raw = Path(paths['raw_dir']).expanduser().resolve()
    if old_raw == expected_raw:
        raise ValueError('Unregistered privacy directory cannot be adopted as old inputs')
    root = expected_raw
    yang = root / 'yang'
    if root.exists() and not root.is_dir():
        raise ValueError('Migration raw destination is not a directory')
    if yang.exists() and (not yang.is_dir() or yang.is_symlink()):
        raise ValueError('Migration Yang destination is not a plain directory')
    if yang.exists() and any(yang.iterdir()) and not yang_privacy.is_active(yang):
        raise ValueError('Unregistered Yang destination retained without overwriting')
    for dataset in ('bnci', 'dreyer'):
        dest = root / dataset
        if (dest.exists() or dest.is_symlink()) and (
                not dest.is_symlink() or dest.resolve() != (old_raw / dataset).resolve()):
            raise ValueError('Migration reuse destination differs; retained: ' + dataset)
    history = project / 'state/source-profile-history' / yang_privacy.PROFILE
    history.mkdir(parents=True, exist_ok=True)
    _immutable_json(history / 'paths.before.json', paths)
    data_path = project / 'config/data_path.json'
    saved_data = history / 'data_path.before.json'
    if not saved_data.exists():
        atomic_json(saved_data, read_json(data_path) if data_path.exists() else None)
    elif data_path.exists() and read_json(data_path) not in (
            read_json(saved_data), {'data_dir': str(expected_data)}):
        raise ValueError('Data path differs from both migration versions; retained')
    yang.mkdir(parents=True, exist_ok=True)
    for dataset in ('bnci', 'dreyer'):
        _link_dataset(root / dataset, old_raw / dataset)
    marker = {'profile': yang_privacy.PROFILE, 'contract_sha256': identity['contract_sha256'],
              'approval_mode': 'explicit_operator_cli_selection'}
    marker_path = yang / '.source-profile.json'
    if marker_path.exists():
        if read_json(marker_path) != marker:
            raise ValueError('Existing source marker differs; retained')
    else:
        atomic_json(marker_path, marker)
    current = {**paths, 'raw_dir': str(root), 'data_dir': str(expected_data),
               'original_raw_dir': str(old_raw), 'yang_source_profile': yang_privacy.PROFILE,
               'yang_source_identity': identity}
    atomic_json(project / 'config/paths.json', current)
    atomic_json(data_path, {'data_dir': current['data_dir']})
    receipt = history / 'activation.json'
    if not receipt.exists():
        atomic_json(receipt, {'activated_at_utc': utc_now(), 'profile': yang_privacy.PROFILE,
            'identity': identity, 'approval_mode': 'explicit_operator_cli_selection',
            'old_yang_directory_untouched': True, 'old_ledgers_and_checkpoints_retained': True,
            'bnci_dreyer_reused_by_directory_links': True,
            'paths_before': paths, 'paths_after': current, 'model_fits_started': 0})
    return current
