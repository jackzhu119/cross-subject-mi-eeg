"""Independently audit a completed source-only Q5 EEGNet LOSO run.

This checks the on-disk receipts, not hidden model behavior. In particular, it
cannot prove that an archived training script was the script actually executed.
"""

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
IDENTITY = (
    "sample_id",
    "subject",
    "session",
    "run",
    "trial",
    "label",
    "event_sample",
    "artifact_flagged",
)
METRICS = (
    "balanced_accuracy",
    "accuracy",
    "macro_f1",
    "macro_precision",
    "macro_recall",
    "cohen_kappa",
)
PROBABILITY_COLUMNS = tuple(f"p_class_{label}" for label in (1, 2, 3, 4))


def _require_columns(frame: pd.DataFrame, columns: tuple[str, ...], context: str) -> None:
    absent = set(columns) - set(frame)
    if absent:
        raise AssertionError(f"{context} missing columns: {sorted(absent)}")


def _assert_close(actual: float, expected: float, context: str) -> None:
    if not np.isclose(actual, expected, rtol=1e-8, atol=1e-9, equal_nan=True):
        raise AssertionError(f"{context}: {actual!r} != {expected!r}")


def _scores(y: np.ndarray, pred: np.ndarray, labels: list[int]) -> dict[str, float]:
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


def _check_metadata(meta: pd.DataFrame, reference: pd.DataFrame, subjects: list[int]) -> None:
    _require_columns(meta, IDENTITY, "trial_metadata.csv")
    _require_columns(reference, IDENTITY, "Q4 trial_metadata.csv")
    if meta.sample_id.duplicated().any() or len(meta) != len(subjects) * 576:
        raise AssertionError("Expected 576 unique four-class trials per subject")
    if sorted(meta.subject.unique().tolist()) != subjects:
        raise AssertionError("Q5 subjects differ from config")
    # Q4's IDs, labels, artifact flags, event samples and order are an exact
    # common-population commitment, not just matching marginal counts.
    pd.testing.assert_frame_equal(
        meta.loc[:, IDENTITY].reset_index(drop=True),
        reference.loc[:, IDENTITY].reset_index(drop=True),
        check_dtype=False,
        check_exact=True,
    )
    if not meta.groupby(["subject", "label"]).size().eq(144).all():
        raise AssertionError("Each subject must have 144 trials for each of four classes")
    if not meta.groupby(["subject", "session"]).size().eq(288).all():
        raise AssertionError("Both Q4 sessions must contain 288 trials per subject")


def _check_manifest(
    manifest: pd.DataFrame,
    subjects: list[int],
    selection_seed: int,
    final_seeds: list[int],
    max_epochs: int,
    selected: dict[str, int],
) -> tuple[int, int]:
    _require_columns(
        manifest,
        ("fold", "stage", "inner_fold", "seed", "subject", "role", "n_trials", "epochs_trained"),
        "fit_manifest.csv",
    )
    if manifest.duplicated(["fold", "stage", "inner_fold", "seed", "subject"]).any():
        raise AssertionError("Duplicate subject in a fitted-model manifest")
    if not manifest.n_trials.eq(576).all():
        raise AssertionError("Manifest subject trial count is not 576")
    if set(manifest.stage) != {"inner", "full"}:
        raise AssertionError("Manifest must distinguish inner from full fits")
    n_inner = n_full = 0
    for target in subjects:
        fold = f"loso_s{target}"
        frame = manifest.loc[manifest.fold == fold]
        if frame.empty:
            raise AssertionError(f"No fit receipts for {fold}")
        inner = frame.loc[frame.stage == "inner"]
        full = frame.loc[frame.stage == "full"]
        if not inner.seed.eq(selection_seed).all():
            raise AssertionError(f"Inner fitting uses a non-selection seed: {fold}")
        if inner.inner_fold.isna().any() or inner.inner_fold.nunique() != 4:
            raise AssertionError(f"Expected four separate inner validation fits: {fold}")
        for inner_fold, fit in inner.groupby("inner_fold", dropna=False):
            _check_fit_subjects(fit, subjects, target, train_count=6, validation_count=2)
            if not fit.epochs_trained.eq(max_epochs).all():
                raise AssertionError(f"Inner fit did not complete max_epochs: {fold}/{inner_fold}")
            n_inner += 1
        if full.inner_fold.notna().any() or set(full.seed) != set(final_seeds):
            raise AssertionError(f"Full-fit seed or inner_fold mismatch: {fold}")
        for seed, fit in full.groupby("seed"):
            _check_fit_subjects(fit, subjects, target, train_count=8, validation_count=0)
            if not fit.epochs_trained.eq(selected[fold]).all():
                raise AssertionError(f"Full fit did not use selected epoch: {fold}/{seed}")
            n_full += 1
    if set(manifest.fold) != {f"loso_s{s}" for s in subjects}:
        raise AssertionError("Unexpected outer fold in fit manifest")
    return n_inner, n_full


