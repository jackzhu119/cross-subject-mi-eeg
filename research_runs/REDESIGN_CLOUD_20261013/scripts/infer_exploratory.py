#!/usr/bin/env python3
"""Frozen, eval-only exploratory target inference. Default does not read EEG.

This is a new explicitly exploratory path. It does not open, spoof, or bypass
any v1 first-use execution gate. Only the unchanged numerical model/input
helpers are reused. Unknown prior exposure remains unknown throughout.
"""
from __future__ import annotations
import argparse
import collections
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
LEGACY = ROOT / 'research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts'
EXPLORATORY = ROOT / 'research_runs/REDESIGN_EXPLORATORY_20261013'
CONFIG = STUDY / 'config/experiment.json'
AUTHOR = EXPLORATORY / 'evidence/author_prior_use_uncertain.json'
REPOSITORY = 'jackzhu119/cross-subject-mi-eeg'
SHA = re.compile(r'[0-9a-f]{64}\Z')
COMMIT = re.compile(r'[0-9a-f]{40}\Z')
ARCH_MAP = {'BROAD_EEGNET': 'broad', 'MU_BETA_SHARED': 'shared'}
SELECTOR_MAP = {'fixed20': 'fixed', 'mean_loss': 'mean_loss', 'mean_rank': 'mean_rank'}
SEEDS = [20261013, 20261014, 20261015]
RESULT_ROLE = 'EXPOSURE_UNCONFIRMED_EXPLORATORY'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 ** 2), b''):
            h.update(block)
    return h.hexdigest()


def object_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read_json(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'required_regular_json_absent:' + path.name)
    value = json.loads(path.read_text())
    require(isinstance(value, dict), 'json_object_required:' + path.name)
    return value


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    temp.replace(path)


def inside(base, name):
    require(isinstance(name, str) and name and not Path(name).is_absolute() and '..' not in Path(name).parts,
            'nontraversing_relative_artifact_required')
    base, path = Path(base).resolve(), Path(base) / name
    require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(base), 'unsafe_or_absent_artifact:' + name)
    for parent in path.parents:
        if parent == base:
            break
        require(not parent.is_symlink(), 'symlink_artifact_ancestor:' + name)
    return path


def numerical_helpers():
    # Importing these modules has no execution side effects; no v1 gate is called.
    if str(LEGACY) not in sys.path:
        sys.path.insert(0, str(LEGACY))
    from core_source_inputs import array_hash
    from train_source_selection_core import build_model, state_hash, select_epochs, schedule_cells
    return array_hash, build_model, state_hash, select_epochs, schedule_cells


def validate_exploratory_author(value):
    require(value.get('status') == 'AUTHOR_REPORTED_UNCERTAIN'
            and value.get('independent_confirmation_qualified') is False, 'unknown_exposure_record_required')
    for key in ('prior_proposed_decoder_results_inspected_or_used', 'prior_dataset_scientific_analysis_performed',
                'used_in_other_manuscripts_or_projects'):
        require(key in value and value[key] is None, 'unknown_must_not_be_rewritten_as_never_used:' + key)
    return value


def validate_config(value):
    require(value.get('architectures') == list(ARCH_MAP) and value.get('selectors') == list(SELECTOR_MAP)
            and value.get('final_seeds') == SEEDS and value.get('selection_seed') == 20261012,
            'frozen_architecture_selector_or_seed_changed')
    require(value.get('batch_size') == 64 and value.get('BatchNorm_target_mode') == 'eval_no_target_updates'
            and value.get('target_fits') == 0 and type(value.get('target_fits')) is int
            and value.get('target_fitted_transforms') is False, 'target_adaptation_forbidden')
    require(value.get('source_validation_groups') == [[1, 2], [3, 4], [5, 6], [7, 8, 9]]
            and value.get('source_validation_group_weight') == 'equal_fold'
            and value.get('candidate_epochs') == list(range(1, 41)), 'frozen_source_selection_design_changed')
    from train_exploratory import validate_config as validate_source_config
    validate_source_config(value)
    return value


