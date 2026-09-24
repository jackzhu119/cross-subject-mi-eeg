"""Independent prediction-level audit of Q10-E001; never fits a model.

Unlike the batch receipt check, this validates source partitions, projector
receipts, source-only epoch selection, target trial identity, probabilities,
metrics and paired subject-level interpretation. It writes analysis outputs
only after both conditions pass. It does not select a winning method.
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
CONDITIONS = ("MU_BETA_CSP8_EEGNET", "MU_BETA_PCA8_EEGNET")
SEEDS = (20260924, 20260925, 20260926)
PROBABILITY_COLUMNS = [f"p_class_{i}" for i in range(1, 5)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return value


def check_fit_files(directory: Path, filenames: tuple[str, ...]) -> dict:
    status = read_json(directory / "status.json")
    if status.get("status") != "complete":
        raise AssertionError(f"Incomplete fit: {directory}")
    for name in filenames:
        path = directory / name
        if not path.is_file() or sha256(path) != status.get(f"sha256_{name}"):
            raise AssertionError(f"Fit file missing or hash mismatch: {path}")
    return status


def independent_selected_epoch(curves: list[pd.DataFrame]) -> int:
    if len(curves) != 4:
        raise AssertionError("Four inner curves required")
    columns = []
    for curve in curves:
        if curve.epoch.astype(int).tolist() != list(range(1, 41)):
            raise AssertionError("Inner curve must cover epochs 1..40 in order")
        values = curve.val_ce.to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise AssertionError("Nonfinite source-validation CE")
        columns.append(pd.Series(values).rank(method="average", ascending=True).to_numpy())
    means = np.stack(columns, axis=1).mean(axis=1)
    return int(np.flatnonzero(np.isclose(means, means.min(), atol=1e-12, rtol=0))[0] + 1)


def validate_prediction_frame(frame: pd.DataFrame, reference: pd.DataFrame,
                              subject: int, seed: int) -> dict:
    if len(frame) != 576 or frame.sample_id.nunique() != 576:
        raise AssertionError("Expected 576 unique target trials")
    if frame.subject.astype(int).unique().tolist() != [subject] or frame.seed.astype(int).unique().tolist() != [seed]:
        raise AssertionError("Subject/seed identity mismatch")
    joined = frame.merge(reference[["sample_id", "subject", "session", "label", "artifact_flagged"]],
                         on="sample_id", how="left", validate="one_to_one", suffixes=("", "_ref"))
    if len(joined) != 576 or joined.label_ref.isna().any():
        raise AssertionError("Q8 reference trial coverage differs")
    for column in ("subject", "session", "label", "artifact_flagged"):
        if not (joined[column].astype(str).to_numpy() == joined[f"{column}_ref"].astype(str).to_numpy()).all():
            raise AssertionError(f"Q8 trial identity mismatch: {column}")
    truth = frame.y_true.to_numpy(dtype=int)
    prediction = frame.y_pred.to_numpy(dtype=int)
    if not np.array_equal(truth, frame.label.to_numpy(dtype=int)):
        raise AssertionError("Target labels differ from original event labels")
    if np.bincount(truth, minlength=5)[1:].tolist() != [144] * 4:
        raise AssertionError("Four-class target population is not 144 per class")
    probabilities = frame[PROBABILITY_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(probabilities).all() or (probabilities < 0).any():
        raise AssertionError("Nonfinite or negative target probabilities")
    if not np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-6, rtol=0):
        raise AssertionError("Class probabilities do not sum to one")
    if not np.array_equal(prediction, probabilities.argmax(axis=1) + 1):
        raise AssertionError("Predicted label disagrees with argmax probability")
    confusion = confusion_matrix(truth, prediction, labels=[1, 2, 3, 4])
    recalls = np.diag(confusion) / confusion.sum(axis=1)
    return {"subject": subject, "seed": seed,
            "balanced_accuracy": float(balanced_accuracy_score(truth, prediction)),
            "class_recall": recalls.tolist(),
            "zero_recall_classes": int(np.sum(recalls == 0)),
            "dominant_prediction_share": float(np.bincount(prediction, minlength=5)[1:].max() / len(prediction)),
            "n_trials": len(frame)}


def fit_sample_hash(ids: list[str]) -> str:
    return hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest()


def validate_spatial_receipt(receipt: dict, *, method: str, fit_subjects: list[int],
                             fit_sample_ids: list[str]) -> None:
    """Recompute the parameter digest; status-file hashes alone are not independent evidence."""
    if (receipt.get("method") != method or receipt.get("fit_subjects") != fit_subjects
            or receipt.get("n_source_trials") != len(fit_sample_ids)
            or receipt.get("fit_sample_ids_sha256") != fit_sample_hash(fit_sample_ids)
            or receipt.get("n_components_per_band") != 8):
        raise AssertionError("Spatial receipt has an unexpected source fit or method")
    expected_channels = [f"mu_{i:02d}" for i in range(1, 9)] + [
        f"beta_{i:02d}" for i in range(1, 9)]
    if receipt.get("projected_channel_order") != expected_channels:
        raise AssertionError("Spatial projected channel order changed")
    shapes = {
        "filters_mu": (8, 22), "filters_beta": (8, 22),
        "channel_mean_mu": (22,), "channel_mean_beta": (22,),
        "projected_mean_mu": (8,), "projected_mean_beta": (8,),
        "projected_scale_mu": (8,), "projected_scale_beta": (8,),
    }
    parameters = receipt.get("parameters", {})
    if set(parameters) != set(shapes):
        raise AssertionError("Spatial receipt parameter set changed")
    digest = hashlib.sha256()
    for key in sorted(shapes):
        value = np.asarray(parameters[key], dtype="<f8")
        if value.shape != shapes[key] or not np.isfinite(value).all():
            raise AssertionError(f"Spatial parameter {key} has invalid shape or values")
        if key.startswith("projected_scale_") and (value <= 0).any():
            raise AssertionError("Spatial projection has nonpositive source scale")
        digest.update(key.encode("utf-8") + b"\0")
        digest.update(np.ascontiguousarray(value).tobytes())
    if digest.hexdigest() != receipt.get("parameter_sha256"):
        raise AssertionError("Spatial parameter SHA256 does not match values")


def validate_fit_manifest(manifest: pd.DataFrame, reference: pd.DataFrame, *,
                          target: int, stage: str, inner_fold: int | None,
                          seed: int, epochs: int) -> None:
    """Independently check every subject role and trial count in a fitted partition."""
    if len(manifest) != 9 or set(manifest.subject.astype(int)) != set(range(1, 10)):
        raise AssertionError("Fit manifest must contain exactly nine subject rows")
    sources = [subject for subject in range(1, 10) if subject != target]
    validation = ([] if stage == "full" else
                  sources[2 * (inner_fold - 1):2 * inner_fold])
    for _, row in manifest.iterrows():
        subject = int(row.subject)
        expected_role = ("outer_test_excluded" if stage == "inner" else "test") if subject == target else (
            "validation" if subject in validation else "train")
        expected_used = 576 if expected_role == "train" else 0
        expected_val = 576 if expected_role == "validation" else 0
        expected_inner = inner_fold if stage == "inner" else None
        observed_inner = None if pd.isna(row.inner_fold) else int(row.inner_fold)
        if (row.fold != f"loso_s{target}" or row.stage != stage
                or observed_inner != expected_inner or int(row.seed) != seed
                or row.role != expected_role or int(row.n_trials) != 576
                or int(row.n_used_for_fit) != expected_used
                or int(row.n_used_for_validation) != expected_val
                or int(row.epochs_trained) != epochs
                or int(row.n_excluded_from_fit) != 0):
            raise AssertionError(f"Fit manifest mismatch for target S{target}, subject S{subject}")
        if int((reference.subject == subject).sum()) != 576:
            raise AssertionError("Frozen reference subject population changed")


def validate_saved_metrics(frame: pd.DataFrame, metrics: pd.DataFrame,
                           confusion: pd.DataFrame, *, subject: int, seed: int,
                           condition: str) -> None:
    flagged = frame.artifact_flagged.astype(str).str.lower().eq("true").to_numpy()
    strata = {"all": np.ones(len(frame), dtype=bool), "unflagged": ~flagged,
              "flagged": flagged}
    for name, mask in strata.items():
        sub = frame.loc[mask]
        saved = metrics.loc[metrics.stratum == name]
        cells = confusion.loc[confusion.stratum == name]
        if sub.empty:
            if not saved.empty or not cells.empty:
                raise AssertionError(f"Unexpected empty stratum in saved results: {name}")
            continue
        if len(saved) != 1 or len(cells) != 16:
            raise AssertionError(f"Missing metric or confusion rows for stratum {name}")
        row = saved.iloc[0]
        if (row.fold != f"loso_s{subject}" or int(row.subject) != subject
                or int(row.seed) != seed or row.condition != condition
                or int(row.n_test) != len(sub)
                or not np.isclose(float(row.balanced_accuracy),
                                  balanced_accuracy_score(sub.y_true, sub.y_pred),
                                  atol=1e-12, rtol=0)):
            raise AssertionError(f"Saved metric differs from target predictions: {name}")
        actual = confusion_matrix(sub.y_true, sub.y_pred, labels=[1, 2, 3, 4])
        ordered = cells.sort_values(["true_label", "predicted_label"])
        if (not np.array_equal(ordered.true_label.to_numpy(dtype=int),
                               np.repeat(np.arange(1, 5), 4))
                or not np.array_equal(ordered.predicted_label.to_numpy(dtype=int),
                                      np.tile(np.arange(1, 5), 4))
                or not np.array_equal(ordered["count"].to_numpy(dtype=int), actual.ravel())
                or not (cells.subject.astype(int) == subject).all()
                or not (cells.seed.astype(int) == seed).all()
                or not (cells.condition == condition).all()):
            raise AssertionError(f"Saved confusion differs from target predictions: {name}")


def audit_condition(root: Path, condition: str, reference: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    directory = root / condition
    config = read_json(directory / "run_config.json")
    if config.get("experiment_id") != "Q10-E001" or config.get("condition") != condition:
        raise AssertionError("Condition/run configuration mismatch")
    if config.get("architecture", {}).get("n_chans") != 16 or config.get("shared_mean_logits"):
        raise AssertionError("Expected one 16-channel EEGNet")
    method = "csp8" if "CSP8" in condition else "pca8"
    if config.get("spatial_method") != method or config.get("fixed_q8_epochs"):
        raise AssertionError("Spatial method or selection protocol changed")
    if (config.get("source_only_selection") is not True
            or config.get("source_training_artifact_exclusion") is not False
            or config.get("source_fit_per_band_channel_zscore") is not False
            or config.get("spatial_helper_sha256") != sha256(ROOT / "scripts/q9_spatial_features.py")
            or config.get("q8_config_sha256") != sha256(ROOT / "research_runs/Q8-E001/results/config.json")
            or config.get("q9_parent_matrix_sha256") != sha256(ROOT / "research_runs/Q9-E001/Q9_BATCH_MATRIX.json")
            or config.get("execution_matrix_sha256") != sha256(ROOT / "research_runs/Q10-E001/MATRIX.json")
            or config.get("runner_sha256") != sha256(ROOT / "scripts/q10_spatial_neural.py")):
        raise AssertionError("Source-only protocol or frozen code hash differs from run configuration")
    frozen = pd.read_csv(directory / "selection.csv")
    if set(frozen.subject.astype(int)) != set(range(1, 10)):
        raise AssertionError("Selection is not a nine-subject grid")
    provenance = read_json(directory / "selection_provenance.json")
    if (provenance.get("status") != "frozen_before_Q10_target_inference"
            or provenance.get("target_result_used") is not False
            or provenance.get("inner_fits") != 36
            or provenance.get("selection_seed") != 20260923
            or provenance.get("run_config_sha256") != sha256(directory / "run_config.json")
            or provenance.get("mean_rank_details_sha256") != sha256(directory / "mean_rank_epoch_details.csv")):
        raise AssertionError("Source-only selection provenance missing")
    if sha256(directory / "selection.csv") != provenance.get("selection_sha256"):
        raise AssertionError("Frozen epoch CSV hash mismatch")
    rows, predictions = [], []
    for subject in range(1, 10):
        sources = [s for s in range(1, 10) if s != subject]
        curves = []
        for inner in range(1, 5):
            fit = directory / "inner" / f"loso_s{subject}" / f"inner_{inner}"
            status = check_fit_files(fit, ("checkpoint.pt", "learning_curve.csv", "fit_manifest.csv", "spatial_receipt.json"))
            val = sources[2 * (inner - 1):2 * inner]
            train = [s for s in sources if s not in val]
            if status.get("target_subject") != subject or status.get("train_subjects") != train or status.get("validation_subjects") != val:
                raise AssertionError("Inner source/validation subject split changed")
            receipt = read_json(fit / "spatial_receipt.json")
            ids = reference.loc[reference.subject.isin(train), "sample_id"].astype(str).tolist()
            validate_spatial_receipt(receipt, method=method, fit_subjects=train,
                                     fit_sample_ids=ids)
            validate_fit_manifest(pd.read_csv(fit / "fit_manifest.csv"), reference,
                                  target=subject, stage="inner", inner_fold=inner,
                                  seed=20260923, epochs=40)
            curves.append(pd.read_csv(fit / "learning_curve.csv"))
        selected = independent_selected_epoch(curves)
        if int(frozen.loc[frozen.subject == subject, "selected_epochs"].iloc[0]) != selected:
            raise AssertionError("Frozen selected epoch differs from independent mean-rank calculation")
        for seed in SEEDS:
            fit = directory / "final" / f"loso_s{subject}" / f"seed_{seed}"
            status = check_fit_files(fit, ("checkpoint.pt", "learning_curve.csv", "fit_manifest.csv", "spatial_receipt.json", "predictions.csv", "metrics.csv", "confusion.csv"))
            if status.get("target_subject") != subject or status.get("train_subjects") != sources or status.get("selected_epochs") != selected:
                raise AssertionError("Final source list or frozen duration changed")
            receipt = read_json(fit / "spatial_receipt.json")
            ids = reference.loc[reference.subject.isin(sources), "sample_id"].astype(str).tolist()
            validate_spatial_receipt(receipt, method=method, fit_subjects=sources,
                                     fit_sample_ids=ids)
            validate_fit_manifest(pd.read_csv(fit / "fit_manifest.csv"), reference,
                                  target=subject, stage="full", inner_fold=None,
                                  seed=seed, epochs=selected)
            frame = pd.read_csv(fit / "predictions.csv")
            row = validate_prediction_frame(frame, reference, subject, seed)
            if (frame.experiment_id.unique().tolist() != ["Q10-E001"]
                    or frame.condition.unique().tolist() != [condition]
                    or frame.fold.unique().tolist() != [f"loso_s{subject}"]
                    or frame.selected_epochs.astype(int).unique().tolist() != [selected]
                    or frame.selection_rule.unique().tolist() != ["mean_rank"]):
                raise AssertionError("Final predictions have wrong experiment or selection metadata")
            saved = pd.read_csv(fit / "metrics.csv")
            validate_saved_metrics(frame, saved, pd.read_csv(fit / "confusion.csv"),
                                   subject=subject, seed=seed, condition=condition)
            saved_ba = float(saved.loc[saved.stratum == "all", "balanced_accuracy"].iloc[0])
            if not np.isclose(saved_ba, row["balanced_accuracy"], atol=1e-12, rtol=0):
                raise AssertionError("Saved BA differs from independent predictions")
            row["condition"] = condition
            row["selected_epochs"] = selected
            rows.append(row)
            predictions.append(frame)
    result = pd.DataFrame(rows)
    if len(result) != 27:
        raise AssertionError("Incomplete 9-subject × 3-seed final grid")
    combined = pd.concat(predictions, ignore_index=True)
    archived = pd.read_csv(directory / "predictions.csv")
    key = ["subject", "seed", "sample_id", "y_true", "y_pred"]
    if not combined[key].sort_values(key).reset_index(drop=True).equals(
        archived[key].sort_values(key).reset_index(drop=True)
    ):
        raise AssertionError("Aggregate predictions differ from per-fit files")
    return result, combined


def paired_summary(candidate: pd.DataFrame, baseline: pd.DataFrame) -> dict:
    keys = ["subject", "seed"]
    merged = candidate.merge(baseline, on=keys, validate="one_to_one", suffixes=("_new", "_q9"))
    if len(merged) != 27:
        raise AssertionError("Q9 comparator lacks a paired 9 × 3 grid")
    delta = merged.groupby("subject", sort=True).apply(
        lambda x: float((x.balanced_accuracy_new - x.balanced_accuracy_q9).mean()),
        include_groups=False,
    ).to_numpy()
    rng = np.random.default_rng(20260924)
    samples = rng.choice(delta, size=(20000, len(delta)), replace=True).mean(axis=1)
    observed = abs(float(delta.mean()))
    flips = np.array(list(itertools.product((-1, 1), repeat=len(delta))), dtype=int)
    p = float(np.mean(np.abs((flips * delta).mean(axis=1)) >= observed - 1e-15))
    return {"paired_subject_deltas": delta.tolist(), "mean_delta": float(delta.mean()),
            "median_delta": float(np.median(delta)),
            "subject_bootstrap_95ci": np.quantile(samples, [0.025, 0.975]).tolist(),
            "exact_sign_flip_two_sided_p_exploratory": p,
            "inference_unit": "nine_target_subjects_not_seeds_or_trials"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    results = args.results_root.resolve()
    report_path = results / "Q10-E001" / "validation_report.json"
    try:
        reference = pd.read_csv(ROOT / "research_runs/Q8-E001/results/trial_metadata.csv")
        if len(reference) != 5184 or reference.sample_id.nunique() != 5184:
            raise AssertionError("Frozen Q8 trial reference is incomplete")
        q8_sources = json.loads((ROOT / "research_runs/Q8-E001/results/source_files.json").read_text(encoding="utf-8"))
        if not isinstance(q8_sources, list) or len(q8_sources) != 18:
            raise AssertionError("Frozen Q8 MAT provenance is incomplete")
        for condition in CONDITIONS:
            q10_record = read_json(results / "Q10-E001" / condition / "source_files.json")
            q10_sources = q10_record["files"]
            if q10_record.get("q8_metadata_sha256") != sha256(ROOT / "research_runs/Q8-E001/results/trial_metadata.csv"):
                raise AssertionError(f"Q8 trial metadata hash changed for {condition}")
            frozen = sorted((Path(item["path"]).name, item["bytes"], item["sha256"])
                            for item in q8_sources)
            current = sorted((Path(item["path"]).name, item["bytes"], item["sha256"])
                             for item in q10_sources)
            if current != frozen:
                raise AssertionError(f"BNCI MAT provenance differs for {condition}")
        result_tables = []
        for condition in CONDITIONS:
            table, _ = audit_condition(results / "Q10-E001", condition, reference)
            result_tables.append(table)
        all_rows = pd.concat(result_tables, ignore_index=True)
        q9 = pd.read_csv(results / "Q9-E001/MU_BETA_SHARED/predictions.csv")
        q9_rows = []
        for (subject, seed), frame in q9.groupby(["subject", "seed"], sort=True):
            validate_prediction_frame(frame, reference, int(subject), int(seed))
            q9_rows.append({"subject": int(subject), "seed": int(seed),
                            "balanced_accuracy": float(balanced_accuracy_score(frame.y_true, frame.y_pred))})
        baseline = pd.DataFrame(q9_rows)
        contrasts = {condition: paired_summary(all_rows.loc[all_rows.condition == condition], baseline)
                     for condition in CONDITIONS}
        output = results / "Q10-E001" / "analysis"
        output.mkdir(parents=True, exist_ok=True)
        all_rows.to_csv(output / "subject_seed_metrics.csv", index=False)
        subject = all_rows.groupby(["condition", "subject"], as_index=False).agg(
            mean_ba=("balanced_accuracy", "mean"), seed_sd_ba=("balanced_accuracy", "std"),
            mean_dominant_prediction_share=("dominant_prediction_share", "mean"),
            zero_recall_seed_count=("zero_recall_classes", lambda x: int((x > 0).sum())),
        )
        subject.to_csv(output / "subject_metrics.csv", index=False)
        with (output / "paired_contrasts.json").open("w", encoding="utf-8") as stream:
            json.dump(contrasts, stream, indent=2)
            stream.write("\n")
        report = {"status": "passed_scientific_checks", "conditions": list(CONDITIONS),
                  "final_fits": 54, "inner_fits": 72, "target_trials_per_fit": 576,
                  "checked_source_only_spatial_receipts": 126,
                  "checked_independent_epoch_selections": 18,
                  "comparison_scope": "exploratory_same_dataset_not_external_confirmation",
                  "analysis_files": ["analysis/subject_seed_metrics.csv", "analysis/subject_metrics.csv",
                                     "analysis/paired_contrasts.json"], "errors": []}
        result_code = 0
    except Exception as exc:  # noqa: BLE001 - validator must always emit a failure receipt
        report = {"status": "failed", "errors": [f"{type(exc).__name__}: {exc}"]}
        result_code = 1
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return result_code


if __name__ == "__main__":
    raise SystemExit(main())