def _check_fit_subjects(
    fit: pd.DataFrame,
    subjects: list[int],
    target: int,
    *,
    train_count: int,
    validation_count: int,
) -> None:
    if len(fit) != len(subjects) or set(fit.subject) != set(subjects):
        raise AssertionError("Fitted model does not account for every subject exactly once")
    actual = fit.groupby("role").subject.apply(set).to_dict()
    if actual.get("train", set()) & {target} or actual.get("validation", set()) & {target}:
        raise AssertionError(f"Target subject {target} entered training or validation")
    if len(actual.get("train", set())) != train_count or len(
        actual.get("validation", set())
    ) != validation_count:
        raise AssertionError("Incorrect number of source training/validation subjects")
    target_role = "outer_test_excluded" if validation_count else "test"
    if actual.get(target_role, set()) != {target} or set(actual) != (
        {"train", "validation", target_role}
        if validation_count
        else {"train", target_role}
    ):
        raise AssertionError("Incorrect target role or an unexpected fit role")


def _check_selection_and_curves(
    selection: pd.DataFrame,
    curves: pd.DataFrame,
    subjects: list[int],
    selection_seed: int,
    final_seeds: list[int],
    max_epochs: int,
) -> dict[str, int]:
    _require_columns(selection, ("fold", "selected_epochs", "validation_ce"), "selection.csv")
    _require_columns(
        curves,
        ("fold", "stage", "inner_fold", "seed", "epoch", "train_ce", "val_ce"),
        "learning_curves.csv",
    )
    expected_folds = {f"loso_s{s}" for s in subjects}
    if len(selection) != len(subjects) or set(selection.fold) != expected_folds:
        raise AssertionError("Expected one source-only selection record per outer fold")
    if selection.fold.duplicated().any():
        raise AssertionError("Duplicate selection row")
    if curves.duplicated(["fold", "stage", "inner_fold", "seed", "epoch"]).any():
        raise AssertionError("Duplicate epoch in learning curves")
    if not np.isfinite(curves.train_ce.to_numpy(dtype=float)).all():
        raise AssertionError("Non-finite training loss")
    chosen = {}
    for target in subjects:
        fold = f"loso_s{target}"
        inner = curves.loc[(curves.fold == fold) & (curves.stage == "inner")]
        full = curves.loc[(curves.fold == fold) & (curves.stage == "full")]
        if inner.inner_fold.nunique() != 4 or not inner.seed.eq(selection_seed).all():
            raise AssertionError(f"Incomplete or wrong-seed inner curves: {fold}")
        if not np.isfinite(inner.val_ce.to_numpy(dtype=float)).all():
            raise AssertionError(f"Non-finite inner validation loss: {fold}")
        epoch_set = set(range(1, max_epochs + 1))
        for _, group in inner.groupby("inner_fold"):
            if len(group) != max_epochs or set(group.epoch) != epoch_set:
                raise AssertionError(f"Inner loss trajectory is incomplete: {fold}")
        mean_loss = inner.groupby("epoch").val_ce.mean().sort_index()
        best_epoch = int(mean_loss.idxmin())  # pandas chooses earliest exact minimum.
        row = selection.loc[selection.fold == fold].iloc[0]
        if int(row.selected_epochs) != best_epoch:
            raise AssertionError(f"Selected epoch is not source-validation minimum: {fold}")
        _assert_close(float(row.validation_ce), float(mean_loss.loc[best_epoch]), f"{fold} CE")
        chosen[fold] = best_epoch
        if full.inner_fold.notna().any() or set(full.seed) != set(final_seeds):
            raise AssertionError(f"Unexpected full-fit curve seeds: {fold}")
        if not full.val_ce.isna().all():
            raise AssertionError(f"Full-fit curve used validation data: {fold}")
        for _, group in full.groupby("seed"):
            if len(group) != best_epoch or set(group.epoch) != set(range(1, best_epoch + 1)):
                raise AssertionError(f"Full-fit epoch trajectory differs from selection: {fold}")
    if set(curves.fold) != expected_folds or set(curves.stage) != {"inner", "full"}:
        raise AssertionError("Unexpected fold/stage in learning curves")
    return chosen


