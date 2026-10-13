"""Deterministic new 19-channel source inputs; never truncate Q15 tensors.

This module does not load target data, fit a transform, fit a model or download
EEG. The real-data caller must first verify the live-GPU/authorization/public
protocol gates. Native BNCI values follow the recorded microvolt convention;
we do not claim to have re-established the original device calibration.
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import scipy
from scipy.signal import butter, resample_poly, sosfiltfilt

STUDY = Path(__file__).resolve().parents[1]
ROOT = STUDY.parents[1]
SOURCE_PROVENANCE = ROOT / "research_runs/Q8-E001/results/source_files.json"
CHANNELS19 = ("Fz", "FC3", "FC1", "FCz", "FC2", "FC4", "C5", "C3", "C1", "Cz", "C2", "C4", "C6",
              "CP3", "CP1", "CPz", "CP2", "CP4", "Pz")
BANDS = {"broad": [8, 30], "mu": [8, 13], "beta": [13, 30]}


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for piece in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(piece)
    return digest.hexdigest()


def array_hash(value):
    value = np.ascontiguousarray(value)
    digest = hashlib.sha256()
    digest.update(json.dumps({"shape": list(value.shape), "dtype": value.dtype.str}, sort_keys=True).encode())
    digest.update(memoryview(value).cast("B"))
    return digest.hexdigest()


def check_processing(config):
    expected = {
        "channels": list(CHANNELS19), "common_sampling_hz": 160,
        "context_half_open_s": [-1.5, 4.5], "epoch_half_open_s": [0.5, 2.5],
        "n_times": 320, "reference": "common_average_actual19", "bands_hz": BANDS,
        "filter": {"family": "Butterworth", "prototype_order": 4, "phase": "zero",
                   "scope": "each_native_trial_context", "representation": "SOS", "padtype": "odd",
                   "padlen_native_samples": 27},
        "resampling": {"method": "scipy.signal.resample_poly", "window": ["kaiser", 5.0], "padding": "constant_zero"},
        "target_fitted_transforms": False,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"Core input contract differs from fixed design: {key}")
    return config


def ordered_channels19(values, channel_names):
    names = tuple(channel_names)
    values = np.asarray(values)
    if values.ndim != 2 or values.shape[0] != len(names) or len(names) != len(set(names)):
        raise ValueError("Real native channel names must be unique and match rows")
    if not set(CHANNELS19).issubset(names):
        raise ValueError("A genuine required channel is absent; interpolation is forbidden")
    return values[[names.index(name) for name in CHANNELS19]]


def transform_context19(signal_channels_time, sfreq, cue_zero_based, config, bounds=None):
    """Input genuine ordered channels in µV; CAR19→native filter→resample→crop.

    This pure numerical function is usable in source-only synthetic tests. A
    target adapter must independently qualify headers/events/run identity and
    convert declared units before calling it; this function authenticates no
    dataset and estimates no distributional transform.
    """
    check_processing(config)
    signal = np.asarray(signal_channels_time)
    if signal.ndim != 2 or signal.shape[0] != 19 or not np.issubdtype(signal.dtype, np.number) or np.iscomplexobj(signal):
        raise ValueError("Expected real numeric native [19 channels,time] in declared microvolts")
    if not np.isfinite(sfreq) or sfreq <= 60:
        raise ValueError("Native sampling rate cannot represent fixed bands")
    if isinstance(cue_zero_based, (bool, np.bool_)) or not isinstance(cue_zero_based, (int, np.integer)) or cue_zero_based < 0:
        raise ValueError("Cue must be an audited zero-based native sample")
    offsets = np.array([-1.5, 4.5]) * sfreq
    if not np.isclose(offsets, np.round(offsets), rtol=0, atol=1e-8).all():
        raise ValueError("Fixed context does not lie on native sampling grid")
    start, stop = int(cue_zero_based) + np.round(offsets).astype(np.int64)
    lower, upper = (0, signal.shape[1]) if bounds is None else bounds
    if any(isinstance(x, (bool, np.bool_)) or not isinstance(x, (int, np.integer)) for x in (lower, upper)):
        raise ValueError("Native physical run bounds must be integer samples")
    if lower < 0 or upper > signal.shape[1] or lower >= upper or start < lower or stop > upper:
        raise ValueError("Complete fixed six-second context is absent from real run")
    context = np.array(signal[:, start:stop], dtype=np.float64, copy=True)
    if not np.isfinite(context).all():
        raise ValueError("Retained native trial context is nonfinite")
    context -= context.mean(axis=0, keepdims=True)
    ratio = Fraction(160 / float(sfreq)).limit_denominator(100000)
    if not np.isclose(ratio.numerator / ratio.denominator, 160 / sfreq, rtol=0, atol=1e-12):
        raise ValueError("Unsupported native/common rate ratio")
    arrays = {}
    for band, limits in BANDS.items():
        sos = butter(4, limits, btype="bandpass", fs=sfreq, output="sos")
        filtered = sosfiltfilt(sos, context, axis=-1, padtype="odd", padlen=27)
        common = resample_poly(filtered, ratio.numerator, ratio.denominator, axis=-1,
                               window=("kaiser", 5.0), padtype="constant", cval=0.0)
        if common.shape != (19, 960):
            raise ValueError("Resampled six-second context is not exactly [19,960]")
        output = np.ascontiguousarray(common[:, 320:640], dtype=np.float32)
        if output.shape != (19, 320) or not np.isfinite(output).all():
            raise ValueError("Invalid core source input")
        arrays[band] = output
    return arrays


def input_contract(config):
    check_processing(config)
    return {"channels": list(CHANNELS19), "reference": "common_average_actual19",
            "native_input_unit_policy": "BNCI native numeric microvolt convention; device calibration not independently re-established",
            "output_units": "microvolts", "output_dtype": "float32", "n_times": 320, "rate_hz": 160,
            "context_half_open_s": [-1.5, 4.5], "epoch_half_open_s": [0.5, 2.5],
            "context_common_samples": 960, "crop_common_half_open": [320, 640],
            "native_filter_sos_250_hz": {name: butter(4, band, btype="bandpass", fs=250, output="sos").tolist()
                                         for name, band in BANDS.items()},
            "filter": config["filter"], "resampling": config["resampling"],
            "numpy_version": np.__version__, "scipy_version": scipy.__version__,
            "fitted_normalization": False, "target_fits": 0, "baseline_correction": False,
            "loader_sha256": file_hash(__file__), "config_canonical_sha256": canonical_hash(config)}


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
    return arrays, rows, audit
