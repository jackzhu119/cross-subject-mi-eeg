"""School-HPC entry point; login process only submits and observes saved files."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback

from .common import atomic_json, read_json, canonical_hash, exclusive_lock, utc_now

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PYTHON = "/public/home/zhuziyuan/.venvs/paper3-hpc-cu121-offline/bin/python"
DEFAULT_PROJECT = "/public/home/zhuziyuan/projects/paper1-risk-v1"
REPOSITORY = "jackzhu119/cross-subject-mi-eeg"


def runtime_metadata(python):
    code = ('import json,platform,sys;from importlib.metadata import version;'
            'print(json.dumps({"python":platform.python_version(),"executable":sys.executable,'
            '"torch":version("torch"),"numpy":version("numpy")}))')
    result = subprocess.run([str(python), "-u", "-c", code], capture_output=True, text=True,
                            check=True, timeout=30)
    value = json.loads(result.stdout)
    if (value["python"], value["torch"], value["numpy"]) != ("3.12.3", "2.5.1+cu121", "2.2.6"):
        raise ValueError("Training interpreter differs from the supplied HPC runtime; use an isolated matching environment, not a global upgrade: " + json.dumps(value))
    return value


def setup(project, python, raw_dir=None, data_dir=None, prep_python=None, repository=REPOSITORY):
    project = Path(project).expanduser().resolve()
    for name in ("config", "state", "logs", "outputs", "data"):
        (project / name).mkdir(parents=True, exist_ok=True)
    with exclusive_lock(project / "state/setup.lock"):
        for name in ("study.json", "cluster.json"):
            dest = project / "config" / name
            if not dest.exists():
                atomic_json(dest, read_json(ROOT / "config" / name))
        paths_file = project / "config/paths.json"
        if paths_file.exists():
            paths = read_json(paths_file)
            for arg, key in ((raw_dir, "raw_dir"), (data_dir, "data_dir"), (python, "training_python")):
                observed = str(Path(arg).expanduser().absolute()) if arg and key == "training_python" else str(Path(arg).expanduser().resolve()) if arg else None
                if arg and observed != paths[key]:
                    raise ValueError("Existing project " + key + " differs; retained paths/checkpoints were not replaced")
            return paths
        paths = {"project": str(project), "code_root": str(ROOT),
                 "raw_dir": str(Path(raw_dir or project / "raw").expanduser().resolve()),
                 "data_dir": str(Path(data_dir or project / "data/prepared").expanduser().resolve()),
                 "cache_dir": str(project / "data/eligible_npz"),
                 "training_python": str(Path(python).expanduser().absolute()),
                 "preprocessing_python": str(Path(prep_python).expanduser().absolute()) if prep_python else None,
                 "repository": repository}
        atomic_json(paths_file, paths)
        atomic_json(project / "config/data_path.json", {"data_dir": paths["data_dir"]})
        return paths


def _completed(project, task):
    path = project / "outputs/runs" / task["id"] / "complete.json"
    if not path.exists():
        return False
    body = read_json(path)
    if body.get("status") != "complete" or body.get("task_id") != task["id"]:
        raise ValueError("Invalid completion identity: " + task["id"])
    for key in ("phase", "method", "seed"):
        if body.get(key) != task[key]:
            raise ValueError("Completion task fields changed: " + task["id"])
    if not body.get("evaluations"):
        raise ValueError("Completion has no saved evaluation: " + task["id"])
    run_dir = path.parent.resolve()
    for variant, relative in body["evaluations"].items():
        summary_path = (run_dir / relative).resolve()
        if not summary_path.is_relative_to(run_dir) or not summary_path.is_file():
            raise ValueError("Saved evaluation missing or outside task: " + task["id"])
    return True


def _emit(project, state):
    value = {"updated_at_utc": utc_now(), **state}
    atomic_json(project / "state/controller_status.json", value)
    print(json.dumps(value), flush=True)
    return value


def stop_legacy_controller(project, proc_root=Path("/proc")):
    """Stop only this user's exact project monitor commands, never a worker."""
    project = Path(project).expanduser().resolve()
    stopped = []
    for entry in Path(proc_root).iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            argv = (entry / "cmdline").read_bytes().decode().rstrip("\0").split("\0")
            module_pos = argv.index("-m") + 1
            module = argv[module_pos]
            if module == "hpcmi.cli":
                if argv[module_pos + 1] != "controller":
                    continue
            elif module != "hpcmi.github_sync":
                continue
            target = argv[argv.index("--project") + 1]
            if Path(target).expanduser().resolve() != project:
                continue
            os.kill(int(entry.name), signal.SIGTERM)
            stopped.append(int(entry.name))
        except (FileNotFoundError, ProcessLookupError, ValueError, IndexError, UnicodeError):
            continue
    # An old progress writer may be finishing its bounded 15-second HTTP call.
    deadline = time.monotonic() + 20
    waiting = set(stopped)
    while waiting and time.monotonic() < deadline:
        for pid in list(waiting):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                waiting.discard(pid)
        if waiting:
            time.sleep(.1)
    if waiting:
        raise RuntimeError("Existing project monitor has not exited; no new controller started")
    return stopped


