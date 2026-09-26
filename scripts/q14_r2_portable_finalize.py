"""Versioned, validation-only Q14-R2 continuation on a different cloud host.

The default is a dry run. ``--execute`` verifies frozen input hashes, runs the
independent 327-EDF validator against existing predictions, and publishes its
new output plus failure/success logs. It never trains or invokes inference.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/Q14-E002R2/external"
OUTPUT = ROOT / "results/Q14-E002R2V1"
BATCH = ROOT / "results/Q14-R2PORT"
AMENDMENT = ROOT / "research_runs/Q14-E002R2/VALIDATION_PORTABILITY_AMENDMENT_20260926.md"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return value


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_manifest() -> list[dict]:
    """Hash every immutable R2 input this validator consumes, except raw EDFs.

    The full validator independently checks all 327 EDFs against the official
    checksum manifest and the saved subject receipts. This manifest is a
    before/after guard against accidentally changing *prediction* artifacts.
    """
    names = [
        "run_config.json", "migration_receipt.json", "metadata_preflight.json",
        "completion_receipt.json", "physionet_SHA256SUMS.txt", "predictions.csv",
    ]
    paths = [SOURCE / name for name in names]
    for subject in range(1, 110):
        folder = SOURCE / f"subject_{subject:03d}"
        paths.extend((folder / "receipt.json", folder / "predictions.csv"))
    if any(not path.is_file() for path in paths):
        raise FileNotFoundError("Q14-R2 immutable subject or source artifact missing")
    return [
        {"path": path.relative_to(ROOT).as_posix(), "sha256": _hash(path)}
        for path in paths
    ]


def _git_guard() -> None:
    tracked = (
        "scripts/q14_r2_validate.py",
        "scripts/q14_r2_numeric.py",
        "scripts/q14_r2_portable_finalize.py",
        "research_runs/Q14-E002R2/VALIDATION_PORTABILITY_AMENDMENT_20260926.md",
    )
    for command in (
        ("ls-files", "--error-unmatch", "--", *tracked),
        ("diff", "--quiet", "--", *tracked),
        ("diff", "--cached", "--quiet", "--", *tracked),
    ):
        if subprocess.run(["git", *command], cwd=ROOT, capture_output=True, check=False).returncode:
            raise RuntimeError("Versioned portable validation code must be committed unchanged")
    branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=ROOT, text=True, capture_output=True,
        check=False,
    )
    if branch.returncode or branch.stdout.strip() != "main":
        raise RuntimeError("Automatic validation publication requires the main branch")


def _publish(python: Path, attempts: int) -> bool:
    command = [
        str(python), "scripts/publish_research_run.py", "--batch-dir", str(BATCH),
        "--experiment-dir", str(OUTPUT), "--attempts", str(attempts),
    ]
    result = subprocess.run(
        command, cwd=ROOT, stdin=subprocess.DEVNULL, check=False,
        env={
            **os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/bin/false",
            "SSH_ASKPASS": "/bin/false",
        },
    )
    status_path = BATCH / "publish_status.json"
    status = _read(status_path) if status_path.is_file() else {}
    return result.returncode == 0 and status.get("status") in {
        "pushed", "pushed_with_skipped_files",
    }


def run(data_dir: Path, python: Path, publish_attempts: int) -> int:
    if os.name != "posix" or not str(ROOT).startswith("/root/autodl-tmp/"):
        raise RuntimeError("Portable Q14 validation requires the persistent AutoDL data volume")
    _git_guard()
    if not python.is_file() or not data_dir.is_dir():
        raise FileNotFoundError("Validator Python environment or official EDF cache missing")
    run_config = _read(SOURCE / "run_config.json")
    if data_dir.resolve() != Path(run_config["data_dir"]).resolve():
        raise AssertionError("EDF path differs from the frozen R2 inference path")
    old_batch = _read(ROOT / "results/Q14-R2BATCH/batch_status.json")
    if old_batch.get("status") != "failed_stopped":
        raise AssertionError("Historical R2 failed validation state changed")
    completion = _read(SOURCE / "completion_receipt.json")
    if completion.get("n_subjects") != 109 or completion.get("external_target_fit_count") != 0:
        raise AssertionError("Frozen R2 completion receipt incomplete or changed")
    if _hash(SOURCE / "predictions.csv") != completion["aggregate_predictions_sha256"]:
        raise AssertionError("Frozen aggregate prediction hash changed")

    import fcntl  # Linux-only; dry-run does not import it.

    BATCH.mkdir(parents=True, exist_ok=True)
    with (BATCH / "batch.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        before = source_manifest()
        _write(BATCH / "immutable_input_manifest.json", {"artifacts": before})
        attempt = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        log_path = BATCH / f"validation_attempt_{attempt}.log"
        status = {
            "status": "running_validation_only", "validation_attempt_id": "Q14-E002R2V1",
            "original_experiment_id": "Q14-E002R2", "n_subjects": 109,
            "new_model_fits": 0, "new_inference_rows": 0,
            "started_at_utc": _now(), "validator_sha256": _hash(ROOT / "scripts/q14_r2_validate.py"),
            "portability_amendment_sha256": _hash(AMENDMENT),
            "original_failed_batch_status_retained": True,
            "log": log_path.relative_to(ROOT).as_posix(),
        }
        _write(BATCH / "batch_status.json", status)
        validator_exit_code = None
        validation_error = None
        try:
            with log_path.open("wb") as log:
                completed = subprocess.run(
                    [str(python), "scripts/q14_r2_validate.py", "--data-dir", str(data_dir),
                     "--portable-output-root", str(OUTPUT)],
                    cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    check=False,
                )
            validator_exit_code = completed.returncode
            if before != source_manifest():
                raise AssertionError("Portable validator changed immutable R2 inference artifacts")
        except Exception as exc:  # noqa: BLE001 - preserve and publish failure evidence
            validation_error = f"{type(exc).__name__}: {exc}"
        report_path = OUTPUT / "validation_report.json"
        report = _read(report_path) if report_path.is_file() else {}
        passed = (
            validator_exit_code == 0
            and validation_error is None
            and report.get("passed") is True
            and report.get("validation_attempt_id") == "Q14-E002R2V1"
            and report.get("n_subjects") == 109
            and report.get("n_verified_official_edf_files") == 327
            and report.get("n_prediction_rows") == completion["n_prediction_rows"]
            and report.get("external_target_fit_count") == 0
            and report.get("portability_amendment_sha256") == _hash(AMENDMENT)
        )
        status.update(
            status="complete_validated" if passed else "failed_stopped",
            validator_exit_code=validator_exit_code,
            validation_error=validation_error,
            finished_at_utc=_now(),
            validation_report=report_path.relative_to(ROOT).as_posix() if passed else None,
            immutable_input_artifacts_unchanged=validation_error is None,
        )
        _write(BATCH / "batch_status.json", status)
        first_push = _publish(python, publish_attempts)
        receipt = {
            "status": status["status"] if first_push else "publication_pending",
            "github_published": first_push, "new_model_fits": 0,
            "new_inference_rows": 0, "recorded_at_utc": _now(),
        }
        _write(BATCH / "completion_receipt.json", receipt)
        final_push = _publish(python, publish_attempts)
        if not final_push:
            receipt.update(status="publication_pending", github_published=False)
            _write(BATCH / "completion_receipt.json", receipt)
        return 0 if passed and final_push else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--publish-attempts", type=int, default=3)
    args = parser.parse_args()
    if not args.execute:
        print("DRY RUN: existing Q14-R2 predictions only; 327 EDF checks; zero fits/inference")
        return
    if args.data_dir is None or not 1 <= args.publish_attempts <= 10:
        parser.error("--execute requires --data-dir and 1..10 publication attempts")
    raise SystemExit(run(args.data_dir, args.python, args.publish_attempts))


if __name__ == "__main__":
    main()
