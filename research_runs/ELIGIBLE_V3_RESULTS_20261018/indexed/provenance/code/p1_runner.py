#!/usr/bin/env python3
"""Run the complete pinned source-expansion task without target-driven tuning."""
from __future__ import annotations

import argparse
import csv
import gc
import gzip
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import traceback
import zipfile

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import numpy as np

from p1_common import (atomic_bytes, atomic_json, canonical_hash, code_manifest,
                       exclusive_lock, log, read_json, sha256_file, utc_now)

BUNDLE = Path(__file__).resolve().parent
DEFAULT_CONFIG = BUNDLE / "config" / "study.json"


def write_csv(path, rows):
    rows = list(rows)
    if not rows:
        raise ValueError(f"Refusing an empty result table: {path}")
    keys = list(dict.fromkeys(k for r in rows for k in r))
    s = io.StringIO(newline="")
    writer = csv.DictWriter(s, fieldnames=keys)
    writer.writeheader()
    writer.writerows(rows)
    atomic_bytes(path, s.getvalue().encode("utf-8"))


def runtime_info():
    import torch
    import braindecode.models.eegnet as implementation
    versions = {name: importlib.metadata.version(name) for name in
                ["torch", "torchaudio", "braindecode", "mne", "numpy", "scipy", "pandas", "scikit-learn", "h5py"]}
    return {"python": platform.python_version(), "platform": platform.platform(), "versions": versions,
            "eegnet_source_sha256": sha256_file(implementation.__file__),
            "cuda_runtime": torch.version.cuda, "cudnn": torch.backends.cudnn.version(),
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "torch_deterministic": True, "amp": False, "tf32": False}


def validate_runtime(info):
    expected = {"torch": "2.8.0", "torchaudio": "2.8.0", "braindecode": "1.5.1", "mne": "1.13.2",
                "numpy": "2.3.5", "scipy": "1.17.0", "pandas": "2.2.3", "scikit-learn": "1.8.0", "h5py": "3.16.0"}
    for name, value in expected.items():
        if info["versions"][name].split("+")[0] != value:
            raise RuntimeError(f"Pinned dependency mismatch: {name}")
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("This package requires Python 3.12. Use bootstrap.sh.")
    if info["eegnet_source_sha256"] != "913d804f17d4501f818031aba7c6dfc4a1ba0d70e27ce6a6961e1cb1b7dc09e5":
        raise RuntimeError("Official EEGNet implementation differs from the pinned source")


def registry(config):
    folds = config["source_folds"]
    if not isinstance(folds, int) or isinstance(folds, bool) or not 2 <= folds <= 9:
        raise ValueError("Source folds must be an integer between 2 and 9")
    if set(config["source_levels"]) != {"S9", "S29", "S60"}:
        raise ValueError("The expansion protocol requires S9, S29 and S60")
    for counts in config["source_levels"].values():
        if set(counts) != {"bnci", "yang"}:
            raise ValueError("Source levels may contain only BNCI and Yang")
        for dataset, maximum in (("bnci", 9), ("yang", 51)):
            if type(counts[dataset]) is not int or not 0 <= counts[dataset] <= maximum:
                raise ValueError(f"Invalid {dataset} source count")
    rng = np.random.default_rng(config["source_subject_registry_seed"])
    bnci = [int(x) for x in rng.permutation(np.arange(1, 10))]
    yang = [int(x) for x in rng.permutation(np.arange(1, 52))]
    fold_map = {f"bnci:{s:03d}": i % config["source_folds"] for i, s in enumerate(bnci)}
    fold_map.update({f"yang:{s:03d}": i % config["source_folds"] for i, s in enumerate(yang)})
    levels = {name: sorted([f"bnci:{s:03d}" for s in bnci[:counts["bnci"]]] +
                           [f"yang:{s:03d}" for s in yang[:counts["yang"]]])
              for name, counts in config["source_levels"].items()}
    if not set(levels["S9"]) < set(levels["S29"]) < set(levels["S60"]):
        raise ValueError("Source levels must be genuinely nested by participant identity")
    for keys in levels.values():
        for fold in range(config["source_folds"]):
            for dataset in {k.split(":")[0] for k in keys}:
                group = [k for k in keys if k.startswith(dataset+":")]
                if not any(fold_map[k] == fold for k in group) or not any(fold_map[k] != fold for k in group):
                    raise ValueError("Every source fold requires training and held-out people from each present cohort")
    return {"seed": config["source_subject_registry_seed"], "bnci_random_order": bnci,
            "yang_random_order": yang, "fold_map": fold_map, "levels": levels,
            "grouping_unit": "whole_person_all_sessions_and_trials", "uses_external_labels": False}


