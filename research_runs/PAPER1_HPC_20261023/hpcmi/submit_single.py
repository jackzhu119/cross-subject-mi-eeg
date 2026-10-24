"""Submit/resume exactly one school-HPC job; no GPU work runs on login1."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import traceback
import uuid

from . import cli
from .common import atomic_json, read_json, utc_now
from .slurm import submission_lock

ROOT = Path(__file__).resolve().parents[1]
OWNER = "zhuziyuan"


def _command(runner, arguments):
    return runner(arguments, capture_output=True, text=True, timeout=30, check=False)


def _queue(runner):
    result = _command(runner, ["squeue", "--array", "-h", "-u", OWNER,
                               "-o", "%i|%j|%u|%T|%P|%Z"])
    if result.returncode:
        raise RuntimeError("squeue failed; no new job submitted: " + result.stderr.strip()[:1000])
    rows = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        values = [v.strip() for v in line.split("|")]
        if len(values) != 6:
            raise RuntimeError("Unparseable scheduler row; no new job submitted")
        rows.append(dict(zip(("id", "name", "owner", "state", "partition", "directory"), values)))
    return rows


def _identity(row, project):
    if row["owner"] != OWNER or row["directory"] != str(project):
        raise RuntimeError("Scheduler user/directory disagrees with this project; no job cancelled or submitted")


def _ledger(path):
    if not path.exists():
        return {"schema_version": 1, "submissions": []}
    value = read_json(path)
    if value.get("schema_version") != 1 or not isinstance(value.get("submissions"), list):
        raise ValueError("Single-job submission record is invalid; existing record retained")
    return value


def _legacy_training(project, rows):
    names = set()
    for name in ("submissions.json", "aux_prep.json", "aux_smoke.json"):
        path = project / "state" / name
        if path.exists():
            records = read_json(path)
            names.update(item["job_name"] for item in records.get("submissions", []) if item.get("job_name"))
    observed = [r for r in rows if r["name"] in names]
    for row in observed:
        _identity(row, project)
    return observed


def _job_memory(value, explicit=False):
    if not isinstance(value, str):
        raise ValueError("Job memory must be a Slurm integer with an optional K/M/G/T/P suffix")
    value = value.strip().upper()
    if not re.fullmatch(r"(?:[1-9]\d*[KMGTP]?|0)", value) or (value == "0" and not explicit):
        raise ValueError("Invalid job memory; use a positive Slurm integer with an optional K/M/G/T/P suffix, or explicitly request 0")
    return value


def _configure_resources(project, memory):
    path = project / "config/cluster.json"
    old = read_json(path)
    new = {**old, "account": OWNER, "squeue_user": OWNER, "partition": "hpc_gpu",
           "gres": "gpu:1", "cpus_per_task": 16, "mem": "128G", "max_parallel": 2,
           "exclude": [], "single_job_memory": memory}
    if old != new:
        stamp = utc_now().replace(":", "").replace("+", "_")
        atomic_json(project / "state" / ("cluster-before-single-" + stamp + ".json"), old)
        atomic_json(path, new)
    return new


def _migrate_download(project, rows, name, runner):
    old = [r for r in rows if r["name"] == name]
    if len(old) > 1:
        raise RuntimeError("Multiple old downloads observed; retained without another submission")
    if not old:
        return None
    item = old[0]
    _identity(item, project)
    if not item["id"].isdigit():
        raise RuntimeError("Old download ID is not a single numeric job; retained")
    if item["state"] != "PENDING":
        return {"status": "LEGACY_DOWNLOAD_ACTIVE_NO_NEW_JOB", "job_id": item["id"],
                "scheduler_state": item["state"]}
    prefix = project / "state" / ("legacy-download-" + item["id"])
    snapshot = prefix.with_name(prefix.name + "-before-single.json")
    if not snapshot.exists():
        atomic_json(snapshot, {"observed_at_utc": utc_now(), "scheduler": item,
                               "reason": "User requested one enclosing Slurm job"})
    original = project / "state/download-data.sbatch"
    backup = prefix.with_name(prefix.name + "-original.sbatch")
    if original.exists() and not backup.exists():
        shutil.copyfile(original, backup)
    result = _command(runner, ["scancel", "--state=PENDING", item["id"]])
    if result.returncode:
        raise RuntimeError("Pending download cancellation failed; no replacement submitted: " + result.stderr.strip()[:1000])
    after = [r for r in _queue(runner) if r["name"] == name]
    atomic_json(prefix.with_name(prefix.name + "-after-single.json"),
                {"observed_at_utc": utc_now(), "scheduler": after})
    if after:
        for row in after:
            _identity(row, project)
        return {"status": "LEGACY_DOWNLOAD_STILL_ACTIVE_NO_NEW_JOB", "job_id": after[0]["id"],
                "scheduler_state": after[0]["state"]}
    return None


def submit(project, python=cli.DEFAULT_PYTHON, raw_dir=None, wheelhouse=None,
           repository=cli.REPOSITORY, runner=None, memory=None):
    """Prepare private configuration on login1, then perform one short submission.

    Network synchronization failures are handled independently by the existing
    GitHub writer. Explicit initial credential rejection still blocks submission.
    No raw EEG, CUDA import, model fitting or checkpoint loading occurs here.
    """
    if os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Run this submission command on login1, outside a compute allocation")
    runner = runner or subprocess.run
    project = Path(project).expanduser().resolve()
    if memory is None:
        cluster_path = project / "config/cluster.json"
        saved_memory = read_json(cluster_path).get("single_job_memory") if cluster_path.exists() else None
        memory = _job_memory(saved_memory, explicit=True) if saved_memory is not None else "240G"
    else:
        memory = _job_memory(memory, explicit=True)
    paths = cli.setup(project, python, raw_dir=raw_dir, repository=repository)
    metadata = cli.runtime_metadata(paths["training_python"])
    atomic_json(project / "state/training_metadata.json", metadata)
    from .github_sync import confirm_credentials
    from .prep_runtime import prepare
    token = confirm_credentials(paths["repository"], project.name)
    atomic_json(project / "config/sync.json", {"repository": paths["repository"],
                "project_id": project.name, "token_file": str(token)})
    prep = prepare(project, paths["training_python"], wheelhouse=wheelhouse or ROOT / "wheelhouse")
    paths["preprocessing_python"] = str(prep)
    atomic_json(project / "config/paths.json", paths)
    log_dir = project / "logs/slurm"
    log_dir.mkdir(parents=True, exist_ok=True)
    script = ROOT / "slurm/single_job.sh"
    if not script.is_file():
        raise FileNotFoundError(script)
    key = hashlib.sha256(str(project).encode()).hexdigest()[:10]
    name = "p1-single-" + key
    ledger_path = project / "state/single_job_submissions.json"
    with submission_lock(project):
        rows = _queue(runner)
        own = [r for r in rows if r["name"] == name]
        if len(own) > 1:
            raise RuntimeError("Multiple matching single jobs observed; no new job submitted")
        ledger = _ledger(ledger_path)
        if own:
            item = own[0]
            _identity(item, project)
            if not item["id"].isdigit():
                raise RuntimeError("Single-job scheduler identity is not numeric")
            if ledger["submissions"]:
                last = ledger["submissions"][-1]
                if last.get("job_id") is None and last["status"] in {"SUBMITTING", "SUBMISSION_UNCERTAIN"}:
                    last.update(job_id=item["id"], status="SUBMITTED_RECOVERED", recovered_at_utc=utc_now())
                    atomic_json(ledger_path, ledger)
            return {"status": "EXISTING_SINGLE_JOB_REUSED", "job_id": item["id"],
                    "scheduler_state": item["state"]}
        if any(item.get("job_id") is None and item["status"] in {"SUBMITTING", "SUBMISSION_UNCERTAIN"}
               for item in ledger["submissions"]):
            raise RuntimeError("Previous sbatch outcome is uncertain; retained intent prevents another submission")
        legacy = _legacy_training(project, rows)
        if legacy:
            return {"status": "LEGACY_TRAINING_ACTIVE_NO_NEW_JOB", "jobs": legacy}
        # Stops only the exact same-user, same-project lightweight old controller.
        # It does not terminate workers or another paper's processes.
        stopped = cli.stop_legacy_controller(project)
        atomic_json(project / "config/execution_mode.json", {"mode": "single_job",
                    "updated_at_utc": utc_now(), "stopped_legacy_controller_pids": stopped})
        cluster = _configure_resources(project, memory)
        blocked = _migrate_download(project, rows, "p1-download-" + key, runner)
        if blocked:
            return blocked
        item = {"submission_id": uuid.uuid4().hex[:12], "created_at_utc": utc_now(),
                "job_name": name, "job_id": None, "status": "SUBMITTING", "project": str(project),
                "shape": {"gpus": 2, "cpus": 32, "memory": memory, "max_worker_processes": 2}}
        ledger["submissions"].append(item)
        atomic_json(ledger_path, ledger)
        output = str(log_dir / "single-%j.out")
        command = ["sbatch", "--parsable", "--nodes=1", "--ntasks=1", "--account=" + OWNER,
                   "--partition=" + cluster["partition"], "--gres=gpu:2", "--cpus-per-task=32",
                   "--mem=" + memory, "--time=" + str(cluster.get("time_limit", "1-00:00:00")),
                   "--signal=B:USR1@180", "--requeue", "--open-mode=append", "--job-name=" + name,
                   "--chdir=" + str(project), "--output=" + output, "--error=" + output,
                   str(script), str(project), paths["training_python"], str(ROOT)]
        try:
            result = _command(runner, command)
        except (OSError, subprocess.TimeoutExpired) as error:
            item.update(status="SUBMISSION_UNCERTAIN", error_class=type(error).__name__)
            atomic_json(ledger_path, ledger)
            raise RuntimeError("sbatch outcome uncertain; inspect the preserved intent instead of submitting twice") from error
        answer = result.stdout.strip().split(";", 1)[0]
        if result.returncode or not re.fullmatch(r"\d+", answer):
            item.update(status="SUBMISSION_FAILED" if result.returncode else "SUBMISSION_UNCERTAIN",
                        returncode=result.returncode, stdout=result.stdout[:1000], stderr=result.stderr[:1000])
            atomic_json(ledger_path, ledger)
            summary = "Single-job submission failed" if result.returncode else "Single-job submission outcome uncertain"
            raise RuntimeError(summary + " (exit=" + str(result.returncode) + "); stderr=" +
                               repr(item["stderr"]) + "; stdout=" + repr(item["stdout"]) +
                               "; scheduler response retained in " + str(ledger_path))
        item.update(job_id=answer, status="SUBMITTED", submitted_at_utc=utc_now())
        atomic_json(ledger_path, ledger)
        return {"status": "SINGLE_JOB_SUBMITTED", "job_id": answer, "partition": cluster["partition"],
                "gpu_request": "gpu:2", "cpus": 32, "memory": memory, "log": output,
                "subjobs_or_array": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=cli.DEFAULT_PROJECT)
    parser.add_argument("--python", default=os.environ.get("PAPER1_PYTHON", cli.DEFAULT_PYTHON))
    parser.add_argument("--raw-dir")
    parser.add_argument("--wheelhouse", type=Path)
    parser.add_argument("--repository", default=cli.REPOSITORY)
    parser.add_argument("--memory", default=os.environ.get("PAPER1_JOB_MEMORY"),
                        help="Total memory for the one enclosing job; saved for subsequent resumes")
    arguments = parser.parse_args(argv)
    try:
        result = submit(arguments.project, arguments.python, arguments.raw_dir,
                        arguments.wheelhouse, arguments.repository, memory=arguments.memory)
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0
    except Exception:
        traceback.print_exc()
        print("Existing downloads, checkpoints and job records were retained.", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
