"""Resumable Q13-E001/E004/E005 sequence; dry-run unless --execute is given.

Each condition has a separate output and fit-level checkpoint/hash receipts.
Publication is opt-in and attempted for both completed and failed batches.
This batch never shuts down the host or changes any frozen predecessor.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import publish_research_run, q9_batch, q13_neural
from scripts.q13_neural import CONDITIONS, MATRIX

ORDER = (
    "Q8_FIXED20", "Q9_SHARED_RAW_CE", "Q9_SHARED_FIXED20",
    "Q8_SRC2", "Q8_SRC4", "Q8_SRC6",
    "Q9_SHARED_SRC2", "Q9_SHARED_SRC4", "Q9_SHARED_SRC6",
    "Q8_SOURCE_SESSION_T", "Q8_SOURCE_SESSION_E",
    "Q9_SHARED_SOURCE_SESSION_T", "Q9_SHARED_SOURCE_SESSION_E",
)


def now_utc() -> str:
    return datetime.now(UTC).isoformat()


def plan(only_experiment: str | None = None) -> list[dict]:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    if set(ORDER) != set(CONDITIONS) or matrix["total_new_deep_fits"] != 837:
        raise AssertionError("Q13 execution plan differs from frozen matrix")
    jobs = []
    for condition in ORDER:
        experiment = CONDITIONS[condition][0]
        if only_experiment is None or experiment == only_experiment:
            jobs.append({"experiment_id": experiment, "condition": condition,
                         "expected_fits": 108 if experiment == "Q13-E004" else 27})
    if not jobs:
        raise ValueError("No Q13 jobs selected")
    return jobs


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def validate_publish_destination(output_root: Path) -> None:
    if output_root.resolve() != (ROOT / "results").resolve():
        raise ValueError("--publish requires this repository's results directory")


def preflight(*, output_root: Path, publish: bool, device: str) -> None:
    q13_neural.assert_pretarget_git_freeze()
    q13_neural._check_q5_reuse()
    q13_neural.q9_source_only_epochs()
    if device != "cuda":
        raise RuntimeError("Q13 paid batch requires a real CUDA device")
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; Q13 batch not started")
    if publish:
        validate_publish_destination(output_root)
        publish_research_run._preflight(ROOT)


def execute(jobs: list[dict], *, data_dir: Path, output_root: Path,
            device: str, python: str) -> int:
    if not data_dir.is_dir():
        raise FileNotFoundError(f"BNCI raw data directory absent: {data_dir}")
    if device == "cuda":
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA unavailable; Q13 GPU batch not started")
    batch = output_root / "Q13-BATCH"
    batch.mkdir(parents=True, exist_ok=True)
    receipt_path = batch / "batch_status.json"
    receipt = {"status": "running", "planned_jobs": jobs, "updated_at_utc": now_utc()}
    _atomic_json(receipt_path, receipt)
    for job in jobs:
        name = f"{job['experiment_id']}_{job['condition']}"
        job_dir = batch / "jobs" / name
        job_dir.mkdir(parents=True, exist_ok=True)
        command = [python, str(ROOT / "scripts/q13_neural.py"),
                   "--condition", job["condition"], "--data-dir", str(data_dir),
                   "--output-root", str(output_root), "--device", device]
        _atomic_json(job_dir / "command.json", {"argv": command, "cwd": str(ROOT),
                                                "started_at_utc": now_utc()})
        with (job_dir / "run.log").open("a", encoding="utf-8") as log:
            log.write(f"\nQ13 invocation {now_utc()}\n")
            log.flush()
            process = subprocess.run(command, cwd=ROOT, stdout=log,
                                     stderr=subprocess.STDOUT, check=False)
        condition_status = output_root / job["experiment_id"] / job["condition"] / "status.json"
        actual = (json.loads(condition_status.read_text(encoding="utf-8"))
                  if condition_status.exists() else {})
        passed = (process.returncode == 0 and actual.get("status") == "complete"
                  and actual.get("completed_final_fits") == job["expected_fits"])
        _atomic_json(job_dir / "status.json", {"status": "complete" if passed else "failed",
                                                 "returncode": process.returncode,
                                                 "condition_status": actual,
                                                 "updated_at_utc": now_utc()})
        receipt["updated_at_utc"] = now_utc()
        receipt["completed_jobs"] = sum(
            (batch / "jobs" / f"{row['experiment_id']}_{row['condition']}" / "status.json").exists()
            and json.loads((batch / "jobs" / f"{row['experiment_id']}_{row['condition']}" / "status.json")
                           .read_text(encoding="utf-8")).get("status") == "complete"
            for row in jobs)
        receipt["last_job"] = name
        receipt["status"] = "running" if passed else "failed_stopped"
        _atomic_json(receipt_path, receipt)
        if not passed:
            return process.returncode or 1
    receipt["status"] = "fits_complete_pending_independent_validation"
    receipt["updated_at_utc"] = now_utc()
    _atomic_json(receipt_path, receipt)
    validation_command = [python, str(ROOT / "scripts/validate_q13.py"),
                          "--results-root", str(output_root),
                          "--data-dir", str(data_dir), "--device", device]
    with (batch / "validation.log").open("a", encoding="utf-8") as log:
        log.write(f"\nQ13 independent validation {now_utc()}\n")
        log.flush()
        validation = subprocess.run(validation_command, cwd=ROOT, stdout=log,
                                    stderr=subprocess.STDOUT, check=False)
    report_path = batch / "validation_report.json"
    report = (json.loads(report_path.read_text(encoding="utf-8"))
              if report_path.is_file() else {})
    scientific_pass = (
        validation.returncode == 0 and report.get("status") == "passed"
        and report.get("checkpoint_replays") == 837
    )
    receipt["status"] = (
        "complete_validated" if scientific_pass else "failed_stopped"
    )
    receipt["validation_returncode"] = validation.returncode
    receipt["updated_at_utc"] = now_utc()
    _atomic_json(receipt_path, receipt)
    return 0 if scientific_pass else (validation.returncode or 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Actually train; omitted means plan only")
    parser.add_argument("--only-experiment", choices=("Q13-E001", "Q13-E004", "Q13-E005"))
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--output-root", type=Path, default=ROOT / "results")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--publish", action="store_true",
                        help="publish validated or failed records noninteractively")
    args = parser.parse_args()
    jobs = plan(args.only_experiment)
    if not args.execute:
        if args.publish:
            parser.error("--publish requires --execute")
        print(json.dumps({"status": "dry_run_no_training", "jobs": jobs,
                          "new_fits": sum(job["expected_fits"] for job in jobs)}, indent=2))
        return 0
    if args.only_experiment:
        raise RuntimeError("Partial Q13 batch cannot produce an all-Q13 validation receipt; "
                           "use the full sequence or invoke q13_neural for a condition")
    output_root = args.output_root.resolve()
    preflight(output_root=output_root, publish=args.publish, device=args.device)
    batch = output_root / "Q13-BATCH"
    batch.mkdir(parents=True, exist_ok=True)
    lock = q9_batch._lock(batch / "batch.lock")
    try:
        try:
            result = execute(jobs, data_dir=args.data_dir.resolve(),
                             output_root=output_root, device=args.device,
                             python=args.python)
        except Exception as error:  # noqa: BLE001 - preserve unexpected cloud failure
            _atomic_json(batch / "batch_status.json", {
                "status": "failed_stopped", "error": str(error),
                "traceback": traceback.format_exc(limit=10),
                "updated_at_utc": now_utc(), "planned_jobs": jobs,
            })
            result = 1
        if args.publish:
            published = {}
            for experiment in ("Q13-E001", "Q13-E004", "Q13-E005"):
                attempt = subprocess.run(
                    [args.python, "scripts/publish_research_run.py",
                     "--batch-dir", str(batch),
                     "--experiment-dir", str(output_root / experiment)],
                    cwd=ROOT, stdin=subprocess.DEVNULL, check=False,
                )
                published[experiment] = attempt.returncode == 0
            _atomic_json(batch / "publication_summary.json", {
                "status": "published_all" if all(published.values()) else "publication_pending",
                "experiments": published, "updated_at_utc": now_utc(),
            })
            # Publish the summary itself in the same allowlisted batch directory.
            final = subprocess.run(
                [args.python, "scripts/publish_research_run.py", "--batch-dir", str(batch),
                 "--experiment-dir", str(output_root / "Q13-E005")],
                cwd=ROOT, stdin=subprocess.DEVNULL, check=False,
            )
            if not all(published.values()) or final.returncode:
                result = result or 2
        return result
    finally:
        lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
