"""Resume the frozen Q14-E002 external inference after a kernel-only container change.

Q14-E002R1 is a custody/continuation ID, NOT a new fitted method. The original
55 subject predictions and receipts are copied byte-for-byte. New subjects use
the frozen Q14-E002 loader and inference primitives, with no target fitting.
Never run this on a partly understood origin: all original hashes, source
freeze, runtime fields other than ``platform``, and the official EDF checksums
must first pass. The migration receipt is written before any prediction is
read, scored, or made on the new container.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from scripts import q14_external
from scripts.q14_source import CONFIG, E002_ROOT, runtime_receipt, sha256

ID = "Q14-E002R1"
ORIGINAL_ID = "Q14-E002"
ORIGINAL = E002_ROOT / "external"
RESULT = ROOT / "results" / ID / "external"
MIGRATED = tuple(range(1, 56))  # Pre-outcome custody boundary: exactly S001--S055.
ALL = tuple(range(1, 110))
EXPECTED_OLD_PLATFORM = "Linux-5.15.0-78-generic-x86_64-with-glibc2.35"
EXPECTED_NEW_PLATFORM = "Linux-5.15.0-25-generic-x86_64-with-glibc2.35"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, data: dict) -> None:
    q14_external._atomic_json(path, data)


def _assert_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"Q14-E002R1 custody mismatch: {label}")


def _edf_index(data_dir: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in data_dir.rglob("*.edf"):
        if path.name in index:
            raise AssertionError(f"Duplicate EDF basename: {path.name}")
        index[path.name] = path
    return index


def audit_origin(data_dir: Path, device_name: str, config: dict, freeze_sha: str) -> dict:
    """Hash-only pre-outcome audit; does not parse trial labels or probabilities."""
    old_run = read_json(ORIGINAL / "run_config.json")
    checksum_file = ORIGINAL / "physionet_SHA256SUMS.txt"
    official_sha = sha256(checksum_file)
    official = q14_external.parse_official_checksums(checksum_file.read_text(encoding="ascii"))
    current_runtime = runtime_receipt()
    old_runtime = old_run.get("runtime")
    if not isinstance(old_runtime, dict) or set(old_runtime) != set(current_runtime):
        raise AssertionError("Original runtime schema differs")
    old_platform = old_runtime.get("platform")
    new_platform = current_runtime.get("platform")
    if not isinstance(old_platform, str) or not isinstance(new_platform, str):
        raise AssertionError("Missing platform identity")
    if (old_platform, new_platform) != (EXPECTED_OLD_PLATFORM, EXPECTED_NEW_PLATFORM):
        raise AssertionError("R1 permits only the audited 5.15.0-78 to 5.15.0-25 kernel change")
    old_without_platform = {k: v for k, v in old_runtime.items() if k != "platform"}
    current_without_platform = {k: v for k, v in current_runtime.items() if k != "platform"}
    _assert_equal(old_without_platform, current_without_platform, "runtime fields except platform")
    expected_run = {
        "experiment_id": ORIGINAL_ID,
        "config_sha256": sha256(CONFIG),
        "freeze_receipt_sha256": freeze_sha,
        "runner_sha256": sha256(ROOT / "scripts/q14_external.py"),
        "data_dir": str(data_dir.resolve()),
        "device": device_name,
        "subjects": list(ALL),
        "runs": config["external_runs"],
        "official_checksum_manifest_sha256": official_sha,
        "runtime": old_runtime,
    }
    _assert_equal(old_run, expected_run, "original external run_config")
    frozen_at = datetime.fromisoformat(
        read_json(E002_ROOT / "freeze_receipt.json")["frozen_at_utc"]
    )
    if frozen_at.tzinfo is None:
        raise AssertionError("Source freeze timestamp is naive")
    index = _edf_index(data_dir)
    verified: list[dict] = []
    for subject in MIGRATED:
        folder = ORIGINAL / f"subject_{subject:03d}"
        receipt_file = folder / "receipt.json"
        prediction_file = folder / "predictions.csv"
        receipt = read_json(receipt_file)
        mandatory = {
            "status": "complete",
            "subject": subject,
            "source_models": config["models"],
            "external_target_fit_count": 0,
            "freeze_receipt_sha256": freeze_sha,
            "official_checksum_manifest_sha256": official_sha,
            "predictions_sha256": sha256(prediction_file),
        }
        for key, value in mandatory.items():
            _assert_equal(receipt.get(key), value, f"S{subject:03d} receipt {key}")
        if receipt.get("n_prediction_rows") != 7 * receipt.get("n_trials", -1):
            raise AssertionError(f"S{subject:03d} has incomplete model/seed row count")
        if datetime.fromisoformat(receipt["completed_at_utc"]) < frozen_at:
            raise AssertionError(f"S{subject:03d} predictions predate source freeze")
        files = receipt.get("edf_files")
        if not isinstance(files, list) or len(files) != 3:
            raise AssertionError(f"S{subject:03d} has wrong EDF provenance count")
        if {record.get("run") for record in files} != set(config["external_runs"]):
            raise AssertionError(f"S{subject:03d} has wrong EDF run set")
        for record in files:
            filename = f"S{subject:03d}R{record['run']:02d}.edf"
            _assert_equal(record.get("filename"), filename, "EDF filename")
            path = index.get(filename)
            if path is None or path.stat().st_size != record.get("bytes"):
                raise AssertionError(f"Missing/size-mismatched {filename}")
            _assert_equal(sha256(path), record.get("sha256"), f"{filename} bytes")
            _assert_equal(record.get("sha256"), official.get(filename), f"{filename} official")
        verified.append(
            {
                "subject": subject,
                "receipt_sha256": sha256(receipt_file),
                "predictions_sha256": sha256(prediction_file),
                "n_trials": receipt["n_trials"],
                "n_prediction_rows": receipt["n_prediction_rows"],
                "edf_sha256": {item["filename"]: item["sha256"] for item in files},
            }
        )
    completed_subjects = sorted(
        int(path.parent.name.split("_")[1])
        for path in ORIGINAL.glob("subject_???/receipt.json")
    )
    _assert_equal(completed_subjects, list(MIGRATED), "original complete subject set")
    return {
        "schema_version": 1,
        "status": "ORIGIN_55_HASH_VERIFIED_BEFORE_CONTINUATION",
        "resumption_id": ID,
        "original_experiment_id": ORIGINAL_ID,
        "source_freeze_sha256": freeze_sha,
        "original_run_config_sha256": sha256(ORIGINAL / "run_config.json"),
        "official_checksum_manifest_sha256": official_sha,
        "old_platform": old_platform,
        "new_platform": new_platform,
        "runtime_fields_except_platform_identical": True,
        "original_completion_schema_gap": (
            "The frozen Q14-E002 producer omitted official_checksum_manifest_sha256 "
            "from completion_receipt.json but its frozen validator required that field; "
            "R1 emits the field in a new result directory without editing originals."
        ),
        "data_dir": str(data_dir.resolve()),
        "device": device_name,
        "original_subjects_hash_verified": verified,
        "n_original_subjects": len(verified),
        "target_outcomes_scored_during_migration": False,
        "new_target_fits": 0,
    }


def _ensure_json(path: Path, data: dict) -> None:
    if path.exists():
        _assert_equal(read_json(path), data, str(path))
    else:
        atomic_json(path, data)


def _atomic_subject_copy(subject: int, record: dict) -> None:
    src = ORIGINAL / f"subject_{subject:03d}"
    dst = RESULT / f"subject_{subject:03d}"
    if dst.exists():
        _assert_equal(sha256(dst / "receipt.json"), record["receipt_sha256"], "copied receipt")
        _assert_equal(
            sha256(dst / "predictions.csv"), record["predictions_sha256"], "copied prediction"
        )
        return
    tmp = Path(tempfile.mkdtemp(prefix=f".subject_{subject:03d}_", dir=RESULT))
    shutil.copyfile(src / "receipt.json", tmp / "receipt.json")
    shutil.copyfile(src / "predictions.csv", tmp / "predictions.csv")
    _assert_equal(sha256(tmp / "receipt.json"), record["receipt_sha256"], "staged receipt")
    _assert_equal(
        sha256(tmp / "predictions.csv"), record["predictions_sha256"], "staged prediction"
    )
    os.rename(tmp, dst)  # A subject becomes visible only with BOTH verified files.


def _verify_new_subject(subject: int, freeze_sha: str, official_sha: str, config: dict) -> None:
    folder = RESULT / f"subject_{subject:03d}"
    receipt = read_json(folder / "receipt.json")
    for key, value in {
        "status": "complete",
        "subject": subject,
        "source_models": config["models"],
        "external_target_fit_count": 0,
        "freeze_receipt_sha256": freeze_sha,
        "official_checksum_manifest_sha256": official_sha,
        "resumption_id": ID,
    }.items():
        _assert_equal(receipt.get(key), value, f"resumed S{subject:03d} {key}")
    _assert_equal(
        sha256(folder / "predictions.csv"), receipt["predictions_sha256"], "new prediction bytes"
    )
    _assert_equal(
        receipt["n_prediction_rows"], 7 * receipt["n_trials"], "new prediction rows"
    )


def run(data_dir: Path, device_name: str) -> None:
    import torch

    # This is the first I/O involving Q14 artifacts; target files are untouched
    # until the unchanged original source-freeze gate passes.
    config = read_json(CONFIG)
    q14_external.verify_freeze(config)
    freeze_sha = sha256(E002_ROOT / "freeze_receipt.json")
    device = torch.device(device_name)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    audit = audit_origin(data_dir, device_name, config, freeze_sha)
    RESULT.mkdir(parents=True, exist_ok=True)
    _ensure_json(RESULT / "migration_receipt.json", audit)
    migration_sha = sha256(RESULT / "migration_receipt.json")
    run_config = {
        "resumption_id": ID,
        "original_experiment_id": ORIGINAL_ID,
        "runner_sha256": sha256(Path(__file__)),
        "original_runner_sha256": sha256(ROOT / "scripts/q14_external.py"),
        "config_sha256": sha256(CONFIG),
        "freeze_receipt_sha256": freeze_sha,
        "migration_receipt_sha256": migration_sha,
        "original_run_config_sha256": audit["original_run_config_sha256"],
        "official_checksum_manifest_sha256": audit["official_checksum_manifest_sha256"],
        "data_dir": str(data_dir.resolve()),
        "device": device_name,
        "subjects": list(ALL),
        "runs": config["external_runs"],
        "runtime": runtime_receipt(),
    }
    _ensure_json(RESULT / "run_config.json", run_config)
    for record in audit["original_subjects_hash_verified"]:
        _atomic_subject_copy(record["subject"], record)
    print("S001--S055: byte-identical migrated copies verified", flush=True)
    shutil.copyfile(
        ORIGINAL / "physionet_SHA256SUMS.txt", RESULT / "physionet_SHA256SUMS.txt.tmp"
    )
    _assert_equal(
        sha256(RESULT / "physionet_SHA256SUMS.txt.tmp"),
        audit["official_checksum_manifest_sha256"],
        "copied official manifest",
    )
    os.replace(RESULT / "physionet_SHA256SUMS.txt.tmp", RESULT / "physionet_SHA256SUMS.txt")
    official = q14_external.parse_official_checksums(
        (RESULT / "physionet_SHA256SUMS.txt").read_text(encoding="ascii")
    )
    deep, csp = q14_external._load_source_models(config, device)
    for subject in ALL[len(MIGRATED) :]:
        dst = RESULT / f"subject_{subject:03d}"
        if dst.exists():
            _verify_new_subject(subject, freeze_sha, audit["official_checksum_manifest_sha256"], config)
            print(f"S{subject:03d}: verified complete, skip", flush=True)
            continue
        arrays, meta, files = q14_external.load_one_external_subject(
            subject, data_dir, config, official
        )
        frame = q14_external._subject_predictions(arrays, meta, deep, csp, config, device)
        if set(frame["experiment_id"]) != {ORIGINAL_ID} or len(frame) != 7 * len(meta):
            raise AssertionError("Frozen inference primitive produced different prediction schema")
        tmp = Path(tempfile.mkdtemp(prefix=f".subject_{subject:03d}_", dir=RESULT))
        q14_external._atomic_csv(tmp / "predictions.csv", frame)
        atomic_json(
            tmp / "receipt.json",
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
                "official_checksum_manifest_sha256": audit["official_checksum_manifest_sha256"],
                "predictions_sha256": sha256(tmp / "predictions.csv"),
                "edf_files": files,
                "completed_at_utc": datetime.now(UTC).isoformat(),
                "resumption_id": ID,
                "migration_receipt_sha256": migration_sha,
            },
        )
        os.rename(tmp, dst)
        print(f"S{subject:03d}: {len(meta)} trials, {len(frame)} prediction rows", flush=True)
    frames = [
        pd.read_csv(RESULT / f"subject_{subject:03d}/predictions.csv") for subject in ALL
    ]
    aggregate = pd.concat(frames, ignore_index=True)
    q14_external._atomic_csv(RESULT / "predictions.csv", aggregate)
    completion = {
        "status": "all_109_subjects_inferred",
        "resumption_id": ID,
        "original_experiment_id": ORIGINAL_ID,
        "n_original_subjects_byte_identical": len(MIGRATED),
        "n_new_subjects": len(ALL) - len(MIGRATED),
        "n_subjects": len(ALL),
        "n_prediction_rows": len(aggregate),
        "freeze_receipt_sha256": freeze_sha,
        "migration_receipt_sha256": migration_sha,
        "official_checksum_manifest_sha256": audit["official_checksum_manifest_sha256"],
        "aggregate_predictions_sha256": sha256(RESULT / "predictions.csv"),
        "external_target_fit_count": 0,
        "completed_at_utc": datetime.now(UTC).isoformat(),
    }
    atomic_json(RESULT / "completion_receipt.json", completion)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    args = parser.parse_args()
    run(args.data_dir, args.device)


if __name__ == "__main__":
    main()
