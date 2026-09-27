"""Synthetic n=9, 837-fit + 27-fit Q13/E006 statistical-analysis tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts import q13_e006_postrun_stats as stats


def _fixture(results: Path) -> None:
    batch = results / "Q13-BATCH"
    analysis = batch / "analysis"
    analysis.mkdir(parents=True)
    (batch / "validation_report.json").write_text(json.dumps({
        "status": "passed", "checkpoint_replays": 837, "new_deep_fits": 837,
        "target_fit_or_selection": False}), encoding="utf-8")
    (batch / "batch_status.json").write_text(
        json.dumps({"status": "complete_validated", "completed_jobs": 13}), encoding="utf-8")
    e006 = results / "Q13-E006"
    e006.mkdir()
    (e006 / "validation_report.json").write_text(json.dumps({
        "status": "passed", "checkpoint_replays": 27,
        "experiment_id": "Q13-E006", "condition": "Q8_RAW_CE_MATCHED",
        "target_fit_or_selection": False}), encoding="utf-8")
    e006_condition = e006 / "Q8_RAW_CE_MATCHED"
    e006_condition.mkdir()
    (e006_condition / "status.json").write_text(json.dumps({
        "status": "complete", "completed_final_fits": 27,
        "experiment_id": "Q13-E006", "condition": "Q8_RAW_CE_MATCHED"}), encoding="utf-8")
    conditions = {
        "Q8_FIXED20": ("Q8_BROAD", 8, ["all"], "both", 0.0),
        "Q9_SHARED_RAW_CE": ("Q9_MU_BETA_SHARED", 8, ["all"], "both", -0.015),
        "Q9_SHARED_FIXED20": ("Q9_MU_BETA_SHARED", 8, ["all"], "both", 0.0),
    }
    for prefix, method in (("Q8", "Q8_BROAD"),
                           ("Q9_SHARED", "Q9_MU_BETA_SHARED")):
        for count, offset in ((2, -0.1), (4, -0.06), (6, -0.03)):
            conditions[f"{prefix}_SRC{count}"] = (
                method, count, [f"k{count}_start{x}" for x in (0, 2, 4, 6)],
                "both", offset)
        conditions[f"{prefix}_SOURCE_SESSION_T"] = (
            method, 8, ["all"], "0train", -0.04)
        conditions[f"{prefix}_SOURCE_SESSION_E"] = (
            method, 8, ["all"], "1test", 0.01)
    rows = []
    for condition, (method, count, subsets, source_session, offset) in conditions.items():
        for target in range(1, 10):
            for subset in subsets:
                subset_offset = 0.001 * (int(subset.rsplit("start", 1)[1]) if
                                         "start" in subset else 0)
                for seed_index, seed in enumerate(stats.SEEDS):
                    baseline = 0.5 + target * 0.01 + (0.02 if method == "Q9_MU_BETA_SHARED" else 0)
                    rows.append({
                        "target": target, "seed": seed, "condition": condition,
                        "subset_id": subset, "source_count": count,
                        "source_session": source_session,
                        "balanced_accuracy": baseline + offset + subset_offset +
                                             (seed_index - 1) * 0.002,
                    })
    fit = pd.DataFrame(rows)
    assert len(fit) == 837
    fit.to_csv(analysis / "fit_level.csv", index=False)
    condition_to_experiment = {
        condition: experiment
        for experiment, values in stats.Q13_CONDITIONS.items()
        for condition in values
    }
    for row in fit.itertuples(index=False):
        directory = (results / condition_to_experiment[row.condition] / row.condition /
                     "final" / f"loso_s{row.target}" / row.subset_id /
                     f"seed_{row.seed}")
        directory.mkdir(parents=True)
        metric = directory / "metrics.csv"
        pd.DataFrame([{"stratum": "all", "balanced_accuracy": row.balanced_accuracy}]).to_csv(
            metric, index=False)
        prediction = directory / "predictions.csv"
        prediction.write_text("synthetic_test_only\n", encoding="utf-8")
        (directory / "status.json").write_text(json.dumps({
            "status": "complete",
            "sha256_metrics.csv": hashlib.sha256(metric.read_bytes()).hexdigest(),
            "sha256_predictions.csv": hashlib.sha256(prediction.read_bytes()).hexdigest(),
        }), encoding="utf-8")
    source = fit[fit.condition.str.contains("_SRC")].copy()
    source["method"] = np.where(source.condition.str.startswith("Q8"),
                                "Q8_BROAD", "Q9_MU_BETA_SHARED")
    anchor = fit[fit.condition.isin(("Q8_FIXED20", "Q9_SHARED_FIXED20"))].copy()
    anchor["method"] = np.where(anchor.condition.eq("Q8_FIXED20"),
                                "Q8_BROAD", "Q9_MU_BETA_SHARED")
    count = pd.concat((source, anchor)).groupby(
        ["target", "method", "source_count"], as_index=False).agg(
            balanced_accuracy=("balanced_accuracy", "mean"),
            n_repeated_fits=("balanced_accuracy", "size"))
    count.to_csv(analysis / "subject_source_count.csv", index=False)
    session = fit[fit.condition.str.contains("_SOURCE_SESSION_")].copy()
    session["method"] = np.where(session.condition.str.startswith("Q8"),
                                 "Q8_BROAD", "Q9_MU_BETA_SHARED")
    session = session.groupby(
        ["target", "method", "source_session"], as_index=False).agg(
            balanced_accuracy=("balanced_accuracy", "mean"))
    session.to_csv(analysis / "subject_source_session.csv", index=False)
    selected = fit[fit.condition.isin(("Q8_FIXED20", "Q9_SHARED_RAW_CE",
                                       "Q9_SHARED_FIXED20"))].groupby(
        ["target", "condition"], as_index=False).agg(
            balanced_accuracy=("balanced_accuracy", "mean"))
    historical = selected[selected.condition.eq("Q8_FIXED20")].copy()
    historical["condition"] = "Q8_RAW_CE_REUSE_Q5"
    historical["balanced_accuracy"] -= 0.02
    pd.concat((selected, historical), ignore_index=True).to_csv(
        analysis / "subject_selection.csv", index=False)
    primary = fit[fit.condition.eq("Q8_FIXED20")].rename(
        columns={"target": "subject"})
    primary["stratum"] = "all"
    fixed_root = results / "Q13-E001" / "Q8_FIXED20"
    fixed_root.mkdir(parents=True, exist_ok=True)
    primary[["subject", "seed", "balanced_accuracy", "stratum"]].to_csv(
        fixed_root / "per_subject_metrics.csv", index=False)
    q5_root = results / "Q5-E001"
    q5_root.mkdir()
    q5 = primary[["subject", "seed", "balanced_accuracy", "stratum"]].copy()
    q5["balanced_accuracy"] -= 0.02
    q5["model"] = "EEGNet"
    q5.to_csv(q5_root / "per_subject_metrics.csv", index=False)
    (q5_root / "validation_report.json").write_text(
        json.dumps({"status": "passed"}), encoding="utf-8")
    e006_metrics = primary[["subject", "seed", "stratum"]].copy()
    e006_metrics["balanced_accuracy"] = 1.0
    e006_metrics.to_csv(e006_condition / "per_subject_metrics.csv", index=False)
    predictions = []
    labels = np.repeat(np.arange(1, 5), 144)
    for target in stats.SUBJECTS:
        for seed in stats.SEEDS:
            part = pd.DataFrame({
                "subject": target, "seed": seed,
                "sample_id": [f"S{target}_trial_{trial}" for trial in range(576)],
                "y_true": labels, "y_pred": labels,
            })
            for category in (1, 2, 3, 4):
                part[f"p_class_{category}"] = (labels == category).astype(float)
            predictions.append(part)
    pd.concat(predictions, ignore_index=True).to_csv(
        e006_condition / "predictions.csv", index=False)


def test_exact_sign_flip_holm_and_subject_bootstrap() -> None:
    values = np.repeat(0.1, 9)
    assert stats.exact_sign_flip_p(values) == pytest.approx(2 / 512)
    assert stats.exact_sign_flip_p(np.zeros(9)) == 1
    draws = np.random.default_rng(17).integers(0, 9, size=(100, 9))
    report = stats.paired_summary(values, draws)
    assert report["n_subjects"] == 9
    assert report["subject_bootstrap_95ci_low"] == pytest.approx(0.1)
    assert report["subject_bootstrap_95ci_high"] == pytest.approx(0.1)
    adjusted = stats.holm({"a": 0.01, "b": 0.02, "c": 0.5})
    assert adjusted["a"] == pytest.approx(0.03)
    assert adjusted["b"] == pytest.approx(0.04)
    assert adjusted["c"] == pytest.approx(0.5)


def test_full_synthetic_analysis_uses_nine_subjects_not_837_fits(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _fixture(results)
    receipt = stats.analyze(results)
    assert receipt["status"] == "post_validation_exploratory_statistics_complete"
    assert receipt["q13_checkpoint_replays"] == 837
    assert receipt["e006_checkpoint_replays"] == 27
    assert receipt["contrast_count"] == 11
    out = results / "Q13-E006" / "postrun_statistics"
    effects = pd.read_csv(out / "paired_contrasts.csv")
    assert len(effects) == 11
    assert effects.n_subjects.eq(9).all()
    details = pd.read_csv(out / "subject_paired_differences.csv")
    assert len(details) == 99
    assert details.groupby("contrast").target_subject.nunique().eq(9).all()
    assert details.paired_ba_difference.lt(0).any()  # negative outcomes remain present
    assert len(pd.read_csv(out / "source_count_trajectories.csv")) == 72
    assert len(pd.read_csv(out / "source_subset_means.csv")) == 216
    assert len(pd.read_csv(out / "source_identity_spread.csv")) == 54
    assert len(pd.read_csv(out / "source_session_subjects.csv")) == 36
    matched = effects[effects.family.eq("E006_matched_runtime_amendment")].iloc[0]
    assert matched["mean_paired_ba_difference"] > 0
    assert matched["holm_within_family_p_exploratory"] >= matched[
        "exact_sign_flip_p_exploratory"]


def test_missing_scientific_pass_or_tampered_table_fails_before_receipt(
    tmp_path: Path,
) -> None:
    results = tmp_path / "results"
    _fixture(results)
    output = results / "Q13-E006" / "postrun_statistics"
    report = results / "Q13-E006" / "validation_report.json"
    report.write_text(json.dumps({"status": "artifact_only", "checkpoint_replays": 0,
                                  "target_fit_or_selection": False}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="full scientific passes"):
        stats.analyze(results)
    assert not output.exists()
    report.write_text(json.dumps({"status": "passed", "checkpoint_replays": 27,
                                  "experiment_id": "Q13-E006",
                                  "condition": "Q8_RAW_CE_MATCHED",
                                  "target_fit_or_selection": False}), encoding="utf-8")
    table = results / "Q13-BATCH" / "analysis" / "subject_source_count.csv"
    count = pd.read_csv(table)
    count.loc[0, "balanced_accuracy"] += 0.1
    count.to_csv(table, index=False)
    with pytest.raises(AssertionError, match="source-count differs"):
        stats.analyze(results)
    assert not output.exists()


def test_original_q13_metric_or_historical_q5_drift_is_rejected(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _fixture(results)
    metric = (results / "Q13-E001" / "Q8_FIXED20" / "final" /
              "loso_s1" / "all" / f"seed_{stats.SEEDS[0]}" / "metrics.csv")
    metric.write_text("stratum,balanced_accuracy\nall,0.99\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="receipt/hash differs"):
        stats.analyze(results)
    _fixture_reset = tmp_path / "fresh_results"
    _fixture(_fixture_reset)
    q5 = _fixture_reset / "Q5-E001" / "per_subject_metrics.csv"
    historical = pd.read_csv(q5)
    historical.loc[0, "balanced_accuracy"] += 0.1
    historical.to_csv(q5, index=False)
    with pytest.raises(AssertionError, match="historical Q5 selection differs"):
        stats.analyze(_fixture_reset)
