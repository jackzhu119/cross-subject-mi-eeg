"""Detached, resumable Q14-E002R1 continuation, publication and optional shutdown.

This supervisor does not change the frozen Q14-E002 source models or original
external results. The migration runner independently validates the old and new
artifacts. A failure is published as a failure, never marked scientifically
complete. Only an explicit ``--execute-shutdown`` may power off AutoDL.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "results/Q14-R1BATCH"
EXPERIMENT = ROOT / "results/Q14-E002R1"
SUCCESS = {"pushed", "pushed_with_skipped_files"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _publish(python: Path, attempts: int, delay: int) -> bool:
    command = [str(python), "scripts/publish_research_run.py", "--batch-dir",
               str(BATCH), "--experiment-dir", str(EXPERIMENT), "--attempts", "3"]
    environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0",
                   "GIT_ASKPASS": "/bin/false", "SSH_ASKPASS": "/bin/false"}
    for number in range(1, attempts + 1):
        result = subprocess.run(command, cwd=ROOT, env=environment,
                                stdin=subprocess.DEVNULL, check=False)
        receipt = _read(BATCH / "publish_status.json")
        skipped = receipt.get("skipped_files", [])
        runtime_only_skips = isinstance(skipped, list) and all(
            isinstance(item, dict)
            and item.get("reason") == "extension_or_runtime_file"
            and Path(str(item.get("path", ""))).name in
            {"batch.lock", "supervisor.pid", "publish_status.json"}
            for item in skipped
        )
        okay = (result.returncode == 0 and receipt.get("status") in SUCCESS
                and receipt.get("experiment_dir") == "results/Q14-E002R1"
                and runtime_only_skips)
        print(f"[publish] attempt={number} status={receipt.get('status')} exit={result.returncode}",
              flush=True)
        if okay:
            return True
        if number < attempts:
            time.sleep(delay)
    return False


def _other_research_worker_alive() -> bool:
    """Do not shut down an instance with a different research worker running."""
    markers = (
        b"scripts/q10_cloud_queue.py", b"scripts/followup_queue.py",
        b"scripts/q14_batch.py", b"scripts/q14_external.py",
        b"scripts/q14_r1_supervisor.py", b"scripts/q14_r1_migration.py",
    )
    own = os.getpid()
    for path in Path("/proc").iterdir():
        if not path.name.isdigit() or int(path.name) == own:
            continue
        try:
            command = (path / "cmdline").read_bytes().replace(b"\x00", b" ")
        except OSError:
            continue
        if any(marker in command for marker in markers):
            return True
    return False


def run(data_dir: Path, python: Path, *, publish_attempts: int,
        publish_delay: int, execute_shutdown: bool) -> int:
    if os.name != "posix" or not str(ROOT).startswith("/root/autodl-tmp/"):
        raise RuntimeError("Q14-R1 cloud supervisor requires the AutoDL Linux data volume")
    if not python.is_file() or not data_dir.is_dir():
        raise FileNotFoundError("Frozen Python environment or PhysioNet cache is missing")
    BATCH.mkdir(parents=True, exist_ok=True)
    with (BATCH / "batch.lock").open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another Q14-R1 supervisor is active") from exc
        status = {
            "status": "running", "experiment_id": "Q14-E002R1",
            "parent_experiment_id": "Q14-E002", "started_or_resumed_at_utc": _now(),
            "external_target_fits": 0,
            "migration_policy": "only_kernel_platform_change; frozen_model_and_method_unchanged",
        }
        _write(BATCH / "batch_status.json", status)
        command = [str(python), "scripts/q14_r1_migration.py", "--data-dir",
                   str(data_dir.resolve()), "--device", "cuda"]
        exit_code = 1
        try:
            print(f"[run] Q14-E002R1 attempt at {_now()}", flush=True)
            result = subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                    check=False)
            exit_code = result.returncode
            if exit_code:
                raise RuntimeError(f"Migration inference failed (exit {exit_code})")
            validation_command = [str(python), "scripts/q14_r1_validate.py", "--data-dir",
                                  str(data_dir.resolve())]
            print(f"[validate] Q14-E002R1 at {_now()}", flush=True)
            validation_result = subprocess.run(validation_command, cwd=ROOT,
                                               stdin=subprocess.DEVNULL, check=False)
            if validation_result.returncode:
                raise RuntimeError(
                    f"Independent migration validation failed (exit {validation_result.returncode})"
                )
            validation = _read(EXPERIMENT / "validation_report.json")
            if (validation.get("passed") is not True
                    or validation.get("experiment_id") != "Q14-E002R1"):
                raise RuntimeError("Independent migration validation report is incomplete")
            status.update({"status": "complete_validated", "finished_at_utc": _now(),
                           "validation_report": "results/Q14-E002R1/validation_report.json"})
        except Exception as exc:  # preserve failed attempts and partial subject receipts
            status.update({"status": "failed_stopped", "finished_at_utc": _now(),
                           "error": str(exc), "traceback": traceback.format_exc(limit=12),
                           "runner_exit_code": exit_code})
        _write(BATCH / "batch_status.json", status)
        first_pushed = _publish(python, publish_attempts, publish_delay)
        final = {"status": status["status"], "github_published": first_pushed,
                 "shutdown_requested": execute_shutdown, "recorded_at_utc": _now()}
        _write(BATCH / "completion_receipt.json", final)
        # Publish the final receipt as well, not only prediction files and logs.
        final_pushed = _publish(python, publish_attempts, publish_delay)
        if not final_pushed:
            final.update({"github_published": False, "status": "publication_pending",
                          "recorded_at_utc": _now()})
            _write(BATCH / "completion_receipt.json", final)
        if execute_shutdown:
            if _other_research_worker_alive():
                final.update({"shutdown_skipped": "another_research_worker_active",
                              "recorded_at_utc": _now()})
                _write(BATCH / "completion_receipt.json", final)
                _publish(python, 1, 0)
            else:
                print("[shutdown] requesting official AutoDL poweroff", flush=True)
                try:
                    subprocess.run(["/usr/bin/shutdown"], check=True, timeout=20,
                                   stdin=subprocess.DEVNULL)
                except (OSError, subprocess.CalledProcessError,
                        subprocess.TimeoutExpired) as exc:
                    final.update({"shutdown_error": type(exc).__name__,
                                  "recorded_at_utc": _now()})
                    _write(BATCH / "completion_receipt.json", final)
                    _publish(python, 1, 0)
                    raise
        return 0 if status["status"] == "complete_validated" and final_pushed else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--publish-attempts", type=int, default=6)
    parser.add_argument("--publish-delay-seconds", type=int, default=30)
    parser.add_argument("--execute-shutdown", action="store_true")
    args = parser.parse_args()
    if not (1 <= args.publish_attempts <= 10 and 0 <= args.publish_delay_seconds <= 300):
        parser.error("Publication retry bounds exceeded")
    raise SystemExit(run(args.data_dir, args.python,
                         publish_attempts=args.publish_attempts,
                         publish_delay=args.publish_delay_seconds,
                         execute_shutdown=args.execute_shutdown))


if __name__ == "__main__":
    main()
