from __future__ import annotations

import hashlib
import json
import math
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

import mne
import numpy as np
import pandas as pd
import torch
from threadpoolctl import threadpool_limits

from mi_eeg.data.bnci_epochs import load_configured_epochs
from mi_eeg.evaluation.splits import iter_loso
from mi_eeg.models.eegnet_training import predict_probabilities

from scripts.run_eegnet import (
    METRIC_COLUMNS,
    cpu_state,
    fit_for_epochs,
    score_predictions,
    seed_manifest,
    source_files,
    verify_q4_identity,
    write_json,
)

Q5 = Path("/workspace/Q5_EEGNet_Cloud_Ready")
Q8 = Path("/workspace/Q8_MeanRank_Selection")

RUN = Q8 / "results/Q8-E001"
CONFIG = RUN / "config.json"
SELECTION = RUN / "predeclared_selection.csv"
SELECTION_PROVENANCE = RUN / "selection_provenance.json"

DATA = Q5 / "data/raw"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            b = f.read(1024 * 1024)

            if not b:
                break

            h.update(b)

    return h.hexdigest()


def find_complete_fold(
    fold: str,
    seeds: list[int],
) -> Path | None:

    fold_root = RUN / "folds"

    if not fold_root.exists():
        return None

    candidates = sorted(
        fold_root.glob(f"{fold}*")
    )

    complete = []

    required = (
        ["status.json",
         "learning_curves.csv",
         "fit_manifest.csv",
         "selection.csv",
         "predictions.csv",
         "per_subject_metrics.csv",
         "confusion_matrices.csv",
         "checkpoint_hashes.csv"]
        + [
            f"seed_{seed}.pt"
            for seed in seeds
        ]
    )

    for path in candidates:

        status_path = path / "status.json"

        if not status_path.is_file():
            continue

        status = json.loads(
            status_path.read_text(
                encoding="utf-8"
            )
        )

        if status.get("status") != "complete":
            continue

        missing = [
            name
            for name in required
            if not (path / name).is_file()
        ]

        if missing:
            raise AssertionError(
                f"Completed {path} missing: {missing}"
            )

        complete.append(path)

    if len(complete) > 1:
        raise AssertionError(
            f"Multiple complete attempts for {fold}"
        )

    return complete[0] if complete else None


def aggregate(config: dict):

    collections = {
        name: []
        for name in [
            "fit_manifest",
            "learning_curves",
            "selection",
            "predictions",
            "per_subject_metrics",
            "confusion_matrices",
            "checkpoint_hashes",
        ]
    }

    completed = []

    for subject in config["subjects"]:

        fold = f"loso_s{subject}"

        path = find_complete_fold(
            fold,
            config["training"]["final_seeds"],
        )

        if path is None:
            continue

        completed.append(path)

        for name in collections:
            collections[name].append(
                pd.read_csv(
                    path / f"{name}.csv"
                )
            )

    for name, frames in collections.items():

        if frames:
            pd.concat(
                frames,
                ignore_index=True,
            ).to_csv(
                RUN / f"{name}.csv",
                index=False,
            )

    if collections["per_subject_metrics"]:

        frame = pd.concat(
            collections[
                "per_subject_metrics"
            ],
            ignore_index=True,
        )

        all_rows = frame[
            frame.stratum == "all"
        ]

        summary = (
            all_rows.groupby("seed")[
                METRIC_COLUMNS
            ]
            .agg(["mean", "std"])
        )

        summary.columns = [
            f"{metric}_{stat}"
            for metric, stat
            in summary.columns
        ]

        summary.reset_index().to_csv(
            RUN / "summary_by_seed.csv",
            index=False,
        )

        subject_seed = all_rows[
            [
                "subject",
                "seed",
                "balanced_accuracy",
                "macro_f1",
                "cohen_kappa",
            ]
        ].copy()

        subject_seed.to_csv(
            RUN / "subject_seed_metrics.csv",
            index=False,
        )

    status = {
        "status": (
            "complete"
            if len(completed)
            == len(config["subjects"])
            else "running"
        ),
        "experiment_id": "Q8-E001",
        "completed_folds": len(completed),
        "completed_inner_fits": 0,
        "reused_inner_curve_experiment": "Q5-E001",
        "completed_final_fits": (
            len(completed)
            * len(
                config["training"][
                    "final_seeds"
                ]
            )
        ),
        "q8_complete": (
            len(completed)
            == len(config["subjects"])
        ),
    }

    write_json(
        RUN / "status.json",
        status,
    )


