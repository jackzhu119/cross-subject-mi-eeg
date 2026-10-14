#!/usr/bin/env python3
"""Bounded, resumable, source-only GPU execution of the frozen exploratory core.

This is a new executor, not an override of the v1 first-use gates. It never
opens target tensors or computes target predictions. Completed minibatch state
is committed atomically. An unresolved update intent blocks automatic recovery
because a crash may have performed an unrecorded optimizer update.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import random
import socket
import subprocess
import sys
import time

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
LEGACY = ROOT / "research_runs/REDESIGN_SOURCE_SELECTION_20261012"
EXPLORATORY = ROOT / "research_runs/REDESIGN_EXPLORATORY_20261013"
sys.path.insert(0, str(LEGACY / "scripts"))
from formal_core_inputs import array_hash, load_source19, check_processing, numerical_identity
from train_source_selection_core import (build_model, compute_accounting, source_partition,
                                         select_epochs, schedule_cells, state_hash, seed_everything,
                                         evaluate_source_ce)

CONFIG = STUDY / "config/experiment.json"
ARCHITECTURES = ("BROAD_EEGNET", "MU_BETA_SHARED")
SELECTORS = ("fixed20", "mean_loss", "mean_rank")
PACKAGES = ("torch", "torchaudio", "braindecode", "numpy", "scipy", "pandas", "mne", "scikit-learn", "skorch", "einops")


def now():
    return datetime.now(timezone.utc).isoformat()


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Required regular artifact absent: {path.name}")
    return json.loads(path.read_text())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def atomic_torch_save(path, value):
    import torch
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        torch.save(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def validate_config(config):
    """Authenticate all consequential numerical choices against the frozen v1.

    Metadata qualification is deliberately different; no v1 scientific gate is
    called or supplied with a fictitious first-use declaration.
    """
    check_processing(config)
    reference = read_json(LEGACY / "config/core_experiment_v1.json")
    numerical_keys = ("source_dataset", "source_subjects", "source_population", "source_validation_groups",
        "source_validation_group_weight", "selection_seed", "final_seeds", "architectures", "selectors",
        "fixed_epochs", "candidate_epochs", "selection_loss", "loss_rule", "rank_rule", "final_training",
        "optimizer", "learning_rate", "weight_decay", "batch_size", "drop_last", "architecture",
        "shared_training", "BatchNorm_target_mode", "target_fitted_transforms", "target_fits",
        "core_inner_fits", "nominal_core_final_fits", "nominal_core_neural_fits", "optional_extra_grouping_enabled",
        "target_performance_used_for_design")
    for key in numerical_keys:
        if canonical_hash(config.get(key)) != canonical_hash(reference[key]):
            raise ValueError(f"Frozen numerical source design differs: {key}")
    if config.get("qualified_independent_confirmation") is not False:
        raise ValueError("Unknown prior exposure cannot qualify as independent confirmation")
    if config.get("prior_exposure_status") != "AUTHOR_REPORTED_UNCERTAIN":
        raise ValueError("Author uncertainty must be retained truthfully")
    return config


def verify_freeze(job, required_paths):
    """Re-read actual immutable public bytes; no trusted PASS-wrapper shortcut."""
    from cloud_contract import verify_public_freeze
    if read_json(Path(job) / "public_freeze.json").get("public_readback_verified") is not True:
        raise ValueError("Public readback receipt is absent; actual public bytes will also be rechecked")
    return verify_public_freeze(job, required_paths=required_paths)


def required_execution_paths(job, data):
    """Actual runtime, budget, raw-only eligibility and author records are frozen."""
    job = Path(job).resolve()
    required = [CONFIG, Path(__file__), HERE / "validate_source.py", HERE / "cloud_contract.py",
        HERE / "prepare_data.py", HERE / "cloud_locks.py", HERE / "formal_core_inputs.py", HERE / "numerical_review_gate.py",
        HERE.parent / "config/numerical_execution_v1.json", LEGACY / "scripts/train_source_selection_core.py",
        LEGACY / "scripts/core_source_inputs.py", LEGACY / "config/core_experiment_v1.json",
        ROOT / "research_runs/Q8-E001/results/source_files.json", ROOT / "src/mi_eeg/data/q15_context.py",
        EXPLORATORY / "evidence/author_prior_use_uncertain.json",
        EXPLORATORY / "evidence/author_conditional_gpu_budget.json",
        EXPLORATORY / "results/raw-qc-543feb2f/raw_only_roster.json",
        EXPLORATORY / "results/raw-qc-543feb2f/full_raw_qc_report.json",
        EXPLORATORY / "evidence/source_exact_input_fingerprints.csv",
        EXPLORATORY / "evidence/source_exact_input_fingerprints_receipt.json",
        ROOT / "research_runs/REDESIGN_HANDOFF_20261014/formal_numerical_execution/accept_source_numerics.py",
        ROOT / "research_runs/REDESIGN_HANDOFF_20261014/formal_numerical_execution/audit_full_diagnostic_bundle.py",
        ROOT / "research_runs/REDESIGN_HANDOFF_20261014/formal_numerical_execution/OPERATION_AMENDMENT.md",
        job / "runtime_lock.json", job / "budget_authorization.json", job / "data_prepare_receipt.json",
        job / "numerical_execution_review.json", job / "formal_source_acceptance.json"]
    for key in ("roster_path", "raw_qc_report_path", "tensor_cache_receipt_path"):
        raw_path = Path(data.get(key, ""))
        if raw_path.is_symlink() or not raw_path.resolve().is_relative_to(job):
            raise ValueError("Required prepared-data artifact escaped the current job")
        required.append(raw_path)
    return required


def validate_prepared_data(job, data, source_data_dir):
    """Metadata-only full-cohort gate; never opens target EEG or input arrays."""
    if data.get('numerical_execution') != numerical_identity():
        raise ValueError('Prepared numerical execution identity differs from registered adapter')
    from numerical_review_gate import verify_review
    verify_review(job)
    expected = {"status": "PASS_DATA_PREPARATION_EXPLORATORY", "source_raw_files_verified": 18,
        "qualified_independent_confirmation": False, "independent_confirmation_qualified": False,
        "target_fits": 0, "target_predictions_computed": False, "author_prior_use": "unknown",
        "source_file_count": 18, "target_file_count": 174, "retained_participants": 85,
        "retained_events": 6800, "exact_frozen_input_reconstruction": True}
    for key, value in expected.items():
        if type(data.get(key)) is not type(value) or data[key] != value:
            raise ValueError(f"Full raw-only exploratory data preparation gate differs: {key}")
    if Path(data.get("source_data_dir", "")).resolve() != Path(source_data_dir).resolve():
        raise ValueError("Source directory differs from prepared data")
    if len(data.get("source_files", [])) != 18:
        raise ValueError("Prepared source provenance must cover all 18 originals")
    roster_path = Path(data["roster_path"])
    if file_hash(roster_path) != data.get("roster_sha256"):
        raise ValueError("Raw-only roster changed after preparation")
    if file_hash(roster_path) != file_hash(EXPLORATORY / "results/raw-qc-543feb2f/raw_only_roster.json"):
        raise ValueError("Prepared raw-only roster differs from the previously frozen 85-person cohort")
    roster = read_json(roster_path)
    if (len(roster.get("participants", [])) != 85 or len(roster.get("events", [])) != 6800
            or set(roster.get("technical_exclusions", [])) != {"A17", "A41"}
            or roster.get("independent_confirmation_qualified") is not False or roster.get("prior_use") != "unknown"
            or roster.get("performance_used_for_eligibility") is not False or roster.get("synthetic_fixture") is not False
            or roster.get("target_fits") != 0 or roster.get("target_predictions_computed") is not False):
        raise ValueError("Prepared target roster is not the frozen pre-outcome exploratory cohort")
    qc = read_json(data["raw_qc_report_path"])
    if (qc.get("status") != "PASS_RAW_ONLY_FULL_COHORT_QC_EXPLORATORY_OPERATIONAL_SCOPE"
            or qc.get("all_174_files_examined") is not True or qc.get("full_physical_signal_scan_passed") is not True
            or qc.get("n_retained_participants") != 85 or qc.get("n_eligible_events") != 6800
            or qc.get("independent_confirmation_qualified") is not False
            or qc.get("target_fits") != 0 or qc.get("target_predictions_computed") is not False
            or qc.get("roster_sha256") != file_hash(roster_path)
            or qc.get("tensor_cache_receipt_sha256") != file_hash(data["tensor_cache_receipt_path"])):
        raise ValueError("Actual complete operational raw QC is not authenticated")
    author = read_json(EXPLORATORY / "evidence/author_prior_use_uncertain.json")
    if author.get("status") != "AUTHOR_REPORTED_UNCERTAIN" or author.get("independent_confirmation_qualified") is not False:
        raise ValueError("Actual author uncertainty record changed")
    for key in ("prior_proposed_decoder_results_inspected_or_used", "prior_dataset_scientific_analysis_performed", "used_in_other_manuscripts_or_projects"):
        if key not in author or author[key] is not None:
            raise ValueError("Unknown prior use must remain unknown, not never-used")
    return data


def runtime_identity():
    import torch
    if not torch.cuda.is_available() or torch.cuda.device_count() < 1:
        raise ValueError("Actual EEG source fitting requires CUDA; CPU fits are blocked")
    properties = torch.cuda.get_device_properties(0)
    uuid = str(getattr(properties, "uuid", ""))
    if not uuid:
        raise ValueError("Live GPU UUID is not authenticated")
    if float((torch.ones(1, device="cuda") * 2).item()) != 2:
        raise ValueError("GPU arithmetic failed")
    return {"machine_hostname": socket.gethostname(), "gpu_uuid": uuid, "gpu_name": properties.name,
            "runtime_cuda": torch.version.cuda, "python": platform.python_version(),
            "packages": {name: importlib.metadata.version(name) for name in PACKAGES}}


def validate_runtime(actual, lock):
    if lock.get("status") != "FROZEN_BEFORE_SOURCE_FITS":
        raise ValueError("Runtime was not frozen before fitting")
    for key in ("python", "runtime_cuda", "packages", "machine_hostname", "gpu_uuid"):
        if actual.get(key) != lock.get(key):
            raise ValueError(f"Runtime lock mismatch: {key}")
    if actual["packages"]["braindecode"] != "1.5.1":
        raise ValueError("Frozen EEGNet requires braindecode 1.5.1")


def validate_budget(receipt, runtime, current=None):
    current = current or datetime.now(timezone.utc)
    if receipt.get("status") not in {"AUTHORIZED", "PASS_BOUNDED_MACHINE_BUDGET"}:
        raise ValueError("Bounded machine budget missing")
    if receipt.get("config_sha256") != file_hash(CONFIG):
        raise ValueError("Machine budget is not bound to the frozen numerical configuration")
    for key in ("machine_hostname", "gpu_uuid"):
        if receipt.get(key) != runtime[key]:
            raise ValueError("Budget belongs to another live machine")
    if receipt.get("target_fits_authorized") is not False or receipt.get("optional_grouping_authorized") is not False:
        raise ValueError("No target fits or optional grouping may be authorized")
    limits = {"maximum_neural_fits": 26, "maximum_optimizer_updates": 34440,
              "maximum_gpu_hours": 8, "maximum_total_usd": 10,
              "approved_hourly_rate_usd": .75, "non_gpu_reserved_usd": 2}
    for key, upper in limits.items():
        value = receipt.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= upper:
            raise ValueError(f"Invalid authorized limit: {key}")
    for key in ("maximum_neural_fits", "maximum_optimizer_updates"):
        if type(receipt[key]) is not int:
            raise ValueError("Fit/update ceilings must be integer counts")
    if receipt["maximum_gpu_hours"] * receipt["approved_hourly_rate_usd"] + receipt["non_gpu_reserved_usd"] > receipt["maximum_total_usd"]:
        raise ValueError("Worst-case budget exceeds approved total")
    deadline = datetime.fromisoformat(receipt.get("expires_at_utc", receipt.get("deadline_utc", "")))
    if deadline.tzinfo is None or current >= deadline:
        raise ValueError("Machine budget has expired")
    started = datetime.fromisoformat(receipt.get("authorized_at_utc", receipt.get("started_at_utc", "")))
    if started.tzinfo is None or started > current or (deadline - started).total_seconds() > receipt["maximum_gpu_hours"] * 3600:
        raise ValueError("Machine deadline exceeds the approved lifetime")
    return receipt


class PersistentBudget:
    def __init__(self, job, receipt):
        self.job = Path(job)
        self.receipt = receipt
        self.path = self.job / "source/budget_ledger.json"
        self.state = read_json(self.path) if self.path.exists() else {
            "actual_neural_fits_started": 0, "actual_neural_fits_completed": 0,
            "optimizer_updates": 0, "target_fits": 0, "target_predictions_computed": False}
        for key in ("actual_neural_fits_started", "actual_neural_fits_completed", "optimizer_updates"):
            if type(self.state.get(key)) is not int or self.state[key] < 0:
                raise ValueError("Persistent source counters must be nonnegative integers")
        if self.state["actual_neural_fits_completed"] > self.state["actual_neural_fits_started"]:
            raise ValueError("Completed source fits exceed started fits")
        if self.state.get("target_fits") != 0 or self.state.get("target_predictions_computed") is not False:
            raise ValueError("Source budget ledger crosses target boundary")
        self.guard()

    def guard(self):
        deadline = datetime.fromisoformat(self.receipt.get("expires_at_utc", self.receipt.get("deadline_utc", "")))
        if datetime.now(timezone.utc) >= deadline:
            raise RuntimeError("Approved machine deadline reached; worker stop does not stop billing")
        if self.state["actual_neural_fits_started"] > self.receipt["maximum_neural_fits"] or self.state["optimizer_updates"] > self.receipt["maximum_optimizer_updates"]:
            raise RuntimeError("Saved source counters exceed approved budget")

    def start_fit(self):
        self.guard()
        if self.state["actual_neural_fits_started"] >= self.receipt["maximum_neural_fits"]:
            raise RuntimeError("Real neural fit ceiling exhausted")
        self.state["actual_neural_fits_started"] += 1
        self.save()

    def before_update(self):
        self.guard()
        if self.state["optimizer_updates"] >= self.receipt["maximum_optimizer_updates"]:
            raise RuntimeError("Optimizer update ceiling exhausted")

    def save(self):
        self.state["updated_at_utc"] = now()
        write_json(self.path, self.state)


def capture_rng():
    import numpy as np
    import torch
    numpy_state = np.random.get_state()
    safe_numpy = [numpy_state[0], numpy_state[1].tolist(), int(numpy_state[2]), int(numpy_state[3]), float(numpy_state[4])]
    return {"python": random.getstate(), "numpy": safe_numpy, "torch": torch.get_rng_state(),
            "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []}


def restore_rng(state):
    import numpy as np
    import torch
    random.setstate(state["python"])
    n = state["numpy"]
    np.random.set_state((n[0], np.asarray(n[1], dtype=np.uint32), n[2], n[3], n[4]))
    torch.set_rng_state(state["torch"].cpu())
    if torch.cuda.is_available():
        torch.cuda.set_rng_state_all([x.cpu() for x in state["cuda"]])


def recover_batch_state(path, config_sha, fit_identity):
    import torch
    path = Path(path)
    checkpoint = path / "resume_state.pt"
    if not checkpoint.exists():
        raise RuntimeError("Started fit has no committed resumable state; silent fresh restart is blocked")
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    if state["config_sha256"] != config_sha or state["fit_identity"] != fit_identity:
        raise ValueError("Resume state belongs to another frozen fit")
    intent_path = path / "update_intent.json"
    if intent_path.exists():
        intent = read_json(intent_path)
        # The durable checkpoint itself authenticates completion of this exact
        # update. A crash between commit and removing the intent is recoverable.
        if intent.get("fit_identity") == fit_identity and state["global_updates"] == intent.get("next_global_update"):
            intent_path.unlink()
        else:
            raise RuntimeError("Unresolved optimizer-update intent: no automatic restart or repeated update is allowed")
    return state


def verify_completed(path):
    receipt = read_json(Path(path) / "fit_receipt.json")
    if receipt.get("status") != "completed":
        raise ValueError("Source owner fit is not complete")
    for name, key in (("checkpoint.pt", "checkpoint_sha256"), ("source_curve.json", "curve_sha256"), ("partition.json", "partition_sha256")):
        if file_hash(Path(path) / name) != receipt[key]:
            raise ValueError("Completed source artifact changed")
    return receipt


def execute(job_dir, source_data_dir):
    import numpy as np
    import torch
    import fcntl
    job = Path(job_dir).resolve()
    job.mkdir(parents=True, exist_ok=True)
    from cloud_locks import local_lock
    with local_lock("source", job):
        return _execute_locked(job, Path(source_data_dir).resolve())


def _execute_locked(job, source_data_dir):
    import numpy as np
    import torch
    config = validate_config(read_json(CONFIG))
    data = read_json(job / "data_prepare_receipt.json")
    freeze = verify_freeze(job, required_execution_paths(job, data))
    runtime = runtime_identity()
    validate_runtime(runtime, read_json(job / "runtime_lock.json"))
    authorization = validate_budget(read_json(job / "budget_authorization.json"), runtime)
    validate_prepared_data(job, data, source_data_dir)
    from private_recovery import from_environment
    recovery = from_environment(job)
    output = job / "source"
    output.mkdir(parents=True, exist_ok=True)
    budget = PersistentBudget(job, authorization)
    saved_receipts = list(output.glob("**/fit_receipt.json"))
    if len(saved_receipts) != budget.state["actual_neural_fits_started"]:
        raise RuntimeError("A consumed fit ordinal has no authenticated receipt; automatic fresh fitting is blocked")
    budget.state["actual_neural_fits_completed"] = sum(read_json(p).get("status") == "completed" for p in saved_receipts)
    budget.save()
    arrays, records, audit = load_source19(source_data_dir, config)
    if canonical_hash(audit) != canonical_hash(data.get("source_input_audit")):
        raise ValueError("Actual source input audit differs from the publicly prepared source arrays")
    existing = output / "source19_input_audit.json"
    if existing.exists() and canonical_hash(read_json(existing)) != canonical_hash(audit):
        raise ValueError("Resumed source input provenance differs")
    write_json(existing, audit)
    write_json(output / "source_metadata.json", records)
    runtime.update(protocol_commit=freeze.get("commit_sha", freeze.get("protocol_commit")),
                   config_sha256=file_hash(CONFIG), executor_sha256=file_hash(__file__),
                   input_loader_sha256=file_hash(HERE / "formal_core_inputs.py"),
                   historical_input_loader_sha256=file_hash(LEGACY / "scripts/core_source_inputs.py"),
                   numerical_execution=numerical_identity(),
                   runtime_lock_sha256=file_hash(job / "runtime_lock.json"),
                   budget_authorization_sha256=file_hash(job / "budget_authorization.json"),
                   data_prepare_receipt_sha256=file_hash(job / "data_prepare_receipt.json"))
    write_json(output / "runtime_provenance.json", runtime)
    status = {"status": "source_fitting_exploratory", "target_fits": 0, "target_predictions_computed": False,
              "qualified_independent_confirmation": False, "nominal_final_cells_completed": 0, "checkpoint_aliases": 0}

    def save_status():
        status.update(budget.state)
        status["updated_at_utc"] = now()
        write_json(output / "source_status.json", status)

    save_status()
    recovery.snapshot("source_preflight")
    device = torch.device("cuda:0")
    y = torch.as_tensor([r["label_index"] for r in records], dtype=torch.long, device=device)
    config_sha = file_hash(CONFIG)

    def fit(name, x, train, validation, seed, epochs, path, kind):
        path.mkdir(parents=True, exist_ok=True)
        identity = {"architecture": name, "seed": seed, "epochs": epochs, "cell_kind": kind}
        receipt_path = path / "fit_receipt.json"
        if receipt_path.exists() and read_json(receipt_path).get("status") == "completed":
            verify_completed(path)
            return read_json(path / "source_curve.json")
        train_t = torch.as_tensor(train, dtype=torch.long, device=device)
        val_t = None if validation is None else torch.as_tensor(validation, dtype=torch.long, device=device)
        partition = {"train_records": [records[i] for i in train],
                     "validation_records": [] if validation is None else [records[i] for i in validation],
                     "validation_kind": "none_final_all_source" if validation is None else "heldout_source_participants"}
        if (path / "partition.json").exists() and read_json(path / "partition.json") != partition:
            raise ValueError("Resumed source partition differs")
        write_json(path / "partition.json", partition)
        seed_everything(seed)
        model = build_model(name, config["architecture"], device)
        optimizer = torch.optim.Adam(model.parameters(), lr=.001, weight_decay=0.)
        if receipt_path.exists():
            receipt = read_json(receipt_path)
            if receipt.get("status") != "started" or any(receipt.get(key) != value for key, value in identity.items()):
                raise ValueError("Fit receipt is not resumable")
            state = recover_batch_state(path, config_sha, identity)
            model.load_state_dict(state["model_state"])
            optimizer.load_state_dict(state["optimizer_state"])
            restore_rng(state["rng"])
            # A committed batch may precede the ledger write after a process
            # interruption; recover the same consumed update, never repeat it.
            if state["global_updates"] < budget.state["optimizer_updates"]:
                raise ValueError("Ledger is ahead of the committed active fit")
            budget.state["optimizer_updates"] = state["global_updates"]
            budget.save()
            curve = state["curve"]
            write_json(path / "source_curve.json", curve)
        else:
            if (path / "resume_state.pt").exists() or (path / "update_intent.json").exists():
                raise ValueError("Unowned resume artifacts cannot authorize a fresh fit")
            recovery.begin("consume_fit_ordinal", budget.state["actual_neural_fits_started"] + 1)
            budget.start_fit()
            receipt = {**identity, "status": "started", "fit_ordinal": budget.state["actual_neural_fits_started"],
                "started_at_utc": now(), "n_training_trials": len(train), "n_validation_trials": 0 if validation is None else len(validation),
                "partition_sha256": file_hash(path / "partition.json"), "configuration_sha256": config_sha,
                "training_input_sha256": array_hash(x[train_t].detach().cpu().numpy()),
                "training_labels_sha256": array_hash(y[train_t].detach().cpu().numpy()),
                "validation_input_sha256": None if val_t is None else array_hash(x[val_t].detach().cpu().numpy()),
                "validation_labels_sha256": None if val_t is None else array_hash(y[val_t].detach().cpu().numpy()),
                "target_fit": False, "new_real_neural_fit": True, "input_dtype": "float32",
                "model_accounting": compute_accounting(model, name, device),
                "model_structure_repr": repr(model), "actual_named_parameter_shapes": {k: list(p.shape) for k, p in model.named_parameters()}}
            write_json(receipt_path, receipt)
            curve = []
            state = {"config_sha256": config_sha, "fit_identity": identity, "model_state": model.state_dict(),
                "optimizer_state": optimizer.state_dict(), "rng": capture_rng(), "curve": [], "epoch": 1,
                "order": None, "batch_offset": 0, "epoch_ce_sum": 0., "fit_updates": 0,
                "global_updates": budget.state["optimizer_updates"], "active_seconds": 0.}
            atomic_torch_save(path / "resume_state.pt", state)
        save_status()
        recovery.snapshot("fit_initialized_or_restored")
        started = time.monotonic()
        active_before = state["active_seconds"]
        torch.cuda.reset_peak_memory_stats(device)
        for epoch in range(state["epoch"], epochs + 1):
            model.train()
            if state["order"] is None:
                order = train_t[torch.randperm(len(train_t), device=device)]
                state.update(order=order.detach().cpu(), batch_offset=0, epoch_ce_sum=0., epoch=epoch)
            else:
                order = state["order"].to(device)
            for offset in range(state["batch_offset"], len(order), 64):
                budget.before_update()
                recovery.begin("optimizer_update", budget.state["optimizer_updates"] + 1)
                batch = order[offset:offset + 64]
                write_json(path / "update_intent.json", {"fit_identity": identity, "epoch": epoch,
                    "batch_offset": offset, "next_global_update": budget.state["optimizer_updates"] + 1,
                    "status": "PENDING_UPDATE_CRASH_MUST_NOT_RESTART_SILENTLY"})
                optimizer.zero_grad(set_to_none=True)
                loss = torch.nn.functional.cross_entropy(model(x[batch]), y[batch])
                if not torch.isfinite(loss):
                    raise FloatingPointError("Nonfinite source training cross entropy")
                loss.backward()
                if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):
                    raise FloatingPointError("Nonfinite source gradient")
                optimizer.step()
                budget.state["optimizer_updates"] += 1
                state.update(model_state=model.state_dict(), optimizer_state=optimizer.state_dict(), rng=capture_rng(),
                    batch_offset=offset + len(batch), epoch_ce_sum=state["epoch_ce_sum"] + float(loss.detach()) * len(batch),
                    fit_updates=state["fit_updates"] + 1, global_updates=budget.state["optimizer_updates"], curve=curve,
                    active_seconds=active_before + time.monotonic() - started)
                atomic_torch_save(path / "resume_state.pt", state)
                (path / "update_intent.json").unlink()
                budget.save()
                recovery.snapshot("committed_batch")
            validation_ce = None if val_t is None else evaluate_source_ce(model, x, y, val_t, 64)
            curve.append({"epoch": epoch, "training_cross_entropy": state["epoch_ce_sum"] / len(train),
                          "validation_cross_entropy": validation_ce, "optimizer_updates": math.ceil(len(train) / 64)})
            state.update(epoch=epoch + 1, order=None, batch_offset=0, epoch_ce_sum=0., curve=curve,
                         model_state=model.state_dict(), optimizer_state=optimizer.state_dict(), rng=capture_rng(),
                         active_seconds=active_before + time.monotonic() - started)
            atomic_torch_save(path / "resume_state.pt", state)
            write_json(path / "source_curve.json", curve)
            save_status()
            recovery.snapshot("committed_epoch")
        torch.cuda.synchronize(device)
        checkpoint = path / "checkpoint.pt"
        atomic_torch_save(checkpoint, {"state_dict": model.state_dict(), "architecture": config["architecture"], "model": name,
                                     "seed": seed, "epochs": epochs, "config_sha256": config_sha})
        receipt.update(status="completed", completed_at_utc=now(), wall_seconds=active_before + time.monotonic() - started,
            optimizer_updates=state["fit_updates"], expected_optimizer_updates=math.ceil(len(train) / 64) * epochs,
            checkpoint_sha256=file_hash(checkpoint), model_state_sha256=state_hash(model),
            curve_sha256=file_hash(path / "source_curve.json"), peak_cuda_memory_allocated_bytes=torch.cuda.max_memory_allocated(device),
            actual_parameters=config["architecture"], optimizer={"name": "Adam", "learning_rate": .001,
                "weight_decay": 0., "batch_size": 64, "drop_last": False},
            resume_policy="atomic_completed_batch_state_and_rng; unresolved_update_intent_blocks_automatic_recovery")
        if receipt["optimizer_updates"] != receipt["expected_optimizer_updates"]:
            raise ValueError("Source minibatch update coverage differs")
        write_json(receipt_path, receipt)
        # Derive completion count from receipts so a crash after receipt commit
        # cannot result in either a missing completion or a repeated fit.
        budget.state["actual_neural_fits_completed"] = sum(read_json(p).get("status") == "completed" for p in output.glob("**/fit_receipt.json"))
        budget.save()
        save_status()
        recovery.snapshot("completed_fit")
        del optimizer, model
        return curve

    selections, final_cells = {}, []
    try:
        for name in ARCHITECTURES:
            values = arrays["broad"] if name == "BROAD_EEGNET" else np.stack([arrays["mu"], arrays["beta"]], axis=1)
            x = torch.from_numpy(values).to(device)
            curves = []
            for index, group in enumerate(config["source_validation_groups"], 1):
                train, val = source_partition(records, group)
                curves.append(fit(name, x, train, val, config["selection_seed"], 40,
                                  output / "inner" / name / f"fold_{index:02d}", "source_validation_trajectory"))
            selections[name] = select_epochs(curves, config["candidate_epochs"])
            write_json(output / "selected_epochs.json", selections)
            cells = schedule_cells(name, selections[name], config["final_seeds"])
            for cell in cells:
                path = output / "final" / cell["cell"]
                if cell["alias"]:
                    owner = verify_completed(output / "final" / cell["owner_cell"])
                    alias = {**cell, "new_real_neural_fit": False, "optimizer_updates": 0,
                             "owner_checkpoint_sha256": owner["checkpoint_sha256"], "owner_model_state_sha256": owner["model_state_sha256"]}
                    if (path / "alias_receipt.json").exists() and read_json(path / "alias_receipt.json") != alias:
                        raise ValueError("Checkpoint alias provenance differs")
                    write_json(path / "alias_receipt.json", alias)
                    status["checkpoint_aliases"] += 1
                else:
                    fit(name, x, list(range(len(records))), None, cell["seed"], cell["epochs"], path, "final_all_source")
                status["nominal_final_cells_completed"] += 1
                final_cells.append(cell)
                save_status()
            del x, values
        status["status"] = "source_grid_completed_pending_separate_validation_no_target_predictions"
        save_status()
        write_json(output / "source_completion_manifest.json", {**status, "nominal_inner_fits": 8,
            "nominal_final_cells": 18, "actual_new_neural_fits": budget.state["actual_neural_fits_completed"],
            "aliases": status["checkpoint_aliases"], "actual_optimizer_updates": budget.state["optimizer_updates"],
            "selected_epochs": selections, "final_cells": final_cells, "source_validation_passed": False,
            "protocol_commit": freeze.get("commit_sha", freeze.get("protocol_commit")),
            "external_experiment_completed": False, "target_scores_released": False})
        recovery.snapshot("source_completed")
        return output
    except Exception as error:
        status.update(status="FAILED_OR_BLOCKED", error_type=type(error).__name__, error_message=str(error))
        save_status()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-dir", type=Path)
    parser.add_argument("--source-data-dir", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"status": "DRY_RUN_NO_EEG_READ_NO_NEURAL_FITS", "target_fits": 0,
                          "target_predictions_computed": False, "qualified_independent_confirmation": False,
                          "nominal_source_neural_fits": 26, "optional_grouping_enabled": False}))
        return
    if args.job_dir is None or args.source_data_dir is None:
        parser.error("--execute requires --job-dir and --source-data-dir")
    print(json.dumps({"status": "SOURCE_ONLY_RETURNED_PENDING_SEPARATE_VALIDATION", "output": str(execute(args.job_dir, args.source_data_dir)),
                      "target_fits": 0, "target_predictions_computed": False}))


if __name__ == "__main__":
    main()
