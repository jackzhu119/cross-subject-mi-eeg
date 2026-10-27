"""Frozen composition contrasts from saved participant summaries; no EEG or inference."""
from __future__ import annotations
import argparse
from collections import defaultdict
import csv
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path
import numpy as np
from hpcmi.common import atomic_json, canonical_hash, read_json, utc_now

RECALL_METRICS = ("min_recall", "ba", "recall_left", "recall_right")
METRICS = RECALL_METRICS + ("ce",)
METHODS = ("erm", "tail", "weighted_csp_rlda")
CELLS = ("s9-all", "y51-all", "y51-matched", "s60-all", "s60-matched") + tuple(
    f"s29r{i:02d}-{regime}" for i in range(1, 6) for regime in ("all", "matched"))

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



def _write_csv(path, rows):
    rows = list(rows)
    if not rows:
        return
    names = list(dict.fromkeys(key for row in rows for key in row))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=names, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as output:
            output.write(stream.getvalue())
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load_rows(project, tasks, variant):
    rows, evidence, missing = [], [], []
    for task in tasks:
        run = project / "outputs/runs" / task["id"]
        path = run / "complete.json"
        if not path.exists():
            missing.append(task["id"])
            continue
        complete = read_json(path)
        if complete.get("status") != "complete" or complete.get("task_id", complete.get("id")) != task["id"]:
            raise ValueError("Completion identity differs: " + task["id"])
        for key in ("family", "cell_id", "phase", "method", "seed", "fold", "train_trials_sha256"):
            if complete.get(key) != task.get(key):
                raise ValueError("Completed field differs: " + key + "/" + task["id"])
        relative = complete.get("evaluations", {}).get(variant)
        if not isinstance(relative, str):
            raise ValueError("Missing completed fixed-endpoint evaluation")
        summary_path = (run / relative).resolve()
        if run.resolve() not in summary_path.parents:
            raise ValueError("Evaluation path escapes task")
        summary = read_json(summary_path)
        if summary.get("variant") != variant:
            raise ValueError("Evaluation variant differs")
        digest = complete.get("model_sha256")
        if not isinstance(digest, str) or len(digest) != 64 or summary.get("model_sha256") != digest:
            raise ValueError("Evaluation model identity differs from completed task")
        people = summary["people"]
        if len(people) != len(task["test_ids"]) or {row["person_id"] for row in people} != set(task["test_ids"]):
            raise ValueError("Evaluation omits or duplicates registered test participants")
        for person in people:
            if person.get("seed") != task["seed"] or person.get("variant") != variant:
                raise ValueError("Participant seed/variant differs")
            if not isinstance(person.get("dataset"), str):
                raise ValueError("Missing participant cohort")
            if any(type(person.get(k)) is not int or person[k] <= 0 for k in ("n", "n_left", "n_right")) or person["n"] != person["n_left"] + person["n_right"]:
                raise ValueError("Invalid participant trial counts")
            if any(not np.isfinite(person[m]) or not 0 <= person[m] <= 1 for m in RECALL_METRICS):
                raise ValueError("Invalid saved participant metric")
            if not np.isfinite(person.get("ce", float("nan"))) or person["ce"] < 0:
                raise ValueError("Invalid saved participant cross-entropy")
            if not np.isclose(person["ba"], (person["recall_left"] + person["recall_right"]) / 2, rtol=0, atol=1e-12):
                raise ValueError("BA differs from recalls")
            if not np.isclose(person["min_recall"], min(person["recall_left"], person["recall_right"]), rtol=0, atol=1e-12):
                raise ValueError("W differs from recalls")
            rows.append({**person, **{k: task[k] for k in ("family", "cell_id", "method", "fold", "seed")}, "task_id": task["id"]})
        evidence.append({"task_id": task["id"], "family": task["family"],
                         "complete_sha256": canonical_hash(complete), "evaluation_sha256": canonical_hash(summary)})
    return rows, evidence, missing


def aggregate_people(rows, expected_seeds):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["cell_id"], row["method"], row["person_id"]].append(row)
    output = []
    for (cell, method, person), values in sorted(grouped.items()):
        seeds = expected_seeds if method != "weighted_csp_rlda" else [0]
        if len(values) != len(seeds) or {v["seed"] for v in values} != set(seeds):
            raise ValueError("Missing or duplicate seed: " + "/".join((cell, method, person)))
        for key in ("dataset", "fold", "n", "n_left", "n_right"):
            if len({v[key] for v in values}) != 1:
                raise ValueError("Cross-seed participant identity/count differs: " + key)
        output.append({"cell_id": cell, "method": method, "person_id": person,
                       "dataset": values[0]["dataset"], "fold": values[0]["fold"],
                       "n_seeds": len(values), "n_trials": values[0]["n"],
                       **{m: float(np.mean([v[m] for v in values])) for m in METRICS}})
    return output