def target_metadata(job):
    """Metadata-only eligibility gate; opens no target tensor before freezing."""
    job = Path(job)
    roster_path = inside(job, 'target/raw_only_roster.json')
    roster = read_json(roster_path)
    audit = read_json(inside(job, 'target/full_raw_qc_report.json'))
    require(audit.get('status') == 'PASS_RAW_ONLY_FULL_COHORT_QC_EXPLORATORY_OPERATIONAL_SCOPE'
            and audit.get('all_174_files_examined') is True and audit.get('full_physical_signal_scan_passed') is True
            and audit.get('roster_sha256') == sha(roster_path), 'actual_full_signal_audit_required')
    require(audit.get('independent_confirmation_qualified') is False
            and roster.get('independent_confirmation_qualified') is False
            and roster.get('evidence_class') == RESULT_ROLE and roster.get('prior_use') == 'unknown'
            and roster.get('synthetic_fixture') is False, 'real_exploratory_roster_required_no_independence_promotion')
    require(audit.get('target_fits') == 0 and type(audit.get('target_fits')) is int
            and audit.get('target_predictions_computed') is False
            and roster.get('target_predictions_computed') is False
            and roster.get('performance_used_for_eligibility') is False, 'raw_only_eligibility_must_precede_results')
    from analyze_redesign_scores import validate_contract
    people, events = validate_contract(roster, False)
    require(len(people) == 85 and len(events) == 6800 and audit.get('n_retained_participants') == 85
            and audit.get('n_eligible_events') == 6800, 'fixed_actual_full_cohort_coverage_required')
    require(set(roster.get('technical_exclusions', [])) == {'A17', 'A41'}, 'raw_only_exclusions_changed')
    tensor = read_json(inside(job, 'target/tensor_cache_receipt.json'))
    require(audit.get('tensor_cache_receipt_sha256') == sha(job / 'target/tensor_cache_receipt.json'),
            'tensor_cache_receipt_not_bound_to_actual_raw_qc')
    require(tensor.get('target_fits') == 0 and tensor.get('target_predictions_computed') is False,
            'tensor_cache_must_be_pre_outcome')
    require(len(tensor.get('files', [])) == 85 and {r.get('subject_id') for r in tensor['files']} == set(people),
            'full_subject_tensor_inventory_required')
    return roster, tensor


