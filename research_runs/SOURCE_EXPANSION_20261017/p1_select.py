"""Source-only epoch selection and paired external evaluation for Paper 1 v4.

Source curves contain one held-out-person metric row per seed and epoch. Fold
means are deliberately not an input: people are the observational unit. The
eight selectors are defined here; RACAC-NC is not part of this protocol.

Public APIs:
  select_epochs(curves, ...) -> epochs, curve_scores, diagnostics
  prediction_metrics(trial_rows) -> per-person/per-seed metric rows
  paired_statistics(metric_rows, ...) -> person means, summaries, comparisons

This module never trains, opens target data for selection, or selects an epoch
from target scores. Calling code must freeze the returned source choices before
producing external predictions. Dreyer evaluation remains exploratory because
its prior exposure is uncertain; prespecifying a contrast does not undo that.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from collections import defaultdict
from typing import Iterable, Mapping, Sequence

import numpy as np
from scipy.stats import rankdata, t as student_t


SELECTORS = (
    "fixed20", "mean_ce", "mean_ba", "mean_rank", "tail_ce", "tail_ba",
    "mean_min_recall", "tail_min_recall",
)
PIPELINES = ("BROAD", "MU_BETA_SHARED")
SOURCE_LEVELS = ("S9", "S29", "S60")
METRICS = ("ce", "ba", "min_recall")
DEFAULT_CONDITIONS = tuple(itertools.product(SOURCE_LEVELS, PIPELINES, SELECTORS))
DEFAULT_COMPARISONS = (
    {
        "name": "primary_source_expansion_min_recall",
        "family": "prespecified_primary",
        "metric": "min_recall",
        "left": ("S60", "BROAD", "tail_min_recall"),
        "right": ("S9", "BROAD", "tail_min_recall"),
    },
    {
        "name": "secondary_selector_min_recall",
        "family": "secondary_holm_3",
        "metric": "min_recall",
        "left": ("S60", "BROAD", "tail_min_recall"),
        "right": ("S60", "BROAD", "mean_ba"),
    },
    {
        "name": "secondary_larger_source_min_recall",
        "family": "secondary_holm_3",
        "metric": "min_recall",
        "left": ("S60", "BROAD", "tail_min_recall"),
        "right": ("S29", "BROAD", "tail_min_recall"),
    },
    {
        "name": "secondary_source_expansion_ba",
        "family": "secondary_holm_3",
        "metric": "ba",
        "left": ("S60", "BROAD", "tail_min_recall"),
        "right": ("S9", "BROAD", "tail_min_recall"),
    },
)


def _integer(value, field):
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer, not bool")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"invalid integer {field}: {value!r}") from error
    if str(value).strip() not in (str(result), f"{result}.0"):
        raise ValueError(f"nonintegral {field}: {value!r}")
    return result


def _identifier(row, field):
    value = row.get(field)
    if value is None or isinstance(value, bool) or not str(value).strip():
        raise ValueError(f"missing or empty {field}")
    return str(value)


def _metric_values(row):
    # The long spelling is canonical; support the short runner spelling too.
    value = row.get("min_recall", row.get("minrecall"))
    try:
        result = (float(row["ce"]), float(row["ba"]), float(value))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("metric row requires ce, ba, min_recall") from error
    ce, ba, minimum = result
    if not all(math.isfinite(x) for x in result):
        raise ValueError("nonfinite metric")
    if ce < 0 or not 0 <= ba <= 1 or not 0 <= minimum <= 1:
        raise ValueError("CE must be nonnegative; BA and min_recall must be fractions")
    if minimum > ba + 1e-10 or 2 * ba - minimum > 1 + 1e-10:
        raise ValueError("BA and min_recall are inconsistent with two class recalls")
    return result


def _check_seed_set(observed, expected):
    if isinstance(expected, int):
        if expected < 1 or len(observed) != expected:
            raise ValueError(f"expected {expected} seeds, found {sorted(observed)}")
    elif observed != {str(seed) for seed in expected}:
        raise ValueError("seed IDs differ from the expected seed set")


def _sha256_json(value):
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def weighted_tail(values, weights, *, lower, mass=1 / 3):
    """Mean of exactly ``mass`` of a weighted distribution's worst tail.

    A boundary person's weight is split if necessary. This is a weighted
    expected-shortfall definition, not ceil(n / 3) and not a percentile cutoff
    that might include a larger mass when there are ties.
    """
    values = np.asarray(values, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    if values.ndim != 1 or values.shape != weights.shape or not len(values):
        raise ValueError("tail requires equally sized nonempty vectors")
    if not np.isfinite(values).all() or not np.isfinite(weights).all():
        raise ValueError("tail requires finite values and weights")
    if np.any(weights <= 0) or not 0 < mass <= 1:
        raise ValueError("tail weights must be positive and mass in (0,1]")
    weights = weights / math.fsum(weights.tolist())
    order = np.argsort(values if lower else -values, kind="stable")
    remaining = float(mass)
    terms = []
    for index in order:
        take = min(remaining, float(weights[index]))
        terms.append(take * float(values[index]))
        remaining -= take
        if remaining <= 1e-15:
            break
    if remaining > 1e-12:
        raise ValueError("insufficient probability mass")
    return math.fsum(terms) / mass


def select_epochs(
    curves: Iterable[Mapping], *, expected_epochs=40, expected_seeds=3,
    expected_subjects=None, expected_folds=None, fixed_epoch=20,
    allowed_datasets: Sequence[str] | None = None, tail_mass=1 / 3,
    tie_atol=1e-12,
):
    """Select eight source epochs from a complete person x seed x epoch grid.

    Required row keys: dataset, subject, seed, epoch, ce, ba, min_recall.
    Optional fold, source_level, pipeline must be consistent when supplied.
    For mixed sources, datasets have equal mass and people within each dataset
    have equal mass. Three seed scores are averaged for each person *before*
    ranking, tail selection, and dataset aggregation.

    All optimizing rules break score ties by maximum mean BA then earliest
    epoch, except mean_rank, which uses earliest minimum directly. ``fixed20``
    uses fixed_epoch; an override exists solely for short synthetic smoke runs.
    """
    if isinstance(expected_epochs, int):
        epochs = list(range(1, expected_epochs + 1))
    else:
        epochs = sorted({_integer(e, "epoch") for e in expected_epochs})
    fixed_epoch = _integer(fixed_epoch, "fixed_epoch")
    if not epochs or epochs[0] < 1 or fixed_epoch not in epochs:
        raise ValueError("expected epochs must contain the positive fixed epoch")
    if not math.isfinite(tie_atol) or tie_atol < 0:
        raise ValueError("tie_atol must be finite and nonnegative")
    observations = {}
    subjects = set()
    seeds = set()
    conditions = defaultdict(set)
    fold_by_person = defaultdict(set)
    with_fold = 0
    normalized = []
    allowed = None if allowed_datasets is None else set(allowed_datasets)
    for original in curves:
        row = dict(original)
        dataset = _identifier(row, "dataset")
        person = (dataset, _identifier(row, "subject"))
        seed = _identifier(row, "seed")
        epoch = _integer(row.get("epoch"), "epoch")
        if dataset.lower().startswith("dreyer") or row.get("is_target") is True:
            raise ValueError("target data cannot enter source epoch selection")
        for field in ("role", "split", "scope"):
            marker = str(row.get(field, "")).lower()
            if "target" in marker or "external" in marker or marker == "test":
                raise ValueError("target/external rows cannot enter source selection")
        if allowed is not None and dataset not in allowed:
            raise ValueError(f"unregistered source dataset {dataset}")
        if epoch not in epochs:
            raise ValueError(f"unexpected source epoch {epoch}")
        key = (person, seed, epoch)
        if key in observations:
            raise ValueError(f"duplicate source metric row {key}")
        observations[key] = _metric_values(row)
        subjects.add(person)
        seeds.add(seed)
        item = {"dataset": dataset, "subject": person[1], "seed": seed,
                "epoch": epoch, **dict(zip(METRICS, observations[key]))}
        if "fold" in row:
            fold = _integer(row["fold"], "fold")
            if fold < 0:
                raise ValueError("fold must be nonnegative")
            fold_by_person[person].add(fold)
            item["fold"] = fold
            with_fold += 1
        for field in ("source_level", "pipeline"):
            if field in row:
                conditions[field].add(_identifier(row, field))
                item[field] = str(row[field])
        normalized.append(item)
    if not subjects:
        raise ValueError("no source curves")
    _check_seed_set(seeds, expected_seeds)
    if any(len(values) > 1 for values in conditions.values()):
        raise ValueError("select each source_level/pipeline separately")
    if any(len(values) != 1 for values in fold_by_person.values()):
        raise ValueError("a source person belongs to multiple validation folds")
    if with_fold and with_fold != len(observations):
        raise ValueError("fold metadata must be present on every source row")
    all_folds = set().union(*fold_by_person.values()) if with_fold else set()
    if expected_folds is not None and len(all_folds) != expected_folds:
        raise ValueError(f"expected {expected_folds} source folds")
    people = sorted(subjects)
    seed_order = sorted(seeds)
    counts = defaultdict(int)
    for dataset, _ in people:
        counts[dataset] += 1
    if isinstance(expected_subjects, int) and len(people) != expected_subjects:
        raise ValueError(f"expected {expected_subjects} source people, found {len(people)}")
    if isinstance(expected_subjects, Mapping) and dict(counts) != dict(expected_subjects):
        raise ValueError("source cohort sizes differ from expected_subjects")
    if expected_subjects is not None and not isinstance(expected_subjects, (int, Mapping)):
        expected_ids = list(expected_subjects)
        if expected_ids and isinstance(expected_ids[0], (tuple, list)):
            expected_people = {tuple(map(str, value)) for value in expected_ids}
            if len(expected_people) != len(expected_ids) or set(people) != expected_people:
                raise ValueError("source person identities differ from expected_subjects")
        else:
            expected_ids = [str(value) for value in expected_ids]
            actual_ids = [subject for _, subject in people]
            if (len(set(expected_ids)) != len(expected_ids) or len(set(actual_ids)) != len(actual_ids)
                    or set(actual_ids) != set(expected_ids)):
                raise ValueError("source person identities differ from expected_subjects")
    expected_rows = len(people) * len(seed_order) * len(epochs)
    if len(observations) != expected_rows:
        raise ValueError(f"incomplete source grid: {len(observations)}/{expected_rows} rows")
    grid = np.empty((len(people), len(seed_order), len(epochs), 3), dtype=np.float64)
    for pi, person in enumerate(people):
        for si, seed in enumerate(seed_order):
            for ei, epoch in enumerate(epochs):
                if (person, seed, epoch) not in observations:
                    raise ValueError(f"missing source metric: {person}, seed {seed}, epoch {epoch}")
                grid[pi, si, ei] = observations[(person, seed, epoch)]
    means = grid.mean(axis=1)
    weights = np.array([1 / (len(counts) * counts[d]) for d, _ in people])
    scores = {
        "mean_ce": weights @ means[:, :, 0],
        "mean_ba": weights @ means[:, :, 1],
        "mean_rank": weights @ np.vstack([rankdata(row, method="average")
                                          for row in means[:, :, 0]]),
        "mean_min_recall": weights @ means[:, :, 2],
    }
    for name, mi, lower in (("tail_ce", 0, False), ("tail_ba", 1, True),
                            ("tail_min_recall", 2, True)):
        scores[name] = np.array([weighted_tail(means[:, ei, mi], weights,
                                              lower=lower, mass=tail_mass)
                                 for ei in range(len(epochs))])
    selected = {"fixed20": fixed_epoch}
    for selector in SELECTORS[1:]:
        objective = scores[selector]
        best = objective.min() if selector in ("mean_ce", "mean_rank", "tail_ce") else objective.max()
        candidates = np.flatnonzero(np.isclose(objective, best, rtol=0, atol=tie_atol))
        if selector != "mean_rank" and len(candidates) > 1:
            ba = scores["mean_ba"][candidates]
            candidates = candidates[np.isclose(ba, ba.max(), rtol=0, atol=tie_atol)]
        selected[selector] = epochs[int(candidates[0])]
    curve_scores = [{"epoch": epoch, "fixed20_selected": epoch == fixed_epoch,
                     **{name: float(score[index]) for name, score in scores.items()}}
                    for index, epoch in enumerate(epochs)]
    normalized.sort(key=lambda r: (r["dataset"], r["subject"], r["seed"], r["epoch"]))
    return {
        "epochs": selected,
        "curve_scores": curve_scores,
        "diagnostics": {
            "protocol": "paper1_expansion_v4_eight_selectors",
            "selection_scope": "source_out_of_subject_only",
            "input_metric_rows_sha256": _sha256_json(normalized),
            "n_metric_rows": len(observations), "complete_grid": True,
            "n_subjects": len(people), "cohort_sizes": dict(sorted(counts.items())),
            "seeds": seed_order, "epochs": epochs, "n_folds": len(all_folds),
            "folds_are_replicates": False, "seed_aggregation": "mean_within_person_first",
            "person_weight": "1/(number_of_datasets * persons_in_own_dataset)",
            "tail_mass": tail_mass, "tail_boundary": "fractional_probability_weight",
            "tie_atol": tie_atol, "ties": "maximum_mean_ba_then_earliest",
            "mean_rank_ties": "earliest_minimum",
            "fixed_epoch": fixed_epoch, "synthetic_fixed_epoch_override": fixed_epoch != 20,
            "condition": {name: next(iter(values)) for name, values in conditions.items()},
        },
    }


def _condition(row):
    return tuple(_identifier(row, field) for field in ("source_level", "pipeline", "selector"))


def _condition_fields(condition):
    return dict(zip(("source_level", "pipeline", "selector"), condition))


def prediction_metrics(predictions: Iterable[Mapping]):
    """Aggregate trial predictions while checking identities and paired coverage.

    Rows require source_level, pipeline, selector, seed, dataset, subject,
    trial_id, y_true and either logit_left/logit_right (preferred) or p_right.
    If probability-only rows contain exactly zero/one, CE clips the true-class
    probability at 1e-15. Logits avoid this representational clipping entirely.
    The prediction tie rule is class 0, matching torch.argmax for equal logits.
    """
    groups = {}
    labels = {}
    for original in predictions:
        row = dict(original)
        condition = _condition(row)
        seed = _identifier(row, "seed")
        person = (_identifier(row, "dataset"), _identifier(row, "subject"))
        trial = _identifier(row, "trial_id")
        y = _integer(row.get("y_true"), "y_true")
        if y not in (0, 1):
            raise ValueError("binary labels must be 0=left, 1=right")
        label_key = (person, trial)
        if label_key in labels and labels[label_key] != y:
            raise ValueError("target labels differ across conditions/seeds")
        labels[label_key] = y
        key = (condition, seed, person)
        group = groups.setdefault(key, {"trials": {}, "ce": [], "confusion": np.zeros((2, 2), dtype=int)})
        if trial in group["trials"]:
            raise ValueError("duplicate trial prediction within a condition/seed/person")
        group["trials"][trial] = y
        if "logit_left" in row or "logit_right" in row:
            try:
                logits = np.array([float(row["logit_left"]), float(row["logit_right"])])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("both logits are required") from error
            if not np.isfinite(logits).all():
                raise ValueError("nonfinite prediction logits")
            # Subtract first: logsumexp(logits)-logits[y] loses log(2)
            # if two equal logits have a very large common offset.
            loss = float(np.logaddexp(0.0, logits[1 - y] - logits[y]))
            if not math.isfinite(loss):
                raise ValueError("nonfinite cross entropy from prediction logits")
            predicted = int(logits[1] > logits[0])
            if "p_right" in row:
                expected = math.exp(-float(np.logaddexp(0.0, logits[0] - logits[1])))
                if not math.isclose(float(row["p_right"]), expected, rel_tol=0, abs_tol=1e-6):
                    raise ValueError("saved probability disagrees with logits")
        else:
            try:
                right = float(row["p_right"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("predictions need paired logits or p_right") from error
            if not math.isfinite(right) or not 0 <= right <= 1:
                raise ValueError("p_right must be a probability")
            if "p_left" in row and not math.isclose(float(row["p_left"]) + right, 1,
                                                   rel_tol=0, abs_tol=1e-6):
                raise ValueError("left/right probabilities do not sum to one")
            loss = -math.log(max(right if y else 1 - right, 1e-15))
            predicted = int(right > 0.5)
        group["ce"].append(loss)
        group["confusion"][y, predicted] += 1
    if not groups:
        raise ValueError("no prediction rows")
    reference_hashes = {}
    result = []
    for (condition, seed, person), group in sorted(groups.items()):
        confusion = group["confusion"]
        counts = confusion.sum(axis=1)
        if not np.all(counts > 0):
            raise ValueError("every target person/seed/condition needs both true classes")
        fingerprint = _sha256_json(sorted(group["trials"].items()))
        previous = reference_hashes.setdefault(person, fingerprint)
        if fingerprint != previous:
            raise ValueError("target trial coverage differs across conditions/seeds")
        recall = confusion.diagonal() / counts
        result.append({
            **_condition_fields(condition), "seed": seed,
            "dataset": person[0], "subject": person[1],
            "ce": math.fsum(group["ce"]) / len(group["ce"]),
            "ba": float(recall.mean()), "min_recall": float(recall.min()),
            "recall_left": float(recall[0]), "recall_right": float(recall[1]),
            "n_trials": int(counts.sum()), "n_left": int(counts[0]), "n_right": int(counts[1]),
            "trial_manifest_sha256": fingerprint,
        })
    return result


def holm_adjust(pvalues):
    """Holm step-down family-wise correction, preserving input order."""
    values = np.asarray(pvalues, dtype=np.float64)
    if values.ndim != 1 or not np.isfinite(values).all() or np.any((values < 0) | (values > 1)):
        raise ValueError("p values must be finite probabilities")
    order = np.argsort(values, kind="stable")
    adjusted = np.empty_like(values)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (len(values) - rank) * float(values[index])))
        adjusted[index] = running
    return adjusted.tolist()


def _mean_summary(values, bootstrap_indices):
    n = len(values)
    mean = float(np.mean(values))
    sd = float(np.std(values, ddof=1))
    se = sd / math.sqrt(n)
    half = float(student_t.ppf(0.975, n - 1)) * se
    boot = values[bootstrap_indices].mean(axis=1)
    lo, hi = np.quantile(boot, [0.025, 0.975], method="linear")
    return {"n_subjects": n, "mean": mean, "sd": sd, "se": se,
            "t_ci95_low": mean - half, "t_ci95_high": mean + half,
            "bootstrap_ci95_low": float(lo), "bootstrap_ci95_high": float(hi)}


def paired_statistics(
    metric_rows: Iterable[Mapping], *, expected_subjects=85, expected_seeds=3,
    expected_conditions=DEFAULT_CONDITIONS, comparisons=DEFAULT_COMPARISONS,
    n_bootstrap=10000, bootstrap_seed=20261017,
):
    """Paired person-level external statistics after averaging seeds per person.

    Input rows are produced by prediction_metrics. Directly computed rows must
    provide the same three metrics and trial_manifest_sha256. Every expected
    condition must contain exactly the same people, seeds, and each person's
    trial manifest. No intersection/drop-missing operation is permitted.

    The primary contrast and the three secondary Holm contrasts are fixed above.
    Both t and percentile bootstrap confidence intervals are pointwise 95%.
    Resampling units are people; the three seeds and the five CV folds never
    become additional independent replicates. All labels remain exploratory.
    """
    observations = {}
    people = set()
    seeds = set()
    actual_conditions = set()
    fingerprints = {}
    for original in metric_rows:
        row = dict(original)
        condition = _condition(row)
        person = (_identifier(row, "dataset"), _identifier(row, "subject"))
        seed = _identifier(row, "seed")
        key = (condition, person, seed)
        if key in observations:
            raise ValueError("duplicate target person/seed/condition metrics")
        observations[key] = _metric_values(row)
        fingerprint = _identifier(row, "trial_manifest_sha256")
        if len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
            raise ValueError("trial_manifest_sha256 must be a lowercase SHA256")
        if fingerprints.setdefault(person, fingerprint) != fingerprint:
            raise ValueError("target trials differ across paired conditions/seeds")
        people.add(person)
        seeds.add(seed)
        actual_conditions.add(condition)
    if len(people) != expected_subjects or len(people) < 2:
        raise ValueError(f"expected {expected_subjects} target people, found {len(people)}")
    if len({d for d, _ in people}) != 1:
        raise ValueError("this external statistical plan requires a single target cohort")
    _check_seed_set(seeds, expected_seeds)
    required_conditions = {tuple(c) for c in expected_conditions}
    if actual_conditions != required_conditions:
        missing = sorted(required_conditions - actual_conditions)
        extra = sorted(actual_conditions - required_conditions)
        raise ValueError(f"target conditions incomplete/different; missing={missing[:5]}, extra={extra[:5]}")
    ordered_people = sorted(people)
    ordered_seeds = sorted(seeds)
    grid = {}
    subject_means = []
    for condition in sorted(required_conditions):
        array = np.empty((len(ordered_people), len(ordered_seeds), 3), dtype=np.float64)
        for pi, person in enumerate(ordered_people):
            for si, seed in enumerate(ordered_seeds):
                key = (condition, person, seed)
                if key not in observations:
                    raise ValueError(f"missing paired target cell {key}")
                array[pi, si] = observations[key]
        means = array.mean(axis=1)
        grid[condition] = means
        for person, values in zip(ordered_people, means):
            subject_means.append({**_condition_fields(condition), "dataset": person[0],
                                  "subject": person[1], **dict(zip(METRICS, map(float, values))),
                                  "n_seeds": len(ordered_seeds),
                                  "trial_manifest_sha256": fingerprints[person]})
    n_bootstrap = _integer(n_bootstrap, "n_bootstrap")
    if n_bootstrap < 100:
        raise ValueError("at least 100 bootstrap replicates are required")
    rng = np.random.default_rng(bootstrap_seed)
    bootstrap_indices = rng.integers(0, len(people), size=(n_bootstrap, len(people)))
    summaries = []
    for condition, means in sorted(grid.items()):
        for mi, metric in enumerate(METRICS):
            summaries.append({**_condition_fields(condition), "metric": metric,
                              "analysis_status": "descriptive_exploratory_external",
                              **_mean_summary(means[:, mi], bootstrap_indices)})
    contrast_rows = []
    contrast_subjects = []
    names = set()
    for definition in comparisons:
        name = str(definition["name"])
        if name in names:
            raise ValueError("comparison names must be unique")
        names.add(name)
        left, right = tuple(definition["left"]), tuple(definition["right"])
        metric = definition["metric"]
        if metric not in METRICS or left not in grid or right not in grid:
            raise ValueError(f"comparison {name} requests an unavailable metric/condition")
        mi = METRICS.index(metric)
        difference = grid[left][:, mi] - grid[right][:, mi]
        summary = _mean_summary(difference, bootstrap_indices)
        if summary["se"] == 0:
            t_value = 0.0 if summary["mean"] == 0 else None
            p_value = 1.0 if summary["mean"] == 0 else 0.0
            t_kind = "finite" if summary["mean"] == 0 else "infinite_constant_difference"
        else:
            t_value = summary["mean"] / summary["se"]
            p_value = float(2 * student_t.sf(abs(t_value), len(people) - 1))
            t_kind = "finite"
        row = {"name": name, "family": str(definition["family"]), "metric": metric,
               "left": list(left), "right": list(right), "direction": "left_minus_right",
               "analysis_status": "prespecified_contrast_exploratory_external",
               **summary, "t_statistic": t_value, "t_statistic_kind": t_kind,
               "degrees_of_freedom": len(people) - 1, "p_two_sided": p_value,
               "p_holm": None, "ci_multiplicity": "pointwise_unadjusted_95_percent"}
        if metric in ("ba", "min_recall"):
            row.update({"mean_difference_percentage_points": summary["mean"] * 100,
                        "t_ci95_low_percentage_points": summary["t_ci95_low"] * 100,
                        "t_ci95_high_percentage_points": summary["t_ci95_high"] * 100,
                        "bootstrap_ci95_low_percentage_points": summary["bootstrap_ci95_low"] * 100,
                        "bootstrap_ci95_high_percentage_points": summary["bootstrap_ci95_high"] * 100})
        contrast_rows.append(row)
        for person, value in zip(ordered_people, difference):
            contrast_subjects.append({"comparison": name, "dataset": person[0],
                                      "subject": person[1], "metric": metric,
                                      "difference": float(value)})
    secondary = [row for row in contrast_rows if row["family"] == "secondary_holm_3"]
    if secondary and len(secondary) != 3:
        raise ValueError("secondary_holm_3 must contain exactly three prespecified contrasts")
    for row, adjusted in zip(secondary, holm_adjust([row["p_two_sided"] for row in secondary])):
        row["p_holm"] = adjusted
    return {
        "study_status": "exploratory_external",
        "per_subject_metrics": subject_means,
        "condition_summaries": summaries,
        "comparisons": contrast_rows,
        "paired_subject_differences": contrast_subjects,
        "diagnostics": {
            "n_subjects": len(people), "n_seeds": len(seeds), "seeds": ordered_seeds,
            "n_conditions": len(required_conditions), "n_metric_rows": len(observations),
            "complete_paired_grid": True, "trial_manifests_identical_per_person": True,
            "unit_of_analysis": "target_person_after_mean_of_seed_metrics",
            "min_recall_order": "minimum_per_seed_then_average_seeds",
            "cv_folds_are_replicates": False, "seeds_are_replicates": False,
            "bootstrap": "paired_person_percentile", "bootstrap_replicates": n_bootstrap,
            "bootstrap_seed": bootstrap_seed, "confidence": 0.95,
            "subject_metric_rows_sha256": _sha256_json(subject_means),
            "primary": "prespecified but exploratory external; no confirmatory claim",
            "secondary": "three two-sided paired t-test p-values adjusted with Holm",
        },
    }
