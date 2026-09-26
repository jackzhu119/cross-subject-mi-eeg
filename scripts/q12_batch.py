"""Single-GPU resumable Q12 source-only queue; no target-driven job selection.

The six conditions are immutable and run in matrix order. Every source-only
selection finishes before any final target predictions. Failed jobs retain
their logs, checkpoints, and status for a later same-protocol resume.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import publish_research_run, q9_batch, q9_validate_batch, q12_dg

MATRIX = ROOT / "research_runs/Q12-PREP-20260926/MATRIX.json"
CODE_FILES = (
    "research_runs/Q12-PREP-20260926/MATRIX.json",
    "research_runs/Q12-PREP-20260926/PROTOCOL.md",
    "scripts/q12_dg.py", "scripts/q12_batch.py", "scripts/validate_q12.py",
    "scripts/q9_neural.py", "scripts/q9_batch.py", "scripts/q9_validate_batch.py",
    "scripts/q11_neural.py", "scripts/validate_q11_e001.py", "scripts/run_eegnet.py",
    "scripts/publish_research_run.py",
    "src/mi_eeg/data/bnci_epochs.py", "src/mi_eeg/models/eegnet_training.py",
)


def validate_publish_destination(output_root: Path) -> None:
    if output_root.resolve() != (ROOT / "results").resolve():
        raise ValueError("--publish requires this repository's results directory")


def preflight(python: str, *, publish: bool = False) -> None:
    q12_dg.assert_pretarget_git_freeze()
    q8_report = q9_batch.read_json(ROOT / "research_runs/Q8-E001/analysis/validation_report.json")
    if (q8_report.get("status") != "passed"
            or q8_report.get("target_training_leakage_detected") is not False
            or q8_report.get("n_final_fits") != 27):
        raise RuntimeError("Frozen Q8 comparator lacks a passing independent validation receipt")
    if publish:
        # Resolve Git branch, remote, SSH write permission and clean index
        # before spending paid GPU time. The publisher repeats this at push.
        publish_research_run._preflight(ROOT)
    script = (
        "import torch,torchaudio,braindecode,mne,moabb; "
        "assert torch.cuda.is_available(), 'CUDA unavailable'; "
        "assert torch.isfinite(torch.ones(1,device='cuda')).all(); "
        "print(torch.__version__,torchaudio.__version__,torch.cuda.get_device_name(0))"
    )
    subprocess.run([python, "-c", script], cwd=ROOT, check=True, timeout=120)


def build_manifest(data_dir: Path, output_root: Path, python: str) -> dict:
    matrix = q9_batch.read_json(MATRIX)
    rows = matrix["conditions"]
    names = [row["id"] for row in rows]
    if (len(names) != 6 or len(set(names)) != 6
            or sum(int(row["inner_fits"]) for row in rows) != 216
            or sum(int(row["final_fits"]) for row in rows) != 162):
        raise AssertionError("Q12 fit arithmetic or condition set changed")
    for row in rows:
        if row["experiment_id"] not in {"Q12-E001", "Q12-E002"}:
            raise AssertionError("Unknown Q12 result directory")
    jobs = []
    # Complete all source-only model selection before first outer target inference.
    for phase in ("selection", "final"):
        for row in rows:
            name = q9_batch.safe_name(row["id"])
            experiment = row["experiment_id"]
            output = output_root / experiment / name
            jobs.append({
                "job_id": q9_batch.safe_name(f"{experiment}_{name}_{phase}"),
                "experiment_id": experiment, "condition": name, "phase": phase,
                "argv": [python, "scripts/q12_dg.py", "--condition", name,
                         "--phase", phase, "--data-dir", str(data_dir.resolve()),
                         "--output-root", str(output_root.resolve()), "--device", "cuda"],
                "completion_status": str((output / ("selection_provenance.json" if phase == "selection"
                                                    else "status.json")).resolve()),
                "completion_value": ("frozen_before_Q12_target_inference" if phase == "selection"
                                     else "complete"),
            })
    return {
        "schema_version": 1, "created_at_utc": q9_batch.now(),
        "scope": "Q12_source_only_orchestration_plus_independent_scientific_validation",
        "matrix_path": str(MATRIX.resolve()), "matrix_sha256": q9_batch.sha256(MATRIX),
        "code_sha256": {name: q9_batch.sha256(ROOT / name) for name in CODE_FILES},
        "selected_conditions": names, "unselected_planned_conditions": [],
        "selected_fit_counts": {"deep_inner": 216, "deep_final": 162, "shallow_source": 0},
        "data_dir": str(data_dir.resolve()), "output_root": str(output_root.resolve()),
        "device": "cuda", "python_executable": python, "jobs": jobs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT / "results")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--execute", action="store_true",
                        help="Explicitly activate paid GPU training after all gates")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    output = args.output_root.resolve()
    batch = output / "Q12-BATCH"
    manifest = build_manifest(args.data_dir.resolve(), output, sys.executable)
    if args.plan_only or not args.execute:
        if args.publish:
            parser.error("--publish requires --execute")
        print(json.dumps({"status": "plan_only_no_gpu_job_started",
                          "activation": "pass --execute only after reviewed Git freeze",
                          "jobs": manifest["jobs"],
                          "fit_counts": manifest["selected_fit_counts"]}, indent=2))
        return 0
    if args.publish:
        validate_publish_destination(output)
    if not args.data_dir.is_dir():
        raise FileNotFoundError(args.data_dir)
    preflight(sys.executable, publish=args.publish)
    batch.mkdir(parents=True, exist_ok=True)
    lock = q9_batch._lock(batch / "batch.lock")
    try:
        manifest_path = batch / "batch_manifest.json"
        if manifest_path.exists():
            previous = q9_batch.read_json(manifest_path)
            if q9_batch.stable_manifest(previous) != q9_batch.stable_manifest(manifest):
                raise RuntimeError("Existing Q12 batch differs; refusing mixed-protocol resume")
            manifest = previous
        else:
            q9_batch.atomic_json(manifest_path, manifest)
        environment = {**os.environ, "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
                       "PYTHONUNBUFFERED": "1", "MNE_DATA": str(args.data_dir.resolve())}
        status = {"status": "running", "started_or_resumed_at_utc": q9_batch.now(),
                  "planned_jobs": 12, "completed_jobs": 0,
                  "manifest_sha256": q9_batch.sha256(manifest_path),
                  "planned_inner_fits": 216, "planned_final_fits": 162}
        q9_batch.atomic_json(batch / "batch_status.json", status)
        try:
            for job in manifest["jobs"]:
                q9_batch.run_job(job, batch, environment)
                status["completed_jobs"] += 1
                q9_batch.atomic_json(batch / "batch_status.json", status)
            orchestration = q9_validate_batch.validate(batch)
            q9_batch.atomic_json(batch / "orchestration_validation.json", orchestration)
            if orchestration["status"] != "passed_orchestration_only":
                raise RuntimeError(f"Q12 job/receipt validation failed: {orchestration['errors']}")
            scientific = subprocess.run(
                [sys.executable, "scripts/validate_q12.py", "--results-root", str(output),
                 "--data-dir", str(args.data_dir.resolve())],
                cwd=ROOT, env=environment, check=False)
            if scientific.returncode:
                raise RuntimeError("Q12 independent scientific validation failed")
            status.update({"status": "complete_validated", "completed_jobs": 12,
                           "finished_at_utc": q9_batch.now()})
            result = 0
        except Exception as error:  # noqa: BLE001 - persist every cloud failure
            status.update({"status": "failed_stopped", "error": str(error),
                           "traceback": traceback.format_exc(limit=10),
                           "stopped_at_utc": q9_batch.now()})
            result = 1
        q9_batch.atomic_json(batch / "batch_status.json", status)
        if args.publish:
            for experiment in ("Q12-E001", "Q12-E002"):
                published = subprocess.run(
                    [sys.executable, "scripts/publish_research_run.py",
                     "--batch-dir", str(batch), "--experiment-dir", str(output / experiment)],
                    cwd=ROOT, env=environment, check=False)
                if result == 0 and published.returncode:
                    result = 2
        return result
    finally:
        lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
