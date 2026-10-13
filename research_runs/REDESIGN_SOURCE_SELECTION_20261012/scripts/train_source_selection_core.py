#!/usr/bin/env python3
"""Prepare/train the new source-only core; default is a no-data dry run.

Real neural fits are blocked unless public code/protocol/runtime/data gates,
explicit bounded machine authorization and a live CUDA device all pass. This
runner never loads target EEG or computes target predictions. Source completion
does not mean the prospective external experiment is complete.
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
from urllib.parse import quote
from urllib.request import Request, urlopen
import uuid

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = STUDY.parents[1]
CONFIG = STUDY / "config/core_experiment_v1.json"
PREANALYSIS = STUDY / "evidence/core_neural_preanalysis_receipt.json"
RUNTIME_LOCK = STUDY / "evidence/core_runtime_lock.json"
DATA_GATE = STUDY / "evidence/core_data_gate.json"
AUTHORIZATION = STUDY / "evidence/gpu_execution_authorization.json"
PUBLIC_REPOSITORY = "jackzhu119/cross-subject-mi-eeg"
ARCHITECTURES = ("BROAD_EEGNET", "MU_BETA_SHARED")
SELECTORS = ("fixed20", "mean_loss", "mean_rank")
PACKAGES = ("torch", "torchaudio", "braindecode", "numpy", "scipy", "pandas", "mne", "scikit-learn", "skorch", "einops")


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"Required regular non-symlink gate absent: {path.name}")
    return json.loads(path.read_text())


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    tmp.replace(path)


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def validate_config(config):
    from core_source_inputs import check_processing
    check_processing(config)
    required = {"schema_version": 1, "experiment": "selection_reliability_core_v1", "source_dataset": "BNCI2014_001",
                "source_subjects": list(range(1, 10)), "source_population": "both_sessions_all_binary_hand_trials_include_provider_flags",
                "source_validation_groups": [[1, 2], [3, 4], [5, 6], [7, 8, 9]], "source_validation_group_weight": "equal_fold",
                "selection_seed": 20261012, "final_seeds": [20261013, 20261014, 20261015],
                "architectures": list(ARCHITECTURES), "selectors": list(SELECTORS), "fixed_epochs": 20,
                "candidate_epochs": list(range(1, 41)), "selection_loss": "validation_cross_entropy",
                "loss_rule": "earliest_argmin_equal_fold_mean_loss",
                "rank_rule": "earliest_argmin_equal_fold_mean_within_fold_average_tie_rank",
                "optimizer": "Adam", "learning_rate": .001, "weight_decay": 0., "batch_size": 64, "drop_last": False,
                "architecture": {"library": "braindecode", "model": "EEGNet", "n_chans": 19, "n_times": 320,
                                 "n_outputs": 2, "F1": 8, "D": 2, "F2": 16, "kernel_length": 64, "drop_prob": .25},
                "shared_training": "concatenate_two_fixed_views_in_batch_dimension_same_backbone_then_average_logits_before_CE",
                "BatchNorm_target_mode": "eval_no_target_updates", "target_fits": 0, "target_new_predictions": 0,
                "core_inner_fits": 8, "nominal_core_final_fits": 18, "nominal_core_neural_fits": 26,
                "optional_extra_grouping_enabled": False, "target_performance_used_for_design": False}
    for key, value in required.items():
        if canonical_hash(config.get(key)) != canonical_hash(value):
            raise ValueError(f"Core model or selection specification changed: {key}")
    return config


def public_source_bytes(revision, name):
    url = f"https://raw.githubusercontent.com/{PUBLIC_REPOSITORY}/{revision}/{quote(name, safe='/')}"
    with urlopen(Request(url, headers={"User-Agent": "source-core-preanalysis-verification"}), timeout=30) as response:
        if response.status != 200:
            raise ValueError("Public core preanalysis read-back did not return HTTP 200")
        return response.read()


def verify_public_preanalysis(config):
    receipt = read_json(PREANALYSIS)
    revision = receipt.get("protocol_commit", "")
    public = receipt.get("public_verification", {})
    if (not isinstance(revision, str) or len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision)
            or public.get("status") != "PASS" or public.get("commit_sha") != revision
            or public.get("repository") != PUBLIC_REPOSITORY or not public.get("branch")):
        raise ValueError("Public core protocol commit identity not verified")
    subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", revision, "HEAD"], check=True)
    required = [CONFIG, Path(__file__), HERE / "core_source_inputs.py", STUDY / "PROSPECTIVE_VALIDATION_PROTOCOL.md",
                STUDY / "STATISTICAL_ANALYSIS_PLAN.md", STUDY / "EXPERIMENT_EXECUTION_PLAN.md", RUNTIME_LOCK, DATA_GATE,
                ROOT / "research_runs/Q8-E001/results/source_files.json", ROOT / "src/mi_eeg/data/q15_context.py"]
    protected = receipt.get("protocol_files", {})
    qualified_data = verify_data_gate(config, read_json(DATA_GATE))
    # The raw-QC/author/roster judgments and their actual dependencies must be
    # the publicly committed ones, not a newly self-written PASS wrapper.
    required += qualified_data["required_paths"] + [HERE / "infer_selection_core.py", HERE / "check_dreyer_metadata.py",
                HERE / "acquire_dreyer_runs.py", HERE / "analyze_redesign_scores.py", STUDY / "DREYER_DATA_ACCESS_PLAN.json",
                STUDY / "evidence/dataset_sources/dreyer_nemar_manifest.txt"]
    required = sorted(set(required))
    for path in required:
        name = path.relative_to(ROOT).as_posix()
        expected = protected.get(name)
        if not expected or path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError(f"Core freeze omits or redirects dependency: {name}")
        committed = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{revision}:{name}"])
        if file_hash(path) != expected or hashlib.sha256(committed).hexdigest() != expected:
            raise ValueError(f"Local core dependency differs from committed freeze: {name}")
        if hashlib.sha256(public_source_bytes(revision, name)).hexdigest() != expected:
            raise ValueError(f"Public core dependency differs from freeze: {name}")
    return receipt


def verify_data_gate_envelope(config, gate):
    required = {"status": "PASS", "config_sha256": file_hash(CONFIG), "author_first_use_confirmation": True,
                "all_retained_target_files_verified": True, "complete_acquisition_run_coverage_verified": True,
                "native_event_semantics_verified": True, "physical_header_scale_verified": True,
                "genuine_channel_order_verified": True, "cross_version_event_conversion_verified": True,
                "raw_only_roster_frozen": True, "duplicate_identity_audit_passed": True,
                "target_predictions_computed": False, "target_fits": 0}
    for field, value in required.items():
        if type(gate.get(field)) is not type(value) or gate.get(field) != value:
            raise ValueError(f"Full cohort/first-use gate is incomplete: {field}")
    if gate.get("qualification") not in {"first_use_independent_cohort", "independent_operational_derivative_cohort"}:
        raise ValueError("Target data provenance qualification is missing")
    for field in ("roster_path", "adapter_path", "raw_audit_path"):
        name, expected = gate.get(field), gate.get(field.replace("_path", "_sha256"))
        if not isinstance(name, str) or not isinstance(expected, str) or len(expected) != 64:
            raise ValueError(f"Data gate omits authenticated artifact: {field}")
        path = (ROOT / name).resolve()
        if not path.is_relative_to(STUDY) or not path.is_file() or (ROOT / name).is_symlink() or file_hash(path) != expected:
            raise ValueError(f"Data gate artifact absent, redirected or modified: {field}")
    return gate


def verify_data_gate(config, gate):
    """Qualify actual author/QC/acquisition/event records before source fitting.

    Reuse the inference adapter's metadata-only full-data validation, not its
    checkpoint/inference gates. That verifier calls the envelope helper above,
    so no circular recursion or target EEG/model access occurs here.
    """
    verify_data_gate_envelope(config, gate)
    if canonical_hash(gate) != canonical_hash(read_json(DATA_GATE)):
        raise ValueError("Supplied source data gate differs from the actual required artifact")
    from infer_selection_core import verify_target_gate
    return verify_target_gate(config)


def runtime_versions():
    return {name: importlib.metadata.version(name) for name in PACKAGES}


def gpu_identity():
    import torch
    if not torch.cuda.is_available() or torch.cuda.device_count() < 1:
        raise ValueError("Real neural execution requires a live CUDA GPU; CPU scientific fits are blocked")
    properties = torch.cuda.get_device_properties(0)
    gpu_uuid = str(getattr(properties, "uuid", ""))
    if not gpu_uuid:
        raise ValueError("GPU UUID cannot be authenticated")
    probe = torch.ones(1, device="cuda")
    if float((probe * 2).item()) != 2.0:
        raise ValueError("Live GPU arithmetic preflight failed")
    return {"machine_hostname": socket.gethostname(), "gpu_uuid": gpu_uuid,
            "gpu_name": properties.name, "gpu_total_memory_bytes": properties.total_memory,
            "runtime_cuda": torch.version.cuda, "python": platform.python_version(), "packages": runtime_versions()}


def verify_runtime_lock(runtime, lock):
    if lock.get("status") != "FROZEN_BEFORE_SOURCE_FITS" or lock.get("packages") != runtime["packages"]:
        raise ValueError("Actual scientific packages do not match publicly frozen runtime")
    if lock.get("runtime_cuda") != runtime["runtime_cuda"] or lock.get("python") != runtime["python"]:
        raise ValueError("Python or CUDA runtime differs from public runtime freeze")
    if runtime["packages"]["braindecode"] != "1.5.1":
        raise ValueError("Configured architecture implementation requires braindecode 1.5.1")


def verify_authorization(receipt, runtime, current=None):
    current = current or datetime.now(timezone.utc)
    exact = {"schema_version": 1, "status": "AUTHORIZED", "scope": "core_source_training_v1",
             "authorization_kind": "explicit_author_approval", "config_sha256": file_hash(CONFIG),
             "machine_hostname": runtime["machine_hostname"], "gpu_uuid": runtime["gpu_uuid"],
             "target_fits_authorized": False, "target_predictions_authorized": False, "optional_grouping_authorized": False}
    for key, value in exact.items():
        if type(receipt.get(key)) is not type(value) or receipt.get(key) != value:
            raise ValueError(f"Explicit source GPU authorization missing or mismatched: {key}")
    limits = {"maximum_neural_fits": 26, "maximum_optimizer_updates": 34440,
              "maximum_gpu_hours": 8, "maximum_total_usd": 10, "approved_hourly_rate_usd": .75,
              "non_gpu_reserved_usd": 2}
    for key, ceiling in limits.items():
        value = receipt.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not (0 <= value <= ceiling):
            raise ValueError(f"Authorization exceeds or omits hard budget bound: {key}")
    for key in ("maximum_neural_fits", "maximum_optimizer_updates"):
        if type(receipt.get(key)) is not int:
            raise ValueError(f"Fit/update budget is an integer count: {key}")
    if receipt["maximum_neural_fits"] < 8 or receipt["maximum_optimizer_updates"] < 9840 or receipt["maximum_gpu_hours"] <= 0:
        raise ValueError("Authorized source budget cannot cover even the inner grid")
    if receipt["approved_hourly_rate_usd"] <= 0 or not receipt.get("author_approval_record"):
        raise ValueError("Actual quoted rate and author approval evidence are required")
    if receipt["maximum_gpu_hours"] * receipt["approved_hourly_rate_usd"] + receipt["non_gpu_reserved_usd"] > receipt["maximum_total_usd"]:
        raise ValueError("Worst-case allocated GPU and contingency exceeds authorized total")
    for key in ("authorized_at_utc", "expires_at_utc"):
        stamp = datetime.fromisoformat(receipt.get(key, ""))
        if stamp.tzinfo is None:
            raise ValueError("Authorization timestamps require a timezone")
        if key == "authorized_at_utc" and stamp > current or key == "expires_at_utc" and stamp <= current:
            raise ValueError("Source execution authorization is not currently valid")
    return receipt


class Budget:
    """Stop computation at the approved bound; this does not stop cloud billing."""
    def __init__(self, receipt, started_monotonic=None):
        self.receipt = receipt
        self.started = time.monotonic() if started_monotonic is None else started_monotonic
        self.fits_started = 0
        self.fits_completed = 0
        self.updates = 0

    def guard(self):
        elapsed = time.monotonic() - self.started
        cost_bound = elapsed / 3600 * self.receipt["approved_hourly_rate_usd"] + self.receipt["non_gpu_reserved_usd"]
        if elapsed > self.receipt["maximum_gpu_hours"] * 3600 or cost_bound > self.receipt["maximum_total_usd"]:
            raise RuntimeError("Authorized worker time/cost envelope exhausted; manual instance billing control still required")
        if datetime.now(timezone.utc) >= datetime.fromisoformat(self.receipt["expires_at_utc"]):
            raise RuntimeError("Authorization expired during source execution")

    def start_fit(self):
        self.guard()
        if self.fits_started >= self.receipt["maximum_neural_fits"]:
            raise RuntimeError("Authorized real fit ceiling exhausted")
        self.fits_started += 1

    def before_step(self):
        self.guard()
        if self.updates >= self.receipt["maximum_optimizer_updates"]:
            raise RuntimeError("Authorized optimizer-update ceiling exhausted")


def source_partition(records, validation_subjects):
    subjects = set(validation_subjects)
    if not subjects or not subjects.issubset(set(range(1, 10))):
        raise ValueError("Source validation group invalid")
    ids = [row["sample_id"] for row in records]
    if len(ids) != len(set(ids)) or any(row["subject"] not in range(1, 10) for row in records):
        raise ValueError("Only unique source-participant trial identities are allowed")
    train = [i for i, row in enumerate(records) if row["subject"] not in subjects]
    val = [i for i, row in enumerate(records) if row["subject"] in subjects]
    if not train or not val or set(train) & set(val):
        raise ValueError("Source holdout partition is empty or overlaps")
    for indices in (train, val):
        if {records[i]["label"] for i in indices} != {1, 2}:
            raise ValueError("Both source hand classes are required in each partition")
    return train, val


def select_epochs(curves, candidate_epochs):
    import numpy as np
    from scipy.stats import rankdata
    if len(curves) != 4 or candidate_epochs != list(range(1, 41)):
        raise ValueError("Selection requires the same four complete 1–40 source trajectories")
    values = []
    for rows in curves:
        if [row["epoch"] for row in rows] != candidate_epochs:
            raise ValueError("Source selection curve epochs are missing or reordered")
        ce = np.array([row["validation_cross_entropy"] for row in rows], dtype=float)
        if not np.isfinite(ce).all() or (ce < 0).any():
            raise ValueError("Invalid source validation CE")
        values.append(ce)
    matrix = np.stack(values)
    mean_loss = matrix.mean(axis=0)
    mean_rank = np.stack([rankdata(row, method="average") for row in matrix]).mean(axis=0)
    return {"fixed20": 20, "mean_loss": int(np.argmin(mean_loss)) + 1, "mean_rank": int(np.argmin(mean_rank)) + 1,
            "equal_fold_mean_loss": mean_loss.tolist(), "equal_fold_mean_average_tie_rank": mean_rank.tolist()}


def seed_everything(seed):
    import numpy as np
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False


def state_hash(model):
    from core_source_inputs import array_hash
    return canonical_hash({name: array_hash(value.detach().cpu().numpy()) for name, value in sorted(model.state_dict().items())})


def build_model(name, architecture, device):
    import torch
    from braindecode.models import EEGNet
    parameters = {key: value for key, value in architecture.items() if key not in {"library", "model"}}
    backbone = EEGNet(**parameters).to(device)
    if name == "BROAD_EEGNET":
        model = backbone
    elif name == "MU_BETA_SHARED":
        class SharedViews(torch.nn.Module):
            def __init__(self, base):
                super().__init__()
                self.backbone = base

            def forward(self, x):
                if x.ndim != 4 or tuple(x.shape[1:]) != (2, 19, 320):
                    raise ValueError("Shared input must be [trials,mu/beta,19,320]")
                return self.backbone(x.reshape(-1, 19, 320)).reshape(len(x), 2, 2).mean(dim=1)
        model = SharedViews(backbone).to(device)
    else:
        raise ValueError("Unknown fixed source architecture")
    model.eval()
    shape = (2, 19, 320) if name == "BROAD_EEGNET" else (2, 2, 19, 320)
    with torch.inference_mode():
        if tuple(model(torch.zeros(shape, device=device)).shape) != (2, 2):
            raise ValueError("Configured EEGNet output shape differs")
    return model


def compute_accounting(model, name, device):
    """Exact parameter count and explicitly partial convolution/linear MACs."""
    import torch
    macs = [0]
    def hook(module, inputs, output):
        if isinstance(module, (torch.nn.Conv1d, torch.nn.Conv2d)):
            kernel = math.prod(module.kernel_size)
            macs[0] += output.numel() * (module.in_channels // module.groups) * kernel
        elif isinstance(module, torch.nn.Linear):
            macs[0] += output.numel() * module.in_features
    handles = [module.register_forward_hook(hook) for module in model.modules()
               if isinstance(module, (torch.nn.Conv1d, torch.nn.Conv2d, torch.nn.Linear))]
    before = state_hash(model)
    model.eval()
    shape = (1, 19, 320) if name == "BROAD_EEGNET" else (1, 2, 19, 320)
    try:
        with torch.inference_mode():
            model(torch.zeros(shape, device=device))
    finally:
        for handle in handles:
            handle.remove()
    if before != state_hash(model):
        raise ValueError("Zero-input accounting updated learned state")
    return {"parameters": sum(p.numel() for p in model.parameters()),
            "trainable_parameters": sum(p.numel() for p in model.parameters() if p.requires_grad),
            "conv_linear_macs_per_trial": macs[0], "conv_linear_multiply_add_flops_per_trial": 2 * macs[0],
            "accounting_scope": "Conv1d/Conv2d/Linear only; excludes pooling/BN/activations/filtering/resampling and optimizer/backward",
            "input_views_per_trial": 1 if name == "BROAD_EEGNET" else 2, "state_unchanged_during_probe": True}


def train_one_epoch(model, optimizer, x, y, train_indices, batch_size, budget=None):
    import torch
    if len(train_indices) == 0 or batch_size <= 0:
        raise ValueError("Nonempty source training partition and batch are required")
    model.train()
    order = train_indices[torch.randperm(len(train_indices), device=train_indices.device)]
    ce_sum, steps = 0., 0
    for indices in order.split(batch_size):
        if budget is not None:
            budget.before_step()
        optimizer.zero_grad(set_to_none=True)
        logits = model(x[indices])
        loss = torch.nn.functional.cross_entropy(logits, y[indices])
        if not torch.isfinite(loss):
            raise FloatingPointError("Nonfinite source training CE")
        loss.backward()
        if any(parameter.grad is not None and not torch.isfinite(parameter.grad).all() for parameter in model.parameters()):
            raise FloatingPointError("Nonfinite source gradient; optimizer update not executed")
        optimizer.step()
        if budget is not None:
            budget.updates += 1
        ce_sum += float(loss.detach()) * len(indices)
        steps += 1
    return ce_sum / len(train_indices), steps


def evaluate_source_ce(model, x, y, indices, batch_size):
    import torch
    if len(indices) == 0:
        raise ValueError("Source validation cannot be empty")
    model.eval()
    before = state_hash(model)
    ce_sum = 0.
    with torch.inference_mode():
        for batch in indices.split(batch_size):
            loss = torch.nn.functional.cross_entropy(model(x[batch]), y[batch], reduction="sum")
            if not torch.isfinite(loss):
                raise FloatingPointError("Nonfinite source validation CE")
            ce_sum += float(loss)
    if before != state_hash(model):
        raise ValueError("Heldout source evaluation changed learned/BatchNorm state")
    return ce_sum / len(indices)


def schedule_cells(name, selection, final_seeds):
    """Nominal conditions share only truly identical architecture/seed/duration."""
    output = []
    owners = {}
    for selector in SELECTORS:
        for seed in final_seeds:
            epoch = selection[selector]
            key = (name, seed, epoch)
            cell = f"{name}/{selector}/seed_{seed}"
            owner = owners.setdefault(key, cell)
            output.append({"cell": cell, "architecture": name, "selector": selector, "seed": seed,
                           "epochs": epoch, "owner_cell": owner, "alias": cell != owner})
    return output


def execute(data_dir, output_dir=None):
    from core_source_inputs import array_hash, load_source19
    config = validate_config(read_json(CONFIG))
    preanalysis = verify_public_preanalysis(config)
    data_gate = verify_data_gate(config, read_json(DATA_GATE))
    runtime = gpu_identity()
    verify_runtime_lock(runtime, read_json(RUNTIME_LOCK))
    authorization = verify_authorization(read_json(AUTHORIZATION), runtime)
    budget = Budget(authorization)
    import numpy as np
    import torch
    device = torch.device("cuda:0")
    run_id = "source-core-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    output = Path(output_dir).resolve() if output_dir else STUDY / "results" / run_id
    if not output.is_relative_to(STUDY / "results") or output.exists():
        raise ValueError("New source job requires a fresh result directory inside this study")
    output.mkdir(parents=True)
    status = {"status": "source_raw_and_19channel_input_audit", "run_id": run_id,
              "actual_neural_fits_started": 0, "actual_neural_fits_completed": 0,
              "optimizer_updates": 0, "nominal_final_cells_completed": 0, "checkpoint_aliases": 0,
              "target_fits": 0, "target_predictions_computed": False, "external_experiment_completed": False,
              "updated_at_utc": now()}
    write_json(output / "source_status.json", status)
    def save_status():
        status.update(actual_neural_fits_started=budget.fits_started, actual_neural_fits_completed=budget.fits_completed,
                      optimizer_updates=budget.updates, updated_at_utc=now())
        write_json(output / "source_status.json", status)
    try:
        arrays, records, audit = load_source19(data_dir, config)
        write_json(output / "source19_input_audit.json", audit)
        with (output / "source_metadata.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader(); writer.writerows(records)
        runtime.update(protocol_commit=preanalysis["protocol_commit"], executor_sha256=file_hash(__file__),
                       input_loader_sha256=file_hash(HERE / "core_source_inputs.py"), config_sha256=file_hash(CONFIG),
                       authorization_sha256=file_hash(AUTHORIZATION), data_gate_sha256=file_hash(DATA_GATE),
                       runtime_lock_sha256=file_hash(RUNTIME_LOCK), source19_audit_sha256=file_hash(output / "source19_input_audit.json"))
        write_json(output / "runtime_provenance.json", runtime)
        y = torch.as_tensor([r["label_index"] for r in records], dtype=torch.long, device=device)
        all_curves, selections, final_cells = {}, {}, []
        def fit(name, x, train, validation, seed, epochs, path, cell_kind):
            path.mkdir(parents=True)
            train_t = torch.as_tensor(train, dtype=torch.long, device=device)
            val_t = None if validation is None else torch.as_tensor(validation, dtype=torch.long, device=device)
            partition = {"train_records": [records[i] for i in train],
                         "validation_records": [] if validation is None else [records[i] for i in validation],
                         "validation_kind": "none_final_all_source" if validation is None else "heldout_source_participants"}
            write_json(path / "partition.json", partition)
            receipt = {"status": "prepared_not_started", "cell_kind": cell_kind, "architecture": name, "seed": seed,
                       "epochs": epochs, "n_training_trials": len(train), "n_validation_trials": 0 if validation is None else len(validation),
                       "partition_sha256": file_hash(path / "partition.json"), "input_dtype": "float32",
                       "training_input_sha256": array_hash(x[train_t].detach().cpu().numpy()),
                       "training_labels_sha256": array_hash(y[train_t].detach().cpu().numpy()),
                       "validation_input_sha256": None if validation is None else array_hash(x[val_t].detach().cpu().numpy()),
                       "validation_labels_sha256": None if validation is None else array_hash(y[val_t].detach().cpu().numpy()),
                       "configuration_sha256": file_hash(CONFIG), "target_fit": False, "new_real_neural_fit": True}
            seed_everything(seed)
            model = build_model(name, config["architecture"], device)
            receipt["model_accounting"] = compute_accounting(model, name, device)
            receipt["model_structure_repr"] = repr(model)
            receipt["actual_named_parameter_shapes"] = {key: list(parameter.shape) for key, parameter in model.named_parameters()}
            optimizer = torch.optim.Adam(model.parameters(), lr=.001, weight_decay=0.)
            budget.start_fit()
            receipt.update(status="started", fit_ordinal=budget.fits_started, started_at_utc=now())
            write_json(path / "fit_receipt.json", receipt)
            save_status()
            torch.cuda.reset_peak_memory_stats(device)
            torch.cuda.synchronize(device); started = time.monotonic()
            curve, update_start = [], budget.updates
            for epoch in range(1, epochs + 1):
                training_ce, updates = train_one_epoch(model, optimizer, x, y, train_t, 64, budget)
                validation_ce = None if val_t is None else evaluate_source_ce(model, x, y, val_t, 64)
                curve.append({"epoch": epoch, "training_cross_entropy": training_ce,
                              "validation_cross_entropy": validation_ce, "optimizer_updates": updates})
                write_json(path / "source_curve.json", curve)
                save_status()
            torch.cuda.synchronize(device)
            checkpoint = path / "checkpoint.pt"
            torch.save({"state_dict": model.state_dict(), "architecture": config["architecture"], "model": name,
                        "seed": seed, "epochs": epochs, "config_sha256": file_hash(CONFIG)}, checkpoint)
            receipt.update(status="completed", completed_at_utc=now(), wall_seconds=time.monotonic() - started,
                           optimizer_updates=budget.updates - update_start, expected_optimizer_updates=math.ceil(len(train) / 64) * epochs,
                           peak_cuda_memory_allocated_bytes=torch.cuda.max_memory_allocated(device),
                           checkpoint_sha256=file_hash(checkpoint), model_state_sha256=state_hash(model),
                           curve_sha256=file_hash(path / "source_curve.json"), actual_parameters=config["architecture"],
                           optimizer={"name": "Adam", "learning_rate": .001, "weight_decay": 0., "batch_size": 64, "drop_last": False})
            if receipt["optimizer_updates"] != receipt["expected_optimizer_updates"]:
                raise ValueError("Optimizer update coverage does not match complete source minibatches")
            write_json(path / "fit_receipt.json", receipt)
            budget.fits_completed += 1
            save_status()
            del optimizer, model
            return curve
        for name in ARCHITECTURES:
            values = arrays["broad"] if name == "BROAD_EEGNET" else np.stack([arrays["mu"], arrays["beta"]], axis=1)
            x = torch.from_numpy(values).to(device)
            curves = []
            for index, group in enumerate(config["source_validation_groups"], 1):
                train, val = source_partition(records, group)
                curve = fit(name, x, train, val, config["selection_seed"], 40,
                            output / "inner" / name / f"fold_{index:02d}", "source_validation_trajectory")
                curves.append(curve)
            all_curves[name] = curves
            selection = select_epochs(curves, config["candidate_epochs"])
            selections[name] = selection
            write_json(output / "selected_epochs.json", selections)
            cells = schedule_cells(name, selection, config["final_seeds"])
            for cell in cells:
                path = output / "final" / cell["cell"]
                if cell["alias"]:
                    owner = output / "final" / cell["owner_cell"]
                    owner_receipt = read_json(owner / "fit_receipt.json")
                    if owner_receipt.get("status") != "completed" or file_hash(owner / "checkpoint.pt") != owner_receipt["checkpoint_sha256"]:
                        raise ValueError("Identical-schedule owner checkpoint not actually completed or altered")
                    path.mkdir(parents=True)
                    write_json(path / "alias_receipt.json", {**cell, "new_real_neural_fit": False,
                               "owner_checkpoint_sha256": owner_receipt["checkpoint_sha256"],
                               "owner_model_state_sha256": owner_receipt["model_state_sha256"], "optimizer_updates": 0})
                    status["checkpoint_aliases"] += 1
                else:
                    fit(name, x, list(range(len(records))), None, cell["seed"], cell["epochs"], path, "final_all_source")
                status["nominal_final_cells_completed"] += 1
                final_cells.append(cell)
                save_status()
            del x, values
        status["status"] = "source_grid_completed_pending_independent_validation_no_target_predictions"
        save_status()
        write_json(output / "source_completion_manifest.json", {"status": status["status"], "run_id": run_id,
                   "nominal_inner_fits": 8, "nominal_final_cells": 18, "actual_new_neural_fits": budget.fits_completed,
                   "aliases": status["checkpoint_aliases"], "actual_optimizer_updates": budget.updates,
                   "selected_epochs": selections, "final_cells": final_cells,
                   "target_fits": 0, "target_predictions_computed": False, "target_scores_released": False,
                   "independent_validation_passed": False, "external_experiment_completed": False,
                   "protocol_commit": preanalysis["protocol_commit"], "public_source_model_freeze_created": False,
                   "limits": ["Source models still require independent artifact/partition/curve/selection/update validation",
                              "Target adapter/roster/inference state require a separate committed freeze before target scoring",
                              "Worker budget guards cannot shut down the billable cloud instance"]})
        return output
    except Exception as error:
        status.update(status="FAILED_OR_BLOCKED", error_type=type(error).__name__, error_message=str(error))
        save_status()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--source-data-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({"status": "DRY_RUN_NO_EEG_READ_NO_NEURAL_FITS", "new_neural_fits": 0,
                          "target_fits": 0, "target_predictions_computed": False,
                          "nominal_source_neural_fits": 26, "default_gpu_authorization": False,
                          "required_gates": [str(path.relative_to(ROOT)) for path in (PREANALYSIS, RUNTIME_LOCK, DATA_GATE, AUTHORIZATION)],
                          "implementation_status": "software_candidate_real_source_gpu_execution_not_validated",
                          "external_experiment_completed": False}, indent=2))
        return
    if args.source_data_dir is None:
        parser.error("--execute requires the authenticated 18-file --source-data-dir")
    output = execute(args.source_data_dir, args.output_dir)
    print(json.dumps({"status": "source_only_worker_returned_pending_independent_validation", "output": str(output.relative_to(ROOT)),
                      "target_fits": 0, "target_predictions_computed": False}))


if __name__ == "__main__":
    main()
