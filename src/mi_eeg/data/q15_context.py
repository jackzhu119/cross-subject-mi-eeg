"""Prospectively fixed Q15 trial-context preprocessing, with no fitted transform.

Every dataset uses the same function. Unscaled native values follow a declared
microvolt analysis convention; external export calibration is unverified.
Channel selection happens before common-average referencing. Each trial is processed
in isolation, so class-concatenated Cho arrays are never filtered across their
artificial trial boundaries. This module has no network or dataset downloader.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy.io import loadmat
from scipy.signal import butter, resample_poly, sosfiltfilt

BNCI_CHANNELS = (
    "Fz", "FC3", "FC1", "FCz", "FC2", "FC4", "C5", "C3", "C1", "Cz", "C2",
    "C4", "C6", "CP3", "CP1", "CPz", "CP2", "CP4", "P1", "Pz", "P2", "POz",
)
CHANNELS = tuple(name for name in BNCI_CHANNELS if name != "FCz")
BANDS = {"broad": (8.0, 30.0), "mu": (8.0, 13.0), "beta": (13.0, 30.0)}
CONTEXT_WINDOW = (-1.5, 4.5)
EPOCH_WINDOW = (0.5, 2.5)
COMMON_RATE = 160
N_TIMES = 320
FILTER_PADLEN = 27
SOURCE_PROVENANCE = Path(__file__).resolve().parents[3] / "research_runs/Q8-E001/results/source_files.json"


def preprocessing_contract(execution_path: Path | None = None, protocol_path: Path | None = None) -> dict:
    """Canonical source/target input contract; the prospective amendment is explicit."""
    root = Path(__file__).resolve().parents[3]
    execution_path = execution_path or root / "research_runs/Q15-EXECUTION-20261003/EXECUTION_CONTRACT.json"
    protocol_path = protocol_path or root / "research_runs/PAPER_RELEASE_20260927/Q15_CONTRACT.json"
    execution = json.loads(Path(execution_path).read_text(encoding="utf-8"))
    if execution.get("schema_version") != 1 or execution.get("target_fits") != 0:
        raise AssertionError("Prospective execution identity or zero-target-fit policy changed")
    arm = json.loads(Path(protocol_path).read_text(encoding="utf-8"))["new_source_arm"]
    transform = execution["shared_transform"]
    required = {
        "context_relative_s": [-1.5, 4.5], "cue_window_s": [0.5, 2.5],
        "common_rate_hz": 160, "channels": list(CHANNELS), "reference": "common_average_21",
        "bands": {band: list(limits) for band, limits in BANDS.items()}, "output_unit": "uV",
        "dtype": "float32", "artifact_policy": "include_all",
        "target_fitted_normalization": False, "baseline_correction": False,
    }
    if any(transform.get(key) != value for key, value in required.items()):
        raise AssertionError("Prospective execution contract differs from the implemented transform")
    if transform.get("filter") != {"order": 4, "ftype": "butter", "phase": "zero", "scope": "each_real_retained_trial_context", "padlen": 27}:
        raise AssertionError("Prospective context filtering contract changed")
    if transform.get("analysis_input_unit_convention") != "native_numeric_as_microvolts" or transform.get("native_export_units_verified") is not False:
        raise AssertionError("External native voltage calibration must remain explicitly unverified")
    if arm["channels"] != list(CHANNELS) or arm["frequency_bands_hz"] != required["bands"]:
        raise AssertionError("Original Q15 protocol input channels or bands changed")
    return {
        "channels": list(CHANNELS), "sampling_rate_hz": 160, "n_times": 320,
        "cue_window_s_half_open": [0.5, 2.5], "bands_hz": arm["frequency_bands_hz"],
        "filter": transform["filter"], "unit": "uV", "dtype": "float32",
        "analysis_input_unit_convention": "native_numeric_as_microvolts",
        "native_microvolt_analysis_convention": True,
        "native_export_units_verified": False, "calibration_verified": False,
        "artifact_policy": "include_all", "label_map": {"left_hand": 1, "right_hand": 2},
        "target_normalization": False, "target_alignment": False,
        "target_channel_interpolation": False, "target_fits": 0,
        "shared_transform": transform,
        "numerical_implementation": numerical_implementation(),
    }


def numerical_implementation() -> dict:
    """Record coefficients and library versions used by the immutable gate."""
    return {
        "numpy_version": np.__version__, "scipy_version": scipy.__version__,
        "filter_representation": "SOS", "prototype_order": 4,
        "bandpass_order": 8, "sos_sections": 4,
        "filter_padtype": "odd", "filter_padlen_native_samples": FILTER_PADLEN,
        "resampling": {
            "implementation": "scipy.signal.resample_poly", "window": ["kaiser", 5.0],
            "padtype": "constant", "cval": 0.0,
            "native_to_common_ratios": {"250": [16, 25], "512": [5, 16], "1000": [4, 25]},
            "context_samples": 960, "crop_half_open": [320, 640],
        },
        "native_filter_sos": {
            str(rate): {
                band: butter(4, limits, btype="bandpass", fs=rate, output="sos").tolist()
                for band, limits in BANDS.items()
            }
            for rate in (250, 512, 1000)
        },
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _grid(value: float, name: str) -> int:
    if not np.isfinite(value) or not np.isclose(value, round(value), rtol=0, atol=1e-8):
        raise ValueError(f"{name} must lie on the native sampling grid")
    return round(value)


def select_channels(signal: np.ndarray, channel_names: list[str] | tuple[str, ...]) -> np.ndarray:
    """Return the frozen 21-channel order without interpolation or imputation."""
    values = np.asarray(signal)
    names = tuple(channel_names)
    if values.ndim != 2 or values.shape[0] != len(names):
        raise ValueError("Signal must have one row per named channel")
    if len(names) != len(set(names)) or not set(CHANNELS).issubset(names):
        raise ValueError("Missing or duplicate canonical EEG channel names")
    return values[[names.index(name) for name in CHANNELS]]


def transform_context(
    native_channels_time: np.ndarray,
    sfreq: float,
    cue: int,
    context_bounds: tuple[int, int] | None = None,
) -> dict[str, np.ndarray]:
    """CAR, native zero-phase filtering, anti-aliased resampling, then crop.

    ``cue`` is an already audited zero-based sample. ``context_bounds`` is the
    permitted native trial interval (half-open), not a suggestion to shorten
    the context. A missing or truncated six-second context fails closed.
    Synthetic tests may call this mathematical function; writing real epochs
    is guarded in the external preparation script by committed audit/freeze.
    """
    signal = np.asarray(native_channels_time)
    if signal.ndim != 2 or signal.shape[0] != len(CHANNELS):
        raise ValueError("Q15 input must be [21 channels, native samples]")
    if not np.issubdtype(signal.dtype, np.number) or np.iscomplexobj(signal):
        raise ValueError("Q15 input contains nonnumeric EEG")
    if not np.isfinite(sfreq) or sfreq <= 2 * max(band[1] for band in BANDS.values()):
        raise ValueError("Native sampling rate cannot represent the frozen bands")
    if isinstance(cue, (bool, np.bool_)) or not isinstance(cue, (int, np.integer)) or cue < 0:
        raise ValueError("Cue sample must be a zero-based nonnegative integer")
    start = int(cue) + _grid(CONTEXT_WINDOW[0] * sfreq, "Context start")
    stop = int(cue) + _grid(CONTEXT_WINDOW[1] * sfreq, "Context stop")
    lower, upper = (0, signal.shape[1]) if context_bounds is None else context_bounds
    if not all(isinstance(v, (int, np.integer)) and not isinstance(v, (bool, np.bool_))
               for v in (lower, upper)):
        raise ValueError("Trial boundaries must be integer native samples")
    if lower < 0 or upper > signal.shape[1] or lower >= upper:
        raise ValueError("Invalid native trial boundaries")
    if start < lower or stop > upper or stop - start != _grid(6 * sfreq, "Context length"):
        raise ValueError("Audited trial does not cover the complete frozen context")
    # Float64 deterministic filtering; the final model input alone is float32.
    context = np.array(signal[:, start:stop], dtype=np.float64, copy=True)
    if not np.isfinite(context).all():
        raise ValueError("Q15 retained context contains nonfinite EEG")
    context -= context.mean(axis=0, keepdims=True)
    ratio = Fraction(COMMON_RATE / float(sfreq)).limit_denominator(100000)
    if not np.isclose(ratio.numerator / ratio.denominator, COMMON_RATE / sfreq, rtol=0, atol=1e-12):
        raise ValueError("Unsupported nonrational native/common sampling ratio")
    arrays = {}
    for name, (low, high) in BANDS.items():
        sos = butter(4, (low, high), btype="bandpass", fs=float(sfreq), output="sos")
        filtered = sosfiltfilt(sos, context, axis=-1, padtype="odd", padlen=FILTER_PADLEN)
        common = resample_poly(filtered, ratio.numerator, ratio.denominator, axis=-1,
                               window=("kaiser", 5.0), padtype="constant", cval=0.0)
        if common.shape != (21, 960):
            raise AssertionError("Q15 common-rate context must contain exactly 960 samples")
        epoch = np.ascontiguousarray(common[:, 320:640], dtype=np.float32)
        if epoch.shape != (21, N_TIMES) or not np.isfinite(epoch).all():
            raise AssertionError("Invalid fixed Q15 epoch")
        arrays[name] = epoch
    return arrays


def verify_bnci_originals(data_dir: Path, provenance_path: Path) -> dict[str, Path]:
    """Independently rehash all 18 originals against the previously frozen Q8 list."""
    records = json.loads(Path(provenance_path).read_text(encoding="utf-8"))
    if not isinstance(records, list) or len(records) != 18:
        raise ValueError("Q8 BNCI provenance must identify all 18 source originals")
    expected = {f"A{subject:02d}{session}.mat" for subject in range(1, 10) for session in "TE"}
    names = [Path(row["path"]).name for row in records]
    if len(set(names)) != 18 or set(names) != expected:
        raise ValueError("BNCI provenance contains missing, duplicate, or unexpected files")
    root = Path(data_dir).resolve(strict=True)
    candidates = list(root.rglob("A*.mat"))
    found = {}
    for name in sorted(expected):
        matches = [p for p in candidates if p.name == name and p.is_file()]
        if len(matches) != 1:
            raise ValueError(f"Exactly one source original is required: {name}")
        candidate = matches[0]
        if any(part.is_symlink() for part in (candidate, *candidate.parents)):
            raise ValueError(f"Source originals cannot traverse symlinks: {name}")
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ValueError(f"Source original escapes the declared data directory: {name}")
        found[name] = resolved
    for row in records:
        path = found[Path(row["path"]).name]
        if path.stat().st_size != row["bytes"] or sha256_file(path) != row["sha256"]:
            raise ValueError(f"BNCI original differs from frozen Q8 provenance: {path.name}")
    return found


def _integer_vector(values, name: str) -> np.ndarray:
    values = np.asarray(values).reshape(-1)
    if not np.issubdtype(values.dtype, np.number) or np.iscomplexobj(values):
        raise ValueError(f"BNCI {name} must be real numeric values")
    if not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
        raise ValueError(f"BNCI {name} must be finite native integers")
    if np.any(values < -(2 ** 63)) or np.any(values >= 2 ** 63):
        raise ValueError(f"BNCI {name} exceeds the integer sample representation")
    return values.astype(np.int64)


def _validated_bnci_runs(path: Path) -> list[dict]:
    """Audit original run schema and all four classes without transforming EEG."""
    runs = loadmat(path, variable_names=["data"], simplify_cells=True).get("data")
    if isinstance(runs, dict):
        runs = [runs]
    elif isinstance(runs, np.ndarray):
        runs = runs.reshape(-1).tolist()
    if not isinstance(runs, list) or any(not isinstance(run, dict) for run in runs):
        raise ValueError("BNCI data must contain original MATLAB run structs")
    active = [run for run in runs if np.asarray(run.get("trial", [])).size]
    if len(active) != 6:
        raise ValueError("BNCI must contain exactly six labeled MI runs")
    validated = []
    for run in active:
        signal = np.asarray(run["X"])
        trials = _integer_vector(run["trial"], "trial starts")
        labels = _integer_vector(run["y"], "label codes")
        artifacts = _integer_vector(run["artifacts"], "artifact flags")
        rate_value = np.asarray(run["fs"])
        if rate_value.size != 1 or not np.issubdtype(rate_value.dtype, np.number) or np.iscomplexobj(rate_value):
            raise ValueError("BNCI sampling rate must be a real numeric scalar")
        rate = float(rate_value.reshape(-1)[0])
        if rate != 250 or signal.ndim != 2 or signal.shape[1] != 25:
            raise ValueError("BNCI native sampling rate or 22 EEG + 3 EOG shape changed")
        if not np.issubdtype(signal.dtype, np.number) or np.iscomplexobj(signal) or not np.isfinite(signal).all():
            raise ValueError("BNCI native run contains nonfinite or nonnumeric EEG/EOG")
        if any(len(values) != 48 for values in (trials, labels, artifacts)):
            raise ValueError("BNCI run must retain all 48 original four-class trials")
        if Counter(labels.tolist()) != Counter({1: 12, 2: 12, 3: 12, 4: 12}):
            raise ValueError("BNCI original class counts changed")
        if not np.isin(artifacts, (0, 1)).all():
            raise ValueError("BNCI artifact flags must be native binary indicators")
        if np.any(trials < 1) or np.any(trials > signal.shape[0]) or np.any(np.diff(trials) <= 0):
            raise ValueError("BNCI trial starts must be positive increasing MATLAB samples")
        # BNCI trial starts precede the operational MI cue by exactly 2 s.
        cues = trials - 1 + 500
        starts, stops = cues - 375, cues + 1125
        if np.any(starts < 0) or np.any(stops > signal.shape[0]):
            raise ValueError("BNCI original trial lacks a complete six-second context in its run")
        validated.append({"X": signal, "trial": trials, "y": labels,
                          "artifacts": artifacts, "fs": rate,
                          "context_start": starts, "context_stop": stops})
    return validated


def audit_bnci_source(data_dir: Path, provenance_path: Path | None = None) -> dict:
    """Metadata-only all-original source audit suitable for the pre-fit freeze.

    This checks all four classes, including trials outside the binary task. It
    reads and hashes native arrays but performs no filtering or resampling.
    """
    provenance_path = Path(provenance_path or SOURCE_PROVENANCE)
    originals = verify_bnci_originals(data_dir, provenance_path)
    files = []
    for name, path in sorted(originals.items()):
        runs = _validated_bnci_runs(path)
        files.append({
            "file_id": name, "path": str(path), "bytes": path.stat().st_size,
            "sha256": sha256_file(path), "subject": int(name[1:3]),
            "session": "0train" if name[3] == "T" else "1test",
            "runs": [{
                "run": index, "n_native_samples": run["X"].shape[0],
                "native_sampling_rate_hz": 250, "n_native_eeg_channels": 22,
                "native_eeg_channel_names": list(BNCI_CHANNELS),
                "n_all_four_class_trials": 48, "n_binary_trials": 24,
                "class_counts": {str(code): 12 for code in (1, 2, 3, 4)},
                "trial_samples_matlab_one_based": run["trial"].tolist(),
                "context_start_samples_zero_based": run["context_start"].tolist(),
                "context_stop_samples_exclusive": run["context_stop"].tolist(),
                "native_artifact_flags": run["artifacts"].tolist(),
            } for index, run in enumerate(runs)],
        })
    return {
        "schema_version": 1, "dataset": "BNCI2014_001",
        "status": "source_metadata_passed_non_authorizing", "metadata_only": True,
        "source_training_authorized": False, "external_prediction_authorized": False,
        "predictions_computed": False, "performance_metrics_computed": False,
        "target_fits": 0, "fits_started": 0, "raw_hashes_verified": True,
        "n_files": 18, "n_runs": 108, "n_all_four_class_trials": 5184,
        "n_binary_trials": 2592, "context_relative_s": list(CONTEXT_WINDOW),
        "provenance_sha256": sha256_file(provenance_path), "files": files,
        "auditor_sha256": sha256_file(Path(__file__)),
    }


def load_bnci_source(
    data_dir: Path,
    subjects: list[int],
    provenance_path: Path,
) -> tuple[dict[str, np.ndarray], pd.DataFrame, pd.DataFrame]:
    """Return uniform Q15 source epochs in memory after all raw hashes pass.

    The source runner verifies committed scientific audit/freeze before calling
    this function. There are no model fits or processed-file writes here.
    Sessions, run numbers, and sample IDs match the original Q8 loader.
    """
    if (not subjects or sorted(set(subjects)) != sorted(subjects)
            or any(not isinstance(s, (int, np.integer)) or isinstance(s, (bool, np.bool_))
                   or s not in range(1, 10) for s in subjects)):
        raise ValueError("Unique BNCI subjects 1 through 9 are required")
    originals = verify_bnci_originals(data_dir, provenance_path)
    metadata, audits = [], []
    chunks = {name: [] for name in BANDS}
    for subject in sorted(subjects):
        for suffix, session in (("T", "0train"), ("E", "1test")):
            active = _validated_bnci_runs(originals[f"A{subject:02d}{suffix}.mat"])
            for run_index, run in enumerate(active):
                signal = np.asarray(run["X"])
                trials = np.asarray(run["trial"]).reshape(-1)
                labels = np.asarray(run["y"]).reshape(-1)
                artifacts = np.asarray(run["artifacts"]).reshape(-1)
                rate = float(run["fs"])
                selected = select_channels(signal[:, :22].T, BNCI_CHANNELS)
                counts_flagged = Counter(int(label) for label, flag in zip(labels, artifacts) if flag and label in (1, 2))
                for trial_index, (mat_start, label, artifact) in enumerate(zip(trials, labels, artifacts), 1):
                    if label not in (1, 2):
                        continue
                    start = int(mat_start) - 1
                    cue = start + 500
                    transformed = transform_context(selected, rate, cue)
                    for name, values in transformed.items():
                        chunks[name].append(values)
                    metadata.append({
                        "sample_id": f"s{subject:02d}_{session}_r{run_index}_t{trial_index:02d}",
                        "subject": subject, "session": session, "run": run_index,
                        "trial": trial_index, "label": int(label), "event_sample": start,
                        "artifact_flagged": bool(artifact),
                    })
                audit = {
                    "subject": subject, "session": session, "run": run_index,
                    "n_all_four_class_trials": 48, "n_candidate_trials": 24,
                    "n_source_artifact_flags_all_classes": int(np.count_nonzero(artifacts)),
                    "n_flagged_trials": sum(counts_flagged.values()), "n_rejected_trials": 0,
                    "n_kept_trials": 24, "n_times_per_epoch": 500, "n_eeg_channels": 22,
                    "sampling_rate_hz": rate, "native_sampling_rate_hz": rate,
                    "output_n_times": 320, "output_n_channels": 21, "common_rate": 160,
                    "transform_context_relative_s": json.dumps(CONTEXT_WINDOW),
                    "reference": "common_average_21", "padlen": FILTER_PADLEN,
                    "artifact_policy": "include_all", "class_counts_candidate": json.dumps({1: 12, 2: 12}),
                    "class_counts_flagged": json.dumps({code: counts_flagged[code] for code in (1, 2)}),
                    "class_counts_kept": json.dumps({1: 12, 2: 12}),
                    "eeg_channel_names": json.dumps(BNCI_CHANNELS),
                    "output_channel_names": json.dumps(CHANNELS),
                    "preprocessing": "q15_uniform_trial_context_v1",
                }
                for code in (1, 2):
                    audit.update({f"n_class_{code}_candidate": 12, f"n_class_{code}_flagged": counts_flagged[code], f"n_class_{code}_kept": 12})
                audits.append(audit)
    arrays = {name: np.stack(values).astype(np.float32, copy=False) for name, values in chunks.items()}
    meta = pd.DataFrame(metadata)
    if len(meta) != len(subjects) * 2 * 6 * 24 or meta["sample_id"].duplicated().any():
        raise AssertionError("BNCI binary trial identity/count differs from frozen plan")
    return arrays, meta, pd.DataFrame(audits)
