#!/usr/bin/env python3
"""Separate source partition/curve/selector/checkpoint validation; no target data.

The selector calculation and accounting are independently implemented here.
Raw-source preprocessing uses the already frozen deterministic loader. This is
numerical/software validation, not a claim of independent human peer review.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
LEGACY = ROOT / "research_runs/REDESIGN_SOURCE_SELECTION_20261012"
sys.path.insert(0, str(LEGACY / "scripts"))
from formal_core_inputs import load_source19
from train_source_selection_core import build_model


def digest(path):
    sha = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for piece in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            sha.update(piece)
    return sha.hexdigest()


def encoded_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def array_digest(value):
    import numpy as np
    a = np.ascontiguousarray(value)
    h = hashlib.sha256(json.dumps({"shape": list(a.shape), "dtype": a.dtype.str}, sort_keys=True).encode())
    h.update(memoryview(a).cast("B"))
    return h.hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("Required source artifact absent or redirected")
    return json.loads(path.read_text())


def independent_selection(curves):
    """Average ranks, including exact ties, and earliest minimum, without SciPy."""
    matrix = [[float(row["validation_cross_entropy"]) for row in curve] for curve in curves]
    if len(matrix) != 4 or any(len(row) != 40 for row in matrix):
        raise ValueError("Four complete 40-epoch curves are required")
    if any(not math.isfinite(x) or x < 0 for row in matrix for x in row):
        raise ValueError("Invalid heldout-source cross entropy")
    ranks = []
    for row in matrix:
        counts = Counter(row)
        lower, value_rank = 0, {}
        for value in sorted(counts):
            count = counts[value]
            value_rank[value] = lower + (count + 1) / 2
            lower += count
        ranks.append([value_rank[x] for x in row])
    means = [sum(row[i] for row in matrix) / 4 for i in range(40)]
    mean_ranks = [sum(row[i] for row in ranks) / 4 for i in range(40)]
    return {"fixed20": 20, "mean_loss": min(range(40), key=means.__getitem__) + 1,
            "mean_rank": min(range(40), key=mean_ranks.__getitem__) + 1,
            "equal_fold_mean_loss": means, "equal_fold_mean_average_tie_rank": mean_ranks}


def expected_cells(architecture, choices, seeds):
    owner_by_key, cells = {}, []
    for selector in ("fixed20", "mean_loss", "mean_rank"):
        for seed in seeds:
            key = (architecture, seed, choices[selector])
            cell = f"{architecture}/{selector}/seed_{seed}"
            owner = owner_by_key.setdefault(key, cell)
            cells.append({"cell": cell, "architecture": architecture, "selector": selector, "seed": seed,
                          "epochs": choices[selector], "owner_cell": owner, "alias": cell != owner})
    return cells


def selections_agree(reconstructed, recorded):
    """Exact selected durations; bounded rounding tolerance for aggregation."""
    if set(reconstructed) != set(recorded):
        return False
    for arch, expected in reconstructed.items():
        actual = recorded[arch]
        if any(expected[k] != actual.get(k) for k in ("fixed20", "mean_loss", "mean_rank")):
            return False
        for key in ("equal_fold_mean_loss", "equal_fold_mean_average_tie_rank"):
            values = actual.get(key, [])
            if len(values) != 40 or any(not math.isclose(a, b, rel_tol=0., abs_tol=1e-12) for a, b in zip(expected[key], values)):
                return False
    return True


def assert_curve(curve, epochs, training_n, heldout):
    if [row.get("epoch") for row in curve] != list(range(1, epochs + 1)):
        raise ValueError("Missing/reordered source curve epochs")
    per_epoch = math.ceil(training_n / 64)
    for row in curve:
        train_ce = row.get("training_cross_entropy")
        if isinstance(train_ce, bool) or not isinstance(train_ce, (int, float)) or not math.isfinite(train_ce) or train_ce < 0:
            raise ValueError("Invalid training cross entropy")
        if row.get("optimizer_updates") != per_epoch:
            raise ValueError("Source optimizer-step coverage differs")
        val_ce = row.get("validation_cross_entropy")
        if heldout and (isinstance(val_ce, bool) or not isinstance(val_ce, (int, float)) or not math.isfinite(val_ce) or val_ce < 0):
            raise ValueError("Missing heldout-source loss")
        if not heldout and val_ce is not None:
            raise ValueError("Final source fit must have no validation selection")


def replay_last_source_loss(model, x, y, validation, expected):
    import torch
    model.eval()
    device = next(model.parameters()).device
    state_before = {k: array_digest(v.detach().cpu().numpy()) for k, v in model.state_dict().items()}
    total = 0.
    with torch.inference_mode():
        for offset in range(0, len(validation), 32):
            ids = validation[offset:offset + 32]
            logits = model(torch.as_tensor(x[ids], device=device))
            truth = torch.as_tensor(y[ids], dtype=torch.long, device=device)
            # Separate arithmetic: per-trial float64 log probabilities, rather
            # than the trainer's batched float32 CE sum.
            logp = torch.log_softmax(logits.to(torch.float64), dim=1)
            total += float((-logp[torch.arange(len(ids), device=device), truth]).sum())
    actual = total / len(validation)
    state_after = {k: array_digest(v.detach().cpu().numpy()) for k, v in model.state_dict().items()}
    if state_before != state_after:
        raise ValueError("Source validation changed learned/BatchNorm state")
    if not math.isclose(actual, expected, rel_tol=2e-5, abs_tol=2e-6):
        raise ValueError("Final-epoch heldout-source CE failed separate replay")
    return {"expected_cross_entropy": expected, "replayed_cross_entropy": actual,
            "absolute_difference": abs(actual - expected), "rtol": 2e-5, "atol": 2e-6,
            "source_only": True, "model_state_unchanged": True}


def independent_model_accounting(model, architecture):
    """Separately count parameters and explicitly partial forward MACs."""
    import torch
    device = next(model.parameters()).device
    macs = [0]
    def collect(module, inputs, output):
        if isinstance(module, (torch.nn.Conv1d, torch.nn.Conv2d)):
            macs[0] += output.numel() * math.prod(module.kernel_size) * module.in_channels // module.groups
        elif isinstance(module, torch.nn.Linear):
            macs[0] += output.numel() * module.in_features
    handles = [m.register_forward_hook(collect) for m in model.modules()
               if isinstance(m, (torch.nn.Conv1d, torch.nn.Conv2d, torch.nn.Linear))]
    model.eval()
    before = {k: array_digest(v.detach().cpu().numpy()) for k, v in model.state_dict().items()}
    shape = (1, 19, 320) if architecture == "BROAD_EEGNET" else (1, 2, 19, 320)
    try:
        with torch.inference_mode():
            model(torch.zeros(shape, device=device))
    finally:
        for hook in handles:
            hook.remove()
    if before != {k: array_digest(v.detach().cpu().numpy()) for k, v in model.state_dict().items()}:
        raise ValueError("Separate accounting probe changed source model state")
    return {"parameters": sum(p.numel() for p in model.parameters()),
            "trainable_parameters": sum(p.numel() for p in model.parameters() if p.requires_grad),
            "conv_linear_macs_per_trial": macs[0], "conv_linear_multiply_add_flops_per_trial": 2 * macs[0],
            "input_views_per_trial": 1 if architecture == "BROAD_EEGNET" else 2,
            "state_unchanged_during_probe": True}


def validate(job_dir, source_data_dir):
    import numpy as np
    import torch
    job = Path(job_dir).resolve()
    source = job / "source"
    config_path = STUDY / "config/experiment.json"
    config = read(config_path)
    if config.get("qualified_independent_confirmation") is not False or config.get("prior_exposure_status") != "AUTHOR_REPORTED_UNCERTAIN":
        raise ValueError("Exploratory uncertainty qualification differs")
    # Require the same authenticated live GPU and budget as the actual source
    # worker, without ever loading target tensors or permitting new fitting.
    from train_exploratory import (runtime_identity, validate_runtime, validate_budget, PersistentBudget,
        verify_freeze, validate_config, required_execution_paths, validate_prepared_data)
    validate_config(config)
    data = read(job / "data_prepare_receipt.json")
    verify_freeze(job, required_execution_paths(job, data))
    validate_prepared_data(job, data, source_data_dir)
    runtime = runtime_identity()
    validate_runtime(runtime, read(job / "runtime_lock.json"))
    authorization = validate_budget(read(job / "budget_authorization.json"), runtime)
    budget = PersistentBudget(job, authorization)
    budget.guard()
    completion = read(source / "source_completion_manifest.json")
    if completion.get("status") != "source_grid_completed_pending_separate_validation_no_target_predictions":
        raise ValueError("Source grid is incomplete")
    if completion.get("target_fits") != 0 or completion.get("target_predictions_computed") is not False:
        raise ValueError("Source-only training boundary changed")
    arrays, records, raw_audit = load_source19(source_data_dir, config)
    if encoded_sha(raw_audit) != encoded_sha(data.get("source_input_audit")):
        raise ValueError("Source preparation fingerprint changed before source numerical validation")
    if encoded_sha(raw_audit) != encoded_sha(read(source / "source19_input_audit.json")) or records != read(source / "source_metadata.json"):
        raise ValueError("Raw-source input audit or identities failed separate reconstruction")
    labels = np.array([r["label_index"] for r in records], dtype=np.int64)
    metadata_by_id = {r["sample_id"]: r for r in records}
    if len(metadata_by_id) != 2592:
        raise ValueError("Source identity inventory differs")
    selections, cells, ordinals, fit_count, updates, ce_replays = {}, [], [], 0, 0, []
    artifact_hashes = {}

    def bind(path):
        if path.is_symlink() or not path.resolve().is_relative_to(job):
            raise ValueError("Source artifact escaped job directory")
        artifact_hashes[path.relative_to(job).as_posix()] = digest(path)

    def check_fit(path, arch, seed, epochs, training, heldout):
        nonlocal fit_count, updates
        receipt = read(path / "fit_receipt.json")
        if receipt.get("status") != "completed" or receipt.get("architecture") != arch or receipt.get("seed") != seed or receipt.get("epochs") != epochs:
            raise ValueError("Actual source fit identity differs")
        if receipt.get("configuration_sha256") != digest(config_path) or receipt.get("target_fit") is not False or receipt.get("new_real_neural_fit") is not True:
            raise ValueError("Source fit provenance/target boundary differs")
        expected_optimizer = {"name": "Adam", "learning_rate": .001, "weight_decay": 0., "batch_size": 64, "drop_last": False}
        expected_kind = "source_validation_trajectory" if heldout else "final_all_source"
        if (receipt.get("optimizer") != expected_optimizer or receipt.get("actual_parameters") != config["architecture"]
                or receipt.get("cell_kind") != expected_kind or receipt.get("input_dtype") != "float32"):
            raise ValueError("Source optimizer/architecture/input recipe differs")
        partition = read(path / "partition.json")
        expected_train = [records[i] for i in training]
        expected_val = [records[i] for i in heldout]
        if partition["train_records"] != expected_train or partition["validation_records"] != expected_val:
            raise ValueError("Source group membership differs from frozen identities")
        if partition.get("validation_kind") != ("heldout_source_participants" if heldout else "none_final_all_source"):
            raise ValueError("Source partition selection role differs")
        train_ids = {r["sample_id"] for r in expected_train}
        val_ids = {r["sample_id"] for r in expected_val}
        if train_ids & val_ids or train_ids | val_ids != set(metadata_by_id):
            raise ValueError("Source partition overlap/incomplete coverage")
        if receipt["n_training_trials"] != len(training) or receipt["n_validation_trials"] != len(heldout):
            raise ValueError("Source participant/trial accounting differs")
        x = arrays["broad"] if arch == "BROAD_EEGNET" else np.stack([arrays["mu"], arrays["beta"]], axis=1)
        for indices, prefix in ((training, "training"), (heldout, "validation")):
            expected_x = None if not indices else array_digest(x[indices])
            expected_y = None if not indices else array_digest(labels[indices])
            if receipt[f"{prefix}_input_sha256"] != expected_x or receipt[f"{prefix}_labels_sha256"] != expected_y:
                raise ValueError("Source fit input/label hashes differ")
        curve = read(path / "source_curve.json")
        assert_curve(curve, epochs, len(training), bool(heldout))
        expected_updates = math.ceil(len(training) / 64) * epochs
        if receipt.get("optimizer_updates") != expected_updates or receipt.get("expected_optimizer_updates") != expected_updates:
            raise ValueError("Source fit update total differs")
        for filename, key in (("partition.json", "partition_sha256"), ("source_curve.json", "curve_sha256"), ("checkpoint.pt", "checkpoint_sha256")):
            if receipt[key] != digest(path / filename):
                raise ValueError("Source checkpoint/curve/partition integrity failed")
            bind(path / filename)
        checkpoint = torch.load(path / "checkpoint.pt", map_location="cpu", weights_only=True)
        if checkpoint["model"] != arch or checkpoint["seed"] != seed or checkpoint["epochs"] != epochs or checkpoint["architecture"] != config["architecture"] or checkpoint["config_sha256"] != digest(config_path):
            raise ValueError("Checkpoint attributes differ from source receipt")
        state_sha = encoded_sha({k: array_digest(v.detach().cpu().numpy()) for k, v in sorted(checkpoint["state_dict"].items())})
        if state_sha != receipt["model_state_sha256"] or any(not torch.isfinite(v).all() for v in checkpoint["state_dict"].values()):
            raise ValueError("Checkpoint learned state invalid or altered")
        model = build_model(arch, config["architecture"], "cuda")
        model.load_state_dict(checkpoint["state_dict"], strict=True)
        actual_shapes = {k: list(p.shape) for k, p in model.named_parameters()}
        separate_accounting = independent_model_accounting(model, arch)
        if actual_shapes != receipt["actual_named_parameter_shapes"] or any(receipt["model_accounting"].get(k) != v for k, v in separate_accounting.items()):
            raise ValueError("Checkpoint architecture parameter accounting differs")
        if heldout:
            budget.guard()
            ce_replays.append({"fit": path.relative_to(source).as_posix(), **replay_last_source_loss(model, x, labels, heldout, curve[-1]["validation_cross_entropy"])})
        del model, x
        ordinals.append(receipt["fit_ordinal"])
        fit_count += 1
        updates += expected_updates
        bind(path / "fit_receipt.json")
        return curve

    for arch in ("BROAD_EEGNET", "MU_BETA_SHARED"):
        curves = []
        for fold, subjects in enumerate(config["source_validation_groups"], 1):
            val = [i for i, r in enumerate(records) if r["subject"] in subjects]
            train = [i for i, r in enumerate(records) if r["subject"] not in subjects]
            if {records[i]["subject"] for i in train} & {records[i]["subject"] for i in val}:
                raise ValueError("Source participant overlap")
            curves.append(check_fit(source / "inner" / arch / f"fold_{fold:02d}", arch,
                                    config["selection_seed"], 40, train, val))
        selections[arch] = independent_selection(curves)
        for cell in expected_cells(arch, selections[arch], config["final_seeds"]):
            path = source / "final" / cell["cell"]
            if cell["alias"]:
                alias = read(path / "alias_receipt.json")
                owner = read(source / "final" / cell["owner_cell"] / "fit_receipt.json")
                expected = {**cell, "new_real_neural_fit": False, "optimizer_updates": 0,
                            "owner_checkpoint_sha256": owner["checkpoint_sha256"], "owner_model_state_sha256": owner["model_state_sha256"]}
                if alias != expected or (path / "fit_receipt.json").exists() or (path / "checkpoint.pt").exists():
                    raise ValueError("Checkpoint alias incorrectly claims a real source fit")
                bind(path / "alias_receipt.json")
            else:
                check_fit(path, arch, cell["seed"], cell["epochs"], list(range(2592)), [])
            cells.append(cell)
    recorded_selections = read(source / "selected_epochs.json")
    if not selections_agree(selections, recorded_selections) or not selections_agree(selections, completion["selected_epochs"]):
        raise ValueError("Source-only selected epochs differ from separate reconstruction")
    if cells != completion["final_cells"] or len(cells) != 18:
        raise ValueError("Nominal final-cell inventory differs")
    aliases = sum(c["alias"] for c in cells)
    if len(ordinals) != len(set(ordinals)) or sorted(ordinals) != list(range(1, fit_count + 1)):
        raise ValueError("Actual source fit ordinals are duplicated or incomplete")
    ledger = read(source / "budget_ledger.json")
    if fit_count != completion["actual_new_neural_fits"] or updates != completion["actual_optimizer_updates"] or aliases != completion["aliases"]:
        raise ValueError("Source completion counters differ")
    if ledger["actual_neural_fits_started"] != fit_count or ledger["actual_neural_fits_completed"] != fit_count or ledger["optimizer_updates"] != updates:
        raise ValueError("Persistent source budget ledger differs")
    if fit_count + aliases != 26 or fit_count > 26 or updates > 34440:
        raise ValueError("Source fit/update ceiling or nominal inventory differs")
    if list(source.glob("**/update_intent.json")):
        raise ValueError("Unresolved optimizer update intent remains")
    for name in ("source_completion_manifest.json", "source19_input_audit.json", "source_metadata.json", "selected_epochs.json", "runtime_provenance.json", "budget_ledger.json"):
        bind(source / name)
    output = {"schema_version": 1, "status": "PASS_SOURCE_ARTIFACT_VALIDATION_EXPLORATORY",
        "qualified_independent_confirmation": False, "source_raw_trials_reconstructed": 2592,
        "inner_curves_verified": 8, "heldout_source_final_epoch_loss_replays": ce_replays,
        "nominal_final_cells": 18, "actual_neural_fits": fit_count, "checkpoint_aliases": aliases,
        "optimizer_updates": updates, "selected_epochs": recorded_selections,
        "independently_reconstructed_selections": selections, "mean_aggregation_absolute_tolerance": 1e-12, "target_fits": 0,
        "target_predictions_computed": False, "config_sha256": digest(config_path),
        "source_completion_manifest_sha256": digest(source / "source_completion_manifest.json"),
        "artifact_hashes": artifact_hashes, "validator_sha256": digest(__file__),
        "validation_scope": "separate source numerical reconstruction and final heldout-CE replay; not independent human review"}
    temporary = source / "source_validation.json.tmp"
    temporary.write_text(json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(source / "source_validation.json")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-dir", type=Path)
    parser.add_argument("--source-data-dir", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"status": "DRY_RUN_NO_EEG_NO_FITS_NO_PREDICTIONS", "target_fits": 0,
                          "target_predictions_computed": False, "qualified_independent_confirmation": False}))
        return
    if args.job_dir is None or args.source_data_dir is None:
        parser.error("--execute requires --job-dir and --source-data-dir")
    result = validate(args.job_dir, args.source_data_dir)
    print(json.dumps({key: result[key] for key in ("status", "actual_neural_fits", "optimizer_updates", "target_fits", "qualified_independent_confirmation")}))


if __name__ == "__main__":
    main()