def prepare(raw_root, cache_root, dataset, subjects):
    from p1_data import build_subject_npz, verify_subject_npz, VerifiedFiles, DATASET_NAMES
    out = {}
    for i, subject in enumerate(subjects, 1):
        log(f"Prepare {dataset} subject {subject} ({i}/{len(subjects)})")
        path = Path(cache_root) / dataset / f"sub-{subject:03d}.npz"
        native_root = Path(raw_root)/dataset
        manifest_path = native_root/"_download_manifest.json"
        audit = None
        if path.exists():
            try:
                cached = verify_subject_npz(path, filter_bank_json=BUNDLE/"config/filter_bank18.json")
                verified = VerifiedFiles(native_root, manifest_path)
                if (cached["dataset"] != DATASET_NAMES[dataset] or cached["provider_subject"] != subject
                        or cached["downloader_manifest_sha256"] != verified.manifest_sha256):
                    raise ValueError("Cached participant/manifest identity changed")
                for raw in cached["raw_files"]:
                    if verified.records.get(raw["path"]) != raw:
                        raise ValueError("Cached native-file provenance changed")
                    verified.find(relative=raw["path"])
                if sha256_file(manifest_path) != verified.manifest_sha256:
                    raise ValueError("Native manifest changed during cache verification")
                audit = {**cached, "npz_path": str(path), "npz_sha256": sha256_file(path),
                         "npz_bytes": path.stat().st_size}
                from eligibility_policy import annotate_legacy_reuse
                audit = annotate_legacy_reuse(path, native_root, audit)
                log(f"Reuse verified prepared input {dataset}:{subject:03d}")
            except (OSError, ValueError, KeyError, EOFError, zipfile.BadZipFile) as error:
                raise ValueError(f"Existing cache failed verification; preserved {dataset}:{subject:03d}") from error
        if audit is None:
            audit = build_subject_npz(dataset, subject, native_root, path,
                                     filter_bank_json=BUNDLE/"config/filter_bank18.json",
                                     manifest_path=manifest_path,
                                     yang_unit_policy="yang_v5_questionmark_V_scale_invariant")
        out[f"{dataset}:{subject:03d}"] = {"path": str(path), "sha256": sha256_file(path), "audit": audit}
    return out


def load_people(inputs, role):
    from p1_data import DATASET_NAMES
    if role not in ("source", "external"):
        raise ValueError("Prepared inputs need an explicit source or external role")
    allowed = {"bnci", "yang"} if role == "source" else {"dreyer"}
    people = {}
    for key, entry in inputs.items():
        match = re.fullmatch(r"(bnci|yang|dreyer):(\d{3})", key)
        if match is None or match[1] not in allowed:
            raise ValueError("An input dataset is incompatible with its source/external role")
        dataset, provider_subject = match[1], int(match[2])
        audit = entry["audit"]
        if audit["dataset"] != DATASET_NAMES[dataset] or audit["provider_subject"] != provider_subject:
            raise ValueError("Prepared audit and source registry identify different people")
        if sha256_file(entry["path"]) != entry["sha256"]:
            raise RuntimeError(f"Processed subject file changed: {key}")
        with np.load(entry["path"], allow_pickle=False) as f:
            x, y = f["X"], f["y"]
            trials = f["trial_id"].astype(str)
            embedded = json.loads(f["audit_json"].item())
            if embedded["dataset"] != DATASET_NAMES[dataset] or embedded["provider_subject"] != provider_subject:
                raise ValueError("Prepared arrays and source registry identify different people")
        if x.dtype != np.float32 or x.shape != (len(y), 3, 18, 320) or not np.isfinite(x).all():
            raise ValueError(f"Invalid prepared arrays: {key}")
        if set(np.unique(y).tolist()) != {0, 1} or len(set(trials)) != len(y):
            raise ValueError(f"Invalid labels or duplicate trials: {key}")
        people[key] = {"X": x, "y": y.astype(np.int64), "trial_id": trials, "dataset": key.split(":")[0],
                       "subject": key, "role": role, "input_sha256": entry["sha256"]}
    return people


def fit_folder(run, stage, level, pipeline, seed, fold=None):
    suffix = "all_source" if fold is None else f"fold_{fold}"
    return Path(run)/"checkpoints"/stage/level/pipeline/suffix/f"seed_{seed}"


