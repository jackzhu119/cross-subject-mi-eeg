"""Independently validate completed Q15-E005 source artifacts without fitting.

This validator reads source metadata and already fitted artifacts only. It does
not load raw EEG, calculate predictions, or authorize external evaluation. The
real metadata gates and separately committed pre-fit freeze remain mandatory.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
MODELS = ("BROAD_EEGNET", "MU_BETA_SHARED")
SESSIONS = ("0train", "1test")
EXPERIMENT = "Q15-E005"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MD5 = re.compile(r"[0-9a-f]{32}\Z")


def _reject_constant(value: str):
    raise ValueError(f"Nonfinite JSON constant: {value}")


def _read(path: Path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, f"Duplicate JSON field: {path}: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant, object_pairs_hook=unique_object)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _ids(values) -> str:
    return hashlib.sha256("\n".join(map(str, values)).encode("utf-8")).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _fields(record: dict, expected: dict, label: str) -> None:
    _require(isinstance(record, dict), f"Not a JSON object: {label}")
    for key, value in expected.items():
        _require(key in record and _same(record[key], value), f"{label}: mismatched {key}")
    forbidden = ("external_predictions_computed", "external_prediction_authorized", "predictions_computed", "performance_metrics_computed")
    for key in forbidden:
        _require(key not in record or record[key] is False, f"{label}: external outcomes present")
    _require(type(record.get("target_fits", 0)) is int and record.get("target_fits", 0) == 0, f"{label}: target fits present")
    _require(record.get("target_subjects", []) == [], f"{label}: target subjects present")


def _same(actual, expected) -> bool:
    """Keep JSON booleans/counts distinct; Python equality considers 1 == True."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(actual) == set(expected) and all(_same(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(_same(left, right) for left, right in zip(actual, expected))
    if type(expected) in (bool, int, str) or expected is None:
        return type(actual) is type(expected) and actual == expected
    if type(expected) is float:
        return type(actual) in (int, float) and math.isfinite(actual) and actual == expected
    return actual == expected


def _check_hash(path: Path, digest: str) -> None:
    _require(isinstance(digest, str) and SHA256.fullmatch(digest) is not None, f"Invalid SHA256: {path}")
    _require(path.is_file() and not path.is_symlink(), f"Artifact missing or symlinked: {path}")
    _require(_sha(path) == digest, f"Artifact SHA256 mismatch: {path}")


def _check_original(path: Path, digest: str, md5_digest: str, size: int) -> None:
    _require(path.is_file() and not path.is_symlink(), f"Original missing or symlinked: {path}")
    _require(isinstance(digest, str) and SHA256.fullmatch(digest) is not None, "Invalid original SHA256")
    _require(isinstance(md5_digest, str) and MD5.fullmatch(md5_digest) is not None, "Invalid original MD5")
    _require(type(size) is int and size > 0 and path.stat().st_size == size, "Raw original byte count differs")
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
            md5.update(block)
    _require(sha.hexdigest() == digest and md5.hexdigest() == md5_digest, "Raw original SHA256/MD5 differs from frozen transport")


def _committed(path: Path) -> None:
    relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    result = subprocess.run(["git", "show", f"HEAD:{relative}"], cwd=ROOT, capture_output=True, check=False)
    _require(result.returncode == 0 and result.stdout == path.read_bytes(), f"Pre-fit input is not committed unchanged: {relative}")


