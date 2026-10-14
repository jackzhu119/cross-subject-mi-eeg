"""Input diagnostic fixtures: no real EEG models or predictions."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

path = Path(__file__).resolve().parents[1] / 'DIAGNOSE_SOURCE_INPUTS.py'
spec = importlib.util.spec_from_file_location('source_diagnostic', path)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def setup_job(tmp_path, fits=0, predictions=False):
    revision, job_id = 'a' * 40, 'fixture-job'
    root = tmp_path / ('code-' + revision)
    job = root / 'research_runs/REDESIGN_CLOUD_20261013/jobs' / job_id
    put(tmp_path / 'execution_registration.json', {'code_revision': revision, 'job_id': job_id})
    put(job / 'job_status.json', {'stage': 'FAILED_OR_BLOCKED_MANUAL_REVIEW_REQUIRED',
        'actual_neural_fits_started': fits, 'target_predictions_computed': predictions})
    return root, job


@pytest.mark.parametrize('fits,predictions', [(1, False), (False, False), (0, True), (None, False)])
def test_observed_prefit_status_required(tmp_path, fits, predictions):
    setup_job(tmp_path, fits, predictions)
    with pytest.raises(ValueError, match='prefit_failure'):
        probe.registered_job(tmp_path)


def test_registration_path_traversal_rejected(tmp_path):
    put(tmp_path / 'execution_registration.json', {'code_revision': 'a' * 40, 'job_id': '../other'})
    with pytest.raises(ValueError, match='invalid_registration'):
        probe.registered_job(tmp_path)


def test_active_job_rejected(tmp_path):
    _, job = setup_job(tmp_path)
    state = probe.read(job / 'job_status.json')
    state['stage'] = 'source_only_training_exploratory'
    put(job / 'job_status.json', state)
    with pytest.raises(ValueError, match='blocked_job'):
        probe.registered_job(tmp_path)


def test_mismatch_report_does_not_modify_frozen_or_job_files(tmp_path, monkeypatch):
    import hashlib
    root, job = setup_job(tmp_path)
    put(job / 'launch_record.json', {'data_dir': str(tmp_path / 'data')})
    put(tmp_path / 'budget_origin.json', {'started_at_utc': '2026-10-14T07:00:00+00:00'})
    cloud = root / 'research_runs/REDESIGN_CLOUD_20261013'
    put(cloud / 'config/experiment.json', {})
    audit = root / 'research_runs/REDESIGN_EXPLORATORY_20261013/evidence'
    def digest(value):
        return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()
    frozen = np.zeros((2, 2, 3), dtype=np.float32)
    current = frozen.copy()
    current[1, 0, 0] = 1
    arrays = {'broad': current}
    expected = {'array_hashes': {'broad': digest(frozen)}, 'source_metadata_sha256': 'metadata',
        'source_labels_sha256': 'labels', 'source_sample_ids_sha256': 'ids',
        'preprocessing': {'native_filter_sos_250_hz': {'broad': [[1., 2.]]}}}
    put(audit / 'source_exact_input_fingerprints_receipt.json', {'source_file_provenance': expected})
    (audit / 'source_exact_input_fingerprints.csv').write_text(
        'source_sample_id,broad_sha256\ns01,' + digest(frozen[0]) + '\ns02,' + digest(frozen[1]) + '\n')
    actual = {**expected, 'array_hashes': {'broad': digest(current)}, 'n_raw_files': 18}
    monkeypatch.setitem(sys.modules, 'core_source_inputs', SimpleNamespace(
        load_source19=lambda *args: (arrays, [{'sample_id': 's01'}, {'sample_id': 's02'}], actual),
        array_hash=digest))
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    probe.observe(tmp_path)
    report = probe.read(tmp_path / 'diagnostics/fixture-job-source-input-diagnostic.json')
    assert report['array_hashes_match'] is False
    assert report['per_trial_hash_comparison']['broad'] == {
        'mismatched_trials': 1, 'first_mismatched_sample_ids': ['s02']}
    assert report['filter_coefficient_comparison']['broad']['identical'] is True
    assert report['new_model_fits'] == report['new_target_predictions'] == 0
    assert all(p.read_bytes() == content for p, content in before.items())