def run_source_validation(config, reg, people, run, identity, update_status, device):
    from p1_train import train_trajectory, read_validation_curves
    from p1_select import select_epochs
    selections, all_rows = {}, []
    done = 0
    total = len(reg["levels"])*len(config["pipelines"])*config["source_folds"]*len(config["validation_seeds"])
    for level, keys in reg["levels"].items():
        selections[level] = {}
        for pipeline in config["pipelines"]:
            rows = []
            for fold in range(config["source_folds"]):
                train = {k: people[k] for k in keys if reg["fold_map"][k] != fold}
                valid = {k: people[k] for k in keys if reg["fold_map"][k] == fold}
                for seed in config["validation_seeds"]:
                    folder = fit_folder(run, "validation", level, pipeline, seed, fold)
                    update_status("SOURCE_VALIDATION", trajectory=f"{level}/{pipeline}/fold{fold}/seed{seed}", completed=done, total=total)
                    contract_hash = train_trajectory(config, train, valid, folder, seed=seed, pipeline=pipeline,
                                                     source_level=level, fold=fold, execution_identity=identity,
                                                     device=device)
                    rows.extend(read_validation_curves(folder, config["epochs"], expected_contract=contract_hash))
                    done += 1
            chosen = select_epochs(rows, expected_epochs=config["epochs"], expected_seeds=config["validation_seeds"],
                                   expected_subjects=keys, expected_folds=config["source_folds"],
                                   allowed_datasets=sorted({k.split(":")[0] for k in keys}),
                                   fixed_epoch=config["fixed_epoch"], tail_mass=config["tail_probability"])
            if set(chosen["epochs"]) != set(config["selectors"]):
                raise ValueError("Selector implementation differs from the frozen protocol")
            selections[level][pipeline] = chosen
            all_rows.extend(rows)
    write_csv(Path(run)/"results/source_validation_curves.csv", all_rows)
    freeze = {"protocol_id": config["protocol_id"], "selections": selections, "source_only": True,
              "external_raw_read_by_this_task": False, "source_registry_sha256": canonical_hash(reg),
              "execution_identity": identity, "curves_sha256": sha256_file(Path(run)/"results/source_validation_curves.csv"),
              "source_input_hashes": {k: v["input_sha256"] for k, v in people.items()}, "complete_validation_trajectories": done}
    freeze["freeze_sha256"] = canonical_hash(freeze)
    path = Path(run)/"results/selection_freeze.json"
    if path.exists() and read_json(path) != freeze:
        raise RuntimeError("An existing source selection freeze differs; results are not overwritten")
    atomic_json(path, freeze)
    return freeze


def run_final_fits(config, reg, people, freeze, run, identity, update_status, device):
    from p1_train import train_trajectory, load_checkpoint
    rows = []
    total = len(reg["levels"])*len(config["pipelines"])*len(config["final_seeds"])
    done = 0
    for level, keys in reg["levels"].items():
        source = {k: people[k] for k in keys}
        for pipeline in config["pipelines"]:
            chosen = freeze["selections"][level][pipeline]["epochs"]
            for seed in config["final_seeds"]:
                update_status("FINAL_SOURCE_TRAINING", trajectory=f"{level}/{pipeline}/seed{seed}", completed=done, total=total)
                folder = fit_folder(run, "final", level, pipeline, seed)
                train_trajectory(config, source, {}, folder, seed=seed, pipeline=pipeline, source_level=level,
                                 fold="all_source", execution_identity=identity, device=device)
                for epoch in sorted(set(chosen.values())):
                    _, receipt = load_checkpoint(folder, epoch)
                    rows.append({"source_level": level, "pipeline": pipeline, "seed": seed, "epoch": epoch,
                                 "selectors": ";".join(k for k, v in chosen.items() if v == epoch),
                                 "checkpoint": str(folder/receipt["path"]), "checkpoint_sha256": receipt["sha256"],
                                 "source_only": True, "distinct_trajectory": f"{level}/{pipeline}/{seed}"})
                done += 1
    write_csv(Path(run)/"results/final_fit_manifest.csv", rows)
    completion = {"source_only": True, "complete_final_trajectories": done, "freeze_sha256": freeze["freeze_sha256"],
                  "fit_manifest_sha256": sha256_file(Path(run)/"results/final_fit_manifest.csv")}
    atomic_json(Path(run)/"results/source_training_complete.json", completion)
    return completion