def _check_predictions(
    predictions: pd.DataFrame,
    meta: pd.DataFrame,
    subjects: list[int],
    seeds: list[int],
) -> None:
    _require_columns(
        predictions,
        (*IDENTITY, "fold", "seed", "y_true", "y_pred", *PROBABILITY_COLUMNS),
        "predictions.csv",
    )
    if len(predictions) != len(meta) * len(seeds):
        raise AssertionError("Missing or excess target predictions")
    if predictions.duplicated(["sample_id", "seed"]).any():
        raise AssertionError("A trial has duplicate predictions for the same seed")
    if set(predictions.seed) != set(seeds):
        raise AssertionError("Prediction seed set differs from config")
    for seed, group in predictions.groupby("seed"):
        if set(group.sample_id) != set(meta.sample_id):
            raise AssertionError(f"Seed {seed} does not predict every trial exactly once")
    joint = predictions.merge(meta.loc[:, IDENTITY], on="sample_id", validate="many_to_one", suffixes=("", "_meta"))
    if len(joint) != len(predictions):
        raise AssertionError("Predictions include unknown trial IDs")
    for key in IDENTITY[1:]:
        if not joint[key].equals(joint[f"{key}_meta"]):
            raise AssertionError(f"Predicted {key} disagrees with Q4-matched metadata")
    if not joint.y_true.eq(joint.label).all():
        raise AssertionError("Prediction truth differs from trial label")
    if not joint.fold.eq("loso_s" + joint.subject.astype(str)).all():
        raise AssertionError("A trial was predicted outside its held-out-subject fold")
    prob = joint.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    if (
        not np.isfinite(prob).all()
        or np.any(prob < -1e-9)
        or np.any(prob > 1 + 1e-9)
        or not np.allclose(prob.sum(axis=1), 1, rtol=0, atol=1e-5)
    ):
        raise AssertionError("Invalid or unnormalized prediction probabilities")
    predicted = np.argmax(prob, axis=1) + 1
    if not np.array_equal(predicted, joint.y_pred.to_numpy(dtype=int)):
        raise AssertionError("Predicted labels do not match probability argmax")
    if not joint.y_pred.isin([1, 2, 3, 4]).all():
        raise AssertionError("Invalid predicted class")


