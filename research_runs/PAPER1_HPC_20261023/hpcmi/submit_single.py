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
                               "-o", "%i|%j|%u|%T|%P|%Z|%r"])
    if result.returncode:
        raise RuntimeError("squeue failed; no new job submitted: " + result.stderr.strip()[:1000])
    rows = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        values = [v.strip() for v in line.split("|")]
        if len(values) not in {6, 7}:
            raise RuntimeError("Unparseable scheduler row; no new job submitted")
        rows.append(dict(zip(("id", "name", "owner", "state", "partition", "directory", "reason"), values)))
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


def _configure_resources(project, memory, gpus):
    path = project / "config/cluster.json"
    old = read_json(path)
    new = {**old, "account": OWNER, "squeue_user": OWNER, "partition": "hpc_gpu",
           "gres": "gpu:1", "cpus_per_task": 13, "mem": "128G", "max_parallel": gpus,
           "exclude": [], "single_job_memory": memory, "single_job_gpus": gpus}
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


def _known_single_names(ledger, name, project):
    names = {name}
    for item in ledger["submissions"]:
        if item.get("project", str(project)) == str(project) and isinstance(item.get("job_name"), str):
            names.add(item["job_name"])
    return names


def _replacement_row(rows, job_id, project, names):
    observed = [row for row in rows if row["id"] == job_id]
    if len(observed) > 1:
        raise RuntimeError("Multiple scheduler rows for a replacement identity; no cancellation or release")
    if not observed:
        return None
    row = observed[0]
    _identity(row, project)
    if row["name"] not in names:
        raise RuntimeError("Replacement ID is not a known job of this project; no cancellation or release")
    return row


def _finish_replacement(project, runner, ledger_path, ledger, item, known_names):
    """A held replacement cannot fit until the verified old job has left queue."""
    new_id, old_id = item["job_id"], item["replaces_job_id"]
    rows = _queue(runner)
    new = _replacement_row(rows, new_id, project, {item["job_name"]})
    if new is None:
        raise RuntimeError("Recorded held replacement was not observed; no duplicate submitted")
    if item.get("status") in {"SUBMITTED", "SUBMITTED_RECOVERED"}:
        return {"status": "EXISTING_SINGLE_JOB_REUSED", "job_id": new_id, "scheduler_state": new["state"]}
    old = _replacement_row(rows, old_id, project, known_names)
    release_was_requested = item.get("release_requested_at_utc") is not None
    if release_was_requested and old is None and (new["state"] == "RUNNING" or
            (new["state"] == "PENDING" and new.get("reason") not in {None, "JobHeldUser", "JobHeldAdmin"})):
        item.update(status="SUBMITTED_RECOVERED", release_recovered_at_utc=utc_now())
        atomic_json(ledger_path, ledger)
        return {"status": "EXISTING_SINGLE_JOB_REUSED", "job_id": new_id, "scheduler_state": new["state"]}
    if new["state"] != "PENDING":
        raise RuntimeError("Replacement was expected to remain held/PENDING; old job retained")
    item.update(status="HELD_REPLACEMENT_VERIFIED", verified_at_utc=utc_now(), new_scheduler=new)
    atomic_json(ledger_path, ledger)
    old = _replacement_row(rows, old_id, project, known_names)
    if old is not None:
        if old["state"] != "PENDING":
            item.update(status="HELD_REPLACEMENT_WAITING_OLD", old_scheduler=old)
            atomic_json(ledger_path, ledger)
            return {"status": "REPLACEMENT_HELD_OLD_JOB_ACTIVE", "job_id": new_id,
                    "old_job_id": old_id, "old_scheduler_state": old["state"], "released": False}
        item.update(old_pending_cancel_requested_at_utc=utc_now(), old_scheduler=old)
        atomic_json(ledger_path, ledger)
        cancelled = _command(runner, ["scancel", "--state=PENDING", old_id])
        item["old_cancel_returncode"] = cancelled.returncode
        item["old_cancel_stderr"] = cancelled.stderr[:1000]
        atomic_json(ledger_path, ledger)
        after = _queue(runner)
        old = _replacement_row(after, old_id, project, known_names)
        if old is not None or cancelled.returncode:
            item.update(status="HELD_REPLACEMENT_WAITING_OLD", old_scheduler=old)
            atomic_json(ledger_path, ledger)
            return {"status": "REPLACEMENT_HELD_OLD_JOB_RETAINED", "job_id": new_id,
                    "old_job_id": old_id, "old_scheduler_state": old["state"] if old else "NOT_OBSERVED",
                    "released": False}
        # Recheck the held successor immediately before releasing it.
        new = _replacement_row(after, new_id, project, {item["job_name"]})
        if new is None or new["state"] != "PENDING":
            raise RuntimeError("Held replacement identity changed; no release requested")
    item.update(status="REPLACEMENT_RELEASE_REQUESTED", old_left_queue_observed_at_utc=utc_now(),
                release_requested_at_utc=utc_now())
    atomic_json(ledger_path, ledger)
    released = _command(runner, ["scontrol", "release", new_id])
    item["release_returncode"] = released.returncode
    item["release_stderr"] = released.stderr[:1000]
    if released.returncode:
        item["status"] = "HELD_REPLACEMENT_RELEASE_FAILED"
        atomic_json(ledger_path, ledger)
        raise RuntimeError("Replacement release was not verified; scontrol release failed: " + released.stderr.strip()[:1000])
    item.update(status="SUBMITTED", released_at_utc=utc_now())
    atomic_json(ledger_path, ledger)
    return {"status": "SINGLE_JOB_SUBMITTED", "job_id": new_id, "replaced_job_id": old_id,
            "old_removed_from_queue": True, "release_request_accepted": True,
            "gpu_execution_verified": False, **item["shape"]}