def controller_tick(project, explicit_resume=False):
    from .slurm import (submit_auxiliary, auxiliary_state, active_task_ids,
                        task_scheduler_states, submit_task_array)
    project = Path(project).expanduser().resolve()
    mode = project / "config/execution_mode.json"
    if mode.exists() and read_json(mode).get("mode") == "single_job":
        return _emit(project, {"stage": "single_job_managed", "legacy_array_submission": False})
    paths = read_json(project / "config/paths.json")
    cluster = read_json(project / "config/cluster.json")
    # Small receipts are re-read; raw EEG and full library scans are not.
    prepared = project / "state/data_prepared.json"
    if not prepared.exists():
        state = auxiliary_state(project, "prep", cluster)
        if state["state"] == "NOT_SUBMITTED" or explicit_resume:
            job = submit_auxiliary(project, "prep", paths["preprocessing_python"],
                                   cluster_config=cluster, explicit_resume=explicit_resume, code_root=ROOT)
            return _emit(project, {"stage": "data_preprocessing", "job_id": job})
        return _emit(project, {"stage": "data_preprocessing", "scheduler": state["state"],
                               "manual_resume_required": state["state"] in {"UNKNOWN", "FAILED", "CANCELLED", "COMPLETED", "TIMEOUT", "OUT_OF_MEMORY"}})
    evidence = read_json(prepared)
    if evidence.get("status") != "complete" or evidence.get("data_dir") != paths["data_dir"]:
        raise ValueError("Invalid prepared-data receipt")
    smoke_path = project / "state/gpu_smoke.json"
    if smoke_path.exists():
        smoke = read_json(smoke_path)
        if smoke.get("status") != "passed" or not smoke.get("gpu_verified") or not smoke.get("forward_backward_save_restore"):
            raise ValueError("GPU smoke receipt is not a successful allocated GPU test")
        identity = smoke.get("identity", {})
        metadata = read_json(project / "state/training_metadata.json")
        study = read_json(project / "config/study.json")
        if (identity.get("device_type") != "cuda"
                or smoke.get("fingerprint") != canonical_hash(identity)
                or any(identity.get(key) != metadata.get(key) for key in ("python", "torch", "numpy"))
                or any(identity.get(key) != study.get(key) for key in ("architecture", "input_shape"))):
            raise ValueError("GPU smoke receipt belongs to a different runtime or model; inspect the retained receipt before requesting a new smoke")
    else:
        state = auxiliary_state(project, "smoke", cluster)
        if state["state"] == "NOT_SUBMITTED" or explicit_resume:
            job = submit_auxiliary(project, "smoke", paths["training_python"],
                                   cluster_config=cluster, explicit_resume=explicit_resume, code_root=ROOT)
            return _emit(project, {"stage": "once_per_runtime_gpu_smoke", "job_id": job})
        return _emit(project, {"stage": "once_per_runtime_gpu_smoke", "scheduler": state["state"],
                               "manual_resume_required": state["state"] in {"UNKNOWN", "FAILED", "CANCELLED", "COMPLETED", "TIMEOUT", "OUT_OF_MEMORY"}})
    from .plan import create_plan, append_final_tasks
    from .analysis import analyze
    create_plan(project)
    tasks = read_json(project / "tasks.json")
    dev = [t for t in tasks if t["phase"] == "development"]
    if all(_completed(project, t) for t in dev):
        append_final_tasks(project)
        tasks = read_json(project / "tasks.json")
    pending = [t["id"] for t in tasks if not _completed(project, t)]
    if not pending:
        summary = analyze(project)
        return _emit(project, {"stage": "complete" if summary["status"] == "complete" else "analysis_pending",
                               "completed_fits": len(tasks), "analysis_status": summary["status"],
                               "manual_resume_required": summary["status"] != "complete"})
    active = active_task_ids(project, cluster)
    if active:
        return _emit(project, {"stage": "training_or_evaluation", "active_scheduler_tasks": len(active),
                               "completed_fits": len(tasks) - len(pending), "pending": len(pending)})
    previous = task_scheduler_states(project, cluster)
    # Background may submit a fresh phase, never retry a failed/cancelled task.
    candidates = pending if explicit_resume else [t for t in pending if t not in previous]
    if candidates:
        job = submit_task_array(project, candidates, paths["training_python"], cluster, ROOT)
        return _emit(project, {"stage": "array_submitted", "job_id": job, "submitted": len(candidates),
                               "max_parallel": cluster["max_parallel"]})
    return _emit(project, {"stage": "manual_resume_required", "unfinished": pending,
                           "scheduler_states": {t: previous.get(t, "UNKNOWN") for t in pending}})


def _daemon(project, module, arguments, log_name):
    log_path = project / "logs" / log_name
    with log_path.open("ab", buffering=0) as stream:
        process = subprocess.Popen([sys.executable, "-u", "-m", module] + arguments,
                                   cwd=ROOT, stdin=subprocess.DEVNULL, stdout=stream, stderr=stream,
                                   start_new_session=True, close_fds=True)
    return process.pid


