"""Check Q4-A001 against exact Q4 parent features, source fits and predictions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, cohen_kappa_score, f1_score

ROOT = Path(__file__).resolve().parents[1]


def score(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    return {
        "balanced_accuracy": balanced_accuracy_score(y, p),
        "accuracy": accuracy_score(y, p),
        "macro_f1": f1_score(y, p, labels=[1, 2, 3, 4], average="macro", zero_division=0),
        "cohen_kappa": cohen_kappa_score(y, p, labels=[1, 2, 3, 4]),
    }


def verify(output: Path, parent: Path) -> dict:
    config = json.loads((output / "config.json").read_text(encoding="utf-8"))
    status = json.loads((output / "status.json").read_text(encoding="utf-8"))
    if status["status"] != "complete" or config["feature_counts"] != [8, 16, 32, 72]:
        raise AssertionError("Ablation not complete or feature grid changed")
    original = json.loads((parent / "config.json").read_text(encoding="utf-8"))
    bands = next(m["bands"] for m in original["models"] if m["name"] == "FBCSP_LDA")
    meta = pd.read_csv(output / "trial_metadata.csv")
    pred = pd.read_csv(output / "predictions.csv")
    q4_pred = pd.read_csv(parent / "predictions.csv")
    metrics = pd.read_csv(output / "per_subject_metrics.csv")
    summary = pd.read_csv(output / "summary.csv")
    pd.testing.assert_frame_equal(meta, pd.read_csv(parent / "trial_metadata.csv"))
    pd.testing.assert_frame_equal(
        pd.read_csv(output / "fit_manifest.csv"), pd.read_csv(parent / "fit_manifest.csv")
    )
    if len(meta) != 5184 or len(pred) != 5184 * 4 or len(metrics) != 9 * 4 * 3:
        raise AssertionError("Incomplete trial/model/stratum coverage")
    if pred.duplicated(["sample_id", "model"]).any():
        raise AssertionError("Duplicate prediction")
    if set(pred.sample_id) != set(meta.sample_id) or set(pred.y_pred).difference({1, 2, 3, 4}):
        raise AssertionError("Unknown trial or class")
    hash_count = 0
    for item in json.loads((output / "parent_inputs.json").read_text(encoding="utf-8")):
        path = Path(item["path"])
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise AssertionError(f"Parent input changed: {path}")
        hash_count += 1
    score_checks = 0
    scaler_checks = 0
    endpoint_checks = 0
    for subject in config["subjects"]:
        source = meta.subject.ne(subject).to_numpy()
        test = ~source
        if source.sum() != 4608 or test.sum() != 576:
            raise AssertionError("LOSO source/target counts wrong")
        fold = f"loso_s{subject}"
        chunks = []
        for band in bands:
            with np.load(parent / "folds" / fold / f"csp_{band}.npz", allow_pickle=False) as cached:
                if not np.array_equal(cached["sample_ids"], meta.sample_id.to_numpy(dtype=str)):
                    raise AssertionError("Parent CSP trial order changed")
                chunks.append(cached["features"].copy())
        matrix = np.concatenate(chunks, axis=1)
        q4_receipt = json.loads((parent / "folds" / fold / "model_FBCSP_MI8_LDA.json").read_text())
        ranking = np.argsort(-np.asarray(q4_receipt["mi_scores"]), kind="stable")
        for k in config["feature_counts"]:
            name = f"FBCSP_MI{k}_LDA"
            part = pred[(pred.subject == subject) & (pred.model == name)]
            if len(part) != 576 or set(part.sample_id) != set(meta.loc[test, "sample_id"]):
                raise AssertionError(f"Model {name} incomplete for {fold}")
            receipt = json.loads((output / "folds" / fold / f"k{k:02d}_receipt.json").read_text())
            selected = ranking[:k]
            if receipt["selected_feature_indices"] != selected.tolist():
                raise AssertionError("Selector differs from source-only parent MI ranking")
            np.testing.assert_allclose(
                receipt["scaler_mean"],
                matrix[source][:, selected].mean(axis=0),
                rtol=1e-9,
                atol=1e-12,
            )
            np.testing.assert_allclose(
                receipt["scaler_scale"],
                matrix[source][:, selected].std(axis=0),
                rtol=1e-9,
                atol=1e-12,
            )
            scaler_checks += 1
            if k in (8, 72):
                q4_name = "FBCSP_MI8_LDA" if k == 8 else "FBCSP_LDA"
                original_part = q4_pred[
                    (q4_pred.subject == subject) & (q4_pred.model == q4_name)
                ].set_index("sample_id")
                checked_part = part.set_index("sample_id")
                if not np.array_equal(
                    checked_part.loc[original_part.index, "y_pred"], original_part.y_pred
                ):
                    raise AssertionError("Ablation endpoint differs from Q4 predictions")
                endpoint_checks += 1
            for stratum in ("all", "unflagged", "flagged"):
                selected_trials = (
                    part
                    if stratum == "all"
                    else part[part.artifact_flagged == (stratum == "flagged")]
                )
                row = metrics[
                    (metrics.subject == subject)
                    & (metrics.model == name)
                    & (metrics.stratum == stratum)
                ]
                if len(row) != 1 or int(row.iloc[0].n_test) != len(selected_trials):
                    raise AssertionError("Metric denominator mismatch")
                for measure, value in score(
                    selected_trials.y_true.to_numpy(), selected_trials.y_pred.to_numpy()
                ).items():
                    if not np.isclose(row.iloc[0][measure], value, atol=1e-10):
                        raise AssertionError("Per-subject metric mismatch")
                    score_checks += 1
    aggregate = metrics.groupby(["model", "stratum"])[
        list(score(np.array([1, 2, 3, 4]), np.array([1, 2, 3, 4])))
    ].agg(["mean", "std"])
    aggregate.columns = [f"{measure}_{stat}" for measure, stat in aggregate.columns]
    merged = summary.merge(
        aggregate.reset_index(),
        on=["model", "stratum"],
        validate="one_to_one",
        suffixes=("_saved", "_check"),
    )
    if len(merged) != 12:
        raise AssertionError("Summary coverage incomplete")
    for column in aggregate.columns:
        np.testing.assert_allclose(
            merged[f"{column}_saved"], merged[f"{column}_check"], rtol=1e-9, atol=1e-10
        )
    provenance = json.loads((output / "provenance/manifest.json").read_text())
    for item in provenance["source_files"]:
        archived = output / "provenance/source" / item["path"]
        if hashlib.sha256(archived.read_bytes()).hexdigest() != item["sha256"]:
            raise AssertionError("Startup source snapshot damaged")
    return {
        "status": "passed",
        "n_trials": len(meta),
        "n_predictions": len(pred),
        "n_score_scalar_checks": score_checks,
        "n_scaler_source_fit_checks": scaler_checks,
        "n_q4_endpoint_prediction_checks": endpoint_checks,
        "n_parent_input_hashes": hash_count,
        "note": "Exploratory feature-count sweep; no target-based selection or independent confirmation.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, nargs="?", default=ROOT / "outputs/Q4-A001")
    parser.add_argument("--parent", type=Path, default=ROOT / "outputs/Q4-E001")
    args = parser.parse_args()
    result = verify(args.output, args.parent)
    (args.output / "validation_report.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
