"""Independently audit P3 source hashes, fixed test IDs, LOSO isolation and scores."""

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
    run = parser.parse_args().run_dir.resolve()
    status = json.loads((run / "run_status.json").read_text(encoding="utf-8"))
    assert status["status"] == "complete"
    protocol_bytes = (run / "protocol.json").read_bytes()
    metadata_run = json.loads((run / "run_metadata.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(protocol_bytes).hexdigest() == metadata_run["protocol_sha256"]
    protocol = json.loads(protocol_bytes)
    meta = pd.read_csv(run / "trial_metadata.csv")
    audit = pd.read_csv(run / "data_audit.csv")
    splits = pd.read_csv(run / "split_manifest.csv")
    predictions = pd.read_csv(run / "predictions.csv")
    subjects = pd.read_csv(run / "subject_metrics.csv")
    summary = pd.read_csv(run / "summary.csv")
    contrasts = json.loads((run / "paired_contrasts.json").read_text(encoding="utf-8"))
    files = json.loads((run / "source_files.json").read_text(encoding="utf-8"))
    # P3-E001 saved pandas object-string IDs; this is a locally generated, trusted artifact.
    # Subsequent runs write plain Unicode arrays and do not require pickle loading.
    features = np.load(run / "welch_features.npz", allow_pickle=True)

    assert len(meta) == 2592 and meta["sample_id"].is_unique
    assert int(meta["artifact_flagged"].sum()) == 246
    assert set(meta["subject"]) == set(protocol["subjects"]) == set(range(1, 10))
    assert features["features"].shape == (2592, 88)
    assert np.array_equal(features["sample_id"], meta["sample_id"].to_numpy())
    assert np.isfinite(features["features"]).all()
    assert len(audit) == 108 and int(audit["n_left_right_flagged"].sum()) == 246
    assert set(audit["n_times_per_epoch"]) == {750}

    models = set(protocol["candidate_models"])
    policies = set(protocol["training_artifact_policies"])
    assert set(predictions["model"]) == models
    assert set(predictions["training_policy"]) == policies
    assert not predictions.duplicated(["training_policy", "model", "sample_id"]).any()
    meta_by_id = meta.set_index("sample_id")
    assert (
        predictions["artifact_flagged"].to_numpy()
        == meta_by_id.loc[predictions["sample_id"], "artifact_flagged"].to_numpy()
    ).all()
    assert (
        predictions["y_true"].to_numpy()
        == meta_by_id.loc[predictions["sample_id"], "label"].to_numpy()
    ).all()

    for subject in range(1, 10):
        fold = f"loso_s{subject}"
        fold_meta = meta[meta["subject"] == subject]
        clean_ids = set(fold_meta.loc[~fold_meta["artifact_flagged"], "sample_id"])
        flagged_ids = set(fold_meta.loc[fold_meta["artifact_flagged"], "sample_id"])
        source = meta[meta["subject"] != subject]
        for policy in policies:
            part = splits[(splits["fold_id"] == fold) & (splits["training_policy"] == policy)]
            train = part[part["role"] == "train"]
            test_clean = part[part["role"] == "test_clean"]
            test_flagged = part[part["role"] == "test_flagged"]
            expected_train = (
                source[~source["artifact_flagged"]] if policy == "expert_clean_only" else source
            )
            assert set(train["sample_id"]) == set(expected_train["sample_id"])
            assert set(test_clean["sample_id"]) == clean_ids
            assert set(test_flagged["sample_id"]) == flagged_ids
            assert set(train["subject"]).isdisjoint({subject})
            assert set(train["sample_id"]).isdisjoint(clean_ids | flagged_ids)
            for model in models:
                pred = predictions[
                    (predictions["fold_id"] == fold)
                    & (predictions["training_policy"] == policy)
                    & (predictions["model"] == model)
                ]
                assert set(pred["sample_id"]) == clean_ids | flagged_ids

    for row in subjects.itertuples(index=False):
        group = predictions[
            (predictions["training_policy"] == row.training_policy)
            & (predictions["model"] == row.model)
            & (predictions["subject"] == row.subject)
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
        if set(group["y_true"]) == {1, 2}:
            assert np.isclose(
                balanced_accuracy_score(group["y_true"], group["y_pred"]),
                row.balanced_accuracy,
                atol=1e-12,
            )
        else:
            assert pd.isna(row.balanced_accuracy)

    for row in summary.itertuples(index=False):
        group = subjects[
            (subjects["training_policy"] == row.training_policy)
            & (subjects["model"] == row.model)
            & (subjects["test_stratum"] == row.test_stratum)
        ]
        values = group["balanced_accuracy"].dropna()
        assert len(values) == row.n_subjects_scored
        assert int(group["n_test"].sum()) == row.n_test_trials
        assert np.isclose(values.mean(), row.mean_balanced_accuracy, atol=1e-12)
        if len(values) > 1:
            assert np.isclose(values.std(ddof=1), row.sd_balanced_accuracy, atol=1e-12)

    clean = subjects[subjects["test_stratum"] == "clean"]
    wide = clean.pivot(
        index="subject", columns=["training_policy", "model"], values="balanced_accuracy"
    )
    for name, item in contrasts.items():
        if name == "PSD_minus_CSP_clean_training":
            left, right = (
                ("expert_clean_only", "WelchPSD88+shrinkageLDA"),
                ("expert_clean_only", "CSP4+shrinkageLDA"),
            )
        elif name == "Fusion_minus_CSP_clean_training":
            left, right = (
                ("expert_clean_only", "CSP4+WelchPSD88+shrinkageLDA"),
                ("expert_clean_only", "CSP4+shrinkageLDA"),
            )
        else:
            model = name.split("__", 1)[1]
            left, right = ("all_trials", model), ("expert_clean_only", model)
        difference = wide[left] - wide[right]
        assert np.isclose(difference.mean(), item["mean_paired_difference_ba"], atol=1e-12)
        assert len(item["per_subject_differences"]) == 9

    for item in files:
        path = Path(item["path"])
        assert path.is_file() and path.stat().st_size == item["bytes"]
        with path.open("rb") as handle:
            assert hashlib.file_digest(handle, "sha256").hexdigest() == item["sha256"]

    report = {
        "status": "validated",
        "n_subjects": 9,
        "n_trials": len(meta),
        "n_expert_flagged": int(meta["artifact_flagged"].sum()),
        "n_predictions": len(predictions),
        "n_model_fits": 54,
        "n_source_files_hash_verified": len(files),
        "checks": [
            "protocol copy integrity",
            "FFT feature shape and trial alignment",
            "identical clean held-out test IDs across training policies",
            "subject-disjoint LOSO source training",
            "complete per-model prediction coverage",
            "independent per-subject and summary balanced-accuracy recalculation",
            "paired contrast recalculation",
            "source file size and SHA-256 integrity",
        ],
    }
    (run / "validation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
