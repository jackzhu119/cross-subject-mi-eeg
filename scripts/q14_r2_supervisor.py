"""Detached Q14-R2 runner: resume, validate, and publish success or failure.

The runner also publishes after every new complete subject. The supervisor
publishes final logs/receipts after either handled failure or validation.
It deliberately does not call AutoDL shutdown: the previous shutdown helper
raised OSError and poweroff is not evidence of scientific completion.
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
BATCH = ROOT / "results/Q14-R2BATCH"
EXPERIMENT = ROOT / "results/Q14-E002R2"
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
    command = [
        str(python),
        "scripts/publish_research_run.py",
        "--batch-dir",
        str(BATCH),
        "--experiment-dir",
        str(EXPERIMENT),
        "--attempts",
        "3",
    ]
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/bin/false",
        "SSH_ASKPASS": "/bin/false",
    }
    for attempt in range(1, attempts + 1):
        result = subprocess.run(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, check=False)
        receipt = _read(BATCH / "publish_status.json")
        skipped = receipt.get("skipped_files", [])
        runtime_only = isinstance(skipped, list) and all(
            isinstance(item, dict)
            and item.get("reason") == "extension_or_runtime_file"
            and Path(str(item.get("path", ""))).name
            in {"batch.lock", "supervisor.pid", "publish_status.json"}
            for item in skipped
        )
        okay = (
            result.returncode == 0
            and receipt.get("status") in SUCCESS
            and receipt.get("experiment_dir") == "results/Q14-E002R2"
            and runtime_only
        )
        print(
            f"[publish] attempt={attempt} status={receipt.get('status')} exit={result.returncode}",
            flush=True,
        )
        if okay:
            return True
        if attempt < attempts:
            time.sleep(delay)
    return False


def run(data_dir: Path, python: Path, *, publish_attempts: int, publish_delay: int) -> int:
    if os.name != "posix" or not str(ROOT).startswith("/root/autodl-tmp/"):
        raise RuntimeError("Q14-R2 supervisor requires the AutoDL data volume")
    if not python.is_file() or not data_dir.is_dir():
        raise FileNotFoundError("Frozen Python environment or PhysioNet cache missing")
    BATCH.mkdir(parents=True, exist_ok=True)
    with (BATCH / "batch.lock").open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another Q14-R2 supervisor is active") from exc
        status = {
            "status": "running",
            "experiment_id": "Q14-E002R2",
            "parent_experiment_id": "Q14-E002R1",
            "started_or_resumed_at_utc": _now(),
            "external_target_fits": 0,
            "protocol_amendment": "native-128-Hz EDFs resampled 5/4 after native-Hz filtering/epoching",
        }
        _write(BATCH / "batch_status.json", status)
        exit_code = 1
        try:
            print(f"[run] Q14-E002R2 attempt at {_now()}", flush=True)
            result = subprocess.run(
                [
                    str(python),
                    "scripts/q14_r2_migration.py",
                    "--data-dir",
                    str(data_dir.resolve()),
                    "--device",
                    "cuda",
                    "--checkpoint-publish",
                ],
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                check=False,
            )
            exit_code = result.returncode
            if exit_code:
                raise RuntimeError(f"R2 inference failed (exit {exit_code})")
            print(f"[validate] Q14-E002R2 at {_now()}", flush=True)
            validation = subprocess.run(
                [str(python), "scripts/q14_r2_validate.py", "--data-dir", str(data_dir.resolve())],
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                check=False,
            )
            if validation.returncode:
                raise RuntimeError(
                    f"R2 independent validation failed (exit {validation.returncode})"
                )
            report = _read(EXPERIMENT / "validation_report.json")
            if report.get("passed") is not True or report.get("experiment_id") != "Q14-E002R2":
                raise RuntimeError("R2 validation report missing/invalid")
            status.update(
                {
                    "status": "complete_validated",
                    "finished_at_utc": _now(),
                    "validation_report": "results/Q14-E002R2/validation_report.json",
                }
            )
        except Exception as exc:  # noqa: BLE001 - preserve failed data and exact error
            status.update(
                {
                    "status": "failed_stopped",
                    "finished_at_utc": _now(),
                    "error": str(exc),
                    "traceback": traceback.format_exc(limit=12),
                    "runner_exit_code": exit_code,
                }
            )
        _write(BATCH / "batch_status.json", status)
        initial_pushed = _publish(python, publish_attempts, publish_delay)
        final = {
            "status": status["status"],
            "github_published": initial_pushed,
            "shutdown_requested": False,
            "recorded_at_utc": _now(),
        }
        _write(BATCH / "completion_receipt.json", final)
        final_pushed = _publish(python, publish_attempts, publish_delay)
        if not final_pushed:
            final.update(
                {
                    "status": "publication_pending",
                    "github_published": False,
                    "recorded_at_utc": _now(),
                }
            )
            _write(BATCH / "completion_receipt.json", final)
        return 0 if status["status"] == "complete_validated" and final_pushed else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--publish-attempts", type=int, default=6)
    parser.add_argument("--publish-delay-seconds", type=int, default=30)
    args = parser.parse_args()
    if not (1 <= args.publish_attempts <= 10 and 0 <= args.publish_delay_seconds <= 300):
        parser.error("Publication retry bounds exceeded")
    raise SystemExit(
        run(
            args.data_dir,
            args.python,
            publish_attempts=args.publish_attempts,
            publish_delay=args.publish_delay_seconds,
        )
    )


if __name__ == "__main__":
    main()
