"""Independent Q12 scientific audit of fits, source-only splits and predictions.

Unlike batch orchestration, this checks the underlying per-trial labels,
probabilities, metrics, checkpoint outputs and source-transform fit identities.
The default mode requires raw BNCI data to reconstruct every target prediction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import balanced_accuracy_score, confusion_matrix
from threadpoolctl import threadpool_limits

from mi_eeg.data.bnci_epochs import load_configured_epochs
from mi_eeg.models.eegnet_training import build_eegnet, predict_probabilities
from scripts import q9_batch
from scripts import validate_q11_e001 as q11_audit
from scripts.run_eegnet import source_files, verify_q4_identity

MATRIX = ROOT / "research_runs/Q12-PREP-20260926/MATRIX.json"
PROTOCOL = ROOT / "research_runs/Q12-PREP-20260926/PROTOCOL.md"
Q8_CONFIG = ROOT / "research_runs/Q8-E001/results/config.json"
Q8_META = ROOT / "research_runs/Q8-E001/results/trial_metadata.csv"
Q8_METRICS = ROOT / "research_runs/Q8-E001/results/subject_seed_metrics.csv"
SEEDS = (20260924, 20260925, 20260926)
COMMON = ("checkpoint.pt", "learning_curve.csv", "fit_manifest.csv", "model_receipt.json")
FINAL = COMMON + ("predictions.csv", "metrics.csv", "confusion.csv")


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def sample_ids_hash(ids: list[str]) -> str:
    result = hashlib.sha256()
    for sample_id in ids:
        encoded = sample_id.encode("utf-8")
        result.update(len(encoded).to_bytes(4, "big"))
        result.update(encoded)
    return result.hexdigest()


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected JSON object at {path}")
    return value


def _check_fit(directory: Path, expected: tuple[str, ...]) -> dict:
    status = _read(directory / "status.json")
    if status.get("status") != "complete":
        raise AssertionError(f"Incomplete Q12 fit: {directory}")
    for name in expected:
        path = directory / name
        if not path.is_file() or digest(path) != status.get(f"sha256_{name}"):
            raise AssertionError(f"Missing/corrupt Q12 fit artifact: {path}")
    return status


def check_whitener(receipt: dict, reference: pd.DataFrame, *, subjects: list[int]) -> np.ndarray:
    """Check exact source membership and mathematical shape, not target moments."""
    subjects = sorted(subjects)
    training = reference.loc[reference.subject.isin(subjects)]
    if (receipt.get("method") != "source_subject_equal_covariance_whitening"
            or receipt.get("target_fitted_transform") is not False
            or receipt.get("train_subjects") != subjects
            or receipt.get("n_train_trials") != len(training)
            or receipt.get("ordered_train_sample_ids_sha256")
            != sample_ids_hash(training.sample_id.astype(str).tolist())
            or receipt.get("ridge_fraction") != 0.05):
        raise AssertionError("Whitening fit boundaries/parameters differ from source-only protocol")
    if receipt.get("train_subject_trial_counts") != {
            str(subject): int((training.subject == subject).sum()) for subject in subjects}:
        raise AssertionError("Whitening source-subject trial counts changed")
    matrix = np.asarray(receipt["spatial_weight"], dtype=float)
    eigenvalues = np.asarray(receipt["source_covariance_eigenvalues"], dtype=float)
    if (matrix.shape != (22, 22) or eigenvalues.shape != (22,)
            or not np.isfinite(matrix).all() or not np.isfinite(eigenvalues).all()
            or not np.allclose(matrix, matrix.T, rtol=0, atol=1e-9)
            or np.linalg.eigvalsh(matrix).min() <= 0
            or receipt["ridge"] <= 0 or receipt["mean_eigenvalue"] <= 0):
        raise AssertionError("Invalid source spatial whitener")
    return matrix


def check_checkpoint(directory: Path, config: dict, status: dict) -> dict:
    state = torch.load(directory / "checkpoint.pt", map_location="cpu", weights_only=True)
    receipt = _read(directory / "model_receipt.json")
    for key in ("experiment_id", "condition", "target_subject", "stage", "seed", "train_subjects"):
        if state.get(key) != status.get(key):
            raise AssertionError(f"Q12 checkpoint/status identity mismatch: {key}")
    if status["stage"] == "full" and state.get("selected_epochs") != status.get("selected_epochs"):
        raise AssertionError("Q12 trained duration differs from selected duration")
    if (receipt.get("experiment_id") != config["experiment_id"]
            or receipt.get("condition") != config["condition"]
            or receipt.get("architecture") != config["architecture"]
            or receipt.get("method") != config["method"]
            or receipt.get("method_parameters") != config["method_parameters"]):
        raise AssertionError("Q12 model receipt differs from locked config")
    weights = state.get("model_state")
    if not isinstance(weights, dict):
        raise TypeError("Q12 checkpoint lacks model state")
    count = 0
    for name, shape in receipt["parameter_shapes"].items():
        if name not in weights or list(weights[name].shape) != shape:
            raise AssertionError(f"Q12 checkpoint missing/wrong model tensor {name}")
        count += weights[name].numel()
    if count != receipt["trainable_parameter_count"]:
        raise AssertionError("Q12 model parameter count disagrees with checkpoint")
    group = receipt["group_training"]
    if (group["train_subjects"] != sorted(status["train_subjects"])
            or group["balanced_batches"] != (config["method"] in {"balanced_erm", "group_dro"})
            or group["nominal_batch_size"] != 64):
        raise AssertionError("Q12 group-training provenance differs")
    group_weights = group["final_group_weights"]
    if config["method"] == "group_dro":
        if (len(group_weights) != len(status["train_subjects"])
                or not np.isfinite(group_weights).all()
                or not np.isclose(sum(group_weights), 1.0, atol=1e-8)):
            raise AssertionError("Invalid saved Q12 GroupDRO weights")
    elif group_weights is not None:
        raise AssertionError("Non-GroupDRO condition saved GroupDRO weights")
    return weights


def check_predictions(frame: pd.DataFrame, reference: pd.DataFrame, *,
                      subject: int, seed: int, config: dict, selected: int) -> dict:
    expected = reference.loc[reference.subject == subject].reset_index(drop=True)
    if len(frame) != 576 or frame.sample_id.nunique() != 576:
        raise AssertionError("Q12 target does not have 576 unique trials")
    for column in ("sample_id", "label", "session", "artifact_flagged"):
        if frame[column].astype(str).tolist() != expected[column].astype(str).tolist():
            raise AssertionError(f"Q12 target inventory mismatch in {column}")
    if (frame.subject.astype(int).unique().tolist() != [subject]
            or frame.seed.astype(int).unique().tolist() != [seed]
            or frame.experiment_id.unique().tolist() != [config["experiment_id"]]
            or frame.condition.unique().tolist() != [config["condition"]]
            or frame.fold.unique().tolist() != [f"loso_s{subject}"]
            or frame.selected_epochs.astype(int).unique().tolist() != [selected]
            or frame.selection_rule.unique().tolist() != ["mean_rank"]):
        raise AssertionError("Q12 prediction identity/selection metadata mismatch")
    truth = frame.y_true.to_numpy(dtype=int)
    prediction = frame.y_pred.to_numpy(dtype=int)
    if (not np.array_equal(truth, frame.label.to_numpy(dtype=int))
            or np.bincount(truth, minlength=5)[1:].tolist() != [144] * 4):
        raise AssertionError("Q12 labels/class balance differ from Q8")
    probability = frame[[f"p_class_{cls}" for cls in range(1, 5)]].to_numpy(dtype=float)
    if (not np.isfinite(probability).all() or (probability < 0).any()
            or not np.allclose(probability.sum(axis=1), 1.0, atol=1e-6, rtol=0)
            or not np.array_equal(prediction, probability.argmax(axis=1) + 1)):
        raise AssertionError("Q12 probabilities/prediction disagree")
    matrix = confusion_matrix(truth, prediction, labels=[1, 2, 3, 4])
    recalls = np.diag(matrix) / matrix.sum(axis=1)
    return {"experiment_id": config["experiment_id"], "condition": config["condition"],
            "subject": subject, "seed": seed,
            "balanced_accuracy": float(balanced_accuracy_score(truth, prediction)),
            "zero_recall_classes": int((recalls == 0).sum()),
            "dominant_prediction_share": float(np.bincount(prediction, minlength=5)[1:].max()
                                               / len(prediction)),
            **{f"recall_class_{cls}": float(recalls[cls - 1]) for cls in range(1, 5)}}


def load_signal(data_dir: Path, device: torch.device) -> tuple[torch.Tensor, pd.DataFrame]:
    frozen = _read(Q8_CONFIG)
    with threadpool_limits(limits=2):
        bands, meta, _audit = load_configured_epochs(
            frozen["subjects"], data_dir, frozen["preprocessing"], frozen["class_ids"])
    if list(bands) != ["broad"] or len(meta) != 5184:
        raise AssertionError("Independent Q12 input differs from frozen Q8")
    verify_q4_identity(meta, pd.read_csv(Q8_META))
    signal = bands["broad"] * np.float32(frozen["input"]["volts_to_microvolts"])
    if signal.shape != (5184, 22, 750) or not np.isfinite(signal).all():
        raise AssertionError("Invalid independent Q12 signal array")
    return torch.from_numpy(signal).to(device), meta


def reconstruct_prediction(weights: dict, config: dict, signal: torch.Tensor,
                           target: np.ndarray, receipt: dict | None,
                           saved: pd.DataFrame, device: torch.device) -> None:
    model = build_eegnet(config["architecture"], device)
    model.load_state_dict(weights, strict=True)
    model.eval()
    if receipt is None:
        transformed = signal
    else:
        matrix = torch.as_tensor(receipt["spatial_weight"], dtype=signal.dtype,
                                 device=signal.device)
        transformed = torch.einsum("cd,ndt->nct", matrix, signal[target])
    indices = target if receipt is None else np.arange(len(target))
    reconstructed = predict_probabilities(model, transformed, indices,
                                          int(config["training"]["batch_size"]))
    stored = saved[[f"p_class_{cls}" for cls in range(1, 5)]].to_numpy(dtype=float)
    if not np.allclose(reconstructed, stored, rtol=1e-4, atol=5e-5):
        raise AssertionError("Q12 saved target probabilities differ from checkpoint inference")
    if not np.array_equal(reconstructed.argmax(axis=1) + 1, saved.y_pred.to_numpy(dtype=int)):
        raise AssertionError("Q12 checkpoint yields different class predictions")


def _compare_aggregate(path: Path, frames: list[pd.DataFrame]) -> None:
    observed = pd.read_csv(path)
    expected = pd.concat(frames, ignore_index=True)
    pd.testing.assert_frame_equal(observed, expected, check_dtype=False,
                                  check_exact=False, rtol=0, atol=1e-12)


def audit(results_root: Path, data_dir: Path) -> dict:
    matrix = _read(MATRIX)
    rows = matrix["conditions"]
    if len(rows) != 6 or matrix["totals"]["new_deep_fits"] != 378:
        raise AssertionError("Q12 matrix/fit count changed")
    reference = pd.read_csv(Q8_META)
    if len(reference) != 5184:
        raise AssertionError("Frozen Q8 trial reference unavailable")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    signal, independent_meta = load_signal(data_dir, device)
    expected_source_files = {
        "files": source_files(data_dir, list(range(1, 10))),
        "q8_metadata_sha256": digest(Q8_META),
    }
    all_metrics, condition_reports = [], []
    for row in rows:
        experiment, condition = row["experiment_id"], row["id"]
        directory = results_root / experiment / condition
        config = _read(directory / "run_config.json")
        if (config.get("experiment_id") != experiment or config.get("condition") != condition
                or config.get("method") != row["method"]
                or config.get("target_fitted_transform") is not False
                or config.get("matrix_sha256") != digest(MATRIX)
                or config.get("protocol_sha256") != digest(PROTOCOL)
                or config.get("q8_config_sha256") != digest(Q8_CONFIG)
                or config.get("runner_sha256") != digest(ROOT / "scripts/q12_dg.py")
                or config.get("data_dir") != str(data_dir.resolve())):
            raise AssertionError(f"Q12 locked config mismatch: {condition}")
        q11_audit_hash = _read(directory / "source_files.json")
        if q11_audit_hash != expected_source_files:
            raise AssertionError("Q12 raw MAT file hashes or Q8 metadata source changed")
        selection = pd.read_csv(directory / "selection.csv").set_index("subject")
        provenance = _read(directory / "selection_provenance.json")
        if (provenance["status"] != "frozen_before_Q12_target_inference"
                or provenance["selection_sha256"] != digest(directory / "selection.csv")
                or provenance["run_config_sha256"] != digest(directory / "run_config.json")
                or provenance["target_result_used"] is not False
                or set(selection.index.astype(int)) != set(range(1, 10))):
            raise AssertionError(f"Q12 source selection not frozen: {condition}")
        inner_count, final_count = 0, 0
        prediction_frames, metric_frames, confusion_frames = [], [], []
        for subject in range(1, 10):
            source = [item for item in range(1, 10) if item != subject]
            curves = []
            for inner in range(1, 5):
                fit = directory / "inner" / f"loso_s{subject}" / f"inner_{inner}"
                required = COMMON + (("source_whitener.json",) if row["method"] == "whiten" else ())
                status = _check_fit(fit, required)
                if (status["target_subject"] != subject or status["inner_fold"] != inner
                        or status["seed"] != 20260923
                        or status["validation_subjects"] != source[2 * (inner - 1):2 * inner]):
                    raise AssertionError("Q12 inner source/validation subjects differ")
                manifest = pd.read_csv(fit / "fit_manifest.csv")
                q11_audit.validate_manifest(manifest, target=subject, inner=inner,
                                            seed=20260923, epochs=40)
                if row["method"] == "whiten":
                    check_whitener(_read(fit / "source_whitener.json"), reference,
                                   subjects=status["train_subjects"])
                check_checkpoint(fit, config, status)
                curves.append(pd.read_csv(fit / "learning_curve.csv"))
                inner_count += 1
            chosen = q11_audit.independent_epoch(curves)
            if (int(selection.loc[subject, "selected_epochs"]) != chosen
                    or str(selection.loc[subject, "target_result_used"]).lower() != "false"):
                raise AssertionError("Q12 selected epoch differs from independent source-only curves")
            for seed in SEEDS:
                fit = directory / "final" / f"loso_s{subject}" / f"seed_{seed}"
                required = FINAL + (("source_whitener.json",) if row["method"] == "whiten" else ())
                status = _check_fit(fit, required)
                if (status["target_subject"] != subject or status["seed"] != seed
                        or status["train_subjects"] != source
                        or status["selected_epochs"] != chosen
                        or status["selection_sha256"] != digest(directory / "selection.csv")):
                    raise AssertionError("Q12 final fit/source selection provenance mismatch")
                manifest = pd.read_csv(fit / "fit_manifest.csv")
                q11_audit.validate_manifest(manifest, target=subject, inner=None,
                                            seed=seed, epochs=chosen)
                weights = check_checkpoint(fit, config, status)
                whitening = None
                if row["method"] == "whiten":
                    whitening = _read(fit / "source_whitener.json")
                    check_whitener(whitening, reference, subjects=source)
                pred = pd.read_csv(fit / "predictions.csv")
                metrics = pd.read_csv(fit / "metrics.csv")
                confusion = pd.read_csv(fit / "confusion.csv")
                summary = check_predictions(pred, reference, subject=subject, seed=seed,
                                            config=config, selected=chosen)
                q11_audit.validate_metric_files(pred, metrics, confusion,
                                                subject=subject, seed=seed, condition=condition)
                target = np.flatnonzero((independent_meta.subject == subject).to_numpy())
                reconstruct_prediction(weights, config, signal, target, whitening, pred, device)
                prediction_frames.append(pred)
                metric_frames.append(metrics)
                confusion_frames.append(confusion)
                all_metrics.append(summary)
                final_count += 1
        status = _read(directory / "status.json")
        if (inner_count, final_count) != (36, 27) or status.get("status") != "complete":
            raise AssertionError(f"Q12 {condition} expected 36 inner and 27 final fits")
        _compare_aggregate(directory / "predictions.csv", prediction_frames)
        _compare_aggregate(directory / "per_subject_metrics.csv", metric_frames)
        _compare_aggregate(directory / "confusion_matrices.csv", confusion_frames)
        condition_reports.append({"experiment_id": experiment, "condition": condition,
                                  "inner_fits": inner_count, "final_fits": final_count,
                                  "checkpoint_predictions_reconstructed": 27})
    metrics = pd.DataFrame(all_metrics)
    baseline = pd.read_csv(Q8_METRICS)[["subject", "seed", "balanced_accuracy"]]
    paired = {}
    families = matrix["contrast_families"]
    for family, entries in families.items():
        p_values = {}
        for contrast in entries:
            new, old = contrast.split("-", 1)
            candidate = metrics.loc[metrics.condition == new,
                                    ["subject", "seed", "balanced_accuracy"]]
            control = baseline if old == "Q8-E001" else metrics.loc[
                metrics.condition == old, ["subject", "seed", "balanced_accuracy"]]
            effect = q11_audit.paired_subject_summary(candidate, control)
            paired[contrast] = {"family": family, **effect}
            p_values[contrast] = effect["exact_sign_flip_two_sided_p_exploratory"]
        adjusted = q11_audit.holm_adjust(p_values)
        for contrast in entries:
            paired[contrast]["holm_within_family_p_exploratory"] = adjusted[contrast]
    batch = results_root / "Q12-BATCH"
    batch.mkdir(parents=True, exist_ok=True)
    q9_batch.atomic_json(batch / "paired_subject_contrasts.json", paired)
    metrics.to_csv(batch / "subject_seed_metrics.csv", index=False)
    subject = metrics.groupby(["experiment_id", "condition", "subject"], as_index=False).agg(
        balanced_accuracy_mean=("balanced_accuracy", "mean"),
        balanced_accuracy_seed_sd=("balanced_accuracy", "std"),
        zero_recall_classes_mean=("zero_recall_classes", "mean"),
        dominant_prediction_share_mean=("dominant_prediction_share", "mean"))
    subject.to_csv(batch / "subject_level_metrics.csv", index=False)
    return {"status": "passed_scientific_checks", "conditions": condition_reports,
            "inner_fits": 216, "final_fits": 162, "target_prediction_reconstructions": 162,
            "inference_unit": "held_out_subject_after_paired_seed_mean",
            "exploratory_post_Q8": True, "source_only_transform_receipts_checked": 63,
            "paired_contrasts": list(paired), "matrix_sha256": digest(MATRIX)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, default=ROOT / "results")
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.results_root.resolve() / "Q12-BATCH" / "scientific_validation.json"
    try:
        report = audit(args.results_root.resolve(), args.data_dir.resolve())
        result = 0
    except Exception:  # noqa: BLE001 - persist failed scientific audit receipt
        report = {"status": "failed_scientific_checks", "traceback": traceback.format_exc()}
        result = 1
    q9_batch.atomic_json(output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
