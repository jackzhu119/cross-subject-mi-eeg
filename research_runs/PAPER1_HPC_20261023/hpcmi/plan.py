"""Freeze source-person partitions once; append final fits after source completion.

Only registry metadata and local completion summaries are read here. No EEG,
model import, target outcome, Slurm submission, or network access is involved.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics

import numpy as np

from .common import atomic_json, canonical_hash, read_json, utc_now
from .data import Registry

METHODS = ("erm", "groupdro", "tail", "consistency", "tail_consistency")
OPERATIONAL_FIELDS = {
    "torch_threads", "checkpoint_seconds", "heartbeat_seconds", "eval_batch_size",
    "num_workers", "log_seconds",
}


class PlanNotReady(RuntimeError):
    """Previous phase is not complete; existing fits remain reusable."""


def _registry(project: Path) -> Registry:
    selector = project / "config" / "data_path.json"
    raw = read_json(selector)["data_dir"] if selector.exists() else "data"
    directory = Path(raw).expanduser()
    if not directory.is_absolute():
        directory = project / directory
    return Registry(directory)


def _configuration(study):
    return {k: v for k, v in study.items() if k not in OPERATIONAL_FIELDS}


def _positive_unique_ints(values, name):
    out = list(values)
    if not out or any(type(v) is not int or v < 0 for v in out) or len(set(out)) != len(out):
        raise ValueError(f"{name} must contain distinct nonnegative integers")
    return out


def _partitions(entries, folds, split_seed):
    """Dataset-stratified outer folds and fixed inner people shared by methods/seeds."""
    groups = {}
    for row in entries:
        groups.setdefault(row["dataset"], []).append(row["id"])
    if len(entries) != len({row["id"] for row in entries}):
        raise ValueError("Duplicate registered source person")
    rng = np.random.default_rng(split_seed)
    outer = [[] for _ in range(folds)]
    for dataset in sorted(groups):
        members = sorted(groups[dataset])
        if len(members) < folds:
            raise ValueError(f"Dataset {dataset} has fewer people than outer folds")
        shuffled = list(rng.permutation(members))
        for i, chunk in enumerate(np.array_split(shuffled, folds)):
            outer[i].extend(str(value) for value in chunk)
    all_ids = {row["id"] for row in entries}
    result = []
    for fold, test_ids in enumerate(outer):
        test_ids = sorted(test_ids)
        train_ids, validation_ids = [], []
        for dataset in sorted(groups):
            available = sorted(set(groups[dataset]) - set(test_ids))
            n_validation = max(1, math.ceil(0.2 * len(available)))
            if len(available) - n_validation < 2:
                raise ValueError(f"Dataset {dataset}: inner split requires at least two training people")
            order = [str(v) for v in rng.permutation(available)]
            validation_ids.extend(order[:n_validation])
            train_ids.extend(order[n_validation:])
        train_ids, validation_ids = sorted(train_ids), sorted(validation_ids)
        groups_this_fold = [set(train_ids), set(validation_ids), set(test_ids)]
        if any(groups_this_fold[i] & groups_this_fold[j] for i in range(3) for j in range(i)):
            raise ValueError("Source split overlap")
        if set.union(*groups_this_fold) != all_ids:
            raise ValueError("Source split does not cover the registered people")
        result.append({"fold": fold, "train_ids": train_ids,
                       "validation_ids": validation_ids, "test_ids": test_ids})
    if sorted(p for row in result for p in row["test_ids"]) != sorted(all_ids):
        raise ValueError("Outer people must each be scored in exactly one fold")
    return result


def create_plan(project) -> dict:
    """Create an immutable scientific task plan, or reuse the identical existing plan.

    A runtime-only change to the documented operational fields does not create a
    new experiment. A changed scientific configuration or registry needs a new
    project directory; existing ledgers/checkpoints are never reset here.
    """
    project = Path(project).expanduser().resolve()
    study = read_json(project / "config" / "study.json")
    registry = _registry(project)
    methods = tuple(study.get("methods", METHODS))
    if methods != METHODS:
        raise ValueError("This experiment freezes the complete five-method comparison")
    folds = int(study.get("source_folds", study.get("outer_folds", 5)))
    if folds < 2:
        raise ValueError("At least two whole-person outer folds are required")
    seeds = _positive_unique_ints(study.get("validation_seeds", study.get("seeds", [20261031, 20261032, 20261033])), "validation_seeds")
    final_seeds = _positive_unique_ints(study.get("final_seeds", [20261101, 20261102, 20261103]), "final_seeds")
    if set(seeds) & set(final_seeds):
        raise ValueError("Development and final seeds must be distinct")
    source_ids = sorted(registry.source_ids)
    external_ids = sorted(registry.external_ids)
    registry.ensure_source(source_ids)
    if set(source_ids) & set(external_ids):
        raise ValueError("Source and external person identifiers overlap")
    source_entries = [registry.by_id[p] for p in source_ids]
    source_counts = dict(sorted(Counter(p["dataset"] for p in source_entries).items()))
    expected = study.get("expected_source_counts")
    if expected is not None and source_counts != expected:
        raise ValueError(f"Source counts differ from the registered protocol: {source_counts} vs {expected}")
    split_seed = int(study.get("split_seed", 20261023))
    identity = {"science_configuration": _configuration(study),
                "data_fingerprint": registry.fingerprint,
                "source_people": [{"id": p["id"], "dataset": p["dataset"]} for p in source_entries],
                "external_people": [{"id": p, "dataset": registry.by_id[p]["dataset"]} for p in external_ids]}
    fingerprint = canonical_hash(identity)
    plan_path, tasks_path = project / "state" / "plan.json", project / "tasks.json"
    if plan_path.exists():
        plan = read_json(plan_path)
        if plan["fingerprint"] != fingerprint:
            raise ValueError("Scientific plan/data changed: preserve this project and use a new experiment version")
        if not tasks_path.exists():
            raise ValueError("Existing plan has lost tasks.json; recover the existing file rather than initialize a replacement")
        tasks = read_json(tasks_path)
        current_development = [t for t in tasks if t["phase"] == "development"]
        if canonical_hash(current_development) != plan["development_tasks_sha256"]:
            raise ValueError("Existing development task definitions changed")
        return {**plan, "reused": True}
    partitions = _partitions(source_entries, folds, split_seed)
    tasks = []
    # First fold comes first so the early queue provides a complete method profile.
    for partition in partitions:
        for seed in seeds:
            for method in methods:
                tasks.append({"id": f"dev-f{partition['fold']:02d}-{method}-s{seed}",
                              "phase": "development", "method": method, "seed": seed, **partition})
    # Recover the narrow interruption between the two initial atomic writes.
    # Existing task content is never replaced by a different generated plan.
    partial_tasks = tasks_path.exists()
    if partial_tasks and read_json(tasks_path) != tasks:
        raise ValueError("tasks.json exists without its plan and differs from deterministic preparation; preserve it")
    plan = {"schema_version": 1, "created_at_utc": utc_now(),
            "fingerprint": fingerprint, "identity": identity,
            "source_counts": source_counts, "external_count": len(external_ids),
            "source_ids": source_ids, "external_ids": external_ids,
            "partitions": partitions, "methods": list(methods),
            "validation_seeds": seeds, "final_seeds": final_seeds,
            "development_task_count": len(tasks), "final_task_count": len(methods) * len(final_seeds),
            "development_tasks_sha256": canonical_hash(tasks),
            "statistical_unit": "person after within-person metric averaging over fitted seeds",
            "primary": "nested outer-source tail_consistency minus erm on weaker-class recall",
            "external_role": "exploratory Dreyer evaluation; prior exposure uncertain",
            "target_model_selection": False}
    if not partial_tasks:
        atomic_json(tasks_path, tasks)
    atomic_json(plan_path, plan)
    return {**plan, "reused": False}


def append_final_tasks(project) -> list:
    """Append final fits using only completed source-inner choices, once.

    The integer median of each method's inner-selected epochs supplies its
    secondary external checkpoint. All methods still train the full fixed
    trajectory for the primary fixed-40 external comparison.
    """
    project = Path(project).expanduser().resolve()
    plan = create_plan(project)
    study = read_json(project / "config" / "study.json")
    tasks_path = project / "tasks.json"
    tasks = read_json(tasks_path)
    development = [t for t in tasks if t["phase"] == "development"]
    choices = {m: [] for m in plan["methods"]}
    records = []
    missing = []
    for task in development:
        path = project / "outputs" / "runs" / task["id"] / "complete.json"
        if not path.exists():
            missing.append(task["id"])
            continue
        result = read_json(path)
        if result.get("status") != "complete" or result.get("task_id", result.get("id")) != task["id"]:
            raise ValueError(f"Invalid completion identity for {task['id']}")
        for key in ("phase", "method", "seed"):
            if result.get(key) != task[key]:
                raise ValueError(f"Completion {key} differs for {task['id']}")
        epoch = result.get("best_epoch")
        if type(epoch) is not int or not 1 <= epoch <= int(study["epochs"]):
            raise ValueError(f"Invalid inner-selected epoch for {task['id']}")
        choices[task["method"]].append(epoch)
        records.append({"task_id": task["id"], "best_epoch": epoch,
                        "complete_sha256": canonical_hash(result)})
    if missing:
        raise PlanNotReady(f"Source development incomplete: {len(missing)} tasks remain")
    if not plan["external_ids"]:
        raise PlanNotReady("No external participant metadata was bound to this experiment")
    selected = {method: int(statistics.median(epochs)) for method, epochs in choices.items()}
    selection = {"schema_version": 1, "plan_fingerprint": plan["fingerprint"],
                 "rule": "integer median of source-inner best epochs across all development folds and seeds",
                 "primary_external_checkpoint": int(study["epochs"]),
                 "selected_epochs": selected, "source_records": records,
                 "target_outcomes_read": False}
    expected = [{"id": f"final-{method}-s{seed}", "phase": "final", "method": method,
                 "seed": seed, "fold": None, "train_ids": plan["source_ids"],
                 "validation_ids": [], "test_ids": plan["external_ids"],
                 "selected_epoch": selected[method]}
                for seed in plan["final_seeds"] for method in plan["methods"]]
    existing = [t for t in tasks if t["phase"] == "final"]
    selection_path = project / "state" / "selection.json"
    if existing:
        if existing != expected or not selection_path.exists() or read_json(selection_path) != selection:
            raise ValueError("Existing final task selection differs; do not regenerate or silently overwrite")
        return []
    if selection_path.exists() and read_json(selection_path) != selection:
        raise ValueError("Saved source selection differs from completed source evidence")
    # A crash after this write is resumable: the identical selection is reused.
    atomic_json(selection_path, selection)
    atomic_json(tasks_path, tasks + expected)
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--append-final", action="store_true")
    args = parser.parse_args()
    if args.append_final:
        print(json.dumps({"final_tasks_added": len(append_final_tasks(args.project))}))
    else:
        result = create_plan(args.project)
        print(json.dumps({k: result[k] for k in ("fingerprint", "development_task_count", "final_task_count", "reused")}))


if __name__ == "__main__":
    main()
