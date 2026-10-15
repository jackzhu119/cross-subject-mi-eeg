#!/usr/bin/env python3
"""Metadata-only 18-source +174-target route candidate; never raw-data access.

The default prints a frozen catalogue only. Explicit receipt review reads five
named JSON records, each with an externally supplied full SHA256. It does not
inspect cache roots, download, import a scientific library, call prepare_data,
authenticate R2, issue a slot, or grant a scientific/training PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

REPO = Path(__file__).resolve().parents[3]
SOURCE_PATH = 'research_runs/Q8-E001/results/source_files.json'
SOURCE_SHA = '0ccef780ed5bfbc2d430b8caf0c108641fb230a2dc27e4189e7e771c999f64a6'
SOURCE_OFFICIAL_SHA = 'e553d65cd86e5309e077ccfea21a9bee6020c5d9d5040de12089c2b859770b86'
TARGET_HELPER = 'research_runs/REDESIGN_HANDOFF_20261015/official_edf_transport/official_edf_transport.py'
TARGET_HELPER_SHA = '1aa2da0b710b3ef109d00d19c75a00fda013a79f947e9aebbe3480c8e99b895f'
REFERENCE_PATH = 'research_runs/REDESIGN_EXPLORATORY_20261013/evidence/source_exact_input_fingerprints_receipt.json'
REFERENCE_SHA = '66c5aa472809cf29fe68b7b56401c4f0aa4b4f577156425a1f4e1fc20d45d8dd'
POLICY_PATH = 'research_runs/REDESIGN_CLOUD_20261013/config/numerical_execution_v1.json'
POLICY_SHA = '04f562ddddc4e5019e56240b980d6d9c2d78645860857a5ab0d9746e788ae476'
EXECUTION_SHA = 'bcd89d6747f00fb03bf1793df3753c53f67cfbf2f95275d40b042b682db61577'
LEGACY_SHA = '03f47bceb3998e407a28e7da56da4875b5d3e1e38746d196739be7262be7cff5'
OLD_TASK = '20261014T071918Z-exploratory-89b0c07d'
BASE_REVISION = '1efe9d1ba2ab8671ad1bf76c360e067fb63fd7ac'
REPAIR_RECEIPT_SHA = '0e487c7c8dcc83006681c8bdb066254da4184d49ab9f6ce96a07ad53d7cf092b'
REPAIR_ARCHIVE_SHA = '7ebd6080181ec3bb5d2c9faf74d754af68c0ea4eea48978467df713e8465f8a1'
FULL_SHA = '2871f422755bf5d0b939d0db59fc41547b192d6c939db1a6a13b97a91ba49ae9'
FORMAL_ARCHIVE_SHA = 'a4c6c3f7beadf6ce0c927c6e4b9d20b6d37ff3bc2c033ad4b4fd836ca38a6b0d'
NBYTES = 3295217315
MAX_JSON = 2 * 1024**2
SHA_RE = re.compile('[0-9a-f]{64}')
SOURCE_NAME = re.compile('A0[1-9][TE]\\.mat')
RECORDS = ('source_restore', 'target_bytes', 'runtime_bound', 'formal_source', 'route_binding')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strict_equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(strict_equal(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(strict_equal(a, b) for a, b in zip(actual, expected))
    return actual == expected


def require(actual, expected, message):
    if not strict_equal(actual, expected):
        raise ValueError(message)


def parse(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('duplicate_JSON_key')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_JSON')))


def read_json(path, expected_sha):
    """Open only an explicitly named bounded regular JSON metadata file."""
    path = Path(path).absolute()
    if path.suffix != '.json' or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('named_regular_JSON_without_symlink_required')
    if not isinstance(expected_sha, str) or not SHA_RE.fullmatch(expected_sha):
        raise ValueError('external_full_JSON_SHA256_required')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_JSON:
            raise ValueError('bounded_regular_JSON_required')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(MAX_JSON + 1)
        after = os.fstat(fd)
        attrs = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if any(getattr(before, a) != getattr(after, a) for a in attrs) or sha(raw) != expected_sha:
            raise ValueError('JSON_identity_changed')
    finally:
        os.close(fd)
    return parse(raw)


def canonical_root(value):
    """Lexical metadata validation only; never stat or walk a cache root."""
    if (not isinstance(value, str) or not value.startswith('/workspace/')
            or '\\' in value or any(ord(c) < 32 for c in value)
            or any(c in ('', '.', '..') for c in value.split('/')[1:])
            or str(PurePosixPath(value)) != value):
        raise ValueError('explicit_canonical_workspace_root_required')
    return value


def disjoint_roots(source_root, target_root):
    roots = [PurePosixPath(canonical_root(v)) for v in (source_root, target_root)]
    if roots[0] == roots[1] or roots[0] in roots[1].parents or roots[1] in roots[0].parents:
        raise ValueError('separate_nonoverlapping_source_and_target_roots_required')
    protected = (PurePosixPath('/workspace/.venvs'), PurePosixPath('/workspace/paper1-training-runtime-cp312-run01'),
                 PurePosixPath('/workspace/paper1-metadata-code-1efe9d1'))
    if any(r == p or r in p.parents or p in r.parents for r in roots for p in protected):
        raise ValueError('cache_metadata_root_overlaps_protected_runtime_or_code')
    return tuple(str(r) for r in roots)


def reject_r2_keys(value):
    if isinstance(value, dict):
        if {'object_key', 'r2_enabled', 'r2_import_receipt', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY'} & value.keys():
            raise ValueError('R2_identity_or_credentials_not_a_same_byte_official_receipt')
        for item in value.values():
            reject_r2_keys(item)
    elif isinstance(value, list):
        for item in value:
            reject_r2_keys(item)


def frozen_catalogue():
    source = read_json(REPO / SOURCE_PATH, SOURCE_SHA)
    if not isinstance(source, list) or len(source) != 18:
        raise ValueError('frozen_source18_required')
    source_rows = []
    for row in source:
        if set(row) != {'path', 'bytes', 'sha256'} or not isinstance(row['path'], str):
            raise ValueError('frozen_source_schema')
        name = PurePosixPath(row['path']).name
        if not SOURCE_NAME.fullmatch(name):
            raise ValueError('frozen_source_name')
        source_rows.append({'path': 'bnci/' + name, 'bytes': row['bytes'], 'sha256': row['sha256']})
    if len({r['path'] for r in source_rows}) != 18 or sum(r['bytes'] for r in source_rows) != 779873919:
        raise ValueError('frozen_source_identity_inventory')
    helper_path = REPO / TARGET_HELPER
    if helper_path.is_symlink() or sha(helper_path.read_bytes()) != TARGET_HELPER_SHA:
        raise ValueError('fixed_official_metadata_helper_changed')
    spec = importlib.util.spec_from_file_location('paper1_official_frozen_metadata_only', helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    target = helper.frozen_plan()  # Only its pinned public JSON/provenance/README.
    target_rows = [{'path': r['restore_relative_path'], 'bytes': r['bytes'], 'sha256': r['sha256']}
                   for r in target['files']]
    rows = sorted(source_rows + target_rows, key=lambda r: r['path'])
    if len(rows) != 192 or len({r['path'] for r in rows}) != 192 or sum(r['bytes'] for r in rows) != NBYTES:
        raise ValueError('frozen_192_input_union_changed')
    reference = read_json(REPO / REFERENCE_PATH, REFERENCE_SHA)
    policy = read_json(REPO / POLICY_PATH, POLICY_SHA)
    numerical = {'policy_id': policy['policy_id'], 'policy_sha256': POLICY_SHA,
        'execution_module_sha256': EXECUTION_SHA, 'historical_loader_sha256': LEGACY_SHA,
        'historical_generation_BLAS_identity_established': False,
        'state_application': 'every_band_every_trial_source_and_target'}
    return {'files': rows, 'source_files': sorted(source_rows, key=lambda r: r['path']),
            'target_files': sorted(target_rows, key=lambda r: r['path']), 'target_plan': target,
            'source_array_hashes': reference['source_file_provenance']['array_hashes'],
            'numerical_execution': numerical}


def exact_inventory(rows, expected, *, source=False):
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError('receipt_inventory_length')
    observed = []
    for row in rows:
        keys = {'filename', 'status', 'bytes', 'sha256'} if source else {'path', 'bytes', 'sha256'}
        allowed = keys | ({'response_route'} if source else set())
        if not isinstance(row, dict) or not keys <= row.keys() or set(row) - allowed:
            raise ValueError('exact_receipt_row_schema_no_aliases')
        if source:
            if row['status'] not in ('RESTORED_OFFICIAL_EXACT_BYTES', 'REUSED_VERIFIED_CACHE'):
                raise ValueError('source_official_or_verified_cache_status_required')
            name = row['filename']
            if not isinstance(name, str) or not SOURCE_NAME.fullmatch(name):
                raise ValueError('source_filename_alias_rejected')
            path = 'bnci/' + name
        else:
            path = row['path']
        observed.append({'path': path, 'bytes': row['bytes'], 'sha256': row['sha256']})
    if any(not isinstance(r['path'], str) for r in observed):
        raise ValueError('receipt_path_string_required')
    require(sorted(observed, key=lambda r: r['path']), expected, 'receipt_exact_path_size_SHA_inventory_required')


def pending_result(catalogue):
    return {'schema_version': 1, 'status': 'OFFLINE_FROZEN_192_CATALOGUE_ROUTE_PLAN_ONLY',
        'old_job_id': OLD_TASK, 'file_count': 192, 'source_file_count': 18, 'target_file_count': 174,
        'total_bytes': NBYTES, 'files': catalogue['files'],
        'source_manifest_sha256': SOURCE_SHA,
        'target_manifest_sha256': catalogue['target_plan']['frozen_manifest_sha256'],
        'provider_provenance_sha256': catalogue['target_plan']['provider_provenance_sha256'],
        'provider_tree_sha': catalogue['target_plan']['provider_tree_sha'],
        'license': catalogue['target_plan']['license'],
        'route': 'separate_official_source_and_target_cache_roots_not_R2_import',
        'cache_roots_observed': False, 'raw_bytes_opened': False,
        'actual_receipts_consumed': False, 'byte_identity_receipt_metadata_matched': False,
        'source_acceptance_receipt_metadata_matched': False,
        'actual_target_header_event_qc_input_acceptance': False,
        'actual_runtime_and_source_acceptance_granted_by_this_tool': False,
        'accounting_and_checkpoint_acceptance': False, 'verified_backup_acceptance': False,
        'target_transport_authorization': False, 'target_scientific_consumption_authorization': False,
        'production_routing_modified': False, 'prepare_data_called': False,
        'budget_reset': False, 'new_fits': 0, 'target_fits': 0,
        'target_predictions_computed': False, 'training_authorization': False}


def bound_candidate(catalogue, records, digests):
    """Check only named receipt metadata; their assertions remain evidence claims."""
    require(set(records), set(RECORDS), 'all_five_independent_metadata_records_required')
    require(set(digests), set(RECORDS), 'all_five_external_SHA_bindings_required')
    for name in RECORDS:
        if not isinstance(records[name], dict) or not isinstance(digests[name], str) or not SHA_RE.fullmatch(digests[name]):
            raise ValueError('complete_named_metadata_and_external_SHA_required')
        reject_r2_keys(records[name])
    source, target, runtime, formal, binding = (records[n] for n in RECORDS)
    expected_binding = {'schema_version': 1,
        'status': 'METADATA_ROUTE_BINDING_FOR_INDEPENDENT_REVIEW_NOT_EXECUTION',
        'old_job_id': OLD_TASK, 'source_root': binding.get('source_root'),
        'target_root': binding.get('target_root'),
        'source_restore_sha256': digests['source_restore'], 'target_bytes_sha256': digests['target_bytes'],
        'runtime_bound_sha256': digests['runtime_bound'], 'formal_source_sha256': digests['formal_source'],
        'source_manifest_sha256': SOURCE_SHA,
        'target_manifest_sha256': catalogue['target_plan']['frozen_manifest_sha256'],
        'training_authorization': False}
    require(binding, expected_binding, 'independent_cross_job_and_receipt_route_binding_required')
    source_root, target_root = disjoint_roots(binding['source_root'], binding['target_root'])
    for key, value in {'status': 'SOURCE18_EXACT_BYTES_RESTORED_NUMERICAL_ACCEPTANCE_PENDING',
            'source_expected_files': 18, 'source_expected_bytes': 779873919,
            'official_manifest_sha256': SOURCE_OFFICIAL_SHA, 'source_root': source_root,
            'old_task': OLD_TASK, 'diagnostic_rerun': False, 'runtime_imported': False,
            'target_EEG_accessed': False, 'training_authorization': False,
            'new_fits': 0, 'budget_reset': False}.items():
        require(source.get(key), value, 'source_restore_identity_or_pending_boundary:' + key)
    exact_inventory(source.get('files'), catalogue['source_files'], source=True)
    target_expected = {'schema_version': 1,
        'status': 'FROZEN_174_LOCAL_EDF_BYTES_VERIFIED_SCIENTIFIC_GATES_PENDING',
        'frozen_manifest_sha256': catalogue['target_plan']['frozen_manifest_sha256'],
        'file_count': 174, 'verified_bytes': 2515343396, 'files': target.get('files'),
        'transport': 'official_nemar_same_byte_edf_not_r2_key_receipt',
        'target_header_event_qc_and_input_hash_acceptance': False,
        'accounting_budget_checkpoint_acceptance': False,
        'source_and_actual_training_runtime_acceptance': False,
        'new_source_fits': 0, 'target_fits': 0, 'target_predictions': 0, 'training_authorization': False}
    require(target, target_expected, 'unchanged_explicit_target_byte_only_receipt_required')
    exact_inventory(target['files'], catalogue['target_files'])
    runtime_checks = {'status': 'REPAIRED_ACTUAL_TRAINING_RUNTIME_SOURCE_MATCH_OTHER_GATES_PENDING',
        'original_base_revision': BASE_REVISION, 'repair_archive_sha256': REPAIR_ARCHIVE_SHA,
        'independent_repair_receipt_sha256': REPAIR_RECEIPT_SHA,
        'new_container_source_restore_receipt_sha256': digests['source_restore'],
        'formal_source_acceptance_sha256': digests['formal_source'],
        'historical_full_diagnostic_package_sha256': FULL_SHA,
        'historical_formal_diagnostic_archive_sha256': FORMAL_ARCHIVE_SHA,
        'strict_trial_and_aggregate_hash_gate_passed': True,
        'actual_training_runtime_imports_verified': True, 'source_arrays_serialized': False,
        'historical_diagnostic_executed': False, 'original_preparation_receipt_created': False,
        'CUDA_initialized': False, 'GPU_computation_verified': False, 'new_fits': 0,
        'target_EEG_read': False, 'target_fits': 0, 'training_authorization': False,
        'old_accounting_reconciled': False, 'old_cost_known': False, 'budget_reset': False,
        'budget_expanded': False, 'budget_transition_authorized': False,
        'checkpoint_and_backup_transition_verified': False, 'target_mapping_and_restore_accepted': False}
    for key, value in runtime_checks.items():
        require(runtime.get(key), value, 'repaired_runtime_source_binding:' + key)
    source_ids = runtime.get('source_originals_verified')
    if not isinstance(source_ids, list):
        raise ValueError('complete_runtime_source_originals_required')
    exact_inventory([dict(row, status='REUSED_VERIFIED_CACHE') for row in source_ids], catalogue['source_files'], source=True)
    formal_checks = {'status': 'SOURCE_NUMERICAL_ACCEPTANCE_MATCH_TRAINING_STILL_BLOCKED',
        'code_revision': BASE_REVISION, 'source_complete_exact_hash_gate_passed': True,
        'source_array_hashes': catalogue['source_array_hashes'], 'source_files': 18,
        'source_runs': 108, 'source_trials': 2592, 'numerical_execution': catalogue['numerical_execution'],
        'training_consumer_imports_verified': True, 'private_full_package_independently_verified': True,
        'private_full_package_sha256': FULL_SHA, 'target_complete_restoration_verified': False,
        'target_frozen_input_mapping_verified': False, 'runtime_GPU_preflight_verified': False,
        'old_machine_identity_proven': False, 'budget_resume_authorized': False,
        'checkpoint_and_verified_backup_gates_passed': False, 'training_authorization': False,
        'new_fits': 0, 'target_EEG_read': False, 'target_predictions_computed': False,
        'source_arrays_serialized_or_replaced': False, 'historical_generation_BLAS_identity_established': False}
    for key, value in formal_checks.items():
        require(formal.get(key), value, 'formal_source_strict_scientific_metadata_required:' + key)
    result = pending_result(catalogue)
    result.update(status='METADATA_BOUND_192_ROUTE_CANDIDATE_SCIENTIFIC_GATES_PENDING',
        actual_receipts_consumed=True, byte_identity_receipt_metadata_matched=True,
        source_acceptance_receipt_metadata_matched=True,
        source_root=source_root, source_cache_root=source_root + '/bnci', target_root=target_root,
        target_cache_root=target_root + '/dreyer_acquisition', receipt_sha256=digests,
        independent_repair_receipt_sha256=REPAIR_RECEIPT_SHA,
        source_array_hashes=catalogue['source_array_hashes'], numerical_execution=catalogue['numerical_execution'],
        observation_boundary='Named JSON metadata matched; no raw cache existence or bytes independently observed; no scientific PASS or production route invoked.')
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, help='Optional new JSON output; never overwrite an existing file.')
    for name in RECORDS:
        option = name.replace('_', '-')
        p.add_argument('--' + option, type=Path)
        p.add_argument('--' + option + '-sha256')
    args = p.parse_args(argv)
    catalogue = frozen_catalogue()
    supplied = [getattr(args, n) is not None or getattr(args, n + '_sha256') is not None for n in RECORDS]
    if any(supplied):
        if not all(supplied) or any(getattr(args, n) is None or getattr(args, n + '_sha256') is None for n in RECORDS):
            p.error('Receipt mode requires all five named JSON files and all five independent SHA256 bindings.')
        digests = {n: getattr(args, n + '_sha256') for n in RECORDS}
        records = {n: read_json(getattr(args, n), digests[n]) for n in RECORDS}
        result = bound_candidate(catalogue, records, digests)
    else:
        result = pending_result(catalogue)
    data = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.output is not None:
        output = args.output.absolute()
        if output.suffix != '.json' or any(x.is_symlink() for x in (output, *output.parents)):
            raise ValueError('new_named_JSON_output_without_symlinks_required')
        if any(output == getattr(args, n) for n in RECORDS):
            raise ValueError('output_must_not_overlap_input_metadata')
        with output.open('x', encoding='utf-8') as stream:
            stream.write(data)
    print(data, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