def _verify_metadata_receipt(receipt: dict, manifest_path: Path, dataset: str, channels: list[str]) -> None:
    """Rehash full external provenance without loading raw EEG or model code."""
    expected_subjects, sessions = {"Lee2019_MI": (54, 2), "Cho2017": (52, 1)}[dataset]
    _fields(receipt, {"failed_files": [], "blocking_reasons": []}, f"{dataset} metadata receipt")
    for field in ("provider_version", "loader_version", "license", "provider_inventory_source"):
        _require(isinstance(receipt.get(field), str) and bool(receipt[field].strip()), f"{dataset}: missing {field}")
    manifest = _read(manifest_path)
    _fields(manifest, {"schema_version": 1, "dataset": dataset}, f"{dataset} provider manifest")
    rows, ids = receipt["files"], receipt["expected_file_ids"]
    if dataset == "Cho2017":
        expected_ids = {f"s{subject:02d}.mat": (subject, 1, "retained_labeled_MI") for subject in range(1, 53)}
    else:
        expected_ids = {f"session{session}/s{subject}/sess0{session}_subj{subject:02d}_EEG_MI.mat": (subject, session, "offline_train") for session in (1, 2) for subject in range(1, 55)}
    _require(set(ids) == set(expected_ids), "Scientific receipt differs from complete canonical cohort inventory")
    base = ROOT / "research_runs/Q15-EXECUTION-20261003/evidence"
    provider = _read(base / ("cho_transfer_manifest.json" if dataset == "Cho2017" else "lee_transfer_manifest.json"))
    _fields(provider, {"schema_version": 1, "dataset": dataset}, "Archived provider inventory")
    provider_rows = provider.get("files", [])
    providers = {row["file_id"]: row for row in provider_rows}
    _require(len(provider_rows) == len(providers) == len(expected_ids) and set(providers) == set(provider.get("expected_file_ids", [])) == set(expected_ids), "Archived provider inventory is incomplete")
    transport_rows = [row for row in _read(ROOT / "research_runs/Q15-PREPARATION/transport_inventory.json")["files"] if row.get("dataset") == dataset]
    transport = {row["file_id"]: row for row in transport_rows}
    _require(len(transport_rows) == len(transport) == len(expected_ids) and set(transport) == set(expected_ids), "Transport inventory is incomplete")
    official_md5 = {}
    if dataset == "Lee2019_MI":
        for line in (base / "100542.md5").read_text(encoding="utf-8").splitlines():
            match = re.fullmatch(r"([0-9a-fA-F]{32})\s+\*?\.?/?(.*)", line.strip())
            if match:
                _require(match[2] not in official_md5, "Duplicate official Lee checksum ID")
                official_md5[match[2]] = match[1].lower()
    manifest_rows, manifest_ids = manifest.get("files", []), manifest.get("expected_file_ids", [])
    _require(isinstance(manifest_rows, list) and isinstance(manifest_ids, list) and len(manifest_rows) == len(manifest_ids) == len(rows), "Provider inventory is incomplete")
    _require(len(set(manifest_ids)) == len(manifest_ids) and set(manifest_ids) == set(ids), "Provider and scientific receipt IDs differ")
    originals = {row.get("file_id"): row for row in manifest_rows}
    _require(len(originals) == len(rows) and set(originals) == set(ids), "Provider file IDs are missing or duplicated")
    subjects, identities, paths = {}, set(), set()
    for row in rows:
        _require(isinstance(row, dict), "Scientific receipt contains a non-object row")
        raw_path = Path(row.get("path", ""))
        _require(raw_path.is_absolute() and raw_path not in paths, "Raw metadata paths must be absolute and distinct")
        paths.add(raw_path)
        snapshot, archived = transport[row["file_id"]], providers[row["file_id"]]
        _fields(row, {key: snapshot[key] for key in ("sha256", "md5", "size_bytes")}, f"{dataset} transport metadata")
        _require(type(row["size_bytes"]) is int and row["size_bytes"] > 0 and archived.get("size_bytes") == row["size_bytes"], "Provider original byte count differs")
        _check_original(raw_path, row["sha256"], row["md5"], row["size_bytes"])
        expected_md5 = archived.get("provider_md5")
        if dataset == "Lee2019_MI":
            _require(official_md5.get(row["file_id"]) == expected_md5, "Archived Lee checksum differs from official manifest")
        if expected_md5:
            _require(expected_md5 == row["md5"], "Raw original differs from provider MD5")
        else:
            _require(dataset == "Cho2017" and expected_ids[row["file_id"]][0] in (7, 9, 46), "Unexpected unavailable provider content MD5")
        original = originals[row["file_id"]]
        _require(original.get("sha256") == row["sha256"], "Provider and scientific receipt raw SHA256 differ")
        provider_path = Path(original.get("path", ""))
        if not provider_path.is_absolute():
            provider_path = manifest_path.parent / provider_path
        _require(provider_path.resolve() == raw_path.resolve(), "Provider and scientific receipt raw paths differ")
        for field in ("subject", "session", "run"):
            _require(_same(original.get(field), row.get(field)), f"Provider and scientific receipt {field} differs")
        subject, session, run = row.get("subject"), row.get("session"), row.get("run")
        _require(_same([subject, session, run], list(expected_ids[row["file_id"]])), "Scientific receipt identity differs from canonical provider file ID")
        _require(type(subject) is int and subject in range(1, expected_subjects + 1), "External metadata subject inventory differs")
        _require(str(session) and str(run) and session is not None and run is not None, "Missing external session/run identity")
        identity = subject, str(session), str(run)
        _require(identity not in identities, "Duplicate external subject/session/run")
        identities.add(identity)
        subjects.setdefault(subject, set()).add(str(session))
        names = row.get("channels")
        _require(isinstance(names, list) and len(set(names)) == len(names) and set(channels).issubset(names), "Required canonical channels absent from scientific receipt")
        _fields(row, {"cue_origin": "MI_cue_onset", "task": "left_right_motor_imagery", "labeled": True, "label_map": {"left_hand": 1, "right_hand": 2}, "loader_output_unit": "V", "declared_analysis_unit": "uV", "native_numeric_calibration_verified": False, "hardware_cue_latency_verified": False, "context_bounds_verified": True, "no_outcomes_inspected": True, "execution_contract_sha256": receipt["execution_contract_sha256"], "n_labeled_trials": 100 if dataset == "Lee2019_MI" else 240 if subject in (7, 9, 46) else 200, "sampling_rate_hz": 1000 if dataset == "Lee2019_MI" else 512, "run_role": "offline_train" if dataset == "Lee2019_MI" else "offline_labeled"}, f"{dataset} raw metadata")
        window = row.get("available_cue_window_s")
        _require(isinstance(window, list) and len(window) == 2 and all(type(value) in (int, float) and math.isfinite(value) for value in window) and window[0] <= -1.5 and window[1] >= 4.5, "Scientific receipt does not cover the frozen trial context")
    _require(set(subjects) == set(range(1, expected_subjects + 1)) and all(len(value) == sessions for value in subjects.values()), "External cohort subject/session inventory is incomplete")


