"""Detached, resumable Q14 validation then Q12/Q13 cloud queue.

This supervisor never changes experiment conditions or interprets outer-target
scores. Q14 performs only the versioned independent validation of frozen R2
predictions, with zero new fits or inference rows. Its failure is recorded but
does not suppress the independent BNCI Q12/Q13 jobs. A Q12 or Q13 failure
stops that training sequence. Each child owns its scientific validator and
publication; the queue also publishes its own receipt and logs on failure.
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import q9_batch

BATCH = ROOT / "results/Q12-BATCH"
RECEIPT = BATCH / "paper_queue_status.json"
MANIFEST = BATCH / "paper_queue_manifest.json"
SUCCESSFUL_PUBLICATION = {"pushed", "pushed_with_skipped_files"}
SOURCE_FILES = (
    "scripts/paper_cloud_queue.py", "scripts/run_paper_cloud.sh",
    "scripts/q14_r2_portable_finalize.py", "scripts/q14_r2_validate.py",
    "scripts/q14_r2_numeric.py",
    "research_runs/Q14-E002R2/VALIDATION_PORTABILITY_AMENDMENT_20260926.md",
    "scripts/q12_batch.py", "scripts/q12_dg.py", "scripts/validate_q12.py",
    "scripts/q13_batch.py", "scripts/q13_neural.py", "scripts/validate_q13.py",
    "scripts/q9_batch.py", "scripts/q9_neural.py",
    "scripts/publish_research_run.py", "scripts/run_eegnet.py",
    "src/mi_eeg/data/bnci_epochs.py", "src/mi_eeg/models/eegnet_training.py",
    "research_runs/Q12-PREP-20260926/MATRIX.json",
    "research_runs/Q13-PREP-20260926/MATRIX.json",
)


def now() -> str:
    return datetime.now(UTC).isoformat()


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stages(python: str, data_dir: Path, physionet_dir: Path) -> list[dict]:
    """A fixed order and fit budget, independent of all target outcomes."""
    first = [python, "scripts/q14_r2_portable_finalize.py", "--execute",
             "--data-dir", str(physionet_dir)]
    command = [python, "scripts/q12_batch.py", "--execute", "--publish",
               "--data-dir", str(data_dir)]
    second = [python, "scripts/q13_batch.py", "--execute", "--publish",
              "--data-dir", str(data_dir), "--device", "cuda"]
    return [
        {"id": "Q14_PORTABLE_VALIDATION", "new_deep_fits": 0, "argv": first,
         "failure_policy": "record_and_continue_independent_BNCI_stages",
         "batch_status": "results/Q14-R2PORT/batch_status.json",
         "scientific_report": "results/Q14-E002R2V1/validation_report.json"},
        {"id": "Q12", "new_deep_fits": 378, "argv": command,
         "failure_policy": "stop_training_sequence",
         "batch_status": "results/Q12-BATCH/batch_status.json",
         "scientific_report": "results/Q12-BATCH/scientific_validation.json",
         "scientific_pass": "passed_scientific_checks"},
        {"id": "Q13", "new_deep_fits": 837, "argv": second,
         "failure_policy": "stop_training_sequence",
         "batch_status": "results/Q13-BATCH/batch_status.json",
         "scientific_report": "results/Q13-BATCH/validation_report.json",
         "scientific_pass": "passed"},
    ]


def build_manifest(python: str, data_dir: Path, physionet_dir: Path) -> dict:
    files = {name: sha256(ROOT / name) for name in SOURCE_FILES}
    return {
        "schema_version": 1,
        "purpose": "post_hoc_source_only_Q12_then_Q13_no_target_driven_selection",
        "python": str(Path(python).resolve()),
        "data_dir": str(data_dir.resolve()),
        "physionet_dir": str(physionet_dir.resolve()),
        "output_root": str((ROOT / "results").resolve()),
        "source_sha256": files,
        "stages": stages(str(Path(python).resolve()), data_dir.resolve(),
                         physionet_dir.resolve()),
        "total_new_deep_fits": 1215,
        "q14_validation_only": True,
        "automatic_shutdown": False,
    }


def check_scientific_receipt(stage: dict) -> dict[str, str]:
    batch_path = ROOT / stage["batch_status"]
    report_path = ROOT / stage["scientific_report"]
    batch = read_json(batch_path)
    report = read_json(report_path)
    if batch.get("status") != "complete_validated":
        raise RuntimeError(f"{stage['id']} batch is not complete_validated")
    if stage["id"] == "Q14_PORTABLE_VALIDATION":
        if (report.get("passed") is not True
                or report.get("validation_attempt_id") != "Q14-E002R2V1"
                or report.get("n_subjects") != 109
                or report.get("n_verified_official_edf_files") != 327
                or report.get("external_target_fit_count") != 0):
            raise RuntimeError("Q14 portable independent 327-EDF scientific validation did not pass")
        completion = read_json(ROOT / "results/Q14-R2PORT/completion_receipt.json")
        if completion.get("github_published") is not True:
            raise RuntimeError("Q14 portable completion/publication receipt missing")
    elif report.get("status") != stage["scientific_pass"]:
        raise RuntimeError(f"{stage['id']} independent scientific report did not pass")
    if stage["id"] == "Q12" and (report.get("inner_fits"), report.get("final_fits")) != (216, 162):
        raise RuntimeError("Q12 scientific fit counts differ from frozen matrix")
    if stage["id"] == "Q13" and report.get("checkpoint_replays") != 837:
        raise RuntimeError("Q13 checkpoint replay count differs from frozen matrix")
    return {"batch_status_sha256": sha256(batch_path),
            "scientific_report_sha256": sha256(report_path)}


def _publish_queue(python: str) -> bool:
    """Publish the queue's own records with a named Q12 result directory."""
    command = [python, "scripts/publish_research_run.py", "--batch-dir", str(BATCH),
               "--experiment-dir", str(ROOT / "results/Q12-E001")]
    environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0",
                   "GIT_ASKPASS": "/bin/false", "SSH_ASKPASS": "/bin/false"}
    with (BATCH / "paper_queue_publish.log").open("a", encoding="utf-8") as log:
        log.write(f"\n[{now()}] publish queue receipt and logs\n")
        log.flush()
        attempt = subprocess.run(command, cwd=ROOT, env=environment,
                                 stdin=subprocess.DEVNULL, stdout=log,
                                 stderr=subprocess.STDOUT, check=False)
    report = read_json(BATCH / "publish_status.json")
    return attempt.returncode == 0 and report.get("status") in SUCCESSFUL_PUBLICATION


