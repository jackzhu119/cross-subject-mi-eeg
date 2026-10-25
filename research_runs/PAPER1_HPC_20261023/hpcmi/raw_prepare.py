"""Offline, person-resumable reproduction of the archived eligible-v3 preprocessing."""
from __future__ import annotations
import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import sys
import threading
import time

from .data import _atomic_json, _file_sha, _stat, _utc, prepare
from .acquire import VENDOR, quick_raw_ready
from . import yang_privacy
sys.path.insert(0, str(VENDOR))
import numpy as np
import scipy
import p1_data

HPC_FILTER_BANK = Path(__file__).resolve().parents[1] / "config/hpc_filter_bank18.json"


def _identity():
    source = json.loads((VENDOR / 'VENDORED.json').read_text())
    identity = {r['path']: _file_sha(VENDOR / r['path']) for r in source['files']}
    if identity != {r['path']: r['sha256'] for r in source['files']}:
        raise ValueError('Vendored preprocessing code or fixed metadata changed')
    if np.__version__ != '2.2.6' or scipy.__version__ != '1.15.3':
        raise ValueError('Use the isolated CPU preprocessing environment: numpy 2.2.6, scipy 1.15.3')
    old_bank = json.loads((VENDOR / 'config/filter_bank18.json').read_text())
    new_bank = json.loads(HPC_FILTER_BANK.read_text())
    changed_keys = {'profile_id', 'numpy_version', 'scipy_version', 'parent_profile_sha256', 'runtime_amendment'}
    if ({k: v for k, v in old_bank.items() if k not in changed_keys}
            != {k: v for k, v in new_bank.items() if k not in changed_keys}
            or new_bank['parent_profile_sha256'] != _file_sha(VENDOR / 'config/filter_bank18.json')):
        raise ValueError('HPC numeric profile changes scientific preprocessing rules')
    p1_data.load_filter_bank(HPC_FILTER_BANK)
    return {'code': identity, 'numpy': np.__version__, 'scipy': scipy.__version__,
            'hpc_filter_bank_sha256': _file_sha(HPC_FILTER_BANK)}


def _raw_stats(root, dataset, person):
    manifest = json.loads((root / '_download_manifest.json').read_text())
    if dataset == 'bnci':
        selected = [r for r in manifest['files'] if Path(r['path']).name in ('A%02dT.mat' % person, 'A%02dE.mat' % person)]
    elif dataset == 'yang':
        selected = [r for r in manifest['files'] if '/sub-%03d/' % person in r['path'] and r['path'].endswith('.bdf')]
    else:
        selected = [r for r in manifest['files'] if '/sub-%02d/' % person in r['path']]
    expected = 6 if dataset == 'yang' else 2
    if len(selected) != expected:
        raise ValueError('Missing native input identity for person')
    return {r['path']: _stat(root / r['path']) for r in selected}


