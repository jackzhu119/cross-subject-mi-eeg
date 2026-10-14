"""Read-only scientific inputs probe; no fits, predictions, recovery or credentials.

Use the registered checkout and its existing exact numerical runtime. Only a new
diagnostic JSON is written, outside the checkout; frozen gates remain unchanged.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys


def read(path):
    return json.loads(Path(path).read_text())


def registered_job(base):
    record = read(base / 'execution_registration.json')
    revision, job_id = record['code_revision'], record['job_id']
    if not re.fullmatch(r'[0-9a-f]{40}', revision) or not re.fullmatch(r'[A-Za-z0-9_-]+', job_id):
        raise ValueError('invalid_registration')
    root = base / ('code-' + revision)
    job = root / 'research_runs/REDESIGN_CLOUD_20261013/jobs' / job_id
    status = read(job / 'job_status.json')
    fits = status.get('actual_neural_fits_started')
    if type(fits) is not int or fits != 0 or status.get('target_predictions_computed') is not False:
        raise ValueError('probe_requires_observed_prefit_failure')
    if status.get('stage') != 'FAILED_OR_BLOCKED_MANUAL_REVIEW_REQUIRED':
        raise ValueError('probe_requires_blocked_job')
    return root, job, record


def observe(base):
    import csv
    import numpy as np
    import scipy
    if np.__version__ != '2.3.5' or scipy.__version__ != '1.17.0':
        raise ValueError('exact_numerical_runtime_required')
    root, job, record = registered_job(base)
    scripts = root / 'research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts'
    sys.path.insert(0, str(scripts))
    import core_source_inputs as source
    audit_dir = root / 'research_runs/REDESIGN_EXPLORATORY_20261013'
    expected = read(audit_dir / 'evidence/source_exact_input_fingerprints_receipt.json')['source_file_provenance']
    config = read(root / 'research_runs/REDESIGN_CLOUD_20261013/config/experiment.json')
    data = Path(read(job / 'launch_record.json')['data_dir']) / 'bnci'
    arrays, rows, actual = source.load_source19(data, config)
    with (audit_dir / 'evidence/source_exact_input_fingerprints.csv').open(newline='') as stream:
        fingerprints = {r['source_sample_id']: r for r in csv.DictReader(stream)}
    mismatch = {}
    for band, values in arrays.items():
        ids = [row['sample_id'] for row, value in zip(rows, values)
               if source.array_hash(value) != fingerprints[row['sample_id']][band + '_sha256']]
        mismatch[band] = {'mismatched_trials': len(ids), 'first_mismatched_sample_ids': ids[:5]}
    features = getattr(np._core._multiarray_umath, '__cpu_features__', {})
    coefficient_difference = {}
    for band, actual_sos in actual['preprocessing']['native_filter_sos_250_hz'].items():
        reference = np.asarray(expected['preprocessing']['native_filter_sos_250_hz'][band])
        current = np.asarray(actual_sos)
        coefficient_difference[band] = {'identical': bool(np.array_equal(current, reference)),
                                        'max_absolute_difference': float(np.max(np.abs(current - reference)))}
    report = {'status': 'SOURCE_INPUT_DIAGNOSTIC_ONLY_NOT_RECOVERY',
              'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'job_id': job.name, 'code_revision': record['code_revision'],
              'numpy_version': np.__version__, 'scipy_version': scipy.__version__,
              'enabled_numpy_cpu_features': sorted(k for k, v in features.items() if v),
              'actual_array_hashes': actual['array_hashes'], 'frozen_array_hashes': expected['array_hashes'],
              'array_hashes_match': actual['array_hashes'] == expected['array_hashes'],
              'metadata_match': actual['source_metadata_sha256'] == expected['source_metadata_sha256'],
              'labels_match': actual['source_labels_sha256'] == expected['source_labels_sha256'],
              'sample_ids_match': actual['source_sample_ids_sha256'] == expected['source_sample_ids_sha256'],
              'raw_files_verified': actual['n_raw_files'], 'trials': len(rows),
              'per_trial_hash_comparison': mismatch, 'filter_coefficient_comparison': coefficient_difference,
              'new_model_fits': 0, 'new_target_predictions': 0,
              'frozen_files_modified': False, 'registration_modified': False, 'budget_origin_modified': False}
    folder = base / 'diagnostics'
    folder.mkdir(exist_ok=True)
    output = folder / (job.name + '-source-input-diagnostic.json')
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)
    print('Diagnostic saved:', output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    default = '/workspace/mi-eeg-cloud' if Path('/workspace').is_dir() else str(Path.home() / 'mi-eeg-cloud')
    parser.add_argument('--work-dir', type=Path, default=Path(default))
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    base = args.work_dir.expanduser().resolve()
    registered_job(base)
    if args.worker:
        observe(base)
        return
    for python in sorted(base.glob('runtime-*/bin/python')):
        result = subprocess.run([str(python), '-c',
            'import numpy,scipy;assert numpy.__version__=="2.3.5" and scipy.__version__=="1.17.0"'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            raise SystemExit(subprocess.call([str(python), str(Path(__file__).resolve()),
                                             '--work-dir', str(base), '--worker']))
    raise SystemExit('No existing exact numerical runtime found; nothing installed or started.')


if __name__ == '__main__':
    main()
