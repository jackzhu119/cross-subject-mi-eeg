#!/usr/bin/env python3
"""Separate artifact/logit reconstruction, without training or model inference.

A PASS means file coverage, event identity, labels, hashes, eval-state receipts
and independent arithmetic agree. It is not independent human review or proof
of independent participant identity, physiological mechanism, or novelty.
"""
from __future__ import annotations
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
import numpy as np
from scipy.special import softmax

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
CONFIG = STUDY / 'config/experiment.json'
ARCHITECTURES = ('broad', 'shared')
SELECTORS = ('fixed', 'mean_loss', 'mean_rank')
SEEDS = (20261013, 20261014, 20261015)
HASH = re.compile(r'[0-9a-f]{64}\Z')


def require(condition, code):
    if not condition:
        raise ValueError(code)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 ** 2), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'required_regular_json_absent:' + path.name)
    value = json.loads(path.read_text())
    require(isinstance(value, dict), 'json_object_required')
    return value


def integer(value, field):
    require(type(value) is int or isinstance(value, str) and re.fullmatch(r'-?[0-9]+', value), 'invalid_integer:' + field)
    return int(value)


def local_path(job, name):
    require(isinstance(name, str) and name and not Path(name).is_absolute() and '..' not in Path(name).parts,
            'nontraversing_artifact_required')
    job, path = Path(job).resolve(), Path(job) / name
    require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(job), 'unsafe_artifact:' + name)
    for parent in path.parents:
        if parent == job:
            break
        require(not parent.is_symlink(), 'symlink_ancestor:' + name)
    return path


def validate_roster(roster, expected_participants=85, expected_events=6800):
    require(roster.get('independent_confirmation_qualified') is False and roster.get('prior_use') == 'unknown'
            and roster.get('synthetic_fixture') is False and roster.get('target_fits') == 0
            and type(roster.get('target_fits')) is int and roster.get('target_predictions_computed') is False,
            'locked_exploratory_raw_only_roster_required')
    people = roster.get('participants', [])
    require(len(people) == expected_participants and len(set(people)) == len(people), 'participant_coverage_changed')
    require(not {'A17', 'A41'}.intersection(people), 'provider_bad_montage_cannot_reenter')
    events = {}
    fingerprints = set()
    counts = collections.Counter()
    for row in roster.get('events', []):
        key = (row.get('subject_id'), row.get('event_id'))
        require(key[0] in people and isinstance(key[1], str) and key[1] and key not in events, 'duplicate_or_unknown_locked_event')
        label = integer(row.get('ytrue'), 'locked_ytrue')
        require(label in (0, 1), 'nonbinary_locked_label')
        fingerprint = row.get('epoch_sha256')
        require(isinstance(fingerprint, str) and HASH.fullmatch(fingerprint) and fingerprint not in fingerprints,
                'invalid_or_duplicate_locked_window_hash')
        hashes = row.get('input_sha256', {})
        require(set(hashes) == {'broad', 'mu', 'beta'} and all(isinstance(x, str) and HASH.fullmatch(x) for x in hashes.values()),
                'all_input_fingerprints_required')
        combined = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        require(combined == fingerprint, 'combined_window_fingerprint_mismatch')
        events[key] = (label, fingerprint)
        fingerprints.add(fingerprint)
        counts[(key[0], label)] += 1
    require(len(events) == expected_events and all(counts[(p, c)] >= 1 for p in people for c in (0, 1)),
            'locked_event_coverage_or_binary_class_missing')
    return people, events