def _verify_protocol(output: Path) -> tuple[dict, dict, str]:
    """Check byte-level freeze provenance independently of the training runner."""
    packet = ROOT / "research_runs/PAPER_RELEASE_20260927"
    contract_path = packet / "Q15_CONTRACT.json"
    q14_path = ROOT / "research_runs/Q14-E001/CONFIG.json"
    contract, q14 = _read(contract_path), _read(q14_path)
    plan = contract["new_source_arm"]
    _require(plan["id"] == EXPERIMENT and plan["dataset"] == "BNCI2014_001", "Unexpected source experiment")
    _require(plan["channels"] == [ch for ch in q14["channels"] if ch != "FCz"], "Q15 may remove FCz only")
    _require(plan["cue_window_s_half_open"] == [0.5, 2.5] and plan["n_times"] == 320 and plan["common_sampling_rate_hz"] == 160, "Q15 window/sample rate changed")
    config = copy.deepcopy(q14)
    config.update(channels=plan["channels"], cue_relative_start_s=0.5, cue_relative_stop_exclusive_s=2.5, source_trial_start_s=2.5, source_trial_stop_exclusive_s=4.5, n_times=320, q14_e002_inner_groups=plan["source_only_inner_groups"])
    config["architecture"].update(plan["architecture_changes_from_q14"])
    execution_path = ROOT / "research_runs/Q15-EXECUTION-20261003/EXECUTION_CONTRACT.json"
    execution = _read(execution_path)
    _fields(execution, {"schema_version": 1, "target_fits": 0}, "execution contract")
    transform = execution.get("shared_transform", {})
    _fields(transform, {"context_relative_s": [-1.5, 4.5], "cue_window_s": [0.5, 2.5], "common_rate_hz": 160, "channels": plan["channels"], "reference": "common_average_21", "bands": plan["frequency_bands_hz"], "output_unit": "uV", "analysis_input_unit_convention": "native_numeric_as_microvolts", "native_export_units_verified": False, "dtype": "float32", "artifact_policy": "include_all", "target_fitted_normalization": False, "baseline_correction": False}, "execution transform")
    _fields(transform.get("filter", {}), {"order": 4, "ftype": "butter", "phase": "zero", "scope": "each_real_retained_trial_context", "padlen": 27}, "execution filter")
    _fields(execution.get("csp_coordinate_rule", {}), {"name": "fixed_21_to_20_helmert", "data_dependent": False, "basis": "scipy.linalg.helmert(21, full=False)", "n_coordinates": 20, "n_components": 4, "target_fit": False}, "CSP coordinate rule")
    config.update(execution_context_relative_s=[-1.5, 4.5], execution_reference="common_average_21", execution_filter_scope="each_real_retained_trial_context", execution_filter_padlen=27, execution_contract_sha256=_sha(execution_path), execution_csp_basis="fixed_21_to_20_helmert")
    for key in ("selection_seed", "final_seeds", "max_epochs", "batch_size", "learning_rate", "weight_decay", "artifact_policy", "source_only_epoch_rule"):
        _require(plan[key] == config[key], f"Q15 hyperparameter drift: {key}")
    _require(plan["frequency_bands_hz"] == config["bands_hz"], "Q15 frequency bands drift")
    _require(config["architecture"]["n_chans"] == 21 and config["architecture"]["n_times"] == 320 and config["architecture"]["n_outputs"] == 2, "Wrong Q15 architecture shape")
    _require(config["source_subjects"] == list(range(1, 10)) and config["q14_e002_inner_groups"] == [[1, 2], [3, 4], [5, 6], [7, 8, 9]], "Wrong source subjects/folds")
    _require(config["final_seeds"] == [20260924, 20260925, 20260926] and config["max_epochs"] == 40, "Wrong Q15 fit budget")
    freeze_path = output / "pre_fit_freeze.json"
    freeze = _read(freeze_path)
    _fields(freeze, {"schema_version": 1, "experiment_id": EXPERIMENT, "status": "pre_fit_frozen_pending_commit", "external_outcomes_inspected": False, "source_only": True, "target_fits": 0, "allowed_fits": {"deep": 14, "shallow": 1, "external_target": 0}}, "pre-fit freeze")
    paths = {
        "contract_sha256": contract_path,
        "contract_checker_sha256": packet / "q15_validate_contract.py",
        "q14_config_sha256": q14_path,
        "q8_bnci_source_provenance_sha256": ROOT / "research_runs/Q8-E001/results/source_files.json",
        "q8_source_metadata_sha256": ROOT / "research_runs/Q8-E001/results/trial_metadata.csv",
        "dependency_spec_sha256": ROOT / "requirements-q15-runtime.txt",
        "bnci_loader_sha256": ROOT / "src/mi_eeg/data/bnci_epochs.py",
        "eegnet_training_helper_sha256": ROOT / "src/mi_eeg/models/eegnet_training.py",
        "metadata_auditor_sha256": ROOT / "scripts/q15_metadata_audit.py",
        "runner_sha256": ROOT / "scripts/q15_source.py",
        "q14_source_helper_sha256": ROOT / "scripts/q14_source.py",
        "execution_contract_sha256": execution_path,
        "real_metadata_adapter_sha256": ROOT / "scripts/q15_real_metadata.py",
        "context_preprocessor_sha256": ROOT / "src/mi_eeg/data/q15_context.py",
        "external_preprocessor_sha256": ROOT / "scripts/q15_preprocess_external.py",
        "csp_basis_sha256": ROOT / "src/mi_eeg/models/q15_csp.py",
        "transport_inventory_sha256": ROOT / "research_runs/Q15-PREPARATION/transport_inventory.json",
        "source_validator_sha256": ROOT / "scripts/q15_validate_source.py",
    }
    for field, path in paths.items():
        _check_hash(path, freeze.get(field))
        _committed(path)
    for name, digest in execution.get("evidence_sha256", {}).items():
        _require(Path(name).name == name, "Unsafe execution evidence path")
        evidence_path = execution_path.parent / "evidence" / name
        _check_hash(evidence_path, digest)
        _committed(evidence_path)
    _require(set(execution.get("evidence_sha256", {})) == {"cho_transfer_manifest.json", "100542.md5", "lee_transfer_manifest.json", "cho_channel_map.json", "cho_figure1.jpg", "cho_bucket_inventory.xml", "moabb_v1.7.2_Cho2017.py", "moabb_v1.7.2_Lee2019.py", "openbmi_bv_read.m", "openbmi_prep_segmentation.m"}, "Execution evidence inventory differs")
    expected_freeze_fields = {"schema_version", "experiment_id", "status", "external_outcomes_inspected", "source_only", "target_fits", "allowed_fits", "metadata_receipt_sha256", "metadata_receipt_status", "numerical_preprocessing"} | set(paths)
    _require(set(freeze) == expected_freeze_fields, "Unexpected pre-fit freeze fields")
    _require(Path(__file__).resolve() == paths["source_validator_sha256"].resolve(), "Running source validator differs from frozen validator path")
    _verify_numerical(freeze["numerical_preprocessing"], plan["frequency_bands_hz"])
    expected_counts = {"Lee2019_MI": 108, "Cho2017": 52}
    expected_receipts = {"Lee2019_MI": "Q15-V001", "Cho2017": "Q15-V002"}
    _require(set(freeze.get("metadata_receipt_sha256", {})) == set(expected_receipts), "Metadata receipt datasets differ")
    _require(set(freeze.get("metadata_receipt_status", {})) == set(expected_receipts), "Metadata receipt status datasets differ")
    for dataset, experiment in expected_receipts.items():
        path = ROOT / "results" / experiment / "metadata_audit_receipt.json"
        _check_hash(path, freeze["metadata_receipt_sha256"][dataset])
        _committed(path)
        receipt = _read(path)
        _fields(receipt, {"schema_version": 1, "dataset": dataset, "status": "metadata_passed_non_authorizing", "metadata_only": True, "raw_hashes_verified": True, "provider_inventory_verified": True, "provider_manifest_authenticated": True, "all_expected_files_hashed": True, "synthetic_fixture": False, "model_predictions_computed": False, "predictions_computed": False, "performance_metrics_computed": False, "external_prediction_authorized": False, "source_training_authorized": False, "target_fits": 0, "auditor_sha256": freeze["metadata_auditor_sha256"], "raw_adapter_sha256": freeze["real_metadata_adapter_sha256"], "execution_contract_sha256": freeze["execution_contract_sha256"], "native_numeric_calibration_verified": False, "calibration_limitations_must_be_reported": True}, f"{dataset} metadata receipt")
        _require(freeze.get("metadata_receipt_status", {}).get(dataset) == receipt["status"], "Metadata receipt status differs from freeze")
        rows, ids = receipt.get("files", []), receipt.get("expected_file_ids", [])
        _require(isinstance(rows, list) and isinstance(ids, list) and len(rows) == len(ids) == expected_counts[dataset] and len(set(ids)) == len(ids) and {row["file_id"] for row in rows} == set(ids), "Scientific receipt inventory incomplete")
        manifest_path = Path(receipt.get("provider_manifest_path", ""))
        _require(manifest_path.is_absolute(), "Provider inventory path must be absolute")
        _check_hash(manifest_path, receipt.get("provider_manifest_sha256"))
        _committed(manifest_path)
        _verify_metadata_receipt(receipt, manifest_path, dataset, plan["channels"])
    _committed(freeze_path)
    return config, freeze, _sha(freeze_path)


