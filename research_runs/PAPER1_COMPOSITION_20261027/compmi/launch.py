"""Prepare frozen task metadata and submit one resumable school-HPC job.

No dependency installation, EEG download, preprocessing or GPU work happens on
login1. The existing prepared-data identity and original common folds are reused.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
import uuid

from hpcmi.common import atomic_json, canonical_hash, exclusive_lock, read_json, utc_now

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARENT = Path("/public/home/zhuziyuan/projects")
DEFAULT_PYTHON = "/public/home/zhuziyuan/.venvs/paper3-hpc-cu121-offline/bin/python"
REPOSITORY = "jackzhu119/cross-subject-mi-eeg"
# School system curl already passed TLS/API access; its CA store works where
# this older Python installation's default CA discovery did not.
os.environ.setdefault("PAPER1_GITHUB_TRANSPORT", "curl")


def queue(project, command=subprocess.run):
    result = command(["squeue", "-h", "-u", "zhuziyuan", "-o", "%i|%j|%T|%Z"],
                     text=True, capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise RuntimeError("squeue failed; no duplicate job was submitted: " + result.stderr[:1000])
    observed = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        row = line.split("|")
        if len(row) != 4:
            raise ValueError("Unparseable squeue response; no new submission")
        job, name, state, directory = [p.strip() for p in row]
        if directory == str(project):
            observed.append({"job_id": job, "job_name": name, "scheduler_state": state})
    return observed


def _write_identical(path, value):
    if path.exists():
        if read_json(path) != value:
            raise ValueError("Existing scientific configuration changed; keep this project and version the new experiment")
    else:
        atomic_json(path, value)


def prepare_project(project, base_project, python):
    from hpcmi.data import Registry
    project, base_project = Path(project).resolve(), Path(base_project).resolve()
    if project == base_project:
        raise ValueError("The follow-up needs its own output directory; original results are retained")
    base_paths = read_json(base_project / "config/paths.json")
    receipt = read_json(base_project / "state/data_prepared.json")
    data_dir = Path(base_paths["data_dir"]).resolve()
    if receipt.get("status") != "complete" or Path(receipt.get("data_dir", "")).resolve() != data_dir:
        raise ValueError("Original prepared-data completion receipt is unavailable or inconsistent")
    registry = Registry(data_dir)
    if registry.fingerprint != receipt.get("fingerprint"):
        raise ValueError("Prepared-data identity changed; no re-download or reprocessing was attempted")
    if not Path(python).is_file() or not os.access(python, os.X_OK):
        raise FileNotFoundError("Existing training Python is unavailable: " + str(python))
    for name in ("config", "state", "outputs", "logs/slurm", "logs/workers"):
        (project / name).mkdir(parents=True, exist_ok=True)
    study = read_json(ROOT / "config/study.json")
    _write_identical(project / "config/study.json", study)
    paths = {"project": str(project), "base_project": str(base_project), "data_dir": str(data_dir),
             # Preserve the venv executable path: resolving its symlink would
             # silently select the base interpreter without this environment.
             "training_python": str(Path(python).expanduser().absolute()),
             "classical_python": str(Path(python).expanduser().absolute()),
             "code_root": str(ROOT), "repository": REPOSITORY}
    old = read_json(project / "config/paths.json") if (project / "config/paths.json").exists() else None
    if old and any(old.get(k) != paths[k] for k in ("project", "base_project", "data_dir")):
        raise ValueError("Existing follow-up paths refer to different inputs")
    # Execution-only code/interpreter paths may move; scientific task identities
    # are independently immutable in state/plan.json and every checkpoint.
    atomic_json(project / "config/paths.json", paths)
    atomic_json(project / "state/reused_inputs.json", {"status": "PREPARED_INPUT_IDENTITY_REUSED",
                "data_fingerprint": registry.fingerprint, "data_dir": str(data_dir),
                "base_project": str(base_project), "base_receipt_sha256": hashlib.sha256(
                    (base_project / "state/data_prepared.json").read_bytes()).hexdigest(),
                "observed_at_utc": utc_now(), "raw_redownloaded": False, "preprocessing_repeated": False})
    from .plan import create_plan
    return paths, create_plan(project, registry=registry)


def start_sync(project, python):
    env = {**os.environ, "PYTHONPATH": str(ROOT) + os.pathsep + str(ROOT / "shared"),
           "PYTHONUNBUFFERED": "1", "PYTHONNOUSERSITE": "1",
           "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    stream = (project / "logs/sync.log").open("ab", buffering=0)
    try:
        process = subprocess.Popen([python, "-u", "-m", "compmi.sync", "--project", str(project),
                                    "--daemon", "--interval", "180"], cwd=ROOT, env=env,
                                   stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=True, close_fds=True)
    finally:
        stream.close()
    # Daemon owns an advisory lock; a second launcher cannot create a second
    # uploader. A detached session survives closing the browser terminal.
    return process.pid


def submit(project=DEFAULT_PARENT / "paper1-composition-v2", *, base_project=DEFAULT_PARENT / "paper1-risk-v1",
           python=DEFAULT_PYTHON, partition="hpc_gpu", time_limit="1-00:00:00", reauthorize=False,
           command=subprocess.run, sync_starter=start_sync):
    if os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Run this launcher on login1, outside a compute allocation")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", partition):
        raise ValueError("Invalid Slurm partition")
    if not re.fullmatch(r"(?:\d+-)?\d{1,3}:\d{2}:\d{2}", time_limit):
        raise ValueError("Use a Slurm time limit such as 1-00:00:00; queue maximum is not assumed")
    project = Path(project).expanduser().resolve()
    (project / "state").mkdir(parents=True, exist_ok=True)
    with exclusive_lock(project / "state/submit.lock"):
        paths, plan = prepare_project(project, base_project, python)
        auth_path = project / "config/sync.json"
        first_authorization = not auth_path.exists()
        from hpcmi.github_sync import confirm_credentials
        token_path = confirm_credentials(REPOSITORY, project.name, force=reauthorize or first_authorization,
                                         require_verified=reauthorize or first_authorization)
        atomic_json(auth_path, {"repository": REPOSITORY, "project_id": project.name,
                    "token_file": str(token_path), "branch": "hpc/" + project.name})
        # A reporting outage never cancels or prevents resuming an existing fit.
        try:
            sync_pid = sync_starter(project, paths["training_python"])
        except OSError as error:
            sync_pid = None
            print(json.dumps({"sync_start_pending": True, "error_class": type(error).__name__}), flush=True)
        existing = queue(project, command)
        if existing:
            return {"status": "EXISTING_ALLOCATION_REUSED", "jobs": existing, "sync_pid": sync_pid,
                    "new_jobs_submitted": 0, "new_model_fits_on_login": 0}
        # Completed task identity is checked inside the supervisor on resume.
        # No source/input scan, test suite or pilot is repeated here.
        name = "p1-comp-" + hashlib.sha256(str(project).encode()).hexdigest()[:10]
        logs = project / "logs/slurm"
        logs.mkdir(parents=True, exist_ok=True)  # Slurm opens logs before shell execution.
        script = ROOT / "slurm/single_job.sh"
        args = ["sbatch", "--parsable", "--account=zhuziyuan", "--partition=" + partition,
                "--nodes=1", "--ntasks=1", "--gres=gpu:2", "--cpus-per-task=24", "--mem=128G",
                "--time=" + time_limit, "--signal=B:USR1@180", "--requeue", "--job-name=" + name,
                "--chdir=" + str(project), "--output=" + str(logs / "composition-%j.out"),
                "--error=" + str(logs / "composition-%j.err"), "--export=ALL",
                str(script), str(project), paths["training_python"], str(ROOT)]
        ledger_path = project / "state/submissions.json"
        ledger = read_json(ledger_path) if ledger_path.exists() else {"schema_version": 1, "submissions": []}
        item = {"id": uuid.uuid4().hex, "created_at_utc": utc_now(), "status": "SUBMITTING",
                "command": args, "job_name": name, "task_fingerprint": plan["fingerprint"],
                "resources": {"nodes": 1, "gpus": 2, "total_cpus": 24, "total_memory": "128G", "partition": partition}}
        ledger["submissions"].append(item)
        atomic_json(ledger_path, ledger)
        result = command(args, text=True, capture_output=True, timeout=60, check=False)
        job_id = result.stdout.strip().split(";")[0]
        item.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr,
                    job_id=job_id if re.fullmatch(r"\d+", job_id) else None,
                    status="SUBMITTED" if result.returncode == 0 and re.fullmatch(r"\d+", job_id) else "SUBMISSION_FAILED")
        atomic_json(ledger_path, ledger)
        if item["status"] != "SUBMITTED":
            raise RuntimeError("Slurm submission failed; exact scheduler response retained in " + str(ledger_path))
        return {"status": "ONE_NODE_TWO_GPU_JOB_SUBMITTED", "job_id": job_id, "sync_pid": sync_pid,
                "project": str(project), "task_counts": plan["task_counts"], "resources": item["resources"],
                "new_model_fits_on_login": 0, "gpu_execution_verified": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=DEFAULT_PARENT / "paper1-composition-v2")
    parser.add_argument("--base-project", type=Path, default=DEFAULT_PARENT / "paper1-risk-v1")
    parser.add_argument("--python", default=DEFAULT_PYTHON)
    parser.add_argument("--partition", default="hpc_gpu")
    parser.add_argument("--time", dest="time_limit", default="1-00:00:00")
    parser.add_argument("--reauthorize", action="store_true")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(submit(**vars(args)), allow_nan=False), flush=True)
        return 0
    except Exception:
        traceback.print_exc()
        print("Existing inputs, task records and checkpoints retained; use the same launch command to resume.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
