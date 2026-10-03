"""Frozen, local-only Q15 external epochs and independent raw-to-array replay.

Writing an epoch requires both real metadata audits and a byte-identical
committed pre-fit freeze. A transport receipt, caller's boolean, or synthetic
fixture cannot release this gate. No fitted target transform is implemented.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT, ROOT / "src"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from mi_eeg.data.q15_context import (
    BANDS,
    preprocessing_contract,
    select_channels,
    sha256_file,
    transform_context,
)
from scripts import q15_source

DATASETS = {"Cho2017": (52, [1]), "Lee2019_MI": (54, [1, 2])}
METADATA_COLUMNS = (
    "sample_id", "subject", "session", "run", "label", "file_id", "raw_sha256",
    "cue_sample_native", "trial", "event_sample", "artifact_flagged",
)


def _json(path: Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("Expected a JSON object")
    return value


def _real_auditor():
    path = ROOT / "scripts/q15_real_metadata.py"
    spec = importlib.util.spec_from_file_location("q15_real_metadata_for_epochs", path)
    if spec is None or spec.loader is None:
        raise AssertionError("Real metadata auditor is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _execution_gate() -> dict[str, dict]:
    """Replay real audits and verify every freeze input against committed HEAD."""
    q15_source._verify_committed_freeze()
    preprocessing_contract()
    receipts = {dataset: _json(path) for dataset, path in q15_source.AUDIT_RECEIPTS.items()}
    for dataset, receipt in receipts.items():
        if receipt.get("status") != "metadata_passed_non_authorizing":
            raise AssertionError("Real metadata audit has not passed")
        if receipt.get("synthetic_fixture") is not False or receipt.get("target_fits") != 0:
            raise AssertionError("Synthetic or fitted-target receipt is forbidden")
        count, sessions = DATASETS[dataset]
        files = receipt.get("files", [])
        if len(files) != count * len(sessions):
            raise AssertionError("Complete declared external cohort is required")
        if {(row.get("subject"), int(row.get("session", 0))) for row in files} != {
            (subject, session) for subject in range(1, count + 1) for session in sessions
        }:
            raise AssertionError("External audit cohort subject/session identity changed")
    return receipts


def _native_integer_vector(values, name: str) -> np.ndarray:
    values = np.asarray(values).reshape(-1)
    if not np.issubdtype(values.dtype, np.number) or np.iscomplexobj(values) or not np.isfinite(values).all():
        raise ValueError(f"Invalid {name}")
    if not np.equal(values, np.floor(values)).all():
        raise ValueError(f"Noninteger {name}")
    if np.any(values < -(2 ** 63)) or np.any(values >= 2 ** 63):
        raise ValueError(f"Unrepresentable {name}")
    return values.astype(np.int64)


def _decode_file(record: dict, dataset: str) -> tuple[dict[str, np.ndarray], pd.DataFrame]:
    """Decode signals independently of the metadata adapter and compare events."""
    path = Path(record["path"])
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise AssertionError("Audited raw original is missing or unsafe")
    if sha256_file(path) != record["sha256"]:
        raise AssertionError("Audited raw original changed before preprocessing")
    auditor = _real_auditor()
    audited = auditor.audit_raw_file(path, dataset, record["file_id"])
    if audited != record:
        raise AssertionError("Real file metadata cannot be reproduced")
    subject, session = int(record["subject"]), int(record["session"])
    events = record.get("events", [])
    if not events or len({event["sample_id"] for event in events}) != len(events):
        raise AssertionError("Raw audit must contain unique operational trial identities")
    decoded = []
    if dataset == "Lee2019_MI":
        train = loadmat(path, variable_names=["EEG_MI_train"], mat_dtype=True)["EEG_MI_train"][0, 0]
        signal = np.asarray(train["x"])
        names = [str(np.asarray(cell).squeeze().item()) for cell in train["chan"].ravel()]
        cues = _native_integer_vector(train["t"], "Lee cue samples") - 1
        native_labels = _native_integer_vector(train["y_dec"], "Lee label codes")
        sfreq = float(train["fs"].item())
        if sfreq != float(record["sampling_rate_hz"]) or names != record["channels"]:
            raise AssertionError("Lee independent channel/rate decode disagrees with audit")
        if signal.ndim != 2 or signal.shape[1] != len(names) or len(cues) != len(native_labels):
            raise AssertionError("Lee independent signal/event shape mismatch")
        if not np.isin(native_labels, (1, 2)).all() or np.any(np.diff(cues) <= 0):
            raise AssertionError("Lee offline training trial labels/order changed")
        selected = select_channels(signal.T, names)
        for index, (cue, label) in enumerate(zip(cues, native_labels), 1):
            canonical = 2 if label == 1 else 1
            decoded.append((int(cue), canonical, index, selected, None))
    elif dataset == "Cho2017":
        eeg = loadmat(path, variable_names=["eeg"], simplify_cells=True)["eeg"]
        sfreq = float(eeg["srate"])
        n_trials = int(eeg["n_imagery_trials"])
        marker_values = np.asarray(eeg["imagery_event"]).reshape(-1)
        markers = np.flatnonzero(marker_values)
        if sfreq != 512 or sfreq != float(record["sampling_rate_hz"]) or n_trials != len(markers):
            raise AssertionError("Cho independent native event/rate decode disagrees with audit")
        for name, label in (("imagery_left", 1), ("imagery_right", 2)):
            signal = np.asarray(eeg[name])
            if signal.ndim != 2 or signal.shape[0] != 68 or signal.shape[1] != n_trials * 3584:
                raise AssertionError("Cho retained 68-channel seven-second trial layout changed")
            if not np.array_equal(markers, 1023 + 3584 * np.arange(n_trials)):
                raise AssertionError("Cho operational cue markers changed")
            names = list(auditor.CHO_CHANNELS)
            if names != record["channels"] or len(names) != 64:
                raise AssertionError("Cho provider figure channel mapping changed")
            selected = select_channels(signal[:64], names)
            for index, cue in enumerate(markers, 1):
                bounds = ((index - 1) * 3584, index * 3584)
                decoded.append((int(cue), label, index, selected, bounds))
    else:
        raise ValueError("Unsupported Q15 dataset")
    if len(decoded) != len(events):
        raise AssertionError("Independent decoded trial count differs from real raw audit")
    arrays = {band: [] for band in BANDS}
    rows = []
    for event, (cue, label, trial, signal, bounds) in zip(events, decoded):
        label_name = "left_hand" if label == 1 else "right_hand"
        if event["onset_sample"] != cue or event["label"] != label_name:
            raise AssertionError("Independent native cue/label decode disagrees with real audit")
        if event.get("trial_ordinal") != trial:
            raise AssertionError("Independent native trial identity disagrees with real audit")
        expected_id = (f"s{subject:02d}_{session}_retained_{label}_t{trial:03d}"
                       if dataset == "Cho2017" else
                       f"s{subject:02d}_{session}_offline_train_t{trial:03d}")
        if event["sample_id"] != expected_id:
            raise AssertionError("Operational sample identity differs from the frozen convention")
        transformed = transform_context(signal, sfreq, cue, bounds)
        for band, values in transformed.items():
            arrays[band].append(values)
        rows.append({
            "sample_id": event["sample_id"], "subject": subject, "session": session,
            "run": "retained_labeled_MI" if dataset == "Cho2017" else "offline_train",
            "label": label, "file_id": record["file_id"],
            "raw_sha256": record["sha256"], "cue_sample_native": cue, "trial": trial,
            "event_sample": cue, "artifact_flagged": False,
        })
    return {band: np.stack(values) for band, values in arrays.items()}, pd.DataFrame(rows, columns=METADATA_COLUMNS)


def _decode_subject(dataset: str, subject: int, records: list[dict]):
    records = sorted(records, key=lambda row: (int(row["session"]), str(row["run"]), row["file_id"]))
    expected_sessions = DATASETS[dataset][1]
    if [int(row["session"]) for row in records] != expected_sessions:
        raise AssertionError("Each person must retain every declared session exactly once")
    arrays, metadata = {band: [] for band in BANDS}, []
    for record in records:
        if int(record["subject"]) != subject:
            raise AssertionError("Raw file belongs to a different person")
        bands, rows = _decode_file(record, dataset)
        for band, values in bands.items():
            arrays[band].append(values)
        metadata.append(rows)
    arrays = {band: np.concatenate(values, axis=0) for band, values in arrays.items()}
    metadata = pd.concat(metadata, ignore_index=True)
    if metadata.empty or metadata["sample_id"].duplicated().any() or set(metadata["label"]) != {1, 2}:
        raise AssertionError("Invalid within-person trial identity or classes")
    return arrays, metadata, records


def _write_subject(dataset: str, subject: int, records: list[dict], output_dir: Path) -> dict:
    """Internal writer, reached only after the public entrypoint's freeze gate."""
    arrays, metadata, records = _decode_subject(dataset, subject, records)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    npz_path, csv_path = output_dir / f"s{subject:02d}.npz", output_dir / f"s{subject:02d}.csv"
    for path in (npz_path, csv_path):
        if path.is_symlink():
            raise AssertionError("Processed artifact symlink is forbidden")
    descriptor, temporary = tempfile.mkstemp(prefix=".q15-epochs-", suffix=".npz", dir=output_dir)
    os.close(descriptor)
    try:
        np.savez(temporary, **arrays)
        with np.load(temporary, allow_pickle=False) as saved:
            if set(saved.files) != set(BANDS) or any(not np.array_equal(saved[band], arrays[band]) for band in BANDS):
                raise AssertionError("Persisted epoch read-back differs from decoded raw EEG")
        os.replace(temporary, npz_path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".q15-identities-", suffix=".csv", dir=output_dir)
    os.close(descriptor)
    try:
        metadata.to_csv(temporary, index=False)
        reread = pd.read_csv(temporary, dtype={"sample_id": str, "file_id": str, "raw_sha256": str, "run": str})
        pd.testing.assert_frame_equal(reread, metadata, check_dtype=False)
        os.replace(temporary, csv_path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {
        "subject": subject, "sessions": DATASETS[dataset][1],
        "npz_path": str(npz_path), "npz_sha256": sha256_file(npz_path),
        "metadata_path": str(csv_path), "metadata_sha256": sha256_file(csv_path),
        "n_trials": len(metadata), "raw_file_ids": [row["file_id"] for row in records],
        "physical_run_identity": None if dataset == "Cho2017" else "offline_train",
    }


def preprocess_subject(dataset: str, subject: int, output_dir: Path) -> dict:
    """Safe standalone entry: verify the complete scientific freeze before writes."""
    if dataset not in DATASETS or subject not in range(1, DATASETS[dataset][0] + 1):
        raise ValueError("Person is outside the frozen declared cohort")
    receipts = _execution_gate()
    records = [row for row in receipts[dataset]["files"] if int(row["subject"]) == subject]
    return _write_subject(dataset, subject, records, output_dir)


def prepare_dataset(dataset: str, output_dir: Path) -> Path:
    """Write complete fixed epochs after real audits and committed pre-fit freeze."""
    if dataset not in DATASETS:
        raise ValueError("Unsupported dataset")
    receipts = _execution_gate()
    count, _ = DATASETS[dataset]
    rows = []
    for subject in range(1, count + 1):
        records = [row for row in receipts[dataset]["files"] if int(row["subject"]) == subject]
        rows.append(_write_subject(dataset, subject, records, output_dir))
        print(json.dumps({"dataset": dataset, "persons_preprocessed": subject, "expected_persons": count}), flush=True)
    manifest = {
        "schema_version": 1, "status": "epochs_verified_non_authorizing", "dataset": dataset,
        "metadata_receipt_sha256": sha256_file(q15_source.AUDIT_RECEIPTS[dataset]),
        "expected_subject_ids": list(range(1, count + 1)),
        "preprocessing": preprocessing_contract(), "subjects": rows,
        "pre_fit_freeze_sha256": sha256_file(q15_source.FREEZE),
        "transform_sha256": sha256_file(ROOT / "src/mi_eeg/data/q15_context.py"),
        "preprocessor_sha256": sha256_file(Path(__file__)),
        "target_fits": 0, "predictions_computed": False,
    }
    path = Path(output_dir).resolve() / "epoch_manifest.json"
    q15_source.q14_source.atomic_json(path, manifest)
    return path


def prepare_epochs(audit_receipts: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    """Prepare both frozen cohorts; the caller cannot supply alternate audit receipts."""
    if set(audit_receipts) != set(DATASETS) or any(Path(audit_receipts[name]).resolve() != Path(q15_source.AUDIT_RECEIPTS[name]).resolve() for name in DATASETS):
        raise AssertionError("Only the committed source-runner audit receipts are accepted")
    return {dataset: prepare_dataset(dataset, Path(output_dir) / dataset) for dataset in sorted(DATASETS)}


def prepare_manifest(dataset: str, receipt_path: Path, output_dir: Path) -> Path:
    """Compatibility entrypoint with the same immutable audit/freeze gate."""
    if dataset not in DATASETS:
        raise ValueError("Unsupported dataset")
    if Path(receipt_path).resolve() != Path(q15_source.AUDIT_RECEIPTS[dataset]).resolve():
        raise AssertionError("Only the committed source-runner audit receipt is accepted")
    return prepare_dataset(dataset, output_dir)


prepare_epoch_manifest = prepare_manifest


def validate_epoch_manifest(path: Path) -> dict:
    """Independently decode every original and compare actual tensors and IDs.

    Receipt flags and processed-file hashes are necessary but insufficient.
    No successful subject is reused across calls; failures are never ignored.
    This performs no inference and returns the exact supplied manifest only
    after its full raw-to-epoch replay succeeds.
    """
    manifest = _json(path)
    dataset = manifest.get("dataset")
    if dataset not in DATASETS or manifest.get("schema_version") != 1:
        raise AssertionError("Invalid external epoch manifest identity")
    receipts = _execution_gate()
    required = {
        "status": "epochs_verified_non_authorizing", "target_fits": 0,
        "predictions_computed": False, "preprocessing": preprocessing_contract(),
        "pre_fit_freeze_sha256": sha256_file(q15_source.FREEZE),
        "metadata_receipt_sha256": sha256_file(q15_source.AUDIT_RECEIPTS[dataset]),
        "transform_sha256": sha256_file(ROOT / "src/mi_eeg/data/q15_context.py"),
        "preprocessor_sha256": sha256_file(Path(__file__)),
    }
    if any(manifest.get(key) != value for key, value in required.items()):
        raise AssertionError("External epoch manifest differs from frozen audited execution")
    expected = list(range(1, DATASETS[dataset][0] + 1))
    persons = manifest.get("subjects", [])
    if manifest.get("expected_subject_ids") != expected or [row.get("subject") for row in persons] != expected:
        raise AssertionError("Missing, duplicate, reordered, or unexpected person")
    for row in persons:
        subject = row["subject"]
        records = [item for item in receipts[dataset]["files"] if int(item["subject"]) == subject]
        arrays, metadata, records = _decode_subject(dataset, subject, records)
        if row.get("sessions") != DATASETS[dataset][1] or row.get("n_trials") != len(metadata):
            raise AssertionError("Subject session/trial counts differ from original replay")
        if row.get("raw_file_ids") != [item["file_id"] for item in records]:
            raise AssertionError("Subject original-file identity differs from replay")
        if row.get("physical_run_identity") != (None if dataset == "Cho2017" else "offline_train"):
            raise AssertionError("Physical-run identity differs from the prospective convention")
        for name, digest in (("npz_path", "npz_sha256"), ("metadata_path", "metadata_sha256")):
            artifact = Path(row.get(name, ""))
            if not artifact.is_absolute() or not artifact.is_file() or artifact.is_symlink() or sha256_file(artifact) != row.get(digest):
                raise AssertionError("Processed artifact is unsafe, missing, or changed")
        with np.load(row["npz_path"], allow_pickle=False) as saved:
            if set(saved.files) != set(BANDS):
                raise AssertionError("Unexpected processed frequency band")
            for band in BANDS:
                if saved[band].dtype != np.float32 or saved[band].shape != (len(metadata), 21, 320):
                    raise AssertionError("Processed tensor shape/unit representation changed")
                if not np.array_equal(saved[band], arrays[band]):
                    raise AssertionError("Processed tensor cannot be reproduced from audited original")
        saved_metadata = pd.read_csv(row["metadata_path"], dtype={"sample_id": str, "file_id": str, "raw_sha256": str, "run": str})
        pd.testing.assert_frame_equal(saved_metadata, metadata, check_dtype=False)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(DATASETS))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate", type=Path)
    args = parser.parse_args()
    if args.validate is not None:
        if args.dataset is not None or args.output is not None:
            parser.error("--validate cannot be combined with writing epochs")
        validate_epoch_manifest(args.validate)
        print(json.dumps({"status": "raw_to_epoch_replay_verified", "target_fits": 0}))
    elif args.dataset is not None and args.output is not None:
        print(json.dumps({"epoch_manifest": str(prepare_dataset(args.dataset, args.output)), "target_fits": 0}))
    else:
        parser.error("Provide --validate or both --dataset and --output")


if __name__ == "__main__":
    main()