def main():

    config = json.loads(
        CONFIG.read_text(
            encoding="utf-8"
        )
    )

    selection = pd.read_csv(
        SELECTION
    )

    provenance = json.loads(
        SELECTION_PROVENANCE.read_text(
            encoding="utf-8"
        )
    )

    # --------------------------------------------------------
    # Lock the selection file.
    # --------------------------------------------------------

    current_sha = sha256_file(
        SELECTION
    )

    expected_sha = provenance[
        "predeclared_selection_sha256"
    ]

    if current_sha != expected_sha:
        raise AssertionError(
            "Frozen selection SHA changed"
        )

    if (
        provenance[
            "target_results_read_by_freeze_script"
        ]
        is not False
    ):
        raise AssertionError(
            "Invalid selection provenance"
        )

    if (
        provenance[
            "inner_fits_retrained"
        ]
        is not False
    ):
        raise AssertionError(
            "Q8 must reuse Q5 inner curves"
        )

    # --------------------------------------------------------
    # Strict single-factor protocol check vs Q5.
    # --------------------------------------------------------

    q5_config = json.loads(
        (
            Q5
            / "configs/q5_e001_eegnet.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    for key in [
        "dataset",
        "subjects",
        "class_ids",
        "preprocessing",
        "input",
        "architecture",
    ]:

        if config[key] != q5_config[key]:
            raise AssertionError(
                f"Q8 changed frozen Q5 {key}"
            )

    q8_training = dict(
        config["training"]
    )

    q5_training = dict(
        q5_config["training"]
    )

    # Only selection metadata may differ.
    for key in [
        "epoch_selection",
        "inner_curve_source",
        "inner_fits_retrained",
    ]:
        q8_training.pop(
            key,
            None,
        )

    q5_training.pop(
        "epoch_selection",
        None,
    )

    if q8_training != q5_training:
        raise AssertionError(
            "Q8 training configuration changed "
            "beyond epoch-selection declaration"
        )

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print("Device:", device)

    torch.set_num_threads(
        config["training"][
            "torch_threads"
        ]
    )

    torch.set_num_interop_threads(1)

    mne.set_log_level("ERROR")

    started = time.perf_counter()

    # --------------------------------------------------------
    # Load exact frozen Q5 preprocessing.
    # --------------------------------------------------------

    print(
        "Loading exact frozen Q5 EEG preprocessing..."
    )

    with threadpool_limits(limits=2):

        bands, meta, audit = (
            load_configured_epochs(
                config["subjects"],
                DATA.resolve(),
                config["preprocessing"],
                config["class_ids"],
            )
        )

    if len(meta) != 5184:
        raise AssertionError(
            f"Expected 5184 trials, got {len(meta)}"
        )

    if int(
        meta.artifact_flagged.sum()
    ) != 488:
        raise AssertionError(
            "Artifact population changed"
        )

    # Exact row-wise identity with Q4.
    q4_meta = pd.read_csv(
        Q5
        / "outputs/Q4-E001/trial_metadata.csv"
    )

    verify_q4_identity(
        meta,
        q4_meta,
    )

    # Also compare against frozen Q5 metadata.
    q5_meta = pd.read_csv(
        Q5
        / "results/Q5-E001/trial_metadata.csv"
    )

    verify_q4_identity(
        meta,
        q5_meta,
    )

    meta.to_csv(
        RUN / "trial_metadata.csv",
        index=False,
    )

    audit.to_csv(
        RUN / "data_audit.csv",
        index=False,
    )

    records = source_files(
        DATA.resolve(),
        config["subjects"],
    )

    write_json(
        RUN / "source_files.json",
        records,
    )

    signal = bands["broad"]

    if signal.shape != (
        5184,
        22,
        750,
    ):
        raise AssertionError(
            f"Unexpected EEG shape {signal.shape}"
        )

    signal *= np.float32(
        config["input"][
            "volts_to_microvolts"
        ]
    )

    if not np.isfinite(
        signal
    ).all():
        raise AssertionError(
            "Non-finite raw microvolt EEG"
        )

    x = torch.from_numpy(
        signal
    ).to(device)

    y = torch.as_tensor(
        meta.label.to_numpy(
            dtype=np.int64
        )
        - 1,
        dtype=torch.long,
        device=device,
    )

    write_json(
        RUN / "data_contract.json",
        {
            "shape": list(
                signal.shape
            ),
            "labels": {
                "scientific": [
                    1,
                    2,
                    3,
                    4,
                ],
                "torch": [
                    0,
                    1,
                    2,
                    3,
                ],
            },
            "fixed_scale": (
                config["input"][
                    "volts_to_microvolts"
                ]
            ),
            "normalization": False,
            "target_fitted_transform": False,
            "q4_identity_match": True,
            "q5_identity_match": True,
            "selection_sha256": current_sha,
        },
    )

    # --------------------------------------------------------
    # Train ONLY final source models.
    # --------------------------------------------------------

    seeds = config["training"][
        "final_seeds"
    ]

    batch_size = config[
        "training"
    ]["batch_size"]

    for fold, train_idx, test_idx in iter_loso(
        meta
    ):

        target = int(
            meta.iloc[
                test_idx
            ].subject.unique().item()
        )

        expected_fold = (
            f"loso_s{target}"
        )

        if fold != expected_fold:
            raise AssertionError(
                f"Fold mismatch: {fold}"
            )

        source_subjects = sorted(
            int(s)
            for s in (
                meta.iloc[
                    train_idx
                ]
                .subject.unique()
            )
        )

        if (
            len(source_subjects)
            != 8
            or target in source_subjects
        ):
            raise AssertionError(
                "Invalid LOSO source set"
            )

        if (
            len(train_idx) != 4608
            or len(test_idx) != 576
        ):
            raise AssertionError(
                "Unexpected LOSO trial counts"
            )

        selected_row = selection[
            selection.fold == fold
        ]

        if len(
            selected_row
        ) != 1:
            raise AssertionError(
                f"Missing frozen selection for {fold}"
            )

        selected_epochs = int(
            selected_row[
                "selected_epochs"
            ].iloc[0]
        )

        if not (
            1
            <= selected_epochs
            <= 40
        ):
            raise AssertionError(
                "Invalid selected epoch"
            )

        complete = find_complete_fold(
            fold,
            seeds,
        )

        if complete is not None:

            print(
                f"{fold}: already complete; reusing"
            )

            aggregate(
                config
            )

            continue

        fold_root = RUN / "folds"

        fold_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        attempt = (
            fold_root
            / fold
        )

        retry = 0

        while attempt.exists():

            retry += 1

            attempt = (
                fold_root
                / f"{fold}_retry{retry}"
            )

        attempt.mkdir(
            parents=True
        )

        fold_started = (
            time.perf_counter()
        )

        write_json(
            attempt / "status.json",
            {
                "status": "running",
                "fold": fold,
                "target_subject": target,
                "selected_epochs": (
                    selected_epochs
                ),
                "selection_rule": "mean_rank",
            },
        )

        curves = []
        manifests = []
        metric_frames = []
        confusion_frames = []
        prediction_frames = []
        checkpoint_rows = []

        try:

            # Defensive copy prevents the harmless
            # non-writable NumPy-index warning.
            train_for_fit = (
                np.asarray(
                    train_idx,
                    dtype=np.int64,
                )
                .copy()
            )

            test_for_predict = (
                np.asarray(
                    test_idx,
                    dtype=np.int64,
                )
                .copy()
            )

            for seed in seeds:

                print(
                    f"{fold} seed {seed}: "
                    f"training {selected_epochs} epochs",
                    flush=True,
                )

                model, curve = (
                    fit_for_epochs(
                        x,
                        y,
                        train_for_fit,
                        None,
                        seed,
                        selected_epochs,
                        config,
                        device,
                    )
                )

                for row in curve:

                    curves.append(
                        {
                            "fold": fold,
                            "subject": target,
                            "stage": "full",
                            "inner_fold": math.nan,
                            "seed": seed,
                            "selected_epochs": (
                                selected_epochs
                            ),
                            "selection_rule": (
                                "mean_rank"
                            ),
                            **row,
                        }
                    )

                manifests.extend(
                    seed_manifest(
                        fold,
                        "full",
                        None,
                        seed,
                        source_subjects,
                        target,
                        None,
                        selected_epochs,
                    )
                )

                checkpoint = (
                    attempt
                    / f"seed_{seed}.pt"
                )

                torch.save(
                    {
                        "experiment_id":
                            "Q8-E001",
                        "fold": fold,
                        "target_subject":
                            target,
                        "stage":
                            "full",
                        "seed":
                            seed,
                        "selected_epochs":
                            selected_epochs,
                        "selection_rule":
                            "mean_rank",
                        "normalization":
                            False,
                        "selection_sha256":
                            current_sha,
                        "model_state":
                            cpu_state(
                                model
                            ),
                    },
                    checkpoint,
                )

                checkpoint_rows.append(
                    {
                        "fold":
                            fold,
                        "subject":
                            target,
                        "seed":
                            seed,
                        "selected_epochs":
                            selected_epochs,
                        "checkpoint":
                            str(
                                checkpoint
                            ),
                        "sha256":
                            sha256_file(
                                checkpoint
                            ),
                    }
                )

                probabilities = (
                    predict_probabilities(
                        model,
                        x,
                        test_for_predict,
                        batch_size,
                    )
                )

                if probabilities.shape != (
                    576,
                    4,
                ):
                    raise AssertionError(
                        "Unexpected prediction shape"
                    )

                part = (
                    meta.iloc[
                        test_idx
                    ]
                    .copy()
                    .reset_index(
                        drop=True
                    )
                )

                part[
                    "experiment_id"
                ] = "Q8-E001"

                part[
                    "fold"
                ] = fold

                part[
                    "seed"
                ] = seed

                part[
                    "selection_rule"
                ] = "mean_rank"

                part[
                    "selected_epochs"
                ] = selected_epochs

                part[
                    "y_true"
                ] = part.label.astype(
                    int
                )

                part[
                    "y_pred"
                ] = (
                    probabilities.argmax(
                        axis=1
                    ).astype(int)
                    + 1
                )

                for i, label in enumerate(
                    [1, 2, 3, 4]
                ):

                    part[
                        f"p_class_{label}"
                    ] = (
                        probabilities[
                            :,
                            i,
                        ]
                    )

                metrics, confusions = (
                    score_predictions(
                        part,
                        [1, 2, 3, 4],
                        fold,
                        seed,
                        len(
                            train_idx
                        ),
                    )
                )

                metric_df = (
                    pd.DataFrame(
                        metrics
                    )
                )

                metric_df[
                    "selection_rule"
                ] = "mean_rank"

                metric_df[
                    "selected_epochs"
                ] = selected_epochs

                confusion_df = (
                    pd.DataFrame(
                        confusions
                    )
                )

                confusion_df[
                    "selection_rule"
                ] = "mean_rank"

                confusion_df[
                    "selected_epochs"
                ] = selected_epochs

                confusion_df[
                    "model"
                ] = "EEGNet"

                pred_path = (
                    attempt
                    / (
                        "predictions_seed_"
                        f"{seed}.csv"
                    )
                )

                metric_path = (
                    attempt
                    / (
                        "metrics_seed_"
                        f"{seed}.csv"
                    )
                )

                confusion_path = (
                    attempt
                    / (
                        "confusion_seed_"
                        f"{seed}.csv"
                    )
                )

                part.to_csv(
                    pred_path,
                    index=False,
                )

                metric_df.to_csv(
                    metric_path,
                    index=False,
                )

                confusion_df.to_csv(
                    confusion_path,
                    index=False,
                )

                prediction_frames.append(
                    part
                )

                metric_frames.append(
                    metric_df
                )

                confusion_frames.append(
                    confusion_df
                )

                all_metric = metric_df[
                    metric_df.stratum
                    == "all"
                ].iloc[0]

                print(
                    f"{fold} seed {seed}: "
                    f"BA="
                    f"{all_metric.balanced_accuracy:.4f} "
                    f"epochs={selected_epochs}",
                    flush=True,
                )

                del model

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            pd.DataFrame(
                curves
            ).to_csv(
                attempt
                / "learning_curves.csv",
                index=False,
            )

            pd.DataFrame(
                manifests
            ).to_csv(
                attempt
                / "fit_manifest.csv",
                index=False,
            )

            pd.DataFrame(
                [
                    {
                        "fold":
                            fold,
                        "subject":
                            target,
                        "selected_epochs":
                            selected_epochs,
                        "selection_rule":
                            "mean_rank",
                        "selection_sha256":
                            current_sha,
                        "source":
                            "frozen_Q5_inner_curves",
                    }
                ]
            ).to_csv(
                attempt
                / "selection.csv",
                index=False,
            )

            pd.concat(
                prediction_frames,
                ignore_index=True,
            ).to_csv(
                attempt
                / "predictions.csv",
                index=False,
            )

            pd.concat(
                metric_frames,
                ignore_index=True,
            ).to_csv(
                attempt
                / "per_subject_metrics.csv",
                index=False,
            )

            pd.concat(
                confusion_frames,
                ignore_index=True,
            ).to_csv(
                attempt
                / "confusion_matrices.csv",
                index=False,
            )

            pd.DataFrame(
                checkpoint_rows
            ).to_csv(
                attempt
                / "checkpoint_hashes.csv",
                index=False,
            )

            write_json(
                attempt
                / "status.json",
                {
                    "status":
                        "complete",
                    "fold":
                        fold,
                    "target_subject":
                        target,
                    "selected_epochs":
                        selected_epochs,
                    "selection_rule":
                        "mean_rank",
                    "normalization":
                        False,
                    "final_fits":
                        len(seeds),
                    "elapsed_seconds":
                        (
                            time.perf_counter()
                            - fold_started
                        ),
                },
            )

        except Exception:

            write_json(
                attempt
                / "failure.json",
                {
                    "traceback":
                        traceback.format_exc(),
                    "elapsed_seconds":
                        (
                            time.perf_counter()
                            - fold_started
                        ),
                },
            )

            write_json(
                attempt
                / "status.json",
                {
                    "status":
                        "failed",
                    "fold":
                        fold,
                },
            )

            raise

        aggregate(
            config
        )

    aggregate(
        config
    )

    final_status = json.loads(
        (
            RUN
            / "status.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    if not final_status.get(
        "q8_complete"
    ):
        raise AssertionError(
            "Q8 did not complete all folds"
        )

    final_status[
        "finished_at_utc"
    ] = datetime.now(
        UTC
    ).isoformat()

    final_status[
        "elapsed_seconds_this_invocation"
    ] = (
        time.perf_counter()
        - started
    )

    write_json(
        RUN / "status.json",
        final_status,
    )

    print()
    print(
        "Q8-E001 FINAL TRAINING COMPLETE"
    )


if __name__ == "__main__":
    main()