def _weighted(values, datasets, equal_cohort):
    values = np.asarray(values, dtype=np.float64)
    datasets = np.asarray(datasets, dtype=str)
    if not equal_cohort:
        return float(values.mean())
    return float(np.mean([values[datasets == cohort].mean() for cohort in sorted(set(datasets))]))


def _means(people, equal_cohort):
    grouped = defaultdict(list)
    for row in people:
        grouped[row["cell_id"], row["method"]].append(row)
    result = []
    for (cell, method), rows in sorted(grouped.items()):
        for cohort in ["overall"] + sorted({r["dataset"] for r in rows}):
            chosen = rows if cohort == "overall" else [r for r in rows if r["dataset"] == cohort]
            for metric in METRICS:
                mean = _weighted([r[metric] for r in chosen], [r["dataset"] for r in chosen], equal_cohort and cohort == "overall")
                result.append({"cell_id": cell, "method": method, "cohort": cohort,
                               "metric": metric, "mean": mean, "mean_percent": mean * 100,
                               "n_participants": len(chosen)})
    return result


def _contrast_vectors(people):
    by = {(r["cell_id"], r["method"], r["person_id"]): r for r in people}
    roster = sorted(r["person_id"] for r in people if r["cell_id"] == "s9-all" and r["method"] == "erm")
    if not roster:
        raise ValueError("No paired participant roster")
    reference = [by["s9-all", "erm", person] for person in roster]
    cohorts = [r["dataset"] for r in reference]
    folds = [r["fold"] for r in reference]
    for cell in CELLS:
        for method in ("erm", "tail"):
            rows = [r for r in people if r["cell_id"] == cell and r["method"] == method]
            if len(rows) != len(roster) or {r["person_id"] for r in rows} != set(roster):
                raise ValueError("Cell methods score different participant rosters")
            for person in roster:
                row, base = by[cell, method, person], by["s9-all", "erm", person]
                if any(row[k] != base[k] for k in ("dataset", "fold", "n_trials")):
                    raise ValueError("Cell methods score different participant/trial identities")
    def vector(cell, method, metric="min_recall"):
        if cell == "s9-matched":
            cell = "s9-all"
        if cell.startswith("s29mean-"):
            regime = cell.split("-", 1)[1]
            # Each person's W is already calculated per seed then averaged. The
            # linear mean over the five subsets commutes with the seed mean.
            return np.mean([vector(f"s29r{i:02d}-{regime}", method, metric) for i in range(1, 6)], axis=0)
        return np.asarray([by[cell, method, p][metric] for p in roster])
    def interaction(regime, metric="min_recall"):
        return vector("s60-" + regime, "tail", metric) - vector("s60-" + regime, "erm", metric) - vector("s9-all", "tail", metric) + vector("s9-all", "erm", metric)
    specifications = [
        ("matched_source_composition_by_tail_W_interaction", "min_recall", interaction("matched")),
        ("matched_s60_minus_s9_erm_W", "min_recall", vector("s60-matched", "erm") - vector("s9-all", "erm")),
        ("matched_tail_minus_erm_s60_W", "min_recall", vector("s60-matched", "tail") - vector("s60-matched", "erm")),
        ("all_source_composition_by_tail_W_interaction", "min_recall", interaction("all")),
        ("s60_erm_all_minus_matched_W", "min_recall", vector("s60-all", "erm") - vector("s60-matched", "erm")),
        ("matched_source_composition_by_tail_BA_interaction", "ba", interaction("matched", "ba")),
        ("matched_s29mean_minus_s9_erm_W", "min_recall", vector("s29mean-matched", "erm") - vector("s9-all", "erm")),
        ("matched_s60_minus_s29mean_erm_W", "min_recall", vector("s60-matched", "erm") - vector("s29mean-matched", "erm")),
        ("matched_y51_minus_s9_erm_W", "min_recall", vector("y51-matched", "erm") - vector("s9-all", "erm")),
        ("matched_s60_minus_y51_erm_W", "min_recall", vector("s60-matched", "erm") - vector("y51-matched", "erm"))]
    subset = []
    for i in range(1, 6):
        for metric in METRICS:
            delta = vector(f"s29r{i:02d}-matched", "erm", metric) - vector("s9-all", "erm", metric)
            subset.append((i, metric, delta))
    return roster, cohorts, folds, specifications, subset


