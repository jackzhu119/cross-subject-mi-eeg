"""Detached, resumable Q11 then Q14 cloud queue after the frozen Q10 run.

This process waits for *both* independent Q10 scientific validators and both
noninteractive GitHub publication receipts. It never uses target outcomes to
select a Q11/Q14 condition. Scientific stages are serial on one GPU; each
underlying runner owns fit/subject checkpoints. Re-running this supervisor
only resumes incomplete stages and retries missing publication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUSHED = {"pushed", "pushed_with_skipped_files"}
Q10_PUBLICATIONS = (("Q10-BATCH", "Q10-E001"), ("Q10-QUEUE", "Q10-A001"))
FOLLOWUP_PUBLICATIONS = (("Q11-BATCH", "Q11-E001"),
                         ("Q14-BATCH", "Q14-E001"),
                         ("Q14-QUEUE", "Q14-E002"))


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _read(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _q10_active(results: Path) -> bool:
    """Check the precise Q10 Python process, not an unrelated reused PID."""
    pid_file = results / "Q10-QUEUE/supervisor.pid"
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        command = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\x00", b" ")
    except (OSError, ValueError):
        return False
    return b"scripts/q10_cloud_queue.py" in command


def _q10_scientific_ready(results: Path) -> tuple[bool, str]:
    status = _read(results / "Q10-QUEUE/batch_status.json").get("status")
    if status != "complete_validated":
        return False, f"Q10 queue status is {status or 'missing'}"
    deep = _read(results / "Q10-E001/validation_report.json")
    geometry = _read(results / "Q10-A001/validation_report.json")
    if deep.get("status") != "passed_scientific_checks":
        return False, "Q10-E001 independent scientific validation is not passed"
    if geometry.get("status") != "passed_scientific_artifact_validation":
        return False, "Q10-A001 independent scientific validation is not passed"
    return True, "validated"


def _publication_ok(results: Path, batch: str, experiment: str) -> bool:
    receipt = _read(results / batch / "publish_status.json")
    return (receipt.get("status") in PUSHED and
            receipt.get("experiment_dir") == f"results/{experiment}")


def _q11_validated(results: Path) -> bool:
    manifest = _read(results / "Q11-BATCH/batch_manifest.json")
    code_hashes = manifest.get("code_sha256")
    if not isinstance(code_hashes, dict) or not code_hashes:
        return False
    if manifest.get("matrix_sha256") != _sha256(
        ROOT / "research_runs/Q11-E001/MATRIX.json"
    ):
        return False
    if any(_sha256(ROOT / path) != digest for path, digest in code_hashes.items()):
        return False
    return (_read(results / "Q11-BATCH/batch_status.json").get("status") ==
            "complete_validated" and
            _read(results / "Q11-E001/validation_report.json").get("status") ==
            "passed_scientific_checks")


def _q14_validated(results: Path) -> bool:
    freeze_file = results / "Q14-E002/freeze_receipt.json"
    freeze = _read(freeze_file)
    frozen_hashes = {
        "config_sha256": ROOT / "research_runs/Q14-E001/CONFIG.json",
        "source_runner_sha256": ROOT / "scripts/q14_source.py",
        "external_runner_sha256": ROOT / "scripts/q14_external.py",
        "batch_runner_sha256": ROOT / "scripts/q14_batch.py",
        "validator_sha256": ROOT / "scripts/q14_validate.py",
        "contract_tests_sha256": ROOT / "tests/test_q14_external_protocol.py",
        "metadata_audit_sha256": ROOT / "research_runs/Q14-E001/METADATA_AUDIT.json",
        "source_validation_report_sha256":
            results / "Q14-E002/source/validation_report.json",
        "q14_e001_validation_report_sha256":
            results / "Q14-E001/validation_report.json",
    }
    if any(freeze.get(key) != _sha256(path) for key, path in frozen_hashes.items()):
        return False
    external = _read(results / "Q14-E002/external/validation_report.json")
    return (
        _read(results / "Q14-BATCH/completion_receipt.json").get("status") ==
        "complete_external_validated"
        and _read(results / "Q14-E001/validation_report.json").get("passed") is True
        and _read(results / "Q14-E002/source/validation_report.json").get("passed") is True
        and freeze.get("status") == "FROZEN_BEFORE_EXTERNAL_DATA_ACCESS"
        and external.get("source_freeze_sha256") == _sha256(freeze_file)
        and external.get("status") ==
        "independent_external_validation_passed"
        and external.get("external_target_fit_count") == 0
    )


def _publish(python: str, results: Path, batch: str, experiment: str,
             env: dict[str, str], retries: int, delay: int) -> bool:
    batch_dir = results / batch
    experiment_dir = results / experiment
    if not batch_dir.is_dir():
        return False
    for attempt in range(1, retries + 1):
        # Always ask the allowlisted publisher to inspect current files. A
        # prior pushed receipt may describe an earlier *failed/partial* run;
        # treating that receipt alone as fresh would silently omit resumed
        # checkpoints, validation and final metrics from GitHub.
        command = [python, "scripts/publish_research_run.py", "--batch-dir", str(batch_dir),
                   "--experiment-dir", str(experiment_dir)]
        result = subprocess.run(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, check=False)
        print(f"[publish] {batch}/{experiment} attempt={attempt} exit={result.returncode} "
              f"{result.stdout.strip()}", flush=True)
        if result.returncode == 0 and _publication_ok(results, batch, experiment):
            return True
        if attempt < retries:
            time.sleep(delay)
    return False


def _wait_q10(results: Path, python: str, env: dict[str, str],
              poll_seconds: int, retries: int, publish_delay: int,
              startup_grace_seconds: int) -> None:
    start = time.monotonic()
    while True:
        status = _read(results / "Q10-QUEUE/batch_status.json").get("status")
        active = _q10_active(results)
        if status == "failed_stopped":
            raise RuntimeError("Q10 stopped with a failed scientific stage; refusing follow-up")
        if active:
            time.sleep(poll_seconds)
            continue
        ready, reason = _q10_scientific_ready(results)
        if ready:
            for batch, experiment in Q10_PUBLICATIONS:
                if not _publish(python, results, batch, experiment, env,
                                retries, publish_delay):
                    raise RuntimeError(f"Q10 {experiment} validated but Git publication pending")
            print("[gate] Q10 independently validated and both result sets published", flush=True)
            return
        if status is None and time.monotonic() - start < startup_grace_seconds:
            time.sleep(poll_seconds)
            continue
        raise RuntimeError(f"Q10 is not running and cannot pass follow-up gate: {reason}")


def _stage(name: str, argv: list[str], results: Path, queue: Path,
           env: dict[str, str], verified) -> None:
    receipt_path = queue / f"{name}_stage_receipt.json"
    log = queue / f"{name}.log"
    prior = _read(receipt_path)
    attempts = list(prior.get("attempts", []))
    if prior.get("status") == "running":
        # A cloud/process interruption may happen after the stage started but
        # before its exit receipt. Preserve that attempt rather than silently
        # recycling its number on the next launch.
        attempts.append({"attempt": prior.get("current_attempt"),
                         "started_at_utc": prior.get("started_at_utc"),
                         "finished_at_utc": None, "exit_code": None,
                         "status": "interrupted_without_exit_receipt",
                         "log_sha256": _sha256(log)})
    if verified(results):
        if prior.get("status") != "complete":
            _write(receipt_path, {"status": "complete_existing_validated",
                                  "stage": name, "attempts": attempts, "argv": argv,
                                  "verified_at_utc": _now()})
        print(f"[resume] {name}: existing independent markers passed", flush=True)
        return
    start = _now()
    attempt_no = len(attempts) + 1
    _write(receipt_path, {"status": "running", "stage": name, "attempts": attempts,
                          "current_attempt": attempt_no, "started_at_utc": start,
                          "argv": argv})
    print(f"[stage] {name} attempt={attempt_no}", flush=True)
    with log.open("ab") as stream:
        stream.write(f"\n===== ATTEMPT {attempt_no} {start} =====\n".encode())
        stream.flush()
        result = subprocess.run(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                stdout=stream, stderr=subprocess.STDOUT, check=False)
        stream.write(f"\n===== EXIT {result.returncode} {_now()} =====\n".encode())
    complete = result.returncode == 0 and verified(results)
    attempts.append({"attempt": attempt_no, "started_at_utc": start,
                     "finished_at_utc": _now(), "exit_code": result.returncode,
                     "independent_markers_passed": verified(results),
                     "log_sha256": _sha256(log)})
    _write(receipt_path, {"status": "complete" if complete else "failed_stopped",
                          "stage": name, "attempts": attempts, "argv": argv})
    if not complete:
        raise RuntimeError(f"{name} failed or independent validation missing; inspect {log}")


def _publish_available_failure(python: str, results: Path, env: dict[str, str]) -> None:
    """Best-effort public failure history; never delete or hide cloud-local data."""
    for batch, experiment in FOLLOWUP_PUBLICATIONS:
        if (results / batch).is_dir():
            _publish(python, results, batch, experiment, env, retries=1, delay=0)
    if (results / "Q14-QUEUE").is_dir() and not (results / "Q14-E002").is_dir():
        # The queue may fail before Q14 begins. The publisher permits a missing
        # experiment directory and still preserves this supervisor's logs.
        _publish(python, results, "Q14-QUEUE", "Q14-E002", env, retries=1, delay=0)


def _run(args: argparse.Namespace) -> int:
    results = (ROOT / "results").resolve()
    queue = results / "Q14-QUEUE"
    python = sys.executable
    q11 = [python, "scripts/q11_batch.py", "--data-dir", str(args.bnci_data_dir.resolve()),
           "--output-root", str(results), "--device", "cuda"]
    q14 = [python, "scripts/q14_batch.py", "--bnci-data-dir",
           str(args.bnci_data_dir.resolve()), "--physionet-data-dir",
           str(args.physionet_data_dir.resolve()), "--device", "cuda", "--execute-external"]
    plan = {"stages": ["wait_Q10_validation_and_publication", "Q11-E001",
                       "Q14-E001_source_development", "Q14-E002_source_freeze_and_external"],
            "planned_new_deep_fits": 392, "planned_new_shallow_fits": 10,
            "Q11_E001": {"deep_inner": 144, "deep_final": 108},
            "Q14_E001_E002": {"source_deep": 140, "source_shallow": 10,
                                "external_target_fits": 0},
            "q11_command": q11, "q14_command": q14}
    if args.plan_only:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0
    if os.name != "posix":
        raise RuntimeError("Detached cloud follow-up requires Linux/POSIX")
    import fcntl

    if not args.bnci_data_dir.is_dir():
        raise FileNotFoundError(args.bnci_data_dir)
    args.physionet_data_dir.mkdir(parents=True, exist_ok=True)
    queue.mkdir(parents=True, exist_ok=True)
    lock = (queue / "followup.lock").open("a+")
    try:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another follow-up queue already holds the lock") from None
        env = {**os.environ, "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
               "PYTHONUNBUFFERED": "1", "MNE_DATA": str(args.bnci_data_dir.resolve()),
               "MOABB_DOWNLOAD_PROVIDER": "upstream"}
        status = {"status": "waiting_for_q10", "started_or_resumed_at_utc": _now(),
                  "experiment_ids": ["Q11-E001", "Q14-E001", "Q14-E002"],
                  "planned_new_deep_fits": 392, "planned_new_shallow_fits": 10,
                  "external_target_fits": 0}
        _write(queue / "batch_status.json", status)
        try:
            _wait_q10(results, python, env, args.poll_seconds,
                      args.max_publish_retries, args.publish_retry_seconds,
                      args.startup_grace_seconds)
            status["status"] = "running"
            _write(queue / "batch_status.json", status)
            _stage("q11", q11, results, queue, env, _q11_validated)
            if not _publish(python, results, "Q11-BATCH", "Q11-E001", env,
                            args.max_publish_retries, args.publish_retry_seconds):
                raise RuntimeError("Q11 validated but Git publication is pending")
            _stage("q14", q14, results, queue, env, _q14_validated)
            # The Q14 batch's native completion receipt is authoritative. This
            # batch status only labels a verified result for the allowlisted
            # publisher; it never overrides the independent validators.
            _write(results / "Q14-BATCH/batch_status.json",
                   {"status": "complete_validated", "scientific_receipt":
                    "results/Q14-BATCH/completion_receipt.json",
                    "external_validator":
                    "results/Q14-E002/external/validation_report.json"})
            status.update({"status": "complete_validated", "finished_at_utc": _now()})
            _write(queue / "batch_status.json", status)
            for batch, experiment in FOLLOWUP_PUBLICATIONS[1:]:
                if not _publish(python, results, batch, experiment, env,
                                args.max_publish_retries, args.publish_retry_seconds):
                    raise RuntimeError(f"{experiment} validated but Git publication pending")
            print("[complete] Q11 and Q14 scientific checks passed; all GitHub publications pushed",
                  flush=True)
            return 0
        except Exception as exc:  # noqa: BLE001 - retain failure traceback and partial data
            if status["status"] != "complete_validated":
                status.update({"status": "failed_stopped", "finished_at_utc": _now(),
                               "error": str(exc), "traceback": traceback.format_exc(limit=12)})
                _write(queue / "batch_status.json", status)
            else:
                # Distinguish finished science from a later Git/network failure.
                # The pushed/pending receipts remain the publication authority.
                status.update({"publication_status": "pending_manual_publish",
                               "publication_error": str(exc)})
                _write(queue / "batch_status.json", status)
            _publish_available_failure(python, results, env)
            if (status["status"] == "complete_validated" and
                    all(_publication_ok(results, batch, experiment)
                        for batch, experiment in FOLLOWUP_PUBLICATIONS)):
                status.pop("publication_error", None)
                status["publication_status"] = "pushed"
                _write(queue / "batch_status.json", status)
                if _publish(python, results, "Q14-QUEUE", "Q14-E002", env,
                            retries=1, delay=0):
                    return 0
            print(f"[failed] {exc}", flush=True)
            return 1
    finally:
        lock.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bnci-data-dir", type=Path, required=True)
    parser.add_argument("--physionet-data-dir", type=Path, required=True)
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--startup-grace-seconds", type=int, default=600)
    parser.add_argument("--max-publish-retries", type=int, default=12)
    parser.add_argument("--publish-retry-seconds", type=int, default=60)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    if (args.poll_seconds < 1 or args.startup_grace_seconds < 0 or
            args.max_publish_retries < 1 or args.publish_retry_seconds < 0):
        parser.error("Invalid polling or publication retry interval")
    return _run(args)


if __name__ == "__main__":
    raise SystemExit(main())
