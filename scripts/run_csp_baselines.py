"""Run fixed CSP+LDA/SVM baselines on real BNCI2014_001 left/right trials.

No target-subject samples are used when fitting the LOSO pipeline. The script
records every split and per-trial prediction. It does not implement EEGNet.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import platform
import sys
import time
import warnings
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import moabb
import numpy as np
import pandas as pd
import scipy
import sklearn
from mne.decoding import CSP
from moabb.datasets import BNCI2014_001
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from mi_eeg.evaluation.splits import iter_cross_session, iter_loso, iter_within_session
from mi_eeg.provenance import (
    capture_startup_provenance,
    check_declared_constants,
    require_new_run_directory,
)
from mi_eeg.reproducibility import set_global_seed

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "p2_csp_baselines.json"
CLASS_IDS = {"left_hand": 1, "right_hand": 2}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subjects", type=int, nargs="+", default=list(range(1, 10)))
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=("within_session", "cross_session", "cross_subject"),
        default=["within_session", "cross_session", "cross_subject"],
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "P2-E001")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument(
        "--artifact-policy",
        choices=("exclude", "include"),
        default="exclude",
        help="Expert-marked trial policy. 'include' is a sensitivity analysis, not the primary run.",
    )
    return parser.parse_args()


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(
            f1_score(y_true, y_pred, labels=[1, 2], average="macro", zero_division=0)
        ),
        "cohen_kappa": float(cohen_kappa_score(y_true, y_pred, labels=[1, 2])),
    }


def model_for(name: str) -> object:
    feature = CSP(
        n_components=4,
        reg=None,
        log=True,
        cov_est="concat",
        transform_into="average_power",
        norm_trace=False,
    )
    if name == "CSP+LDA":
        classifier = LinearDiscriminantAnalysis(solver="svd")
    elif name == "CSP+linearSVM":
        classifier = SVC(kernel="linear", C=1.0)
    else:
        raise ValueError(f"Unknown model: {name}")
    return make_pipeline(feature, StandardScaler(), classifier)


def load_epochs(
    subjects: list[int], data_dir: Path, reject_artifacts: bool
) -> tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MNE_DATASETS_BNCI_PATH"] = str(data_dir.resolve())
    # Explicitly preserve expert artifact flags; the MOABB default is 'ignore'.
    dataset = BNCI2014_001(artifact_handling="annotate_bad")
    arrays: list[np.ndarray] = []
    rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    channel_reference: tuple[str, ...] | None = None

    for subject in subjects:
        print(f"Loading subject {subject} ...", flush=True)
        sessions = dataset.get_data(subjects=[subject])[subject]
        if set(sessions) != {"0train", "1test"}:
            raise AssertionError(f"Unexpected session keys for subject {subject}: {list(sessions)}")
        for session, runs in sorted(sessions.items()):
            if len(runs) != 6:
                raise AssertionError(f"Expected 6 runs: subject={subject} session={session}")
            for run_name, raw in sorted(runs.items(), key=lambda item: int(item[0])):
                run = int(run_name)
                if raw.info["sfreq"] != 250.0:
                    raise AssertionError("Sampling rate differs from preregistered 250 Hz")
                eeg_channels = tuple(
                    name
                    for name, kind in zip(raw.ch_names, raw.get_channel_types())
                    if kind == "eeg"
                )
                if len(eeg_channels) != 22:
                    raise AssertionError(f"Expected 22 EEG channels, found {len(eeg_channels)}")
                if channel_reference is None:
                    channel_reference = eeg_channels
                elif eeg_channels != channel_reference:
                    raise AssertionError("EEG channel order changed across runs")

                events = mne.find_events(raw, stim_channel="STI", shortest_event=1, verbose=False)
                event_counts = Counter(events[:, 2].tolist())
                if event_counts != Counter({1: 12, 2: 12, 3: 12, 4: 12}):
                    raise AssertionError(
                        f"Unexpected trial labels: subject={subject} session={session} "
                        f"run={run}, {event_counts}"
                    )
                sample_to_trial = {
                    int(sample): trial for trial, sample in enumerate(events[:, 0], 1)
                }
                flagged_trial_ids = {
                    int(extra["trial"])
                    for description, extra in zip(
                        raw.annotations.description, raw.annotations.extras
                    )
                    if description == "BAD_artifact" and extra is not None
                }
                flagged_left_right = sum(
                    sample_to_trial[int(sample)] in flagged_trial_ids
                    for sample, _, label in events
                    if int(label) in (1, 2)
                )

                # MOABB's MAT stim mark is trial onset, not the 2 s later visual cue.
                # Trial-relative [2.5, 5.5) s = cue-relative [0.5, 3.5) s.
                eeg_raw = raw.copy().pick("eeg")
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message=".*filter_length.*")
                    eeg_raw.filter(
                        l_freq=8.0,
                        h_freq=30.0,
                        method="iir",
                        iir_params={"order": 4, "ftype": "butter"},
                        phase="zero",
                        verbose=False,
                    )
                tmax = 5.5 - 1.0 / raw.info["sfreq"]
                epochs = mne.Epochs(
                    eeg_raw,
                    events,
                    event_id=CLASS_IDS,
                    tmin=2.5,
                    tmax=tmax,
                    baseline=None,
                    reject_by_annotation=reject_artifacts,
                    preload=True,
                    verbose=False,
                )
                X_run = epochs.get_data(copy=True).astype(np.float32)
                if X_run.shape[1:] != (22, 750):
                    raise AssertionError(f"Unexpected epoch shape: {X_run.shape}")
                n_rejected = 24 - len(epochs)
                expected_rejected = flagged_left_right if reject_artifacts else 0
                if n_rejected != expected_rejected:
                    raise AssertionError(
                        "Artifact rejection does not match source trial flags: "
                        f"s={subject} session={session} run={run} "
                        f"rejected={n_rejected} expected={expected_rejected}"
                    )
                if len(epochs) == 0:
                    raise AssertionError(f"No clean left/right trials: subject={subject} run={run}")

                arrays.append(X_run)
                for sample, _, label in epochs.events:
                    trial = sample_to_trial[int(sample)]
                    rows.append(
                        {
                            "sample_id": f"s{subject:02d}_{session}_r{run}_t{trial:02d}",
                            "subject": subject,
                            "session": session,
                            "run": run,
                            "trial": trial,
                            "label": int(label),
                            "event_sample": int(sample),
                            "artifact_flagged": trial in flagged_trial_ids,
                        }
                    )
                audit_rows.append(
                    {
                        "subject": subject,
                        "session": session,
                        "run": run,
                        "n_all_four_class_trials": len(events),
                        "n_left_right_before_rejection": 24,
                        "n_source_artifact_flags_all_classes": len(flagged_trial_ids),
                        "n_left_right_flagged": flagged_left_right,
                        "n_left_right_rejected": n_rejected,
                        "n_left_right_kept": len(epochs),
                        "n_left_kept": int(np.sum(epochs.events[:, 2] == 1)),
                        "n_right_kept": int(np.sum(epochs.events[:, 2] == 2)),
                        "n_times_per_epoch": X_run.shape[2],
                        "n_eeg_channels": X_run.shape[1],
                        "sampling_rate_hz": raw.info["sfreq"],
                    }
                )
            print(
                f"  {session}: {sum(r['n_left_right_kept'] for r in audit_rows if r['subject'] == subject and r['session'] == session)} selected left/right trials",
                flush=True,
            )
        del sessions

    X = np.concatenate(arrays, axis=0)
    meta = pd.DataFrame(rows)
    audit = pd.DataFrame(audit_rows)
    if len(X) != len(meta) or meta["sample_id"].duplicated().any():
        raise AssertionError("Epoch array and metadata do not align")
    if sorted(meta["subject"].unique()) != sorted(subjects):
        raise AssertionError("Missing requested subjects")
    return X, meta, audit


def source_files(data_dir: Path, subjects: list[int]) -> list[dict[str, object]]:
    result = []
    for subject in subjects:
        for suffix in ("T", "E"):
            name = f"A{subject:02d}{suffix}.mat"
            paths = sorted(data_dir.rglob(name))
            if not paths:
                raise FileNotFoundError(f"Cached source file not found: {name}")
            path = paths[0]
            with path.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            result.append(
                {
                    "file": name,
                    "path": str(path.resolve()),
                    "bytes": path.stat().st_size,
                    "sha256": digest,
                }
            )
    return result


def split_manifest_rows(
    mode: str, fold_id: str, train: np.ndarray, test: np.ndarray, meta: pd.DataFrame
) -> list[dict[str, object]]:
    rows = []
    for role, indices in (("train", train), ("test", test)):
        for idx in indices:
            row = meta.iloc[int(idx)]
            rows.append(
                {
                    "mode": mode,
                    "fold_id": fold_id,
                    "role": role,
                    "sample_id": row["sample_id"],
                    "subject": int(row["subject"]),
                    "session": row["session"],
                    "run": int(row["run"]),
                    "trial": int(row["trial"]),
                }
            )
    return rows


def evaluate(
    X: np.ndarray, meta: pd.DataFrame, modes: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    split_generators = {
        "within_session": iter_within_session,
        "cross_session": iter_cross_session,
        "cross_subject": iter_loso,
    }
    y = meta["label"].to_numpy(dtype=np.int64)
    fold_rows: list[dict[str, object]] = []
    prediction_rows: list[dict[str, object]] = []
    manifest_rows: list[dict[str, object]] = []

    for mode in modes:
        for fold_number, (fold_id, train, test) in enumerate(split_generators[mode](meta), 1):
            if set(y[train]) != {1, 2} or set(y[test]) != {1, 2}:
                raise AssertionError(f"Class missing from a split: {fold_id}")
            manifest_rows.extend(split_manifest_rows(mode, fold_id, train, test, meta))
            print(
                f"{mode} fold {fold_number}: {fold_id} train={len(train)} test={len(test)}",
                flush=True,
            )
            for model_name in ("CSP+LDA", "CSP+linearSVM"):
                pipeline = model_for(model_name)
                start = time.perf_counter()
                pipeline.fit(X[train], y[train])
                predicted = pipeline.predict(X[test]).astype(np.int64)
                elapsed = time.perf_counter() - start
                score = metrics(y[test], predicted)
                fold_rows.append(
                    {
                        "mode": mode,
                        "fold_id": fold_id,
                        "model": model_name,
                        "n_train": len(train),
                        "n_test": len(test),
                        "fit_predict_seconds": elapsed,
                        **score,
                    }
                )
                for idx, value in zip(test, predicted):
                    row = meta.iloc[int(idx)]
                    prediction_rows.append(
                        {
                            "mode": mode,
                            "fold_id": fold_id,
                            "model": model_name,
                            "sample_id": row["sample_id"],
                            "subject": int(row["subject"]),
                            "session": row["session"],
                            "run": int(row["run"]),
                            "trial": int(row["trial"]),
                            "y_true": int(y[idx]),
                            "y_pred": int(value),
                        }
                    )
    return pd.DataFrame(fold_rows), pd.DataFrame(prediction_rows), pd.DataFrame(manifest_rows)


def summarize_predictions(
    predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    subject_rows = []
    session_rows = []
    for (mode, model, subject), group in predictions.groupby(
        ["mode", "model", "subject"], sort=True
    ):
        subject_rows.append(
            {
                "mode": mode,
                "model": model,
                "subject": subject,
                "n_test": len(group),
                **metrics(group["y_true"].to_numpy(), group["y_pred"].to_numpy()),
            }
        )
    for (mode, model, subject, session), group in predictions.groupby(
        ["mode", "model", "subject", "session"], sort=True
    ):
        session_rows.append(
            {
                "mode": mode,
                "model": model,
                "subject": subject,
                "session": session,
                "n_test": len(group),
                **metrics(group["y_true"].to_numpy(), group["y_pred"].to_numpy()),
            }
        )
    subjects = pd.DataFrame(subject_rows)
    sessions = pd.DataFrame(session_rows)
    summaries = []
    for (mode, model), group in subjects.groupby(["mode", "model"], sort=True):
        values = group["balanced_accuracy"]
        summaries.append(
            {
                "mode": mode,
                "model": model,
                "n_subjects": len(group),
                "mean_balanced_accuracy": values.mean(),
                "sd_balanced_accuracy": values.std(ddof=1),
                "median_balanced_accuracy": values.median(),
                "min_balanced_accuracy": values.min(),
                "max_balanced_accuracy": values.max(),
                "mean_accuracy": group["accuracy"].mean(),
                "mean_macro_f1": group["macro_f1"].mean(),
                "mean_cohen_kappa": group["cohen_kappa"].mean(),
            }
        )
    return subjects, sessions, pd.DataFrame(summaries)


def paired_loso_comparison(subject_scores: pd.DataFrame, seed: int) -> dict[str, object] | None:
    loso = subject_scores[subject_scores["mode"] == "cross_subject"]
    if loso.empty:
        return None
    wide = loso.pivot(index="subject", columns="model", values="balanced_accuracy")
    differences = (wide["CSP+LDA"] - wide["CSP+linearSVM"]).to_numpy()
    observed = abs(differences.mean())
    sign_means = np.array(
        [
            abs(np.mean(differences * signs))
            for signs in itertools.product((-1, 1), repeat=len(differences))
        ]
    )
    p_value = float(np.mean(sign_means >= observed - 1e-12))
    rng = np.random.default_rng(seed)
    samples = rng.choice(differences, size=(10000, len(differences)), replace=True).mean(axis=1)
    lo, hi = np.quantile(samples, [0.025, 0.975])
    return {
        "contrast": "CSP+LDA minus CSP+linearSVM",
        "unit": "held-out subject",
        "n_subjects": len(differences),
        "mean_paired_difference_ba": float(differences.mean()),
        "bootstrap_percentile_95_ci": [float(lo), float(hi)],
        "bootstrap_repetitions": 10000,
        "exact_sign_flip_two_sided_p": p_value,
        "inference_note": "Exploratory resampling of nine fixed held-out-subject scores; overlapping LOSO training sets and model-selection uncertainty are not represented. Not confirmatory population inference.",
    }


def save_plots(subject_scores: pd.DataFrame, predictions: pd.DataFrame, figures_dir: Path) -> None:
    figures_dir.mkdir(parents=True, exist_ok=True)
    for mode, group in subject_scores.groupby("mode", sort=True):
        fig, ax = plt.subplots(figsize=(9, 4.7), layout="constrained")
        for model, model_group in group.groupby("model", sort=True):
            model_group = model_group.sort_values("subject")
            ax.plot(
                model_group["subject"],
                model_group["balanced_accuracy"],
                marker="o",
                linewidth=1.8,
                label=model,
            )
        ax.axhline(0.5, color="gray", linestyle="--", linewidth=1, label="Chance (balanced)")
        ax.set(xlabel="Subject", ylabel="Balanced accuracy", title=mode.replace("_", " ").title())
        ax.set_ylim(0, 1)
        ax.set_xticks(sorted(group["subject"].unique()))
        ax.legend(loc="best", fontsize=8)
        fig.savefig(figures_dir / f"{mode}_per_subject_ba.png", dpi=180)
        plt.close(fig)

    for model, group in predictions[predictions["mode"] == "cross_subject"].groupby("model"):
        cm = confusion_matrix(group["y_true"], group["y_pred"], labels=[1, 2])
        fig, ax = plt.subplots(figsize=(5, 4.5), layout="constrained")
        image = ax.imshow(cm, cmap="Blues")
        fig.colorbar(image, ax=ax, label="Trial count")
        for row in range(2):
            for col in range(2):
                ax.text(col, row, str(cm[row, col]), ha="center", va="center", color="black")
        ax.set_xticks([0, 1], ["left", "right"])
        ax.set_yticks([0, 1], ["left", "right"])
        ax.set(xlabel="Predicted", ylabel="True", title=f"LOSO: {model}")
        safe_name = model.replace("+", "_")
        fig.savefig(figures_dir / f"loso_confusion_{safe_name}.png", dpi=180)
        plt.close(fig)


def main() -> None:
    args = parse_args()
    mne.set_log_level("WARNING")
    warnings.filterwarnings(
        "ignore",
        message="Montage name 'standard_1005' is deprecated.*",
        category=FutureWarning,
    )
    subjects = sorted(set(args.subjects))
    if any(subject not in range(1, 10) for subject in subjects):
        raise SystemExit("Subjects must be integers 1 through 9")
    if "cross_subject" in args.modes and len(subjects) < 2:
        raise SystemExit("LOSO requires at least two subjects")
    output_dir = args.output_dir.resolve()
    data_dir = args.data_dir.resolve()
    require_new_run_directory(output_dir)
    started = datetime.now(UTC)
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    check_declared_constants(
        config,
        {
            "dataset": "BNCI2014_001",
            "classes": CLASS_IDS,
            "channels": "all_22_eeg_only",
            "additional_filter": {
                "band_hz": [8.0, 30.0],
                "type": "4th_order_butterworth_iir",
                "phase": "zero_phase_offline",
                "unit": "each_run_independently",
            },
            "epoch": {
                "trial_relative_start_s": 2.5,
                "trial_relative_stop_exclusive_s": 5.5,
                "baseline": None,
                "expected_samples_at_250_hz": 750,
            },
            "models": {
                "CSP+LDA": {
                    "csp_components": 4,
                    "csp_cov_est": "concat",
                    "csp_reg": None,
                    "classifier": "LinearDiscriminantAnalysis(solver='svd')",
                },
                "CSP+linearSVM": {
                    "csp_components": 4,
                    "csp_cov_est": "concat",
                    "csp_reg": None,
                    "classifier": "SVC(kernel='linear', C=1.0)",
                },
            },
        },
    )
    capture_startup_provenance(ROOT, output_dir)
    config["effective_subjects"] = subjects
    config["effective_modes"] = args.modes
    config["effective_artifact_policy"] = args.artifact_policy
    config["data_cache_root"] = str(data_dir)
    config["started_at_utc"] = started.isoformat()
    (output_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "mne": mne.__version__,
        "moabb": moabb.__version__,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
    }
    (output_dir / "environment.json").write_text(
        json.dumps(environment, indent=2), encoding="utf-8"
    )
    set_global_seed(config["seed"])

    try:
        X, meta, audit = load_epochs(subjects, data_dir, args.artifact_policy == "exclude")
        meta.to_csv(output_dir / "trial_metadata.csv", index=False)
        audit.to_csv(output_dir / "data_audit.csv", index=False)
        files = source_files(data_dir, subjects)
        (output_dir / "source_files.json").write_text(json.dumps(files, indent=2), encoding="utf-8")
        print(f"Ready: X={X.shape}, selected trials={len(meta)}", flush=True)

        folds, predictions, manifest = evaluate(X, meta, args.modes)
        folds.to_csv(output_dir / "fold_metrics.csv", index=False)
        predictions.to_csv(output_dir / "predictions.csv", index=False)
        manifest.to_csv(output_dir / "split_manifest.csv", index=False)
        subject_scores, session_scores, summary = summarize_predictions(predictions)
        subject_scores.to_csv(output_dir / "subject_metrics.csv", index=False)
        session_scores.to_csv(output_dir / "session_metrics.csv", index=False)
        summary.to_csv(output_dir / "summary.csv", index=False)
        paired = paired_loso_comparison(subject_scores, config["seed"])
        (output_dir / "paired_loso.json").write_text(json.dumps(paired, indent=2), encoding="utf-8")
        save_plots(subject_scores, predictions, output_dir / "figures")
        status = {
            "status": "complete",
            "started_at_utc": started.isoformat(),
            "finished_at_utc": datetime.now(UTC).isoformat(),
            "n_selected_epochs": len(meta),
            "n_folds": len(manifest[["mode", "fold_id"]].drop_duplicates()),
            "n_model_fits": len(folds),
        }
        (output_dir / "run_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
        print(summary.to_string(index=False), flush=True)
        print(f"Completed results: {output_dir}", flush=True)
    except Exception as exc:
        status = {
            "status": "failed",
            "started_at_utc": started.isoformat(),
            "failed_at_utc": datetime.now(UTC).isoformat(),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        (output_dir / "run_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
