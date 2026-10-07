"""Independent raw Q16 numerical replay; no decoder fitting or inference.

The CLI requires the committed Q16 freeze and --execute. The central-channel
replay uses an explicitly constructed periodic Hann, closed-form least-squares
linear detrending, NumPy rFFT periodograms, and hand-written trapezoidal band
integration. It never imports the Q16 estimator or aggregation helpers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "research_runs/Q16-P001-BNCI-20261006"
CHANNELS = ("Fz", "FC3", "FC1", "FCz", "FC2", "FC4", "C5", "C3", "C1", "Cz", "C2", "C4", "C6", "CP3", "CP1", "CPz", "CP2", "CP4", "P1", "Pz", "P2", "POz")
CENTRAL = ("C3", "Cz", "C4")
CLASS = {1: "left_hand", 2: "right_hand", 3: "feet", 4: "tongue"}
BANDS = {"mu": (8, 13), "beta": (13, 30)}
MODELS = ("BROAD_EEGNET", "MU_BETA_SHARED", "CSP4_LDA")
Q8 = ROOT / "research_runs/Q8-E001/results/trial_metadata.csv"
Q14 = ROOT / "results/Q14-E001"
OLD_RECEIPT = ROOT / "research_runs/Q15-EXECUTION-20261003/jobs/20261004T005335Z-9b3bce30277a/bnci_source_receipt.json"
POWER_RTOL = 1e-10
DB_ATOL = 1e-10
SUMMARY_ATOL = 1e-11


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def record(path: Path) -> dict:
    path = path.resolve()
    try:
        location = path.relative_to(ROOT).as_posix()
    except ValueError:
        location = str(path)
    return {"path": location, "sha256": digest(path), "bytes": path.stat().st_size}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_true(value, description: str) -> None:
    if not bool(value):
        raise AssertionError(description)


def git_bytes(path: Path, commit: str) -> bytes:
    relative = path.resolve().relative_to(ROOT).as_posix()
    return subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=ROOT, capture_output=True, check=True).stdout


def verify_gate(commit: str, run_dir: Path) -> dict:
    assert_true(len(commit) == 40, "Full immutable freeze SHA required")
    resolved = subprocess.run(["git", "rev-parse", "--verify", f"{commit}^{{commit}}"], cwd=ROOT, capture_output=True, check=True, text=True).stdout.strip()
    assert_true(resolved == commit, "Freeze SHA is not an existing commit")
    subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT, capture_output=True, check=True)
    freeze_path = run_dir / "preprocessing_freeze.json"
    assert_true(hashlib.sha256(git_bytes(freeze_path, commit)).hexdigest() == digest(freeze_path), "Freeze manifest differs from immutable commit")
    freeze = read_json(freeze_path)
    assert_true(freeze["status"] == "frozen_before_raw_power", "Freeze status invalid")
    assert_true(freeze["analysis_id"] == "Q16-P001-BNCI-20261006", "Freeze analysis identity invalid")
    for item in freeze["code_files"] + freeze["input_files"] + freeze["protocol_files"]:
        path = Path(item["path"])
        if not path.is_absolute():
            path = ROOT / path
        assert_true(record(path) == item, f"Frozen local bytes changed: {path.name}")
        assert_true(hashlib.sha256(git_bytes(path, commit)).hexdigest() == item["sha256"], f"Frozen commit bytes changed: {path.name}")
    recipe = freeze["recipe"]
    checks = {
        "sampling_rate_hz": 250,
        "channels": list(CHANNELS),
        "baseline_trial_relative_samples_half_open": [125, 375],
        "task_trial_relative_samples_half_open": [625, 1125],
        "cue_offset_native_samples": 500,
        "additional_filter": None,
        "additional_reference": None,
        "additional_scaler": None,
        "bands_hz_inclusive": {"mu": [8.0, 13.0], "beta": [13.0, 30.0]},
        "epsilon_or_clipping": None,
        "new_decoder_fits": 0,
        "new_decoder_inference": 0,
    }
    for key, value in checks.items():
        assert_true(recipe.get(key) == value, f"Fixed recipe differs: {key}")
    welch = recipe["welch"]
    for key, value in {"nperseg": 250, "noverlap": 125, "nfft": 250, "detrend": "linear", "return_onesided": True, "scaling": "density", "average": "mean", "baseline_segments": 1, "task_segments": 3}.items():
        assert_true(welch.get(key) == value, f"Fixed Welch recipe differs: {key}")
    assert_true("hann" in welch["window"] and "fftbins=True" in welch["window"], "Periodic Hann not frozen")
    audit = read_json(run_dir / "metadata_audit.json")
    assert_true(audit["status"] == "metadata_passed_before_raw_power" and audit["raw_power_computed"] is False, "Metadata-only gate not passed")
    manifest = read_json(run_dir / "run_manifest.json")
    assert_true(manifest["status"] == "complete" and manifest["freeze"]["git_commit"] == commit, "Raw computation manifest incomplete or different freeze")
    assert_true(manifest["recipe"] == recipe, "Executed recipe differs from committed recipe")
    for item in manifest["outputs"]:
        output_path = Path(item["path"])
        if not output_path.is_absolute():
            output_path = ROOT / output_path
        assert_true(record(output_path) == {k: item[k] for k in ("path", "sha256", "bytes")}, f"Result digest differs: {Path(item['path']).name}")
    for key in ("new_decoder_fits", "new_decoder_inference", "new_checkpoint_inference"):
        assert_true(manifest.get(key) == 0, f"Unexpected decoder operation: {key}")
    assert_true(manifest["external_physiology_computed"] is False and manifest["p_values_computed"] is False and manifest["high_low_groups_computed"] is False, "Scope changed from descriptive BNCI component")
    assert_true(manifest["started_at_utc"] >= freeze["created_at_utc"], "Raw analysis predates written gate")
    return {"freeze_commit": commit, "freeze_manifest": record(freeze_path), "metadata_audit": record(run_dir / "metadata_audit.json"), "run_manifest": record(run_dir / "run_manifest.json"), "n_result_hashes_checked": len(manifest["outputs"])}


def independent_power(signal: np.ndarray) -> dict[str, np.ndarray]:
    """Closed-form OLS detrending and explicit NumPy one-sided periodograms."""
    x = np.asarray(signal, dtype=np.float64)
    assert_true(x.ndim == 2 and x.shape[0] in (250, 500), "Independent native sample window changed")
    n = 250
    t = np.arange(n, dtype=np.float64) - (n - 1) / 2
    window = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n, dtype=np.float64) / n)
    accumulated = np.zeros((126, x.shape[1]), dtype=np.float64)
    segments = 0
    for start in range(0, x.shape[0] - n + 1, 125):
        segment = x[start:start + n]
        mean = segment.mean(axis=0)
        slope = np.sum(t[:, None] * (segment - mean), axis=0) / np.dot(t, t)
        residual = segment - mean - t[:, None] * slope
        fft = np.fft.rfft(residual * window[:, None], n=n, axis=0)
        psd = (fft.real ** 2 + fft.imag ** 2) / (250.0 * np.dot(window, window))
        psd[1:-1] *= 2.0  # DC/Nyquist are not doubled for an even-length FFT.
        accumulated += psd
        segments += 1
    accumulated /= segments
    assert_true(segments == (1 if len(x) == 250 else 3), "Independent Welch segment count changed")
    return {name: 0.5 * (accumulated[low] + accumulated[high]) + accumulated[low + 1:high].sum(axis=0) for name, (low, high) in BANDS.items()}


def verify_raw_and_central(data_dir: Path, trials: pd.DataFrame) -> dict:
    expected = pd.read_csv(Q8).sort_values("sample_id").reset_index(drop=True)
    receipt = read_json(OLD_RECEIPT)
    expected_files = {f"A{s:02d}{suffix}.mat" for s in range(1, 10) for suffix in ("T", "E")}
    rows = {row["file_id"]: row for row in receipt["files"]}
    assert_true(set(rows) == expected_files, "Raw frozen receipt is not the expected 18-file population")
    assert_true(len(trials) == 228096 and trials.sample_id.nunique() == 5184, "Trial-channel-band population changed")
    assert_true(not trials.duplicated(["sample_id", "channel", "band"]).any(), "Duplicated trial/channel/band identities")
    assert_true(set(trials.channel) == set(CHANNELS) and set(trials.band) == set(BANDS), "Channel or band coverage changed")
    assert_true((trials.groupby("sample_id").size() == 44).all(), "Trial row coverage must be 22 channels times two bands")
    indexed = trials.set_index(["sample_id", "channel", "band"], verify_integrity=True)
    event_rows = []
    power_errors, db_errors = [], []
    reason_counts = Counter()
    n_pairs, n_runs, n_previous_checks, min_gap = 0, 0, 0, None
    central_idx = [CHANNELS.index(c) for c in CENTRAL]
    for name in sorted(expected_files):
        path = data_dir / name
        assert_true(path.is_file(), f"Missing original file: {name}")
        sha = digest(path)
        assert_true(sha == rows[name]["sha256"] and path.stat().st_size == rows[name]["size_bytes"], f"Original bytes differ: {name}")
        subject = int(name[1:3])
        session = "0train" if name[3] == "T" else "1test"
        native = loadmat(path, variable_names=["data"], simplify_cells=True)["data"]
        if isinstance(native, np.ndarray):
            native = native.reshape(-1).tolist()
        if isinstance(native, dict):
            native = [native]
        active_idx = -1
        for struct_idx, run in enumerate(native):
            if np.asarray(run.get("trial", [])).size == 0:
                continue
            active_idx += 1
            n_runs += 1
            x = np.asarray(run["X"])
            rate = float(np.asarray(run["fs"]).item())
            assert_true(rate == 250.0 and x.ndim == 2 and x.shape[1] == 25, "Native sampling/channel topology changed")
            starts = np.asarray(run["trial"]).reshape(-1)
            labels = np.asarray(run["y"]).reshape(-1)
            flags = np.asarray(run["artifacts"]).reshape(-1)
            assert_true(len(starts) == len(labels) == len(flags) == 48, "Native 48-trial run topology changed")
            assert_true(Counter(labels.tolist()) == Counter({1: 12, 2: 12, 3: 12, 4: 12}), "Native class balance changed")
            classes = [str(c).strip().lower().replace(" ", "_") for c in np.asarray(run["classes"]).reshape(-1)]
            assert_true(classes == list(CLASS.values()), "Native label meaning changed")
            starts = starts.astype(np.int64) - 1
            for ordinal, (anchor, label, flag) in enumerate(zip(starts, labels, flags), 1):
                sample = f"s{subject:02d}_{session}_r{active_idx}_t{ordinal:02d}"
                if ordinal > 1:
                    gap = int(anchor + 125 - (starts[ordinal - 2] + 1500))
                    min_gap = gap if min_gap is None else min(min_gap, gap)
                    assert_true(gap >= 0, "Baseline overlaps previous nominal imagery")
                    n_previous_checks += 1
                assert_true(anchor + 125 >= 0 and anchor + 1125 <= len(x), "Fixed intervals leave native run")
                events = {"sample_id": sample, "subject": subject, "session": session, "run": active_idx, "trial": ordinal, "label": int(label), "event_sample": int(anchor), "artifact_flagged": bool(flag)}
                event_rows.append(events)
                saved = indexed.loc[sample]
                checks = {"subject": subject, "session": session, "run": active_idx, "trial": ordinal, "label": int(label), "artifact_flagged": bool(flag), "native_struct_index_zero_based": struct_idx, "native_struct_index_matlab_one_based": struct_idx + 1, "raw_file_id": name, "raw_sha256": sha, "class_name": CLASS[int(label)], "binary_hand_trial": bool(label in (1, 2)), "trial_start_sample_zero_based": int(anchor), "cue_sample_zero_based": int(anchor + 500), "baseline_start_sample_zero_based": int(anchor + 125), "baseline_stop_sample_exclusive": int(anchor + 375), "task_start_sample_zero_based": int(anchor + 625), "task_stop_sample_exclusive": int(anchor + 1125), "psd_unit": "native_numeric_squared_per_Hz", "integrated_power_unit": "native_numeric_squared", "ratio_unit": "dB"}
                for key, value in checks.items():
                    assert_true((saved[key] == value).all(), f"Saved raw/event/unit identity mismatch: {sample}/{key}")
                baseline, task = x[anchor + 125:anchor + 375, :22], x[anchor + 625:anchor + 1125, :22]
                finite_base, finite_task = np.isfinite(baseline).all(), np.isfinite(task).all()
                if not finite_base or not finite_task:
                    reason = "nonfinite_baseline_samples_trial" if not finite_base else "nonfinite_task_samples_trial"
                    assert_true((saved.eligibility_reason == reason).all() and saved.logratio_db.isna().all(), "Nonfinite-window guards not preserved")
                    reason_counts.update(saved.eligibility_reason.tolist())
                    continue
                # Every channel-band row must obey guards and its stored ratio.
                bp = saved.baseline_power_native_numeric_squared.to_numpy(float)
                tp = saved.task_power_native_numeric_squared.to_numpy(float)
                reasons = np.full(len(saved), "eligible", dtype=object)
                reasons[~np.isfinite(bp)] = "nonfinite_baseline_power"
                reasons[np.isfinite(bp) & ~np.isfinite(tp)] = "nonfinite_task_power"
                reasons[np.isfinite(bp) & np.isfinite(tp) & (bp <= 0)] = "nonpositive_baseline_power"
                reasons[np.isfinite(bp) & np.isfinite(tp) & (bp > 0) & (tp <= 0)] = "nonpositive_task_power"
                valid = reasons == "eligible"
                expected_db = np.full(len(saved), np.nan)
                expected_db[valid] = 10 * np.log10(tp[valid] / bp[valid])
                bad_db = valid & ~np.isfinite(expected_db)
                reasons[bad_db] = "nonfinite_logratio"
                valid = reasons == "eligible"
                assert_true(np.array_equal(reasons, saved.eligibility_reason.to_numpy()), "Saved positivity/finite guard differs")
                np.testing.assert_allclose(saved.logratio_db, expected_db, rtol=0, atol=DB_ATOL, equal_nan=True)
                reason_counts.update(reasons.tolist())
                independent_base = independent_power(baseline[:, central_idx])
                independent_task = independent_power(task[:, central_idx])
                for band in BANDS:
                    for ci, channel in enumerate(CENTRAL):
                        row = indexed.loc[(sample, channel, band)]
                        for computed, stored in ((independent_base[band][ci], row.baseline_power_native_numeric_squared), (independent_task[band][ci], row.task_power_native_numeric_squared)):
                            np.testing.assert_allclose(computed, stored, rtol=POWER_RTOL, atol=0)
                            if computed > 0:
                                power_errors.append(float(abs(computed - stored) / computed))
                        if row.eligibility_reason == "eligible":
                            value = float(10 * np.log10(independent_task[band][ci] / independent_base[band][ci]))
                            error = abs(value - float(row.logratio_db))
                            assert_true(error <= DB_ATOL, "Independent log-ratio differs")
                            db_errors.append(error)
                        n_pairs += 1
        assert_true(active_idx == 5, "Native file is not six labeled runs")
        print(f"Independent raw FFT replay verified {name}", flush=True)
    actual_events = pd.DataFrame(event_rows).sort_values("sample_id").reset_index(drop=True)
    pd.testing.assert_frame_equal(actual_events[expected.columns], expected, check_dtype=False)
    assert_true(n_runs == 108 and n_previous_checks == 5076 and n_pairs == 31104, "Full raw replay coverage differs")
    assert_true(int(actual_events.artifact_flagged.sum()) == 488, "Artifact annotations discarded")
    assert_true(int(actual_events.loc[actual_events.label.isin([1, 2]), "artifact_flagged"].sum()) == 246, "Hand artifact annotations discarded")
    return {"raw_files_sha256_verified": 18, "raw_event_identities_replayed": 5184, "all_trial_channel_band_rows_checked": 228096, "manual_central_channel_band_pairs_replayed": n_pairs, "manual_baseline_task_power_comparisons": 2 * n_pairs, "n_labeled_native_runs": n_runs, "n_nominal_previous_imagery_checks": n_previous_checks, "minimum_baseline_gap_after_previous_nominal_imagery_samples": min_gap, "eligibility_reason_row_counts": dict(reason_counts), "all_class_artifact_flags_retained": 488, "binary_artifact_flags_retained": 246, "maximum_relative_power_difference": max(power_errors, default=0), "maximum_absolute_logratio_difference_db": max(db_errors, default=0), "power_relative_tolerance": POWER_RTOL, "logratio_absolute_tolerance_db": DB_ATOL, "independent_algorithm": "closed_form_OLS_linear_detrend_explicit_periodic_Hann_numpy_rFFT_onesided_periodograms_manual_trapezoid"}


def compare_table(expected: pd.DataFrame, actual_path: Path, keys: list[str], checks: dict) -> None:
    actual = pd.read_csv(actual_path)
    assert_true(not expected.duplicated(keys).any() and not actual.duplicated(keys).any(), f"Summary key duplication: {actual_path.name}")
    e = expected.sort_values(keys).reset_index(drop=True)
    a = actual.sort_values(keys).reset_index(drop=True)
    assert_true(len(e) == len(a), f"Summary row count differs: {actual_path.name}")
    for col in e.columns:
        assert_true(col in a, f"Summary column missing: {actual_path.name}/{col}")
        if pd.api.types.is_numeric_dtype(e[col]):
            np.testing.assert_allclose(a[col].to_numpy(float), e[col].to_numpy(float), rtol=0, atol=SUMMARY_ATOL, equal_nan=True, err_msg=f"Summary differs: {actual_path.name}/{col}")
        else:
            assert_true(a[col].fillna("<NA>").astype(str).tolist() == e[col].fillna("<NA>").astype(str).tolist(), f"Summary identity differs: {actual_path.name}/{col}")
    checks[actual_path.name] = {"rows": len(a), "computed_columns_checked": list(e.columns), "sha256": digest(actual_path)}


def verify_performance(q8: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    metrics_path = Q14 / "subject_seed_metrics.csv"
    metrics = pd.read_csv(metrics_path, dtype={"seed": str})
    previous_validator = read_json(Q14 / "validation_report.json")
    assert_true(previous_validator["passed"] is True and previous_validator["subject_seed_metrics_sha256"] == digest(metrics_path), "Frozen BA receipt no longer matches metrics")
    assert_true(len(metrics) == 63 and not metrics.duplicated(["subject", "model", "seed"]).any(), "Frozen metrics seed grain changed")
    source_meta = pd.read_csv(Q14 / "source_metadata.csv")
    expected = q8[q8.label.isin([1, 2])]
    check_cols = ["sample_id", "subject", "session", "run", "trial", "label", "artifact_flagged"]
    pd.testing.assert_frame_equal(source_meta[check_cols].sort_values("sample_id").reset_index(drop=True), expected[check_cols].sort_values("sample_id").reset_index(drop=True), check_dtype=False)
    summary_rows, manifests_checked, prediction_rows = [], 0, 0
    for model in MODELS:
        for subject in range(1, 10):
            source_people = [s for s in range(1, 10) if s != subject]
            source_ids = source_meta.loc[source_meta.subject.isin(source_people), "sample_id"].tolist()
            source_sha = hashlib.sha256("\n".join(source_ids).encode()).hexdigest()
            base = Q14 / model / f"target_{subject:02d}"
            records = metrics[(metrics.subject == subject) & (metrics.model == model)]
            required_seeds = {"deterministic"} if model == "CSP4_LDA" else {"20260924", "20260925", "20260926"}
            assert_true(set(records.seed) == required_seeds, "Frozen final seed set changed")
            if model != "CSP4_LDA":
                selection = read_json(base / "selection.json")
                assert_true(selection["source_subjects"] == source_people and subject not in sum(selection["validation_groups"], []), "Target enters source-only epoch selection")
                for fold in range(1, 5):
                    im = read_json(base / f"inner_{fold:02d}/manifest.json")
                    train, val = im["train_subjects"], im["validation_subjects"]
                    assert_true(subject not in train + val and not set(train).intersection(val) and sorted(train + val) == source_people and im["target_subjects"] == [subject], "Inner fit/validation leaked held-out subject")
                    manifests_checked += 1
            bvalues = []
            for row in records.itertuples(index=False):
                path = base if model == "CSP4_LDA" else base / f"final_seed_{row.seed}"
                manifest = read_json(path / "manifest.json")
                assert_true(manifest["status"] == "complete" and manifest["train_subjects"] == source_people and manifest["train_sample_ids_sha256"] == source_sha, "Final fit includes held-out subject or source IDs differ")
                if model != "CSP4_LDA":
                    assert_true(manifest["target_subjects"] == [subject], "Final target manifest identity differs")
                manifests_checked += 1
                pred_path = path / "predictions.csv"
                assert_true(digest(pred_path) == row.prediction_sha256, "Saved prediction file differs from frozen BA input")
                pred = pd.read_csv(pred_path, dtype={"seed": str})
                expected_target = source_meta[source_meta.subject == subject]
                pd.testing.assert_frame_equal(pred[check_cols].reset_index(drop=True), expected_target[check_cols].reset_index(drop=True), check_dtype=False)
                assert_true(len(pred) == 288 and (pred.model == model).all() and (pred.seed == row.seed).all(), "Prediction population/model/seed differs")
                probs = pred[["p_left", "p_right"]].to_numpy(float)
                assert_true(np.isfinite(probs).all() and (probs >= 0).all() and (probs <= 1).all(), "Saved prediction probability invalid")
                np.testing.assert_allclose(probs.sum(axis=1), 1, rtol=0, atol=1e-5)
                assert_true(np.array_equal(np.argmax(probs, axis=1) + 1, pred.predicted_label), "Saved prediction labels differ from probability argmax")
                y, yp = pred.label.to_numpy(), pred.predicted_label.to_numpy()
                assert_true(Counter(y.tolist()) == Counter({1: 144, 2: 144}), "Saved binary population is not class balanced")
                matrix = [int(((y == c) & (yp == p)).sum()) for c in (1, 2) for p in (1, 2)]
                ba = 0.5 * (matrix[0] / 144 + matrix[3] / 144)
                assert_true(matrix == json.loads(row.tn_fp_fn_tp) and abs(ba - row.balanced_accuracy) <= 1e-14, "Independent saved-prediction BA differs")
                bvalues.append(ba)
                prediction_rows += len(pred)
            summary_rows.append({"subject": subject, "model": model, "n_frozen_seeds": len(bvalues), "balanced_accuracy_mean": float(np.mean(bvalues)), "balanced_accuracy_min_seed": min(bvalues), "balanced_accuracy_max_seed": max(bvalues), "balanced_accuracy_sd_across_seeds": float(np.std(bvalues, ddof=1)) if len(bvalues) > 1 else np.nan, "seed_ids": ";".join(sorted(required_seeds)), "n_test_trials_per_seed": 288})
    assert_true(prediction_rows == 18144 and manifests_checked == 135, "Independent source-only archive coverage differs")
    return pd.DataFrame(summary_rows), {"saved_prediction_files_reverified": 63, "saved_prediction_rows_recomputed": prediction_rows, "source_only_fit_manifests_checked": manifests_checked, "n_people": 9, "target_fit_count_from_manifests": 0, "performance_source": "Q14-E001_binary_BNCI_source_LOSO", "metric_input_sha256": digest(metrics_path), "validator_input_sha256": digest(Q14 / "validation_report.json"), "new_decoder_fits": 0, "new_checkpoint_inference": 0}


def mean_or_nan(values) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return float(values.mean()) if len(values) else np.nan


def median_or_nan(values) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return float(np.median(values)) if len(values) else np.nan


def average_ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="stable")
    ranks = np.zeros(len(values), dtype=float)
    start = 0
    while start < len(values):
        stop = start + 1
        while stop < len(values) and values[order[stop]] == values[order[start]]:
            stop += 1
        ranks[order[start:stop]] = (start + 1 + stop) / 2
        start = stop
    return ranks


def spearman_manual(x, y) -> float:
    rx, ry = average_ranks(np.asarray(x)), average_ranks(np.asarray(y))
    rx, ry = rx - rx.mean(), ry - ry.mean()
    return float(np.dot(rx, ry) / np.sqrt(np.dot(rx, rx) * np.dot(ry, ry)))


def verify_aggregations(trials: pd.DataFrame, run_dir: Path, perf: pd.DataFrame) -> dict:
    checked = {}
    keys = ["subject", "session", "class_name", "channel", "band"]
    sessions = []
    for identity, group in trials.groupby(keys, sort=True, observed=True):
        sessions.append({**dict(zip(keys, identity)), "n_trials": len(group), "n_eligible": int(group.logratio_db.notna().sum()), "n_artifact_flagged": int(group.artifact_flagged.sum()), "mean_trial_logratio_db": mean_or_nan(group.logratio_db), "median_trial_logratio_db": median_or_nan(group.logratio_db), "mean_baseline_power_native_numeric_squared": mean_or_nan(group.baseline_power_native_numeric_squared), "mean_task_power_native_numeric_squared": mean_or_nan(group.task_power_native_numeric_squared), "ratio_unit": "dB"})
    session_frame = pd.DataFrame(sessions)
    compare_table(session_frame, run_dir / "subject_session_band_summary.csv", keys, checked)
    subject_rows = []
    subject_keys = ["subject", "class_name", "channel", "band"]
    for identity, group in session_frame.groupby(subject_keys, sort=True, observed=True):
        complete = set(group.session) == {"0train", "1test"} and group.mean_trial_logratio_db.notna().all()
        subject_rows.append({**dict(zip(subject_keys, identity)), "n_sessions_expected": 2, "n_sessions_available": int(group.mean_trial_logratio_db.notna().sum()), "n_trials": int(group.n_trials.sum()), "n_eligible": int(group.n_eligible.sum()), "n_artifact_flagged": int(group.n_artifact_flagged.sum()), "equal_session_mean_trial_logratio_db": mean_or_nan(group.mean_trial_logratio_db) if complete else np.nan, "equal_session_mean_of_trial_medians_db": mean_or_nan(group.median_trial_logratio_db) if complete else np.nan, "eligibility_reason": "eligible" if complete else "one_or_more_required_sessions_unavailable", "ratio_unit": "dB"})
    subjects = pd.DataFrame(subject_rows)
    compare_table(subjects, run_dir / "subject_band_summary.csv", subject_keys, checked)
    strata = []
    skeys = keys + ["artifact_flagged"]
    for identity, group in trials.groupby(skeys, sort=True, observed=True):
        strata.append({**dict(zip(skeys, identity)), "n_trials": len(group), "n_eligible": int(group.logratio_db.notna().sum()), "mean_trial_logratio_db": mean_or_nan(group.logratio_db), "median_trial_logratio_db": median_or_nan(group.logratio_db), "ratio_unit": "dB"})
    observed_strata = {tuple(row[k] for k in skeys) for row in strata}
    for identity in product(range(1, 10), ("0train", "1test"), CLASS.values(), CHANNELS, BANDS, (False, True)):
        if identity not in observed_strata:
            strata.append({**dict(zip(skeys, identity)), "n_trials": 0, "n_eligible": 0, "mean_trial_logratio_db": np.nan, "median_trial_logratio_db": np.nan, "ratio_unit": "dB"})
    compare_table(pd.DataFrame(strata), run_dir / "artifact_stratum_band_summary.csv", skeys, checked)
    paired_rows, laterality_rows = [], []
    for subject in range(1, 10):
        for band in BANDS:
            cell_values = {}
            cell_counts = {}
            for session in ("0train", "1test"):
                for hand in ("left_hand", "right_hand"):
                    group = trials[(trials.subject == subject) & (trials.band == band) & (trials.session == session) & (trials.class_name == hand) & trials.channel.isin(["C3", "C4"])]
                    c3 = group[group.channel == "C3"].set_index("sample_id").logratio_db
                    c4 = group[group.channel == "C4"].set_index("sample_id").logratio_db
                    assert_true(set(c3.index) == set(c4.index), "Unpaired hand trial identities")
                    c4 = c4.loc[c3.index]
                    valid = c3.notna() & c4.notna()
                    c3, c4 = c3[valid], c4[valid]
                    cell_values[(session, hand)] = {"C3": mean_or_nan(c3), "C4": mean_or_nan(c4)}
                    cell_counts[(session, hand)] = len(c3)
                    paired_rows.append({"subject": subject, "session": session, "class_name": hand, "band": band, "n_trials": len(group) // 2, "n_paired_eligible": len(c3), "C3_mean_trial_logratio_db": mean_or_nan(c3), "C4_mean_trial_logratio_db": mean_or_nan(c4), "C3_median_trial_logratio_db": median_or_nan(c3), "C4_median_trial_logratio_db": median_or_nan(c4)})
            for output_session in ("0train", "1test", "equal_session"):
                used_sessions = ("0train", "1test") if output_session == "equal_session" else (output_session,)
                required_cells = len(used_sessions) * 2
                present = sum(cell_counts[(s, h)] > 0 for s in used_sessions for h in ("left_hand", "right_hand"))
                complete = present == required_cells
                vals = {}
                for hand in ("left_hand", "right_hand"):
                    for channel in ("C3", "C4"):
                        vals[(hand, channel)] = mean_or_nan([cell_values[(s, hand)][channel] for s in used_sessions]) if complete else np.nan
                c3r, c4r, c4l, c3l = (vals[("right_hand", "C3")], vals[("right_hand", "C4")], vals[("left_hand", "C4")], vals[("left_hand", "C3")])
                laterality_rows.append({"subject": subject, "session": output_session, "band": band, "C3_right_mean_db": c3r, "C4_right_mean_db": c4r, "C4_left_mean_db": c4l, "C3_left_mean_db": c3l, "right_C3_minus_C4_db": c3r - c4r, "left_C4_minus_C3_db": c4l - c3l, "contralateral_mean_db": (c3r + c4l) / 2, "ipsilateral_mean_db": (c4r + c3l) / 2, "signed_laterality_db": (c3r - c4r + c4l - c3l) / 2, "n_hand_session_cells_expected": required_cells, "n_hand_session_cells_available": present, "n_paired_eligible_trials": sum(cell_counts[(s, h)] for s in used_sessions for h in ("left_hand", "right_hand")), "eligibility_reason": "eligible" if complete else "one_or_more_required_hand_sessions_unavailable", "ratio_unit": "dB"})
    compare_table(pd.DataFrame(paired_rows), run_dir / "subject_session_hand_pair_summary.csv", ["subject", "session", "class_name", "band"], checked)
    lat = pd.DataFrame(laterality_rows)
    compare_table(lat[lat.session != "equal_session"], run_dir / "subject_session_hand_laterality.csv", ["subject", "session", "band"], checked)
    lat = lat[lat.session == "equal_session"].reset_index(drop=True)
    compare_table(lat, run_dir / "subject_hand_laterality.csv", ["subject", "session", "band"], checked)
    compare_table(perf, run_dir / "frozen_subject_performance.csv", ["subject", "model"], checked)
    joined = lat.merge(perf, on="subject", validate="many_to_many")
    joined["primary_descriptive_context"] = joined.model == "BROAD_EEGNET"
    compare_table(joined, run_dir / "subject_physiology_performance.csv", ["subject", "band", "model"], checked)
    correlations = []
    for model in MODELS:
        for band in BANDS:
            data = joined[(joined.model == model) & (joined.band == band)].sort_values("subject")
            assert_true(len(data) == 9 and set(data.subject) == set(range(1, 10)), "Descriptive correlation omitted people")
            complete = data.signed_laterality_db.notna().all()
            reason = "eligible" if complete else "required_subject_descriptor_unavailable"
            rho = np.nan
            if complete:
                if data.signed_laterality_db.nunique() < 2 or data.balanced_accuracy_mean.nunique() < 2:
                    reason = "constant_descriptor_or_performance"
                else:
                    rho = spearman_manual(data.signed_laterality_db.to_numpy(), data.balanced_accuracy_mean.to_numpy())
            correlations.append({"model": model, "band": band, "n_subjects_expected": 9, "n_subjects_with_descriptor": int(data.signed_laterality_db.notna().sum()), "spearman_rho": rho, "primary_descriptive_context": model == "BROAD_EEGNET", "eligibility_reason": reason, "p_value_computed": False})
    association = pd.DataFrame(correlations)
    compare_table(association, run_dir / "descriptive_associations.csv", ["model", "band"], checked)
    summary = read_json(run_dir / "summary.json")
    assert_true(summary["new_decoder_fits"] == 0 and summary["new_checkpoint_inference"] == 0, "Summary decoder operations changed")
    # Recompute all 24 central population rows and both descriptor population rows.
    central = subjects[subjects.channel.isin(CENTRAL)]
    population = []
    pkeys = ["class_name", "channel", "band"]
    for identity, group in central.groupby(pkeys, observed=True, sort=True):
        values = group.equal_session_mean_trial_logratio_db.to_numpy(float)
        values = values[np.isfinite(values)]
        population.append({**dict(zip(pkeys, identity)), "n_subjects": len(values), "equal_subject_mean_db": mean_or_nan(values), "between_subject_sd_db": float(np.std(values, ddof=1)), "minimum_subject_mean_db": float(values.min()), "maximum_subject_mean_db": float(values.max())})
    e = pd.DataFrame(population).sort_values(pkeys).reset_index(drop=True)
    a = pd.DataFrame(summary["channel_population_summary"]).sort_values(pkeys).reset_index(drop=True)
    for column in e:
        if column in pkeys:
            assert_true(e[column].tolist() == a[column].tolist(), "Summary central identity changed")
        else:
            np.testing.assert_allclose(e[column], a[column], rtol=0, atol=SUMMARY_ATOL)
    for item in summary["laterality_population_summary"]:
        group = lat[lat.band == item["band"]]
        value = group.signed_laterality_db
        comparisons = {"n_subjects": int(value.notna().sum()), "mean_signed_laterality_db": mean_or_nan(value), "minimum_signed_laterality_db": value.min(), "maximum_signed_laterality_db": value.max(), "mean_contralateral_db": mean_or_nan(group.contralateral_mean_db), "mean_ipsilateral_db": mean_or_nan(group.ipsilateral_mean_db)}
        for name, val in comparisons.items():
            np.testing.assert_allclose(item[name], val, rtol=0, atol=SUMMARY_ATOL)
    assert_true(summary["counts"]["eligibility_reason_row_counts"] == dict(Counter(trials.eligibility_reason)), "Summary invalid/eligible counts differ")
    return {"table_checks": checked, "full_aggregation_absolute_tolerance": SUMMARY_ATOL, "population_rows_recomputed": len(population), "laterality_rows_recomputed": 54, "all_six_descriptive_correlations": json.loads(association.to_json(orient="records", double_precision=15)), "paired_trial_laterality_verified": True, "equal_session_equal_person_aggregation_verified": True, "p_values_computed": False}


def write_report(report: dict, run_dir: Path) -> None:
    (run_dir / "independent_validation.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    lines = ["# Independent Q16 validation", "", f"Status: **{report['status']}**", "", "No decoder fitting or new checkpoint inference was performed.", ""]
    if report.get("passed"):
        raw = report["raw_replay"]
        lines.extend([f"All 18 original files matched their frozen SHA-256 and byte counts. All 5,184 four-class trial identities and 228,096 channel-band rows were checked. The independent FFT calculation replayed all 31,104 C3/Cz/C4 trial-band pairs.", "", f"Maximum relative power difference: {raw['maximum_relative_power_difference']:.3g}; maximum absolute dB difference: {raw['maximum_absolute_logratio_difference_db']:.3g} dB. Tolerances were fixed at 1e-10 relative power and 1e-10 absolute dB to accommodate float64 detrending/FFT round-off; no fitted tolerance or arbitrary power epsilon was used.", "", "All session, equal-session person, paired-channel laterality, artifact-stratum, and six descriptive correlation tables were recomputed. All 63 Q14 saved prediction files, 18,144 prediction rows, and 135 source-only fit manifests were checked without loading models or recomputing predictions.", "", "This validation supports the fixed descriptive BNCI estimator and its output arithmetic. It does not prove absolute voltage calibration, resting-state recovery, an external physiological replication, a cortical mechanism, decoder causality, or inferential significance of nine-person correlations."])
    else:
        lines.extend([f"Blocking reason: `{report.get('error', 'unspecified')}`", "", "Do not use unverified Q16 results in the manuscript."])
    (run_dir / "independent_validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Independent raw PSD replay after the committed freeze")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--run-dir", type=Path, default=RUN)
    parser.add_argument("--freeze-commit")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"status": "prepared_not_executed", "raw_power_computed": False, "new_decoder_fits": 0, "new_checkpoint_inference": 0}))
        return
    if not args.data_dir or not args.freeze_commit:
        parser.error("--execute requires --data-dir and the full committed --freeze-commit SHA")
    report = {"schema_version": 1, "analysis_id": "Q16-P001-BNCI-20261006", "started_at_utc": datetime.now(timezone.utc).isoformat(), "passed": False, "status": "validation_in_progress", "independent_validator": record(Path(__file__)), "software": {"python": sys.version, "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__, "platform": platform.platform()}, "command": sys.argv, "new_decoder_fits": 0, "new_checkpoint_inference": 0}
    try:
        report["freeze_and_hash_gate"] = verify_gate(args.freeze_commit, args.run_dir)
        trials = pd.read_csv(args.run_dir / "trial_power.csv.gz")
        report["raw_replay"] = verify_raw_and_central(args.data_dir, trials)
        perf, receipt = verify_performance(pd.read_csv(Q8))
        report["saved_performance_replay"] = receipt
        report["aggregations"] = verify_aggregations(trials, args.run_dir, perf)
        report.update({"passed": True, "status": "independent_raw_and_saved_evidence_validation_passed"})
    except Exception as exc:
        report.update({"status": "independent_validation_failed", "error": f"{type(exc).__name__}: {exc}"})
        report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_report(report, args.run_dir)
        raise
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_report(report, args.run_dir)
    print(json.dumps({"status": report["status"], "passed": True, "central_pairs": report["raw_replay"]["manual_central_channel_band_pairs_replayed"], "maximum_relative_power_difference": report["raw_replay"]["maximum_relative_power_difference"], "maximum_absolute_logratio_difference_db": report["raw_replay"]["maximum_absolute_logratio_difference_db"], "new_decoder_fits": 0, "new_checkpoint_inference": 0}))


if __name__ == "__main__":
    main()
