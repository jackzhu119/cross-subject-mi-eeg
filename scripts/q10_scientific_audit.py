"""Independent, CPU-only audit of frozen Q5--Q9 prediction artifacts.

This script never imports training code, loads EEG, or changes Q5--Q9 files.
Its unit of inference is the held-out *subject*, not a seed or a trial. The
output is descriptive/exploratory evidence, not external confirmation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import random
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (20260924, 20260925, 20260926)
SUBJECTS = tuple(range(1, 10))
CLASSES = (1, 2, 3, 4)
Q9_NEURAL = {
    "Q9-E001/BETA_13_30": "results/Q9-E001/BETA_13_30",
    "Q9-E001/MID_8_30": "results/Q9-E001/MID_8_30",
    "Q9-E001/MU_8_13": "results/Q9-E001/MU_8_13",
    "Q9-E001/MU_BETA_SHARED": "results/Q9-E001/MU_BETA_SHARED",
    "Q9-E002/MID_8_30_Q8_EPOCHS": "results/Q9-E002/MID_8_30_Q8_EPOCHS",
    "Q9-E002/MU_BETA_SHARED_Q8_EPOCHS": "results/Q9-E002/MU_BETA_SHARED_Q8_EPOCHS",
    "Q9-E004/MU_BETA_SHARED_SOURCE_CLEAN": "results/Q9-E004/MU_BETA_SHARED_SOURCE_CLEAN",
    "Q9-E005/MU_BETA_SHARED_SOURCE_NORM": "results/Q9-E005/MU_BETA_SHARED_SOURCE_NORM",
}
BASE_CONDITIONS = {
    "Q5-E001": "results/Q5-E001",
    "Q6-E001": "research_runs/Q6-E001/results",
    "Q7-E001/B": "research_runs/Q7-E001/results",
    "Q7-E001/C": "research_runs/Q7-E001/results",
    "Q8-E001": "research_runs/Q8-E001/results",
}
PRIMARY = "Q9-E001/MU_BETA_SHARED"
REFERENCE = "Q8-E001"


@dataclass(frozen=True)
class Prediction:
    sample_id: str
    subject: int
    seed: str
    session: str
    flagged: bool
    y_true: int
    y_pred: int


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def mean_or_none(values: Iterable[float]) -> float | None:
    values = list(values)
    return statistics.mean(values) if values else None


def metric(rows: Iterable[Prediction]) -> dict:
    """Four-class confusion and observed-class BA; absent classes stay null."""
    rows = list(rows)
    confusion = [[0] * 4 for _ in CLASSES]
    for row in rows:
        confusion[row.y_true - 1][row.y_pred - 1] += 1
    support = [sum(line) for line in confusion]
    predicted = [sum(confusion[i][j] for i in range(4)) for j in range(4)]
    recalls = [confusion[i][i] / support[i] if support[i] else None for i in range(4)]
    n = len(rows)
    f1 = []
    for i in range(4):
        precision = confusion[i][i] / predicted[i] if predicted[i] else 0.0
        recall = recalls[i] or 0.0
        f1.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    accuracy = sum(confusion[i][i] for i in range(4)) / n if n else None
    expected_agreement = sum(s * p for s, p in zip(support, predicted)) / (n * n) if n else None
    return {
        "n_trials": n,
        "class_support": support,
        "predicted_counts": predicted,
        "confusion": confusion,
        "accuracy": accuracy,
        "macro_f1": statistics.mean(f1) if n else None,
        "cohen_kappa": ((accuracy - expected_agreement) / (1 - expected_agreement)
                        if n and expected_agreement < 1 else None),
        "balanced_accuracy_observed_classes": mean_or_none(v for v in recalls if v is not None),
        "n_classes_present": sum(bool(v) for v in support),
        "class_recall": recalls,
        "zero_recall_classes": [i + 1 for i, (count, value) in enumerate(zip(support, recalls))
                                if count and value == 0.0],
        "dominant_prediction_share": max(predicted) / n if n else None,
        "prediction_entropy_bits": -sum((v / n) * math.log2(v / n) for v in predicted if v) if n else None,
    }


def exact_sign_flip_p(differences: list[float]) -> float:
    """Two-sided, nonzero-tie-retaining exhaustive sign-flip sensitivity."""
    if not differences:
        raise ValueError("At least one paired subject is required")
    observed = abs(statistics.mean(differences))
    count = sum(
        abs(sum(sign * delta for sign, delta in zip(signs, differences)) / len(differences))
        >= observed - 1e-12
        for signs in itertools.product((-1, 1), repeat=len(differences))
    )
    return count / (2 ** len(differences))


def bootstrap_mean_ci(differences: list[float], *, replicates: int = 20000,
                      seed: int = 20260924) -> tuple[float, float]:
    """Deterministic percentile CI, resampling subjects (never seeds/trials)."""
    if not differences or replicates < 100:
        raise ValueError("Need paired subjects and at least 100 replicates")
    rng = random.Random(seed)
    n = len(differences)
    draws = sorted(sum(differences[rng.randrange(n)] for _ in range(n)) / n
                   for _ in range(replicates))
    return draws[int(.025 * replicates)], draws[min(replicates - 1, int(.975 * replicates))]


def mean_rank_epoch(curves: dict[int, list[float]]) -> int:
    """Earliest epoch with minimal equal-inner-fold mean CE rank, as Q8/Q9."""
    if set(curves) != {1, 2, 3, 4} or any(len(v) != 40 for v in curves.values()):
        raise ValueError("Exactly four complete 40-epoch inner curves are required")
    ranks = []
    for values in curves.values():
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Nonfinite validation cross-entropy")
        ranks.append([1 + sum(x < y for x in values) + .5 * (sum(x == y for x in values) - 1)
                      for y in values])
    means = [statistics.mean(rank[i] for rank in ranks) for i in range(40)]
    return means.index(min(means)) + 1


def source_manifest(path: Path) -> dict[str, tuple[int, str]]:
    value = read_json(path)
    files = value.get("files", value) if isinstance(value, dict) else value
    result = {}
    for item in files:
        name = Path(item.get("name", item.get("path", ""))).name
        result[name] = int(item["bytes"]), str(item["sha256"])
    if len(result) != len(files):
        raise ValueError(f"Duplicate source MAT basename in {path}")
    return result


def load_predictions(path: Path, condition: str, *, required_probability: bool,
                     selector: str | None = None) -> tuple[list[Prediction], list[str]]:
    """Load one aggregate prediction source and independently check row semantics."""
    rows = read_csv(path)
    problems = []
    required = {"sample_id", "subject", "session", "artifact_flagged", "y_true", "y_pred"}
    if rows and not required.issubset(rows[0]):
        raise ValueError(f"Missing required columns in {path}: {sorted(required - set(rows[0]))}")
    result = []
    keys = set()
    for line_number, row in enumerate(rows, start=2):
        if selector is not None and row.get("condition", row.get("model")) != selector:
            continue
        subject, truth, predicted = (int(row[field]) for field in ("subject", "y_true", "y_pred"))
        seed = row.get("seed", "")
        key = subject, seed, row["sample_id"]
        if key in keys:
            problems.append(f"duplicate prediction identity at {path}:{line_number}")
        keys.add(key)
        if subject not in SUBJECTS or truth not in CLASSES or predicted not in CLASSES:
            problems.append(f"out-of-range subject or class at {path}:{line_number}")
        if row.get("label") and int(row["label"]) != truth:
            problems.append(f"label/y_true mismatch at {path}:{line_number}")
        if row.get("fold") and row["fold"] != f"loso_s{subject}":
            problems.append(f"fold/subject mismatch at {path}:{line_number}")
        if required_probability:
            try:
                probabilities = [float(row[f"p_class_{c}"]) for c in CLASSES]
                if (not all(math.isfinite(p) and -1e-6 <= p <= 1 + 1e-6 for p in probabilities)
                    or abs(sum(probabilities) - 1) > 1e-4
                    or probabilities.index(max(probabilities)) + 1 != predicted):
                    problems.append(f"invalid probability or argmax at {path}:{line_number}")
            except (KeyError, TypeError, ValueError):
                problems.append(f"missing or invalid probability at {path}:{line_number}")
        result.append(Prediction(row["sample_id"], subject, seed, row["session"],
                                 row["artifact_flagged"].lower() == "true", truth, predicted))
    if not result:
        problems.append(f"no selected rows in {path} for {condition}")
    return result, problems


def grouped_metrics(condition: str, rows: list[Prediction]) -> tuple[list[dict], list[dict], list[dict]]:
    groups = defaultdict(list)
    for row in rows:
        groups[row.subject, row.seed].append(row)
    fold_rows, confusion_rows, strata_rows = [], [], []
    for (subject, seed), group in sorted(groups.items()):
        whole = metric(group)
        fold_rows.append({"condition": condition, "subject": subject, "seed": seed,
                          "balanced_accuracy": whole["balanced_accuracy_observed_classes"],
                          "accuracy": whole["accuracy"], "macro_f1": whole["macro_f1"],
                          "cohen_kappa": whole["cohen_kappa"], "n_trials": whole["n_trials"],
                          "n_classes_present": whole["n_classes_present"],
                          "zero_recall_count": len(whole["zero_recall_classes"]),
                          "zero_recall_classes": ";".join(map(str, whole["zero_recall_classes"])),
                          "dominant_prediction_share": whole["dominant_prediction_share"],
                          "prediction_entropy_bits": whole["prediction_entropy_bits"],
                          **{f"recall_class_{c}": whole["class_recall"][c - 1] for c in CLASSES},
                          **{f"support_class_{c}": whole["class_support"][c - 1] for c in CLASSES}})
        for truth in CLASSES:
            for predicted in CLASSES:
                confusion_rows.append({"condition": condition, "subject": subject, "seed": seed,
                                       "true_class": truth, "predicted_class": predicted,
                                       "n_trials": whole["confusion"][truth - 1][predicted - 1]})
        strata = {("session", session) for session in {r.session for r in group}}
        strata |= {("artifact", str(flag)) for flag in (False, True)}
        for dimension, value in sorted(strata):
            subset = ([r for r in group if r.session == value] if dimension == "session"
                      else [r for r in group if str(r.flagged) == value])
            part = metric(subset)
            strata_rows.append({"condition": condition, "subject": subject, "seed": seed,
                                "dimension": dimension, "stratum": value,
                                "n_trials": part["n_trials"],
                                "n_classes_present": part["n_classes_present"],
                                "balanced_accuracy_observed_classes": part["balanced_accuracy_observed_classes"],
                                "accuracy": part["accuracy"],
                                **{f"recall_class_{c}": part["class_recall"][c - 1] for c in CLASSES}})
    return fold_rows, confusion_rows, strata_rows


def check_reported_ba(path: Path, condition: str, recomputed: list[dict]) -> list[str]:
    if not path.is_file():
        return [f"missing reported metric file: {path}"]
    reported = {}
    for row in read_csv(path):
        if row.get("stratum") != "all":
            continue
        if row.get("condition") and condition.split("/")[-1] != row["condition"]:
            continue
        if condition.startswith(("Q4", "Q9-A")) and row.get("model") != condition.split("/")[-1]:
            continue
        reported[int(row["subject"]), row.get("seed", "")] = row
    expected = {(r["subject"], r["seed"]): r for r in recomputed}
    if set(expected) != set(reported):
        return [f"reported/recomputed fold grid differs: {condition}"]
    problems = []
    for (subject, seed), actual in expected.items():
        row = reported[subject, seed]
        for key in ("balanced_accuracy", "accuracy", "macro_f1", "cohen_kappa"):
            if key in row and row[key] and actual[key] is not None and abs(actual[key] - float(row[key])) > 1e-10:
                problems.append(f"reported {key} differs: {condition} S{subject} seed {seed}")
    return problems


def verify_selection(repo: Path, condition: str, directory: Path, *, fixed_q8: dict[int, int] | None = None) -> tuple[list[dict], list[str]]:
    """Read inner CE directly; inspect final source lists and frozen epochs."""
    findings, problems = [], []
    if fixed_q8 is None:
        selection_path = directory / "selection.csv"
        selected = {int(r["subject"]): int(r["selected_epochs"]) for r in read_csv(selection_path)}
        if set(selected) != set(SUBJECTS):
            problems.append(f"selection does not cover nine targets: {condition}")
            return findings, problems
    else:
        selected = fixed_q8
    for target in SUBJECTS:
        recomputed = None
        if fixed_q8 is None:
            curves = {}
            for inner in range(1, 5):
                fit = directory / "inner" / f"loso_s{target}" / f"inner_{inner}"
                values = read_csv(fit / "learning_curve.csv")
                if [int(r["epoch"]) for r in values] != list(range(1, 41)):
                    problems.append(f"incomplete inner curve: {condition} S{target} inner {inner}")
                    continue
                curves[inner] = [float(r["val_ce"]) for r in values]
                status = read_json(fit / "status.json")
                source, validation = status["train_subjects"], status["validation_subjects"]
                if (target in source + validation or len(source) != 6 or len(validation) != 2
                    or set(source) & set(validation) or set(source + validation) != set(SUBJECTS) - {target}):
                    problems.append(f"invalid source-only inner partition: {condition} S{target} inner {inner}")
            if len(curves) == 4:
                recomputed = mean_rank_epoch(curves)
                if selected[target] != recomputed:
                    problems.append(f"mean-rank epoch mismatch: {condition} S{target}")
        for seed in SEEDS:
            status = read_json(directory / "final" / f"loso_s{target}" / f"seed_{seed}" / "status.json")
            if (status["target_subject"] != target or status["test_subjects"] != [target]
                or status["train_subjects"] != [s for s in SUBJECTS if s != target]
                or int(status["selected_epochs"]) != selected[target]):
                problems.append(f"invalid final source list or selected epoch: {condition} S{target} seed {seed}")
        findings.append({"condition": condition, "subject": target,
                         "selected_epochs": selected[target],
                         "recomputed_mean_rank_epoch": recomputed,
                         "source_only_status_lists_valid": not any(f"{condition} S{target}" in e for e in problems)})
    return findings, problems


def paired_contrast(name: str, against: str, fold_lookup: dict[tuple[str, int, str], float]) -> tuple[dict, list[dict]]:
    deltas, subject_rows = [], []
    for subject in SUBJECTS:
        seed_deltas = [fold_lookup[name, subject, str(seed)] - fold_lookup[against, subject, str(seed)]
                       for seed in SEEDS]
        delta = statistics.mean(seed_deltas)
        deltas.append(delta)
        subject_rows.append({"contrast": f"{name} minus {against}", "subject": subject,
                             "mean_seed_paired_delta_ba": delta,
                             **{f"delta_seed_{seed}": value for seed, value in zip(SEEDS, seed_deltas)}})
    lo, hi = bootstrap_mean_ci(deltas)
    return {
        "contrast": f"{name} minus {against}", "n_subjects": 9,
        "mean_subject_paired_delta_ba": statistics.mean(deltas),
        "median_subject_paired_delta_ba": statistics.median(deltas),
        "subject_bootstrap_95ci_low": lo, "subject_bootstrap_95ci_high": hi,
        "exact_two_sided_sign_flip_p": exact_sign_flip_p(deltas),
        "mean_excluding_s3_s8": statistics.mean(v for s, v in enumerate(deltas, 1) if s not in (3, 8)),
        "mean_excluding_s3_s9": statistics.mean(v for s, v in enumerate(deltas, 1) if s not in (3, 9)),
        "status": "exploratory_same_dataset_not_confirmatory",
    }, subject_rows


def git_pretraining_evidence(repo: Path, head: str) -> dict:
    """Check repository tree, not mutable working-tree timestamps."""
    try:
        run = subprocess.run(["git", "ls-tree", "-r", "--name-only", head], cwd=repo,
                             check=True, capture_output=True, text=True)
        names = set(run.stdout.splitlines())
        return {"runtime_git_head": head,
                "q9_protocol_in_runtime_commit": "research_runs/Q9-E001/PROTOCOL.md" in names,
                "q9_matrix_in_runtime_commit": "research_runs/Q9-E001/Q9_BATCH_MATRIX.json" in names,
                "q9_runner_in_runtime_commit": "scripts/q9_neural.py" in names}
    except (OSError, subprocess.CalledProcessError):
        return {"runtime_git_head": head, "git_tree_check": "unavailable"}


def run(repo: Path, output: Path) -> dict:
    repo, output = repo.resolve(), output.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    sources: list[dict] = []
    predictions: dict[str, list[Prediction]] = {}
    fold_metrics: list[dict] = []
    confusion: list[dict] = []
    strata: list[dict] = []
    specification = {**BASE_CONDITIONS, **Q9_NEURAL,
                     "Q9-A001/PSD44_LDA": "results/Q9-A001",
                     "Q9-A001/PSD44_LINEAR_SVM": "results/Q9-A001"}
    specification.update({f"Q4-E001/{model}": "outputs/Q4-E001" for model in
                          ("BroadCSP_LDA", "BroadCSP_SVM", "FBCSP_LDA", "FBCSP_MI8_LDA")})
    for condition, directory in specification.items():
        source = repo / directory / "predictions.csv"
        if not source.is_file():
            errors.append(f"missing aggregate predictions: {source.relative_to(repo)}")
            continue
        selector = (condition.split("/")[-1] if condition.startswith(("Q7", "Q9-A", "Q4")) else None)
        rows, problems = load_predictions(source, condition,
                                          required_probability=condition.startswith(("Q5", "Q6", "Q7", "Q8", "Q9-E")),
                                          selector=selector)
        errors.extend(problems)
        predictions[condition] = rows
        sources.append({"condition": condition, "path": str(source.relative_to(repo)).replace("\\", "/"),
                        "sha256": sha256(source), "n_rows": len(rows)})
        folded, conf, stratified = grouped_metrics(condition, rows)
        fold_metrics.extend(folded)
        confusion.extend(conf)
        strata.extend(stratified)
        expected_subjects = {3} if condition.startswith("Q7") else set(SUBJECTS)
        observed_subjects = {row["subject"] for row in folded}
        if observed_subjects != expected_subjects:
            errors.append(f"incomplete subject grid: {condition}: {sorted(observed_subjects)}")
        expected_seeds = {str(v) for v in SEEDS} if condition.startswith(("Q5", "Q6", "Q7", "Q8", "Q9-E")) else {""}
        if any({row["seed"] for row in folded if row["subject"] == s} != expected_seeds for s in expected_subjects):
            errors.append(f"incomplete seed grid: {condition}")
        if any(row["n_trials"] != 576 or any(row[f"support_class_{c}"] != 144 for c in CLASSES)
               for row in folded):
            errors.append(f"nonstandard primary trial/class population: {condition}")
        reported = repo / directory / "per_subject_metrics.csv"
        errors.extend(check_reported_ba(reported, condition, folded))

    # Every neural condition must describe identical held-out trial identities.
    reference = {(r.subject, r.seed, r.sample_id): (r.y_true, r.session, r.flagged)
                 for r in predictions[REFERENCE]}
    for condition, rows in predictions.items():
        if condition.startswith(("Q4", "Q9-A")):
            identity = {(r.subject, r.sample_id): (r.y_true, r.session, r.flagged) for r in rows}
            expected = {(s, sample): values for (s, seed, sample), values in reference.items()
                        if seed == str(SEEDS[0])}
        else:
            identity = {(r.subject, r.seed, r.sample_id): (r.y_true, r.session, r.flagged) for r in rows}
            expected = reference if not condition.startswith("Q7") else {
                key: values for key, values in reference.items() if key[0] == 3}
        if identity != expected:
            errors.append(f"held-out sample identity/label/session/flag mismatch: {condition}")

    # Source manifests are path-independent: only MAT basenames, sizes, hashes.
    source_check = []
    canonical = source_manifest(repo / "results/Q5-E001/source_files.json")
    manifests = {"Q5-E001": "results/Q5-E001/source_files.json",
                 "Q6-E001": "research_runs/Q6-E001/results/source_files.json",
                 "Q8-E001": "research_runs/Q8-E001/results/source_files.json"}
    manifests.update({name: f"{directory}/source_files.json" for name, directory in Q9_NEURAL.items()})
    for condition, relative in manifests.items():
        actual = source_manifest(repo / relative)
        equal = actual == canonical and len(actual) == 18
        source_check.append({"condition": condition, "n_files": len(actual),
                             "same_bytes_and_sha256_as_Q5": equal})
        if not equal:
            errors.append(f"source MAT manifest differs from Q5: {condition}")
    psd_manifest = read_json(repo / "results/Q9-A001/config.json")["data_manifest"]["source_mat_files"]
    psd = {row["name"]: (int(row["bytes"]), row["sha256"]) for row in psd_manifest}
    equal = psd == canonical and len(psd) == 18
    source_check.append({"condition": "Q9-A001", "n_files": len(psd), "same_bytes_and_sha256_as_Q5": equal})
    if not equal:
        errors.append("source MAT manifest differs from Q5: Q9-A001")
    warnings.append("Q7-E001 contains only S3 new B/C fits; A/D reuse Q5/Q6 and Q7 is not a nine-subject estimate.")

    # Independently recompute selection from source-only curves where available.
    q8_epochs = {int(r["subject"]): int(r["selected_epochs"]) for r in
                 read_csv(repo / "research_runs/Q8-E001/results/predeclared_selection.csv")}
    selection_rows: list[dict] = []
    for condition, relative in Q9_NEURAL.items():
        fixed = q8_epochs if condition.startswith("Q9-E002") else None
        findings, problems = verify_selection(repo, condition, repo / relative, fixed_q8=fixed)
        selection_rows.extend(findings)
        errors.extend(problems)
    # Q8's mean-rank rule reuses Q5's four source-only inner CE curves.
    q5_curves: dict[int, dict[int, list[float]]] = defaultdict(dict)
    q5_grouped: dict[tuple[int, int], list[tuple[int, float]]] = defaultdict(list)
    for row in read_csv(repo / "results/Q5-E001/learning_curves.csv"):
        if row["stage"] == "inner":
            subject = int(row["fold"].removeprefix("loso_s"))
            q5_grouped[subject, int(float(row["inner_fold"]))].append((int(row["epoch"]), float(row["val_ce"])))
    for (subject, inner), values in q5_grouped.items():
        ordered = sorted(values)
        if [epoch for epoch, _ in ordered] != list(range(1, 41)):
            errors.append(f"Q5 source inner curve incomplete: S{subject} inner {inner}")
        q5_curves[subject][inner] = [value for _, value in ordered]
    for subject in SUBJECTS:
        selected = mean_rank_epoch(q5_curves[subject])
        if selected != q8_epochs[subject]:
            errors.append(f"Q8 predeclared mean-rank epoch mismatch against Q5 source curves: S{subject}")
        selection_rows.append({"condition": "Q8-E001/from_Q5_source_curves", "subject": subject,
                               "selected_epochs": q8_epochs[subject],
                               "recomputed_mean_rank_epoch": selected,
                               "source_only_status_lists_valid": selected == q8_epochs[subject]})

    lookup = {(r["condition"], r["subject"], r["seed"]): r["balanced_accuracy"] for r in fold_metrics}
    paired_rows, paired_subjects = [], []
    contrasts = [(name, REFERENCE) for name in Q9_NEURAL]
    contrasts += [("Q9-E001/MID_8_30", PRIMARY),
                  ("Q9-E002/MID_8_30_Q8_EPOCHS", "Q9-E001/MID_8_30"),
                  ("Q9-E002/MU_BETA_SHARED_Q8_EPOCHS", PRIMARY),
                  ("Q9-E004/MU_BETA_SHARED_SOURCE_CLEAN", PRIMARY),
                  ("Q9-E005/MU_BETA_SHARED_SOURCE_NORM", PRIMARY)]
    for name, against in contrasts:
        result, details = paired_contrast(name, against, lookup)
        paired_rows.append(result)
        paired_subjects.extend(details)

    summary, by_subject = [], []
    for condition in specification:
        cells = [r for r in fold_metrics if r["condition"] == condition]
        per_subject = defaultdict(list)
        for cell in cells:
            per_subject[cell["subject"]].append(cell["balanced_accuracy"])
        subject_means = [statistics.mean(per_subject[s]) for s in sorted(per_subject)]
        for subject, values in sorted(per_subject.items()):
            by_subject.append({"condition": condition, "subject": subject, "n_seeds": len(values),
                               "mean_seed_ba": statistics.mean(values),
                               "seed_ba_range": max(values) - min(values)})
        summary.append({"condition": condition, "n_subjects": len(per_subject),
                        "n_fits": len(cells), "mean_equal_subject_ba": statistics.mean(subject_means),
                        "subject_sd_ba": statistics.stdev(subject_means) if len(subject_means) > 1 else None,
                        "median_subject_ba": statistics.median(subject_means),
                        "n_zero_recall_fold_seeds": sum(r["zero_recall_count"] > 0 for r in cells),
                        "estimand": "nine_subject_exploratory_LOSO" if len(per_subject) == 9
                                    else "single_subject_descriptive_only"})

    batch = read_json(repo / "results/Q9-BATCH/validation_report.json")
    if batch.get("scientific_validation") != "not_performed_by_this_batch_validator":
        warnings.append("Q9 batch validator scope changed; inspect its claims before using it.")
    else:
        warnings.append("Q9 existing batch validation is orchestration-only, not independent scientific validation.")
    missing_q9 = list(batch.get("unselected_planned_conditions", []))
    if missing_q9:
        warnings.append("Q9 planned but unrun: " + ", ".join(missing_q9))
    environment = read_json(repo / "results/Q9-E001/MU_BETA_SHARED/environment.json")
    provenance = git_pretraining_evidence(repo, str(environment.get("git_head", "")))
    if provenance.get("q9_protocol_in_runtime_commit") is False:
        warnings.append("Q9 protocol/matrix/runner absent from recorded runtime Git commit; do not call it pre-run Git preregistration.")
    historical_failures = []
    log_root = repo / "results/Q9-BATCH/jobs"
    for path in sorted(log_root.glob("*/run.log")):
        content = path.read_text(encoding="utf-8", errors="replace")
        hits = sorted(set(re.findall(r"(?:ModuleNotFoundError|FileNotFoundError|RuntimeError|Traceback \(most recent call last\))[^\n]*", content)))
        if hits:
            historical_failures.append({"path": str(path.relative_to(repo)).replace("\\", "/"),
                                        "indicators": hits})
    if historical_failures:
        warnings.append("Historical Q9 launch failures are retained in logs; later success does not erase them.")
    warnings.extend([
        "All Q5-Q9 primary results use the same nine BNCI2014_001 subjects; no independent external confirmation.",
        "Nine subjects, not seeds or trials, are the paired inferential units; p-values are exploratory and multiple comparisons remain.",
        "Zero-phase filtering is acausal; artifact-flag exclusion is source-training sensitivity, not deployable artifact detection.",
        "Flagged/unflagged BA uses only classes present within the stratum and is not a replacement for the all-trial four-class primary metric.",
    ])
    report = {"audit_id": "Q10-V001", "scope": "frozen_Q5_to_Q9_prediction_level_independent_CPU_audit",
              "status": "passed_with_caveats" if not errors else "failed",
              "scientific_validation_scope": "prediction_metrics_identity_source_manifests_selection_status_lists_not_raw_EEG_or_checkpoint_replay",
              "n_prediction_sources": len(sources), "prediction_sources": sources,
              "source_manifest_checks": source_check, "selection_rows_checked": len(selection_rows),
              "q9_batch_status": batch.get("status"), "q9_unrun_planned_conditions": missing_q9,
              "q9_runtime_commit_evidence": provenance,
              "historical_failure_logs": historical_failures,
              "paired_primary_contrast": next(row for row in paired_rows if row["contrast"] == f"{PRIMARY} minus {REFERENCE}"),
              "errors": errors, "warnings": warnings}

    write_csv(output / "condition_summary.csv", summary,
              ["condition", "n_subjects", "n_fits", "mean_equal_subject_ba", "subject_sd_ba",
               "median_subject_ba", "n_zero_recall_fold_seeds", "estimand"])
    write_csv(output / "subject_summary.csv", by_subject,
              ["condition", "subject", "n_seeds", "mean_seed_ba", "seed_ba_range"])
    write_csv(output / "subject_seed_metrics.csv", fold_metrics,
              ["condition", "subject", "seed", "balanced_accuracy", "accuracy", "macro_f1", "cohen_kappa", "n_trials",
               "n_classes_present", "zero_recall_count", "zero_recall_classes",
               "dominant_prediction_share", "prediction_entropy_bits",
               *[f"recall_class_{c}" for c in CLASSES], *[f"support_class_{c}" for c in CLASSES]])
    write_csv(output / "confusion_matrices.csv", confusion,
              ["condition", "subject", "seed", "true_class", "predicted_class", "n_trials"])
    write_csv(output / "strata_metrics.csv", strata,
              ["condition", "subject", "seed", "dimension", "stratum", "n_trials",
               "n_classes_present", "balanced_accuracy_observed_classes", "accuracy",
               *[f"recall_class_{c}" for c in CLASSES]])
    write_csv(output / "paired_contrasts.csv", paired_rows,
              ["contrast", "n_subjects", "mean_subject_paired_delta_ba", "median_subject_paired_delta_ba",
               "subject_bootstrap_95ci_low", "subject_bootstrap_95ci_high", "exact_two_sided_sign_flip_p",
               "mean_excluding_s3_s8", "mean_excluding_s3_s9", "status"])
    write_csv(output / "paired_subject_deltas.csv", paired_subjects,
              ["contrast", "subject", "mean_seed_paired_delta_ba", *[f"delta_seed_{seed}" for seed in SEEDS]])
    write_csv(output / "selection_checks.csv", selection_rows,
              ["condition", "subject", "selected_epochs", "recomputed_mean_rank_epoch", "source_only_status_lists_valid"])
    write_csv(output / "source_manifest_checks.csv", source_check,
              ["condition", "n_files", "same_bytes_and_sha256_as_Q5"])
    write_json(output / "audit_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = (args.output or repo / "results/Q10-V001").resolve()
    report = run(repo, output)
    print(json.dumps({key: report[key] for key in ("status", "n_prediction_sources", "selection_rows_checked",
                                                    "q9_unrun_planned_conditions", "errors")},
                     ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed_with_caveats" else 1


if __name__ == "__main__":
    raise SystemExit(main())
