"""One allocation: two independent neural workers and one CPU reference worker.

The supervisor never imports Torch. Every task owns its state; a failed task is
retained and does not cancel other independent source/final fits.
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

from hpcmi.common import atomic_json, canonical_hash, exclusive_lock, read_json, utc_now

ROOT = Path(__file__).resolve().parents[1]


def allocated_slots(environ=None):
    env = os.environ if environ is None else environ
    slots = [v.strip() for v in env.get("CUDA_VISIBLE_DEVICES", "").split(",")]
    if len(slots) != 2 or len(set(slots)) != 2 or any(v in {"", "-1", "NoDevFiles"} for v in slots):
        raise RuntimeError("This study requests exactly two Slurm-assigned visible GPUs")
    return slots


def is_complete(project, task):
    run = Path(project) / "outputs/runs" / task["id"]
    path = run / "complete.json"
    if not path.exists():
        return False
    value = read_json(path)
    if value.get("status") != "complete" or not value.get("complete"):
        raise ValueError("Non-complete completion record: " + task["id"])
    for key in ("task_id", "family", "cell_id", "phase", "method", "seed", "fold", "train_trials_sha256"):
        expected = task["id"] if key == "task_id" else task[key]
        if value.get(key) != expected:
            raise ValueError("Completion identity mismatch: " + task["id"] + ":" + key)
    if task["family"] == "neural":
        steps = task["epochs"] * task["updates_per_epoch"]
        if value.get("global_step") != steps or value.get("optimizer_updates") != steps or value.get("epochs_completed") != task["epochs"]:
            raise ValueError("Neural endpoint is incomplete: " + task["id"])
    elif value.get("classical_fits_completed") != 1 or value.get("optimizer_updates") != 0:
        raise ValueError("Classical endpoint is incomplete: " + task["id"])
    variant = "outer_fixed40" if task["phase"] == "development" else "fixed40"
    evaluations = value.get("evaluations", {})
    if set(evaluations) != {variant}:
        raise ValueError("Unexpected fixed-endpoint evaluation: " + task["id"])
    relative = Path(evaluations[variant])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Evaluation path escapes its run")
    summary_path = run / relative
    if not summary_path.is_file():
        raise ValueError("Completed task evaluation is missing: " + task["id"])
    summary = read_json(summary_path)
    people = summary.get("people", [])
    ids = [p.get("person_id") for p in people]
    if (summary.get("variant") != variant or summary.get("model_sha256") != value.get("model_sha256")
            or len(ids) != len(set(ids)) or set(ids) != set(task["test_ids"])
            or any(p.get("seed") != task["seed"] or p.get("variant") != variant for p in people)):
        raise ValueError("Completion evaluation identity mismatch: " + task["id"])
    return True


class Runner:
    def __init__(self, project, *, popen=None, environ=None, poll_seconds=.5):
        self.project = Path(project).resolve()
        self.paths = read_json(self.project / "config/paths.json")
        self.env = dict(os.environ if environ is None else environ)
        if not self.env.get("SLURM_JOB_ID"):
            raise RuntimeError("Training supervisor must run inside the allocated Slurm job")
        self.slots = allocated_slots(self.env)
        self.python = self.paths["training_python"]
        self.popen = popen or subprocess.Popen
        self.poll_seconds = poll_seconds
        self.stop_code = None
        self.children = {}
        self.handlers = {}
        self.last_emit = 0.
        self.failures = []
        self.stage = "starting"
        self.completed_count = 0
        (self.project / "state").mkdir(parents=True, exist_ok=True)
        (self.project / "logs/workers").mkdir(parents=True, exist_ok=True)

    def child_environment(self, slot=None):
        env = {**self.env, "PYTHONUNBUFFERED": "1", "PYTHONNOUSERSITE": "1",
               "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
               "NUMEXPR_NUM_THREADS": "1", "CUBLAS_WORKSPACE_CONFIG": ":4096:8"}
        # Slurm owns both identifiers; each child sees only its assigned device.
        env["CUDA_VISIBLE_DEVICES"] = self.slots[slot] if slot is not None else ""
        return env

    def request_stop(self, signum, frame=None):
        if signum in (signal.SIGTERM, signal.SIGINT):
            self.stop_code = 143 if signum == signal.SIGTERM else 130
        elif self.stop_code is None:
            self.stop_code = 75
        for process in list(self.children):
            if process.poll() is None:
                try:
                    process.send_signal(signal.SIGUSR1 if self.stop_code == 75 else signal.SIGTERM)
                except ProcessLookupError:
                    pass

    def emit(self, force=False, **extra):
        now = time.monotonic()
        if not force and now - self.last_emit < 30:
            return
        self.last_emit = now
        active = []
        for process, row in self.children.items():
            item = {"task_id": row.get("task_id"), "family": row.get("family"), "pid": process.pid}
            if row.get("task_id"):
                path = self.project / "outputs/runs" / row["task_id"] / "status.json"
                if path.exists():
                    try:
                        status = read_json(path)
                        for key in ("global_step", "optimizer_updates", "epoch", "processed_evaluation_samples", "stage"):
                            if key in status:
                                item[key] = status[key]
                    except (OSError, ValueError):
                        pass  # Reporting failure does not interrupt a fitted worker.
            active.append(item)
        state = {"updated_at_utc": utc_now(), "stage": self.stage,
                 "slurm_job_id": self.env["SLURM_JOB_ID"], "completed_tasks": self.completed_count,
                 "total_tasks": 630, "active_children": active, "failed_this_invocation": len(self.failures),
                 "max_concurrent_neural_fits": 2, "max_concurrent_classical_fits": 1,
                 "stop_requested_exit_code": self.stop_code, **extra}
        atomic_json(self.project / "state/controller_status.json", state)
        print(json.dumps(state, allow_nan=False), flush=True)

    def history(self, value):
        with (self.project / "state/execution_history.jsonl").open("a") as stream:
            stream.write(json.dumps({"observed_at_utc": utc_now(), **value}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def spawn(self, command, *, task=None, slot=None, stream=None):
        if self.stop_code is not None:
            return None
        process = self.popen(command, cwd=ROOT, env=self.child_environment(slot), stdin=subprocess.DEVNULL,
                             stdout=stream, stderr=subprocess.STDOUT, close_fds=True)
        self.children[process] = {"task_id": task["id"] if task else None,
                                  "family": task["family"] if task else "smoke", "stream": stream}
        self.history({"event": "child_started", "task_id": task["id"] if task else None,
                      "pid": process.pid, "gpu_slot": slot})
        if self.stop_code is not None:
            self.request_stop(signal.SIGUSR1 if self.stop_code == 75 else signal.SIGTERM)
        return process

    def smoke(self):
        for slot in range(2):
            if self.stop_code is not None:
                return self.stop_code
            destination = self.project / "state/gpu-slots" / ("slot-%d" % slot)
            (destination / "state").mkdir(parents=True, exist_ok=True)
            atomic_json(destination / "config/study.json", read_json(self.project / "config/study.json"))
            self.stage = "cached_gpu_smoke_slot_%d" % slot
            process = self.spawn([self.python, "-u", "-m", "hpcmi.smoke", "--project", str(destination),
                                  "--device", "cuda"], slot=slot)
            if process is None:
                return self.stop_code
            while process.poll() is None:
                self.emit()
                time.sleep(self.poll_seconds)
            code = process.poll()
            del self.children[process]
            if self.stop_code is not None:
                return self.stop_code
            if code:
                raise RuntimeError("Allocated GPU smoke exited %d; no scientific fits started" % code)
            receipt = read_json(destination / "state/gpu_smoke.json")
            if receipt.get("status") != "passed" or not receipt.get("gpu_verified") or not receipt.get("forward_backward_save_restore"):
                raise ValueError("Allocated GPU smoke receipt is incomplete")
        return 0

    def pool(self, tasks):
        pending = {"neural": [], "classical": []}
        for task in tasks:
            try:
                if is_complete(self.project, task):
                    self.completed_count += 1
                else:
                    pending[task["family"]].append(task)
            except Exception as error:
                self.failures.append({"task_id": task["id"], "error_class": type(error).__name__,
                                      "stage": "completion_identity"})
                self.history({"event": "retained_invalid_completion", **self.failures[-1]})
        active = {}
        self.stage = "fitting_and_evaluation"
        while any(pending.values()) or active:
            if self.stop_code is None:
                for lane, family, slot in (("gpu0", "neural", 0), ("gpu1", "neural", 1), ("cpu", "classical", None)):
                    if lane in active or not pending[family]:
                        continue
                    task = pending[family].pop(0)
                    log = self.project / "logs/workers" / (task["id"] + ".log")
                    stream = log.open("ab", buffering=0)
                    module = "compmi.worker" if family == "neural" else "compmi.classical"
                    command = [self.python, "-u", "-m", module, "--project", str(self.project), "--task-id", task["id"]]
                    if family == "neural":
                        command += ["--device", "cuda"]
                    try:
                        process = self.spawn(command, task=task, slot=slot, stream=stream)
                    except OSError as error:
                        stream.close()
                        self.failures.append({"task_id": task["id"], "stage": "spawn", "error_class": type(error).__name__})
                        continue
                    if process is None:
                        stream.close()
                        break
                    active[lane] = (process, task, stream)
            for lane, (process, task, stream) in list(active.items()):
                code = process.poll()
                if code is None:
                    continue
                stream.close()
                del active[lane]
                del self.children[process]
                self.history({"event": "child_exited", "task_id": task["id"], "returncode": code})
                if self.stop_code is not None:
                    continue
                try:
                    if code or not is_complete(self.project, task):
                        raise RuntimeError("Worker did not produce a verified completion")
                    self.completed_count += 1
                except Exception as error:
                    self.failures.append({"task_id": task["id"], "returncode": code,
                                          "stage": "worker_or_completion", "error_class": type(error).__name__})
                    self.history({"event": "task_failed_retained", **self.failures[-1]})
            self.emit(pending_neural=len(pending["neural"]), pending_classical=len(pending["classical"]))
            if self.stop_code is not None and not active:
                return self.stop_code
            time.sleep(self.poll_seconds)
        return 0

    def run(self):
        with exclusive_lock(self.project / "state/runner.lock"):
            for number in (signal.SIGUSR1, signal.SIGTERM, signal.SIGINT):
                self.handlers[number] = signal.signal(number, self.request_stop)
            try:
                plan = read_json(self.project / "state/plan.json")
                tasks = read_json(self.project / "tasks.json")
                if len(tasks) != 630 or canonical_hash(tasks) != plan["tasks_sha256"]:
                    raise ValueError("Frozen task list changed")
                # Registry validates its small manifest/stat receipts, not full EEG hashes.
                from hpcmi.data import Registry
                if Registry(self.paths["data_dir"]).fingerprint != plan["data_fingerprint"]:
                    raise ValueError("Prepared-data identity changed")
                # Do not reserve GPUs for a completed experiment just to redo smoke.
                try:
                    all_done = all(is_complete(self.project, task) for task in tasks)
                except (ValueError, OSError, KeyError):
                    # The pool records malformed completed tasks without
                    # blocking the remaining independent tasks.
                    all_done = False
                if not all_done:
                    code = self.smoke()
                    if code:
                        return code
                    code = self.pool(tasks)
                    if code:
                        return code
                else:
                    self.completed_count = len(tasks)
                atomic_json(self.project / "state/failed_tasks_latest.json", {"failures": self.failures, "updated_at_utc": utc_now()})
                self.stage = "analysis"
                analysis_log = (self.project / "logs/analysis.log").open("ab", buffering=0)
                try:
                    process = self.spawn([self.python, "-u", "-m", "compmi.analysis", "--project", str(self.project)], stream=analysis_log)
                    if process is None:
                        return self.stop_code
                    while process.poll() is None:
                        self.emit()
                        time.sleep(self.poll_seconds)
                    code = process.poll()
                    del self.children[process]
                finally:
                    analysis_log.close()
                if self.stop_code is not None:
                    return self.stop_code
                self.stage = "complete" if not self.failures and code == 0 else "incomplete_resume_pending"
                self.emit(force=True, analysis_returncode=code)
                return 0 if not self.failures and code == 0 else 1
            except Exception:
                self.stage = "supervisor_failed"
                traceback.print_exc()
                # A supervisor/reporting error must not leave untracked workers
                # fitting after the batch shell has reported failure.
                self.request_stop(signal.SIGTERM)
                deadline = time.monotonic() + 150
                while any(p.poll() is None for p in self.children) and time.monotonic() < deadline:
                    time.sleep(self.poll_seconds)
                try:
                    self.emit(force=True)
                except OSError:
                    traceback.print_exc()
                return 1
            finally:
                for number, handler in self.handlers.items():
                    signal.signal(number, handler)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    args = parser.parse_args(argv)
    return Runner(args.project).run()


if __name__ == "__main__":
    raise SystemExit(main())
