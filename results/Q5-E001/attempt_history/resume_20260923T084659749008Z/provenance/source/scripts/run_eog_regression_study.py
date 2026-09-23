"""Explore source-fitted EOG regression without target-subject coefficient fitting."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import warnings
from datetime import UTC, datetime
from pathlib import Path

import mne
import moabb
import numpy as np
import pandas as pd
import scipy
import sklearn
from moabb.datasets import BNCI2014_001
from run_csp_baselines import load_epochs, metrics, source_files
from run_spectral_artifact_study import csp_features, fit_predict_features

from mi_eeg.evaluation.splits import iter_loso
from mi_eeg.preprocessing.eog_regression import (
    apply_eog_coefficients,
    fit_eog_coefficients,
    mean_abs_cross_correlation,
)
from mi_eeg.provenance import (
    capture_startup_provenance,
    check_declared_constants,
    require_new_run_directory,
)
from mi_eeg.reproducibility import set_global_seed

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "configs" / "p4_eog_regression_protocol.json"


def load_filtered_eog_epochs(data_dir: Path, meta: pd.DataFrame) -> np.ndarray:
    """Load synchronous EOG epochs with exactly the same event and filter anchors."""

    os.environ["MNE_DATASETS_BNCI_PATH"] = str(data_dir.resolve())
    dataset = BNCI2014_001(artifact_handling="annotate_bad")
    arrays = []
    sample_ids = []
    for subject in range(1, 10):
        print(f"Loading EOG subject {subject} ...", flush=True)
        sessions = dataset.get_data(subjects=[subject])[subject]
        for session, runs in sorted(sessions.items()):
            for run_name, raw in sorted(runs.items(), key=lambda item: int(item[0])):
                run = int(run_name)
                events = mne.find_events(raw, stim_channel="STI", shortest_event=1, verbose=False)
                sample_to_trial = {
                    int(sample): trial for trial, sample in enumerate(events[:, 0], 1)
                }
                eog_raw = raw.copy().pick("eog")
                eog_raw.filter(
                    l_freq=8.0,
                    h_freq=30.0,
                    picks="eog",
                    method="iir",
                    iir_params={"order": 4, "ftype": "butter"},
                    phase="zero",
                    verbose=False,
                )
                epochs = mne.Epochs(
                    eog_raw,
                    events,
                    event_id={"left_hand": 1, "right_hand": 2},
                    tmin=2.5,
                    tmax=5.5 - 1.0 / 250.0,
                    baseline=None,
                    reject_by_annotation=False,
                    preload=True,
                    verbose=False,
                )
                array = epochs.get_data(copy=True).astype(np.float32)
                if array.shape != (24, 3, 750):
                    raise AssertionError(f"Unexpected EOG epochs: {subject} {session} {run}")
                arrays.append(array)
                for sample, _, _ in epochs.events:
                    trial = sample_to_trial[int(sample)]
                    sample_ids.append(f"s{subject:02d}_{session}_r{run}_t{trial:02d}")
    if sample_ids != meta["sample_id"].tolist():
        raise AssertionError("EEG and EOG trial IDs differ in order")
    eog = np.concatenate(arrays)
    if eog.shape != (2592, 3, 750):
        raise AssertionError("Unexpected concatenated EOG shape")
    return eog


def evaluate(X: np.ndarray, EOG: np.ndarray, meta: pd.DataFrame) -> tuple:
    labels = meta["label"].to_numpy(dtype=np.int64)
    flagged = meta["artifact_flagged"].to_numpy(dtype=bool)
    predictions = []
    qc_rows = []
    coefficient_rows = []
    fit_manifest_rows = []
    for fold_id, source_idx, target_idx in iter_loso(meta):
        train = source_idx[~flagged[source_idx]]
        for role, indices in (("fit_all_learned_steps", train), ("test", target_idx)):
            for idx in indices:
                row = meta.iloc[int(idx)]
                fit_manifest_rows.append(
                    {
                        "fold_id": fold_id,
                        "role": role,
                        "sample_id": row["sample_id"],
                        "subject": int(row["subject"]),
                        "artifact_flagged": bool(row["artifact_flagged"]),
                    }
                )
        beta, info = fit_eog_coefficients(X[train], EOG[train], ridge_fraction=1e-4)
        corrected_train = apply_eog_coefficients(X[train], EOG[train], beta)
        corrected_target = apply_eog_coefficients(X[target_idx], EOG[target_idx], beta)
        for eog_index in range(3):
            for eeg_index in range(22):
                coefficient_rows.append(
                    {
                        "fold_id": fold_id,
                        "eog_channel": f"EOG{eog_index + 1}",
                        "eeg_channel_index": eeg_index,
                        "coefficient": float(beta[eog_index, eeg_index]),
                    }
                )
        qc_rows.append(
            {
                "fold_id": fold_id,
                "n_source_clean_trials": len(train),
                "n_target_clean_trials": int(np.sum(~flagged[target_idx])),
                "n_target_flagged_trials": int(np.sum(flagged[target_idx])),
                "source_abs_eeg_eog_corr_before": mean_abs_cross_correlation(X[train], EOG[train]),
                "source_abs_eeg_eog_corr_after": mean_abs_cross_correlation(
                    corrected_train, EOG[train]
                ),
                "target_abs_eeg_eog_corr_before": mean_abs_cross_correlation(
                    X[target_idx], EOG[target_idx]
                ),
                "target_abs_eeg_eog_corr_after": mean_abs_cross_correlation(
                    corrected_target, EOG[target_idx]
                ),
                "target_correction_rms_ratio": float(
                    np.sqrt(np.mean((corrected_target.astype(np.float64) - X[target_idx]) ** 2))
                    / np.sqrt(np.mean(X[target_idx].astype(np.float64) ** 2))
                ),
                **info,
            }
        )
        for condition, train_X, target_X in (
            ("uncorrected", X[train], X[target_idx]),
            ("source_train_fitted_EOG_regression", corrected_train, corrected_target),
        ):
            train_features, target_features = csp_features(train_X, labels[train], target_X)
            predicted = fit_predict_features(train_features, labels[train], target_features)
            for idx, pred in zip(target_idx, predicted):
                row = meta.iloc[int(idx)]
                predictions.append(
                    {
                        "fold_id": fold_id,
                        "condition": condition,
                        "sample_id": row["sample_id"],
                        "subject": int(row["subject"]),
                        "session": row["session"],
                        "artifact_flagged": bool(row["artifact_flagged"]),
                        "y_true": int(row["label"]),
                        "y_pred": int(pred),
                    }
                )
        print(f"{fold_id}: EOG coefficients fit on {len(train)} clean source trials", flush=True)
    return (
        pd.DataFrame(predictions),
        pd.DataFrame(qc_rows),
        pd.DataFrame(coefficient_rows),
        pd.DataFrame(fit_manifest_rows),
    )


def summarize(predictions: pd.DataFrame, seed: int) -> tuple:
    rows = []
    for (condition, subject), group in predictions.groupby(["condition", "subject"], sort=True):
        for stratum, part in (
            ("clean", group[~group["artifact_flagged"]]),
            ("flagged", group[group["artifact_flagged"]]),
            ("all", group),
        ):
            score = metrics(part["y_true"].to_numpy(), part["y_pred"].to_numpy())
            rows.append(
                {
                    "condition": condition,
                    "subject": int(subject),
                    "test_stratum": stratum,
                    "n_test": len(part),
                    "n_left": int((part["y_true"] == 1).sum()),
                    "n_right": int((part["y_true"] == 2).sum()),
                    **score,
                }
            )
    subjects = pd.DataFrame(rows)
    summaries = []
    for (condition, stratum), group in subjects.groupby(["condition", "test_stratum"]):
        values = group["balanced_accuracy"]
        summaries.append(
            {
                "condition": condition,
                "test_stratum": stratum,
                "n_subjects": len(group),
                "n_test_trials": int(group["n_test"].sum()),
                "mean_balanced_accuracy": float(values.mean()),
                "sd_balanced_accuracy": float(values.std(ddof=1)),
                "median_balanced_accuracy": float(values.median()),
                "min_balanced_accuracy": float(values.min()),
                "max_balanced_accuracy": float(values.max()),
            }
        )
    clean = subjects[subjects["test_stratum"] == "clean"].pivot(
        index="subject", columns="condition", values="balanced_accuracy"
    )
    difference = (clean["source_train_fitted_EOG_regression"] - clean["uncorrected"]).to_numpy()
    rng = np.random.default_rng(seed)
    boot = rng.choice(difference, size=(10000, len(difference)), replace=True).mean(axis=1)
    contrast = {
        "comparison": "source_train_fitted_EOG_regression minus uncorrected",
        "test_population": "same expert-clean target trial IDs",
        "unit": "held-out subject",
        "mean_paired_difference_ba": float(difference.mean()),
        "bootstrap_percentile_95_ci": [float(v) for v in np.quantile(boot, [0.025, 0.975])],
        "per_subject_differences": {
            str(subject): float(delta) for subject, delta in zip(clean.index, difference)
        },
        "note": "Exploratory nine-subject follow-up; EOG-assisted pipeline needs three extra sensors.",
    }
    return subjects, pd.DataFrame(summaries), contrast


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "P4-E001")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "raw")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    require_new_run_directory(output)
    mne.set_log_level("WARNING")
    warnings.filterwarnings("ignore", message="Montage name 'standard_1005' is deprecated.*")
    protocol_bytes = PROTOCOL_PATH.read_bytes()
    protocol = json.loads(protocol_bytes)
    check_declared_constants(
        protocol,
        {
            "dataset": "BNCI2014_001",
            "subjects": list(range(1, 10)),
            "analysis_band_hz": [8, 30],
            "epoch_cue_relative_s": [0.5, 3.5],
            "eog_correction": {
                "ridge_fraction_of_mean_eog_energy": 0.0001,
                "trial_centering": True,
            },
            "classifier": "4-component CSP, StandardScaler, LDA(solver='lsqr', shrinkage='auto')",
            "training_artifact_policy": "expert-clean only",
        },
    )
    capture_startup_provenance(ROOT, output)
    (output / "protocol.json").write_bytes(protocol_bytes)
    (output / "run_metadata.json").write_text(
        json.dumps(
            {
                "started_at_utc": datetime.now(UTC).isoformat(),
                "protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
                "python": sys.version,
                "platform": platform.platform(),
                "mne": mne.__version__,
                "moabb": moabb.__version__,
                "numpy": np.__version__,
                "scipy": scipy.__version__,
                "pandas": pd.__version__,
                "scikit_learn": sklearn.__version__,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    set_global_seed(protocol["seed"])
    try:
        X, meta, audit = load_epochs(list(range(1, 10)), args.data_dir.resolve(), False)
        EOG = load_filtered_eog_epochs(args.data_dir.resolve(), meta)
        meta.to_csv(output / "trial_metadata.csv", index=False)
        audit.to_csv(output / "data_audit.csv", index=False)
        (output / "source_files.json").write_text(
            json.dumps(source_files(args.data_dir.resolve(), list(range(1, 10))), indent=2),
            encoding="utf-8",
        )
        predictions, qc, coefficients, fit_manifest = evaluate(X, EOG, meta)
        fit_manifest.to_csv(output / "fit_manifest.csv", index=False)
        predictions.to_csv(output / "predictions.csv", index=False)
        qc.to_csv(output / "eog_qc.csv", index=False)
        coefficients.to_csv(output / "eog_coefficients.csv", index=False)
        subject_scores, summary, contrast = summarize(predictions, protocol["seed"])
        subject_scores.to_csv(output / "subject_metrics.csv", index=False)
        summary.to_csv(output / "summary.csv", index=False)
        (output / "paired_contrast.json").write_text(
            json.dumps(contrast, indent=2), encoding="utf-8"
        )
        (output / "run_status.json").write_text(
            json.dumps(
                {
                    "status": "complete",
                    "finished_at_utc": datetime.now(UTC).isoformat(),
                    "n_trials": len(meta),
                    "n_flagged": int(meta["artifact_flagged"].sum()),
                    "n_loso_folds": 9,
                    "n_model_fits": 18,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(summary[summary["test_stratum"] == "clean"].to_string(index=False), flush=True)
        print(f"Completed: {output}", flush=True)
    except Exception as error:
        (output / "run_status.json").write_text(
            json.dumps(
                {
                    "status": "failed",
                    "failed_at_utc": datetime.now(UTC).isoformat(),
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        raise


if __name__ == "__main__":
    main()
