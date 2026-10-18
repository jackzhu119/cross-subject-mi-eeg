#!/usr/bin/env python3
"""Complete post hoc source-expansion inventory from saved metrics only.

No model, raw signal, hypothesis test, confidence interval or selector search.
The complete scope is hashed before calculation; no existing output is replaced.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import math
import platform
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np

PLAN_SHA256 = "defe2e1d50892f68108a3abd29f065479c9cbe7b16f332c2c130c2298c14dba6"


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def csv_write(path: Path, rows: list[dict]) -> None:
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    started = now()
    root = Path(__file__).resolve().parents[1]
    repo = root.parents[1]
    plan_file = root / "evidence/source_expansion_inventory_plan.json"
    require(sha(plan_file.read_bytes()) == PLAN_SHA256, "Frozen descriptive plan differs")
    plan = json.loads(plan_file.read_bytes())
    output_names = plan["outputs"]
    require(all(not (root / name).exists() for name in output_names),
            "Existing inventory output retained; refuse repeat execution")
    raw = (repo / plan["input_archive"]["path"]).read_bytes()
    require(len(raw) == plan["input_archive"]["bytes"] and
            sha(raw) == plan["input_archive"]["sha256"], "Original archive differs")
    data = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for name, identity in plan["input_members"].items():
            value = archive.read(name)
            require(len(value) == identity["bytes"] and sha(value) == identity["sha256"],
                    "Input member differs: " + name)
            data[name] = value
    source = json.loads(data["provenance/study.json"])
    frozen = json.loads(data["results/selection_freeze.json"])
    require(source["updates_per_epoch"] == 128, "Update count differs")
    levels, pipelines = plan["source_levels"], plan["neural_pipelines"]
    selectors, metrics = plan["neural_selectors"], plan["metrics"]
    subjects = sorted(plan["expected_subjects"])
    require(len(set(subjects)) == 85, "Expected participant set differs")
    trial_identities = {}

    def identity(row: dict) -> None:
        subject = row["subject"]
        require(row["dataset"] == "dreyer" and subject in subjects,
                "Unexpected dataset/participant")
        manifest = row["trial_manifest_sha256"]
        require(len(manifest) == 64 and all(c in "0123456789abcdef" for c in manifest),
                "Invalid saved trial manifest hash")
        if subject in trial_identities:
            require(manifest == trial_identities[subject], "Saved participant trial identity differs")
        else:
            trial_identities[subject] = manifest
        for metric in metrics:
            require(math.isfinite(float(row[metric])) and 0 <= float(row[metric]) <= 1,
                    "Nonfinite or out-of-range endpoint")

    def participant_table(name: str, expected_pipelines: list[str],
                          expected_selectors: list[str]) -> dict:
        rows = list(csv.DictReader(io.StringIO(data[name].decode("utf-8"))))
        require(len(rows) == len(levels) * len(expected_pipelines) * len(expected_selectors) * 85,
                "Participant table row count differs")
        table = {}
        for row in rows:
            identity(row)
            require(int(row["n_seeds"]) == 3, "Saved metric is not a three-seed mean")
            require(row["source_level"] in levels and row["pipeline"] in expected_pipelines
                    and row["selector"] in expected_selectors, "Unexpected condition")
            key = (row["source_level"], row["pipeline"], row["selector"], row["subject"])
            require(key not in table, "Duplicate saved participant condition")
            table[key] = row
        return table

    neural = participant_table("results/per_subject_metrics.csv", pipelines, selectors)
    csp = participant_table("results/csp_per_subject_metrics.csv", ["CSP_LDA"], ["fixed"])
    eps = plan["direction_classification"]["epsilon_pp"]

    def direction(value: float) -> str:
        return "positive" if value > eps else "negative" if value < -eps else "numerical_zero"

    def values(table: dict, level: str, pipeline: str, selector: str, metric: str) -> np.ndarray:
        return np.array([float(table[(level, pipeline, selector, s)][metric]) for s in subjects],
                        dtype=np.float64)

    inventory = []
    for table, pipe_list, rule_list in ((neural, pipelines, selectors),
                                        (csp, ["CSP_LDA"], ["fixed"])):
        for high_level, low_level in plan["expansion_comparisons"]:
            for pipeline in pipe_list:
                for selector in rule_list:
                    for metric in metrics:
                        high = values(table, high_level, pipeline, selector, metric)
                        low = values(table, low_level, pipeline, selector, metric)
                        difference = float(np.mean(100 * (high - low)))
                        is_neural = table is neural
                        high_epoch = frozen["selections"][high_level][pipeline]["epochs"][selector] if is_neural else None
                        low_epoch = frozen["selections"][low_level][pipeline]["epochs"][selector] if is_neural else None
                        if selector == "fixed20":
                            require(high_epoch == low_epoch == 20, "fixed20 duration differs")
                        inventory.append({
                            "analysis_class": "post_hoc_complete_descriptive_inventory",
                            "higher_source_level": high_level, "lower_source_level": low_level,
                            "pipeline": pipeline, "selector": selector, "metric": metric,
                            "n_participants": 85, "n_seeds_per_participant_metric": 3,
                            "higher_mean_percent": float(np.mean(high) * 100),
                            "lower_mean_percent": float(np.mean(low) * 100),
                            "difference_pp": difference, "direction": direction(difference),
                            "higher_selected_epoch": high_epoch, "lower_selected_epoch": low_epoch,
                            "higher_selected_updates": high_epoch * 128 if is_neural else None,
                            "lower_selected_updates": low_epoch * 128 if is_neural else None,
                            "hypothesis_test_performed": False,
                        })
    require(len(inventory) == 68, "Incomplete descriptive inventory")
    seed_rows = list(csv.DictReader(io.StringIO(data["results/external_subject_seed_metrics.csv"].decode("utf-8"))))
    seed_table = {}
    seeds = plan["fixed20_seed_scope"]["seeds"]
    for row in seed_rows:
        if row["selector"] != "fixed20":
            continue
        identity(row)
        seed = int(row["seed"])
        require(seed in seeds and row["pipeline"] in pipelines and row["source_level"] in levels,
                "Unexpected fixed20 seed condition")
        require(int(row["n_trials"]) == 80 and int(row["n_left"]) == int(row["n_right"]) == 40,
                "Saved seed metric trial counts differ")
        left, right = float(row["recall_left"]), float(row["recall_right"])
        require(abs(float(row["min_recall"]) - min(left, right)) <= 1e-12 and
                abs(float(row["ba"]) - (left + right) / 2) <= 1e-12,
                "Saved seed endpoint arithmetic differs")
        key = (row["source_level"], row["pipeline"], seed, row["subject"])
        require(key not in seed_table, "Duplicate fixed20 seed-participant")
        seed_table[key] = row
    require(len(seed_table) == 1530, "Missing fixed20 seed-participant rows")
    seed_means, seed_differences = [], []
    for level in levels:
        for pipeline in pipelines:
            require(frozen["selections"][level][pipeline]["epochs"]["fixed20"] == 20,
                    "Frozen fixed20 checkpoint differs")
            for seed in seeds:
                for metric in metrics:
                    value = np.array([float(seed_table[(level, pipeline, seed, s)][metric])
                                      for s in subjects])
                    seed_means.append({"source_level": level, "pipeline": pipeline,
                                       "selector": "fixed20", "seed": seed, "metric": metric,
                                       "n_participants": 85, "selected_epoch": 20,
                                       "selected_updates": 2560,
                                       "mean_percent": float(np.mean(value) * 100)})
    for high_level, low_level in plan["expansion_comparisons"]:
        for pipeline in pipelines:
            for seed in seeds:
                for metric in metrics:
                    high = np.array([float(seed_table[(high_level, pipeline, seed, s)][metric])
                                     for s in subjects])
                    low = np.array([float(seed_table[(low_level, pipeline, seed, s)][metric])
                                    for s in subjects])
                    difference = float(np.mean(100 * (high - low)))
                    seed_differences.append({"higher_source_level": high_level,
                        "lower_source_level": low_level, "pipeline": pipeline,
                        "selector": "fixed20", "seed": seed, "metric": metric,
                        "n_participants": 85, "higher_selected_updates": 2560,
                        "lower_selected_updates": 2560, "difference_pp": difference,
                        "direction": direction(difference), "hypothesis_test_performed": False})
    require(len(seed_means) == 36 and len(seed_differences) == 24, "Incomplete seed inventory")
    # Verify saved three-seed means against the complete fixed20 seed records.
    max_seed_mean_difference = 0.0
    for level in levels:
        for pipeline in pipelines:
            for subject in subjects:
                for metric in metrics:
                    recomputed = float(np.mean([float(seed_table[(level, pipeline, seed, subject)][metric])
                                                for seed in seeds]))
                    stored = float(neural[(level, pipeline, "fixed20", subject)][metric])
                    delta = abs(recomputed - stored)
                    max_seed_mean_difference = max(max_seed_mean_difference, delta)
                    require(delta <= 1e-12, "Archived participant/seed average differs")
    groups = []
    for high_level, low_level in plan["expansion_comparisons"]:
        for pipeline in pipelines + ["CSP_LDA"]:
            for metric in metrics:
                cells = [r for r in inventory if r["higher_source_level"] == high_level
                         and r["pipeline"] == pipeline and r["metric"] == metric]
                groups.append({"higher_source_level": high_level,
                    "lower_source_level": low_level, "pipeline": pipeline, "metric": metric,
                    "n_rules": len(cells),
                    "n_positive": sum(r["direction"] == "positive" for r in cells),
                    "n_negative": sum(r["direction"] == "negative" for r in cells),
                    "n_numerical_zero": sum(r["direction"] == "numerical_zero" for r in cells),
                    "min_difference_pp": min(r["difference_pp"] for r in cells),
                    "max_difference_pp": max(r["difference_pp"] for r in cells)})
    seed_summary = []
    for high_level, low_level in plan["expansion_comparisons"]:
        for pipeline in pipelines:
            for metric in metrics:
                cells = [r for r in seed_differences if r["higher_source_level"] == high_level
                         and r["pipeline"] == pipeline and r["metric"] == metric]
                seed_summary.append({"higher_source_level": high_level,
                    "lower_source_level": low_level, "pipeline": pipeline, "metric": metric,
                    "n_seeds": 3, "n_positive": sum(r["direction"] == "positive" for r in cells),
                    "n_negative": sum(r["direction"] == "negative" for r in cells),
                    "n_numerical_zero": sum(r["direction"] == "numerical_zero" for r in cells),
                    "min_seed_difference_pp": min(r["difference_pp"] for r in cells),
                    "max_seed_difference_pp": max(r["difference_pp"] for r in cells)})
    (root / "tables").mkdir(exist_ok=True)
    for name, rows in zip(output_names[:3], (inventory, seed_means, seed_differences), strict=True):
        csv_write(root / name, rows)
    receipt = {"schema_version": 1, "analysis_id": plan["analysis_id"],
        "status": "COMPLETE_68_CELL_DESCRIPTIVE_INVENTORY_NO_NEW_TESTS",
        "started_at_utc": started, "completed_at_utc": now(),
        "classification": plan["classification"], "plan_sha256": PLAN_SHA256,
        "script_sha256": sha(Path(__file__).read_bytes()),
        "input_archive": plan["input_archive"], "input_members": plan["input_members"],
        "code_checkout_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
        "runtime": {"python": platform.python_version(), "executable": sys.executable,
                    "numpy": np.__version__},
        "rows": {"inventory": 68, "fixed20_seed_means": 36, "fixed20_seed_differences": 24},
        "direction_classification": plan["direction_classification"],
        "complete_rule_direction_summaries": groups,
        "fixed20_cells": [r for r in inventory if r["selector"] == "fixed20"],
        "fixed20_seed_direction_summaries": seed_summary,
        "max_absolute_fixed20_saved_seed_mean_difference_proportion": max_seed_mean_difference,
        "all_inventory_rows_retained": True, "new_hypothesis_tests": 0,
        "new_confidence_intervals": 0, "new_bootstrap_analyses": 0,
        "new_model_fits": 0, "new_model_forwards": 0, "raw_eeg_read": False,
        "original_primary_secondary_posthoc_outputs_modified": False,
        "reporting_boundary": plan["reporting_policy"],
        "outputs": {name: {"bytes": (root / name).stat().st_size,
                    "sha256": sha((root / name).read_bytes())} for name in output_names[:3]}}
    with (root / output_names[3]).open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"], "rows": receipt["rows"],
        "fixed20_cells": receipt["fixed20_cells"], "rule_direction_summaries": groups,
        "fixed20_seed_direction_summaries": seed_summary}, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