def _verify_numerical(record: dict, bands: dict) -> None:
    """Recreate declared coefficients without calling the EEG preprocessor."""
    import scipy
    from scipy.signal import butter
    expected = {
        "numpy_version": np.__version__, "scipy_version": scipy.__version__,
        "filter_representation": "SOS", "prototype_order": 4, "bandpass_order": 8, "sos_sections": 4,
        "filter_padtype": "odd", "filter_padlen_native_samples": 27,
        "resampling": {"implementation": "scipy.signal.resample_poly", "window": ["kaiser", 5.0], "padtype": "constant", "cval": 0.0, "native_to_common_ratios": {"250": [16, 25], "512": [5, 16], "1000": [4, 25]}, "context_samples": 960, "crop_half_open": [320, 640]},
        "native_filter_sos": {str(rate): {name: butter(4, limits, btype="bandpass", fs=rate, output="sos").tolist() for name, limits in bands.items()} for rate in (250, 512, 1000)},
    }
    _require(_same(record, expected), "Frozen numerical preprocessing differs from independent coefficients/runtime")


def _verify_source_files(root: Path, run: dict) -> None:
    inventory = _read(root / "source_files.json")
    _require(isinstance(inventory, dict) and set(inventory) == {"files"}, "Unexpected source file receipt fields")
    rows = inventory["files"]
    frozen_rows = _read(ROOT / "research_runs/Q8-E001/results/source_files.json")
    frozen = {Path(row["path"]).name: row for row in frozen_rows}
    expected_names = {f"A{subject:02d}{session}.mat" for subject in range(1, 10) for session in ("E", "T")}
    _require(len(frozen_rows) == len(frozen) == 18 and set(frozen) == expected_names, "Frozen BNCI inventory must contain exactly 18 originals")
    _require(isinstance(rows, list) and len(rows) == 18 and {row["filename"] for row in rows} == expected_names, "Source inventory missing or duplicated")
    _require([row["filename"] for row in rows] == sorted(expected_names), "Source raw inventory order differs from frozen runner")
    canonical = hashlib.sha256(json.dumps(rows, sort_keys=True).encode("utf-8")).hexdigest()
    _require(run.get("source_file_receipt_sha256") == canonical, "Run config source inventory digest differs")
    data_dir = Path(run.get("data_dir", ""))
    _require(data_dir.is_absolute() and data_dir.is_dir(), "Source raw directory unavailable")
    paths = list(data_dir.rglob("*.mat"))
    _require(len(paths) == 18 and {path.name for path in paths} == expected_names, "Source directory must contain only 18 distinct BNCI MAT files")
    actual = {path.name: path for path in paths}
    for row in rows:
        _require(isinstance(row, dict) and set(row) == {"filename", "bytes", "sha256"}, "Unexpected source raw file receipt fields")
        _require(type(row["bytes"]) is int and row["bytes"] > 0, "Invalid source MAT byte count")
        reference = frozen[row["filename"]]
        _require(row["bytes"] == reference["bytes"] and row["sha256"] == reference["sha256"], "Source MAT provenance differs from frozen Q8")
        _require(actual[row["filename"]].stat().st_size == row["bytes"], "Source MAT byte count differs")
        _check_hash(actual[row["filename"]], row["sha256"])


