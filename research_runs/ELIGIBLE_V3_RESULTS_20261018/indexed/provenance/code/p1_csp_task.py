"""Orchestrate separately reported, fixed conventional source-only baselines."""
from __future__ import annotations

import csv
import gzip
import os
from pathlib import Path

from p1_common import atomic_json, canonical_hash, read_json, sha256_file
from p1_csp import fit, load_model, predict, save_model


def enabled(config):
    return config.get("traditional_baseline", {}).get("enabled", False)


def fit_baselines(config, reg, sources, freeze, run, identity, update_status):
    if not enabled(config):
        return None
    rows = []
    for level, keys in reg["levels"].items():
        people = {key: sources[key] for key in keys}
        hashes = {key: person["input_sha256"] for key, person in people.items()}
        if hashes != {key: freeze["source_input_hashes"][key] for key in keys}:
            raise ValueError("CSP source inputs differ from the source selection freeze")
        for seed in config["final_seeds"]:
            update_status("FIXED_CSP_SOURCE_TRAINING", trajectory=f"{level}/CSP_LDA/seed{seed}")
            path = Path(run)/"checkpoints/traditional"/level/f"seed_{seed}.npz"
            if path.exists():
                model = load_model(path)
                if model.metadata["seed"] != seed or model.metadata["source_input_hashes"] != hashes:
                    raise ValueError("Existing CSP model uses different source data or seed")
                if model.metadata["csp_module_sha256"] != sha256_file(Path(__file__).with_name("p1_csp.py")):
                    raise ValueError("Existing CSP implementation changed")
                record = {"path": str(path), "sha256": sha256_file(path)}
            else:
                model = fit(people, seed=seed)
                saved = save_model(model, path)
                record = {"path": saved["path"], "sha256": saved["sha256"]}
            rows.append({**record, "source_level": level, "seed": seed, "source_input_hashes": hashes,
                         "source_only": True, "target_fits": 0})
    manifest = {"source_only": True, "fits": rows, "n_conventional_fits": len(rows),
                "execution_identity": identity, "source_freeze_sha256": freeze["freeze_sha256"]}
    manifest["manifest_sha256"] = canonical_hash(manifest)
    path = Path(run)/"results/csp_fit_manifest.json"
    if path.exists() and read_json(path) != manifest:
        raise ValueError("CSP source fit manifest changed; use a separate run directory")
    atomic_json(path, manifest)
    return manifest


def require_baselines(config, reg, freeze, run):
    if not enabled(config):
        return None
    manifest = read_json(Path(run)/"results/csp_fit_manifest.json")
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if (canonical_hash(body) != manifest["manifest_sha256"] or not manifest["source_only"]
            or manifest["source_freeze_sha256"] != freeze["freeze_sha256"]
            or manifest["execution_identity"] != freeze["execution_identity"]):
        raise ValueError("Conventional models require the same frozen source-only execution")
    expected = {(level, seed) for level in reg["levels"] for seed in config["final_seeds"]}
    seen = set()
    for row in manifest["fits"]:
        key = (row["source_level"], row["seed"])
        if key not in expected or key in seen:
            raise ValueError("Duplicate or unexpected conventional fit")
        seen.add(key)
        expected_path = Path(run)/"checkpoints/traditional"/key[0]/f"seed_{key[1]}.npz"
        if Path(row["path"]).resolve() != expected_path.resolve() or sha256_file(expected_path) != row["sha256"]:
            raise ValueError("A conventional model differs from its frozen file")
        hashes = {person: freeze["source_input_hashes"][person] for person in reg["levels"][key[0]]}
        model = load_model(expected_path)
        if (row["source_input_hashes"] != hashes or model.metadata["source_input_hashes"] != hashes
                or model.metadata["seed"] != key[1] or model.metadata["target_fits"] != 0
                or not row["source_only"] or row["target_fits"] != 0):
            raise ValueError("Conventional model has an unexpected source population")
    if seen != expected or manifest["n_conventional_fits"] != len(expected):
        raise ValueError("All conventional source fits must complete before target access")
    return manifest


def evaluate_baselines(config, reg, targets, freeze, run, update_status):
    if not enabled(config):
        return None
    # Import lazily to keep the source-data fitting module independent of targets.
    from p1_runner import require_source_freeze, write_csv
    from p1_select import prediction_metrics, paired_statistics
    require_source_freeze(run, freeze, config)
    manifest = require_baselines(config, reg, freeze, run)
    if len(targets) != config["target"]["subjects"]:
        raise ValueError("Unexpected external population for the conventional comparator")
    path = Path(run)/"results/csp_external_predictions.csv.gz"
    temporary = path.with_suffix(".gz.tmp")
    metrics, n_predictions = [], 0
    fields = ["source_level", "pipeline", "selector", "seed", "dataset", "subject", "trial_id", "y_true", "p_right"]
    with gzip.open(temporary, "wt", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for fit_row in manifest["fits"]:
            level, seed = fit_row["source_level"], fit_row["seed"]
            update_status("FIXED_CSP_EXTERNAL_EVALUATION", trajectory=f"{level}/CSP_LDA/seed{seed}")
            model = load_model(fit_row["path"])
            for key, person in sorted(targets.items()):
                if (person["role"] != "external" or person["dataset"] != "dreyer"
                        or key in freeze["source_input_hashes"] or len(person["y"]) != config["target"]["trials_per_subject"]):
                    raise ValueError("CSP external evaluation received an invalid target person")
                probability = predict(model, person["X"])
                rows = [{"source_level": level, "pipeline": "CSP_LDA", "selector": "fixed", "seed": seed,
                         "dataset": "dreyer", "subject": key, "trial_id": str(t), "y_true": int(y), "p_right": float(p[1])}
                        for t, y, p in zip(person["trial_id"], person["y"], probability)]
                writer.writerows(rows)
                metrics.extend(prediction_metrics(rows))
                n_predictions += len(rows)
    expected = len(manifest["fits"])*config["target"]["subjects"]*config["target"]["trials_per_subject"]
    if n_predictions != expected:
        raise ValueError("Incomplete conventional prediction table")
    os.replace(temporary, path)
    write_csv(Path(run)/"results/csp_subject_seed_metrics.csv", metrics)
    report = paired_statistics(metrics, expected_subjects=config["target"]["subjects"], expected_seeds=config["final_seeds"],
                               expected_conditions=[(level, "CSP_LDA", "fixed") for level in reg["levels"]], comparisons=[],
                               n_bootstrap=config["bootstrap_replicates"], bootstrap_seed=config["bootstrap_seed"])
    # The shared summary helper's default diagnostic labels describe the neural
    # contrast family. This separate comparator requests no hypothesis tests.
    report["diagnostics"].update({"primary": "none; separate descriptive conventional baseline",
                                  "secondary": "none; no conventional baseline hypothesis tests",
                                  "n_hypothesis_tests": 0})
    report.update({"n_conventional_fits": len(manifest["fits"]), "prediction_rows": n_predictions,
                   "source_freeze_sha256": freeze["freeze_sha256"], "prediction_sha256": sha256_file(path),
                   "role": "separate_descriptive_conventional_baseline"})
    atomic_json(Path(run)/"results/csp_report.json", report)
    write_csv(Path(run)/"results/csp_condition_summaries.csv", report["condition_summaries"])
    return report
