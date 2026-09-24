"""Sequential, resumable Q10-E001 CUDA queue; no target-metric-based decisions.

The Q9 batch helpers are imported without modifying the frozen Q9 code or
results. This supervisor has its own manifest/lock directory and additionally
requires a prediction-level Q10 scientific validator before marking complete.
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

MATRIX = ROOT / "research_runs/Q10-E001/MATRIX.json"
CONDITIONS = ("MU_BETA_CSP8_EEGNET", "MU_BETA_PCA8_EEGNET")
CODE_FILES = (
    "scripts/q10_e001_batch.py",
    "scripts/q10_spatial_neural.py",
    "scripts/validate_q10_e001.py",
    "scripts/q9_spatial_features.py",
    "scripts/q9_batch.py",
    "scripts/q9_validate_batch.py",
    "scripts/run_eegnet.py",
    "src/mi_eeg/data/bnci_epochs.py",
    "src/mi_eeg/models/eegnet_training.py",
    "src/mi_eeg/evaluation/splits.py",
)


def preflight(python: str) -> None:
    """Fail before training if the actual cloud CUDA/import stack is broken."""
    code = (
        "import torch,torchaudio,braindecode,mne,moabb; "
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
    output_root = args.output_root.resolve()
    batch_dir = output_root / "Q10-BATCH"
    templates = {
        "neural": [sys.executable, "scripts/q10_spatial_neural.py", "--condition",
                   "{condition}", "--phase", "{phase}", "--data-dir", "{data_dir}",
                   "--output-root", "{output_root}", "--device", "{device}"],
        "psd": [sys.executable, "-c", "raise SystemExit('not a Q10-E001 job')"],
    }
    manifest = q9_batch.build_manifest(MATRIX, templates, list(CONDITIONS),
                                       args.data_dir.resolve(), output_root,
                                       args.device, sys.executable)
    for job in manifest["jobs"]:
        if job["phase"] == "selection":
            job["completion_value"] = "frozen_before_Q10_target_inference"
    manifest["code_sha256"] = {name: q9_batch.sha256(ROOT / name) for name in CODE_FILES}
    manifest["scope"] = "Q10_E001_source_only_orchestration_plus_science_audit"
    if manifest["selected_fit_counts"] != {"deep_inner": 72, "deep_final": 54,
                                            "shallow_source": 0}:
        raise AssertionError("Q10-E001 planned fit count changed")
    if args.plan_only:
        print(json.dumps({"jobs": manifest["jobs"],
                          "fit_counts": manifest["selected_fit_counts"]}, indent=2))
        return 0
    if not args.data_dir.is_dir():
        raise FileNotFoundError(args.data_dir)
    preflight(sys.executable)
    batch_dir.mkdir(parents=True, exist_ok=True)
    lock = q9_batch._lock(batch_dir / "batch.lock")
    try:
        manifest_file = batch_dir / "batch_manifest.json"
        if manifest_file.exists():
            previous = q9_batch.read_json(manifest_file)
            if q9_batch.stable_manifest(previous) != q9_batch.stable_manifest(manifest):
                raise RuntimeError("Existing Q10 manifest differs; refusing to mix runs")
            manifest = previous
        else:
            q9_batch.atomic_json(manifest_file, manifest)
        environment = {**os.environ, "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
                       "PYTHONUNBUFFERED": "1", "MNE_DATA": str(args.data_dir.resolve())}
        status = {"status": "running", "started_or_resumed_at_utc": q9_batch.now(),
                  "planned_jobs": len(manifest["jobs"]), "completed_jobs": 0,
                  "manifest_sha256": q9_batch.sha256(manifest_file)}
        q9_batch.atomic_json(batch_dir / "batch_status.json", status)
        try:
            for job in manifest["jobs"]:
                q9_batch.run_job(job, batch_dir, environment)
                status["completed_jobs"] += 1
                q9_batch.atomic_json(batch_dir / "batch_status.json", status)
            orchestration = q9_validate_batch.validate(batch_dir)
            q9_batch.atomic_json(batch_dir / "orchestration_validation.json", orchestration)
            if orchestration["status"] != "passed_orchestration_only":
                raise RuntimeError(f"Orchestration validation failed: {orchestration['errors']}")
            scientific = subprocess.run(
                [sys.executable, "scripts/validate_q10_e001.py", "--results-root",
                 str(output_root)], cwd=ROOT, env=environment, check=False)
            if scientific.returncode:
                raise RuntimeError("Q10-E001 scientific validation failed")
            status.update({"status": "complete_validated", "completed_jobs": len(manifest["jobs"]),
                           "finished_at_utc": q9_batch.now()})
            q9_batch.atomic_json(batch_dir / "batch_status.json", status)
            result = 0
        except Exception as exc:  # noqa: BLE001 - write a terminal failure receipt for every job error
            status.update({"status": "failed_stopped", "error": str(exc),
                           "traceback": traceback.format_exc(limit=10),
                           "stopped_at_utc": q9_batch.now()})
            q9_batch.atomic_json(batch_dir / "batch_status.json", status)
            result = 1
        if args.publish:
            subprocess.run([sys.executable, "scripts/publish_research_run.py",
                            "--batch-dir", str(batch_dir), "--experiment-dir",
                            str(output_root / "Q10-E001")], cwd=ROOT, env=environment,
                           check=False)
        return result
    finally:
        lock.close()


if __name__ == "__main__":
    sys.exit(main())
