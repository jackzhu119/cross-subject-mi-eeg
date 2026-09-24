"""Q14-E002 frozen BNCI-to-PhysioNet zero-shot inference (no target fitting).

Requires a validated, hash-locked BNCI source freeze receipt before any EDF
file is fetched or opened. Only PhysioNet runs 4/8/12 enter the trial stream.
Each target subject is written atomically and independently for resumption.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mne
import numpy as np
import pandas as pd

from scripts.q14_source import CONFIG, DEEP_MODELS, E001_ROOT, E002_ROOT, runtime_receipt, sha256

EXTERNAL_ROOT = E002_ROOT / "external"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)


def _atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(tmp, index=False)
    os.replace(tmp, path)


def parse_official_checksums(contents: str) -> dict[str, str]:
    """Parse PhysioNet's versioned SHA256SUMS; only EDF entries are used."""
    rows = {}
    for line in contents.splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64})\s+S(\d{3})/(S\d{3}R\d{2}\.edf)", line.strip())
        if not match:
            continue
        digest, directory, filename = match.groups()
        if filename[:4] != "S" + directory:
            raise AssertionError("Official PhysioNet checksum path is internally inconsistent")
        if filename in rows:
            raise AssertionError("Duplicate EDF in official checksum manifest")
        rows[filename] = digest.lower()
    required = {
        f"S{subject:03d}R{run:02d}.edf"
        for subject in range(1, 110)
        for run in (4, 8, 12)
    }
    missing = required - rows.keys()
    if missing:
        raise AssertionError(
            "Official PhysioNet manifest lacks predeclared imagery EDF coverage: "
            f"{sorted(missing)[:5]}"
        )
    return rows


def official_checksums(config: dict) -> dict[str, str]:
    file = EXTERNAL_ROOT / "physionet_SHA256SUMS.txt"
    if not file.exists():
        with urllib.request.urlopen(
            config["external_checksum_manifest_url"], timeout=60
        ) as response:
            contents = response.read()
        parsed = parse_official_checksums(contents.decode("ascii"))
        tmp = file.with_suffix(file.suffix + ".tmp")
        tmp.write_bytes(contents)
        os.replace(tmp, file)
        return parsed
    return parse_official_checksums(file.read_text(encoding="ascii"))


def verify_freeze(config: dict) -> dict:
    freeze = _read(E002_ROOT / "freeze_receipt.json")
    if freeze["status"] != "FROZEN_BEFORE_EXTERNAL_DATA_ACCESS":
        raise AssertionError("Q14 source models are not frozen")
    expected = {
        "experiment_id": "Q14-E002",
        "models": config["models"],
        "target_dataset": config["external_dataset"],
        "target_runs": config["external_runs"],
        "target_subjects": config["external_subjects"],
        "primary_contrast": config["external_primary_contrast"],
        "external_target_fit_count": 0,
        "config_sha256": sha256(CONFIG),
        "source_runner_sha256": sha256(ROOT / "scripts/q14_source.py"),
        "external_runner_sha256": sha256(Path(__file__)),
        "batch_runner_sha256": sha256(ROOT / "scripts/q14_batch.py"),
        "contract_tests_sha256": sha256(ROOT / "tests/test_q14_external_protocol.py"),
        "metadata_audit_sha256": sha256(ROOT / "research_runs/Q14-E001/METADATA_AUDIT.json"),
        "validator_sha256": sha256(ROOT / "scripts/q14_validate.py"),
        "source_validation_report_sha256": sha256(E002_ROOT / "source/validation_report.json"),
        "q14_e001_validation_report_sha256": sha256(E001_ROOT / "validation_report.json"),
        "source_files_sha256": sha256(E002_ROOT / "source/source_files.json"),
        "source_metadata_sha256": sha256(E002_ROOT / "source/source_metadata.csv"),
        "source_run_config_sha256": sha256(E002_ROOT / "source/run_config.json"),
    }
    for key, value in expected.items():
        if freeze.get(key) != value:
            raise AssertionError(f"Q14 freeze mismatch: {key}")
    for model in DEEP_MODELS:
        selection = _read(E002_ROOT / "source" / model / "all_source" / "selection.json")
        if freeze["selected_epochs"][model] != selection["selected_epoch"]:
            raise AssertionError("Selected epoch changed after source freeze")
        for seed in config["final_seeds"]:
            file = (
                E002_ROOT / "source" / model / "all_source" / f"final_seed_{seed}" / "checkpoint.pt"
            )
            if freeze["checkpoints"][model][str(seed)] != sha256(file):
                raise AssertionError("Frozen model checkpoint changed")
    csp = E002_ROOT / "source/CSP4_LDA/all_source/model.joblib"
    if freeze["csp_model_sha256"] != sha256(csp):
        raise AssertionError("Frozen CSP checkpoint changed")
    return freeze


