"""Validation-only Q14-R2 cloud continuation; never rerun model inference.

Run this only after restoring the original AutoDL data volume and committed
validator erratum. It retains the historical failed R2 batch and publishes a
new, separately identified validation attempt and result.
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
EXTERNAL = ROOT / "results" / "Q14-E002R2" / "external"
BATCH = ROOT / "results" / "Q14-R2FINAL"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _publish(python: Path, attempts: int) -> bool:
    environment = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/bin/false",
        "SSH_ASKPASS": "/bin/false",
    }
    command = [
        str(python),
        "scripts/publish_research_run.py",
        "--batch-dir",
        str(BATCH),
        "--experiment-dir",
        str(ROOT / "results" / "Q14-E002R2"),
        "--attempts",
        str(attempts),
    ]
    result = subprocess.run(
        command, cwd=ROOT, env=environment, stdin=subprocess.DEVNULL, check=False
    )
    status_path = BATCH / "publish_status.json"
    status = _read(status_path) if status_path.exists() else {}
    return result.returncode == 0 and status.get("status") in {
        "pushed", "pushed_with_skipped_files"
    }


def run(data_dir: Path, python: Path, publish_attempts: int) -> int:
    if os.name != "posix" or not str(ROOT).startswith("/root/autodl-tmp/"):
        raise RuntimeError("Q14-R2 finalization requires the original AutoDL data volume")
    tracked = (
        "scripts/q14_r2_numeric.py",
        "scripts/q14_r2_validate.py",
        "scripts/q14_r2_finalize.py",
        "research_runs/Q14-E002R2/VALIDATOR_ERRATUM_20260926.md",
    )
    for command in (
        ("ls-files", "--error-unmatch", "--", *tracked),
        ("diff", "--quiet", "--", *tracked),
        ("diff", "--cached", "--quiet", "--", *tracked),
    ):
        result = subprocess.run(
            ["git", *command], cwd=ROOT, capture_output=True, check=False
        )
        if result.returncode:
            raise RuntimeError("Q14-R2 validator amendment must be committed unchanged")
    branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=ROOT, capture_output=True,
        text=True, check=False,
    )
    if branch.returncode or branch.stdout.strip() != "main":
        raise RuntimeError("Q14-R2 validation and automatic publication require main")
    if not python.is_file() or not data_dir.is_dir():
        raise FileNotFoundError("Frozen Python environment or PhysioNet EDF cache missing")
    import fcntl  # Linux-only lock; the dry-run path does not import it.

    BATCH.mkdir(parents=True, exist_ok=True)
    with (BATCH / "batch.lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        original = _read(ROOT / "results" / "Q14-R2BATCH" / "batch_status.json")
        completion = _read(EXTERNAL / "completion_receipt.json")
        if original.get("status") != "failed_stopped":
            raise AssertionError("Historical failed R2 receipt unexpectedly changed")
        if completion.get("n_subjects") != 109 or completion.get("external_target_fit_count") != 0:
            raise AssertionError("Frozen 109-subject inference receipt missing or changed")
        if _hash(EXTERNAL / "predictions.csv") != completion["aggregate_predictions_sha256"]:
            raise AssertionError("Original aggregate prediction hash changed")
        run_config = _read(EXTERNAL / "run_config.json")
        if data_dir.resolve() != Path(run_config["data_dir"]).resolve():
            raise AssertionError("EDF data directory differs from frozen R2 run config")

        attempt = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        log_path = BATCH / f"validation_attempt_{attempt}.log"
        status = {
            "status": "running_validation_only",
            "experiment_id": "Q14-E002R2",
            "n_subjects": 109,
            "new_model_fits": 0,
            "new_inference_rows": 0,
            "started_at_utc": _now(),
            "validator_sha256": _hash(ROOT / "scripts" / "q14_r2_validate.py"),
            "original_failed_batch_status_retained": True,
            "log": log_path.relative_to(ROOT).as_posix(),
        }
        _write(BATCH / "batch_status.json", status)
        with log_path.open("wb") as log:
            result = subprocess.run(
                [str(python), "scripts/q14_r2_validate.py", "--data-dir", str(data_dir)],
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
        report_path = ROOT / "results" / "Q14-E002R2" / "validation_report.json"
        report = _read(report_path) if report_path.exists() else {}
        success = (
            result.returncode == 0
            and report.get("passed") is True
            and report.get("experiment_id") == "Q14-E002R2"
            and report.get("n_subjects") == 109
            and report.get("n_prediction_rows") == completion["n_prediction_rows"]
        )
        status.update(
            {
                "status": "complete_validated" if success else "failed_stopped",
                "validator_exit_code": result.returncode,
                "finished_at_utc": _now(),
                "validation_report": report_path.relative_to(ROOT).as_posix() if success else None,
            }
        )
        _write(BATCH / "batch_status.json", status)
        first_push = _publish(python, publish_attempts)
        receipt = {
            "status": status["status"] if first_push else "publication_pending",
            "github_published": first_push,
            "shutdown_requested": False,
            "recorded_at_utc": _now(),
        }
        _write(BATCH / "completion_receipt.json", receipt)
        final_push = _publish(python, publish_attempts)
        if not final_push:
            receipt.update(status="publication_pending", github_published=False)
            _write(BATCH / "completion_receipt.json", receipt)
        return 0 if success and final_push else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="actually validate and publish")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--publish-attempts", type=int, default=3)
    args = parser.parse_args()
    if not args.execute:
        print("DRY RUN: Q14-R2 full validator only; zero training/inference; preserve old batch")
        return
    if args.data_dir is None or not 1 <= args.publish_attempts <= 10:
        parser.error("--execute requires --data-dir and 1..10 publish attempts")
    raise SystemExit(run(args.data_dir, args.python, args.publish_attempts))


if __name__ == "__main__":
    main()
