#!/usr/bin/env python3
"""Raw-only exploratory QC; default reads no EEG and fits no models.

Full-cohort execution is rejected unless this new code/rules/tests are present
in an actual Git commit and identical public bytes, and acquisition is complete.
Physical headers do not certify original-device calibration or real placement;
unknown prior exposure never becomes independent confirmatory evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

import numpy as np

STUDY = Path(__file__).resolve().parents[1]
REPO = STUDY.parents[1]
PREVIOUS = STUDY.parent / 'REDESIGN_SOURCE_SELECTION_20261012'
RULES_PATH = STUDY / 'config/RAW_QC_RULES_V2.json'
ACQUISITION_PATH = STUDY / 'evidence/full_acquisition_receipt.json'
MANIFEST = PREVIOUS / 'evidence/dataset_sources/dreyer_nemar_manifest.txt'
MANIFEST_SHA = '061a8e215093e1bb0db8f80f95b112c60266acfa640284d05f92c0c6a5ddc544'
CLASS = 'EXPOSURE_UNCONFIRMED_EXPLORATORY'
PATH_PATTERN = re.compile(r'sourcedata/sub-(\d{2})/eeg/sub-\1_task-(R[12]acquisition)_eeg\.edf\Z')
PINNED = {
    'scripts/infer_selection_core.py': '4374a65e24eb888657f1017e190f4da5714b84d783a0d90862964a2887945928',
    'scripts/core_source_inputs.py': '03f47bceb3998e407a28e7da56da4875b5d3e1e38746d196739be7262be7cff5',
    'scripts/check_dreyer_metadata.py': '4cc3930913c4dfe0f6cb2d768cf70057b446642d00b0936796d493a5649302fa',
    'config/core_experiment_v1.json': '7b072edced5e49f869f047d0a72871de4bb0e8a6108718aa90adf640bf02b5bc',
}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def object_hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read_json(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'required_regular_JSON_missing')
    obj = json.loads(path.read_text())
    require(isinstance(obj, dict), 'expected_JSON_object')
    return obj


def save_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.new-' + uuid.uuid4().hex)
    temporary.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    os.replace(temporary, path)


def pinned_modules():
    for relative, expected in PINNED.items():
        require(sha(PREVIOUS / relative) == expected, 'frozen_previous_code_changed:' + relative)
    sys.path.insert(0, str(PREVIOUS / 'scripts'))
    import core_source_inputs as inputs
    spec = importlib.util.spec_from_file_location('published_native_edf_adapter', PREVIOUS / 'scripts/infer_selection_core.py')
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    return inputs, adapter


def verified_rules(path=RULES_PATH):
    rules = read_json(path)
    required = {
        'schema_version': 2, 'status': 'FROZEN_BEFORE_FULL_ACQUISITION_SIGNAL_QC',
        'evidence_class': CLASS, 'independent_confirmation_qualified': False,
        'prior_use': 'unknown', 'model_training_enabled': False, 'model_inference_enabled': False,
        'required_runs': ['R1acquisition', 'R2acquisition'], 'required_participants': list(range(1, 88)),
        'provider_montage_exclusions': [17, 41], 'provider_flags_retained_unless_fixed_technical_failure': [4, 9, 29, 78, 79],
        'native_sampling_hz': 512, 'native_cue_code_to_label_index': {'769': 0, '770': 1},
        'class_cues_each_run': {'769': 20, '770': 20},
        'minimum_valid_trials_each_class_each_retained_person': 20,
        'original_GDF_verified': False, 'original_device_calibration_verified': False,
        'true_electrode_placement_independently_verified': False,
    }
    for key, expected in required.items():
        require(type(rules.get(key)) is type(expected) and rules.get(key) == expected, 'fixed_rule_mismatch:' + key)
    inputs, _ = pinned_modules()
    inputs.check_processing(rules['input_processing'])
    return rules


def registration_files():
    return [RULES_PATH, Path(__file__).resolve(), STUDY / 'tests/test_acquisition_signal_qc.py',
            STUDY / 'scripts/acquire_exposure_unconfirmed.py', STUDY / 'EXPLORATORY_DATA_ACCESS_PLAN.json',
            STUDY / 'evidence/author_prior_use_uncertain.json', STUDY / 'scripts/build_source_duplicate_reference.py',
            ACQUISITION_PATH, STUDY / 'evidence/source_exact_input_fingerprints.csv',
            STUDY / 'evidence/source_exact_input_fingerprints_receipt.json',
            REPO / 'research_runs/Q8-E001/results/source_files.json', MANIFEST] + [PREVIOUS / p for p in PINNED]


def verify_registration(commit):
    from acquire_exposure_unconfirmed import read_public
    require(isinstance(commit, str) and re.fullmatch('[0-9a-f]{40}', commit), 'full_public_registration_commit_required')
    records = []
    for path in registration_files():
        require(path.is_file() and not path.is_symlink(), 'registration_regular_file_absent:' + path.name)
        relative = path.resolve().relative_to(REPO.resolve()).as_posix()
        local = path.read_bytes()
        stored = subprocess.run(['git', '-C', str(REPO), 'show', commit + ':' + relative], capture_output=True)
        require(stored.returncode == 0 and stored.stdout == local, 'registered_Git_bytes_mismatch:' + relative)
        url = 'https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/' + commit + '/' + relative
        public = read_public(url, max(len(local), 1024))
        require(public == local, 'registered_public_bytes_mismatch:' + relative)
        records.append({'path': relative, 'sha256': sha(path), 'public_identical': True})
    return {'status': 'PASS_GIT_AND_PUBLIC_READBACK_BEFORE_RAW_QC', 'commit_sha': commit,
            'checked_at_utc': now(), 'files': records, 'independent_confirmation_qualified': False}


def verified_acquisition(receipt_path=ACQUISITION_PATH, cache_dir=None):
    from acquire_exposure_unconfirmed import author_uncertainty_gate, verified_plan
    author = author_uncertainty_gate()
    rows, _ = verified_plan()
    require(sha(MANIFEST) == MANIFEST_SHA, 'frozen_full_provider_manifest_changed')
    receipt = read_json(receipt_path)
    require(receipt.get('status') == 'ALL_174_HASH_HEADER_EVENT_AUDITED_EXPLORATORY_ONLY_FULL_SIGNAL_QC_PENDING',
            'actual_complete_174_acquisition_required')
    require(receipt.get('evidence_class') == CLASS and receipt.get('independent_confirmation_qualified') is False,
            'acquisition_prior_exposure_class_invalid')
    require(type(receipt.get('target_fits')) is int and receipt['target_fits'] == 0
            and type(receipt.get('target_predictions')) is int and receipt['target_predictions'] == 0
            and receipt.get('all_174_hash_header_event_audited') is True and not receipt.get('errors'),
            'receipt_contains_target_models_or_predictions')
    files = receipt.get('files')
    require(isinstance(files, list) and len(files) == 174, 'incomplete_acquisition_records')
    by_path = {row.get('path'): row for row in files}
    require(len(by_path) == 174 and set(by_path) == {row['path'] for row in rows}, 'duplicate_or_wrong_acquisition_identity')
    manifest = {}
    for row in rows:
        actual = by_path[row['path']]
        match = PATH_PATTERN.fullmatch(row['path'])
        require(match is not None, 'provider_path_identity_invalid')
        person, run = int(match.group(1)), match.group(2)
        require(actual.get('sha256') == row['checksum'] and actual.get('size_bytes') == row['size'],
                'acquisition_receipt_provider_hash_binding_mismatch')
        require(actual.get('subject') == person and actual.get('run') == run, 'acquisition_subject_or_run_mismatch')
        path = Path(cache_dir) / row['path'] if cache_dir is not None else Path(actual['cache_path'])
        if cache_dir is not None:
            require(path.resolve().is_relative_to(Path(cache_dir).resolve()), 'raw_cache_path_escape')
        require(path.is_file() and not path.is_symlink(), 'raw_regular_file_missing:' + row['path'])
        require(path.stat().st_size == row['size'], 'raw_file_size_mismatch:' + row['path'])
        manifest[row['path']] = {**row, 'cache_path': path, 'subject': person, 'run': run}
    return manifest, receipt, author


def subject_name(number):
    require(type(number) is int and 1 <= number <= 87, 'invalid_provider_person')
    return ('A' if number <= 60 else 'B' if number <= 81 else 'C') + f'{number:02d}'


def cue_records(cues, sfreq, n_samples, person, run, raw_hash, source_file, rules):
    require(sfreq == rules['native_sampling_hz'], 'native_sampling_mismatch')
    require(len(cues) == 40 and Counter(e['description'] for e in cues) == rules['class_cues_each_run'],
            'native_class_cue_counts_mismatch')
    result, excluded = [], []
    prior = -np.inf
    samples = set()
    for ordinal, cue in enumerate(cues, 1):
        onset = cue.get('onset')
        require(type(onset) in (int, float) and np.isfinite(onset) and onset > prior, 'cue_order_or_onset_ambiguity')
        prior = onset
        position = onset * sfreq
        sample = int(round(position))
        require(sample >= 0 and abs(position - sample) <= .5, 'cue_grid_mismatch')
        require(sample not in samples, 'duplicate_native_cue_sample')
        samples.add(sample)
        code = cue['description']
        identity = f'{subject_name(person)}_{run}_cue_{ordinal:02d}'
        start = sample - int(1.5 * sfreq)
        stop = sample + int(4.5 * sfreq)
        row = {'subject_id': subject_name(person), 'provider_person': person, 'run': run,
               'event_id': identity, 'cue_ordinal': ordinal, 'cue_sample': sample,
               'cue_onset_seconds': onset, 'native_sampling_hz': sfreq, 'native_event_code': code,
               'ytrue': rules['native_cue_code_to_label_index'][code],
               'label_index': rules['native_cue_code_to_label_index'][code],
               'label': rules['native_cue_code_to_label_index'][code] + 1,
               'context_native_start': start, 'context_native_stop': stop,
               'source_file': source_file, 'source_file_sha256': raw_hash}
        if start < 0 or stop > n_samples:
            excluded.append({**row, 'reason': 'incomplete_registered_native_six_second_context'})
        else:
            result.append(row)
    return result, excluded


def continuous_record_timing(path, header):
    """Verify EDF+C timekeeping without inferring events from channel values."""
    channels = header['channels']
    ann = [i for i, c in enumerate(channels) if c['label'] == 'EDF Annotations']
    require(len(ann) == 1 and header['sample_bytes'] == 2, 'unique_EDF_annotation_channel_required')
    offset = sum(c['samples_per_record'] * 2 for c in channels[:ann[0]])
    length = channels[ann[0]]['samples_per_record'] * 2
    block_bytes = sum(c['samples_per_record'] * 2 for c in channels)
    times = []
    with Path(path).open('rb') as stream:
        stream.seek(header['header_bytes'])
        for record in range(header['records']):
            block = stream.read(block_bytes)
            require(len(block) == block_bytes, 'truncated_native_record')
            tal = block[offset:offset + length].split(b'\x00')[0]
            require(b'\x14\x14' in tal, 'EDF_continuous_timekeeping_TAL_absent')
            stamp = float(tal.split(b'\x14')[0].split(b'\x15')[0].decode('ascii'))
            require(np.isfinite(stamp) and abs(stamp - record * header['record_duration_seconds']) <= .5 / 512,
                    'EDF_record_timekeeping_discontinuity')
            times.append(stamp)
    return {'records_verified': len(times), 'first_record_onset_seconds': times[0],
            'last_record_onset_seconds': times[-1], 'continuous_grid_verified': True}


def inspect_run(path, manifest_row, rules, modules=None):
    inputs, adapter = pinned_modules() if modules is None else modules
    signal, header, cues = adapter.load_physical_edf(path, manifest_row)
    require(signal.shape[0] == 19 and np.isfinite(signal).all() and (np.ptp(signal, axis=1) > 0).all(),
            'nonfinite_or_zero_dynamic_range_required_channel')
    timing = continuous_record_timing(path, header)
    rows, exclusions = cue_records(cues, 512, signal.shape[1], manifest_row['subject'], manifest_row['run'],
                                    manifest_row['checksum'], manifest_row['path'], rules)
    row = {'path': manifest_row['path'], 'subject_id': subject_name(manifest_row['subject']),
           'run': manifest_row['run'], 'sha256': manifest_row['checksum'],
           'native_signal19_sha256': inputs.array_hash(signal),
           'n_samples': signal.shape[1], 'physical_header_units': 'microvolts',
           'full_signal_finite': True, 'required_channels_positive_full_run_dynamic_range': True,
           'dynamic_range_microvolts': dict(zip(inputs.CHANNELS19, np.ptp(signal, axis=1).tolist())),
           'native_cue_counts': dict(Counter(e['description'] for e in cues)),
           'native_record_timing': timing, 'header': header,
           'genuine_channel_names_only_verified': True, 'true_device_montage_independently_verified': False,
           'original_device_calibration_verified': False,
           'provider_montage_hard_excluded': manifest_row['subject'] in rules['provider_montage_exclusions'],
           'incomplete_context_trials': len(exclusions)}
    return signal, rows, exclusions, row


def record_unique(seen, key, identity, scope):
    if key in seen:
        raise ValueError('exact_duplicate_' + scope + ':' + str(seen[key]) + '|' + str(identity))
    seen[key] = identity


def verify_source_fingerprints(path):
    if path is None:
        return {}, {'status': 'NOT_CHECKED_NO_AUTHENTICATED_SOURCE19_FINGERPRINTS', 'cross_dataset_identity_established': False}
    path = Path(path)
    require(path.suffix == '.csv' and path.is_file() and not path.is_symlink(), 'source_reference_regular_CSV_required')
    receipt_path = path.with_name(path.stem + '_receipt.json')
    obj = read_json(receipt_path)
    require(obj.get('status') == 'SOURCE_COPY_FINGERPRINTS_READY_NO_MODEL_RESULTS'
            and obj.get('new_source_models_fitted') == 0 and obj.get('new_neural_fits') == 0
            and obj.get('target_predictions') == 0 and obj.get('target_fits') == 0,
            'source_fingerprint_scope_invalid')
    require(obj.get('helper_sha256') == PINNED['scripts/core_source_inputs.py']
            and obj.get('config_sha256') == PINNED['config/core_experiment_v1.json']
            and obj.get('reference_sha256') == sha(path), 'source_reference_code_or_CSV_binding_mismatch')
    audit = obj.get('source_file_provenance', {})
    require(audit.get('status') == 'PASS_SOURCE19_INPUTS_ONLY'
            and audit.get('n_binary_trials') == 2592 and audit.get('n_raw_files') == 18,
            'source19_actual_raw_audit_missing')
    with path.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    require(len(rows) == obj.get('source_trials') == 2592, 'source_fingerprint_inventory_incomplete')
    seen, identifiers = {}, set()
    for row in rows:
        require(int(row['subject']) in range(1,10) and int(row['canonical_label']) in (1,2), 'source_reference_identity_or_label_invalid')
        hashes = {band: row.get(band + '_sha256') for band in ('broad', 'mu', 'beta')}
        require(all(re.fullmatch('[0-9a-f]{64}', h or '') for h in hashes.values()), 'source_input_fingerprint_invalid')
        identity = row.get('source_sample_id')
        require(isinstance(identity, str) and identity and identity not in identifiers, 'source_duplicate_sample_identity')
        identifiers.add(identity)
        for band, digest in hashes.items():
            record_unique(seen, (band, digest), identity, 'source_input')
        record_unique(seen, ('combined', object_hash(hashes)), identity, 'source_combined_input')
    return seen, {'status': 'AUTHENTICATED_SOURCE19_INPUT_FINGERPRINT_COMPARISON_ENABLED',
                  'CSV_sha256': sha(path), 'receipt_sha256': sha(receipt_path),
                  'n_source_trials': len(rows), 'new_model_fits': 0, 'cross_dataset_identity_established': False}


def eligible_people(event_rows, inspected, rules):
    retained, excluded = [], []
    for person in rules['required_participants']:
        person_name = subject_name(person)
        runs = {r['run'] for r in inspected if r['subject_id'] == person_name}
        require(runs == set(rules['required_runs']), 'required_two_raw_runs_absent:' + person_name)
        if person in rules['provider_montage_exclusions']:
            excluded.append({'subject_id': person_name, 'reason': 'provider_unrecoverable_electrode_order_flag'})
            continue
        events = [e for e in event_rows if e['subject_id'] == person_name]
        counts = Counter(e['ytrue'] for e in events)
        if any(counts[c] < rules['minimum_valid_trials_each_class_each_retained_person'] for c in (0, 1)):
            excluded.append({'subject_id': person_name, 'reason': 'prespecified_minimum_twenty_complete_context_trials_each_class_not_met',
                             'valid_class_counts': dict(counts)})
        else:
            retained.append(person_name)
    return retained, excluded


def write_csv(path, rows, fields):
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def audit(cache_dir, receipt_path, registration, output_dir, tensor_cache=None, source_fingerprints=None):
    rules = verified_rules()
    modules = pinned_modules()
    inputs, _ = modules
    manifest, receipt, author = verified_acquisition(receipt_path, cache_dir)
    if source_fingerprints is not None:
        require(Path(source_fingerprints).resolve() == (STUDY / 'evidence/source_exact_input_fingerprints.csv').resolve(),
                'source_reference_must_equal_publicly_registered_CSV')
    source_seen, source_scope = verify_source_fingerprints(source_fingerprints)
    output_dir = Path(output_dir)
    require(not output_dir.exists(), 'audit_output_already_exists_no_overwrite')
    output_dir.mkdir(parents=True)
    base = {'schema_version': 2, 'evidence_class': CLASS, 'independent_confirmation_qualified': False,
            'author_prior_use': 'unknown', 'original_GDF_verified': False,
            'original_device_calibration_verified': False, 'true_electrode_placement_independently_verified': False,
            'new_source_fits': 0, 'new_neural_fits': 0, 'target_fits': 0, 'target_predictions_computed': False,
            'target_performance_used_for_eligibility': False, 'rules_sha256': sha(RULES_PATH),
            'qc_code_sha256': sha(__file__), 'acquisition_receipt_sha256': sha(receipt_path),
            'author_uncertainty_sha256': author['sha256'], 'public_registration': registration,
            'source_target_duplicate_scope': source_scope, 'started_at_utc': now(),
            'qualification': 'Published source EDF mirror; operational header/channel/event qualification only, not original GDF/device/montage authentication.'}
    save_json(output_dir / 'raw_qc_status.json', {**base, 'status': 'RUNNING_RAW_ONLY_QC', 'files_processed': 0})
    events, exclusions, inspected, tensor_receipts = [], [], [], []
    raw_seen, signal_seen, input_seen, context_seen = {}, {}, dict(source_seen), {}
    try:
        for person in rules['required_participants']:
            person_tensors = {band: [] for band in ('broad', 'mu', 'beta')}
            person_rows = []
            for run in rules['required_runs']:
                name = f'sourcedata/sub-{person:02d}/eeg/sub-{person:02d}_task-{run}_eeg.edf'
                entry = manifest[name]
                record_unique(raw_seen, entry['checksum'], name, 'raw_EDF_file')
                signal, rows, drops, run_audit = inspect_run(entry['cache_path'], entry, rules, modules)
                record_unique(signal_seen, run_audit['native_signal19_sha256'], name, 'native_signal19_run')
                inspected.append(run_audit)
                if not run_audit['provider_montage_hard_excluded']:
                    exclusions.extend(drops)
                    for row in rows:
                        native = signal[:, row['context_native_start']:row['context_native_stop']]
                        row['native_context19_sha256'] = inputs.array_hash(native)
                        record_unique(context_seen, row['native_context19_sha256'], row['event_id'], 'native_context19')
                        arrays = inputs.transform_context19(signal, 512, row['cue_sample'], rules['input_processing'])
                        row['input_sha256'] = {band: inputs.array_hash(value) for band, value in arrays.items()}
                        row['epoch_sha256'] = object_hash(row['input_sha256'])
                        for band, digest in row['input_sha256'].items():
                            record_unique(input_seen, (band, digest), row['event_id'], 'source_or_target_input_' + band)
                            person_tensors[band].append(arrays[band])
                        record_unique(input_seen, ('combined', row['epoch_sha256']), row['event_id'], 'source_or_target_combined_input')
                        person_rows.append(row)
                else:
                    exclusions.extend({**row, 'reason': 'provider_unrecoverable_electrode_order_flag'} for row in rows + drops)
                save_json(output_dir / 'raw_qc_status.json', {**base, 'status': 'RUNNING_RAW_ONLY_QC', 'files_processed': len(inspected),
                                                          'eligible_event_inputs_created': len(events) + len(person_rows), 'updated_at_utc': now()})
                print(json.dumps({'stage': 'raw_signal_qc_no_models', 'files_processed': len(inspected),
                                  'expected_files': 174, 'subject_id': subject_name(person),
                                  'target_fits': 0, 'target_predictions_computed': False}), flush=True)
            events.extend(person_rows)
            if tensor_cache is not None and person_rows:
                folder = Path(tensor_cache)
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / (subject_name(person) + '.npz')
                require(not path.exists(), 'tensor_cache_file_already_exists_no_overwrite')
                arrays = {band: np.stack(values) for band, values in person_tensors.items()}
                arrays['event_ids'] = np.asarray([row['event_id'] for row in person_rows])
                np.savez(path, **arrays)
                tensor_receipts.append({'subject_id': subject_name(person), 'path': str(path), 'bytes': path.stat().st_size,
                                        'sha256': sha(path), 'n_events': len(person_rows), 'raw_only_input_cache_no_models': True})
            save_json(output_dir / 'partial_file_audit.json', {'files': inspected, 'events_created': len(events),
                                                            'target_fits': 0, 'target_predictions_computed': False})
        retained, person_exclusions = eligible_people(events, inspected, rules)
        for person in retained:
            require({e['run'] for e in events if e['subject_id']==person} == set(rules['required_runs']),
                    'complete_contexts_do_not_cover_both_required_runs:'+person)
        retained_events = [row for row in events if row['subject_id'] in retained]
        require(len(inspected) == 174 and len(retained) >= 3, 'complete_QC_or_minimum_eligible_cohort_absent')
        roster = {'schema_version': 2, 'cohort_id': 'Dreyer2023', 'evidence_class': CLASS,
                  'independent_confirmation_qualified': False, 'prior_use': 'unknown', 'synthetic_fixture': False,
                  'participants': retained, 'seeds': [20261013, 20261014, 20261015],
                  'architectures': ['broad', 'shared'], 'selectors': ['fixed', 'mean_loss', 'mean_rank'],
                  'label_map': {'0': 'left_hand_MI', '1': 'right_hand_MI'},
                  'technical_exclusions': [row['subject_id'] for row in person_exclusions],
                  'participant_exclusion_details': person_exclusions, 'events': retained_events,
                  'event_exclusions': exclusions, 'qualification': base['qualification'],
                  'raw_only_roster_frozen': True, 'performance_used_for_eligibility': False,
                  'target_fits': 0, 'target_predictions_computed': False, 'rules_sha256': sha(RULES_PATH)}
        save_json(output_dir / 'raw_only_roster.json', roster)
        fields = ['subject_id', 'provider_person', 'run', 'event_id', 'cue_ordinal', 'cue_sample', 'cue_onset_seconds',
                  'native_sampling_hz', 'native_event_code', 'ytrue', 'label', 'context_native_start', 'context_native_stop',
                  'source_file', 'source_file_sha256', 'native_context19_sha256', 'epoch_sha256']
        write_csv(output_dir / 'raw_only_event_roster.csv', retained_events, fields)
        save_json(output_dir / 'file_signal_audit.json', {'files': inspected})
        save_json(output_dir / 'tensor_cache_receipt.json', {'files': tensor_receipts, 'new_model_fits': 0,
                                                          'target_fits': 0, 'target_predictions_computed': False})
        class_counts = Counter(row['ytrue'] for row in retained_events)
        report = {**base, 'status': 'PASS_RAW_ONLY_FULL_COHORT_QC_EXPLORATORY_OPERATIONAL_SCOPE',
                  'finished_at_utc': now(), 'all_174_files_examined': True, 'files_processed': len(inspected),
                  'participant_and_event_eligibility_frozen': True,
                  'retained_participants': retained, 'n_retained_participants': len(retained),
                  'n_eligible_events': len(retained_events), 'retained_class_counts': {str(k): v for k, v in class_counts.items()},
                  'participant_exclusions': person_exclusions, 'n_event_exclusion_records': len(exclusions),
                  'full_physical_signal_scan_passed': True, 'physical_header_scale_verified': True,
                  'native_event_semantics_verified': True, 'published_channel_label_order_verified': True,
                  'exact_duplicate_raw_files_found': 0, 'exact_duplicate_native_runs_found': 0,
                  'exact_duplicate_native_contexts_found': 0, 'exact_duplicate_inputs_found': 0,
                  'source_target_exact_input_comparison_checked': bool(source_seen),
                  'participant_identity_independence_established_by_hashes': False,
                  'roster_sha256': sha(output_dir / 'raw_only_roster.json'),
                  'csv_roster_sha256': sha(output_dir / 'raw_only_event_roster.csv'),
                  'file_audit_sha256': sha(output_dir / 'file_signal_audit.json'),
                  'tensor_cache_receipt_sha256': sha(output_dir / 'tensor_cache_receipt.json'),
                  'future_model_execution_authorized_by_this_audit': False,
                  'independent_confirmation_authorized_by_this_audit': False}
        save_json(output_dir / 'full_raw_qc_report.json', report)
        save_json(output_dir / 'raw_qc_status.json', report)
        return report
    except Exception as error:
        failure = {**base, 'status': 'BLOCKED_RAW_ONLY_QC_NO_MODEL_EXECUTION', 'updated_at_utc': now(),
                   'error_code': str(error), 'files_processed': len(inspected), 'event_inputs_created': len(events),
                   'future_model_execution_authorized_by_this_audit': False}
        save_json(output_dir / 'failure.json', failure)
        save_json(output_dir / 'raw_qc_status.json', failure)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--registration-commit')
    parser.add_argument('--cache-dir', type=Path, default=Path('/workspace/mi-eeg-redesign-data/dreyer_acquisition'))
    parser.add_argument('--acquisition-receipt', type=Path, default=ACQUISITION_PATH)
    parser.add_argument('--source-fingerprints', type=Path)
    parser.add_argument('--tensor-cache', type=Path)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({'status': 'DRY_RUN_NO_RAW_EEG_READ', 'evidence_class': CLASS,
                          'independent_confirmation_qualified': False, 'target_fits': 0,
                          'target_predictions_computed': False, 'source_fits': 0}))
        return
    registration = verify_registration(args.registration_commit)
    out = args.output_dir or STUDY / 'results' / ('raw-qc-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    result = audit(args.cache_dir, args.acquisition_receipt, registration, out, args.tensor_cache, args.source_fingerprints)
    print(json.dumps({key: result[key] for key in ('status', 'files_processed', 'n_retained_participants', 'n_eligible_events',
                                                'target_fits', 'target_predictions_computed', 'independent_confirmation_qualified')}))


if __name__ == '__main__':
    main()
