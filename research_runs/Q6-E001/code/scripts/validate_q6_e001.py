"""Independently validate Q6-E001 receipts, including source-only scalers.

This reruns preprocessing and recomputes every scaler from its declared
source-train trial IDs.  It does not retrain EEGNet or claim to prove hidden
GPU execution beyond the saved code, checkpoints, logs and predictions.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mne
import numpy as np
import pandas as pd
import torch
from threadpoolctl import threadpool_limits

from mi_eeg.data.bnci_epochs import load_configured_epochs
from mi_eeg.preprocessing.source_normalization import fit_source_channel_standardizer
from scripts.run_eegnet import sha256_file, write_json
from scripts.run_q6_e001 import (
    CONFIG,
    Q5_CONFIG,
    ROOT,
    _complete_fold_dir,
    assert_single_factor_protocol,
)
from scripts.validate_eegnet_run import (
    _check_confusions,
    _check_hashes,
    _check_manifest,
    _check_metadata,
    _check_metrics,
    _check_predictions,
    _check_selection_and_curves,
)


def _check_aggregate_files(output: Path, config: dict) -> None:
    for name in (
        "fit_manifest", "learning_curves", "selection", "predictions",
        "per_subject_metrics", "confusion_matrices",
    ):
        expected = pd.concat(
            [
                pd.read_csv(_complete_fold_dir(output, f"loso_s{s}", config) / f"{name}.csv")
                for s in config["subjects"]
            ],
            ignore_index=True,
        )
        observed = pd.read_csv(output / f"{name}.csv")
        pd.testing.assert_frame_equal(
            observed, expected, check_dtype=False, check_exact=False,
            rtol=1e-10, atol=1e-12,
        )


def _check_raw_hashes_match_q5(output: Path) -> None:
    current = json.loads((output / "source_files.json").read_text(encoding="utf-8"))
    q5 = json.loads((ROOT / "results/Q5-E001/source_files.json").read_text(encoding="utf-8"))
    def inventory(records: list[dict]) -> dict[str, str]:
        return {Path(row["path"].replace("\\", "/")).name: row["sha256"] for row in records}
    if len(current) != 18 or len(q5) != 18 or inventory(current) != inventory(q5):
        raise AssertionError("Q6 raw MAT filenames/hashes differ from Q5")


def _check_scalers(
    output: Path,
    config: dict,
    meta: pd.DataFrame,
    signal_microvolts: np.ndarray,
) -> int:
    receipts = json.loads((output / "normalization_receipts.json").read_text(encoding="utf-8"))
    if len(receipts) != 9 * 5:
        raise AssertionError("Expected four inner and one full Q6 scaler per target")
    expected_receipts = []
    checked = 0
    for target in config["subjects"]:
        fold = f"loso_s{target}"
        directory = _complete_fold_dir(output, fold, config)
        if directory is None:
            raise AssertionError(f"Incomplete outer fold {fold}")
        sources = sorted(s for s in config["subjects"] if s != target)
        for inner_fold in (1, 2, 3, 4, None):
            stage = "full" if inner_fold is None else "inner"
            name = "full" if inner_fold is None else f"inner_{inner_fold}"
            path = directory / "normalization" / f"{name}.json"
            saved = json.loads(path.read_text(encoding="utf-8"))
            expected_receipts.append(saved)
            validation = [] if inner_fold is None else sources[(inner_fold - 1) * 2 : inner_fold * 2]
            train_subjects = [s for s in sources if s not in validation]
            if saved.get("train_subjects") != train_subjects:
                raise AssertionError(f"Scaler included validation/target subject: {fold}/{name}")
            indices = np.flatnonzero(meta.subject.isin(train_subjects).to_numpy())
            fitted = fit_source_channel_standardizer(
                signal_microvolts, meta, indices, train_subjects,
                min_std_microvolts=config["input"]["normalization"]["min_std_microvolts"],
            )
            expected = fitted.receipt(fold=fold, stage=stage, inner_fold=inner_fold)
            for key in expected:
                if key in ("channel_mean_microvolts", "channel_std_microvolts"):
                    actual_values = np.asarray(saved.get(key), dtype=np.float64)
                    expected_values = np.asarray(expected[key], dtype=np.float64)
                    if actual_values.shape != (22,) or not np.allclose(
                        actual_values, expected_values, rtol=1e-12, atol=1e-12
                    ):
                        raise AssertionError(f"Source-only {key} differs: {fold}/{name}")
                    checked += 22
                elif saved.get(key) != expected[key]:
                    raise AssertionError(f"Scaler receipt {key} differs: {fold}/{name}")
            if set(saved) != set(expected):
                raise AssertionError(f"Unexpected or missing scaler receipt fields: {fold}/{name}")
            if len(indices) != (4608 if inner_fold is None else 3456):
                raise AssertionError("Q6 scaler train count changed")
            checkpoint_files = (
                [directory / f"seed_{seed}.pt" for seed in config["training"]["final_seeds"]]
                if inner_fold is None else [directory / f"inner_{inner_fold}.pt"]
            )
            receipt_sha = sha256_file(path)
            for checkpoint_file in checkpoint_files:
                checkpoint = torch.load(checkpoint_file, map_location="cpu", weights_only=True)
                if checkpoint.get("normalization_receipt_sha256") != receipt_sha:
                    raise AssertionError(f"Checkpoint/scaler mismatch: {checkpoint_file}")
                if checkpoint.get("fold") != fold or checkpoint.get("stage") != stage:
                    raise AssertionError(f"Checkpoint/fold identity mismatch: {checkpoint_file}")
                if inner_fold is not None and checkpoint.get("inner_fold") != inner_fold:
                    raise AssertionError(f"Checkpoint/inner-fold mismatch: {checkpoint_file}")
                checked += 1
    if receipts != expected_receipts:
        raise AssertionError("Aggregate Q6 scaler receipts differ from per-fold receipts")
    return checked


def verify(
    output: Path,
    *,
    data_dir: Path,
    reference: Path = ROOT / "outputs/Q4-E001",
) -> dict:
    config = json.loads((output / "config.json").read_text(encoding="utf-8"))
    q5 = json.loads(Q5_CONFIG.read_text(encoding="utf-8"))
    assert_single_factor_protocol(config, q5)
    status = json.loads((output / "status.json").read_text(encoding="utf-8"))
    if status.get("status") != "complete" or not status.get("q6_complete"):
        raise AssertionError("Q6 run has not finished all outer folds")
    if status.get("completed_folds") != 9 or status.get("completed_inner_fits") != 36 or status.get("completed_final_fits") != 27:
        raise AssertionError("Q6 fit/fold counts differ from fixed protocol")
    subjects = sorted(config["subjects"])
    seeds = config["training"]["final_seeds"]
    meta = pd.read_csv(output / "trial_metadata.csv")
    reference_meta = pd.read_csv(reference / "trial_metadata.csv")
    _check_metadata(meta, reference_meta, subjects)
    _check_aggregate_files(output, config)
    selection = pd.read_csv(output / "selection.csv")
    curves = pd.read_csv(output / "learning_curves.csv")
    chosen = _check_selection_and_curves(
        selection, curves, subjects, config["training"]["selection_seed"],
        seeds, config["training"]["max_epochs"],
    )
    n_inner, n_final = _check_manifest(
        pd.read_csv(output / "fit_manifest.csv"), subjects,
        config["training"]["selection_seed"], seeds,
        config["training"]["max_epochs"], chosen,
    )
    predictions = pd.read_csv(output / "predictions.csv")
    _check_predictions(predictions, meta, subjects, seeds)
    n_metric_checks = _check_metrics(
        predictions, pd.read_csv(output / "per_subject_metrics.csv"), subjects, seeds
    )
    n_confusion_checks = _check_confusions(
        predictions, pd.read_csv(output / "confusion_matrices.csv"), subjects, seeds
    )
    n_mat, n_snapshot = _check_hashes(output, reference, len(subjects))
    _check_raw_hashes_match_q5(output)
    mne.set_log_level("ERROR")
    with threadpool_limits(limits=2):
        bands, loaded_meta, _ = load_configured_epochs(
            subjects, data_dir.resolve(), config["preprocessing"], config["class_ids"]
        )
    _check_metadata(loaded_meta, meta, subjects)
    signal = bands["broad"]
    if signal.shape != (5184, 22, 750):
        raise AssertionError("Q6 raw scaler recheck EEG shape differs")
    signal *= np.float32(config["input"]["volts_to_microvolts"])
    n_scaler_checks = _check_scalers(output, config, meta, signal)
    return {
        "status": "passed",
        "experiment_id": "Q6-E001",
        "n_subjects": len(subjects),
        "n_trials": len(meta),
        "n_inner_fits": n_inner,
        "n_final_fits": n_final,
        "n_predictions": len(predictions),
        "n_source_only_scalers": 45,
        "n_scaler_scalar_or_checkpoint_checks": n_scaler_checks,
        "n_metric_scalar_checks": n_metric_checks,
        "n_confusion_cell_checks": n_confusion_checks,
        "n_raw_mat_hashes": n_mat,
        "n_snapshot_source_hashes": n_snapshot,
        "interpretation_boundary": (
            "Q6 is a post-Q5 exploratory ablation. Nine people, not 27 seed fits, "
            "are the units for subject-level inference. Receipts and raw scaler "
            "recomputation do not prove unlogged GPU behavior or external generalization."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, nargs="?", default=ROOT / "results/Q6-E001")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/raw")
    parser.add_argument("--reference", type=Path, default=ROOT / "outputs/Q4-E001")
    args = parser.parse_args()
    report = verify(args.output, data_dir=args.data_dir, reference=args.reference)
    write_json(args.output / "validation_report.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
