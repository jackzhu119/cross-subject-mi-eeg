"""Fixed source-only four-class LOSO baselines; parameters are configuration-driven."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

import mne
import numpy as np
import pandas as pd
from mne.decoding import CSP
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.feature_selection import mutual_info_classif
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from threadpoolctl import threadpool_limits

from mi_eeg.data.bnci_epochs import load_configured_epochs
from mi_eeg.evaluation.splits import iter_loso
from mi_eeg.provenance import capture_startup_provenance, require_new_run_directory
from mi_eeg.reproducibility import set_global_seed

ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, content: object) -> None:
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")


def classification_metrics(y: np.ndarray, pred: np.ndarray, labels: list[int]) -> dict:
    return {
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "accuracy": float(accuracy_score(y, pred)),
        "macro_f1": float(f1_score(y, pred, labels=labels, average="macro", zero_division=0)),
        "macro_precision": float(
            precision_score(y, pred, labels=labels, average="macro", zero_division=0)
        ),
        "macro_recall": float(
            recall_score(y, pred, labels=labels, average="macro", zero_division=0)
        ),
        "cohen_kappa": float(cohen_kappa_score(y, pred, labels=labels)),
    }


def fit_classifier(
    features: np.ndarray,
    y: np.ndarray,
    train: np.ndarray,
    test: np.ndarray,
    model: dict,
    config: dict,
) -> tuple[np.ndarray, dict]:
    """Select, scale and fit using source rows only; return a fitted-parameter receipt."""
    if np.intersect1d(train, test).size:
        raise ValueError("Train and test overlap")
    selected = np.arange(features.shape[1])
    mi = None
    if model["select_k"] is not None:
        k = int(model["select_k"])
        if not 1 <= k <= features.shape[1]:
            raise ValueError("Invalid selection size")
        mi = mutual_info_classif(
            features[train], y[train], random_state=config["seed"], **config["mi_selection"]
        )
        # Stable descending ordering explicitly resolves equal MI estimates.
        selected = np.argsort(-mi, kind="stable")[:k]
    scaler = StandardScaler().fit(features[train][:, selected])
    x_train = scaler.transform(features[train][:, selected])
    x_test = scaler.transform(features[test][:, selected])
    if model["classifier"] == "lda":
        clf = LinearDiscriminantAnalysis(**config["lda"])
    elif model["classifier"] == "svm":
        clf = SVC(random_state=config["seed"], **config["svm"])
    else:
        raise ValueError(f"Unsupported classifier {model['classifier']}")
    clf.fit(x_train, y[train])
    receipt = {
        "selected_feature_indices": selected.tolist(),
        "mi_scores": None if mi is None else mi.tolist(),
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "classes": clf.classes_.tolist(),
        "coef": clf.coef_.tolist(),
        "intercept": clf.intercept_.tolist(),
        "n_input_features": features.shape[1],
        "n_selected_features": len(selected),
        "fit_rows": len(train),
        "test_rows": len(test),
    }
    return clf.predict(x_test), receipt


def evaluate(bands: dict[str, np.ndarray], meta: pd.DataFrame, config: dict, output: Path) -> None:
    labels = sorted(config["class_ids"].values())
    y = meta.label.to_numpy()
    metric_rows, prediction_rows, manifest_parts, confusion_rows = [], [], [], []
    feature_rows = []
    batch = config["runtime"]["transform_batch_size"]
    for fold, train, test in iter_loso(meta):
        started = time.perf_counter()
        target = int(meta.iloc[test].subject.unique().item())
        print(f"Fitting {fold}: {len(train)} source / {len(test)} target trials", flush=True)
        fold_dir = output / "folds" / fold
        fold_dir.mkdir(parents=True, exist_ok=False)
        manifest = meta[["sample_id", "subject", "label"]].copy()
        manifest["fold"] = fold
        manifest["role"] = "test"
        manifest.loc[train, "role"] = "train"
        # Written before fitting; it is the exact index partition used below.
        manifest.to_csv(fold_dir / "fit_manifest.csv", index=False)
        manifest_parts.append(manifest)
        features = {}
        for band_name, data in bands.items():
            csp = CSP(**config["csp"])
            fit_started = time.perf_counter()
            csp.fit(data[train].astype(np.float64), y[train])
            values = np.empty((len(meta), config["csp"]["n_components"]), dtype=float)
            for offset in range(0, len(meta), batch):
                values[offset : offset + batch] = csp.transform(
                    data[offset : offset + batch].astype(np.float64)
                )
            if not np.isfinite(values).all():
                raise AssertionError("Non-finite CSP features")
            features[band_name] = values
            np.savez_compressed(
                fold_dir / f"csp_{band_name}.npz",
                filters=csp.filters_,
                patterns=csp.patterns_,
                features=values,
                sample_ids=meta.sample_id.to_numpy(dtype=str),
            )
            feature_rows.append(
                {
                    "fold": fold,
                    "band": band_name,
                    "n_components": values.shape[1],
                    "fit_rows": len(train),
                    "fit_transform_seconds": time.perf_counter() - fit_started,
                }
            )
            print(f"  {band_name} CSP complete", flush=True)
        for model in config["models"]:
            name = model["name"]
            values = np.concatenate([features[key] for key in model["bands"]], axis=1)
            pred, receipt = fit_classifier(values, y, train, test, model, config)
            receipt.update(
                {
                    "fold": fold,
                    "model": name,
                    "bands": model["bands"],
                    "feature_names": [
                        f"{key}_csp{j + 1:02d}"
                        for key in model["bands"]
                        for j in range(config["csp"]["n_components"])
                    ],
                    "fit_manifest": "fit_manifest.csv",
                }
            )
            write_json(fold_dir / f"model_{name}.json", receipt)
            part = meta.iloc[test].copy()
            part["fold"], part["model"], part["y_true"], part["y_pred"] = fold, name, y[test], pred
            prediction_rows.append(part)
            all_trial_ba = classification_metrics(y[test], pred, labels)["balanced_accuracy"]
            for stratum in ("all", "unflagged", "flagged"):
                subset = (
                    part
                    if stratum == "all"
                    else part[part.artifact_flagged == (stratum == "flagged")]
                )
                if subset.empty:
                    continue
                row = {
                    "fold": fold,
                    "subject": target,
                    "model": name,
                    "stratum": stratum,
                    "n_train": len(train),
                    "n_test": len(subset),
                    "n_classes_present": subset.y_true.nunique(),
                    **classification_metrics(
                        subset.y_true.to_numpy(), subset.y_pred.to_numpy(), labels
                    ),
                }
                metric_rows.append(row)
                cm = confusion_matrix(subset.y_true, subset.y_pred, labels=labels)
                for i, true_label in enumerate(labels):
                    for j, predicted_label in enumerate(labels):
                        confusion_rows.append(
                            {
                                "fold": fold,
                                "subject": target,
                                "model": name,
                                "stratum": stratum,
                                "true_label": true_label,
                                "predicted_label": predicted_label,
                                "count": int(cm[i, j]),
                            }
                        )
            print(f"  {name}: all-trial BA={all_trial_ba:.4f}", flush=True)
        pd.concat(prediction_rows[-len(config["models"]) :], ignore_index=True).to_csv(
            fold_dir / "predictions.csv", index=False
        )
        write_json(
            fold_dir / "status.json",
            {
                "status": "complete",
                "target_subject": target,
                "elapsed_seconds": time.perf_counter() - started,
            },
        )
        # Full completed-fold checkpoints survive interruption in a later fold.
        pd.DataFrame(metric_rows).to_csv(output / "per_subject_metrics.csv", index=False)
        pd.concat(prediction_rows, ignore_index=True).to_csv(
            output / "predictions.csv", index=False
        )
        pd.concat(manifest_parts, ignore_index=True).to_csv(
            output / "fit_manifest.csv", index=False
        )
        pd.DataFrame(confusion_rows).to_csv(output / "confusion_matrices.csv", index=False)
        pd.DataFrame(feature_rows).to_csv(output / "feature_fit_times.csv", index=False)
        write_json(
            output / "status.json", {"status": "running", "completed_folds": len(manifest_parts)}
        )
    frame = pd.DataFrame(metric_rows)
    numeric = ["balanced_accuracy", "accuracy", "macro_f1", "macro_precision", "macro_recall", "cohen_kappa"]
    summary = frame.groupby(["model", "stratum"])[numeric].agg(["mean", "std"])
    summary.columns = [f"{measure}_{stat}" for measure, stat in summary.columns]
    summary.reset_index().to_csv(output / "summary.csv", index=False)
    pivot = frame.query("stratum == 'all'").pivot(
        index="subject", columns="model", values="balanced_accuracy"
    )
    reference = config["models"][0]["name"]
    deltas = pivot.subtract(pivot[reference], axis=0).drop(columns=reference)
    deltas.to_csv(output / "paired_differences_vs_broad_lda.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=ROOT / "configs/q4_e001_fourclass_filterbank.json"
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/raw")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    output = args.output_dir or ROOT / "outputs" / config["experiment_id"]
    require_new_run_directory(output)
    started = time.perf_counter()
    write_json(output / "config.json", config)
    capture_startup_provenance(ROOT, output)
    set_global_seed(config["seed"])
    mne.set_log_level("ERROR")
    try:
        files = []
        for path in sorted(args.data_dir.rglob("*.mat")):
            if path.stem in {
                f"A{s:02d}{session}" for s in config["subjects"] for session in ("T", "E")
            }:
                files.append(
                    {
                        "path": str(path.resolve()),
                        "bytes": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                )
        if len(files) != len(config["subjects"]) * 2:
            raise ValueError("Expected both local MAT files per subject before starting")
        write_json(output / "source_files.json", files)
        write_json(
            output / "status.json",
            {"status": "loading", "started_at_utc": datetime.now(UTC).isoformat()},
        )
        with threadpool_limits(limits=config["runtime"]["blas_threads"]):
            bands, meta, audit = load_configured_epochs(
                config["subjects"], args.data_dir, config["preprocessing"], config["class_ids"]
            )
            meta.to_csv(output / "trial_metadata.csv", index=False)
            audit.to_csv(output / "data_audit.csv", index=False)
            evaluate(bands, meta, config, output)
        write_json(
            output / "status.json",
            {
                "status": "complete",
                "n_trials": len(meta),
                "n_flagged": int(meta.artifact_flagged.sum()),
                "n_csp_fits": len(config["subjects"]) * len(bands),
                "n_classifier_fits": len(config["subjects"]) * len(config["models"]),
                "elapsed_seconds": time.perf_counter() - started,
                "finished_at_utc": datetime.now(UTC).isoformat(),
            },
        )
    except Exception:
        write_json(
            output / "failure.json",
            {"traceback": traceback.format_exc(), "elapsed_seconds": time.perf_counter() - started},
        )
        write_json(output / "status.json", {"status": "failed"})
        raise


if __name__ == "__main__":
    main()
