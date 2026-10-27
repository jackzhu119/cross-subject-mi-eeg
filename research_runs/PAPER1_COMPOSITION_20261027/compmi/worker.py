"""Fixed-endpoint composition experiment, reusing the frozen runtime helpers.

Each task owns its checkpoint and held-out session shards. Training uses only
its planned source-trial whitelist. Held-out people enter once, after the fixed
training endpoint; there is no inner validation or epoch selection in this study.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
import traceback

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import numpy as np
import torch

from hpcmi.checkpoint import atomic_json, canonical_hash, exclusive_lock, load_checkpoint, save_checkpoint, utc_now
from hpcmi.data import Registry
from hpcmi.models import build_model, three_view_logits
from hpcmi.objectives import Objective
from hpcmi.worker import (BalancedSampler as SharedBalancedSampler, Progress,
                          RequestedStop, SignalState, capture_rng, configure,
                          cpu_state, evaluate, model_hash, restore_rng, seed_all)


class TrialsetSampler(SharedBalancedSampler):
    """Keep shared cohort/person/class sampling, restricting its trial support."""

    def __init__(self, registry, ids, config, seed, indices_by_person):
        super().__init__(registry, ids, config, seed)
        if set(indices_by_person) != set(self.ids):
            raise ValueError("Training trial whitelist does not match source people")
        per_cohort = int(config.get("subjects_per_batch", 4)) // len(self.people)
        if any(len(people) < per_cohort for people in self.people.values()):
            raise ValueError("Insufficient source people for distinct balanced participant groups")
        checked = {}
        for person in self.ids:
            raw = indices_by_person[person]
            values = list(raw)
            if not values or any(isinstance(x, (bool, np.bool_)) or not isinstance(x, (int, np.integer)) for x in values):
                raise ValueError("Training trial whitelist must contain integer indices")
            indices = np.asarray(values, dtype=np.int64)
            entry = registry.load_person(person)
            if len(set(indices.tolist())) != len(indices) or np.any(indices < 0) or np.any(indices >= len(entry["y"])):
                raise ValueError("Training trial whitelist contains duplicate or out-of-range indices")
            checked[person] = indices.tolist()
            for label in (0, 1):
                choices = indices[np.asarray(entry["y"])[indices] == label]
                if len(choices) == 0:
                    raise ValueError("Training whitelist omits a participant class: " + person)
                self.indices[person, label] = choices
        self.trialset_fingerprint = canonical_hash(checked)

    def state_dict(self):
        return {**super().state_dict(), "trialset_fingerprint": self.trialset_fingerprint}

    def load_state_dict(self, state):
        if state.get("trialset_fingerprint") != self.trialset_fingerprint:
            raise ValueError("Checkpoint sampler uses a different training trial whitelist")
        super().load_state_dict(state)


def science_fingerprint(config, task, registry):
    defaults = {"science_version": "paper1-composition-objective-v2-20261027",
                "input_shape": [3, 18, 320], "epochs": 40, "updates_per_epoch": 128,
                "subjects_per_batch": 4, "trials_per_class": 16, "batch_size": 128,
                "learning_rate": .001, "weight_decay": 0, "amp": False,
                "architecture": {}, "objective": {},
                "evaluation": "fixed40_only_no_inner_selection"}
    science = {key: config.get(key, value) for key, value in defaults.items()}
    fields = ("id", "family", "cell_id", "pool", "subset", "regime", "phase", "method",
              "seed", "fold", "train_ids", "validation_ids", "test_ids", "train_trials_sha256")
    return canonical_hash({"worker_protocol": "composition_fixed_endpoint_v1", "science": science,
                           "task": {key: task.get(key) for key in fields}, "data": registry.fingerprint})


def _read_task(project, task_id):
    rows = json.loads((project / "tasks.json").read_text())
    if isinstance(rows, dict):
        rows = rows["tasks"]
    found = [row for row in rows if row["id"] == task_id]
    if len(found) != 1 or not re.fullmatch(r"[A-Za-z0-9_.-]+", task_id):
        raise ValueError("Unknown or unsafe task ID")
    task = found[0]
    if task.get("family") != "neural" or task.get("method") not in ("erm", "tail"):
        raise ValueError("This worker accepts only the frozen neural ERM/TAIL tasks")
    return task


def run_task(project, task_id, device="cuda", stop_after_steps=None):
    project = Path(project).resolve()
    config = json.loads((project / "config/study.json").read_text())
    task = _read_task(project, task_id)
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
            paths = json.loads((project / "config/paths.json").read_text())
            registry = Registry(Path(paths["data_dir"]))
            # This checks only this small source-only trialset and saved registry
            # identity/stat receipts; it does not rescan prepared EEG array hashes.
            from .plan import task_trialset
            indices_by_person = task_trialset(project, task, registry)
            fingerprint = science_fingerprint(config, task, registry)
            completed = run_dir / "complete.json"
            if completed.exists():
                done = json.loads(completed.read_text())
                if done["fingerprint"] != fingerprint:
                    raise ValueError("Completed task has a different scientific contract")
                if not done.get("evaluations") or any(not (run_dir / name).is_file() for name in done["evaluations"].values()):
                    raise ValueError("Completed task evaluation summary is missing; retain checkpoint and inspect")
                progress.global_step = done["global_step"]
                progress.epoch = done["epochs_completed"]
                progress.emit("already_complete", force=True)
                return 0
            train_ids = task["train_ids"]
            test_ids = task["test_ids"]
            registry.ensure_source(train_ids)
            if task.get("validation_ids") or not test_ids or len(test_ids) != len(set(test_ids)) or set(train_ids) & set(test_ids):
                raise ValueError("Fixed-endpoint train/test split is invalid or has inner validation")
            if task["phase"] == "development":
                registry.ensure_source(test_ids)
                variant = "outer_fixed40"
            elif task["phase"] == "final":
                if not all(registry.by_id[x]["role"] == "external" for x in test_ids):
                    raise ValueError("Final evaluation requires external people")
                variant = "fixed40"
            else:
                raise ValueError("Unknown task phase")
            epochs, updates = int(config.get("epochs", 40)), int(config.get("updates_per_epoch", 128))
            if epochs <= 0 or updates <= 0:
                raise ValueError("Fixed training budget must be positive")
            configure(config, device)
            seed_all(int(task["seed"]))
            model = build_model(config, device)
            optimizer = torch.optim.Adam(model.parameters(), lr=float(config.get("learning_rate", .001)),
                                         weight_decay=float(config.get("weight_decay", 0)))
            amp = bool(config.get("amp", False))
            scaler = torch.amp.GradScaler("cuda", enabled=amp)
            sampler = TrialsetSampler(registry, train_ids, config, int(task["seed"]) + 101, indices_by_person)
            objective = Objective(task["method"], len(sampler.group_index), config, device,
                                  sampler.inclusion_probabilities, sampler.group_prior)
            runtime = {"torch": torch.__version__, "numpy": np.__version__, "python": sys.version.split()[0],
                       "device": device, "cuda_build": torch.version.cuda,
                       "device_name": torch.cuda.get_device_name(0) if device.startswith("cuda") else "cpu"}
            state = load_checkpoint(run_dir / "checkpoints", fingerprint)
            if state is None:
                for marker in (run_dir / "status.json", run_dir / "checkpoints/checkpoint_status.json"):
                    if marker.exists():
                        step = int(json.loads(marker.read_text()).get("global_step", 0))
                        if step > 0:
                            progress.global_step = step
                            raise RuntimeError("Prior optimizer updates recorded but both checkpoint generations are missing")
                state = {"fingerprint": fingerprint, "epoch": 0, "step_in_epoch": 0, "global_step": 0,
                         "best_model": None, "best_epoch": None, "validation_history": [],
                         "training_history": [], "epoch_loss_sum": 0., "runtime_history": [runtime]}
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

            checkpoint()
            progress.emit("training", force=True, resume_from_step=state["global_step"], runtime=runtime)
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
                            logits = three_view_logits(model, x)
                            loss, details = objective(logits, y, group)
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
                        progress.emit("training", step_in_epoch=state["step_in_epoch"], loss=details["loss"],
                                      training_samples=state["global_step"] * len(y))
                        if time.monotonic() - checkpoint_time >= float(config.get("checkpoint_seconds", 180)):
                            checkpoint()
                            checkpoint_time = time.monotonic()
                        if stop_after_steps is not None and state["global_step"] >= stop_after_steps:
                            raise RequestedStop(75, "synthetic_test_stop_after_steps")
                    epoch = state["epoch"] + 1
                    state["training_history"].append({"epoch": epoch, "mean_loss": state["epoch_loss_sum"] / updates})
                    state["epoch"], state["step_in_epoch"], state["epoch_loss_sum"] = epoch, 0, 0.
                    progress.epoch = epoch
                    checkpoint()
                    checkpoint_time = time.monotonic()
                    progress.emit("epoch_completed", force=True, selection_rule="fixed_endpoint")
                # Evaluation shards resume independently; a failed evaluation
                # resumes from this endpoint without repeating any optimizer step.
                digest = model_hash(model)
                _, evaluation = evaluate(model, registry, test_ids, run_dir, variant, task["seed"],
                                          device, config, signals, progress)
                complete = {"status": "complete", "complete": True, "id": task_id, "task_id": task_id,
                            **{key: task.get(key) for key in ("family", "cell_id", "pool", "subset", "regime", "phase", "method", "seed", "fold")},
                            "train_trials_sha256": task["train_trials_sha256"], "model_sha256": digest,
                            "global_step": state["global_step"], "optimizer_updates": state["global_step"],
                            "epochs_completed": state["epoch"], "fingerprint": fingerprint,
                            "evaluations": {variant: evaluation}, "validation_history": [],
                            "epoch_selection": False, "runtime_history": state["runtime_history"],
                            "completed_at_utc": utc_now()}
                atomic_json(completed, complete)
                progress.emit("complete", force=True, evaluations=complete["evaluations"])
                return 0
            except RequestedStop as stop:
                checkpoint()
                progress.emit("checkpointed_for_resume" if stop.code == 75 else "cancelled_checkpointed", force=True,
                              requested_exit_code=stop.code, reason=stop.reason, automatic_requeue_requested=False)
                return stop.code
        except Exception:
            failure = {"status": "failed", "task_id": task_id, "failed_at_utc": utc_now(),
                       "traceback": traceback.format_exc(),
                       "last_completed_optimizer_updates": state.get("global_step", 0) if state is not None else (progress.global_step or None)}
            atomic_json(run_dir / "error.json", failure)
            stamp = utc_now().replace(":", "").replace("+", "_")
            atomic_json(run_dir / ("error-" + stamp + ".json"), failure)
            print(failure["traceback"], file=sys.stderr, flush=True)
            progress.emit("failed", force=True, error_path="error.json", exit_code=1)
            return 1
        finally:
            signals.restore()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--device", default="cuda", choices=("cuda", "cpu"))
    parser.add_argument("--stop-after-steps", type=int, help="Synthetic recovery test only")
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
