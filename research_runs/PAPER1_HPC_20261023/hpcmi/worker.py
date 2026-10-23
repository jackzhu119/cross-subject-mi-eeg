"""Resumable, one-GPU task worker. No downloads and no scheduler operations.

USR1 checkpoints then exits 75. TERM/INT checkpoint then exit 143/130 and never
request a requeue; that decision belongs to the Slurm wrapper. Only registered
source people may enter fitting or epoch selection. Target labels are read only
inside held-out evaluation after the applicable source task has finished.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import random
import re
import signal
import sys
import time
import traceback

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import numpy as np
import torch
from .checkpoint import atomic_json, atomic_npz, canonical_hash, exclusive_lock, load_checkpoint, save_checkpoint, utc_now
from .models import build_model, three_view_logits
from .objectives import Objective


class RequestedStop(Exception):
    def __init__(self, code, reason):
        self.code, self.reason = code, reason


class SignalState:
    def __init__(self):
        self.code = None
        self.reason = None
        self.old = {}

    def handler(self, number, frame):
        # Cancellation dominates an earlier USR1 so scancel cannot revive a job.
        if number in (signal.SIGTERM, signal.SIGINT):
            self.code = 128 + number
            self.reason = signal.Signals(number).name
        elif self.code is None:
            self.code, self.reason = 75, "SIGUSR1_checkpoint"

    def install(self):
        for number in (signal.SIGUSR1, signal.SIGTERM, signal.SIGINT):
            self.old[number] = signal.signal(number, self.handler)

    def restore(self):
        for number, old in self.old.items():
            signal.signal(number, old)

    def check(self):
        if self.code is not None:
            raise RequestedStop(self.code, self.reason)


def cpu_state(model):
    return {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}


def model_hash(model):
    digest = hashlib.sha256()
    for name, value in model.state_dict().items():
        array = value.detach().cpu().contiguous().numpy()
        digest.update(name.encode())
        digest.update(str((str(array.dtype), array.shape)).encode())
        digest.update(array.tobytes())
    return digest.hexdigest()


def configure(config, device):
    torch.set_num_threads(int(config.get("torch_threads", 4)))
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass  # Already initialized in a same-process synthetic test.
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    if device.startswith("cuda"):
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA unavailable in assigned worker runtime")
        if not os.environ.get("SLURM_JOB_ID") and not config.get("allow_local_gpu_test", False):
            raise RuntimeError("Production GPU work requires a Slurm allocation")
    if config.get("amp", False) and not device.startswith("cuda"):
        raise ValueError("AMP requires CUDA for this protocol")


def seed_all(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def capture_rng():
    return {"python": random.getstate(), "numpy": np.random.get_state(), "torch": torch.get_rng_state(),
            "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None}


def restore_rng(value):
    random.setstate(value["python"])
    np.random.set_state(value["numpy"])
    torch.set_rng_state(value["torch"].cpu())
    if value["cuda"] is not None and torch.cuda.is_available():
        states = value["cuda"]
        if len(states) == torch.cuda.device_count():
            torch.cuda.set_rng_state_all([state.cpu() for state in states])
        else:
            # Single-GPU tasks use the visible logical device, not old UUIDs.
            torch.cuda.set_rng_state(states[0].cpu(), device=0)


class BalancedSampler:
    """Uniform cohort, person, class and trial with a serialized RNG/cursor.

