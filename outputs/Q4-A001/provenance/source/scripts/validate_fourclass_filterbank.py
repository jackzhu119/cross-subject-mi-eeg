"""Independently audit the completed Q4 four-class LOSO predictions and fit receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

ROOT = Path(__file__).resolve().parents[1]
METRICS = (
    "balanced_accuracy",
    "accuracy",
    "macro_f1",
    "macro_precision",
    "macro_recall",
    "cohen_kappa",
)


def scores(y: np.ndarray, pred: np.ndarray, labels: list[int]) -> dict[str, float]:
    return {
        "balanced_accuracy": balanced_accuracy_score(y, pred),
        "accuracy": accuracy_score(y, pred),
        "macro_f1": f1_score(y, pred, labels=labels, average="macro", zero_division=0),
        "macro_precision": precision_score(
            y, pred, labels=labels, average="macro", zero_division=0
        ),
        "macro_recall": recall_score(y, pred, labels=labels, average="macro", zero_division=0),
        "cohen_kappa": cohen_kappa_score(y, pred, labels=labels),
    }


def close(actual: float, expected: float, context: str) -> None:
    if not np.isclose(actual, expected, rtol=1e-9, atol=1e-10, equal_nan=True):
        raise AssertionError(f"{context}: {actual} != {expected}")


def verify(output: Path, *, expected_subjects: int = 9) -> dict:
    config = json.loads((output / "config.json").read_text(encoding="utf-8"))
    status = json.loads((output / "status.json").read_text(encoding="utf-8"))
    if status["status"] != "complete":
        raise AssertionError(f"Experiment is not complete: {status}")
    labels = sorted(config["class_ids"].values())
    if labels != [1, 2, 3, 4]:
        raise AssertionError("Four-class code mapping differs from expected dataset events")
    model_names = [item["name"] for item in config["models"]]
    if len(set(model_names)) != len(model_names):
        raise AssertionError("Duplicate model names")
    meta = pd.read_csv(output / "trial_metadata.csv")
    predictions = pd.read_csv(output / "predictions.csv")
    manifest = pd.read_csv(output / "fit_manifest.csv")
    reported = pd.read_csv(output / "per_subject_metrics.csv")
    summary = pd.read_csv(output / "summary.csv")
    confusions = pd.read_csv(output / "confusion_matrices.csv")
    audit = pd.read_csv(output / "data_audit.csv")
    subjects = sorted(meta.subject.unique().tolist())
    if subjects != config["subjects"] or len(subjects) != expected_subjects:
        raise AssertionError("Subject coverage differs from config")
    if len(meta) != expected_subjects * 576 or meta.sample_id.duplicated().any():
        raise AssertionError("Expected 576 unique four-class trials per subject")
    if meta.groupby(["subject", "label"]).size().ne(144).any():
        raise AssertionError("Four-class balance per subject is incorrect")
    if not set(meta.session) == {"0train", "1test"}:
        raise AssertionError("Both sessions are required")
    if not meta.groupby(["subject", "session"]).size().eq(288).all():
        raise AssertionError("Expected 288 four-class trials per subject/session")
    if len(audit) != expected_subjects * 12 or audit.n_kept_trials.sum() != len(meta):
        raise AssertionError("Run audit is incomplete or inconsistent")
    if int(meta.artifact_flagged.sum()) != int(audit.n_flagged_trials.sum()):
        raise AssertionError("Expert flag count differs from run audit")
    if audit.n_rejected_trials.sum() != 0 or not audit.artifact_policy.eq("include_all").all():
        raise AssertionError("Primary analysis must include all trials")
    if len(predictions) != len(meta) * len(model_names):
        raise AssertionError("Prediction count differs from model x trial coverage")
    if predictions.duplicated(["sample_id", "model"]).any():
        raise AssertionError("Duplicate prediction for a model and trial")
    if not predictions.model.isin(model_names).all():
        raise AssertionError("Unexpected model in predictions")
    expected_ids = set(meta.sample_id)
    for name, group in predictions.groupby("model"):
        if set(group.sample_id) != expected_ids:
            raise AssertionError(f"Model {name} does not cover every trial once")
    joint = predictions.merge(meta, on="sample_id", validate="many_to_one", suffixes=("", "_meta"))
    if len(joint) != len(predictions):
        raise AssertionError("Unknown prediction IDs")
    for key in ("subject", "session", "run", "trial", "label", "artifact_flagged"):
        if not joint[key].equals(joint[f"{key}_meta"]):
            raise AssertionError(f"Prediction {key} does not match trial metadata")
    if not (joint.y_true == joint.label).all() or not joint.y_pred.isin(labels).all():
        raise AssertionError("Prediction labels are invalid")
    if (
        manifest.duplicated(["fold", "sample_id"]).any()
        or len(manifest) != len(meta) * expected_subjects
    ):
        raise AssertionError("Fit manifest is incomplete or duplicated")
    tested_ids = set()
    n_score_checks = 0
    n_scaler_checks = 0
    for target in subjects:
        fold = f"loso_s{target}"
        fold_dir = output / "folds" / fold
        split = manifest[manifest.fold == fold]
        if len(split) != len(meta) or set(split.sample_id) != expected_ids:
            raise AssertionError(f"Incomplete manifest: {fold}")
        train = split[split.role == "train"]
        test = split[split.role == "test"]
        if len(train) != (expected_subjects - 1) * 576 or len(test) != 576:
            raise AssertionError(f"Incorrect LOSO row counts: {fold}")
        if set(train.subject) != set(subjects) - {target} or set(test.subject) != {target}:
            raise AssertionError(f"Target subject crossed fit boundary: {fold}")
        if set(train.sample_id).intersection(test.sample_id):
            raise AssertionError("Train and test sample IDs overlap")
        tested_ids.update(test.sample_id)
        fold_manifest = pd.read_csv(fold_dir / "fit_manifest.csv")
        pd.testing.assert_frame_equal(
            split.reset_index(drop=True), fold_manifest, check_dtype=False
        )
        fold_predictions = pd.read_csv(fold_dir / "predictions.csv")
        subset_saved = predictions[predictions.fold == fold].reset_index(drop=True)
        pd.testing.assert_frame_equal(subset_saved, fold_predictions, check_dtype=False)
        if len(subset_saved) != len(model_names) * 576:
            raise AssertionError("Missing fold predictions")
        band_features = {}
        for band in config["preprocessing"]["bands"]:
            with np.load(fold_dir / f"csp_{band}.npz", allow_pickle=False) as fitted:
                if fitted["filters"].shape != (22, 22) or fitted["patterns"].shape != (22, 22):
                    raise AssertionError("Unexpected spatial-filter dimensions")
                if not np.array_equal(fitted["sample_ids"], meta.sample_id.to_numpy(dtype=str)):
                    raise AssertionError("Cached CSP features have different trial order")
                band_features[band] = fitted["features"].copy()
            if band_features[band].shape != (len(meta), config["csp"]["n_components"]):
                raise AssertionError("Unexpected CSP feature dimensions")
        source_mask = meta.subject.ne(target).to_numpy()
        for model in config["models"]:
            name = model["name"]
            receipt = json.loads((fold_dir / f"model_{name}.json").read_text(encoding="utf-8"))
            if (
                receipt["fold"] != fold
                or receipt["model"] != name
                or receipt["bands"] != model["bands"]
            ):
                raise AssertionError("Model receipt identity differs from config")
            if receipt["fit_rows"] != len(train) or receipt["test_rows"] != len(test):
                raise AssertionError("Model fit row count is wrong")
            matrix = np.concatenate([band_features[b] for b in model["bands"]], axis=1)
            selected = receipt["selected_feature_indices"]
            if receipt["n_input_features"] != matrix.shape[1] or receipt[
                "n_selected_features"
            ] != len(selected):
                raise AssertionError("Feature dimensionality receipt is wrong")
            if model["select_k"] is None:
                if selected != list(range(matrix.shape[1])) or receipt["mi_scores"] is not None:
                    raise AssertionError("Non-selection model unexpectedly selected features")
            else:
                mi = np.asarray(receipt["mi_scores"])
                if (
                    len(mi) != matrix.shape[1]
                    or selected != np.argsort(-mi, kind="stable")[: model["select_k"]].tolist()
                ):
                    raise AssertionError("MI selection differs from stored source scores")
            from_train = matrix[source_mask][:, selected]
            np.testing.assert_allclose(
                receipt["scaler_mean"], from_train.mean(axis=0), rtol=1e-9, atol=1e-12
            )
            np.testing.assert_allclose(
                receipt["scaler_scale"], from_train.std(axis=0), rtol=1e-9, atol=1e-12
            )
            n_scaler_checks += 1
            pred = subset_saved[subset_saved.model == name]
            if len(pred) != 576 or set(pred.sample_id) != set(test.sample_id):
                raise AssertionError("Model target predictions are incomplete")
            for stratum in ("all", "unflagged", "flagged"):
                values = (
                    pred
                    if stratum == "all"
                    else pred[pred.artifact_flagged == (stratum == "flagged")]
                )
                recorded = reported[
                    (reported.subject == target)
                    & (reported.model == name)
                    & (reported.stratum == stratum)
                ]
                if values.empty:
                    if not recorded.empty:
                        raise AssertionError("Empty stratum has a reported score")
                    continue
                if len(recorded) != 1 or int(recorded.iloc[0].n_test) != len(values):
                    raise AssertionError("Metric row missing or wrong denominator")
                independent = scores(values.y_true.to_numpy(), values.y_pred.to_numpy(), labels)
                for metric in METRICS:
                    close(
                        recorded.iloc[0][metric],
                        independent[metric],
                        f"{fold}/{name}/{stratum}/{metric}",
                    )
                    n_score_checks += 1
                cm = confusion_matrix(values.y_true, values.y_pred, labels=labels)
                saved_cm = confusions[
                    (confusions.subject == target)
                    & (confusions.model == name)
                    & (confusions.stratum == stratum)
                ]
                if len(saved_cm) != 16:
                    raise AssertionError("Incomplete four-class confusion matrix")
                for i, true_label in enumerate(labels):
                    for j, predicted_label in enumerate(labels):
                        cell = saved_cm[
                            (saved_cm.true_label == true_label)
                            & (saved_cm.predicted_label == predicted_label)
                        ]
                        if len(cell) != 1 or int(cell.iloc[0]["count"]) != cm[i, j]:
                            raise AssertionError("Confusion cell does not match predictions")
    if tested_ids != expected_ids:
        raise AssertionError("Outer folds do not test every trial exactly once")
    aggregate = reported.groupby(["model", "stratum"])[list(METRICS)].agg(["mean", "std"])
    aggregate.columns = [f"{m}_{stat}" for m, stat in aggregate.columns]
    merged = summary.merge(
        aggregate.reset_index(),
        on=["model", "stratum"],
        validate="one_to_one",
        suffixes=("_saved", "_check"),
    )
    if len(merged) != len(summary) or len(summary) != len(model_names) * 3:
        raise AssertionError("Summary model/stratum coverage is incomplete")
    for metric in METRICS:
        for stat in ("mean", "std"):
            col = f"{metric}_{stat}"
            for _, row in merged.iterrows():
                close(
                    row[f"{col}_saved"],
                    row[f"{col}_check"],
                    f"summary/{row.model}/{row.stratum}/{col}",
                )
    source_files = json.loads((output / "source_files.json").read_text(encoding="utf-8"))
    if len(source_files) != expected_subjects * 2:
        raise AssertionError("Source MAT inventory is incomplete")
    for item in source_files:
        path = Path(item["path"])
        if not path.is_file() or path.stat().st_size != item["bytes"]:
            raise AssertionError(f"Source data changed: {path}")
        with path.open("rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != item["sha256"]:
                raise AssertionError(f"Source data hash changed: {path}")
    provenance = json.loads((output / "provenance/manifest.json").read_text(encoding="utf-8"))
    for item in provenance["source_files"]:
        archived = output / "provenance/source" / item["path"]
        if (
            not archived.is_file()
            or hashlib.sha256(archived.read_bytes()).hexdigest() != item["sha256"]
        ):
            raise AssertionError(f"Startup source snapshot mismatch: {item['path']}")
    if (
        json.loads(
            (output / "provenance/source/configs/q4_e001_fourclass_filterbank.json").read_text(
                encoding="utf-8"
            )
        )
        != config
    ):
        raise AssertionError("Run config differs from archived startup config")
    return {
        "status": "passed",
        "n_subjects": len(subjects),
        "n_trials": len(meta),
        "n_flagged": int(meta.artifact_flagged.sum()),
        "n_models": len(model_names),
        "n_predictions": len(predictions),
        "n_metric_scalar_checks": n_score_checks,
        "n_scaler_fit_checks": n_scaler_checks,
        "n_source_mat_hashes": len(source_files),
        "n_snapshot_source_hashes": len(provenance["source_files"]),
        "note": "Deterministic source snapshots and fit boundaries checked; not proof of independent external generalization.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, nargs="?", default=ROOT / "outputs/Q4-E001")
    parser.add_argument("--expected-subjects", type=int, default=9)
    args = parser.parse_args()
    report = verify(args.output, expected_subjects=args.expected_subjects)
    (args.output / "validation_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
