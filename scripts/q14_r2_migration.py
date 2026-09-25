"""Custody-preserving Q14 external continuation after the 128-Hz EDF failure.

R2 copies 87 verified prior subjects and infers only S088--S109. The frozen
source estimator and original Q14 loader are never modified. A metadata-only
amendment handles the nine known 128-Hz official EDFs.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import q14_external, q14_r2_external
from scripts.q14_source import CONFIG, E002_ROOT, runtime_receipt, sha256

ID = "Q14-E002R2"
R1_ID = "Q14-E002R1"
AMENDMENT = ROOT / "research_runs/Q14-E002R2/CONFIG.json"
R1 = ROOT / "results" / R1_ID / "external"
RESULT = ROOT / "results" / ID / "external"
BATCH = ROOT / "results/Q14-R2BATCH"
COPIED = tuple(range(1, 88))
NEW = tuple(range(88, 110))
ALL = tuple(range(1, 110))
OLD_PLATFORM = "Linux-5.15.0-25-generic-x86_64-with-glibc2.35"
NEW_PLATFORM = "Linux-5.4.0-153-generic-x86_64-with-glibc2.35"


def read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return value


def same(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"Q14-R2 custody mismatch: {label}")


def ensure_json(path: Path, value: dict) -> None:
    if path.exists():
        same(read(path), value, str(path))
    else:
        q14_external._atomic_json(path, value)


def audit_r1_origin(data_dir: Path, device_name: str, config: dict, freeze_sha: str) -> dict:
    """Hash-only origin audit; never read target prediction values or scores."""
    r1_run = read(R1 / "run_config.json")
    r1_migration_file = R1 / "migration_receipt.json"
    r1_migration = read(r1_migration_file)
    official_file = R1 / "physionet_SHA256SUMS.txt"
    official_sha = sha256(official_file)
    official = q14_external.parse_official_checksums(official_file.read_text(encoding="ascii"))
    current = runtime_receipt()
    previous = r1_run.get("runtime")
    if not isinstance(previous, dict) or set(previous) != set(current):
        raise AssertionError("R1/current runtime schema differs")
    same(previous.get("platform"), OLD_PLATFORM, "R1 kernel")
    same(current.get("platform"), NEW_PLATFORM, "R2 kernel")
    same(
        {key: value for key, value in previous.items() if key != "platform"},
        {key: value for key, value in current.items() if key != "platform"},
        "all runtime fields except audited kernel",
    )
    for key, expected in {
        "resumption_id": R1_ID,
        "original_experiment_id": "Q14-E002",
        "runner_sha256": sha256(ROOT / "scripts/q14_r1_migration.py"),
        "original_runner_sha256": sha256(ROOT / "scripts/q14_external.py"),
        "config_sha256": sha256(CONFIG),
        "freeze_receipt_sha256": freeze_sha,
        "migration_receipt_sha256": sha256(r1_migration_file),
        "official_checksum_manifest_sha256": official_sha,
        "data_dir": str(data_dir.resolve()),
        "device": device_name,
        "subjects": list(ALL),
        "runs": config["external_runs"],
    }.items():
        same(r1_run.get(key), expected, f"R1 run {key}")
    for key, expected in {
        "status": "ORIGIN_55_HASH_VERIFIED_BEFORE_CONTINUATION",
        "n_original_subjects": 55,
        "source_freeze_sha256": freeze_sha,
        "official_checksum_manifest_sha256": official_sha,
        "new_platform": OLD_PLATFORM,
        "new_target_fits": 0,
    }.items():
        same(r1_migration.get(key), expected, f"R1 migration {key}")
    same(
        read(ROOT / "results/Q14-R1BATCH/batch_status.json").get("status"),
        "failed_stopped",
        "R1 failed batch state",
    )
    if (ROOT / "results/Q14-E002R1/validation_report.json").exists():
        raise AssertionError("R1 already has a validation report; R2 custody scope is stale")
    present = sorted(int(path.parent.name[-3:]) for path in R1.glob("subject_???/receipt.json"))
    same(present, list(COPIED), "exactly S001--S087 R1 receipts")
    original_55 = {
        record["subject"]: record for record in r1_migration["original_subjects_hash_verified"]
    }
    same(sorted(original_55), list(range(1, 56)), "R1 first-55 custody records")
    edfs = {}
    for path in data_dir.rglob("*.edf"):
        if path.name in edfs:
            raise AssertionError(f"Duplicate EDF basename: {path.name}")
        edfs[path.name] = path
    frozen_at = datetime.fromisoformat(read(E002_ROOT / "freeze_receipt.json")["frozen_at_utc"])
    verified = []
    for subject in COPIED:
        folder = R1 / f"subject_{subject:03d}"
        receipt_file = folder / "receipt.json"
        prediction_file = folder / "predictions.csv"
        receipt = read(receipt_file)
        for key, expected in {
            "status": "complete",
            "subject": subject,
            "source_models": config["models"],
            "external_target_fit_count": 0,
            "freeze_receipt_sha256": freeze_sha,
            "official_checksum_manifest_sha256": official_sha,
            "predictions_sha256": sha256(prediction_file),
        }.items():
            same(receipt.get(key), expected, f"R1 S{subject:03d} {key}")
        if receipt.get("n_prediction_rows") != 7 * receipt.get("n_trials", -1):
            raise AssertionError(f"R1 S{subject:03d} has incomplete prediction rows")
        if datetime.fromisoformat(receipt["completed_at_utc"]) < frozen_at:
            raise AssertionError(f"R1 S{subject:03d} predates source freeze")
        if subject <= 55:
            old = E002_ROOT / "external" / f"subject_{subject:03d}"
            same(sha256(receipt_file), sha256(old / "receipt.json"), "original receipt bytes")
            same(
                sha256(prediction_file),
                sha256(old / "predictions.csv"),
                "original prediction bytes",
            )
            same(
                sha256(receipt_file), original_55[subject]["receipt_sha256"], "R1 migration receipt"
            )
        else:
            same(receipt.get("resumption_id"), R1_ID, "R1 continuation ID")
            same(
                receipt.get("migration_receipt_sha256"),
                sha256(r1_migration_file),
                "R1 migration link",
            )
        files = receipt.get("edf_files")
        if not isinstance(files, list) or len(files) != 3:
            raise AssertionError(f"R1 S{subject:03d} missing three EDFs")
        same({item["run"] for item in files}, set(config["external_runs"]), "R1 EDF runs")
        for record in files:
            name = f"S{subject:03d}R{record['run']:02d}.edf"
            same(record["filename"], name, "R1 EDF filename")
            path = edfs.get(name)
            if path is None or path.stat().st_size != record["bytes"]:
                raise AssertionError(f"R1 EDF missing/size drift: {name}")
            same(sha256(path), record["sha256"], f"R1 {name} bytes")
            same(record["sha256"], official[name], f"R1 {name} official SHA")
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
    return {
        "status": "R1_87_HASH_VERIFIED_BEFORE_R2_INFERENCE",
        "resumption_id": ID,
        "parent_resumption_id": R1_ID,
        "original_experiment_id": "Q14-E002",
        "n_copied_subjects": 87,
        "r1_run_config_sha256": sha256(R1 / "run_config.json"),
        "r1_migration_receipt_sha256": sha256(r1_migration_file),
        "official_checksum_manifest_sha256": official_sha,
        "source_freeze_sha256": freeze_sha,
        "old_platform": OLD_PLATFORM,
        "new_platform": NEW_PLATFORM,
        "runtime_fields_except_platform_identical": True,
        "target_outcomes_scored_during_migration": False,
        "external_target_fit_count": 0,
        "copied_subjects_hash_verified": verified,
    }


def copy_subject(subject: int, record: dict) -> None:
    src = R1 / f"subject_{subject:03d}"
    dst = RESULT / f"subject_{subject:03d}"
    if dst.exists():
        same(sha256(dst / "receipt.json"), record["receipt_sha256"], "existing copy receipt")
        same(
            sha256(dst / "predictions.csv"),
            record["predictions_sha256"],
            "existing copy predictions",
        )
        return
    tmp = Path(tempfile.mkdtemp(prefix=f".subject_{subject:03d}_", dir=RESULT))
    shutil.copyfile(src / "receipt.json", tmp / "receipt.json")
    shutil.copyfile(src / "predictions.csv", tmp / "predictions.csv")
    same(sha256(tmp / "receipt.json"), record["receipt_sha256"], "staged receipt")
    same(sha256(tmp / "predictions.csv"), record["predictions_sha256"], "staged prediction")
    os.rename(tmp, dst)


def verify_new_subject(
    subject: int,
    migration_sha: str,
    freeze_sha: str,
    official_sha: str,
    config: dict,
    preflight: list[dict],
) -> None:
    folder = RESULT / f"subject_{subject:03d}"
    receipt = read(folder / "receipt.json")
    for key, expected in {
        "status": "complete",
        "subject": subject,
        "resumption_id": ID,
        "source_models": config["models"],
        "external_target_fit_count": 0,
        "freeze_receipt_sha256": freeze_sha,
        "official_checksum_manifest_sha256": official_sha,
        "migration_receipt_sha256": migration_sha,
        "predictions_sha256": sha256(folder / "predictions.csv"),
    }.items():
        same(receipt.get(key), expected, f"existing R2 S{subject:03d} {key}")
    same(receipt["n_prediction_rows"], 7 * receipt["n_trials"], "R2 prediction count")
    expected_files = {item["filename"]: item for item in preflight if item["subject"] == subject}
    same(len(expected_files), 3, "R2 preflight file count")
    for record in receipt["edf_files"]:
        prior = expected_files[record["filename"]]
        for key in ("subject", "run", "filename", "bytes", "sha256"):
            same(record[key], prior[key], f"R2 EDF {key}")
    same(
        receipt.get("native_rates_hz"),
        {str(item["run"]): item["native_rate_hz"] for item in expected_files.values()},
        "R2 native rate record",
    )


def _publish_checkpoint(python: Path) -> None:
    if not BATCH.is_dir():
        raise AssertionError("Checkpoint publication requires the R2 batch directory")
    result = subprocess.run(
        [
            str(python),
            "scripts/publish_research_run.py",
            "--batch-dir",
            str(BATCH),
            "--experiment-dir",
            str(RESULT.parent),
            "--attempts",
            "3",
        ],
        cwd=ROOT,
        check=False,
        stdin=subprocess.DEVNULL,
        env={
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "/bin/false",
            "SSH_ASKPASS": "/bin/false",
        },
    )
    receipt = read(BATCH / "publish_status.json")
    if result.returncode or receipt.get("status") not in {"pushed", "pushed_with_skipped_files"}:
        print(
            "[checkpoint] GitHub publication pending; local subject receipt preserved", flush=True
        )
    else:
        print("[checkpoint] GitHub subject snapshot pushed", flush=True)


def run(data_dir: Path, device_name: str, checkpoint_publish: bool = False) -> None:
    import torch

    config = read(CONFIG)
    amendment = read(AMENDMENT)
    same(amendment["resumption_id"], ID, "R2 config identity")
    q14_external.verify_freeze(config)
    freeze_sha = sha256(E002_ROOT / "freeze_receipt.json")
    device = torch.device(device_name)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    origin = audit_r1_origin(data_dir, device_name, config, freeze_sha)
    RESULT.mkdir(parents=True, exist_ok=True)
    manifest = R1 / "physionet_SHA256SUMS.txt"
    official = q14_external.parse_official_checksums(manifest.read_text(encoding="ascii"))
    preflight = q14_r2_external.preflight_remaining(data_dir, config, amendment, official)
    preflight_receipt = {
        "status": "OFFICIAL_66_EDF_METADATA_VERIFIED_BEFORE_NEW_PREDICTIONS",
        "resumption_id": ID,
        "amendment_sha256": sha256(AMENDMENT),
        "official_checksum_manifest_sha256": sha256(manifest),
        "edf_files": preflight,
        "n_files": 66,
        "n_128_hz_runs": 9,
        "target_outcomes_scored": False,
    }
    ensure_json(RESULT / "metadata_preflight.json", preflight_receipt)
    migration = {
        **origin,
        "amendment_sha256": sha256(AMENDMENT),
        "metadata_preflight_sha256": sha256(RESULT / "metadata_preflight.json"),
        "data_dir": str(data_dir.resolve()),
        "device": device_name,
    }
    ensure_json(RESULT / "migration_receipt.json", migration)
    migration_sha = sha256(RESULT / "migration_receipt.json")
    run_config = {
        "resumption_id": ID,
        "original_experiment_id": "Q14-E002",
        "runner_sha256": sha256(Path(__file__)),
        "adapter_sha256": sha256(ROOT / "scripts/q14_r2_external.py"),
        "original_runner_sha256": sha256(ROOT / "scripts/q14_external.py"),
        "config_sha256": sha256(CONFIG),
        "amendment_sha256": sha256(AMENDMENT),
        "freeze_receipt_sha256": freeze_sha,
        "migration_receipt_sha256": migration_sha,
        "metadata_preflight_sha256": sha256(RESULT / "metadata_preflight.json"),
        "official_checksum_manifest_sha256": sha256(manifest),
        "data_dir": str(data_dir.resolve()),
        "device": device_name,
        "subjects": list(ALL),
        "runs": config["external_runs"],
        "runtime": runtime_receipt(),
    }
    ensure_json(RESULT / "run_config.json", run_config)
    for record in origin["copied_subjects_hash_verified"]:
        copy_subject(record["subject"], record)
    print("S001--S087: byte-identical custody copies verified", flush=True)
    target_manifest = RESULT / "physionet_SHA256SUMS.txt"
    if target_manifest.exists():
        same(sha256(target_manifest), sha256(manifest), "R2 manifest copy")
    else:
        tmp = target_manifest.with_suffix(".txt.tmp")
        shutil.copyfile(manifest, tmp)
        same(sha256(tmp), sha256(manifest), "staged official manifest")
        os.replace(tmp, target_manifest)
    deep, csp = q14_external._load_source_models(config, device)
    for subject in NEW:
        dst = RESULT / f"subject_{subject:03d}"
        if dst.exists():
            verify_new_subject(
                subject,
                migration_sha,
                freeze_sha,
                run_config["official_checksum_manifest_sha256"],
                config,
                preflight,
            )
            print(f"S{subject:03d}: verified complete, skip", flush=True)
            continue
        if q14_r2_external.expected_rate(subject, amendment) == 128:
            arrays, meta, files = q14_r2_external.load_128_subject(
                subject, data_dir, config, amendment, official, preflight
            )
        else:
            arrays, meta, files = q14_external.load_one_external_subject(
                subject, data_dir, config, official
            )
        expected_files = {
            item["filename"]: item for item in preflight if item["subject"] == subject
        }
        for record in files:
            prior = expected_files[record["filename"]]
            for key in ("subject", "run", "filename", "bytes", "sha256"):
                same(record[key], prior[key], f"R2 S{subject:03d} EDF {key}")
        frame = q14_external._subject_predictions(arrays, meta, deep, csp, config, device)
        if set(frame["experiment_id"]) != {"Q14-E002"} or len(frame) != 7 * len(meta):
            raise AssertionError("Frozen model inference output schema changed")
        tmp = Path(tempfile.mkdtemp(prefix=f".subject_{subject:03d}_", dir=RESULT))
        q14_external._atomic_csv(tmp / "predictions.csv", frame)
        q14_external._atomic_json(
            tmp / "receipt.json",
            {
                "status": "complete",
                "subject": subject,
                "resumption_id": ID,
                "n_trials": len(meta),
                "n_prediction_rows": len(frame),
                "run_counts": {str(k): int(v) for k, v in meta.groupby("run").size().items()},
                "class_counts": {str(k): int(v) for k, v in meta.groupby("label").size().items()},
                "source_models": config["models"],
                "external_target_fit_count": 0,
                "freeze_receipt_sha256": freeze_sha,
                "official_checksum_manifest_sha256": run_config[
                    "official_checksum_manifest_sha256"
                ],
                "migration_receipt_sha256": migration_sha,
                "metadata_preflight_sha256": run_config["metadata_preflight_sha256"],
                "predictions_sha256": sha256(tmp / "predictions.csv"),
                "edf_files": files,
                "native_rates_hz": {
                    str(item["run"]): item["native_rate_hz"] for item in expected_files.values()
                },
                "completed_at_utc": datetime.now(UTC).isoformat(),
            },
        )
        os.rename(tmp, dst)
        print(f"S{subject:03d}: {len(meta)} trials, {len(frame)} prediction rows", flush=True)
        if checkpoint_publish:
            _publish_checkpoint(Path(sys.executable))
    frames = [pd.read_csv(RESULT / f"subject_{subject:03d}/predictions.csv") for subject in ALL]
    aggregate = pd.concat(frames, ignore_index=True)
    q14_external._atomic_csv(RESULT / "predictions.csv", aggregate)
    q14_external._atomic_json(
        RESULT / "completion_receipt.json",
        {
            "status": "all_109_subjects_inferred_under_r2_amendment",
            "resumption_id": ID,
            "original_experiment_id": "Q14-E002",
            "n_original_subjects_byte_identical": 87,
            "n_new_subjects": 22,
            "n_subjects": 109,
            "n_resampled_subjects": 3,
            "n_prediction_rows": len(aggregate),
            "freeze_receipt_sha256": freeze_sha,
            "migration_receipt_sha256": migration_sha,
            "metadata_preflight_sha256": run_config["metadata_preflight_sha256"],
            "official_checksum_manifest_sha256": run_config["official_checksum_manifest_sha256"],
            "aggregate_predictions_sha256": sha256(RESULT / "predictions.csv"),
            "external_target_fit_count": 0,
            "completed_at_utc": datetime.now(UTC).isoformat(),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    parser.add_argument("--checkpoint-publish", action="store_true")
    args = parser.parse_args()
    run(args.data_dir, args.device, args.checkpoint_publish)


if __name__ == "__main__":
    main()
