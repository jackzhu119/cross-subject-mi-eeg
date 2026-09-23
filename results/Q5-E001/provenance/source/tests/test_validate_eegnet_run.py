"""Synthetic receipts exercise Q5's independent boundary and score auditor."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.validate_eegnet_run import (
    _check_manifest,
    _check_metadata,
    _check_metrics,
    _check_predictions,
    _check_selection_and_curves,
    _scores,
)

SUBJECTS = list(range(1, 10))
SEEDS = [101, 102, 103]
SELECTION_SEED = 77
MAX_EPOCHS = 3


@pytest.fixture(scope="module")
def receipts() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    meta_rows = []
    for subject in SUBJECTS:
        for trial in range(576):
            session = "0train" if trial < 288 else "1test"
            meta_rows.append(
                {
                    "sample_id": f"s{subject:02d}_{session}_t{trial:03d}",
                    "subject": subject,
                    "session": session,
                    "run": trial // 48,
                    "trial": trial,
                    "label": trial % 4 + 1,
                    "event_sample": 250 + 750 * trial,
                    "artifact_flagged": trial % 11 == 0,
                }
            )
    meta = pd.DataFrame(meta_rows)
    manifest_rows, curve_rows, selection_rows, prediction_parts = [], [], [], []
    for target in SUBJECTS:
        fold = f"loso_s{target}"
        sources = [s for s in SUBJECTS if s != target]
        for inner_fold in range(1, 5):
            held = set(sources[(inner_fold - 1) * 2 : inner_fold * 2])
            for subject in SUBJECTS:
                role = (
                    "outer_test_excluded"
                    if subject == target
                    else ("validation" if subject in held else "train")
                )
                manifest_rows.append(
                    {
                        "fold": fold,
                        "stage": "inner",
                        "inner_fold": inner_fold,
                        "seed": SELECTION_SEED,
                        "subject": subject,
                        "role": role,
                        "n_trials": 576,
                        "epochs_trained": MAX_EPOCHS,
                    }
                )
            for epoch, loss in enumerate([0.9, 0.5, 0.6], start=1):
                curve_rows.append(
                    {
                        "fold": fold,
                        "stage": "inner",
                        "inner_fold": inner_fold,
                        "seed": SELECTION_SEED,
                        "epoch": epoch,
                        "train_ce": loss / 2,
                        "val_ce": loss,
                    }
                )
        selection_rows.append(
            {"fold": fold, "selected_epochs": 2, "validation_ce": 0.5}
        )
        for seed in SEEDS:
            for subject in SUBJECTS:
                manifest_rows.append(
                    {
                        "fold": fold,
                        "stage": "full",
                        "inner_fold": np.nan,
                        "seed": seed,
                        "subject": subject,
                        "role": "test" if subject == target else "train",
                        "n_trials": 576,
                        "epochs_trained": 2,
                    }
                )
            for epoch in (1, 2):
                curve_rows.append(
                    {
                        "fold": fold,
                        "stage": "full",
                        "inner_fold": np.nan,
                        "seed": seed,
                        "epoch": epoch,
                        "train_ce": 0.7 / epoch,
                        "val_ce": np.nan,
                    }
                )
            trial_rows = meta.loc[meta.subject == target].copy()
            trial_rows["fold"] = fold
            trial_rows["seed"] = seed
            trial_rows["y_true"] = trial_rows.label
            trial_rows["y_pred"] = trial_rows.label
            for label in range(1, 5):
                trial_rows[f"p_class_{label}"] = trial_rows.label.eq(label).astype(float)
            prediction_parts.append(trial_rows)
    return (
        meta,
        pd.DataFrame(manifest_rows),
        pd.DataFrame(curve_rows),
        pd.DataFrame(selection_rows),
        pd.concat(prediction_parts, ignore_index=True),
    )


def _reported_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (fold, seed), part in predictions.groupby(["fold", "seed"]):
        for stratum in ("all", "unflagged", "flagged"):
            subset = (
                part
                if stratum == "all"
                else part.loc[part.artifact_flagged.eq(stratum == "flagged")]
            )
            rows.append(
                {
                    "fold": fold,
                    "subject": int(part.subject.iloc[0]),
                    "seed": seed,
                    "model": "EEGNet",
                    "stratum": stratum,
                    "n_train": 8 * 576,
                    "n_test": len(subset),
                    "n_classes_present": subset.y_true.nunique(),
                    **_scores(subset.y_true.to_numpy(), subset.y_pred.to_numpy(), [1, 2, 3, 4]),
                }
            )
    return pd.DataFrame(rows)


def test_coherent_q5_receipts_pass(receipts) -> None:
    meta, manifest, curves, selection, predictions = receipts
    _check_metadata(meta, meta.copy(), SUBJECTS)
    chosen = _check_selection_and_curves(
        selection, curves, SUBJECTS, SELECTION_SEED, SEEDS, MAX_EPOCHS
    )
    assert set(chosen.values()) == {2}
    assert _check_manifest(
        manifest, SUBJECTS, SELECTION_SEED, SEEDS, MAX_EPOCHS, chosen
    ) == (36, 27)
    _check_predictions(predictions, meta, SUBJECTS, SEEDS)
    assert _check_metrics(predictions, _reported_metrics(predictions), SUBJECTS, SEEDS) == 486


def test_target_cannot_enter_inner_validation(receipts) -> None:
    _, original, _, _, _ = receipts
    changed = original.copy()
    row = changed.index[
        changed.fold.eq("loso_s1")
        & changed.stage.eq("inner")
        & changed.inner_fold.eq(1)
        & changed.subject.eq(1)
    ][0]
    changed.loc[row, "role"] = "validation"
    with pytest.raises(AssertionError, match="Target subject 1 entered"):
        _check_manifest(
            changed, SUBJECTS, SELECTION_SEED, SEEDS, MAX_EPOCHS,
            {f"loso_s{s}": 2 for s in SUBJECTS},
        )


def test_selection_cannot_use_nonminimum_epoch(receipts) -> None:
    _, _, curves, original, _ = receipts
    changed = original.copy()
    changed.loc[changed.fold.eq("loso_s1"), "selected_epochs"] = 3
    with pytest.raises(AssertionError, match="source-validation minimum"):
        _check_selection_and_curves(
            changed, curves, SUBJECTS, SELECTION_SEED, SEEDS, MAX_EPOCHS
        )


def test_wrong_probability_or_metric_fails(receipts) -> None:
    meta, _, _, _, original = receipts
    changed = original.copy()
    changed.loc[0, "p_class_1"] = 0.1
    with pytest.raises(AssertionError, match="unnormalized"):
        _check_predictions(changed, meta, SUBJECTS, SEEDS)
    reported = _reported_metrics(original)
    reported.loc[0, "balanced_accuracy"] = 0.01
    with pytest.raises(AssertionError, match="balanced_accuracy"):
        _check_metrics(original, reported, SUBJECTS, SEEDS)


def test_q4_identity_mismatch_fails(receipts) -> None:
    meta, *_ = receipts
    reference = meta.copy()
    reference.loc[0, "artifact_flagged"] = not bool(reference.loc[0, "artifact_flagged"])
    with pytest.raises(AssertionError):
        _check_metadata(meta, reference, SUBJECTS)