def _event_epochs(
    raw, config: dict, band: str, events: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    filt = raw.copy()
    low, high = config["bands_hz"][band]
    filt.filter(
        l_freq=float(low),
        h_freq=float(high),
        method="iir",
        iir_params={"order": config["filter"]["order"], "ftype": config["filter"]["ftype"]},
        phase=config["filter"]["phase"],
        verbose=False,
    )
    epochs = mne.Epochs(
        filt,
        events,
        event_id=config["external_event_map"],
        tmin=config["cue_relative_start_s"],
        tmax=config["cue_relative_stop_exclusive_s"] - 1 / config["common_rate_hz"],
        baseline=None,
        reject_by_annotation=False,
        preload=True,
        verbose=False,
    )
    if len(epochs) != len(events):
        raise AssertionError(
            "External event lacked a complete fixed 3 s epoch; stop rather than silently exclude"
        )
    values = epochs.get_data(copy=True).astype(np.float32)
    if values.shape != (len(events), len(config["channels"]), config["n_times"]):
        raise AssertionError(f"External epoch shape mismatch: {values.shape}")
    if not np.isfinite(values).all():
        raise AssertionError("Nonfinite external EEG after filtering")
    return values * config["volts_to_microvolts"], epochs.events[:, 2].copy()


def load_one_external_subject(
    subject: int, data_dir: Path, config: dict, checksums: dict[str, str]
):
    """Fetch and inspect only the three predeclared imagery runs; no estimator fit."""
    from mne.datasets import eegbci

    if subject not in range(1, 110) or config["external_runs"] != [4, 8, 12]:
        raise AssertionError("External subject/run scope changed")
    files = eegbci.load_data(
        subjects=subject,
        runs=config["external_runs"],
        path=str(data_dir),
        update_path=False,
        verbose="ERROR",
    )
    by_run = {}
    for file in map(Path, files):
        match = re.search(r"R(\d{2})\.edf$", file.name, re.IGNORECASE)
        if not match or int(match.group(1)) not in config["external_runs"]:
            raise AssertionError(f"Unexpected EDF filename/run: {file.name}")
        by_run[int(match.group(1))] = file
    if set(by_run) != set(config["external_runs"]):
        raise AssertionError(f"Missing external imagery run for S{subject:03d}")
    chunks = {band: [] for band in config["bands_hz"]}
    metadata = []
    file_records = []
    for run in config["external_runs"]:
        file = by_run[run]
        file_hash = sha256(file)
        if checksums.get(file.name) != file_hash:
            raise AssertionError(
                f"EDF differs from official PhysioNet v1.0.0 checksum: {file.name}"
            )
        file_records.append(
            {
                "subject": subject,
                "run": run,
                "filename": file.name,
                "bytes": file.stat().st_size,
                "sha256": file_hash,
            }
        )
        raw = mne.io.read_raw_edf(file, preload=True, verbose=False)
        eegbci.standardize(raw)
        if not np.isclose(raw.info["sfreq"], config["common_rate_hz"]):
            raise AssertionError("External sampling rate changed")
        if not set(config["channels"]).issubset(raw.ch_names):
            missing = sorted(set(config["channels"]) - set(raw.ch_names))
            raise AssertionError(f"Missing predeclared external EEG channels: {missing}")
        raw.pick_channels(config["channels"], ordered=True, verbose=False)
        if raw.ch_names != config["channels"] or set(raw.get_channel_types()) != {"eeg"}:
            raise AssertionError("External channel names/order/kind differ from BNCI contract")
        events, _ = mne.events_from_annotations(
            raw, event_id=config["external_event_map"], verbose=False
        )
        if len(events) < 2 or set(events[:, 2]) != {1, 2}:
            raise AssertionError(
                f"External run has missing left/right events: S{subject:03d}R{run:02d}"
            )
        reference_labels = None
        for band in config["bands_hz"]:
            values, labels = _event_epochs(raw, config, band, events)
            if reference_labels is None:
                reference_labels = labels
            elif not np.array_equal(labels, reference_labels):
                raise AssertionError("Bands produced different external events/order")
            chunks[band].append(values)
        for trial, (event, label) in enumerate(zip(events, reference_labels), 1):
            metadata.append(
                {
                    "sample_id": f"physio_s{subject:03d}_r{run:02d}_t{trial:03d}",
                    "subject": subject,
                    "run": run,
                    "trial": trial,
                    "label": int(label),
                    "event_sample": int(event[0]),
                }
            )
        del raw
    frame = pd.DataFrame(metadata)
    if frame.empty or frame["sample_id"].duplicated().any():
        raise AssertionError("Empty/duplicated target subject trials")
    arrays = {band: np.concatenate(parts, axis=0) for band, parts in chunks.items()}
    if any(values.shape[0] != len(frame) for values in arrays.values()):
        raise AssertionError("External arrays and trial metadata misaligned")
    return arrays, frame, file_records


def _load_source_models(config: dict, device):
    import joblib

    from scripts.q14_source import _load_model

    root = E002_ROOT / "source"
    deep = {
        (model, seed): _load_model(
            root / model / "all_source" / f"final_seed_{seed}" / "checkpoint.pt",
            model,
            config,
            device,
        )
        for model in DEEP_MODELS
        for seed in config["final_seeds"]
    }
    csp = joblib.load(root / "CSP4_LDA/all_source/model.joblib")
    if list(csp.named_steps["lda"].classes_) != [1, 2]:
        raise AssertionError("Frozen CSP binary class order differs")
    return deep, csp


def _subject_predictions(arrays, meta, deep, csp, config, device):
    import torch

    from mi_eeg.models.eegnet_training import predict_probabilities

    rows = []
    for model_name in DEEP_MODELS:
        if model_name == "BROAD_EEGNET":
            x = torch.from_numpy(arrays["broad"]).to(device)
        else:
            x = torch.from_numpy(np.stack([arrays["mu"], arrays["beta"]], axis=1)).to(device)
        for seed in config["final_seeds"]:
            probabilities = predict_probabilities(
                deep[(model_name, seed)], x, range(len(meta)), config["batch_size"]
            )
            rows.append(_make_frame(meta, model_name, seed, probabilities))
        del x
    probabilities = csp.predict_proba(arrays["broad"].astype(np.float64))
    rows.append(_make_frame(meta, "CSP4_LDA", "deterministic", probabilities))
    return pd.concat(rows, ignore_index=True)


def _make_frame(meta, model_name, seed, probabilities):
    if probabilities.shape != (len(meta), 2) or not np.isfinite(probabilities).all():
        raise AssertionError("Invalid external model probabilities")
    if not np.allclose(probabilities.sum(1), 1, atol=1e-5):
        raise AssertionError("External probabilities do not sum to one")
    frame = meta.copy()
    frame["experiment_id"] = "Q14-E002"
    frame["model"] = model_name
    frame["seed"] = seed
    frame["p_left"] = probabilities[:, 0]
    frame["p_right"] = probabilities[:, 1]
    frame["predicted_label"] = np.argmax(probabilities, axis=1) + 1
    return frame


def run_external(data_dir: Path, device_name: str) -> None:
    import torch

    config = _read(CONFIG)
    verify_freeze(config)  # Hard gate BEFORE target loader/import/fetch.
    freeze_sha = sha256(E002_ROOT / "freeze_receipt.json")
    device = torch.device(device_name)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    EXTERNAL_ROOT.mkdir(parents=True, exist_ok=True)
    checksums = official_checksums(config)
    official_manifest_sha = sha256(EXTERNAL_ROOT / "physionet_SHA256SUMS.txt")
    run_config = {
        "experiment_id": "Q14-E002",
        "config_sha256": sha256(CONFIG),
        "freeze_receipt_sha256": freeze_sha,
        "runner_sha256": sha256(Path(__file__)),
        "data_dir": str(data_dir.resolve()),
        "device": device_name,
        "subjects": list(range(1, 110)),
        "runs": config["external_runs"],
        "official_checksum_manifest_sha256": official_manifest_sha,
        "runtime": runtime_receipt(),
    }
    lock = EXTERNAL_ROOT / "run_config.json"
    if lock.exists() and _read(lock) != run_config:
        raise AssertionError("Existing external run_config differs; do not mix protocols")
    _atomic_json(lock, run_config)
    deep, csp = _load_source_models(config, device)
    for subject in range(1, 110):
        output = EXTERNAL_ROOT / f"subject_{subject:03d}"
        receipt_path = output / "receipt.json"
        prediction_file = output / "predictions.csv"
        if receipt_path.exists():
            prior = _read(receipt_path)
            if (
                prior.get("status") == "complete"
                and prior.get("subject") == subject
                and prior.get("freeze_receipt_sha256") == freeze_sha
                and prediction_file.exists()
                and prior.get("predictions_sha256") == sha256(prediction_file)
            ):
                print(f"S{subject:03d}: verified complete, skip", flush=True)
                continue
            raise AssertionError(f"Existing external subject output corrupted/mismatched: {output}")
        arrays, meta, files = load_one_external_subject(subject, data_dir, config, checksums)
        frame = _subject_predictions(arrays, meta, deep, csp, config, device)
        output.mkdir(parents=True, exist_ok=True)
        _atomic_csv(prediction_file, frame)
        _atomic_json(
            receipt_path,
            {
                "status": "complete",
                "subject": subject,
                "n_trials": len(meta),
                "n_prediction_rows": len(frame),
                "run_counts": {str(k): int(v) for k, v in meta.groupby("run").size().items()},
                "class_counts": {str(k): int(v) for k, v in meta.groupby("label").size().items()},
                "source_models": config["models"],
                "external_target_fit_count": 0,
                "freeze_receipt_sha256": freeze_sha,
                "official_checksum_manifest_sha256": official_manifest_sha,
                "predictions_sha256": sha256(prediction_file),
                "edf_files": files,
                "completed_at_utc": datetime.now(UTC).isoformat(),
            },
        )
        print(f"S{subject:03d}: {len(meta)} trials, {len(frame)} prediction rows", flush=True)
    frames = [
        pd.read_csv(EXTERNAL_ROOT / f"subject_{subject:03d}/predictions.csv")
        for subject in range(1, 110)
    ]
    aggregate = pd.concat(frames, ignore_index=True)
    _atomic_csv(EXTERNAL_ROOT / "predictions.csv", aggregate)
    _atomic_json(
        EXTERNAL_ROOT / "completion_receipt.json",
        {
            "status": "all_109_subjects_inferred",
            "experiment_id": "Q14-E002",
            "n_subjects": 109,
            "n_prediction_rows": len(aggregate),
            "freeze_receipt_sha256": freeze_sha,
            "aggregate_predictions_sha256": sha256(EXTERNAL_ROOT / "predictions.csv"),
            "external_target_fit_count": 0,
            "completed_at_utc": datetime.now(UTC).isoformat(),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    args = parser.parse_args()
    run_external(args.data_dir, args.device)


if __name__ == "__main__":
    main()
