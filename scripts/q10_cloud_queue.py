"""Run Q10-E001 deep and Q10-A001 classical experiments in one cloud queue.

The Q10-E001 batch and Q10-A001 runner own their scientific checkpoints. This
supervisor only sequences them, saves logs/receipts, verifies their validators,
and attempts noninteractive Git publication. It never chooses a condition from
held-out subject metrics. Re-running the command resumes rather than restarts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stage(name: str, argv: list[str], queue_dir: Path, expected: Path,
           expected_status: str, env: dict[str, str]) -> dict:
    log = queue_dir / f"{name}.log"
    receipt_path = queue_dir / f"{name}_receipt.json"
    attempt = int(_read_json(receipt_path).get("attempt", 0)) + 1
    started = _now()
    print(f"[start] {name}, attempt {attempt}", flush=True)
    with log.open("ab") as stream:
        stream.write(f"\n===== ATTEMPT {attempt} {started} =====\n".encode())
        stream.flush()
        process = subprocess.run(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                 stdout=stream, stderr=subprocess.STDOUT, check=False)
    marker = _read_json(expected)
    complete = process.returncode == 0 and marker.get("status") == expected_status
    receipt = {"status": "complete" if complete else "failed", "stage": name,
               "attempt": attempt, "started_at_utc": started, "finished_at_utc": _now(),
               "argv": argv, "exit_code": process.returncode,
               "expected_marker": str(expected), "expected_status": expected_status,
               "observed_status": marker.get("status"), "log_sha256": _sha256(log),
               "marker_sha256": _sha256(expected) if expected.is_file() else None}
    _write_json(receipt_path, receipt)
    if not complete:
        raise RuntimeError(f"{name} stopped or validation marker missing; inspect {log}")
    print(f"[complete] {name}", flush=True)
    return receipt


def _publish(python: str, queue_dir: Path, experiment_dir: Path,
             env: dict[str, str]) -> bool:
    argv = [python, "scripts/publish_research_run.py", "--batch-dir", str(queue_dir),
            "--experiment-dir", str(experiment_dir)]
    process = subprocess.run(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, check=False)
    print(f"[publish] {experiment_dir.name}: {process.stdout.strip()}", flush=True)
    return process.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--results-root", type=Path, default=ROOT / "results")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    results = args.results_root.resolve()
    if results != (ROOT / "results").resolve():
        raise ValueError("Cloud publication requires this repository's results/ directory")
    data_dir = args.data_dir.resolve()
    queue_dir = results / "Q10-QUEUE"
    deep_dir = results / "Q10-E001"
    geometry_dir = results / "Q10-A001"
    python = sys.executable
    deep = [python, "scripts/q10_e001_batch.py", "--data-dir", str(data_dir),
            "--output-root", str(results), "--device", "cuda", "--publish"]
    geometry = [python, "scripts/q10_geometry.py", "run", "--data-dir", str(data_dir),
                "--output-dir", str(geometry_dir), "--resume"]
    validate_geometry = [python, "scripts/q10_geometry.py", "validate",
                         "--output-dir", str(geometry_dir)]
    if args.plan_only:
        print(json.dumps({"deep": deep, "geometry": geometry,
                          "validate_geometry": validate_geometry,
                          "planned_deep_fits": 126, "planned_shallow_fits": 36}, indent=2))
        return 0
    if os.name != "posix":
        raise RuntimeError("Q10 cloud queue requires Linux/POSIX")
    import fcntl

    if not data_dir.is_dir():
        raise FileNotFoundError(data_dir)
    queue_dir.mkdir(parents=True, exist_ok=True)
    lock = (queue_dir / "queue.lock").open("a+")
    try:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another Q10 queue already holds the lock") from None
        env = {**os.environ, "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
               "PYTHONUNBUFFERED": "1", "MNE_DATA": str(data_dir)}
        status = {"status": "running", "started_or_resumed_at_utc": _now(),
                  "planned_deep_fits": 126, "planned_shallow_fits": 36,
                  "stages": ["q10_deep", "q10_geometry", "q10_geometry_validation"]}
        _write_json(queue_dir / "batch_status.json", status)
        try:
            _stage("q10_deep", deep, queue_dir, results / "Q10-BATCH/batch_status.json",
                   "complete_validated", env)
            # The batch's own validator must independently pass, not merely its
            # orchestration status or a prior green receipt.
            if _read_json(deep_dir / "validation_report.json").get("status") != "passed_scientific_checks":
                raise RuntimeError("Q10-E001 independent scientific validation did not pass")
            _stage("q10_geometry", geometry, queue_dir, geometry_dir / "status.json",
                   "complete_validated", env)
            _stage("q10_geometry_validation", validate_geometry, queue_dir,
                   geometry_dir / "validation_report.json", "passed_scientific_artifact_validation", env)
            status.update({"status": "complete_validated", "finished_at_utc": _now()})
            code = 0
        except Exception as exc:  # noqa: BLE001 - retain any failed-stage traceback
            status.update({"status": "failed_stopped", "finished_at_utc": _now(),
                           "error": str(exc), "traceback": traceback.format_exc(limit=8)})
            code = 1
        _write_json(queue_dir / "batch_status.json", status)
        # Even a failed stage must leave inspectable logs and a publication
        # attempt; failed Git auth does not erase any cloud checkpoint.
        publication: dict[str, bool] = {}
        if code == 0:
            # The deep batch owns its own publication receipt. Retry it here
            # if its first end-of-batch network attempt did not succeed.
            publication["Q10-E001"] = _publish(python, results / "Q10-BATCH", deep_dir, env)
            # The queue receipt includes its stage logs and the geometry fit
            # artifacts, including any failed historical attempts.
            publication["Q10-A001"] = _publish(python, queue_dir, geometry_dir, env)
        elif deep_dir.exists():
            # Preserve queue failure logs even when geometry did not start.
            _publish(python, queue_dir, deep_dir, env)
        elif geometry_dir.exists():
            _publish(python, queue_dir, geometry_dir, env)
        if code == 0 and not all(publication.values()):
            # Scientific completion is separate from Git publication. Return
            # nonzero so an external monitor does not report full success.
            return 2
        return code
    finally:
        lock.close()


if __name__ == "__main__":
    sys.exit(main())