def submit(project, python=cli.DEFAULT_PYTHON, raw_dir=None, wheelhouse=None,
           repository=cli.REPOSITORY, runner=None, memory=None, gpus=2,
           reauthorize=False, require_github=False, offline_inputs=False, login_sync=False,
           replace_job=None):
    """Prepare private login configuration and submit one allocation.

    Replacement is staged held, verified in the real queue, and only released
    after the exact pending predecessor is gone. A running predecessor is never
    cancelled. All fitted state, inputs and original submission records remain.
    """
    if os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Run this submission command on login1, outside a compute allocation")
    if type(gpus) is not int or gpus not in {2, 3}:
        raise ValueError("The combined job supports exactly two or three GPU workers")
    if replace_job is not None and not re.fullmatch(r"[0-9]+", str(replace_job)):
        raise ValueError("Replacement requires one numeric Slurm job ID")
    replace_job = str(replace_job) if replace_job is not None else None
    runner = runner or subprocess.run
    project = Path(project).expanduser().resolve()
    if memory is None:
        cluster_path = project / "config/cluster.json"
        saved_memory = read_json(cluster_path).get("single_job_memory") if cluster_path.exists() else None
        memory = _job_memory(saved_memory, explicit=True) if saved_memory is not None else "128G"
    else:
        memory = _job_memory(memory, explicit=True)
    paths = cli.setup(project, python, raw_dir=raw_dir, repository=repository)
    metadata = cli.runtime_metadata(paths["training_python"])
    atomic_json(project / "state/training_metadata.json", metadata)
    from .github_sync import confirm_credentials
    from .prep_runtime import prepare
    token = confirm_credentials(paths["repository"], project.name, force=reauthorize,
                                require_verified=require_github or reauthorize)
    atomic_json(project / "config/sync.json", {"repository": paths["repository"],
                "project_id": project.name, "token_file": str(token)})
    prep = prepare(project, paths["training_python"], wheelhouse=wheelhouse or ROOT / "wheelhouse")
    paths["preprocessing_python"] = str(prep)
    paths["single_job_gpus"] = gpus
    if offline_inputs:
        paths["network_mode"] = "offline"
    if login_sync:
        paths["sync_mode"] = "login"
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
        ledger = _ledger(ledger_path)
        known_names = _known_single_names(ledger, name, project)
        old = _replacement_row(rows, replace_job, project, known_names) if replace_job else None
        matching_replacements = [item for item in ledger["submissions"]
                                 if replace_job and item.get("replaces_job_id") == replace_job
                                 and item.get("status") != "SUBMISSION_FAILED"]
        if matching_replacements:
            item = matching_replacements[-1]
            if item.get("status") in {"SUBMITTED", "SUBMITTED_RECOVERED"} and not any(
                    row["id"] == item.get("job_id") for row in rows):
                matching_replacements = []
        if matching_replacements:
            item = matching_replacements[-1]
            if item.get("job_id") is None:
                recovered = [row for row in rows if row["name"] == item["job_name"]]
                if len(recovered) != 1:
                    raise RuntimeError("Previous replacement outcome is uncertain; no duplicate submitted")
                _identity(recovered[0], project)
                if not recovered[0]["id"].isdigit():
                    raise RuntimeError("Replacement scheduler identity is not numeric")
                item.update(job_id=recovered[0]["id"], status="HELD_REPLACEMENT_SUBMITTED")
                atomic_json(ledger_path, ledger)
            return _finish_replacement(project, runner, ledger_path, ledger, item, known_names)
        own = [row for row in rows if row["name"] in known_names]
        if replace_job and old is not None:
            own = [row for row in own if row["id"] != replace_job]
        if len(own) > 1:
            raise RuntimeError("Multiple matching single jobs observed; no new job submitted")
        if own:
            observed = own[0]
            _identity(observed, project)
            if not observed["id"].isdigit():
                raise RuntimeError("Single-job scheduler identity is not numeric")
            if ledger["submissions"]:
                last = ledger["submissions"][-1]
                if (last.get("job_id") is None and last.get("job_name") == observed["name"]
                        and last["status"] in {"SUBMITTING", "SUBMISSION_UNCERTAIN"}):
                    last.update(job_id=observed["id"], status="SUBMITTED_RECOVERED", recovered_at_utc=utc_now())
                    atomic_json(ledger_path, ledger)
            return {"status": "EXISTING_SINGLE_JOB_REUSED", "job_id": observed["id"],
                    "scheduler_state": observed["state"]}
        if any(item.get("job_id") is None and item["status"] in {"SUBMITTING", "SUBMISSION_UNCERTAIN"}
               for item in ledger["submissions"]):
            raise RuntimeError("Previous sbatch outcome is uncertain; retained intent prevents another submission")
        legacy = _legacy_training(project, rows)
        if legacy:
            return {"status": "LEGACY_TRAINING_ACTIVE_NO_NEW_JOB", "jobs": legacy}
        stopped = cli.stop_legacy_controller(project, include_sync=not login_sync)
        mode = {"mode": "single_job", "updated_at_utc": utc_now(), "stopped_legacy_controller_pids": stopped}
        for field in ("network_mode", "sync_mode"):
            if field in paths:
                mode[field] = paths[field]
        atomic_json(project / "config/execution_mode.json", mode)
        cluster = _configure_resources(project, memory, gpus)
        blocked = _migrate_download(project, rows, "p1-download-" + key, runner)
        if blocked:
            return blocked
        held = old is not None
        job_name = name + "-r" + replace_job if held else name
        item = {"submission_id": uuid.uuid4().hex[:12], "created_at_utc": utc_now(),
                "job_name": job_name, "job_id": None, "status": "SUBMITTING", "project": str(project),
                "shape": {"gpus": gpus, "cpus": 13 * gpus, "memory": memory, "max_worker_processes": gpus}}
        if replace_job:
            item.update(replaces_job_id=replace_job, old_job_observed=held, hold_requested=held)
        ledger["submissions"].append(item)
        atomic_json(ledger_path, ledger)
        output = str(log_dir / "single-%j.out")
        command = ["sbatch", "--parsable", "--nodes=1", "--ntasks=1", "--account=" + OWNER,
                   "--partition=" + cluster["partition"], "--gres=gpu:" + str(gpus),
                   "--cpus-per-task=" + str(13 * gpus), "--mem=" + memory,
                   "--export=ALL,PAPER1_WORKERS=" + str(gpus),
                   "--time=" + str(cluster.get("time_limit", "1-00:00:00")),
                   "--signal=B:USR1@180", "--requeue", "--open-mode=append", "--job-name=" + job_name,
                   "--chdir=" + str(project), "--output=" + output, "--error=" + output]
        if held:
            command.append("--hold")
        command += [str(script), str(project), paths["training_python"], str(ROOT)]
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
        item.update(job_id=answer, status="HELD_REPLACEMENT_SUBMITTED" if held else "SUBMITTED", submitted_at_utc=utc_now())
        atomic_json(ledger_path, ledger)
        if held:
            return _finish_replacement(project, runner, ledger_path, ledger, item, known_names)
        response = {"status": "SINGLE_JOB_SUBMITTED", "job_id": answer, "partition": cluster["partition"],
                    "gpu_request": "gpu:" + str(gpus), "cpus": 13 * gpus, "memory": memory,
                    "log": output, "subjobs_or_array": False}
        if replace_job:
            response.update(replaced_job_id=replace_job, old_job_observed=False,
                            old_job_status="NOT_OBSERVED_IN_QUEUE")
        return response


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=cli.DEFAULT_PROJECT)
    parser.add_argument("--python", default=os.environ.get("PAPER1_PYTHON", cli.DEFAULT_PYTHON))
    parser.add_argument("--raw-dir")
    parser.add_argument("--wheelhouse", type=Path)
    parser.add_argument("--repository", default=cli.REPOSITORY)
    parser.add_argument("--memory", default=os.environ.get("PAPER1_JOB_MEMORY"),
                        help="Total memory for the one enclosing job; saved for subsequent resumes")
    parser.add_argument("--gpus", type=int, choices=(2, 3), default=2)
    parser.add_argument("--reauthorize", action="store_true", help="Always prompt for a token and verify actual GitHub write/readback")
    parser.add_argument("--require-github", action="store_true", help="Require fresh live write/readback before submission")
    parser.add_argument("--offline-inputs", action="store_true", help="Compute allocation never downloads inputs")
    parser.add_argument("--login-sync", action="store_true", help="Keep GitHub synchronization outside the compute allocation")
    parser.add_argument("--replace-job", help="Stage and verify a held replacement before cancelling the exact pending predecessor")
    arguments = parser.parse_args(argv)
    try:
        result = submit(arguments.project, arguments.python, arguments.raw_dir,
                        arguments.wheelhouse, arguments.repository, memory=arguments.memory,
                        gpus=arguments.gpus, reauthorize=arguments.reauthorize,
                        require_github=arguments.require_github, offline_inputs=arguments.offline_inputs,
                        login_sync=arguments.login_sync, replace_job=arguments.replace_job)
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0
    except Exception:
        traceback.print_exc()
        print("Existing downloads, checkpoints and job records were retained.", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