def source_cells(job, config):
    """Reconstruct source selectors and checkpoint aliases, then check audit binding."""
    job = Path(job)
    source = job / 'source'
    completion_path = inside(job, 'source/source_completion_manifest.json')
    completion = read_json(completion_path)
    validation = read_json(inside(job, 'source/source_validation.json'))
    require(validation.get('status') == 'PASS_SOURCE_ARTIFACT_VALIDATION_EXPLORATORY'
            and type(validation.get('target_fits')) is int and validation.get('target_fits') == 0
            and validation.get('target_predictions_computed') is False,
            'actual_validated_source_receipt_required')
    require(validation.get('source_completion_manifest_sha256') == sha(completion_path),
            'source_validation_completion_hash_mismatch')
    require(validation.get('independent_confirmation_qualified') is False
            or validation.get('qualified_independent_confirmation') is False, 'source_audit_cannot_qualify_target_independence')
    require(type(completion.get('target_fits')) is int and completion.get('target_fits') == 0
            and completion.get('target_predictions_computed') is False
            and completion.get('nominal_inner_fits') == 8 and completion.get('nominal_final_cells') == 18,
            'source_grid_incomplete_or_contains_target_results')
    audit = read_json(inside(job, 'source/source19_input_audit.json'))
    require(audit.get('status') == 'PASS_SOURCE19_INPUTS_ONLY' and audit.get('n_binary_trials') == 2592
            and audit.get('n_raw_files') == 18 and audit.get('target_eeg_read') is False, 'actual_source19_audit_required')
    selected = read_json(inside(job, 'source/selected_epochs.json'))
    _, _, _, select_epochs, schedule_cells = numerical_helpers()
    output, actual, aliases = [], 8, 0
    required_artifacts = ['source/source_completion_manifest.json', 'source/source_validation.json',
                          'source/source19_input_audit.json', 'source/runtime_provenance.json', 'source/selected_epochs.json']
    for name in ARCH_MAP:
        curves = []
        for fold, group in enumerate(config['source_validation_groups'], 1):
            relative = f'source/inner/{name}/fold_{fold:02d}'
            curve_path = inside(job, relative + '/source_curve.json')
            curves.append(json.loads(curve_path.read_text()))
            receipt = read_json(inside(job, relative + '/fit_receipt.json'))
            require(receipt.get('status') == 'completed' and receipt.get('architecture') == name
                    and receipt.get('seed') == config['selection_seed'] and receipt.get('epochs') == 40
                    and receipt.get('target_fit') is False and receipt.get('n_validation_trials') == 288 * len(group)
                    and receipt.get('n_training_trials') == 288 * (9 - len(group))
                    and receipt.get('curve_sha256') == sha(curve_path), 'invalid_source_inner_trajectory')
            required_artifacts += [relative + '/source_curve.json', relative + '/fit_receipt.json', relative + '/partition.json']
        reconstructed = select_epochs(curves, config['candidate_epochs'])
        require(selected.get(name) == reconstructed and completion.get('selected_epochs', {}).get(name) == reconstructed,
                'source_only_selector_not_reproducible')
        for cell in schedule_cells(name, reconstructed, config['final_seeds']):
            relative = 'source/final/' + cell['owner_cell']
            checkpoint = inside(job, relative + '/checkpoint.pt')
            fit = read_json(inside(job, relative + '/fit_receipt.json'))
            require(fit.get('status') == 'completed' and fit.get('architecture') == name
                    and fit.get('seed') == cell['seed'] and fit.get('epochs') == cell['epochs']
                    and fit.get('n_training_trials') == 2592 and fit.get('n_validation_trials') == 0
                    and fit.get('target_fit') is False and fit.get('configuration_sha256') == sha(CONFIG)
                    and fit.get('checkpoint_sha256') == sha(checkpoint)
                    and fit.get('optimizer_updates') == math.ceil(2592 / 64) * cell['epochs'], 'source_owner_identity_invalid')
            if cell['alias']:
                alias_name = 'source/final/' + cell['cell'] + '/alias_receipt.json'
                alias = read_json(inside(job, alias_name))
                require(all(alias.get(k) == v for k, v in cell.items()) and alias.get('new_real_neural_fit') is False
                        and alias.get('owner_checkpoint_sha256') == fit['checkpoint_sha256']
                        and alias.get('owner_model_state_sha256') == fit['model_state_sha256'], 'source_alias_identity_invalid')
                required_artifacts.append(alias_name)
                aliases += 1
            else:
                actual += 1
            output.append({**cell, 'model_arch': ARCH_MAP[name], 'analysis_selector': SELECTOR_MAP[cell['selector']],
                           'checkpoint_file': relative + '/checkpoint.pt', 'checkpoint_sha256': fit['checkpoint_sha256'],
                           'model_state_sha256': fit['model_state_sha256'], 'source_only': True, 'target_fit_count': 0})
            required_artifacts += [relative + '/fit_receipt.json', relative + '/source_curve.json', relative + '/partition.json']
    audit_hashes = validation.get('artifact_hashes', {})
    for name in sorted(set(required_artifacts) - {'source/source_validation.json'}):
        require(audit_hashes.get(name) == sha(inside(job, name)), 'source_validation_artifact_hash_missing_or_changed:' + name)
    for cell in output:
        require(audit_hashes.get(cell['checkpoint_file']) == cell['checkpoint_sha256'], 'source_validation_checkpoint_hash_missing')
    require(validation.get('config_sha256') == sha(CONFIG), 'source_validation_config_hash_changed')
    require(len(output) == 18 and completion.get('actual_new_neural_fits') == actual
            and completion.get('aliases') == aliases, 'source_alias_fit_accounting_invalid')
    require(completion.get('final_cells') == [{k: c[k] for k in ('cell', 'architecture', 'selector', 'seed', 'epochs', 'owner_cell', 'alias')}
                                            for c in output], 'source_nominal_cell_inventory_differs')
    return output, sorted(set(required_artifacts))


def public_bytes(revision, name):
    url = f'https://raw.githubusercontent.com/{REPOSITORY}/{revision}/{quote(name, safe="/")}'
    from cloud_transport import public_bytes as verified_public_bytes
    return verified_public_bytes(url)