def raw_prepare(raw_dir, cache_dir, output):
    raw_dir, cache_dir, output = Path(raw_dir).resolve(), Path(cache_dir).resolve(), Path(output).resolve()
    identity = _identity()
    if not quick_raw_ready(raw_dir):
        raise ValueError('Offline raw files incomplete; finish FETCH_DATA.sh before submitting preprocessing')
    privacy_active = yang_privacy.is_active(raw_dir / 'yang')
    privacy_execution = yang_privacy.current_identity() if privacy_active else None
    # Implementation fixes are execution evidence, not a change in source bytes
    # or scientific policy. Keep them out of cache and import-config identity.
    privacy_identity = ({k: v for k, v in privacy_execution.items() if k != 'adapter_sha256'}
                        if privacy_active else None)
    execution_evidence = ({'yang_privacy_adapter_sha256': privacy_execution['adapter_sha256']}
                          if privacy_active else None)
    cache_folders = {'bnci': 'bnci', 'yang': 'yang-nemar-privacy-v1' if privacy_active else 'yang',
                     'dreyer': 'dreyer'}
    cache_dir.mkdir(parents=True, exist_ok=True)
    completed = 0
    state = {'stage': 'offline_raw_preprocessing', 'person': None, 'completed_people': 0, 'model_fits': 0}
    if privacy_active:
        state['input_source_profiles'] = {'yang': privacy_identity}
        state['execution_evidence'] = execution_evidence
    stop = threading.Event()
    def heartbeat():
        while not stop.wait(30):
            print(json.dumps({**state, 'updated_at_utc': _utc()}), flush=True)
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        for dataset in ('bnci', 'yang', 'dreyer'):
            root = raw_dir / dataset
            use_privacy = privacy_active and dataset == 'yang'
            person_identity = ({**identity, 'input_source_profile': privacy_identity}
                               if use_privacy else identity)
            context = yang_privacy.policy_context(p1_data) if use_privacy else nullcontext()
            with context:
                for person in p1_data.roster(dataset):
                    state['person'] = '%s/%03d' % (dataset, person)
                    path = cache_dir / cache_folders[dataset] / ('sub-%03d.npz' % person)
                    receipt_path = path.with_suffix('.hpc-preparation.json')
                    before = _raw_stats(root, dataset, person)
                    if receipt_path.is_file():
                        receipt = json.loads(receipt_path.read_text())
                        saved_identity = receipt['identity']
                        if use_privacy and isinstance(saved_identity.get('input_source_profile'), dict):
                            saved_identity = {**saved_identity, 'input_source_profile': {
                                k: v for k, v in saved_identity['input_source_profile'].items()
                                if k != 'adapter_sha256'}}
                        if saved_identity != person_identity or receipt['raw_stat'] != before or receipt['output_stat'] != _stat(path):
                            raise ValueError('Completed raw preprocessing input/runtime/output changed; retain prior output version')
                    else:
                        if path.exists():
                            # A crash after atomic NPZ publication but before receipt is recoverable.
                            audit = p1_data.verify_subject_npz(path, filter_bank_json=HPC_FILTER_BANK)
                            if (audit['numpy_version'] != np.__version__ or audit['scipy_version'] != scipy.__version__
                                    or audit['downloader_manifest_sha256'] != _file_sha(root / '_download_manifest.json')):
                                raise ValueError('Unreceipted cache belongs to different inputs/runtime; retained')
                        else:
                            p1_data.build_subject_npz(dataset, person, root, path, filter_bank_json=HPC_FILTER_BANK,
                                yang_unit_policy=p1_data.YANG_UNIT_CONVENTION if dataset == 'yang' else None)
                            audit = p1_data.verify_subject_npz(path, filter_bank_json=HPC_FILTER_BANK)
                        if before != _raw_stats(root, dataset, person):
                            raise ValueError('Native files changed during preparation')
                        with path.open('rb') as stream:
                            os.fsync(stream.fileno())
                        receipt = {'status': 'OFFLINE_PERSON_PREPROCESSED', 'identity': person_identity,
                            'raw_stat': before, 'output_stat': _stat(path), 'output_sha256': _file_sha(path),
                            'array_sha256': audit['X_sha256'], 'completed_at_utc': _utc(), 'model_fits': 0}
                        if use_privacy:
                            receipt['execution_evidence'] = execution_evidence
                        _atomic_json(receipt_path, receipt)
                    completed += 1
                    state['completed_people'] = completed
                    print(json.dumps({**state, 'updated_at_utc': _utc()}), flush=True)
                    _atomic_json(cache_dir / 'raw_preparation_status.json', {**state, 'updated_at_utc': _utc()})
        sources = {'schema_version': 1, 'preprocessing_id': 'eligible-v3-18ch-hpc-np226-sp1153-20261023',
                   'datasets': [{'dataset': d, 'role': 'external' if d == 'dreyer' else 'source',
                                 'directory': str(cache_dir / cache_folders[d]), 'pattern': 'sub-*.npz',
                                 'expected_subjects': n, 'expected_trials': t}
                                for d, n, t in [('bnci', 9, 2592), ('yang', 51, 30591), ('dreyer', 85, 6800)]]}
        if privacy_active:
            sources['input_source_profiles'] = {'yang': privacy_identity}
            sources['datasets'][1]['input_source_profile'] = privacy_identity
        sources_path = cache_dir / ('input_sources-nemar-privacy-v1.json' if privacy_active else 'input_sources.json')
        _atomic_json(sources_path, sources)
        manifest = prepare(sources_path, output)
        if privacy_active:
            manifest['input_source_profiles'] = {'yang': privacy_identity}
            manifest['execution_evidence'] = execution_evidence
            _atomic_json(output / 'manifest.json', manifest)
        completion = {'status': 'ALL_DATA_PREPARED', 'people': completed,
                      'fingerprint': manifest['fingerprint'], 'updated_at_utc': _utc(), 'model_fits': 0}
        if privacy_active:
            completion['input_source_profiles'] = {'yang': privacy_identity}
            completion['execution_evidence'] = execution_evidence
        _atomic_json(cache_dir / 'raw_preparation_status.json', completion)
        return manifest
    finally:
        stop.set()
        thread.join(timeout=1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', required=True, type=Path)
    parser.add_argument('--cache-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps({'stage': 'offline_raw_preparation_started', 'time': _utc()}), flush=True)
    raw_prepare(args.raw_dir, args.cache_dir, args.output)


if __name__ == '__main__':
    main()
