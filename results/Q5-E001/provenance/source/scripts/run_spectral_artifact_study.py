"""Run a frozen Fourier-spectral and artifact-training LOSO extension.

This follows, but is analytically distinct from, the already inspected P2 baseline.
The clean held-out test IDs are identical for both source-training policies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import moabb
import numpy as np
import pandas as pd
import scipy
import sklearn
from mne.decoding import CSP
from run_csp_baselines import load_epochs, metrics, source_files
from scipy.signal import welch
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.preprocessing import StandardScaler

from mi_eeg.evaluation.splits import iter_loso
from mi_eeg.provenance import (
    capture_startup_provenance,
    check_declared_constants,
    require_new_run_directory,
)
from mi_eeg.reproducibility import set_global_seed

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "configs" / "p3_spectral_artifact_protocol.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "P3-E001")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--subjects", type=int, nargs="+", default=list(range(1, 10)))
    return parser.parse_args()


def welch_log_bandpower(X: np.ndarray, protocol: dict) -> np.ndarray:
    """Fixed FFT-derived features; no parameter is learned from test subjects."""

    spec = protocol["fft_features"]
    freqs, psd = welch(
        X,
        fs=protocol["input"]["sampling_rate_hz"],
        window=spec["window"],
        nperseg=spec["nperseg"],
        noverlap=spec["noverlap"],
        nfft=spec["nfft"],
        detrend=spec["detrend"],
        scaling="density",
        average="mean",
        axis=-1,
    )
    df = float(freqs[1] - freqs[0])
    bands = spec["bands_hz_half_open_except_last"]
    columns = []
    for index, (low, high) in enumerate(bands):
        # The last band includes 30 Hz; all earlier upper edges are exclusive.
        mask = (freqs >= low) & ((freqs <= high) if index == len(bands) - 1 else (freqs < high))
        if not mask.any():
            raise AssertionError(f"No Fourier bins in {low}-{high} Hz")
        power = psd[..., mask].sum(axis=-1) * df
        columns.append(np.log10(np.maximum(power, spec["log_floor"])))
    features = np.concatenate(columns, axis=1).astype(np.float32)
    expected = X.shape[1] * len(bands)
    if features.shape != (len(X), expected) or not np.isfinite(features).all():
        raise AssertionError("Unexpected or nonfinite Welch PSD feature matrix")
    return features


def csp_features(X_train: np.ndarray, y_train: np.ndarray, X_test: np.ndarray) -> tuple:
    spatial = CSP(
        n_components=4,
        reg=None,
        log=True,
        cov_est="concat",
        transform_into="average_power",
        norm_trace=False,
    )
    spatial.fit(X_train, y_train)
    return spatial.transform(X_train), spatial.transform(X_test)


def fit_predict_features(
    train_features: np.ndarray, y_train: np.ndarray, test_features: np.ndarray
) -> np.ndarray:
    scaler = StandardScaler()
    scaled_train = scaler.fit_transform(train_features)
    scaled_test = scaler.transform(test_features)
    clf = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
    clf.fit(scaled_train, y_train)
    return clf.predict(scaled_test).astype(np.int64)


def evaluate(X: np.ndarray, meta: pd.DataFrame, psd: np.ndarray) -> tuple:
    labels = meta["label"].to_numpy(dtype=np.int64)
    flagged = meta["artifact_flagged"].to_numpy(dtype=bool)
    prediction_rows = []
    fold_rows = []
    split_rows = []
    for fold_id, source_idx, target_idx in iter_loso(meta):
        clean_target = target_idx[~flagged[target_idx]]
        flagged_target = target_idx[flagged[target_idx]]
        if len(clean_target) + len(flagged_target) != len(target_idx):
            raise AssertionError("Test strata do not partition held-out trials")
        print(
            f"{fold_id}: clean test={len(clean_target)}, flagged test={len(flagged_target)}",
            flush=True,
        )
        for policy in ("expert_clean_only", "all_trials"):
            train_idx = (
                source_idx[~flagged[source_idx]] if policy == "expert_clean_only" else source_idx
            )
            if set(labels[train_idx]) != {1, 2} or set(labels[target_idx]) != {1, 2}:
                raise AssertionError("A class is missing from train or test")
            for role, indices in (
                ("train", train_idx),
                ("test_clean", clean_target),
                ("test_flagged", flagged_target),
            ):
                for idx in indices:
                    row = meta.iloc[int(idx)]
                    split_rows.append(
                        {
                            "fold_id": fold_id,
                            "training_policy": policy,
                            "role": role,
                            "sample_id": row["sample_id"],
                            "subject": int(row["subject"]),
                            "artifact_flagged": bool(row["artifact_flagged"]),
                        }
                    )
            start = time.perf_counter()
            csp_train, csp_target = csp_features(X[train_idx], labels[train_idx], X[target_idx])
            csp_seconds = time.perf_counter() - start
            train_psd, target_psd = psd[train_idx], psd[target_idx]
            candidates = {
                "CSP4+shrinkageLDA": (csp_train, csp_target),
                "WelchPSD88+shrinkageLDA": (train_psd, target_psd),
                "CSP4+WelchPSD88+shrinkageLDA": (
                    np.concatenate([csp_train, train_psd], axis=1),
                    np.concatenate([csp_target, target_psd], axis=1),
                ),
            }
            for model, (train_features, target_features) in candidates.items():
                begin = time.perf_counter()
                predicted = fit_predict_features(train_features, labels[train_idx], target_features)
                elapsed = time.perf_counter() - begin
                clean_mask = ~flagged[target_idx]
                fold_rows.append(
                    {
                        "fold_id": fold_id,
                        "training_policy": policy,
                        "model": model,
                        "n_train": len(train_idx),
                        "n_test_clean": len(clean_target),
                        "n_test_flagged": len(flagged_target),
                        "n_features": train_features.shape[1],
                        "csp_fit_transform_seconds_shared": csp_seconds,
                        "classifier_seconds": elapsed,
                        **metrics(labels[target_idx][clean_mask], predicted[clean_mask]),
                    }
                )
                for idx, pred in zip(target_idx, predicted):
                    row = meta.iloc[int(idx)]
                    prediction_rows.append(
                        {
                            "fold_id": fold_id,
                            "training_policy": policy,
                            "model": model,
                            "sample_id": row["sample_id"],
                            "subject": int(row["subject"]),
                            "session": row["session"],
                            "run": int(row["run"]),
                            "trial": int(row["trial"]),
                            "artifact_flagged": bool(row["artifact_flagged"]),
                            "y_true": int(row["label"]),
                            "y_pred": int(pred),
                        }
                    )
            print(f"  {policy}: train={len(train_idx)}, 3 models complete", flush=True)
    return pd.DataFrame(prediction_rows), pd.DataFrame(fold_rows), pd.DataFrame(split_rows)


def summarize(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for (policy, model, subject), group in predictions.groupby(
        ["training_policy", "model", "subject"], sort=True
    ):
        for stratum, part in (
            ("clean", group[~group["artifact_flagged"]]),
            ("flagged", group[group["artifact_flagged"]]),
            ("all", group),
        ):
            y_true = part["y_true"].to_numpy(dtype=np.int64)
            y_pred = part["y_pred"].to_numpy(dtype=np.int64)
            scores = metrics(y_true, y_pred) if len(part) and set(y_true) == {1, 2} else {}
            rows.append(
                {
                    "training_policy": policy,
                    "model": model,
                    "subject": int(subject),
                    "test_stratum": stratum,
                    "n_test": len(part),
                    "n_left": int(np.sum(y_true == 1)),
                    "n_right": int(np.sum(y_true == 2)),
                    **{
                        key: scores.get(key, np.nan)
                        for key in ("balanced_accuracy", "accuracy", "macro_f1", "cohen_kappa")
                    },
                }
            )
    subjects = pd.DataFrame(rows)
    summaries = []
    for (policy, model, stratum), group in subjects.groupby(
        ["training_policy", "model", "test_stratum"], sort=True
    ):
        ba = group["balanced_accuracy"].dropna()
        summaries.append(
            {
                "training_policy": policy,
                "model": model,
                "test_stratum": stratum,
                "n_subjects_scored": len(ba),
                "n_test_trials": int(group["n_test"].sum()),
                "mean_balanced_accuracy": float(ba.mean()) if len(ba) else np.nan,
                "sd_balanced_accuracy": float(ba.std(ddof=1)) if len(ba) > 1 else np.nan,
                "median_balanced_accuracy": float(ba.median()) if len(ba) else np.nan,
                "min_balanced_accuracy": float(ba.min()) if len(ba) else np.nan,
                "max_balanced_accuracy": float(ba.max()) if len(ba) else np.nan,
            }
        )
    return subjects, pd.DataFrame(summaries)


def contrasts(subjects: pd.DataFrame, seed: int) -> dict:
    clean = subjects[subjects["test_stratum"] == "clean"]
    wide = clean.pivot(
        index="subject", columns=["training_policy", "model"], values="balanced_accuracy"
    )
    definitions = {
        "PSD_minus_CSP_clean_training": (
            ("expert_clean_only", "WelchPSD88+shrinkageLDA"),
            ("expert_clean_only", "CSP4+shrinkageLDA"),
        ),
        "Fusion_minus_CSP_clean_training": (
            ("expert_clean_only", "CSP4+WelchPSD88+shrinkageLDA"),
            ("expert_clean_only", "CSP4+shrinkageLDA"),
        ),
    }
    for model in (
        "CSP4+shrinkageLDA",
        "WelchPSD88+shrinkageLDA",
        "CSP4+WelchPSD88+shrinkageLDA",
    ):
        definitions[f"all_minus_clean_training__{model}"] = (
            ("all_trials", model),
            ("expert_clean_only", model),
        )
    rng = np.random.default_rng(seed)
    result = {}
    for name, (left, right) in definitions.items():
        delta = (wide[left] - wide[right]).to_numpy(dtype=float)
        samples = rng.choice(delta, size=(10000, len(delta)), replace=True).mean(axis=1)
        result[name] = {
            "unit": "held-out subject",
            "n_subjects": len(delta),
            "mean_paired_difference_ba": float(delta.mean()),
            "sd_paired_difference_ba": float(delta.std(ddof=1)),
            "bootstrap_percentile_95_ci": [
                float(value) for value in np.quantile(samples, [0.025, 0.975])
            ],
            "per_subject_differences": {
                str(subject): float(value) for subject, value in zip(wide.index, delta)
            },
            "note": "Exploratory nine-subject inference; interval does not establish broad generalization.",
        }
    return result


def save_figure(subjects: pd.DataFrame, path: Path) -> None:
    clean = subjects[
        (subjects["test_stratum"] == "clean") & (subjects["training_policy"] == "expert_clean_only")
    ]
    fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    for model, group in clean.groupby("model", sort=True):
        ax.plot(group["subject"], group["balanced_accuracy"], marker="o", label=model)
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=1)
    ax.set(
        xlabel="Held-out subject",
        ylabel="Balanced accuracy",
        title="Spectral and spatial features: clean-source LOSO",
        ylim=(0, 1),
    )
    ax.set_xticks(range(1, 10))
    ax.legend(fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    output = args.output_dir.resolve()
    subjects = sorted(set(args.subjects))
    if subjects != list(range(1, 10)):
        raise SystemExit("Frozen P3 protocol requires exactly subjects 1 through 9")
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
            "input": {
                "sampling_rate_hz": 250,
                "epoch_trial_relative_s": [2.5, 5.5],
                "n_samples": 750,
                "no_rereference": True,
            },
            "csp": {"n_components": 4, "cov_est": "concat", "reg": None, "log": True},
            "classifier": "LinearDiscriminantAnalysis(solver='lsqr', shrinkage='auto')",
            "training_artifact_policies": ["expert_clean_only", "all_trials"],
            "fft_features": {
                "bands_hz_half_open_except_last": [[8, 12], [12, 16], [16, 20], [20, 30]]
            },
        },
    )
    capture_startup_provenance(ROOT, output)
    if protocol["candidate_models"] != [
        "CSP4+shrinkageLDA",
        "WelchPSD88+shrinkageLDA",
        "CSP4+WelchPSD88+shrinkageLDA",
    ]:
        raise AssertionError("Protocol model list differs from implementation")
    started = datetime.now(UTC)
    (output / "protocol.json").write_bytes(protocol_bytes)
    (output / "run_metadata.json").write_text(
        json.dumps(
            {
                "started_at_utc": started.isoformat(),
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
        X, meta, audit = load_epochs(subjects, args.data_dir.resolve(), reject_artifacts=False)
        if X.shape != (2592, 22, 750) or int(meta["artifact_flagged"].sum()) != 246:
            raise AssertionError("P3 input audit differs from previously audited BNCI2014_001")
        meta.to_csv(output / "trial_metadata.csv", index=False)
        audit.to_csv(output / "data_audit.csv", index=False)
        (output / "source_files.json").write_text(
            json.dumps(source_files(args.data_dir.resolve(), subjects), indent=2), encoding="utf-8"
        )
        psd = welch_log_bandpower(X, protocol)
        np.savez_compressed(
            output / "welch_features.npz",
            sample_id=meta["sample_id"].to_numpy(dtype=str),
            features=psd,
        )
        predictions, folds, splits = evaluate(X, meta, psd)
        predictions.to_csv(output / "predictions.csv", index=False)
        folds.to_csv(output / "fold_metrics.csv", index=False)
        splits.to_csv(output / "split_manifest.csv", index=False)
        subject_scores, summary = summarize(predictions)
        subject_scores.to_csv(output / "subject_metrics.csv", index=False)
        summary.to_csv(output / "summary.csv", index=False)
        (output / "paired_contrasts.json").write_text(
            json.dumps(contrasts(subject_scores, protocol["seed"]), indent=2), encoding="utf-8"
        )
        figures = output / "figures"
        figures.mkdir(exist_ok=True)
        save_figure(subject_scores, figures / "spectral_loso_per_subject.png")
        (output / "run_status.json").write_text(
            json.dumps(
                {
                    "status": "complete",
                    "finished_at_utc": datetime.now(UTC).isoformat(),
                    "n_trials": len(meta),
                    "n_expert_flagged": int(meta["artifact_flagged"].sum()),
                    "n_loso_folds": 9,
                    "n_model_fits": len(folds),
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