def verify_freeze(job, required_artifacts, public_reader=public_bytes):
    """Verify actual immutable public metadata before any target model output."""
    job = Path(job)
    freeze = read_json(inside(job, 'preinference_freeze.json'))
    require(freeze.get('status') == 'FROZEN_BEFORE_TARGET_INFERENCE_EXPLORATORY_ONLY'
            and freeze.get('independent_confirmation_qualified') is False and freeze.get('target_fits') == 0
            and type(freeze.get('target_fits')) is int and freeze.get('target_predictions_computed') is False,
            'actual_preinference_exploratory_freeze_required')
    revision = freeze.get('commit_sha', '')
    require(isinstance(revision, str) and COMMIT.fullmatch(revision), 'public_full_commit_required')
    protocol = read_json(inside(job, 'public_freeze.json'))
    protocol_revision = protocol.get('commit_sha', protocol.get('protocol_commit', ''))
    require(protocol.get('status') in {'PASS', 'PASS_PUBLIC_FREEZE'}
            and isinstance(protocol_revision, str) and COMMIT.fullmatch(protocol_revision),
            'initial_public_protocol_freeze_required')
    # A runtime job snapshot can be created with the GitHub Git API while the
    # checkout remains on the launch revision. Authenticate the new commit as a
    # descendant of that public protocol, without mutating the checkout HEAD.
    subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', protocol_revision, revision], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    bound = freeze.get('artifact_bindings', {})
    files = freeze.get('files', {})
    require(isinstance(bound, dict) and isinstance(files, dict) and files, 'public_freeze_binding_inventory_missing')
    for name in required_artifacts:
        path = inside(job, name)
        binding = bound.get(name, {})
        require(isinstance(binding, dict) and binding.get('sha256') == sha(path)
                and files.get(binding.get('public_path')) == sha(path), 'preinference_job_artifact_not_publicly_bound:' + name)
    required_code = [Path(__file__), HERE / 'validate_predictions.py', HERE / 'cloud_locks.py', HERE / 'analyze_exploratory.py', CONFIG, AUTHOR,
                     LEGACY / 'core_source_inputs.py', LEGACY / 'train_source_selection_core.py',
                     LEGACY / 'analyze_redesign_scores.py', HERE / 'train_exploratory.py', HERE / 'validate_source.py',
                     LEGACY.parent / 'config/core_experiment_v1.json', ROOT / 'src/mi_eeg/data/q15_context.py']
    for path in required_code:
        require(files.get(path.relative_to(ROOT).as_posix()) == sha(path), 'adapter_config_or_author_not_frozen:' + path.name)
    for name, expected in sorted(files.items()):
        path = inside(ROOT, name)
        require(isinstance(expected, str) and SHA.fullmatch(expected) and sha(path) == expected,
                'live_public_freeze_artifact_changed:' + name)
        committed = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{revision}:{name}'])
        require(hashlib.sha256(committed).hexdigest() == expected
                and hashlib.sha256(public_reader(revision, name)).hexdigest() == expected,
                'local_or_public_immutable_freeze_bytes_differ:' + name)
    return freeze