def _verify_metadata(root: Path, config: dict) -> pd.DataFrame:
    meta, audit = pd.read_csv(root / "source_metadata.csv"), pd.read_csv(root / "source_audit.csv")
    columns = {"sample_id", "subject", "session", "run", "trial", "label", "event_sample", "artifact_flagged"}
    _require(set(meta.columns) == columns and len(meta) == 2592 and not meta.isna().any().any(), "Source trial metadata columns/count/nulls differ")
    _require(not meta["sample_id"].duplicated().any(), "Duplicate source sample ID")
    _require(pd.api.types.is_bool_dtype(meta["artifact_flagged"]), "Artifact flags must be native booleans")
    _require(set(meta["subject"]) == set(config["source_subjects"]) and set(meta["label"]) == {1, 2} and set(meta["session"]) == set(SESSIONS), "External or unexpected source rows")
    expected_runs = {(s, session, r) for s in range(1, 10) for session in SESSIONS for r in range(6)}
    _require(set(map(tuple, meta[["subject", "session", "run"]].drop_duplicates().to_numpy())) == expected_runs, "Source run inventory incomplete")
    keys = audit[["subject", "session", "run"]]
    audit_columns = {"subject", "session", "run", "n_all_four_class_trials", "n_candidate_trials", "n_source_artifact_flags_all_classes", "n_flagged_trials", "n_rejected_trials", "n_kept_trials", "n_times_per_epoch", "n_eeg_channels", "sampling_rate_hz", "native_sampling_rate_hz", "artifact_policy", "class_counts_candidate", "class_counts_kept", "class_counts_flagged", "eeg_channel_names", "output_n_times", "output_n_channels", "common_rate", "transform_context_relative_s", "reference", "padlen", "output_channel_names", "preprocessing"} | {f"n_class_{label}_{stage}" for label in (1, 2) for stage in ("candidate", "kept", "flagged")}
    _require(set(audit.columns) == audit_columns and not audit.isna().any().any(), "Unexpected source audit columns or missing values")
    _require(len(audit) == 108 and not keys.duplicated().any() and set(map(tuple, keys.to_numpy())) == expected_runs, "Source audit run inventory differs")
    full_channels = _read(ROOT / "research_runs/Q14-E001/CONFIG.json")["channels"]
    for key, rows in meta.groupby(["subject", "session", "run"], sort=False):
        s, session, run = key
        _require(len(rows) == 24 and rows["label"].value_counts().to_dict() == {1: 12, 2: 12}, "Source binary run class counts differ")
        trials = rows["trial"].to_numpy()
        events = rows["event_sample"].to_numpy()
        _require(all(int(x) == x and 1 <= x <= 48 for x in trials) and len(set(trials)) == 24, "Source trial IDs are invalid")
        _require(all(int(x) == x and x >= 0 for x in events) and np.all(np.diff(events) > 0) and np.all(np.diff(trials) > 0), "Source events/trials must be ordered and unique")
        ids = [f"s{s:02d}_{session}_r{run}_t{int(trial):02d}" for trial in trials]
        _require(rows["sample_id"].tolist() == ids, "Source sample IDs disagree with run/trial identity")
        _require(rows["artifact_flagged"].isin([True, False]).all(), "Invalid artifact flags")
        record = audit.loc[(audit["subject"] == s) & (audit["session"] == session) & (audit["run"] == run)].iloc[0]
        expected = {"n_all_four_class_trials": 48, "n_candidate_trials": 24, "n_rejected_trials": 0, "n_kept_trials": 24, "n_times_per_epoch": 500, "n_eeg_channels": 22, "sampling_rate_hz": 250.0, "native_sampling_rate_hz": 250.0, "artifact_policy": "include_all", "n_class_1_candidate": 12, "n_class_1_kept": 12, "n_class_2_candidate": 12, "n_class_2_kept": 12, "n_flagged_trials": int(rows["artifact_flagged"].sum()), "output_n_times": 320, "output_n_channels": 21, "common_rate": 160, "reference": config["execution_reference"], "padlen": config["execution_filter_padlen"], "preprocessing": "q15_uniform_trial_context_v1"}
        for field, value in expected.items():
            _require(record[field] == value, f"Source run audit differs: {field}")
        _require(json.loads(record["eeg_channel_names"]) == full_channels, "Native source channel order differs")
        _require(json.loads(record["output_channel_names"]) == config["channels"], "Processed source channel order differs")
        _require(json.loads(record["transform_context_relative_s"]) == config["execution_context_relative_s"], "Source trial filtering context differs")
        native_flagged = record["n_source_artifact_flags_all_classes"]
        _require(int(native_flagged) == native_flagged and int(rows["artifact_flagged"].sum()) <= native_flagged <= 48, "Source native all-class artifact flag count differs")
        for field in ("class_counts_candidate", "class_counts_kept"):
            _require(json.loads(record[field]) == {"1": 12, "2": 12}, "Source audit class counts differ")
        flagged = {str(label): int(rows.loc[rows["label"] == label, "artifact_flagged"].sum()) for label in (1, 2)}
        _require(json.loads(record["class_counts_flagged"]) == flagged, "Source audit flagged class counts differ")
        _require(all(record[f"n_class_{label}_flagged"] == flagged[str(label)] for label in (1, 2)), "Source audit flagged label counts differ")
    order = [(int(row.subject), row.session, int(row.run), int(row.trial)) for row in meta.itertuples()]
    _require(order == sorted(order), "Source trial order differs from source loader")
    q8 = pd.read_csv(ROOT / "research_runs/Q8-E001/results/trial_metadata.csv")
    _require(set(q8.columns) == columns and len(q8) == 5184 and not q8.isna().any().any() and not q8["sample_id"].duplicated().any() and set(q8["label"]) == {1, 2, 3, 4}, "Frozen Q8 trial metadata is incomplete")
    expected = q8.loc[q8["label"].isin([1, 2]), list(meta.columns)].reset_index(drop=True)
    _require(meta.equals(expected), "Source native metadata/IDs differ from frozen Q8 binary trials")
    return meta


