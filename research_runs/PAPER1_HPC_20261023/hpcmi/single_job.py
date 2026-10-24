"""Run the frozen study inside one Slurm allocation, using two independent GPUs.

This supervisor never imports torch, installs dependencies, or submits another
Slurm job. Download, CPU preparation and fitted workers remain separate child
processes, so a failed report or one failed fit cannot cancel independent fits.
"""
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

from .common import atomic_json, exclusive_lock, read_json, utc_now

ROOT = Path(__file__).resolve().parents[1]


def allocated_slots(environ=None):
    env = os.environ if environ is None else environ
    values = [value.strip() for value in env.get("CUDA_VISIBLE_DEVICES", "").split(",")]
    if len(values) < 2 or any(not value or value in {"-1", "NoDevFiles"} for value in values):
        raise RuntimeError("The two-GPU allocation must provide CUDA_VISIBLE_DEVICES with two assigned devices")
    if len(set(values)) != len(values):
        raise RuntimeError("Slurm supplied duplicate visible GPU assignments")
    return values[:2]


def is_complete(project, task):
    # Reuse actual completion/evaluation identity validation; file existence alone
    # must never turn an interrupted fit or missing evaluation into success.
    from .cli import _completed
    return _completed(Path(project), task)


class StageFailure(RuntimeError):
    def __init__(self, stage, returncode):
        self.stage, self.returncode = stage, returncode
        super().__init__(f"{stage} exited {returncode}; original logs and checkpoints retained")


