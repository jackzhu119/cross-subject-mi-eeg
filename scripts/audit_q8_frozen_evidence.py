"""Read-only, standard-library audit of frozen Q5/Q8 predictions.

This script never trains a model or writes into Q5-E001 or Q8-E001. Its
output is deliberately compact: the subject, not the seed or trial, is the
unit used for cross-subject summaries.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_predictions(path: Path) -> dict[tuple[int, int, str], tuple]:
    rows: dict[tuple[int, int, str], tuple] = {}
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            subject = int(row["subject"])
            seed = int(row["seed"])
            key = (subject, seed, row["sample_id"])
            if key in rows:
                raise ValueError(f"Duplicate prediction key in {path}: {key}")
            if row["fold"] != f"loso_s{subject}":
                raise ValueError(f"Incorrect LOSO fold for {key}")
            truth, prediction = int(row["y_true"]), int(row["y_pred"])
            if truth != int(row["label"]) or truth not in (1, 2, 3, 4):
                raise ValueError(f"Invalid true label for {key}")
            if prediction not in (1, 2, 3, 4):
                raise ValueError(f"Invalid predicted label for {key}")
            trial_identity = tuple(
                row[column]
                for column in ("session", "run", "trial", "event_sample", "artifact_flagged")
            )
            rows[key] = (truth, prediction, trial_identity)
    return rows


def metrics(rows: list[tuple[int, int]]) -> dict:
    truth_counts = Counter(truth for truth, _ in rows)
    if set(truth_counts) != {1, 2, 3, 4}:
        raise ValueError("All four true classes must be present")
    prediction_counts = Counter(prediction for _, prediction in rows)
    recall = {
        str(label): sum(truth == label and prediction == label for truth, prediction in rows)
        / truth_counts[label]
        for label in range(1, 5)
    }
    proportions = [prediction_counts[label] / len(rows) for label in range(1, 5)]
    entropy = -sum(p * math.log(p) for p in proportions if p) / math.log(4)
    return {
        "balanced_accuracy": statistics.mean(recall.values()),
        "class_recall": recall,
        "dominant_predicted_share": max(proportions),
        "predicted_class_entropy_normalized": entropy,
        "active_predicted_classes": sum(p > 0 for p in proportions),
        "true_counts": {str(label): truth_counts[label] for label in range(1, 5)},
        "predicted_counts": {str(label): prediction_counts[label] for label in range(1, 5)},
    }


def committed_bytes(repo: Path, path: Path) -> bytes:
    relative = path.relative_to(repo).as_posix()
    return subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=repo,
        capture_output=True,
        check=True,
    ).stdout


def committed_sha256(repo: Path, path: Path) -> str:
    return hashlib.sha256(committed_bytes(repo, path)).hexdigest()


def verify_q8_manifest(repo: Path, folder: Path) -> dict:
    checked = 0
    manifest = folder / "SHA256SUMS.txt"
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split(maxsplit=1)
        target = folder / relative.removeprefix("./")
        # Git's Windows checkout may convert LF to CRLF. The repository
        # manifest hashes the committed byte stream, not checkout line endings.
        if not target.is_file() or committed_sha256(repo, target) != expected:
            raise ValueError(f"Q8 manifest mismatch: {target}")
        checked += 1
    return {"files_verified": checked, "manifest_sha256": committed_sha256(repo, manifest)}


def audit(repo: Path) -> dict:
    q5_path = repo / "results/Q5-E001/predictions.csv"
    q8_folder = repo / "research_runs/Q8-E001"
    q8_path = q8_folder / "results/predictions.csv"
    historical_status = subprocess.run(
        ["git", "status", "--porcelain", "--", "outputs/Q4-E001", "results/Q5-E001", "research_runs/Q8-E001"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if historical_status.strip():
        raise ValueError(f"Historical Q5/Q8 files are not clean: {historical_status}")
    manifest = verify_q8_manifest(repo, q8_folder)
    q5, q8 = read_predictions(q5_path), read_predictions(q8_path)
    if q5.keys() != q8.keys() or len(q8) != 9 * 3 * 576:
        raise ValueError("Q5/Q8 key sets or expected prediction counts differ")
    if any(q5[key][0] != q8[key][0] or q5[key][2] != q8[key][2] for key in q5):
        raise ValueError("Q5/Q8 target labels or trial metadata differ")
    q4_reference = {}
    q4_predictions_path = repo / "outputs/Q4-E001/predictions.csv"
    with q4_predictions_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["model"] != "BroadCSP_LDA":
                continue
            key = (int(row["subject"]), 20260924, row["sample_id"])
            identity = (
                int(row["y_true"]),
                tuple(
                    row[column]
                    for column in ("session", "run", "trial", "event_sample", "artifact_flagged")
                ),
            )
            if key in q4_reference:
                raise ValueError(f"Duplicate Q4 trial: {key}")
            q4_reference[key] = identity
    q8_first_seed = {key: (value[0], value[2]) for key, value in q8.items() if key[1] == 20260924}
    if q4_reference != q8_first_seed:
        raise ValueError("Q4 and Q8 target trial identity or labels differ")

    grouped: dict[str, dict[tuple[int, int], list[tuple[int, int]]]] = {}
    for name, predictions in (("Q5", q5), ("Q8", q8)):
        groups: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
        for (subject, seed, _sample_id), pair in predictions.items():
            groups[(subject, seed)].append(pair[:2])
        if len(groups) != 27 or any(len(rows) != 576 for rows in groups.values()):
            raise ValueError(f"Unexpected fold/seed trial count in {name}")
        grouped[name] = groups

    subjects = []
    for subject in range(1, 10):
        row = {"subject": subject}
        for name in ("Q5", "Q8"):
            per_seed = [
                metrics(grouped[name][(subject, seed)])
                for seed in (20260924, 20260925, 20260926)
            ]
            row[name] = {
                "balanced_accuracy": statistics.mean(item["balanced_accuracy"] for item in per_seed),
                "balanced_accuracy_seed_sd": statistics.stdev(
                    item["balanced_accuracy"] for item in per_seed
                ),
                "entropy": statistics.mean(
                    item["predicted_class_entropy_normalized"] for item in per_seed
                ),
                "dominant_share": statistics.mean(
                    item["dominant_predicted_share"] for item in per_seed
                ),
                "active_classes": statistics.mean(
                    item["active_predicted_classes"] for item in per_seed
                ),
                "class_recall": {
                    str(label): statistics.mean(item["class_recall"][str(label)] for item in per_seed)
                    for label in range(1, 5)
                },
                "per_seed": [
                    {"seed": seed, **item}
                    for seed, item in zip((20260924, 20260925, 20260926), per_seed)
                ],
            }
        row["delta_balanced_accuracy_pp"] = (
            row["Q8"]["balanced_accuracy"] - row["Q5"]["balanced_accuracy"]
        ) * 100
        subjects.append(row)

    changes = [row["delta_balanced_accuracy_pp"] for row in subjects]
    s3_s8 = changes[2] + changes[7]
    positives = sum(value > 1e-10 for value in changes)
    negatives = sum(value < -1e-10 for value in changes)
    nonzero = positives + negatives
    # Conventional two-sided exact sign test drops tied subject pairs.
    tail = sum(math.comb(nonzero, k) for k in range(min(positives, negatives) + 1))
    sign_test_p = min(1.0, 2 * tail / (2**nonzero))
    q4_path = repo / "outputs/Q4-E001/per_subject_metrics.csv"
    q4_by_model: dict[str, dict[int, float]] = defaultdict(dict)
    with q4_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["stratum"] == "all":
                q4_by_model[row["model"]][int(row["subject"])] = float(
                    row["balanced_accuracy"]
                )
    if any(set(values) != set(range(1, 10)) for values in q4_by_model.values()):
        raise ValueError("Q4 comparator is missing one or more LOSO subjects")
    q4_comparison = {
        model: {
            "q4_mean_balanced_accuracy": statistics.mean(values.values()),
            "q8_minus_q4_mean_pp": statistics.mean(
                (row["Q8"]["balanced_accuracy"] - values[row["subject"]]) * 100
                for row in subjects
            ),
            "q8_subject_wins": sum(
                row["Q8"]["balanced_accuracy"] > values[row["subject"]]
                for row in subjects
            ),
        }
        for model, values in sorted(q4_by_model.items())
    }
    return {
        "source": {
            "q5_predictions_git_sha256": committed_sha256(repo, q5_path),
            "q8_predictions_git_sha256": committed_sha256(repo, q8_path),
            "q5_predictions_worktree_sha256": sha256(q5_path),
            "q8_predictions_worktree_sha256": sha256(q8_path),
            "q4_subject_metrics_git_sha256": committed_sha256(repo, q4_path),
            "q4_predictions_git_sha256": committed_sha256(repo, q4_predictions_path),
            "q8_manifest": manifest,
            "paired_predictions": len(q8),
            "inference_unit": "subject; seeds are repeated model fits",
        },
        "subjects": subjects,
        "aggregate": {
            "q5_mean_balanced_accuracy": statistics.mean(row["Q5"]["balanced_accuracy"] for row in subjects),
            "q8_mean_balanced_accuracy": statistics.mean(row["Q8"]["balanced_accuracy"] for row in subjects),
            "q5_subject_sd_balanced_accuracy": statistics.stdev(
                row["Q5"]["balanced_accuracy"] for row in subjects
            ),
            "q8_subject_sd_balanced_accuracy": statistics.stdev(
                row["Q8"]["balanced_accuracy"] for row in subjects
            ),
            "q8_mean_balanced_accuracy_by_seed": {
                str(seed): statistics.mean(
                    next(
                        item["balanced_accuracy"]
                        for item in row["Q8"]["per_seed"]
                        if item["seed"] == seed
                    )
                    for row in subjects
                )
                for seed in (20260924, 20260925, 20260926)
            },
            "q8_mean_class_recall": {
                str(label): statistics.mean(
                    row["Q8"]["class_recall"][str(label)] for row in subjects
                )
                for label in range(1, 5)
            },
            "q4_comparison": q4_comparison,
            "mean_delta_pp": statistics.mean(changes),
            "median_delta_pp": statistics.median(changes),
            "s3_s8_share_of_total_delta": s3_s8 / sum(changes),
            "mean_delta_excluding_s3_s8_pp": statistics.mean(
                value for index, value in enumerate(changes, 1) if index not in (3, 8)
            ),
            "leave_one_subject_out_mean_delta_pp": {
                str(subject): statistics.mean(
                    value for index, value in enumerate(changes, 1) if index != subject
                )
                for subject in range(1, 10)
            },
            "improved_subjects": sum(value > 1e-10 for value in changes),
            "unchanged_subjects": sum(abs(value) <= 1e-10 for value in changes),
            "worsened_subjects": sum(value < -1e-10 for value in changes),
            "conventional_two_sided_sign_test_excluding_ties_p": sign_test_p,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.repo.resolve())
    content = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(json.dumps(result["aggregate"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
