"""Explicit pre-resumption numerical amendment, never an element/hash repair.

The historical core implementation is retained byte-for-byte. This registered
adapter applies one fixed SOS initial-state profile to every band at both native
rates. Exact input hashes, not floating tolerances, remain authoritative.
"""
from collections import Counter
import csv
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np
import scipy
from scipy.signal import sosfilt
from scipy.signal._signaltools import _validate_pad

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / 'research_runs/REDESIGN_CLOUD_20261013'
POLICY = STUDY / 'config/numerical_execution_v1.json'
POLICY_SHA256 = '04f562ddddc4e5019e56240b980d6d9c2d78645860857a5ab0d9746e788ae476'
LEGACY_PATH = ROOT / 'research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts/core_source_inputs.py'
LEGACY_SHA256 = '03f47bceb3998e407a28e7da56da4875b5d3e1e38746d196739be7262be7cff5'
sys.path.insert(0, str(LEGACY_PATH.parent))
import core_source_inputs as legacy

array_hash = legacy.array_hash
canonical_hash = legacy.canonical_hash
file_hash = legacy.file_hash
check_processing = legacy.check_processing
ordered_channels19 = legacy.ordered_channels19
CHANNELS19 = legacy.CHANNELS19
BANDS = legacy.BANDS
SOURCE_PROVENANCE = legacy.SOURCE_PROVENANCE


def checked_policy():
    payload = POLICY.read_bytes()
    if POLICY.is_symlink() or hashlib.sha256(payload).hexdigest() != POLICY_SHA256:
        raise ValueError('explicit_numerical_policy_changed')
    if LEGACY_PATH.is_symlink() or file_hash(LEGACY_PATH) != LEGACY_SHA256:
        raise ValueError('historical_input_implementation_changed')
    if Path(legacy.__file__).resolve() != LEGACY_PATH.resolve():
        raise ValueError('historical_loader_module_shadowed')
    if (np.__version__, scipy.__version__) != ('2.3.5', '1.17.0'):
        raise ValueError('explicit_numerics_runtime_changed')
    if os.environ.get('OPENBLAS_CORETYPE') or os.environ.get('NPY_DISABLE_CPU_FEATURES'):
        raise ValueError('unregistered_numeric_override')
    return json.loads(payload)


def numerical_identity():
    policy = checked_policy()
    return {'policy_id': policy['policy_id'], 'policy_sha256': POLICY_SHA256,
            'execution_module_sha256': file_hash(__file__),
            'historical_loader_sha256': LEGACY_SHA256,
            'historical_generation_BLAS_identity_established': False,
            'state_application': 'every_band_every_trial_source_and_target'}


def coefficients(sfreq, band):
    policy = checked_policy()
    if isinstance(sfreq, (bool, np.bool_)) or sfreq not in (250, 512) or band not in BANDS:
        raise ValueError('unregistered_native_rate_or_band')
    entry = policy['rates'][str(int(sfreq))][band]
    sos = np.array([[float.fromhex(x) for x in row] for row in entry['sos_hex']], dtype=np.float64)
    zi = np.array([[float.fromhex(x) for x in row] for row in entry['zi_hex']], dtype=np.float64)
    generated = legacy.butter(4, BANDS[band], btype='bandpass', fs=sfreq, output='sos')
    if (array_hash(sos) != entry['sos_sha256'] or array_hash(zi) != entry['zi_sha256']
            or array_hash(generated) != entry['sos_sha256']):
        raise ValueError('explicit_filter_coefficient_identity_changed')
    return sos, zi


def explicit_filter(context, sos, zi):
    """SciPy 1.17 odd-pad27 equations with a registered binary64 state."""
    edge, extended = _validate_pad('odd', 27, context, -1, ntaps=9)
    state = zi.reshape(sos.shape[0], 1, 2)
    filtered, _ = sosfilt(sos, extended, axis=-1, zi=state * extended[..., :1])
    filtered, _ = sosfilt(sos, filtered[..., ::-1], axis=-1, zi=state * filtered[..., -1:])
    filtered = filtered[..., ::-1]
    return filtered[..., edge:-edge]


