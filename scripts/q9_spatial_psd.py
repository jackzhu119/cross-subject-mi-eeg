"""Resumable Q9-A001 Welch-PSD four-class source-only LOSO controls.

The 44 features are fixed before fitting: for each of 22 channels, integrate
Hamming-window Welch PSD over 8 <= f < 13 and 13 <= f <= 30 Hz, then take
log10(power + 1e-12). StandardScaler and either shrinkage LDA or linear SVM
are fitted on the eight source subjects only. SVM scores are uncalibrated
margins, deliberately not mislabeled as probabilities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import tempfile
import traceback
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import welch
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    recall_score,
)
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

ROOT = Path(__file__).resolve().parents[1]
LABELS = (1, 2, 3, 4)
MODELS = ("PSD44_LDA", "PSD44_LINEAR_SVM")
FEATURE_NAMES = tuple(
    f"ch{channel:02d}_{band}" for channel in range(1, 23) for band in ("mu", "beta")
)
FEATURE_SPEC = {
    "sampling_rate_hz": 250,
    "input_units": "microvolts",
    "window": "hamming",
    "nperseg": 250,
    "noverlap": 125,
    "nfft": 250,
    "detrend": "constant",
    "scaling": "density",
    "average": "mean",
    "mu_bins_hz": "8 <= f < 13",
    "beta_bins_hz": "13 <= f <= 30",
    "power_integral": "sum(psd_bin) * df",
    "log": "log10(power + 1e-12)",
    "n_features": 44,
}


def _sha_ids(ids: np.ndarray) -> str:
    return hashlib.sha256("\n".join(np.asarray(ids, dtype=str).tolist()).encode()).hexdigest()


def _sha_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def _write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
        temp = Path(f.name)
    os.replace(temp, path)


def _write_csv_atomic(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".csv", dir=path.parent, delete=False) as f:
        frame.to_csv(f, index=False)
        temp = Path(f.name)
    os.replace(temp, path)


def welch_psd44(data_uv: np.ndarray, *, batch_size: int = 128) -> np.ndarray:
    """Return the locked 44 log-bandpower features in channel-major order.

    Input shape is (trials, 22, 750) for production. No labels, subject IDs,
    target moments, or fitted preprocessing are used by this transform.
    """
    data_uv = np.asarray(data_uv)
    if data_uv.ndim != 3 or data_uv.shape[1:] != (22, 750):
        raise ValueError("Expected EEG of shape (trials, 22, 750)")
    if not len(data_uv) or not np.isfinite(data_uv).all() or batch_size < 1:
        raise ValueError("Empty/nonfinite EEG or invalid batch size")
    features = np.empty((len(data_uv), 44), dtype=np.float64)
    for start in range(0, len(data_uv), batch_size):
        stop = min(start + batch_size, len(data_uv))
        frequencies, psd = welch(
            np.asarray(data_uv[start:stop], dtype=np.float64),
            fs=250.0,
            window="hamming",
            nperseg=250,
            noverlap=125,
            nfft=250,
            detrend="constant",
            return_onesided=True,
            scaling="density",
            average="mean",
            axis=-1,
        )
        df = frequencies[1] - frequencies[0]
        mu = np.sum(psd[..., (frequencies >= 8) & (frequencies < 13)], axis=-1) * df
        beta = np.sum(psd[..., (frequencies >= 13) & (frequencies <= 30)], axis=-1) * df
        features[start:stop] = np.log10(
            np.stack([mu, beta], axis=-1).reshape(stop - start, 44) + 1e-12
        )
    if not np.isfinite(features).all():
        raise AssertionError("Nonfinite PSD features")
    return features


def fit_predict_source_only(
    features: np.ndarray,
    labels: np.ndarray,
    subjects: np.ndarray,
    train_idx: np.ndarray,
    target_idx: np.ndarray,
    *,
    model: str,
    sample_ids: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Fit scaler/classifier on source rows; never estimate from target rows."""
    features = np.asarray(features, dtype=np.float64)
    labels = np.asarray(labels)
    subjects = np.asarray(subjects)
    sample_ids = np.asarray(sample_ids, dtype=str)
    train_idx = np.asarray(train_idx, dtype=np.int64)
    target_idx = np.asarray(target_idx, dtype=np.int64)
    if features.ndim != 2 or features.shape[1] != 44:
        raise ValueError("The Q9-A001 classifier requires exactly 44 features")
    if any(len(value) != len(features) for value in (labels, subjects, sample_ids)):
        raise ValueError("Metadata rows are misaligned with features")
    if not len(train_idx) or not len(target_idx):
        raise ValueError("Empty source or target partition")
    if (
        np.any(train_idx < 0)
        or np.any(target_idx < 0)
        or np.any(train_idx >= len(features))
        or np.any(target_idx >= len(features))
        or len(np.unique(train_idx)) != len(train_idx)
        or len(np.unique(target_idx)) != len(target_idx)
        or np.intersect1d(train_idx, target_idx).size
    ):
        raise ValueError("Invalid or overlapping source/target indices")
    source_subjects = set(subjects[train_idx].tolist())
    target_subjects = set(subjects[target_idx].tolist())
    if source_subjects & target_subjects or len(target_subjects) != 1:
        raise ValueError("The target subject must be wholly unseen in the fit")
    if set(np.unique(labels[train_idx])) != set(LABELS):
        raise ValueError("All four classes are required among source trials")
    if len(np.unique(sample_ids)) != len(sample_ids):
        raise ValueError("Duplicate sample identities")
    if model == "PSD44_LDA":
        classifier = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
        score_type = "probability"
    elif model == "PSD44_LINEAR_SVM":
        classifier = SVC(kernel="linear", C=1.0, decision_function_shape="ovr")
        score_type = "uncalibrated_ovr_margin"
    else:
        raise ValueError(f"Unknown locked Q9-A001 model: {model}")
    scaler = StandardScaler().fit(features[train_idx])
    x_train = scaler.transform(features[train_idx])
    x_target = scaler.transform(features[target_idx])
    classifier.fit(x_train, labels[train_idx])
    predicted = classifier.predict(x_target)
    scores = (
        classifier.predict_proba(x_target)
        if model == "PSD44_LDA"
        else classifier.decision_function(x_target)
    )
    if scores.shape != (len(target_idx), 4):
        raise AssertionError("Unexpected class-score matrix shape")
    receipt = {
        "model": model,
        "fit_subjects": sorted(int(value) for value in source_subjects),
        "target_subject": int(next(iter(target_subjects))),
        "fit_sample_ids_sha256": _sha_ids(sample_ids[train_idx]),
        "target_sample_ids_sha256": _sha_ids(sample_ids[target_idx]),
        "n_fit_trials": len(train_idx),
        "n_target_trials": len(target_idx),
        "feature_names": list(FEATURE_NAMES),
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "classifier_classes": classifier.classes_.tolist(),
        "classifier_coef": classifier.coef_.tolist(),
        "classifier_intercept": classifier.intercept_.tolist(),
        "score_type": score_type,
        "classifier_parameters": (
            {"solver": "lsqr", "shrinkage": "auto"}
            if model == "PSD44_LDA"
            else {"kernel": "linear", "C": 1.0, "probability": False}
        ),
    }
    return predicted, scores, receipt


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "n_trials": len(y_true),
        "n_classes_present": len(np.unique(y_true)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)),
        "cohen_kappa": float(cohen_kappa_score(y_true, y_pred, labels=LABELS)),
        **{
            f"recall_class_{label}": float(
                recall_score(y_true, y_pred, labels=[label], average="macro", zero_division=0)
            )
            for label in LABELS
        },
    }