def validate_records(rows, roster, checkpoint_identities, raw_logits, expected_participants=85, expected_events=6800):
    """Own reconstruction from raw logits and locked event order, never scores."""
    people, events = validate_roster(roster, expected_participants, expected_events)
    event_order = [(row['subject_id'], row['event_id']) for row in roster['events']]
    event_indices = {key: i for i, key in enumerate(event_order)}
    expected_conditions = {(a, r, s) for a in ARCHITECTURES for r in SELECTORS for s in SEEDS}
    identities = {}
    for cell in checkpoint_identities:
        key = (cell.get('model_arch'), cell.get('analysis_selector', cell.get('selector')), integer(cell.get('seed'), 'checkpoint_seed'))
        require(key in expected_conditions and key not in identities, 'duplicate_or_unknown_checkpoint_condition')
        require(cell.get('source_only') is True and type(cell.get('target_fit_count')) is int and cell.get('target_fit_count') == 0,
                'source_only_checkpoint_policy_required')
        require(isinstance(cell.get('checkpoint_sha256'), str) and HASH.fullmatch(cell['checkpoint_sha256']), 'invalid_checkpoint_hash')
        identities[key] = cell
    require(set(identities) == expected_conditions, 'nominal_source_checkpoint_coverage_incomplete')
    expected_keys = {f'{a}__{r}__{s}' for a, r, s in expected_conditions}
    require(set(raw_logits) == expected_keys, 'raw_logits_condition_inventory_changed')
    probabilities = {}
    for key in expected_keys:
        values = raw_logits[key]
        require(values.dtype == np.float32 and values.shape == (expected_events, 2) and np.isfinite(values).all(),
                'raw_logits_not_complete_finite_float32')
        probabilities[key] = softmax(values.astype(np.float64), axis=1)
    seen = set()
    largest_probability_error = 0.0
    for row in rows:
        event = (row.get('subject_id'), row.get('event_id'))
        condition = (row.get('model_arch'), row.get('selector'), integer(row.get('seed'), 'seed'))
        require(event in events and condition in expected_conditions, 'unknown_prediction_event_or_condition')
        key = (*condition, *event)
        require(key not in seen, 'duplicate_prediction_cell')
        seen.add(key)
        label, fingerprint = events[event]
        require(integer(row.get('ytrue'), 'ytrue') == label and row.get('epoch_sha256') == fingerprint,
                'prediction_truth_or_window_hash_changed')
        cell = identities[condition]
        require(row.get('checkpoint_sha256') == cell['checkpoint_sha256']
                and row.get('owner_cell') == cell.get('owner_cell'), 'prediction_checkpoint_or_alias_identity_changed')
        logit_key = '__'.join(map(str, condition))
        values = raw_logits[logit_key][event_indices[event]]
        try:
            declared_logits = np.asarray([float(row['logit_left']), float(row['logit_right'])], dtype=np.float64)
            declared_probs = np.asarray([float(row['p_left']), float(row['p_right'])], dtype=np.float64)
        except (ValueError, KeyError, TypeError):
            raise ValueError('missing_or_invalid_logits_probabilities') from None
        require(np.isfinite(declared_logits).all() and np.array_equal(declared_logits, values.astype(np.float64)),
                'csv_logits_differ_from_raw_archive')
        expected_probs = probabilities[logit_key][event_indices[event]]
        error = float(np.max(np.abs(declared_probs - expected_probs)))
        largest_probability_error = max(largest_probability_error, error)
        require(np.isfinite(declared_probs).all() and error <= 1e-12 and abs(declared_probs.sum() - 1.0) <= 1e-12,
                'independent_softmax_reconstruction_failed')
        require(integer(row.get('ypred'), 'ypred') == int(np.argmax(values)), 'prediction_not_raw_logit_argmax')
    require(len(seen) == len(events) * 18 and len(rows) == len(seen), 'full_18_cell_prediction_coverage_incomplete')
    # Aliases are legitimate only identical architecture/seed/duration owners.
    owner_hashes = {}
    for condition, cell in identities.items():
        name = '__'.join(map(str, condition))
        owner = cell.get('owner_cell')
        signature = (cell.get('checkpoint_sha256'), hashlib.sha256(raw_logits[name].tobytes()).hexdigest())
        require(owner not in owner_hashes or owner_hashes[owner] == signature, 'alias_logits_or_checkpoint_disagree')
        owner_hashes[owner] = signature
    return {'participants_n': len(people), 'eligible_events': len(events), 'nominal_cells': 18,
            'prediction_rows': len(rows), 'largest_independent_softmax_absolute_error': largest_probability_error,
            'aliases_have_identical_checkpoint_and_logits': True, 'logits_argmax_reconstructed': True,
            'truth_and_input_hashes_reconstructed': True}


