"""Safely power off this AutoDL container after the frozen research queues stop.

The watcher is deliberately separate from the Q10/Q11/Q14 scientific runners.
It never trains, edits checkpoints, or interprets a successful process exit as
scientific success.  An explicit ``--execute-shutdown`` is required; otherwise
the same checks and publication attempts end in a dry run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import followup_queue as gates

PAIRS = (
    ("Q10-BATCH", "Q10-E001"),
    ("Q10-QUEUE", "Q10-A001"),
    ("Q11-BATCH", "Q11-E001"),
    ("Q14-BATCH", "Q14-E001"),
    ("Q14-QUEUE", "Q14-E002"),
)
PUSHED = {"pushed", "pushed_with_skipped_files"}
WATCH_DIR = "Q14-QUEUE"
CHILD_RUNNERS = (
    "q10_e001_batch.py", "q10_spatial_neural.py", "q10_geometry.py",
    "q11_batch.py", "q11_neural.py", "q14_batch.py", "q14_source.py",
    "q14_external.py",
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _worker_alive(pid_file: Path, script_name: str) -> bool:
    """Reject a recycled PID or unrelated process; Linux-only by design."""
    try:
        pid = int(pid_file.read_text(encoding="ascii").strip())
        if pid < 2:
            return False
        command = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\x00", b" ")
    except (OSError, ValueError):
        return False
    return (f"scripts/{script_name}".encode() in command or
            f"/scripts/{script_name}".encode() in command)


def _orphan_training_alive() -> bool:
    """Keep a surviving child fit from being cut off after its supervisor dies."""
    try:
        processes = Path("/proc").iterdir()
        for entry in processes:
            if not entry.name.isdigit():
                continue
            try:
                command = (entry / "cmdline").read_bytes().replace(b"\x00", b" ")
            except OSError:
                continue
            if any(f"scripts/{name}".encode() in command for name in CHILD_RUNNERS):
                return True
    except OSError:
        return False
    return False


def _workers(results: Path) -> dict[str, bool]:
    return {
        "Q10": _worker_alive(results / "Q10-QUEUE/supervisor.pid", "q10_cloud_queue.py"),
        "followup": _worker_alive(results / "Q14-QUEUE/supervisor.pid", "followup_queue.py"),
        "child_training": _orphan_training_alive(),
    }


def _scientific_state(results: Path) -> tuple[bool, dict[str, bool]]:
    q10, _ = gates._q10_scientific_ready(results)
    q11 = gates._q11_validated(results)
    q14 = gates._q14_validated(results)
    return all((q10, q11, q14)), {"Q10": q10, "Q11": q11, "Q14": q14}


def assess(results: Path, active: dict[str, bool]) -> tuple[str, str, dict[str, bool]]:
    """Return wait, success_candidate, or failure_candidate without side effects."""
    q10 = _read(results / "Q10-QUEUE/batch_status.json").get("status")
    followup = _read(results / "Q14-QUEUE/batch_status.json").get("status")
    complete, checks = _scientific_state(results)
    # A worker may still be writing a failure receipt or attempting Git push.
    # Never shut down another still-running worker because its peer failed.
    if any(active.values()):
        return "wait", f"workers_active; Q10={q10}; followup={followup}", checks
    if q10 == "complete_validated" and followup == "complete_validated" and complete:
        return "success_candidate", "all independent scientific checks passed", checks
    return ("failure_candidate",
            f"workers stopped without complete validation; Q10={q10}; followup={followup}",
            checks)


def _publish_once(python: str, results: Path, batch: str, experiment: str) -> bool:
    """Use the existing allowlisted publisher; never git-add arbitrary paths."""
    if not (results / batch).is_dir():
        return False
    argv = [python, "scripts/publish_research_run.py", "--batch-dir", str(results / batch),
            "--experiment-dir", str(results / experiment), "--attempts", "2"]
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/bin/false",
           "SSH_ASKPASS": "/bin/false"}
    try:
        result = subprocess.run(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=480, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"[publish] {batch}/{experiment}: {type(exc).__name__}", flush=True)
        return False
    receipt = _read(results / batch / "publish_status.json")
    # The publisher intentionally excludes transient locks/PIDs and its own
    # receipt.  A size- or credential-based exclusion of a checkpoint/log is
    # different: GitHub cannot be called a complete durable copy in that case.
    skipped = receipt.get("skipped_files", [])
    runtime_only_skips = isinstance(skipped, list) and all(
        isinstance(item, dict) and item.get("reason") == "extension_or_runtime_file"
        and (Path(str(item.get("path", ""))).suffix in {".lock", ".pid"}
             or Path(str(item.get("path", ""))).name == "publish_status.json")
        for item in skipped
    )
    okay = (result.returncode == 0 and receipt.get("status") in PUSHED and
            receipt.get("experiment_dir") == f"results/{experiment}" and
            runtime_only_skips)
    print(f"[publish] {batch}/{experiment}: {'pushed' if okay else 'pending'}", flush=True)
    return okay


def _publish_all(python: str, results: Path, *, attempts: int,
                 pause_seconds: int, include_last: bool = True) -> dict[str, bool]:
    outcome: dict[str, bool] = {}
    for batch, experiment in PAIRS if include_last else PAIRS[:-1]:
        if not (results / batch).is_dir():
            continue
        key = f"{batch}/{experiment}"
        outcome[key] = False
        for attempt in range(attempts):
            if _publish_once(python, results, batch, experiment):
                outcome[key] = True
                break
            if attempt + 1 < attempts:
                time.sleep(pause_seconds)
    return outcome


def _cloud_guard(root: Path) -> None:
    if os.name != "posix" or not root.resolve().is_relative_to(Path("/root/autodl-tmp")):
        raise RuntimeError("AutoDL shutdown watcher may run only under /root/autodl-tmp on Linux")
    if not Path("/usr/bin/shutdown").is_file():
        raise RuntimeError("Official AutoDL /usr/bin/shutdown is unavailable")


def _default_shutdown() -> None:
    # Use AutoDL's documented command exactly, without an unverified flag.
    subprocess.run(["/usr/bin/shutdown"], check=True, timeout=20,
                   stdin=subprocess.DEVNULL)


def finish(results: Path, *, python: str, decision: str, reason: str,
           checks: dict[str, bool], attempts: int, pause_seconds: int,
           execute_shutdown: bool, shutdown: Callable[[], None] = _default_shutdown) -> dict:
    """Republish all available evidence, then optionally schedule poweroff."""
    watch = results / WATCH_DIR
    receipt_path = watch / "autoshutdown_receipt.json"
    if decision not in {"success_candidate", "failure_candidate"}:
        raise ValueError("A live worker is not a shutdown condition")
    stage = {"status": "preparing", "decision": decision, "reason": reason,
             "scientific_checks": checks, "started_at_utc": _now(),
             "shutdown_requested": execute_shutdown}
    _write(receipt_path, stage)
    if not execute_shutdown:
        # Inspection mode must have no external writes or power actions.
        stage.update({"status": "dry_run_" + decision, "finished_at_utc": _now()})
        _write(receipt_path, stage)
        return {"status": stage["status"], "publication": {},
                "shutdown_requested": False}
    # The Q14-QUEUE publication is always last: it includes this receipt and
    # every earlier publisher outcome. The publisher itself then pushes its
    # own publish_status.json in a separate commit.
    publications = _publish_all(python, results, attempts=attempts,
                                pause_seconds=pause_seconds, include_last=False)
    all_expected = {f"{batch}/{experiment}" for batch, experiment in PAIRS[:-1]}
    all_science = decision == "success_candidate" and all(checks.values())
    all_earlier_pushed = all_expected <= set(publications) and all(publications.values())
    scientific_success = all_science and all_earlier_pushed
    stage.update({"status": "validated_publication_ready" if scientific_success else
                  "failure_or_publication_pending", "publication_before_final": publications,
                  "finished_preflight_at_utc": _now(),
                  "final_publication": "Q14-QUEUE/Q14-E002 attempted last"})
    _write(receipt_path, stage)
    last_key = "Q14-QUEUE/Q14-E002"
    final_pushed = False
    for attempt in range(attempts):
        if _publish_once(python, results, *PAIRS[-1]):
            final_pushed = True
            break
        if attempt + 1 < attempts:
            time.sleep(pause_seconds)
    publications[last_key] = final_pushed
    status = "complete_published" if scientific_success and final_pushed else "failed_or_pending"
    if not final_pushed:
        # Preserve a cloud-local final receipt even when GitHub is unavailable.
        stage.update({"status": status, "publication": publications,
                      "github_publication_pending": True, "finished_at_utc": _now()})
        _write(receipt_path, stage)
    try:
        shutdown()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        stage.update({"status": "shutdown_command_failed", "publication": publications,
                      "shutdown_error": type(exc).__name__, "finished_at_utc": _now()})
        _write(receipt_path, stage)
        raise
    return {"status": status, "publication": publications,
            "shutdown_requested": execute_shutdown}


def run(args: argparse.Namespace) -> int:
    _cloud_guard(ROOT)
    if os.geteuid() != 0 and args.execute_shutdown:
        raise RuntimeError("Shutdown requires the root user on this AutoDL instance")
    results = ROOT / "results"
    watch = results / WATCH_DIR
    watch.mkdir(parents=True, exist_ok=True)
    import fcntl

    with (watch / "autoshutdown.lock").open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another AutoDL shutdown watcher already holds the lock") from None
        result = "wait"
        unchanged_since: float | None = None
        while True:
            active = _workers(results)
            decision, reason, checks = assess(results, active)
            print(f"[watch] {decision}: {reason}", flush=True)
            if decision == "wait":
                unchanged_since = None
            elif decision != result:
                unchanged_since = time.monotonic()
            result = decision
            _write(watch / "autoshutdown_status.json",
                   {"status": decision, "reason": reason, "active": active,
                    "scientific_checks": checks, "observed_at_utc": _now(),
                    "execute_shutdown": args.execute_shutdown})
            if decision != "wait" and unchanged_since is not None and (
                time.monotonic() - unchanged_since >= args.settle_seconds
            ):
                break
            time.sleep(args.poll_seconds)
        report = finish(results, python=sys.executable, decision=decision, reason=reason,
                        checks=checks, attempts=args.publish_attempts,
                        pause_seconds=args.publish_pause_seconds,
                        execute_shutdown=args.execute_shutdown)
        return 0 if report["status"] == "complete_published" or not args.execute_shutdown else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-shutdown", action="store_true",
                        help="explicitly arm AutoDL poweroff; omission is a dry run")
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--settle-seconds", type=int, default=45)
    parser.add_argument("--publish-attempts", type=int, default=3)
    parser.add_argument("--publish-pause-seconds", type=int, default=30)
    args = parser.parse_args()
    if (args.poll_seconds < 1 or args.settle_seconds < 0 or
            not 1 <= args.publish_attempts <= 10 or args.publish_pause_seconds < 0):
        parser.error("Invalid polling or publication retry interval")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