def _completed_fold_is_valid(
    fold_dir: Path, expected_ids: np.ndarray, source_ids_sha: str, config_sha: str
) -> bool:
    status_file = fold_dir / "status.json"
    if not status_file.exists():
        return False
    status = json.loads(status_file.read_text(encoding="utf-8"))
    if status.get("status") != "complete":
        return False
    if status.get("config_sha256") != config_sha:
        raise RuntimeError(f"Completed PSD fold uses another config: {fold_dir}")
    predictions_file = fold_dir / "predictions.csv"
    receipt_file = fold_dir / "fit_receipts.json"
    if not predictions_file.exists() or not receipt_file.exists():
        raise RuntimeError(f"Completed PSD fold has missing artifacts: {fold_dir}")
    predictions = pd.read_csv(predictions_file)
    receipts = json.loads(receipt_file.read_text(encoding="utf-8"))
    if set(predictions.model) != set(MODELS) or set(receipts) != set(MODELS):
        raise RuntimeError(f"Completed PSD fold has missing models: {fold_dir}")
    for model in MODELS:
        part = predictions[predictions.model == model]
        if not np.array_equal(part.sample_id.to_numpy(dtype=str), expected_ids.astype(str)):
            raise RuntimeError(f"Completed PSD fold target identities changed: {fold_dir}")
        if receipts[model]["fit_sample_ids_sha256"] != source_ids_sha:
            raise RuntimeError(f"Completed PSD fold source identities changed: {fold_dir}")
    return True


