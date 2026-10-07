"""Fixed Q16 BNCI metadata helpers; no filtering, fitting, or power analysis."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "research_runs/Q16-P001-BNCI-20261006"
Q15_DIR = ROOT / "research_runs/Q15-EXECUTION-20261003/jobs/20261004T005335Z-9b3bce30277a"
Q15_RAW_RECEIPT = Q15_DIR / "bnci_source_receipt.json"
RAW_RECEIPT = RUN_DIR / "raw_source_receipt.json"
PRIOR_AUDIT = Q15_DIR / "bnci_metadata_audit.json"
Q8_METADATA = ROOT / "research_runs/Q8-E001/results/trial_metadata.csv"
PERFORMANCE = ROOT / "results/Q14-E001/subject_seed_metrics.csv"
PERFORMANCE_VALIDATION = ROOT / "results/Q14-E001/validation_report.json"
CHANNELS = ("Fz", "FC3", "FC1", "FCz", "FC2", "FC4", "C5", "C3", "C1", "Cz", "C2", "C4", "C6", "CP3", "CP1", "CPz", "CP2", "CP4", "P1", "Pz", "P2", "POz")
CLASS_MAP = {1: "left_hand", 2: "right_hand", 3: "feet", 4: "tongue"}
BANDS = {"mu": (8.0, 13.0), "beta": (13.0, 30.0)}
BASELINE_OFFSETS = (125, 375)
TASK_OFFSETS = (625, 1125)
EXPECTED_NAMES = {f"A{s:02d}{suffix}.mat" for s in range(1, 10) for suffix in ("T", "E")}
LIMITS = [
    "BNCI-only physiology; external physiological replication not performed.",
    "Baseline is a pre-cue fixation interval, not a separately recorded resting state.",
    "Baseline has one Welch segment and task has three correlated Welch segments; unequal estimator variance can bias a log-power ratio.",
    "Native numerical voltage calibration was not newly verified; absolute power is native_numeric_squared and only within-recording ratios are gain invariant.",
    "A negative laterality descriptor indicates relatively stronger contralateral suppression, not proof that absolute contralateral power decreased.",
    "Scalp channel descriptors do not identify cortical sources or establish decoder mechanism or causality.",
    "Six n=9 correlations are descriptive contexts without p values, model selection, subgroup thresholds, or independent external validation.",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def software() -> dict:
    return {"python": sys.version, "python_executable": sys.executable, "numpy": np.__version__, "scipy": scipy.__version__, "pandas": pd.__version__, "platform": platform.platform()}


def binding(path: Path) -> dict:
    path = Path(path).resolve()
    stored_path = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
    return {"path": stored_path, "sha256": sha256_file(path), "bytes": path.stat().st_size}


def resolve_bound_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def integer_vector(value, name: str) -> np.ndarray:
    result = np.asarray(value).reshape(-1)
    if not np.issubdtype(result.dtype, np.number) or np.iscomplexobj(result):
        raise ValueError(f"{name}: expected real numeric integers")
    if not np.isfinite(result).all() or not np.equal(result, np.floor(result)).all():
        raise ValueError(f"{name}: nonfinite or noninteger metadata")
    if np.any(result < -(2**63)) or np.any(result >= 2**63):
        raise ValueError(f"{name}: outside int64 representation")
    return result.astype(np.int64)


def native_class_names(value) -> list[str]:
    """Normalize only the documented label spelling, not the event order."""
    if isinstance(value, str):
        values = [value]
    else:
        values = np.asarray(value, dtype=object).reshape(-1).tolist()
    result = []
    for item in values:
        if isinstance(item, np.ndarray):
            if item.size != 1:
                raise ValueError("Native class name has unexpected array topology")
            item = item.item()
        if not isinstance(item, str):
            raise ValueError("Native class map must contain text")
        result.append(item.strip().lower().replace(" ", "_"))
    return result


def load_native_runs(path: Path) -> list[dict]:
    """Keep original MAT struct identity while exposing the six labeled runs.

    This metadata adapter examines structure and metadata only. Signal amplitudes
    are left unchanged; their finite guards belong to the power calculation.
    """
    data = loadmat(path, variable_names=["data"], simplify_cells=True).get("data")
    if isinstance(data, dict):
        data = [data]
    elif isinstance(data, np.ndarray):
        data = data.reshape(-1).tolist()
    if not isinstance(data, list) or any(not isinstance(run, dict) for run in data):
        raise ValueError(f"{path.name}: expected native MATLAB run structs")
    active = []
    for native_index, run in enumerate(data):
        if not np.asarray(run.get("trial", [])).size:
            continue
        signal = np.asarray(run.get("X"))
        if signal.ndim != 2 or signal.shape[1] != 25 or not np.issubdtype(signal.dtype, np.number) or np.iscomplexobj(signal):
            raise ValueError(f"{path.name}: expected real native samples by 22 EEG + 3 EOG")
        rate = np.asarray(run.get("fs"))
        if rate.size != 1 or not np.issubdtype(rate.dtype, np.number) or np.iscomplexobj(rate) or not np.isfinite(rate).all() or float(rate.item()) != 250.0:
            raise ValueError(f"{path.name}: native sampling rate differs from 250 Hz")
        trials = integer_vector(run.get("trial"), "MATLAB trial starts")
        labels = integer_vector(run.get("y"), "native class labels")
        artifacts = integer_vector(run.get("artifacts"), "native artifact flags")
        if any(len(values) != 48 for values in (trials, labels, artifacts)):
            raise ValueError(f"{path.name}: labeled run must have all 48 trial rows")
        if Counter(labels.tolist()) != Counter({1: 12, 2: 12, 3: 12, 4: 12}):
            raise ValueError(f"{path.name}: four-class event counts differ")
        if not np.isin(artifacts, (0, 1)).all():
            raise ValueError(f"{path.name}: artifact flags are not native binary indicators")
        if np.any(trials < 1) or np.any(trials > signal.shape[0]) or np.any(np.diff(trials) <= 0):
            raise ValueError(f"{path.name}: trial starts are not positive increasing integers")
        raw_class_field = np.asarray(run.get("classes", []), dtype=object)
        classes = native_class_names(raw_class_field)
        if classes != list(CLASS_MAP.values()):
            raise ValueError(f"{path.name}: native class map differs: {classes}")
        trial0 = trials - 1
        starts = trial0 + BASELINE_OFFSETS[0]
        stops = trial0 + TASK_OFFSETS[1]
        if np.any(starts < 0) or np.any(stops > signal.shape[0]):
            raise ValueError(f"{path.name}: fixed baseline/task leaves its native run")
        # Nominal imagery lasts cue + 0 through +4 s: trial0 + 500 through +1500.
        gaps = starts[1:] - (trial0[:-1] + 1500)
        if np.any(gaps < 0):
            raise ValueError(f"{path.name}: baseline overlaps previous nominal imagery")
        active.append({"X": signal, "trial": trials, "y": labels, "artifacts": artifacts, "native_struct_index_zero_based": native_index, "native_struct_index_matlab_one_based": native_index + 1, "run": len(active), "native_total_structs": len(data), "classes": classes, "raw_class_names": raw_class_field.reshape(-1).tolist(), "class_field_shape_after_scipy_simplify_cells": list(raw_class_field.shape), "prior_nominal_imagery_gap_samples": gaps})
    if len(active) != 6:
        raise ValueError(f"{path.name}: expected six labeled MI runs, found {len(active)}")
    return active


def verify_raw_files(data_dir: Path, receipt_path: Path = RAW_RECEIPT) -> tuple[list[dict], dict]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    records = receipt.get("files", [])
    if len(records) != 18 or {r.get("file_id") for r in records} != EXPECTED_NAMES:
        raise ValueError("Q15 frozen raw receipt does not cover exactly 18 original files")
    old = json.loads(Q15_RAW_RECEIPT.read_text(encoding="utf-8"))
    comparison_fields = ("file_id", "sha256", "size_bytes")
    inventory = lambda rows: sorted([{key: row[key] for key in comparison_fields} for row in rows], key=lambda row: row["file_id"])
    if inventory(records) != inventory(old["files"]):
        raise ValueError("Current persisted raw receipt differs from prior Q15 original-file receipt")
    found = {}
    for path in data_dir.resolve().rglob("*.mat"):
        if path.name in EXPECTED_NAMES:
            if path.name in found:
                raise ValueError(f"Duplicate original file identity: {path.name}")
            found[path.name] = path
    if set(found) != EXPECTED_NAMES:
        raise ValueError(f"Incomplete 18-file raw inventory: missing={sorted(EXPECTED_NAMES-set(found))}")
    checked = []
    for expected in sorted(records, key=lambda item: item["file_id"]):
        path = found[expected["file_id"]]
        actual = binding(path)
        if actual["bytes"] != expected["size_bytes"] or actual["sha256"] != expected["sha256"]:
            raise ValueError(f"Original raw file disagrees with Q15 receipt: {path.name}")
        checked.append({**actual, "file_id": path.name, "subject": int(path.name[1:3]), "session": "0train" if path.name[3] == "T" else "1test", "official_url": expected["official_url"]})
    return checked, binding(receipt_path)


def fixed_recipe() -> dict:
    return {
        "sampling_rate_hz": 250, "channels": list(CHANNELS), "native_eeg_columns_half_open": [0, 22], "native_eog_columns_skipped": [22, 23, 24],
        "additional_filter": None, "additional_reference": None, "additional_scaler": None, "provider_acquisition_filtering_retained": True, "voltage_calibration_newly_verified": False,
        "trial_anchor": "MATLAB_trial_minus_1", "cue_offset_native_samples": 500,
        "baseline_cue_relative_s_half_open": [-1.5, -0.5], "task_cue_relative_s_half_open": [0.5, 2.5],
        "baseline_trial_relative_samples_half_open": list(BASELINE_OFFSETS), "task_trial_relative_samples_half_open": list(TASK_OFFSETS),
        "welch": {"implementation": "scipy.signal.welch", "window": "scipy.signal.get_window('hann',250,fftbins=True)", "nperseg": 250, "noverlap": 125, "nfft": 250, "detrend": "linear", "return_onesided": True, "scaling": "density", "average": "mean", "axis": -1, "baseline_segments": 1, "task_segments": 3},
        "bands_hz_inclusive": {name: list(limits) for name, limits in BANDS.items()}, "band_integration": "numpy.trapezoid(PSD[low<=frequency<=high], frequency)",
        "psd_unit": "native_numeric_squared_per_Hz", "integrated_power_unit": "native_numeric_squared", "ratio_unit": "dB", "ratio": "10*log10(task_power/baseline_power)", "epsilon_or_clipping": None,
        "artifacts": "include_all_native_flags_preserved", "laterality_pairing": "C3_and_C4_both_eligible_in_same_trial_band", "laterality_aggregation": "mean_trial_dB_within_subject_hand_session_then_equal_session_means_then_equal_hand_signed_descriptor",
        "laterality_formula": "0.5*((C3_right-C4_right)+(C4_left-C3_left))", "negative_laterality_means": "relatively_more_contralateral_suppression_not_absolute_ERD",
        "associations": {"statistic": "Spearman_correlation_of_average_ranks", "n_subjects": 9, "primary_model": "BROAD_EEGNET", "models": ["BROAD_EEGNET", "MU_BETA_SHARED", "CSP4_LDA"], "bands": ["mu", "beta"], "performance_aggregation": "mean_three_frozen_neural_seeds_per_subject_CSP_one_frozen_fit", "p_values": False, "model_selection": False, "high_low_groups": False},
        "new_decoder_fits": 0, "new_decoder_inference": 0,
    }


def committed_binding(path: Path, commit: str) -> None:
    path = resolve_bound_path(path)
    relative = path.resolve().relative_to(ROOT).as_posix()
    content = subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=ROOT, check=True, capture_output=True).stdout
    if hashlib.sha256(content).hexdigest() != sha256_file(path):
        raise ValueError(f"Working file differs from committed freeze: {relative}")


def require_committed_freeze(manifest_path: Path, commit: str, audit_path: Path) -> dict:
    resolved = subprocess.run(["git", "rev-parse", "--verify", f"{commit}^{{commit}}"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    if len(commit) != 40 or resolved != commit:
        raise ValueError("Supply the full 40-character committed freeze SHA")
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT, check=True, capture_output=True)
    committed_binding(manifest_path, commit)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("analysis_id") != "Q16-P001-BNCI-20261006" or manifest.get("status") != "frozen_before_raw_power" or manifest.get("recipe") != fixed_recipe():
        raise ValueError("Freeze identity, status, or fixed recipe differs from implementation")
    needed_code = {"scripts/q16_common.py", "scripts/q16_metadata_audit.py", "scripts/q16_bnci_analysis.py"}
    if {r["path"] for r in manifest.get("code_files", [])} != needed_code:
        raise ValueError("Freeze must bind all three Q16 calculation/audit code files")
    needed_inputs = {binding(p)["path"] for p in (RAW_RECEIPT, Q15_RAW_RECEIPT, PRIOR_AUDIT, Q8_METADATA, PERFORMANCE, PERFORMANCE_VALIDATION, audit_path)}
    if not needed_inputs.issubset({r["path"] for r in manifest.get("input_files", [])}):
        raise ValueError("Freeze misses required metadata/performance/provenance inputs")
    if not manifest.get("protocol_files"):
        raise ValueError("Freeze must bind a written protocol/amendment")
    expected_code_mapping = {r["path"]: r["sha256"] for r in manifest["code_files"]}
    if manifest.get("code_sha256") != expected_code_mapping or manifest.get("protocol_sha256") != manifest["protocol_files"][0]["sha256"] or manifest.get("raw_receipt_sha256") != sha256_file(RAW_RECEIPT) or manifest.get("metadata_audit_sha256") != sha256_file(audit_path) or manifest.get("methodology") != fixed_recipe() or manifest.get("expected") != {"raw_files": 18, "labeled_runs": 108, "all_four_class_trials": 5184, "binary_trials": 2592} or manifest.get("new_decoder_fits") != 0 or manifest.get("new_checkpoint_inference") != 0:
        raise ValueError("Freeze flat code/protocol/input/recipe/count/zero-fit bindings differ")
    for record in manifest["code_files"] + manifest["input_files"] + manifest["protocol_files"]:
        path = resolve_bound_path(record["path"])
        if binding(path) != record:
            raise ValueError(f"Frozen file changed: {path}")
        committed_binding(path, commit)
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("status") != "metadata_passed_before_raw_power" or audit.get("metadata_only") is not True or audit.get("raw_power_computed") is not False or audit.get("recipe") != fixed_recipe():
        raise ValueError("Passed fixed metadata gate required before raw power")
    audited = {r["path"]: r for r in audit.get("auditor_code_files", [])}
    frozen = {r["path"]: r for r in manifest["code_files"]}
    if set(audited) != {"scripts/q16_common.py", "scripts/q16_metadata_audit.py"} or any(frozen.get(p) != r for p, r in audited.items()):
        raise ValueError("Metadata auditor code differs from the committed freeze")
    return {"git_commit": commit, "manifest": binding(manifest_path), "metadata_audit": binding(audit_path), "frozen_inputs": manifest["input_files"], "frozen_protocols": manifest["protocol_files"], "frozen_code": manifest["code_files"]}