def _check_metrics(
    predictions: pd.DataFrame, reported: pd.DataFrame, subjects: list[int], seeds: list[int]
) -> int:
    _require_columns(
        reported,
        (
            "fold", "subject", "seed", "model", "stratum", "n_train", "n_test",
            "n_classes_present", *METRICS,
        ),
        "per_subject_metrics.csv",
    )
    if reported.duplicated(["fold", "seed", "stratum"]).any():
        raise AssertionError("Duplicate subject/seed/stratum metric")
    n_checks = 0
    expected_keys = set()
    for target in subjects:
        fold = f"loso_s{target}"
        for seed in seeds:
            trial_predictions = predictions.loc[
                (predictions.fold == fold) & (predictions.seed == seed)
            ]
            if len(trial_predictions) != 576:
                raise AssertionError(f"Incomplete target predictions: {fold}/{seed}")
            for stratum in ("all", "unflagged", "flagged"):
                subset = (
                    trial_predictions
                    if stratum == "all"
                    else trial_predictions.loc[
                        trial_predictions.artifact_flagged.eq(stratum == "flagged")
                    ]
                )
                if subset.empty:
                    continue
                expected_keys.add((fold, seed, stratum))
                row = reported.loc[
                    (reported.fold == fold)
                    & (reported.seed == seed)
                    & (reported.stratum == stratum)
                ]
                if len(row) != 1:
                    raise AssertionError(f"Missing metric row: {fold}/{seed}/{stratum}")
                row = row.iloc[0]
                if (
                    int(row.subject) != target
                    or row.model != "EEGNet"
                    or int(row.n_train) != (len(subjects) - 1) * 576
                    or int(row.n_test) != len(subset)
                    or int(row.n_classes_present) != subset.y_true.nunique()
                ):
                    raise AssertionError(f"Incorrect metric identity or denominator: {fold}/{seed}/{stratum}")
                scores = _scores(subset.y_true.to_numpy(), subset.y_pred.to_numpy(), [1, 2, 3, 4])
                for metric in METRICS:
                    _assert_close(float(row[metric]), scores[metric], f"{fold}/{seed}/{stratum}/{metric}")
                    n_checks += 1
    observed = set(zip(reported.fold, reported.seed, reported.stratum, strict=True))
    if observed != expected_keys:
        raise AssertionError("Unexpected or missing per-subject metric rows")
    return n_checks


def _check_confusions(
    predictions: pd.DataFrame, saved: pd.DataFrame, subjects: list[int], seeds: list[int]
) -> int:
    _require_columns(
        saved,
        ("fold", "subject", "seed", "model", "stratum", "true_label", "predicted_label", "count"),
        "confusion_matrices.csv",
    )
    n_checks = 0
    for target in subjects:
        fold = f"loso_s{target}"
        for seed in seeds:
            part = predictions.loc[(predictions.fold == fold) & (predictions.seed == seed)]
            for stratum in ("all", "unflagged", "flagged"):
                subset = (
                    part
                    if stratum == "all"
                    else part.loc[part.artifact_flagged.eq(stratum == "flagged")]
                )
                cells = saved.loc[
                    (saved.fold == fold) & (saved.seed == seed) & (saved.stratum == stratum)
                ]
                if subset.empty:
                    if not cells.empty:
                        raise AssertionError("Confusion matrix supplied for an empty stratum")
                    continue
                if len(cells) != 16 or cells.duplicated(["true_label", "predicted_label"]).any():
                    raise AssertionError("Incomplete or duplicate four-class confusion cells")
                if not cells.subject.eq(target).all() or not cells.model.eq("EEGNet").all():
                    raise AssertionError("Confusion-matrix identity mismatch")
                actual = confusion_matrix(subset.y_true, subset.y_pred, labels=[1, 2, 3, 4])
                for _, cell in cells.iterrows():
                    i, j = int(cell.true_label) - 1, int(cell.predicted_label) - 1
                    if i not in range(4) or j not in range(4) or int(cell["count"]) != actual[i, j]:
                        raise AssertionError("Confusion matrix differs from trial predictions")
                    n_checks += 1
    return n_checks


