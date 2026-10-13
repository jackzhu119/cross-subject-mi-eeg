#!/usr/bin/env python3
"""Read-only historical artifact audit; writes solely into this redesign directory.

No raw EEG loading, sklearn model deserialization, training, checkpoint inference,
network access, or target preprocessing is performed. Historical outcomes have
already been observed; these calculations are retrospective diagnostics.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest


OUT_REL = Path("research_runs/REDESIGN_SOURCE_SELECTION_20261012")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def historical_scope(path: str) -> bool:
    return bool(re.match(r"(?:results|research_runs)/Q(?:[1-9]|1[0-6])(?:[-_/])", path)
                or re.match(r"outputs/(?:P[1-4]|Q4)[-_]", path)
                or path.startswith("configs/") or path.startswith("docs/")
                or path.startswith("research_runs/PAPER_FINAL_20261006/")
                or path.startswith("research_runs/PLOS_ONE_SUBMISSION/")
                or path.startswith("research_runs/PLOS_ONE_POSTSUBMISSION_REVIEW_20261010/evidence/"))


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def prediction_cells(df: pd.DataFrame, extra_groups=()) -> pd.DataFrame:
    truth = "y_true" if "y_true" in df else "label"
    pred = "y_pred" if "y_pred" in df else "predicted_label"
    groups = [g for g in ["subject", "model", "seed", *extra_groups] if g in df]
    if "subject" not in groups:
        raise ValueError("prediction table has no participant identity")
    results = []
    for key, cell in df.groupby(groups, dropna=False, sort=True):
        keys = key if isinstance(key, tuple) else (key,)
        labels = sorted(cell[truth].unique())
        recalls = [(cell.loc[cell[truth] == lab, pred] == lab).mean() for lab in labels]
        counts = cell[pred].value_counts(normalize=True)
        row = dict(zip(groups, keys))
        row.update(n_trials=len(cell), n_classes=len(labels), balanced_accuracy=float(np.mean(recalls)),
                   dominant_prediction_share=float(counts.max()),
                   zero_recall_classes=int(sum(r == 0 for r in recalls)))
        for lab, recall in zip(labels, recalls):
            row[f"recall_class_{lab}"] = float(recall)
        results.append(row)
    return pd.DataFrame(results)


def probability_check(df: pd.DataFrame) -> dict:
    truth = "y_true" if "y_true" in df else "label"
    pred = "y_pred" if "y_pred" in df else "predicted_label"
    probs = sorted([c for c in df if c.startswith("p_class_")], key=lambda x: int(x.rsplit("_", 1)[1]))
    if not probs and {"p_left", "p_right"}.issubset(df):
        probs = ["p_left", "p_right"]
    result = {"rows": len(df), "truth_missing": int(df[truth].isna().sum()),
              "prediction_missing": int(df[pred].isna().sum())}
    ids = [c for c in ["sample_id", "model", "seed", "condition", "subset_id", "mode", "fold_id", "training_policy"] if c in df]
    if ids:
        result["duplicate_identity_rows"] = int(df.duplicated(ids).sum())
    if probs:
        p = df[probs].to_numpy(dtype=float)
        labels = [int(x.rsplit("_", 1)[1]) for x in probs] if probs[0].startswith("p_class_") else [1, 2]
        result.update(probabilities_nonfinite=int((~np.isfinite(p)).sum()),
                      probability_max_sum_error=float(np.max(np.abs(p.sum(axis=1) - 1))),
                      probability_outside_unit_interval=int(((p < -1e-6) | (p > 1 + 1e-6)).sum()),
                      argmax_disagreements=int((np.array(labels)[p.argmax(axis=1)] != df[pred].to_numpy()).sum()))
    else:
        result["probability_validation"] = "no recognized probability columns; labels only"
    return result


def participant_metrics(df: pd.DataFrame) -> pd.DataFrame:
    cells = prediction_cells(df)
    groups = [c for c in ["subject", "model"] if c in cells]
    return cells.groupby(groups, as_index=False).agg(
        balanced_accuracy=("balanced_accuracy", "mean"),
        dominant_prediction_share=("dominant_prediction_share", "mean"),
        zero_recall_classes_mean=("zero_recall_classes", "mean"))


def paired_summary(diff: np.ndarray) -> dict:
    diff = np.asarray(diff, dtype=float)
    nonzero = diff[np.abs(diff) > 1e-12]
    if len(nonzero):
        sign_p = float(binomtest(int((nonzero > 0).sum()), len(nonzero), 0.5).pvalue)
    else:
        sign_p = 1.0
    result = dict(n_participants=len(diff), mean_difference_pp=float(diff.mean() * 100),
                  median_difference_pp=float(np.median(diff) * 100),
                  improved=int((diff > 1e-12).sum()), worsened=int((diff < -1e-12).sum()),
                  tied=int((np.abs(diff) <= 1e-12).sum()), exact_sign_test_excluding_ties_p=sign_p)
    if len(diff) <= 12:
        means = np.array([np.mean(diff * signs) for signs in itertools.product([-1, 1], repeat=len(diff))])
        result["exhaustive_sign_flip_p"] = float((np.abs(means) >= abs(diff.mean()) - 1e-12).mean())
    return result


def frozen_resampling(diff, bootstrap_seed, draws=20000, sign_seed=None):
    values = np.asarray(diff, dtype=float)
    rng = np.random.default_rng(bootstrap_seed)
    indices = rng.integers(0, len(values), size=(draws, len(values)))
    interval = np.quantile(values[indices].mean(axis=1), [.025, .975]).tolist()
    result = dict(bootstrap_draws=draws, bootstrap_seed=bootstrap_seed,
                  participant_bootstrap_percentile_95_ci_pp=[float(x * 100) for x in interval])
    if sign_seed is not None:
        rng = np.random.default_rng(sign_seed)
        signs = rng.integers(0, 2, size=(draws, len(values))) * 2 - 1
        extreme = int((np.abs((signs * values).mean(axis=1)) >= abs(values.mean()) - 1e-15).sum())
        result.update(sign_flip_draws=draws, sign_flip_seed=sign_seed,
                      sign_flip_monte_carlo_plus_one_p=(extreme + 1) / (draws + 1))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--inventory", action="store_true", help="Parse every historical tracked text/CSV in the defined scope")
    args = parser.parse_args()
    root = args.root.resolve()
    out = root / OUT_REL
    (out / "evidence").mkdir(parents=True, exist_ok=True)
    (out / "results").mkdir(parents=True, exist_ok=True)
    ledger = []
    if args.inventory:
        paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
        for rel in sorted(filter(historical_scope, filter(None, paths))):
            p = root / rel
            record = dict(path=rel, bytes=p.stat().st_size, sha256=sha(p), scope="bytes_hashed_only")
            try:
                if p.suffix == ".json":
                    val = json.loads(p.read_text())
                    record.update(scope="fully_parsed_json_structure_not_full_semantic_review", json_type=type(val).__name__)
                    if isinstance(val, dict):
                        record["top_level_keys"] = sorted(val)
                        for name in ["status", "passed", "scientific_validation_passed", "new_model_fits", "target_fits"]:
                            if name in val and isinstance(val[name], (str, bool, int, float, type(None))):
                                record[name] = val[name]
                elif p.suffix == ".csv" or p.name.endswith(".csv.gz"):
                    df = pd.read_csv(p)
                    record.update(scope="all_csv_rows_parsed_structure_checked", rows=len(df), columns=list(df))
                    if ("y_true" in df or "label" in df) and ("y_pred" in df or "predicted_label" in df):
                        record["prediction_checks"] = probability_check(df)
                elif p.suffix in {".md", ".txt", ".py", ".toml"}:
                    value = p.read_text()
                    record.update(scope="fully_decoded_text_not_full_semantic_review", characters=len(value), lines=len(value.splitlines()))
            except Exception as err:
                record.update(parse_error=type(err).__name__, parse_error_message=str(err)[:200])
            ledger.append(record)
        (out / "evidence/historical_read_scope_ledger.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")

    primary_paths = {
        "q5_mean_loss": "results/Q5-E001/predictions.csv",
        "q8_mean_rank": "research_runs/Q8-E001/results/predictions.csv",
        "fixed20": "results/Q13-E001/Q8_FIXED20/predictions.csv",
        "matched_runtime_historical_loss_schedule": "results/Q13-E006/Q8_RAW_CE_MATCHED/predictions.csv",
        "q14_physionet": "results/Q14-E002R2/external/predictions.csv",
        "q15_cho": "results/Q15-EXTERNAL/Q15-E006/predictions.csv",
        "q15_lee": "results/Q15-EXTERNAL/Q15-E007/predictions.csv",
    }
    dfs = {}; participant_tables = {}; summary = {}; all_cells = []
    for name, rel in primary_paths.items():
        df = pd.read_csv(root / rel)
        dfs[name] = df
        cells = prediction_cells(df)
        cells.insert(0, "condition", name)
        all_cells.append(cells)
        person = participant_metrics(df)
        participant_tables[name] = person
        if "model" in person:
            summary[name] = {str(model): dict(n_participants=len(cell), mean_balanced_accuracy=float(cell.balanced_accuracy.mean()),
                                                participant_sample_sd=float(cell.balanced_accuracy.std(ddof=1)))
                             for model, cell in person.groupby("model")}
        else:
            summary[name] = dict(n_participants=len(person), mean_balanced_accuracy=float(person.balanced_accuracy.mean()),
                                 participant_sample_sd=float(person.balanced_accuracy.std(ddof=1)))
        summary[name]["artifact_checks"] = probability_check(df)
        summary[name]["input_path"] = rel
        summary[name]["input_sha256"] = sha(root / rel)
        person.insert(0, "condition", name)
    pd.concat(all_cells).to_csv(out / "results/historical_participant_seed_cells.csv", index=False, float_format="%.12g")
    pd.concat(participant_tables.values()).to_csv(out / "results/historical_participant_metrics.csv", index=False, float_format="%.12g")

    internal = pd.DataFrame({name: table.set_index("subject").balanced_accuracy for name, table in participant_tables.items() if not "model" in table})
    internal.index.name = "subject"
    internal["rank_minus_loss_pp"] = (internal.q8_mean_rank - internal.q5_mean_loss) * 100
    internal["fixed_minus_matched_loss_pp"] = (internal.fixed20 - internal.matched_runtime_historical_loss_schedule) * 100
    internal["fixed_minus_historical_rank_pp"] = (internal.fixed20 - internal.q8_mean_rank) * 100
    internal.to_csv(out / "results/historical_internal_paired.csv", float_format="%.12g")
    rank_diff = internal.q8_mean_rank.to_numpy() - internal.q5_mean_loss.to_numpy()
    summary["q8_minus_q5"] = paired_summary(rank_diff)
    summary["q8_minus_q5"].update(frozen_resampling(rank_diff, 20260923))
    summary["q8_minus_q5"]["s3_s8_fraction_of_signed_aggregate_gain"] = float(internal.loc[[3, 8], "rank_minus_loss_pp"].sum() / internal.rank_minus_loss_pp.sum())
    summary["fixed_minus_matched_loss"] = paired_summary(internal.fixed20.to_numpy() - internal.matched_runtime_historical_loss_schedule.to_numpy())
    summary["fixed_minus_matched_loss"].update(frozen_resampling(internal.fixed20.to_numpy() - internal.matched_runtime_historical_loss_schedule.to_numpy(), 20260926, draws=10000))
    summary["fixed_minus_historical_rank"] = paired_summary(internal.fixed20.to_numpy() - internal.q8_mean_rank.to_numpy())
    summary["fixed_minus_historical_rank"]["interpretation"] = "cross_run_retrospective_development_description_not_matched_runtime_algorithm_confirmation"

    for key in ["q14_physionet", "q15_cho", "q15_lee"]:
        pt = participant_tables[key].pivot(index="subject", columns="model", values="balanced_accuracy")
        summary[key]["shared_minus_broad"] = paired_summary((pt.MU_BETA_SHARED - pt.BROAD_EEGNET).to_numpy())
        summary[key]["shared_minus_broad"]["role"] = "new_retrospective_saved_count_diagnostic_with_1e-12_tie_tolerance_not_replacement_of_frozen_primary_test"
        if key.startswith("q15"):
            computed = frozen_resampling((pt.MU_BETA_SHARED - pt.BROAD_EEGNET).to_numpy(), 20260924, sign_seed=20261003)
            frozen = json.loads((root / primary_paths[key]).with_name("statistics.json").read_text())["primary_contrast"]
            assert np.allclose(computed["participant_bootstrap_percentile_95_ci_pp"], np.array(frozen["paired_person_bootstrap_percentile_95_ci"]) * 100, atol=1e-10)
            assert computed["sign_flip_monte_carlo_plus_one_p"] == frozen["two_sided_person_sign_flip_p_value"]
            summary[key]["frozen_primary_resampling_replayed"] = computed
    phys_frozen_path = root / "results/Q14-E002R2V1/external/subject_primary_contrast.csv"
    phys_frozen = pd.read_csv(phys_frozen_path).primary_difference_shared_minus_broad.to_numpy()
    phys_nz = phys_frozen[phys_frozen != 0]
    summary["q14_physionet"]["frozen_primary_exact_zero_policy_replayed"] = dict(
        input_path=str(phys_frozen_path.relative_to(root)), input_sha256=sha(phys_frozen_path),
        positive=int((phys_frozen > 0).sum()), negative=int((phys_frozen < 0).sum()), exact_ties=int((phys_frozen == 0).sum()),
        exact_sign_test_p=float(binomtest(int((phys_nz > 0).sum()), len(phys_nz), .5).pvalue),
        floating_point_tie_note="S010 stored difference -1.1102230246251563e-16 is negative under original exact-zero rule; count-based tolerance sensitivity instead treats it as tied; frozen output is retained.",
        **frozen_resampling(phys_frozen, 20260924))
    raw_p = {key: summary[key]["frozen_primary_resampling_replayed"]["sign_flip_monte_carlo_plus_one_p"] for key in ["q15_cho", "q15_lee"]}
    ordered_p = sorted(raw_p, key=raw_p.get)
    adjusted = {}; running = 0.
    for j, key in enumerate(ordered_p):
        running = max(running, min(1., raw_p[key] * (2 - j)))
        adjusted[key] = running
    summary["q15_two_cohort_holm_replayed"] = adjusted
    for key in ["q15_cho", "q15_lee"]:
        df = dfs[key]
        csp = df.loc[df.model == "CSP4_LDA"]
        csppt = participant_tables[key].query("model == 'CSP4_LDA'")
        pooled_left_recall = (csp.loc[csp.label == 1, "predicted_label"] == 1).mean()
        pooled_right_recall = (csp.loc[csp.label == 2, "predicted_label"] == 2).mean()
        summary[key]["archived_csp_diagnostics"] = {
            "n_trials": len(csp), "trial_pooled_left_prediction_share": float((csp.predicted_label == 1).mean()),
            "participant_mean_left_prediction_share": float(csp.groupby("subject").predicted_label.apply(lambda x: (x == 1).mean()).mean()),
            "trial_pooled_median_p_left": float(csp.p_left.median()),
            "trial_pooled_probability_045_055_share": float(csp.p_left.between(.45, .55).mean()),
            "participant_mean_ba": float(csppt.balanced_accuracy.mean()),
            "trial_pooled_ba": float((pooled_left_recall + pooled_right_recall) / 2),
            "arithmetic_binary_label_complement_participant_mean_ba": float(1 - csppt.balanced_accuracy.mean()),
            "no_target_centering_or_new_inference": True,
        }

    q5_curves = pd.read_csv(root / "results/Q5-E001/learning_curves.csv")
    inner = q5_curves[q5_curves.stage == "inner"]
    schedule = []
    expected_loss = pd.read_csv(root / "results/Q5-E001/selection.csv").set_index("fold").selected_epochs
    expected_rank = pd.read_csv(root / "research_runs/Q8-E001/results/selection.csv").set_index("fold").selected_epochs
    for fold, cell in inner.groupby("fold"):
        curves = cell.pivot(index="epoch", columns="inner_fold", values="val_ce").sort_index()
        assert curves.shape == (40, 4) and not curves.isna().any().any()
        loss_epoch = int(curves.mean(axis=1).idxmin())
        rank_epoch = int(curves.rank(axis=0, method="average").mean(axis=1).idxmin())
        assert loss_epoch == expected_loss[fold] and rank_epoch == expected_rank[fold]
        schedule.append(dict(fold=fold, loss_epoch=loss_epoch, rank_epoch=rank_epoch, source_curve_folds=4, source_curve_epochs=40))
    pd.DataFrame(schedule).to_csv(out / "results/historical_source_schedule_replay.csv", index=False)
    summary["selection_replay"] = dict(n_outer_folds=9, source_curve_rows=len(inner), all_loss_and_rank_epochs_match=True,
                                         original_source_curve_sha256=sha(root / "results/Q5-E001/learning_curves.csv"))

    q16 = pd.read_csv(root / "research_runs/Q16-P001-BNCI-20261006/subject_hand_laterality.csv")
    recomputed = .5 * ((q16.C3_right_mean_db - q16.C4_right_mean_db) + (q16.C4_left_mean_db - q16.C3_left_mean_db))
    assert np.allclose(recomputed, q16.signed_laterality_db, atol=1e-12)
    summary["q16_saved_descriptor_reaggregation"] = {band: dict(n_participants=cell.subject.nunique(), mean_signed_laterality_db=float(cell.signed_laterality_db.mean())) for band, cell in q16.groupby("band")}
    power_path = root / "research_runs/Q16-P001-BNCI-20261006/trial_power.csv.gz"
    powers = pd.read_csv(power_path)
    observed_db = 10 * np.log10(powers.task_power_native_numeric_squared / powers.baseline_power_native_numeric_squared)
    max_db_diff = float(np.max(np.abs(observed_db - powers.logratio_db)))
    assert max_db_diff < 1e-10
    physperf = pd.read_csv(root / "research_runs/Q16-P001-BNCI-20261006/subject_physiology_performance.csv")
    correlations = []
    for (model, band), cell in physperf.groupby(["model", "band"]):
        rho = float(np.corrcoef(cell.signed_laterality_db.rank(method="average"), cell.balanced_accuracy_mean.rank(method="average"))[0, 1])
        correlations.append(dict(model=model, band=band, n_participants=cell.subject.nunique(), spearman_rho=rho, p_value_computed=False))
    frozen_corr = pd.read_csv(root / "research_runs/Q16-P001-BNCI-20261006/descriptive_associations.csv")
    for row in correlations:
        original = frozen_corr.query("model == @row['model'] and band == @row['band']")
        assert len(original) == 1 and np.isclose(row["spearman_rho"], original.spearman_rho.iloc[0], atol=1e-12)
    pd.DataFrame(correlations).to_csv(out / "results/historical_q16_association_replay.csv", index=False, float_format="%.12g")
    summary["q16_saved_power_arithmetic"] = dict(rows=len(powers), max_abs_logratio_db_difference=max_db_diff,
                                                source_sha256=sha(power_path), raw_spectral_replay_performed=False,
                                                all_six_saved_rank_correlations_match=True)
    hash_bindings = {}
    for rel in ["results/Q15-E005/source_validation.json", "results/Q15-EXTERNAL/validation_report.json"]:
        receipt = json.loads((root / rel).read_text())
        checked = []
        for path, expected in receipt["artifact_sha256"].items():
            actual = sha(root / path)
            assert actual == expected, path
            checked.append(dict(path=path, sha256=actual))
        hash_bindings[rel] = dict(receipt_sha256=sha(root / rel), matching_artifact_count=len(checked), mismatches=0, artifacts=checked)
    summary["q15_frozen_artifact_hash_bindings"] = hash_bindings
    fixed_env = json.loads((root / "results/Q13-E001/Q8_FIXED20/environment.json").read_text())
    matched_env = json.loads((root / "results/Q13-E006/Q8_RAW_CE_MATCHED/environment.json").read_text())
    env_keys = ["python", "platform", "packages", "torch_cuda_runtime", "cuda_available", "cuda_device_name"]
    summary["matched_runtime_record_comparison"] = {key: fixed_env[key] == matched_env[key] for key in env_keys}
    assert all(summary["matched_runtime_record_comparison"].values())
    summary["no_new_models_or_raw_eeg"] = dict(new_model_fits=0, new_checkpoint_inference=0, new_raw_downloads=0, target_fits=0)
    summary["audit_scope"] = dict(primary_prediction_files=len(primary_paths), inventory_files=len(ledger),
                                    fully_parsed_json=sum(x["scope"].startswith("fully_parsed_json") for x in ledger),
                                    full_csv_parses=sum(x["scope"].startswith("all_csv_rows") for x in ledger),
                                    text_files_decoded=sum(x["scope"].startswith("fully_decoded_text") for x in ledger),
                                    parse_errors=[x for x in ledger if "parse_error" in x],
                                    epistemic_limit="Full parsing/hash checks are not full semantic review or raw-to-prediction replay.")
    (out / "evidence/historical_reaggregation.json").write_text(json.dumps(json_safe(summary), ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(dict(status="historical_saved_outputs_reaggregated", **summary["audit_scope"], **summary["no_new_models_or_raw_eeg"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
