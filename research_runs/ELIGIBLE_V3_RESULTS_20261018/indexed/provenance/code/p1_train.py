"""Fixed-update EEGNet trajectories with atomic, RNG-complete checkpoints.

No data download, target data access, or epoch selection takes place here.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import random
import tempfile
import time

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import numpy as np
import torch
from braindecode.models import EEGNet

from p1_common import atomic_json, canonical_hash, log, read_json, sha256_file


def configure_runtime(device):
    torch.set_num_threads(min(8, os.cpu_count() or 1))
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable. Use a GPU Pod with a compatible NVIDIA driver.")


def seed_all(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def build_model(config, device):
    a = config["architecture"]
    return EEGNet(n_chans=18, n_times=320, n_outputs=2, F1=a["F1"], D=a["D"],
                  F2=a["F2"], kernel_length=a["kernel_length"], drop_prob=a["drop_prob"]).to(device)


def logits(model, x, pipeline):
    if x.ndim != 4 or tuple(x.shape[1:]) != (3, 18, 320):
        raise ValueError("Expected input [batch, broad/mu/beta, 18 channels, 320 samples]")
    if pipeline == "BROAD":
        return model(x[:, 0])
    if pipeline == "MU_BETA_SHARED":
        n = x.shape[0]
        both = torch.cat((x[:, 1], x[:, 2]), dim=0)
        z = model(both)
        return (z[:n] + z[n:]) / 2
    raise ValueError(pipeline)


def model_hash(model):
    h = hashlib.sha256()
    for name, value in model.state_dict().items():
        x = value.detach().cpu().contiguous()
        h.update(name.encode())
        h.update(str((str(x.dtype), tuple(x.shape))).encode())
        h.update(x.numpy().tobytes())
    return h.hexdigest()


def predict(model, subject, pipeline, device, batch_size=128):
    if len(subject["y"]) == 0 or batch_size < 1:
        raise ValueError("Prediction requires nonempty trials and a positive batch size")
    model.eval()
    before = model_hash(model)
    out = []
    with torch.inference_mode():
        for start in range(0, len(subject["y"]), batch_size):
            x = torch.from_numpy(subject["X"][start:start+batch_size]).to(device)
            out.append(logits(model, x, pipeline).detach().cpu().numpy())
    if model_hash(model) != before:
        raise RuntimeError("Evaluation changed model weights or BatchNorm buffers")
    z = np.concatenate(out)
    if z.shape != (len(subject["y"]), 2) or not np.isfinite(z).all():
        raise RuntimeError("Invalid predictions")
    return z


def metrics_from_logits(y, z):
    y = np.asarray(y)
    zz = np.asarray(z, dtype=np.float64)
    if (y.ndim != 1 or not np.issubdtype(y.dtype, np.integer)
            or zz.shape != (len(y), 2) or not np.isfinite(zz).all()
            or set(np.unique(y).tolist()) != {0, 1}):
        raise ValueError("Metrics require finite two-class logits and integer binary labels")
    y = y.astype(np.int64, copy=False)
    pred = np.argmax(zz, axis=1)
    n0, n1 = int((y == 0).sum()), int((y == 1).sum())
    if not n0 or not n1:
        raise ValueError("Both classes are required for subject-wise metrics")
    recall0 = float((pred[y == 0] == 0).mean())
    recall1 = float((pred[y == 1] == 1).mean())
    # Stable log-sum-exp in binary64, not log of rounded probabilities.
    true_logits = zz[np.arange(len(y)), y]
    other_logits = zz[np.arange(len(y)), 1-y]
    ce = float(np.logaddexp(0.0, other_logits-true_logits).mean())
    if not np.isfinite(ce):
        raise ValueError("Cross entropy is nonfinite")
    return {"ce": ce, "ba": (recall0+recall1)/2, "min_recall": min(recall0, recall1),
            "recall_left": recall0, "recall_right": recall1, "n": len(y), "n_left": n0, "n_right": n1}


class HierarchicalSampler:
    """Equal datasets, then people, then classes; sampling with replacement."""
    def __init__(self, subjects, seed):
        if not subjects:
            raise ValueError("No source subjects to sample")
        self.subjects = subjects
        self.datasets = sorted({s["dataset"] for s in subjects.values()})
        if not set(self.datasets) <= {"bnci", "yang", "synthetic_bnci", "synthetic_yang"}:
            raise ValueError("An external dataset was passed to source training")
        self.people = {d: sorted(k for k, s in subjects.items() if s["dataset"] == d) for d in self.datasets}
        self.indices = {(k, c): np.flatnonzero(s["y"] == c) for k, s in subjects.items() for c in (0, 1)}
        if any(len(v) == 0 for v in self.indices.values()):
            raise ValueError("A source subject is missing a class")
        self.rng = np.random.default_rng(seed)

    def batch(self, size):
        if not isinstance(size, int) or isinstance(size, bool) or size < 1:
            raise ValueError("Batch size must be a positive integer")
        x = np.empty((size, 3, 18, 320), dtype=np.float32)
        y = np.empty(size, dtype=np.int64)
        for i in range(size):
            d = self.datasets[int(self.rng.integers(len(self.datasets)))]
            group = self.people[d]
            k = group[int(self.rng.integers(len(group)))]
            c = int(self.rng.integers(2))
            choices = self.indices[k, c]
            index = int(choices[int(self.rng.integers(len(choices)))])
            x[i], y[i] = self.subjects[k]["X"][index], c
        return torch.from_numpy(x), torch.from_numpy(y)


def capture_rng(sampler):
    return {"python": random.getstate(), "numpy": np.random.get_state(),
            "torch": torch.get_rng_state(), "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
            "sampler": sampler.rng.bit_generator.state}


def restore_rng(rng, sampler):
    random.setstate(rng["python"])
    np.random.set_state(rng["numpy"])
    torch.set_rng_state(rng["torch"].cpu())
    if rng["cuda"] is not None and torch.cuda.is_available():
        torch.cuda.set_rng_state_all([s.cpu() for s in rng["cuda"]])
    sampler.rng.bit_generator.state = rng["sampler"]


def save_checkpoint(folder, epoch, payload):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"epoch_{epoch:03d}.pt"
    fd, temporary = tempfile.mkstemp(prefix="checkpoint_", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "wb") as f:
            torch.save(payload, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    receipt = {"epoch": epoch, "path": path.name, "sha256": sha256_file(path), "contract_hash": payload["contract_hash"]}
    atomic_json(folder / f"epoch_{epoch:03d}.json", receipt)
    atomic_json(folder / "latest.json", receipt)
    return receipt


def load_checkpoint(folder, epoch=None, expected_contract=None):
    folder = Path(folder)
    pointer = folder / ("latest.json" if epoch is None else f"epoch_{epoch:03d}.json")
    receipt = read_json(pointer)
    path = folder / receipt["path"]
    if (receipt["path"] != f"epoch_{receipt['epoch']:03d}.pt"
            or (epoch is not None and receipt["epoch"] != epoch)
            or sha256_file(path) != receipt["sha256"]):
        raise RuntimeError("Checkpoint checksum/name mismatch")
    if expected_contract and receipt["contract_hash"] != expected_contract:
        raise RuntimeError("Resume configuration, data or code changed. Use a separate run directory.")
    # Only this program's locally written and SHA-verified checkpoints are loaded.
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if payload["contract_hash"] != receipt["contract_hash"] or payload["epoch"] != receipt["epoch"]:
        raise RuntimeError("Checkpoint contents disagree with the atomic receipt")
    if canonical_hash(payload["contract"]) != payload["contract_hash"]:
        raise RuntimeError("Checkpoint contract body differs from its hash")
    if payload["updates"] != payload["epoch"] * payload["contract"]["config"]["updates_per_epoch"]:
        raise RuntimeError("Checkpoint update count differs from the frozen budget")
    return payload, receipt


def train_trajectory(config, train_subjects, validation_subjects, folder, *, seed, pipeline,
                     source_level, fold, execution_identity, device="cuda", stop_after_epoch=None):
    if set(train_subjects) & set(validation_subjects):
        raise ValueError("Train/validation person overlap")
    if not train_subjects:
        raise ValueError("No source training people")
    allowed_sources = {"bnci", "yang", "synthetic_bnci", "synthetic_yang"}
    physical_sets = []
    for group in (train_subjects, validation_subjects):
        physical_ids = set()
        for key, person in group.items():
            if person.get("role") != "source" or person.get("dataset") not in allowed_sources:
                raise ValueError("Only registered source data may enter model fitting or epoch selection")
            identity = (person["dataset"], str(person.get("subject", key)))
            if identity in physical_ids:
                raise ValueError("Duplicate physical source person under different dictionary keys")
            physical_ids.add(identity)
            if tuple(person["X"].shape) != (len(person["y"]), 3, 18, 320):
                raise ValueError("Invalid source tensor shape")
        physical_sets.append(physical_ids)
    if physical_sets[0] & physical_sets[1]:
        raise ValueError("Train/validation physical person overlap, including aliases")
    if pipeline not in ("BROAD", "MU_BETA_SHARED"):
        raise ValueError("Unknown training pipeline")
    for field in ("epochs", "updates_per_epoch", "batch_size"):
        if not isinstance(config[field], int) or isinstance(config[field], bool) or config[field] < 1:
            raise ValueError(f"{field} must be a positive integer")
    if stop_after_epoch is not None and (not isinstance(stop_after_epoch, int) or stop_after_epoch < 1):
        raise ValueError("stop_after_epoch must be a positive integer")
    contract = {"config": config, "seed": seed, "pipeline": pipeline, "source_level": source_level,
                "fold": fold, "train": {k: s["input_sha256"] for k, s in train_subjects.items()},
                "validation": {k: s["input_sha256"] for k, s in validation_subjects.items()},
                "execution_identity": execution_identity}
    contract_hash = canonical_hash(contract)
    seed_all(seed)
    model = build_model(config, device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
    sampler = HierarchicalSampler(train_subjects, seed)
    folder = Path(folder)
    start_epoch = 0
    if (folder / "latest.json").exists():
        saved, _ = load_checkpoint(folder, expected_contract=contract_hash)
        model.load_state_dict(saved["model"])
        optimizer.load_state_dict(saved["optimizer"])
        # PyTorch maps parameter-shaped states to each parameter's device and
        # preserves Adam's scalar step placement. Moving every state tensor to
        # CUDA here also moves step and defeats the non-capturable Adam policy.
        restore_rng(saved["rng"], sampler)
        start_epoch = saved["epoch"]
        log(f"Resume {source_level}/{pipeline}/fold={fold}/seed={seed}, completed epoch={start_epoch}")
    limit = config["epochs"] if stop_after_epoch is None else min(stop_after_epoch, config["epochs"])
    last_receipt = None
    for epoch in range(start_epoch + 1, limit + 1):
        started = time.monotonic()
        model.train()
        losses = []
        for _ in range(config["updates_per_epoch"]):
            x, y = sampler.batch(config["batch_size"])
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = torch.nn.functional.cross_entropy(logits(model, x, pipeline), y)
            if not torch.isfinite(loss):
                raise RuntimeError("Non-finite training loss; no checkpoint marked complete")
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        if any(not torch.isfinite(value).all() for value in model.state_dict().values()
               if torch.is_floating_point(value)):
            raise RuntimeError("Non-finite model state; epoch is not marked complete")
        rows = []
        for key in sorted(validation_subjects):
            s = validation_subjects[key]
            z = predict(model, s, pipeline, device)
            rows.append({"source_level": source_level, "pipeline": pipeline, "fold": fold, "seed": seed,
                         "epoch": epoch, "dataset": s["dataset"], "subject": key,
                         **metrics_from_logits(s["y"], z)})
        payload = {"schema": 1, "contract_hash": contract_hash, "contract": contract,
                   "epoch": epoch, "updates": epoch * config["updates_per_epoch"],
                   "model": model.state_dict(), "optimizer": optimizer.state_dict(), "rng": capture_rng(sampler),
                   "validation_rows": rows, "training_mean_ce": float(np.mean(losses)),
                   "elapsed_epoch_s": time.monotonic()-started,
                   "parameter_count": sum(p.numel() for p in model.parameters())}
        last_receipt = save_checkpoint(folder, epoch, payload)
        log(f"{source_level}/{pipeline}/fold={fold}/seed={seed}: epoch {epoch}/{config['epochs']}, "
            f"train CE={np.mean(losses):.5f}, seconds={payload['elapsed_epoch_s']:.1f}")
    if limit == config["epochs"]:
        if last_receipt is None:
            _, last_receipt = load_checkpoint(folder, expected_contract=contract_hash)
        if last_receipt["epoch"] != config["epochs"]:
            raise RuntimeError("Trajectory did not reach the frozen training budget")
        atomic_json(folder / "complete.json", {**last_receipt, "complete": True,
                    "updates": config["epochs"]*config["updates_per_epoch"], "source_only": True})
    return contract_hash


def read_validation_curves(folder, epochs, expected_contract=None):
    rows = []
    for epoch in range(1, epochs+1):
        checkpoint, _ = load_checkpoint(folder, epoch, expected_contract=expected_contract)
        rows.extend(checkpoint["validation_rows"])
    return rows