def _curve(path: Path, epochs: int, validation: bool) -> list[dict]:
    value = _read(path)
    _require(isinstance(value, dict) and set(value) == {"epochs"}, "Unexpected curve content")
    rows = value["epochs"]
    _require(isinstance(rows, list) and len(rows) == epochs, "Curve length differs from fit epoch count")
    for expected_epoch, row in enumerate(rows, 1):
        _require(set(row) == {"epoch", "train_ce", "val_ce"} and type(row["epoch"]) is int and row["epoch"] == expected_epoch, "Curve epoch fields/order differ")
        _require(isinstance(row["train_ce"], (int, float)) and not isinstance(row["train_ce"], bool) and math.isfinite(row["train_ce"]) and row["train_ce"] >= 0, "Nonfinite or negative training CE")
        if validation:
            _require(isinstance(row["val_ce"], (int, float)) and not isinstance(row["val_ce"], bool) and math.isfinite(row["val_ce"]) and row["val_ce"] >= 0, "Nonfinite or negative source validation CE")
        else:
            _require(row["val_ce"] is None, "Final fit contains target/validation selection outcomes")
    return rows


def independent_rank_epoch(curves: list[list[dict]]) -> int:
    """Average tie ranks per fold, then choose the earliest minimum mean rank."""
    _require(len(curves) == 4 and len({len(rows) for rows in curves}) == 1, "Four equal-length selection curves required")
    ranks = []
    for rows in curves:
        values = [row["val_ce"] for row in rows]
        _require(values and all(isinstance(x, (int, float)) and math.isfinite(x) for x in values), "Nonfinite selection CE")
        ranks.append([1 + sum(other < value for other in values) + (sum(other == value for other in values) - 1) / 2 for value in values])
    means = [sum(fold[index] for fold in ranks) / 4 for index in range(len(curves[0]))]
    return min(range(len(means)), key=lambda index: (means[index], index)) + 1


def _state_schema(config: dict) -> dict[str, tuple[tuple[int, ...], str, int | None]]:
    # Construction inspects architecture only; no data, fitting, or predictions.
    from braindecode.models import EEGNet
    architecture = {key: value for key, value in config["architecture"].items() if key not in {"library", "model"}}
    import torch
    with torch.random.fork_rng(devices=[]):
        model = EEGNet(**architecture)
    return {name: (tuple(tensor.shape), str(tensor.dtype), int(tensor) if name.endswith("num_batches_tracked") else None) for name, tensor in model.state_dict().items()}


def _checkpoint(path: Path, model: str, seed: int, epochs: int, schema: dict, training_batches: int) -> None:
    import torch
    checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    _require(isinstance(checkpoint, dict) and set(checkpoint) == {"state_dict", "model", "seed", "epochs"}, "Unexpected checkpoint payload")
    _fields(checkpoint, {"model": model, "seed": seed, "epochs": epochs}, "checkpoint")
    expected = {("eegnet." + name if model == "MU_BETA_SHARED" else name): spec for name, spec in schema.items()}
    state = checkpoint["state_dict"]
    _require(isinstance(state, dict) and set(state) == set(expected), "Checkpoint tensor keys differ from Q15 architecture")
    for name, (shape, dtype, initial_batches) in expected.items():
        tensor = state[name]
        _require(isinstance(tensor, torch.Tensor) and tuple(tensor.shape) == shape and str(tensor.dtype) == dtype, f"Checkpoint tensor shape/dtype differs: {name}")
        _require(bool(torch.isfinite(tensor).all()), f"Nonfinite checkpoint tensor: {name}")
        if name.endswith("num_batches_tracked"):
            _require(int(tensor) == initial_batches + training_batches, "BatchNorm training count differs from declared source fit")
        elif name.endswith("running_var"):
            _require(bool((tensor >= 0).all()), "Invalid BatchNorm running variance")


def _neural_fit(path: Path, required: dict, validation: bool, schema: dict, batch_size: int) -> list[dict]:
    record = _read(path / "manifest.json")
    _fields(record, {**required, "status": "complete"}, "neural manifest")
    _require(set(record) == set(required) | {"status", "checkpoint_sha256", "curve_sha256"}, "Unexpected neural manifest fields")
    _check_hash(path / "checkpoint.pt", record["checkpoint_sha256"])
    _check_hash(path / "curve.json", record["curve_sha256"])
    rows = _curve(path / "curve.json", required["epochs"], validation)
    training_batches = required["epochs"] * math.ceil(288 * len(required["train_subjects"]) / batch_size)
    _checkpoint(path / "checkpoint.pt", required["model"], required["seed"], required["epochs"], schema, training_batches)
    return rows


