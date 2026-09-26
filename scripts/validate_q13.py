"""Independent Q13 fit/prediction/protocol audit and subject-level tables.

The full scientific pass replays every frozen checkpoint against raw BNCI EEG.
An explicit artifact-only mode is available for cheap triage, but cannot issue
the scientific ``passed`` receipt. No model fitting occurs in either mode.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, confusion_matrix

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "research_runs/Q13-PREP-20260926/MATRIX.json"
REFERENCE = ROOT / "research_runs/Q8-E001/results/trial_metadata.csv"
Q5_METRICS = ROOT / "results/Q5-E001/per_subject_metrics.csv"
Q9_INNER = ROOT / "results/Q9-E001/MU_BETA_SHARED/inner"
SEEDS = (20260924, 20260925, 20260926)
SUBJECTS = tuple(range(1, 10))
REQUIRED = ("checkpoint.pt", "learning_curve.csv", "fit_manifest.csv",
            "predictions.csv", "metrics.csv", "confusion.csv")
CONDITIONS = {
    "Q13-E001": ("Q8_FIXED20", "Q9_SHARED_RAW_CE", "Q9_SHARED_FIXED20"),
    "Q13-E004": ("Q8_SRC2", "Q8_SRC4", "Q8_SRC6",
                  "Q9_SHARED_SRC2", "Q9_SHARED_SRC4", "Q9_SHARED_SRC6"),
    "Q13-E005": ("Q8_SOURCE_SESSION_T", "Q8_SOURCE_SESSION_E",
                  "Q9_SHARED_SOURCE_SESSION_T", "Q9_SHARED_SOURCE_SESSION_E"),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _receipt_matches(path: Path, expected: str) -> bool:
    if _sha256(path) == expected:
        return True
    # Git for Windows may check out historical result CSVs as CRLF. Only allow
    # the original tracked Git blob when the checkout is unmodified.
    try:
        relative = path.relative_to(ROOT).as_posix()
    except ValueError:
        return False
    clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", relative],
                           cwd=ROOT, capture_output=True, check=False)
    if clean.returncode:
        return False
    blob = subprocess.run(["git", "show", f"HEAD:{relative}"], cwd=ROOT,
                          capture_output=True, check=False)
    return blob.returncode == 0 and hashlib.sha256(blob.stdout).hexdigest() == expected


def source_windows_independent(target: int, k: int) -> list[tuple[str, tuple[int, ...]]]:
    others = [i for i in SUBJECTS if i != target]
    if k not in (2, 4, 6):
        raise AssertionError("Unexpected source count")
    rows = [(f"k{k}_start{start}", tuple(others[(start + j) % 8] for j in range(k)))
            for start in (0, 2, 4, 6)]
    if {subject: sum(subject in subset for _, subset in rows) for subject in others} != {
            subject: k // 2 for subject in others}:
        raise AssertionError("Unbalanced source identity window")
    return rows


def condition_specs(condition: str, target: int) -> list[tuple[str, tuple[int, ...], str | None]]:
    if "_SRC" in condition:
        k = int(condition.rsplit("_SRC", 1)[1])
        return [(subset, source, None) for subset, source in source_windows_independent(target, k)]
    source = tuple(subject for subject in SUBJECTS if subject != target)
    session = ("0train" if condition.endswith("_SESSION_T") else
               "1test" if condition.endswith("_SESSION_E") else None)
    return [("all", source, session)]


def raw_ce_from_original_curves(target: int) -> int:
    columns = []
    for inner in (1, 2, 3, 4):
        curve = pd.read_csv(Q9_INNER / f"loso_s{target}" / f"inner_{inner}" / "learning_curve.csv")
        if curve.epoch.astype(int).tolist() != list(range(1, 41)):
            raise AssertionError("Q9 original curve has wrong epochs")
        values = curve.val_ce.to_numpy(float)
        if not np.isfinite(values).all():
            raise AssertionError("Q9 original source CE nonfinite")
        columns.append(values)
    averages = np.vstack(columns).mean(axis=0)
    return int(np.flatnonzero(np.isclose(averages, averages.min(), atol=1e-12, rtol=0))[0] + 1)


def validate_prediction(frame: pd.DataFrame, reference: pd.DataFrame,
                        *, target: int, seed: int, condition: str,
                        subset_id: str, source: tuple[int, ...],
                        source_session: str | None, selected_epochs: int) -> dict:
    expected = reference[reference.subject == target].copy()
    if len(frame) != len(expected) or len(frame) != 576:
        raise AssertionError("Target predictions do not cover 576 trials")
    if frame.sample_id.duplicated().any() or set(frame.sample_id) != set(expected.sample_id):
        raise AssertionError("Prediction trial identities differ from frozen Q8")
    merged = frame.set_index("sample_id").loc[expected.sample_id].reset_index()
    for key in ("subject", "session", "run", "trial", "label", "event_sample", "artifact_flagged"):
        if merged[key].astype(str).tolist() != expected[key].astype(str).tolist():
            raise AssertionError(f"Prediction metadata {key} differs from frozen Q8")
    if (merged.subject.ne(target).any() or merged.seed.ne(seed).any()
            or merged.condition.ne(condition).any() or merged.subset_id.ne(subset_id).any()
            or merged.selected_epochs.ne(selected_epochs).any()
            or merged.y_true.astype(int).ne(merged.label.astype(int)).any()):
        raise AssertionError("Prediction fit identity/labels differ")
    if merged.train_subjects.unique().tolist() != ["|".join(str(s) for s in source)]:
        raise AssertionError("Prediction source identity differs")
    if merged.source_session.unique().tolist() != [source_session or "both"]:
        raise AssertionError("Prediction source session differs")
    p = merged[[f"p_class_{i}" for i in range(1, 5)]].to_numpy(float)
    if (not np.isfinite(p).all() or (p < -1e-6).any() or (p > 1 + 1e-6).any()
            or not np.allclose(p.sum(axis=1), 1.0, atol=1e-5, rtol=0)):
        raise AssertionError("Prediction probabilities are invalid")
    prediction = np.argmax(p, axis=1) + 1
    if not np.array_equal(prediction, merged.y_pred.to_numpy(int)):
        raise AssertionError("Saved classes disagree with probability argmax")
    truth = merged.y_true.to_numpy(int)
    matrix = confusion_matrix(truth, prediction, labels=[1, 2, 3, 4])
    if not np.array_equal(matrix.sum(axis=1), np.full(4, 144)):
        raise AssertionError("Held-out class counts are not 144 each")
    return {"balanced_accuracy": float(balanced_accuracy_score(truth, prediction)),
            "confusion": matrix, "n_predictions": 576,
            "zero_recall_classes": int((matrix.diagonal() == 0).sum())}


def _replay_checkpoint(directory: Path, config: dict, signal: object,
                       reference: pd.DataFrame, frame: pd.DataFrame,
                       *, target: int, seed: int, source: tuple[int, ...],
                       selected: int, device: object) -> None:
    """Rebuild one model and compare its probabilities on frozen target trials."""
    import torch

    from mi_eeg.models.eegnet_training import predict_probabilities
    from scripts import q9_neural

    payload = torch.load(directory / "checkpoint.pt", map_location="cpu", weights_only=True)
    if (payload.get("target_subject") != target or payload.get("seed") != seed
            or payload.get("train_subjects") != list(source)
            or payload.get("selected_epochs") != selected):
        raise AssertionError("Q13 checkpoint identity differs from fit receipt")
    model = q9_neural._build_model(config, device)
    model.load_state_dict(payload["model_state"], strict=True)
    test = np.flatnonzero(reference.subject.eq(target).to_numpy())
    replay = predict_probabilities(model, signal, test, config["training"]["batch_size"])
    ordered = frame.set_index("sample_id").loc[reference.iloc[test].sample_id]
    saved = ordered[[f"p_class_{i}" for i in range(1, 5)]].to_numpy(float)
    if (replay.shape != (576, 4) or not np.isfinite(replay).all()
            or not np.allclose(replay, saved, rtol=0, atol=1e-5)
            or not np.array_equal(replay.argmax(axis=1) + 1, ordered.y_pred.to_numpy(int))):
        raise AssertionError("Q13 checkpoint replay differs from saved target predictions")
    del model
    if device.type == "cuda":
        torch.cuda.empty_cache()


def _validate_fit(directory: Path, reference: pd.DataFrame, *, target: int,
                  seed: int, condition: str, subset_id: str,
                  source: tuple[int, ...], session: str | None,
                  selected: int, replay_context: tuple | None = None) -> dict:
    status_path = directory / "status.json"
    if not status_path.is_file():
        raise AssertionError(f"Missing Q13 fit: {directory}")
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if status.get("status") != "complete":
        raise AssertionError(f"Q13 fit incomplete: {directory}")
    for filename in REQUIRED:
        path = directory / filename
        if not path.is_file() or not _receipt_matches(path, status.get(f"sha256_{filename}", "")):
            raise AssertionError(f"Q13 fit receipt/hash failed: {path}")
    n_source_trials = len(source) * (288 if session else 576)
    if (status.get("target_subject") != target or status.get("seed") != seed
            or status.get("train_subjects") != list(source)
            or status.get("source_session") != session
            or status.get("selected_epochs") != selected
            or status.get("n_train") != n_source_trials
            or status.get("n_test") != 576
            or status.get("optimizer_updates") != selected * ((n_source_trials + 63) // 64)):
        raise AssertionError("Q13 fit source/epoch/update receipt differs")
    manifest = pd.read_csv(directory / "fit_manifest.csv")
    if len(manifest) != 18 or manifest.n_used_for_fit.sum() != n_source_trials:
        raise AssertionError("Q13 fit manifest count differs")
    for row in manifest.itertuples():
        expected_role = ("target_test" if row.subject == target else
                         "source_fit" if row.subject in source and (session is None or row.session == session)
                         else "source_excluded")
        if row.role != expected_role or row.n_trials != 288 or row.n_used_for_fit != (
                288 if expected_role == "source_fit" else 0):
            raise AssertionError("Q13 source/target/session fit boundary violated")
    frame = pd.read_csv(directory / "predictions.csv")
    scores = validate_prediction(frame, reference,
                                 target=target, seed=seed, condition=condition,
                                 subset_id=subset_id, source=source,
                                 source_session=session, selected_epochs=selected)
    if replay_context is not None:
        config, signal, device = replay_context
        _replay_checkpoint(directory, config, signal, reference, frame,
                           target=target, seed=seed, source=source,
                           selected=selected, device=device)
    metric = pd.read_csv(directory / "metrics.csv")
    primary = metric[metric.stratum == "all"]
    if len(primary) != 1 or not np.isclose(
            float(primary.balanced_accuracy.iloc[0]), scores["balanced_accuracy"], atol=1e-12):
        raise AssertionError("Saved BA differs from recomputed trial predictions")
    confusion = pd.read_csv(directory / "confusion.csv")
    all_rows = confusion[confusion.stratum == "all"]
    observed = all_rows.pivot(index="true_label", columns="predicted_label", values="count")
    observed = observed.reindex(index=[1, 2, 3, 4], columns=[1, 2, 3, 4])
    if not np.array_equal(observed.to_numpy(int), scores["confusion"]):
        raise AssertionError("Saved confusion differs from recomputed trial predictions")
    return {"target": target, "seed": seed, "condition": condition,
            "subset_id": subset_id, "source_count": len(source),
            "source_session": session or "both", "train_subjects": "|".join(map(str, source)),
            "balanced_accuracy": scores["balanced_accuracy"],
            "zero_recall_classes": scores["zero_recall_classes"],
            "optimizer_updates": status["optimizer_updates"],
            "n_train": n_source_trials}


def _atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temp, index=False)
    os.replace(temp, path)


def validate_all(results_root: Path, *, data_dir: Path | None = None,
                 device_name: str = "cuda") -> dict:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    if matrix["total_new_deep_fits"] != 837:
        raise AssertionError("Q13 predeclared fit total changed")
    reference = pd.read_csv(REFERENCE)
    if len(reference) != 5184 or reference.sample_id.duplicated().any():
        raise AssertionError("Frozen Q8 metadata invalid")
    if data_dir is not None:
        import mne
        import torch

        from scripts import q9_neural

        if not data_dir.is_dir():
            raise FileNotFoundError(f"Raw BNCI directory missing: {data_dir}")
        if device_name == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested for Q13 checkpoint replay but unavailable")
        device = torch.device(device_name)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        torch.set_num_threads(4)
        mne.set_log_level("ERROR")
    rows = []
    for experiment, conditions in CONDITIONS.items():
        for condition in conditions:
            root = results_root / experiment / condition
            config = json.loads((root / "run_config.json").read_text(encoding="utf-8"))
            summary = json.loads((root / "status.json").read_text(encoding="utf-8"))
            expected_count = 108 if experiment == "Q13-E004" else 27
            if config.get("target_fit_or_selection") is not False:
                raise AssertionError("Target fit/selection contract is not false")
            if config.get("experiment_id") != experiment or config.get("condition") != condition:
                raise AssertionError("Run config ID mismatch")
            if summary.get("status") != "complete" or summary.get("completed_final_fits") != expected_count:
                raise AssertionError(f"Q13 condition incomplete: {condition}")
            replay_context = None
            if data_dir is not None:
                signal, _labels, loaded_meta, _numpy_signal = q9_neural._load_data(
                    config, data_dir, device, root
                )
                if loaded_meta.sample_id.astype(str).tolist() != reference.sample_id.astype(str).tolist():
                    raise AssertionError("Raw EEG trial order differs from frozen Q8 metadata")
                replay_context = (config, signal, device)
            for target in SUBJECTS:
                selected = (raw_ce_from_original_curves(target) if condition == "Q9_SHARED_RAW_CE"
                            else 20)
                if config["selected_epochs_by_target"][str(target)] != selected:
                    raise AssertionError("Q13 epoch selection differs from independent reconstruction")
                for subset_id, source, session in condition_specs(condition, target):
                    for seed in SEEDS:
                        directory = root / "final" / f"loso_s{target}" / subset_id / f"seed_{seed}"
                        rows.append(_validate_fit(directory, reference, target=target,
                                                  seed=seed, condition=condition,
                                                  subset_id=subset_id, source=source,
                                                  session=session, selected=selected,
                                                  replay_context=replay_context))
            if replay_context is not None:
                del signal, replay_context
                if device.type == "cuda":
                    torch.cuda.empty_cache()
    if len(rows) != 837:
        raise AssertionError("Q13 new fit count differs from 837")
    analysis = results_root / "Q13-BATCH" / "analysis"
    fit_table = pd.DataFrame(rows)
    _atomic_csv(analysis / "fit_level.csv", fit_table)
    # Subsets and seeds are repeated measurements; only target subjects form
    # the top-level inference rows. k=8 anchors are Q13-E001 fixed-20 fits.
    count_rows = fit_table[fit_table.condition.str.contains("_SRC")].copy()
    count_rows["method"] = np.where(count_rows.condition.str.startswith("Q8"), "Q8_BROAD", "Q9_MU_BETA_SHARED")
    count_rows["source_count"] = count_rows.condition.str.extract(r"_SRC([246])").astype(int)
    anchors = fit_table[fit_table.condition.isin(["Q8_FIXED20", "Q9_SHARED_FIXED20"])].copy()
    anchors["method"] = np.where(anchors.condition == "Q8_FIXED20", "Q8_BROAD", "Q9_MU_BETA_SHARED")
    anchors["source_count"] = 8
    count_rows = pd.concat([count_rows, anchors], ignore_index=True)
    subject_count = count_rows.groupby(["target", "method", "source_count"], as_index=False).agg(
        balanced_accuracy=("balanced_accuracy", "mean"),
        min_subset_seed_ba=("balanced_accuracy", "min"),
        max_subset_seed_ba=("balanced_accuracy", "max"),
        n_repeated_fits=("balanced_accuracy", "size"))
    if len(subject_count) != 9 * 2 * 4:
        raise AssertionError("Q13 subject/count table has wrong grain")
    _atomic_csv(analysis / "subject_source_count.csv", subject_count)
    session_rows = fit_table[fit_table.condition.str.contains("_SOURCE_SESSION_")].copy()
    session_rows["method"] = np.where(session_rows.condition.str.startswith("Q8"), "Q8_BROAD", "Q9_MU_BETA_SHARED")
    subject_session = session_rows.groupby(["target", "method", "source_session"], as_index=False).agg(
        balanced_accuracy=("balanced_accuracy", "mean"),
        seed_sd=("balanced_accuracy", "std"))
    if len(subject_session) != 9 * 2 * 2:
        raise AssertionError("Q13 source-session table has wrong grain")
    _atomic_csv(analysis / "subject_source_session.csv", subject_session)
    # Q5 reuse is read-only and appears only in the selection-sensitivity table.
    q5 = pd.read_csv(Q5_METRICS)
    original = q5[(q5.stratum == "all") & (q5.model == "EEGNet")][
        ["subject", "seed", "balanced_accuracy"]].copy()
    if len(original) != 27:
        raise AssertionError("Q5 reused model has not exactly 27 full primary metrics")
    original["condition"] = "Q8_RAW_CE_REUSE_Q5"
    original = original.rename(columns={"subject": "target"})
    selection = pd.concat([fit_table[fit_table.condition.isin((
        "Q8_FIXED20", "Q9_SHARED_RAW_CE", "Q9_SHARED_FIXED20"))][
        ["target", "seed", "balanced_accuracy", "condition"]], original], ignore_index=True)
    selection_subject = selection.groupby(["target", "condition"], as_index=False).agg(
        balanced_accuracy=("balanced_accuracy", "mean"),
        seed_sd=("balanced_accuracy", "std"))
    if len(selection_subject) != 9 * 4:
        raise AssertionError("Q13 selection-sensitivity table has wrong grain")
    _atomic_csv(analysis / "subject_selection.csv", selection_subject)
    report = {"status": "passed" if data_dir is not None else "artifact_only_not_scientific_pass",
              "checkpoint_replays": 837 if data_dir is not None else 0,
              "new_deep_fits": 837,
              "reused_q5_raw_ce_fits": 27, "reused_q13_fixed20_k8_fits": 54,
              "n_outer_subjects": 9, "n_independently_checked_predictions": 837 * 576,
              "target_fit_or_selection": False,
              "inference_unit": "held_out_subject; seeds and source subsets are repeated measurements",
              "analysis_status": "exploratory_post_Q9_not_independent_confirmation",
              "tables": ["fit_level.csv", "subject_source_count.csv",
                         "subject_source_session.csv", "subject_selection.csv"]}
    path = results_root / "Q13-BATCH" / "validation_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, default=ROOT / "results")
    parser.add_argument("--data-dir", type=Path,
                        help="raw BNCI MAT directory for full checkpoint replay")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--artifact-only", action="store_true",
                        help="triage existing files only; cannot issue a scientific pass")
    args = parser.parse_args()
    if args.artifact_only == (args.data_dir is not None):
        parser.error("provide exactly one of --data-dir or --artifact-only")
    report = validate_all(args.results_root.resolve(),
                          data_dir=args.data_dir.resolve() if args.data_dir else None,
                          device_name=args.device)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