def validate(job):
    job = Path(job).resolve()
    target = job / 'target'
    receipt = read_json(local_path(job, 'target/prediction_completion_receipt.json'))
    require(receipt.get('status') == 'EXPLORATORY_PREDICTIONS_COMPLETE_UNVALIDATED_NO_STATISTICS'
            and receipt.get('independent_confirmation_qualified') is False and receipt.get('prior_use') == 'unknown'
            and type(receipt.get('target_fits')) is int and receipt['target_fits'] == 0
            and receipt.get('target_predictions_computed') is True
            and receipt.get('nominal_cells_completed') == 18 and receipt.get('prediction_rows') == 122400,
            'exploratory_prediction_completion_required')
    bindings = {'target/predictions.csv': 'predictions_sha256', 'target/raw_logits.npz': 'raw_logits_sha256',
                'target/model_state_receipts.json': 'model_state_receipts_sha256',
                'target/raw_only_roster.json': 'roster_sha256', 'source/source_completion_manifest.json': 'source_manifest_sha256',
                'preinference_freeze.json': 'preinference_freeze_sha256'}
    for name, field in bindings.items():
        require(digest(local_path(job, name)) == receipt.get(field), 'completion_artifact_hash_mismatch:' + name)
    source_validation = read_json(local_path(job, 'source/source_validation.json'))
    require(source_validation.get('status') == 'PASS_SOURCE_ARTIFACT_VALIDATION_EXPLORATORY'
            and source_validation.get('source_completion_manifest_sha256') == receipt['source_manifest_sha256']
            and source_validation.get('qualified_independent_confirmation') is False
            and type(source_validation.get('target_fits')) is int and source_validation['target_fits'] == 0
            and source_validation.get('target_predictions_computed') is False,
            'validated_source_identity_missing')
    freeze = read_json(job / 'preinference_freeze.json')
    require(freeze.get('status') == 'FROZEN_BEFORE_TARGET_INFERENCE_EXPLORATORY_ONLY'
            and freeze.get('independent_confirmation_qualified') is False and freeze.get('target_predictions_computed') is False,
            'pre_output_exploratory_freeze_missing')
    for name in ('source/source_validation.json', 'source/source_completion_manifest.json', 'target/raw_only_roster.json'):
        binding = freeze.get('artifact_bindings', {}).get(name, {})
        require(binding.get('sha256') == digest(local_path(job, name))
                and freeze.get('files', {}).get(binding.get('public_path')) == binding.get('sha256'),
                'public_preinference_binding_changed:' + name)
    require(source_validation.get('config_sha256') == digest(CONFIG), 'source_validation_config_changed')
    roster = read_json(target / 'raw_only_roster.json')
    with (target / 'predictions.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    with np.load(target / 'raw_logits.npz', allow_pickle=False) as data:
        require(data['event_ids'].tolist() == [r['event_id'] for r in roster['events']], 'raw_archive_event_order_differs')
        logits = {k: data[k].copy() for k in data.files if k != 'event_ids'}
    checked = validate_records(rows, roster, receipt.get('checkpoints', []), logits)
    states = read_json(target / 'model_state_receipts.json')
    require(states.get('target_fits') == 0 and states.get('independent_confirmation_qualified') is False
            and states.get('cells') == receipt.get('checkpoints'), 'full_eval_state_receipt_inventory_mismatch')
    for cell in states['cells']:
        checkpoint = local_path(job, cell['checkpoint_file'])
        require(digest(checkpoint) == cell['checkpoint_sha256'] and cell.get('parameters_and_buffers_unchanged') is True
                and cell.get('mode') == 'eval_inference_mode' and cell.get('target_fits') == 0
                and cell.get('state_before_sha256') == cell.get('state_after_sha256') == cell.get('model_state_sha256'),
                'source_checkpoint_changed_or_target_state_updated')
        partial = local_path(job, cell['logits_file'])
        require(digest(partial) == cell['logits_sha256'], 'raw_cell_logit_file_changed')
        with np.load(partial, allow_pickle=False) as data:
            key = f"{cell['model_arch']}__{cell['analysis_selector']}__{cell['seed']}"
            require(np.array_equal(data['logits'], logits[key])
                    and data['event_ids'].tolist() == [r['event_id'] for r in roster['events']], 'cell_and_combined_logits_differ')
    result = {'status': 'PASS_SEPARATE_PREDICTION_ARTIFACT_VALIDATION_EXPLORATORY', **checked,
              'predictions_sha256': receipt['predictions_sha256'], 'raw_logits_sha256': receipt['raw_logits_sha256'],
              'roster_sha256': receipt['roster_sha256'], 'completion_receipt_sha256': digest(target / 'prediction_completion_receipt.json'),
              'source_validation_sha256': digest(job / 'source/source_validation.json'),
              'validator_sha256': digest(Path(__file__)), 'config_sha256': digest(CONFIG),
              'model_fits_started_by_validation': 0, 'target_predictions_computed_by_validation': False,
              'target_fits': 0, 'independent_confirmation_qualified': False, 'independent_human_peer_review': False,
              'scope': 'Separate arithmetic/logit/event/checkpoint artifact reconstruction; not real-data model rerun or independence certification.'}
    from infer_exploratory import write_json
    write_json(target / 'prediction_validation.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job-dir', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.job_dir)
        print(json.dumps({'status': result['status'], 'prediction_rows': result['prediction_rows'],
                          'target_fits': 0, 'independent_confirmation_qualified': False}))
    except Exception as error:
        from infer_exploratory import write_json
        failure = {'status': 'FAILED_PREDICTION_ARTIFACT_VALIDATION', 'error_code': str(error), 'target_fits': 0,
                   'model_fits_started_by_validation': 0, 'target_predictions_computed_by_validation': False,
                   'independent_confirmation_qualified': False}
        write_json(args.job_dir / 'target/prediction_validation_failure.json', failure)
        print(json.dumps(failure))
        raise SystemExit(2) from None


if __name__ == '__main__':
    main()
