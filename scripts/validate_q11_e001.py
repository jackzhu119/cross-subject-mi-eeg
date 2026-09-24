"""Independent Q11-E001 fit, prediction, selection and architecture audit.

This does not train or refit any model. Failure writes a durable failed receipt.
Its scientific checks are separate from the orchestration/job-exit validator.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, confusion_matrix

ROOT = Path(__file__).resolve().parents[1]
CONDITIONS = (
    "FOUR_BAND_SHARED", "TWO_BAND_INDEPENDENT", "TWO_BAND_EARLY_STACK",
    "BROAD_CAPACITY_MATCHED",
)
SEEDS = (20260924, 20260925, 20260926)
FIT_FILES = ("checkpoint.pt", "learning_curve.csv", "fit_manifest.csv", "model_receipt.json")
FINAL_FILES = FIT_FILES + ("predictions.csv", "metrics.csv", "confusion.csv")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return value


def check_fit(directory: Path, filenames: tuple[str, ...]) -> dict:
    status = read_json(directory / "status.json")
    if status.get("status") != "complete":
        raise AssertionError(f"Incomplete Q11 fit {directory}")
    for filename in filenames:
        path = directory / filename
        if not path.is_file() or digest(path) != status.get(f"sha256_{filename}"):
            raise AssertionError(f"Missing or altered Q11 fit artifact {path}")
    return status


def independent_epoch(curves: list[pd.DataFrame]) -> int:
    if len(curves) != 4:
        raise AssertionError("Expected four source-validation curves")
    ranks = []
    for curve in curves:
        if curve.epoch.astype(int).tolist() != list(range(1, 41)):
            raise AssertionError("Source-validation curve must cover epochs 1..40")
        val = curve.val_ce.to_numpy(dtype=float)
        if not np.isfinite(val).all():
            raise AssertionError("Source-validation curve has nonfinite CE")
        ranks.append(pd.Series(val).rank(method="average", ascending=True).to_numpy())
    mean = np.stack(ranks, axis=1).mean(axis=1)
    return int(np.flatnonzero(np.isclose(mean, mean.min(), atol=1e-12, rtol=0))[0] + 1)


def validate_manifest(manifest: pd.DataFrame, *, target: int, inner: int | None,
                      seed: int, epochs: int) -> None:
    if len(manifest) != 9 or set(manifest.subject.astype(int)) != set(range(1, 10)):
        raise AssertionError("Q11 manifest lacks exactly nine subject rows")
    sources = [subject for subject in range(1, 10) if subject != target]
    val = sources[2 * (inner - 1):2 * inner] if inner is not None else []
    stage = "inner" if inner is not None else "full"
    for _, row in manifest.iterrows():
        subject = int(row.subject)
        role = ("outer_test_excluded" if inner is not None else "test") if subject == target else (
            "validation" if subject in val else "train")
        observed_inner = None if pd.isna(row.inner_fold) else int(row.inner_fold)
        if (row.fold != f"loso_s{target}" or row.stage != stage or observed_inner != inner
                or int(row.seed) != seed or row.role != role or int(row.n_trials) != 576
                or int(row.n_used_for_fit) != (576 if role == "train" else 0)
                or int(row.n_used_for_validation) != (576 if role == "validation" else 0)
                or int(row.n_excluded_from_fit) != 0 or int(row.epochs_trained) != epochs):
            raise AssertionError(f"Q11 source-only manifest mismatch S{target}/S{subject}")


def validate_checkpoint(directory: Path, config: dict, condition: str, status: dict) -> int:
    """Check parameter shapes/count against saved tensors, not just a JSON claim."""
    import torch

    receipt = read_json(directory / "model_receipt.json")
    if (receipt.get("condition") != condition or receipt.get("fusion") != config["fusion"]
            or receipt.get("architecture") != config["architecture"]
            or receipt.get("target_or_EEG_used_to_size_model") is not False):
        raise AssertionError("Architecture receipt differs from locked Q11 config")
    state = torch.load(directory / "checkpoint.pt", map_location="cpu", weights_only=True)
    for key in ("experiment_id", "condition", "target_subject", "stage", "seed", "train_subjects"):
        if state.get(key) != status.get(key):
            raise AssertionError(f"Checkpoint/status fit provenance mismatch: {key}")
    if status.get("stage") == "full" and state.get("selected_epochs") != status.get("selected_epochs"):
        raise AssertionError("Checkpoint trained duration differs from selected duration")
    weights = state.get("model_state")
    names = receipt.get("parameter_shapes")
    if not isinstance(weights, dict) or not isinstance(names, dict) or not names:
        raise AssertionError("Checkpoint or architecture parameter inventory missing")
    count = 0
    for name, shape in names.items():
        if name not in weights or list(weights[name].shape) != shape:
            raise AssertionError(f"Checkpoint parameter missing or wrong shape: {name}")
        count += weights[name].numel()
    if count != receipt.get("trainable_parameter_count"):
        raise AssertionError("Trainable parameter count does not match checkpoint")
    reference = config["capacity_plan"]["reference_independent_two_branch_count"]
    if receipt.get("capacity_reference_two_branch_count") != reference:
        raise AssertionError("Capacity reference changed between fit and config")
    if condition == "TWO_BAND_INDEPENDENT" and count != reference:
        raise AssertionError("Independent model does not have two baseline branches")
    if condition == "FOUR_BAND_SHARED" and count != config["capacity_plan"]["reference_single_branch_count"]:
        raise AssertionError("Shared model unexpectedly increased parameter count")
    if condition == "BROAD_CAPACITY_MATCHED" and count != config["capacity_plan"]["chosen"]["parameter_count"]:
        raise AssertionError("Capacity-matched model differs from structure-only choice")
    if condition == "TWO_BAND_EARLY_STACK" and config["architecture"]["n_chans"] != 44:
        raise AssertionError("Early stacking must use 44 channels")
    return count


def validate_predictions(frame: pd.DataFrame, reference: pd.DataFrame, *,
                         subject: int, seed: int, condition: str, selected: int) -> dict:
    if len(frame) != 576 or frame.sample_id.nunique() != 576:
        raise AssertionError("Q11 target predictions lack 576 unique trials")
    expected = reference.loc[reference.subject == subject].reset_index(drop=True)
    if (frame.sample_id.astype(str).tolist() != expected.sample_id.astype(str).tolist()
            or frame.label.astype(int).tolist() != expected.label.astype(int).tolist()
            or frame.session.astype(str).tolist() != expected.session.astype(str).tolist()
            or frame.artifact_flagged.astype(str).str.lower().tolist()
            != expected.artifact_flagged.astype(str).str.lower().tolist()):
        raise AssertionError("Q11 trial identity, label, session or flags differ from frozen Q8")
    if (frame.subject.astype(int).unique().tolist() != [subject]
            or frame.seed.astype(int).unique().tolist() != [seed]
            or frame.experiment_id.unique().tolist() != ["Q11-E001"]
            or frame.condition.unique().tolist() != [condition]
            or frame.fold.unique().tolist() != [f"loso_s{subject}"]
            or frame.selected_epochs.astype(int).unique().tolist() != [selected]
            or frame.selection_rule.unique().tolist() != ["mean_rank"]):
        raise AssertionError("Q11 prediction experiment/fold/selection metadata mismatch")
    truth = frame.y_true.to_numpy(dtype=int)
    pred = frame.y_pred.to_numpy(dtype=int)
    if not np.array_equal(truth, frame.label.to_numpy(dtype=int)) or np.bincount(truth, minlength=5)[1:].tolist() != [144] * 4:
        raise AssertionError("Q11 target event mapping or class counts changed")
    prob = frame[[f"p_class_{i}" for i in range(1, 5)]].to_numpy(dtype=float)
    if (not np.isfinite(prob).all() or (prob < 0).any()
            or not np.allclose(prob.sum(axis=1), 1.0, atol=1e-6, rtol=0)
            or not np.array_equal(pred, prob.argmax(axis=1) + 1)):
        raise AssertionError("Q11 probabilities are invalid or predictions disagree with argmax")
    matrix = confusion_matrix(truth, pred, labels=[1, 2, 3, 4])
    recalls = np.diag(matrix) / matrix.sum(axis=1)
    return {"condition": condition, "subject": subject, "seed": seed,
            "balanced_accuracy": float(balanced_accuracy_score(truth, pred)),
            "selected_epochs": selected, "zero_recall_classes": int((recalls == 0).sum()),
            "dominant_prediction_share": float(np.bincount(pred, minlength=5)[1:].max() / len(pred)),
            **{f"recall_class_{i}": float(recalls[i - 1]) for i in range(1, 5)}}


def validate_metric_files(frame: pd.DataFrame, metrics: pd.DataFrame, confusion: pd.DataFrame,
                          *, subject: int, seed: int, condition: str) -> None:
    flagged = frame.artifact_flagged.astype(str).str.lower().eq("true").to_numpy()
    strata = {"all": np.ones(len(frame), dtype=bool), "unflagged": ~flagged, "flagged": flagged}
    for name, mask in strata.items():
        sub = frame.loc[mask]
        saved = metrics.loc[metrics.stratum == name]
        cells = confusion.loc[confusion.stratum == name]
        if sub.empty:
            if not saved.empty or not cells.empty:
                raise AssertionError("Metric saved for empty target stratum")
            continue
        if len(saved) != 1 or len(cells) != 16:
            raise AssertionError(f"Q11 {name} metric/confusion incomplete")
        row = saved.iloc[0]
        if (row.fold != f"loso_s{subject}" or int(row.subject) != subject
                or int(row.seed) != seed or row.condition != condition or int(row.n_test) != len(sub)
                or not np.isclose(float(row.balanced_accuracy),
                                  balanced_accuracy_score(sub.y_true, sub.y_pred), atol=1e-12, rtol=0)):
            raise AssertionError(f"Q11 {name} metric differs from predictions")
        actual = confusion_matrix(sub.y_true, sub.y_pred, labels=[1, 2, 3, 4]).ravel()
        saved_counts = cells.sort_values(["true_label", "predicted_label"])["count"].to_numpy(dtype=int)
        if not np.array_equal(saved_counts, actual):
            raise AssertionError(f"Q11 {name} confusion differs from predictions")


def paired_subject_summary(candidate: pd.DataFrame, baseline: pd.DataFrame) -> dict:
    joined = candidate.merge(baseline, on=["subject", "seed"], validate="one_to_one", suffixes=("_new", "_base"))
    if len(joined) != 27:
        raise AssertionError("Paired Q11 contrast lacks 9×3 subjects/seeds")
    grouped = joined.groupby("subject", sort=True)
    deltas = grouped.apply(lambda part: float((part.balanced_accuracy_new - part.balanced_accuracy_base).mean()),
                           include_groups=False)
    values = deltas.to_numpy()
    rng = np.random.default_rng(20260924)
    means = rng.choice(values, size=(20000, 9), replace=True).mean(axis=1)
    observed = abs(float(values.mean()))
    flips = np.asarray(list(itertools.product((-1, 1), repeat=9)), dtype=float)
    p = float(np.mean(np.abs((flips * values).mean(axis=1)) >= observed - 1e-15))
    return {"per_subject_delta": {str(int(index)): float(delta) for index, delta in deltas.items()},
            "mean_delta": float(values.mean()), "median_delta": float(np.median(values)),
            "subject_bootstrap_95ci": np.quantile(means, [0.025, 0.975]).tolist(),
            "exact_sign_flip_two_sided_p_exploratory": p,
            "inference_unit": "nine_held_out_subjects_not_seeds_or_trials"}


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    """Holm step-down within a predeclared four-condition comparator family."""
    ordered = sorted(p_values, key=lambda key: p_values[key])
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, key in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - rank) * p_values[key]))
        adjusted[key] = running
    return adjusted


def audit(root: Path) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    reference = pd.read_csv(ROOT / "research_runs/Q8-E001/results/trial_metadata.csv")
    if len(reference) != 5184 or reference.sample_id.nunique() != 5184:
        raise AssertionError("Frozen Q8 metadata incomplete")
    q8_sources = json.loads((ROOT / "research_runs/Q8-E001/results/source_files.json").read_text(encoding="utf-8"))
    frozen_sources = sorted((Path(item["path"]).name, item["bytes"], item["sha256"]) for item in q8_sources)
    if len(frozen_sources) != 18:
        raise AssertionError("Frozen Q8 MAT provenance incomplete")
    matrix = read_json(ROOT / "research_runs/Q11-E001/MATRIX.json")
    if [row["name"] for row in matrix["conditions"]] != list(CONDITIONS):
        raise AssertionError("Q11 matrix condition list changed")
    results = []
    parameter_rows = []
    condition_predictions: dict[str, pd.DataFrame] = {}
    for condition in CONDITIONS:
        directory = root / "Q11-E001" / condition
        config = read_json(directory / "run_config.json")
        if (config.get("experiment_id") != "Q11-E001" or config.get("condition") != condition
                or config.get("bands") != next(row["bands"] for row in matrix["conditions"] if row["name"] == condition)
                or config.get("source_only_selection") is not True
                or config.get("target_fitted_transform") is not False
                or config.get("q8_config_sha256") != digest(ROOT / "research_runs/Q8-E001/results/config.json")
                or config.get("execution_matrix_sha256") != digest(ROOT / "research_runs/Q11-E001/MATRIX.json")
                or config.get("runner_sha256") != digest(ROOT / "scripts/q11_neural.py")):
            raise AssertionError("Q11 locked condition/preprocessing/code differs")
        current = read_json(directory / "source_files.json")
        observed_sources = sorted((Path(item["path"]).name, item["bytes"], item["sha256"])
                                  for item in current["files"])
        if (observed_sources != frozen_sources or
                current.get("q8_metadata_sha256") != digest(ROOT / "research_runs/Q8-E001/results/trial_metadata.csv")):
            raise AssertionError("Q11 source MAT/trial hashes differ from Q8")
        provenance = read_json(directory / "selection_provenance.json")
        selection = pd.read_csv(directory / "selection.csv")
        if (provenance.get("status") != "frozen_before_Q11_target_inference"
                or provenance.get("selection_seed") != 20260923
                or provenance.get("inner_fits") != 36
                or provenance.get("target_result_used") is not False
                or provenance.get("selection_sha256") != digest(directory / "selection.csv")
                or provenance.get("run_config_sha256") != digest(directory / "run_config.json")
                or provenance.get("mean_rank_details_sha256") != digest(directory / "mean_rank_epoch_details.csv")
                or selection.subject.astype(int).tolist() != list(range(1, 10))):
            raise AssertionError("Q11 source-only selection provenance invalid")
        predictions = []
        for subject in range(1, 10):
            sources = [value for value in range(1, 10) if value != subject]
            curves = []
            for inner in range(1, 5):
                fit = directory / "inner" / f"loso_s{subject}" / f"inner_{inner}"
                status = check_fit(fit, FIT_FILES)
                val = sources[2 * (inner - 1):2 * inner]
                train = [value for value in sources if value not in val]
                if (status.get("target_subject") != subject or status.get("train_subjects") != train
                        or status.get("validation_subjects") != val or status.get("seed") != 20260923
                        or status.get("epochs_trained") != 40):
                    raise AssertionError("Q11 inner source split/seed/epoch mismatch")
                validate_manifest(pd.read_csv(fit / "fit_manifest.csv"), target=subject,
                                  inner=inner, seed=20260923, epochs=40)
                count = validate_checkpoint(fit, config, condition, status)
                parameter_rows.append({"condition": condition, "subject": subject,
                                       "stage": "inner", "fold_or_seed": inner, "parameter_count": count})
                curves.append(pd.read_csv(fit / "learning_curve.csv"))
            selected = independent_epoch(curves)
            if int(selection.loc[selection.subject == subject, "selected_epochs"].iloc[0]) != selected:
                raise AssertionError("Q11 saved epoch differs from independent mean-rank calculation")
            for seed in SEEDS:
                fit = directory / "final" / f"loso_s{subject}" / f"seed_{seed}"
                status = check_fit(fit, FINAL_FILES)
                if (status.get("target_subject") != subject or status.get("train_subjects") != sources
                        or status.get("test_subjects") != [subject] or status.get("seed") != seed
                        or status.get("selected_epochs") != selected
                        or status.get("selection_sha256") != digest(directory / "selection.csv")):
                    raise AssertionError("Q11 final source split/selection mismatch")
                validate_manifest(pd.read_csv(fit / "fit_manifest.csv"), target=subject,
                                  inner=None, seed=seed, epochs=selected)
                count = validate_checkpoint(fit, config, condition, status)
                parameter_rows.append({"condition": condition, "subject": subject,
                                       "stage": "final", "fold_or_seed": seed, "parameter_count": count})
                frame = pd.read_csv(fit / "predictions.csv")
                result = validate_predictions(frame, reference, subject=subject, seed=seed,
                                              condition=condition, selected=selected)
                validate_metric_files(frame, pd.read_csv(fit / "metrics.csv"),
                                      pd.read_csv(fit / "confusion.csv"), subject=subject,
                                      seed=seed, condition=condition)
                results.append(result)
                predictions.append(frame)
        combined = pd.concat(predictions, ignore_index=True)
        aggregate = pd.read_csv(directory / "predictions.csv")
        keys = ["subject", "seed", "sample_id", "y_true", "y_pred"]
        if not combined[keys].sort_values(keys).reset_index(drop=True).equals(
            aggregate[keys].sort_values(keys).reset_index(drop=True)):
            raise AssertionError("Q11 aggregate predictions differ from per-fit predictions")
        condition_predictions[condition] = combined
        state = read_json(directory / "status.json")
        if state.get("status") != "complete" or state.get("completed_inner_fits") != 36 or state.get("completed_final_fits") != 27:
            raise AssertionError("Q11 condition completion marker incomplete")
    result_table = pd.DataFrame(results)
    if len(result_table) != 108:
        raise AssertionError("Q11 lacks four conditions × nine subjects × three seeds")
    refs = {}
    for name, path in (("Q8_broad", ROOT / "research_runs/Q8-E001/results/predictions.csv"),
                       ("Q9_mu_beta_shared", root / "Q9-E001/MU_BETA_SHARED/predictions.csv")):
        frame = pd.read_csv(path)
        rows = []
        for (subject, seed), part in frame.groupby(["subject", "seed"], sort=True):
            if len(part) != 576 or not np.array_equal(part.y_true.to_numpy(dtype=int),
                                                       reference.loc[reference.subject == subject, "label"].to_numpy(dtype=int)):
                raise AssertionError(f"Frozen comparator {name} trial identity changed")
            rows.append({"subject": int(subject), "seed": int(seed),
                         "balanced_accuracy": float(balanced_accuracy_score(part.y_true, part.y_pred))})
        refs[name] = pd.DataFrame(rows)
    contrasts = {condition: {name: paired_subject_summary(
        result_table.loc[result_table.condition == condition], baseline)
        for name, baseline in refs.items()} for condition in CONDITIONS}
    for reference_name in refs:
        corrected = holm_adjust({condition: contrasts[condition][reference_name][
            "exact_sign_flip_two_sided_p_exploratory"] for condition in CONDITIONS})
        for condition in CONDITIONS:
            contrasts[condition][reference_name]["holm_adjusted_p_within_four_Q11_conditions"] = corrected[condition]
    summary = {"conditions": contrasts, "scope": "exploratory_BNCI_same_dataset_after_Q9",
               "primary_unit": "held_out_subject_equal_weight_after_three_seed_mean"}
    sessions, flags = [], []
    for condition, frame in condition_predictions.items():
        for (subject, seed, session), part in frame.groupby(["subject", "seed", "session"], sort=True):
            sessions.append({"condition": condition, "subject": int(subject), "seed": int(seed),
                             "session": session, "n_trials": len(part),
                             "n_true_classes": part.y_true.nunique(),
                             "balanced_accuracy": float(balanced_accuracy_score(part.y_true, part.y_pred))})
        for (subject, seed, flagged), part in frame.groupby(["subject", "seed", "artifact_flagged"], sort=True):
            flags.append({"condition": condition, "subject": int(subject), "seed": int(seed),
                          "artifact_flagged": bool(flagged), "n_trials": len(part),
                          "n_true_classes": part.y_true.nunique(),
                          "balanced_accuracy_present_classes": float(balanced_accuracy_score(part.y_true, part.y_pred))})
    return summary, result_table, pd.DataFrame(parameter_rows), pd.DataFrame(sessions), pd.DataFrame(flags)


def draw_subject_heatmap(subject_table: pd.DataFrame, destination: Path) -> None:
    """Descriptive, all-subject BA map; no winning-condition highlight."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    grid = subject_table.pivot(index="condition", columns="subject", values="mean_ba")
    grid = grid.reindex(CONDITIONS).reindex(columns=range(1, 10))
    if grid.isna().any().any():
        raise AssertionError("Incomplete Q11 subject heatmap data")
    fig, ax = plt.subplots(figsize=(11, 4.1), layout="constrained")
    image = ax.imshow(grid.to_numpy(dtype=float), aspect="auto", vmin=0.25, vmax=0.75,
                      cmap="viridis")
    ax.set_yticks(np.arange(len(CONDITIONS)), labels=CONDITIONS)
    ax.set_xticks(np.arange(9), labels=[f"S{subject}" for subject in range(1, 10)])
    ax.set_title("Q11 exploratory held-out-subject BA (3-seed mean)")
    ax.set_xlabel("Held-out BNCI subject")
    for row in range(len(CONDITIONS)):
        for col in range(9):
            value = float(grid.iloc[row, col])
            ax.text(col, row, f"{value:.3f}", ha="center", va="center",
                    fontsize=8, color="white" if value < 0.48 else "black")
    fig.colorbar(image, ax=ax, label="Balanced accuracy (chance = 0.25)")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    result_root = args.results_root.resolve()
    validation_file = result_root / "Q11-E001" / "validation_report.json"
    try:
        summary, rows, parameters, sessions, flags = audit(result_root)
        out = result_root / "Q11-E001" / "analysis"
        out.mkdir(parents=True, exist_ok=True)
        rows.to_csv(out / "subject_seed_metrics.csv", index=False)
        subject_table = rows.groupby(["condition", "subject"], as_index=False).agg(
            mean_ba=("balanced_accuracy", "mean"),
            seed_sd_ba=("balanced_accuracy", "std"),
            mean_dominant_class_share=("dominant_prediction_share", "mean"),
            zero_recall_seed_count=("zero_recall_classes", lambda value: int((value > 0).sum())),
        )
        subject_table.to_csv(out / "subject_metrics.csv", index=False)
        condition_table = subject_table.groupby("condition", as_index=False).agg(
            equal_subject_mean_ba=("mean_ba", "mean"),
            between_subject_sd_ba=("mean_ba", "std"),
            median_subject_ba=("mean_ba", "median"),
            min_subject_ba=("mean_ba", "min"),
            max_subject_ba=("mean_ba", "max"),
            mean_within_subject_seed_sd_ba=("seed_sd_ba", "mean"),
            n_subjects=("subject", "nunique"),
        )
        for cls in range(1, 5):
            recall = rows.groupby("condition")[f"recall_class_{cls}"].mean()
            condition_table[f"mean_recall_class_{cls}"] = condition_table.condition.map(recall)
        condition_table.to_csv(out / "condition_metrics.csv", index=False)
        parameters.to_csv(out / "parameter_counts.csv", index=False)
        sessions.to_csv(out / "session_metrics.csv", index=False)
        flags.to_csv(out / "artifact_flag_strata.csv", index=False)
        (out / "paired_contrasts.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        draw_subject_heatmap(subject_table, out / "subject_ba_heatmap.png")
        report = {"status": "passed_scientific_checks", "inner_fits": 144,
                  "final_fits": 108, "checkpoint_parameter_counts_checked": 252,
                  "source_only_selections_recomputed": 36,
                  "conditions": list(CONDITIONS), "errors": [],
                  "scope": "exploratory_BNCI_not_external_confirmation"}
        code = 0
    except Exception as exc:  # noqa: BLE001 - permanent failure receipt for review
        report = {"status": "failed", "errors": [f"{type(exc).__name__}: {exc}"]}
        code = 1
    validation_file.parent.mkdir(parents=True, exist_ok=True)
    validation_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