def load_target_inputs(cache, roster, tensor_receipt, guard=None):
    import numpy as np
    array_hash, _, _, _, _ = numerical_helpers()
    require(not Path(cache).is_symlink(), 'actual_tensor_cache_symlink_forbidden')
    cache = Path(cache).resolve()
    require(cache.is_dir(), 'actual_tensor_cache_required')
    by_person = collections.defaultdict(list)
    for event in roster['events']:
        by_person[event['subject_id']].append(event)
    receipt_by_person = {row['subject_id']: row for row in tensor_receipt['files']}
    collected = {band: {} for band in ('broad', 'mu', 'beta')}
    checked = []
    for person in roster['participants']:
        if guard:
            guard()
        path = inside(cache, person + '.npz')
        entry = receipt_by_person[person]
        require(path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256'], 'target_tensor_bytes_changed:' + person)
        with np.load(path, allow_pickle=False) as data:
            rows = by_person[person]
            require(set(data.files) == {'event_ids', 'broad', 'mu', 'beta'}
                    and data['event_ids'].tolist() == [r['event_id'] for r in rows], 'tensor_event_order_mismatch:' + person)
            for band in collected:
                values = data[band]
                require(values.dtype == np.float32 and values.shape == (len(rows), 19, 320)
                        and np.isfinite(values).all(), 'target_tensor_shape_dtype_or_finiteness_invalid')
                for row, value in zip(rows, values):
                    require(array_hash(value) == row['input_sha256'][band]
                            and object_hash(row['input_sha256']) == row['epoch_sha256'], 'frozen_target_input_hash_mismatch')
                    collected[band][row['event_id']] = value.copy()
        require(sha(path) == entry['sha256'], 'target_tensor_changed_during_read')
        checked.append({'subject_id': person, 'sha256': entry['sha256'], 'n_events': len(rows)})
    output = {band: np.stack([mapping[row['event_id']] for row in roster['events']]) for band, mapping in collected.items()}
    return output, {'status': 'ALL_FROZEN_INPUT_BYTES_AND_WINDOWS_REPLAYED_EXPLORATORY_ONLY', 'files': checked,
                    'n_events': len(roster['events']), 'aggregate_input_hashes': {band: array_hash(values) for band, values in output.items()},
                    'target_fits': 0, 'target_fitted_transforms': False, 'labels_used_for_fitting': False,
                    'independent_confirmation_qualified': False}


def softmax64(logits):
    import numpy as np
    values = np.asarray(logits, dtype=np.float64)
    require(values.ndim == 2 and values.shape[1] == 2 and np.isfinite(values).all(), 'finite_binary_logits_required')
    e = np.exp(values - values.max(axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)


def predict_logits(model, values, device, batch_size=64, guard=None):
    """Only numerical fixture helpers allow CPU; real execute requires CUDA."""
    import numpy as np
    import torch
    _, _, state_hash, _, _ = numerical_helpers()
    require(batch_size == 64 and len(values) > 0 and np.isfinite(values).all(), 'fixed_nonempty_finite_inference_input_required')
    model.eval()
    before = state_hash(model)
    outputs = []
    with torch.inference_mode():
        for start in range(0, len(values), batch_size):
            if guard:
                guard()
            logits = model(torch.as_tensor(values[start:start + batch_size], dtype=torch.float32, device=device))
            require(tuple(logits.shape) == (min(batch_size, len(values) - start), 2)
                    and bool(torch.isfinite(logits).all()), 'invalid_binary_model_logits')
            outputs.append(logits.cpu().numpy())
    after = state_hash(model)
    require(before == after and all(not module.training for module in model.modules()), 'target_inference_changed_model_state_or_training_mode')
    return np.concatenate(outputs), {'state_before_sha256': before, 'state_after_sha256': after,
                                     'parameters_and_buffers_unchanged': True, 'mode': 'eval_inference_mode', 'target_fits': 0}


def cell_key(cell):
    return f"{cell['model_arch']}__{cell['analysis_selector']}__{cell['seed']}"


def save_npz(path, **values):
    import numpy as np
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('wb') as handle:
        np.savez(handle, **values)
    temp.replace(path)


def execution_gates(job):
    numerical_helpers()
    config = validate_config(read_json(CONFIG))
    validate_exploratory_author(read_json(AUTHOR))
    roster, tensors = target_metadata(job)
    cells, artifact_names = source_cells(job, config)
    artifact_names += ['target/raw_only_roster.json', 'target/full_raw_qc_report.json', 'target/tensor_cache_receipt.json',
                       'runtime_lock.json', 'budget_authorization.json']
    freeze = verify_freeze(job, artifact_names)
    import torch
    require(torch.cuda.is_available(), 'real_gpu_inference_requires_verified_cuda_runtime')
    # Source training already verified the live machine/runtime under the shared
    # job budget; the continuing same machine must still pass its stored guard.
    from train_exploratory import PersistentBudget, runtime_identity, validate_budget, validate_runtime
    runtime = runtime_identity()
    validate_runtime(runtime, read_json(inside(job, 'runtime_lock.json')))
    authorization = read_json(inside(job, 'budget_authorization.json'))
    validate_budget(authorization, runtime)
    budget = PersistentBudget(Path(job), authorization)
    budget.guard()
    return config, roster, tensors, cells, freeze, budget


def execute(job, cache):
    gates = execution_gates(job)  # No output/tensor is opened before these pass.
    from cloud_locks import local_lock
    with local_lock('inference', job):
        return _execute_validated(job, cache, gates)


def _execute_validated(job, cache, gates):
    config, roster, tensors, cells, freeze, budget = gates
    import numpy as np
    import torch
    _, build_model, state_hash, _, _ = numerical_helpers()
    job = Path(job).resolve()
    target = job / 'target'
    require(not (target / 'prediction_completion_receipt.json').exists(), 'completed_inference_requires_validation_not_rerun')
    status = {'status': 'frozen_target_input_replay', 'updated_at_utc': now(), 'target_fits': 0, 'new_source_fits': 0,
              'target_predictions_computed': False, 'independent_confirmation_qualified': False,
              'public_preinference_commit': freeze['commit_sha'], 'nominal_cells_completed': 0}
    write_json(target / 'target_status.json', status)
    arrays, input_receipt = load_target_inputs(cache, roster, tensors, guard=budget.guard)
    write_json(target / 'target_input_replay_receipt.json', input_receipt)
    receipts, all_logits, predictions = [], {}, []
    owner_outputs = {}
    try:
        for cell in cells:
            budget.guard()
            key = cell_key(cell)
            checkpoint_path = inside(job, cell['checkpoint_file'])
            require(sha(checkpoint_path) == cell['checkpoint_sha256'], 'checkpoint_changed_after_public_freeze')
            partial = target / 'cells' / (key + '.npz')
            partial_receipt = target / 'cells' / (key + '.json')
            expected_identity = {k: cell[k] for k in ('cell', 'architecture', 'seed', 'epochs', 'owner_cell', 'checkpoint_sha256', 'model_state_sha256')}
            if partial.exists() or partial_receipt.exists():
                require(partial.exists() and partial_receipt.exists(), 'incomplete_target_cell_checkpoint_no_silent_overwrite')
                saved = read_json(partial_receipt)
                require(all(saved.get(k) == v for k, v in expected_identity.items())
                        and saved.get('public_preinference_commit') == freeze['commit_sha']
                        and saved.get('logits_sha256') == sha(partial)
                        and saved.get('parameters_and_buffers_unchanged') is True
                        and saved.get('state_before_sha256') == saved.get('state_after_sha256') == cell['model_state_sha256'],
                        'resumed_cell_differs_from_frozen_model')
                with np.load(partial, allow_pickle=False) as data:
                    logits = data['logits'].copy()
                    require(data['event_ids'].tolist() == [row['event_id'] for row in roster['events']], 'resumed_target_event_inventory_changed')
                state_receipt = {k: saved[k] for k in ('state_before_sha256', 'state_after_sha256', 'parameters_and_buffers_unchanged', 'mode', 'target_fits')}
            elif cell['owner_cell'] in owner_outputs:
                logits, state_receipt = owner_outputs[cell['owner_cell']]
                logits = logits.copy()
            else:
                checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
                require(checkpoint.get('model') == cell['architecture'] and checkpoint.get('architecture') == config['architecture']
                        and checkpoint.get('seed') == cell['seed'] and checkpoint.get('epochs') == cell['epochs']
                        and checkpoint.get('config_sha256') == sha(CONFIG), 'deserialized_source_checkpoint_identity_differs')
                model = build_model(cell['architecture'], config['architecture'], torch.device('cuda:0'))
                model.load_state_dict(checkpoint['state_dict'], strict=True)
                require(state_hash(model) == cell['model_state_sha256'], 'deserialized_source_state_mismatch')
                values = arrays['broad'] if cell['architecture'] == 'BROAD_EEGNET' else np.stack([arrays['mu'], arrays['beta']], axis=1)
                status.update(status='exploratory_target_model_output_in_progress', predictions_computation_attempted=True, updated_at_utc=now())
                write_json(target / 'target_status.json', status)
                logits, state_receipt = predict_logits(model, values, 'cuda:0', guard=budget.guard)
                require(sha(checkpoint_path) == cell['checkpoint_sha256'], 'checkpoint_mutated_during_inference')
                del model, checkpoint, values
            require(logits.dtype == np.float32 and logits.shape == (6800, 2) and np.isfinite(logits).all(), 'incomplete_or_nonfinite_target_logits')
            owner_outputs[cell['owner_cell']] = (logits, state_receipt)
            if not partial.exists():
                save_npz(partial, logits=logits, event_ids=np.asarray([row['event_id'] for row in roster['events']]))
                write_json(partial_receipt, {**cell, **state_receipt, 'logits_sha256': sha(partial),
                                             'public_preinference_commit': freeze['commit_sha'], 'independent_confirmation_qualified': False})
            probabilities = softmax64(logits)
            for row, logit, probability in zip(roster['events'], logits, probabilities):
                predictions.append({'subject_id': row['subject_id'], 'event_id': row['event_id'], 'model_arch': cell['model_arch'],
                                    'selector': cell['analysis_selector'], 'seed': cell['seed'], 'ytrue': row['ytrue'],
                                    'ypred': int(np.argmax(logit)), 'logit_left': float(logit[0]), 'logit_right': float(logit[1]),
                                    'p_left': float(probability[0]), 'p_right': float(probability[1]), 'epoch_sha256': row['epoch_sha256'],
                                    'checkpoint_sha256': cell['checkpoint_sha256'], 'owner_cell': cell['owner_cell']})
            all_logits[key] = logits
            receipts.append({**cell, **state_receipt, 'logits_file': 'target/cells/' + partial.name, 'logits_sha256': sha(partial)})
            status.update(status='exploratory_predictions_pending_separate_validation', target_predictions_computed=True,
                          nominal_cells_completed=len(receipts), prediction_rows=len(predictions), updated_at_utc=now())
            write_json(target / 'target_status.json', status)
            write_json(target / 'model_state_receipts.json', {'cells': receipts, 'target_fits': 0, 'independent_confirmation_qualified': False})
        require(len(predictions) == 122400 and len(all_logits) == 18, 'nominal_prediction_coverage_incomplete')
        path = target / 'predictions.csv'
        temp = path.with_suffix('.csv.tmp')
        with temp.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(predictions[0]))
            writer.writeheader(); writer.writerows(predictions)
        temp.replace(path)
        save_npz(target / 'raw_logits.npz', event_ids=np.asarray([row['event_id'] for row in roster['events']]), **all_logits)
        write_json(target / 'prediction_completion_receipt.json', {**status,
                   'status': 'EXPLORATORY_PREDICTIONS_COMPLETE_UNVALIDATED_NO_STATISTICS', 'prediction_rows': len(predictions),
                   'predictions_sha256': sha(path), 'raw_logits_sha256': sha(target / 'raw_logits.npz'),
                   'model_state_receipts_sha256': sha(target / 'model_state_receipts.json'), 'roster_sha256': sha(target / 'raw_only_roster.json'),
                   'source_manifest_sha256': sha(job / 'source/source_completion_manifest.json'),
                   'preinference_freeze_sha256': sha(job / 'preinference_freeze.json'), 'independent_confirmation_qualified': False,
                   'statistical_scores_computed': False, 'target_fits': 0, 'target_normalization_or_BatchNorm_updates': False,
                   'checkpoints': receipts, 'prior_use': 'unknown'})
        status.update(status='exploratory_predictions_complete_need_separate_validation', updated_at_utc=now())
        write_json(target / 'target_status.json', status)
        return target
    except Exception as error:
        status.update(status='FAILED_OR_BLOCKED_INFERENCE', error_code=str(error), updated_at_utc=now())
        write_json(target / 'target_status.json', status)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job-dir', type=Path)
    parser.add_argument('--tensor-cache', type=Path)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({'status': 'DRY_RUN_NO_TARGET_READ_NO_MODEL_OUTPUT', 'target_fits': 0, 'new_source_fits': 0,
                          'target_predictions_computed': False, 'independent_confirmation_qualified': False}))
        return
    if args.job_dir is None or args.tensor_cache is None:
        parser.error('--execute requires --job-dir and --tensor-cache')
    output = execute(args.job_dir, args.tensor_cache)
    print(json.dumps({'status': 'exploratory_predictions_written_need_separate_validation', 'output': str(output),
                      'target_fits': 0, 'independent_confirmation_qualified': False}))


if __name__ == '__main__':
    main()
