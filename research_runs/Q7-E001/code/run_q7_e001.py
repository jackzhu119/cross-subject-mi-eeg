from __future__ import annotations

import json
import hashlib
from pathlib import Path
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import torch
import mne
from threadpoolctl import threadpool_limits

from mi_eeg.data.bnci_epochs import load_configured_epochs
from mi_eeg.evaluation.splits import iter_loso
from mi_eeg.preprocessing.source_normalization import (
    fit_source_channel_standardizer,
    apply_channel_standardizer,
)
from mi_eeg.models.eegnet_training import predict_probabilities
from scripts.run_eegnet import (
    fit_for_epochs,
    score_predictions,
    cpu_state,
)

Q5 = Path("/workspace/Q5_EEGNet_Cloud_Ready")
Q6 = Path("/workspace/Q6_EEGNet_SourceNorm")
Q7 = Path("/workspace/Q7_Mechanistic_Ablation")
OUT = Q7 / "results/Q7-E001"

CONFIG_PATH = Q6 / "configs/q6_e001_source_channel_zscore.json"
DATA_DIR = Q5 / "data/raw"

TARGET = 3
SEEDS = [20260924, 20260925, 20260926]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def check_parent_epochs():
    q5sel = pd.read_csv(Q5 / "results/Q5-E001/selection.csv")
    q6sel = pd.read_csv(Q6 / "results/Q6-E001/selection.csv")

    q5_epoch = int(
        q5sel.loc[q5sel.fold == "loso_s3", "selected_epochs"].iloc[0]
    )
    q6_epoch = int(
        q6sel.loc[q6sel.fold == "loso_s3", "selected_epochs"].iloc[0]
    )

    if q5_epoch != 2:
        raise AssertionError(f"Expected Q5 S3 epoch=2, got {q5_epoch}")

    if q6_epoch != 16:
        raise AssertionError(f"Expected Q6 S3 epoch=16, got {q6_epoch}")

    return q5_epoch, q6_epoch


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    q5_epoch, q6_epoch = check_parent_epochs()

    protocol = {
        "experiment_id": "Q7-E001",
        "type": "mechanistic_factorial_ablation",
        "target_subject": 3,
        "parent_experiments": ["Q5-E001", "Q6-E001"],
        "factor_1": "source_channel_normalization",
        "factor_2": "fixed_training_duration",
        "existing_cells": {
            "A": {
                "normalization": False,
                "epochs": q5_epoch,
                "source": "Q5-E001",
            },
            "D": {
                "normalization": True,
                "epochs": q6_epoch,
                "source": "Q6-E001",
            },
        },
        "new_cells": {
            "B": {
                "normalization": True,
                "epochs": q5_epoch,
            },
            "C": {
                "normalization": False,
                "epochs": q6_epoch,
            },
        },
        "seeds": SEEDS,
        "target_information_used_for_training": False,
        "note": (
            "Q7 tests a predeclared mechanistic 2x2 factorial reconstruction "
            "for S3. Q5/Q6 test outcomes are not used to tune B or C."
        ),
    }

    write_json(OUT / "protocol.json", protocol)

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    print("DEVICE:", device)
    print("Loading exact Q5/Q6 preprocessing...")

    mne.set_log_level("ERROR")

    with threadpool_limits(limits=2):
        bands, meta, audit = load_configured_epochs(
            config["subjects"],
            DATA_DIR,
            config["preprocessing"],
            config["class_ids"],
        )

    signal = bands["broad"]

    if signal.shape != (5184, 22, 750):
        raise AssertionError(f"Unexpected signal shape: {signal.shape}")

    signal *= np.float32(
        config["input"]["volts_to_microvolts"]
    )

    if not np.isfinite(signal).all():
        raise AssertionError("Non-finite EEG")

    # Verify exact trial identity against frozen Q6.
    q6_meta = pd.read_csv(
        Q6 / "results/Q6-E001/trial_metadata.csv"
    )

    if len(meta) != len(q6_meta):
        raise AssertionError("Q7/Q6 metadata length differs")

    for col in ["sample_id", "subject", "label"]:
        if not np.array_equal(
            meta[col].astype(str).to_numpy(),
            q6_meta[col].astype(str).to_numpy(),
        ):
            raise AssertionError(f"Q7/Q6 metadata mismatch: {col}")

    meta.to_csv(OUT / "trial_metadata.csv", index=False)
    audit.to_csv(OUT / "data_audit.csv", index=False)

    raw_x = torch.from_numpy(signal).to(device)

    y = torch.as_tensor(
        meta.label.to_numpy(dtype=np.int64) - 1,
        dtype=torch.long,
        device=device,
    )

    # Find exact S3 LOSO indices.
    found = False

    for fold, train_idx, test_idx in iter_loso(meta):
        target = int(meta.iloc[test_idx].subject.unique().item())

        if target == TARGET:
            found = True
            break

    if not found:
        raise RuntimeError("Could not find S3 LOSO fold")

    if fold != "loso_s3":
        raise AssertionError(f"Unexpected fold: {fold}")

    source_subjects = sorted(
        int(x)
        for x in meta.iloc[train_idx].subject.unique()
    )

    if source_subjects != [1, 2, 4, 5, 6, 7, 8, 9]:
        raise AssertionError(
            f"Unexpected S3 source subjects: {source_subjects}"
        )

    if len(train_idx) != 4608 or len(test_idx) != 576:
        raise AssertionError(
            f"Unexpected LOSO sizes: train={len(train_idx)}, test={len(test_idx)}"
        )

    # Fit exactly one source-only scaler for Condition B.
    scaler = fit_source_channel_standardizer(
        signal,
        meta,
        train_idx,
        source_subjects,
        min_std_microvolts=config["input"]["normalization"][
            "min_std_microvolts"
        ],
    )

    receipt = scaler.receipt(
        fold="loso_s3",
        stage="q7_full_source",
        inner_fold=None,
    )

    write_json(
        OUT / "condition_B_source_normalizer.json",
        receipt,
    )

    if receipt["target_fitted_transform"] is not False:
        raise AssertionError("Target leakage flag invalid")

    norm_x = apply_channel_standardizer(
        raw_x,
        scaler,
    )

    conditions = {
        "B": {
            "name": "SourceNorm_plus_2epochs",
            "x": norm_x,
            "epochs": 2,
            "normalization": True,
        },
        "C": {
            "name": "Raw_plus_16epochs",
            "x": raw_x,
            "epochs": 16,
            "normalization": False,
        },
    }

    metric_frames = []
    confusion_frames = []
    prediction_frames = []
    curve_rows = []
    checkpoint_rows = []

    for condition_id, condition in conditions.items():

        condition_dir = OUT / f"condition_{condition_id}"
        condition_dir.mkdir(parents=True, exist_ok=True)

        print()
        print(
            f"===== CONDITION {condition_id}: "
            f"{condition['name']} ====="
        )

        for seed in SEEDS:

            print(
                f"Training condition={condition_id}, "
                f"seed={seed}, epochs={condition['epochs']}"
            )

            model, curve = fit_for_epochs(
                condition["x"],
                y,
                train_idx,
                None,
                seed,
                condition["epochs"],
                config,
                device,
            )

            for row in curve:
                curve_rows.append(
                    {
                        "condition": condition_id,
                        "condition_name": condition["name"],
                        "fold": "loso_s3",
                        "subject": 3,
                        "seed": seed,
                        "fixed_epochs": condition["epochs"],
                        **row,
                    }
                )

            ckpt = condition_dir / f"seed_{seed}.pt"

            torch.save(
                {
                    "experiment_id": "Q7-E001",
                    "condition": condition_id,
                    "condition_name": condition["name"],
                    "fold": "loso_s3",
                    "target_subject": 3,
                    "seed": seed,
                    "fixed_epochs": condition["epochs"],
                    "normalization": condition["normalization"],
                    "model_state": cpu_state(model),
                },
                ckpt,
            )

            ckpt_sha = sha256_file(ckpt)

            checkpoint_rows.append(
                {
                    "condition": condition_id,
                    "seed": seed,
                    "checkpoint": str(ckpt),
                    "sha256": ckpt_sha,
                }
            )

            probabilities = predict_probabilities(
                model,
                condition["x"],
                test_idx,
                config["training"]["batch_size"],
            )

            part = meta.iloc[test_idx].copy().reset_index(drop=True)

            part["experiment_id"] = "Q7-E001"
            part["condition"] = condition_id
            part["condition_name"] = condition["name"]
            part["fold"] = "loso_s3"
            part["seed"] = seed
            part["fixed_epochs"] = condition["epochs"]
            part["normalization"] = condition["normalization"]
            part["y_true"] = part.label.astype(int)
            part["y_pred"] = (
                probabilities.argmax(axis=1).astype(int) + 1
            )

            for i, label in enumerate([1, 2, 3, 4]):
                part[f"p_class_{label}"] = probabilities[:, i]

            metric_rows, confusion_rows = score_predictions(
                part,
                [1, 2, 3, 4],
                "loso_s3",
                seed,
                len(train_idx),
            )

            metrics_df = pd.DataFrame(metric_rows)
            metrics_df["condition"] = condition_id
            metrics_df["condition_name"] = condition["name"]
            metrics_df["fixed_epochs"] = condition["epochs"]
            metrics_df["normalization"] = condition["normalization"]

            confusion_df = pd.DataFrame(confusion_rows)
            confusion_df["condition"] = condition_id
            confusion_df["condition_name"] = condition["name"]
            confusion_df["fixed_epochs"] = condition["epochs"]
            confusion_df["normalization"] = condition["normalization"]
            confusion_df["model"] = "EEGNet"

            part.to_csv(
                condition_dir / f"predictions_seed_{seed}.csv",
                index=False,
            )

            metrics_df.to_csv(
                condition_dir / f"metrics_seed_{seed}.csv",
                index=False,
            )

            confusion_df.to_csv(
                condition_dir / f"confusion_seed_{seed}.csv",
                index=False,
            )

            prediction_frames.append(part)
            metric_frames.append(metrics_df)
            confusion_frames.append(confusion_df)

            ba = float(
                metrics_df.loc[
                    metrics_df.stratum == "all",
                    "balanced_accuracy",
                ].iloc[0]
            )

            print(
                f"Condition {condition_id}, seed {seed}: "
                f"BA={ba:.6f}"
            )

            del model

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    pd.concat(
        prediction_frames,
        ignore_index=True,
    ).to_csv(
        OUT / "predictions.csv",
        index=False,
    )

    pd.concat(
        metric_frames,
        ignore_index=True,
    ).to_csv(
        OUT / "per_subject_metrics.csv",
        index=False,
    )

    pd.concat(
        confusion_frames,
        ignore_index=True,
    ).to_csv(
        OUT / "confusion_matrices.csv",
        index=False,
    )

    pd.DataFrame(curve_rows).to_csv(
        OUT / "learning_curves.csv",
        index=False,
    )

    pd.DataFrame(checkpoint_rows).to_csv(
        OUT / "checkpoint_hashes.csv",
        index=False,
    )

    write_json(
        OUT / "status.json",
        {
            "status": "complete",
            "experiment_id": "Q7-E001",
            "target_subject": 3,
            "conditions_completed": ["B", "C"],
            "final_fits": 6,
            "q5_q6_reused_cells": ["A", "D"],
            "finished_at_utc": datetime.now(UTC).isoformat(),
        },
    )

    print()
    print("Q7 NEW CONDITIONS COMPLETE")


if __name__ == "__main__":
    main()
