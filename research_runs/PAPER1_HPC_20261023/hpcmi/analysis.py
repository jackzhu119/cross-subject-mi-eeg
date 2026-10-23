"""Paired participant analysis of saved evaluation summaries; no model or EEG I/O."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np

from .common import atomic_json, canonical_hash, read_json, utc_now


class AnalysisNotReady(RuntimeError):
    pass


def holm_adjust(p_values):
    values = np.asarray(p_values, dtype=float)
    if values.ndim != 1 or np.any(~np.isfinite(values)) or np.any((values < 0) | (values > 1)):
        raise ValueError("Invalid p values")
    order = np.argsort(values, kind="stable")
    adjusted = np.empty(len(values), dtype=float)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (len(values) - rank) * values[index])
        adjusted[index] = min(1.0, running)
    return adjusted.tolist()


def paired_statistics(differences, datasets, *, equal_cohort, seed, bootstrap_replicates=10000,
                      permutation_replicates=100000):
    """Conditional participant-paired intervals and two-sided sign-flip inference.

    Source summaries weight cohorts equally and people equally within cohort.
    Bootstrap resampling is stratified by cohort to preserve that estimand.
    External summaries weight each person equally. Seeds are averaged before
    this function; they never increase the participant sample size.
    """
    d = np.asarray(differences, dtype=np.float64)
    ds = np.asarray(datasets, dtype=str)
    if d.ndim != 1 or len(d) < 2 or len(d) != len(ds) or not np.isfinite(d).all():
        raise ValueError("At least two finite paired participant differences are required")
    if bootstrap_replicates < 1 or permutation_replicates < 1:
        raise ValueError("Positive resampling counts required")
    strata = [np.flatnonzero(ds == value) for value in sorted(set(ds))] if equal_cohort else [np.arange(len(d))]
    weights = np.zeros(len(d), dtype=np.float64)
    for group in strata:
        weights[group] = 1.0 / (len(strata) * len(group))
    effect = float(d @ weights)
    rng = np.random.default_rng(seed)
    bootstrap = np.zeros(bootstrap_replicates, dtype=np.float64)
    for group in strata:
        # Bounded chunks avoid a large all-replicates x people temporary array.
        for start in range(0, bootstrap_replicates, 2048):
            count = min(2048, bootstrap_replicates - start)
            indices = rng.integers(0, len(group), size=(count, len(group)))
            bootstrap[start:start+count] += d[group][indices].mean(axis=1) / len(strata)
    low, high = np.quantile(bootstrap, [0.025, 0.975])
    weighted = d * weights
    threshold = abs(effect) - 1e-14
    if len(d) <= 16:
        total = 1 << len(d)
        extreme = 0
        bit_indices = np.arange(len(d), dtype=np.uint64)
        for start in range(0, total, 2048):
            values = np.arange(start, min(start + 2048, total), dtype=np.uint64)
            signs = (((values[:, None] >> bit_indices[None, :]) & 1).astype(float) * 2.0 - 1.0)
            extreme += int(np.count_nonzero(np.abs(signs @ weighted) >= threshold))
        p = extreme / total
        permutation_kind = "exact paired sign-flip enumeration"
    else:
        extreme, total = 0, permutation_replicates
        for start in range(0, total, 2048):
            count = min(2048, total - start)
            signs = rng.integers(0, 2, size=(count, len(d)), dtype=np.int8).astype(float) * 2.0 - 1.0
            extreme += int(np.count_nonzero(np.abs(signs @ weighted) >= threshold))
        p = (extreme + 1) / (total + 1)
        permutation_kind = "Monte Carlo paired sign-flip with plus-one correction"
    return {"n_participants": len(d), "effect": effect,
            "effect_pp": 100 * effect, "ci95_low_pp": 100 * float(low),
            "ci95_high_pp": 100 * float(high), "p_raw": float(p),
            "improved": int(np.count_nonzero(d > 1e-12)),
            "declined": int(np.count_nonzero(d < -1e-12)),
            "numerically_unchanged": int(np.count_nonzero(np.abs(d) <= 1e-12)),
            "aggregation": "equal cohort then equal person" if equal_cohort else "equal person",
            "bootstrap": "stratified paired participant percentile" if equal_cohort else "paired participant percentile",
            "bootstrap_replicates": bootstrap_replicates,
            "permutation": permutation_kind, "permutation_replicates": total,
            "seed": int(seed), "interval_scope": "pointwise, conditional on fitted models and averaged seeds"}


def _read_domain(project, tasks, variant):
    rows = []
    evidence = []
    missing = []
    for task in tasks:
        run = project / "outputs" / "runs" / task["id"]
        complete_path = run / "complete.json"
        if not complete_path.exists():
            missing.append(task["id"])
            continue
        complete = read_json(complete_path)
        if complete.get("status") != "complete" or complete.get("task_id", complete.get("id")) != task["id"]:
            raise ValueError(f"Completion identity differs: {task['id']}")
        for key in ("phase", "method", "seed"):
            if complete.get(key) != task[key]:
                raise ValueError(f"Completed task field {key} differs: {task['id']}")
        relative = complete.get("evaluations", {}).get(variant)
        if not isinstance(relative, str):
            raise ValueError(f"Missing completed evaluation variant: {task['id']} / {variant}")
        path = (run / relative).resolve()
        if run.resolve() not in path.parents:
            raise ValueError("Evaluation path escapes its task directory")
        summary = read_json(path)
        if summary.get("variant") != variant:
            raise ValueError("Evaluation variant identity differs")
        people = summary["people"]
        if len(people) != len(task["test_ids"]) or {r["person_id"] for r in people} != set(task["test_ids"]):
            raise ValueError("Completed evaluation omits or duplicates registered test people")
        for r in people:
            if any(type(r.get(key)) is not int or r[key] <= 0 for key in ("n", "n_left", "n_right")) or r["n"] != r["n_left"] + r["n_right"]:
                raise ValueError("Invalid saved class/trial counts")
            for metric in ("recall_left", "recall_right", "ba", "min_recall"):
                if not np.isfinite(r[metric]) or not 0 <= r[metric] <= 1:
                    raise ValueError("Nonfinite or invalid saved participant metric")
            if not np.isclose(r["ba"], (r["recall_left"] + r["recall_right"]) / 2, rtol=0, atol=1e-12):
                raise ValueError("Saved balanced accuracy differs from saved class recalls")
            if not np.isclose(r["min_recall"], min(r["recall_left"], r["recall_right"]), rtol=0, atol=1e-12):
                raise ValueError("Saved weaker-class recall differs from saved class recalls")
            if r.get("seed") != task["seed"] or r.get("variant") != variant:
                raise ValueError("Saved participant seed/variant identity differs")
            rows.append({**r, "method": task["method"], "task_id": task["id"], "fold": task["fold"]})
        evidence.append({"task_id": task["id"], "complete_sha256": canonical_hash(complete),
                         "evaluation_sha256": canonical_hash(summary)})
    if missing:
        raise AnalysisNotReady(f"{variant}: {len(missing)} tasks are not complete")
    return rows, evidence


def _aggregate_people(rows, methods, expected_seeds):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["method"], row["person_id"]].append(row)
    result = []
    for (method, person), values in sorted(grouped.items()):
        seeds = [v["seed"] for v in values]
        if len(seeds) != len(expected_seeds) or set(seeds) != set(expected_seeds):
            raise ValueError(f"Missing or duplicate seed evaluation: {method}/{person}")
        if len({v["dataset"] for v in values}) != 1 or any(len({v[k] for v in values}) != 1 for k in ("n", "n_left", "n_right")):
            raise ValueError("Person/dataset/trial count identity differs across seeds")
        result.append({"method": method, "person_id": person, "dataset": values[0]["dataset"],
                       "n_trials": values[0]["n"], "n_seeds": len(values),
                       **{metric: float(np.mean([v[metric] for v in values]))
                          for metric in ("ba", "min_recall", "recall_left", "recall_right")}})
    rosters = [{row["person_id"] for row in result if row["method"] == m} for m in methods]
    if not rosters or not rosters[0] or any(roster != rosters[0] for roster in rosters):
        raise ValueError("Methods do not score exactly the same registered people")
    return result


def _domain_result(rows, methods, seeds, domain_name, settings):
    people = _aggregate_people(rows, methods, seeds)
    equal_cohort = domain_name == "nested_outer"
    roster = sorted(row["person_id"] for row in people if row["method"] == "erm")
    by = {(r["method"], r["person_id"]): r for r in people}
    datasets = [by["erm", person]["dataset"] for person in roster]
    if any(by[method, person]["dataset"] != by["erm", person]["dataset"] for method in methods for person in roster):
        raise ValueError("Dataset identity differs between methods")
    means = []
    for method in methods:
        for metric in ("min_recall", "ba", "recall_left", "recall_right"):
            values = np.asarray([by[method, person][metric] for person in roster])
            if equal_cohort:
                mean = np.mean([values[np.asarray(datasets) == d].mean() for d in sorted(set(datasets))])
            else:
                mean = values.mean()
            means.append({"method": method, "metric": metric, "mean": float(mean),
                          "mean_percent": float(100 * mean), "n_participants": len(roster)})
    comparisons = [("primary" if equal_cohort else "exploratory_registered", "erm", "min_recall"),
                   ("secondary", "groupdro", "min_recall"), ("secondary", "tail", "min_recall"),
                   ("secondary", "consistency", "min_recall"), ("secondary", "erm", "ba")]
    tests = []
    for family, comparator, metric in comparisons:
        contrast = f"tail_consistency-minus-{comparator}-{metric}"
        salt = int(hashlib.sha256((domain_name + "/" + contrast).encode()).hexdigest()[:8], 16)
        seed = (int(settings.get("analysis_seed", 20261024)) + salt) % (2**63)
        delta = [by["tail_consistency", person][metric] - by[comparator, person][metric] for person in roster]
        statistics = paired_statistics(delta, datasets, equal_cohort=equal_cohort, seed=seed,
                                       bootstrap_replicates=int(settings.get("bootstrap_replicates", 10000)),
                                       permutation_replicates=int(settings.get("permutation_replicates", 100000)))
        tests.append({"contrast": contrast, "family": family, "endpoint": metric, **statistics})
    for index, adjusted in enumerate(holm_adjust([t["p_raw"] for t in tests[1:]]), start=1):
        tests[index]["p_holm"] = adjusted
    return {"domain": domain_name, "status": "complete", "n_participants": len(roster),
            "n_seeds": len(seeds), "method_means": means, "comparisons": tests,
            "secondary_family_size": 4, "all_comparison_directions_retained": True,
            "independent_external_confirmation": False,
            "inference_scope": "Conditional on fitted models; paired sign flips require exchangeable signs. Shared training sets and cohort dependence are not removed by participant resampling."}, people


def analyze(project) -> dict:
    """Analyze complete domains and reuse unchanged summaries on subsequent sync ticks."""
    project = Path(project).expanduser().resolve()
    plan = read_json(project / "state" / "plan.json")
    study = read_json(project / "config" / "study.json")
    tasks = read_json(project / "tasks.json")
    development = [t for t in tasks if t["phase"] == "development"]
    final = [t for t in tasks if t["phase"] == "final"]
    if len(development) != plan["development_task_count"]:
        raise ValueError("Development task count differs from its frozen plan")
    out = project / "outputs" / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    domains = [("nested_outer", development, "outer_best", plan["validation_seeds"])]
    if final:
        if len(final) != plan["final_task_count"]:
            raise ValueError("Final task count differs from its frozen plan")
        domains += [("external_fixed40", final, "fixed40", plan["final_seeds"]),
                    ("external_source_selected", final, "source_selected", plan["final_seeds"])]
    result = {"schema_version": 1, "updated_at_utc": utc_now(), "plan_fingerprint": plan["fingerprint"],
              "status": "complete" if final else "source_analysis_complete_external_pending",
              "new_model_fits": 0, "new_model_inference": 0, "raw_eeg_read": False,
              "domains": {}, "pending": {}}
    settings = {k: study.get(k, default) for k, default in [("analysis_seed", 20261024), ("bootstrap_replicates", 10000), ("permutation_replicates", 100000)]}
    for name, domain_tasks, variant, seeds in domains:
        try:
            rows, evidence = _read_domain(project, domain_tasks, variant)
        except AnalysisNotReady as error:
            result["pending"][name] = str(error)
            result["status"] = "partially_complete"
            continue
        identity = canonical_hash({"plan": plan["fingerprint"], "evidence": evidence, "settings": settings, "domain": name})
        path = out / f"{name}.json"
        if path.exists():
            stored = read_json(path)
            if stored.get("input_fingerprint") != identity:
                raise ValueError(f"Completed statistical inputs changed for {name}; preserve prior results and inspect")
            summary = stored
        else:
            summary, people = _domain_result(rows, plan["methods"], seeds, name, settings)
            summary.update({"input_fingerprint": identity, "source_evidence": evidence,
                            "analysis_settings": settings, "completed_at_utc": utc_now()})
            atomic_json(out / f"{name}_participants.json", people)
            atomic_json(path, summary)
        result["domains"][name] = {k: v for k, v in summary.items() if k not in {"source_evidence"}}
    if not result["domains"]:
        result["status"] = "waiting_for_complete_saved_evaluations"
    atomic_json(out / "summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.project)
    print(json.dumps({"status": result["status"], "domains": list(result["domains"]), "pending": result["pending"]}, indent=2))


if __name__ == "__main__":
    main()