def input_contract(config):
    return {**legacy.input_contract(config), 'loader_sha256': file_hash(__file__),
            'historical_loader_sha256': LEGACY_SHA256,
            'numerical_execution': numerical_identity()}


def verify_source_inputs(arrays, rows, audit):
    folder = ROOT / 'research_runs/REDESIGN_EXPLORATORY_20261013/evidence'
    receipt = folder / 'source_exact_input_fingerprints_receipt.json'
    if receipt.is_symlink() or file_hash(receipt) != '66c5aa472809cf29fe68b7b56401c4f0aa4b4f577156425a1f4e1fc20d45d8dd':
        raise ValueError('frozen_source_reference_receipt_changed')
    reference = json.loads(receipt.read_text())
    path = folder / 'source_exact_input_fingerprints.csv'
    if path.is_symlink() or file_hash(path) != reference['reference_sha256']:
        raise ValueError('frozen_source_trial_reference_changed')
    expected = reference['source_file_provenance']
    for key in ('array_hashes', 'source_labels_sha256', 'source_metadata_sha256', 'source_sample_ids_sha256'):
        if audit[key] != expected[key]:
            raise ValueError('frozen_source_input_changed:' + key)
    with path.open(newline='') as stream:
        fingerprints = list(csv.DictReader(stream))
    if len(rows) != 2592 or len(fingerprints) != 2592:
        raise ValueError('full_source_reference_inventory_required')
    for i, (row, frozen) in enumerate(zip(rows, fingerprints)):
        if row['sample_id'] != frozen['source_sample_id']:
            raise ValueError('source_trial_order_changed')
        for band in BANDS:
            if array_hash(arrays[band][i]) != frozen[band + '_sha256']:
                raise ValueError('frozen_source_trial_changed:' + band + ':' + row['sample_id'])
    return True


def transform_context19(signal_channels_time, sfreq, cue_zero_based, config, bounds=None):
    check_processing(config)
    # Validate numerical policy before reading/transforming a trial.
    states = {band: coefficients(sfreq, band) for band in BANDS}
    signal = np.asarray(signal_channels_time)
    if signal.ndim != 2 or signal.shape[0] != 19 or not np.issubdtype(signal.dtype, np.number) or np.iscomplexobj(signal):
        raise ValueError('expected_real_numeric_19_channel_signal')
    if isinstance(cue_zero_based, (bool, np.bool_)) or not isinstance(cue_zero_based, (int, np.integer)) or cue_zero_based < 0:
        raise ValueError('audited_zero_based_cue_required')
    offsets = np.array([-1.5, 4.5]) * sfreq
    if not np.isclose(offsets, np.round(offsets), rtol=0, atol=1e-8).all():
        raise ValueError('context_not_on_native_grid')
    start, stop = int(cue_zero_based) + np.round(offsets).astype(np.int64)
    lower, upper = (0, signal.shape[1]) if bounds is None else bounds
    if any(isinstance(x, (bool, np.bool_)) or not isinstance(x, (int, np.integer)) for x in (lower, upper)):
        raise ValueError('integer_physical_run_bounds_required')
    if lower < 0 or upper > signal.shape[1] or lower >= upper or start < lower or stop > upper:
        raise ValueError('complete_trial_context_required')
    context = np.array(signal[:, start:stop], dtype=np.float64, copy=True)
    if not np.isfinite(context).all():
        raise ValueError('nonfinite_trial_context')
    context -= context.mean(axis=0, keepdims=True)
    ratio = Fraction(160 / float(sfreq)).limit_denominator(100000)
    arrays = {}
    for band, (sos, zi) in states.items():
        filtered = explicit_filter(context, sos, zi)
        common = legacy.resample_poly(filtered, ratio.numerator, ratio.denominator, axis=-1,
                                      window=('kaiser', 5.0), padtype='constant', cval=0.0)
        if common.shape != (19, 960):
            raise ValueError('complete_resampled_context_required')
        output = np.ascontiguousarray(common[:, 320:640], dtype=np.float32)
        if output.shape != (19, 320) or not np.isfinite(output).all():
            raise ValueError('invalid_formal_input')
        arrays[band] = output
    return arrays


