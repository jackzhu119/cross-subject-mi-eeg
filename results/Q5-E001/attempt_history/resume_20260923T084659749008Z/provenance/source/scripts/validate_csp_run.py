"""Independently validate a finished CSP experiment's splits and score tables."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    return parser.parse_args()


def main() -> None:
    run_dir = parse_args().run_dir.resolve()
    status = json.loads((run_dir / "run_status.json").read_text(encoding="utf-8"))
    if status["status"] != "complete":
        raise AssertionError(f"Run is not complete: {status['status']}")
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    metadata = pd.read_csv(run_dir / "trial_metadata.csv")
    audit = pd.read_csv(run_dir / "data_audit.csv")
    manifest = pd.read_csv(run_dir / "split_manifest.csv")
    predictions = pd.read_csv(run_dir / "predictions.csv")
    subject_metrics = pd.read_csv(run_dir / "subject_metrics.csv")
    summary = pd.read_csv(run_dir / "summary.csv")
    source_files = json.loads((run_dir / "source_files.json").read_text(encoding="utf-8"))

    assert len(metadata) == len(audit) * 24 - int(audit["n_left_right_rejected"].sum())
    assert len(metadata) == int(audit["n_left_right_kept"].sum())
    assert metadata["sample_id"].is_unique
    assert set(metadata["label"]) == {1, 2}
    assert set(metadata["subject"]) == set(config["effective_subjects"])
    assert set(audit["n_times_per_epoch"]) == {750}
    assert set(audit["n_eeg_channels"]) == {22}
    assert set(audit["sampling_rate_hz"]) == {250.0}
    assert (audit["n_left_kept"] + audit["n_right_kept"] == audit["n_left_right_kept"]).all()
    if config.get("effective_artifact_policy", "exclude") == "exclude":
        if "n_left_right_flagged" in audit:
            assert (audit["n_left_right_flagged"] == audit["n_left_right_rejected"]).all()
    else:
        assert (audit["n_left_right_rejected"] == 0).all()

    n_folds = 0
    for (mode, fold_id), group in manifest.groupby(["mode", "fold_id"]):
        train = group[group["role"] == "train"]
        test = group[group["role"] == "test"]
        assert not train.empty and not test.empty, fold_id
        assert set(train["sample_id"]).isdisjoint(test["sample_id"]), fold_id
        if mode == "cross_subject":
            assert set(train["subject"]).isdisjoint(test["subject"]), fold_id
            assert set(test["session"]) == {"0train", "1test"}, fold_id
        elif mode == "cross_session":
            assert set(train["subject"]) == set(test["subject"]), fold_id
            assert set(train["session"]) == {"0train"}, fold_id
            assert set(test["session"]) == {"1test"}, fold_id
        elif mode == "within_session":
            assert set(train["subject"]) == set(test["subject"]), fold_id
            assert set(train["session"]) == set(test["session"]), fold_id
            assert set(train["run"]).isdisjoint(test["run"]), fold_id
        else:
            raise AssertionError(f"Unknown evaluation mode: {mode}")
        n_folds += 1

    assert not predictions.duplicated(["mode", "model", "sample_id"]).any()
    for (mode, fold_id, model), group in predictions.groupby(["mode", "fold_id", "model"]):
        test_ids = set(
            manifest.loc[
                (manifest["mode"] == mode)
                & (manifest["fold_id"] == fold_id)
                & (manifest["role"] == "test"),
                "sample_id",
            ]
        )
        assert set(group["sample_id"]) == test_ids, (mode, fold_id, model)

    for row in subject_metrics.itertuples(index=False):
        group = predictions[
            (predictions["mode"] == row.mode)
            & (predictions["model"] == row.model)
            & (predictions["subject"] == row.subject)
        ]
        assert len(group) == row.n_test
        recomputed = balanced_accuracy_score(group["y_true"], group["y_pred"])
        assert np.isclose(recomputed, row.balanced_accuracy, atol=1e-12)

    for row in summary.itertuples(index=False):
        group = subject_metrics[
            (subject_metrics["mode"] == row.mode) & (subject_metrics["model"] == row.model)
        ]
        assert len(group) == row.n_subjects
        assert np.isclose(group["balanced_accuracy"].mean(), row.mean_balanced_accuracy, atol=1e-12)
        if len(group) > 1:
            assert np.isclose(
                group["balanced_accuracy"].std(ddof=1), row.sd_balanced_accuracy, atol=1e-12
            )

    for item in source_files:
        path = Path(item["path"])
        assert path.is_file(), path
        assert path.stat().st_size == item["bytes"], path
        with path.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        assert digest == item["sha256"], path

    result = {
        "status": "validated",
        "n_subjects": len(set(metadata["subject"])),
        "n_clean_trials": len(metadata),
        "n_excluded_left_right_trials": int(audit["n_left_right_rejected"].sum()),
        "n_folds": n_folds,
        "n_predictions": len(predictions),
        "n_source_files_hash_verified": len(source_files),
        "checks": [
            "trial counts and epoch dimensions",
            "unique sample identifiers",
            "train/test disjointness and unit-specific split boundaries",
            "prediction coverage per fold and model",
            "independent balanced-accuracy recomputation",
            "subject-equal summary recomputation",
            "source file size and SHA-256 integrity",
        ],
    }
    (run_dir / "validation_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
