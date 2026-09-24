"""Synthetic-only Q10-E001 protocol and scientific-validator tests; no GPU required."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts import q10_e001_batch
from scripts.q9_spatial_features import fit_projector_pair
from scripts.validate_q10_e001 import (
    independent_selected_epoch,
    validate_fit_manifest,
    validate_prediction_frame,
    validate_saved_metrics,
    validate_spatial_receipt,
)

ROOT = Path(__file__).resolve().parents[1]


def test_q10_matrix_and_queue_counts(monkeypatch: pytest.MonkeyPatch,
                                     capsys: pytest.CaptureFixture[str]) -> None:
    matrix = json.loads((ROOT / "research_runs/Q10-E001/MATRIX.json").read_text())
    assert matrix["experiment_id"] == "Q10-E001"
    assert matrix["analysis_scope"].startswith("exploratory_")
    assert len(matrix["conditions"]) == 2
    assert sum(row["inner_fits"] for row in matrix["conditions"]) == 72
    assert sum(row["final_fits"] for row in matrix["conditions"]) == 54
    monkeypatch.setattr(sys, "argv", ["q10_e001_batch.py", "--data-dir", "data/raw", "--plan-only"])
    assert q10_e001_batch.main() == 0
    planned = json.loads(capsys.readouterr().out)
    assert planned["fit_counts"] == {"deep_inner": 72, "deep_final": 54,
                                    "shallow_source": 0}
    assert [(job["condition"], job["phase"]) for job in planned["jobs"]] == [
        ("MU_BETA_CSP8_EEGNET", "selection"), ("MU_BETA_CSP8_EEGNET", "final"),
        ("MU_BETA_PCA8_EEGNET", "selection"), ("MU_BETA_PCA8_EEGNET", "final"),
    ]
    assert all(job["completion_value"] == "frozen_before_Q10_target_inference"
               for job in planned["jobs"] if job["phase"] == "selection")


def _small_receipt() -> tuple[dict, list[str]]:
    rng = np.random.default_rng(10)
    mu = rng.normal(0, 1e-6, size=(8, 22, 64)).astype(np.float32)
    beta = rng.normal(0, 1e-6, size=(8, 22, 64)).astype(np.float32)
    ids = [f"s{1 + i // 4}_t{i}" for i in range(8)]
    fitted = fit_projector_pair(mu, beta, np.tile(np.arange(1, 5), 2),
                                np.repeat([1, 2], 4), method="pca8",
                                source_sample_ids=np.asarray(ids))
    return fitted.receipt(), ids


def test_receipt_recomputes_parameter_hash_and_source_identity() -> None:
    receipt, ids = _small_receipt()
    validate_spatial_receipt(receipt, method="pca8", fit_subjects=[1, 2],
                             fit_sample_ids=ids)
    changed = json.loads(json.dumps(receipt))
    changed["parameters"]["filters_mu"][0][0] += 0.01
    with pytest.raises(AssertionError, match="parameter SHA256"):
        validate_spatial_receipt(changed, method="pca8", fit_subjects=[1, 2],
                                 fit_sample_ids=ids)
    with pytest.raises(AssertionError, match="source fit"):
        validate_spatial_receipt(receipt, method="pca8", fit_subjects=[1, 3],
                                 fit_sample_ids=ids)


def _reference() -> pd.DataFrame:
    subjects = np.repeat(np.arange(1, 10), 576)
    labels = np.tile(np.repeat(np.arange(1, 5), 144), 9)
    return pd.DataFrame({"sample_id": [f"s{s}_t{i}" for s in range(1, 10)
                                         for i in range(576)],
                         "subject": subjects, "session": np.tile(np.repeat(["T", "E"], 288), 9),
                         "label": labels, "artifact_flagged": False})


def _manifest(target: int, *, inner: int | None, seed: int, epochs: int) -> pd.DataFrame:
    sources = [s for s in range(1, 10) if s != target]
    val = [] if inner is None else sources[2 * (inner - 1):2 * inner]
    stage = "full" if inner is None else "inner"
    rows = []
    for subject in range(1, 10):
        role = ("test" if inner is None else "outer_test_excluded") if subject == target else (
            "validation" if subject in val else "train")
        rows.append({"fold": f"loso_s{target}", "stage": stage, "inner_fold": inner,
                     "seed": seed, "subject": subject, "role": role, "n_trials": 576,
                     "n_used_for_fit": 576 if role == "train" else 0,
                     "n_excluded_from_fit": 0,
                     "n_used_for_validation": 576 if role == "validation" else 0,
                     "epochs_trained": epochs})
    return pd.DataFrame(rows)


@pytest.mark.parametrize("inner,seed,epochs", [(2, 20260923, 40),
                                                (None, 20260924, 13)])
def test_fit_manifest_rejects_target_or_validation_leakage(inner: int | None,
                                                            seed: int, epochs: int) -> None:
    ref = _reference()
    frame = _manifest(3, inner=inner, seed=seed, epochs=epochs)
    validate_fit_manifest(frame, ref, target=3,
                          stage="full" if inner is None else "inner",
                          inner_fold=inner, seed=seed, epochs=epochs)
    changed = frame.copy()
    changed.loc[changed.subject == 3, "n_used_for_fit"] = 576
    with pytest.raises(AssertionError, match="Fit manifest mismatch"):
        validate_fit_manifest(changed, ref, target=3,
                              stage="full" if inner is None else "inner",
                              inner_fold=inner, seed=seed, epochs=epochs)
    if inner is not None:
        changed = frame.copy()
        changed.loc[changed.role == "validation", "role"] = "train"
        with pytest.raises(AssertionError, match="Fit manifest mismatch"):
            validate_fit_manifest(changed, ref, target=3, stage="inner",
                                  inner_fold=inner, seed=seed, epochs=epochs)


def test_epoch_rank_selection_is_earliest_exact_tie() -> None:
    curves = []
    for _ in range(4):
        values = np.arange(40, dtype=float)
        values[0], values[1] = 0.0, 0.0
        curves.append(pd.DataFrame({"epoch": np.arange(1, 41), "val_ce": values}))
    assert independent_selected_epoch(curves) == 1
    curves[0].loc[0, "val_ce"] = np.nan
    with pytest.raises(AssertionError, match="Nonfinite"):
        independent_selected_epoch(curves)


def test_prediction_validation_recomputes_target_ba_and_identity() -> None:
    ref = _reference()
    frame = ref.loc[ref.subject == 3].copy().reset_index(drop=True)
    frame["seed"] = 20260924
    frame["y_true"] = frame.label
    frame["y_pred"] = frame.label
    for label in range(1, 5):
        frame[f"p_class_{label}"] = (frame.label == label).astype(float)
    result = validate_prediction_frame(frame, ref, 3, 20260924)
    assert result["balanced_accuracy"] == 1.0
    assert result["zero_recall_classes"] == 0
    changed = frame.copy()
    changed.loc[0, "sample_id"] = "s1_t0"
    with pytest.raises(AssertionError, match="Q8 reference trial coverage|Q8 trial identity"):
        validate_prediction_frame(changed, ref, 3, 20260924)
    changed = frame.copy()
    changed.loc[0, "p_class_1"] = 0.5
    with pytest.raises(AssertionError, match="sum to one"):
        validate_prediction_frame(changed, ref, 3, 20260924)


def test_stratum_metrics_and_confusions_against_existing_q9_record() -> None:
    """A real frozen Q9 file checks the validator's CSV-schema compatibility."""
    folder = ROOT / "results/Q9-E001/MU_BETA_SHARED/final/loso_s1/seed_20260924"
    predictions = pd.read_csv(folder / "predictions.csv")
    metrics = pd.read_csv(folder / "metrics.csv")
    confusion = pd.read_csv(folder / "confusion.csv")
    validate_saved_metrics(predictions, metrics, confusion, subject=1,
                           seed=20260924, condition="MU_BETA_SHARED")
    changed = confusion.copy()
    changed.loc[changed.stratum == "all", "count"] += 1
    with pytest.raises(AssertionError, match="Saved confusion"):
        validate_saved_metrics(predictions, metrics, changed, subject=1,
                               seed=20260924, condition="MU_BETA_SHARED")
