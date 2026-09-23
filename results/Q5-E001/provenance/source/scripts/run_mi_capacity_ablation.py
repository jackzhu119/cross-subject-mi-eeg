"""Post-Q4 exploratory MI feature-count sweep using immutable outer-fold CSP features."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.feature_selection import mutual_info_classif
from sklearn.metrics import accuracy_score, balanced_accuracy_score, cohen_kappa_score, f1_score
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from mi_eeg.provenance import capture_startup_provenance, require_new_run_directory
from mi_eeg.reproducibility import set_global_seed

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, content: object) -> None:
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")


def metrics(y: np.ndarray, pred: np.ndarray, labels: list[int]) -> dict[str, float]:
    return {
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "accuracy": float(accuracy_score(y, pred)),
        "macro_f1": float(f1_score(y, pred, labels=labels, average="macro", zero_division=0)),
        "cohen_kappa": float(cohen_kappa_score(y, pred, labels=labels)),
    }


def run(config: dict, parent: Path, output: Path) -> None:
    parent_status = json.loads((parent / "status.json").read_text(encoding="utf-8"))
    parent_valid = json.loads((parent / "validation_report.json").read_text(encoding="utf-8"))
    parent_config = json.loads((parent / "config.json").read_text(encoding="utf-8"))
    if parent_status["status"] != "complete" or parent_valid["status"] != "passed":
        raise ValueError("Q4 source must be complete and independently validated")
    if (
        config["subjects"] != parent_config["subjects"]
        or config["class_ids"] != parent_config["class_ids"]
    ):
        raise ValueError("Subject or label policy differs from Q4")
    if config["seed"] != parent_config["seed"]:
        raise ValueError("MI random state differs from Q4")
    target_models = {item["name"]: item for item in parent_config["models"]}
    frequency_bands = target_models["FBCSP_MI8_LDA"]["bands"]
    if frequency_bands != target_models["FBCSP_LDA"]["bands"]:
        raise AssertionError("Parent filter-bank models use different frequency bands")
    if config["feature_counts"] != [8, 16, 32, 72]:
        raise ValueError("This fixed ablation script supports the documented 8/16/32/72 grid")
    meta = pd.read_csv(parent / "trial_metadata.csv")
    parent_predictions = pd.read_csv(parent / "predictions.csv")
    parent_manifest = pd.read_csv(parent / "fit_manifest.csv")
    shutil.copy2(parent / "trial_metadata.csv", output / "trial_metadata.csv")
    shutil.copy2(parent / "fit_manifest.csv", output / "fit_manifest.csv")
    inputs = []
    for name in (
        "config.json",
        "status.json",
        "validation_report.json",
        "trial_metadata.csv",
        "fit_manifest.csv",
        "predictions.csv",
    ):
        path = parent / name
        inputs.append(
            {"path": str(path.resolve()), "sha256": digest(path), "bytes": path.stat().st_size}
        )
    labels = sorted(config["class_ids"].values())
    y = meta.label.to_numpy()
    rows, metric_rows = [], []
    for target in config["subjects"]:
        fold = f"loso_s{target}"
        fold_dir = parent / "folds" / fold
        target_folder = output / "folds" / fold
        target_folder.mkdir(parents=True, exist_ok=False)
        source = meta.subject.ne(target).to_numpy()
        test = ~source
        if source.sum() != 4608 or test.sum() != 576:
            raise AssertionError("Outer partition mismatch")
        expected_split = parent_manifest[parent_manifest.fold == fold]
        if set(expected_split[expected_split.role == "train"].sample_id) != set(
            meta.loc[source, "sample_id"]
        ):
            raise AssertionError("Cached feature split differs from manifest")
        chunks = []
        for band in frequency_bands:
            path = fold_dir / f"csp_{band}.npz"
            inputs.append(
                {"path": str(path.resolve()), "sha256": digest(path), "bytes": path.stat().st_size}
            )
            with np.load(path, allow_pickle=False) as cached:
                if not np.array_equal(cached["sample_ids"], meta.sample_id.to_numpy(dtype=str)):
                    raise AssertionError("CSP sample order mismatch")
                chunks.append(cached["features"].copy())
        matrix = np.concatenate(chunks, axis=1)
        if matrix.shape != (len(meta), 72):
            raise AssertionError("Expected nine bands x eight CSP components")
        receipt = json.loads((fold_dir / "model_FBCSP_MI8_LDA.json").read_text(encoding="utf-8"))
        scores = np.asarray(receipt["mi_scores"], dtype=float)
        recomputed = mutual_info_classif(
            matrix[source], y[source], random_state=config["seed"], **parent_config["mi_selection"]
        )
        np.testing.assert_allclose(scores, recomputed, rtol=1e-12, atol=1e-12)
        if receipt["selected_feature_indices"] != np.argsort(-scores, kind="stable")[:8].tolist():
            raise AssertionError(
                "Parent MI8 selected feature receipt differs from source MI scores"
            )
        order = np.argsort(-scores, kind="stable")
        for k in config["feature_counts"]:
            chosen = order[:k]
            scaler = StandardScaler().fit(matrix[source][:, chosen])
            clf = LinearDiscriminantAnalysis(**parent_config["lda"])
            clf.fit(scaler.transform(matrix[source][:, chosen]), y[source])
            pred = clf.predict(scaler.transform(matrix[test][:, chosen]))
            if k in (8, 72):
                parent_name = "FBCSP_MI8_LDA" if k == 8 else "FBCSP_LDA"
                previous = parent_predictions[
                    (parent_predictions.subject == target)
                    & (parent_predictions.model == parent_name)
                ]
                previous = previous.set_index("sample_id").loc[meta.loc[test, "sample_id"]]
                if not np.array_equal(pred, previous.y_pred.to_numpy()):
                    raise AssertionError(f"k={k} does not reproduce Q4 predictions: {fold}")
            write_json(
                target_folder / f"k{k:02d}_receipt.json",
                {
                    "fold": fold,
                    "target_subject": target,
                    "k": k,
                    "source_rows": int(source.sum()),
                    "target_rows": int(test.sum()),
                    "selected_feature_indices": chosen.tolist(),
                    "scaler_mean": scaler.mean_.tolist(),
                    "scaler_scale": scaler.scale_.tolist(),
                    "classifier_coef": clf.coef_.tolist(),
                    "classifier_intercept": clf.intercept_.tolist(),
                    "mi_scores_source_only": scores.tolist(),
                    "parent_feature_files": [f"csp_{band}.npz" for band in frequency_bands],
                },
            )
            part = meta.loc[test].copy()
            part["fold"] = fold
            part["model"] = f"FBCSP_MI{k}_LDA"
            part["y_true"] = y[test]
            part["y_pred"] = pred
            rows.append(part)
            for stratum in ("all", "unflagged", "flagged"):
                selection = (
                    part
                    if stratum == "all"
                    else part[part.artifact_flagged == (stratum == "flagged")]
                )
                if selection.empty:
                    continue
                metric_rows.append(
                    {
                        "fold": fold,
                        "subject": target,
                        "k": k,
                        "model": f"FBCSP_MI{k}_LDA",
                        "stratum": stratum,
                        "n_train": int(source.sum()),
                        "n_test": len(selection),
                        **metrics(selection.y_true.to_numpy(), selection.y_pred.to_numpy(), labels),
                    }
                )
            print(
                f"{fold} k={k}: BA={metrics(y[test], pred, labels)['balanced_accuracy']:.4f}",
                flush=True,
            )
        pd.concat(rows, ignore_index=True).to_csv(output / "predictions.csv", index=False)
        pd.DataFrame(metric_rows).to_csv(output / "per_subject_metrics.csv", index=False)
        write_json(output / "status.json", {"status": "running", "completed_folds": target})
    measures = ["balanced_accuracy", "accuracy", "macro_f1", "cohen_kappa"]
    summary = pd.DataFrame(metric_rows).groupby(["model", "stratum"])[measures].agg(["mean", "std"])
    summary.columns = [f"{name}_{stat}" for name, stat in summary.columns]
    summary.reset_index().to_csv(output / "summary.csv", index=False)
    write_json(output / "parent_inputs.json", inputs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/q4_a001_mi_capacity.json")
    parser.add_argument("--parent", type=Path, default=ROOT / "outputs/Q4-E001")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    output = args.output_dir or ROOT / "outputs" / config["experiment_id"]
    require_new_run_directory(output)
    write_json(output / "config.json", config)
    capture_startup_provenance(ROOT, output)
    set_global_seed(config["seed"])
    start = time.perf_counter()
    try:
        with threadpool_limits(limits=2):
            run(config, args.parent, output)
        write_json(
            output / "status.json",
            {
                "status": "complete",
                "n_subjects": 9,
                "n_models": 4,
                "elapsed_seconds": time.perf_counter() - start,
            },
        )
    except Exception:
        write_json(output / "failure.json", {"traceback": traceback.format_exc()})
        write_json(output / "status.json", {"status": "failed"})
        raise


if __name__ == "__main__":
    main()