def launch(args):
    from .github_sync import confirm_credentials
    project = Path(args.project).expanduser().resolve()
    paths = setup(project, args.python, args.raw_dir, args.data_dir, args.prep_python, args.repository)
    metadata = runtime_metadata(paths["training_python"])
    atomic_json(project / "state/training_metadata.json", metadata)
    # Prompt before any initial training submission; token stays outside project.
    token_file = confirm_credentials(paths["repository"], project.name)
    atomic_json(project / "config/sync.json", {"repository": paths["repository"],
                                               "token_file": str(token_file), "project_id": project.name})
    if not (project / "state/data_prepared.json").exists():
        # Acquisition emits this only after every pinned input is verified.
        from .acquire import quick_raw_ready
        if not quick_raw_ready(paths["raw_dir"]):
            raise RuntimeError("Raw data not ready. Run the separate FETCH_DATA.sh --raw-dir " + paths["raw_dir"] + " on an approved data-transfer machine; the same command resumes interrupted downloads.")
        if not paths.get("preprocessing_python"):
            from .prep_runtime import prepare
            prep = prepare(project, paths["training_python"], wheelhouse=args.wheelhouse or ROOT / "wheelhouse")
            paths["preprocessing_python"] = str(prep)
            atomic_json(project / "config/paths.json", paths)
    # A short tick lock prevents a user's resume and the background scheduler racing.
    with exclusive_lock(project / "state/controller_tick.lock", blocking=True):
        result = controller_tick(project, explicit_resume=True)
    _daemon(project, "hpcmi.github_sync", ["--project", str(project), "--repository", paths["repository"],
            "--branch", "hpc/" + project.name, "--path", "hpc_status/" + project.name + "/status.json",
            "--token-file", str(token_file), "--interval", "180"], "github-sync.log")
    if result["stage"] != "complete":
        _daemon(project, "hpcmi.cli", ["controller", "--project", str(project)], "controller.log")
    print("Progress: " + str(project / "state/controller_status.json"), flush=True)
    print("Logs: " + str(project / "logs/slurm"), flush=True)
    print("Resume with this same LAUNCH.sh command; completed tasks and saved checkpoints are reused.", flush=True)
    return 0


def controller(project):
    project = Path(project).resolve()
    running = True
    def stop(signum, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        with exclusive_lock(project / "state/controller_daemon.lock"):
            while running:
                try:
                    with exclusive_lock(project / "state/controller_tick.lock", blocking=True):
                        result = controller_tick(project, explicit_resume=False)
                    if result["stage"] in {"complete", "manual_resume_required", "single_job_managed"} or result.get("manual_resume_required"):
                        return 0
                except Exception:
                    traceback.print_exc()
                    # Scheduler/network reporting trouble does not terminate workers.
                    _emit(project, {"stage": "controller_observation_error", "workers_cancelled": False})
                deadline = time.monotonic() + 180
                while running and time.monotonic() < deadline:
                    time.sleep(min(1, max(0, deadline - time.monotonic())))
    except BlockingIOError:
        print("Controller already running; existing process retained.", flush=True)
    return 0


def prepare_data(project):
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Raw EEG preprocessing belongs in an allocated CPU job")
    project = Path(project).resolve()
    paths = read_json(project / "config/paths.json")
    from .acquire import quick_raw_ready
    if not quick_raw_ready(paths["raw_dir"]):
        raise RuntimeError("Acquisition incomplete; run separate FETCH_DATA.sh before preprocessing")
    command = [sys.executable, "-u", "-m", "hpcmi.raw_prepare", "--raw-dir", paths["raw_dir"],
               "--cache-dir", paths["cache_dir"], "--output", paths["data_dir"]]
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode:
        return result.returncode
    from .data import Registry
    registry = Registry(paths["data_dir"])
    atomic_json(project / "state/data_prepared.json", {"status": "complete", "updated_at_utc": utc_now(),
                "data_dir": paths["data_dir"], "fingerprint": registry.fingerprint,
                "source_people": len(registry.source_ids), "external_people": len(registry.external_ids)})
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    l = sub.add_parser("launch")
    l.add_argument("--project", default=DEFAULT_PROJECT)
    l.add_argument("--python", default=os.environ.get("PAPER1_PYTHON", DEFAULT_PYTHON))
    l.add_argument("--raw-dir")
    l.add_argument("--data-dir")
    l.add_argument("--prep-python")
    l.add_argument("--wheelhouse", type=Path)
    l.add_argument("--repository", default=REPOSITORY)
    for name in ("controller", "prepare", "status"):
        command = sub.add_parser(name)
        command.add_argument("--project", default=DEFAULT_PROJECT)
    args = p.parse_args(argv)
    try:
        if args.command == "launch":
            return launch(args)
        if args.command == "controller":
            return controller(args.project)
        if args.command == "prepare":
            return prepare_data(args.project)
        from .github_sync import collect_progress
        print(json.dumps(collect_progress(args.project), indent=2))
        return 0
    except Exception:
        traceback.print_exc()
        print("Existing data, checkpoints and failure logs were retained. Correct the reported issue and run the same command.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
