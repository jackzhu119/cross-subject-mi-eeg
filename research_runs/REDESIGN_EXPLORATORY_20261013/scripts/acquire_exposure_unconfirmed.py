#!/usr/bin/env python3
"""Acquire pinned source EDF mirror as EXPOSURE_UNCONFIRMED exploratory data.

Default is metadata-only dry-run. Explicit acquisition requires the author's
actual uncertainty record plus local Git and public fixed-commit byte identity.
No model is fitted or evaluated, and a header/event audit is never full signal QC.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
PREVIOUS = REPO / 'research_runs/REDESIGN_SOURCE_SELECTION_20261012'
PLAN_PATH = ROOT / 'EXPLORATORY_DATA_ACCESS_PLAN.json'
AUTHOR_PATH = ROOT / 'evidence/author_prior_use_uncertain.json'
MANIFEST_PATH = PREVIOUS / 'evidence/dataset_sources/dreyer_nemar_manifest.txt'
MANIFEST_SHA = '061a8e215093e1bb0db8f80f95b112c60266acfa640284d05f92c0c6a5ddc544'
PINNED_HELPERS = {
    'scripts/check_dreyer_metadata.py': '4cc3930913c4dfe0f6cb2d768cf70057b446642d00b0936796d493a5649302fa',
    'scripts/acquire_dreyer_runs.py': 'acbf65e5523bc84c0f985514e4c026fb0dc7bd9477e41a40e82e9dce3746aff2',
}
REPOSITORY = 'jackzhu119/cross-subject-mi-eeg'
COMMON19 = ['Fz', 'FC3', 'FC1', 'FCz', 'FC2', 'FC4', 'C5', 'C3', 'C1', 'Cz',
            'C2', 'C4', 'C6', 'CP3', 'CP1', 'CPz', 'CP2', 'CP4', 'Pz']
PATH_PATTERN = re.compile(r'sourcedata/sub-(\d{2})/eeg/sub-\1_task-(R[12]acquisition)_eeg\.edf')
DEFAULT_CACHE = Path('/workspace/mi-eeg-redesign-data/dreyer_acquisition')
DEFAULT_PILOT = Path('/workspace/mi-eeg-redesign-data/dreyer_subset')
CLASS = 'EXPOSURE_UNCONFIRMED_EXPLORATORY'


def now():
    return datetime.now(timezone.utc).isoformat()


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.new-' + uuid.uuid4().hex)
    temporary.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    os.replace(temporary, path)


def import_previous(relative, name):
    source = PREVIOUS / relative
    if sha_file(source) != PINNED_HELPERS[relative]:
        raise ValueError('published_helper_sha256_changed:' + relative)
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verified_plan(plan_path=PLAN_PATH):
    # Reuse the unchanged published manifest/path/size validation helper.
    module = import_previous('scripts/acquire_dreyer_runs.py', 'published_access_validation')
    rows, plan = module.verified_manifest_and_plan(MANIFEST_PATH, plan_path)
    required = {
        'evidence_class': CLASS, 'independent_confirmation_qualified': False,
        'actual_author_uncertainty_record_required': True,
        'maximum_download_workers': 3,
        'maximum_raw_bytes_for_fixed_full_acquisition_manifest': 2515343396,
        'full_signal_qc_separate_from_header_audit': True,
        'prior_confirmatory_protocol_remains_unchanged': True,
        'model_training_enabled': False, 'model_inference_enabled': False,
    }
    for key, expected in required.items():
        if type(plan.get(key)) is not type(expected) or plan.get(key) != expected:
            raise ValueError('exploratory_plan_mismatch:' + key)
    return rows, plan


def author_uncertainty_gate(path=AUTHOR_PATH):
    if path is None:
        raise ValueError('actual_author_uncertainty_record_missing')
    declaration = json.loads(path.read_text())
    required = {
        'status': 'AUTHOR_REPORTED_UNCERTAIN', 'dataset': 'Dreyer2023',
        'provider_dataset_id': 'nm000250', 'provider_manifest_sha256': MANIFEST_SHA,
        'prior_proposed_decoder_results_inspected_or_used': None,
        'prior_dataset_scientific_analysis_performed': None,
        'used_in_other_manuscripts_or_projects': None,
        'independent_confirmation_qualified': False,
    }
    for key, expected in required.items():
        if type(declaration.get(key)) is not type(expected) or declaration.get(key) != expected:
            raise ValueError('uncertainty_record_mismatch:' + key)
        if key not in declaration:
            raise ValueError('uncertainty_record_field_missing:' + key)
    if not isinstance(declaration.get('author_name'), str) or not declaration['author_name'].strip():
        raise ValueError('author_identity_missing')
    if not isinstance(declaration.get('confirmation_record'), str) or '不确定' not in declaration['confirmation_record']:
        raise ValueError('actual_uncertainty_reply_not_recorded')
    stamp = declaration.get('reported_at_utc')
    if not isinstance(stamp, str) or datetime.fromisoformat(stamp.replace('Z', '+00:00')).tzinfo is None:
        raise ValueError('actual_uncertainty_reply_timestamp_missing')
    return {'sha256': sha_file(path), 'status': 'AUTHOR_REPORTED_UNCERTAIN',
            'prior_use_fact': 'unknown', 'independent_confirmation_qualified': False,
            'scope': 'Free CPU access/QC authorization does not turn uncertain prior exposure into no prior exposure.'}


def registration_files(author_path=AUTHOR_PATH):
    return [PLAN_PATH, Path(__file__).resolve(), author_path, MANIFEST_PATH] + [PREVIOUS / p for p in PINNED_HELPERS]


def read_public(url, limit):
    request = urllib.request.Request(url, headers={'User-Agent': 'Exposure-unconfirmed EEG access audit'})
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError('public_commit_byte_limit_exceeded')
        if response.status != 200:
            raise ValueError('public_commit_readback_not_http_200')
        return data


def registration_gate(commit, author_path=AUTHOR_PATH):
    if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('full_registration_commit_required')
    records = []
    for path in registration_files(author_path):
        if path.is_symlink() or not path.is_file():
            raise ValueError('registration_file_missing_or_symlinked')
        relative = path.resolve().relative_to(REPO.resolve()).as_posix()
        local = path.read_bytes()
        result = subprocess.run(['git', '-C', str(REPO), 'show', commit + ':' + relative], capture_output=True, check=False)
        if result.returncode or result.stdout != local:
            raise ValueError('local_bytes_differ_from_registered_commit:' + relative)
        url = 'https://raw.githubusercontent.com/' + REPOSITORY + '/' + commit + '/' + relative
        public = read_public(url, max(len(local), 1024))
        if public != local:
            raise ValueError('public_bytes_differ_from_registered_commit:' + relative)
        records.append({'path': relative, 'sha256': sha_bytes(local), 'bytes': len(local), 'public_http_200_readback_identical': True})
    return {'status': 'PASS_ACTUAL_GIT_AND_PUBLIC_BYTE_READBACK', 'repository': REPOSITORY,
            'commit_sha': commit, 'verified_at_utc': now(), 'files': records,
            'independent_confirmation_qualified': False, 'target_inference_authorized': False}


def verified_file(row, path):
    if path.is_symlink():
        raise ValueError('cached_file_symlink_rejected:' + row['path'])
    if not path.is_file() or path.stat().st_size != row['size'] or sha_file(path) != row['checksum']:
        raise ValueError('cached_file_size_or_sha256_mismatch:' + row['path'])


def ensure_raw(row, cache, pilot):
    path = cache / row['path']
    if path.exists() or path.is_symlink():
        verified_file(row, path)
        return {'status': 'verified_full_cohort_cache_reused', 'downloaded_now': 0, 'path': path}
    pilot_file = pilot / row['path']
    if pilot_file.exists() or pilot_file.is_symlink():
        verified_file(row, pilot_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Copy, rather than change the previously recorded bounded-cache inode.
        temporary = path.with_name(path.name + '.pilot-copy-' + uuid.uuid4().hex)
        shutil.copyfile(pilot_file, temporary)
        verified_file(row, temporary)
        if path.exists():
            temporary.rename(temporary.with_suffix(temporary.suffix + '.failed'))
            raise ValueError('destination_appeared_during_pilot_copy')
        temporary.rename(path)
        return {'status': 'verified_bounded_pilot_copied', 'downloaded_now': 0, 'path': path}
    path.parent.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    temporary = path.with_name(path.name + '.transfer-' + uuid.uuid4().hex)
    request = urllib.request.Request(row['bytes_url'], headers={'User-Agent': 'Exposure-unconfirmed EEG access audit'})
    try:
        with urllib.request.urlopen(request, timeout=90) as response, temporary.open('xb') as stream:
            if response.status != 200:
                raise ValueError('raw_transfer_http_status_not_200')
            for block in iter(lambda: response.read(1024 * 1024), b''):
                downloaded += len(block)
                if downloaded > row['size']:
                    raise ValueError('raw_transfer_exceeds_fixed_manifest_size')
                stream.write(block)
        verified_file(row, temporary)
        if path.exists():
            raise ValueError('destination_appeared_during_raw_transfer')
        temporary.rename(path)
        return {'status': 'downloaded_and_full_sha256_verified', 'downloaded_now': downloaded, 'path': path}
    except Exception:
        # Preserve partial bytes for diagnosis; never silently replace a corrupt
        # final cache or treat a transport failure as a scientific exclusion.
        if temporary.exists():
            temporary.rename(temporary.with_name(temporary.name + '.failed'))
        raise


def audit_one(row, path, header_module):
    verified_file(row, path)
    header = header_module.parse_header(path)
    events, prefix = header_module.annotation_and_prefix(path, header)
    names = [channel['label'] for channel in header['channels']]
    if len(names) != len(set(names)) or any(label not in names for label in COMMON19):
        raise ValueError('duplicate_or_missing_common19_channel')
    selected = [c for c in header['channels'] if c['label'] in COMMON19]
    if any(c['sampling_frequency_hz'] != 512 or c['unit'] not in ('uV', 'µV') for c in selected):
        raise ValueError('common19_sampling_or_units_mismatch')
    cues = [event for event in events if event['description'] in ('769', '770')]
    counts = collections.Counter(c['description'] for c in cues)
    if counts != {'769': 20, '770': 20} or min(c['onset'] for c in cues) <= 1:
        raise ValueError('cue_counts_or_precue_prefix_mismatch')
    match = PATH_PATTERN.fullmatch(row['path'])
    subject = int(match.group(1))
    return {
        'path': row['path'], 'cache_path': str(path), 'size_bytes': path.stat().st_size,
        'sha256': row['checksum'], 'subject': subject, 'run': match.group(2),
        'common19': COMMON19, 'sampling_hz': 512, 'physical_units': 'uV',
        'si_conversion_scale': 1e-6, 'header': header,
        'duration_seconds': header['duration_seconds'], 'record_shape_verified': True,
        'cue_counts': dict(counts), 'cue_metadata': cues,
        'first_cue_onset_seconds': min(c['onset'] for c in cues),
        'precue_format_prefix_verified': len(prefix) == 19,
        'provider_montage_flag_passes_only': subject not in (17, 41),
        'signal_only_qc_complete': False, 'original_gdf_equivalence_verified': False,
        'physical_channel_order_authentication_established': False,
        'independent_confirmation_qualified': False, 'evidence_class': CLASS,
    }


def run_one(row, cache, pilot, download, module):
    transfer = ensure_raw(row, cache, pilot) if download else {'path': cache / row['path'], 'status': 'existing_cache_audit_only', 'downloaded_now': 0}
    audit = audit_one(row, transfer['path'], module)
    audit.update(transport_status=transfer['status'], raw_bytes_downloaded_now=transfer['downloaded_now'])
    return audit


def perform_unlocked(rows, args, receipt):
    module = import_previous('scripts/check_dreyer_metadata.py', 'published_edf_header_parser')
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    # Validate every existing destination and pilot before any new transport.
    for row in rows:
        path = args.cache_dir / row['path']
        pilot = args.pilot_dir / row['path']
        if path.exists() or path.is_symlink():
            verified_file(row, path)
        elif args.download and (pilot.exists() or pilot.is_symlink()):
            verified_file(row, pilot)
    if args.download:
        needed = sum(r['size'] for r in rows if not (args.cache_dir / r['path']).is_file())
        if shutil.disk_usage(args.cache_dir).free < needed + 512 * 1024 ** 2:
            raise ValueError('insufficient_disk_for_fixed_acquisition_and_reserve')
    # Three active files at most. No worker processes, models or GPU resources.
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(run_one, row, args.cache_dir, args.pilot_dir, args.download, module): row for row in rows}
        for future in as_completed(futures):
            row = futures[future]
            if future.cancelled():
                receipt.setdefault('cancelled_unstarted_files', []).append(row['path'])
                save_json(args.receipt, receipt)
                continue
            try:
                audit = future.result()
                receipt['files'].append(audit)
                receipt['raw_bytes_downloaded_now'] += audit['raw_bytes_downloaded_now']
            except Exception as error:
                receipt['errors'].append({'path': row['path'], 'error_class': type(error).__name__, 'error_code': str(error)[:300]})
                # Cancel work not yet started. Running files are preserved and
                # their eventual receipts collected, with the operation failed.
                for pending in futures:
                    pending.cancel()
            receipt['files'].sort(key=lambda item: item['path'])
            receipt['completed_hash_header_event_files'] = len(receipt['files'])
            save_json(args.receipt, receipt)
            print(json.dumps({'stage': 'byte_header_event_audit', 'completed': len(receipt['files']),
                              'expected': 174, 'errors': len(receipt['errors']), 'evidence_class': CLASS}), flush=True)
    return len(receipt['files']) == 174 and not receipt['errors']


def perform(rows, args, receipt):
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    lock_path = args.cache_dir / '.exploratory_acquisition.lock'
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise ValueError('cache_acquisition_lock_exists_no_parallel_overwrite') from error
    try:
        with os.fdopen(descriptor, 'w') as lock:
            lock.write(json.dumps({'pid': os.getpid(), 'created_at_utc': now(),
                                   'purpose': 'Only one raw byte/header transport per cache at a time.'}) + '\n')
        return perform_unlocked(rows, args, receipt)
    finally:
        lock_path.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--download', action='store_true')
    mode.add_argument('--audit-cache', action='store_true')
    parser.add_argument('--registration-commit')
    parser.add_argument('--author-uncertainty-record', type=Path, default=AUTHOR_PATH)
    parser.add_argument('--cache-dir', type=Path, default=DEFAULT_CACHE)
    parser.add_argument('--pilot-dir', type=Path, default=DEFAULT_PILOT)
    parser.add_argument('--receipt', type=Path, default=ROOT / 'evidence/acquisition_dry_run.json')
    args = parser.parse_args(argv)
    receipt = {
        'schema_version': 1, 'started_at_utc': now(), 'evidence_class': CLASS,
        'status': 'PENDING', 'operation': 'download_byte_header_events' if args.download else 'audit_cache_byte_header_events' if args.audit_cache else 'metadata_only_dry_run',
        'independent_confirmation_qualified': False, 'source_fits_started_by_this_operation': 0,
        'target_fits': 0, 'target_predictions': 0, 'target_decoder_scores': 0,
        'task_features_or_performance_computed': False, 'full_signal_qc_complete': False,
        'original_gdf_equivalence_verified': False, 'model_training_authorized': False,
        'model_inference_authorized': False, 'paid_resources_started': False,
        'raw_bytes_downloaded_now': 0,
        'raw_bytes_counter_scope': 'successfully hash/header/event audited transfers; failed partial bytes are retained separately',
        'files': [], 'errors': [],
    }
    try:
        rows, plan = verified_plan()
        receipt.update(declared_acquisition_files=len(rows), declared_acquisition_bytes=sum(r['size'] for r in rows),
                       provider_manifest_sha256=MANIFEST_SHA, provider_dataset_id='nm000250', provider_version='v1.0.5',
                       source_edf_mirror_not_original_gdf=True, common19=COMMON19,
                       provider_excluded_subjects_primary=[17, 41], preliminary_primary_n_upper_bound=85,
                       cache_directory=str(args.cache_dir))
        if not (args.download or args.audit_cache):
            receipt['status'] = 'DRY_RUN_NO_TRANSFER_NO_MODEL_UNKNOWN_EXPOSURE'
        else:
            receipt['author_uncertainty_record'] = author_uncertainty_gate(args.author_uncertainty_record)
            receipt['registered_access_plan'] = registration_gate(args.registration_commit, args.author_uncertainty_record)
            save_json(ROOT / 'evidence/access_plan_public_readback.json', receipt['registered_access_plan'])
            receipt['status'] = 'RUNNING_BYTE_HEADER_EVENT_AUDIT_ONLY'
            save_json(args.receipt, receipt)
            success = perform(rows, args, receipt)
            receipt['all_174_hash_header_event_audited'] = success
            receipt['status'] = 'ALL_174_HASH_HEADER_EVENT_AUDITED_EXPLORATORY_ONLY_FULL_SIGNAL_QC_PENDING' if success else 'BLOCKED_BYTE_HEADER_EVENT_AUDIT_NO_MODEL_STARTED'
    except Exception as error:
        receipt['errors'].append({'error_class': type(error).__name__, 'error_code': str(error)[:300]})
        receipt['status'] = 'BLOCKED_ACCESS_OR_METADATA_GATE_NO_MODEL_STARTED'
    receipt['completed_at_utc'] = now()
    save_json(args.receipt, receipt)
    print(json.dumps({'status': receipt['status'], 'receipt': str(args.receipt), 'completed_files': len(receipt['files']),
                      'raw_bytes_downloaded_now': receipt['raw_bytes_downloaded_now'], 'target_predictions': 0,
                      'independent_confirmation_qualified': False}), flush=True)
    return 1 if receipt['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