def load_source19(data_dir, config):
    """Read/re-extract original source only after the caller's execution gates."""
    check_processing(config)
    if config.get("source_subjects") != list(range(1, 10)) or config.get("source_population") != "both_sessions_all_binary_hand_trials_include_provider_flags":
        raise ValueError("Source population changed")
    sys.path.insert(0, str(ROOT / "src"))
    from mi_eeg.data.q15_context import BNCI_CHANNELS, _validated_bnci_runs, verify_bnci_originals
    originals = verify_bnci_originals(Path(data_dir), SOURCE_PROVENANCE)
    chunks = {band: [] for band in BANDS}
    rows, runs, files = [], [], []
    for subject in range(1, 10):
        for suffix, session in (("T", "0train"), ("E", "1test")):
            path = originals[f"A{subject:02d}{suffix}.mat"]
            files.append({"filename": path.name, "bytes": path.stat().st_size, "sha256": file_hash(path)})
            for run_index, run in enumerate(_validated_bnci_runs(path)):
                signal = ordered_channels19(run["X"][:, :22].T, BNCI_CHANNELS)
                if (np.ptp(signal, axis=1) == 0).any():
                    raise ValueError("A required source channel is flat across its real run")
                kept, flagged = 0, 0
                for trial_index, (start, label, flag) in enumerate(zip(run["trial"], run["y"], run["artifacts"]), 1):
                    if int(label) not in (1, 2):
                        continue
                    cue = int(start) - 1 + 500
                    transformed = transform_context19(signal, run["fs"], cue, config, bounds=(0, signal.shape[1]))
                    for band, epoch in transformed.items():
                        chunks[band].append(epoch)
                    rows.append({"sample_id": f"s{subject:02d}_{session}_r{run_index}_t{trial_index:02d}",
                                 "subject": subject, "session": session, "run": run_index, "trial": trial_index,
                                 "label": int(label), "label_index": int(label) - 1, "event_sample": int(start) - 1,
                                 "cue_sample": cue, "artifact_flagged": bool(flag), "source_filename": path.name})
                    kept += 1
                    flagged += int(bool(flag))
                runs.append({"subject": subject, "session": session, "run": run_index, "kept_binary_trials": kept,
                             "flagged_binary_trials_included": flagged, "technical_exclusions": 0,
                             "native_rate_hz": run["fs"], "output_channels": list(CHANNELS19)})
    arrays = {band: np.stack(epochs) for band, epochs in chunks.items()}
    if len(rows) != 2592 or len({row["sample_id"] for row in rows}) != 2592 or len(runs) != 108:
        raise ValueError("Incomplete source trial/run inventory")
    counts = Counter((row["subject"], row["session"], row["label"]) for row in rows)
    if len(counts) != 36 or set(counts.values()) != {72}:
        raise ValueError("Source participant/session/hand counts differ from fixed population")
    for value in arrays.values():
        if value.shape != (2592, 19, 320) or value.dtype != np.float32 or not np.isfinite(value).all():
            raise ValueError("Source19 complete input audit failed")
    audit = {"status": "PASS_SOURCE19_INPUTS_ONLY", "raw_files_verified": files, "n_raw_files": 18,
             "source_provenance_sha256": file_hash(SOURCE_PROVENANCE), "n_runs": 108, "n_binary_trials": 2592,
             "source_sample_ids_sha256": canonical_hash([row["sample_id"] for row in rows]),
             "source_metadata_sha256": canonical_hash(rows), "array_hashes": {band: array_hash(value) for band, value in arrays.items()},
             "source_labels_sha256": array_hash(np.array([row["label_index"] for row in rows], dtype=np.int64)),
             "source_artifact_flags_included": sum(row["artifact_flagged"] for row in rows),
             "technical_exclusions": [], "run_audit": runs, "preprocessing": input_contract(config),
             "new_model_fits": 0, "target_eeg_read": False, "target_fits": 0, "target_predictions_computed": False}
    verify_source_inputs(arrays, rows, audit)
    return arrays, rows, audit