def _infer(people, domain, settings):
    roster, cohorts, folds, specifications, subsets = _contrast_vectors(people)
    equal_cohort = domain == "source_fixed40"
    tests, individual, per_fold = [], [], []
    for index, (name, endpoint, delta) in enumerate(specifications):
        salt = int(hashlib.sha256((domain + "/" + name).encode()).hexdigest()[:8], 16)
        stats = paired_statistics(delta, cohorts, equal_cohort=equal_cohort,
                                  seed=(int(settings["analysis_seed"]) + salt) % (2**63),
                                  bootstrap_replicates=int(settings["bootstrap_replicates"]),
                                  permutation_replicates=int(settings["permutation_replicates"]))
        family = ("primary" if index == 0 else "source_secondary_holm9") if equal_cohort else "external_exploratory_holm10"
        tests.append({"contrast": name, "family": family, "endpoint": endpoint, **stats})
        individual.extend({"contrast": name, "endpoint": endpoint, "person_id": p, "dataset": c,
                           "fold": f, "difference": float(d), "difference_pp": float(100*d)}
                          for p, c, f, d in zip(roster, cohorts, folds, delta))
        if equal_cohort:
            for fold in sorted(set(folds)):
                mask = np.asarray([f == fold for f in folds])
                per_fold.append({"contrast": name, "endpoint": endpoint, "fold": fold,
                                 "n_participants": int(mask.sum()),
                                 "effect_pp": 100 * _weighted(delta[mask], np.asarray(cohorts)[mask], True),
                                 "role": "descriptive_fold_sensitivity"})
    start = 1 if equal_cohort else 0
    for row, adjusted in zip(tests[start:], holm_adjust([row["p_raw"] for row in tests[start:]])):
        row["p_holm"] = adjusted
    subset_rows = [{"subset": i, "metric": metric, "effect_pp": 100 * _weighted(delta, cohorts, equal_cohort),
                    "n_participants": len(roster), "role": "descriptive_subset_sensitivity"}
                   for i, metric, delta in subsets]
    return {"comparisons": tests, "n_participants": len(roster),
            "primary_family_size": 1 if equal_cohort else 0,
            "secondary_family_size": 9 if equal_cohort else 10,
            "all_comparison_directions_retained": True,
            "independent_external_confirmation": False,
            "inference_scope": "Conditional on fitted models, frozen trial caps, and five source subsets. Paired sign flips require exchangeable signs. Shared training sets are not made independent by participant resampling.",
            "S29_aggregation": "mean within participant across five subsets and three seeds; not 300 independent participants"}, individual, per_fold, subset_rows


def _classical_differences(people, equal_cohort):
    by = {(r["cell_id"], r["method"], r["person_id"]): r for r in people}
    output = []
    for cell in CELLS:
        roster = sorted(r["person_id"] for r in people if r["cell_id"] == cell and r["method"] == "weighted_csp_rlda")
        for method in ("erm", "tail"):
            for metric in METRICS:
                if not roster or any((cell, method, p) not in by for p in roster):
                    continue
                for person in roster:
                    neural_row, classical_row = by[cell, method, person], by[cell, "weighted_csp_rlda", person]
                    if any(neural_row[key] != classical_row[key] for key in ("dataset", "fold", "n_trials")):
                        raise ValueError("Classical reference participant/trial identity differs")
                delta = [by[cell, method, p][metric] - by[cell, "weighted_csp_rlda", p][metric] for p in roster]
                cohorts = [by[cell, method, p]["dataset"] for p in roster]
                output.append({"cell_id": cell, "method": method, "comparator": "weighted_csp_rlda",
                               "metric": metric, "effect_pp": 100 * _weighted(delta, cohorts, equal_cohort),
                               "n_participants": len(roster), "role": "descriptive_not_compute_matched"})
    return output


