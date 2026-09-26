"""Audit published Q14-R2 predictions without raw EDFs or a GPU.

This is deliberately narrower than q14_r2_validate.py. A successful result
does not establish EDF reconstruction, runtime custody, or scientific pass.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from scripts.q14_r2_numeric import assert_aggregate_matches_subjects

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / "results" / "Q14-E002R2" / "external"
CONFIG = ROOT / "research_runs" / "Q14-E001" / "CONFIG.json"
DEEP = ("BROAD_EEGNET", "MU_BETA_SHARED")
SHALLOW = "CSP4_LDA"


def _verify_published_sha256(path: Path, expected: str) -> str:
    """Verify Linux-published bytes, allowing Git's Windows CRLF checkout only."""

    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() == expected:
        return "raw_bytes"
    # The repository has no text attributes and some Windows installations
    # checkout tracked LF CSVs as CRLF. This does not change the Git blob.
    if (
        data.count(b"\r\n") == data.count(b"\n")
        and data.count(b"\r\n") > 0
        and hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() == expected
    ):
        return "git_crlf_checkout_normalized_to_published_lf"
    raise AssertionError(f"Published artifact hash mismatch: {path}")


def audit(external: Path = EXTERNAL) -> dict:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    receipt = json.loads((external / "completion_receipt.json").read_text(encoding="utf-8"))
    if receipt["n_subjects"] != 109 or receipt["external_target_fit_count"] != 0:
        raise AssertionError("Q14-R2 completion population or fit count changed")
    aggregate_path = external / "predictions.csv"
    aggregate_hash_mode = _verify_published_sha256(
        aggregate_path, receipt["aggregate_predictions_sha256"]
    )

    frames = []
    metrics = []
    expected_arms = {(model, str(seed)) for model in DEEP for seed in config["final_seeds"]}
    expected_arms.add((SHALLOW, "deterministic"))
    for subject in range(1, 110):
        folder = external / f"subject_{subject:03d}"
        subject_receipt = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
        path = folder / "predictions.csv"
        _verify_published_sha256(path, subject_receipt["predictions_sha256"])
        frame = pd.read_csv(path)
        if (
            len(frame) != subject_receipt["n_prediction_rows"]
            or len(frame) != 7 * subject_receipt["n_trials"]
            or set(frame["subject"]) != {subject}
        ):
            raise AssertionError(f"Subject row inventory mismatch: S{subject:03d}")
        actual_arms = set(zip(frame["model"], frame["seed"].astype(str)))
        if actual_arms != expected_arms:
            raise AssertionError(f"Frozen model/seed coverage mismatch: S{subject:03d}")
        frames.append(frame)
        first_trial_ids = None
        for model, seed in sorted(expected_arms):
            arm = frame.loc[(frame["model"] == model) & (frame["seed"].astype(str) == seed)]
            trial_ids = list(zip(arm["sample_id"], arm["run"], arm["trial"], arm["label"]))
            if len(arm) != subject_receipt["n_trials"] or len(set(trial_ids)) != len(trial_ids):
                raise AssertionError(f"Arm trial count/identity mismatch: S{subject:03d}/{model}")
            if first_trial_ids is None:
                first_trial_ids = trial_ids
            elif trial_ids != first_trial_ids:
                raise AssertionError(f"Unequal target trials between arms: S{subject:03d}")
            probabilities = arm[["p_left", "p_right"]].to_numpy(dtype=float)
            if (
                not np.isfinite(probabilities).all()
                or (probabilities < 0).any()
                or (probabilities > 1).any()
                or not np.allclose(probabilities.sum(axis=1), 1, rtol=0, atol=1e-5)
                or not np.array_equal(np.argmax(probabilities, axis=1) + 1, arm["predicted_label"])
            ):
                raise AssertionError(f"Invalid probabilities or decision: S{subject:03d}/{model}")
            label = arm["label"].to_numpy()
            prediction = arm["predicted_label"].to_numpy()
            if set(label) != {1, 2}:
                raise AssertionError(f"Incomplete left/right labels: S{subject:03d}")
            ba = float(np.mean([(prediction[label == klass] == klass).mean() for klass in (1, 2)]))
            metrics.append({"subject": subject, "model": model, "seed": seed, "ba": ba})

    reconstructed = pd.concat(frames, ignore_index=True)
    aggregate = pd.read_csv(aggregate_path)
    assert_aggregate_matches_subjects(reconstructed, aggregate)
    if len(aggregate) != receipt["n_prediction_rows"]:
        raise AssertionError("Aggregate prediction count mismatch")
    table = pd.DataFrame(metrics).groupby(["subject", "model"], as_index=False)["ba"].mean()
    wide = table.pivot(index="subject", columns="model", values="ba")
    if wide.shape != (109, 3) or wide.isna().any().any():
        raise AssertionError("Incomplete subject-level BA table")
    difference = (wide["MU_BETA_SHARED"] - wide["BROAD_EEGNET"]).to_numpy()
    rng = np.random.default_rng(20260924)
    bootstrap = difference[rng.integers(0, 109, size=(20000, 109))].mean(axis=1)
    positive = int((difference > 0).sum())
    negative = int((difference < 0).sum())
    return {
        "status": "published_artifacts_numeric_audit_only",
        "full_edf_independent_validation": "pending_cloud_raw_data_and_runtime",
        "n_subjects": len(wide),
        "n_prediction_rows": len(aggregate),
        "n_trials": len(aggregate) // 7,
        "mean_subject_ba": {model: float(wide[model].mean()) for model in (*DEEP, SHALLOW)},
        "primary_mean_paired_ba_difference": float(difference.mean()),
        "subject_bootstrap_95_ci": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
        "positive_subjects": positive,
        "negative_subjects": negative,
        "tied_subjects": int((difference == 0).sum()),
        "exact_sign_test_p_excluding_ties": float(binomtest(positive, positive + negative).pvalue),
        "aggregate_predictions_sha256": receipt["aggregate_predictions_sha256"],
        "aggregate_checkout_hash_mode": aggregate_hash_mode,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2, sort_keys=True))