A batch samples eight people (four per cohort in the two-cohort protocol), with
both classes and eight trials per class. Small synthetic test cohorts may sample
people with replacement; duplicate person×class groups are aggregated in loss.
"""
    def __init__(self, registry, ids, config, seed):
        registry.ensure_source(ids)
        self.registry, self.ids = registry, sorted(ids)
        self.config = config
        self.rng = np.random.default_rng(seed)
        self.batches = 0
        self.group_index = {(person, c): 2*i+c for i, person in enumerate(self.ids) for c in (0, 1)}
        self.people = {d: [i for i in self.ids if registry.by_id[i]["dataset"] == d]
                       for d in sorted({registry.by_id[i]["dataset"] for i in self.ids})}
        people_count = int(config.get("subjects_per_batch", 8))
        if people_count <= 0 or people_count % len(self.people):
            raise ValueError("subjects_per_batch must be positive and divide evenly across source cohorts")
        count = people_count // len(self.people)
        self.inclusion_probabilities = [0.] * len(self.group_index)
        self.group_prior = [0.] * len(self.group_index)
        for dataset, people in self.people.items():
            n = len(people)
            pi = count / n if n >= count else 1 - (1 - 1/n) ** count
            for person in people:
                for c in (0, 1):
                    self.inclusion_probabilities[self.group_index[person, c]] = pi
                    self.group_prior[self.group_index[person, c]] = 1. / (len(self.people) * 2 * n)
        if int(config.get("trials_per_class", 8)) <= 0:
            raise ValueError("trials_per_class must be positive")
        expected_batch = people_count * 2 * int(config.get("trials_per_class", 8))
        if "batch_size" in config and int(config["batch_size"]) != expected_batch:
            raise ValueError("batch_size differs from balanced sampling design")
        self.indices = {}
        for person in self.ids:
            entry = registry.load_person(person)
            for c in (0, 1):
                choices = np.flatnonzero(entry["y"] == c)
                if len(choices) == 0:
                    raise ValueError("Source person missing a class: " + person)
                self.indices[person, c] = choices

    def state_dict(self):
        return {"rng": copy.deepcopy(self.rng.bit_generator.state), "batches": self.batches}

    def load_state_dict(self, state):
        self.rng.bit_generator.state = state["rng"]
        self.batches = int(state["batches"])

    def batch(self):
        people_count = int(self.config.get("subjects_per_batch", 8))
        trials = int(self.config.get("trials_per_class", 8))
        datasets = list(self.people)
        if people_count % len(datasets):
            raise ValueError("subjects_per_batch must divide evenly across source cohorts")
        people = []
        for dataset in datasets:
            pool = self.people[dataset]
            count = people_count // len(datasets)
            people.extend(self.rng.choice(pool, size=count, replace=len(pool) < count).tolist())
        X, y, groups = [], [], []
        for person in people:
            entry = self.registry.load_person(person)
            for c in (0, 1):
                indices = self.rng.choice(self.indices[person, c], size=trials, replace=True)
                X.append(np.asarray(entry["X"][indices], dtype=np.float32))
                y.extend([c] * trials)
                groups.extend([self.group_index[person, c]] * trials)
        self.batches += 1
        return torch.from_numpy(np.concatenate(X)), torch.tensor(y, dtype=torch.long), torch.tensor(groups, dtype=torch.long)


class Progress:
    def __init__(self, run_dir, task, config):
        self.run_dir, self.task = run_dir, task
        self.interval = float(config.get("heartbeat_seconds", 30))
        self.last = 0.0
        self.global_step, self.epoch, self.processed = 0, 0, 0

    def emit(self, stage, force=False, **extra):
        now = time.monotonic()
        if not force and now - self.last < self.interval:
            return
        self.last = now
        row = {"task_id": self.task["id"], "stage": stage, "pid": os.getpid(), "host": os.uname().nodename,
               "updated_at_utc": utc_now(), "global_step": self.global_step, "optimizer_updates": self.global_step,
               "epoch": self.epoch, "processed_evaluation_samples": self.processed, **extra}
        atomic_json(self.run_dir / "status.json", row)
        print(json.dumps(row, ensure_ascii=False, allow_nan=False), flush=True)


def metric_row(y, logits):
    if len(y) == 0 or logits.shape != (len(y), 2) or not np.isfinite(logits).all():
        raise ValueError("Invalid held-out prediction shard")
    pred = logits.argmax(axis=1)
    counts = {"n": len(y), "n_left": int((y == 0).sum()), "n_right": int((y == 1).sum()),
              "correct_left": int(((y == 0) & (pred == 0)).sum()), "correct_right": int(((y == 1) & (pred == 1)).sum())}
    z = logits.astype(np.float64)
    counts["sum_ce"] = float(np.logaddexp(0, z[np.arange(len(y)), 1-y] - z[np.arange(len(y)), y]).sum())
    return counts


def evaluate(model, registry, ids, run_dir, variant, seed, device, config, signals, progress):
    """Session shards are atomic and reused only with the identical model hash."""
    model.eval()
    digest = model_hash(model)
    folder = run_dir / "evaluations" / variant / digest[:20]
    folder.mkdir(parents=True, exist_ok=True)
    people = []
    for person in ids:
        signals.check()
        entry = registry.load_person(person)
        y = np.asarray(entry["y"], dtype=np.int64)
        sessions = np.asarray([str(s) for s in entry["sessions"]])
        trial_ids = np.asarray([str(t) for t in entry["trial_ids"]])
        totals = {"n": 0, "n_left": 0, "n_right": 0, "correct_left": 0, "correct_right": 0, "sum_ce": 0.0}
        for session in sorted(set(sessions.tolist())):
            signals.check()
            indices = np.flatnonzero(sessions == session)
            key = canonical_hash({"person": person, "session": session})[:24]
            shard = folder / (key + ".npz")
            identity = {"model_sha256": digest, "person_id": person, "session": session, "variant": variant, "seed": seed}
            if shard.exists():
                with np.load(shard, allow_pickle=False) as z:
                    if json.loads(str(z["identity"].item())) != identity or not np.array_equal(z["trial_ids"], trial_ids[indices]) or not np.array_equal(z["y"], y[indices]):
                        raise ValueError("Evaluation shard identity changed: " + str(shard))
                    logits = z["logits"]
                progress.processed += len(indices)
            else:
                pieces = []
                batch_size = int(config.get("eval_batch_size", 128))
                for start in range(0, len(indices), batch_size):
                    signals.check()
                    batch = indices[start:start+batch_size]
                    x = torch.from_numpy(np.array(entry["X"][batch, 0], dtype=np.float32, copy=True)).to(device)
                    with torch.inference_mode():
                        pieces.append(model(x).float().cpu().numpy())
                    progress.processed += len(batch)
                    progress.emit("evaluating", evaluation_variant=variant, person_id=person, session=session)
                logits = np.concatenate(pieces)
                if not np.isfinite(logits).all():
                    raise FloatingPointError("Non-finite held-out logits")
                atomic_npz(shard, logits=logits, y=y[indices], trial_ids=trial_ids[indices], identity=np.asarray(json.dumps(identity, sort_keys=True)))
            counts = metric_row(y[indices], logits)
            for k in totals:
                totals[k] += counts[k]
        if totals["n_left"] == 0 or totals["n_right"] == 0:
            raise ValueError("Held-out person lacks a class: " + person)
        left, right = totals["correct_left"] / totals["n_left"], totals["correct_right"] / totals["n_right"]
        people.append({"person_id": person, "dataset": entry["dataset"], "seed": seed, "variant": variant,
            **totals, "recall_left": left, "recall_right": right, "ba": (left+right)/2,
            "min_recall": min(left, right), "ce": totals["sum_ce"] / totals["n"]})
    if model_hash(model) != digest:
        raise RuntimeError("Held-out evaluation changed weights or BatchNorm buffers")
    summary = {"variant": variant, "model_sha256": digest, "people": people, "completed_at_utc": utc_now()}
    atomic_json(folder / "summary.json", summary)
    return summary, str((folder / "summary.json").relative_to(run_dir))


def source_score(summary):
    people = summary["people"]
    datasets = sorted({p["dataset"] for p in people})
    if not datasets:
        raise ValueError("Source validation is empty")
    return float(np.mean([np.mean([p["min_recall"] for p in people if p["dataset"] == d]) for d in datasets]))


def science_fingerprint(config, task, registry):
    # Operational recovery patches, elapsed wall time, hardware UUIDs and logs do
    # not invalidate an otherwise identical model/optimizer/data task.
    defaults = {"science_version": "paper1_hpc_subject_class_v1", "input_shape": [3,18,320],
        "epochs": 40, "updates_per_epoch": 128, "subjects_per_batch": 8, "trials_per_class": 8,
        "learning_rate": 0.001, "weight_decay": 0.0, "amp": False, "architecture": {}, "objective": {}}
    scientific = {key: config.get(key, value) for key, value in defaults.items()}
    task_fields = {key: task.get(key) for key in ("id", "phase", "method", "seed", "fold", "train_ids", "validation_ids", "test_ids", "selected_epoch")}
    return canonical_hash({"science": scientific, "task": task_fields, "data": registry.fingerprint})


def run_task(project, task_id, device="cuda", stop_after_steps=None):
    project = Path(project).resolve()
    config = json.loads((project / "config/study.json").read_text())
    tasks = json.loads((project / "tasks.json").read_text())
    if isinstance(tasks, dict):
        tasks = tasks["tasks"]
    matches = [task for task in tasks if task["id"] == task_id]
    if len(matches) != 1 or not re.fullmatch(r"[A-Za-z0-9_.-]+", task_id):
        raise ValueError("Unknown or unsafe task ID")
    task = matches[0]
    if device == "cuda":
        device = "cuda:0"
    run_dir = project / "outputs/runs" / task_id
    run_dir.mkdir(parents=True, exist_ok=True)
    progress = Progress(run_dir, task, config)
    with exclusive_lock(run_dir / "worker.lock"):
        signals = SignalState()
        signals.install()
        state = None
        try:
            from .data import Registry
            locator = project / "config/data_path.json"
            data_dir = Path(json.loads(locator.read_text())["data_dir"]) if locator.exists() else project / "data"
            registry = Registry(data_dir)
            fingerprint = science_fingerprint(config, task, registry)
            completed = run_dir / "complete.json"
            if completed.exists():
                done = json.loads(completed.read_text())
                if done["fingerprint"] != fingerprint:
                    raise ValueError("Completed task has a different scientific contract")
                if not done.get("evaluations") or any(not (run_dir / path).is_file() for path in done["evaluations"].values()):
                    raise ValueError("Completed task evaluation summary is missing; retain checkpoint and inspect")
                progress.global_step = done["global_step"]
                progress.emit("already_complete", force=True)
                return 0
            train_ids, validation_ids, test_ids = (task.get(k, []) for k in ("train_ids", "validation_ids", "test_ids"))
            registry.ensure_source(train_ids)
            registry.ensure_source(validation_ids)
            if not train_ids or (set(train_ids)&set(validation_ids)) or (set(train_ids)&set(test_ids)) or (set(validation_ids)&set(test_ids)):
                raise ValueError("Train/validation/test identities overlap or training is empty")
            if task["phase"] == "development":
                registry.ensure_source(test_ids)
                if not validation_ids or not test_ids:
                    raise ValueError("Development requires separate inner validation and outer test people")
            elif task["phase"] == "final":
                if validation_ids or not test_ids or not all(registry.by_id[x]["role"] == "external" for x in test_ids):
                    raise ValueError("Final evaluation requires external test people and no target validation")
                if not 1 <= int(task["selected_epoch"]) <= int(config.get("epochs", 40)):
                    raise ValueError("Missing source-selected final epoch")
            else:
                raise ValueError("Unknown task phase")
            configure(config, device)
            seed_all(int(task["seed"]))
            model = build_model(config, device)
            optimizer = torch.optim.Adam(model.parameters(), lr=float(config.get("learning_rate", .001)), weight_decay=float(config.get("weight_decay", 0)))
            amp = bool(config.get("amp", False))
            scaler = torch.amp.GradScaler("cuda", enabled=amp)
            sampler = BalancedSampler(registry, train_ids, config, int(task["seed"]) + 101)
            objective = Objective(task["method"], len(sampler.group_index), config, device, sampler.inclusion_probabilities, sampler.group_prior)
            runtime = {"torch": torch.__version__, "numpy": np.__version__, "python": sys.version.split()[0],
                "device": device, "cuda_build": torch.version.cuda,
                "device_name": torch.cuda.get_device_name(0) if device.startswith("cuda") else "cpu"}
            state = load_checkpoint(run_dir / "checkpoints", fingerprint)
            if state is None:
                # Never silently initialize zero after evidence of earlier work.
                markers = [run_dir / "status.json", run_dir / "checkpoints/checkpoint_status.json"]
                for marker in markers:
                    if marker.exists():
                        observed_step = int(json.loads(marker.read_text()).get("global_step", 0))
                        if observed_step > 0:
                            progress.global_step = observed_step
                            raise RuntimeError("Prior optimizer updates recorded but both checkpoint generations are missing")
                state = {"fingerprint": fingerprint, "epoch": 0, "step_in_epoch": 0, "global_step": 0,
                    "best_model": None, "best_epoch": None, "best_score": None, "selected_model": None,
                    "validation_history": [], "training_history": [], "epoch_loss_sum": 0., "runtime_history": [runtime]}
            else:
                model.load_state_dict(state["model"])
                optimizer.load_state_dict(state["optimizer"])
                if state["scaler"] is not None:
                    scaler.load_state_dict(state["scaler"])
                sampler.load_state_dict(state["sampler"])
                objective.load_state_dict(state["objective"])
                restore_rng(state["rng"])
                if state.get("runtime_history", [])[-1:] != [runtime]:
                    state.setdefault("runtime_history", []).append(runtime)
                    print(json.dumps({"runtime_changed_on_resume": runtime, "bitwise_cross_runtime_equivalence_claimed": False}), flush=True)
            progress.global_step, progress.epoch = state["global_step"], state["epoch"]
            def checkpoint():
                state.update(model=cpu_state(model), optimizer=optimizer.state_dict(), scheduler=None,
                    scaler=scaler.state_dict() if amp else None, sampler=sampler.state_dict(),
                    objective=objective.state_dict(), rng=capture_rng(), saved_at_utc=utc_now())
                save_checkpoint(run_dir / "checkpoints", state)
            checkpoint()  # A valid initial/resumed state exists before the next update.
            progress.emit("training", force=True, resume_from_step=state["global_step"], runtime=runtime)
            epochs, updates = int(config.get("epochs", 40)), int(config.get("updates_per_epoch", 128))
            checkpoint_time = time.monotonic()
            try:
                while state["epoch"] < epochs:
                    model.train()
                    while state["step_in_epoch"] < updates:
                        signals.check()
                        x, y, group = sampler.batch()
                        x, y, group = x.to(device), y.to(device), group.to(device)
                        optimizer.zero_grad(set_to_none=True)
                        with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=amp):
                            z = three_view_logits(model, x)
                            loss, details = objective(z, y, group)
                        scaler.scale(loss).backward()
                        scaler.unscale_(optimizer)
                        if not all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None):
                            raise FloatingPointError("Non-finite model gradients; retained last valid checkpoint")
                        scaler.step(optimizer)
                        scaler.update()
                        state["global_step"] += 1
                        state["step_in_epoch"] += 1
                        state["epoch_loss_sum"] += details["loss"]
                        progress.global_step = state["global_step"]
                        progress.emit("training", step_in_epoch=state["step_in_epoch"], loss=details["loss"], training_samples=state["global_step"]*len(y))
                        if time.monotonic()-checkpoint_time >= float(config.get("checkpoint_seconds", 180)):
                            checkpoint()
                            checkpoint_time = time.monotonic()
                        if stop_after_steps is not None and state["global_step"] >= stop_after_steps:
                            raise RequestedStop(75, "synthetic_test_stop_after_steps")
                    epoch = state["epoch"] + 1
                    if task["phase"] == "development":
                        summary, _ = evaluate(model, registry, validation_ids, run_dir, "inner_epoch_%03d" % epoch,
                                               task["seed"], device, config, signals, progress)
                        score = source_score(summary)
                        state["validation_history"].append({"epoch": epoch, "source_equal_cohort_mean_min_recall": score})
                        if state["best_score"] is None or score > state["best_score"]:
                            state["best_score"], state["best_epoch"], state["best_model"] = score, epoch, cpu_state(model)
                    elif epoch == int(task["selected_epoch"]):
                        state["selected_model"] = cpu_state(model)
                        state["best_model"], state["best_epoch"] = cpu_state(model), epoch
                    state["training_history"].append({"epoch": epoch, "mean_loss": state["epoch_loss_sum"] / updates})
                    state["epoch"], state["step_in_epoch"], state["epoch_loss_sum"] = epoch, 0, 0.
                    progress.epoch = epoch
                    checkpoint()
                    checkpoint_time = time.monotonic()
                    progress.emit("epoch_completed", force=True, best_epoch=state["best_epoch"])
                # Preserve final train state; evaluated weights live in a separate model.
                trained_state = cpu_state(model)
                variants = {"outer_best": state["best_model"]} if task["phase"] == "development" else {
                    "fixed40": trained_state, "source_selected": state["selected_model"]}
                outputs = {}
                for variant, weights in variants.items():
                    if weights is None:
                        raise RuntimeError("Required selected model is missing")
                    eval_model = build_model(config, device)
                    eval_model.load_state_dict(weights)
                    _, outputs[variant] = evaluate(eval_model, registry, test_ids, run_dir, variant, task["seed"],
                                                     device, config, signals, progress)
                    del eval_model
                complete = {"status": "complete", "complete": True, "id": task_id, "task_id": task_id, "phase": task["phase"],
                    "method": task["method"], "seed": task["seed"], "fold": task.get("fold"),
                    "best_epoch": state["best_epoch"], "selected_epoch": task.get("selected_epoch"),
                    "global_step": state["global_step"], "optimizer_updates": state["global_step"],
                    "epochs_completed": state["epoch"], "fingerprint": fingerprint, "evaluations": outputs,
                    "validation_history": state["validation_history"], "runtime_history": state["runtime_history"],
                    "completed_at_utc": utc_now()}
                atomic_json(completed, complete)
                progress.emit("complete", force=True, evaluations=outputs)
                return 0
            except RequestedStop as stop:
                checkpoint()
                progress.emit("checkpointed_for_resume" if stop.code == 75 else "cancelled_checkpointed", force=True,
                              requested_exit_code=stop.code, reason=stop.reason, automatic_requeue_requested=False)
                return stop.code
        except Exception:
            failure = {"status": "failed", "task_id": task_id, "failed_at_utc": utc_now(), "traceback": traceback.format_exc(),
                       "last_completed_optimizer_updates": state.get("global_step", 0) if state is not None else (progress.global_step or None),
                       "new_task_initialization_not_inferred_from_missing_checkpoint": True}
            atomic_json(run_dir / "error.json", failure)
            stamp = utc_now().replace(":", "").replace("+", "_")
            atomic_json(run_dir / ("error-"+stamp+".json"), failure)
            print(failure["traceback"], file=sys.stderr, flush=True)
            progress.emit("failed", force=True, error_path="error.json", exit_code=1)
            return 1
        finally:
            signals.restore()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    parser.add_argument("--stop-after-steps", type=int, help="Synthetic recovery test only; exits75 after saving")
    args = parser.parse_args()
    try:
        code = run_task(args.project, args.task_id, args.device, args.stop_after_steps)
    except BlockingIOError:
        print(json.dumps({"status": "already_running", "task_id": args.task_id, "new_worker_started": False}), flush=True)
        code = 0
    except Exception:
        traceback.print_exc()
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
