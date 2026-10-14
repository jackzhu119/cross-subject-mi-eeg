"""New-host source-only reconstruction; never creates a job, budget or training fit."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

from r2_only import digest, environment_client, frozen_entries, import_files, validate_mapping, regular_path

ROOT = Path(__file__).resolve().parents[3]
BASELINE = 'eae194514def23e5d1ec6cbb117d4f84fc6f067f'
V1 = ROOT / 'research_runs/REDESIGN_SOURCE_SELECTION_20261012'
AUDIT = ROOT / 'research_runs/REDESIGN_EXPLORATORY_20261013'


def verify_science():
    names = ['research_runs/REDESIGN_CLOUD_20261013/config/experiment.json',
             'research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts/core_source_inputs.py',
             'src/mi_eeg/data/q15_context.py', 'research_runs/Q8-E001/results/source_files.json',
             'research_runs/REDESIGN_EXPLORATORY_20261013/evidence/source_exact_input_fingerprints.csv',
             'research_runs/REDESIGN_EXPLORATORY_20261013/evidence/source_exact_input_fingerprints_receipt.json']
    result = {}
    for name in names:
        p = ROOT / name
        expected = subprocess.check_output(['git', '-C', str(ROOT), 'show', BASELINE + ':' + name])
        if p.is_symlink() or p.read_bytes() != expected:
            raise ValueError('historical_frozen_science_changed')
        result[name] = hashlib.sha256(expected).hexdigest()
    return result


def compare(source_dir):
    import numpy as np
    import scipy
    import pandas as pd
    if (np.__version__, scipy.__version__, pd.__version__) != ('2.3.5', '1.17.0', '2.2.3'):
        raise ValueError('exact_diagnostic_numerical_runtime_required')
    identity = verify_science()
    sys.path.insert(0, str(V1 / 'scripts'))
    import core_source_inputs as source
    expected = json.loads((AUDIT / 'evidence/source_exact_input_fingerprints_receipt.json').read_text())['source_file_provenance']
    config = json.loads((ROOT / 'research_runs/REDESIGN_CLOUD_20261013/config/experiment.json').read_text())
    arrays, rows, actual = source.load_source19(source_dir, config)
    with (AUDIT / 'evidence/source_exact_input_fingerprints.csv').open() as f:
        fingerprints = {r['source_sample_id']: r for r in csv.DictReader(f)}
    mismatches = {}
    for band, values in arrays.items():
        ids = [r['sample_id'] for r, value in zip(rows, values)
               if source.array_hash(value) != fingerprints[r['sample_id']][band + '_sha256']]
        mismatches[band] = {'count': len(ids), 'first_sample_ids': ids[:10]}
    coefficients = {}
    for band, sos in actual['preprocessing']['native_filter_sos_250_hz'].items():
        reference = np.asarray(expected['preprocessing']['native_filter_sos_250_hz'][band])
        coefficients[band] = {'identical': bool(np.array_equal(sos, reference)),
            'max_absolute_difference': float(np.max(np.abs(np.asarray(sos) - reference)))}
    checks = {key: actual[key] == expected[key] for key in
              ('array_hashes', 'source_labels_sha256', 'source_metadata_sha256', 'source_sample_ids_sha256')}
    return {'status': 'NEW_HOST_SOURCE_INPUTS_MATCH' if all(checks.values()) and not any(x['count'] for x in mismatches.values()) else 'NEW_HOST_SOURCE_INPUT_MISMATCH_BLOCKED',
        'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'checks': checks,
        'actual_array_hashes': actual['array_hashes'], 'expected_array_hashes': expected['array_hashes'],
        'per_trial_mismatches': mismatches, 'filter_coefficients': coefficients,
        'source_files_verified': actual['n_raw_files'], 'trials': len(rows),
        'numpy': np.__version__, 'scipy': scipy.__version__, 'pandas': pd.__version__,
        'python': platform.python_version(), 'machine': platform.machine(),
        'enabled_numpy_cpu_features': sorted(k for k, v in getattr(np._core._multiarray_umath, '__cpu_features__', {}).items() if v),
        'frozen_file_identities': identity, 'baseline_revision': BASELINE,
        'new_model_fits': 0, 'target_predictions': 0, 'old_failure_root_cause_established': False,
        'old_registration_recreated': False, 'training_authorization': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir', type=Path, required=True, help='New diagnostic cache; bnci/ lives below this directory')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--import-r2', action='store_true')
    p.add_argument('--mapping', type=Path)
    p.add_argument('--mapping-sha256')
    a = p.parse_args()
    if a.output.exists() or a.output.is_symlink() or a.output.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('new_report_outside_checkout_required')
    regular_path(a.output.parent, a.output.name)
    if a.data_dir.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('raw_cache_must_be_outside_checkout')
    # Verify exact numerical runtime and frozen files before raw import.
    import numpy, scipy, pandas
    if (numpy.__version__, scipy.__version__, pandas.__version__) != ('2.3.5', '1.17.0', '2.2.3'):
        raise ValueError('exact_diagnostic_numerical_runtime_required')
    verify_science()
    if a.import_r2:
        if not a.mapping or not re.fullmatch('[0-9a-f]{64}', a.mapping_sha256 or '') or a.mapping.is_symlink() or digest(a.mapping) != a.mapping_sha256:
            raise ValueError('reviewed_source_mapping_hash_required')
        mapping = json.loads(a.mapping.read_text())
        expected = [r for r in frozen_entries(ROOT) if r['path'].startswith('bnci/')]
        validate_mapping(mapping, expected)
        client, bucket = environment_client()
        import_files(a.data_dir, mapping, expected, client, bucket)
    report = compare(a.data_dir / 'bnci')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print(json.dumps({'status': report['status'], 'report': str(a.output), 'fits': 0}))
    if report['status'] != 'NEW_HOST_SOURCE_INPUTS_MATCH':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