def _csp(path: Path, required: dict) -> str:
    record = _read(path / "manifest.json")
    _fields(record, {**required, "status": "complete", "n_source_trials": 2592}, "CSP manifest")
    _require(set(record) == set(required) | {"status", "n_source_trials", "model_sha256"}, "Unexpected CSP manifest fields")
    artifact = path / "model.joblib"
    _check_hash(artifact, record["model_sha256"])
    import joblib
    from mne.decoding import CSP
    from scipy.linalg import helmert
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    from mi_eeg.models.q15_csp import FixedCARBasis
    pipeline = joblib.load(artifact)
    _require(isinstance(pipeline, Pipeline) and [name for name, _ in pipeline.steps] == ["fixed_car_basis", "csp", "scaler", "lda"], "Unexpected CSP pipeline")
    basis_step, csp, scaler, lda = [step for _, step in pipeline.steps]
    _require(type(basis_step) is FixedCARBasis and type(basis_step.n_channels) is int and basis_step.n_channels == 21, "Unexpected fixed CAR basis")
    basis = np.asarray(basis_step.basis)
    _require(basis.shape == (20, 21) and np.array_equal(basis, helmert(21, full=False)) and np.allclose(basis @ basis.T, np.eye(20), rtol=0, atol=1e-12) and np.allclose(basis @ np.ones(21), 0, rtol=0, atol=1e-12), "Fixed CAR basis differs from the full rank20 Helmert subspace")
    _require(isinstance(csp, CSP) and isinstance(scaler, StandardScaler) and isinstance(lda, LinearDiscriminantAnalysis), "Unexpected CSP estimator types")
    for field, value in {"n_components": 4, "reg": None, "log": True, "cov_est": "concat", "norm_trace": False, "rank": "full", "component_order": "mutual_info"}.items():
        _require(getattr(csp, field) == value, f"CSP parameter differs: {field}")
    _require(np.array_equal(csp.classes_, [1, 2]) and np.array_equal(lda.classes_, [1, 2]) and lda.solver == "svd", "CSP/LDA labels or solver differ")
    for field, shape in (("filters_", (20, 20)), ("patterns_", (20, 20)), ("mean_", (4,)), ("std_", (4,))):
        value = getattr(csp, field)
        _require(np.shape(value) == shape and np.isfinite(value).all(), f"CSP fitted shape/nonfinite: {field}")
    _require(scaler.n_features_in_ == lda.n_features_in_ == 4 and scaler.with_mean and scaler.with_std, "CSP feature count/scaling differs")
    for estimator, field, shape in ((scaler, "mean_", (4,)), (scaler, "scale_", (4,)), (scaler, "var_", (4,)), (lda, "coef_", (1, 4)), (lda, "intercept_", (1,)), (lda, "means_", (2, 4)), (lda, "priors_", (2,)), (lda, "xbar_", (4,)), (lda, "scalings_", (4, 1)), (lda, "explained_variance_ratio_", (1,))):
        value = getattr(estimator, field)
        _require(np.shape(value) == shape and np.isfinite(value).all(), f"CSP classifier fitted shape/nonfinite: {field}")
    _require(np.all(scaler.scale_ > 0) and np.all(csp.mean_ > 0) and np.all(csp.std_ >= 0), "Invalid CSP scaler scale or source power moments")
    _require(np.all(scaler.var_ >= 0) and scaler.n_samples_seen_ == 2592 and np.array_equal(lda.priors_, [0.5, 0.5]), "CSP source sample count, variance, or class priors differ")
    return record["model_sha256"]


def _runtime(run: dict) -> None:
    runtime = run.get("runtime", {})
    packages = runtime.get("packages", {})
    dependency_path = ROOT / "requirements-q15-runtime.txt"
    pins = dict(line.strip().split("==", 1) for line in dependency_path.read_text().splitlines() if line.strip() and not line.lstrip().startswith("#") and "==" in line)
    for package in ("numpy", "scipy", "mne", "moabb", "braindecode", "scikit-learn"):
        _require(packages.get(package) == pins[package], f"Training runtime dependency differs from frozen specification: {package}")
    for package in ("torch", "torchaudio"):
        _require(packages.get(package) == "2.8.0+cu128", f"Training runtime dependency differs from frozen CUDA template: {package}")
    _require(isinstance(runtime.get("python"), str) and runtime["python"].startswith("3.12."), "Training Python runtime differs from frozen Python 3.12 environment")
    _require(run["device"] in {"cpu", "cuda"}, "Unexpected training device")
    if run["device"] == "cuda":
        _require(runtime.get("cuda_available") is True and isinstance(runtime.get("cuda_device_name"), str) and bool(runtime["cuda_device_name"].strip()) and runtime.get("torch_cuda_runtime") == "12.8", "CUDA run lacks frozen GPU/runtime provenance")


def _source_ledger(output: Path, config: dict) -> set[str]:
    """Reject extra fits/outcomes before deserializing any fitted model."""
    root = output / "source"
    _require(output.is_dir() and root.is_dir() and not output.is_symlink() and not root.is_symlink(), "Source output missing or symlinked")
    output.resolve().relative_to(ROOT.resolve())
    _require({path.name for path in output.iterdir()} <= {"pre_fit_freeze.json", "source", "source_validation.json"}, "Unexpected/missing source output artifacts or external outcomes")
    _require(not any(path.is_symlink() for path in output.iterdir()), "Symlinked source output artifact")
    allowed = {"run_config.json", "source_files.json", "source_metadata.csv", "source_audit.csv", "source_stage_complete.json"}
    for model in MODELS:
        base = Path(model) / "all_source"
        allowed.add((base / "selection.json").as_posix())
        jobs = [base / f"inner_{fold:02d}" for fold in range(1, len(config["q14_e002_inner_groups"]) + 1)]
        jobs += [base / f"final_seed_{seed}" for seed in config["final_seeds"]]
        allowed.update((job / name).as_posix() for job in jobs for name in ("manifest.json", "curve.json", "checkpoint.pt"))
    allowed.update({"CSP4_LDA/all_source/manifest.json", "CSP4_LDA/all_source/model.joblib"})
    paths = list(root.rglob("*"))
    _require(not any(path.is_symlink() for path in paths), "Symlinked source artifact or directory")
    files = {path.relative_to(root).as_posix() for path in paths if path.is_file()}
    _require(files == allowed, "Unexpected/missing source artifacts, fits, or external predictions")
    allowed_dirs = {parent.as_posix() for name in allowed for parent in Path(name).parents if parent != Path(".")}
    dirs = {path.relative_to(root).as_posix() for path in paths if path.is_dir()}
    _require(dirs == allowed_dirs and all(path.is_file() or path.is_dir() for path in paths), "Unexpected/missing source artifact directories")
    return allowed