def require_source_freeze(run, freeze, config):
    from p1_train import load_checkpoint
    root = Path(run)/"results"
    on_disk = read_json(root/"selection_freeze.json")
    completion = read_json(root/"source_training_complete.json")
    body = {key: value for key, value in on_disk.items() if key != "freeze_sha256"}
    if (on_disk != freeze or not on_disk["source_only"] or not completion["source_only"]
            or canonical_hash(body) != on_disk["freeze_sha256"]
            or completion["freeze_sha256"] != on_disk["freeze_sha256"]):
        raise ValueError("Target access requires the unchanged source-only selection freeze")
    if (on_disk["protocol_id"] != config["protocol_id"]
            or on_disk["complete_validation_trajectories"] != config["nominal_validation_trajectories"]):
        raise ValueError("All source validation trajectories must finish under the frozen protocol")
    if completion["complete_final_trajectories"] != config["nominal_final_trajectories"]:
        raise ValueError("All final source trajectories must finish before external evaluation")
    if sha256_file(root/"source_validation_curves.csv") != on_disk["curves_sha256"]:
        raise ValueError("Source validation evidence changed")
    if sha256_file(root/"final_fit_manifest.csv") != completion["fit_manifest_sha256"]:
        raise ValueError("Final source fit evidence changed")
    reg = registry(config)
    if canonical_hash(reg) != on_disk["source_registry_sha256"]:
        raise ValueError("The source registry differs from its selection freeze")
    expected = {}
    for level, keys in reg["levels"].items():
        for pipeline in config["pipelines"]:
            chosen = on_disk["selections"][level][pipeline]["epochs"]
            if (set(chosen) != set(config["selectors"]) or chosen["fixed20"] != config["fixed_epoch"]
                    or any(type(e) is not int or not 1 <= e <= config["epochs"] for e in chosen.values())):
                raise ValueError("Frozen epoch choices differ from the selector protocol")
            for seed in config["final_seeds"]:
                contract = {"config": config, "seed": seed, "pipeline": pipeline, "source_level": level,
                            "fold": "all_source", "train": {k: on_disk["source_input_hashes"][k] for k in keys},
                            "validation": {}, "execution_identity": on_disk["execution_identity"]}
                contract_hash = canonical_hash(contract)
                folder = fit_folder(run, "final", level, pipeline, seed)
                completed = read_json(folder/"complete.json")
                _, final_receipt = load_checkpoint(folder, config["epochs"], expected_contract=contract_hash)
                if (not completed.get("complete") or not completed.get("source_only")
                        or completed["epoch"] != config["epochs"]
                        or completed["updates"] != config["epochs"] * config["updates_per_epoch"]
                        or any(completed.get(k) != v for k, v in final_receipt.items())):
                    raise ValueError("A final source checkpoint has not completed the frozen budget")
                for epoch in set(chosen.values()):
                    expected[(level, pipeline, int(seed), epoch)] = (folder, contract_hash,
                                                                    {k for k, e in chosen.items() if e == epoch})
    seen = set()
    with (root/"final_fit_manifest.csv").open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            key = (row["source_level"], row["pipeline"], int(row["seed"]), int(row["epoch"]))
            if key not in expected or key in seen:
                raise ValueError("Final checkpoint manifest has duplicate or unexpected conditions")
            seen.add(key)
            folder, contract_hash, aliases = expected[key]
            _, receipt = load_checkpoint(folder, key[-1], expected_contract=contract_hash)
            if (Path(row["checkpoint"]).resolve() != (folder/receipt["path"]).resolve()
                    or row["checkpoint_sha256"] != receipt["sha256"]
                    or set(row["selectors"].split(";")) != aliases or row["source_only"] != "True"):
                raise ValueError("Actual selected checkpoint differs from the frozen fit manifest")
    if seen != set(expected):
        raise ValueError("Final checkpoint manifest is incomplete")
    from p1_csp_task import require_baselines
    require_baselines(config, reg, freeze, run)


