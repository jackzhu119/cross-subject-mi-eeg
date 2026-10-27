"""Freeze cohort membership and unique-trial support before any new fit.

Only source labels and trial identifiers are inspected here. Prepared EEG is
never scanned, and external participants are accessed only through the registry
metadata. All methods and training seeds share each frozen trial whitelist.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import numpy as np

from hpcmi.common import atomic_json, canonical_hash, exclusive_lock, read_json, utc_now
from hpcmi.data import Registry


_OPERATIONAL = {"resource_request", "torch_threads", "num_workers", "checkpoint_seconds",
                "heartbeat_seconds", "eval_batch_size"}
_TASK_COUNTS = {"neural_development": 450, "neural_final": 90,
                "classical_development": 75, "classical_final": 15,
                "neural_total": 540, "classical_total": 90, "total": 630}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _child(project, relative):
    path = Path(relative)
    _require(not path.is_absolute() and ".." not in path.parts, "Non-relative trialset path")
    resolved = (project / path).resolve()
    _require(resolved.is_relative_to(project), "Trialset path escapes project")
    return resolved


def _rng(*identity):
    digest = canonical_hash(list(identity))
    return np.random.default_rng(int(digest[:16], 16))


def _outer_folds(base_plan, source_ids, by_id, count):
    partitions = base_plan.get("partitions", base_plan.get("outer_folds"))
    _require(isinstance(partitions, list) and len(partitions) == count == 5,
             "Expected the five original common outer folds")
    folds, observed = [], []
    for index, row in enumerate(sorted(partitions, key=lambda r: r["fold"])):
        ids = sorted(row["test_ids"])
        _require(row["fold"] == index and ids and len(ids) == len(set(ids))
                 and set(ids).issubset(source_ids), "Invalid original outer test membership")
        _require(sum(by_id[p]["dataset"] == "yang" for p in ids) >= 4,
                 "Every common outer fold must contain at least four Yang participants")
        folds.append({"fold": index, "test_ids": ids})
        observed.extend(ids)
    _require(len(observed) == len(set(observed)) and set(observed) == set(source_ids),
             "Original outer test folds must partition all source people exactly once")
    return folds


def _source_metadata(registry, ids):
    metadata = {}
    registry.ensure_source(ids)
    for person in ids:
        entry = registry.load_person(person)
        # Do not access entry['X']: labels and identifiers define this whitelist.
        y = np.asarray(entry["y"])
        trial_ids = list(entry["trial_ids"])
        _require(y.ndim == 1 and np.issubdtype(y.dtype, np.integer)
                 and set(np.unique(y).tolist()) == {0, 1}, "Invalid source labels: " + person)
        _require(len(trial_ids) == len(y) and all(isinstance(t, str) and t for t in trial_ids)
                 and len(trial_ids) == len(set(trial_ids)), "Invalid source trial identity: " + person)
        metadata[person] = {"y": y, "trial_ids": trial_ids,
                            "dataset": registry.by_id[person]["dataset"]}
    return metadata


def _cells(source_ids, by_id, folds, seeds):
    bnci = sorted(p for p in source_ids if by_id[p]["dataset"] == "bnci")
    yang = sorted(p for p in source_ids if by_id[p]["dataset"] == "yang")
    rows = [{"cell_id": "s9-all", "pool": "S9", "subset": 0, "regime": "all",
             "pool_ids": bnci, "aliases": ["s9-matched"]}]
    for pool, ids in (("Y51", yang), ("S60", sorted(source_ids))):
        for regime in ("all", "matched"):
            rows.append({"cell_id": pool.lower() + "-" + regime, "pool": pool,
                         "subset": 0, "regime": regime, "pool_ids": ids, "aliases": []})
    _require(len(seeds) == len(set(seeds)) == 5, "Exactly five distinct frozen subset seeds are required")
    for subset, seed in enumerate(seeds, 1):
        selected = []
        for fold in folds:
            candidates = sorted(p for p in fold["test_ids"] if by_id[p]["dataset"] == "yang")
            selected.extend(_rng("s29-person-subset-v1", seed, fold["fold"]).choice(
                candidates, size=4, replace=False).tolist())
        for regime in ("all", "matched"):
            rows.append({"cell_id": f"s29r{subset:02d}-{regime}", "pool": "S29",
                         "subset": subset, "subset_seed": seed, "regime": regime,
                         "pool_ids": sorted(bnci + selected), "aliases": []})
    return rows


def _counts(indices, metadata):
    per_person, cohort = {}, {}
    total = {"0": 0, "1": 0}
    for person, positions in indices.items():
        labels = metadata[person]["y"][positions]
        counts = {str(label): int(np.count_nonzero(labels == label)) for label in (0, 1)}
        per_person[person] = counts
        name = metadata[person]["dataset"]
        cohort.setdefault(name, {"0": 0, "1": 0})
        for label in ("0", "1"):
            total[label] += counts[label]
            cohort[name][label] += counts[label]
    return {"per_person": per_person, "class_total": total, "cohort_class_total": cohort,
            "total_trials": sum(total.values())}


def _trialset(cell, phase, fold, train_ids, reference_ids, metadata, data_fingerprint, seed):
    reference = {str(label): sum(int(np.count_nonzero(metadata[p]["y"] == label))
                                for p in reference_ids) for label in (0, 1)}
    indices = {person: [] for person in train_ids}
    if cell["regime"] == "all":
        indices = {person: list(range(len(metadata[person]["y"]))) for person in train_ids}
    else:
        cohorts = sorted({metadata[p]["dataset"] for p in train_ids})
        for label in (0, 1):
            budget = reference[str(label)]
            _require(budget % len(cohorts) == 0, "Class budget cannot be evenly divided between source cohorts")
            cohort_budget = budget // len(cohorts)
            for cohort in cohorts:
                people = sorted(p for p in train_ids if metadata[p]["dataset"] == cohort)
                # Remainder assignment is seeded independently of outcomes.
                order = _rng("trial-quota-v1", seed, phase, fold, cell["cell_id"], cohort, label).permutation(people)
                quotient, remainder = divmod(cohort_budget, len(people))
                for rank, person in enumerate(order):
                    available = np.flatnonzero(metadata[person]["y"] == label)
                    quota = quotient + int(rank < remainder)
                    _require(0 < quota <= len(available), "Insufficient unique source trials for frozen budget: " + person)
                    positions = _rng("trial-selection-v1", seed, phase, fold, cell["cell_id"], person, label).choice(
                        available, size=quota, replace=False)
                    indices[person].extend(int(value) for value in positions)
        indices = {person: sorted(positions) for person, positions in indices.items()}
    counts = _counts(indices, metadata)
    if cell["regime"] == "matched" or cell["pool"] == "S9":
        _require(counts["class_total"] == reference, "Unique-trial class budget mismatch")
    return {"schema_version": 1, "data_fingerprint": data_fingerprint,
            "cell_id": cell["cell_id"], "phase": phase, "fold": fold, "train_ids": train_ids,
            "indices_by_person": indices,
            "trial_ids_by_person": {p: [metadata[p]["trial_ids"][i] for i in positions]
                                    for p, positions in indices.items()},
            "counts": counts, "matched_reference_class_budget": reference,
            "selection_protocol": "source-only-unique-trial-whitelist-v1"}


def _existing(project, identity):
    plan = read_json(project / "state/plan.json")
    _require(plan.get("fingerprint") == canonical_hash(identity) and plan.get("identity") == identity,
             "Existing scientific plan differs; create an explicitly versioned experiment instead")
    tasks_path = project / "tasks.json"
    _require(tasks_path.is_file(), "Existing plan has lost tasks.json; recover the existing task file")
    tasks = read_json(tasks_path)
    _require(canonical_hash(tasks) == plan["tasks_sha256"], "Existing task whitelist changed")
    for relative, expected in plan["trialsets_sha256"].items():
        path = _child(project, relative)
        _require(path.is_file() and _sha(path) == expected, "Frozen trialset changed or missing: " + relative)
    return {**plan, "reused": True}


def create_plan(project, registry=None, base_plan=None):
    """Create all 630 tasks once; an unchanged plan is reused without data scans."""
    project = Path(project).resolve()
    config = read_json(project / "config/study.json")
    paths = read_json(project / "config/paths.json")
    registry = Registry(Path(paths["data_dir"])) if registry is None else registry
    base_plan = read_json(Path(paths["base_project"]) / "state/plan.json") if base_plan is None else base_plan
    source_ids, external_ids = sorted(registry.source_ids), sorted(registry.external_ids)
    actual_counts = {name: sum(registry.by_id[p]["dataset"] == name for p in source_ids)
                     for name in ("bnci", "yang")}
    _require(actual_counts == config["expected_source_counts"] == {"bnci": 9, "yang": 51}
             and len(source_ids) == 60, "Expected BNCI9 and Yang51 source people")
    _require(len(external_ids) == config["expected_external_people"] == 85
             and all(registry.by_id[p]["dataset"] == "dreyer" for p in external_ids),
             "Expected 85 external Dreyer metadata entries")
    _require(config["methods"] == ["erm", "tail"] and config["epochs"] == 40
             and config["updates_per_epoch"] == 128 and config["subjects_per_batch"] == 4
             and config["trials_per_class"] == 16 and config["batch_size"] == 128,
             "Unexpected fixed-endpoint scientific configuration")
    _require(len(config["validation_seeds"]) == len(set(config["validation_seeds"])) == 3
             and len(config["final_seeds"]) == len(set(config["final_seeds"])) == 3,
             "Exactly three development and final training seeds are required")
    folds = _outer_folds(base_plan, source_ids, registry.by_id, config["source_folds"])
    science = {k: value for k, value in config.items() if k not in _OPERATIONAL}
    identity = {"protocol": "composition-whitelists-v1", "science": science,
                "data_fingerprint": registry.fingerprint, "source_ids": source_ids,
                "external_ids": external_ids, "outer_folds": folds,
                "base_plan_fingerprint": base_plan.get("fingerprint")}
    with exclusive_lock(project / "state/plan.lock"):
        if (project / "state/plan.json").exists():
            return _existing(project, identity)
        metadata = _source_metadata(registry, source_ids)
        cells = _cells(source_ids, registry.by_id, folds, config["subset_seeds"])
        tasks, trialsets = [], {}
        for phase, fold, heldout in [("development", r["fold"], r["test_ids"]) for r in folds] + [
                ("final", None, external_ids)]:
            reference_ids = [p for p in source_ids if registry.by_id[p]["dataset"] == "bnci" and p not in heldout]
            prefix = f"dev-f{fold:02d}" if fold is not None else "final"
            for cell in cells:
                train_ids = sorted(set(cell["pool_ids"]) - set(heldout))
                value = _trialset(cell, phase, fold, train_ids, reference_ids, metadata,
                                  registry.fingerprint, config["trial_subset_seed"])
                relative = f"state/trialsets/{prefix}-{cell['cell_id']}.json"
                trialsets[relative] = value
                digest = hashlib.sha256(_json_bytes(value)).hexdigest()
                method_seeds = [(method, seed, "neural") for method in config["methods"]
                                for seed in config["validation_seeds" if phase == "development" else "final_seeds"]]
                method_seeds.append(("weighted_csp_rlda", 0, "classical"))
                for method, seed, family in method_seeds:
                    task_id = f"{prefix}-{cell['cell_id']}-{method}-s{seed}"
                    _require(len(task_id) < 100 and re.fullmatch(r"[A-Za-z0-9_.-]+", task_id), "Unsafe task ID")
                    tasks.append({"id": task_id, "phase": phase, "family": family, "method": method,
                                  "seed": seed, "fold": fold, "cell_id": cell["cell_id"],
                                  "pool": cell["pool"], "subset": cell["subset"], "regime": cell["regime"],
                                  "train_ids": train_ids, "validation_ids": [], "test_ids": heldout,
                                  "train_trials_file": relative, "train_trials_sha256": digest,
                                  "epochs": config["epochs"], "updates_per_epoch": config["updates_per_epoch"],
                                  "evaluation": config["evaluation"]})
        _require(len(tasks) == _TASK_COUNTS["total"] and len({t["id"] for t in tasks}) == len(tasks),
                 "Unexpected experiment task count")
        # A crashed initial publication can leave exact deterministic files.
        # Reuse only identical files; preserve any conflicting evidence.
        for relative, value in trialsets.items():
            path = _child(project, relative)
            _require(not path.exists() or path.read_bytes() == _json_bytes(value),
                     "Unregistered trialset differs; retain it for review: " + relative)
        tasks_path = project / "tasks.json"
        _require(not tasks_path.exists() or read_json(tasks_path) == tasks,
                 "Existing unregistered task file differs; preserve it")
        for relative, value in trialsets.items():
            if not _child(project, relative).exists():
                atomic_json(_child(project, relative), value)
        if not tasks_path.exists():
            atomic_json(tasks_path, tasks)
        hashes = {relative: hashlib.sha256(_json_bytes(value)).hexdigest() for relative, value in trialsets.items()}
        plan = {"schema_version": 1, "created_at_utc": utc_now(), "fingerprint": canonical_hash(identity),
                "identity": identity, "data_fingerprint": registry.fingerprint,
                "source_ids": source_ids, "external_ids": external_ids, "outer_folds": folds,
                "cells": cells, "task_counts": _TASK_COUNTS,
                "development_task_count": 525, "final_task_count": 105,
                "tasks_sha256": canonical_hash(tasks), "trialsets_sha256": hashes,
                "source_metadata_only": True, "external_eeg_read": False,
                "s9_matched_alias": "s9-all"}
        atomic_json(project / "state/plan.json", plan)
        return {**plan, "reused": False}


def task_trialset(project, task, registry):
    """Verify this task's small source whitelist before sampling or CSP fitting."""
    project = Path(project).resolve()
    path = _child(project, task["train_trials_file"])
    _require(path.is_file() and _sha(path) == task["train_trials_sha256"], "Task trialset SHA256 mismatch")
    value = read_json(path)
    _require(value["schema_version"] == 1 and value["data_fingerprint"] == registry.fingerprint,
             "Trialset prepared-data identity mismatch")
    for key in ("cell_id", "phase", "fold", "train_ids"):
        _require(value[key] == task[key], "Task/trialset identity mismatch: " + key)
    registry.ensure_source(task["train_ids"])
    indices = value["indices_by_person"]
    _require(set(indices) == set(task["train_ids"]) == set(value["trial_ids_by_person"]),
             "Trialset participant whitelist mismatch")
    metadata = _source_metadata(registry, task["train_ids"])
    for person, positions in indices.items():
        _require(isinstance(positions, list) and positions
                 and all(type(index) is int for index in positions)
                 and positions == sorted(set(positions)) and positions[0] >= 0
                 and positions[-1] < len(metadata[person]["y"]), "Invalid unique source trial indices")
        expected = [metadata[person]["trial_ids"][index] for index in positions]
        _require(value["trial_ids_by_person"][person] == expected, "Frozen source trial identity changed")
        _require(set(metadata[person]["y"][positions].tolist()) == {0, 1}, "Trialset omits a source participant class")
    _require(value["counts"] == _counts(indices, metadata), "Frozen source trial counts changed")
    return indices


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    args = parser.parse_args(argv)
    result = create_plan(args.project)
    print(json.dumps({k: result[k] for k in ("fingerprint", "task_counts", "reused")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