def run(data_dir: Path, physionet_dir: Path, python: str, *, publish: bool) -> int:
    if os.name != "posix":
        raise RuntimeError("Detached cloud queue requires Linux/POSIX")
    if not data_dir.is_dir():
        raise FileNotFoundError(f"BNCI raw data cache missing: {data_dir}")
    if not physionet_dir.is_dir():
        raise FileNotFoundError(f"PhysioNet official EDF cache missing: {physionet_dir}")
    if Path(python).resolve() != Path(sys.executable).resolve():
        raise RuntimeError("Queue interpreter and child interpreter must be identical")
    if not publish:
        raise RuntimeError("Cloud execution must request failure/success publication")
    BATCH.mkdir(parents=True, exist_ok=True)
    lock = q9_batch._lock(BATCH / "paper_queue.lock")
    try:
        frozen = build_manifest(python, data_dir, physionet_dir)
        if MANIFEST.exists():
            if read_json(MANIFEST) != frozen:
                raise RuntimeError("Existing queue manifest differs; refusing mixed-protocol resume")
        else:
            q9_batch.atomic_json(MANIFEST, frozen)
        previous = read_json(RECEIPT)
        previous_stages = previous.get("stages", {}) if isinstance(previous.get("stages"), dict) else {}
        receipt = {
            "status": "running", "started_or_resumed_at_utc": now(),
            "manifest_sha256": sha256(MANIFEST),
            "stages": previous_stages, "total_new_deep_fits_planned": 1215,
            "completed_stages": 0, "stage_failures": [],
            "automatic_shutdown": False,
        }
        q9_batch.atomic_json(RECEIPT, receipt)
        exit_code = 0
        try:
            for stage in frozen["stages"]:
                name = stage["id"]
                prior = receipt["stages"].get(name, {})
                if prior.get("status") == "complete_validated":
                    observed = check_scientific_receipt(stage)
                    if any(observed[key] != prior.get(key) for key in observed):
                        raise RuntimeError(f"{name} validated receipt changed after prior run")
                    print(f"[resume] {name} previously validated, skipping", flush=True)
                    receipt["completed_stages"] += 1
                    q9_batch.atomic_json(RECEIPT, receipt)
                    continue
                state = {"status": "running", "argv": stage["argv"],
                         "started_at_utc": now(),
                         "attempts": int(prior.get("attempts", 0)) + 1}
                receipt["current_stage"] = name
                receipt["stages"][name] = state
                q9_batch.atomic_json(RECEIPT, receipt)
                log_path = BATCH / f"paper_queue_{name.lower()}.log"
                with log_path.open("a", encoding="utf-8") as log:
                    log.write(f"\n[{now()}] invocation {state['attempts']}\n")
                    log.flush()
                    process = subprocess.run(stage["argv"], cwd=ROOT,
                                             stdin=subprocess.DEVNULL, stdout=log,
                                             stderr=subprocess.STDOUT, check=False)
                state["returncode"] = process.returncode
                state["log_sha256"] = sha256(log_path)
                state["finished_at_utc"] = now()
                stage_error = (f"{name} batch failed with exit {process.returncode}"
                               if process.returncode else None)
                if stage_error is None:
                    try:
                        state.update(check_scientific_receipt(stage))
                    except Exception as error:  # noqa: BLE001 - preserve and categorize
                        stage_error = f"{name} scientific receipt failed: {error}"
                if stage_error is not None:
                    state["status"] = "failed_stopped"
                    state["error"] = stage_error
                    receipt["stage_failures"].append(name)
                    q9_batch.atomic_json(RECEIPT, receipt)
                    if stage["failure_policy"] == "record_and_continue_independent_BNCI_stages":
                        print(f"[continue] {name} validation failed; Q12/Q13 remain independent", flush=True)
                        continue
                    raise RuntimeError(stage_error)
                state["status"] = "complete_validated"
                receipt["completed_stages"] += 1
                q9_batch.atomic_json(RECEIPT, receipt)
            receipt["status"] = ("complete_validated" if not receipt["stage_failures"]
                                 else "completed_with_q14_validation_failure")
            receipt.pop("current_stage", None)
            if receipt["stage_failures"]:
                exit_code = 1
        except Exception as error:  # noqa: BLE001 - keep cloud failure evidence
            receipt["status"] = "failed_stopped"
            receipt["error"] = str(error)
            receipt["traceback"] = traceback.format_exc(limit=12)
            if receipt.get("current_stage") in receipt["stages"]:
                receipt["stages"][receipt["current_stage"]]["status"] = "failed_stopped"
            exit_code = 1
        receipt["finished_at_utc"] = now()
        q9_batch.atomic_json(RECEIPT, receipt)
        published = _publish_queue(python)
        print(f"[queue] status={receipt['status']} publication={'pushed' if published else 'pending'}", flush=True)
        if not published:
            exit_code = exit_code or 2
        return exit_code
    finally:
        lock.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--physionet-dir", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="Activate paid GPU fits")
    parser.add_argument("--publish", action="store_true", help="Publish success or failure")
    args = parser.parse_args()
    if not args.execute:
        if args.publish:
            parser.error("--publish requires --execute")
        print(json.dumps({"status": "plan_only_no_training",
                          "manifest": build_manifest(sys.executable, args.data_dir,
                                                     args.physionet_dir)},
                         ensure_ascii=False, indent=2))
        return 0
    return run(args.data_dir.resolve(), args.physionet_dir.resolve(),
               sys.executable, publish=args.publish)


if __name__ == "__main__":
    raise SystemExit(main())
