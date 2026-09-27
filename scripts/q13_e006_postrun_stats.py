"""Fail-closed Q13/E006 post-run subject-level sensitivity analysis.

Requires both independent scientific validators. This module never fits a
model, changes the frozen runs, chooses a seed/subset, or declares independent
confirmation from the already explored BNCI2014_001 cohort.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score

from scripts.validate_q13 import CONDITIONS as Q13_CONDITIONS
from scripts.validate_q13 import _receipt_matches

Q13_MATRIX = ROOT / "research_runs/Q13-PREP-20260926/MATRIX.json"
E006_MATRIX = ROOT / "research_runs/Q13-E006/MATRIX.json"
SEEDS = (20260924, 20260925, 20260926)
SUBJECTS = tuple(range(1, 10))
METHODS = ("Q8_BROAD", "Q9_MU_BETA_SHARED")
BOOTSTRAP_SEED = 20260926
BOOTSTRAP_DRAWS = 10000


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return value


def _digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def _unique(frame: pd.DataFrame, keys: list[str], expected: int, label: str) -> None:
    if (len(frame) != expected or not set(keys).issubset(frame)
            or frame[keys].isna().any().any() or frame.duplicated(keys).any()):
        raise AssertionError(f"{label} wrong grain, keys, or row count")


def _equal_mean(saved: pd.DataFrame, derived: pd.DataFrame, keys: list[str],
                label: str) -> None:
    _unique(saved, keys, len(derived), label)
    joined = saved.merge(derived, on=keys, how="outer", indicator=True,
                        suffixes=("_saved", "_derived"), validate="one_to_one")
    if (not joined._merge.eq("both").all()
            or not np.allclose(joined.balanced_accuracy_saved.to_numpy(float),
                               joined.balanced_accuracy_derived.to_numpy(float),
                               rtol=0, atol=1e-12)):
        raise AssertionError(f"{label} differs from fit-level reconstruction")


def exact_sign_flip_p(differences: np.ndarray) -> float:
    """Two-sided exhaustive sign-flip sensitivity for nine paired subjects."""
    values = np.asarray(differences, dtype=float)
    if values.shape != (9,) or not np.isfinite(values).all():
        raise ValueError("Exactly nine finite subject differences required")
    signs = np.asarray(list(itertools.product((-1.0, 1.0), repeat=9)))
    threshold = abs(float(values.mean()))
    null = np.abs((signs * values).mean(axis=1))
    return float(np.mean(null >= threshold - 1e-14))


def holm(p_values: dict[str, float]) -> dict[str, float]:
    """Holm step-down, for one named family at a time."""
    ordered = sorted(p_values, key=lambda name: (p_values[name], name))
    adjusted: dict[str, float] = {}
    current = 0.0
    for index, name in enumerate(ordered):
        p_value = float(p_values[name])
        if not np.isfinite(p_value) or not 0 <= p_value <= 1:
            raise ValueError("Invalid p-value")
        current = max(current, min(1.0, p_value * (len(ordered) - index)))
        adjusted[name] = current
    return adjusted


def paired_summary(differences: np.ndarray, draws: np.ndarray) -> dict:
    values = np.asarray(differences, dtype=float)
    if values.shape != (9,) or draws.ndim != 2 or draws.shape[1] != 9:
        raise ValueError("Subject-level array/bootstrap shape differs")
    boot = values[draws].mean(axis=1)
    lower, upper = np.quantile(boot, [0.025, 0.975])
    spread = float(values.std(ddof=1))
    return {
        "n_subjects": 9, "mean_paired_ba_difference": float(values.mean()),
        "median_paired_ba_difference": float(np.median(values)),
        "sd_paired_ba_difference": spread,
        "paired_dz": float(values.mean() / spread) if spread > 0 else np.nan,
        "min_paired_ba_difference": float(values.min()),
        "max_paired_ba_difference": float(values.max()),
        "subject_bootstrap_95ci_low": float(lower),
        "subject_bootstrap_95ci_high": float(upper),
        "exact_sign_flip_p_exploratory": exact_sign_flip_p(values),
    }


def _check_original_fit_inputs(results_root: Path, fits: pd.DataFrame,
                               selection: pd.DataFrame) -> str:
    """Recheck every Q13 fit-level BA against its hashed saved metrics."""
    condition_to_experiment = {
        condition: experiment
        for experiment, conditions in Q13_CONDITIONS.items()
        for condition in conditions
    }
    if set(fits.condition) != set(condition_to_experiment):
        raise AssertionError("Q13 fit-level condition inventory differs")
    observed = []
    for row in fits.itertuples(index=False):
        directory = (results_root / condition_to_experiment[row.condition] /
                     row.condition / "final" / f"loso_s{row.target}" /
                     row.subset_id / f"seed_{row.seed}")
        status_path = directory / "status.json"
        status = _read(status_path)
        if status.get("status") != "complete":
            raise AssertionError(f"Q13 original fit incomplete: {directory}")
        for filename in ("metrics.csv", "predictions.csv"):
            path = directory / filename
            if not path.is_file() or not _receipt_matches(
                path, status.get(f"sha256_{filename}", "")
            ):
                raise AssertionError(f"Q13 original fit receipt/hash differs: {path}")
            observed.append((path.relative_to(results_root).as_posix(), _digest(path)))
        metric = pd.read_csv(directory / "metrics.csv")
        primary = metric[metric.stratum.eq("all")]
        if (len(primary) != 1 or not np.isclose(
                float(primary.balanced_accuracy.iloc[0]), float(row.balanced_accuracy),
                rtol=0, atol=1e-12)):
            raise AssertionError(f"Q13 fit-level BA differs from original metric: {directory}")
    q5_path = results_root / "Q5-E001" / "per_subject_metrics.csv"
    q5_validation = _read(results_root / "Q5-E001" / "validation_report.json")
    if q5_validation.get("status") != "passed":
        raise AssertionError("Historical Q5 scientific validation not passed")
    q5 = pd.read_csv(q5_path)
    original = q5[q5.stratum.eq("all") & q5.model.eq("EEGNet")].copy()
    _unique(original, ["subject", "seed"], 27, "historical Q5 primary metrics")
    if (set(original.subject) != set(SUBJECTS) or set(original.seed) != set(SEEDS)
            or not original.balanced_accuracy.between(0, 1).all()):
        raise AssertionError("Historical Q5 subject/seed/BA coverage differs")
    expected = original.groupby("subject", as_index=False).balanced_accuracy.mean()
    expected = expected.rename(columns={"subject": "target"})
    historical = selection[selection.condition.eq("Q8_RAW_CE_REUSE_Q5")]
    _equal_mean(historical, expected, ["target"], "historical Q5 selection")
    observed.extend((("Q5-E001/per_subject_metrics.csv", _digest(q5_path)),
                     ("Q5-E001/validation_report.json",
                      _digest(results_root / "Q5-E001" / "validation_report.json"))))
    return hashlib.sha256(json.dumps(sorted(observed)).encode("utf-8")).hexdigest()


def _validated_inputs(results_root: Path) -> tuple[dict, dict, dict[str, pd.DataFrame], str]:
    q13_batch = results_root / "Q13-BATCH"
    e006_root = results_root / "Q13-E006"
    q13_report = _read(q13_batch / "validation_report.json")
    q13_status = _read(q13_batch / "batch_status.json")
    e006_report = _read(e006_root / "validation_report.json")
    e006_status = _read(e006_root / "Q8_RAW_CE_MATCHED" / "status.json")
    if (q13_report.get("status") != "passed"
            or q13_report.get("checkpoint_replays") != 837
            or q13_report.get("new_deep_fits") != 837
            or q13_report.get("target_fit_or_selection") is not False
            or q13_status.get("status") != "complete_validated"
            or q13_status.get("completed_jobs") != 13
            or e006_report.get("status") != "passed"
            or e006_report.get("experiment_id") != "Q13-E006"
            or e006_report.get("condition") != "Q8_RAW_CE_MATCHED"
            or e006_report.get("checkpoint_replays") != 27
            or e006_report.get("target_fit_or_selection") is not False
            or e006_status.get("status") != "complete"
            or e006_status.get("experiment_id") != "Q13-E006"
            or e006_status.get("condition") != "Q8_RAW_CE_MATCHED"
            or e006_status.get("completed_final_fits") != 27):
        raise RuntimeError("Q13 837 and E006 27 full scientific passes required")
    matrix = _read(Q13_MATRIX)
    amendment = _read(E006_MATRIX)
    if (matrix.get("total_new_deep_fits") != 837
            or matrix.get("final_seeds") != list(SEEDS)
            or amendment.get("new_final_fits") != 27
            or amendment.get("final_seeds") != list(SEEDS)
            or amendment.get("target_fits") != 0):
        raise AssertionError("Frozen Q13/E006 fit matrices changed")
    analysis = q13_batch / "analysis"
    tables = {name: pd.read_csv(analysis / f"{name}.csv") for name in (
        "fit_level", "subject_source_count", "subject_source_session",
        "subject_selection")}
    fits = tables["fit_level"]
    _unique(fits, ["target", "seed", "condition", "subset_id"], 837, "Q13 fit_level")
    if (set(fits.target) != set(SUBJECTS) or set(fits.seed) != set(SEEDS)
            or not fits.balanced_accuracy.between(0, 1).all()):
        raise AssertionError("Q13 fit-level subjects, seeds or BA changed")
    source = fits[fits.condition.str.contains("_SRC")].copy()
    source["method"] = np.where(source.condition.str.startswith("Q8"),
                                METHODS[0], METHODS[1])
    anchors = fits[fits.condition.isin(("Q8_FIXED20", "Q9_SHARED_FIXED20"))].copy()
    anchors["method"] = np.where(anchors.condition.eq("Q8_FIXED20"),
                                 METHODS[0], METHODS[1])
    reconstructed_count = pd.concat((source, anchors)).groupby(
        ["target", "method", "source_count"], as_index=False).balanced_accuracy.mean()
    count = tables["subject_source_count"]
    _unique(count, ["target", "method", "source_count"], 72, "Q13 source-count")
    _equal_mean(count, reconstructed_count,
                ["target", "method", "source_count"], "Q13 source-count")
    if (set(count.target) != set(SUBJECTS) or set(count.method) != set(METHODS)
            or set(count.source_count) != {2, 4, 6, 8}):
        raise AssertionError("Q13 source-count coverage changed")
    reconstructed_session = fits[fits.condition.str.contains("_SOURCE_SESSION_")].copy()
    reconstructed_session["method"] = np.where(
        reconstructed_session.condition.str.startswith("Q8"), METHODS[0], METHODS[1])
    reconstructed_session = reconstructed_session.groupby(
        ["target", "method", "source_session"], as_index=False).balanced_accuracy.mean()
    session = tables["subject_source_session"]
    _unique(session, ["target", "method", "source_session"], 36, "Q13 source-session")
    _equal_mean(session, reconstructed_session,
                ["target", "method", "source_session"], "Q13 source-session")
    if set(session.source_session) != {"0train", "1test"}:
        raise AssertionError("Q13 source-session levels changed")
    selection = tables["subject_selection"]
    _unique(selection, ["target", "condition"], 36, "Q13 selection")
    expected_conditions = {"Q8_FIXED20", "Q8_RAW_CE_REUSE_Q5",
                           "Q9_SHARED_FIXED20", "Q9_SHARED_RAW_CE"}
    if set(selection.condition) != expected_conditions:
        raise AssertionError("Q13 selection conditions changed")
    original_fit_input_digest = _check_original_fit_inputs(results_root, fits, selection)
    reconstructed_selection = fits[fits.condition.isin(expected_conditions - {
        "Q8_RAW_CE_REUSE_Q5"})].groupby(
        ["target", "condition"], as_index=False).balanced_accuracy.mean()
    selected = selection[selection.condition.ne("Q8_RAW_CE_REUSE_Q5")]
    _equal_mean(selected, reconstructed_selection,
                ["target", "condition"], "Q13 nonhistorical selection")
    return q13_report, e006_report, tables, original_fit_input_digest


def _primary_metrics(path: Path, label: str) -> pd.DataFrame:
    rows = pd.read_csv(path)
    if not {"stratum", "subject", "seed", "balanced_accuracy"}.issubset(rows):
        raise AssertionError(f"{label} missing primary metric fields")
    primary = rows[rows.stratum.eq("all")].copy()
    _unique(primary, ["subject", "seed"], 27, label)
    if (set(primary.subject) != set(SUBJECTS) or set(primary.seed) != set(SEEDS)
            or not primary.balanced_accuracy.between(0, 1).all()):
        raise AssertionError(f"{label} subject/seed/BA differs")
    return primary


def _matched_duration(results_root: Path, count: pd.DataFrame,
                      selection: pd.DataFrame) -> pd.DataFrame:
    e006 = results_root / "Q13-E006" / "Q8_RAW_CE_MATCHED"
    original = results_root / "Q13-E001" / "Q8_FIXED20"
    amended = _primary_metrics(e006 / "per_subject_metrics.csv", "E006 metrics")
    fixed = _primary_metrics(original / "per_subject_metrics.csv", "Q13 fixed20 metrics")
    predictions = pd.read_csv(e006 / "predictions.csv")
    _unique(predictions, ["subject", "seed", "sample_id"], 27 * 576, "E006 predictions")
    if (set(predictions.subject) != set(SUBJECTS)
            or set(predictions.seed) != set(SEEDS)
            or not predictions.y_true.between(1, 4).all()
            or not predictions.y_pred.between(1, 4).all()):
        raise AssertionError("E006 predictions have wrong subjects/seeds/classes")
    probabilities = predictions[[f"p_class_{c}" for c in (1, 2, 3, 4)]].to_numpy(float)
    if (not np.isfinite(probabilities).all()
            or (probabilities < -1e-6).any() or (probabilities > 1 + 1e-6).any()
            or not np.allclose(probabilities.sum(axis=1), 1, rtol=0, atol=1e-5)
            or not np.array_equal(probabilities.argmax(axis=1) + 1,
                                  predictions.y_pred.to_numpy(int))):
        raise AssertionError("E006 predictions disagree with saved probabilities")
    class_counts = predictions.groupby(["subject", "seed", "y_true"]).size()
    if (len(class_counts) != 27 * 4 or not class_counts.eq(144).all()):
        raise AssertionError("E006 target class coverage differs from frozen four-class task")
    recomputed = predictions.groupby(["subject", "seed"]).apply(
        lambda group: balanced_accuracy_score(group.y_true, group.y_pred),
        include_groups=False).rename("recomputed_ba").reset_index()
    checked = amended.merge(recomputed, on=["subject", "seed"], validate="one_to_one")
    if (len(checked) != 27
            or not np.allclose(checked.balanced_accuracy, checked.recomputed_ba,
                               rtol=0, atol=1e-12)
            or not predictions.groupby(["subject", "seed"]).size().eq(576).all()):
        raise AssertionError("E006 metric/trial coverage differs")
    paired = amended[["subject", "seed", "balanced_accuracy"]].merge(
        fixed[["subject", "seed", "balanced_accuracy"]],
        on=["subject", "seed"], suffixes=("_e006", "_fixed20"),
        validate="one_to_one")
    if len(paired) != 27:
        raise AssertionError("E006/fixed20 paired seeds missing")
    fixed_means = paired.groupby("subject").balanced_accuracy_fixed20.mean()
    q13_means = count[(count.method == "Q8_BROAD") &
                      (count.source_count == 8)].set_index("target").balanced_accuracy
    selection_means = selection[selection.condition.eq("Q8_FIXED20")].set_index(
        "target").balanced_accuracy
    if (not np.allclose(fixed_means.loc[list(SUBJECTS)],
                        q13_means.loc[list(SUBJECTS)], rtol=0, atol=1e-12)
            or not np.allclose(fixed_means.loc[list(SUBJECTS)],
                               selection_means.loc[list(SUBJECTS)], rtol=0, atol=1e-12)):
        raise AssertionError("Q13 fixed20 reference disagrees across validated tables")
    paired["paired_ba_difference"] = (paired.balanced_accuracy_e006 -
                                      paired.balanced_accuracy_fixed20)
    return paired


def analyze(results_root: Path, output_dir: Path | None = None) -> dict:
    results_root = results_root.resolve()
    q13_report, e006_report, tables, original_fit_input_digest = _validated_inputs(results_root)
    count = tables["subject_source_count"]
    session = tables["subject_source_session"]
    selection = tables["subject_selection"]
    matched = _matched_duration(results_root, count, selection)
    count_index = count.set_index(["target", "method", "source_count"]).balanced_accuracy
    session_index = session.set_index(["target", "method", "source_session"]).balanced_accuracy
    selection_index = selection.set_index(["target", "condition"]).balanced_accuracy
    matched_subject = matched.groupby("subject").paired_ba_difference.mean()
    definitions: dict[str, tuple[str, np.ndarray]] = {}
    for method in METHODS:
        for k in (2, 4, 6):
            name = f"{method}_k{k}_minus_k8"
            definitions[name] = ("source_count", np.asarray([
                count_index.loc[(s, method, k)] - count_index.loc[(s, method, 8)]
                for s in SUBJECTS]))
        name = f"{method}_1test_minus_0train"
        definitions[name] = ("source_session", np.asarray([
            session_index.loc[(s, method, "1test")] -
            session_index.loc[(s, method, "0train")] for s in SUBJECTS]))
    definitions["Q8_FIXED20_minus_Q8_RAW_CE_REUSE_Q5"] = ("selection", np.asarray([
        selection_index.loc[(s, "Q8_FIXED20")] -
        selection_index.loc[(s, "Q8_RAW_CE_REUSE_Q5")] for s in SUBJECTS]))
    definitions["Q9_SHARED_FIXED20_minus_Q9_SHARED_RAW_CE"] = ("selection", np.asarray([
        selection_index.loc[(s, "Q9_SHARED_FIXED20")] -
        selection_index.loc[(s, "Q9_SHARED_RAW_CE")] for s in SUBJECTS]))
    matrix = _read(Q13_MATRIX)
    families = matrix["predeclared_contrast_families"]
    if (set(definitions) != {name for names in families.values() for name in names}
            or any(definitions[name][0] != family
                   for family, names in families.items() for name in names)):
        raise AssertionError("Q13 contrasts differ from frozen families")
    families = {**families,
                "E006_matched_runtime_amendment": ["Q8_E006_RAW_CE_minus_Q8_FIXED20"]}
    definitions["Q8_E006_RAW_CE_minus_Q8_FIXED20"] = (
        "E006_matched_runtime_amendment",
        matched_subject.loc[list(SUBJECTS)].to_numpy(float))
    draws = np.random.default_rng(BOOTSTRAP_SEED).integers(
        0, 9, size=(BOOTSTRAP_DRAWS, 9))
    summaries, subject_rows = [], []
    for family, names in families.items():
        rows = []
        for name in names:
            deltas = definitions[name][1]
            row = {"family": family, "contrast": name,
                   "interpretation": ("historical_cross_run_descriptive"
                                      if name == "Q8_FIXED20_minus_Q8_RAW_CE_REUSE_Q5"
                                      else "exploratory_matched_runtime_schedule"
                                      if family == "E006_matched_runtime_amendment"
                                      else "exploratory_predeclared_Q13"),
                   **paired_summary(deltas, draws)}
            rows.append(row)
            subject_rows.extend({"family": family, "contrast": name,
                                 "target_subject": subject,
                                 "paired_ba_difference": float(delta)}
                                for subject, delta in zip(SUBJECTS, deltas, strict=True))
        corrected = holm({row["contrast"]: row["exact_sign_flip_p_exploratory"]
                          for row in rows})
        for row in rows:
            row["holm_within_family_p_exploratory"] = corrected[row["contrast"]]
        summaries.extend(rows)
    fits = tables["fit_level"]
    subset = fits[fits.condition.str.contains("_SRC")].copy()
    subset["method"] = np.where(subset.condition.str.startswith("Q8"), METHODS[0], METHODS[1])
    subset_means = subset.groupby(
        ["target", "method", "source_count", "subset_id"], as_index=False).agg(
            mean_seed_ba=("balanced_accuracy", "mean"),
            seed_sd=("balanced_accuracy", "std"))
    _unique(subset_means, ["target", "method", "source_count", "subset_id"],
            9 * 2 * 3 * 4, "source subset spread")
    spread = subset_means.groupby(
        ["target", "method", "source_count"], as_index=False).agg(
            min_subset_mean_ba=("mean_seed_ba", "min"),
            max_subset_mean_ba=("mean_seed_ba", "max"),
            sd_subset_mean_ba=("mean_seed_ba", "std"))
    spread["range_subset_mean_ba"] = (spread.max_subset_mean_ba -
                                      spread.min_subset_mean_ba)
    if output_dir is None:
        output_dir = results_root / "Q13-E006" / "postrun_statistics"
    receipt = {
        "status": "post_validation_exploratory_statistics_complete",
        "not_a_new_scientific_validation": True,
        "q13_checkpoint_replays": q13_report["checkpoint_replays"],
        "e006_checkpoint_replays": e006_report["checkpoint_replays"],
        "q13_original_fit_and_q5_input_digest": original_fit_input_digest,
        "inference_unit": "nine held-out subjects; seeds and source subsets averaged within subject",
        "bootstrap_seed": BOOTSTRAP_SEED, "bootstrap_draws": BOOTSTRAP_DRAWS,
        "contrast_count": len(summaries), "subject_rows": len(subject_rows),
        "limitations": [
            "BNCI target outcomes were previously examined: all Q13/E006 contrasts exploratory.",
            "LOSO training sets overlap: exact sign-flip is sensitivity, not exact causal inference.",
            "Natural optimizer updates and training trial counts increase with source count.",
            "Q5 historical reuse can differ in runtime from Q13; its contrast remains descriptive.",
            "E006 tests a frozen historical source-only epoch schedule, not reselection under the new runtime.",
            "Nine subjects give fragile confidence intervals; negative and class-collapse results stay visible.",
        ],
        "input_sha256": {
            "q13_validation": _digest(results_root / "Q13-BATCH" / "validation_report.json"),
            "q13_batch_status": _digest(results_root / "Q13-BATCH" / "batch_status.json"),
            "e006_validation": _digest(results_root / "Q13-E006" / "validation_report.json"),
            "e006_fit_status": _digest(results_root / "Q13-E006" /
                                        "Q8_RAW_CE_MATCHED" / "status.json"),
            "q13_matrix": _digest(Q13_MATRIX), "e006_matrix": _digest(E006_MATRIX),
            **{name: _digest(results_root / "Q13-BATCH" / "analysis" / f"{name}.csv")
               for name in tables},
            "e006_predictions": _digest(results_root / "Q13-E006" /
                                        "Q8_RAW_CE_MATCHED" / "predictions.csv"),
            "e006_metrics": _digest(results_root / "Q13-E006" /
                                    "Q8_RAW_CE_MATCHED" / "per_subject_metrics.csv"),
            "q13_fixed20_metrics": _digest(results_root / "Q13-E001" /
                                            "Q8_FIXED20" / "per_subject_metrics.csv"),
        },
        "outputs": ["paired_contrasts.csv", "subject_paired_differences.csv",
                    "source_count_trajectories.csv", "source_subset_means.csv",
                    "source_identity_spread.csv", "source_session_subjects.csv",
                    "e006_seed_pairs.csv"],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in (
        ("paired_contrasts.csv", pd.DataFrame(summaries)),
        ("subject_paired_differences.csv", pd.DataFrame(subject_rows)),
        ("source_count_trajectories.csv", count.sort_values(
            ["target", "method", "source_count"])),
        ("source_subset_means.csv", subset_means),
        ("source_identity_spread.csv", spread),
        ("source_session_subjects.csv", session.sort_values(
            ["target", "method", "source_session"])),
        ("e006_seed_pairs.csv", matched),
    ):
        temporary = output_dir / (name + ".tmp")
        frame.to_csv(temporary, index=False)
        os.replace(temporary, output_dir / name)
    report_path = output_dir / "analysis_receipt.json"
    temporary = report_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    os.replace(temporary, report_path)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, default=ROOT / "results")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.results_root, args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