def validate_source(output_root: Path | None = None, *, write_report: bool = True) -> dict:
    output = Path(output_root) if output_root else ROOT / "results/Q15-E005"
    config, freeze, protocol_sha = _verify_protocol(output)
    root = output / "source"
    _source_ledger(output, config)
    run = _read(root / "run_config.json")
    expected_run = {"experiment_id": EXPERIMENT, "status": "source_fitting_not_external_validation", "pre_fit_freeze_sha256": protocol_sha, "contract_sha256": freeze["contract_sha256"], "runner_sha256": freeze["runner_sha256"], "source_config": config, "execution_contract_sha256": freeze["execution_contract_sha256"]}
    _fields(run, expected_run, "source run config")
    _require(set(run) == set(expected_run) | {"source_file_receipt_sha256", "data_dir", "device", "runtime"}, "Unexpected source run config fields")
    _runtime(run)
    _verify_source_files(root, run)
    meta = _verify_metadata(root, config)
    completion = _read(root / "source_stage_complete.json")
    _fields(completion, {"experiment_id": EXPERIMENT, "status": "fits_complete_pending_independent_source_validation", "deep_fit_count": 14, "shallow_fit_count": 1, "external_predictions_computed": False, "external_prediction_authorized": False, "pre_fit_freeze_sha256": protocol_sha}, "source completion")
    expected_completion_fields = {"experiment_id", "status", "deep_fit_count", "shallow_fit_count", "external_predictions_computed", "external_prediction_authorized", "pre_fit_freeze_sha256", "completed_at_utc"}
    _require(set(completion) == expected_completion_fields, "Unexpected source completion fields")
    _require(datetime.fromisoformat(completion["completed_at_utc"]).tzinfo is not None, "Completion timestamp lacks timezone")
    schema = _state_schema(config)
    source, groups = config["source_subjects"], config["q14_e002_inner_groups"]
    selected_epochs, checkpoints = {}, {}
    for model in MODELS:
        base = root / model / "all_source"
        curves = []
        for fold, subjects in enumerate(groups, 1):
            train_subjects = [s for s in source if s not in subjects]
            train_ids = meta.loc[meta["subject"].isin(train_subjects), "sample_id"]
            val_ids = meta.loc[meta["subject"].isin(subjects), "sample_id"]
            _require(set(train_ids).isdisjoint(val_ids) and len(train_ids) + len(val_ids) == 2592, "Source inner partition overlap/incomplete")
            job = base / f"inner_{fold:02d}"
            required = {"experiment_id": EXPERIMENT, "model": model, "inner_fold": fold, "train_subjects": train_subjects, "validation_subjects": subjects, "train_sample_ids_sha256": _ids(train_ids), "validation_sample_ids_sha256": _ids(val_ids), "seed": config["selection_seed"], "epochs": config["max_epochs"], "protocol_sha256": protocol_sha}
            curves.append(_neural_fit(job, required, True, schema, config["batch_size"]))
        selected = independent_rank_epoch(curves)
        expected_selection = {"experiment_id": EXPERIMENT, "model": model, "source_subjects": source, "validation_groups": groups, "selected_epoch": selected, "selection_rule": config["source_only_epoch_rule"], "inner_curve_sha256": [_sha(base / f"inner_{fold:02d}/curve.json") for fold in range(1, 5)], "protocol_sha256": protocol_sha}
        _require(_same(_read(base / "selection.json"), expected_selection), "Independent source-only rank selection differs")
        selected_epochs[model], checkpoints[model] = selected, {}
        for seed in config["final_seeds"]:
            job = base / f"final_seed_{seed}"
            required = {"experiment_id": EXPERIMENT, "model": model, "train_subjects": source, "train_sample_ids_sha256": _ids(meta["sample_id"]), "seed": seed, "epochs": selected, "protocol_sha256": protocol_sha}
            _neural_fit(job, required, False, schema, config["batch_size"])
            checkpoints[model][str(seed)] = _sha(job / "checkpoint.pt")
    csp_path = root / "CSP4_LDA/all_source"
    csp_sha = _csp(csp_path, {"experiment_id": EXPERIMENT, "model": "CSP4_LDA", "train_subjects": source, "train_sample_ids_sha256": _ids(meta["sample_id"]), "protocol_sha256": protocol_sha})
    files = _source_ledger(output, config)
    report = {"schema_version": 1, "experiment_id": EXPERIMENT, "status": "source_validated_non_authorizing", "passed": True, "counts": {"deep_inner": 8, "deep_final": 6, "shallow": 1, "predictions": 0}, "deep_fit_count": 14, "shallow_fit_count": 1, "source_only": True, "target_fits": 0, "external_prediction_authorized": False, "external_predictions_computed": False, "pre_fit_freeze_sha256": protocol_sha, "contract_sha256": freeze["contract_sha256"], "source_runner_sha256": freeze["runner_sha256"], "validator_sha256": _sha(Path(__file__)), "source_files_sha256": _sha(root / "source_files.json"), "source_metadata_sha256": _sha(root / "source_metadata.csv"), "source_audit_sha256": _sha(root / "source_audit.csv"), "source_run_config_sha256": _sha(root / "run_config.json"), "source_stage_complete_sha256": _sha(root / "source_stage_complete.json"), "selected_epochs": selected_epochs, "checkpoints": checkpoints, "csp_model_sha256": csp_sha, "source_sample_ids_sha256": _ids(meta["sample_id"]), "interpretation": "Artifact/partition validation only; external evaluation requires a separate committed checkpoint and inference freeze."}
    artifact_paths = [output / "pre_fit_freeze.json"] + [root / name for name in sorted(files)]
    report["artifact_sha256"] = {path.resolve().relative_to(ROOT.resolve()).as_posix(): _sha(path) for path in artifact_paths}
    report["execution_contract_sha256"] = freeze["execution_contract_sha256"]
    report["csp_coordinate_rule"] = config["execution_csp_basis"]
    report["calibration_verified"] = False
    if write_report:
        path = output / "source_validation.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Q15-E005 directory containing pre_fit_freeze.json and source/")
    parser.add_argument("--no-write", action="store_true", help="Read-only validation; do not save a report")
    args = parser.parse_args()
    print(json.dumps(validate_source(args.output, write_report=not args.no_write), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