def external_evaluate(config, targets, freeze, run, update_status, device):
    from p1_train import build_model, load_checkpoint, predict
    from p1_select import prediction_metrics, paired_statistics
    require_source_freeze(run, freeze, config)
    if len(targets) != config["target"]["subjects"]:
        raise ValueError("External subject inventory differs from the frozen protocol")
    for key, person in targets.items():
        if (person.get("role") != "external" or person.get("dataset") != "dreyer"
                or key in freeze["source_input_hashes"]):
            raise ValueError("External evaluation requires separate, explicitly external people")
        if len(person["y"]) != config["target"]["trials_per_subject"]:
            raise ValueError("External trial inventory differs from the frozen protocol")
    prediction_path = Path(run)/"results/external_predictions.csv.gz"
    temporary = prediction_path.with_suffix(".gz.tmp")
    condition_metrics = []
    rows_written = 0
    fields = ["source_level", "pipeline", "selector", "seed", "epoch", "dataset", "subject", "trial_id", "y_true", "logit_left", "logit_right"]
    # Re-evaluation is deterministic and rewrites only a temporary results file.
    with gzip.open(temporary, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for level in config["source_levels"]:
            for pipeline in config["pipelines"]:
                chosen = freeze["selections"][level][pipeline]["epochs"]
                for seed in config["final_seeds"]:
                    folder = fit_folder(run, "final", level, pipeline, seed)
                    for epoch in sorted(set(chosen.values())):
                        aliases = [k for k, v in chosen.items() if v == epoch]
                        update_status("EXTERNAL_EVALUATION", trajectory=f"{level}/{pipeline}/seed{seed}/epoch{epoch}", prediction_rows=rows_written)
                        model = build_model(config, device)
                        payload, _ = load_checkpoint(folder, epoch)
                        model.load_state_dict(payload["model"])
                        for key in sorted(targets):
                            person = targets[key]
                            z = predict(model, person, pipeline, device)
                            for selector in aliases:
                                subject_rows = [{"source_level": level, "pipeline": pipeline, "selector": selector, "seed": seed,
                                                 "epoch": epoch, "dataset": "dreyer", "subject": key,
                                                 "trial_id": str(t), "y_true": int(y),
                                                 "logit_left": float(logits[0]), "logit_right": float(logits[1])}
                                                for t, y, logits in zip(person["trial_id"], person["y"], z)]
                                writer.writerows(subject_rows)
                                condition_metrics.extend(prediction_metrics(subject_rows))
                                rows_written += len(subject_rows)
                        del model, payload
    if rows_written != config["nominal_external_prediction_rows"]:
        raise RuntimeError(f"Prediction inventory incomplete: {rows_written}")
    os.replace(temporary, prediction_path)
    write_csv(Path(run)/"results/external_subject_seed_metrics.csv", condition_metrics)
    report = paired_statistics(condition_metrics, expected_subjects=config["target"]["subjects"],
                               expected_seeds=config["final_seeds"], n_bootstrap=config["bootstrap_replicates"],
                               bootstrap_seed=config["bootstrap_seed"])
    report["protocol_id"] = config["protocol_id"]
    report["prediction_rows"] = rows_written
    report["prediction_sha256"] = sha256_file(prediction_path)
    report["source_freeze_sha256"] = freeze["freeze_sha256"]
    report["limitations"] = config["limitations"]
    atomic_json(Path(run)/"results/report.json", report)
    return report


def export_results(run, config):
    from p1_report import render_report
    run = Path(run)
    render_report(run/"results", config)
    artifact = run/"paper1_expansion_results.zip"
    temporary = artifact.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for directory in [run/"results", run/"provenance"]:
            for path in sorted(directory.rglob("*")):
                if path.is_file() and not path.name.endswith(".tmp"):
                    z.write(path, str(path.relative_to(run)))
    os.replace(temporary, artifact)
    atomic_json(run/"export_receipt.json", {"path": str(artifact), "sha256": sha256_file(artifact), "raw_eeg_included": False})
    return artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/workspace/paper1_expansion"))
    parser.add_argument("--run-name", default="expansion18_eligible_v3_20261018")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run_name):
        parser.error("run-name must contain only letters, numbers, underscores and hyphens")
    run = args.root.resolve()/"runs"/args.run_name
    if args.status:
        path = run/"status.json"
        print(path.read_text() if path.exists() else "No run has started.")
        return
    run.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(run/"run.lock"):
        config = read_json(DEFAULT_CONFIG)
        def update_status(stage, **details):
            atomic_json(run/"status.json", {"protocol_id": config["protocol_id"], "stage": stage, "pid": os.getpid(),
                                           "updated_utc": utc_now(), "run_directory": str(run), **details})
        try:
            from p1_train import configure_runtime
            from p1_download import download_sources, download_external
            configure_runtime("cuda")
            runtime = runtime_info()
            validate_runtime(runtime)
            reg = registry(config)
            manifest = code_manifest(BUNDLE)
            # Device names are recorded separately: moving to another GPU is visible
            # but no bit-for-bit identity across GPU models is promised.
            identity = {"code": canonical_hash(manifest), "config": canonical_hash(config),
                        "python": runtime["python"], "versions": runtime["versions"],
                        "eegnet_source_sha256": runtime["eegnet_source_sha256"]}
            frozen = run/"provenance/execution_identity.json"
            if frozen.exists() and read_json(frozen) != identity:
                raise RuntimeError("Code, configuration, Python or dependencies changed. Use a new --run-name.")
            atomic_json(frozen, identity)
            atomic_json(run/"provenance/code_manifest.json", manifest)
            atomic_json(run/"provenance/study.json", config)
            atomic_json(run/"provenance/source_registry.json", reg)
            atomic_json(run/"provenance"/f"runtime_{utc_now().replace(':','-')}.json", runtime)
            for p in BUNDLE.glob("*.py"):
                dest = run/"provenance/code"/p.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dest)
            for name in ["bootstrap.sh", "pyproject.toml", "uv.lock", "README_zh.md"]:
                shutil.copy2(BUNDLE/name, run/"provenance/code"/name)
            for p in (BUNDLE/"config").glob("*.json"):
                dest = run/"provenance/code/config"/p.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dest)
            if (BUNDLE/"BUNDLE_MANIFEST.json").exists():
                shutil.copy2(BUNDLE/"BUNDLE_MANIFEST.json", run/"provenance/code/BUNDLE_MANIFEST.json")
            if (run/"status.json").exists() and read_json(run/"status.json").get("stage") == "COMPLETE":
                receipt = read_json(run/"export_receipt.json")
                if sha256_file(receipt["path"]) != receipt["sha256"]:
                    raise RuntimeError("Completed export differs from its receipt")
                log(f"Already complete: {receipt['path']}")
                return
            raw_root, cache_root = args.root.resolve()/"data/raw", args.root.resolve()/"data/processed18_eligible_v3_20261018"
            update_status("DOWNLOAD_SOURCES")
            download_sources(raw_root)
            update_status("PREPARE_SOURCES")
            inputs = prepare(raw_root, cache_root, "bnci", list(range(1, 10)))
            inputs.update(prepare(raw_root, cache_root, "yang", list(range(1, 52))))
            atomic_json(run/"provenance/source_inputs.json", inputs)
            people = load_people(inputs, "source")
            for level, keys in reg["levels"].items():
                n = sum(len(people[k]["y"]) for k in keys)
                if n != config["source_trial_counts_expected"][level]:
                    raise ValueError(f"Source trial inventory differs at {level}: {n}")
            freeze = run_source_validation(config, reg, people, run, identity, update_status, "cuda")
            run_final_fits(config, reg, people, freeze, run, identity, update_status, "cuda")
            from p1_csp_task import fit_baselines, evaluate_baselines
            fit_baselines(config, reg, people, freeze, run, identity, update_status)
            del people
            gc.collect()
            require_source_freeze(run, freeze, config)
            update_status("DOWNLOAD_EXTERNAL_AFTER_SOURCE_FREEZE")
            download_external(raw_root)
            update_status("PREPARE_EXTERNAL")
            subjects = [s for s in range(1, 88) if s not in config["target"]["exclude_provider_global_subjects"]]
            target_inputs = prepare(raw_root, cache_root, "dreyer", subjects)
            atomic_json(run/"provenance/external_inputs.json", target_inputs)
            targets = load_people(target_inputs, "external")
            require_source_freeze(run, freeze, config)
            external_evaluate(config, targets, freeze, run, update_status, "cuda")
            evaluate_baselines(config, reg, targets, freeze, run, update_status)
            update_status("EXPORT_RESULTS")
            artifact = export_results(run, config)
            update_status("COMPLETE", results_zip=str(artifact), real_neural_trajectories=108,
                          conventional_source_fits=config["traditional_baseline"]["nominal_fits"],
                          external_prediction_rows=config["nominal_external_prediction_rows"])
            log(f"COMPLETE. Download {artifact}")
        except BaseException as exc:
            previous = read_json(run/"status.json") if (run/"status.json").exists() else {}
            update_status("INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "FAILED", error_type=type(exc).__name__,
                          error=str(exc), previous_stage=previous.get("stage"),
                          resume="Run the same bootstrap.sh command; verified raw files and completed epochs are reused.")
            atomic_bytes(run/"last_traceback.txt", traceback.format_exc().encode())
            raise


if __name__ == "__main__":
    main()