def _check_hashes(output: Path, reference: Path, expected_subjects: int) -> tuple[int, int]:
    current = json.loads((output / "source_files.json").read_text(encoding="utf-8"))
    original = json.loads((reference / "source_files.json").read_text(encoding="utf-8"))
    if len(current) != len(original) or len(current) != expected_subjects * 2:
        raise AssertionError("Raw MAT file inventories differ")
    original_hashes = {Path(item["path"]).name: item["sha256"] for item in original}
    if len(original_hashes) != len(original):
        raise AssertionError("Q4 MAT filenames are not unique")
    for item in current:
        path = Path(item["path"])
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or path.name not in original_hashes
            or original_hashes[path.name] != item["sha256"]
        ):
            raise AssertionError(f"Changed or missing Q4-comparable MAT: {path}")
        with path.open("rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != item["sha256"]:
                raise AssertionError(f"On-disk MAT SHA-256 differs: {path}")
    snapshot = output / "provenance/manifest.json"
    if not snapshot.is_file():
        raise AssertionError("Missing source/config snapshot manifest")
    provenance = json.loads(snapshot.read_text(encoding="utf-8"))
    records = provenance["source_files"]
    if not records:
        raise AssertionError("Empty code snapshot")
    for item in records:
        archived = output / "provenance/source" / item["path"]
        if not archived.is_file() or archived.stat().st_size != item["bytes"]:
            raise AssertionError(f"Snapshot file missing or resized: {item['path']}")
        with archived.open("rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != item["sha256"]:
                raise AssertionError(f"Snapshot hash differs: {item['path']}")
    return len(current), len(records)


def verify(output: Path, reference: Path = ROOT / "outputs/Q4-E001") -> dict:
    config = json.loads((output / "config.json").read_text(encoding="utf-8"))
    status = json.loads((output / "status.json").read_text(encoding="utf-8"))
    if status["status"] != "complete":
        raise AssertionError("Q5 run is not complete")
    if not status.get("q5_complete", False):
        raise AssertionError("Q5 status does not certify all outer folds complete")
    subjects = sorted(config["subjects"])
    if subjects != list(range(1, 10)) or sorted(config["class_ids"].values()) != [1, 2, 3, 4]:
        raise AssertionError("Unexpected subjects or class mapping")
    training = config["training"]
    final_seeds = training["final_seeds"]
    selection_seed = int(training["selection_seed"])
    max_epochs = int(training["max_epochs"])
    if len(final_seeds) != 3 or len(set(final_seeds)) != 3 or max_epochs < 1:
        raise AssertionError("Expected three distinct final seeds and a positive epoch budget")
    meta = pd.read_csv(output / "trial_metadata.csv")
    q4 = pd.read_csv(reference / "trial_metadata.csv")
    _check_metadata(meta, q4, subjects)
    selection = pd.read_csv(output / "selection.csv")
    curves = pd.read_csv(output / "learning_curves.csv")
    chosen = _check_selection_and_curves(
        selection, curves, subjects, selection_seed, final_seeds, max_epochs
    )
    manifest = pd.read_csv(output / "fit_manifest.csv")
    n_inner, n_full = _check_manifest(
        manifest, subjects, selection_seed, final_seeds, max_epochs, chosen
    )
    predictions = pd.read_csv(output / "predictions.csv")
    _check_predictions(predictions, meta, subjects, final_seeds)
    reported = pd.read_csv(output / "per_subject_metrics.csv")
    n_metric_checks = _check_metrics(predictions, reported, subjects, final_seeds)
    cm_path = output / "confusion_matrices.csv"
    n_confusion_checks = (
        _check_confusions(predictions, pd.read_csv(cm_path), subjects, final_seeds)
        if cm_path.is_file()
        else 0
    )
    n_mat, n_snapshot = _check_hashes(output, reference, len(subjects))
    return {
        "status": "passed",
        "n_subjects": len(subjects),
        "n_trials": len(meta),
        "n_flagged": int(meta.artifact_flagged.sum()),
        "n_inner_fits": n_inner,
        "n_full_fits": n_full,
        "n_predictions": len(predictions),
        "n_metric_scalar_checks": n_metric_checks,
        "n_confusion_cell_checks": n_confusion_checks,
        "n_raw_mat_hashes": n_mat,
        "n_snapshot_source_hashes": n_snapshot,
        "independence_note": (
            "Three seeds per subject quantify training variability; 27 trained models are not "
            "27 independent people. Receipts and hashes are audited but do not prove "
            "unlogged training behavior or external-dataset generalization."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, nargs="?", default=ROOT / "results/Q5-E001")
    parser.add_argument("--reference", type=Path, default=ROOT / "outputs/Q4-E001")
    args = parser.parse_args()
    report = verify(args.output, args.reference)
    (args.output / "validation_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
