#!/usr/bin/env python3
"""Four frozen post hoc contrasts; reads saved participant metrics only.

This is editorial-stage supplementary arithmetic, not EEG model execution.
Run once after review of evidence/review2_posthoc_plan.json. Existing reports
are not overwritten, and the original primary/secondary analyses are untouched.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import platform
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import scipy
from scipy import stats


PLAN_SHA256 = "8ad283ea9bbcf65371219ecb5d5a3ff1e2b2a115a37388c6ed0093577ef40048"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(ok: bool, text: str) -> None:
    if not ok:
        raise ValueError(text)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    started = now()
    root = Path(__file__).resolve().parents[1]
    repo = root.parents[1]
    plan_path = root / "evidence/review2_posthoc_plan.json"
    plan_bytes = plan_path.read_bytes()
    require(sha(plan_bytes) == PLAN_SHA256, "Frozen post hoc plan SHA differs")
    plan = json.loads(plan_bytes)
    receipt_path = root / "evidence/review2_posthoc_receipt.json"
    comparisons_path = root / "tables/review2_posthoc_comparisons.csv"
    differences_path = root / "review2_posthoc_participant_differences.csv"
    for path in (receipt_path, comparisons_path, differences_path):
        require(not path.exists(), "Existing output retained; no repeat execution: " + str(path))
    archive_path = repo / plan["input_archive"]["path"]
    raw = archive_path.read_bytes()
    require(len(raw) == plan["input_archive"]["bytes"], "Archive length differs")
    require(sha(raw) == plan["input_archive"]["sha256"], "Archive SHA differs")
    tables = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for name, expected in plan["input_members"].items():
            data = archive.read(name)
            require(len(data) == expected["bytes"] and sha(data) == expected["sha256"],
                    "Member length/SHA differs: " + name)
            tables[name] = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
    expected_subjects = set(plan["expected_subjects"])
    require(len(expected_subjects) == 85, "Expected participant count differs")
    summaries, differences = [], []
    for contrast in plan["contrasts"]:
        by_level = {}
        for level in (contrast["higher_source_level"], contrast["lower_source_level"]):
            rows = [r for r in tables[contrast["member"]]
                    if r["source_level"] == level and r["pipeline"] == contrast["pipeline"]
                    and r["selector"] == contrast["selector"]]
            require(len(rows) == 85 and len({r["subject"] for r in rows}) == 85,
                    "Missing or duplicate participant: " + contrast["id"] + "/" + level)
            require({r["subject"] for r in rows} == expected_subjects,
                    "Unexpected participant identities")
            for row in rows:
                require(row["dataset"] == "dreyer" and int(row["n_seeds"]) == 3,
                        "Dataset/seed-count identity differs")
                value = float(row[contrast["metric"]])
                require(np.isfinite(value) and 0 <= value <= 1, "Nonfinite/out-of-range metric")
            by_level[level] = {row["subject"]: row for row in rows}
        higher = by_level[contrast["higher_source_level"]]
        lower = by_level[contrast["lower_source_level"]]
        subjects = sorted(expected_subjects)
        for subject in subjects:
            require(higher[subject]["trial_manifest_sha256"] == lower[subject]["trial_manifest_sha256"],
                    "Paired trial manifest differs: " + subject)
        high = np.array([float(higher[s][contrast["metric"]]) for s in subjects])
        low = np.array([float(lower[s][contrast["metric"]]) for s in subjects])
        diff = 100.0 * (high - low)
        n = len(diff)
        mean = float(np.mean(diff))
        sd = float(np.std(diff, ddof=1))
        se = sd / np.sqrt(n)
        test = stats.ttest_1samp(diff, popmean=0, alternative="two-sided")
        halfwidth = float(stats.t.ppf(0.975, n - 1) * se)
        summary = {
            "analysis_class": "post_hoc_after_outcomes_known",
            "contrast_id": contrast["id"], "label": contrast["label"],
            "pipeline": contrast["pipeline"], "selector": contrast["selector"],
            "higher_source_level": contrast["higher_source_level"],
            "lower_source_level": contrast["lower_source_level"],
            "metric": contrast["metric"], "n_participants": n, "n_seeds_per_metric": 3,
            "higher_mean_percent": float(np.mean(high) * 100),
            "lower_mean_percent": float(np.mean(low) * 100),
            "difference_pp": mean, "sd_difference_pp": sd, "se_difference_pp": float(se),
            "ci95_pointwise_low_pp": mean - halfwidth,
            "ci95_pointwise_high_pp": mean + halfwidth,
            "t_statistic": float(test.statistic), "df": n - 1,
            "p_raw_two_sided": float(test.pvalue), "p_holm_four_posthoc": None,
            "n_improved": int(np.count_nonzero(diff > 0)),
            "n_unchanged": int(np.count_nonzero(diff == 0)),
            "n_declined": int(np.count_nonzero(diff < 0)),
            "ci_adjusted_for_multiplicity": False,
        }
        summaries.append(summary)
        for index, subject in enumerate(subjects):
            differences.append({
                "contrast_id": contrast["id"], "subject": subject,
                "higher_source_level": contrast["higher_source_level"],
                "lower_source_level": contrast["lower_source_level"],
                "pipeline": contrast["pipeline"], "selector": contrast["selector"],
                "metric": contrast["metric"], "n_seeds": 3,
                "higher_metric_proportion": float(high[index]),
                "lower_metric_proportion": float(low[index]),
                "difference_pp": float(diff[index]),
                "trial_manifest_sha256": higher[subject]["trial_manifest_sha256"],
            })
    require(len(summaries) == 4 and len(differences) == 340, "Incomplete post hoc family")
    # Holm's monotone step-down adjusted p values, restricted to this new family.
    order = sorted(range(4), key=lambda i: summaries[i]["p_raw_two_sided"])
    previous = 0.0
    for rank, index in enumerate(order):
        previous = max(previous, min(1.0, (4 - rank) * summaries[index]["p_raw_two_sided"]))
        summaries[index]["p_holm_four_posthoc"] = previous
    comparisons_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv(comparisons_path, summaries)
    write_csv(differences_path, differences)
    receipt = {
        "schema_version": 1, "analysis_id": plan["analysis_id"],
        "status": "FOUR_POSTHOC_SAVED_METRIC_COMPARISONS_COMPLETE",
        "started_at_utc": started, "completed_at_utc": now(),
        "classification": plan["classification"],
        "plan_sha256": PLAN_SHA256, "script_sha256": sha(Path(__file__).read_bytes()),
        "source_archive": plan["input_archive"], "source_members": plan["input_members"],
        "code_checkout_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
        "execution_environment": {"python": platform.python_version(), "executable": sys.executable,
                                  "numpy": np.__version__, "scipy": scipy.__version__},
        "n_contrasts": 4, "n_paired_participants_per_contrast": 85,
        "n_participant_difference_rows": 340,
        "hypothesis_tests_performed": 4,
        "original_primary_or_secondary_family_changed": False,
        "new_model_fits": 0, "new_model_forwards": 0, "raw_eeg_read": False,
        "bootstrap_recomputed": False,
        "results": summaries,
        "outputs": {str(path.relative_to(root)): {"bytes": path.stat().st_size,
                    "sha256": sha(path.read_bytes())} for path in (comparisons_path, differences_path)},
        "interpretation_boundary": "Post hoc after outcomes were known. Pointwise CIs and the separate four-test Holm family do not convert these contrasts to prospective confirmation; no neural-vs-CSP superiority or equivalence test was performed.",
    }
    with receipt_path.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    for summary in summaries:
        print(json.dumps(summary, ensure_ascii=False, allow_nan=False))
    print(json.dumps({"receipt": str(receipt_path), "sha256": sha(receipt_path.read_bytes())}))


if __name__ == "__main__":
    main()