def analyze(project):
    project = Path(project).resolve()
    plan, study, tasks = (read_json(project / relative) for relative in ("state/plan.json", "config/study.json", "tasks.json"))
    if canonical_hash(tasks) != plan["tasks_sha256"]:
        raise ValueError("Frozen tasks changed")
    out = project / "outputs/analysis"
    out.mkdir(parents=True, exist_ok=True)
    settings = {k: study[k] for k in ("analysis_seed", "bootstrap_replicates", "permutation_replicates")}
    result = {"schema_version": 1, "updated_at_utc": utc_now(), "plan_fingerprint": plan["fingerprint"],
              "status": "complete", "new_model_fits": 0, "new_model_inference": 0, "raw_eeg_read": False,
              "domains": {}, "pending": {}}
    for phase, domain, variant, seeds in (("development", "source_fixed40", "outer_fixed40", study["validation_seeds"]),
                                         ("final", "external_fixed40", "fixed40", study["final_seeds"])):
        domain_tasks = [t for t in tasks if t["phase"] == phase]
        rows, evidence, missing = _load_rows(project, domain_tasks, variant)
        missing_neural = [t["id"] for t in domain_tasks if t["family"] == "neural" and t["id"] in missing]
        missing_classical = [t["id"] for t in domain_tasks if t["family"] == "classical" and t["id"] in missing]
        summary = {"domain": domain, "status": "complete" if not missing else "partial", "variant": variant,
                   "completed_tasks": len(domain_tasks) - len(missing), "expected_tasks": len(domain_tasks),
                   "missing_neural_tasks": missing_neural, "missing_classical_tasks": missing_classical,
                   "aggregation": "equal cohort then equal person" if phase == "development" else "equal person"}
        if missing:
            result["status"] = "partial"
            result["pending"][domain] = {"neural": len(missing_neural), "classical": len(missing_classical)}
        # Only aggregate cell/method groups whose full registered task set is
        # present. An interrupted seed never becomes a smaller-seed estimate.
        complete_groups = {(t["cell_id"], t["method"]) for t in domain_tasks}
        complete_groups -= {(t["cell_id"], t["method"]) for t in domain_tasks if t["id"] in missing}
        valid_rows = [r for r in rows if (r["cell_id"], r["method"]) in complete_groups]
        people = aggregate_people(valid_rows, seeds)
        _write_csv(out / (domain + "_seed_participants.csv"), valid_rows)
        seed_means = []
        for seed in sorted({row["seed"] for row in valid_rows}):
            seed_means.extend({"seed": seed, **row} for row in
                              _means([r for r in valid_rows if r["seed"] == seed], phase == "development"))
        _write_csv(out / (domain + "_seed_cell_metrics.csv"), seed_means)
        summary["cell_means"] = _means(people, phase == "development")
        atomic_json(out / (domain + "_participants.json"), people)
        _write_csv(out / (domain + "_participants.csv"), people)
        _write_csv(out / (domain + "_cell_metrics.csv"), summary["cell_means"])
        summary["cohort_cell_means"] = [row for row in summary["cell_means"] if row["cohort"] != "overall"]
        _write_csv(out / (domain + "_cohort_metrics.csv"), summary["cohort_cell_means"])
        if not missing_neural:
            neural = [r for r in people if r["method"] != "weighted_csp_rlda"]
            identity = canonical_hash({"plan": plan["fingerprint"], "domain": domain, "settings": settings,
                                       "evidence": [e for e in evidence if e["family"] == "neural"]})
            cache = out / (domain + "_inference.json")
            if cache.exists():
                stored = read_json(cache)
                if stored["input_fingerprint"] != identity:
                    raise ValueError("Frozen completed inference inputs changed; preserve previous analysis")
                inferred, individual, per_fold, subset_rows = (stored[k] for k in ("inference", "individual", "per_fold", "subsets"))
            else:
                inferred, individual, per_fold, subset_rows = _infer(neural, domain, settings)
                atomic_json(cache, {"input_fingerprint": identity, "inference": inferred, "individual": individual,
                                    "per_fold": per_fold, "subsets": subset_rows, "completed_at_utc": utc_now(),
                                    "settings": settings})
            summary.update(inferred)
            summary["inference_input_fingerprint"] = identity
            summary["analysis_settings"] = settings
            _write_csv(out / (domain + "_comparisons.csv"), summary["comparisons"])
            _write_csv(out / (domain + "_participant_contrasts.csv"), individual)
            _write_csv(out / (domain + "_fold_sensitivity.csv"), per_fold)
            _write_csv(out / (domain + "_subset_sensitivity.csv"), subset_rows)
        else:
            summary["comparisons"] = []
            summary["inference_status"] = "pending_all_registered_neural_tasks"
        classical_deltas = _classical_differences(people, phase == "development")
        summary["classical_reference_differences"] = classical_deltas
        _write_csv(out / (domain + "_classical_differences.csv"), classical_deltas)
        atomic_json(out / (domain + ".json"), summary)
        result["domains"][domain] = summary
    atomic_json(out / "summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    result = analyze(args.project)
    print(json.dumps({"status": result["status"], "pending": result["pending"], "new_model_fits": 0}))


if __name__ == "__main__":
    main()