def run_psd_loso(
    broad_uv: np.ndarray,
    metadata: pd.DataFrame,
    output_dir: Path,
    *,
    config: dict,
) -> None:
    """Run/continue all LOSO folds, aggregating only complete fold artifacts."""
    output_dir = Path(output_dir)
    if not {"sample_id", "subject", "label", "session", "run", "trial", "artifact_flagged"}.issubset(
        metadata.columns
    ):
        raise ValueError("Trial metadata lacks required identity/artifact fields")
    if not metadata.index.equals(pd.RangeIndex(len(metadata))):
        raise ValueError("Trial metadata must have a contiguous 0-based index")
    if metadata.sample_id.duplicated().any() or len(metadata) != len(broad_uv):
        raise ValueError("Duplicate/misaligned trial identities")
    expected_config = {"experiment_id": "Q9-A001", "feature_spec": FEATURE_SPEC, **config}
    config_sha = _sha_json(expected_config)
    config_path = output_dir / "config.json"
    if config_path.exists():
        existing = json.loads(config_path.read_text(encoding="utf-8"))
        if _sha_json(existing) != config_sha:
            raise RuntimeError("Refusing to resume Q9-A001 with a changed configuration")
    else:
        _write_json_atomic(config_path, expected_config)
    _write_json_atomic(
        output_dir / "runtime.json",
        {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": __import__("scipy").__version__,
            "scikit_learn": __import__("sklearn").__version__,
        },
    )
    sample_ids = metadata.sample_id.to_numpy(dtype=str)
    features = welch_psd44(broad_uv)
    if len(metadata.subject.unique()) != 9:
        raise ValueError("Production Q9-A001 requires the declared nine-subject dataset")
    all_predictions: list[pd.DataFrame] = []
    all_metrics: list[pd.DataFrame] = []
    all_confusion: list[pd.DataFrame] = []
    for target in sorted(metadata.subject.unique()):
        train_idx = np.flatnonzero(metadata.subject.to_numpy() != target)
        target_idx = np.flatnonzero(metadata.subject.to_numpy() == target)
        fold_dir = output_dir / "folds" / f"target_s{int(target):02d}"
        source_sha = _sha_ids(sample_ids[train_idx])
        if _completed_fold_is_valid(fold_dir, sample_ids[target_idx], source_sha, config_sha):
            print(f"Q9-A001 target S{target}: verified complete fold, skipping", flush=True)
        else:
            fold_dir.mkdir(parents=True, exist_ok=True)
            _write_json_atomic(
                fold_dir / "status.json",
                {"status": "running", "target_subject": int(target), "config_sha256": config_sha},
            )
            try:
                predictions, metrics, confusion, receipts = [], [], [], {}
                for model in MODELS:
                    pred, scores, receipt = fit_predict_source_only(
                        features,
                        metadata.label.to_numpy(),
                        metadata.subject.to_numpy(),
                        train_idx,
                        target_idx,
                        model=model,
                        sample_ids=sample_ids,
                    )
                    receipts[model] = receipt
                    rows = metadata.iloc[target_idx].copy()
                    rows["model"] = model
                    rows["y_true"] = metadata.label.to_numpy()[target_idx]
                    rows["y_pred"] = pred
                    rows["score_type"] = receipt["score_type"]
                    for column, label in enumerate(LABELS):
                        rows[f"score_class_{label}"] = scores[:, column]
                    predictions.append(rows)
                    for stratum in ("all", "unflagged", "flagged"):
                        selected = (
                            rows
                            if stratum == "all"
                            else rows[rows.artifact_flagged == (stratum == "flagged")]
                        )
                        if selected.empty:
                            continue
                        metrics.append(
                            {
                                "subject": int(target),
                                "model": model,
                                "stratum": stratum,
                                **_metrics(selected.y_true.to_numpy(), selected.y_pred.to_numpy()),
                            }
                        )
                        cm = confusion_matrix(selected.y_true, selected.y_pred, labels=LABELS)
                        for i, truth in enumerate(LABELS):
                            for j, prediction in enumerate(LABELS):
                                confusion.append(
                                    {
                                        "subject": int(target),
                                        "model": model,
                                        "stratum": stratum,
                                        "true_label": truth,
                                        "predicted_label": prediction,
                                        "count": int(cm[i, j]),
                                    }
                                )
                _write_csv_atomic(fold_dir / "predictions.csv", pd.concat(predictions, ignore_index=True))
                _write_csv_atomic(fold_dir / "metrics.csv", pd.DataFrame(metrics))
                _write_csv_atomic(fold_dir / "confusion.csv", pd.DataFrame(confusion))
                _write_json_atomic(fold_dir / "fit_receipts.json", receipts)
                _write_json_atomic(
                    fold_dir / "status.json",
                    {
                        "status": "complete",
                        "target_subject": int(target),
                        "config_sha256": config_sha,
                        "completed_at_utc": datetime.now(UTC).isoformat(),
                    },
                )
            except Exception:
                _write_json_atomic(
                    fold_dir / "failure.json",
                    {"traceback": traceback.format_exc(), "at_utc": datetime.now(UTC).isoformat()},
                )
                raise
        all_predictions.append(pd.read_csv(fold_dir / "predictions.csv"))
        all_metrics.append(pd.read_csv(fold_dir / "metrics.csv"))
        all_confusion.append(pd.read_csv(fold_dir / "confusion.csv"))
        _write_json_atomic(
            output_dir / "status.json",
            {
                "status": "running",
                "completed_folds": len(all_predictions),
                "expected_folds": 9,
                "config_sha256": config_sha,
            },
        )
    _write_csv_atomic(output_dir / "predictions.csv", pd.concat(all_predictions, ignore_index=True))
    _write_csv_atomic(output_dir / "per_subject_metrics.csv", pd.concat(all_metrics, ignore_index=True))
    _write_csv_atomic(output_dir / "confusion_matrices.csv", pd.concat(all_confusion, ignore_index=True))
    summary = (
        pd.concat(all_metrics, ignore_index=True)
        .groupby(["model", "stratum"], sort=True)["balanced_accuracy"]
        .agg(["mean", "std", "count"])
        .reset_index()
    )
    _write_csv_atomic(output_dir / "summary.csv", summary)
    _write_json_atomic(
        output_dir / "status.json",
        {
            "status": "complete",
            "completed_folds": 9,
            "expected_folds": 9,
            "completed_shallow_fits": 18,
            "config_sha256": config_sha,
            "completed_at_utc": datetime.now(UTC).isoformat(),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "Q9-A001")
    args = parser.parse_args()
    import mne

    from mi_eeg.data.bnci_epochs import load_configured_epochs

    mne.set_log_level("ERROR")
    q8_config_path = ROOT / "research_runs" / "Q8-E001" / "results" / "config.json"
    q8_config = json.loads(q8_config_path.read_text(encoding="utf-8"))
    if q8_config["preprocessing"]["bands"] != {"broad": [4, 40]}:
        raise RuntimeError("Frozen Q8 broadband preprocessing unexpectedly changed")
    arrays, meta, audit = load_configured_epochs(
        list(range(1, 10)), args.data_dir, q8_config["preprocessing"], q8_config["class_ids"]
    )
    config = {
        "parent_q8_config_sha256": hashlib.sha256(q8_config_path.read_bytes()).hexdigest(),
        "data_manifest": {
            "trial_ids_sha256": _sha_ids(meta.sample_id.to_numpy(dtype=str)),
            "n_trials": len(meta),
            "n_subjects": 9,
            "source_mat_files": [
                {
                    "name": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
                for path in sorted(args.data_dir.rglob("A*.mat"))
                if path.stem in {f"A{s:02d}{session}" for s in range(1, 10) for session in "TE"}
            ],
        },
        "classifier_spec": {
            "standard_scaler": "fit source subjects only",
            "lda": {"solver": "lsqr", "shrinkage": "auto"},
            "svm": {"kernel": "linear", "C": 1.0, "probability": False},
        },
        "seed": None,
        "labels": list(LABELS),
        "split": "nine outer LOSO; both sessions of target held out",
    }
    output = args.output_dir
    if not (output / "trial_metadata.csv").exists():
        _write_csv_atomic(output / "trial_metadata.csv", meta)
        _write_csv_atomic(output / "data_audit.csv", audit)
    run_psd_loso(arrays["broad"] * 1e6, meta, output, config=config)


if __name__ == "__main__":
    main()
