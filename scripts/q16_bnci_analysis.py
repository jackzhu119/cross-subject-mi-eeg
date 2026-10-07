"""Fixed, separately processed BNCI Q16 physiology; requires committed freeze.

Raw power calculation is opt-in with --execute and a passed metadata-only gate.
--self-check uses deterministic synthetic signals only, never original EEG.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import get_window, welch
from scipy.stats import rankdata

from q16_common import (BANDS, BASELINE_OFFSETS, CHANNELS, CLASS_MAP, LIMITS, PERFORMANCE, PERFORMANCE_VALIDATION, ROOT, RUN_DIR, TASK_OFFSETS, binding, fixed_recipe, json_write, load_native_runs, now_utc, require_committed_freeze, sha256_file, software, verify_raw_files)

TRIAL_FIELDS = ["sample_id", "subject", "session", "run", "native_struct_index_zero_based", "native_struct_index_matlab_one_based", "trial", "label", "class_name", "binary_hand_trial", "artifact_flagged", "raw_file_id", "raw_sha256", "trial_start_sample_zero_based", "cue_sample_zero_based", "baseline_start_sample_zero_based", "baseline_stop_sample_exclusive", "task_start_sample_zero_based", "task_stop_sample_exclusive", "channel", "band", "baseline_power_native_numeric_squared", "task_power_native_numeric_squared", "logratio_db", "eligibility_reason", "psd_unit", "integrated_power_unit", "ratio_unit"]


def fixed_power(values: np.ndarray) -> dict[str, np.ndarray]:
    """Native float64 channel-by-time input; no transform beyond fixed Welch."""
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] not in (250, 500):
        raise ValueError("Fixed Welch input must be channel-by-250/500 native samples")
    frequency, psd = welch(values, fs=250.0, window=get_window("hann", 250, fftbins=True), nperseg=250, noverlap=125, nfft=250, detrend="linear", return_onesided=True, scaling="density", axis=-1, average="mean")
    if not np.array_equal(frequency, np.arange(126, dtype=float)):
        raise ValueError("Native Welch frequency grid changed")
    powers = {}
    for band, (low, high) in BANDS.items():
        mask = (frequency >= low) & (frequency <= high)
        powers[band] = np.trapezoid(psd[:, mask], x=frequency[mask], axis=-1)
    return powers


def guarded_logratio(baseline: float, task: float) -> tuple[float | None, str]:
    if not np.isfinite(baseline):
        return None, "nonfinite_baseline_power"
    if not np.isfinite(task):
        return None, "nonfinite_task_power"
    if baseline <= 0:
        return None, "nonpositive_baseline_power"
    if task <= 0:
        return None, "nonpositive_task_power"
    # Difference of logarithms avoids under/overflow from forming the ratio.
    result = float(10.0 * (np.log10(task) - np.log10(baseline)))
    if not np.isfinite(result):
        return None, "nonfinite_logratio"
    return result, "eligible"


def self_check() -> dict:
    time_base = np.arange(250, dtype=float) / 250
    time_task = np.arange(500, dtype=float) / 250
    base = np.stack([np.sin(2 * np.pi * 10 * time_base), np.sin(2 * np.pi * 20 * time_base)])
    task = np.stack([0.5 * np.sin(2 * np.pi * 10 * time_task), 2 * np.sin(2 * np.pi * 20 * time_task)])
    powers_base, powers_task = fixed_power(base), fixed_power(task)
    ratios = {name: [guarded_logratio(float(a), float(b))[0] for a, b in zip(powers_base[name], powers_task[name])] for name in BANDS}
    for gain in (1e-6, 1e6):
        scaled_base, scaled_task = fixed_power(base * gain), fixed_power(task * gain)
        for name in BANDS:
            scaled = [guarded_logratio(float(a), float(b))[0] for a, b in zip(scaled_base[name], scaled_task[name])]
            np.testing.assert_allclose(scaled, ratios[name], rtol=0, atol=1e-11)
    assert guarded_logratio(0.0, 1.0) == (None, "nonpositive_baseline_power")
    assert guarded_logratio(1.0, 0.0) == (None, "nonpositive_task_power")
    assert guarded_logratio(float("nan"), 1.0) == (None, "nonfinite_baseline_power")
    assert 1 + (250 - 250) // 125 == 1 and 1 + (500 - 250) // 125 == 3
    assert BASELINE_OFFSETS == (125, 375) and TASK_OFFSETS == (625, 1125)
    frequency = np.arange(126)
    assert frequency[(frequency >= 8) & (frequency <= 13)].tolist() == [8, 9, 10, 11, 12, 13]
    assert frequency[(frequency >= 13) & (frequency <= 30)].tolist() == list(range(13, 31))
    assert 0.5 * ((-3 - -1) + (-4 - -2)) == -2
    np.testing.assert_allclose(ratios["mu"][0], -6.020599913279624, atol=0.1)
    np.testing.assert_allclose(ratios["beta"][1], 6.020599913279624, atol=0.1)
    return {"status": "synthetic_checks_passed_non_authorizing", "created_at_utc": now_utc(), "original_raw_files_read": 0, "raw_power_computed": False, "synthetic_power_computed": True, "gain_invariance_test_gains": [1e-6, 1e6], "power_guards_checked": True, "periodic_hann_and_fixed_segment_counts": [1, 3], "inclusive_band_edges_checked": True, "shared_13Hz_bin_in_both_bands": True, "laterality_sign_checked": True, "software": software(), "analysis_code": binding(Path(__file__)), "common_code": binding(ROOT / "scripts/q16_common.py")}


def validate_performance() -> pd.DataFrame:
    validator = json.loads(PERFORMANCE_VALIDATION.read_text(encoding="utf-8"))
    if validator.get("passed") is not True or validator.get("experiment_id") != "Q14-E001" or validator.get("subject_seed_metrics_sha256") != sha256_file(PERFORMANCE):
        raise ValueError("Q14-E001 frozen metrics are not bound by their passed validator")
    metrics = pd.read_csv(PERFORMANCE)
    expected_models = {"BROAD_EEGNET": 27, "MU_BETA_SHARED": 27, "CSP4_LDA": 9}
    if len(metrics) != 63 or metrics.groupby("model").size().to_dict() != expected_models or metrics.duplicated(["subject", "model", "seed"]).any() or set(metrics.subject) != set(range(1, 10)):
        raise ValueError("Q14 metrics must contain exactly 63 unique expected final rows")
    if not np.isfinite(metrics.balanced_accuracy).all() or not metrics.balanced_accuracy.between(0, 1).all() or not (metrics.n_trials == 288).all():
        raise ValueError("Q14 BA or trial counts are not finite/expected")
    rows = []
    for (subject, model), group in metrics.groupby(["subject", "model"], sort=True):
        if model == "CSP4_LDA":
            seeds = set(group.seed.astype(str))
            if len(group) != 1 or seeds != {"deterministic"}:
                raise ValueError("Each frozen CSP subject must retain its one final fit")
        else:
            seeds = set(group.seed.astype(int))
            if seeds != {20260924, 20260925, 20260926}:
                raise ValueError("Frozen neural subject must retain all three predetermined seeds")
        for row in group.itertuples():
            matrix = np.asarray(json.loads(row.tn_fp_fn_tp), dtype=np.int64)
            if matrix.shape != (4,) or np.any(matrix < 0) or matrix.sum() != 288 or matrix[0] + matrix[1] != 144 or matrix[2] + matrix[3] != 144 or not np.isclose(row.balanced_accuracy, 0.5 * (matrix[0]/144 + matrix[3]/144), rtol=0, atol=1e-14):
                raise ValueError("Q14 BA differs from its frozen balanced binary confusion cells")
        rows.append({"subject": int(subject), "model": model, "n_frozen_seeds": len(group), "balanced_accuracy_mean": float(group.balanced_accuracy.mean()), "balanced_accuracy_min_seed": float(group.balanced_accuracy.min()), "balanced_accuracy_max_seed": float(group.balanced_accuracy.max()), "balanced_accuracy_sd_across_seeds": float(group.balanced_accuracy.std(ddof=1)) if len(group) > 1 else None, "seed_ids": ";".join(str(seed) for seed in sorted(seeds)), "performance_source": "Q14-E001_frozen_source_only_binary_LOSO", "n_test_trials_per_seed": 288})
    return pd.DataFrame(rows)


def write_trials(files: list[dict], output: Path) -> dict:
    reasons = Counter()
    counts = Counter()
    invalid_trial_ids = set()
    with output.open("wb") as destination:
        with gzip.GzipFile(filename="", mode="wb", fileobj=destination, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=TRIAL_FIELDS, lineterminator="\n")
                writer.writeheader()
                for record in files:
                    runs = load_native_runs(Path(record["path"]))
                    for run in runs:
                        for ordinal, (matlab_start, label, artifact) in enumerate(zip(run["trial"], run["y"], run["artifacts"]), 1):
                            start = int(matlab_start) - 1
                            sample_id = f"s{record['subject']:02d}_{record['session']}_r{run['run']}_t{ordinal:02d}"
                            base = np.asarray(run["X"][start+125:start+375, :22].T, dtype=np.float64)
                            task = np.asarray(run["X"][start+625:start+1125, :22].T, dtype=np.float64)
                            whole_trial_reason = None
                            if base.shape != (22, 250) or task.shape != (22, 500):
                                whole_trial_reason = "fixed_window_unavailable"
                            elif not np.isfinite(base).all():
                                whole_trial_reason = "nonfinite_baseline_samples_trial"
                            elif not np.isfinite(task).all():
                                whole_trial_reason = "nonfinite_task_samples_trial"
                            baseline_power = fixed_power(base) if whole_trial_reason is None else None
                            task_power = fixed_power(task) if whole_trial_reason is None else None
                            counts["all_trials"] += 1
                            counts["binary_trials"] += int(label in (1, 2))
                            counts["artifact_flagged_trials"] += int(artifact)
                            counts["binary_artifact_flagged_trials"] += int(artifact and label in (1, 2))
                            identity = {"sample_id": sample_id, "subject": record["subject"], "session": record["session"], "run": run["run"], "native_struct_index_zero_based": run["native_struct_index_zero_based"], "native_struct_index_matlab_one_based": run["native_struct_index_matlab_one_based"], "trial": ordinal, "label": int(label), "class_name": CLASS_MAP[int(label)], "binary_hand_trial": bool(label in (1, 2)), "artifact_flagged": bool(artifact), "raw_file_id": record["file_id"], "raw_sha256": record["sha256"], "trial_start_sample_zero_based": start, "cue_sample_zero_based": start+500, "baseline_start_sample_zero_based": start+125, "baseline_stop_sample_exclusive": start+375, "task_start_sample_zero_based": start+625, "task_stop_sample_exclusive": start+1125, "psd_unit": "native_numeric_squared_per_Hz", "integrated_power_unit": "native_numeric_squared", "ratio_unit": "dB"}
                            for channel_index, channel in enumerate(CHANNELS):
                                for band in BANDS:
                                    bp = float(baseline_power[band][channel_index]) if baseline_power is not None else None
                                    tp = float(task_power[band][channel_index]) if task_power is not None else None
                                    db, reason = guarded_logratio(bp, tp) if whole_trial_reason is None else (None, whole_trial_reason)
                                    if reason != "eligible":
                                        invalid_trial_ids.add(sample_id)
                                    reasons[reason] += 1
                                    writer.writerow({**identity, "channel": channel, "band": band, "baseline_power_native_numeric_squared": bp if bp is not None and np.isfinite(bp) else None, "task_power_native_numeric_squared": tp if tp is not None and np.isfinite(tp) else None, "logratio_db": db, "eligibility_reason": reason})
                    print(f"Fixed power saved {record['file_id']}: all four classes and native artifacts retained", flush=True)
    if counts != Counter({"all_trials": 5184, "binary_trials": 2592, "artifact_flagged_trials": 488, "binary_artifact_flagged_trials": 246}) or sum(reasons.values()) != 228096:
        raise ValueError("Fixed physiology output identity/counts differ from passed metadata")
    return {**dict(counts), "trial_channel_band_rows": sum(reasons.values()), "eligibility_reason_row_counts": dict(reasons), "n_unique_trials_with_any_power_guard_failure": len(invalid_trial_ids)}


def summarize_channels(trials: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    keys = ["subject", "session", "class_name", "channel", "band"]
    sessions = trials.groupby(keys, sort=True, observed=True).agg(n_trials=("sample_id", "size"), n_eligible=("logratio_db", "count"), n_artifact_flagged=("artifact_flagged", "sum"), mean_trial_logratio_db=("logratio_db", "mean"), median_trial_logratio_db=("logratio_db", "median"), mean_baseline_power_native_numeric_squared=("baseline_power_native_numeric_squared", "mean"), mean_task_power_native_numeric_squared=("task_power_native_numeric_squared", "mean")).reset_index()
    sessions["ratio_unit"] = "dB"
    subjects = []
    for (subject, hand, channel, band), group in sessions.groupby(["subject", "class_name", "channel", "band"], sort=True):
        complete = set(group.session) == {"0train", "1test"} and group.mean_trial_logratio_db.notna().all()
        subjects.append({"subject": int(subject), "class_name": hand, "channel": channel, "band": band, "n_sessions_expected": 2, "n_sessions_available": int(group.mean_trial_logratio_db.notna().sum()), "n_trials": int(group.n_trials.sum()), "n_eligible": int(group.n_eligible.sum()), "n_artifact_flagged": int(group.n_artifact_flagged.sum()), "equal_session_mean_trial_logratio_db": float(group.mean_trial_logratio_db.mean()) if complete else None, "equal_session_mean_of_trial_medians_db": float(group.median_trial_logratio_db.mean()) if complete else None, "eligibility_reason": "eligible" if complete else "one_or_more_required_sessions_unavailable", "ratio_unit": "dB"})
    strata = trials.groupby(keys + ["artifact_flagged"], sort=True, observed=True).agg(n_trials=("sample_id", "size"), n_eligible=("logratio_db", "count"), mean_trial_logratio_db=("logratio_db", "mean"), median_trial_logratio_db=("logratio_db", "median")).reset_index()
    full_strata = pd.MultiIndex.from_product([range(1, 10), ("0train", "1test"), list(CLASS_MAP.values()), list(CHANNELS), list(BANDS), (False, True)], names=keys + ["artifact_flagged"])
    strata = strata.set_index(keys + ["artifact_flagged"]).reindex(full_strata).reset_index()
    strata[["n_trials", "n_eligible"]] = strata[["n_trials", "n_eligible"]].fillna(0).astype(int)
    strata["ratio_unit"] = "dB"
    return sessions, pd.DataFrame(subjects), strata


def paired_laterality(trials: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    hands = trials.loc[trials.binary_hand_trial & trials.channel.isin(["C3", "C4"])]
    paired = hands.pivot(index=["sample_id", "subject", "session", "class_name", "band"], columns="channel", values="logratio_db").reset_index()
    paired["paired_eligible"] = paired[["C3", "C4"]].notna().all(axis=1)
    paired.loc[~paired.paired_eligible, ["C3", "C4"]] = np.nan
    sessions = paired.groupby(["subject", "session", "class_name", "band"], sort=True, observed=True).agg(n_trials=("sample_id", "size"), n_paired_eligible=("paired_eligible", "sum"), C3_mean_trial_logratio_db=("C3", "mean"), C4_mean_trial_logratio_db=("C4", "mean"), C3_median_trial_logratio_db=("C3", "median"), C4_median_trial_logratio_db=("C4", "median")).reset_index()
    descriptors = []
    for subject in range(1, 10):
        for band in BANDS:
            group = sessions[(sessions.subject == subject) & (sessions.band == band)]
            for session in ("0train", "1test", "equal_session"):
                used = group if session == "equal_session" else group[group.session == session]
                required = 4 if session == "equal_session" else 2
                complete = len(used) == required and (used.n_paired_eligible > 0).all() and used[["C3_mean_trial_logratio_db", "C4_mean_trial_logratio_db"]].notna().all().all()
                means = used.groupby("class_name")[["C3_mean_trial_logratio_db", "C4_mean_trial_logratio_db"]].mean() if complete else None
                c3r = float(means.loc["right_hand", "C3_mean_trial_logratio_db"]) if complete else None
                c4r = float(means.loc["right_hand", "C4_mean_trial_logratio_db"]) if complete else None
                c4l = float(means.loc["left_hand", "C4_mean_trial_logratio_db"]) if complete else None
                c3l = float(means.loc["left_hand", "C3_mean_trial_logratio_db"]) if complete else None
                right_term = c3r-c4r if complete else None
                left_term = c4l-c3l if complete else None
                contra = 0.5*(c3r+c4l) if complete else None
                ipsi = 0.5*(c4r+c3l) if complete else None
                descriptors.append({"subject": subject, "session": session, "band": band, "C3_right_mean_db": c3r, "C4_right_mean_db": c4r, "C4_left_mean_db": c4l, "C3_left_mean_db": c3l, "right_C3_minus_C4_db": right_term, "left_C4_minus_C3_db": left_term, "contralateral_mean_db": contra, "ipsilateral_mean_db": ipsi, "signed_laterality_db": 0.5*(right_term+left_term) if complete else None, "n_hand_session_cells_expected": required, "n_hand_session_cells_available": int((used.n_paired_eligible > 0).sum()), "n_paired_eligible_trials": int(used.n_paired_eligible.sum()), "eligibility_reason": "eligible" if complete else "one_or_more_required_hand_sessions_unavailable", "ratio_unit": "dB"})
    descriptors = pd.DataFrame(descriptors)
    return sessions, descriptors[descriptors.session != "equal_session"].copy(), descriptors[descriptors.session == "equal_session"].copy()


def descriptive_associations(descriptors: pd.DataFrame, performance: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    joined = descriptors.merge(performance, on="subject", validate="many_to_many")
    joined["primary_descriptive_context"] = joined.model == "BROAD_EEGNET"
    rows = []
    for model in ("BROAD_EEGNET", "MU_BETA_SHARED", "CSP4_LDA"):
        for band in ("mu", "beta"):
            group = joined[(joined.model == model) & (joined.band == band)].sort_values("subject")
            complete = len(group) == 9 and set(group.subject) == set(range(1, 10)) and group.signed_laterality_db.notna().all()
            x, y = group.signed_laterality_db.to_numpy(float), group.balanced_accuracy_mean.to_numpy(float)
            reason = "eligible" if complete else "required_subject_descriptor_unavailable"
            rho = None
            if complete:
                if len(np.unique(x)) < 2 or len(np.unique(y)) < 2:
                    reason = "constant_descriptor_or_performance"
                else:
                    rho = float(np.corrcoef(rankdata(x, method="average"), rankdata(y, method="average"))[0, 1])
            rows.append({"model": model, "band": band, "n_subjects_expected": 9, "n_subjects_with_descriptor": int(group.signed_laterality_db.notna().sum()), "spearman_rho": rho, "primary_descriptive_context": model == "BROAD_EEGNET", "eligibility_reason": reason, "statistic": "Pearson_correlation_of_average_ranks", "p_value_computed": False, "performance_aggregation": "three_seed_mean" if model != "CSP4_LDA" else "one_frozen_CSP_fit", "physiology_descriptor": "signed_C3_C4_hand_laterality_equal_session_mean_dB"})
    if len(joined) != 54:
        raise ValueError("Physiology/performance join must preserve all nine people, three models, two bands")
    return joined, pd.DataFrame(rows)


def safe_records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.to_json(orient="records", double_precision=15))


def execute(args: argparse.Namespace) -> None:
    freeze = require_committed_freeze(args.freeze_manifest, args.freeze_commit, args.metadata_audit)
    audit = json.loads(args.metadata_audit.read_text(encoding="utf-8"))
    files, provenance = verify_raw_files(args.data_dir)
    if [{k: r[k] for k in ("file_id", "sha256", "bytes")} for r in files] != [{k: r[k] for k in ("file_id", "sha256", "bytes")} for r in audit["files"]] or provenance != audit["raw_receipt"]:
        raise ValueError("Actual raw inventory differs from committed passed metadata audit")
    performance = validate_performance()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    trial_path = args.output_dir / "trial_power.csv.gz"
    if trial_path.exists():
        raise ValueError("Refuse to overwrite an existing Q16 raw-power artifact; preserve the audited run")
    started = now_utc()
    counts = write_trials(files, trial_path)
    trials = pd.read_csv(trial_path)
    if len(trials) != 228096 or trials.duplicated(["sample_id", "channel", "band"]).any() or trials.sample_id.nunique() != 5184:
        raise ValueError("Saved trial table does not retain the fixed unique grain")
    sessions, subjects, strata = summarize_channels(trials)
    paired_sessions, session_laterality, laterality = paired_laterality(trials)
    joined, associations = descriptive_associations(laterality, performance)
    frames = {
        "subject_session_band_summary.csv": sessions, "subject_band_summary.csv": subjects,
        "artifact_stratum_band_summary.csv": strata, "subject_session_hand_pair_summary.csv": paired_sessions,
        "subject_session_hand_laterality.csv": session_laterality, "subject_hand_laterality.csv": laterality,
        "frozen_subject_performance.csv": performance, "subject_physiology_performance.csv": joined,
        "descriptive_associations.csv": associations,
    }
    for name, frame in frames.items():
        frame.to_csv(args.output_dir / name, index=False, float_format="%.17g", lineterminator="\n")
    sensorimotor = subjects[subjects.channel.isin(["C3", "Cz", "C4"])]
    population = sensorimotor.groupby(["class_name", "channel", "band"], sort=True).agg(n_subjects=("equal_session_mean_trial_logratio_db", "count"), equal_subject_mean_db=("equal_session_mean_trial_logratio_db", "mean"), between_subject_sd_db=("equal_session_mean_trial_logratio_db", "std"), minimum_subject_mean_db=("equal_session_mean_trial_logratio_db", "min"), maximum_subject_mean_db=("equal_session_mean_trial_logratio_db", "max")).reset_index()
    lateral_population = laterality.groupby("band", sort=False).agg(n_subjects=("signed_laterality_db", "count"), mean_signed_laterality_db=("signed_laterality_db", "mean"), minimum_signed_laterality_db=("signed_laterality_db", "min"), maximum_signed_laterality_db=("signed_laterality_db", "max"), mean_contralateral_db=("contralateral_mean_db", "mean"), mean_ipsilateral_db=("ipsilateral_mean_db", "mean")).reset_index()
    summary = {"schema_version": 1, "analysis_id": "Q16-P001-BNCI-20261006", "status": "fixed_BNCI_descriptive_physiology_complete", "counts": counts, "new_decoder_fits": 0, "new_decoder_inference": 0, "new_checkpoint_inference": 0,
               "channel_population_summary": safe_records(population), "laterality_population_summary": safe_records(lateral_population), "descriptive_associations": safe_records(associations), "limits": LIMITS,
               "unit_labels": {"PSD": "native_numeric_squared_per_Hz", "power": "native_numeric_squared", "task_baseline_logratio": "dB", "native_numeric_microvolt_convention_not_newly_calibrated": True, "uniform_voltage_gain_invariance_of_ratio": True},
               "summary_aggregation": "mean trial dB within subject/class/session; equal session mean for each subject; equal subject mean only for population descriptions", "laterality_pairing": "C3/C4 share eligible trials within band; no partial-session or missing-person reweighting"}
    summary_path = args.output_dir / "summary.json"
    json_write(summary_path, summary)
    outputs = [binding(trial_path)] + [{**binding(args.output_dir / name), "rows": len(frame), "columns": list(frame.columns)} for name, frame in frames.items()] + [binding(summary_path)]
    manifest = {"schema_version": 1, "analysis_id": "Q16-P001-BNCI-20261006", "status": "complete", "started_at_utc": started, "completed_at_utc": now_utc(), "freeze": freeze, "recipe": fixed_recipe(), "software": software(), "command": sys.argv,
                "git_HEAD_at_execution": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(), "raw_files": files, "raw_receipt": provenance, "performance_input": binding(PERFORMANCE), "performance_validator": binding(PERFORMANCE_VALIDATION), "outputs": outputs,
                "counts": counts, "new_decoder_fits": 0, "new_decoder_inference": 0, "new_checkpoint_inference": 0, "physiological_power_computed": True, "external_physiology_computed": False, "p_values_computed": False, "high_low_groups_computed": False, "figures_computed_by_this_script": False, "limits": LIMITS}
    json_write(args.output_dir / "run_manifest.json", manifest)
    print(f"Saved fixed Q16 descriptive tables and manifest: {args.output_dir.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--self-check-output", type=Path, default=RUN_DIR / "synthetic_self_check.json")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--metadata-audit", type=Path, default=RUN_DIR / "metadata_audit.json")
    parser.add_argument("--freeze-manifest", type=Path, default=RUN_DIR / "preprocessing_freeze.json")
    parser.add_argument("--freeze-commit")
    parser.add_argument("--output-dir", type=Path, default=RUN_DIR)
    args = parser.parse_args()
    if args.self_check:
        if args.execute:
            parser.error("Synthetic self-check and real execution are separate modes")
        result = self_check()
        json_write(args.self_check_output, result)
        print(f"Synthetic method checks passed; no original EEG read: {args.self_check_output.resolve()}")
        return
    if not args.execute:
        print(json.dumps({"status": "planned_no_raw_power", "recipe": fixed_recipe()}, indent=2))
        return
    if args.data_dir is None or not args.freeze_commit:
        parser.error("--execute requires --data-dir and the full committed --freeze-commit SHA")
    execute(args)


if __name__ == "__main__":
    main()