class SingleJob:
    def __init__(self, project, *, popen=None, environ=None, poll_seconds=.5, heartbeat_seconds=30):
        self.project = Path(project).expanduser().resolve()
        self.paths = read_json(self.project / "config/paths.json")
        self.python = self.paths["training_python"]
        self.prep_python = self.paths.get("preprocessing_python")
        self.env = dict(os.environ if environ is None else environ)
        self.slots = allocated_slots(self.env)
        if not self.env.get("SLURM_JOB_ID"):
            raise RuntimeError("The combined runner must execute inside a Slurm allocation")
        self.popen = popen or subprocess.Popen
        self.poll_seconds, self.heartbeat_seconds = poll_seconds, heartbeat_seconds
        self.children, self.sync_process = {}, None
        self.sync_stream = None
        self.stop_code, self.stage, self.last_heartbeat = None, "starting", 0.
        self.old_handlers = {}
        (self.project / "state").mkdir(parents=True, exist_ok=True)
        (self.project / "logs/workers").mkdir(parents=True, exist_ok=True)

    def emit(self, *, force=False, **extra):
        now = time.monotonic()
        if not force and now - self.last_heartbeat < self.heartbeat_seconds:
            return
        self.last_heartbeat = now
        active = []
        for process, item in list(self.children.items()):
            row = {"stage": item["stage"], "pid": process.pid, "task_id": item.get("task_id")}
            if item.get("task_id"):
                status = self.project / "outputs/runs" / item["task_id"] / "status.json"
                if status.exists():
                    try:
                        saved = read_json(status)
                    except (OSError, ValueError):
                        saved = {}
                    for key in ("global_step", "optimizer_updates", "epoch", "processed_evaluation_samples"):
                        if type(saved.get(key)) is int:
                            row[key] = saved[key]
            active.append(row)
        value = {"updated_at_utc": utc_now(), "stage": self.stage,
                 "slurm_job_id": self.env["SLURM_JOB_ID"], "active_children": active,
                 "max_concurrent_fits": 2, "stop_requested_exit_code": self.stop_code, **extra}
        atomic_json(self.project / "state/single_job_status.json", value)
        atomic_json(self.project / "state/controller_status.json", value)
        print(json.dumps(value, allow_nan=False), flush=True)

    def history(self, event):
        with (self.project / "state/single_job_history.jsonl").open("a") as stream:
            stream.write(json.dumps({"observed_at_utc": utc_now(), **event}, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def request_stop(self, signum, frame=None):
        # Cancellation takes precedence if it follows the advance warning.
        if signum in (signal.SIGTERM, signal.SIGINT):
            self.stop_code = 143 if signum == signal.SIGTERM else 130
        elif self.stop_code is None:
            self.stop_code = 75
        forwarded = signal.SIGUSR1 if self.stop_code == 75 else signal.SIGTERM
        for process in list(self.children):
            if process.poll() is None:
                try:
                    process.send_signal(forwarded)
                except ProcessLookupError:
                    pass

    def install_signals(self):
        for number in (signal.SIGUSR1, signal.SIGTERM, signal.SIGINT):
            self.old_handlers[number] = signal.signal(number, self.request_stop)

    def restore_signals(self):
        for number, handler in self.old_handlers.items():
            signal.signal(number, handler)

    def environment(self, slot=None):
        env = {**self.env, "PYTHONUNBUFFERED": "1", "PYTHONNOUSERSITE": "1",
               "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
               "NUMEXPR_NUM_THREADS": "1", "CUBLAS_WORKSPACE_CONFIG": ":4096:8"}
        if slot is not None:
            # Preserve the assignment supplied by Slurm; never invent an old UUID
            # or a physical GPU index. Each child uses its resulting cuda:0.
            env["CUDA_VISIBLE_DEVICES"] = self.slots[slot]
        return env

    def spawn(self, command, stage, *, slot=None, task_id=None, stream=None):
        if self.stop_code is not None:
            return None
        process = self.popen(command, cwd=ROOT, env=self.environment(slot),
                             stdin=subprocess.DEVNULL, stdout=stream,
                             stderr=subprocess.STDOUT, close_fds=True)
        self.children[process] = {"stage": stage, "task_id": task_id}
        self.history({"event": "child_started", "stage": stage, "task_id": task_id,
                      "pid": process.pid, "gpu_slot": slot})
        # A signal may have arrived inside Popen before registration.
        if self.stop_code is not None:
            self.request_stop(signal.SIGUSR1 if self.stop_code == 75 else signal.SIGTERM)
        return process

    def run_stage(self, stage, command, *, slot=None):
        self.stage = stage
        self.emit(force=True)
        process = self.spawn(command, stage, slot=slot)
        if process is None:
            return self.stop_code
        while process.poll() is None:
            self.emit()
            time.sleep(self.poll_seconds)
        code = process.poll()
        del self.children[process]
        self.history({"event": "child_exited", "stage": stage, "worker_exit_code": code})
        if self.stop_code is not None:
            return self.stop_code
        if code:
            raise StageFailure(stage, code)
        return 0

    def ensure_inputs(self):
        from .acquire import quick_raw_ready
        prepared = self.project / "state/data_prepared.json"
        if prepared.exists():
            receipt = read_json(prepared)
            if receipt.get("status") != "complete" or receipt.get("data_dir") != self.paths["data_dir"]:
                raise ValueError("Prepared-data receipt belongs to different inputs")
            from .data import Registry
            if Registry(self.paths["data_dir"]).fingerprint != receipt.get("fingerprint"):
                raise ValueError("Prepared-data fingerprint changed; existing files retained")
            return 0
        if not quick_raw_ready(self.paths["raw_dir"]):
            code = self.run_stage("raw_download", [self.python, "-u", "-m", "hpcmi.acquire",
                                                   "--raw-dir", self.paths["raw_dir"]])
            if code:
                return code
        if not quick_raw_ready(self.paths["raw_dir"]):
            raise ValueError("Raw acquisition exited without complete verified inputs")
        if not self.prep_python:
            raise ValueError("Prepare the isolated CPU environment once on login1 before submission")
        code = self.run_stage("offline_preprocessing", [self.prep_python, "-u", "-m", "hpcmi.raw_prepare",
                              "--raw-dir", self.paths["raw_dir"], "--cache-dir", self.paths["cache_dir"],
                              "--output", self.paths["data_dir"]])
        if code:
            return code
        from .data import Registry
        registry = Registry(self.paths["data_dir"])
        atomic_json(prepared, {"status": "complete", "updated_at_utc": utc_now(),
                    "data_dir": self.paths["data_dir"], "fingerprint": registry.fingerprint,
                    "source_people": len(registry.source_ids), "external_people": len(registry.external_ids)})
        return 0

    def smoke_slots(self):
        study = read_json(self.project / "config/study.json")
        for slot in range(2):
            destination = self.project / "state/gpu-slots" / ("slot-%d" % slot)
            (destination / "state").mkdir(parents=True, exist_ok=True)
            atomic_json(destination / "config/study.json", study)
            code = self.run_stage("gpu_smoke_slot_%d" % slot,
                                  [self.python, "-u", "-m", "hpcmi.smoke", "--project", str(destination),
                                   "--device", "cuda"], slot=slot)
            if code:
                return code
            receipt = read_json(destination / "state/gpu_smoke.json")
            if receipt.get("status") != "passed" or not receipt.get("gpu_verified") or not receipt.get("forward_backward_save_restore"):
                raise ValueError("Allocated GPU smoke did not provide a successful receipt")
        return 0

    def fit_pool(self, tasks, phase):
        self.stage = phase
        pending, failures = [], []
        for task in tasks:
            try:
                if not is_complete(self.project, task):
                    pending.append(task)
            except Exception as error:
                failures.append({"task_id": task["id"], "completion_error_class": type(error).__name__,
                                 "completion_verified": False})
        active = {}
        self.emit(force=True, pending_fits=len(pending), previously_completed_fits=len(tasks)-len(pending)-len(failures))
        try:
            while pending or active:
                if self.stop_code is None:
                    for slot in range(2):
                        if slot in active or not pending:
                            continue
                        task = pending.pop(0)
                        stream = (self.project / "logs/workers" / (task["id"] + ".log")).open("ab", buffering=0)
                        try:
                            process = self.spawn([self.python, "-u", "-m", "hpcmi.worker", "--project", str(self.project),
                                                  "--task-id", task["id"], "--device", "cuda"],
                                                 phase, slot=slot, task_id=task["id"], stream=stream)
                        except OSError as error:
                            stream.close()
                            failures.append({"task_id": task["id"], "worker_exit_code": None,
                                             "spawn_error_class": type(error).__name__, "completion_verified": False})
                            continue
                        if process is None:
                            stream.close()
                            break
                        active[slot] = (process, task, stream)
                for slot, (process, task, stream) in list(active.items()):
                    code = process.poll()
                    if code is None:
                        continue
                    stream.close()
                    del active[slot]
                    del self.children[process]
                    error_class = None
                    try:
                        completed = code == 0 and is_complete(self.project, task)
                    except Exception as error:
                        completed, error_class = False, type(error).__name__
                    self.history({"event": "fit_exited", "task_id": task["id"], "phase": phase,
                                  "worker_exit_code": code, "verified_complete": completed})
                    if not completed and self.stop_code is None:
                        failures.append({"task_id": task["id"], "worker_exit_code": code,
                                         "completion_verified": False, "completion_error_class": error_class})
                self.emit(pending_fits=len(pending), failed_this_invocation=len(failures))
                if self.stop_code is not None and not active:
                    return self.stop_code
                if pending or active:
                    time.sleep(self.poll_seconds)
        finally:
            for process, task, stream in active.values():
                # Main exception cleanup also waits for these workers to save.
                if process.poll() is not None:
                    stream.close()
        if failures:
            atomic_json(self.project / "state" / (phase + "-unfinished.json"),
                        {"updated_at_utc": utc_now(), "failures": failures,
                         "automatic_same_invocation_retries": False})
        return 1 if failures else 0

    def start_sync(self):
        config = self.project / "config/sync.json"
        if not config.exists():
            raise ValueError("Configure GitHub authorization once on login1 before submitting the combined job")
        self.sync_config = read_json(config)
        project_id = self.sync_config.get("project_id", self.project.name)
        self.sync_arguments = ["--project", str(self.project), "--repository", self.sync_config["repository"],
                               "--branch", "hpc/" + project_id, "--path", "hpc_status/" + project_id + "/status.json",
                               "--token-file", self.sync_config["token_file"], "--interval", "180"]
        try:
            self.sync_stream = (self.project / "logs/github-sync.log").open("ab", buffering=0)
        except OSError:
            self.sync_stream = None  # Fall back to the already-open Slurm log.
        try:
            self.sync_process = self.popen([self.python, "-u", "-m", "hpcmi.github_sync"] + self.sync_arguments,
                                           cwd=ROOT, env=self.environment(), stdin=subprocess.DEVNULL,
                                           stdout=self.sync_stream, stderr=subprocess.STDOUT, close_fds=True)
        except OSError:
            self.history({"event": "github_sync_start_failed", "training_blocked": False})

    def stop_sync(self):
        if self.sync_process is not None and self.sync_process.poll() is None:
            try:
                self.sync_process.terminate()
            except ProcessLookupError:
                pass
            try:
                self.sync_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    self.sync_process.kill()
                except ProcessLookupError:
                    pass
                self.sync_process.wait()
        if getattr(self, "sync_arguments", None):
            try:
                subprocess.run([self.python, "-u", "-m", "hpcmi.github_sync"] + self.sync_arguments + ["--once"],
                               cwd=ROOT, env=self.environment(), stdin=subprocess.DEVNULL,
                               stdout=self.sync_stream, stderr=subprocess.STDOUT, timeout=45, check=False)
            except (OSError, subprocess.TimeoutExpired):
                self.history({"event": "final_github_sync_pending", "training_cancelled": False})
        if self.sync_stream is not None:
            try:
                self.sync_stream.close()
            except OSError:
                pass

    def execute(self):
        from .plan import create_plan, append_final_tasks
        from .analysis import analyze
        code = self.ensure_inputs()
        if code:
            return code
        code = self.smoke_slots()
        if code:
            return code
        create_plan(self.project)
        development = [t for t in read_json(self.project / "tasks.json") if t["phase"] == "development"]
        code = self.fit_pool(development, "development")
        if code:
            return code
        append_final_tasks(self.project)
        final = [t for t in read_json(self.project / "tasks.json") if t["phase"] == "final"]
        code = self.fit_pool(final, "final")
        if code:
            return code
        self.stage = "statistical_analysis"
        self.emit(force=True)
        summary = analyze(self.project)
        if summary.get("status") != "complete":
            raise ValueError("Saved evaluations are not complete; fits retained for resume")
        self.stage = "complete"
        self.emit(force=True, completed_fits=len(development)+len(final), analysis_status="complete")
        return 0

    def run(self):
        self.install_signals()
        result = 1
        try:
            self.start_sync()
            result = self.execute()
        except Exception as error:
            self.history({"event": "failed", "stage": self.stage, "error_class": type(error).__name__,
                          "worker_exit_code": getattr(error, "returncode", None)})
            traceback.print_exc()
            self.emit(force=True, failed=True, error_class=type(error).__name__)
        finally:
            if self.children:
                # An unexpected supervisor exception must not abandon live fits.
                for process in list(self.children):
                    if process.poll() is None:
                        try:
                            process.send_signal(signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                    process.wait()
                self.children.clear()
            if self.stop_code is not None:
                self.stage = "interrupted_resume_available" if self.stop_code == 75 else "cancelled"
                self.emit(force=True)
            self.stop_sync()
            self.restore_signals()
        return self.stop_code if self.stop_code is not None else result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    args = parser.parse_args(argv)
    project = Path(args.project).expanduser().resolve()
    try:
        with exclusive_lock(project / "state/single_job.lock"):
            return SingleJob(project).run()
    except BlockingIOError:
        print("An actual combined runner is already active; no second runner started.", flush=True)
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
