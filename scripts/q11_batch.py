"""Single-GPU resumable Q11-E001 queue with scientific validation and Git receipt.

All four conditions run in fixed matrix order, irrespective of interim target
performance. Interruption preserves completed hashed fits. A failed condition
stops the queue with logs, checkpoints and a failure receipt intact.
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

from scripts import q9_batch, q9_validate_batch

MATRIX = ROOT / "research_runs/Q11-E001/MATRIX.json"
CONDITIONS = ("FOUR_BAND_SHARED", "TWO_BAND_INDEPENDENT",
              "TWO_BAND_EARLY_STACK", "BROAD_CAPACITY_MATCHED")
CODE_FILES = (
    "scripts/q11_neural.py", "scripts/q11_batch.py", "scripts/validate_q11_e001.py",
    "scripts/q9_neural.py", "scripts/q9_batch.py", "scripts/q9_validate_batch.py",
    "scripts/run_eegnet.py", "src/mi_eeg/data/bnci_epochs.py",
    "src/mi_eeg/models/eegnet_training.py", "src/mi_eeg/evaluation/splits.py",
)


def preflight(python: str) -> None:
    code = (
        "import torch,torchaudio,braindecode,mne,moabb,matplotlib; "
        "assert torch.cuda.is_available(), 'CUDA unavailable'; "
        "assert torch.isfinite(torch.ones(1,device='cuda')).all(); "
        "print(torch.__version__,torchaudio.__version__,torch.cuda.get_device_name(0))"
    )
    subprocess.run([python, "-c", code], cwd=ROOT, check=True, timeout=120)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT / "results")
    parser.add_argument("--device", choices=("cuda",), default="cuda")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    output = args.output_root.resolve()
    batch = output / "Q11-BATCH"
    templates = {
        "neural": [sys.executable, "scripts/q11_neural.py", "--condition", "{condition}",
                   "--phase", "{phase}", "--data-dir", "{data_dir}",
                   "--output-root", "{output_root}", "--device", "{device}"],
        "psd": [sys.executable, "-c", "raise SystemExit('not a Q11-E001 job')"],
    }
    manifest = q9_batch.build_manifest(MATRIX, templates, list(CONDITIONS),
                                       args.data_dir.resolve(), output, args.device,
                                       sys.executable)
    for job in manifest["jobs"]:
        if job["phase"] == "selection":
            job["completion_value"] = "frozen_before_Q11_target_inference"
    manifest["code_sha256"] = {file: q9_batch.sha256(ROOT / file) for file in CODE_FILES}
    manifest["scope"] = "Q11_E001_orchestration_and_independent_prediction_audit"
    if manifest["selected_fit_counts"] != {"deep_inner": 144,
                                            "deep_final": 108,
                                            "shallow_source": 0}:
        raise AssertionError("Q11-E001 fit arithmetic changed")
    if args.plan_only:
        print(json.dumps({"jobs": manifest["jobs"],
                          "fit_counts": manifest["selected_fit_counts"]}, indent=2))
        return 0
    if not args.data_dir.is_dir():
        raise FileNotFoundError(args.data_dir)
    preflight(sys.executable)
    batch.mkdir(parents=True, exist_ok=True)
    lock = q9_batch._lock(batch / "batch.lock")
    try:
        manifest_path = batch / "batch_manifest.json"
        if manifest_path.exists():
            previous = q9_batch.read_json(manifest_path)
            if q9_batch.stable_manifest(previous) != q9_batch.stable_manifest(manifest):
                raise RuntimeError("Q11 existing batch manifest differs; refusing mixed protocol")
            manifest = previous
        else:
            q9_batch.atomic_json(manifest_path, manifest)
        env = {**os.environ, "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
               "PYTHONUNBUFFERED": "1", "MNE_DATA": str(args.data_dir.resolve())}
        status = {"status": "running", "started_or_resumed_at_utc": q9_batch.now(),
                  "planned_jobs": len(manifest["jobs"]), "completed_jobs": 0,
                  "manifest_sha256": q9_batch.sha256(manifest_path),
                  "planned_inner_fits": 144, "planned_final_fits": 108}
        q9_batch.atomic_json(batch / "batch_status.json", status)
        try:
            for job in manifest["jobs"]:
                q9_batch.run_job(job, batch, env)
                status["completed_jobs"] += 1
                q9_batch.atomic_json(batch / "batch_status.json", status)
            orchestration = q9_validate_batch.validate(batch)
            q9_batch.atomic_json(batch / "orchestration_validation.json", orchestration)
            if orchestration["status"] != "passed_orchestration_only":
                raise RuntimeError(f"Q11 job validation failed: {orchestration['errors']}")
            scientific = subprocess.run(
                [sys.executable, "scripts/validate_q11_e001.py", "--results-root", str(output)],
                cwd=ROOT, env=env, check=False)
            if scientific.returncode:
                raise RuntimeError("Q11 independent scientific validation failed")
            status.update({"status": "complete_validated", "completed_jobs": len(manifest["jobs"]),
                           "finished_at_utc": q9_batch.now()})
            result = 0
        except Exception as exc:  # noqa: BLE001 - retain stopped batch receipt
            status.update({"status": "failed_stopped", "error": str(exc),
                           "traceback": traceback.format_exc(limit=10),
                           "stopped_at_utc": q9_batch.now()})
            result = 1
        q9_batch.atomic_json(batch / "batch_status.json", status)
        if args.publish:
            published = subprocess.run(
                [sys.executable, "scripts/publish_research_run.py",
                 "--batch-dir", str(batch), "--experiment-dir", str(output / "Q11-E001")],
                cwd=ROOT, env=env, check=False)
            if result == 0 and published.returncode:
                return 2
        return result
    finally:
        lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
