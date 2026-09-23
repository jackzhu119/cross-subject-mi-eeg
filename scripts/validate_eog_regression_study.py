"""Audit EOG-assisted LOSO predictions and optional P3 uncorrected agreement."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--reference-p3", type=Path)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    status = json.loads((run / "run_status.json").read_text(encoding="utf-8"))
    assert status["status"] == "complete"
    protocol_bytes = (run / "protocol.json").read_bytes()
    run_metadata = json.loads((run / "run_metadata.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(protocol_bytes).hexdigest() == run_metadata["protocol_sha256"]
    meta = pd.read_csv(run / "trial_metadata.csv")
    audit = pd.read_csv(run / "data_audit.csv")
    predictions = pd.read_csv(run / "predictions.csv")
    scores = pd.read_csv(run / "subject_metrics.csv")
    summary = pd.read_csv(run / "summary.csv")
    qc = pd.read_csv(run / "eog_qc.csv")
    coefficients = pd.read_csv(run / "eog_coefficients.csv")
    contrast = json.loads((run / "paired_contrast.json").read_text(encoding="utf-8"))
    source_files = json.loads((run / "source_files.json").read_text(encoding="utf-8"))

    assert len(meta) == 2592 and meta["sample_id"].is_unique
    assert int(meta["artifact_flagged"].sum()) == 246
    assert len(audit) == 108 and int(audit["n_left_right_flagged"].sum()) == 246
    assert len(qc) == 9 and qc["fold_id"].is_unique
    assert len(coefficients) == 9 * 3 * 22
    assert np.isfinite(coefficients["coefficient"]).all()
    assert np.isfinite(qc.select_dtypes(include="number")).all().all()
    conditions = {"uncorrected", "source_train_fitted_EOG_regression"}
    assert set(predictions["condition"]) == conditions
    assert len(predictions) == 2 * len(meta)
    assert not predictions.duplicated(["condition", "sample_id"]).any()
    meta_by_id = meta.set_index("sample_id")
    for condition, group in predictions.groupby("condition"):
        assert condition in conditions
        assert set(group["sample_id"]) == set(meta["sample_id"])
        assert (
            group["y_true"].to_numpy() == meta_by_id.loc[group["sample_id"], "label"].to_numpy()
        ).all()
        assert (
            group["artifact_flagged"].to_numpy()
            == meta_by_id.loc[group["sample_id"], "artifact_flagged"].to_numpy()
        ).all()
        assert all(group["fold_id"] == "loso_s" + group["subject"].astype(str))

    for row in scores.itertuples(index=False):
        group = predictions[
            (predictions["condition"] == row.condition) & (predictions["subject"] == row.subject)
        ]
        if row.test_stratum == "clean":
            group = group[~group["artifact_flagged"]]
        elif row.test_stratum == "flagged":
            group = group[group["artifact_flagged"]]
        else:
            assert row.test_stratum == "all"
        assert len(group) == row.n_test
        assert int((group["y_true"] == 1).sum()) == row.n_left
        assert int((group["y_true"] == 2).sum()) == row.n_right
        assert np.isclose(
            balanced_accuracy_score(group["y_true"], group["y_pred"]),
            row.balanced_accuracy,
            atol=1e-12,
        )

    for row in summary.itertuples(index=False):
        group = scores[
            (scores["condition"] == row.condition) & (scores["test_stratum"] == row.test_stratum)
        ]
        assert len(group) == row.n_subjects == 9
        assert int(group["n_test"].sum()) == row.n_test_trials
        assert np.isclose(group["balanced_accuracy"].mean(), row.mean_balanced_accuracy, atol=1e-12)
        assert np.isclose(
            group["balanced_accuracy"].std(ddof=1), row.sd_balanced_accuracy, atol=1e-12
        )

    clean = scores[scores["test_stratum"] == "clean"].pivot(
        index="subject", columns="condition", values="balanced_accuracy"
    )
    difference = clean["source_train_fitted_EOG_regression"] - clean["uncorrected"]
    assert np.isclose(difference.mean(), contrast["mean_paired_difference_ba"], atol=1e-12)
    assert len(contrast["per_subject_differences"]) == 9

    p3_equal = None
    if args.reference_p3 is not None:
        p3 = pd.read_csv(args.reference_p3 / "predictions.csv")
        p3 = (
            p3[
                (p3["training_policy"] == "expert_clean_only")
                & (p3["model"] == "CSP4+shrinkageLDA")
            ][["sample_id", "y_pred"]]
            .sort_values("sample_id")
            .reset_index(drop=True)
        )
        p4 = (
            predictions[predictions["condition"] == "uncorrected"][["sample_id", "y_pred"]]
            .sort_values("sample_id")
            .reset_index(drop=True)
        )
        p3_equal = bool(p3.equals(p4))
        assert p3_equal, "Uncorrected P4 branch differs from identical P3 branch"

    for item in source_files:
        path = Path(item["path"])
        assert path.is_file() and path.stat().st_size == item["bytes"]
        with path.open("rb") as handle:
            assert hashlib.file_digest(handle, "sha256").hexdigest() == item["sha256"]

    report = {
        "status": "validated",
        "n_subjects": 9,
        "n_predictions": len(predictions),
        "n_frozen_coefficient_values": len(coefficients),
        "n_source_files_hash_verified": len(source_files),
        "uncorrected_predictions_identical_to_p3": p3_equal,
        "checks": [
            "protocol copy integrity",
            "EEG/EOG aligned trial-count audit",
            "identical test IDs and labels across correction conditions",
            "independent per-subject and summary score recomputation",
            "paired contrast recomputation",
            "finite source-fitted coefficient and descriptive QC tables",
            "source file size and SHA-256 integrity",
        ],
    }
    (run / "validation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
